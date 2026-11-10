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

        /// <summary>Every frame of the play, its clock running or held by a wait (spin, spawns). `dt`: 1/30 s.</summary>
        public virtual void Frame(float dt) { }

        /// <summary>One sample at play time `t`: fill `sample` ("t" is set): "rows" (with RowSet) or "value".</summary>
        public abstract void Sample(double t, Dictionary<string, object> sample);

        public virtual FrameNeed Needs => FrameNeed.None;

        /// <summary>For a query whose Needs isn't None: the frame drawn right after its sample; complete `sample`.</summary>
        public virtual void FrameDrawn(FrameImage frame, Dictionary<string, object> sample) { }

        protected bool Reads(string field) => Fields.Contains(field);
    }

    /// <summary>A frame as displayed: `Pixels` row by row from the bottom (Unity's order), sRGB-encoded 8 bit.</summary>
    public sealed class FrameImage
    {
        public int Width, Height;
        public Color32[] Pixels;

        /// <summary>The pixel at column x, row y counted from the top.</summary>
        public Color32 At(int x, int yFromTop) => Pixels[(Height - 1 - yFromTop) * Width + x];
    }

    /// <summary>The rows of one selection sample: at most 200 kept, every match counted, and each field's numeric values
    /// summed up over every match, so a count, a sum, a min or a max reads them all (contract section 5: "total",
    /// "full").</summary>
    public sealed class RowSet
    {
        public const int MaxRows = 200;

        sealed class Full
        {
            public int N, Nonzero;
            public double Sum, Min = double.PositiveInfinity, Max = double.NegativeInfinity;
        }

        readonly List<object> rows = new List<object>();
        readonly Dictionary<string, Full> full = new Dictionary<string, Full>(StringComparer.Ordinal);
        readonly List<string> fields;
        int total;

        public RowSet(IEnumerable<string> fields) { this.fields = new List<string>(fields); }

        public int Total => total;
        /// <summary>Whether another row would still be kept (a query may skip costly fields past the cap only if it
        /// still adds the row's numbers: pass every match to Add).</summary>
        public bool Keeps => rows.Count < MaxRows;

        /// <summary>One match: counted, kept while under the cap, its fields' numbers (bools as 0/1) summed up.</summary>
        public void Add(Dictionary<string, object> row)
        {
            total++;
            foreach (var field in fields)
            {
                if (!row.TryGetValue(field, out var v)) continue;
                double number;
                if (v is double d) number = d;
                else if (v is bool b) number = b ? 1.0 : 0.0;
                else if (v is float f) number = f;
                else if (v is int i) number = i;
                else continue;
                if (double.IsNaN(number) || double.IsInfinity(number)) continue;
                if (!full.TryGetValue(field, out var sum)) full[field] = sum = new Full();
                sum.N++;
                if (number != 0.0) sum.Nonzero++;
                sum.Sum += number;
                if (number < sum.Min) sum.Min = number;
                if (number > sum.Max) sum.Max = number;
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
