// render: what the renderer drew (contract section 3, docs/task-probes.md 2.20): the engine's own counts of a frame,
// read through its profiler counters ("Draw Calls Count", "Triangles Count": the Render category, counted in a release
// player too), the highest over the frames since the previous sample, so a heavy frame between two samples is read
// too; and the texture memory in use at the sample. The counts are the whole frame's: the UI's draws, and whatever the
// probe itself rendered in it (a drawn, lit or glow reading), which is why a play that reads them takes none of those
// (tools/validate-game.py render_errors).
// "value": {"draw_calls", "triangles" (null before any frame was counted, or when the player has no such counter),
// "texture_mb" (Texture.currentTextureMemory, MiB)}.
using System;
using System.Collections.Generic;
using Unity.Profiling;
using UnityEngine;

namespace TaskProbe
{
    [ProbeQuery("render")]
    public sealed class RenderQuery : Query
    {
        static readonly string[] Known = { "draw_calls", "triangles", "texture_mb" };

        ProfilerRecorder drawCalls, triangles;
        long maxDrawCalls = -1, maxTriangles = -1;  // since the previous sample (-1: no frame yet)

        public override void Load()
        {
            KnownFields(Known);
            drawCalls = ProfilerRecorder.StartNew(ProfilerCategory.Render, "Draw Calls Count");
            triangles = ProfilerRecorder.StartNew(ProfilerCategory.Render, "Triangles Count");
            if (!drawCalls.Valid || !triangles.Valid) Probe.Error("render " + Id + ": the player has no draw call or triangle counter: no value");
        }

        public override void Frame(float dt)
        {
            // the counts of the last frame the renderer finished
            if (drawCalls.Valid && drawCalls.Count > 0) maxDrawCalls = Math.Max(maxDrawCalls, drawCalls.LastValue);
            if (triangles.Valid && triangles.Count > 0) maxTriangles = Math.Max(maxTriangles, triangles.LastValue);
        }

        public override void Sample(double t, Dictionary<string, object> sample)
        {
            sample["value"] = new Dictionary<string, object>(StringComparer.Ordinal)
            {
                ["draw_calls"] = maxDrawCalls < 0 ? null : (object)(double)maxDrawCalls,
                ["triangles"] = maxTriangles < 0 ? null : (object)(double)maxTriangles,
                ["texture_mb"] = Texture.currentTextureMemory / (1024.0 * 1024.0),
            };
            maxDrawCalls = maxTriangles = -1;
        }
    }
}
