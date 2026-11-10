// What is rendered (contract section 3, `drawn` and lit / glow "as rendered"): a chosen set of renderers drawn alone
// from fixed orthographic views into small float textures, the pixels read back, on the main thread at sample time.
//
// How: a disabled camera of the probe's own (under the probe's object, hidden), rendered by hand through URP's
// single-camera render request with the renderer the player's camera draws with, seeing only the layers of the chosen
// renderers (and terrains) and never the UI layer (world-space canvases aren't renderers and can't be forced off: a
// renderer on that layer isn't drawn either). Every other drawn renderer on those layers inside the views is forced
// off for the render, and every other terrain there stops drawing. The light is the probe's: every Light off, the
// ambient probe a flat white (or nothing, for the glow), fog off, the default reflection at intensity 0, the chosen
// renderers' and terrains' lightmaps, light probes and reflection probes off (so the flat ambient is all that lights
// them), no post-processing, shadows, MSAA, render scale or renderer features but RenderObjects (it may be how a layer
// is drawn at all). One light gets through: under a clustered renderer (Forward+ or Deferred+) with reflection probe
// blending on (URP's probe atlas), the shader reads every reflection probe whose box holds the surface whatever the
// renderer's own setting, so a smooth surface there keeps a little of what the probes reflect, and a realtime probe's
// new picture reads as motion (read in URP's shaders; no play has blending on). Depth: a second render of the same view into a depth
// texture, copied into a float texture by a shader of the package (Resources/TaskProbeDepthCopy) and read back.
//
// Each setting is saved before anything changes and each object recorded before it is changed, and all of it is put
// back in a finally, whatever throws (a game's camera callback, a destroyed renderer). The ambient and the default
// reflection keep their modes and no reflection probe is touched: switching those had the engine build the environment
// again after the sample, and the game's frames came out darker. No game script runs in between but RenderPipelineManager
// callbacks, which see the probe's camera render like any other camera's.
//
// Why not move the chosen renderers to a spare layer: a layer change on an object with a collider refilters its
// physics contacts (a resting body could lose and regain its contacts: OnCollisionEnter again). forceRenderingOff
// does nothing but stop the drawing.
using System;
using System.Collections.Generic;
using System.Diagnostics;
using UnityEngine;
using UnityEngine.Rendering;
#if TASKPROBE_URP
using UnityEngine.Rendering.Universal;
#endif

namespace TaskProbe
{
    /// <summary>A renderer's own light as rendered: drawn alone with every light off (ambient black, no reflections or
    /// fog), orthographic from four fixed views, HDR. `Brightest`: its brightest pixel's luminance. `Glow`: the views'
    /// luminance x pixel area over the seen area of its box, times a quarter of the box's surface (m2).</summary>
    public struct RenderedGlow
    {
        public bool Ok;  // false: not rendered (no renderer facility, not drawn, on the UI layer, the budget spent)
        public double Brightest;
        public double Glow;
    }

    /// <summary>One orthographic view: where the camera is, which way it looks (its forward), how wide it sees (m,
    /// square) and how deep (m from the camera).</summary>
    public struct DrawnView
    {
        public Vector3 Position;
        public Quaternion Rotation;
        public float Width;
        public float Far;
    }

    /// <summary>The light a render is made under: a flat white ambient and nothing else (a lit surface shows its own
    /// colour), or none at all (what is left is what the surface gives off itself).</summary>
    public enum DrawnLight { White, Dark }

    /// <summary>One view's pixels, row by row from the bottom: linear HDR colour, and (when asked) the depth of the
    /// opaque surface drawn there in metres from the camera plane (PositiveInfinity: nothing opaque).</summary>
    public sealed class DrawnImage
    {
        public Color[] Colour;
        public float[] Depth;
    }

    public static class DrawnRender
    {
        /// <summary>The four views of a place near a point and of a glow render: the directions to a regular
        /// tetrahedron's corners, so each face of a box is seen from two of them at the same slant.</summary>
        public static readonly Vector3[] Tetrahedron = { new Vector3(1, 1, 1), new Vector3(1, -1, -1), new Vector3(-1, 1, -1), new Vector3(-1, -1, 1) };
        public const float Back = 0.5f;  // m: a view's camera stands this far outside what it frames

        const float Near = 0.01f;  // m: the camera's near plane (a pixel's depth counts from the camera itself)
        // URP Lit gives a non-metal 96% of its albedo as diffuse (1 - its 4% specular): the white ambient is that much
        // brighter, so a Lit surface reads its own base colour
        const float WhiteAmbient = 1f / 0.96f;
        const int GlowSize = 128;  // pixels square, each view of a renderer
        const int GlowBudget = 64;  // renderers rendered per pass at most (each renderer once a pass)
        const int UiLayer = 5;  // world-space canvases draw on it and can't be forced off: the layer is left out

        const string NoDevice = "rendering: the player has no graphics device (-nographics): drawn and glow as rendered have no value";
        const string NotUrp = "rendering: the render pipeline isn't URP: drawn and glow as rendered have no value";
        const string NotUniversal = "rendering: the player's camera draws with a URP renderer that isn't the Universal Renderer: drawn and glow as rendered have no value";
        const string NoFloat = "rendering: the player can't render to float textures: drawn and glow as rendered have no value";
        const string NoDepthShader = "rendering: the package's depth shader (Resources/TaskProbeDepthCopy) isn't in the player: drawn has no value";

        static GameObject rig;
        static Camera cam;
        static Material depthCopy;
        static bool listening;
        static readonly Dictionary<int, RenderTexture> ColourTargets = new Dictionary<int, RenderTexture>();
        static readonly Dictionary<int, RenderTexture> DepthTargets = new Dictionary<int, RenderTexture>();
        static readonly Dictionary<int, RenderTexture> FloatTargets = new Dictionary<int, RenderTexture>();
        static readonly Dictionary<int, Texture2D> ColourReads = new Dictionary<int, Texture2D>();
        static readonly Dictionary<int, Texture2D> FloatReads = new Dictionary<int, Texture2D>();

        // ---------------------------------------------------------------- what is drawn, once a pass over the scene

        static int snapStamp = -1;
        static readonly List<Component> SnapDrawn = new List<Component>();
        static readonly List<Bounds> SnapBounds = new List<Bounds>();

        /// <summary>What a render can draw in the loaded scenes, and its world bounds, read once a pass over the scene
        /// (Probe.Stamp: the inputs before the game's scripts and the samples after them each read their own): every
        /// renderer that is drawn (enabled, active, not forced off, not drawing shadows only) and every terrain drawing
        /// its heightmap (its trees and details with it), none on the UI layer.</summary>
        public static void Drawn(out List<Component> drawn, out List<Bounds> bounds)
        {
            if (snapStamp != Probe.Stamp)
            {
                snapStamp = Probe.Stamp;
                SnapDrawn.Clear();
                SnapBounds.Clear();
                foreach (var r in UnityEngine.Object.FindObjectsByType<Renderer>(FindObjectsInactive.Exclude, FindObjectsSortMode.None))
                {
                    if (!Find.Drawn(r) || r.shadowCastingMode == ShadowCastingMode.ShadowsOnly || r.gameObject.layer == UiLayer ||
                        Probe.IsOwn(r.gameObject)) continue;
                    SnapDrawn.Add(r);
                    SnapBounds.Add(r.bounds);
                }
#if TASKPROBE_TERRAIN
                foreach (var t in Terrain.activeTerrains)
                {
                    if (t == null || !t.drawHeightmap || t.terrainData == null || t.gameObject.layer == UiLayer || Probe.IsOwn(t.gameObject)) continue;
                    var b = t.terrainData.bounds;  // in the terrain's own space, which only moves (a terrain doesn't turn or scale)
                    b.center += t.GetPosition();
                    SnapDrawn.Add(t);
                    SnapBounds.Add(b);
                }
#endif
            }
            drawn = SnapDrawn;
            bounds = SnapBounds;
        }

        // ---------------------------------------------------------------- what a render needs

        /// <summary>The probe's camera and what a render needs, made when missing (a game may destroy them); false, with
        /// one error, when this player can't render alone. The camera takes the renderer the player's camera draws with.</summary>
        static bool Ready(bool depth)
        {
            if (SystemInfo.graphicsDeviceType == GraphicsDeviceType.Null) return Refuse(NoDevice);
#if TASKPROBE_URP
            var asset = GraphicsSettings.currentRenderPipeline as UniversalRenderPipelineAsset;
            if (asset == null) return Refuse(NotUrp);
            if (!SystemInfo.SupportsRenderTextureFormat(RenderTextureFormat.ARGBFloat)) return Refuse(NoFloat);
            if (depth && depthCopy == null)
            {
                var shader = Resources.Load<Shader>("TaskProbeDepthCopy");
                if (shader == null || !shader.isSupported) return Refuse(NoDepthShader);
                depthCopy = new Material(shader) { hideFlags = HideFlags.HideAndDontSave };
            }
            if (rig == null || cam == null)
            {
                if (rig != null) UnityEngine.Object.Destroy(rig);
                // under the probe's own object and hidden: no select, no game search (FindObjectsByType leaves out what
                // isn't saved) and no "destroy everything" of the game finds it
                rig = new GameObject("TaskProbe.Render") { hideFlags = HideFlags.HideAndDontSave };
                if (Probe.Active != null) rig.transform.SetParent(Probe.Active.transform, false);
                cam = rig.AddComponent<Camera>();
                cam.enabled = false;
                cam.orthographic = true;
                cam.clearFlags = CameraClearFlags.SolidColor;
                cam.backgroundColor = new Color(0, 0, 0, 0);
                cam.allowHDR = true;
                cam.allowMSAA = false;
                cam.allowDynamicResolution = false;
                cam.useOcclusionCulling = false;
                cam.depthTextureMode = DepthTextureMode.None;
                cam.aspect = 1f;
                var extra = cam.GetUniversalAdditionalCameraData();
                extra.renderPostProcessing = false;
                extra.antialiasing = AntialiasingMode.None;
                extra.renderShadows = false;
                extra.requiresDepthOption = CameraOverrideOption.Off;
                extra.requiresColorOption = CameraOverrideOption.Off;
                extra.volumeLayerMask = 0;
                extra.stopNaN = false;
                extra.dithering = false;
                extra.allowXRRendering = false;
            }
            if (!listening)
            {
                listening = true;
                Application.logMessageReceived += Heard;
            }
            // the player's renderer: what the game filters out, draws by a RenderObjects pass, or draws forward only
            // under Deferred, the probe draws the same way
            var index = RendererIndex(asset);
            cam.GetUniversalAdditionalCameraData().SetRenderer(index);
            return asset.rendererDataList[index] is UniversalRendererData || Refuse(NotUniversal);
#else
            return Refuse(NotUrp);
#endif
        }

        static bool Refuse(string why)
        {
            Probe.Active?.Error(why);
            return false;
        }

#if TASKPROBE_URP
        /// <summary>The index in the URP asset's renderer list of the renderer the player's camera draws with (its
        /// default with no such camera).</summary>
        static int RendererIndex(UniversalRenderPipelineAsset asset)
        {
            var view = Probe.Active != null ? Probe.Active.View : null;
            var used = view != null && view.TryGetComponent<UniversalAdditionalCameraData>(out var data) ? data.scriptableRenderer : asset.scriptableRenderer;
            var count = asset.rendererDataList.Length;
            for (var i = 0; i < count; i++)
                if (asset.rendererDataList[i] != null && asset.GetRenderer(i) == used) return i;
            for (var i = 0; i < count; i++)
                if (asset.rendererDataList[i] != null && asset.GetRenderer(i) == asset.scriptableRenderer) return i;
            return 0;
        }
#endif

        static RenderTexture Target(Dictionary<int, RenderTexture> pool, int size, RenderTextureFormat format, int depthBits)
        {
            if (pool.TryGetValue(size, out var rt) && rt != null) return rt;
            rt = new RenderTexture(size, size, depthBits, format, RenderTextureReadWrite.Linear)
            {
                hideFlags = HideFlags.HideAndDontSave, antiAliasing = 1, useMipMap = false, autoGenerateMips = false,
                filterMode = FilterMode.Point,
            };
            rt.Create();
            pool[size] = rt;
            return rt;
        }

        static Texture2D Reader(Dictionary<int, Texture2D> pool, int size, TextureFormat format)
        {
            if (pool.TryGetValue(size, out var t) && t != null) return t;
            t = new Texture2D(size, size, format, false, true) { hideFlags = HideFlags.HideAndDontSave };
            pool[size] = t;
            return t;
        }

        // ---------------------------------------------------------------- rendering

        static readonly HashSet<int> ShowIds = new HashSet<int>();
        static bool rendering;
        static Exception caught;  // the render's first exception
        static string heardType;  // its type, when the render request caught it in a game's callback

        /// <summary>An exception logged while a render request runs: a game's camera callback threw, and the render
        /// request swallowed it, so the render stopped part way.</summary>
        static void Heard(string message, string stack, LogType type)
        {
            if (!rendering || type != LogType.Exception || caught != null) return;
            // the request logs it as "<type>: <message>"
            var colon = message.IndexOf(':');
            heardType = colon > 0 && message.IndexOf(' ', 0, colon) < 0 ? message.Substring(0, colon) : "Exception";
            caught = new Exception(message + "\n" + stack);
        }

        /// <summary>Renders `show` (renderers and terrains) alone from each view (size x size) under `light`, with the depth when `depth`, into
        /// `images` (one per view; their arrays are reused); false when nothing could be rendered (the error is said
        /// once).</summary>
        public static bool Render(IList<Component> show, IList<DrawnView> views, int size, DrawnLight light, bool depth, List<DrawnImage> images)
        {
            var done = 0;
            if (Ready(depth))
            {
                var mask = 0;
                ShowIds.Clear();
                foreach (var c in show)
                {
                    if (c == null) continue;
                    mask |= 1 << c.gameObject.layer;
                    ShowIds.Add(c.GetInstanceID());
                }
                mask &= ~(1 << UiLayer);
                rendering = true;
                caught = null;
                heardType = null;
                try
                {
                    Isolate(show, mask, Seen(views), light);
                    cam.cullingMask = mask;
                    var colourRt = Target(ColourTargets, size, RenderTextureFormat.ARGBFloat, 24);
                    var depthRt = depth ? Target(DepthTargets, size, RenderTextureFormat.Depth, 24) : null;
                    var floatRt = depth ? Target(FloatTargets, size, RenderTextureFormat.RFloat, 0) : null;
                    for (; done < views.Count; done++)
                    {
                        var v = views[done];
                        cam.transform.SetPositionAndRotation(v.Position, v.Rotation);
                        cam.orthographicSize = v.Width * 0.5f;
                        cam.nearClipPlane = Near;
                        cam.farClipPlane = Mathf.Max(v.Far, Near * 2f);
                        if (done == images.Count) images.Add(new DrawnImage());
                        var image = images[done];
                        if (!Submit(colourRt)) break;
                        image.Colour = ReadColour(colourRt, size, image.Colour);
                        if (!depth) continue;
                        if (!Submit(depthRt)) break;
                        Graphics.Blit(depthRt, floatRt, depthCopy);
                        image.Depth = ReadDepth(floatRt, size, cam.farClipPlane, image.Depth);
                    }
                }
                catch (Exception e)
                {
                    caught ??= e;
                }
                finally
                {
                    rendering = false;
                    Restore();
                }
                if (caught != null)
                {
                    done = 0;
                    // as every exception of the probe's: its type in the error, its stack in probe.log once
                    Probe.Active?.Failed(heardType != null ? "rendering: " + heardType + " in a render: no value that sample"
                                                           : "rendering: {0} in a render: no value that sample", caught);
                    caught = null;
                    heardType = null;
                }
            }
            if (done < views.Count)
            {
                images.Clear();
                return false;
            }
            if (images.Count > done) images.RemoveRange(done, images.Count - done);
            return true;
        }

        /// <summary>The space the views see (their boxes from the near to the far plane): only renderers there need
        /// forcing off.</summary>
        static Bounds Seen(IList<DrawnView> views)
        {
            var volume = new Bounds();
            var first = true;
            foreach (var v in views)
            {
                var right = v.Rotation * Vector3.right * (v.Width * 0.5f);
                var up = v.Rotation * Vector3.up * (v.Width * 0.5f);
                var forward = v.Rotation * Vector3.forward;
                foreach (var d in new[] { Near, v.Far })
                    for (var i = 0; i < 4; i++)
                    {
                        var p = v.Position + forward * d + ((i & 1) == 0 ? right : -right) + ((i & 2) == 0 ? up : -up);
                        if (first) { volume = new Bounds(p, Vector3.zero); first = false; }
                        else volume.Encapsulate(p);
                    }
            }
            return volume;
        }

        /// <summary>One render of the probe's camera into `target`; false when an exception stopped it.</summary>
        static bool Submit(RenderTexture target)
        {
#if TASKPROBE_URP
            cam.targetTexture = target;
            cam.aspect = 1f;
            RenderPipeline.SubmitRenderRequest(cam, new UniversalRenderPipeline.SingleCameraRequest { destination = target });
            return caught == null;
#else
            return false;
#endif
        }

        static Color[] ReadColour(RenderTexture rt, int size, Color[] into)
        {
            var read = Reader(ColourReads, size, TextureFormat.RGBAFloat);
            RenderTexture.active = rt;  // put back by Restore
            read.ReadPixels(new Rect(0, 0, size, size), 0, 0, false);
            var raw = read.GetPixelData<Color>(0);
            if (into == null || into.Length != raw.Length) into = new Color[raw.Length];
            raw.CopyTo(into);
            return into;
        }

        /// <summary>Raw depth to metres from the camera plane: an orthographic depth is linear between the planes
        /// (reversed on D3D, Metal, Vulkan); the far plane itself is "nothing opaque".</summary>
        static float[] ReadDepth(RenderTexture rt, int size, float far, float[] into)
        {
            var read = Reader(FloatReads, size, TextureFormat.RFloat);
            RenderTexture.active = rt;  // put back by Restore
            read.ReadPixels(new Rect(0, 0, size, size), 0, 0, false);
            var raw = read.GetPixelData<float>(0);
            var reversed = SystemInfo.usesReversedZBuffer;
            if (into == null || into.Length != raw.Length) into = new float[raw.Length];
            for (var i = 0; i < into.Length; i++)
            {
                var z = reversed ? 1f - raw[i] : raw[i];
                into[i] = z >= 0.99999f || float.IsNaN(z) ? float.PositiveInfinity : Near + z * (far - Near);
            }
            return into;
        }

        // ---------------------------------------------------------------- isolation and the probe's light

        static readonly List<Renderer> ForcedOff = new List<Renderer>();
        static readonly List<Renderer> Tuned = new List<Renderer>();
        static readonly List<int> TunedLightmap = new List<int>();
        static readonly List<LightProbeUsage> TunedProbes = new List<LightProbeUsage>();
        static readonly List<ReflectionProbeUsage> TunedReflections = new List<ReflectionProbeUsage>();
        static readonly List<Light> LightsOff = new List<Light>();
#if TASKPROBE_TERRAIN
        static readonly List<Terrain> TerrainsOff = new List<Terrain>();
        static readonly List<bool> TerrainTrees = new List<bool>();
        static readonly List<Terrain> TunedTerrains = new List<Terrain>();
        static readonly List<int> TunedTerrainLightmap = new List<int>();
        static readonly List<ReflectionProbeUsage> TunedTerrainReflections = new List<ReflectionProbeUsage>();
#endif
#if TASKPROBE_URP
        static readonly List<ScriptableRendererFeature> FeaturesOff = new List<ScriptableRendererFeature>();
        static UniversalRenderPipelineAsset urpAsset;  // set: its render scale was saved
        static float urpScale;
#endif
        static bool settingsSaved, activeSaved;
        static RenderTexture activeBefore;
        static SphericalHarmonicsL2 ambientProbe;
        static float reflectionIntensity;
        static bool fog;

        static void Isolate(IList<Component> show, int mask, Bounds volume, DrawnLight light)
        {
            // first everything a change could leave behind, saved before anything changes
            activeBefore = RenderTexture.active;
            activeSaved = true;
            ambientProbe = RenderSettings.ambientProbe;
            reflectionIntensity = RenderSettings.reflectionIntensity;
            fog = RenderSettings.fog;
            settingsSaved = true;
#if TASKPROBE_URP
            var asset = GraphicsSettings.currentRenderPipeline as UniversalRenderPipelineAsset;
            if (asset != null)
            {
                urpScale = asset.renderScale;
                urpAsset = asset;
            }
#endif

            // the probe's light: the ambient probe alone, a flat white or nothing, with no fog and no reflection. Never
            // the ambient's or the default reflection's mode, never a reflection probe: switching the ambient or the default reflection to
            // another mode, or a reflection probe off and on, left the game's own frames changed after the sample (a
            // realtime probe lost its picture; play drawn.main against drawn.plain), and a probe's intensity counts only
            // from the next frame (a white cube read 0.016 of glow from the probe it stood in), so the chosen renderers
            // stop reading probes instead
            var sh = new SphericalHarmonicsL2();
            if (light == DrawnLight.White) sh.AddAmbientLight(new Color(WhiteAmbient, WhiteAmbient, WhiteAmbient, 1f));
            RenderSettings.ambientProbe = sh;
            RenderSettings.fog = false;
            RenderSettings.reflectionIntensity = 0f;

            // then each object, recorded before it is changed (Restore puts back exactly what is recorded)
#if TASKPROBE_URP
            if (urpAsset != null)
            {
                // render scale would draw the view smaller than its texture
                if (Mathf.Abs(urpScale - 1f) > 1e-4f) urpAsset.renderScale = 1f;
                // renderer features (SSAO, decals, full-screen passes, a game's own) are left out; RenderObjects may be
                // how a layer is drawn at all, so it stays
                var data = urpAsset.rendererDataList[RendererIndex(urpAsset)];
                if (data != null)
                    foreach (var f in data.rendererFeatures)
                        if (f != null && f.isActive && !(f is RenderObjects))
                        {
                            FeaturesOff.Add(f);
                            f.SetActive(false);
                        }
            }
#endif
            foreach (var l in UnityEngine.Object.FindObjectsByType<Light>(FindObjectsInactive.Exclude, FindObjectsSortMode.None))
                if (l.enabled)
                {
                    LightsOff.Add(l);
                    l.enabled = false;
                }
            // the chosen renderers and terrains: lit by the ambient probe alone (no lightmap, no light probes, no
            // reflection probes)
            foreach (var c in show)
            {
                if (c is Renderer r && r != null)
                {
                    Tuned.Add(r);
                    TunedLightmap.Add(r.lightmapIndex);
                    TunedProbes.Add(r.lightProbeUsage);
                    TunedReflections.Add(r.reflectionProbeUsage);
                    if (r.lightmapIndex >= 0 && r.lightmapIndex < 0xFFFE) r.lightmapIndex = -1;
                    if (r.lightProbeUsage != LightProbeUsage.Off) r.lightProbeUsage = LightProbeUsage.Off;
                    if (r.reflectionProbeUsage != ReflectionProbeUsage.Off) r.reflectionProbeUsage = ReflectionProbeUsage.Off;
                }
#if TASKPROBE_TERRAIN
                else if (c is Terrain t && t != null)
                {
                    TunedTerrains.Add(t);
                    TunedTerrainLightmap.Add(t.lightmapIndex);
                    TunedTerrainReflections.Add(t.reflectionProbeUsage);
                    if (t.lightmapIndex >= 0 && t.lightmapIndex < 0xFFFE) t.lightmapIndex = -1;
                    if (t.reflectionProbeUsage != ReflectionProbeUsage.Off) t.reflectionProbeUsage = ReflectionProbeUsage.Off;
                }
#endif
            }
            // everything else drawn on those layers that the views could see
            Drawn(out var all, out var bounds);
            for (var i = 0; i < all.Count; i++)
            {
                var c = all[i];
                if (c == null || (mask & (1 << c.gameObject.layer)) == 0 || ShowIds.Contains(c.GetInstanceID()) || !bounds[i].Intersects(volume)) continue;
                if (c is Renderer r)
                {
                    if (r.forceRenderingOff) continue;
                    ForcedOff.Add(r);
                    r.forceRenderingOff = true;
                }
#if TASKPROBE_TERRAIN
                else if (c is Terrain t)
                {
                    if (!t.drawHeightmap) continue;
                    TerrainsOff.Add(t);
                    TerrainTrees.Add(t.drawTreesAndFoliage);
                    t.drawHeightmap = false;
                    t.drawTreesAndFoliage = false;
                }
#endif
            }
        }

        /// <summary>Puts back what Isolate changed and only what it saved, the settings first (an object put back may read
        /// them at once); each list is emptied as it is put back. Nothing here can throw: every object is checked before
        /// it is touched.</summary>
        static void Restore()
        {
            if (settingsSaved)
            {
                RenderSettings.ambientProbe = ambientProbe;
                RenderSettings.fog = fog;
                RenderSettings.reflectionIntensity = reflectionIntensity;
                settingsSaved = false;
            }
#if TASKPROBE_URP
            foreach (var f in FeaturesOff)
                if (f != null) f.SetActive(true);
            FeaturesOff.Clear();
            if (urpAsset != null)
            {
                if (urpAsset.renderScale != urpScale) urpAsset.renderScale = urpScale;
                urpAsset = null;
            }
#endif
            foreach (var l in LightsOff)
                if (l != null) l.enabled = true;
            LightsOff.Clear();
            for (var i = 0; i < Tuned.Count; i++)
            {
                var r = Tuned[i];
                if (r == null) continue;
                if (r.lightmapIndex != TunedLightmap[i]) r.lightmapIndex = TunedLightmap[i];
                if (r.lightProbeUsage != TunedProbes[i]) r.lightProbeUsage = TunedProbes[i];
                if (r.reflectionProbeUsage != TunedReflections[i]) r.reflectionProbeUsage = TunedReflections[i];
            }
            Tuned.Clear();
            TunedLightmap.Clear();
            TunedProbes.Clear();
            TunedReflections.Clear();
#if TASKPROBE_TERRAIN
            for (var i = 0; i < TunedTerrains.Count; i++)
            {
                var t = TunedTerrains[i];
                if (t == null) continue;
                if (t.lightmapIndex != TunedTerrainLightmap[i]) t.lightmapIndex = TunedTerrainLightmap[i];
                if (t.reflectionProbeUsage != TunedTerrainReflections[i]) t.reflectionProbeUsage = TunedTerrainReflections[i];
            }
            TunedTerrains.Clear();
            TunedTerrainLightmap.Clear();
            TunedTerrainReflections.Clear();
            for (var i = 0; i < TerrainsOff.Count; i++)
            {
                if (TerrainsOff[i] == null) continue;
                TerrainsOff[i].drawHeightmap = true;
                TerrainsOff[i].drawTreesAndFoliage = TerrainTrees[i];
            }
            TerrainsOff.Clear();
            TerrainTrees.Clear();
#endif
            foreach (var r in ForcedOff)
                if (r != null) r.forceRenderingOff = false;
            ForcedOff.Clear();
            if (cam != null) cam.targetTexture = null;
            if (activeSaved)
            {
                RenderTexture.active = activeBefore;  // the render request leaves its target active
                activeBefore = null;
                activeSaved = false;
            }
        }

        // ---------------------------------------------------------------- lit / glow as rendered

        static int glowStamp = -1, glowLeft, glowRenders;
        static double glowMs;
        static readonly Dictionary<int, RenderedGlow> GlowSeen = new Dictionary<int, RenderedGlow>();
        static readonly List<Component> GlowShow = new List<Component>(1);
        static readonly List<DrawnView> GlowViews = new List<DrawnView>(4);
        static readonly List<DrawnImage> GlowImages = new List<DrawnImage>(4);

        /// <summary>One renderer alone with no light at all, from the four corners of a tetrahedron in its own frame
        /// (128 x 128, orthographic, HDR). At most 64 renders a pass over the scene (Probe.Stamp) across every caller,
        /// each renderer once a pass, as the original renders each mesh once a sample and a select's has.lit on its own;
        /// what each costs goes to probe.log.</summary>
        public static RenderedGlow Glow(Renderer r)
        {
            if (glowStamp != Probe.Stamp)
            {
                glowStamp = Probe.Stamp;
                glowLeft = GlowBudget;
                GlowSeen.Clear();
            }
            if (r == null) return new RenderedGlow();
            var id = r.GetInstanceID();
            if (GlowSeen.TryGetValue(id, out var seen)) return seen;
            var read = new RenderedGlow();
            if (glowLeft > 0 && Find.Drawn(r) && r.gameObject.layer != UiLayer)
            {
                glowLeft--;
                var clock = Stopwatch.StartNew();
                read = RenderGlow(r);
                var ms = clock.Elapsed.TotalMilliseconds;
                glowMs += ms;
                glowRenders++;
                if (glowRenders == 1 || glowRenders % 100 == 0)
                    Probe.Log(FormattableString.Invariant($"glow render: {ms:F2} ms this render, {glowMs / glowRenders:F2} ms a render over {glowRenders}"));
            }
            GlowSeen[id] = read;
            return read;
        }

        /// <summary>A renderer's own box in the world, as a glow render frames it and its glow is scaled: a mesh's local
        /// bounds turned and scaled with it (a skinned mesh's in its root bone's frame: its local bounds are in that
        /// bone's space); any other renderer (particles, lines, trails, sprites, tilemaps, visual effects) its world
        /// bounds.</summary>
        public static void LocalBox(Renderer r, out Vector3 size, out Vector3 centre, out Quaternion turn)
        {
            if (r is MeshRenderer || r is SkinnedMeshRenderer)
            {
                var space = r is SkinnedMeshRenderer s && s.rootBone != null ? s.rootBone : r.transform;
                var local = r.localBounds;
                var scale = space.lossyScale;
                size = Vector3.Scale(local.size, new Vector3(Mathf.Abs(scale.x), Mathf.Abs(scale.y), Mathf.Abs(scale.z)));
                centre = space.TransformPoint(local.center);
                turn = space.rotation;
            }
            else
            {
                var world = r.bounds;
                size = world.size;
                centre = world.center;
                turn = Quaternion.identity;
            }
        }

        static RenderedGlow RenderGlow(Renderer r)
        {
            LocalBox(r, out var size, out var centre, out var turn);
            var radius = Mathf.Max(size.magnitude * 0.5f, 0.01f);
            var width = radius * 2f * 1.02f;  // the box from any side, with a margin
            var seenArea = 0.0;  // the box's area the views see (m2)
            GlowViews.Clear();
            foreach (var corner in Tetrahedron)
            {
                var n = corner.normalized;
                var dir = turn * n;  // from the renderer toward the camera; never along its own up
                seenArea += Mathf.Abs(n.x) * size.y * size.z + Mathf.Abs(n.y) * size.x * size.z + Mathf.Abs(n.z) * size.x * size.y;
                GlowViews.Add(new DrawnView
                {
                    Position = centre + dir * (radius + Back), Rotation = Quaternion.LookRotation(-dir, turn * Vector3.up),
                    Width = width, Far = 2f * (radius + Back),
                });
            }
            GlowShow.Clear();
            GlowShow.Add(r);
            if (!Render(GlowShow, GlowViews, GlowSize, DrawnLight.Dark, false, GlowImages)) return new RenderedGlow();
            var pixel = (double)width / GlowSize;
            var pixelArea = pixel * pixel;  // m2
            double sum = 0.0, peak = 0.0;
            foreach (var image in GlowImages)
                foreach (var c in image.Colour)
                {
                    var l = Find.Luminance(c.r, c.g, c.b);
                    if (l > 0.0 && !double.IsNaN(l) && !double.IsInfinity(l))
                    {
                        sum += l * pixelArea;
                        if (l > peak) peak = l;
                    }
                }
            var mean = seenArea > 1e-8 ? sum / seenArea : 0.0;
            var quarterSurface = 2.0 * ((double)size.x * size.y + (double)size.y * size.z + (double)size.x * size.z) / 4.0;
            return new RenderedGlow { Ok = true, Brightest = peak, Glow = mean * quarterSurface };
        }
    }
}
