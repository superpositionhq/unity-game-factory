// Types and members by name: a select's `component`, and `prop:<Component>.<member>[.<sub>]` paths. Everything is read
// by reflection, so the probe compiles against no game code and no optional package. Unknown names give null, never
// an exception.
using System;
using System.Collections;
using System.Collections.Generic;
using System.Globalization;
using System.Reflection;
using UnityEngine;

namespace TaskProbe
{
    public static class Reflect
    {
        const int MaxSteps = 16;  // a path of more steps reads nothing
        static readonly Dictionary<string, Type[]> TypesByName = new Dictionary<string, Type[]>(StringComparer.Ordinal);
        static readonly Dictionary<Type, Type[]> Implementers = new Dictionary<Type, Type[]>();
        static readonly Dictionary<Type, HashSet<string>> NamesOfType = new Dictionary<Type, HashSet<string>>();
        static readonly Dictionary<(Type, string, bool), MemberInfo> MembersByName = new Dictionary<(Type, string, bool), MemberInfo>();
        static readonly List<Component> Parts = new List<Component>();

        /// <summary>A type by its name (`Projectile`) or full name (`Game.Projectile`), in any loaded assembly; null when
        /// there is none. Of several types of one name, a Component type wins, then the first found.</summary>
        public static Type TypeNamed(string name)
        {
            Type first = null;
            foreach (var t in TypesNamed(name))
            {
                if (typeof(Component).IsAssignableFrom(t)) return t;
                if (first == null) first = t;
            }
            return first;
        }

        /// <summary>Every type of the loaded assemblies named `name` (name or full name), in the order the assemblies
        /// and their types are loaded; none for an empty name.</summary>
        public static Type[] TypesNamed(string name)
        {
            if (string.IsNullOrEmpty(name)) return Type.EmptyTypes;
            if (TypesByName.TryGetValue(name, out var cached)) return cached;
            var found = new List<Type>();
            foreach (var assembly in AppDomain.CurrentDomain.GetAssemblies())
            {
                Type[] types;
                try { types = assembly.GetTypes(); }
                catch (ReflectionTypeLoadException e) { types = e.Types; }
                catch { continue; }
                foreach (var t in types)
                    if (t != null && (t.Name == name || t.FullName == name)) found.Add(t);
            }
            return TypesByName[name] = found.ToArray();
        }

        /// <summary>The Component types of the loaded assemblies that implement the interface `iface` (generic ones left
        /// out), but those whose base type is one of them: a search for a type finds its subclasses too.</summary>
        public static Type[] ComponentsImplementing(Type iface)
        {
            if (Implementers.TryGetValue(iface, out var cached)) return cached;
            var found = new HashSet<Type>();
            foreach (var assembly in AppDomain.CurrentDomain.GetAssemblies())
            {
                Type[] types;
                try { types = assembly.GetTypes(); }
                catch (ReflectionTypeLoadException e) { types = e.Types; }
                catch { continue; }
                foreach (var t in types)
                    if (t != null && !t.IsInterface && !t.ContainsGenericParameters && typeof(Component).IsAssignableFrom(t) && iface.IsAssignableFrom(t))
                        found.Add(t);
            }
            var top = new List<Type>();
            foreach (var t in found)
                if (t.BaseType == null || !found.Contains(t.BaseType)) top.Add(t);
            return Implementers[iface] = top.ToArray();
        }

        /// <summary>Whether a component can be of a type named `name`: a Component type, an interface, or one of
        /// Component's own bases (Object) has that name. A select naming anything else matches nothing.</summary>
        public static bool NamesComponent(string name)
        {
            foreach (var t in TypesNamed(name))
                if (typeof(Component).IsAssignableFrom(t) || t.IsInterface || t.IsAssignableFrom(typeof(Component))) return true;
            return false;
        }

        /// <summary>Whether `type`, one of its base types or one of its interfaces is named `name` (name or full name):
        /// two types of one name in two namespaces both are.</summary>
        public static bool IsA(Type type, string name)
        {
            if (!NamesOfType.TryGetValue(type, out var names))
            {
                names = new HashSet<string>(StringComparer.Ordinal);
                for (var t = type; t != null; t = t.BaseType) Add(names, t);
                foreach (var i in type.GetInterfaces()) Add(names, i);
                NamesOfType[type] = names;
            }
            return names.Contains(name);
        }

        static void Add(HashSet<string> names, Type t)
        {
            names.Add(t.Name);
            if (t.FullName != null) names.Add(t.FullName);
        }

        /// <summary>The first component of `go` (in the Inspector's order) whose type is named `typeName` (IsA); with
        /// `descendants`, else the first in its descendants in hierarchy order, inactive ones included. Null when none;
        /// never the probe's own.</summary>
        public static Component ComponentNamed(GameObject go, string typeName, bool descendants = true)
        {
            if (go == null || string.IsNullOrEmpty(typeName)) return null;
            go.GetComponents(Parts);
            foreach (var c in Parts)
                if (c != null && !Find.IsOwn(c) && IsA(c.GetType(), typeName)) return c;
            if (!descendants) return null;
            go.GetComponentsInChildren(true, Parts);
            foreach (var c in Parts)
                if (c != null && c.gameObject != go && !Find.IsOwn(c) && IsA(c.GetType(), typeName)) return c;
            return null;
        }

        /// <summary>A Part of an object (rel_yaw:, world_yaw:, forward:, bone:): a descendant by its GameObject name, else
        /// the object in it (itself included) that carries a component of that type name. Null when none.</summary>
        public static Transform Part(GameObject go, string name)
        {
            if (go == null || string.IsNullOrEmpty(name)) return null;
            foreach (var t in go.GetComponentsInChildren<Transform>(true))
                if (t.name == name) return t;
            var c = ComponentNamed(go, name);
            return c != null ? c.transform : null;
        }

        // ---------------------------------------------------------------- member paths

        /// <summary>`path` (member[.member][[i]]...) read from `root`: fields and properties, public or not, of the type
        /// and its bases (static ones and indexers aren't read). `ok` false when a step doesn't resolve. An array or list
        /// without an index gives its length.</summary>
        public static object ReadPath(object root, string path, out bool ok)
        {
            ok = false;
            var tokens = path.Split('.');
            if (tokens.Length > MaxSteps) return null;
            var value = root;
            foreach (var token in tokens)
            {
                if (value == null || IsDead(value)) return null;
                if (!SplitToken(token, out var name, out var index)) return null;
                if (!ReadMember(value, name, out value)) return null;
                if (index >= 0)
                {
                    if (!(value is IList list) || index >= list.Count) return null;
                    value = list[index];
                }
            }
            ok = true;
            return value;
        }

        /// <summary>`name` or `name[i]` (i a whole number); false for anything else (an empty name, a sign, a fraction).</summary>
        static bool SplitToken(string token, out string name, out int index)
        {
            name = token;
            index = -1;
            var open = token.IndexOf('[');
            if (open < 0) return token.Length > 0;
            if (open == 0 || !token.EndsWith("]", StringComparison.Ordinal)) return false;
            name = token.Substring(0, open);
            return int.TryParse(token.Substring(open + 1, token.Length - open - 2), NumberStyles.None, CultureInfo.InvariantCulture, out index);
        }

        static bool ReadMember(object target, string name, out object value)
        {
            value = null;
            switch (MemberNamed(target.GetType(), name, false))
            {
                case FieldInfo field:
                    value = field.GetValue(target);
                    return true;
                case PropertyInfo property:
                    try { value = property.GetValue(target, null); }
                    catch { return false; }  // a property that throws (a destroyed object, a missing reference) has no value
                    return true;
            }
            // a dictionary's entry by key
            if (target is IDictionary dict && dict.Contains(name)) { value = dict[name]; return true; }
            return false;
        }

        /// <summary>A readable field or property of `type` by name, the most derived first (private ones of a base type
        /// too), indexers left out; with `statics` static ones too. An instancing getter (a renderer's `material` and
        /// `materials`, a filter's `mesh`, a collider's `material`, TextMeshPro's `fontMaterial` and `fontMaterials`)
        /// gives the component a copy of the asset of its own, which then no longer follows the shared asset: a property
        /// that has a shared twin (`shared&lt;Name&gt;`, or `...SharedMaterial...`) is read through it.</summary>
        static MemberInfo MemberNamed(Type type, string name, bool statics)
        {
            var key = (type, name, statics);
            if (MembersByName.TryGetValue(key, out var found)) return found;
            found = Declared(type, name, statics);
            if (found is PropertyInfo && name.Length > 0)
                foreach (var twin in new[] { "shared" + char.ToUpperInvariant(name[0]) + name.Substring(1), name.Replace("Material", "SharedMaterial") })
                    if (twin != name && Declared(type, twin, statics) is MemberInfo shared)
                    {
                        found = shared;
                        break;
                    }
            return MembersByName[key] = found;
        }

        static MemberInfo Declared(Type type, string name, bool statics)
        {
            var flags = BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.DeclaredOnly;
            if (statics) flags |= BindingFlags.Static;
            for (var t = type; t != null; t = t.BaseType)
            {
                try
                {
                    var field = t.GetField(name, flags);
                    if (field != null) return field;
                    var property = t.GetProperty(name, flags);
                    if (property != null && property.CanRead && property.GetIndexParameters().Length == 0) return property;
                }
                catch (AmbiguousMatchException) { return null; }  // overloaded indexers named Item
            }
            return null;
        }

        static bool IsDead(object value) => value is UnityEngine.Object o && o == null;

        /// <summary>A read value as the checker takes it: numbers and bools as numbers (NaN and infinities as no value),
        /// enums as their value, strings as they are (through `match`), an array, list, dictionary or set as its count,
        /// an object reference 1 when set and 0 when not (a destroyed Unity object is not set); a struct (read it by its
        /// members: `.x`, `.r`) or anything else null.</summary>
        public static object Plain(object value)
        {
            switch (value)
            {
                case null: return 0.0;  // an unset reference
                case bool b: return b ? 1.0 : 0.0;
                case string s: return s;
                case char c: return c.ToString();
                case Enum e: return Convert.ToDouble(e, CultureInfo.InvariantCulture);
                case UnityEngine.Object o: return o != null ? 1.0 : 0.0;
                case ICollection collection: return (double)collection.Count;
            }
            if (value is IConvertible)
            {
                try
                {
                    var d = Convert.ToDouble(value, CultureInfo.InvariantCulture);
                    return double.IsNaN(d) || double.IsInfinity(d) ? null : (object)d;
                }
                catch { return null; }
            }
            var type = value.GetType();
            if (value is IEnumerable)
            {
                try
                {
                    // a set (HashSet) is no ICollection, but has its Count
                    if (type.GetProperty("Count") is PropertyInfo count && count.PropertyType == typeof(int))
                        return (double)(int)count.GetValue(value, null);
                }
                catch { return null; }
            }
            return type.IsValueType ? null : (object)1.0;
        }

        /// <summary>prop:&lt;Component&gt;.&lt;member&gt;[.&lt;sub&gt;] or prop:&lt;member&gt; on an object, without the "prop:" (the
        /// component by type name on the object, else the first in its descendants; a single member reads the GameObject,
        /// else its Transform). Null when it doesn't resolve or has more than 16 steps.</summary>
        public static object Prop(GameObject go, string path)
        {
            if (go == null || string.IsNullOrEmpty(path) || path.Split('.').Length > MaxSteps) return null;
            var dot = path.IndexOf('.');
            if (dot > 0)
            {
                var head = path.Substring(0, dot);
                var bracket = head.IndexOf('[');
                var component = ComponentNamed(go, bracket < 0 ? head : head.Substring(0, bracket));
                if (component != null && bracket < 0)
                {
                    var read = ReadPath(component, path.Substring(dot + 1), out var ok);
                    if (ok) return Plain(read);
                }
            }
            var own = ReadPath(go, path, out var found);
            if (found) return Plain(own);
            own = ReadPath(go.transform, path, out found);
            if (found) return Plain(own);
            // a component alone names whether the object has one
            if (dot < 0 && ComponentNamed(go, path) != null) return 1.0;
            return null;
        }

        /// <summary>prop:&lt;path&gt; on a component itself.</summary>
        public static object Prop(Component component, string path)
        {
            if (component == null || string.IsNullOrEmpty(path)) return null;
            var read = ReadPath(component, path, out var ok);
            return ok ? Plain(read) : null;
        }

        // ---------------------------------------------------------------- members of optional packages

        /// <summary>A property or field of `target` (or a static one of `type` when `target` is null), public or not,
        /// by name, as ReadPath finds members; null when it has none or reading it throws. For types of packages the
        /// probe doesn't reference.</summary>
        public static object Get(object target, string name, Type type = null)
        {
            var t = target != null ? target.GetType() : type;
            if (t == null) return null;
            try
            {
                switch (MemberNamed(t, name, true))
                {
                    case FieldInfo f: return f.GetValue(target);
                    case PropertyInfo p: return p.GetValue(target, null);
                }
            }
            catch { }
            return null;
        }
    }
}
