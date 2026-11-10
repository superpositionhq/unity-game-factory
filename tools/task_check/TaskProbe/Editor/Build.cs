// The checker's build of its scratch copy (contract section 5):
//   Unity -batchmode -nographics -quit -projectPath <copy> -executeMethod TaskProbe.EditorTools.Build.Player
//         -taskProbeBuild <request file>
// A Windows x64 Mono player, not a development build (no watermark on the frame), of the project's own enabled build
// scenes plus every scene the task's plays open, into a folder under the project's Build/. For the build only, the
// player gets its own company name (so the plays' saves and settings are their own and never touch the real game's),
// no splash screen, several instances allowed, no static batching (so a renderer keeps its own mesh for the `mesh`
// selects and triangle counts; it draws the same) and no code stripping (the probe reads by reflection members of the
// engine that the game never calls, which the linker removes: measured at High). The play's command line makes the
// window and names the log.
// BuildPlayer saves the changed settings into ProjectSettings/ProjectSettings.asset before it builds; when the build
// ends they are put back and that file gets back its own bytes, read before the first change (a build that kept its
// settings, run in a game's own folder, had its company name committed into the game). An editor killed in mid-build
// leaves the build's settings in that file: the checker deletes its copy, and another project gets the file back from
// its version control. Unity itself rewrites other assets in any player build, this one included: URP saves its
// pipeline assets' prefiltering fields and adds entries to its global settings (measured), as a build of the game's own
// would.
// Scripts that don't compile stop Unity before this method runs: no result file, exit code 1.
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
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
        const BuildTarget Windows = BuildTarget.StandaloneWindows64;
        static readonly NamedBuildTarget Target = NamedBuildTarget.Standalone;
        // a reference in a scene's text: {fileID: n, guid: g, type: t} (a string field holding a GUID is no reference)
        static readonly Regex Reference = new Regex(@"\{fileID: -?\d+, guid: ([0-9a-f]{32}), type: \d+\}", RegexOptions.CultureInvariant);

        public static void Player()
        {
            var request = AssetPass.Request("-taskProbeBuild");
            if (request == null)
            {
                EditorApplication.Exit(2);
                return;
            }
            var project = Directory.GetParent(Application.dataPath).FullName;
            var result = new Dictionary<string, object>(StringComparer.Ordinal)
            {
                ["ok"] = false, ["exe"] = null, ["scenes"] = new List<object>(), ["errors"] = null, ["seconds"] = null,
                ["error"] = null, ["missing"] = new Dictionary<string, object>(StringComparer.Ordinal),
            };
            try
            {
                result["ok"] = Run(project, Json.Str(request, "out") ?? Path.Combine(project, "Build", "TaskProbe"),
                    Json.Strings(request, "scenes"), result);
            }
            catch (Exception e)
            {
                result["error"] = e.GetType().Name + ": " + e.Message;
            }
            if (result["error"] != null) Debug.LogError("TaskProbe: the build failed: " + result["error"]);
            try
            {
                var file = Path.GetFullPath(Json.Str(request, "result") ?? Path.Combine(project, "Logs", "TaskProbe", "build.json"));
                Directory.CreateDirectory(Path.GetDirectoryName(file));
                File.WriteAllText(file, Json.Write(result), new UTF8Encoding(false));
            }
            catch (Exception e) { Debug.LogError("TaskProbe: the build result couldn't be written: " + e.Message); }
            EditorApplication.Exit(true.Equals(result["ok"]) ? 0 : 1);
        }

        static bool Run(string project, string outDir, List<string> asked, Dictionary<string, object> result)
        {
            // the player goes into the project's own Build folder and nowhere else
            var folder = Path.GetFullPath(Path.Combine(project, outDir));
            if (!folder.StartsWith(Path.Combine(project, "Build") + Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase))
                return Failed(result, "the build folder " + outDir + " isn't in the project's Build folder");

            // the project's own enabled build scenes, then the scenes the plays open that it doesn't list
            var scenes = EditorBuildSettings.scenes.Where(s => s.enabled && File.Exists(s.path)).Select(s => s.path).ToList();
            var played = new List<string>();
            foreach (var scene in asked)
            {
                if (!AssetPass.InProject(scene) || !File.Exists(Path.Combine(project, scene)))
                {
                    Debug.LogWarning("TaskProbe: the play scene " + scene + " isn't in the project");
                    continue;
                }
                played.Add(scene);
                if (!scenes.Contains(scene, StringComparer.OrdinalIgnoreCase)) scenes.Add(scene);
            }
            result["scenes"] = scenes.Cast<object>().ToList();
            result["missing"] = Missing(project, played);
            if (scenes.Count == 0) return Failed(result, "no scene to build: the project lists no enabled build scene and the task plays none");

            var kept = new Kept(project);
            try
            {
                PlayerSettings.companyName = "TaskProbe." + Tag(project);
                PlayerSettings.SplashScreen.show = false;
                PlayerSettings.forceSingleInstance = false;
                PlayerSettings.SetScriptingBackend(Target, ScriptingImplementation.Mono2x);
                PlayerSettings.SetStaticBatchingForPlatform(Windows, false);
                PlayerSettings.SetManagedStrippingLevel(Target, ManagedStrippingLevel.Disabled);
                var exe = Path.Combine(folder, "Game.exe");
                var report = BuildPipeline.BuildPlayer(new BuildPlayerOptions
                {
                    scenes = scenes.ToArray(),
                    locationPathName = exe,
                    target = Windows,
                    targetGroup = BuildTargetGroup.Standalone,
                    options = BuildOptions.None,
                });
                var summary = report.summary;
                result["exe"] = exe.Replace('\\', '/');
                result["errors"] = (double)summary.totalErrors;
                result["seconds"] = Math.Round(summary.totalTime.TotalSeconds);
                if (summary.result == BuildResult.Succeeded) return true;
                var first = report.steps.SelectMany(s => s.messages).FirstOrDefault(m => m.type == LogType.Error || m.type == LogType.Exception);
                return Failed(result, "the player build " + (summary.result == BuildResult.Cancelled ? "was cancelled" : "failed")
                                      + (string.IsNullOrEmpty(first.content) ? "" : ": " + first.content));
            }
            finally
            {
                kept.Restore();
            }
        }

        static bool Failed(Dictionary<string, object> result, string why)
        {
            result["error"] = why;
            return false;
        }

        /// <summary>The player settings the build changes, as the project has them and as its file holds them, and
        /// putting them back.</summary>
        sealed class Kept
        {
            readonly string settings;
            readonly byte[] saved;
            readonly string company = PlayerSettings.companyName;
            readonly bool splash = PlayerSettings.SplashScreen.show;
            readonly bool single = PlayerSettings.forceSingleInstance;
            readonly ScriptingImplementation backend = PlayerSettings.GetScriptingBackend(Target);
            readonly bool batching = PlayerSettings.GetStaticBatchingForPlatform(Windows);
            readonly ManagedStrippingLevel stripping = PlayerSettings.GetManagedStrippingLevel(Target);

            public Kept(string project)
            {
                // from the project's folder, not the working one: a game's own editor script may change that
                settings = Path.Combine(project, "ProjectSettings", "ProjectSettings.asset");
                saved = File.Exists(settings) ? File.ReadAllBytes(settings) : null;  // none yet: nothing to put back
            }

            public void Restore()
            {
                PlayerSettings.companyName = company;
                PlayerSettings.SplashScreen.show = splash;
                PlayerSettings.forceSingleInstance = single;
                PlayerSettings.SetScriptingBackend(Target, backend);
                PlayerSettings.SetStaticBatchingForPlatform(Windows, batching);
                PlayerSettings.SetManagedStrippingLevel(Target, stripping);
                // BuildPlayer has written the changed settings: the file gets its own bytes back, and Unity writes
                // nothing more when it exits (it would write the values put back with an entry for each default a new
                // project leaves out: measured)
                EditorUtility.ClearDirty(Unsupported.GetSerializedAssetInterfaceSingleton("PlayerSettings"));
                // a file that can't be written back must not turn a built player into a failed build
                try { if (saved != null && !File.ReadAllBytes(settings).SequenceEqual(saved)) File.WriteAllBytes(settings, saved); }
                catch (Exception e) { Debug.LogWarning("TaskProbe: " + settings + " keeps the build's settings: " + e.Message); }
            }
        }

        /// <summary>A short name for this copy, from its folder: the plays of two copies never share saved data. The
        /// checker deletes that data by the same name (tools/task_check/seeds.py `saves_company`): the sha256 of the
        /// folder with its ASCII letters lower-cased, and only those (Mono and Python lower-case other letters
        /// differently: a Turkish dotted capital I, a final capital sigma).</summary>
        static string Tag(string project)
        {
            var folder = new StringBuilder(project.Length);
            foreach (var c in project) folder.Append(c >= 'A' && c <= 'Z' ? (char)(c + 32) : c);
            using (var sha = SHA256.Create())
                return BitConverter.ToString(sha.ComputeHash(Encoding.UTF8.GetBytes(folder.ToString())), 0, 6).Replace("-", "").ToLowerInvariant();
        }

        /// <summary>{scene: {"missing": [guid, ...], "names": n}} for the played scenes that name assets the project
        /// doesn't have (a pack committed only later): they load as missing. Built-in resources (a GUID of 16 zeros
        /// first) aren't assets. Only what the scene itself names, as the original reads a map's own imports.</summary>
        static Dictionary<string, object> Missing(string project, List<string> played)
        {
            var found = new Dictionary<string, object>(StringComparer.Ordinal);
            foreach (var scene in played)
            {
                var named = new HashSet<string>(StringComparer.Ordinal);
                foreach (Match m in Reference.Matches(File.ReadAllText(Path.Combine(project, scene))))
                    if (!m.Groups[1].Value.StartsWith("0000000000000000", StringComparison.Ordinal)) named.Add(m.Groups[1].Value);
                var missing = new List<object>();
                foreach (var guid in named.OrderBy(g => g, StringComparer.Ordinal))
                {
                    var asset = AssetDatabase.GUIDToAssetPath(guid);
                    if (string.IsNullOrEmpty(asset) || !(File.Exists(asset) || Directory.Exists(asset))) missing.Add(guid);
                }
                if (missing.Count > 0)
                    found[scene] = new Dictionary<string, object>(StringComparer.Ordinal) { ["missing"] = missing, ["names"] = (double)named.Count };
            }
            return found;
        }
    }
}
