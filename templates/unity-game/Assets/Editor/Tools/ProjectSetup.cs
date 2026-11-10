// The project's first open (Scripts/unity.ps1 setup, run once by new-game.ps1 or by the session when the editor was
// missing at creation), in four batchmode runs because each needs what the one before it installed:
//   1. ProjectSetup.AddPackages          (no -quit: waits for the Package Manager, then exits itself)
//   2. Urp.UrpSetup.Apply                (needs the URP package compiled: creates the pipeline asset, makes it the default)
//   3. ProjectSetup.ImportTextEssentials (no -quit: TextMeshPro's fonts and settings; a package import finishes on the
//                                         editor's update loop, never inside the method that starts it)
//   4. ProjectSetup.Configure            (player and editor settings: company, colour space, Input System only, windowing)
// Each run logs its own workflow.jsonl row. Packages are added by name, so the Package Manager picks the version it
// recommends for this editor (6000.3.28f1: Cinemachine 3.1.7 from the registry, where the editor bundles 2.10.7 for
// offline use); the resulting Packages/manifest.json and packages-lock.json are committed.
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEditor.PackageManager;
using UnityEditor.PackageManager.Requests;
using UnityEngine;

namespace __PROJECT__.EditorTools
{
    public static class ProjectSetup
    {
        /// <summary>The packages every game starts with: URP, the Input System, Cinemachine 3, uGUI + TextMeshPro,
        /// NavMesh, Timeline and the Test Framework.</summary>
        static readonly string[] StartPackages =
        {
            "com.unity.render-pipelines.universal",
            "com.unity.inputsystem",
            "com.unity.cinemachine",
            "com.unity.ugui",
            "com.unity.ai.navigation",
            "com.unity.timeline",
            "com.unity.test-framework",
        };

        static AddAndRemoveRequest request;
        static DateTime started;

        /// <summary>Run without -quit: the request finishes on the editor's update loop, then this exits.</summary>
        public static void AddPackages()
        {
            started = DateTime.UtcNow;
            request = Client.AddAndRemove(StartPackages, null);
            EditorApplication.update += WaitForPackages;
        }

        static void WaitForPackages()
        {
            if (!request.IsCompleted)
            {
                if ((DateTime.UtcNow - started).TotalMinutes < 20) return;
                Finish(false, "the Package Manager did not answer in 20 minutes");
                return;
            }
            if (request.Status == StatusCode.Success)
                Finish(true, null);
            else
                Finish(false, request.Error?.message ?? "unknown Package Manager error");
        }

        static void Finish(bool ok, string error)
        {
            EditorApplication.update -= WaitForPackages;
            var p = new Dictionary<string, object> { ["requested"] = StartPackages };
            if (ok) p["installed"] = request.Result.Select(x => $"{x.name}@{x.version}").ToArray();
            else p["error"] = error;
            WorkflowLog.Row("project.packages", "Packages/manifest.json", p, status: ok ? "observed" : "failed");
            EditorApplication.Exit(ok ? 0 : 1);
        }

        const string TextEssentials = "Packages/com.unity.ugui/Package Resources/TMP Essential Resources.unitypackage";
        const string TextSettings = "Assets/TextMesh Pro/Resources/TMP Settings.asset";

        /// <summary>TextMeshPro's essential resources (its settings, default font asset and shaders) into
        /// Assets/TextMesh Pro: without them TMP text draws nothing. Run without -quit: it exits when the import is done.</summary>
        public static void ImportTextEssentials()
        {
            if (File.Exists(TextSettings))
            {
                // setup run again: nothing to import, but every run logs its row
                WorkflowLog.Row("asset.import", "Assets/TextMesh Pro", new Dictionary<string, object>
                    { ["package"] = "TMP Essential Resources", ["settings_present"] = true, ["skipped"] = "already imported" });
                EditorApplication.Exit(0);
                return;
            }
            started = DateTime.UtcNow;
            AssetDatabase.importPackageCompleted += TextImported;
            AssetDatabase.importPackageFailed += TextFailed;
            EditorApplication.update += WaitForText;
            AssetDatabase.ImportPackage(Path.GetFullPath(TextEssentials), false);
        }

        static void TextImported(string name) => FinishText(null);

        static void TextFailed(string name, string error) => FinishText(error ?? "the import failed");

        static void WaitForText()
        {
            if ((DateTime.UtcNow - started).TotalMinutes > 10) FinishText("the import did not finish in 10 minutes");
        }

        static void FinishText(string error)
        {
            EditorApplication.update -= WaitForText;
            AssetDatabase.importPackageCompleted -= TextImported;
            AssetDatabase.importPackageFailed -= TextFailed;
            AssetDatabase.Refresh();
            var present = File.Exists(TextSettings);
            var p = new Dictionary<string, object> { ["package"] = "TMP Essential Resources", ["settings_present"] = present };
            if (error != null) p["error"] = error;
            var ok = error == null && present;
            WorkflowLog.Row("asset.import", "Assets/TextMesh Pro", p, status: ok ? "observed" : "failed");
            EditorApplication.Exit(ok ? 0 : 1);
        }

        /// <summary>Player and editor settings every game shares. Safe to run again.</summary>
        public static void Configure()
        {
            // companyName is the game's own name: it is written to the build's <Game>_Data\app.info and names the
            // Application.persistentDataPath folder.
            PlayerSettings.companyName = "__TITLE__";
            PlayerSettings.productName = "__TITLE__";
            PlayerSettings.colorSpace = ColorSpace.Linear;
            // The game never pauses or goes quiet when its window loses focus: a play behind another window keeps
            // running (and so do AutoPlay runs and recordings).
            PlayerSettings.runInBackground = true;
            PlayerSettings.visibleInBackground = true;
            PlayerSettings.fullScreenMode = FullScreenMode.FullScreenWindow;
            PlayerSettings.resizableWindow = true;
            PlayerSettings.defaultScreenWidth = 1920;
            PlayerSettings.defaultScreenHeight = 1080;
            PlayerSettings.usePlayerLog = true;
            // The project's own backend stays Mono (fast iteration); BuildPlayer switches to IL2CPP for a release build
            // and puts this back. Set explicitly so that put-back writes nothing new into ProjectSettings.asset.
            PlayerSettings.SetScriptingBackend(UnityEditor.Build.NamedBuildTarget.Standalone, ScriptingImplementation.Mono2x);

            // Input System package only (the old Input Manager off): 1 = new, 2 = both. No public API sets it.
            var playerSettings = Unsupported.GetSerializedAssetInterfaceSingleton("PlayerSettings");
            var so = new SerializedObject(playerSettings);
            var handler = so.FindProperty("activeInputHandler");
            var inputSet = handler != null;
            if (inputSet)
            {
                handler.intValue = 1;
                so.ApplyModifiedPropertiesWithoutUndo();
            }

            // Visible .meta files and text YAML, so every asset diffs and merges in git (also set by the template).
            EditorSettings.serializationMode = SerializationMode.ForceText;
            VersionControlSettings.mode = "Visible Meta Files";
            AssetDatabase.SaveAssets();

            WorkflowLog.Row("project.configure", "ProjectSettings/ProjectSettings.asset", new Dictionary<string, object>
            {
                ["company"] = PlayerSettings.companyName,
                ["color_space"] = PlayerSettings.colorSpace.ToString(),
                ["input"] = inputSet ? "input-system-only" : "unchanged (activeInputHandler not found)",
                ["run_in_background"] = true,
                ["fullscreen"] = PlayerSettings.fullScreenMode.ToString(),
                ["serialization"] = "force-text",
                ["meta_files"] = "visible",
            }, status: inputSet ? "observed" : "failed");
            if (!inputSet) EditorApplication.Exit(1);   // a failed row with exit 0 would let new-game.ps1 commit it as done
        }
    }
}
