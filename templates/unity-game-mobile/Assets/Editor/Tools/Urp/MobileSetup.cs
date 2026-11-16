// The mobile setup of an Android phone game (Platform.json at the repo root: this game is held in __ORIENTATION__, for
// good): the fifth run of the project's first open (Scripts/unity.ps1 setup), after ProjectSetup.Configure. It turns
// the project the first four runs made into a phone game:
//   - the URP pipeline asset set for a mid-range phone (no MSAA, no depth or opaque texture, one shadow cascade, a
//     short shadow distance, a few per-pixel additional lights without shadows);
//   - one quality level, Mobile, on every platform, so the Windows player draws what the phone draws;
//   - the Android player settings (package name, SDK levels, arm64 alone, IL2CPP, Vulkan alone, the orientation);
//   - the Windows player's window at the phone's size (__PHONE_WIDTH__x__PHONE_HEIGHT__): on the PC the game is built, played and
//     recorded as that player.
// The validator holds the project to these settings (tools/validate-game.py, rule `mobile`): keep them as they are.
// Safe to run again.
using System;
using System.Collections.Generic;
using System.Linq;
using UnityEditor;
using UnityEditor.Build;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Rendering.Universal;

namespace __PROJECT__.EditorTools.Urp
{
    public static class MobileSetup
    {
        public const string Orientation = "__ORIENTATION__";
        public const int Width = __PHONE_WIDTH__, Height = __PHONE_HEIGHT__;
        public const string Package = "com.__ANDROID_NAME__.game";
        public const int MinSdk = 26, TargetSdk = 34;
        public const string Quality = "Mobile";
        const string PipelinePath = "Assets/Settings/Rendering/URP_Pipeline.asset";

        public static void Apply()
        {
            var pipeline = AssetDatabase.LoadAssetAtPath<UniversalRenderPipelineAsset>(PipelinePath);
            if (pipeline == null)
            {
                WorkflowLog.Row("project.mobile", PipelinePath, new Dictionary<string, object>
                    { ["error"] = "no URP pipeline asset: the first open's URP run (Urp.UrpSetup.Apply) comes before this one" }, status: "failed");
                EditorApplication.Exit(1);
                return;
            }
            var unset = Pipeline(pipeline);
            var levels = OneQualityLevel(pipeline);
            Player();
            AssetDatabase.SaveAssets();

            var ok = unset.Count == 0 && QualitySettings.names.SequenceEqual(new[] { Quality });
            var p = new Dictionary<string, object>
            {
                ["platform"] = "mobile",
                ["orientation"] = Orientation,
                ["window"] = new[] { Width, Height },
                ["package"] = Package,
                ["min_sdk"] = MinSdk,
                ["target_sdk"] = TargetSdk,
                ["architecture"] = "arm64",
                ["backend"] = "il2cpp",
                ["graphics"] = "vulkan",
                ["quality_levels_before"] = levels,
                ["quality_levels"] = QualitySettings.names,
                ["pipeline"] = PipelinePath,
            };
            if (unset.Count > 0) p["pipeline_settings_not_found"] = unset.ToArray();
            WorkflowLog.Row("project.mobile", "ProjectSettings/ProjectSettings.asset", p, status: ok ? "observed" : "failed");
            if (!ok) EditorApplication.Exit(1);   // a failed row with exit 0 would let new-game.ps1 commit it as done
        }

        /// <summary>The pipeline asset for a mid-range phone. What has no public setter is written through the asset's
        /// serialized fields; the names of any that this URP version no longer has come back.</summary>
        static List<string> Pipeline(UniversalRenderPipelineAsset pipeline)
        {
            pipeline.supportsCameraDepthTexture = false;
            pipeline.supportsCameraOpaqueTexture = false;
            pipeline.msaaSampleCount = 1;
            pipeline.renderScale = 1f;
            pipeline.shadowDistance = 40f;
            pipeline.shadowCascadeCount = 1;
            pipeline.maxAdditionalLightsCount = 4;
            var so = new SerializedObject(pipeline);
            var unset = new List<string>();
            foreach (var (name, value) in new[]
                     {
                         ("m_MainLightShadowmapResolution", 1024),
                         ("m_AdditionalLightsRenderingMode", 1),      // per pixel
                         ("m_AdditionalLightShadowsSupported", 0),
                         ("m_SoftShadowsSupported", 0),
                     })
            {
                var field = so.FindProperty(name);
                if (field == null) { unset.Add(name); continue; }
                if (field.propertyType == SerializedPropertyType.Boolean) field.boolValue = value != 0;
                else field.intValue = value;
            }
            so.ApplyModifiedPropertiesWithoutUndo();
            EditorUtility.SetDirty(pipeline);
            return unset;
        }

        /// <summary>One quality level, Mobile, the default on every platform, drawn with the pipeline: the level a new
        /// project starts a phone in (Medium) is kept and renamed, the others go. The levels there were come back.</summary>
        static string[] OneQualityLevel(RenderPipelineAsset pipeline)
        {
            var before = QualitySettings.names;
            var so = new SerializedObject(Unsupported.GetSerializedAssetInterfaceSingleton("QualitySettings"));
            var levels = so.FindProperty("m_QualitySettings");
            var keep = Math.Max(0, Array.IndexOf(before, before.Contains(Quality) ? Quality : "Medium"));
            for (var i = levels.arraySize - 1; i >= 0; i--)
                if (i != keep) levels.DeleteArrayElementAtIndex(i);
            levels.GetArrayElementAtIndex(0).FindPropertyRelative("name").stringValue = Quality;
            so.FindProperty("m_CurrentQuality").intValue = 0;
            var perPlatform = so.FindProperty("m_PerPlatformDefaultQuality");
            for (var i = 0; perPlatform != null && i < perPlatform.arraySize; i++)
            {
                var level = perPlatform.GetArrayElementAtIndex(i).FindPropertyRelative("second");
                if (level != null) level.intValue = 0;
            }
            so.ApplyModifiedPropertiesWithoutUndo();

            QualitySettings.SetQualityLevel(0, false);
            QualitySettings.renderPipeline = pipeline;
            QualitySettings.antiAliasing = 0;
            QualitySettings.skinWeights = SkinWeights.FourBones;
            QualitySettings.lodBias = 1f;
            QualitySettings.globalTextureMipmapLimit = 0;
            QualitySettings.anisotropicFiltering = AnisotropicFiltering.Enable;
            GraphicsSettings.defaultRenderPipeline = pipeline;
            return before;
        }

        static void Player()
        {
            var android = NamedBuildTarget.Android;
            PlayerSettings.SetApplicationIdentifier(android, Package);
            PlayerSettings.bundleVersion = "1.0";
            PlayerSettings.Android.bundleVersionCode = 1;
            PlayerSettings.Android.minSdkVersion = (AndroidSdkVersions)MinSdk;
            PlayerSettings.Android.targetSdkVersion = (AndroidSdkVersions)TargetSdk;
            PlayerSettings.Android.targetArchitectures = AndroidArchitecture.ARM64;
            PlayerSettings.SetScriptingBackend(android, ScriptingImplementation.IL2CPP);
            PlayerSettings.SetUseDefaultGraphicsAPIs(BuildTarget.Android, false);
            PlayerSettings.SetGraphicsAPIs(BuildTarget.Android, new[] { GraphicsDeviceType.Vulkan });

            // one way of holding the phone, for good: upright, or on its side (either side)
            var portrait = Orientation == "portrait";
            PlayerSettings.defaultInterfaceOrientation = portrait ? UIOrientation.Portrait : UIOrientation.AutoRotation;
            PlayerSettings.allowedAutorotateToPortrait = false;
            PlayerSettings.allowedAutorotateToPortraitUpsideDown = false;
            PlayerSettings.allowedAutorotateToLandscapeLeft = !portrait;
            PlayerSettings.allowedAutorotateToLandscapeRight = !portrait;

            // the Windows player, which is what is played, pictured and recorded on the PC: a window of the phone's size
            PlayerSettings.fullScreenMode = FullScreenMode.Windowed;
            PlayerSettings.resizableWindow = false;
            PlayerSettings.defaultScreenWidth = Width;
            PlayerSettings.defaultScreenHeight = Height;
        }
    }
}
