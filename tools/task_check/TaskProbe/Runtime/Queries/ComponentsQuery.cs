// components: components a component select matches, one row each (contract section 3, "components"), so effects and
// parts that are not objects of their own count too.
// select: component (a type name: the type, its base types and interfaces match), effect (true: live effects only),
// name (wildcard on its object's name), owner (an object select its object or an ancestor matches), near (its
// transform's place), mesh (wildcard on a renderer's, filter's or mesh collider's mesh asset name), visible (true:
// drawn only), inactive (true: components of inactive objects too; default only active ones, as an object select).
// rows: {"name" (its object's), "class" (its type), "owner" (its object's name), <fields>...} (+ "glow_sources",
// "glow_read" with lit or glow, for logs).
using System;
using System.Collections.Generic;
using UnityEngine;

namespace TaskProbe
{
    [ProbeQuery("components")]
    public sealed class ComponentsQuery : Query
    {
        string type;
        bool effect, visibleOnly, inactive, broken, change, glow;
        string name, mesh;
        Sel owner;
        NearSel near;
        readonly Places places = new Places();
        readonly Spins spins = new Spins();
        readonly Changes changes = new Changes();
        readonly List<Component> found = new List<Component>();
        readonly List<Component> matched = new List<Component>();

        static readonly HashSet<string> Plain = new HashSet<string>(StringComparer.Ordinal)
        {
            "count", "active", "visible", "x", "y", "z", "speed", "spin", "extent_x", "extent_y", "extent_z", "simulating",
            "changed", "bounds_change", "pose_change", "lit", "glow", "intensity", "on",
        };

        public override void Load()
        {
            KnownFields(Plain, "prop:");
            var s = Json.Obj(Def, "select") ?? new Dictionary<string, object>();
            type = Json.Str(s, "component");
            effect = Json.Bool(s, "effect");
            visibleOnly = Json.Bool(s, "visible");
            inactive = Json.Bool(s, "inactive");
            name = Json.Str(s, "name");
            mesh = Json.Str(s, "mesh");
            var o = Json.Obj(s, "owner");
            if (o != null) owner = Sel.Parse(o, Kind + " " + Id);
            near = NearSel.Parse(Json.Obj(s, "near"));
            change = Fields.Exists(Changes.IsField);
            glow = Reads("lit") || Reads("glow");
#if !TASKPROBE_PHYSICS && !TASKPROBE_PHYSICS2D
            // as every kind says what the project lacks: simulating keeps its value (0) without a physics module
            if (Reads("simulating")) Probe.Error(Kind + " " + Id + ": the project has no Physics module: simulating reads 0");
#endif
            if (type != null && !Reflect.NamesComponent(type))
            {
                Probe.Error(Kind + " " + Id + ": no component type " + type);
                broken = true;
            }
            else if (type == null && !effect)
            {
                Probe.Error(Kind + " " + Id + ": the select names no component and no effect");
                broken = true;
            }
        }

        public override void Frame(float dt)
        {
            spins.Frame(dt);
            places.Frame(dt);
        }

        public override void Sample(double t, Dictionary<string, object> sample)
        {
            var rows = new RowSet(Fields);
            places.Begin();
            if (!broken) Match();
            foreach (var c in matched) rows.Add(Row(c));
            matched.Clear();
            places.End();
            spins.EndSample();
            changes.EndSample();
            rows.WriteTo(sample);
        }

        void Match()
        {
            var centre = Vector3.zero;
            if (near != null && !near.Resolve(out centre)) return;
            var owners = owner != null ? Find.Owners(owner) : null;
            found.Clear();
            if (type != null) Find.Components(type, inactive, found);
            else
                foreach (var t in Effects.Types())
                    foreach (var o in UnityEngine.Object.FindObjectsByType(t, inactive ? FindObjectsInactive.Include : FindObjectsInactive.Exclude, FindObjectsSortMode.None))
                        if (o is Component c && c != null && !Find.IsOwn(c)) found.Add(c);
            foreach (var c in found)
            {
                var go = c.gameObject;
                if (name != null && !Find.Wild(name, go.name)) continue;
                if (near != null && !near.Contains(centre, c.transform.position)) continue;
                if (mesh != null && !Find.Wild(mesh, MeshName(c))) continue;
                if (visibleOnly && !Visible(c)) continue;
                if (effect && !Effects.Live(c)) continue;
                if (owners != null && !Find.OwnedBy(c, owners)) continue;
                matched.Add(c);
            }
            found.Clear();
            Find.SortByHierarchy(matched);
        }

        /// <summary>The name of the mesh a component draws or collides with; null without one (a mesh destroyed while a
        /// renderer still holds it is null too: Unity's ==, not ?., which would throw on it).</summary>
        static string MeshName(Component c)
        {
            var m = Find.MeshOf(c);
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
            if (c is ParticleSystem) return Effects.Live(c);
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
            // changed, bounds_change, pose_change: a renderer against the first sample this query saw it in
            var changed = renderer != null && change ? changes.Part(renderer) : default;
            // lit, glow: a light, a part or an effect as a source; no value for any other component
            var shines = glow ? Glow.Of(c) : default;
            var speedRead = false;
            double? speed = null;
            foreach (var f in Fields)
            {
                object v = null;
                switch (f)
                {
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
                        if (renderer != null) v = changed.Field(f);
                        break;
                    case "lit":
                    case "glow":
                        v = shines.Field(f);
                        break;
                    case "intensity":
                        if (light != null) v = (double)light.intensity;
                        break;
                    case "on":
                        if (light != null) v = Find.LightOn(light) ? 1.0 : 0.0;
                        break;
                    default:
                        v = Reflect.Prop(c, f.Substring(5));
                        break;
                }
                if (v != null) row[f] = v;
            }
            if (glow) shines.Note(row);
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
