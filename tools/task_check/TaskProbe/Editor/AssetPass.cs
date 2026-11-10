// The checker's editor pass (contract section 5): every `asset` measure of one side, on the project as saved.
//   Unity -batchmode -nographics -quit -projectPath <copy> -executeMethod TaskProbe.EditorTools.AssetPass.Run
//         -taskProbeAssets <request file>
// The request: {"nonce", "measures": {"a<id>": <asset measure>}, "result": "<file>"}. The result, written to that file
// (UTF-8) and as one log line after TASK_PROBES (what the checker reads when the file can't be written):
// {"nonce", "measures": {"a<id>": {"value": v} | {"rows": [{"name", "value"}]} | {"error": "..."}}}.
// Nothing is saved: scenes are opened and prefabs loaded only to be read, so a later play of the copy sees the commit
// as committed. One measure failing never stops the others. Exit code 0 when the pass ran, 2 when the request was
// unreadable; scripts that don't compile stop Unity before this method runs (no result file, exit code 1).
using System;
using System.Collections.Generic;
using System.IO;
using System.Text;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

namespace TaskProbe.EditorTools
{
    public static class AssetPass
    {
        const string Marker = "TASK_PROBES";

        public static void Run()
        {
            var request = Request("-taskProbeAssets");
            var measures = Json.Obj(request, "measures");
            if (request != null && measures == null) Debug.LogError("TaskProbe: the request has no `measures` object");
            if (measures == null)
            {
                EditorApplication.Exit(2);
                return;
            }
            var project = Directory.GetParent(Application.dataPath).FullName;
            var line = Json.Write(new SortedDictionary<string, object>(StringComparer.Ordinal)
            {
                ["nonce"] = request.TryGetValue("nonce", out var nonce) ? nonce : null,
                ["measures"] = Evaluate(measures),
            });
            try
            {
                var file = Path.GetFullPath(Json.Str(request, "result") ?? Path.Combine(project, "Logs", "TaskProbe", "probes_editor.json"));
                Directory.CreateDirectory(Path.GetDirectoryName(file));
                File.WriteAllText(file, line, new UTF8Encoding(false));
            }
            catch (Exception e) { Debug.LogWarning("TaskProbe: the asset result couldn't be written: " + e.Message); }
            Debug.LogFormat(LogType.Log, LogOption.NoStacktrace, null, "{0}", Marker + " " + line);
            EditorApplication.Exit(0);
        }

        /// <summary>The request file after `flag` on the command line, as a JSON object; null, with a line in the log
        /// saying why, when there is none or it can't be read (the build and the pass then exit with 2).</summary>
        internal static Dictionary<string, object> Request(string flag)
        {
            var args = Environment.GetCommandLineArgs();
            var at = Array.FindIndex(args, a => string.Equals(a, flag, StringComparison.OrdinalIgnoreCase));
            string why;
            if (at < 0 || at + 1 >= args.Length) why = "no file after " + flag;
            else
            {
                try
                {
                    var found = Json.Obj(Json.Parse(File.ReadAllText(args[at + 1], Encoding.UTF8)));
                    if (found != null) return found;
                    why = args[at + 1] + " holds no JSON object";
                }
                catch (Exception e) { why = args[at + 1] + ": " + e.Message; }
            }
            Debug.LogError("TaskProbe: the request couldn't be read (" + why + ")");
            return null;
        }

        /// <summary>Whether `path` is a path in the project as a task writes one: Assets/... or Packages/..., with
        /// forward slashes and no empty, "." or ".." part. Nothing else is opened or read.</summary>
        internal static bool InProject(string path)
        {
            if (string.IsNullOrEmpty(path) || path.IndexOf('\\') >= 0 || path.IndexOf(':') >= 0) return false;
            var parts = path.Split('/');
            if (parts.Length < 2 || parts[0] != "Assets" && parts[0] != "Packages") return false;
            foreach (var part in parts)
                if (part.Length == 0 || part == "." || part == "..") return false;
            return true;
        }

        /// <summary>{id: result} of every measure. Asset measures first, then each scene and prefab opened once for all
        /// the measures on it.</summary>
        static SortedDictionary<string, object> Evaluate(Dictionary<string, object> measures)
        {
            var results = new SortedDictionary<string, object>(StringComparer.Ordinal);
            var ids = new List<string>(measures.Keys);
            ids.Sort(StringComparer.Ordinal);
            var scenes = new SortedDictionary<string, List<string>>(StringComparer.Ordinal);
            var prefabs = new SortedDictionary<string, List<string>>(StringComparer.Ordinal);
            foreach (var id in ids)
            {
                var m = Json.Obj(measures[id]);
                if (m == null) { results[id] = Error("not an asset measure"); continue; }
                if (Json.Str(m, "asset") != null) results[id] = Safe(() => AssetValues.AssetMeasure(m));
                else if (Json.Str(m, "scene") != null) Add(scenes, Json.Str(m, "scene"), id);
                else if (Json.Str(m, "prefab") != null) Add(prefabs, Json.Str(m, "prefab"), id);
                else results[id] = Error("an asset measure needs `asset`, `scene` or `prefab`");
            }

            foreach (var pair in scenes)
            {
                List<GameObject> objects = null;
                string failed = null;
                if (!InProject(pair.Key) || AssetDatabase.LoadAssetAtPath<SceneAsset>(pair.Key) == null) failed = "no scene " + pair.Key;
                else
                {
                    try
                    {
                        // Single: the scene alone, as saved (an untitled or other scene open at the start goes away unsaved)
                        var scene = EditorSceneManager.OpenScene(pair.Key, OpenSceneMode.Single);
                        objects = new List<GameObject>();
                        foreach (var root in scene.GetRootGameObjects()) Walk(root.transform, objects);
                    }
                    catch (Exception e) { failed = "the scene " + pair.Key + " couldn't be opened: " + e.GetType().Name + ": " + e.Message; }
                }
                foreach (var id in pair.Value)
                    results[id] = failed != null ? Error(failed) : Safe(() => SceneRows.Measure(Json.Obj(measures[id]), objects));
            }

            foreach (var pair in prefabs)
            {
                GameObject root = null;
                string failed = null;
                if (!InProject(pair.Key) || AssetDatabase.LoadAssetAtPath<GameObject>(pair.Key) == null) failed = "no prefab " + pair.Key;
                else
                {
                    // its own preview scene, never saved back (UnloadPrefabContents without SaveAsPrefabAsset)
                    try { root = PrefabUtility.LoadPrefabContents(pair.Key); }
                    catch (Exception e) { failed = "the prefab " + pair.Key + " couldn't be loaded: " + e.GetType().Name + ": " + e.Message; }
                }
                try
                {
                    var objects = new List<GameObject>();
                    if (root != null) Walk(root.transform, objects);
                    foreach (var id in pair.Value)
                        results[id] = failed != null ? Error(failed) : Safe(() => SceneRows.Measure(Json.Obj(measures[id]), objects));
                }
                finally
                {
                    if (root != null) PrefabUtility.UnloadPrefabContents(root);
                }
            }
            return results;
        }

        static void Add(SortedDictionary<string, List<string>> groups, string key, string id)
        {
            if (!groups.TryGetValue(key, out var list)) groups[key] = list = new List<string>();
            list.Add(id);
        }

        /// <summary>Every object under `t`, itself first: hierarchy order (siblings by index, depth first).</summary>
        static void Walk(Transform t, List<GameObject> into)
        {
            into.Add(t.gameObject);
            for (var i = 0; i < t.childCount; i++) Walk(t.GetChild(i), into);
        }

        static Dictionary<string, object> Safe(Func<Dictionary<string, object>> measure)
        {
            try { return measure(); }
            catch (Exception e)
            {
                var text = e.GetType().Name + ": " + e.Message;
                return Error(text.Length > 300 ? text.Substring(0, 300) : text);
            }
        }

        internal static Dictionary<string, object> Error(string why) =>
            new Dictionary<string, object>(StringComparer.Ordinal) { ["error"] = why };

        internal static Dictionary<string, object> Value(object v) =>
            new Dictionary<string, object>(StringComparer.Ordinal) { ["value"] = v };
    }
}
