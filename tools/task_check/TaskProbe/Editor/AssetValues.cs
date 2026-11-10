// Values of the editor pass: an asset's `prop:`, `import:`, `shader:` and `keyword:` fields, a material's shader
// properties, and member paths read by reflection with a SerializedObject property path as the fallback. Values are
// the checker's plain values (Reflect.Plain): numbers, strings (through `match`) or null.
using System;
using System.Collections.Generic;
using System.Globalization;
using UnityEditor;
using UnityEngine;
using UnityEngine.Rendering;

namespace TaskProbe.EditorTools
{
    public static class AssetValues
    {
        /// <summary>{"asset": path, "field": ...}: {"value": v} or {"error": ...}.</summary>
        public static Dictionary<string, object> AssetMeasure(Dictionary<string, object> m)
        {
            var path = Json.Str(m, "asset");
            var field = Json.Str(m, "field") ?? "";
            var asset = AssetDatabase.LoadMainAssetAtPath(path);
            if (asset == null) return AssetPass.Error("no asset " + path);
            if (field.StartsWith("prop:", StringComparison.Ordinal))
            {
                var p = field.Substring(5);
                var value = asset is GameObject go ? ObjectProp(go, p, out var ok) : Path(asset, p, out ok);
                return ok ? AssetPass.Value(value) : AssetPass.Error("no property " + p + " on " + asset.GetType().Name + " " + path);
            }
            if (field.StartsWith("import:", StringComparison.Ordinal))
            {
                var p = field.Substring(7);
                var importer = AssetImporter.GetAtPath(path);
                if (importer == null) return AssetPass.Error("no importer for " + path);
                var value = Path(importer, p, out var ok);
                if (!ok)
                {
                    // an audio clip's load and compression settings live in its default sample settings
                    var settings = Reflect.Get(importer, "defaultSampleSettings");
                    if (settings != null)
                    {
                        var read = Reflect.ReadPath(settings, p, out ok);
                        if (ok) value = Reflect.Plain(read);
                    }
                }
                return ok ? AssetPass.Value(value) : AssetPass.Error("no import setting " + p + " on " + importer.GetType().Name + " " + path);
            }
            if (field.StartsWith("shader:", StringComparison.Ordinal) || field.StartsWith("keyword:", StringComparison.Ordinal))
            {
                if (!(asset is Material material)) return AssetPass.Error(path + " is not a material (" + asset.GetType().Name + ")");
                var spec = field.StartsWith("shader:", StringComparison.Ordinal) ? field.Substring(7) : field;
                if (spec == "name") spec = "shader";  // shader:name = the shader's name
                var value = MaterialValue(material, spec, out var error);
                return error != null ? AssetPass.Error(error) : AssetPass.Value(value);
            }
            return AssetPass.Error("unknown asset field " + field + " (prop:, import:, shader:, keyword:)");
        }

        // ---------------------------------------------------------------- materials

        /// <summary>A material's `spec`: `shader` (its shader's name), `keyword:NAME` (1 when enabled), or a shader
        /// property: a float, range or int as it is, `.r|g|b|a` of a colour, `.x|y|z|w` of a vector, a texture 1 when set
        /// (`.name`: the texture's name). `error` says why there is no value.</summary>
        public static object MaterialValue(Material material, string spec, out string error)
        {
            error = null;
            if (material == null) return null;
            if (spec == "shader") return material.shader != null ? material.shader.name : null;
            if (spec.StartsWith("keyword:", StringComparison.Ordinal))
                return material.IsKeywordEnabled(spec.Substring(8)) ? 1.0 : 0.0;
            var dot = spec.IndexOf('.');
            var name = dot < 0 ? spec : spec.Substring(0, dot);
            var sub = dot < 0 ? null : spec.Substring(dot + 1);
            var shader = material.shader;
            var index = shader != null ? shader.FindPropertyIndex(name) : -1;
            if (index < 0)
            {
                error = "no shader property " + name + " on " + (shader != null ? shader.name : "a material without a shader") + " (" + material.name + ")";
                return null;
            }
            switch (shader.GetPropertyType(index))
            {
                case ShaderPropertyType.Float:
                case ShaderPropertyType.Range:
                    if (sub == null) return (double)material.GetFloat(name);
                    break;
                case ShaderPropertyType.Int:
                    if (sub == null) return (double)material.GetInteger(name);
                    break;
                case ShaderPropertyType.Color:
                {
                    var c = material.GetColor(name);
                    var v = Channel(new Vector4(c.r, c.g, c.b, c.a), sub);
                    if (v.HasValue) return v.Value;
                    error = name + " is a colour: name a channel (" + name + ".r, .g, .b or .a)";
                    return null;
                }
                case ShaderPropertyType.Vector:
                {
                    var v = Channel(material.GetVector(name), sub);
                    if (v.HasValue) return v.Value;
                    error = name + " is a vector: name a channel (" + name + ".x, .y, .z or .w)";
                    return null;
                }
                case ShaderPropertyType.Texture:
                {
                    var t = material.GetTexture(name);
                    if (sub == null) return t != null ? 1.0 : 0.0;
                    if (sub == "name") return t != null ? t.name : null;
                    break;
                }
            }
            error = "no " + sub + " on the shader property " + name;
            return null;
        }

        static double? Channel(Vector4 v, string sub)
        {
            switch (sub)
            {
                case "r": case "x": return v.x;
                case "g": case "y": return v.y;
                case "b": case "z": return v.z;
                case "a": case "w": return v.w;
            }
            return null;
        }

        static Material[] defaults;

        /// <summary>Unity's default materials: the built-in ones and the active render pipeline's default material (what
        /// a new primitive gets). A slot holding one is a placeholder.</summary>
        public static bool IsDefault(Material material)
        {
            if (defaults == null)
            {
                var found = new List<Material>();
                foreach (var name in new[] { "Default-Material.mat", "Default-Diffuse.mat" })
                {
                    try
                    {
                        var m = AssetDatabase.GetBuiltinExtraResource<Material>(name);
                        if (m != null) found.Add(m);
                    }
                    catch { }
                }
                var pipeline = GraphicsSettings.currentRenderPipeline;
                if (pipeline != null && Reflect.Get(pipeline, "defaultMaterial") is Material own && own != null) found.Add(own);
                defaults = found.ToArray();
            }
            return Array.IndexOf(defaults, material) >= 0;
        }

        /// <summary>A shader that draws Unity's magenta error: none, the error shader, or one that doesn't compile.</summary>
        public static bool IsErrorShader(Shader shader)
        {
            if (shader == null || shader.name == "Hidden/InternalErrorShader") return true;
            try { return ShaderUtil.ShaderHasError(shader); }
            catch { return false; }
        }

        // ---------------------------------------------------------------- member paths

        /// <summary>`path` on a Unity object: by reflection (Reflect.ReadPath), else as a SerializedObject property path.
        /// `ok` false when neither resolves.</summary>
        public static object Path(UnityEngine.Object target, string path, out bool ok)
        {
            var read = Reflect.ReadPath(target, path, out ok);
            if (ok) return Reflect.Plain(read);
            return Serialized(target, path, out ok);
        }

        /// <summary>prop:&lt;Component&gt;.&lt;path&gt; on an object as Reflect.Prop reads it, else a SerializedObject path on the
        /// named component (or the GameObject).</summary>
        public static object ObjectProp(GameObject go, string path, out bool ok)
        {
            ok = false;
            if (go == null || string.IsNullOrEmpty(path)) return null;
            var dot = path.IndexOf('.');
            var component = dot > 0 ? Reflect.ComponentNamed(go, path.Substring(0, dot)) : null;
            var value = Reflect.Prop(go, component != null ? Shared(component, path, dot) : path);
            if (value != null) { ok = true; return value; }
            if (component != null)
            {
                value = Serialized(component, path.Substring(dot + 1), out ok);
                if (ok) return value;
            }
            return Serialized(go, path, out ok);
        }

        /// <summary>A component's `material`, `materials` and `mesh` (and the like) read as their shared forms: in the
        /// editor the instancing getters copy the asset into the scene (and log a leak), which a read must never do.</summary>
        static string Shared(Component component, string path, int dot)
        {
            var rest = path.Substring(dot + 1);
            var end = rest.IndexOfAny(new[] { '.', '[' });
            var member = end < 0 ? rest : rest.Substring(0, end);
            if (member.Length == 0) return path;
            var shared = "shared" + char.ToUpperInvariant(member[0]) + member.Substring(1);
            if (component.GetType().GetProperty(shared) == null) return path;
            return path.Substring(0, dot + 1) + shared + (end < 0 ? "" : rest.Substring(end));
        }

        /// <summary>A SerializedObject property path on `target` (`m_Name`, `m_Materials.Array.size`, `waves[2].count`
        /// as `waves.Array.data[2].count`), as a plain value. `ok` false when there is no such property.</summary>
        public static object Serialized(UnityEngine.Object target, string path, out bool ok)
        {
            ok = false;
            if (target == null || string.IsNullOrEmpty(path)) return null;
            using (var so = new SerializedObject(target))
            {
                var p = so.FindProperty(path);
                if (p == null && path.IndexOf('[') >= 0) p = so.FindProperty(ArrayPath(path));
                if (p == null) return null;
                ok = true;
                return PlainProperty(p);
            }
        }

        static string ArrayPath(string path)
        {
            var sb = new System.Text.StringBuilder(path.Length + 16);
            for (var i = 0; i < path.Length; i++)
            {
                if (path[i] == '[' && !(i >= 10 && path.Substring(i - 10, 10) == "Array.data")) sb.Append(".Array.data");
                sb.Append(path[i]);
            }
            return sb.ToString();
        }

        /// <summary>A serialized property as the checker takes it: numbers and bools as numbers, enums as their value, an
        /// object reference 1 when set, strings as they are, an array as its length; anything else (a colour or vector
        /// without its channel) null.</summary>
        static object PlainProperty(SerializedProperty p)
        {
            if (p.isArray && p.propertyType != SerializedPropertyType.String) return (double)p.arraySize;
            switch (p.propertyType)
            {
                case SerializedPropertyType.Integer:
                case SerializedPropertyType.LayerMask:
                case SerializedPropertyType.ArraySize:
                case SerializedPropertyType.FixedBufferSize:
                    return (double)p.longValue;
                case SerializedPropertyType.Enum: return (double)p.intValue;
                case SerializedPropertyType.Boolean: return p.boolValue ? 1.0 : 0.0;
                case SerializedPropertyType.Float:
                {
                    var d = p.doubleValue;
                    return double.IsNaN(d) || double.IsInfinity(d) ? null : (object)d;
                }
                case SerializedPropertyType.String: return p.stringValue;
                case SerializedPropertyType.Character: return ((char)p.intValue).ToString(CultureInfo.InvariantCulture);
                case SerializedPropertyType.ObjectReference:
                case SerializedPropertyType.ExposedReference:
                    return p.propertyType == SerializedPropertyType.ObjectReference && p.objectReferenceValue != null ? 1.0 : 0.0;
            }
            return null;
        }
    }
}
