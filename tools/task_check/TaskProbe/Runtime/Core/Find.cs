// Selects and points (contract sections 2 and 3): which objects a select matches, where a point is, whether a place is
// near, and the small readers every kind shares. An object is a GameObject; its parts are the components of itself and
// of its descendants active in the hierarchy. Only objects active in the hierarchy match unless the select says
// "inactive": true (then inactive objects and parts count too). Matches come in hierarchy order (HierarchyKey), so
// "the first match" is the same object in every play of one build.
using System;
using System.Collections.Generic;
using System.Text.RegularExpressions;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.SceneManagement;

namespace TaskProbe
{
    /// <summary>{"point": &lt;Point&gt;, "radius": m, "y_min", "y_max", "y_relative"}.</summary>
    public sealed class NearSel
    {
        public Dictionary<string, object> Point;  // none: a near without a point matches nothing
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

    /// <summary>A select's `has`: a part of the object (a component of it or of a descendant) that matches every key
    /// given. The original's `movable` (a component's Mobility) has no counterpart: Unity keeps no Static flags in a
    /// player, so a `has` that gives it reads it as any key it doesn't know: not at all.</summary>
    public sealed class HasSel
    {
        public string Component;
        public bool Lit, Visible, Simulating;
        public NearSel Near;

        public static HasSel Parse(Dictionary<string, object> has)
        {
            if (has == null) return null;
            return new HasSel
            {
                Component = Sel.Text(has, "component"), Lit = Json.Bool(has, "lit"), Visible = Json.Bool(has, "visible"),
                Simulating = Json.Bool(has, "simulating"), Near = NearSel.Parse(Json.Obj(has, "near")),
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
        internal int LayerAt = -1;  // the layer named Layer (-1: no layer has that name)

        public static Sel Parse(Dictionary<string, object> select)
        {
            var s = new Sel();
            if (select == null) return s;
            s.Component = Text(select, "component");
            s.Tag = Text(select, "tag");
            s.Layer = Text(select, "layer");
            s.Name = Text(select, "name");
            s.Player = Json.Bool(select, "player");
            s.Inactive = Json.Bool(select, "inactive");
            s.Near = NearSel.Parse(Json.Obj(select, "near"));
            s.Has = HasSel.Parse(Json.Obj(select, "has"));
            if (s.Layer != null)
            {
                s.LayerAt = LayerMask.NameToLayer(s.Layer);
                if (s.LayerAt >= 0 && LayerMask.LayerToName(s.LayerAt) != s.Layer) s.LayerAt = -1;  // the name exactly
            }
            return s;
        }

        /// <summary>Parse, and a component type no component can be of (in `component` or `has.component`, here or in a
        /// select inside a point) said once as "&lt;about&gt;: no component type T": a query passes its kind and id.</summary>
        public static Sel Parse(Dictionary<string, object> select, string about)
        {
            if (about != null) Check(select, about, 0);
            return Parse(select);
        }

        static void Check(Dictionary<string, object> select, string about, int depth)
        {
            if (select == null || depth > Find.MaxDepth) return;
            var has = Json.Obj(select, "has");
            foreach (var name in new[] { Text(select, "component"), Text(has, "component") })
                if (name != null && !Reflect.NamesComponent(name)) Probe.Active?.Error(about + ": no component type " + name);
            foreach (var near in new[] { Json.Obj(select, "near"), Json.Obj(has, "near") })
                Check(Json.Obj(Json.Obj(near, "point"), "object"), about, depth + 1);
        }

        /// <summary>A key's text; an empty one is no key (the original's: empty matches everything).</summary>
        internal static string Text(Dictionary<string, object> o, string key)
        {
            var s = Json.Str(o, key);
            return string.IsNullOrEmpty(s) ? null : s;
        }
    }

    public static class Find
    {
        /// <summary>A point deeper than this doesn't resolve (a select inside a point inside a select...; the depth goes
        /// up by one from a select to its points and from a point to its object select): two object selects nest inside
        /// a select's points, the second without a point of its own (the original's limit).</summary>
        public const int MaxDepth = 3;
        static readonly Dictionary<string, Regex> Wildcards = new Dictionary<string, Regex>(StringComparer.Ordinal);
        static readonly Dictionary<string, TagHandle?> Tags = new Dictionary<string, TagHandle?>(StringComparer.Ordinal);

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

        /// <summary>The objects `sel` matches now, in hierarchy order, at most `limit` of them; `total` counts them all.</summary>
        public static List<GameObject> Objects(Sel sel, int limit, out int total, int depth = 0)
        {
            var found = new List<GameObject>();
            Collect(sel, depth, found, true);
            total = found.Count;
            if (found.Count > limit) found.RemoveRange(limit, found.Count - limit);
            return found;
        }

        /// <summary>The first object `sel` matches, or null.</summary>
        public static GameObject First(Sel sel, int depth = 0)
        {
            var found = Objects(sel, 1, out _, depth);
            return found.Count > 0 ? found[0] : null;
        }

        /// <summary>The objects an `owner` select matches now, as a set to test a component's object and its ancestors
        /// against (OwnedBy): the components, pieces, audio and ground selects. Empty when its points don't resolve.</summary>
        public static HashSet<GameObject> Owners(Sel owner)
        {
            var found = new List<GameObject>();
            if (owner != null) Collect(owner, 0, found, false);
            return new HashSet<GameObject>(found);
        }

        /// <summary>Whether `component`'s object, or one of its ancestors, is one of `owners`.</summary>
        public static bool OwnedBy(Component component, HashSet<GameObject> owners)
        {
            for (var t = component.transform; t != null; t = t.parent)
                if (owners.Contains(t.gameObject)) return true;
            return false;
        }

        /// <summary>Whether `component`'s object, or one of its ancestors, matches `owner` (its points resolved: `centre`,
        /// `hasCentre`). Owners and the set's OwnedBy do this once a sample.</summary>
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

        /// <summary>Adds the objects `sel` matches now to `found`, in hierarchy order when `ordered`.</summary>
        static void Collect(Sel sel, int depth, List<GameObject> found, bool ordered)
        {
            var centre = Vector3.zero;
            if (sel.Near != null && !Point(sel.Near.Point, out centre, depth + 1)) return;
            var hasCentre = Vector3.zero;
            if (sel.Has?.Near != null && !Point(sel.Has.Near.Point, out hasCentre, depth + 1)) return;
            if (sel.Player)
            {
                var player = Probe.Active != null ? Probe.Active.Player : null;
                if (player != null && Matches(player, sel, centre, hasCentre)) found.Add(player);
                return;
            }
            var candidates = Candidates(sel);
            // has.lit may render, and a frame allows so many renders: the first in hierarchy order get them, every play
            var lit = sel.Has != null && sel.Has.Lit;
            if (lit) SortByHierarchy(candidates);
            foreach (var go in candidates)
                if (Matches(go, sel, centre, hasCentre)) found.Add(go);
            if (ordered && !lit) SortByHierarchy(found);
        }

        /// <summary>Where a select's matches can be: the objects carrying a component of the type it names (none when no
        /// component can be of that type), else every object; the probe's own left out.</summary>
        static List<GameObject> Candidates(Sel sel)
        {
            var found = new List<GameObject>();
            if (sel.Component != null)
            {
                var components = new List<Component>();
                if (!Components(sel.Component, sel.Inactive, components)) return found;
                var seen = new HashSet<GameObject>();
                foreach (var c in components)
                    if (seen.Add(c.gameObject)) found.Add(c.gameObject);
                return found;
            }
            foreach (var t in UnityEngine.Object.FindObjectsByType<Transform>(
                         sel.Inactive ? FindObjectsInactive.Include : FindObjectsInactive.Exclude, FindObjectsSortMode.None))
                if (t != null && !Probe.IsOwn(t.gameObject)) found.Add(t.gameObject);
            return found;
        }

        /// <summary>Whether `go` matches every key of `sel` (`centre`, `hasCentre`: its near's and its has.near's points,
        /// resolved).</summary>
        public static bool Matches(GameObject go, Sel sel, Vector3 centre, Vector3 hasCentre)
        {
            if (go == null) return false;
            if (!sel.Inactive && !go.activeInHierarchy) return false;
            if (sel.Name != null && !Wild(sel.Name, go.name)) return false;
            if (sel.Tag != null && !HasTag(go, sel.Tag)) return false;
            if (sel.Layer != null && go.layer != sel.LayerAt) return false;
            if (sel.Component != null && Reflect.ComponentNamed(go, sel.Component, false) == null) return false;
            if (sel.Near != null && !sel.Near.Contains(centre, go.transform.position)) return false;
            if (sel.Has != null && !Carries(go, sel.Has, hasCentre, sel.Inactive)) return false;
            return true;
        }

        /// <summary>The components of the loaded scenes (the DontDestroyOnLoad scene too) whose type, a base type or an
        /// interface is named `type` (name or full name), added to `found` in no particular order: on objects active in
        /// the hierarchy, with `inactive` on inactive ones too; the probe's own left out. False when no component can be
        /// of a type of that name (nothing is added).</summary>
        public static bool Components(string type, bool inactive, List<Component> found)
        {
            var searched = new List<Type>();
            foreach (var t in Reflect.TypesNamed(type))
            {
                if (typeof(Component).IsAssignableFrom(t)) Search(searched, t);
                else if (t.IsInterface)
                    foreach (var implementer in Reflect.ComponentsImplementing(t)) Search(searched, implementer);
                else if (t.IsAssignableFrom(typeof(Component))) Search(searched, typeof(Component));  // Object: every component
            }
            if (searched.Count == 0) return false;
            var mode = inactive ? FindObjectsInactive.Include : FindObjectsInactive.Exclude;
            var seen = searched.Count > 1 ? new HashSet<int>() : null;  // two searches can find one component twice
            foreach (var search in searched)
                foreach (var o in UnityEngine.Object.FindObjectsByType(search, mode, FindObjectsSortMode.None))
                    if (o is Component c && c != null && !IsOwn(c) && Reflect.IsA(c.GetType(), type) && (seen == null || seen.Add(c.GetInstanceID())))
                        found.Add(c);
            return true;
        }

        static void Search(List<Type> searched, Type type)
        {
            if (!searched.Contains(type)) searched.Add(type);
        }

        /// <summary>A component of the probe's own: on its object, or the tap it puts on the game's AudioListener.</summary>
        public static bool IsOwn(Component c)
        {
#if TASKPROBE_AUDIO
            if (c is AudioTap) return true;
#endif
            return Probe.IsOwn(c.gameObject);
        }

        /// <summary>A tag the project doesn't define has no object. Whether it is defined is asked once per tag, through a
        /// TagHandle: CompareTag(string) with such a tag returns false and writes "Tag: T is not defined." into the game's
        /// log at every call (measured: 2,295 lines in a play of 2 s), which a task's log_absent would read.</summary>
        static bool HasTag(GameObject go, string tag)
        {
            if (!Tags.TryGetValue(tag, out var handle))
            {
                try { handle = TagHandle.GetExistingTag(tag); }
                catch (Exception) { handle = null; }
                Tags[tag] = handle;
            }
            return handle.HasValue && go.CompareTag(handle.Value);
        }

        /// <summary>has: a part of `go` (a component of it or of a descendant active in the hierarchy; with `inactive` of
        /// any descendant) that matches every key given, the original's order: `lit` last, as it may render.</summary>
        static bool Carries(GameObject go, HasSel has, Vector3 nearCentre, bool inactive)
        {
            foreach (var c in go.GetComponentsInChildren<Component>(inactive))
            {
                if (c == null || IsOwn(c)) continue;
                if (has.Component != null && !Reflect.IsA(c.GetType(), has.Component)) continue;
                if (has.Near != null && !has.Near.Contains(nearCentre, c.transform.position)) continue;
                if (has.Visible && !(c is Renderer r && Drawn(r))) continue;
                if (has.Simulating && !Simulates(c)) continue;  // as the simulating field reads it: one a player can shove
                if (has.Lit && !Glow.Of(c).Lit) continue;  // as the components lit field reads it
                return true;
            }
            return false;
        }

        // ---------------------------------------------------------------- what an object draws and does

        /// <summary>A renderer that is drawn: enabled, its object active in the hierarchy, not forced off.</summary>
        public static bool Drawn(Renderer r) => r != null && r.enabled && r.gameObject.activeInHierarchy && !r.forceRenderingOff;

        /// <summary>The mesh a component draws or collides with: a MeshRenderer's (its MeshFilter's), a
        /// SkinnedMeshRenderer's, a MeshFilter's or a MeshCollider's; null for any other component or when it has none.</summary>
        public static Mesh MeshOf(Component c)
        {
            switch (c)
            {
                case SkinnedMeshRenderer skinned: return skinned.sharedMesh;
                case MeshRenderer _: return c.TryGetComponent<MeshFilter>(out var filter) ? filter.sharedMesh : null;
                case MeshFilter f: return f.sharedMesh;
#if TASKPROBE_PHYSICS
                case MeshCollider m: return m.sharedMesh;
#endif
            }
            return null;
        }

        /// <summary>Whether a component's object simulates physics: a Rigidbody that isn't kinematic, or a simulated
        /// Dynamic Rigidbody2D, on it (a collider by the body it is attached to), active in the hierarchy (an inactive
        /// body simulates nothing).</summary>
        public static bool Simulates(Component c)
        {
#if TASKPROBE_PHYSICS
            var body = c as Rigidbody;
            if (body == null) body = c is Collider col ? col.attachedRigidbody : c.GetComponent<Rigidbody>();
            if (body != null && !body.isKinematic && body.gameObject.activeInHierarchy) return true;
#endif
#if TASKPROBE_PHYSICS2D
            var body2 = c as Rigidbody2D;
            if (body2 == null) body2 = c is Collider2D col2 ? col2.attachedRigidbody : c.GetComponent<Rigidbody2D>();
            if (body2 != null && body2.bodyType == RigidbodyType2D.Dynamic && body2.simulated && body2.gameObject.activeInHierarchy) return true;
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

        /// <summary>An enabled collider that isn't a trigger (3D or 2D) on `go`, or with `descendants` on it or one of
        /// its descendants active in the hierarchy (collision, mesh_collision).</summary>
        public static bool Collides(GameObject go, bool descendants)
        {
#if TASKPROBE_PHYSICS
            foreach (var c in descendants ? go.GetComponentsInChildren<Collider>(false) : go.GetComponents<Collider>())
                if (c.enabled && !c.isTrigger) return true;
#endif
#if TASKPROBE_PHYSICS2D
            foreach (var c in descendants ? go.GetComponentsInChildren<Collider2D>(false) : go.GetComponents<Collider2D>())
                if (c.enabled && !c.isTrigger) return true;
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

        /// <summary>A Light that lights the scene: enabled, active in the hierarchy, of an intensity above 0 (lit, glow,
        /// on, light, grading's sun).</summary>
        public static bool LightOn(Light light) => light != null && light.enabled && light.gameObject.activeInHierarchy && light.intensity > 0f;

        /// <summary>The colour a Light lights with, its intensity left out: its colour in the space lighting is done in,
        /// times its colour temperature's when the light and the project use temperatures (alpha 1). Glow and the light
        /// measure take it, so a lamp's glow and its share of light agree on its colour.</summary>
        public static Color LightColour(Light light)
        {
            var c = Linear(light.color);
            if (light.useColorTemperature && GraphicsSettings.lightsUseColorTemperature) c *= Mathf.CorrelatedColorTemperatureToRGB(light.colorTemperature);
            c.a = 1f;
            return c;
        }

        /// <summary>Rec. 709 luminance of a linear colour (glow, screen, drawn; the light measure weighs as URP does).</summary>
        public static double Luminance(double r, double g, double b) => 0.2126 * r + 0.7152 * g + 0.0722 * b;

        /// <summary>A colour as the colour picker holds it, in the space shaders and lighting get it: linear in a
        /// linear-space project.</summary>
        public static Color Linear(Color c) => QualitySettings.activeColorSpace == ColorSpace.Linear ? c.linear : c;

        // ---------------------------------------------------------------- points

        /// <summary>{"xyz": [x, y, z]}, {"player": true, "offset": [...]}, {"camera": true, "forward": m} or
        /// {"object": &lt;select&gt;, "offset": [...]} (the first match), tried in that order. False when it doesn't
        /// resolve now, or lies deeper than MaxDepth.</summary>
        public static bool Point(Dictionary<string, object> point, out Vector3 at, int depth = 0)
        {
            at = Vector3.zero;
            if (point == null || depth > MaxDepth) return false;
            var offset = Vector3.zero;
            if (point.TryGetValue("offset", out var o)) Json.TryVec3(o, out offset);
            if (point.TryGetValue("xyz", out var xyz) && Json.TryVec3(xyz, out at)) return true;
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

        // Hierarchy order is the order the Hierarchy window lists a playing game in: the scenes in the order they were
        // loaded (SceneManager's list), the DontDestroyOnLoad scene last; in a scene, its roots in the order of its root
        // list, and below a root by sibling index. A player keeps no sibling order for roots (every root reports index
        // 0), so a scene's roots come in the player's own root list, the same in every play of one build: the player
        // makes it from the scene file as it loads it, not from the editor's Hierarchy. Each object's key is made once
        // per sort: comparing transforms pair by pair cost most of a whole-scene sample. The lists are read once per pass
        // (Probe.Stamp): a search an input makes before the game's scripts never serves the samples taken after them,
        // which may have made a root.
        static readonly Dictionary<int, Dictionary<Transform, int>> RootOrder = new Dictionary<int, Dictionary<Transform, int>>();
        static readonly Dictionary<int, int> SceneOrder = new Dictionary<int, int>();
        static int orderStamp = -1;

        static void Fresh()
        {
            if (orderStamp == Probe.Stamp) return;
            orderStamp = Probe.Stamp;
            RootOrder.Clear();
            SceneOrder.Clear();
            for (var i = 0; i < SceneManager.sceneCount; i++) SceneOrder[SceneManager.GetSceneAt(i).handle] = i;
        }

        // the DontDestroyOnLoad scene is in no place of SceneManager's list: last
        static int ScenePlace(Scene scene) => SceneOrder.TryGetValue(scene.handle, out var at) ? at : int.MaxValue;

        static int RootIndex(Transform root)
        {
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
            return order.TryGetValue(root, out var index) ? index : int.MaxValue;
        }

        static int[] HierarchyKey(Transform t)
        {
            var depth = 0;
            for (var at = t; at != null; at = at.parent) depth++;
            var key = new int[depth + 1];
            var i = key.Length - 1;
            var here = t;
            for (; here.parent != null; here = here.parent) key[i--] = here.GetSiblingIndex();
            key[1] = RootIndex(here);
            key[0] = ScenePlace(here.gameObject.scene);
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
            Fresh();
            var keyed = new List<KeyValuePair<int[], GameObject>>(objects.Count);
            foreach (var go in objects) keyed.Add(new KeyValuePair<int[], GameObject>(HierarchyKey(go.transform), go));
            keyed.Sort((x, y) => CompareKeys(x.Key, y.Key));
            for (var i = 0; i < keyed.Count; i++) objects[i] = keyed[i].Value;
        }

        /// <summary>Sorts components into hierarchy order: by their objects, several on one object in the Inspector's
        /// order.</summary>
        public static void SortByHierarchy<T>(List<T> components) where T : Component
        {
            if (components.Count < 2) return;
            Fresh();
            var keyed = new List<KeyValuePair<int[], T>>(components.Count);
            var on = new List<Component>();
            foreach (var c in components)
            {
                var path = HierarchyKey(c.transform);
                var key = new int[path.Length + 1];
                path.CopyTo(key, 0);
                c.GetComponents(on);
                key[path.Length] = on.IndexOf(c);
                keyed.Add(new KeyValuePair<int[], T>(key, c));
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
