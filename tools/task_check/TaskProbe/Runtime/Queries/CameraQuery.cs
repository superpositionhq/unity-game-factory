// camera: the player's camera against the player (contract section 3, "camera"). The checker reads occluded and
// player_on_screen from here; distance, height, pitch, yaw and fov it computes from the probe's camera and track rows
// (probes.series), and they are here too, as in the original.
// "value": {"pitch", "yaw", "fov", "distance", "height", "occluded", "player_on_screen"} (the player's fields null
// without a player) | null without a camera.
using System;
using System.Collections.Generic;
using UnityEngine;

namespace TaskProbe
{
    [ProbeQuery("camera")]
    public sealed class CameraQuery : Query
    {
        static readonly string[] Plain = { "distance", "height", "pitch", "yaw", "fov", "occluded", "player_on_screen" };

        public override void Load()
        {
            KnownFields(Plain);
#if !TASKPROBE_PHYSICS
            if (Fields.Count == 0 || Reads("occluded")) Probe.Error(Kind + " " + Id + ": the project has no Physics module: occluded reads 0");
#endif
        }

        public override void Sample(double t, Dictionary<string, object> sample)
        {
            var view = Probe.View;
            if (view == null) { sample["value"] = null; return; }
            var at = view.transform.position;
            var e = view.transform.eulerAngles;
            var value = new Dictionary<string, object>(StringComparer.Ordinal)
            {
                ["pitch"] = Find.Angle(e.x), ["yaw"] = Find.Angle(e.y), ["fov"] = view.orthographic ? 0.0 : (double)view.fieldOfView,
                ["distance"] = null, ["height"] = null, ["occluded"] = null, ["player_on_screen"] = null,
            };
            sample["value"] = value;
            var player = Probe.Player;
            if (player == null) return;
            var p = player.transform.position;
            // the player's centre: its colliders' bounds centre, else its drawn renderers', else its place
            var centre = Find.Centre(player);
            value["distance"] = (double)Vector3.Distance(at, p);
            value["height"] = (double)(at.y - p.y);
            value["occluded"] = Occluded(view, player, at, centre) ? 1.0 : 0.0;
            var vp = view.WorldToViewportPoint(centre);
            value["player_on_screen"] = vp.z > 0f && vp.x >= 0f && vp.x <= 1f && vp.y >= 0f && vp.y <= 1f ? 1.0 : 0.0;
        }

        /// <summary>A collider between the camera and the player's centre that is neither the player's nor the camera's
        /// own (triggers and the Ignore Raycast layer aside). Without the physics module there is no collider.</summary>
        static bool Occluded(Camera view, GameObject player, Vector3 from, Vector3 to)
        {
#if TASKPROBE_PHYSICS
            var d = to - from;
            var length = d.magnitude;
            if (length < 1e-4f) return false;
            foreach (var hit in Physics.RaycastAll(from, d / length, length, Physics.DefaultRaycastLayers, QueryTriggerInteraction.Ignore))
            {
                var c = hit.collider.transform;
                if (c.IsChildOf(player.transform) || c.IsChildOf(view.transform)) continue;
                return true;
            }
#endif
            return false;
        }
    }
}
