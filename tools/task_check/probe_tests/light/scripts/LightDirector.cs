// LightLab: switches a light on mid-play, cycles the ambient mode, and logs what the engine itself holds (the culled
// lights' finalColor, the ambient probe) so the probe's light sums can be checked against it.
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Rendering;

namespace LightTests
{
    public sealed class LightDirector : MonoBehaviour
    {
        public Light switchOn;          // off at the start, on at 3 s
        public float switchAt = 3f;
        public Camera cullFrom;         // a disabled camera that sees every light (for the finalColor log)
        float nextLog;
        int phase = -1;

        void Start()
        {
            PlayClock.Reset();
            if (switchOn != null) switchOn.enabled = false;
            RenderPipelineManager.beginCameraRendering += OnBegin;
        }

        void OnDestroy() { RenderPipelineManager.beginCameraRendering -= OnBegin; }

        void Update()
        {
            var t = PlayClock.T;
            if (switchOn != null && !switchOn.enabled && t >= switchAt)
            {
                switchOn.enabled = true;
                Debug.Log($"LT: t={t:F2} switched on {switchOn.name}");
            }
            // ambient: 0-4 s flat, 4-8 s gradient, 8-12 s skybox, 12+ s flat with intensity 2
            var want = t < 4f ? 0 : t < 8f ? 1 : t < 12f ? 2 : 3;
            if (want != phase)
            {
                phase = want;
                switch (want)
                {
                    case 0:
                        RenderSettings.ambientMode = AmbientMode.Flat;
                        RenderSettings.ambientLight = new Color(0.2f, 0.3f, 0.4f);
                        RenderSettings.ambientIntensity = 1f;
                        break;
                    case 1:
                        RenderSettings.ambientMode = AmbientMode.Trilight;
                        RenderSettings.ambientSkyColor = new Color(0.5f, 0.4f, 0.3f);
                        RenderSettings.ambientEquatorColor = new Color(0.1f, 0.1f, 0.1f);
                        RenderSettings.ambientGroundColor = new Color(0.05f, 0.05f, 0.05f);
                        break;
                    case 2:
                        RenderSettings.ambientMode = AmbientMode.Skybox;
                        RenderSettings.ambientIntensity = 1.5f;
                        LogAmbient("skybox before UpdateEnvironment");
                        DynamicGI.UpdateEnvironment();
                        break;
                    case 3:
                        RenderSettings.ambientMode = AmbientMode.Flat;
                        RenderSettings.ambientLight = new Color(0.2f, 0.3f, 0.4f);
                        RenderSettings.ambientIntensity = 2f;
                        break;
                }
                LogAmbient("phase " + want);
            }
            if (t >= nextLog)
            {
                nextLog += 1f;
                LogAmbient("tick");
            }
        }

        static void LogAmbient(string what)
        {
            var up = new Color[1];
            RenderSettings.ambientProbe.Evaluate(new[] { Vector3.up }, up);
            Debug.Log($"LT: t={PlayClock.T:F2} ambient {what}: mode {RenderSettings.ambientMode} probe_up {Fmt(up[0])} lum {Lum(up[0]):F5} " +
                      $"flat {Fmt(RenderSettings.ambientLight.linear)} sky {Fmt(RenderSettings.ambientSkyColor.linear)} intensity {RenderSettings.ambientIntensity:F3}");
        }

        static string Fmt(Color c) => $"({c.r:F5},{c.g:F5},{c.b:F5})";
        static double Lum(Color c) => 0.2126729 * c.r + 0.7151522 * c.g + 0.0721750 * c.b;

        float nextCull;

        void OnBegin(ScriptableRenderContext context, Camera camera)
        {
            if (cullFrom == null || PlayClock.T < nextCull || camera.cameraType != CameraType.Game) return;
            nextCull = PlayClock.T + 2f;
            if (!cullFrom.TryGetCullingParameters(out var p)) return;
            var results = context.Cull(ref p);
            foreach (var v in results.visibleLights)
            {
                var l = v.light;
                if (l == null) continue;
                var mine = l.color.linear * l.intensity;
                if (l.useColorTemperature && GraphicsSettings.lightsUseColorTemperature) mine *= Mathf.CorrelatedColorTemperatureToRGB(l.colorTemperature);
                Debug.Log($"LT: t={PlayClock.T:F2} visible {l.name} finalColor {Fmt(v.finalColor)} lum {Lum(v.finalColor):F5} recomputed {Fmt(mine)} lum {Lum(mine):F5} range {v.range:F2} spot {v.spotAngle:F1}");
            }
        }
    }
}
