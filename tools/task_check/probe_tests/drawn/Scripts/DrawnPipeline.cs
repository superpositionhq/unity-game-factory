using System;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Rendering.Universal;

namespace ProbeTests.Drawn
{
    /// <summary>With -drawnPipeline: what the player's camera draws with for the play, set before anything renders:
    /// "forward", "forwardplus", "deferred" or "2d" (that renderer of the family's own URP asset), "plain" (a URP asset
    /// with HDR off and render scale 0.75) or "builtin" (no render pipeline asset). The assets are referenced here so the
    /// build includes them and keeps their shader variants.</summary>
    [DefaultExecutionOrder(-31500)]
    public sealed class DrawnPipeline : MonoBehaviour
    {
        public UniversalRenderPipelineAsset Urp, Plain;

        void Awake()
        {
            var args = Environment.GetCommandLineArgs();
            var at = Array.IndexOf(args, "-drawnPipeline");
            if (at < 0 || at + 1 >= args.Length) return;
            switch (args[at + 1])
            {
                case "builtin": Use(null, 0); break;
                case "plain": Use(Plain, 0); break;
                case "forward": Use(Urp, 0); break;
                case "forwardplus": Use(Urp, 1); break;
                case "deferred": Use(Urp, 2); break;
                case "2d": Use(Urp, 3); break;
            }
        }

        static void Use(RenderPipelineAsset asset, int renderer)
        {
            GraphicsSettings.defaultRenderPipeline = asset;
            QualitySettings.renderPipeline = asset;
            if (asset != null) Camera.main.GetUniversalAdditionalCameraData().SetRenderer(renderer);
            Debug.Log("DRAWN pipeline " + (asset != null ? asset.name + " renderer " + renderer : "built-in"));
        }
    }
}
