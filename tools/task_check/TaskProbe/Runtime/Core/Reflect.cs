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
        const BindingFlags Members = BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.FlattenHierarchy;
        static readonly Dictionary<string, Type[]> TypesByName = new Dictionary<string, Type[]>(StringComparer.Ordinal);

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

        /// <summary>Whether a component can be of a type named `name`: a Component type, an interface, or one of
        /// Component's own bases (Object) has that name. A select naming anything else matches nothing.</summary>
        public static bool NamesComponent(string name)
        {
            foreach (var t in TypesNamed(name))
                if (typeof(Component).IsAssignableFrom(t) || t.IsInterface || t.IsAssignableFrom(typeof(Component))) return true;
            return false;
        }

        /// <summary>Whether `type`, one of its base types or one of its interfaces is named `name` (name or full name).</summary>
        public static bool IsA(Type type, string name)
        {
            for (var t = type; t != null; t = t.BaseType)
                if (t.Name == name || t.FullName == name) return true;
            foreach (var i in type.GetInterfaces())
                if (i.Name == name || i.FullName == name) return true;
            return false;
        }

        /// <summary>A component of `go` whose type is named `typeName` (or derives from it); with `descendants`, else the
        /// first in its descendants (inactive ones included). Null when none.</summary>
        public static Component ComponentNamed(GameObject go, string typeName, bool descendants = true)
        {
            if (go == null || string.IsNullOrEmpty(typeName)) return null;
            var type = TypeNamed(typeName);
            if (type != null && typeof(Component).IsAssignableFrom(type))
            {
                var own = go.GetComponent(type);
                if (own != null) return own;
                return descendants ? go.GetComponentInChildren(type, true) : null;
            }
            // an interface, or a name only a base type carries: look at each component
            foreach (var c in descendants ? go.GetComponentsInChildren<Component>(true) : go.GetComponents<Component>())
                if (c != null && IsA(c.GetType(), typeName)) return c;
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

        /// <summary>`path` (member[.member][[i]]...) read from `root`: fields and properties, public or not. `ok` false
        /// when a step doesn't resolve. An array or list without an index gives its length.</summary>
        public static object ReadPath(object root, string path, out bool ok)
        {
            ok = false;
            var value = root;
            foreach (var token in path.Split('.'))
            {
                if (value == null || IsDead(value)) return null;
                if (!SplitToken(token, out var name, out var index)) return null;
                if (name.Length > 0 && !ReadMember(value, name, out value)) return null;
                if (index >= 0)
                {
                    if (!(value is IList list) || index >= list.Count) return null;
                    value = list[index];
                }
            }
            ok = true;
            return value;
        }

        static bool SplitToken(string token, out string name, out int index)
        {
            name = token;
            index = -1;
            var open = token.IndexOf('[');
            if (open < 0) return token.Length > 0;
            if (!token.EndsWith("]", StringComparison.Ordinal)) return false;
            name = token.Substring(0, open);
            return int.TryParse(token.Substring(open + 1, token.Length - open - 2), NumberStyles.None, CultureInfo.InvariantCulture, out index);
        }

        static bool ReadMember(object target, string name, out object value)
        {
            value = null;
            for (var t = target.GetType(); t != null; t = t.BaseType)
            {
                var field = t.GetField(name, Members | BindingFlags.DeclaredOnly);
                if (field != null)
                {
                    value = field.GetValue(target);
                    return true;
                }
                var property = t.GetProperty(name, Members | BindingFlags.DeclaredOnly);
                if (property != null && property.CanRead && property.GetIndexParameters().Length == 0)
                {
                    try { value = property.GetValue(target, null); }
                    catch { return false; }  // a property that throws (a destroyed object, a missing reference) has no value
                    return true;
                }
            }
            // a dictionary's entry by key
            if (target is IDictionary dict && dict.Contains(name)) { value = dict[name]; return true; }
            return false;
        }

        static bool IsDead(object value) => value is UnityEngine.Object o && o == null;

        /// <summary>A read value as the checker takes it: numbers and bools as numbers, enums as their value, a Unity
        /// object reference 1 when set and 0 when not, strings as they are (through `match`), an array or list as its
        /// length; anything else null.</summary>
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
            return null;
        }

        /// <summary>prop:&lt;Component&gt;.&lt;member&gt;[.&lt;sub&gt;] or prop:&lt;member&gt; on an object, without the "prop:" (the
        /// component by type name on the object, else the first in its descendants; a single member reads the GameObject,
        /// else its Transform). Null when it doesn't resolve.</summary>
        public static object Prop(GameObject go, string path)
        {
            if (go == null || string.IsNullOrEmpty(path)) return null;
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

        // ---------------------------------------------------------------- calling members of optional packages

        /// <summary>A public instance or static property or field of `target` (or of `type` when `target` is null), by
        /// name; null when it has none. For types of packages the probe doesn't reference.</summary>
        public static object Get(object target, string name, Type type = null)
        {
            var t = target != null ? target.GetType() : type;
            if (t == null) return null;
            const BindingFlags flags = BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance | BindingFlags.Static | BindingFlags.FlattenHierarchy;
            try
            {
                var property = t.GetProperty(name, flags);
                if (property != null && property.CanRead) return property.GetValue(target, null);
                var field = t.GetField(name, flags);
                return field != null ? field.GetValue(target) : null;
            }
            catch { return null; }
        }

        /// <summary>Calls a method of `target` (or a static one of `type`) by name with `args`; null when there is none
        /// or it throws.</summary>
        public static object Call(object target, string name, Type type, params object[] args)
        {
            var t = target != null ? target.GetType() : type;
            if (t == null) return null;
            const BindingFlags flags = BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance | BindingFlags.Static | BindingFlags.FlattenHierarchy;
            try
            {
                foreach (var method in t.GetMethods(flags))
                {
                    if (method.Name != name || method.GetParameters().Length != args.Length) continue;
                    return method.Invoke(target, args);
                }
            }
            catch { }
            return null;
        }
    }
}
