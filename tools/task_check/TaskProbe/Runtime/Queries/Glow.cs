// lit and glow (contract section 3): whether something gives off light and how much, one reading over every way a
// build makes light (a Light, a mesh drawn with an emissive or unlit material, a live particle system), so a lamp lit by
// a Light and a lamp drawn by a glowing material read the same.
//
// A mesh renderer is read from its materials' properties when every material it draws with has a shader with the
// standard interface (an emissive `_EmissionColor` + `_EMISSION` keyword, or an unlit shader's `_BaseColor`/`_Color`)
// and no texture multiplies the colour read, MaterialPropertyBlock overrides included; else (a texture, a Shader Graph
// or a custom shader) it is rendered alone (DrawnRender.Glow), as the original renders a mesh whose material graph it
// can't evaluate whole: a texture may be an atlas whose part the mesh shows, or dark but for a spot. A live particle
// system is always read as rendered. Past the render budget a mesh reads the bound its properties give (a texture
// taken as white: "bound"); a particle system then has no value ("unread").
using System;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Rendering;

namespace TaskProbe
{
    /// <summary>lit and glow of one object or component, summed over its sources.</summary>
    public struct GlowReading
    {
        public const int KindLight = 1, KindEmissive = 2, KindUnlit = 4, KindEffect = 8;
        public const int ReadProps = 1, ReadRender = 2, ReadBound = 4, ReadUnread = 8;

        public bool Read;   // it was read (else lit and glow have no value)
        public bool Lit;
        public double Glow;
        public int Kinds;   // the kinds of source that are lit
        public int Reads;   // how its renderers were read

        public void Add(GlowReading other)
        {
            Read |= other.Read;
            Lit |= other.Lit;
            Glow += other.Glow;
            Kinds |= other.Kinds;
            Reads |= other.Reads;
        }

        /// <summary>"light,emissive,unlit,effect": the kinds lit, for logs.</summary>
        public string Sources()
        {
            var parts = new List<string>();
            if ((Kinds & KindLight) != 0) parts.Add("light");
            if ((Kinds & KindEmissive) != 0) parts.Add("emissive");
            if ((Kinds & KindUnlit) != 0) parts.Add("unlit");
            if ((Kinds & KindEffect) != 0) parts.Add("effect");
            return string.Join(",", parts);
        }

        /// <summary>"props,render,bound,unread": how its renderers were read, for logs; null with no renderer read.</summary>
        public string ReadAs()
        {
            if (Reads == 0) return null;
            var parts = new List<string>();
            if ((Reads & ReadProps) != 0) parts.Add("props");
            if ((Reads & ReadRender) != 0) parts.Add("render");
            if ((Reads & ReadBound) != 0) parts.Add("bound");
            if ((Reads & ReadUnread) != 0) parts.Add("unread");
            return string.Join(",", parts);
        }

        /// <summary>Puts lit / glow (as asked) and glow_sources / glow_read into a row.</summary>
        public void Fill(Dictionary<string, object> row, bool lit, bool glow)
        {
            var how = ReadAs();
            if (how != null) row["glow_read"] = how;  // for logs, never a threshold ("unread": no value, and why)
            if (!Read) return;
            if (lit) row["lit"] = Lit ? 1.0 : 0.0;
            if (glow) row["glow"] = Glow;
            row["glow_sources"] = Sources();  // for logs, never a threshold
        }
    }

    public static class Glow
    {
        const double Floor = 0.01;  // lit: a surface brighter than this (linear luminance), or a rendered pixel

        enum Face { None, Emissive, Unlit }

        static readonly int EmissionColor = Shader.PropertyToID("_EmissionColor");
        static readonly int EmissionMap = Shader.PropertyToID("_EmissionMap");
        static readonly int BaseColor = Shader.PropertyToID("_BaseColor");
        static readonly int ColorId = Shader.PropertyToID("_Color");
        static readonly int BaseMap = Shader.PropertyToID("_BaseMap");
        static readonly int MainTex = Shader.PropertyToID("_MainTex");

        static readonly ShaderTagId GraphTag = new ShaderTagId("ShaderGraphShader");
        static readonly Dictionary<int, Face> Faces = new Dictionary<int, Face>();  // by shader: its interface never changes
        static readonly Dictionary<int, GlowReading> Frame = new Dictionary<int, GlowReading>();
        static int frameOf = -1;
        static MaterialPropertyBlock blockAll, blockOne;

        static double Luminance(Color c) => Find.Luminance(c.r, c.g, c.b);

        // ---------------------------------------------------------------- what reads as a source

        /// <summary>One component as a source: a Light, a mesh renderer, a particle system (or its renderer); not read
        /// (Read false) for anything else.</summary>
        public static GlowReading Of(Component c)
        {
            var r = new GlowReading();
            if (c is Light light) AddLight(ref r, light);
            else if (c is MeshRenderer || c is SkinnedMeshRenderer) AddMesh(ref r, (Renderer)c);
#if TASKPROBE_PARTICLES
            else if (c is ParticleSystem ps) AddEffect(ref r, ps);
            else if (c is ParticleSystemRenderer psr && psr.TryGetComponent<ParticleSystem>(out var owner)) AddEffect(ref r, owner);
#endif
            return r;
        }

        /// <summary>An object's sources: its Lights, its mesh parts (Find.MeshParts) and its particle systems, itself
        /// and its descendants. An object with nothing that gives light reads 0; one with a source that couldn't be read
        /// has no value unless another source is lit.</summary>
        public static GlowReading OfObject(GameObject go)
        {
            var total = new GlowReading { Read = true };
            var unread = false;
            foreach (var light in go.GetComponentsInChildren<Light>(true)) AddLight(ref total, light);
            var parts = new List<Renderer>();
            Find.MeshParts(go, parts);
            foreach (var part in parts) unread |= !AddMesh(ref total, part);
#if TASKPROBE_PARTICLES
            foreach (var ps in go.GetComponentsInChildren<ParticleSystem>(true)) unread |= !AddEffect(ref total, ps);
#endif
            total.Read = total.Lit || !unread;
            return total;
        }

        /// <summary>A Light: glow its intensity times its colour's luminance (its colour temperature included when the
        /// project uses it, as URP lights with it).</summary>
        static void AddLight(ref GlowReading r, Light light)
        {
            r.Read = true;
            if (!Find.LightOn(light)) return;
            var colour = Find.Linear(light.color);
            if (GraphicsSettings.lightsUseColorTemperature && light.useColorTemperature)
                colour *= Mathf.CorrelatedColorTemperatureToRGB(light.colorTemperature);
            var amount = light.intensity * Luminance(colour);
            if (amount <= 0.0) return;
            r.Lit = true;
            r.Glow += amount;
            r.Kinds |= GlowReading.KindLight;
        }

        /// <summary>A mesh renderer, read once a frame (a select's has.lit and the fields share it); false when it
        /// couldn't be read.</summary>
        static bool AddMesh(ref GlowReading total, Renderer renderer)
        {
            if (frameOf != Time.frameCount)
            {
                frameOf = Time.frameCount;
                Frame.Clear();
            }
            var id = renderer.GetInstanceID();
            if (!Frame.TryGetValue(id, out var r)) Frame[id] = r = ReadMesh(renderer);
            total.Add(r);
            return r.Read;
        }

        /// <summary>A mesh as a source, lit when it is drawn and its light is above the floor; glow that light times a
        /// quarter of the surface of its own bounds box (m2), what a lamp that size gives every way. Every material reads
        /// exactly by its properties: the brightest material's luminance, as if it covered the whole mesh. Else (a
        /// texture, another shader) rendered alone without light: lit by its brightest pixel, glow by its luminance over
        /// the box summed and averaged over four views, which is the same amount for a box lit all over and less where
        /// only part of it glows. Past the render budget, the bound its properties give.</summary>
        static GlowReading ReadMesh(Renderer renderer)
        {
            var r = new GlowReading();
            // a mesh that isn't drawn gives no light, whatever its materials
            if (!Find.Drawn(renderer)) { r.Read = true; return r; }
            var materials = renderer.sharedMaterials;
            var read = materials.Length == 0;  // a material said how bright it can be
            var allRead = true;  // every material did
            var exact = true;    // and with no texture: the value, not a bound
            var allUnlit = materials.Length > 0;
            var best = 0.0;
            var bestUnlit = false;
            var blocks = renderer.HasPropertyBlock();
            for (var i = 0; i < materials.Length; i++)
            {
                var m = materials[i];
                if (m == null || m.shader == null) { read = true; continue; }  // an empty slot draws nothing
                var face = FaceOf(m.shader);
                allUnlit &= face == Face.Unlit;
                if (face == Face.None) { exact = allRead = false; continue; }
                read = true;
                MaterialPropertyBlock one = null, all = null;
                if (blocks)
                {
                    blockOne ??= new MaterialPropertyBlock();
                    blockAll ??= new MaterialPropertyBlock();
                    renderer.GetPropertyBlock(blockOne, i);
                    renderer.GetPropertyBlock(blockAll);
                    one = blockOne.isEmpty ? null : blockOne;
                    all = blockAll.isEmpty ? null : blockAll;
                }
                var l = MaterialLight(m, face, one, all, out var textured);
                exact &= !textured;
                if (l > best)
                {
                    best = l;
                    bestUnlit = face == Face.Unlit;
                }
            }
            // a bound at or under the floor is dark whatever its textures are: nothing to render
            if (!exact && !(allRead && best <= Floor))
            {
                var seen = Render(renderer);
                if (seen.Ok)
                {
                    r.Read = true;
                    r.Reads |= GlowReading.ReadRender;
                    if (seen.Brightest > Floor)
                    {
                        r.Lit = true;
                        r.Glow = seen.Glow;
                        r.Kinds |= allUnlit ? GlowReading.KindUnlit : GlowReading.KindEmissive;
                    }
                    return r;
                }
            }
            if (!read)
            {
                r.Reads |= GlowReading.ReadUnread;
                return r;
            }
            r.Read = true;
            r.Reads |= exact ? GlowReading.ReadProps : GlowReading.ReadBound;
            if (best <= Floor) return r;
            r.Lit = true;
            r.Glow = best * QuarterSurface(renderer);
            r.Kinds |= bestUnlit ? GlowReading.KindUnlit : GlowReading.KindEmissive;
            return r;
        }

#if TASKPROBE_PARTICLES
        /// <summary>A particle system: dark unless it is live and its renderer drawn; then as rendered. False when it
        /// couldn't be read.</summary>
        static bool AddEffect(ref GlowReading total, ParticleSystem ps)
        {
            var renderer = ps.GetComponent<ParticleSystemRenderer>();
            if (renderer == null || !Find.Drawn(renderer) || !Effects.Live(ps)) { total.Read = true; return true; }
            var seen = Render(renderer);
            if (!seen.Ok) { total.Reads |= GlowReading.ReadUnread; return false; }
            total.Read = true;
            total.Reads |= GlowReading.ReadRender;
            if (seen.Brightest > Floor)
            {
                total.Lit = true;
                total.Glow += seen.Glow;
                total.Kinds |= GlowReading.KindEffect;
            }
            return true;
        }
#endif

        static RenderedGlow Render(Renderer renderer)
        {
            try { return DrawnRender.Glow(renderer); }
            catch (Exception e)
            {
                // the same line whichever renderer it was; which one, and the exception, in probe.log
                Probe.Active?.Error("lit/glow: a render failed (the exception is in probe.log)");
                Probe.Log("lit/glow: rendering " + renderer.name + " failed: " + e);
                return new RenderedGlow();
            }
        }

        /// <summary>A quarter of the surface of a mesh's own bounds box (m2): its local bounds scaled with it, a skinned
        /// mesh's in its root bone's frame (where its local bounds are, as the render frames it).</summary>
        static double QuarterSurface(Renderer renderer)
        {
            var space = renderer is SkinnedMeshRenderer s && s.rootBone != null ? s.rootBone : renderer.transform;
            var size = Vector3.Scale(renderer.localBounds.size, space.lossyScale);
            double x = Mathf.Abs(size.x), y = Mathf.Abs(size.y), z = Mathf.Abs(size.z);
            return 2.0 * (x * y + y * z + z * x) / 4.0;
        }

        // ---------------------------------------------------------------- material properties

        /// <summary>Which interface a shader has, by its properties and keywords alone (never by their values):
        /// an unlit shader (named so, with a base colour), else an emissive one (`_EmissionColor` and an `_EMISSION`
        /// keyword), else none (a Shader Graph or custom shader: read as rendered).</summary>
        static Face FaceOf(Shader shader)
        {
            var id = shader.GetInstanceID();
            if (Faces.TryGetValue(id, out var face)) return face;
            face = Face.None;
            var name = shader.name ?? "";
            // a Shader Graph's properties are its author's: _BaseColor there says nothing of what it draws. Its name is
            // whatever path its author gave it ("Unlit/Lamp"), so it is known by the tag Shader Graph writes
            var graph = name.StartsWith("Shader Graphs/", StringComparison.Ordinal) ||
                        (shader.subshaderCount > 0 && shader.FindSubshaderTagValue(0, GraphTag).name == "true");
            if (!graph && name.IndexOf("unlit", StringComparison.OrdinalIgnoreCase) >= 0 &&
                (shader.FindPropertyIndex("_BaseColor") >= 0 || shader.FindPropertyIndex("_Color") >= 0))
                face = Face.Unlit;
            else if (!graph && shader.FindPropertyIndex("_EmissionColor") >= 0 && shader.keywordSpace.FindKeyword("_EMISSION").isValid)
                face = Face.Emissive;
            Faces[id] = face;
            return face;
        }

        /// <summary>The luminance a material gives off by its properties, in linear (as the shader gets the colour);
        /// `textured`: a texture multiplies it, so it is a bound (the texture taken as white).</summary>
        static double MaterialLight(Material m, Face face, MaterialPropertyBlock one, MaterialPropertyBlock all, out bool textured)
        {
            textured = false;
            if (face == Face.Emissive)
            {
                // emission off (no _EMISSION keyword) draws none, whatever its colour or map
                if (!m.IsKeywordEnabled("_EMISSION")) return 0.0;
                textured = TextureOf(m, one, all, EmissionMap, EmissionMap) != null;
                return Luminance(Find.Linear(ColourOf(m, one, all, EmissionColor, EmissionColor)));
            }
            textured = TextureOf(m, one, all, BaseMap, MainTex) != null;
            return Luminance(Find.Linear(ColourOf(m, one, all, BaseColor, ColorId)));
        }

        static Color ColourOf(Material m, MaterialPropertyBlock one, MaterialPropertyBlock all, int id, int fallback)
        {
            foreach (var block in new[] { one, all })
            {
                if (block == null) continue;
                if (block.HasColor(id)) return block.GetColor(id);
                if (block.HasVector(id)) return block.GetVector(id);
                if (id != fallback && block.HasColor(fallback)) return block.GetColor(fallback);
            }
            if (m.HasProperty(id)) return m.GetColor(id);
            if (m.HasProperty(fallback)) return m.GetColor(fallback);
            return Color.white;
        }

        static Texture TextureOf(Material m, MaterialPropertyBlock one, MaterialPropertyBlock all, int id, int fallback)
        {
            foreach (var block in new[] { one, all })
            {
                if (block == null) continue;
                if (block.HasTexture(id)) return block.GetTexture(id);
                if (id != fallback && block.HasTexture(fallback)) return block.GetTexture(fallback);
            }
            if (m.HasProperty(id) && m.GetTexture(id) != null) return m.GetTexture(id);
            if (id != fallback && m.HasProperty(fallback)) return m.GetTexture(fallback);
            return null;
        }
    }

    /// <summary>Live effects (a components select's `effect`): a ParticleSystem that is alive (playing or holding
    /// particles), a VisualEffect holding particles, an enabled DecalProjector, a TrailRenderer drawing points. The VFX
    /// Graph and URP decals are read by reflection, so the probe needs neither package.</summary>
    public static class Effects
    {
        static readonly string[] Names = { "ParticleSystem", "TrailRenderer", "UnityEngine.VFX.VisualEffect", "UnityEngine.Rendering.Universal.DecalProjector" };

        /// <summary>The component types an effect can be, those this build has.</summary>
        public static IEnumerable<Type> Types()
        {
            foreach (var name in Names)
            {
                var t = Reflect.TypeNamed(name);
                if (t != null && typeof(Component).IsAssignableFrom(t)) yield return t;
            }
        }

        public static bool Live(Component c)
        {
            if (c == null || !c.gameObject.activeInHierarchy) return false;
#if TASKPROBE_PARTICLES
            if (c is ParticleSystem ps) return ps.isPlaying || ps.particleCount > 0;
#endif
            if (c is TrailRenderer trail) return trail.enabled && trail.positionCount > 0;
            var type = c.GetType();
            if (Reflect.IsA(type, "VisualEffect"))
            {
                if (c is Behaviour b && !b.enabled) return false;
                var alive = Reflect.Get(c, "aliveParticleCount");
                return alive != null && Convert.ToDouble(alive) > 0;
            }
            if (Reflect.IsA(type, "DecalProjector")) return !(c is Behaviour d) || d.enabled;
            return false;
        }
    }
}
