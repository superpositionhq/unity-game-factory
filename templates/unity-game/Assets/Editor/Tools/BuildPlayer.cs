// Builds the Windows x64 player from the scenes in the build list (File > Build Profiles), headless:
//   Scripts/unity.ps1 build [-Development] [-Backend mono|il2cpp]
// which runs  Unity -batchmode -nographics -quit -executeMethod __PROJECT__.EditorTools.BuildPlayer.BuildWindows
//             -buildOut <dir> [-development] [-backend mono|il2cpp]
// Release builds (no -development) default to IL2CPP and development builds to Mono. IL2CPP needs the Windows Build
// Support (IL2CPP) module and Visual Studio's C++ workload; without them pass -backend mono. The project's own scripting
// backend setting is put back after the build, so a build never leaves ProjectSettings changed.
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEditor.Build;
using UnityEditor.Build.Reporting;
using UnityEngine;

namespace __PROJECT__.EditorTools
{
    public static class BuildPlayer
    {
        public static void BuildWindows()
        {
            var args = Environment.GetCommandLineArgs();
            var development = args.Contains("-development");
            var backend = Arg(args, "-backend") ?? (development ? "mono" : "il2cpp");
            var outDir = Arg(args, "-buildOut") ?? Path.Combine("Build", "Windows");
            var exe = Path.Combine(outDir, "__PROJECT__.exe");

            var scenes = EditorBuildSettings.scenes.Where(s => s.enabled).Select(s => s.path).ToArray();
            if (scenes.Length == 0)
            {
                WorkflowLog.Row("build.player", Relative(exe), new Dictionary<string, object> { ["error"] = "no enabled scene in the build list" }, status: "failed");
                EditorApplication.Exit(1);
                return;
            }

            // A fresh folder every time: Unity refuses to build IL2CPP over a Mono build (and the reverse) in one folder.
            // Only a folder under the project's Build/ is ever cleared.
            var fullOut = Path.GetFullPath(outDir);
            var buildRoot = Path.GetFullPath(Path.Combine(WorkflowLog.ProjectRoot, "Build")) + Path.DirectorySeparatorChar;
            if (Directory.Exists(fullOut) && fullOut.StartsWith(buildRoot, StringComparison.OrdinalIgnoreCase))
                Directory.Delete(fullOut, true);

            var target = NamedBuildTarget.Standalone;
            var before = PlayerSettings.GetScriptingBackend(target);
            PlayerSettings.SetScriptingBackend(target, backend == "il2cpp" ? ScriptingImplementation.IL2CPP : ScriptingImplementation.Mono2x);
            BuildReport report;
            try
            {
                report = BuildPipeline.BuildPlayer(new BuildPlayerOptions
                {
                    scenes = scenes,
                    locationPathName = exe,
                    target = BuildTarget.StandaloneWindows64,
                    targetGroup = BuildTargetGroup.Standalone,
                    options = development ? BuildOptions.Development : BuildOptions.None,
                });
            }
            finally
            {
                PlayerSettings.SetScriptingBackend(target, before);
                AssetDatabase.SaveAssets();
            }

            var summary = report.summary;
            var ok = summary.result == BuildResult.Succeeded;
            WorkflowLog.Row("build.player", Relative(exe), new Dictionary<string, object>
            {
                ["result"] = summary.result.ToString(),
                ["configuration"] = development ? "development" : "release",
                ["backend"] = backend,
                ["scenes"] = scenes,
                ["errors"] = summary.totalErrors,
                ["warnings"] = summary.totalWarnings,
                ["seconds"] = (int)summary.totalTime.TotalSeconds,
                ["bytes"] = (long)summary.totalSize,
            }, status: ok ? "observed" : "failed");
            EditorApplication.Exit(ok ? 0 : 1);
        }

        /// <summary>A path as the workflow row names it: relative to the project, never a machine path.</summary>
        static string Relative(string path)
        {
            var full = Path.GetFullPath(path).Replace('\\', '/');
            var root = WorkflowLog.ProjectRoot.Replace('\\', '/').TrimEnd('/') + "/";
            return full.StartsWith(root, StringComparison.OrdinalIgnoreCase) ? full.Substring(root.Length) : Path.GetFileName(full);
        }

        static string Arg(string[] args, string name)
        {
            var i = Array.IndexOf(args, name);
            return i >= 0 && i + 1 < args.Length ? args[i + 1] : null;
        }
    }
}
