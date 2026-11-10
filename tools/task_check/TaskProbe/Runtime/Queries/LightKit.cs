// What the light, grading and audio queries share: which Lights are on and the colour they light with (as URP hands it
// to its shaders), line-of-sight traces that ignore the player, and the URP volume stack as it stands at the camera.
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
        // core Color.hlsl Luminance / ColorUtils.Luminance: linear sRGB (Rec. 709) weights
        public const double LumR = 0.2126729, LumG = 0.7151522, LumB = 0.0721750;
        /// <summary>How far a trace toward a directional light or the sky reaches (m).</summary>
        public const float SkyReach = 2000f;
        /// <summary>A trace toward a point stops this short of it (m), so the surface the point lies on doesn't hide it.</summary>
        const float EndGap = 0.01f;

        public static double Luminance(Color c) => LumR * c.r + LumG * c.g + LumB * c.b;

        /// <summary>A Light that is on: enabled, active in the hierarchy, intensity above 0.</summary>
        public static bool On(Light l) => l != null && l.enabled && l.gameObject.activeInHierarchy && l.intensity > 0f;

        public static Light[] Lights() => UnityEngine.Object.FindObjectsByType<Light>(FindObjectsInactive.Exclude, FindObjectsSortMode.None);

        /// <summary>The colour of a light's colour temperature as the engine multiplies it in (white when the light or the
        /// pipeline doesn't use temperature).</summary>
        public static Color TemperatureColor(Light l)
        {
            if (l == null || !l.useColorTemperature || !GraphicsSettings.lightsUseColorTemperature) return Color.white;
            return Mathf.CorrelatedColorTemperatureToRGB(l.colorTemperature);
        }

        /// <summary>A colour from the editor's colour picker in the space lighting is done in (linear in a linear
        /// project).</summary>
        public static Color Working(Color c) => QualitySettings.activeColorSpace == ColorSpace.Linear ? c.linear : c;

        /// <summary>The light's colour without its intensity, in the working space, temperature applied.</summary>
        public static Color LitColor(Light l)
        {
            var c = Working(l.color) * TemperatureColor(l);
            c.a = 1f;
            return c;
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

        static readonly RaycastHit[] Hits = new RaycastHit[64];

        /// <summary>Whether a collider other than the player's (and `own`'s, a lamp's own housing) lies between `from` and
        /// `to`. Triggers and the Ignore Raycast layer never block.</summary>
        public static bool Blocked(Vector3 from, Vector3 to, Transform own)
        {
#if TASKPROBE_PHYSICS
            var delta = to - from;
            var length = delta.magnitude - EndGap;
            if (length <= 0f) return false;
            var dir = delta / delta.magnitude;
            var n = Physics.RaycastNonAlloc(from, dir, Hits, length, Physics.DefaultRaycastLayers, QueryTriggerInteraction.Ignore);
            if (n >= Hits.Length)
            {
                // more hits than the buffer holds: one of them surely isn't the player's
                return true;
            }
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

        /// <summary>Whether a ray from `from` along `dir` (unit) is blocked within SkyReach.</summary>
        public static bool BlockedToward(Vector3 from, Vector3 dir, Transform own) => Blocked(from, from + dir * SkyReach, own);

        // ---------------------------------------------------------------- ambient

        static readonly Vector3[] Up = { Vector3.up };
        static readonly Color[] UpResult = new Color[1];

        /// <summary>The ambient light falling on an upward-facing surface, as URP shades it: the ambient probe
        /// (RenderSettings.ambientProbe, which the engine builds from the flat colour, the gradient or the skybox with its
        /// intensity) evaluated straight up. `colour` is the setting itself (the flat colour, the gradient's sky colour, or
        /// the probe's value for a skybox), in the working space.</summary>
        public static double Ambient(out string mode, out Color colour, out double intensity)
        {
            mode = RenderSettings.ambientMode.ToString();
            intensity = RenderSettings.ambientIntensity;
            var probe = RenderSettings.ambientProbe;
            probe.Evaluate(Up, UpResult);
            var up = UpResult[0];
            switch (RenderSettings.ambientMode)
            {
                case UnityEngine.Rendering.AmbientMode.Flat: colour = Working(RenderSettings.ambientLight); break;
                case UnityEngine.Rendering.AmbientMode.Trilight: colour = Working(RenderSettings.ambientSkyColor); break;
                default: colour = up; break;
            }
            colour.a = 1f;
            return Math.Max(0.0, Luminance(up));
        }

        // ---------------------------------------------------------------- the volume stack at the camera

        /// <summary>The probe's own stack, blended for the camera at sample time.</summary>
#if TASKPROBE_URP
        static VolumeStack own;
        static int stackFrame = -1;
        static VolumeStack stackCached;
        static string sourceCached;
        static bool postCached;

        /// <summary>The volume stack in effect at the player's camera now: the camera's own stack when it is updated only
        /// by script (URP renders with it as it stands), else every volume blended for the camera's volume trigger and
        /// layer mask at this moment (as URP's UpdateVolumeFramework does before it renders the camera). Null without
        /// URP's volume manager or a camera. `post`: whether the camera renders post-processing at all.</summary>
        public static VolumeStack StackAt(out string source, out bool post)
        {
            if (stackFrame == Time.frameCount)
            {
                source = sourceCached;
                post = postCached;
                return stackCached;
            }
            stackFrame = Time.frameCount;
            stackCached = Evaluate(out sourceCached, out postCached);
            source = sourceCached;
            post = postCached;
            return stackCached;
        }

        static VolumeStack Evaluate(out string source, out bool post)
        {
            post = false;
            source = "none";
            if (!(GraphicsSettings.currentRenderPipeline is UniversalRenderPipelineAsset)) return null;
            var manager = VolumeManager.instance;
            if (manager == null || !manager.isInitialized) return null;
            var view = Probe.Active != null ? Probe.Active.View : null;
            if (view == null) return null;
            var data = view.GetComponent<UniversalAdditionalCameraData>();
            post = data != null && data.renderPostProcessing;
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

        /// <summary>2^postExposure of the stack at the camera; 1 without URP, a stack, or post-processing on the camera.</summary>
        public static double Exposure()
        {
            var stack = StackAt(out _, out var post);
            if (stack == null || !post) return 1.0;
            var adjust = stack.GetComponent<ColorAdjustments>();
            return adjust != null ? Math.Pow(2.0, adjust.postExposure.value) : 1.0;
        }
#else
        public static double Exposure() => 1.0;
#endif
    }
}
