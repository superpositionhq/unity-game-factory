// Builds the game's Android APK (arm64, IL2CPP, release) from the scenes in the build list, headless:
//   Unity -batchmode -nographics -quit -buildTarget Android -executeMethod __PROJECT__.EditorTools.BuildAndroid.Build
//         -buildOut <dir> [-androidSdk <dir> -androidNdk <dir>]
// The release pipeline runs it on a machine that has the editor's Android Build Support module with its OpenJDK and
// Android SDK & NDK tools, or with an SDK and NDK installed apart from Unity, which -androidSdk and -androidNdk name
// (tools/unity-pipeline/build.ps1; machine/check.ps1 says whether the machine has them). A
// game session never needs it: the game is built, played and recorded on the PC as its Windows player
// (Scripts/unity.ps1 build), at the phone's size. The APK is signed with Unity's debug key: it installs on a phone for
// testing and is not a store upload.
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
    public static class BuildAndroid
    {
        public static void Build()
        {
            var args = Environment.GetCommandLineArgs();
            var at = Array.IndexOf(args, "-buildOut");
            var outDir = at >= 0 && at + 1 < args.Length ? args[at + 1] : Path.Combine("Build", "Android");
            var apk = Path.Combine(outDir, "__PROJECT__.apk");
            var target = Path.GetFileName(apk);

            if (!BuildPipeline.IsBuildTargetSupported(BuildTargetGroup.Android, BuildTarget.Android))
            {
                Fail(target, "this editor has no Android Build Support (Unity Hub > Installs > the editor > Add modules: Android Build Support with OpenJDK and Android SDK & NDK Tools)", 3);
                return;
            }
            var scenes = EditorBuildSettings.scenes.Where(s => s.enabled).Select(s => s.path).ToArray();
            if (scenes.Length == 0)
            {
                Fail(target, "no enabled scene in the build list (EditorBuildSettings.scenes: add the game's scenes from an editor step)", 1);
                return;
            }

            // A fresh folder every time; only a folder under the project's Build/ is ever cleared.
            var fullOut = Path.GetFullPath(outDir);
            var buildRoot = Path.GetFullPath(Path.Combine(WorkflowLog.ProjectRoot, "Build")) + Path.DirectorySeparatorChar;
            if (Directory.Exists(fullOut) && fullOut.StartsWith(buildRoot, StringComparison.OrdinalIgnoreCase))
                Directory.Delete(fullOut, true);
            Directory.CreateDirectory(fullOut);

            var tools = Outside(args, "-androidSdk", "sdkRootPath") ?? Outside(args, "-androidNdk", "ndkRootPath");
            if (tools != null)
            {
                Fail(target, tools, 1);
                return;
            }
            EditorUserBuildSettings.buildAppBundle = false;   // an .apk, one file to install
            var report = BuildPipeline.BuildPlayer(new BuildPlayerOptions
            {
                scenes = scenes,
                locationPathName = apk,
                target = BuildTarget.Android,
                targetGroup = BuildTargetGroup.Android,
                options = BuildOptions.None,
            });
            var summary = report.summary;
            var ok = summary.result == BuildResult.Succeeded;
            var p = new Dictionary<string, object>
            {
                ["result"] = summary.result.ToString(),
                ["platform"] = "android",
                ["configuration"] = "release",
                ["backend"] = PlayerSettings.GetScriptingBackend(NamedBuildTarget.Android) == ScriptingImplementation.IL2CPP ? "il2cpp" : "mono",
                ["architecture"] = PlayerSettings.Android.targetArchitectures.ToString(),
                ["package"] = PlayerSettings.GetApplicationIdentifier(NamedBuildTarget.Android),
                ["version_name"] = PlayerSettings.bundleVersion,
                ["version_code"] = PlayerSettings.Android.bundleVersionCode,
                ["min_sdk"] = (int)PlayerSettings.Android.minSdkVersion,
                ["target_sdk"] = (int)PlayerSettings.Android.targetSdkVersion,
                ["scenes"] = scenes,
                ["errors"] = summary.totalErrors,
                ["warnings"] = summary.totalWarnings,
                ["seconds"] = (int)summary.totalTime.TotalSeconds,
                ["bytes"] = (long)summary.totalSize,
            };
            var error = report.steps.SelectMany(s => s.messages).Where(m => m.type == LogType.Error || m.type == LogType.Exception)
                .Select(m => m.content).FirstOrDefault();
            if (!ok && !string.IsNullOrEmpty(error)) p["error"] = error.Split('\n')[0].Trim();
            WorkflowLog.Row("build.player", target, p, status: ok ? "observed" : "failed");
            EditorApplication.Exit(ok ? 0 : 1);
        }

        // An SDK or NDK installed apart from Unity (`flag` names its folder): the editor is told where it is, for
        // this run. Through reflection: the settings' type is the Android module's, which a machine that only plays
        // the game need not have. Returns what went wrong, or null.
        static string Outside(string[] args, string flag, string setting)
        {
            var at = Array.IndexOf(args, flag);
            if (at < 0 || at + 1 >= args.Length) return null;
            var folder = args[at + 1];
            if (!Directory.Exists(folder)) return flag + " " + folder + ": no such folder";
            var type = AppDomain.CurrentDomain.GetAssemblies()
                .Select(a => a.GetType("UnityEditor.Android.AndroidExternalToolsSettings")).FirstOrDefault(t => t != null);
            var property = type?.GetProperty(setting, System.Reflection.BindingFlags.Public | System.Reflection.BindingFlags.Static);
            if (property == null) return "this editor's Android module has no " + setting + " setting: " + flag + " cannot be used";
            property.SetValue(null, folder);
            return null;
        }

        static void Fail(string target, string error, int code)
        {
            WorkflowLog.Row("build.player", target, new Dictionary<string, object> { ["platform"] = "android", ["error"] = error }, status: "failed");
            EditorApplication.Exit(code);
        }
    }
}
