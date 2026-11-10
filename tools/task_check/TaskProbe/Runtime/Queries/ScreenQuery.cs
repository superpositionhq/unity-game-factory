// screen: the mean brightness of the frame as displayed, over a rect (contract section 3): the frame drawn right after
// the sample, after post-processing and tone mapping, with the UI on it. The original reads its viewport before the
// UMG and Slate UI is drawn over it; URP draws the overlay UI in a pass of its own at the end of the last camera's
// render, and the probe reads the frame as displayed, after that pass (reading it before would take a pass of the
// probe's own in the game's renderer).
// "value": {"luminance" (mean linear Rec. 709 luminance of the displayed pixels, sRGB decoded, 0-1), "luma" (mean
// Rec. 709 luma of the encoded values, 0-1), "pixels", "size": [w, h]} | null when no frame was drawn (the play ended
// first).
using System;
using System.Collections.Generic;

namespace TaskProbe
{
    [ProbeQuery("screen")]
    public sealed class ScreenQuery : Query
    {
        static readonly double[] Linear = SrgbToLinear();
        readonly double[] rect = { 0.0, 0.0, 1.0, 1.0 };  // [x0, y0, x1, y1] in viewport fractions, y down

        /// <summary>Each 8-bit sRGB value as linear light, 0-1.</summary>
        static double[] SrgbToLinear()
        {
            var table = new double[256];
            for (var i = 0; i < 256; i++)
            {
                var c = i / 255.0;
                table[i] = c <= 0.04045 ? c / 12.92 : Math.Pow((c + 0.055) / 1.055, 2.4);
            }
            return table;
        }

        public override void Load()
        {
            // rect: [x0, y0, x1, y1] in viewport fractions (default the whole frame)
            if (Def.TryGetValue("rect", out var r) && r is List<object> numbers && numbers.Count == 4)
                for (var i = 0; i < 4; i++)
                    if (numbers[i] is double v) rect[i] = Math.Min(Math.Max(v, 0.0), 1.0);
        }

        public override FrameNeed Needs => FrameNeed.Pixels;

        public override void Sample(double t, Dictionary<string, object> sample)
        {
            sample["value"] = null;  // filled in from the frame drawn next; null if none comes
        }

        public override void FrameDrawn(FrameImage frame, Dictionary<string, object> sample)
        {
            if (frame == null || frame.Width <= 0 || frame.Height <= 0) return;
            frame.Area(rect, out var x0, out var y0, out var x1, out var y1);
            double lum = 0.0, luma = 0.0;
            for (var y = y0; y < y1; y++)
                for (var x = x0; x < x1; x++)
                {
                    var p = frame.At(x, y);
                    lum += Find.Luminance(Linear[p.r], Linear[p.g], Linear[p.b]);
                    luma += Find.Luminance(p.r, p.g, p.b) / 255.0;
                }
            var count = (double)(x1 - x0) * (y1 - y0);
            sample["value"] = new Dictionary<string, object>(StringComparer.Ordinal)
            {
                ["luminance"] = lum / count, ["luma"] = luma / count, ["pixels"] = count,
                ["size"] = new List<object> { (double)frame.Width, (double)frame.Height },
            };
        }
    }
}
