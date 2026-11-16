// world: the game's time as a whole (contract section 3, docs/task-probes.md 2.21): a hit stop slows or stops the
// game's time for a few frames, which a sample every 0.1 s can fall between, so the lowest Time.timeScale of every
// frame since the previous sample is kept. The play's clock runs on whatever the game sets.
// "value": {"time_scale" (the lowest since the previous sample, this frame's included), "paused" (1 when it was 0 in
// any of them)}.
using System;
using System.Collections.Generic;
using UnityEngine;

namespace TaskProbe
{
    [ProbeQuery("world")]
    public sealed class WorldQuery : Query
    {
        static readonly string[] Known = { "time_scale", "paused" };

        double lowest = -1.0;  // since the previous sample (-1: no frame yet)

        public override void Load() => KnownFields(Known);

        public override void Frame(float dt) => Note();

        void Note()
        {
            double scale = Time.timeScale;
            lowest = lowest < 0.0 ? scale : Math.Min(lowest, scale);
        }

        public override void Sample(double t, Dictionary<string, object> sample)
        {
            Note();
            sample["value"] = new Dictionary<string, object>(StringComparer.Ordinal)
            {
                ["time_scale"] = lowest,
                ["paused"] = lowest <= 0.0 ? 1.0 : 0.0,
            };
            lowest = -1.0;
        }
    }
}
