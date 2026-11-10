// The project's first open (Scripts/unity.ps1 setup, run once by new-game.ps1 or by the session when the editor was
// missing at creation), in three batchmode runs because each needs what the one before it installed:
//   1. ProjectSetup.AddPackages   (no -quit: waits for the Package Manager, then exits itself)
//   2. Urp.UrpSetup.Apply         (needs the URP package compiled: creates the pipeline asset, makes it the default)
//   3. ProjectSetup.Configure     (player and editor settings: company, colour space, Input System only, windowing)
// Each run logs its own workflow.jsonl row. Packages are added by name so the Package Manager picks the versions that
// ship with this editor; the resulting Packages/manifest.json and packages-lock.json are committed.
using System;
using System.Collections.Generic;
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

        /// <summary>Player and editor settings every game shares. Safe to run again.</summary>
        public static void Configure()
        {
            // companyName is the game's own name: it becomes the exe's company and the persistentDataPath folder.
            PlayerSettings.companyName = "__TITLE__";
            PlayerSettings.productName = "__TITLE__";
            PlayerSettings.colorSpace = ColorSpace.Linear;
            // AutoPlay and recordings keep running when the window loses focus.
            PlayerSettings.runInBackground = true;
            PlayerSettings.visibleInBackground = true;
            PlayerSettings.fullScreenMode = FullScreenMode.FullScreenWindow;
            PlayerSettings.resizableWindow = true;
            PlayerSettings.defaultScreenWidth = 1920;
            PlayerSettings.defaultScreenHeight = 1080;
            PlayerSettings.usePlayerLog = true;

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
        }
    }
}
