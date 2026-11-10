// screen: the mean brightness of the frame as displayed, over a rect (contract section 3). The frame is the one drawn
// right after the sample, after post-processing, with the UI on it.
// "value": {"luminance", "luma", "pixels", "size": [w, h]} | null when no frame was read.
using System;
using System.Collections.Generic;
using UnityEngine;

namespace TaskProbe
{
    [ProbeQuery("screen")]
    public sealed class ScreenQuery : Query
    {
        static readonly double[] Linear = BuildLinear();
        double x0, y0 = 0.0, x1 = 1.0, y1 = 1.0;

        static double[] BuildLinear()
        {
            var table = new double[256];
            for (var i = 0; i < 256; i++)
            {
                var v = i / 255.0;
                table[i] = v <= 0.04045 ? v / 12.92 : Math.Pow((v + 0.055) / 1.055, 2.4);
            }
            return table;
        }

        public override void Load()
        {
            if (Def.TryGetValue("rect", out var rect) && Json.TryNumbers(rect, 4, out var r))
            {
                x0 = r[0]; y0 = r[1]; x1 = r[2]; y1 = r[3];
            }
        }

        public override FrameNeed Needs => FrameNeed.Pixels;

        public override void Sample(double t, Dictionary<string, object> sample)
        {
            sample["value"] = null;  // filled in when the frame has been drawn
        }

        public override void FrameDrawn(FrameImage frame, Dictionary<string, object> sample)
        {
            if (frame == null) return;
            // the rect is in viewport fractions, y down from the top
            var left = Mathf.Clamp((int)Math.Floor(x0 * frame.Width), 0, frame.Width);
            var right = Mathf.Clamp((int)Math.Ceiling(x1 * frame.Width), 0, frame.Width);
            var top = Mathf.Clamp((int)Math.Floor(y0 * frame.Height), 0, frame.Height);
            var bottom = Mathf.Clamp((int)Math.Ceiling(y1 * frame.Height), 0, frame.Height);
            long count = 0;
            double luminance = 0.0, luma = 0.0;
            for (var y = top; y < bottom; y++)
            {
                var row = (frame.Height - 1 - y) * frame.Width;
                for (var x = left; x < right; x++)
                {
                    var p = frame.Pixels[row + x];
                    luminance += 0.2126 * Linear[p.r] + 0.7152 * Linear[p.g] + 0.0722 * Linear[p.b];
                    luma += (0.2126 * p.r + 0.7152 * p.g + 0.0722 * p.b) / 255.0;
                    count++;
                }
            }
            if (count == 0) return;
            sample["value"] = new Dictionary<string, object>(StringComparer.Ordinal)
            {
                ["luminance"] = luminance / count, ["luma"] = luma / count, ["pixels"] = (double)count,
                ["size"] = new List<object> { (double)frame.Width, (double)frame.Height },
            };
        }
    }
}
