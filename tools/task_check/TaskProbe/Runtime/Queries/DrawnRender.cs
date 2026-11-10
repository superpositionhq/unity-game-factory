// What is rendered (contract section 3, `drawn` and lit / glow "as rendered"): a chosen set of renderers drawn alone
// from fixed orthographic views into small HDR textures, the pixels read back, on the main thread at sample time.
//
// How: a disabled camera of the probe's own, rendered by hand (a render request), seeing only the layers of the chosen
// renderers; every other drawn renderer on those layers inside the views is forced off for the render (a terrain
// there stops drawing). The light is the probe's: every Light and reflection probe off, a flat ambient (white, or
// black for the glow), fog off, the default reflection black, the chosen renderers' lightmaps and light probes off (so
// the flat ambient is all that lights them), no post-processing, shadows, MSAA, render scale or renderer features
// (but RenderObjects). Depth: a second render of the same view into a depth texture, copied into a float texture by
// a shader of the package (Resources/TaskProbeDepthCopy) and read back. Everything changed is put back before
// returning; no game script runs in between, except RenderPipelineManager camera callbacks, which see the probe's
// camera render like any other camera.
//
// Why not move the chosen renderers to a spare layer: a layer change on an object with a collider refilters its
// physics contacts (a resting body could lose and regain its contacts: OnCollisionEnter again). forceRenderingOff
// does nothing but stop the drawing.
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Reflection;
using UnityEngine;
using UnityEngine.Rendering;
#if TASKPROBE_URP
using UnityEngine.Rendering.Universal;
#endif

namespace TaskProbe
{
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
        public int Size;
        public Color[] Colour;
        public float[] Depth;
    }

    public static class DrawnRender
    {
        public const float Near = 0.01f;  // m: the camera's near plane (a pixel's depth counts from the camera itself)
        // URP Lit gives a non-metal 96% of its albedo as diffuse (1 - its 4% specular): the white ambient is that much
        // brighter, so a Lit surface reads its own base colour
        const float WhiteAmbient = 1f / 0.96f;
        const int GlowSize = 128, GlowBudget = 64;
        const int UiLayer = 5;  // world-space canvases aren't renderers and can't be forced off: the UI layer is left out
        static readonly Vector3[] Tetrahedron = { new Vector3(1, 1, 1), new Vector3(1, -1, -1), new Vector3(-1, 1, -1), new Vector3(-1, -1, 1) };

        static GameObject rig;
        static Camera cam;
        static Material depthCopy;
        static Cubemap black;
        static bool broken;
        static readonly Dictionary<int, RenderTexture> colourTargets = new Dictionary<int, RenderTexture>();
        static readonly Dictionary<int, RenderTexture> depthTargets = new Dictionary<int, RenderTexture>();
        static readonly Dictionary<int, RenderTexture> floatTargets = new Dictionary<int, RenderTexture>();
        static readonly Dictionary<int, Texture2D> colourReads = new Dictionary<int, Texture2D>();
        static readonly Dictionary<int, Texture2D> floatReads = new Dictionary<int, Texture2D>();

        /// <summary>Milliseconds spent rendering and reading back since the play started (cost reports).</summary>
        public static double TotalMs;
        public static int Renders;

        // ---------------------------------------------------------------- the scene's drawn renderers, once a frame

        static int snapFrame = -1;
        static readonly List<Renderer> snapRenderers = new List<Renderer>();
        static readonly List<Bounds> snapBounds = new List<Bounds>();

        /// <summary>Every drawn renderer of the loaded scenes (enabled, active, not forced off) and its world bounds, read
        /// once a frame.</summary>
        public static void Drawn(out List<Renderer> renderers, out List<Bounds> bounds)
        {
            if (snapFrame != Time.frameCount)
            {
                snapFrame = Time.frameCount;
                snapRenderers.Clear();
                snapBounds.Clear();
                foreach (var r in UnityEngine.Object.FindObjectsByType<Renderer>(FindObjectsInactive.Exclude, FindObjectsSortMode.None))
                {
                    if (!Find.Drawn(r) || Probe.IsOwn(r.gameObject)) continue;
                    snapRenderers.Add(r);
                    snapBounds.Add(r.bounds);
                }
            }
            renderers = snapRenderers;
            bounds = snapBounds;
        }

        // ---------------------------------------------------------------- set up once

        static bool Ready()
        {
            if (broken) return false;
            if (cam != null) return true;
            if (!SystemInfo.SupportsRenderTextureFormat(RenderTextureFormat.ARGBFloat) || SystemInfo.graphicsDeviceType == GraphicsDeviceType.Null)
            {
                broken = true;
                Probe.Active?.Error("drawn: this player can't render offscreen in HDR (no float render textures)");
                return false;
            }
            var shader = Resources.Load<Shader>("TaskProbeDepthCopy");
            if (shader == null || !shader.isSupported)
            {
                broken = true;
                Probe.Active?.Error("drawn: the package's depth shader (Resources/TaskProbeDepthCopy) isn't in the player");
                return false;
            }
            depthCopy = new Material(shader) { hideFlags = HideFlags.HideAndDontSave };
            black = new Cubemap(1, TextureFormat.RGBA32, false) { hideFlags = HideFlags.HideAndDontSave };
            for (var f = 0; f < 6; f++) black.SetPixel((CubemapFace)f, 0, 0, Color.black);
            black.Apply(false, true);
            // HideAndDontSave: FindObjectsByType doesn't return it, so no query selects the probe's camera
            rig = new GameObject("TaskProbe.Render") { hideFlags = HideFlags.HideAndDontSave };
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
            cam.nearClipPlane = Near;
            cam.aspect = 1f;
#if TASKPROBE_URP
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
#endif
            return true;
        }

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

        static readonly HashSet<int> showIds = new HashSet<int>();

        /// <summary>Renders `show` alone from each view (size x size) under `light`, with the depth when `depth`; false
        /// when nothing could be rendered (the error is reported once).</summary>
        public static bool Render(IList<Renderer> show, IList<DrawnView> views, int size, DrawnLight light, bool depth, List<DrawnImage> images)
        {
            images.Clear();
            if (!Ready()) return false;
            var clock = Stopwatch.StartNew();
            var mask = 0;
            showIds.Clear();
            foreach (var r in show)
            {
                if (r == null) continue;
                mask |= 1 << r.gameObject.layer;
                showIds.Add(r.GetInstanceID());
            }
            var hasUi = (mask & (1 << UiLayer)) != 0;
            // the space the views see, so only renderers there need forcing off
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
            var ok = true;
            Isolate(show, mask, volume, light);
            try
            {
                cam.cullingMask = hasUi ? mask : mask & ~(1 << UiLayer);
                var colourRt = Target(colourTargets, size, RenderTextureFormat.ARGBFloat, 24);
                var depthRt = depth ? Target(depthTargets, size, RenderTextureFormat.Depth, 24) : null;
                var floatRt = depth ? Target(floatTargets, size, RenderTextureFormat.RFloat, 0) : null;
                foreach (var v in views)
                {
                    cam.transform.SetPositionAndRotation(v.Position, v.Rotation);
                    cam.orthographicSize = v.Width * 0.5f;
                    cam.nearClipPlane = Near;
                    cam.farClipPlane = Mathf.Max(v.Far, Near * 2f);
                    var image = new DrawnImage { Size = size };
                    if (!Submit(colourRt)) { ok = false; break; }
                    image.Colour = ReadColour(colourRt, size);
                    if (depth)
                    {
                        if (!Submit(depthRt)) { ok = false; break; }
                        Graphics.Blit(depthRt, floatRt, depthCopy);
                        image.Depth = ReadDepth(floatRt, size, cam.farClipPlane);
                    }
                    images.Add(image);
                    Renders++;
                }
            }
            catch (Exception e)
            {
                ok = false;
                Probe.Active?.Error("drawn: a render failed: " + e.Message);
            }
            finally
            {
                Restore();
                cam.targetTexture = null;
            }
            TotalMs += clock.Elapsed.TotalMilliseconds;
            return ok;
        }

        static bool Submit(RenderTexture target)
        {
            cam.targetTexture = target;
            cam.aspect = 1f;
#if TASKPROBE_URP
            if (GraphicsSettings.currentRenderPipeline is UniversalRenderPipelineAsset)
            {
                var single = new UniversalRenderPipeline.SingleCameraRequest { destination = target };
                if (RenderPipeline.SupportsRenderRequest(cam, single))
                {
                    RenderPipeline.SubmitRenderRequest(cam, single);
                    return true;
                }
            }
#endif
            if (GraphicsSettings.currentRenderPipeline != null)
            {
                var standard = new RenderPipeline.StandardRequest { destination = target };
                if (RenderPipeline.SupportsRenderRequest(cam, standard))
                {
                    RenderPipeline.SubmitRenderRequest(cam, standard);
                    return true;
                }
            }
            cam.Render();
            return true;
        }

        static Color[] ReadColour(RenderTexture rt, int size)
        {
            var read = Reader(colourReads, size, TextureFormat.RGBAFloat);
            var before = RenderTexture.active;
            RenderTexture.active = rt;
            read.ReadPixels(new Rect(0, 0, size, size), 0, 0, false);
            RenderTexture.active = before;
            return read.GetPixels();
        }

        /// <summary>Raw depth to metres from the camera plane: an orthographic depth is linear between the planes
        /// (reversed on D3D, Metal, Vulkan); the far plane itself is "nothing opaque".</summary>
        static float[] ReadDepth(RenderTexture rt, int size, float far)
        {
            var read = Reader(floatReads, size, TextureFormat.RFloat);
            var before = RenderTexture.active;
            RenderTexture.active = rt;
            read.ReadPixels(new Rect(0, 0, size, size), 0, 0, false);
            RenderTexture.active = before;
            var raw = read.GetPixelData<float>(0);
            var reversed = SystemInfo.usesReversedZBuffer;
            var depth = new float[size * size];
            for (var i = 0; i < depth.Length; i++)
            {
                var z = reversed ? 1f - raw[i] : raw[i];
                depth[i] = z >= 0.99999f || float.IsNaN(z) ? float.PositiveInfinity : Near + z * (far - Near);
            }
            return depth;
        }

        // ---------------------------------------------------------------- isolation and the probe's light

        static readonly List<Renderer> forcedOff = new List<Renderer>();
        static readonly List<Renderer> tuned = new List<Renderer>();
        static readonly List<int> tunedLightmap = new List<int>();
        static readonly List<LightProbeUsage> tunedProbes = new List<LightProbeUsage>();
        static readonly List<ReflectionProbeUsage> tunedReflections = new List<ReflectionProbeUsage>();
        static readonly List<Light> lightsOff = new List<Light>();
        static readonly List<ReflectionProbe> probesOff = new List<ReflectionProbe>();
#if TASKPROBE_TERRAIN
        static readonly List<Terrain> terrainsOff = new List<Terrain>();
        static readonly List<bool> terrainTrees = new List<bool>();
#endif
#if TASKPROBE_URP
        static readonly List<ScriptableRendererFeature> featuresOff = new List<ScriptableRendererFeature>();
        static UniversalRenderPipelineAsset urpAsset;
        static bool urpHdr;
        static float urpScale;
        static PropertyInfo featureList;
#endif
        static AmbientMode ambientMode;
        static Color ambientLight, ambientSky, ambientEquator, ambientGround;
        static SphericalHarmonicsL2 ambientProbe;
        static float ambientIntensity, reflectionIntensity;
        static bool fog;
        static DefaultReflectionMode reflectionMode;
        static Texture customReflection;

        static void Isolate(IList<Renderer> show, int mask, Bounds volume, DrawnLight light)
        {
            // every other drawn renderer the views could see
            Drawn(out var all, out var bounds);
            for (var i = 0; i < all.Count; i++)
            {
                var r = all[i];
                if (r == null || r.forceRenderingOff || (mask & (1 << r.gameObject.layer)) == 0 || showIds.Contains(r.GetInstanceID())) continue;
                if (!bounds[i].Intersects(volume)) continue;
                r.forceRenderingOff = true;
                forcedOff.Add(r);
            }
#if TASKPROBE_TERRAIN
            foreach (var t in Terrain.activeTerrains)
            {
                if (t == null || !t.drawHeightmap || (mask & (1 << t.gameObject.layer)) == 0) continue;
                terrainsOff.Add(t);
                terrainTrees.Add(t.drawTreesAndFoliage);
                t.drawHeightmap = false;
                t.drawTreesAndFoliage = false;
            }
#endif
            // the chosen renderers: lit by the flat ambient alone, no reflection probe
            foreach (var r in show)
            {
                if (r == null) continue;
                tuned.Add(r);
                tunedLightmap.Add(r.lightmapIndex);
                tunedProbes.Add(r.lightProbeUsage);
                tunedReflections.Add(r.reflectionProbeUsage);
                if (r.lightmapIndex >= 0 && r.lightmapIndex < 0xFFFE) r.lightmapIndex = -1;
                if (r.lightProbeUsage != LightProbeUsage.Off) r.lightProbeUsage = LightProbeUsage.Off;
                if (r.reflectionProbeUsage != ReflectionProbeUsage.Off) r.reflectionProbeUsage = ReflectionProbeUsage.Off;
            }
            foreach (var l in UnityEngine.Object.FindObjectsByType<Light>(FindObjectsInactive.Exclude, FindObjectsSortMode.None))
                if (l.enabled)
                {
                    l.enabled = false;
                    lightsOff.Add(l);
                }
            foreach (var p in UnityEngine.Object.FindObjectsByType<ReflectionProbe>(FindObjectsInactive.Exclude, FindObjectsSortMode.None))
                if (p.enabled)
                {
                    p.enabled = false;
                    probesOff.Add(p);
                }

            ambientMode = RenderSettings.ambientMode;
            ambientLight = RenderSettings.ambientLight;
            ambientSky = RenderSettings.ambientSkyColor;
            ambientEquator = RenderSettings.ambientEquatorColor;
            ambientGround = RenderSettings.ambientGroundColor;
            ambientProbe = RenderSettings.ambientProbe;
            ambientIntensity = RenderSettings.ambientIntensity;
            reflectionIntensity = RenderSettings.reflectionIntensity;
            fog = RenderSettings.fog;
            reflectionMode = RenderSettings.defaultReflectionMode;
            customReflection = RenderSettings.customReflectionTexture;
            // the ambient colour is gamma-encoded in a linear-space project (the engine linearises it for the shaders):
            // the white is set so that the shaders get WhiteAmbient
            var ambient = light == DrawnLight.White ? new Color(WhiteAmbient, WhiteAmbient, WhiteAmbient, 1f) : Color.black;
            if (QualitySettings.activeColorSpace == ColorSpace.Linear) ambient = ambient.gamma;
            RenderSettings.ambientMode = AmbientMode.Flat;
            RenderSettings.ambientLight = ambient;
            RenderSettings.ambientSkyColor = ambient;
            RenderSettings.ambientEquatorColor = ambient;
            RenderSettings.ambientGroundColor = ambient;
            RenderSettings.ambientIntensity = 1f;
            var sh = new SphericalHarmonicsL2();
            if (light == DrawnLight.White) sh.AddAmbientLight(new Color(WhiteAmbient, WhiteAmbient, WhiteAmbient, 1f));
            RenderSettings.ambientProbe = sh;
            RenderSettings.fog = false;
            RenderSettings.defaultReflectionMode = DefaultReflectionMode.Custom;
            RenderSettings.customReflectionTexture = black;
            RenderSettings.reflectionIntensity = 0f;

#if TASKPROBE_URP
            urpAsset = GraphicsSettings.currentRenderPipeline as UniversalRenderPipelineAsset;
            if (urpAsset != null)
            {
                urpHdr = urpAsset.supportsHDR;
                urpScale = urpAsset.renderScale;
                if (!urpHdr) urpAsset.supportsHDR = true;
                if (Mathf.Abs(urpScale - 1f) > 1e-4f) urpAsset.renderScale = 1f;
                // renderer features (SSAO, decals, full-screen passes, a game's own) are left out; RenderObjects may be
                // how a layer is drawn at all, so it stays
                ScriptableRenderer renderer = null;
                try { renderer = cam.GetUniversalAdditionalCameraData().scriptableRenderer; } catch (Exception) { }
                if (renderer != null)
                {
                    if (featureList == null) featureList = typeof(ScriptableRenderer).GetProperty("rendererFeatures", BindingFlags.Instance | BindingFlags.NonPublic | BindingFlags.Public);
                    if (featureList?.GetValue(renderer) is List<ScriptableRendererFeature> features)
                        foreach (var f in features)
                            if (f != null && f.isActive && f.GetType().Name != "RenderObjects")
                            {
                                f.SetActive(false);
                                featuresOff.Add(f);
                            }
                }
            }
#endif
        }

        static void Restore()
        {
            // in reverse of Isolate; each list emptied as it is put back
#if TASKPROBE_URP
            foreach (var f in featuresOff)
                if (f != null) f.SetActive(true);
            featuresOff.Clear();
            if (urpAsset != null)
            {
                if (urpAsset.supportsHDR != urpHdr) urpAsset.supportsHDR = urpHdr;
                if (urpAsset.renderScale != urpScale) urpAsset.renderScale = urpScale;
                urpAsset = null;
            }
#endif
            RenderSettings.ambientMode = ambientMode;
            RenderSettings.ambientLight = ambientLight;
            RenderSettings.ambientSkyColor = ambientSky;
            RenderSettings.ambientEquatorColor = ambientEquator;
            RenderSettings.ambientGroundColor = ambientGround;
            RenderSettings.ambientIntensity = ambientIntensity;
            RenderSettings.ambientProbe = ambientProbe;
            RenderSettings.fog = fog;
            RenderSettings.defaultReflectionMode = reflectionMode;
            RenderSettings.customReflectionTexture = customReflection;
            RenderSettings.reflectionIntensity = reflectionIntensity;
            foreach (var p in probesOff)
                if (p != null) p.enabled = true;
            probesOff.Clear();
            foreach (var l in lightsOff)
                if (l != null) l.enabled = true;
            lightsOff.Clear();
            for (var i = 0; i < tuned.Count; i++)
            {
                var r = tuned[i];
                if (r == null) continue;
                if (r.lightmapIndex != tunedLightmap[i]) r.lightmapIndex = tunedLightmap[i];
                if (r.lightProbeUsage != tunedProbes[i]) r.lightProbeUsage = tunedProbes[i];
                if (r.reflectionProbeUsage != tunedReflections[i]) r.reflectionProbeUsage = tunedReflections[i];
            }
            tuned.Clear();
            tunedLightmap.Clear();
            tunedProbes.Clear();
            tunedReflections.Clear();
#if TASKPROBE_TERRAIN
            for (var i = 0; i < terrainsOff.Count; i++)
            {
                if (terrainsOff[i] == null) continue;
                terrainsOff[i].drawHeightmap = true;
                terrainsOff[i].drawTreesAndFoliage = terrainTrees[i];
            }
            terrainsOff.Clear();
            terrainTrees.Clear();
#endif
            foreach (var r in forcedOff)
                if (r != null) r.forceRenderingOff = false;
            forcedOff.Clear();
        }

        // ---------------------------------------------------------------- lit / glow as rendered (Hooks.GlowRender)

        static int glowFrame = -1, glowLeft;
        static readonly Dictionary<int, RenderedGlow> glowSeen = new Dictionary<int, RenderedGlow>();
        static readonly List<Renderer> glowShow = new List<Renderer>(1);
        static readonly List<DrawnView> glowViews = new List<DrawnView>(4);
        static readonly List<DrawnImage> glowImages = new List<DrawnImage>(4);

        /// <summary>Glow renders since the play started and the time they took (cost reports).</summary>
        public static int GlowCalls;
        public static double GlowMs;

        [ProbeInit]
        static void Register()
        {
            Hooks.GlowRender = Glow;
        }

        /// <summary>One renderer alone with no light at all, from the four corners of a tetrahedron in its own frame
        /// (128 x 128, orthographic, HDR). At most 64 renders a frame (a sample) across every caller, each renderer
        /// once a frame.</summary>
        public static RenderedGlow Glow(Renderer r)
        {
            if (glowFrame != Time.frameCount)
            {
                glowFrame = Time.frameCount;
                glowLeft = GlowBudget;
                glowSeen.Clear();
            }
            if (r == null) return new RenderedGlow();
            var id = r.GetInstanceID();
            if (glowSeen.TryGetValue(id, out var seen)) return seen;
            var read = new RenderedGlow();
            if (glowLeft > 0 && Find.Drawn(r))
            {
                glowLeft--;
                var clock = Stopwatch.StartNew();
                read = RenderGlow(r);
                GlowCalls++;
                GlowMs += clock.Elapsed.TotalMilliseconds;
            }
            glowSeen[id] = read;
            return read;
        }

        static RenderedGlow RenderGlow(Renderer r)
        {
            // its own bounds box in the world: a mesh's local box turned and scaled with it; anything else (particles,
            // lines, trails, sprites: their bounds are drawn in world space) its world box
            Vector3 size, centre;
            Quaternion turn;
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
            var radius = Mathf.Max(size.magnitude * 0.5f, 0.01f);
            var width = radius * 2f * 1.02f;
            double seenArea = 0.0;
            glowViews.Clear();
            foreach (var corner in Tetrahedron)
            {
                var n = corner.normalized;
                var dir = turn * n;  // from the renderer toward the camera
                seenArea += Mathf.Abs(n.x) * size.y * size.z + Mathf.Abs(n.y) * size.x * size.z + Mathf.Abs(n.z) * size.x * size.y;
                glowViews.Add(new DrawnView
                {
                    Position = centre + dir * (radius + 0.5f), Rotation = Quaternion.LookRotation(-dir, Mathf.Abs(dir.y) > 0.99f ? turn * Vector3.forward : turn * Vector3.up),
                    Width = width, Far = 2f * radius + 1.0f,
                });
            }
            glowShow.Clear();
            glowShow.Add(r);
            if (!Render(glowShow, glowViews, GlowSize, DrawnLight.Dark, false, glowImages) || glowImages.Count != 4) return new RenderedGlow();
            var pixelArea = (double)(width / GlowSize) * (width / GlowSize);
            double sum = 0.0, peak = 0.0;
            foreach (var image in glowImages)
                foreach (var c in image.Colour)
                {
                    var l = Luminance(c);
                    if (l > 0.0 && !double.IsNaN(l) && !double.IsInfinity(l))
                    {
                        sum += l * pixelArea;
                        if (l > peak) peak = l;
                    }
                }
            var mean = seenArea > 1e-8 ? sum / seenArea : 0.0;
            var quarterSurface = (size.x * size.y + size.y * size.z + size.x * size.z) * 2.0 / 4.0;
            return new RenderedGlow { Ok = true, Brightest = peak, Glow = mean * quarterSurface };
        }

        /// <summary>Rec. 709 luminance of a linear colour.</summary>
        public static double Luminance(Color c) => 0.2126 * c.r + 0.7152 * c.g + 0.0722 * c.b;
    }
}
