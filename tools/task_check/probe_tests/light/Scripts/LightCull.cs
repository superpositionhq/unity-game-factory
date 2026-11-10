using System.Linq;
using UnityEngine;
using UnityEngine.Rendering;

namespace ProbeTests.Lighting
{
    /// <summary>What the engine itself holds for each Light, logged once at frame `at`: what its last bake stored
    /// (Light.bakingOutput), and the Lights culling finds visible from `cull` (a disabled camera that sees everything)
    /// with the colour URP lights with (VisibleLight.finalColor). Lines "LIGHT bake ..." and "LIGHT visible ...".</summary>
    public sealed class LightCull : MonoBehaviour
    {
        public Camera cull;
        public int at = 30;
        int frames;
        bool done;

        void OnEnable() { RenderPipelineManager.beginCameraRendering += Begin; }
        void OnDisable() { RenderPipelineManager.beginCameraRendering -= Begin; }
        void Update() { frames++; }

        void Begin(ScriptableRenderContext context, Camera camera)
        {
            if (done || frames < at || camera.cameraType != CameraType.Game) return;
            done = true;
            foreach (var l in FindObjectsByType<Light>(FindObjectsInactive.Include, FindObjectsSortMode.None).OrderBy(l => l.name))
            {
                var bake = l.bakingOutput;
                Debug.Log($"LIGHT bake {l.name} {bake.isBaked} {bake.lightmapBakeType} {bake.mixedLightingMode}");
            }
            if (cull == null || !cull.TryGetCullingParameters(out var p)) return;
            var results = context.Cull(ref p);
            foreach (var v in results.visibleLights)
            {
                if (v.light == null) continue;
                var c = v.finalColor;
                Debug.Log($"LIGHT visible {v.light.name} {c.r:R} {c.g:R} {c.b:R}");
            }
        }
    }
}
