// widgets: the UI's own elements and their state (contract section 3): uGUI objects (graphics, selectables, TextMeshPro)
// on the scene's canvases and UI Toolkit elements of every UIDocument, hidden ones included.
// "rows": [{"name", "class", <field>: value}] for every widget the select matches (select: component, a type name of
// a component on the object, or of the element, base types included; name, a wildcard on the object's or element's
// name; text, a regex its text must match; visible: true, only the widgets the visible field reads 1 for).
using System;
using System.Collections.Generic;
using System.Text.RegularExpressions;

namespace TaskProbe
{
    [ProbeQuery("widgets")]
    public sealed class WidgetsQuery : Query
    {
        static readonly HashSet<string> Known = new HashSet<string>(StringComparer.Ordinal)
        {
            "count", "visible", "text", "percent", "value", "interactable", "has_brush", "brush", "x", "y", "w", "h",
        };
        string component, name;
        Regex text;
        bool visibleOnly, bad;

        public override void Load()
        {
            KnownFields(Known);
            var select = Json.Obj(Def, "select");
            if (select == null) return;
            component = Json.Str(select, "component");
            if (!string.IsNullOrEmpty(component) && Reflect.TypeNamed(component) == null)
                Probe.Error("widgets " + Id + ": no component type " + component);  // a typo, or a UI system the project lacks
            name = Json.Str(select, "name");
            var pattern = Json.Str(select, "text");
            if (!string.IsNullOrEmpty(pattern))
            {
                text = Find.Pattern(pattern);
                if (text == null)
                {
                    bad = true;  // matches nothing
                    Probe.Error("widgets " + Id + ": the text regex " + pattern + " doesn't compile");
                }
            }
            visibleOnly = Json.Bool(select, "visible");
        }

        public override void Sample(double t, Dictionary<string, object> sample)
        {
            var rows = new RowSet(Fields);
            if (!bad)
                foreach (var w in UiScan.Widgets(component, name, text, visibleOnly))
                {
                    var row = new Dictionary<string, object>(StringComparer.Ordinal) { ["name"] = w.Name, ["class"] = w.Class };
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
