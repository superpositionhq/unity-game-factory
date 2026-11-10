using System;
using System.Reflection;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Rendering.Universal;

namespace ProbeTests.Lighting
{
    /// <summary>LightLab's events, by frame (play time x 30): a lamp switched on; the URP asset's additional light
    /// shadows switched on (what the measure reads: the build stripped their shader variants, since the project's asset
    /// has none, so the frame can't show them) and the sun's shadow strength at 0.5 for 2 s; the ambient through its
    /// modes; additional lights off, then the main light off. With -lightbuiltin the render pipeline is switched off
    /// before the first frame (the built-in renderer draws).</summary>
    public sealed class LightEvents : MonoBehaviour
    {
        public Light switched, sun;
        int frames;

        void Awake()
        {
            if (Array.IndexOf(Environment.GetCommandLineArgs(), "-lightbuiltin") < 0) return;
            GraphicsSettings.defaultRenderPipeline = null;
            QualitySettings.renderPipeline = null;
            Debug.Log("LIGHT builtin: pipeline " + (GraphicsSettings.currentRenderPipeline == null ? "none" : GraphicsSettings.currentRenderPipeline.name));
        }

        void Update()
        {
            frames++;
            switch (frames)
            {
                case 105: switched.enabled = true; break;
                case 225:
                    Asset("supportsAdditionalLightShadows", true);
                    sun.shadowStrength = 0.5f;
                    break;
                case 285: sun.shadowStrength = 1f; break;
                case 345:
                    RenderSettings.ambientMode = AmbientMode.Trilight;
                    RenderSettings.ambientSkyColor = new Color(0.5f, 0.4f, 0.3f);
                    RenderSettings.ambientEquatorColor = new Color(0.1f, 0.1f, 0.1f);
                    RenderSettings.ambientGroundColor = new Color(0.05f, 0.05f, 0.05f);
                    break;
                case 375:
                    RenderSettings.ambientMode = AmbientMode.Skybox;
                    RenderSettings.ambientIntensity = 1.5f;
                    break;
                case 405: DynamicGI.UpdateEnvironment(); break;
                case 435:
                    RenderSettings.ambientMode = AmbientMode.Flat;
                    RenderSettings.ambientLight = new Color(0.2f, 0.3f, 0.4f);
                    RenderSettings.ambientIntensity = 2f;
                    break;
                case 465: Asset("additionalLightsRenderingMode", LightRenderingMode.Disabled); break;
                case 495:
                    Asset("additionalLightsRenderingMode", LightRenderingMode.PerPixel);
                    Asset("mainLightRenderingMode", LightRenderingMode.Disabled);
                    break;
            }
        }

        /// <summary>A setting of the URP asset in use, set as the Inspector would (its setters are internal).</summary>
        static void Asset(string name, object value)
        {
            var asset = GraphicsSettings.currentRenderPipeline;
            if (asset == null) return;
            var property = asset.GetType().GetProperty(name, BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic);
            property.GetSetMethod(true).Invoke(asset, new[] { value });
            Debug.Log("LIGHT asset " + name + " = " + value);
        }
    }
}
