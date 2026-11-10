// The checker's build of its scratch copy (contract section 5):
//   Unity -batchmode -nographics -quit -projectPath <copy> -executeMethod TaskProbe.EditorTools.Build.Player
//         -taskProbeBuild <request file>
// A Windows x64 Mono player, not a development build (no watermark on the frame), of the project's own enabled build
// scenes plus every scene the task's plays open. The build settings it changes are the copy's, for the plays only:
// the company name (so the plays' saves and settings are their own and never touch the real game's), no splash
// screen, windowed, running in the background, several instances allowed, and no static batching (so a renderer keeps
// its own mesh for the `mesh` selects and triangle counts; it draws the same). The game's assets and code are untouched.
// Scripts that don't compile stop Unity before this method runs: no result file, exit code 1.
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Security.Cryptography;
using System.Text;
using System.Text.RegularExpressions;
using UnityEditor;
using UnityEditor.Build;
using UnityEditor.Build.Reporting;
using UnityEngine;

namespace TaskProbe.EditorTools
{
    public static class Build
    {
        static readonly Regex Guid = new Regex("guid: ([0-9a-f]{32})", RegexOptions.CultureInvariant);

        public static void Player()
        {
            var args = Environment.GetCommandLineArgs();
            var at = Array.FindIndex(args, a => string.Equals(a, "-taskProbeBuild", StringComparison.OrdinalIgnoreCase));
            Dictionary<string, object> request = null;
            if (at >= 0 && at + 1 < args.Length)
            {
                try { request = Json.Obj(Json.Parse(File.ReadAllText(args[at + 1], Encoding.UTF8))); }
                catch (Exception e) { Debug.LogError("TaskProbe: the build request couldn't be read: " + e.Message); }
            }
            if (request == null)
            {
                EditorApplication.Exit(2);
                return;
            }
            var project = Directory.GetParent(Application.dataPath).FullName;
            var outDir = Json.Str(request, "out") ?? Path.Combine(project, "Build", "TaskProbe");
            var resultPath = Json.Str(request, "result") ?? Path.Combine(project, "Logs", "TaskProbe", "build.json");
            var result = new Dictionary<string, object>(StringComparer.Ordinal) { ["ok"] = false };
            var ok = false;
            try
            {
                ok = Run(project, outDir, Json.Strings(request, "scenes"), result);
            }
            catch (Exception e)
            {
                result["error"] = e.GetType().Name + ": " + e.Message;
            }
            result["ok"] = ok;
            try
            {
                Directory.CreateDirectory(Path.GetDirectoryName(resultPath));
                File.WriteAllText(resultPath, Json.Write(result), new UTF8Encoding(false));
            }
            catch (Exception e) { Debug.LogError("TaskProbe: the build result couldn't be written: " + e.Message); }
            EditorApplication.Exit(ok ? 0 : 1);
        }

        static bool Run(string project, string outDir, List<string> played, Dictionary<string, object> result)
        {
            // the project's own enabled build scenes, then the scenes the plays open that it doesn't list
            var scenes = EditorBuildSettings.scenes.Where(s => s.enabled && File.Exists(s.path)).Select(s => s.path).ToList();
            foreach (var scene in played)
                if (!scenes.Contains(scene, StringComparer.OrdinalIgnoreCase))
                {
                    if (File.Exists(Path.Combine(project, scene))) scenes.Add(scene);
                    else Debug.LogWarning("TaskProbe: the play scene " + scene + " isn't in the project");
                }
            result["scenes"] = scenes.Cast<object>().ToList();
            result["missing"] = Missing(project, played);
            if (scenes.Count == 0)
            {
                result["error"] = "no scene to build: the project lists no enabled build scene and the task plays none";
                return false;
            }

            var target = NamedBuildTarget.Standalone;
            PlayerSettings.companyName = "TaskProbe." + Tag(project);
            PlayerSettings.SplashScreen.show = false;
            PlayerSettings.fullScreenMode = FullScreenMode.Windowed;
            PlayerSettings.defaultScreenWidth = Probe.Width;
            PlayerSettings.defaultScreenHeight = Probe.Height;
            PlayerSettings.resizableWindow = false;
            PlayerSettings.runInBackground = true;
            PlayerSettings.visibleInBackground = true;
            PlayerSettings.forceSingleInstance = false;
            PlayerSettings.usePlayerLog = true;
            PlayerSettings.SetScriptingBackend(target, ScriptingImplementation.Mono2x);
            NoStaticBatching();

            if (Directory.Exists(outDir)) Directory.Delete(outDir, true);
            var exe = Path.Combine(outDir, "Game.exe");
            var report = BuildPipeline.BuildPlayer(new BuildPlayerOptions
            {
                scenes = scenes.ToArray(),
                locationPathName = exe,
                target = BuildTarget.StandaloneWindows64,
                targetGroup = BuildTargetGroup.Standalone,
                options = BuildOptions.None,
            });
            var summary = report.summary;
            result["exe"] = exe.Replace('\\', '/');
            result["errors"] = (double)summary.totalErrors;
            result["warnings"] = (double)summary.totalWarnings;
            result["seconds"] = Math.Round(summary.totalTime.TotalSeconds);
            if (summary.result == BuildResult.Succeeded) return true;
            var first = report.steps.SelectMany(s => s.messages).FirstOrDefault(m => m.type == LogType.Error || m.type == LogType.Exception);
            result["error"] = "the player build " + summary.result.ToString().ToLowerInvariant()
                              + (string.IsNullOrEmpty(first.content) ? "" : ": " + first.content);
            return false;
        }

        /// <summary>A short name for this copy, from its folder: the plays of two copies never share saved data.</summary>
        static string Tag(string project)
        {
            using (var sha = SHA256.Create())
                return BitConverter.ToString(sha.ComputeHash(Encoding.UTF8.GetBytes(project.ToLowerInvariant())), 0, 6).Replace("-", "").ToLowerInvariant();
        }

        /// <summary>Static batching off for the build: a batched renderer's mesh becomes one combined mesh, which hides
        /// each object's own mesh name and triangles from the probe. PlayerSettings has no public setter for it.</summary>
        static void NoStaticBatching()
        {
            try
            {
                var set = typeof(PlayerSettings).GetMethod("SetBatchingForPlatform", BindingFlags.Static | BindingFlags.NonPublic | BindingFlags.Public);
                var get = typeof(PlayerSettings).GetMethod("GetBatchingForPlatform", BindingFlags.Static | BindingFlags.NonPublic | BindingFlags.Public);
                if (set == null || get == null) { Debug.LogWarning("TaskProbe: static batching couldn't be turned off (no setter)"); return; }
                var values = new object[] { BuildTarget.StandaloneWindows64, 0, 0 };
                get.Invoke(null, values);
                set.Invoke(null, new object[] { BuildTarget.StandaloneWindows64, 0, values[2] });
            }
            catch (Exception e) { Debug.LogWarning("TaskProbe: static batching couldn't be turned off: " + e.Message); }
        }

        /// <summary>{scene: {"missing": [guid, ...], "names": n}} for the played scenes that name assets the project
        /// doesn't have (a pack committed only later): they load as missing. Built-in resources aren't assets.</summary>
        static Dictionary<string, object> Missing(string project, List<string> played)
        {
            var found = new Dictionary<string, object>(StringComparer.Ordinal);
            foreach (var scene in played)
            {
                var path = Path.Combine(project, scene);
                if (!File.Exists(path)) continue;
                var named = new HashSet<string>(StringComparer.Ordinal);
                foreach (Match m in Guid.Matches(File.ReadAllText(path)))
                    if (!m.Groups[1].Value.StartsWith("0000000000000000", StringComparison.Ordinal)) named.Add(m.Groups[1].Value);
                var missing = new List<object>();
                foreach (var guid in named)
                {
                    var asset = AssetDatabase.GUIDToAssetPath(guid);
                    if (string.IsNullOrEmpty(asset) || !(File.Exists(asset) || Directory.Exists(asset))) missing.Add(guid);
                }
                if (missing.Count == 0) continue;
                missing.Sort((a, b) => string.CompareOrdinal((string)a, (string)b));
                found[scene] = new Dictionary<string, object>(StringComparer.Ordinal) { ["missing"] = missing, ["names"] = (double)named.Count };
            }
            return found;
        }
    }
}
