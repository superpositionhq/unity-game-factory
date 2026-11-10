// The editor pass's `scene` / `prefab` measures: the objects of a scene or prefab as saved that an object select
// matches, one row (or one per renderer slot, one per mesh object) each. The select is the runtime's (Sel, Find.Matches)
// with what needs a running game left out: `player`, `has`, and points other than `xyz` or another object of the same
// scene. A select using them gives an error, not an empty match, so a task can't pass on a select that can't work here.
using System;
using System.Collections.Generic;
using UnityEngine;

namespace TaskProbe.EditorTools
{
    public static class SceneRows
    {
        /// <summary>{"rows": [{"name", "value"}]} or {"error"} of a measure over `objects` (the scene's or prefab's, in
        /// hierarchy order, inactive ones included).</summary>
        public static Dictionary<string, object> Measure(Dictionary<string, object> m, List<GameObject> objects)
        {
            var field = Json.Str(m, "field") ?? "";
            if (!(field == "count" || field == "material_default" || field == "mesh_collision"
                  || field.StartsWith("material:", StringComparison.Ordinal) || field.StartsWith("prop:", StringComparison.Ordinal)))
                return AssetPass.Error("unknown field " + field + " (count, material_default, material:<property>, mesh_collision, prop:<Component>.<path>)");
            var sel = Sel.Parse(Json.Obj(m, "select"));
            var matched = Select(sel, objects, 0, out var why);
            if (why != null) return AssetPass.Error(why);
            var rows = new List<object>();
            foreach (var go in matched) AddRows(go, field, rows);
            return new Dictionary<string, object>(StringComparer.Ordinal) { ["rows"] = rows };
        }

        /// <summary>The objects `sel` matches, in hierarchy order; `why` says why the select can't be used here.</summary>
        static List<GameObject> Select(Sel sel, List<GameObject> objects, int depth, out string why)
        {
            var found = new List<GameObject>();
            why = null;
            if (sel.Player) { why = "`player` selects need a running game: the editor pass can't match them"; return found; }
            if (sel.Has != null) { why = "`has` needs a running game: the editor pass can't match it"; return found; }
            var centre = Vector3.zero;
            if (sel.Near != null && !Point(sel.Near.Point, objects, depth + 1, out centre, out why))
                return found;  // why is set, or the point's object isn't there (nothing is near it)
            foreach (var go in objects)
                if (Find.Matches(go, sel, centre, Vector3.zero)) found.Add(go);
            return found;
        }

        /// <summary>A near's point in the saved scene: {"xyz"} or {"object": select, "offset"} (its first match).</summary>
        static bool Point(Dictionary<string, object> point, List<GameObject> objects, int depth, out Vector3 at, out string why)
        {
            at = Vector3.zero;
            why = null;
            // counted as a play counts it (Find.Point): one for the point, one for its object's select
            if (depth > Find.MaxDepth) { why = "the select nests too deep"; return false; }
            if (point == null) { why = "a `near` without a point"; return false; }
            if (point.TryGetValue("xyz", out var xyz))
            {
                if (Json.TryVec3(xyz, out at)) return true;
                why = "a point's xyz isn't three numbers";
                return false;
            }
            var select = Json.Obj(point, "object");
            if (select == null)
            {
                why = "a `near` point on the player or the camera needs a running game: use {\"xyz\": [x, y, z]}";
                return false;
            }
            var first = Select(Sel.Parse(select), objects, depth + 1, out why);
            if (why != null || first.Count == 0) return false;
            var offset = Vector3.zero;
            if (point.TryGetValue("offset", out var o)) Json.TryVec3(o, out offset);
            at = first[0].transform.position + offset;
            return true;
        }

        /// <summary>`go`'s rows of `field` (a known one).</summary>
        static void AddRows(GameObject go, string field, List<object> rows)
        {
            if (field == "count") rows.Add(Row(go.name, 1.0));
            else if (field == "material_default")
            {
                var bad = false;
                foreach (var r in go.GetComponentsInChildren<Renderer>(true))
                {
                    var slots = r.sharedMaterials;
                    // a part of the mesh beyond the last slot is drawn with no material: the original's empty slot
                    if (slots.Length == 0 || slots.Length < Parts(r)) bad = true;
                    foreach (var s in slots)
                        if (s == null || AssetValues.IsErrorShader(s.shader) || AssetValues.IsDefault(s)) bad = true;
                    if (bad) break;
                }
                rows.Add(Row(go.name, bad ? 1.0 : 0.0));
            }
            else if (field.StartsWith("material:", StringComparison.Ordinal))
            {
                var spec = field.Substring(9);
                foreach (var r in go.GetComponentsInChildren<Renderer>(true))
                    foreach (var s in r.sharedMaterials)
                        rows.Add(Row(go.name + "/" + r.gameObject.name, s != null ? AssetValues.MaterialValue(s, spec, out _) : null));
            }
            else if (field == "mesh_collision")
            {
                foreach (var filter in go.GetComponentsInChildren<MeshFilter>(true))
                {
                    if (filter.sharedMesh == null) continue;
                    var has = false;
                    for (var t = filter.transform; t != null && !has; t = t == go.transform ? null : t.parent)
                        has = Find.Collides(t.gameObject, false);
                    rows.Add(Row(go.name + "/" + filter.gameObject.name, has ? 1.0 : 0.0));
                }
            }
            else
            {
                var value = AssetValues.ObjectProp(go, field.Substring(5), out var ok);
                rows.Add(Row(go.name, ok ? value : null));
            }
        }

        /// <summary>How many parts (submeshes) a renderer's mesh has; the slot of each part's index draws it.</summary>
        static int Parts(Renderer r)
        {
            Mesh mesh = null;
            if (r is SkinnedMeshRenderer skinned) mesh = skinned.sharedMesh;
            else if (r is MeshRenderer)
            {
                var filter = r.GetComponent<MeshFilter>();
                if (filter != null) mesh = filter.sharedMesh;
            }
            return mesh != null ? mesh.subMeshCount : 0;
        }

        static Dictionary<string, object> Row(string name, object value) =>
            new Dictionary<string, object>(StringComparer.Ordinal) { ["name"] = name, ["value"] = value };
    }
}
