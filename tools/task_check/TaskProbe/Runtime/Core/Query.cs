// A query: one of the checker's measures, sampled with the track. One class per kind under Runtime/Queries, marked
// [ProbeQuery("kind")] and found by reflection, so adding a kind touches no other file.
using System;
using System.Collections.Generic;
using UnityEngine;

namespace TaskProbe
{
    [AttributeUsage(AttributeTargets.Class)]
    public sealed class ProbeQueryAttribute : Attribute
    {
        public readonly string Kind;
        public ProbeQueryAttribute(string kind) { Kind = kind; }
    }

    /// <summary>What a query needs of the frame drawn right after a sample.</summary>
    public enum FrameNeed
    {
        None,    // the sample is complete when Sample returns
        Drawn,   // FrameDrawn is called once that frame has been drawn (frame is null unless another query asked for pixels)
        Pixels   // FrameDrawn gets the frame's pixels
    }

    public abstract class Query
    {
        public string Id;
        public string Kind;
        /// <summary>The query as the checker wrote it (contract section 5): its select, point, rect and so on.</summary>
        public Dictionary<string, object> Def;
        /// <summary>The fields the task's probes read of it (empty for a count).</summary>
        public List<string> Fields = new List<string>();
        public Probe Probe;

        /// <summary>Once, after Def and Fields are set: parse the select. Report a bad definition with Probe.Error.</summary>
        public virtual void Load() { }

        /// <summary>Every frame of the play, its clock running or held (a wait, a scene loading) (spin, spawns). `dt`: 1/30 s.</summary>
        public virtual void Frame(float dt) { }

        /// <summary>One sample at play time `t`: fill `sample` ("t" is set): "rows" (with RowSet) or "value".</summary>
        public abstract void Sample(double t, Dictionary<string, object> sample);

        public virtual FrameNeed Needs => FrameNeed.None;

        /// <summary>For a query whose Needs isn't None: the frame drawn right after its sample; complete `sample`.</summary>
        public virtual void FrameDrawn(FrameImage frame, Dictionary<string, object> sample) { }

        protected bool Reads(string field) => Fields.Contains(field);

        /// <summary>Leaves out the fields this kind doesn't have (one of `plain`, or a prefix with a name after it), each
        /// said once as "&lt;kind&gt; &lt;id&gt;: no field F".</summary>
        protected void KnownFields(ICollection<string> plain, params string[] prefixes)
        {
            Fields.RemoveAll(f =>
            {
                if (plain.Contains(f)) return false;
                foreach (var p in prefixes)
                    if (f.Length > p.Length && f.StartsWith(p, StringComparison.Ordinal)) return false;
                Probe.Error(Kind + " " + Id + ": no field " + f);
                return true;
            });
        }
    }

    /// <summary>A frame as displayed: `Pixels` row by row from the bottom (Unity's order), sRGB-encoded 8 bit.</summary>
    public sealed class FrameImage
    {
        public int Width, Height;
        public Color32[] Pixels;

        /// <summary>The pixel at column x, row y counted from the top.</summary>
        public Color32 At(int x, int yFromTop) => Pixels[(Height - 1 - yFromTop) * Width + x];

        /// <summary>The pixels a rect [x0, y0, x1, y1] in viewport fractions (y down) covers: columns x0..x1-1 and rows
        /// y0..y1-1 from the top, its corners in either order, clamped to the frame and at least one pixel.</summary>
        public void Area(double[] rect, out int x0, out int y0, out int x1, out int y1)
        {
            x0 = Clamp(Math.Floor(Math.Min(rect[0], rect[2]) * Width), 0, Width - 1);
            y0 = Clamp(Math.Floor(Math.Min(rect[1], rect[3]) * Height), 0, Height - 1);
            x1 = Clamp(Math.Ceiling(Math.Max(rect[0], rect[2]) * Width), x0 + 1, Width);
            y1 = Clamp(Math.Ceiling(Math.Max(rect[1], rect[3]) * Height), y0 + 1, Height);
        }

        static int Clamp(double v, int lo, int hi) => !(v > lo) ? lo : v > hi ? hi : (int)v;  // NaN: lo
    }

    /// <summary>The rows of one selection sample: at most 200 kept, every match counted, and each field's numbers summed
    /// up over every match, so a count, a sum, a min or a max reads them all ("total" and "full", written when more
    /// matched than the rows hold: every field asked for, in the order asked).</summary>
    public sealed class RowSet
    {
        public const int MaxRows = 200;

        /// <summary>Every match's number of one field (n: how many have one).</summary>
        sealed class Full
        {
            public int N, Nonzero;
            public double Sum, Min, Max;
        }

        readonly List<object> rows = new List<object>();
        readonly List<KeyValuePair<string, Full>> full = new List<KeyValuePair<string, Full>>();
        int total;

        public RowSet(IEnumerable<string> fields)
        {
            foreach (var field in fields) full.Add(new KeyValuePair<string, Full>(field, new Full()));
        }

        /// <summary>One match: counted, kept while under the cap, its fields' numbers summed up (a field with no value,
        /// or a string, counts in the rows only; numbers are doubles, booleans 1.0 and 0.0).</summary>
        public void Add(Dictionary<string, object> row)
        {
            total++;
            foreach (var kv in full)
            {
                if (!row.TryGetValue(kv.Key, out var v) || !(v is double x) || double.IsNaN(x) || double.IsInfinity(x)) continue;
                var f = kv.Value;
                f.Min = f.N > 0 ? Math.Min(f.Min, x) : x;
                f.Max = f.N > 0 ? Math.Max(f.Max, x) : x;
                f.Sum += x;
                if (x != 0.0) f.Nonzero++;
                f.N++;
            }
            if (rows.Count < MaxRows) rows.Add(row);
        }

        public void WriteTo(Dictionary<string, object> sample)
        {
            sample["rows"] = rows;
            if (total <= rows.Count) return;
            sample["total"] = (double)total;
            var summed = new Dictionary<string, object>(StringComparer.Ordinal);
            foreach (var kv in full)
                summed[kv.Key] = new Dictionary<string, object>(StringComparer.Ordinal)
                {
                    ["n"] = (double)kv.Value.N, ["nonzero"] = (double)kv.Value.Nonzero, ["sum"] = kv.Value.Sum,
                    ["min"] = kv.Value.N > 0 ? kv.Value.Min : (object)null, ["max"] = kv.Value.N > 0 ? kv.Value.Max : (object)null,
                };
            sample["full"] = summed;
        }
    }
}
