// A readout drawn with no UI component, for the ui query's frame reader: OnGUI rectangles laid along the centre lines
// of a small stroke font (capitals, digits, ':' and '%'), white on a dark box. Line 1: "TIME m:ss" (play time); line 2:
// "HP n%" (falls 1 a second from 99).
using System.Collections.Generic;
using System.Globalization;
using UnityEngine;

public class StrokeReadout : MonoBehaviour
{
    public float Cap = 36f;      // glyph height, px
    public float Stroke = 4f;    // line width, px
    public Vector2 Origin = new Vector2(30f, 405f);

    static readonly Dictionary<char, string> Font = new Dictionary<char, string>
    {
        ['T'] = "0,0 4,0;2,0 2,6",
        ['I'] = "1,0 3,0;2,0 2,6;1,6 3,6",
        ['M'] = "0,6 0,0 2,3 4,0 4,6",
        ['E'] = "4,0 0,0 0,6 4,6;0,3 3,3",
        ['H'] = "0,0 0,6;4,0 4,6;0,3 4,3",
        ['P'] = "0,6 0,0 3,0 4,1 4,2 3,3 0,3",
        ['%'] = "4,0 0,6;0,0 1.2,0 1.2,1.5 0,1.5 0,0;2.8,4.5 4,4.5 4,6 2.8,6 2.8,4.5",
        ['0'] = "1,0 3,0 4,1 4,5 3,6 1,6 0,5 0,1 1,0;4,1 0,5",
        ['1'] = "1,1 2,0 2,6",
        ['2'] = "0,1 1,0 3,0 4,1 4,2 0,6 4,6",
        ['3'] = "0,1 1,0 3,0 4,1 4,2 3,3 4,4 4,5 3,6 1,6 0,5;2,3 3,3",
        ['4'] = "3,6 3,0 0,4 4,4",
        ['5'] = "4,0 0,0 0,3 3,3 4,4 4,5 3,6 1,6 0,5",
        ['6'] = "4,1 3,0 1,0 0,1 0,5 1,6 3,6 4,5 4,4 3,3 0,3",
        ['7'] = "0,0 4,0 1,6",
        ['8'] = "1,0 3,0 4,1 4,2 3,3 1,3 0,2 0,1 1,0;1,3 0,4 0,5 1,6 3,6 4,5 4,4 3,3",
        ['9'] = "4,3 1,3 0,2 0,1 1,0 3,0 4,1 4,5 3,6 1,6",
    };

    Texture2D white;

    void Awake()
    {
        white = Texture2D.whiteTexture;
    }

    void Line(Vector2 a, Vector2 b)
    {
        var d = b - a;
        var len = d.magnitude;
        var mid = (a + b) / 2f;
        var angle = Mathf.Atan2(d.y, d.x) * Mathf.Rad2Deg;
        var saved = GUI.matrix;
        GUIUtility.RotateAroundPivot(angle, mid);
        GUI.DrawTexture(new Rect(mid.x - (len + Stroke) / 2f, mid.y - Stroke / 2f, len + Stroke, Stroke), white);
        GUI.matrix = saved;
    }

    void Text(string s, Vector2 at)
    {
        var unit = Cap / 6f;
        var x = at.x;
        GUI.color = Color.white;
        foreach (var ch in s)
        {
            if (ch == ' ') { x += Cap; continue; }
            if (ch == ':')
            {
                var dot = Stroke + 1f;
                GUI.DrawTexture(new Rect(x, at.y + 1.5f * unit - dot / 2f, dot, dot), white);
                GUI.DrawTexture(new Rect(x, at.y + Cap + Stroke / 2f - dot, dot, dot), white);
                x += dot + 0.33f * Cap;
                continue;
            }
            if (!Font.TryGetValue(ch, out var shape)) { x += Cap; continue; }
            foreach (var poly in shape.Split(';'))
            {
                Vector2? prev = null;
                foreach (var p in poly.Split(' '))
                {
                    var xy = p.Split(',');
                    var v = new Vector2(x + float.Parse(xy[0], CultureInfo.InvariantCulture) * unit,
                        at.y + float.Parse(xy[1], CultureInfo.InvariantCulture) * unit);
                    if (prev.HasValue) Line(prev.Value, v);
                    prev = v;
                }
            }
            x += 4f * unit + 0.33f * Cap + Stroke;
        }
    }

    void OnGUI()
    {
        if (Event.current.type != EventType.Repaint) return;
        GUI.color = new Color(0.08f, 0.08f, 0.12f, 1f);
        GUI.DrawTexture(new Rect(Origin.x - 10f, Origin.y - 15f, 400f, 130f), white);
        var t = Mathf.FloorToInt(Time.timeSinceLevelLoad);
        Text("TIME " + (t / 60) + ":" + (t % 60).ToString("00"), Origin);
        Text("HP " + Mathf.Max(0, 99 - t) + "%", Origin + new Vector2(0f, Cap + 24f));
        GUI.color = Color.white;
    }
}
