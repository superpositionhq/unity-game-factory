// components: components a component select matches, one row each (contract section 3, "components"), so effects and
// parts that are not objects of their own count too.
// select: component (type name), effect (true: live effects only), name (wildcard on its object's name), owner (an
// object select its object or an ancestor matches), near (its transform's place), mesh (wildcard on a renderer's,
// filter's or mesh collider's mesh asset name), visible (true: drawn only), inactive (true: components of inactive
// objects too; default only active ones, as an object select).
// rows: {"name" (its object's), "class" (its type), "owner" (its object's name), <fields>...}.
using System;
using System.Collections.Generic;
using UnityEngine;

namespace TaskProbe
{
    [ProbeQuery("components")]
    public sealed class ComponentsQuery : Query
    {
        Type type;
        bool effect, visibleOnly, inactive, broken;
        string name, mesh;
        Sel owner;
        NearSel near;
        readonly Places places = new Places();
        readonly Spins spins = new Spins();
        readonly Changes changes = new Changes();
        readonly HashSet<int> seen = new HashSet<int>();
        readonly List<Component> matched = new List<Component>();

        static readonly HashSet<string> Plain = new HashSet<string>(StringComparer.Ordinal)
        {
            "count", "active", "visible", "x", "y", "z", "speed", "spin", "extent_x", "extent_y", "extent_z", "simulating",
            "changed", "bounds_change", "pose_change", "lit", "glow", "intensity", "on",
        };

        public override void Load()
        {
            Fields.RemoveAll(f =>
            {
                if (Plain.Contains(f) || (f.StartsWith("prop:", StringComparison.Ordinal) && f.Length > 5)) return false;
                Probe.Error("components: no field " + f);
                return true;
            });
            var s = Json.Obj(Def, "select") ?? new Dictionary<string, object>();
            var typeName = Json.Str(s, "component");
            effect = Json.Bool(s, "effect");
            visibleOnly = Json.Bool(s, "visible");
            inactive = Json.Bool(s, "inactive");
            name = Json.Str(s, "name");
            mesh = Json.Str(s, "mesh");
            var o = Json.Obj(s, "owner");
            if (o != null) owner = Sel.Parse(o);
            near = NearSel.Parse(Json.Obj(s, "near"));
            if (typeName != null)
            {
                type = Reflect.TypeNamed(typeName);
                if (type == null || !typeof(Component).IsAssignableFrom(type))
                {
                    Probe.Error("components: no component type " + typeName);
                    broken = true;
                }
            }
            else if (!effect)
            {
                Probe.Error("components: the select names no component and no effect");
                broken = true;
            }
        }

        public override void Frame(float dt) => spins.Frame(dt);

        public override void Sample(double t, Dictionary<string, object> sample)
        {
            var rows = new RowSet(Fields);
            places.Begin(t);
            if (!broken) Match();
            foreach (var c in matched) rows.Add(Row(c));
            matched.Clear();
            places.End();
            spins.EndSample();
            rows.WriteTo(sample);
        }

        void Match()
        {
            var centre = Vector3.zero;
            if (near != null && !near.Resolve(out centre)) return;
            Vector3 ownerCentre = Vector3.zero, ownerHas = Vector3.zero;
            if (owner != null)
            {
                if (owner.Near != null && !Find.Point(owner.Near.Point, out ownerCentre, 1)) return;
                if (owner.Has?.Near != null && !Find.Point(owner.Has.Near.Point, out ownerHas, 1)) return;
            }
            seen.Clear();
            var mode = inactive ? FindObjectsInactive.Include : FindObjectsInactive.Exclude;
            foreach (var t in type != null ? new[] { type } : new List<Type>(Effects.Types()).ToArray())
                foreach (var o in UnityEngine.Object.FindObjectsByType(t, mode, FindObjectsSortMode.None))
                {
                    if (!(o is Component c) || c == null || !seen.Add(c.GetInstanceID())) continue;
                    var go = c.gameObject;
                    if (Probe.IsOwn(go)) continue;
                    if (name != null && !Find.Wild(name, go.name)) continue;
                    if (near != null && !near.Contains(centre, c.transform.position)) continue;
                    if (mesh != null && !Find.Wild(mesh, MeshName(c))) continue;
                    if (visibleOnly && !Visible(c)) continue;
                    if (effect && !Effects.Live(c)) continue;
                    if (owner != null && !Find.OwnedBy(c, owner, ownerCentre, ownerHas)) continue;
                    matched.Add(c);
                }
            Find.SortByHierarchy(matched);
        }

        /// <summary>The name of the mesh asset a component draws or collides with; null when it has none.</summary>
        public static string MeshName(Component c)
        {
            Mesh m = null;
            if (c is SkinnedMeshRenderer smr) m = smr.sharedMesh;
            else if (c is MeshRenderer && c.TryGetComponent<MeshFilter>(out var filter)) m = filter.sharedMesh;
            else if (c is MeshFilter f) m = f.sharedMesh;
#if TASKPROBE_PHYSICS
            else if (c is MeshCollider mc) m = mc.sharedMesh;
#endif
            return m != null ? m.name : null;
        }

        /// <summary>visible: a Renderer drawn; any other component, its object active.</summary>
        static bool Visible(Component c) => c is Renderer r ? Find.Drawn(r) : c.gameObject.activeInHierarchy;

        /// <summary>active: enabled and active in the hierarchy; a ParticleSystem also playing or holding particles, an
        /// AudioSource also playing.</summary>
        static bool Active(Component c)
        {
            if (!c.gameObject.activeInHierarchy) return false;
#if TASKPROBE_PARTICLES
            if (c is ParticleSystem ps) return ps.isPlaying || ps.particleCount > 0;
#endif
#if TASKPROBE_AUDIO
            if (c is AudioSource audio) return audio.enabled && audio.isPlaying;
#endif
            if (c is Behaviour b) return b.enabled;
            if (c is Renderer r) return r.enabled;
#if TASKPROBE_PHYSICS
            if (c is Collider col) return col.enabled;
#endif
#if TASKPROBE_PHYSICS2D
            if (c is Collider2D col2) return col2.enabled;
#endif
            return true;
        }

        Dictionary<string, object> Row(Component c)
        {
            var go = c.gameObject;
            var row = new Dictionary<string, object>(StringComparer.Ordinal)
            {
                ["name"] = go.name, ["class"] = c.GetType().Name, ["owner"] = go.name,
            };
            var renderer = c as Renderer;
            var light = c as Light;
            if (Reads("lit") || Reads("glow")) Glow.Of(c).Fill(row, Reads("lit"), Reads("glow"));
            Changes.Reading change = default;
            if (renderer != null && Fields.Exists(Changes.IsField)) change = changes.Part(renderer);
            var speedRead = false;
            double? speed = null;
            foreach (var f in Fields)
            {
                object v = null;
                switch (f)
                {
                    case "lit":
                    case "glow":
                        continue;
                    case "count": v = 1.0; break;
                    case "active": v = Active(c) ? 1.0 : 0.0; break;
                    case "visible": v = Visible(c) ? 1.0 : 0.0; break;
                    case "x": v = (double)c.transform.position.x; break;
                    case "y": v = (double)c.transform.position.y; break;
                    case "z": v = (double)c.transform.position.z; break;
                    case "speed":
                        if (!speedRead)
                        {
                            var own = ObjectRead.OwnVelocity(go, out var ownV);
                            speed = places.Speed(c.GetInstanceID(), c.transform.position, own, ownV, out _);
                            speedRead = true;
                        }
                        v = speed;
                        break;
                    case "spin": v = spins.Of(c.transform); break;
                    case "extent_x":
                    case "extent_y":
                    case "extent_z":
                        if (Extent(c, out var e)) v = ObjectRead.Axis(e, f.Substring(7));
                        break;
                    case "simulating": v = go.activeInHierarchy && Find.Simulates(c) ? 1.0 : 0.0; break;
                    case "changed":
                    case "bounds_change":
                    case "pose_change":
                        if (renderer != null) v = change.Field(f);
                        break;
                    case "intensity":
                        if (light != null) v = (double)light.intensity;
                        break;
                    case "on":
                        if (light != null) v = Glow.LightOn(light) ? 1.0 : 0.0;
                        break;
                    default:
                        v = Reflect.Prop(c, f.Substring(5));
                        break;
                }
                if (v != null) row[f] = v;
            }
            return row;
        }

        /// <summary>A Renderer's or Collider's world bounds half-size.</summary>
        static bool Extent(Component c, out Vector3 e)
        {
            e = Vector3.zero;
            if (c is Renderer r) { e = r.bounds.extents; return true; }
#if TASKPROBE_PHYSICS
            if (c is Collider col) { e = col.bounds.extents; return true; }
#endif
#if TASKPROBE_PHYSICS2D
            if (c is Collider2D col2) { e = col2.bounds.extents; return true; }
#endif
            return false;
        }
    }
}
