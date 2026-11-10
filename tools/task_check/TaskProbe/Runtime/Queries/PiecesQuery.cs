// pieces: placed mesh pieces, whatever form the scene holds them in (contract section 3, "pieces"): a MeshRenderer or a
// SkinnedMeshRenderer whose mesh has triangles is 1, a Terrain's tree instances are 1 each. Under a
// LODGroup only LOD 0's renderers count. Renderers of objects active in the hierarchy only (a deactivated object is
// no placed piece; a disabled renderer is a piece that isn't drawn). Counted over every piece, never cut at a cap.
// Unity has no instanced or procedural mesh component (the original's instances and sections): a mesh drawn from code
// (Graphics.RenderMesh*) is no piece, a mesh built at run time is an ordinary one, its submeshes one piece.
// select: component (MeshRenderer, SkinnedMeshRenderer, Terrain, Renderer...), name (wildcard on its object's name),
// mesh (wildcard on its mesh asset's name; a tree's: its prototype's first mesh), owner (an object select its object
// or an ancestor matches), near (each piece by its own place: a renderer's transform, a tree instance's position).
// "value": {"count", "visible", "components", "objects", "triangles", "visible_triangles"} | null when near doesn't
// resolve or no component can be of the select's type.
using System;
using System.Collections.Generic;
using UnityEngine;

namespace TaskProbe
{
    [ProbeQuery("pieces")]
    public sealed class PiecesQuery : Query
    {
        string component, name, mesh;
        bool unknown;
        Sel owner;
        NearSel near;
        readonly Dictionary<int, long> triangles = new Dictionary<int, long>();  // this sample's meshes, read once each

        public override void Load()
        {
            var s = Json.Obj(Def, "select");
            component = Sel.Text(s, "component");
            name = Sel.Text(s, "name");
            mesh = Sel.Text(s, "mesh");
            var o = Json.Obj(s, "owner");
            if (o != null) owner = Sel.Parse(o, Kind + " " + Id);
            near = NearSel.Parse(Json.Obj(s, "near"));
            if (component != null && !Reflect.NamesComponent(component))
            {
                Probe.Error(Kind + " " + Id + ": no component type " + component);
                unknown = true;
            }
        }

        /// <summary>Index count / 3 over a mesh's triangle submeshes (an index count needs no read access).</summary>
        long TrianglesOf(Mesh m)
        {
            if (m == null) return 0;
            var id = m.GetInstanceID();
            if (triangles.TryGetValue(id, out var n)) return n;
            n = 0;
            for (var i = 0; i < m.subMeshCount; i++)
                if (m.GetTopology(i) == MeshTopology.Triangles) n += (long)m.GetIndexCount(i) / 3;
            return triangles[id] = n;
        }

        public override void Sample(double t, Dictionary<string, object> sample)
        {
            sample["value"] = null;
            if (unknown) return;
            var centre = Vector3.zero;
            if (near != null && !near.Resolve(out centre)) return;
            var owners = owner != null ? Find.Owners(owner) : null;
            triangles.Clear();

            // renderers of LOD 1 and on that aren't in LOD 0 too
            var lower = new HashSet<int>();
            foreach (var group in UnityEngine.Object.FindObjectsByType<LODGroup>(FindObjectsInactive.Exclude, FindObjectsSortMode.None))
            {
                var lods = group.GetLODs();
                if (lods.Length < 2) continue;
                var first = new HashSet<int>();
                foreach (var r in lods[0].renderers)
                    if (r != null) first.Add(r.GetInstanceID());
                for (var i = 1; i < lods.Length; i++)
                    foreach (var r in lods[i].renderers)
                        if (r != null && !first.Contains(r.GetInstanceID())) lower.Add(r.GetInstanceID());
            }

            long count = 0, visible = 0, tris = 0, visibleTris = 0;
            var components = 0;
            var objects = new HashSet<int>();
            foreach (var r in UnityEngine.Object.FindObjectsByType<Renderer>(FindObjectsInactive.Exclude, FindObjectsSortMode.None))
            {
                if (!(r is MeshRenderer) && !(r is SkinnedMeshRenderer)) continue;
                var m = Find.MeshOf(r);
                if (m == null || lower.Contains(r.GetInstanceID()) || Probe.IsOwn(r.gameObject)) continue;
                var each = TrianglesOf(m);
                if (each == 0) continue;  // a mesh with no triangles (lines, points) is no piece
                if (!Keep(r, m.name, owners)) continue;
                if (near != null && !near.Contains(centre, r.transform.position)) continue;
                count++;
                tris += each;
                if (Find.Drawn(r)) { visible++; visibleTris += each; }
                components++;
                objects.Add(r.gameObject.GetInstanceID());
            }
#if TASKPROBE_TERRAIN
            foreach (var terrain in UnityEngine.Object.FindObjectsByType<Terrain>(FindObjectsInactive.Exclude, FindObjectsSortMode.None))
            {
                var data = terrain.terrainData;
                if (data == null || data.treeInstanceCount == 0 || Probe.IsOwn(terrain.gameObject)) continue;
                var prototypes = data.treePrototypes;
                var protoTris = new long[prototypes.Length];
                var protoMesh = new string[prototypes.Length];
                for (var i = 0; i < prototypes.Length; i++) protoTris[i] = PrefabTriangles(prototypes[i].prefab, out protoMesh[i]);
                var drawn = terrain.enabled && terrain.drawTreesAndFoliage;
                var origin = terrain.transform.position;
                var size = data.size;
                long n = 0, nt = 0;
                foreach (var tree in data.treeInstances)
                {
                    var p = tree.prototypeIndex;
                    if (p < 0 || p >= prototypes.Length) continue;
                    if (!Keep(terrain, protoMesh[p], owners)) continue;
                    if (near != null && !near.Contains(centre, origin + Vector3.Scale(tree.position, size))) continue;
                    n++;
                    nt += protoTris[p];
                }
                if (n == 0) continue;
                count += n;
                tris += nt;
                if (drawn) { visible += n; visibleTris += nt; }
                components++;
                objects.Add(terrain.gameObject.GetInstanceID());
            }
#endif
            sample["value"] = new Dictionary<string, object>(StringComparer.Ordinal)
            {
                ["count"] = (double)count, ["visible"] = (double)visible, ["components"] = (double)components,
                ["objects"] = (double)objects.Count, ["triangles"] = (double)tris, ["visible_triangles"] = (double)visibleTris,
            };
        }

        /// <summary>The select's keys but near (each piece by its own place).</summary>
        bool Keep(Component c, string meshName, HashSet<GameObject> owners)
        {
            if (component != null && !Reflect.IsA(c.GetType(), component)) return false;
            if (name != null && !Find.Wild(name, c.gameObject.name)) return false;
            if (mesh != null && !Find.Wild(mesh, meshName)) return false;
            if (owners != null && !Find.OwnedBy(c, owners)) return false;
            return true;
        }

        /// <summary>The triangles a tree prototype's prefab draws at full detail (LOD 0 under a LODGroup, else every mesh
        /// renderer in it), and its first mesh's name.</summary>
        long PrefabTriangles(GameObject prefab, out string meshName)
        {
            meshName = null;
            if (prefab == null) return 0;
            var renderers = new List<Renderer>();
            if (prefab.TryGetComponent<LODGroup>(out var group) && group.lodCount > 0)
                renderers.AddRange(group.GetLODs()[0].renderers);
            else
                renderers.AddRange(prefab.GetComponentsInChildren<Renderer>(true));
            long n = 0;
            foreach (var r in renderers)
            {
                if (!(r is MeshRenderer) && !(r is SkinnedMeshRenderer)) continue;
                var m = Find.MeshOf(r);
                if (m == null) continue;
                meshName ??= m.name;
                n += TrianglesOf(m);
            }
            return n;
        }
    }
}
