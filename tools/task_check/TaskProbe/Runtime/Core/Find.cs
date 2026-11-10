// Selects and points (contract sections 2 and 3): which objects a select matches, where a point is, whether a place is
// near. An object is a GameObject; its parts are the components of itself and its descendants. Only objects active in
// the hierarchy match unless the select says "inactive": true. Matches come in hierarchy order (scene, then sibling
// indices from the root down), so "the first match" is the same object in every play of one scene.
using System;
using System.Collections.Generic;
using System.Text.RegularExpressions;
using UnityEngine;

namespace TaskProbe
{
    /// <summary>{"point": &lt;Point&gt;, "radius": m, "y_min", "y_max", "y_relative"}.</summary>
    public sealed class NearSel
    {
        public Dictionary<string, object> Point;
        public float Radius;
        public float? YMin, YMax;
        public bool YRelative;

        public static NearSel Parse(Dictionary<string, object> near)
        {
            if (near == null) return null;
            var found = new NearSel { Point = Json.Obj(near, "point"), Radius = (float)Json.Num(near, "radius", 0), YRelative = Json.Bool(near, "y_relative") };
            if (Json.TryNum(near, "y_min", out var lo)) found.YMin = (float)lo;
            if (Json.TryNum(near, "y_max", out var hi)) found.YMax = (float)hi;
            return found;
        }

        /// <summary>The point it is near, now; false when it doesn't resolve (no player yet, no object matches).</summary>
        public bool Resolve(out Vector3 centre) => Find.Point(Point, out centre);

        /// <summary>Whether `place` is within the radius of `centre` and inside the height band.</summary>
        public bool Contains(Vector3 centre, Vector3 place)
        {
            if ((place - centre).sqrMagnitude > Radius * Radius) return false;
            var y = YRelative ? place.y - centre.y : place.y;
            return (!YMin.HasValue || y >= YMin.Value) && (!YMax.HasValue || y <= YMax.Value);
        }
    }

    /// <summary>A select's `has`: a component in the object (or its descendants) that matches every key given.</summary>
    public sealed class HasSel
    {
        public string Component;
        public bool Lit, Visible, Simulating, Movable;
        public NearSel Near;

        public static HasSel Parse(Dictionary<string, object> has)
        {
            if (has == null) return null;
            return new HasSel
            {
                Component = Json.Str(has, "component"), Lit = Json.Bool(has, "lit"), Visible = Json.Bool(has, "visible"),
                Simulating = Json.Bool(has, "simulating"), Movable = Json.Bool(has, "movable"), Near = NearSel.Parse(Json.Obj(has, "near")),
            };
        }
    }

    /// <summary>An object select: every key given must match.</summary>
    public sealed class Sel
    {
        public string Component, Tag, Layer, Name;
        public bool Player, Inactive;
        public NearSel Near;
        public HasSel Has;

        public static Sel Parse(Dictionary<string, object> select)
        {
            var s = new Sel();
            if (select == null) return s;
            s.Component = Json.Str(select, "component");
            s.Tag = Json.Str(select, "tag");
            s.Layer = Json.Str(select, "layer");
            s.Name = Json.Str(select, "name");
            s.Player = Json.Bool(select, "player");
            s.Inactive = Json.Bool(select, "inactive");
            s.Near = NearSel.Parse(Json.Obj(select, "near"));
            s.Has = HasSel.Parse(Json.Obj(select, "has"));
            return s;
        }
    }

    public static class Find
    {
        /// <summary>has.lit: whether a component gives off light (a Light that is on, a drawn mesh whose material emits,
        /// a live particle system). Set by the objects queries ([ProbeInit]); without it `lit` matches nothing.</summary>
        public static Func<Component, bool> LitTest;

        const int MaxDepth = 4;  // a select inside a point inside a select...
        static readonly Dictionary<string, Regex> Wildcards = new Dictionary<string, Regex>(StringComparer.Ordinal);

        /// <summary>A wildcard match (* any run, ? one character), case-insensitive, on the whole text.</summary>
        public static bool Wild(string pattern, string text)
        {
            if (pattern == null) return true;
            if (text == null) return false;
            if (!Wildcards.TryGetValue(pattern, out var rx))
            {
                rx = new Regex("^" + Regex.Escape(pattern).Replace("\\*", ".*").Replace("\\?", ".") + "$",
                    RegexOptions.IgnoreCase | RegexOptions.CultureInvariant | RegexOptions.Singleline);
                Wildcards[pattern] = rx;
            }
            return rx.IsMatch(text);
        }

        /// <summary>A regular expression from a task (text, match), or null when it doesn't compile.</summary>
        public static Regex Pattern(string pattern)
        {
            if (string.IsNullOrEmpty(pattern)) return null;
            try { return new Regex(pattern, RegexOptions.CultureInvariant); }
            catch (ArgumentException) { return null; }
        }

        // ---------------------------------------------------------------- objects

        /// <summary>Every object of the loaded scenes (the DontDestroyOnLoad scene too), the probe's own left out.</summary>
        public static IEnumerable<GameObject> All(bool inactive)
        {
            var transforms = UnityEngine.Object.FindObjectsByType<Transform>(
                inactive ? FindObjectsInactive.Include : FindObjectsInactive.Exclude, FindObjectsSortMode.None);
            foreach (var t in transforms)
                if (t != null && !Probe.IsOwn(t.gameObject)) yield return t.gameObject;
        }

        /// <summary>The objects `sel` matches, in hierarchy order, at most `limit` of them; `total` counts them all.</summary>
        public static List<GameObject> Objects(Sel sel, int limit, out int total, int depth = 0)
        {
            var found = new List<GameObject>();
            total = 0;
            if (depth > MaxDepth) return found;
            var centre = Vector3.zero;
            if (sel.Near != null && !Find.Point(sel.Near.Point, out centre, depth + 1)) return found;
            var hasCentre = Vector3.zero;
            if (sel.Has?.Near != null && !Find.Point(sel.Has.Near.Point, out hasCentre, depth + 1)) return found;
            if (sel.Player)
            {
                var player = Probe.Active != null ? Probe.Active.Player : null;
                if (player != null && Matches(player, sel, centre, hasCentre)) found.Add(player);
                total = found.Count;
                return found;
            }
            foreach (var go in Candidates(sel))
                if (Matches(go, sel, centre, hasCentre)) found.Add(go);
            total = found.Count;
            SortByHierarchy(found);
            if (found.Count > limit) found.RemoveRange(limit, found.Count - limit);
            return found;
        }

        /// <summary>The first object `sel` matches, or null.</summary>
        public static GameObject First(Sel sel, int depth = 0)
        {
            var found = Objects(sel, 1, out _, depth);
            return found.Count > 0 ? found[0] : null;
        }

        static IEnumerable<GameObject> Candidates(Sel sel)
        {
            var type = sel.Component != null ? Reflect.TypeNamed(sel.Component) : null;
            if (type != null && typeof(Component).IsAssignableFrom(type))
            {
                var seen = new HashSet<GameObject>();
                foreach (var o in UnityEngine.Object.FindObjectsByType(type,
                             sel.Inactive ? FindObjectsInactive.Include : FindObjectsInactive.Exclude, FindObjectsSortMode.None))
                    if (o is Component c && c != null && !Probe.IsOwn(c.gameObject) && seen.Add(c.gameObject)) yield return c.gameObject;
                yield break;
            }
            foreach (var go in All(sel.Inactive)) yield return go;
        }

        /// <summary>Whether `go` matches every key of `sel` (`centre`, `hasCentre`: its near's and its has.near's points,
        /// resolved).</summary>
        public static bool Matches(GameObject go, Sel sel, Vector3 centre, Vector3 hasCentre)
        {
            if (go == null) return false;
            if (!sel.Inactive && !go.activeInHierarchy) return false;
            if (sel.Name != null && !Wild(sel.Name, go.name)) return false;
            if (sel.Tag != null && !HasTag(go, sel.Tag)) return false;
            if (sel.Layer != null && LayerMask.LayerToName(go.layer) != sel.Layer) return false;
            if (sel.Component != null && Reflect.ComponentNamed(go, sel.Component, false) == null) return false;
            if (sel.Near != null && !sel.Near.Contains(centre, go.transform.position)) return false;
            if (sel.Has != null && !Carries(go, sel.Has, hasCentre)) return false;
            return true;
        }

        /// <summary>Whether `go` matches `sel` now (its near points resolved here).</summary>
        public static bool Matches(GameObject go, Sel sel, int depth = 0)
        {
            var centre = Vector3.zero;
            if (sel.Near != null && !Find.Point(sel.Near.Point, out centre, depth + 1)) return false;
            var hasCentre = Vector3.zero;
            if (sel.Has?.Near != null && !Find.Point(sel.Has.Near.Point, out hasCentre, depth + 1)) return false;
            if (sel.Player && (Probe.Active == null || Probe.Active.Player != go)) return false;
            return Matches(go, sel, centre, hasCentre);
        }

        /// <summary>Whether `component`'s object, or one of its ancestors, matches `owner` (a components, pieces or audio
        /// select's `owner`).</summary>
        public static bool OwnedBy(Component component, Sel owner, Vector3 centre, Vector3 hasCentre)
        {
            for (var t = component.transform; t != null; t = t.parent)
            {
                if (owner.Player)
                {
                    if (Probe.Active != null && Probe.Active.Player == t.gameObject && Matches(t.gameObject, owner, centre, hasCentre)) return true;
                }
                else if (Matches(t.gameObject, owner, centre, hasCentre)) return true;
            }
            return false;
        }

        static bool HasTag(GameObject go, string tag)
        {
            try { return go.CompareTag(tag); }
            catch (UnityException) { return false; }  // a tag the project doesn't define
        }

        /// <summary>has: a component of `go` or its descendants matches every key given.</summary>
        public static bool Carries(GameObject go, HasSel has, Vector3 nearCentre)
        {
            foreach (var c in go.GetComponentsInChildren<Component>(true))
            {
                if (c == null || c is Transform) continue;
                if (has.Component != null && !Reflect.IsA(c.GetType(), has.Component)) continue;
                if (has.Visible && !(c is Renderer r && Drawn(r))) continue;
                if (has.Lit && (LitTest == null || !LitTest(c))) continue;
                if (has.Near != null && !has.Near.Contains(nearCentre, c.transform.position)) continue;
                if (has.Simulating && !Simulates(c)) continue;
                if (has.Movable && c.gameObject.isStatic) continue;
                return true;
            }
            return false;
        }

        // ---------------------------------------------------------------- what an object draws and does

        /// <summary>A renderer that is drawn: enabled, its object active in the hierarchy, not forced off.</summary>
        public static bool Drawn(Renderer r) => r != null && r.enabled && r.gameObject.activeInHierarchy && !r.forceRenderingOff;

        /// <summary>The parts an object draws with: its MeshRenderers that have a mesh with triangles and its
        /// SkinnedMeshRenderers, in itself and its descendants (extent_, spread, changed, lit).</summary>
        public static void MeshParts(GameObject go, List<Renderer> parts, bool inactive = true)
        {
            foreach (var r in go.GetComponentsInChildren<Renderer>(inactive))
            {
                if (r is SkinnedMeshRenderer s) { if (s.sharedMesh != null) parts.Add(r); }
                else if (r is MeshRenderer)
                {
                    var filter = r.GetComponent<MeshFilter>();
                    if (filter != null && filter.sharedMesh != null && filter.sharedMesh.vertexCount > 0) parts.Add(r);
                }
            }
        }

        /// <summary>Whether a component's object simulates physics: a Rigidbody that isn't kinematic, or a Dynamic
        /// Rigidbody2D, on it (a collider by the body it is attached to).</summary>
        public static bool Simulates(Component c)
        {
#if TASKPROBE_PHYSICS
            var body = c as Rigidbody;
            if (body == null) body = c is Collider col ? col.attachedRigidbody : c.GetComponent<Rigidbody>();
            if (body != null && !body.isKinematic) return true;
#endif
#if TASKPROBE_PHYSICS2D
            var body2 = c as Rigidbody2D;
            if (body2 == null) body2 = c is Collider2D col2 ? col2.attachedRigidbody : c.GetComponent<Rigidbody2D>();
            if (body2 != null && body2.bodyType == RigidbodyType2D.Dynamic && body2.simulated) return true;
#endif
            return false;
        }

        /// <summary>Whether anything in the object simulates physics.</summary>
        public static bool Simulates(GameObject go)
        {
#if TASKPROBE_PHYSICS
            foreach (var body in go.GetComponentsInChildren<Rigidbody>(false))
                if (!body.isKinematic) return true;
#endif
#if TASKPROBE_PHYSICS2D
            foreach (var body in go.GetComponentsInChildren<Rigidbody2D>(false))
                if (body.bodyType == RigidbodyType2D.Dynamic && body.simulated) return true;
#endif
            return false;
        }

        /// <summary>The centre of an object: its colliders' bounds centre, else its drawn renderers', else its place.</summary>
        public static Vector3 Centre(GameObject go)
        {
            var have = false;
            var box = new Bounds();
#if TASKPROBE_PHYSICS
            foreach (var c in go.GetComponentsInChildren<Collider>(false))
            {
                if (!c.enabled || c.isTrigger) continue;
                if (have) box.Encapsulate(c.bounds); else { box = c.bounds; have = true; }
            }
#endif
#if TASKPROBE_PHYSICS2D
            if (!have)
                foreach (var c in go.GetComponentsInChildren<Collider2D>(false))
                {
                    if (!c.enabled || c.isTrigger) continue;
                    if (have) box.Encapsulate(c.bounds); else { box = c.bounds; have = true; }
                }
#endif
            if (!have)
                foreach (var r in go.GetComponentsInChildren<Renderer>(false))
                {
                    if (!Drawn(r)) continue;
                    if (have) box.Encapsulate(r.bounds); else { box = r.bounds; have = true; }
                }
            return have ? box.center : go.transform.position;
        }

        // ---------------------------------------------------------------- points

        /// <summary>{"xyz": [x, y, z]}, {"player": true, "offset": [...]}, {"camera": true, "forward": m} or
        /// {"object": &lt;select&gt;, "offset": [...]} (the first match). False when it doesn't resolve now.</summary>
        public static bool Point(Dictionary<string, object> point, out Vector3 at, int depth = 0)
        {
            at = Vector3.zero;
            if (point == null || depth > MaxDepth) return false;
            if (point.TryGetValue("xyz", out var xyz)) return Json.TryVec3(xyz, out at);
            var offset = Vector3.zero;
            if (point.TryGetValue("offset", out var o)) Json.TryVec3(o, out offset);
            var probe = Probe.Active;
            if (Json.Bool(point, "player"))
            {
                var player = probe != null ? probe.Player : null;
                if (player == null) return false;
                at = player.transform.position + offset;
                return true;
            }
            if (Json.Bool(point, "camera"))
            {
                var view = probe != null ? probe.View : null;
                if (view == null) return false;
                at = view.transform.position + view.transform.forward * (float)Json.Num(point, "forward", 0);
                return true;
            }
            var select = Json.Obj(point, "object");
            if (select == null) return false;
            var first = First(Sel.Parse(select), depth + 1);
            if (first == null) return false;
            at = first.transform.position + offset;
            return true;
        }

        // ---------------------------------------------------------------- hierarchy order

        // In a built player every scene root reports sibling index 0, so roots are ordered by their place in the
        // scene's own root list (the same in every play of one build); below a root, by sibling index. Each object's
        // key is made once per sort: comparing transforms pair by pair cost most of a whole-scene sample.
        static readonly Dictionary<int, Dictionary<Transform, int>> RootOrder = new Dictionary<int, Dictionary<Transform, int>>();
        static int rootOrderFrame = -1;

        static int RootIndex(Transform root)
        {
            if (rootOrderFrame != Time.frameCount)
            {
                RootOrder.Clear();
                rootOrderFrame = Time.frameCount;
            }
            var scene = root.gameObject.scene;
            if (!RootOrder.TryGetValue(scene.handle, out var order))
            {
                order = new Dictionary<Transform, int>();
                if (scene.IsValid() && scene.isLoaded)
                {
                    var roots = scene.GetRootGameObjects();
                    for (var i = 0; i < roots.Length; i++) order[roots[i].transform] = i;
                }
                RootOrder[scene.handle] = order;
            }
            return order.TryGetValue(root, out var index) ? index : root.GetSiblingIndex();
        }

        static int[] HierarchyKey(Transform t)
        {
            var depth = 0;
            for (var at = t; at != null; at = at.parent) depth++;
            var key = new int[depth + 2];
            var i = key.Length - 1;
            var here = t;
            for (; here.parent != null; here = here.parent) key[i--] = here.GetSiblingIndex();
            key[i--] = RootIndex(here);
            key[1] = here.gameObject.scene.handle;
            key[0] = here.gameObject.scene.buildIndex;
            return key;
        }

        static int CompareKeys(int[] a, int[] b)
        {
            for (var i = 0; i < a.Length && i < b.Length; i++)
                if (a[i] != b[i]) return a[i].CompareTo(b[i]);
            return a.Length.CompareTo(b.Length);
        }

        /// <summary>Sorts objects into hierarchy order.</summary>
        public static void SortByHierarchy(List<GameObject> objects)
        {
            if (objects.Count < 2) return;
            var keyed = new List<KeyValuePair<int[], GameObject>>(objects.Count);
            foreach (var go in objects) keyed.Add(new KeyValuePair<int[], GameObject>(HierarchyKey(go.transform), go));
            keyed.Sort((x, y) => CompareKeys(x.Key, y.Key));
            for (var i = 0; i < keyed.Count; i++) objects[i] = keyed[i].Value;
        }

        /// <summary>Sorts components into hierarchy order (by their objects; several on one object keep their order).</summary>
        public static void SortByHierarchy<T>(List<T> components) where T : Component
        {
            if (components.Count < 2) return;
            var keyed = new List<KeyValuePair<int[], T>>(components.Count);
            for (var i = 0; i < components.Count; i++)
            {
                var path = HierarchyKey(components[i].transform);
                var key = new int[path.Length + 1];
                path.CopyTo(key, 0);
                key[path.Length] = i;  // the order they came in, among the components of one object
                keyed.Add(new KeyValuePair<int[], T>(key, components[i]));
            }
            keyed.Sort((x, y) =>
            {
                // the last element is the tie-break only: compare the paths first
                int n = x.Key.Length - 1, m = y.Key.Length - 1;
                for (var i = 0; i < n && i < m; i++)
                    if (x.Key[i] != y.Key[i]) return x.Key[i].CompareTo(y.Key[i]);
                return n != m ? n.CompareTo(m) : x.Key[n].CompareTo(y.Key[m]);
            });
            for (var i = 0; i < keyed.Count; i++) components[i] = keyed[i].Value;
        }

        // ---------------------------------------------------------------- angles

        /// <summary>An angle in (-180, 180].</summary>
        public static double Angle(double degrees)
        {
            var a = degrees % 360.0;
            if (a > 180.0) a -= 360.0;
            if (a <= -180.0) a += 360.0;
            return a;
        }
    }
}
