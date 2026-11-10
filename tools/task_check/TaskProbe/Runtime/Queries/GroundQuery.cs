// ground: the lie of the land (contract section 3, "ground"): a ray straight down from 2000 m up meets the first
// collider that isn't a trigger nor the player's (the Ignore Raycast layer aside); with `select`, only colliders of the
// objects it matches (or of their descendants) are ground, the rest traced through. A 3D ray: 2D colliders are never
// met. Without the Physics module there is no collider: nothing is met, and the query says so once in query_errors.
// `xz` [x, z] -> "value": {"height" (null when nothing was met), "hit"};
// `box` [x0, z0, x1, z1] + `grid` (2-32, default 8; corners and edges included) -> "value": {"min", "max", "mean",
// "range" (null with no hit), "hits", "points"}; null with neither.
using System;
using System.Collections.Generic;
using UnityEngine;

namespace TaskProbe
{
    [ProbeQuery("ground")]
    public sealed class GroundQuery : Query
    {
        const float Top = 2000f;
        double[] xz, box;
        int grid = 8;
        Sel sel;
        HashSet<GameObject> ground;

        public override void Load()
        {
#if !TASKPROBE_PHYSICS
            Probe.Error(Kind + " " + Id + ": the project has no Physics module: no ground is read");
#endif
            if (Numbers("box", 4, out var b))
            {
                box = new[] { Math.Min(b[0], b[2]), Math.Min(b[1], b[3]), Math.Max(b[0], b[2]), Math.Max(b[1], b[3]) };
                grid = (int)Math.Min(Math.Max(Math.Floor(Json.Num(Def, "grid", 8) + 0.5), 2), 32);
            }
            else if (Numbers("xz", 2, out var p)) xz = p;
            else Probe.Error(Kind + " " + Id + ": a ground query takes xz [x, z] or box [x0, z0, x1, z1] (null values)");
            var s = Json.Obj(Def, "select");
            if (s != null) sel = Sel.Parse(s, Kind + " " + Id);
        }

        /// <summary>Def[key] as exactly `count` numbers.</summary>
        bool Numbers(string key, int count, out double[] numbers)
        {
            numbers = null;
            return Def.TryGetValue(key, out var v) && v is List<object> list && list.Count == count && Json.TryNumbers(list, count, out numbers);
        }

        public override void Sample(double t, Dictionary<string, object> sample)
        {
            sample["value"] = null;
            if (xz == null && box == null) return;
            ground = sel != null ? Find.Owners(sel) : null;
            var player = Probe.Player;
            if (box == null)
            {
                var hit = Down((float)xz[0], (float)xz[1], player, out var y);
                sample["value"] = new Dictionary<string, object>(StringComparer.Ordinal)
                {
                    ["height"] = hit ? (object)(double)y : null, ["hit"] = hit ? 1.0 : 0.0,
                };
                return;
            }
            // the box on a grid x grid lattice, its corners and edges included
            var hits = 0;
            double min = 0, max = 0, sum = 0;
            for (var i = 0; i < grid; i++)
                for (var j = 0; j < grid; j++)
                {
                    var x = box[0] + (box[2] - box[0]) * i / (grid - 1);
                    var z = box[1] + (box[3] - box[1]) * j / (grid - 1);
                    if (!Down((float)x, (float)z, player, out var y)) continue;
                    min = hits > 0 ? Math.Min(min, y) : y;
                    max = hits > 0 ? Math.Max(max, y) : y;
                    sum += y;
                    hits++;
                }
            sample["value"] = new Dictionary<string, object>(StringComparer.Ordinal)
            {
                ["min"] = hits > 0 ? (object)min : null, ["max"] = hits > 0 ? (object)max : null,
                ["mean"] = hits > 0 ? (object)(sum / hits) : null, ["range"] = hits > 0 ? (object)(max - min) : null,
                ["hits"] = (double)hits, ["points"] = (double)(grid * grid),
            };
        }

#if TASKPROBE_PHYSICS
        RaycastHit[] buffer = new RaycastHit[64];
#endif

        /// <summary>The y where the ray at (x, z) first meets ground.</summary>
        bool Down(float x, float z, GameObject player, out float y)
        {
            y = 0f;
#if TASKPROBE_PHYSICS
            var n = Physics.RaycastNonAlloc(new Vector3(x, Top, z), Vector3.down, buffer, 2f * Top, Physics.DefaultRaycastLayers, QueryTriggerInteraction.Ignore);
            while (n == buffer.Length)
            {
                buffer = new RaycastHit[buffer.Length * 2];
                n = Physics.RaycastNonAlloc(new Vector3(x, Top, z), Vector3.down, buffer, 2f * Top, Physics.DefaultRaycastLayers, QueryTriggerInteraction.Ignore);
            }
            var best = float.PositiveInfinity;
            for (var i = 0; i < n; i++)
            {
                var h = buffer[i];
                if (h.distance >= best) continue;
                var tr = h.collider.transform;
                if (player != null && tr.IsChildOf(player.transform)) continue;
                if (ground != null && !IsGround(tr)) continue;
                best = h.distance;
                y = h.point.y;
            }
            return !float.IsPositiveInfinity(best);
#else
            return false;
#endif
        }

        bool IsGround(Transform t)
        {
            for (; t != null; t = t.parent)
                if (ground.Contains(t.gameObject)) return true;
            return false;
        }
    }
}
