// lit and glow (contract section 3): whether something gives off light and how much, one reading over every way a
// build makes light (a Light, a mesh drawn with an emissive or unlit material, a live particle system), so a lamp lit by
// a Light and a lamp drawn by a glowing material read the same.
//
// A mesh renderer is read from its material properties when every material it draws with has a shader with the
// standard interface (an emissive `_EmissionColor` + `_EMISSION` keyword, or an unlit shader's `_BaseColor`/`_Color`),
// MaterialPropertyBlock overrides included; else as rendered, through Hooks.GlowRender (another family's renderer).
// A live particle system is always read as rendered. Without the hook those read no value and say "unread".
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
        public const int ReadProps = 1, ReadRender = 2, ReadUnread = 4;

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

        /// <summary>"props,render,unread": how its renderers were read, for logs; null with no renderer read.</summary>
        public string ReadAs()
        {
            if (Reads == 0) return null;
            var parts = new List<string>();
            if ((Reads & ReadProps) != 0) parts.Add("props");
            if ((Reads & ReadRender) != 0) parts.Add("render");
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
        /// <summary>lit: an emissive surface brighter than this (linear luminance), or a rendered pixel.</summary>
        public const double Floor = 0.01;

        enum Face { None, Emissive, Unlit }

        static readonly int EmissionColor = Shader.PropertyToID("_EmissionColor");
        static readonly int EmissionMap = Shader.PropertyToID("_EmissionMap");
        static readonly int BaseColor = Shader.PropertyToID("_BaseColor");
        static readonly int ColorId = Shader.PropertyToID("_Color");
        static readonly int BaseMap = Shader.PropertyToID("_BaseMap");
        static readonly int MainTex = Shader.PropertyToID("_MainTex");

        static readonly Dictionary<int, Face> Faces = new Dictionary<int, Face>();
        static readonly Dictionary<int, KeyValuePair<uint, Color>> Means = new Dictionary<int, KeyValuePair<uint, Color>>();
        static readonly Dictionary<int, GlowReading> Frame = new Dictionary<int, GlowReading>();
        static int frameOf = -1;
        static MaterialPropertyBlock blockAll, blockOne;
        static Texture2D readBack;

        [ProbeInit]
        static void Init()
        {
            // has: {"lit": true} reads a part as the components lit field does
            Find.LitTest = c => Of(c).Lit;
        }

        public static double Luminance(Color c) => 0.2126 * c.r + 0.7152 * c.g + 0.0722 * c.b;

        /// <summary>A colour property as the shader gets it: converted to linear in a linear-space project.</summary>
        static Color Linear(Color c) => QualitySettings.activeColorSpace == ColorSpace.Linear ? c.linear : c;

        // ---------------------------------------------------------------- what reads as a source

        /// <summary>A Light that lights the scene: enabled, active in the hierarchy, of an intensity above 0.</summary>
        public static bool LightOn(Light light) => light != null && light.enabled && light.gameObject.activeInHierarchy && light.intensity > 0f;

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
        /// project uses it).</summary>
        public static void AddLight(ref GlowReading r, Light light)
        {
            r.Read = true;
            if (!LightOn(light)) return;
            var colour = Linear(light.color);
            if (GraphicsSettings.lightsUseColorTemperature && light.useColorTemperature)
                colour *= Mathf.CorrelatedColorTemperatureToRGB(light.colorTemperature);
            var amount = light.intensity * Luminance(colour);
            if (amount <= 0.0) return;
            r.Lit = true;
            r.Glow += amount;
            r.Kinds |= GlowReading.KindLight;
        }

        /// <summary>A mesh renderer; false when it couldn't be read (its shader needs rendering and there is no
        /// renderer). Read once a frame (a select's has.lit and the fields share it).</summary>
        public static bool AddMesh(ref GlowReading total, Renderer renderer)
        {
            if (frameOf != Time.frameCount)
            {
                frameOf = Time.frameCount;
                Frame.Clear();
            }
            var id = renderer.GetInstanceID();
            if (!Frame.TryGetValue(id, out var r))
            {
                r = ReadMesh(renderer, out var ok);
                if (!ok) r.Reads |= GlowReading.ReadUnread;
                Frame[id] = r;
            }
            total.Add(r);
            return r.Read;
        }

        static GlowReading ReadMesh(Renderer renderer, out bool ok)
        {
            ok = true;
            var r = new GlowReading();
            // a renderer that isn't drawn gives no light, whatever its materials
            if (!Find.Drawn(renderer)) { r.Read = true; return r; }
            var materials = renderer.sharedMaterials;
            var best = 0.0;
            var bestUnlit = false;
            var allUnlit = materials.Length > 0;
            var render = false;
            var blocks = renderer.HasPropertyBlock();
            for (var i = 0; i < materials.Length; i++)
            {
                var m = materials[i];
                if (m == null || m.shader == null) { allUnlit = false; continue; }
                var face = FaceOf(m.shader);
                if (face == Face.None) { render = true; allUnlit = false; continue; }
                allUnlit &= face == Face.Unlit;
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
                double l;
                if (face == Face.Emissive)
                {
                    // emission off (no _EMISSION keyword) draws none, whatever its colour
                    if (!m.IsKeywordEnabled("_EMISSION")) continue;
                    var c = Linear(ColourOf(m, one, all, EmissionColor, EmissionColor));
                    var tex = TextureOf(m, one, all, EmissionMap, EmissionMap);
                    l = Luminance(tex != null ? c * Mean(tex) : c);
                }
                else
                {
                    var c = Linear(ColourOf(m, one, all, BaseColor, ColorId));
                    var tex = TextureOf(m, one, all, BaseMap, MainTex);
                    l = Luminance(tex != null ? c * Mean(tex) : c);
                }
                if (l > best) { best = l; bestUnlit = face == Face.Unlit; }
            }
            if (render)
            {
                // a shader without the interface: as rendered, the whole renderer
                var hook = Hooks.GlowRender;
                if (hook == null) { ok = false; return r; }
                RenderedGlow seen;
                try { seen = hook(renderer); }
                catch (Exception e) { Probe.Active?.Error("glow render of " + renderer.name + ": " + e.Message); ok = false; return r; }
                if (!seen.Ok) { ok = false; return r; }
                r.Read = true;
                r.Reads |= GlowReading.ReadRender;
                if (seen.Brightest > Floor)
                {
                    r.Lit = true;
                    r.Glow += seen.Glow;
                    r.Kinds |= allUnlit ? GlowReading.KindUnlit : GlowReading.KindEmissive;
                }
                return r;
            }
            r.Read = true;
            r.Reads |= GlowReading.ReadProps;
            if (best <= Floor) return r;
            r.Lit = true;
            // the brightest material over its whole local bounds: the candelas a lamp that size gives every way
            r.Glow += best * QuarterSurface(renderer);
            r.Kinds |= bestUnlit ? GlowReading.KindUnlit : GlowReading.KindEmissive;
            return r;
        }

#if TASKPROBE_PARTICLES
        /// <summary>A particle system: dark unless it is live and its renderer drawn; then as rendered. False when it
        /// couldn't be read.</summary>
        public static bool AddEffect(ref GlowReading total, ParticleSystem ps)
        {
            var renderer = ps.GetComponent<ParticleSystemRenderer>();
            if (renderer == null || !Find.Drawn(renderer) || !Effects.Live(ps)) { total.Read = true; return true; }
            var hook = Hooks.GlowRender;
            if (hook == null) { total.Reads |= GlowReading.ReadUnread; return false; }
            RenderedGlow seen;
            try { seen = hook(renderer); }
            catch (Exception e) { Probe.Active?.Error("glow render of " + ps.name + ": " + e.Message); total.Reads |= GlowReading.ReadUnread; return false; }
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

        /// <summary>A quarter of the surface of a renderer's local bounds, scaled (m2).</summary>
        public static double QuarterSurface(Renderer renderer)
        {
            var s = Vector3.Scale(renderer.localBounds.size, renderer.transform.lossyScale);
            double x = Mathf.Abs(s.x), y = Mathf.Abs(s.y), z = Mathf.Abs(s.z);
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
            // a Shader Graph's properties are its author's: _BaseColor there says nothing of what it draws
            var graph = name.StartsWith("Shader Graphs/", StringComparison.Ordinal);
            if (!graph && name.IndexOf("unlit", StringComparison.OrdinalIgnoreCase) >= 0 &&
                (shader.FindPropertyIndex("_BaseColor") >= 0 || shader.FindPropertyIndex("_Color") >= 0))
                face = Face.Unlit;
            else if (!graph && shader.FindPropertyIndex("_EmissionColor") >= 0 && shader.keywordSpace.FindKeyword("_EMISSION").isValid)
                face = Face.Emissive;
            Faces[id] = face;
            return face;
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

        /// <summary>A texture's mean linear colour, by halving it on the GPU down to 16 x 16 and reading that back, so a
        /// texture that isn't readable reads too. Cached by the texture and its update count.</summary>
        public static Color Mean(Texture tex)
        {
            if (tex == null) return Color.white;
            var id = tex.GetInstanceID();
            var version = tex.updateCount;
            if (Means.TryGetValue(id, out var cached) && cached.Key == version) return cached.Value;
            var mean = Color.white;
            if (tex.dimension == TextureDimension.Tex2D)
            {
                try { mean = Halve(tex); }
                catch (Exception e) { Probe.Active?.Error("the mean of texture " + tex.name + " couldn't be read: " + e.Message); }
            }
            Means[id] = new KeyValuePair<uint, Color>(version, mean);
            return mean;
        }

        static Color Halve(Texture tex)
        {
            const int Side = 16;
            Texture source = tex;
            RenderTexture held = null;
            int w = tex.width, h = tex.height;
            // each halving's bilinear tap averages a 2 x 2 block exactly, so the mean survives a texture without mips
            while (w > Side || h > Side)
            {
                w = Math.Max(Side, (w + 1) / 2);
                h = Math.Max(Side, (h + 1) / 2);
                var next = RenderTexture.GetTemporary(w, h, 0, RenderTextureFormat.ARGBHalf, RenderTextureReadWrite.Linear);
                next.filterMode = FilterMode.Bilinear;
                Graphics.Blit(source, next);
                if (held != null) RenderTexture.ReleaseTemporary(held);
                held = next;
                source = next;
            }
            if (held == null)
            {
                held = RenderTexture.GetTemporary(w, h, 0, RenderTextureFormat.ARGBHalf, RenderTextureReadWrite.Linear);
                Graphics.Blit(source, held);
            }
            if (readBack == null || readBack.width != held.width || readBack.height != held.height)
            {
                if (readBack != null) UnityEngine.Object.Destroy(readBack);
                readBack = new Texture2D(held.width, held.height, TextureFormat.RGBAHalf, false, true);
            }
            var before = RenderTexture.active;
            RenderTexture.active = held;
            readBack.ReadPixels(new Rect(0, 0, held.width, held.height), 0, 0, false);
            RenderTexture.active = before;
            RenderTexture.ReleaseTemporary(held);
            var pixels = readBack.GetPixels();
            var sum = Color.clear;
            foreach (var p in pixels) sum += p;
            return pixels.Length > 0 ? sum / pixels.Length : Color.white;
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
