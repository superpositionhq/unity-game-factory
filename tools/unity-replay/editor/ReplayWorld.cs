// Scene-building ops (derive.py) played through the editor, headless, to check that they rebuild the scenes:
//   Unity.exe -batchmode -nographics -quit -projectPath <project> -logFile <log>
//             -executeMethod CreationReplay.ReplayWorld.Run -replayRequest <request.json>
// The request: {"ops": ops.jsonl, "prefix": "Assets/CreationReplayWorld", "out": dir, "log": steps.jsonl}.
//   scene.create   {"scene", "as"}             a new empty scene, saved under the prefix
//   object.spawn   {"path", "object"}          a GameObject (or a prefab instance) with its components and values
//   object.update  {"path", "object"}          the object made again from its new values
//   object.remove  {"path"}                    destroyed
//   scene.save     {"settings"}                the values and render settings applied, the scene saved and dumped
//   ui.caption                                 nothing in a scene
// Values are set through SerializedObject once every object of the scene exists, so references between objects
// resolve (by hierarchy path, as the dump writes them). Each op's result goes to the log, one JSON line per op.
using System;
using System.Collections;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Text;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.SceneManagement;
using Object = UnityEngine.Object;

namespace CreationReplay
{
    [Serializable]
    public class WorldRequest
    {
        public string ops;
        public string prefix = "Assets/CreationReplayWorld";
        public string @out;
        public string log;
    }

    public static class ReplayWorld
    {
        static readonly Dictionary<string, string> Rebuilt = new Dictionary<string, string>();   // scene -> rebuilt path
        static readonly List<KeyValuePair<Object, Dictionary<string, object>>> Pending = new List<KeyValuePair<Object, Dictionary<string, object>>>();
        static List<Object> builtins;
        static string current;

        public static void Run()
        {
            var args = Environment.GetCommandLineArgs();
            var i = Array.IndexOf(args, "-replayRequest");
            var req = JsonUtility.FromJson<WorldRequest>(File.ReadAllText(args[i + 1]));
            using var log = new StreamWriter(req.log, false, new UTF8Encoding(false));
            int n = 0, failed = 0;
            foreach (var line in File.ReadAllLines(req.ops))
            {
                if (string.IsNullOrWhiteSpace(line)) continue;
                var op = (Dictionary<string, object>)Json.Parse(line);
                var t0 = DateTime.Now;
                var res = new SortedDictionary<string, object>(StringComparer.Ordinal);
                try { Do(op, req, res); }
                catch (Exception e) { res["error"] = e.GetType().Name + ": " + e.Message.Split('\n')[0]; }
                if (res.ContainsKey("error")) failed++;
                var rec = new SortedDictionary<string, object>(StringComparer.Ordinal)
                {
                    ["id"] = op["id"], ["op"] = op["op"], ["seconds"] = Math.Round((DateTime.Now - t0).TotalSeconds, 3), ["result"] = res
                };
                var sb = new StringBuilder();
                ReplayDump.WriteValue(sb, rec);
                log.WriteLine(sb.ToString());
                n++;
            }
            Debug.Log($"[replay] world: {n} ops, {failed} failed");
        }

        static void Do(Dictionary<string, object> op, WorldRequest req, IDictionary<string, object> res)
        {
            var kind = (string)op["op"];
            var p = op.TryGetValue("params", out var pv) ? pv as Dictionary<string, object> : null;
            var target = op.TryGetValue("target", out var tv) ? tv as string : null;
            switch (kind)
            {
                case "scene.create":
                {
                    var asPath = (string)p["as"];
                    var path = req.prefix.TrimEnd('/') + "/" + asPath.Substring("Assets/".Length);
                    EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
                    Rebuilt[target] = path;
                    current = target;
                    Pending.Clear();
                    res["scene"] = path;
                    break;
                }
                case "object.spawn":
                case "object.update":
                {
                    Open(target);
                    var obj = (Dictionary<string, object>)p["object"];
                    var path = (string)p["path"];
                    if (kind == "object.update")
                    {
                        var old = Find(path);
                        if (old != null && !PrefabUtility.IsPartOfPrefabInstance(old)) Object.DestroyImmediate(old);
                    }
                    res["made"] = Spawn(path, obj, res);
                    break;
                }
                case "object.remove":
                {
                    Open(target);
                    var old = Find((string)p["path"]);
                    res["removed"] = old != null;
                    if (old != null) Object.DestroyImmediate(old);
                    break;
                }
                case "scene.save":
                {
                    Open(target);
                    res["values"] = ApplyPending();
                    if (p != null && p.TryGetValue("settings", out var s) && s is Dictionary<string, object> sd) ApplySettings(sd);
                    var path = Rebuilt[target];
                    Directory.CreateDirectory(Path.GetDirectoryName(path));
                    var scene = SceneManager.GetActiveScene();
                    res["saved"] = EditorSceneManager.SaveScene(scene, path);
                    res["dump"] = ReplayDump.DumpScene(path, req.@out);
                    current = null;   // the dump opened the scene again; the next op opens it as needed
                    break;
                }
            }
        }

        /// <summary>The rebuilt scene of `scene` open (a later run's ops change the scene an earlier one made).</summary>
        static void Open(string scene)
        {
            if (current == scene) return;
            if (!Rebuilt.TryGetValue(scene, out var path)) throw new InvalidOperationException("no scene.create for " + scene);
            EditorSceneManager.OpenScene(path, OpenSceneMode.Single);
            current = scene;
            Pending.Clear();
        }

        static string Spawn(string path, Dictionary<string, object> obj, IDictionary<string, object> res)
        {
            var parentPath = path.Contains("/") ? path.Substring(0, path.LastIndexOf('/')) : null;
            var parent = parentPath != null ? Find(parentPath) : null;
            if (parentPath != null && parent == null) throw new InvalidOperationException("no parent " + parentPath);
            var go = Find(path);
            string made;
            if (go != null && PrefabUtility.IsPartOfPrefabInstance(go)) made = "prefab_part";   // came with its instance
            else if (obj.TryGetValue("prefab", out var pf) && pf is string prefab && AssetDatabase.LoadAssetAtPath<GameObject>(prefab) is GameObject asset)
            {
                go = (GameObject)PrefabUtility.InstantiatePrefab(asset, SceneManager.GetActiveScene());
                made = "prefab";
            }
            else
            {
                go = new GameObject((string)obj["name"]);
                made = "new";
            }
            go.name = (string)obj["name"];
            if (parent != null && go.transform.parent != parent.transform) go.transform.SetParent(parent.transform, false);
            go.layer = Convert.ToInt32(obj["layer"]);
            try { go.tag = (string)obj["tag"]; } catch { res["tag"] = "unknown tag"; }
            GameObjectUtility.SetStaticEditorFlags(go, (StaticEditorFlags)Convert.ToInt32(obj["static"]));
            var missing = new List<object>();
            foreach (var c in (List<object>)obj["components"])
            {
                var cd = (Dictionary<string, object>)c;
                var tn = (string)cd["type"];
                var type = FindType(tn);
                if (type == null) { missing.Add(tn); continue; }
                var idx = cd.TryGetValue("index", out var ix) ? Convert.ToInt32(ix) : 0;
                var have = go.GetComponents(type);
                var comp = idx < have.Length ? have[idx] : go.AddComponent(type);
                if (comp == null) { missing.Add(tn); continue; }
                if (cd.TryGetValue("props", out var props) && props is Dictionary<string, object> pd) Pending.Add(new KeyValuePair<Object, Dictionary<string, object>>(comp, pd));
            }
            go.SetActive((bool)obj["active"]);
            if (missing.Count > 0) res["missing_types"] = missing;
            return made;
        }

        static Type FindType(string name)
        {
            foreach (var a in AppDomain.CurrentDomain.GetAssemblies())
            {
                var t = a.GetType(name);
                if (t != null) return t;
            }
            return null;
        }

        /// <summary>A GameObject of the open scene by the dump's hierarchy path (name or name[k] per level).</summary>
        public static GameObject Find(string path)
        {
            IEnumerable<Transform> level = SceneManager.GetActiveScene().GetRootGameObjects().Select(g => g.transform);
            Transform hit = null;
            foreach (var part in path.Split('/'))
            {
                var name = part;
                var k = 0;
                var b = part.LastIndexOf('[');
                if (b > 0 && part.EndsWith("]") && int.TryParse(part.Substring(b + 1, part.Length - b - 2), out var kk)) { name = part.Substring(0, b); k = kk; }
                var same = level.Where(t => t.name == name).ToList();
                if (k >= same.Count) return null;
                hit = same[k];
                level = Enumerable.Range(0, hit.childCount).Select(i => hit.GetChild(i));
            }
            return hit != null ? hit.gameObject : null;
        }

        static object ApplyPending()
        {
            int set = 0, notFound = 0, failed = 0;
            foreach (var kv in Pending)
            {
                if (kv.Key == null) continue;
                var so = new SerializedObject(kv.Key);
                foreach (var e in kv.Value.Where(e => e.Key.EndsWith(".Array.size")).OrderBy(e => e.Key.Length))
                {
                    var p = so.FindProperty(e.Key);
                    if (p != null) { p.intValue = Convert.ToInt32(e.Value); set++; }
                }
                so.ApplyModifiedPropertiesWithoutUndo();
                so.Update();
                foreach (var e in kv.Value)
                {
                    if (e.Key.EndsWith(".size") || e.Key.EndsWith(".sha256") || e.Key.StartsWith("<")) continue;
                    var p = so.FindProperty(e.Key);
                    if (p == null) { notFound++; continue; }
                    try { if (Set(p, e.Value)) set++; }
                    catch { failed++; }
                }
                so.ApplyModifiedPropertiesWithoutUndo();
            }
            Pending.Clear();
            return new List<object> { set, notFound, failed };
        }

        static float F(object o) => Convert.ToSingle(o, CultureInfo.InvariantCulture);
        static List<object> L(object o) => (List<object>)o;

        static bool Set(SerializedProperty p, object v)
        {
            switch (p.propertyType)
            {
                case SerializedPropertyType.Integer: p.longValue = Convert.ToInt64(v); return true;
                case SerializedPropertyType.Boolean: p.boolValue = (bool)v; return true;
                case SerializedPropertyType.Float: p.doubleValue = Convert.ToDouble(v, CultureInfo.InvariantCulture); return true;
                case SerializedPropertyType.String: p.stringValue = (string)v; return true;
                case SerializedPropertyType.Color: var c = L(v); p.colorValue = new Color(F(c[0]), F(c[1]), F(c[2]), F(c[3])); return true;
                case SerializedPropertyType.ObjectReference: p.objectReferenceValue = Resolve(v as string); return true;
                case SerializedPropertyType.LayerMask:
                case SerializedPropertyType.Character:
                case SerializedPropertyType.ArraySize: p.intValue = Convert.ToInt32(v); return true;
                case SerializedPropertyType.Enum:
                    if (v is string s) { var i = Array.IndexOf(p.enumNames, s); if (i >= 0) p.enumValueIndex = i; return i >= 0; }
                    p.intValue = Convert.ToInt32(v);
                    return true;
                case SerializedPropertyType.Vector2: var v2 = L(v); p.vector2Value = new Vector2(F(v2[0]), F(v2[1])); return true;
                case SerializedPropertyType.Vector3: var v3 = L(v); p.vector3Value = new Vector3(F(v3[0]), F(v3[1]), F(v3[2])); return true;
                case SerializedPropertyType.Vector4: var v4 = L(v); p.vector4Value = new Vector4(F(v4[0]), F(v4[1]), F(v4[2]), F(v4[3])); return true;
                case SerializedPropertyType.Quaternion: var q = L(v); p.quaternionValue = new Quaternion(F(q[0]), F(q[1]), F(q[2]), F(q[3])); return true;
                case SerializedPropertyType.Rect: var r = L(v); p.rectValue = new Rect(F(r[0]), F(r[1]), F(r[2]), F(r[3])); return true;
                case SerializedPropertyType.Bounds:
                    var b = L(v); var bc = L(b[0]); var be = L(b[1]);
                    p.boundsValue = new Bounds(new Vector3(F(bc[0]), F(bc[1]), F(bc[2])), new Vector3(F(be[0]), F(be[1]), F(be[2])) * 2f);
                    return true;
                case SerializedPropertyType.Vector2Int: var a2 = L(v); p.vector2IntValue = new Vector2Int(Convert.ToInt32(a2[0]), Convert.ToInt32(a2[1])); return true;
                case SerializedPropertyType.Vector3Int:
                    var a3 = L(v); p.vector3IntValue = new Vector3Int(Convert.ToInt32(a3[0]), Convert.ToInt32(a3[1]), Convert.ToInt32(a3[2])); return true;
                case SerializedPropertyType.AnimationCurve:
                    if (v == null) return false;
                    p.animationCurveValue = new AnimationCurve(L(v).Select(k => { var kk = L(k); return new Keyframe(F(kk[0]), F(kk[1]), F(kk[2]), F(kk[3])); }).ToArray());
                    return true;
                default:
                    if (p.propertyType.ToString() == "RenderingLayerMask") { p.uintValue = Convert.ToUInt32(v); return true; }
                    return false;
            }
        }

        /// <summary>A reference as the dump writes it, back to the object.</summary>
        public static Object Resolve(string r)
        {
            if (string.IsNullOrEmpty(r)) return null;
            if (r.StartsWith("asset:"))
            {
                var rest = r.Substring(6);
                var hash = rest.IndexOf('#');
                if (hash < 0) return AssetDatabase.LoadMainAssetAtPath(rest);
                var path = rest.Substring(0, hash);
                var sub = rest.Substring(hash + 1);
                var colon = sub.IndexOf(':');
                if (colon > 0 && sub.IndexOf('/') < 0 && sub.IndexOf('|') < 0)
                {
                    var tn = sub.Substring(0, colon); var name = sub.Substring(colon + 1);
                    return AssetDatabase.LoadAllAssetsAtPath(path).FirstOrDefault(o => o != null && o.GetType().Name == tn && o.name == name);
                }
                var root = AssetDatabase.LoadAssetAtPath<GameObject>(path);
                return root != null ? InHierarchy(new[] { root.transform }, sub) : null;
            }
            if (r.StartsWith("builtin:"))
            {
                builtins ??= AssetDatabase.LoadAllAssetsAtPath("Library/unity default resources")
                    .Concat(AssetDatabase.LoadAllAssetsAtPath("Resources/unity_builtin_extra")).Where(o => o != null).ToList();
                var parts = r.Substring(8).Split(new[] { ':' }, 2);
                return builtins.FirstOrDefault(o => o.GetType().Name == parts[0] && o.name == parts[1]);
            }
            if (r.StartsWith("scene:"))
            {
                var sub = r.Substring(6);
                return InHierarchy(SceneManager.GetActiveScene().GetRootGameObjects().Select(g => g.transform), sub);
            }
            return null;
        }

        /// <summary>"Root/Child[1]" or "Root/Child|Type#k" under the given roots.</summary>
        static Object InHierarchy(IEnumerable<Transform> roots, string sub)
        {
            var bar = sub.IndexOf('|');
            var hier = bar >= 0 ? sub.Substring(0, bar) : sub;
            var comp = bar >= 0 ? sub.Substring(bar + 1) : null;
            IEnumerable<Transform> level = roots;
            Transform hit = null;
            foreach (var part in hier.Split('/'))
            {
                var name = part; var k = 0;
                var b = part.LastIndexOf('[');
                if (b > 0 && part.EndsWith("]") && int.TryParse(part.Substring(b + 1, part.Length - b - 2), out var kk)) { name = part.Substring(0, b); k = kk; }
                var same = level.Where(t => t.name == name).ToList();
                if (k >= same.Count) return null;
                hit = same[k];
                level = Enumerable.Range(0, hit.childCount).Select(i => hit.GetChild(i));
            }
            if (hit == null) return null;
            if (comp == null) return hit.gameObject;
            var tn = comp; var idx = 0;
            var h = comp.LastIndexOf('#');
            if (h > 0 && int.TryParse(comp.Substring(h + 1), out var ci)) { tn = comp.Substring(0, h); idx = ci; }
            var type = FindType(tn);
            if (type == null) return null;
            var all = hit.GetComponents(type);
            return idx < all.Length ? all[idx] : null;
        }

        static void ApplySettings(Dictionary<string, object> s)
        {
            Color Col(string k) { var c = L(s[k]); return new Color(F(c[0]), F(c[1]), F(c[2]), F(c[3])); }
            if (s.TryGetValue("ambientMode", out var am) && Enum.TryParse(am as string, out AmbientMode m)) RenderSettings.ambientMode = m;
            if (s.ContainsKey("ambientSkyColor")) RenderSettings.ambientSkyColor = Col("ambientSkyColor");
            if (s.ContainsKey("ambientEquatorColor")) RenderSettings.ambientEquatorColor = Col("ambientEquatorColor");
            if (s.ContainsKey("ambientGroundColor")) RenderSettings.ambientGroundColor = Col("ambientGroundColor");
            if (s.ContainsKey("ambientLight")) RenderSettings.ambientLight = Col("ambientLight");
            if (s.ContainsKey("ambientIntensity")) RenderSettings.ambientIntensity = F(s["ambientIntensity"]);
            if (s.ContainsKey("fog")) RenderSettings.fog = (bool)s["fog"];
            if (s.ContainsKey("fogColor")) RenderSettings.fogColor = Col("fogColor");
            if (s.TryGetValue("fogMode", out var fm) && Enum.TryParse(fm as string, out FogMode f)) RenderSettings.fogMode = f;
            if (s.ContainsKey("fogDensity")) RenderSettings.fogDensity = F(s["fogDensity"]);
            if (s.ContainsKey("fogStartDistance")) RenderSettings.fogStartDistance = F(s["fogStartDistance"]);
            if (s.ContainsKey("fogEndDistance")) RenderSettings.fogEndDistance = F(s["fogEndDistance"]);
            if (s.ContainsKey("skybox")) RenderSettings.skybox = Resolve(s["skybox"] as string) as Material;
            if (s.ContainsKey("sun")) RenderSettings.sun = Resolve(s["sun"] as string) as Light;
            if (s.TryGetValue("defaultReflectionMode", out var rm) && Enum.TryParse(rm as string, out DefaultReflectionMode d)) RenderSettings.defaultReflectionMode = d;
            if (s.ContainsKey("reflectionIntensity")) RenderSettings.reflectionIntensity = F(s["reflectionIntensity"]);
            if (s.ContainsKey("reflectionBounces")) RenderSettings.reflectionBounces = Convert.ToInt32(s["reflectionBounces"]);
            if (s.ContainsKey("subtractiveShadowColor")) RenderSettings.subtractiveShadowColor = Col("subtractiveShadowColor");
        }
    }

    /// <summary>A small JSON reader: objects as Dictionary, arrays as List, numbers as long or double.</summary>
    public static class Json
    {
        public static object Parse(string s)
        {
            var i = 0;
            var v = Value(s, ref i);
            return v;
        }

        static void Ws(string s, ref int i) { while (i < s.Length && char.IsWhiteSpace(s[i])) i++; }

        static object Value(string s, ref int i)
        {
            Ws(s, ref i);
            var c = s[i];
            if (c == '{')
            {
                var d = new Dictionary<string, object>();
                i++; Ws(s, ref i);
                if (s[i] == '}') { i++; return d; }
                while (true)
                {
                    Ws(s, ref i);
                    var k = Str(s, ref i);
                    Ws(s, ref i); i++;   // ':'
                    d[k] = Value(s, ref i);
                    Ws(s, ref i);
                    if (s[i] == ',') { i++; continue; }
                    i++; return d;    // '}'
                }
            }
            if (c == '[')
            {
                var l = new List<object>();
                i++; Ws(s, ref i);
                if (s[i] == ']') { i++; return l; }
                while (true)
                {
                    l.Add(Value(s, ref i));
                    Ws(s, ref i);
                    if (s[i] == ',') { i++; continue; }
                    i++; return l;    // ']'
                }
            }
            if (c == '"') return Str(s, ref i);
            if (s.Substring(i).StartsWith("true")) { i += 4; return true; }
            if (s.Substring(i).StartsWith("false")) { i += 5; return false; }
            if (s.Substring(i).StartsWith("null")) { i += 4; return null; }
            var st = i;
            while (i < s.Length && "+-0123456789.eE".IndexOf(s[i]) >= 0) i++;
            var num = s.Substring(st, i - st);
            if (num.IndexOfAny(new[] { '.', 'e', 'E' }) < 0 && long.TryParse(num, NumberStyles.Integer, CultureInfo.InvariantCulture, out var lv)) return lv;
            return double.Parse(num, NumberStyles.Float, CultureInfo.InvariantCulture);
        }

        static string Str(string s, ref int i)
        {
            var sb = new StringBuilder();
            i++;   // '"'
            while (s[i] != '"')
            {
                if (s[i] == '\\')
                {
                    i++;
                    switch (s[i])
                    {
                        case 'n': sb.Append('\n'); break;
                        case 'r': sb.Append('\r'); break;
                        case 't': sb.Append('\t'); break;
                        case 'b': sb.Append('\b'); break;
                        case 'f': sb.Append('\f'); break;
                        case 'u': sb.Append((char)Convert.ToInt32(s.Substring(i + 1, 4), 16)); i += 4; break;
                        default: sb.Append(s[i]); break;
                    }
                    i++;
                }
                else sb.Append(s[i++]);
            }
            i++;
            return sb.ToString();
        }
    }
}
