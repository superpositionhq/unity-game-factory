// Structure dump of a Unity project, run headless by the creation replay:
//   Unity.exe -batchmode -nographics -quit -projectPath <project> -logFile <log>
//             -executeMethod CreationReplay.ReplayDump.Run -replayRequest <request.json>
// The replay puts this folder into the project for one run and removes it afterwards. The request:
//   {"out": dir, "assets": true, "all_scenes": true, "scenes": [paths], "only": [paths], "asset_roots": ["Assets"],
//    "scene_roots": ["Assets"], "exclude": [folders]}
// Writes <out>/assets.json (every asset: path, main type, importer and its settings, the source file's sha256 for
// files the builder writes, every serialized object of the file, a prefab's hierarchy), <out>/scenes/<path>.json
// (every GameObject of a scene by hierarchy path: active, tag, layer, static flags, prefab source, world position,
// every component with all its visible serialized fields; the scene's render and lighting settings; the hierarchy
// order) and <out>/done.json. References are written as paths ("asset:Assets/X.mat", "scene:Root/Child|Light",
// "builtin:Mesh:Cube"), never as GUIDs or file ids, which are random in every editor. Floats are rounded to 1e-4.
using System;
using System.Collections;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.SceneManagement;
using Object = UnityEngine.Object;

namespace CreationReplay
{
    [Serializable]
    public class DumpRequest
    {
        public string @out;
        public bool assets = true;
        public bool all_scenes = true;
        public string[] scenes = new string[0];
        public string[] only = new string[0];
        public string[] asset_roots = { "Assets" };
        public string[] scene_roots = { "Assets" };
        public string[] exclude = new string[0];
    }

    public static class ReplayDump
    {
        const int MaxProps = 20000;     // per object: a bigger one is cut (and says so)
        const int BigArray = 256;       // longer arrays are written as size + sha256 of their values

        // identity and bookkeeping fields, never content (random ids, owner links the hierarchy already says)
        static readonly HashSet<string> Skip = new HashSet<string>
        {
            "m_ObjectHideFlags", "m_CorrespondingSourceObject", "m_PrefabInstance", "m_PrefabAsset", "m_GameObject",
            "m_Father", "m_Children", "m_EditorHideFlags", "m_EditorClassIdentifier", "m_LocalIdentfierInFile",
            "m_RootOrder", "m_LocalEulerAnglesHint", "m_InternalIDToNameTable", "internalIDToNameTable",
            "m_FileIDToRecycleName", "m_UsedFileIDs", "m_ConstrainProportionsScale"
        };

        static readonly HashSet<SerializedPropertyType> Compound = new HashSet<SerializedPropertyType>
        {
            SerializedPropertyType.Color, SerializedPropertyType.Vector2, SerializedPropertyType.Vector3,
            SerializedPropertyType.Vector4, SerializedPropertyType.Quaternion, SerializedPropertyType.Rect,
            SerializedPropertyType.Bounds, SerializedPropertyType.Vector2Int, SerializedPropertyType.Vector3Int,
            SerializedPropertyType.RectInt, SerializedPropertyType.BoundsInt, SerializedPropertyType.AnimationCurve,
            SerializedPropertyType.Gradient
        };

        static readonly string[] YamlExt =
        {
            ".unity", ".prefab", ".mat", ".asset", ".anim", ".controller", ".overridecontroller", ".mask",
            ".physicmaterial", ".physicsmaterial2d", ".mixer", ".playable", ".signal", ".lighting", ".terrainlayer",
            ".spriteatlas", ".spriteatlasv2", ".rendertexture", ".cubemap", ".flare", ".guiskin", ".fontsettings",
            ".brush", ".preset", ".giparams", ".shadervariants", ".shadergraph", ".shadersubgraph", ".vfx",
            ".scenetemplate", ".lightingsettings"
        };

        public static void Run()
        {
            var t0 = DateTime.Now;
            string outDir = null;
            try
            {
                var req = JsonUtility.FromJson<DumpRequest>(File.ReadAllText(Arg("-replayRequest")));
                outDir = req.@out;
                Directory.CreateDirectory(outDir);
                var only = new HashSet<string>(req.only ?? new string[0]);
                var exclude = (req.exclude ?? new string[0]).Select(e => e.TrimEnd('/') + "/").ToArray();
                int nAssets = 0, nScenes = 0;
                if (req.assets) nAssets = DumpAssets(req, only, exclude, outDir);
                var scenes = req.all_scenes
                    ? AssetDatabase.FindAssets("t:Scene", req.scene_roots).Select(AssetDatabase.GUIDToAssetPath)
                        .Where(p => p.EndsWith(".unity") && !Excluded(p, exclude)).Distinct().OrderBy(p => p, StringComparer.Ordinal).ToList()
                    : (req.scenes ?? new string[0]).ToList();
                var summary = new List<object>();
                foreach (var s in scenes)
                {
                    summary.Add(DumpScene(s, outDir));
                    nScenes++;
                }
                Write(Path.Combine(outDir, "scenes.json"), summary);
                Write(Path.Combine(outDir, "done.json"), new SortedDictionary<string, object>(StringComparer.Ordinal)
                {
                    ["seconds"] = Math.Round((DateTime.Now - t0).TotalSeconds, 1), ["unity"] = Application.unityVersion,
                    ["assets"] = nAssets, ["scenes"] = nScenes
                });
                Debug.Log($"[replay] dump: {nAssets} assets, {nScenes} scenes in {(DateTime.Now - t0).TotalSeconds:F1} s");
            }
            catch (Exception e)
            {
                Debug.LogError("[replay] dump failed: " + e);
                if (outDir != null) File.WriteAllText(Path.Combine(outDir, "error.txt"), e.ToString());
                EditorApplication.Exit(1);
            }
        }

        static string Arg(string name)
        {
            var a = Environment.GetCommandLineArgs();
            var i = Array.IndexOf(a, name);
            if (i < 0 || i + 1 >= a.Length) throw new ArgumentException("missing " + name);
            return a[i + 1];
        }

        static bool Excluded(string path, string[] exclude) => exclude.Any(e => path.StartsWith(e, StringComparison.Ordinal));

        static bool IsYaml(string path) => YamlExt.Contains(Path.GetExtension(path).ToLowerInvariant());

        // ---------------------------------------------------------------------------------------------- assets
        static int DumpAssets(DumpRequest req, HashSet<string> only, string[] exclude, string outDir)
        {
            var paths = AssetDatabase.FindAssets("", req.asset_roots).Select(AssetDatabase.GUIDToAssetPath)
                .Where(p => !string.IsNullOrEmpty(p) && !AssetDatabase.IsValidFolder(p) && !Excluded(p, exclude))
                .Where(p => only.Count == 0 || only.Contains(p))
                .Distinct().OrderBy(p => p, StringComparer.Ordinal).ToList();
            var rows = new List<object>();
            var n = 0;
            foreach (var p in paths)
            {
                rows.Add(DumpAsset(p));
                if (++n % 200 == 0) EditorUtility.UnloadUnusedAssetsImmediate();
            }
            Write(Path.Combine(outDir, "assets.json"), new SortedDictionary<string, object>(StringComparer.Ordinal)
            {
                ["roots"] = req.asset_roots.ToList<object>(), ["count"] = rows.Count, ["assets"] = rows
            });
            return rows.Count;
        }

        static object DumpAsset(string path)
        {
            var row = new SortedDictionary<string, object>(StringComparer.Ordinal) { ["path"] = path };
            try
            {
                var type = AssetDatabase.GetMainAssetTypeAtPath(path);
                row["type"] = type != null ? type.FullName : null;
                var imp = AssetImporter.GetAtPath(path);
                if (imp != null)
                {
                    row["importer"] = imp.GetType().FullName;
                    row["importer_settings"] = Props(imp, null);
                }
                if (!IsYaml(path) && File.Exists(path)) row["source_sha256"] = Sha(File.ReadAllBytes(path));
                if (path.EndsWith(".unity", StringComparison.OrdinalIgnoreCase)) return row;   // scenes: scenes/*.json
                var main = AssetDatabase.LoadMainAssetAtPath(path);
                if (main is GameObject go && path.EndsWith(".prefab", StringComparison.OrdinalIgnoreCase))
                {
                    row["hierarchy"] = Hierarchy(new[] { go }, "asset:" + path);
                    return row;
                }
                var objs = new List<object>();
                foreach (var o in AssetDatabase.LoadAllAssetsAtPath(path).Where(o => o != null)
                             .OrderBy(o => o.GetType().FullName, StringComparer.Ordinal).ThenBy(o => o.name, StringComparer.Ordinal))
                {
                    if (o is GameObject || o is Component) continue;   // a model's hierarchy: its importer and meshes say it
                    var d = new SortedDictionary<string, object>(StringComparer.Ordinal)
                    {
                        ["type"] = o.GetType().FullName, ["name"] = o.name, ["main"] = AssetDatabase.IsMainAsset(o)
                    };
                    if (o is Mesh m) d["mesh"] = MeshInfo(m);
                    else if (o is Texture t) d["texture"] = new List<object> { t.width, t.height, t.graphicsFormat.ToString(), t.mipmapCount };
                    else if (o is AudioClip a) d["audio"] = new List<object> { R(a.length), a.channels, a.frequency };
                    else if (o is MonoScript ms) d["script_class"] = ms.GetClass() != null ? ms.GetClass().FullName : null;
                    else d["props"] = Props(o, null);
                    objs.Add(d);
                }
                row["objects"] = objs;
            }
            catch (Exception e)
            {
                row["error"] = e.GetType().Name + ": " + e.Message.Split('\n')[0];
            }
            return row;
        }

        static object MeshInfo(Mesh m)
        {
            var b = m.bounds;
            return new SortedDictionary<string, object>(StringComparer.Ordinal)
            {
                ["vertices"] = m.vertexCount, ["submeshes"] = m.subMeshCount,
                ["indices"] = Enumerable.Range(0, m.subMeshCount).Select(i => (object)(long)m.GetIndexCount(i)).ToList(),
                ["bounds"] = new List<object> { V(b.center), V(b.size) }
            };
        }

        // ---------------------------------------------------------------------------------------------- scenes
        public static object DumpScene(string path, string outDir)
        {
            var info = new SortedDictionary<string, object>(StringComparer.Ordinal) { ["scene"] = path };
            try
            {
                var scene = EditorSceneManager.OpenScene(path, OpenSceneMode.Single);
                var roots = scene.GetRootGameObjects();
                var objects = Hierarchy(roots, "scene:");
                var rec = new SortedDictionary<string, object>(StringComparer.Ordinal)
                {
                    ["scene"] = path, ["objects"] = objects, ["count"] = objects.Count,
                    ["order"] = objects.Select(o => ((IDictionary)o)["path"]).ToList(),
                    ["settings"] = SceneSettings()
                };
                var file = path.Replace("/", "__") + ".json";
                Write(Path.Combine(outDir, "scenes", file), rec);
                info["objects"] = objects.Count;
                info["file"] = file;
            }
            catch (Exception e)
            {
                info["error"] = e.GetType().Name + ": " + e.Message.Split('\n')[0];
            }
            return info;
        }

        static object SceneSettings()
        {
            var d = new SortedDictionary<string, object>(StringComparer.Ordinal)
            {
                ["ambientMode"] = RenderSettings.ambientMode.ToString(), ["ambientLight"] = C(RenderSettings.ambientLight),
                ["ambientSkyColor"] = C(RenderSettings.ambientSkyColor), ["ambientEquatorColor"] = C(RenderSettings.ambientEquatorColor),
                ["ambientGroundColor"] = C(RenderSettings.ambientGroundColor), ["ambientIntensity"] = R(RenderSettings.ambientIntensity),
                ["fog"] = RenderSettings.fog, ["fogColor"] = C(RenderSettings.fogColor), ["fogMode"] = RenderSettings.fogMode.ToString(),
                ["fogDensity"] = R(RenderSettings.fogDensity), ["fogStartDistance"] = R(RenderSettings.fogStartDistance),
                ["fogEndDistance"] = R(RenderSettings.fogEndDistance), ["skybox"] = Ref(RenderSettings.skybox),
                ["sun"] = Ref(RenderSettings.sun), ["defaultReflectionMode"] = RenderSettings.defaultReflectionMode.ToString(),
                ["reflectionIntensity"] = R(RenderSettings.reflectionIntensity), ["reflectionBounces"] = RenderSettings.reflectionBounces,
                ["subtractiveShadowColor"] = C(RenderSettings.subtractiveShadowColor)
            };
            if (Lightmapping.TryGetLightingSettings(out var ls) && ls != null)
            {
                d["lighting_settings"] = Ref(ls);
                d["lighting"] = Props(ls, null);
            }
            return d;
        }

        /// <summary>Every GameObject under the roots, depth first in hierarchy order.</summary>
        static List<object> Hierarchy(IEnumerable<GameObject> roots, string refPrefix)
        {
            var list = new List<object>();
            var rootList = roots.ToList();
            foreach (var r in rootList) Walk(r.transform, list, rootList);
            return list;
        }

        static void Walk(Transform t, List<object> list, List<GameObject> roots)
        {
            var go = t.gameObject;
            var d = new SortedDictionary<string, object>(StringComparer.Ordinal)
            {
                ["path"] = HierPath(t, roots), ["name"] = go.name, ["active"] = go.activeSelf, ["tag"] = SafeTag(go),
                ["layer"] = go.layer, ["static"] = (long)GameObjectUtility.GetStaticEditorFlags(go),
                ["position"] = V(t.position)
            };
            if (PrefabUtility.IsAnyPrefabInstanceRoot(go))
            {
                var src = PrefabUtility.GetCorrespondingObjectFromSource(go);
                d["prefab"] = src != null ? AssetDatabase.GetAssetPath(src) : "missing";
            }
            var comps = new List<object>();
            var seen = new Dictionary<string, int>();
            foreach (var c in go.GetComponents<Component>())
            {
                var cd = new SortedDictionary<string, object>(StringComparer.Ordinal);
                if (c == null) { cd["type"] = "<missing script>"; comps.Add(cd); continue; }
                var tn = c.GetType().FullName;
                seen[tn] = seen.TryGetValue(tn, out var k) ? k + 1 : 0;
                cd["type"] = tn;
                if (seen[tn] > 0) cd["index"] = seen[tn];
                cd["props"] = Props(c, roots);
                comps.Add(cd);
            }
            d["components"] = comps;
            list.Add(d);
            for (var i = 0; i < t.childCount; i++) Walk(t.GetChild(i), list, roots);
        }

        static string SafeTag(GameObject go)
        {
            try { return go.tag; } catch { return "?"; }
        }

        /// <summary>Names from the root down; a name its siblings share gets [k] (k-th of that name).</summary>
        public static string HierPath(Transform t, List<GameObject> roots = null)
        {
            var parts = new List<string>();
            for (var x = t; x != null; x = x.parent)
            {
                IEnumerable<Transform> sibs = x.parent != null
                    ? Enumerable.Range(0, x.parent.childCount).Select(i => x.parent.GetChild(i))
                    : (x.gameObject.scene.IsValid() ? x.gameObject.scene.GetRootGameObjects().Select(g => g.transform)
                        : (roots != null ? roots.Select(g => g.transform) : new[] { x }));
                var same = sibs.Where(s => s.name == x.name).ToList();
                parts.Insert(0, same.Count > 1 ? $"{x.name}[{same.IndexOf(x)}]" : x.name);
            }
            return string.Join("/", parts);
        }

        static string ComponentKey(Component c)
        {
            var tn = c.GetType().FullName;
            var same = c.gameObject.GetComponents(c.GetType()).ToList();
            var i = same.IndexOf(c);
            return i > 0 ? $"{tn}#{i}" : tn;
        }

        // ---------------------------------------------------------------------------------------------- values
        /// <summary>Every visible serialized field of an object: property path -> value.</summary>
        public static SortedDictionary<string, object> Props(Object o, List<GameObject> roots)
        {
            var d = new SortedDictionary<string, object>(StringComparer.Ordinal);
            SerializedObject so;
            try { so = new SerializedObject(o); }
            catch (Exception e) { d["<error>"] = e.Message; return d; }
            var it = so.GetIterator();
            var enter = true;
            var n = 0;
            while (it.NextVisible(enter))
            {
                enter = true;
                if (Skip.Contains(it.name)) { enter = false; continue; }
                if (it.isArray && it.propertyType == SerializedPropertyType.Generic)
                {
                    // its elements follow (Unity's own <path>.Array.size first); a long one as size + hash instead
                    if (it.arraySize > BigArray)
                    {
                        d[it.propertyPath + ".Array.size"] = (long)it.arraySize;
                        d[it.propertyPath + ".sha256"] = ArrayHash(it, roots);
                        enter = false;
                    }
                    continue;
                }
                var v = Value(it, roots, out var has);
                if (has)
                {
                    d[it.propertyPath] = v;
                    enter = !Compound.Contains(it.propertyType);   // a vector's x, y, z are in its value already
                }
                if (++n >= MaxProps) { d["<cut>"] = true; break; }
            }
            return d;
        }

        static string ArrayHash(SerializedProperty array, List<GameObject> roots)
        {
            var sb = new StringBuilder();
            var it = array.Copy();
            var end = array.GetEndProperty();
            var enter = true;
            while (it.NextVisible(enter) && !SerializedProperty.EqualContents(it, end))
            {
                enter = true;
                var v = Value(it, roots, out var has);
                if (has) { sb.Append(it.propertyPath.Substring(array.propertyPath.Length)).Append('='); WriteValue(sb, v); sb.Append('\n'); }
            }
            return Sha(Encoding.UTF8.GetBytes(sb.ToString()));
        }

        static object Value(SerializedProperty p, List<GameObject> roots, out bool has)
        {
            has = true;
            switch (p.propertyType)
            {
                case SerializedPropertyType.Integer: return p.longValue;
                case SerializedPropertyType.Boolean: return p.boolValue;
                case SerializedPropertyType.Float: return R(p.doubleValue);
                case SerializedPropertyType.String: return p.stringValue;
                case SerializedPropertyType.Color: return C(p.colorValue);
                case SerializedPropertyType.ObjectReference: return Ref(p.objectReferenceValue, roots);
                case SerializedPropertyType.ExposedReference: return Ref(p.exposedReferenceValue, roots);
                case SerializedPropertyType.LayerMask: return (long)p.intValue;
                case SerializedPropertyType.Enum:
                    return p.enumValueIndex >= 0 && p.enumValueIndex < p.enumNames.Length ? p.enumNames[p.enumValueIndex] : (object)(long)p.intValue;
                case SerializedPropertyType.Vector2: return V(p.vector2Value);
                case SerializedPropertyType.Vector3: return V(p.vector3Value);
                case SerializedPropertyType.Vector4: return V(p.vector4Value);
                case SerializedPropertyType.Quaternion:
                    var q = p.quaternionValue;
                    return new List<object> { R(q.x), R(q.y), R(q.z), R(q.w) };
                case SerializedPropertyType.Rect:
                    var r = p.rectValue;
                    return new List<object> { R(r.x), R(r.y), R(r.width), R(r.height) };
                case SerializedPropertyType.Bounds:
                    return new List<object> { V(p.boundsValue.center), V(p.boundsValue.extents) };
                case SerializedPropertyType.Vector2Int: return new List<object> { (long)p.vector2IntValue.x, (long)p.vector2IntValue.y };
                case SerializedPropertyType.Vector3Int:
                    return new List<object> { (long)p.vector3IntValue.x, (long)p.vector3IntValue.y, (long)p.vector3IntValue.z };
                case SerializedPropertyType.RectInt:
                    var ri = p.rectIntValue;
                    return new List<object> { (long)ri.x, (long)ri.y, (long)ri.width, (long)ri.height };
                case SerializedPropertyType.BoundsInt:
                    var bi = p.boundsIntValue;
                    return new List<object> { (long)bi.x, (long)bi.y, (long)bi.z, (long)bi.size.x, (long)bi.size.y, (long)bi.size.z };
                case SerializedPropertyType.ArraySize: return (long)p.intValue;
                case SerializedPropertyType.Character: return (long)p.intValue;
                case SerializedPropertyType.FixedBufferSize: return (long)p.fixedBufferSize;
                case SerializedPropertyType.Hash128: return p.hash128Value.ToString();
                case SerializedPropertyType.AnimationCurve:
                    var curve = p.animationCurveValue;
                    return curve == null ? null : curve.keys.Select(k => (object)new List<object> { R(k.time), R(k.value), R(k.inTangent), R(k.outTangent) }).ToList();
                case SerializedPropertyType.Gradient:
                    var g = p.gradientValue;
                    if (g == null) return null;
                    return new List<object>
                    {
                        g.colorKeys.Select(k => (object)new List<object> { R(k.time), C(k.color) }).ToList(),
                        g.alphaKeys.Select(k => (object)new List<object> { R(k.time), R(k.alpha) }).ToList(), g.mode.ToString()
                    };
                case SerializedPropertyType.ManagedReference: return p.managedReferenceFullTypename;
                case SerializedPropertyType.Generic: has = false; return null;
                default:
                    if (p.propertyType.ToString() == "RenderingLayerMask") return (long)p.uintValue;
                    return p.propertyType.ToString();
            }
        }

        public static object Ref(Object o, List<GameObject> roots = null)
        {
            if (o == null) return null;
            if (EditorUtility.IsPersistent(o))
            {
                var path = AssetDatabase.GetAssetPath(o);
                if (string.IsNullOrEmpty(path) || path.StartsWith("Library/") || path.StartsWith("Resources/unity_builtin"))
                    return "builtin:" + o.GetType().Name + ":" + o.name;
                if (AssetDatabase.IsMainAsset(o)) return "asset:" + path;
                if (o is GameObject pg) return "asset:" + path + "#" + HierPath(pg.transform);
                if (o is Component pc) return "asset:" + path + "#" + HierPath(pc.transform) + "|" + ComponentKey(pc);
                return "asset:" + path + "#" + o.GetType().Name + ":" + o.name;
            }
            if (o is GameObject go) return "scene:" + HierPath(go.transform, roots);
            if (o is Component c) return "scene:" + HierPath(c.transform, roots) + "|" + ComponentKey(c);
            return "object:" + o.GetType().Name + ":" + o.name;
        }

        static object R(double v)
        {
            var r = Math.Round(v, 4);
            return r == 0 ? 0.0 : r;
        }

        static List<object> V(Vector2 v) => new List<object> { R(v.x), R(v.y) };
        static List<object> V(Vector3 v) => new List<object> { R(v.x), R(v.y), R(v.z) };
        static List<object> V(Vector4 v) => new List<object> { R(v.x), R(v.y), R(v.z), R(v.w) };
        static List<object> C(Color c) => new List<object> { R(c.r), R(c.g), R(c.b), R(c.a) };

        static string Sha(byte[] b)
        {
            using var h = SHA256.Create();
            return BitConverter.ToString(h.ComputeHash(b)).Replace("-", "").ToLowerInvariant();
        }

        // ---------------------------------------------------------------------------------------------- JSON out
        public static void Write(string path, object value)
        {
            Directory.CreateDirectory(Path.GetDirectoryName(path));
            var sb = new StringBuilder();
            WriteValue(sb, value);
            sb.Append('\n');
            File.WriteAllText(path, sb.ToString(), new UTF8Encoding(false));
        }

        public static void WriteValue(StringBuilder sb, object v)
        {
            switch (v)
            {
                case null: sb.Append("null"); break;
                case string s: WriteString(sb, s); break;
                case bool b: sb.Append(b ? "true" : "false"); break;
                case double d: sb.Append(double.IsNaN(d) || double.IsInfinity(d) ? "null" : d.ToString("R", CultureInfo.InvariantCulture)); break;
                case float f: sb.Append(float.IsNaN(f) || float.IsInfinity(f) ? "null" : ((double)f).ToString("R", CultureInfo.InvariantCulture)); break;
                case long l: sb.Append(l.ToString(CultureInfo.InvariantCulture)); break;
                case int i: sb.Append(i.ToString(CultureInfo.InvariantCulture)); break;
                case IDictionary dict:
                    sb.Append('{');
                    var first = true;
                    foreach (DictionaryEntry e in dict)
                    {
                        if (!first) sb.Append(',');
                        first = false;
                        WriteString(sb, Convert.ToString(e.Key, CultureInfo.InvariantCulture));
                        sb.Append(':');
                        WriteValue(sb, e.Value);
                    }
                    sb.Append('}');
                    break;
                case IEnumerable list:
                    sb.Append('[');
                    var f2 = true;
                    foreach (var item in list)
                    {
                        if (!f2) sb.Append(',');
                        f2 = false;
                        WriteValue(sb, item);
                    }
                    sb.Append(']');
                    break;
                default: WriteString(sb, Convert.ToString(v, CultureInfo.InvariantCulture)); break;
            }
        }

        static void WriteString(StringBuilder sb, string s)
        {
            sb.Append('"');
            foreach (var c in s)
            {
                switch (c)
                {
                    case '"': sb.Append("\\\""); break;
                    case '\\': sb.Append("\\\\"); break;
                    case '\n': sb.Append("\\n"); break;
                    case '\r': sb.Append("\\r"); break;
                    case '\t': sb.Append("\\t"); break;
                    default:
                        if (c < 0x20) sb.Append("\\u").Append(((int)c).ToString("x4", CultureInfo.InvariantCulture));
                        else sb.Append(c);
                        break;
                }
            }
            sb.Append('"');
        }
    }
}
