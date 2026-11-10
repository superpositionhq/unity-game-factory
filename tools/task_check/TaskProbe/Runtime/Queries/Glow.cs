// lit and glow (contract section 3): whether something gives off light and how much, one reading over every way a
// build makes light (a Light, a part drawn with an emissive or unlit material, a live effect), so a lamp lit by a
// Light and a lamp drawn by a glowing material read the same.
//
// A mesh renderer is read from its materials' properties when every material it draws with has a shader with the
// standard interface (an emissive `_EmissionColor` + `_EMISSION` keyword, or an unlit shader's `_BaseColor`/`_Color`)
// and no texture multiplies the colour read, MaterialPropertyBlock overrides included; else (a texture, a Shader Graph
// or a custom shader) it is rendered alone (DrawnRender.Glow), as the original renders a mesh whose material graph it
// can't evaluate whole: a texture may be an atlas whose part the mesh shows, or dark but for a spot. Any other part
// (a sprite, a line) and a live effect (a particle system, a trail, a visual effect) are always read as rendered: what
// they draw is their own (a sprite, vertex colours), not their material's. Past the render budget a mesh reads the
// bound its properties give (a texture taken as white: "bound"); anything else then has no value ("unread").
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

        /// <summary>lit or glow; null when it wasn't read.</summary>
        public object Field(string f)
        {
            if (!Read) return null;
            return f == "lit" ? Lit ? 1.0 : 0.0 : (object)Glow;
        }

        /// <summary>glow_sources (the kinds lit: "light,emissive,unlit,effect") and glow_read (how its renderers were read:
        /// "props,render,bound,unread"; "unread": no value, and why), for logs, never a threshold.</summary>
        public void Note(Dictionary<string, object> row)
        {
            if (Read)
            {
                var kinds = new List<string>();
                if ((Kinds & KindLight) != 0) kinds.Add("light");
                if ((Kinds & KindEmissive) != 0) kinds.Add("emissive");
                if ((Kinds & KindUnlit) != 0) kinds.Add("unlit");
                if ((Kinds & KindEffect) != 0) kinds.Add("effect");
                row["glow_sources"] = string.Join(",", kinds);
            }
            if (Reads == 0) return;
            var reads = new List<string>();
            if ((Reads & ReadProps) != 0) reads.Add("props");
            if ((Reads & ReadRender) != 0) reads.Add("render");
            if ((Reads & ReadBound) != 0) reads.Add("bound");
            if ((Reads & ReadUnread) != 0) reads.Add("unread");
            row["glow_read"] = string.Join(",", reads);
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
        static readonly Dictionary<int, GlowReading> Seen = new Dictionary<int, GlowReading>();  // each part once a pass
        static int seenStamp = -1;
        static MaterialPropertyBlock blockAll, blockOne;

        static double Luminance(Color c) => Find.Luminance(c.r, c.g, c.b);

        // ---------------------------------------------------------------- what reads as a source

        /// <summary>One component as a source: a Light, a renderer that draws a shape (a mesh, sprite or line), an effect
        /// (a particle system, a trail, a visual effect, or its renderer); not read (Read false) for anything else.</summary>
        public static GlowReading Of(Component c)
        {
            var r = new GlowReading();
            if (c is Light light) AddLight(ref r, light);
            else if (Effects.Drawn(c, out var effect, out var drawn)) AddEffect(ref r, effect, drawn);
            else if (c is Renderer part && !(part is SpriteMask)) AddPart(ref r, part);
            return r;
        }

        /// <summary>An object's sources: its Lights, its parts (ObjectRead.Parts) and its effects, itself and its
        /// descendants. An object with nothing that gives light reads 0; one with a source that couldn't be read has no
        /// value unless another source is lit.</summary>
        public static GlowReading OfObject(GameObject go, List<Renderer> parts)
        {
            var total = new GlowReading { Read = true };
            var unread = false;
            foreach (var light in go.GetComponentsInChildren<Light>(true)) AddLight(ref total, light);
            foreach (var part in parts) unread |= !AddPart(ref total, part);
            foreach (var c in Effects.In(go))
                if (Effects.Drawn(c, out var effect, out var drawn)) unread |= !AddEffect(ref total, effect, drawn);
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

        /// <summary>A part, read once a pass of the probe (the samples' has.lit and fields share it; an input's select,
        /// before the game's scripts of that frame, reads it anew); false when it couldn't be read.</summary>
        static bool AddPart(ref GlowReading total, Renderer renderer)
        {
            if (seenStamp != Probe.Stamp)
            {
                seenStamp = Probe.Stamp;
                Seen.Clear();
            }
            var id = renderer.GetInstanceID();
            if (!Seen.TryGetValue(id, out var r)) Seen[id] = r = ReadPart(renderer);
            total.Add(r);
            return r.Read;
        }

        /// <summary>A part as a source, lit when it is drawn and its light is above the floor; glow that light times a
        /// quarter of the surface of its own bounds box (m2), what a lamp that size gives every way. A mesh whose every
        /// material reads exactly by its properties: the brightest material's luminance, as if it covered the whole mesh.
        /// Else (a texture, another shader; and any part but a mesh) rendered alone without light: lit by its brightest
        /// pixel, glow by its luminance over the box summed and averaged over four views, which is the same amount for a
        /// box lit all over and less where only part of it glows. Past the render budget, a mesh's bound.</summary>
        static GlowReading ReadPart(Renderer renderer)
        {
            var r = new GlowReading();
            // a part that isn't drawn gives no light, whatever its materials
            if (!Find.Drawn(renderer)) { r.Read = true; return r; }
            var mesh = renderer is MeshRenderer || renderer is SkinnedMeshRenderer;
            var materials = renderer.sharedMaterials;
            var read = materials.Length == 0;  // a material said how bright it can be
            var allRead = mesh;  // every material did (a sprite's or a line's light is its own, not its material's)
            var exact = mesh;    // and with no texture: the value, not a bound
            var allUnlit = materials.Length > 0;
            var best = 0.0;
            var bestUnlit = false;
            var blocks = mesh && renderer.HasPropertyBlock();
            for (var i = 0; i < materials.Length; i++)
            {
                var m = materials[i];
                if (m == null || m.shader == null) { read = true; continue; }  // an empty slot draws nothing
                var face = FaceOf(m.shader);
                allUnlit &= face == Face.Unlit;
                if (!mesh || face == Face.None) { exact = allRead = false; continue; }
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

        /// <summary>An effect: dark unless it is live and its renderer drawn; then rendered alone as a part is (its world
        /// box), lit by its brightest pixel. False when it couldn't be read.</summary>
        static bool AddEffect(ref GlowReading total, Component effect, Renderer renderer)
        {
            if (renderer == null || !Find.Drawn(renderer) || !Effects.Live(effect)) { total.Read = true; return true; }
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

        static RenderedGlow Render(Renderer renderer)
        {
            try { return DrawnRender.Glow(renderer); }
            catch (Exception e)
            {
                // the same line whichever renderer it was; which one in probe.log, the exception with it once
                Probe.Log("lit/glow: rendering " + renderer.name + " failed");
                Probe.Active?.Failed("lit/glow: {0} in a render", e);
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

    /// <summary>Live effects (a components select's `effect`, and lit / glow): a ParticleSystem that is alive (playing or
    /// holding particles), a VisualEffect holding particles, an enabled DecalProjector, a TrailRenderer drawing points.
    /// The VFX Graph and URP decals are read by name, so the probe references neither.</summary>
    public static class Effects
    {
        static readonly string[] Names = { "ParticleSystem", "TrailRenderer", "UnityEngine.VFX.VisualEffect", "UnityEngine.Rendering.Universal.DecalProjector" };
        static readonly Type VisualEffect = Reflect.TypeNamed("UnityEngine.VFX.VisualEffect");

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

        /// <summary>Whether a renderer is an effect's own (a particle system's, a trail, a visual effect's).</summary>
        public static bool IsRenderer(Renderer r)
        {
#if TASKPROBE_PARTICLES
            if (r is ParticleSystemRenderer) return true;
#endif
            return r is TrailRenderer || r.GetType().Name == "VFXRenderer";
        }

        /// <summary>An effect that draws light (lit, glow) and the renderer that draws it, from either of the two: a
        /// ParticleSystem or its renderer, a TrailRenderer, a VisualEffect or its renderer. False for anything else (a
        /// decal is no source).</summary>
        public static bool Drawn(Component c, out Component effect, out Renderer renderer)
        {
            effect = null;
            renderer = null;
#if TASKPROBE_PARTICLES
            if (c is ParticleSystem ps) { effect = ps; renderer = ps.GetComponent<ParticleSystemRenderer>(); return true; }
            if (c is ParticleSystemRenderer psr) { effect = psr.GetComponent<ParticleSystem>(); renderer = psr; return effect != null; }
#endif
            if (c is TrailRenderer trail) { effect = renderer = trail; return true; }
            if (VisualEffect == null) return false;
            if (VisualEffect.IsInstanceOfType(c)) { effect = c; renderer = c.GetComponent<Renderer>(); return true; }
            if (c is Renderer r && r.GetType().Name == "VFXRenderer") { effect = c.GetComponent(VisualEffect); renderer = r; return effect != null; }
            return false;
        }

        /// <summary>The effects that draw light in an object and its descendants (inactive ones too: they read dark).</summary>
        public static IEnumerable<Component> In(GameObject go)
        {
#if TASKPROBE_PARTICLES
            foreach (var ps in go.GetComponentsInChildren<ParticleSystem>(true)) yield return ps;
#endif
            foreach (var trail in go.GetComponentsInChildren<TrailRenderer>(true)) yield return trail;
            if (VisualEffect == null) yield break;
            foreach (var vfx in go.GetComponentsInChildren(VisualEffect, true)) yield return vfx;
        }
    }
}
