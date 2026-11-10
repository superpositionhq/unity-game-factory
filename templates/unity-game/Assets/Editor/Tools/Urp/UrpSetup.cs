// Makes URP the project's render pipeline: one Universal Renderer, one pipeline asset, assigned as the default and to
// every quality level. This assembly compiles only once the URP package is installed (defineConstraints HAS_URP in
// its .asmdef), so the project still compiles before ProjectSetup.AddPackages has run.
using System.Collections.Generic;
using System.IO;
using UnityEditor;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Rendering.Universal;

namespace __PROJECT__.EditorTools.Urp
{
    public static class UrpSetup
    {
        const string Folder = "Assets/Settings/Rendering";
        const string RendererPath = Folder + "/URP_Renderer.asset";
        const string PipelinePath = Folder + "/URP_Pipeline.asset";
        const string DefaultPostProcessData = "Packages/com.unity.render-pipelines.universal/Runtime/Data/PostProcessData.asset";

        public static void Apply()
        {
            Directory.CreateDirectory(Folder);

            var renderer = AssetDatabase.LoadAssetAtPath<UniversalRendererData>(RendererPath);
            if (renderer == null)
            {
                renderer = ScriptableObject.CreateInstance<UniversalRendererData>();
                if (renderer.postProcessData == null)
                    renderer.postProcessData = AssetDatabase.LoadAssetAtPath<PostProcessData>(DefaultPostProcessData);
                AssetDatabase.CreateAsset(renderer, RendererPath);
            }

            var pipeline = AssetDatabase.LoadAssetAtPath<UniversalRenderPipelineAsset>(PipelinePath);
            if (pipeline == null)
            {
                pipeline = UniversalRenderPipelineAsset.Create(renderer);
                AssetDatabase.CreateAsset(pipeline, PipelinePath);
            }

            GraphicsSettings.defaultRenderPipeline = pipeline;
            var current = QualitySettings.GetQualityLevel();
            for (var i = 0; i < QualitySettings.names.Length; i++)
            {
                QualitySettings.SetQualityLevel(i, false);
                QualitySettings.renderPipeline = pipeline;
            }
            QualitySettings.SetQualityLevel(current, false);
            AssetDatabase.SaveAssets();

            WorkflowLog.Row("render.pipeline", PipelinePath, new Dictionary<string, object>
            {
                ["pipeline"] = "URP",
                ["renderer"] = RendererPath,
                ["post_process_data"] = renderer.postProcessData != null,
                ["quality_levels"] = QualitySettings.names,
            });
        }
    }
}
