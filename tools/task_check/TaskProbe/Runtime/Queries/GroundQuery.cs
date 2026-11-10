// ground: the lie of the land (contract section 3, "ground"): a ray straight down from 2000 m up meets the first
// collider that isn't a trigger nor the player's; with `select`, only colliders of the objects it matches (or of their
// descendants) are ground, the rest traced through.
// `xz` [x, z] -> "value": {"height" (null when nothing was met), "hit"};
// `box` [x0, z0, x1, z1] + `grid` (2-32, default 8; corners and edges included) -> "value": {"min", "max", "mean",
// "range" (null with no hit), "hits", "points"}.
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
        readonly HashSet<int> ground = new HashSet<int>();

        public override void Load()
        {
            if (Def.TryGetValue("box", out var b) && Json.TryNumbers(b, 4, out var nb)) box = nb;
            else if (Def.TryGetValue("xz", out var p) && Json.TryNumbers(p, 2, out var np)) xz = np;
            else Probe.Error("ground: neither xz [x, z] nor box [x0, z0, x1, z1]");
            grid = (int)Math.Min(Math.Max(Json.Num(Def, "grid", 8), 2), 32);
            var s = Json.Obj(Def, "select");
            if (s != null) sel = Sel.Parse(s);
        }

        public override void Sample(double t, Dictionary<string, object> sample)
        {
            sample["value"] = null;
#if TASKPROBE_PHYSICS
            if (xz == null && box == null) return;
            ground.Clear();
            if (sel != null)
                foreach (var go in Find.Objects(sel, int.MaxValue, out _)) ground.Add(go.GetInstanceID());
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
#endif
        }

#if TASKPROBE_PHYSICS
        RaycastHit[] buffer = new RaycastHit[64];

        bool Down(float x, float z, GameObject player, out float y)
        {
            y = 0f;
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
                if (sel != null && !IsGround(tr)) continue;
                best = h.distance;
                y = h.point.y;
            }
            return !float.IsPositiveInfinity(best);
        }

        bool IsGround(Transform t)
        {
            for (; t != null; t = t.parent)
                if (ground.Contains(t.gameObject.GetInstanceID())) return true;
            return false;
        }
#endif
    }
}
