// What the light and grading queries share: the Lights that are on, the colour URP lights with, which Lights URP draws
// at run time and which of them it shadows, the line of sight from a light to a point, the ambient light at a point, and
// the URP volume stack as it stands at the camera.
using System;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Rendering;
#if TASKPROBE_URP
using UnityEngine.Rendering.Universal;
#endif

namespace TaskProbe
{
    public static class LightKit
    {
        // core Color.hlsl Luminance (ColorUtils.Luminance), linear sRGB: the light measure takes the engine's own
        // luminance, as the original does (FLinearColor::GetLuminance); glow, screen and drawn use their Rec. 709 one
        const double LumR = 0.2126729, LumG = 0.7151522, LumB = 0.0721750;
        /// <summary>How far away a directional light's ray starts (m).</summary>
        public const float TraceLength = 2000f;
        /// <summary>A ray toward a point stops this short of it (m), so the surface the point lies on doesn't hide it.</summary>
        const float EndGap = 0.01f;

        public static double Luminance(Color c) => LumR * c.r + LumG * c.g + LumB * c.b;

        /// <summary>Whether URP is the render pipeline (what light and grading read is URP's).</summary>
        public static bool Urp
        {
            get
            {
#if TASKPROBE_URP
                return GraphicsSettings.currentRenderPipeline is UniversalRenderPipelineAsset;
#else
                return false;
#endif
            }
        }

        // ---------------------------------------------------------------- the Lights

        static readonly List<Light> lights = new List<Light>();
        static Light main;
        static int lightsStamp = -1;

        /// <summary>Every Light on an active object, in hierarchy order (a sum or a tie comes out the same in every play),
        /// looked up once a pass (Probe.Stamp).</summary>
        public static List<Light> Lights()
        {
            if (lightsStamp == Probe.Stamp) return lights;
            lightsStamp = Probe.Stamp;
            lights.Clear();
            lights.AddRange(UnityEngine.Object.FindObjectsByType<Light>(FindObjectsInactive.Exclude, FindObjectsSortMode.None));
            Find.SortByHierarchy(lights);
            main = MainLight();
            return lights;
        }

        /// <summary>URP's main light (UniversalRenderPipeline.GetMainLightIndex): the sun source of the Lighting settings
        /// when it is a directional light URP draws, else the one of the highest intensity (of equals the first in
        /// hierarchy order); none when the pipeline asset draws no main light, or without URP.</summary>
        static Light MainLight()
        {
#if TASKPROBE_URP
            if (!(GraphicsSettings.currentRenderPipeline is UniversalRenderPipelineAsset urp) || urp.mainLightRenderingMode != LightRenderingMode.PerPixel) return null;
            Light best = null;
            var sun = RenderSettings.sun;
            foreach (var l in lights)
            {
                if (l == null || l.type != LightType.Directional || !Find.LightOn(l) || Baked(l)) continue;
                if (l == sun) return l;
                if (best == null || l.intensity > best.intensity) best = l;
            }
            return best;
#else
            return null;
#endif
        }

        /// <summary>Whether URP lights with `l` at run time (Lights() first), and whether it draws its shadows: only then
        /// does a wall stop its light (a light without shadows lights through walls in the frame). Not a Light that is
        /// off, nor one whose bake stored its light in the lightmaps and light probes (one set to Baked but never baked
        /// still lights at run time, a Mixed one always does), nor an area light (URP only bakes those); and only what
        /// the pipeline asset lights: the main light when it is lit per pixel, the others when additional lights are on.
        /// Shadows: the light's own (on, of a strength above 0) where the asset has shadows for it: the main light's,
        /// point and spot lights' (URP shadows no other directional light). Without URP: every Light that is on,
        /// shadowed when its shadows are on and the quality settings have shadows.</summary>
        public static bool Lit(Light l, out bool shadowed)
        {
            shadowed = false;
            if (!Find.LightOn(l) || Baked(l)) return false;
            if (l.type != LightType.Directional && l.type != LightType.Point && l.type != LightType.Spot) return false;
            var casts = l.shadows != LightShadows.None && l.shadowStrength > 0f;
#if TASKPROBE_URP
            if (GraphicsSettings.currentRenderPipeline is UniversalRenderPipelineAsset urp)
            {
                if (l == main)
                {
                    shadowed = casts && urp.supportsMainLightShadows;
                    return true;
                }
                if (urp.additionalLightsRenderingMode == LightRenderingMode.Disabled) return false;
                shadowed = casts && l.type != LightType.Directional && urp.supportsAdditionalLightShadows;
                return true;
            }
#endif
            shadowed = casts && QualitySettings.shadows != UnityEngine.ShadowQuality.Disable;
            return true;
        }

        /// <summary>A Light whose last bake stored its light in the lightmaps and light probes: the engine leaves it out at
        /// run time. Light.lightmapBakeType is the editor's setting; bakingOutput is what the player has.</summary>
        static bool Baked(Light l)
        {
            var bake = l.bakingOutput;
            return bake.isBaked && bake.lightmapBakeType == LightmapBakeType.Baked;
        }

        /// <summary>The colour of a light's colour temperature as the engine multiplies it in (white when the light or the
        /// pipeline doesn't use temperature).</summary>
        static Color TemperatureColor(Light l)
        {
            if (l == null || !l.useColorTemperature || !GraphicsSettings.lightsUseColorTemperature) return Color.white;
            return Mathf.CorrelatedColorTemperatureToRGB(l.colorTemperature);
        }

        /// <summary>VisibleLight.finalColor as the engine builds it: colour x intensity (linear intensity in a linear
        /// project: URP sets lightsUseLinearIntensity there) x the temperature colour.</summary>
        public static Color FinalColor(Light l)
        {
            Color c;
            if (QualitySettings.activeColorSpace == ColorSpace.Linear)
                c = GraphicsSettings.lightsUseLinearIntensity ? l.color.linear * l.intensity : (l.color * l.intensity).linear;
            else c = l.color * l.intensity;
            c *= TemperatureColor(l);
            c.a = 1f;
            return c;
        }

        // ---------------------------------------------------------------- line of sight

#if TASKPROBE_PHYSICS
        static readonly RaycastHit[] Hits = new RaycastHit[64];
#endif

        /// <summary>Whether a collider stops the ray from a light at `from` to the point `to` (1 cm short of it, so the
        /// surface the point lies on doesn't): any collider but a trigger, one on the Ignore Raycast layer, the player's
        /// and `own`'s (the Light's object and what is under it). A ray doesn't hit a collider it starts inside, so a
        /// housing around a lamp never stops its light; one around the point does. Without the physics module nothing
        /// can.</summary>
        public static bool Blocked(Vector3 from, Vector3 to, Transform own)
        {
#if TASKPROBE_PHYSICS
            var delta = to - from;
            var length = delta.magnitude - EndGap;
            if (length <= 0f) return false;
            var dir = delta / delta.magnitude;
            var n = Physics.RaycastNonAlloc(from, dir, Hits, length, Physics.DefaultRaycastLayers, QueryTriggerInteraction.Ignore);
            if (n >= Hits.Length) return true;  // more hits than the buffer holds: one of them surely isn't the player's
            var player = Probe.Active != null ? Probe.Active.Player : null;
            for (var i = 0; i < n; i++)
            {
                var c = Hits[i].collider;
                if (c == null) continue;
                if (player != null && c.transform.IsChildOf(player.transform)) continue;
                if (own != null && c.transform.IsChildOf(own)) continue;
                return true;
            }
#endif
            return false;
        }

        // ---------------------------------------------------------------- ambient

        static readonly Vector3[] Up = { Vector3.up };
        static readonly Color[] UpResult = new Color[1];

        /// <summary>The light no Light gives an upward-facing surface at `p`: the spherical harmonics URP lights a moving
        /// object there with, evaluated straight up: the baked light probes around `p` when the scene has them (they
        /// hold the baked Lights, the sky and their bounces, shaded by walls as they were baked), else the ambient probe
        /// (the flat colour, the gradient or the skybox). URP doesn't shade either by walls at run time.</summary>
        public static double Ambient(Vector3 p)
        {
            SphericalHarmonicsL2 sh;
            var probes = LightmapSettings.lightProbes;
            if (probes != null && probes.count > 0) LightProbes.GetInterpolatedProbe(p, null, out sh);
            else sh = RenderSettings.ambientProbe;
            sh.Evaluate(Up, UpResult);
            return Math.Max(0.0, Luminance(UpResult[0]));
        }

        /// <summary>The ambient as the Lighting settings set it: its mode, its colour in the working space (the flat
        /// colour, the gradient's sky colour, or for a skybox the ambient probe straight up) and its intensity.</summary>
        public static void Sky(out string mode, out Color colour, out double intensity)
        {
            mode = RenderSettings.ambientMode.ToString();
            intensity = RenderSettings.ambientIntensity;
            switch (RenderSettings.ambientMode)
            {
                case AmbientMode.Flat: colour = Find.Linear(RenderSettings.ambientLight); break;
                case AmbientMode.Trilight: colour = Find.Linear(RenderSettings.ambientSkyColor); break;
                default:
                    RenderSettings.ambientProbe.Evaluate(Up, UpResult);
                    colour = UpResult[0];
                    break;
            }
            colour.a = 1f;
        }

        // ---------------------------------------------------------------- the volume stack at the camera

#if TASKPROBE_URP
        static VolumeStack own;  // the probe's own stack, blended for the camera at sample time
        static int stackStamp = -1;
        static VolumeStack stackCached;
        static string sourceCached;
        static bool postCached;

        /// <summary>The volume stack in effect at the player's camera now, looked up once a pass: the camera's own stack
        /// when it is updated only by script (URP renders with it as it stands), else every volume blended for the
        /// camera's volume trigger and layer mask at this moment (as URP's UpdateVolumeFramework does before it renders
        /// the camera). Null without URP, a camera, or URP's volume framework (URP sets it up when it first draws, which
        /// can come after a play's first sample). `post`: whether the camera renders post-processing at all.</summary>
        public static VolumeStack StackAt(out string source, out bool post)
        {
            if (stackStamp != Probe.Stamp)
            {
                stackStamp = Probe.Stamp;
                stackCached = Evaluate(out sourceCached, out postCached);
            }
            source = sourceCached;
            post = postCached;
            return stackCached;
        }

        static VolumeStack Evaluate(out string source, out bool post)
        {
            post = false;
            source = "none";
            if (!Urp) return null;
            var view = Probe.Active != null ? Probe.Active.View : null;
            if (view == null) return null;
            var data = view.GetComponent<UniversalAdditionalCameraData>();
            post = data != null && data.renderPostProcessing;
            var manager = VolumeManager.instance;
            if (manager == null || !manager.isInitialized) return null;
            if (data != null && !data.requiresVolumeFrameworkUpdate && data.volumeStack != null && data.volumeStack.isValid)
            {
                source = "camera_stack";
                return data.volumeStack;
            }
            if (own == null || !own.isValid) own = manager.CreateStack();
            LayerMask mask = data != null ? data.volumeLayerMask : (LayerMask)1;
            var trigger = data != null && data.volumeTrigger != null ? data.volumeTrigger : view.transform;
            manager.Update(own, trigger, mask);
            source = "camera";
            return own;
        }

        /// <summary>Whether the grade the camera's frame gets is known now: without URP (no grade is read: neutral), for a
        /// camera that renders no post-processing (its frame is ungraded), or once its stack can be read. Not without a
        /// camera, nor before URP has set up its volume framework: no value then (the original's exposure has none
        /// until the renderer has one), never a neutral one no frame shows.</summary>
        public static bool GradeKnown()
        {
            if (!Urp) return true;
            if (StackAt(out _, out var post) != null) return true;
            return !post && Probe.Active != null && Probe.Active.View != null;
        }

        /// <summary>2^postExposure of the stack at the camera; 1 without URP or post-processing on the camera; null while
        /// the grade isn't known (GradeKnown).</summary>
        public static double? Exposure()
        {
            if (!GradeKnown()) return null;
            var stack = StackAt(out _, out var post);
            if (stack == null || !post) return 1.0;
            var adjust = stack.GetComponent<ColorAdjustments>();
            return adjust != null ? Math.Pow(2.0, adjust.postExposure.value) : 1.0;
        }
#else
        public static bool GradeKnown() => true;
        public static double? Exposure() => 1.0;
#endif
    }
}
