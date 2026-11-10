// widgets: the UI's own elements and their state (contract section 3): uGUI objects (graphics, selectables, TextMeshPro)
// on the scene's canvases and UI Toolkit elements of every UIDocument. A selection sample: one row per widget.
// select: component (a type name of a component on the object, or of the element, base types included), name (a wildcard
// on the object's or element's name), text (a regex its text must match), visible (true: on screen only).
using System.Collections.Generic;
using System.Text.RegularExpressions;

namespace TaskProbe
{
    [ProbeQuery("widgets")]
    public sealed class WidgetsQuery : Query
    {
        string component, name;
        Regex text;
        bool visibleOnly, bad;

        public override void Load()
        {
            var select = Json.Obj(Def, "select");
            if (select == null) return;
            component = Json.Str(select, "component");
            if (string.IsNullOrEmpty(component)) component = Json.Str(select, "class");  // the original's key
            name = Json.Str(select, "name");
            var pattern = Json.Str(select, "text");
            if (!string.IsNullOrEmpty(pattern))
            {
                text = Find.Pattern(pattern);
                if (text == null) { bad = true; Probe.Error("widgets " + Id + ": the text regex " + pattern + " doesn't compile"); }
            }
            visibleOnly = Json.Bool(select, "visible");
        }

        public override void Sample(double t, Dictionary<string, object> sample)
        {
            var rows = new RowSet(Fields);
            if (bad) { rows.WriteTo(sample); return; }  // a regex that doesn't compile matches nothing
            foreach (var w in UiScan.Widgets(component, name, text, visibleOnly))
            {
                var row = new Dictionary<string, object> { ["name"] = w.Name, ["class"] = w.Class };
                foreach (var f in Fields)
                {
                    var v = w.Field(f);
                    if (v != null) row[f] = v;
                }
                rows.Add(row);
            }
            rows.WriteTo(sample);
        }
    }
}
