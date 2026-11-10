// objects: GameObjects an object select matches, one row each (contract section 3, "objects"). Every match is read and
// summed up in the sample; the first 200 are kept as rows.
// rows: {"name", "class", <fields>...} (+ "glow_sources", "glow_read" with lit or glow, for logs).
using System;
using System.Collections.Generic;
using UnityEngine;

namespace TaskProbe
{
    [ProbeQuery("objects")]
    public sealed class ObjectsQuery : Query
    {
        Sel sel;
        readonly Places places = new Places();
        readonly Spins spins = new Spins();
        readonly Changes changes = new Changes();
        readonly List<Renderer> parts = new List<Renderer>();
        bool change, glow, withParts;

        static readonly HashSet<string> Plain = new HashSet<string>(StringComparer.Ordinal)
        {
            "count", "x", "y", "z", "yaw", "pitch", "roll", "scale", "extent_x", "extent_y", "extent_z", "active", "hidden",
            "collision", "speed", "spin", "simulating", "spread", "changed", "bounds_change", "pose_change", "lit", "glow",
            "facing_vs_velocity", "clip",
        };
        static readonly string[] Prefixes = { "prop:", "bone:", "anim:", "forward:", "rel_yaw:", "world_yaw:", "world_pitch:", "world_roll:" };

        public override void Load()
        {
            KnownFields(Plain, Prefixes);
            sel = Sel.Parse(Json.Obj(Def, "select"), Kind + " " + Id);
            change = Fields.Exists(Changes.IsField);
            glow = Reads("lit") || Reads("glow");
            withParts = change || glow || Reads("spin") || Reads("spread") || Fields.Exists(f => f.StartsWith("extent_", StringComparison.Ordinal));
#if !TASKPROBE_PHYSICS && !TASKPROBE_PHYSICS2D
            Lacks("Physics", " read 0", " reads 0", Fields.FindAll(f => f == "collision" || f == "simulating"));
#endif
#if !TASKPROBE_ANIMATION
            Lacks("Animation", " have no value", " has no value", Fields.FindAll(f => f == "clip" || f.StartsWith("anim:", StringComparison.Ordinal)));
#endif
        }

        /// <summary>A field read through a module the project doesn't have keeps its value without it; the query says so
        /// once, as every kind says what the project lacks.</summary>
        void Lacks(string module, string many, string one, List<string> fields)
        {
            if (fields.Count == 0) return;
            Probe.Error(Kind + " " + Id + ": the project has no " + module + " module: " + string.Join(" and ", fields) + (fields.Count > 1 ? many : one));
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
            foreach (var go in Find.Objects(sel, int.MaxValue, out _))
                rows.Add(Row(go));
            places.End();
            spins.EndSample();
            if (change) changes.EndSample();
            rows.WriteTo(sample);
        }

        Dictionary<string, object> Row(GameObject go)
        {
            var row = new Dictionary<string, object>(StringComparer.Ordinal) { ["name"] = go.name, ["class"] = ObjectRead.ClassOf(go) };
            if (withParts) ObjectRead.Parts(go, parts);
            // changed, bounds_change, pose_change: against the first sample this query saw the object in
            var c = change ? changes.Object(go, parts) : default;
            // lit, glow: over its lights, parts and effects
            var light = glow ? Glow.OfObject(go, parts) : default;
            Vector3 velocity = Vector3.zero;
            double? speed = null;
            var speedRead = false;
            foreach (var f in Fields)
            {
                object v;
                if (Changes.IsField(f)) v = c.Field(f);
                else if (f == "lit" || f == "glow") v = light.Field(f);
                else if (f == "speed" || f == "facing_vs_velocity")
                {
                    if (!speedRead)
                    {
                        var own = ObjectRead.OwnVelocity(go, out var ownV);
                        speed = places.Speed(go.GetInstanceID(), go.transform.position, own, ownV, out velocity);
                        speedRead = true;
                    }
                    if (f == "speed") v = speed;
                    else v = speed.HasValue && velocity.magnitude >= 0.1f ? (object)(double)Vector3.Angle(go.transform.forward, velocity) : null;
                }
                else v = Field(go, f);
                if (v != null) row[f] = v;
            }
            if (glow) light.Note(row);
            return row;
        }

        object Field(GameObject go, string f)
        {
            var tr = go.transform;
            switch (f)
            {
                case "count": return 1.0;
                case "x": return (double)tr.position.x;
                case "y": return (double)tr.position.y;
                case "z": return (double)tr.position.z;
                case "yaw": return Find.Angle(tr.eulerAngles.y);
                case "pitch": return Find.Angle(tr.eulerAngles.x);
                case "roll": return Find.Angle(tr.eulerAngles.z);
                case "scale":
                {
                    var s = tr.lossyScale;
                    return (Math.Abs(s.x) + Math.Abs(s.y) + Math.Abs(s.z)) / 3.0;
                }
                case "extent_x":
                case "extent_y":
                case "extent_z":
                    if (!ObjectRead.DrawnBox(parts, out var box)) return null;  // it draws nothing
                    return ObjectRead.Axis(box.extents, f.Substring(7));
                case "active": return go.activeInHierarchy ? 1.0 : 0.0;
                case "hidden": return ObjectRead.Hidden(go) ? 1.0 : 0.0;
                // an inactive object collides with nothing (Find.Collides finds its own colliders even then)
                case "collision": return go.activeInHierarchy && Find.Collides(go, true) ? 1.0 : 0.0;
                case "simulating": return go.activeInHierarchy && Find.Simulates(go) ? 1.0 : 0.0;
                case "spread": return ObjectRead.Spread(parts);
                case "spin": return Spin(go);
                case "clip": return ObjectRead.Clip(go);
            }
            var colon = f.IndexOf(':');
            if (colon > 0)
            {
                var head = f.Substring(0, colon);
                var rest = f.Substring(colon + 1);
                switch (head)
                {
                    case "prop": return Reflect.Prop(go, rest);
                    case "bone": return ObjectRead.Bone(go, rest);
                    case "anim": return ObjectRead.AnimParameter(go, rest);
                    case "forward": return ObjectRead.Forward(go, rest);
                    case "rel_yaw":
                    {
                        var part = Reflect.Part(go, rest);
                        return part != null ? (object)Find.Angle(part.eulerAngles.y - tr.eulerAngles.y) : null;
                    }
                    case "world_yaw":
                    case "world_pitch":
                    case "world_roll":
                    {
                        // the part's own rotation in the world, whether its object or the part itself turned
                        var part = Reflect.Part(go, rest);
                        if (part == null) return null;
                        var e = part.eulerAngles;
                        return Find.Angle(head == "world_yaw" ? e.y : head == "world_pitch" ? e.x : e.z);
                    }
                }
            }
            return null;
        }

        /// <summary>The fastest of its parts (as changed takes them); with none, its own transform.</summary>
        object Spin(GameObject go)
        {
            if (parts.Count == 0) return spins.Of(go.transform);
            double? best = null;
            foreach (var r in parts)
            {
                var v = spins.Of(r.transform);
                if (v.HasValue && (!best.HasValue || v.Value > best.Value)) best = v;
            }
            return best;
        }
    }
}
