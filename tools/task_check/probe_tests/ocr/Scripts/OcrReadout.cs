// One line of text drawn without UI components, for the ui query's frame reader: strokes along the centre lines of a
// stroke font, each segment a rectangle half a stroke longer than the segment at both ends, and dots and dashes as
// boxes. Drawn one of three ways: OnGUI textures (a rotated texture a segment, as a HUD drawn with OnGUI does: the GUI
// matrix covers a slanted stroke's pixels a little differently from its exact quad), GL quads (in OnGUI's repaint) or a
// mesh of quads the camera draws (orthographic at one unit a pixel, centred on the frame); these two cover exactly the
// pixels whose centres their quads hold.
using System.Collections.Generic;
using System.Globalization;
using UnityEngine;

namespace ProbeTests.Ocr
{
    public sealed class OcrReadout : MonoBehaviour
    {
        public enum Way { Gui, Gl, Mesh }

        // One shape of the reader's own table (UiOcr) for each character, chosen among its shapes as one it reads at
        // 16, 24 and 36 px drawn this way. O, D, Q and B have no shape another character doesn't share closely.
        public static readonly Dictionary<char, string> Plain = new Dictionary<char, string>
        {
            ['0'] = "1,0 3,0 4,1 4,5 3,6 1,6 0,5 0,1 1,0;4,1 0,5", ['1'] = "0.5,1.5 2,0 2,6",
            ['2'] = "0,1 1,0 3,0 4,1 4,2.5 0,6 4,6", ['3'] = "0,0 4,0 1.5,3 3,3 4,4 4,5 3,6 0,6", ['4'] = "3,6 3,0 0,4 4,4",
            ['5'] = "4,0 1,0 0,1 0,3 3,3 4,4 4,5 3,6 0,6", ['6'] = "4,1 3,0 1,0 0,1 0,5 1,6 3,6 4,5 4,4 3,3 0,3",
            ['7'] = "0,0 4,0 1,6", ['8'] = "1,0 3,0 4,1 4,5 3,6 1,6 0,5 0,1 1,0;0,3 4,3",
            ['9'] = "4,3 1,3 0,2 0,1 1,0 3,0 4,1 4,5 3,6 1,6",
            ['A'] = "0,6 2,0 4,6;1,3.5 3,3.5", ['B'] = "0,0 3,0 4,1 4,2 3,3 0,3;3,3 4,4 4,5 3,6 0,6 0,0",
            ['C'] = "4,0 1,0 0,1 0,5 1,6 4,6", ['D'] = "0,0 2.5,0 4,1.5 4,4.5 2.5,6 0,6 0,0", ['E'] = "4,0 0,0 0,6 4,6;0,3 3,3",
            ['F'] = "4,0 0,0 0,6;0,3 3,3", ['G'] = "4,1 3,0 1,0 0,1 0,5 1,6 3,6 4,5 4,3 2,3", ['H'] = "0,0 0,6;4,0 4,6;0,3 4,3",
            ['I'] = "1,0 3,0;2,0 2,6;1,6 3,6", ['J'] = "4,0 4,5 3,6 1,6 0,5 0,4", ['K'] = "0,0 0,6;4,0 0,3 4,6",
            ['L'] = "0,0 0,6 4,6", ['M'] = "0,6 0,0 2,4 4,0 4,6", ['N'] = "0,6 0,0 4,6 4,0",
            ['O'] = "1,0 3,0 4,1 4,5 3,6 1,6 0,5 0,1 1,0", ['P'] = "0,6 0,0 3,0 4,1 4,2 3,3 0,3",
            ['Q'] = "1,0 3,0 4,1 4,5 3,6 1,6 0,5 0,1 1,0;2.5,4.5 4,6", ['R'] = "0,6 0,0 3,0 4,1 4,2 3,3 0,3;2,3 4,6",
            ['S'] = "4,1 3,0 1,0 0,1 0,2 1,3 3,3 4,4 4,5 3,6 1,6 0,5", ['T'] = "0,0 4,0;2,0 2,6",
            ['U'] = "0,0 0,5 1,6 3,6 4,5 4,0", ['V'] = "0,0 2,6 4,0", ['W'] = "0,0 1,6 2,2 3,6 4,0", ['X'] = "0,0 4,6;4,0 0,6",
            ['Y'] = "0,0 2,3 4,0;2,3 2,6", ['Z'] = "0,0 4,0 0,6 4,6",
            ['%'] = "4,0 0,6;0,0 1.2,0 1.2,1.5 0,1.5 0,0;2.8,4.5 4,4.5 4,6 2.8,6 2.8,4.5", ['/'] = "4,0 0,6",
        };

        // The same with a 3 that has short hooks at both ends, as the first stroke readout of these tests drew it
        public static readonly Dictionary<char, string> Hooked = new Dictionary<char, string>(Plain)
        {
            ['3'] = "0,1 1,0 3,0 4,1 4,2 3,3 4,4 4,5 3,6 1,6 0,5;2,3 3,3",
        };

        // The same where a character has a shape that reads at every sub-pixel place, drawn as exact quads at 36 px (and
        // 14 to 30 px for the digits): what a readout whose every value must read draws with
        public static readonly Dictionary<char, string> Steady = new Dictionary<char, string>(Plain)
        {
            ['0'] = "1,0 3,0 4,1 4,5 3,6 1,6 0,5 0,1 1,0;3,1.5 1,4.5", ['1'] = "1,1 2,0 2,6",
            ['2'] = "0,0 4,0 4,3 0,3 0,6 4,6", ['M'] = "0,6 0,0 2,3 4,0 4,6",
        };

        public Way way;
        public string text = "";
        public float cap = 36f;      // the centre lines' height, px
        public float stroke = 3f;    // line width, px
        public Vector2 origin;       // px from the frame's top left: the top left of the first glyph's centre lines
        public float shear;          // a slant: x moves right by shear times the height above the baseline
        public Color colour = Color.white;
        public Dictionary<char, string> font = Plain;
        public Material material;    // GL and Mesh
        public readonly List<Rect> extra = new List<Rect>();  // boxes drawn with the text (a rule, a frame), px
        public Texture2D backdrop;   // drawn first, over backdropRect (px)
        public Rect backdropRect;

        readonly List<Vector2> ends = new List<Vector2>();   // each segment's two ends
        readonly List<Rect> boxes = new List<Rect>();
        readonly List<Vector3> corners = new List<Vector3>();
        string laidOut;
        Mesh mesh;

        void Layout()
        {
            if (laidOut == text) return;
            laidOut = text;
            ends.Clear();
            boxes.Clear();
            boxes.AddRange(extra);
            float unit = cap / 6f, x = origin.x, y = origin.y, dot = stroke + 1f;
            foreach (var ch in text)
            {
                if (ch == ' ')
                {
                    x += cap;
                    continue;
                }
                if (ch == ':' || ch == '.')
                {
                    if (ch == ':') boxes.Add(new Rect(x, y + 2f * unit - dot / 2f, dot, dot));
                    boxes.Add(new Rect(x, y + cap + stroke / 2f - dot, dot, dot));
                    x += dot + 0.33f * cap;
                    continue;
                }
                if (ch == '-')
                {
                    boxes.Add(new Rect(x, y + 3f * unit - stroke / 2f, 2.4f * unit, stroke));
                    x += 2.4f * unit + 0.33f * cap;
                    continue;
                }
                if (!font.TryGetValue(ch, out var shape))
                {
                    x += cap;
                    continue;
                }
                foreach (var line in shape.Split(';'))
                {
                    var points = line.Split(' ');
                    for (var i = 0; i + 1 < points.Length; i++)
                    {
                        ends.Add(Point(points[i], x, y, unit));
                        ends.Add(Point(points[i + 1], x, y, unit));
                    }
                }
                x += 4f * unit + 0.33f * cap + stroke;
            }
            // the quads' corners, px from the top left
            corners.Clear();
            for (var i = 0; i < ends.Count; i += 2)
            {
                Vector2 a = ends[i], b = ends[i + 1], d = b - a;
                var u = d.sqrMagnitude > 0f ? d.normalized : Vector2.right;
                Vector2 along = u * (stroke / 2f), across = new Vector2(-u.y, u.x) * (stroke / 2f);
                corners.Add(a - along + across);
                corners.Add(b + along + across);
                corners.Add(b + along - across);
                corners.Add(a - along - across);
            }
            foreach (var r in boxes)
            {
                corners.Add(new Vector2(r.xMin, r.yMin));
                corners.Add(new Vector2(r.xMax, r.yMin));
                corners.Add(new Vector2(r.xMax, r.yMax));
                corners.Add(new Vector2(r.xMin, r.yMax));
            }
        }

        Vector2 Point(string xy, float x, float y, float unit)
        {
            var parts = xy.Split(',');
            float px = float.Parse(parts[0], CultureInfo.InvariantCulture), py = float.Parse(parts[1], CultureInfo.InvariantCulture);
            return new Vector2(x + (px + shear * (6f - py)) * unit, y + py * unit);
        }

        void LateUpdate()
        {
            if (way != Way.Mesh) return;
            if (mesh == null)
            {
                var child = new GameObject("Strokes", typeof(MeshFilter), typeof(MeshRenderer));
                child.transform.SetParent(transform, false);
                mesh = new Mesh();
                child.GetComponent<MeshFilter>().sharedMesh = mesh;
                child.GetComponent<MeshRenderer>().sharedMaterial = material;
            }
            if (laidOut == text && mesh.vertexCount > 0) return;
            Layout();
            // world units are pixels, the frame's centre at the origin, y up
            var vertices = new List<Vector3>();
            var triangles = new List<int>();
            foreach (var c in corners) vertices.Add(new Vector3(c.x - Screen.width / 2f, Screen.height / 2f - c.y, 0f));
            for (var i = 0; i < corners.Count; i += 4) triangles.AddRange(new[] { i, i + 1, i + 2, i, i + 2, i + 3 });
            mesh.Clear();
            mesh.SetVertices(vertices);
            mesh.SetTriangles(triangles, 0);
            mesh.RecalculateBounds();
        }

        void OnGUI()
        {
            if (Event.current.type != EventType.Repaint) return;
            Layout();
            if (backdrop != null) GUI.DrawTexture(backdropRect, backdrop);
            if (way == Way.Gui)
            {
                GUI.color = colour;
                for (var i = 0; i < ends.Count; i += 2)
                {
                    Vector2 a = ends[i], b = ends[i + 1], d = b - a, mid = (a + b) / 2f;
                    var saved = GUI.matrix;
                    GUIUtility.RotateAroundPivot(Mathf.Atan2(d.y, d.x) * Mathf.Rad2Deg, mid);
                    GUI.DrawTexture(new Rect(mid.x - (d.magnitude + stroke) / 2f, mid.y - stroke / 2f, d.magnitude + stroke, stroke), Texture2D.whiteTexture);
                    GUI.matrix = saved;
                }
                foreach (var r in boxes) GUI.DrawTexture(r, Texture2D.whiteTexture);
                GUI.color = Color.white;
            }
            else if (way == Way.Gl)
            {
                material.SetPass(0);
                GL.PushMatrix();
                GL.LoadPixelMatrix();  // in OnGUI's repaint its y runs down from the top, as GUI coordinates do
                GL.Begin(GL.QUADS);
                GL.Color(colour);
                foreach (var c in corners) GL.Vertex3(c.x, c.y, 0f);
                GL.End();
                GL.PopMatrix();
            }
        }
    }
}
