// ui: what the UI shows on screen, whatever draws it (contract section 3). Every element on screen in the frame drawn
// right after the sample: uGUI graphics on screen-space canvases (text: Text, TMP_Text; image: an Image or RawImage
// with a sprite or texture; box: any other drawn graphic) and UI Toolkit elements (text: a TextElement with text, or
// an empty field's placeholder; image: an image or background image; box: a background colour or a border). A select
// of text in a rect also reads the frame's pixels inside the rect (UiOcr): each line read for sure, where no element
// already reads text, joins as a text row of source "ocr". The select alone decides, so every measure on it counts and
// reads the same elements.
// "rows": [{"name", "class", "source", "kind", <field>: value}] (fields count, text, x, y, w, h); a sample whose frame
// was never drawn (the play ended first) has no "rows" key.
using System;
using System.Collections.Generic;
using System.Text.RegularExpressions;

namespace TaskProbe
{
    [ProbeQuery("ui")]
    public sealed class UiQuery : Query
    {
        static readonly HashSet<string> Known = new HashSet<string>(StringComparer.Ordinal) { "count", "text", "x", "y", "w", "h" };
        string kind;
        Regex text;
        bool bad, ocr, readerFailed;
        double[] rect;

        public override void Load()
        {
            KnownFields(Known);
            var select = Json.Obj(Def, "select");
            if (select == null) return;
            kind = Json.Str(select, "kind");
            if (kind != null && kind != "text" && kind != "box" && kind != "image") Probe.Error("ui " + Id + ": no element kind " + kind + " (text, box, image)");
            var pattern = Json.Str(select, "text");
            if (!string.IsNullOrEmpty(pattern))
            {
                text = Find.Pattern(pattern);
                if (text == null)
                {
                    bad = true;  // matches nothing
                    Probe.Error("ui " + Id + ": the text regex " + pattern + " doesn't compile");
                }
            }
            if (select.TryGetValue("rect", out var r) && Json.TryNumbers(r, 4, out var numbers)) rect = numbers;
            // a select of text in a rect also reads the frame as drawn; only such a query pays for the capture
            ocr = rect != null && (kind == "text" || (string.IsNullOrEmpty(kind) && !string.IsNullOrEmpty(pattern)));
        }

        public override FrameNeed Needs => ocr ? FrameNeed.Pixels : FrameNeed.Drawn;

        public override void Sample(double t, Dictionary<string, object> sample)
        {
            // filled in once the frame after it has been drawn; no rows if none comes
        }

        public override void FrameDrawn(FrameImage frame, Dictionary<string, object> sample)
        {
            var found = UiScan.Elements();
            // text read from the frame in the rect: this query's own rows, after every element read the other ways
            var candidates = new List<UiElement>(found);
            if (ocr && frame != null)
            {
                try { UiOcr.Elements(frame, rect, found, candidates); }
                catch (Exception e)
                {
                    // the elements still count; the lines of this frame are lost
                    if (!readerFailed) Probe.Log(e.ToString());
                    readerFailed = true;
                    Probe.Error("ui " + Id + ": " + e.GetType().Name + " in the frame reader (the exception is in probe.log)");
                }
            }
            var rows = new RowSet(Fields);
            if (!bad)
                foreach (var e in candidates)
                {
                    if ((!string.IsNullOrEmpty(kind) && e.Kind != kind) || (text != null && e.Kind != "text")) continue;
                    if (text != null && !text.IsMatch(e.Text ?? "")) continue;
                    if (rect != null)
                    {
                        double cx = e.X + e.W / 2.0, cy = e.Y + e.H / 2.0;
                        if (!e.HasRect || cx < Math.Min(rect[0], rect[2]) || cx > Math.Max(rect[0], rect[2]) ||
                            cy < Math.Min(rect[1], rect[3]) || cy > Math.Max(rect[1], rect[3]))
                            continue;
                    }
                    var row = new Dictionary<string, object>(StringComparer.Ordinal)
                    {
                        ["name"] = e.Name, ["class"] = e.Class, ["source"] = e.Source, ["kind"] = e.Kind,
                    };
                    foreach (var f in Fields)
                    {
                        if (f == "count") row[f] = 1.0;
                        else if (f == "text") { if (e.Kind == "text") row[f] = e.Text; }
                        else if (e.HasRect) row[f] = f == "x" ? e.X : f == "y" ? e.Y : f == "w" ? e.W : e.H;
                    }
                    rows.Add(row);
                }
            rows.WriteTo(sample);
        }
    }
}
