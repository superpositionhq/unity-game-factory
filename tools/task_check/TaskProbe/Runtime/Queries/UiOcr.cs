// Text read from the frame as drawn (the ui query's glyph reader): the fallback for text no element reads, whatever drew
// it (OnGUI, GL lines, a custom mesh, a texture, segments). Only a ui query that asks for text inside a rect reads it:
// the frame drawn after the sample, cropped to the rect, is read here. The reader is small and strict: the text must
// stand out from an even background in one colour; its marks are split into lines and glyphs, and each glyph is matched
// against the centre lines of 0-9, A-Z and a few signs (each in the shapes stroke fonts draw them: plain strokes, cut
// corners, segments, slashed zeros, diagonal 1, 4 and 7). A glyph reads only when one character matches it closely and
// no other comes near; anything else (a glyph that fits two characters, an unknown mark, a line cut by the rect, a busy
// background) reads nothing for that line rather than a guess.
//
// A port of the Unreal probe's reader (OcrRead and its helpers): the constants and decisions are the same; only the
// pixel source differs (a FrameImage, rows read from the top).
using System;
using System.Collections.Generic;
using System.Globalization;
using System.Text;
using UnityEngine;

namespace TaskProbe
{
    public static class UiOcr
    {
        struct Pt
        {
            public double X, Y;
            public Pt(double x, double y) { X = x; Y = y; }
        }

        /// <summary>One character's shape: its centre-line segments in the normalised glyph space (Normal), points
        /// along them, and the distance from every cell of the glyph grid to them.</summary>
        sealed class Shape
        {
            public char Char;
            public double Aspect;  // max(width, 0.3 height) / height of its centre lines
            public double Step;  // the length (in heights) each sample stands for
            public bool Square;  // it has a square corner (an upright and a level line meeting): a segment font's shape
            public readonly List<Pt> Samples = new List<Pt>();
            public float[] Dist;
        }

        /// <summary>One line of text read in an image: its text and its pixel box (x0, y0 inclusive; x1, y1 exclusive).</summary>
        public struct Line
        {
            public string Text;
            public int X0, Y0, X1, Y1;
        }

        // the glyph grid: normalised x (centred, a glyph's width scaled to Width) and y (0 top, 1 bottom), with a margin
        const double Width = 0.6;
        const double GridX0 = -0.5, GridY0 = -0.25, Cell = 0.02;
        const int GridW = 50, GridH = 75;
        // reading a glyph (Scores, Decide): the loose distance's base (in heights), the tight one's share of it, how much
        // a shape may miss and still fit (loose) and in detail (tight), how much every other character must miss (loose)
        // and by how much more (tight)
        const double Loose = 0.04, Tight = 0.6, Fits = 0.1, Detail = 0.4, Apart = 0.03, Margin = 0.2;
        // how much worse in detail a glyph's square-cornered shapes must be for it to show cut or round corners
        const double Corner = 0.08;
        // the marks' cut, a share of the way from the background to the ink
        const double CutShare = 0.33;

        // Character shapes as centre lines on a 4 x 6 box (x right, y down): polylines of "x,y" points split by ';'. A
        // character has every shape it is commonly drawn in, so characters that look alike in some font (0, O, D; 5, S;
        // 8, B; 1, I) all match such a glyph and it reads nothing.
        static readonly KeyValuePair<char, string>[] ShapeDefs =
        {
            S('0', "1,0 3,0 4,1 4,5 3,6 1,6 0,5 0,1 1,0"),
            S('0', "0,0 4,0 4,6 0,6 0,0"),
            S('0', "1.5,0 2.5,0 4,1.5 4,4.5 2.5,6 1.5,6 0,4.5 0,1.5 1.5,0"),
            S('0', "1,0 3,0 4,1 4,5 3,6 1,6 0,5 0,1 1,0;4,1 0,5"),
            S('0', "1,0 3,0 4,1 4,5 3,6 1,6 0,5 0,1 1,0;3,1.5 1,4.5"),
            S('0', "0,0 4,0 4,6 0,6 0,0;4,0 0,6"),
            S('0', "1.5,0 2.5,0 4,1.5 4,4.5 2.5,6 1.5,6 0,4.5 0,1.5 1.5,0;3.5,1 0.5,5"),
            S('O', "1,0 3,0 4,1 4,5 3,6 1,6 0,5 0,1 1,0"),
            S('O', "0,0 4,0 4,6 0,6 0,0"),
            S('O', "1.5,0 2.5,0 4,1.5 4,4.5 2.5,6 1.5,6 0,4.5 0,1.5 1.5,0"),
            S('D', "0,0 2.5,0 4,1.5 4,4.5 2.5,6 0,6 0,0"),
            S('D', "0,0 4,0 4,6 0,6 0,0"),
            S('Q', "1,0 3,0 4,1 4,5 3,6 1,6 0,5 0,1 1,0;2.5,4.5 4,6"),
            S('Q', "0,0 4,0 4,6 0,6 0,0;2.5,4.5 4,6"),
            S('1', "2,0 2,6"),
            S('1', "1,1 2,0 2,6"),
            S('1', "0.5,1.5 2,0 2,6"),
            S('1', "1,1 2,0 2,6;1,6 3,6"),
            S('I', "2,0 2,6"),
            S('I', "1,0 3,0;2,0 2,6;1,6 3,6"),
            S('2', "0,1 1,0 3,0 4,1 4,2 0,6 4,6"),
            S('2', "0,1 1,0 3,0 4,1 4,2.5 0,6 4,6"),
            S('2', "0,0 4,0 4,3 0,3 0,6 4,6"),
            S('2', "0,1 1,0 3,0 4,1 4,2 3,3 1,3 0,4 0,6 4,6"),
            S('2', "0,0 4,0 4,2 0,6 4,6"),
            S('Z', "0,0 4,0 0,6 4,6"),
            S('Z', "0,0 4,0 4,1 0,5 0,6 4,6"),
            S('3', "0,0 4,0 4,6 0,6;0,3 4,3"),
            S('3', "0,1 1,0 3,0 4,1 4,2 3,3 4,4 4,5 3,6 1,6 0,5;1,3 3,3"),
            S('3', "0,1 1,0 3,0 4,1 4,2 3,3 4,4 4,5 3,6 1,6 0,5;2,3 3,3"),
            S('3', "0,0 4,0 2,2.5 3,2.5 4,3.5 4,5 3,6 1,6 0,5"),
            S('3', "0,0 4,0 1.5,3 3,3 4,4 4,5 3,6 0,6"),
            S('4', "3,6 3,0 0,4 4,4"),
            S('4', "3,6 3,0 0,4.5 4,4.5"),
            S('4', "0,0 0,3 4,3;4,0 4,6"),
            S('4', "0,0 0,4 4,4;3,2 3,6"),
            S('4', "2.5,6 2.5,0 0,4 4,4"),
            S('5', "4,0 0,0 0,3 4,3 4,6 0,6"),
            S('5', "4,0 0,0 0,3 3,3 4,4 4,5 3,6 0,6"),
            S('5', "4,0 0,0 0,2.5 3,2.5 4,3.5 4,5 3,6 1,6 0,5"),
            S('5', "4,0 0,0 0,3 3,3 4,4 4,5 3,6 1,6 0,5"),
            S('5', "4,0 1,0 0,1 0,3 3,3 4,4 4,5 3,6 0,6"),
            S('5', "4,0 1,0 0,1 0,2 1,3 3,3 4,4 4,5 3,6 0,6"),
            S('S', "4,1 3,0 1,0 0,1 0,2 1,3 3,3 4,4 4,5 3,6 1,6 0,5"),
            S('S', "4,0 0,0 0,3 4,3 4,6 0,6"),
            S('S', "4,1 3,0 1,0 0,1 0,2 1,3 3,3 4,4 4,5 3,6 0,6"),
            S('S', "4,0.5 3.5,0 1,0 0,1 0,2 1,3 3,3 4,4 4,5 3,6 1,6 0,5"),
            S('6', "4,0 0,0 0,6 4,6 4,3 0,3"),
            S('6', "0,0 0,6 4,6 4,3 0,3"),
            S('6', "3,0 1,0 0,1 0,5 1,6 3,6 4,5 4,4 3,3 0,3"),
            S('6', "4,1 3,0 1,0 0,1 0,5 1,6 3,6 4,5 4,4 3,3 0,3"),
            S('6', "3,0 0,3 0,5 1,6 3,6 4,5 4,4 3,3 0,3"),
            S('6', "4,0 1,0 0,1 0,5 1,6 3,6 4,5 4,4 3,3 0,3"),
            S('G', "4,1 3,0 1,0 0,1 0,5 1,6 3,6 4,5 4,3 2,3"),
            S('G', "4,0 0,0 0,6 4,6 4,3 2,3"),
            S('G', "4,0 1,0 0,1 0,5 1,6 4,6 4,3 2,3"),
            S('7', "0,0 4,0 1,6"),
            S('7', "0,0 4,0 4,6"),
            S('7', "0,1 0,0 4,0 4,6"),
            S('7', "0,0 4,0 4,1 1.5,6"),
            S('7', "0,0 4,0 2,6"),
            S('7', "0,0 4,0 4,1.5 2,6"),
            S('8', "1,0 3,0 4,1 4,2 3,3 1,3 0,2 0,1 1,0;1,3 0,4 0,5 1,6 3,6 4,5 4,4 3,3"),
            S('8', "0,0 4,0 4,6 0,6 0,0;0,3 4,3"),
            S('8', "1,0 3,0 4,1 4,5 3,6 1,6 0,5 0,1 1,0;0,3 4,3"),
            S('B', "0,0 3,0 4,1 4,2 3,3 0,3;3,3 4,4 4,5 3,6 0,6 0,0"),
            S('B', "0,0 4,0 4,6 0,6 0,0;0,3 4,3"),
            S('B', "0,0 3,0 4,1 4,2 3,3 4,4 4,5 3,6 0,6 0,0;0,3 3,3"),
            S('9', "4,3 0,3 0,0 4,0 4,6 0,6"),
            S('9', "4,3 0,3 0,0 4,0 4,6"),
            S('9', "4,3 1,3 0,2 0,1 1,0 3,0 4,1 4,5 3,6 1,6"),
            S('9', "4,3 1,3 0,2 0,1 1,0 3,0 4,1 4,6"),
            S('9', "4,3 1,3 0,2 0,1 1,0 3,0 4,1 4,3 1,6"),
            S('9', "4,3 1,3 0,2 0,1 1,0 3,0 4,1 4,5 3,6 0,6"),
            S('A', "0,6 2,0 4,6;1,3.5 3,3.5"),
            S('A', "0,6 0,1 1,0 3,0 4,1 4,6;0,3 4,3"),
            S('A', "0,6 0,0 4,0 4,6;0,3 4,3"),
            S('A', "0,6 0,2 2,0 4,2 4,6;0,3.5 4,3.5"),
            S('A', "0,6 1.5,0 2.5,0 4,6;0.75,3.5 3.25,3.5"),
            S('C', "4,0 1,0 0,1 0,5 1,6 4,6"),
            S('C', "4,0 0,0 0,6 4,6"),
            S('C', "4,1 3,0 1,0 0,1 0,5 1,6 3,6 4,5"),
            S('E', "4,0 0,0 0,6 4,6;0,3 3,3"),
            S('E', "4,0 0,0 0,6 4,6;0,3 4,3"),
            S('F', "4,0 0,0 0,6;0,3 3,3"),
            S('F', "4,0 0,0 0,6;0,3 4,3"),
            S('H', "0,0 0,6;4,0 4,6;0,3 4,3"),
            S('J', "4,0 4,5 3,6 1,6 0,5 0,4"),
            S('J', "4,0 4,6 0,6 0,4"),
            S('J', "1,0 4,0;3,0 3,5 2,6 1,6 0,5"),
            S('K', "0,0 0,6;4,0 0,3.5;1.5,2.5 4,6"),
            S('K', "0,0 0,6;4,0 0,3 4,6"),
            S('K', "0,0 0,6;0,3 2,3 4,0;2,3 4,6"),
            S('L', "0,0 0,6 4,6"),
            S('M', "0,6 0,0 2,3 4,0 4,6"),
            S('M', "0,6 0,0 2,4 4,0 4,6"),
            S('M', "0,6 0,0 2,2 4,0 4,6"),
            S('M', "0,6 1,0 2,3 3,0 4,6"),
            S('M', "0,6 0,0 2,6 4,0 4,6"),
            S('N', "0,6 0,0 4,6 4,0"),
            S('P', "0,6 0,0 3,0 4,1 4,2 3,3 0,3"),
            S('P', "0,6 0,0 4,0 4,3 0,3"),
            S('R', "0,6 0,0 3,0 4,1 4,2 3,3 0,3;2,3 4,6"),
            S('R', "0,6 0,0 4,0 4,3 0,3;2,3 4,6"),
            S('R', "0,6 0,0 3,0 4,1 4,2 3,3 0,3;3,3 4,4 4,6"),
            S('R', "0,6 0,0 3,0 4,1 4,2 3,3 0,3;1,3 4,6"),
            S('T', "0,0 4,0;2,0 2,6"),
            S('U', "0,0 0,5 1,6 3,6 4,5 4,0"),
            S('U', "0,0 0,6 4,6 4,0"),
            S('V', "0,0 2,6 4,0"),
            S('V', "0,0 0,3 2,6 4,3 4,0"),
            S('W', "0,0 1,6 2,3 3,6 4,0"),
            S('W', "0,0 0,6 2,3 4,6 4,0"),
            S('W', "0,0 1,6 2,2 3,6 4,0"),
            S('W', "0,0 0,6 2,4 4,6 4,0"),
            S('X', "0,0 4,6;4,0 0,6"),
            S('Y', "0,0 2,3 4,0;2,3 2,6"),
            S('Y', "0,0 2,2.5 4,0;2,2.5 2,6"),
            S('%', "4,0 0,6;0,0 1.2,0 1.2,1.5 0,1.5 0,0;2.8,4.5 4,4.5 4,6 2.8,6 2.8,4.5"),
            S('%', "4,0 0,6;0.5,0 1,0 1.5,0.5 1.5,1 1,1.5 0.5,1.5 0,1 0,0.5 0.5,0;3,4.5 3.5,4.5 4,5 4,5.5 3.5,6 3,6 2.5,5.5 2.5,5 3,4.5"),
            S('/', "4,0 0,6"),
        };

        static KeyValuePair<char, string> S(char c, string lines) => new KeyValuePair<char, string>(c, lines);

        static int FloorToInt(double v) => (int)Math.Floor(v);
        static int RoundToInt(double v) => (int)Math.Floor(v + 0.5);  // Unreal's RoundToInt: halves up
        static int Clamp(int v, int lo, int hi) => v < lo ? lo : v > hi ? hi : v;

        static Pt Normal(double x, double y, double centreX, double top, double scaleX, double height) =>
            new Pt((x - centreX) / scaleX * Width, (y - top) / height);

        static int CellAt(Pt p)
        {
            var cx = Clamp(FloorToInt((p.X - GridX0) / Cell), 0, GridW - 1);
            var cy = Clamp(FloorToInt((p.Y - GridY0) / Cell), 0, GridH - 1);
            return cy * GridW + cx;
        }

        static double SegDist(Pt p, Pt a, Pt b)
        {
            double dx = b.X - a.X, dy = b.Y - a.Y;
            var l = dx * dx + dy * dy;
            var t = l > 0.0 ? Math.Min(Math.Max(((p.X - a.X) * dx + (p.Y - a.Y) * dy) / l, 0.0), 1.0) : 0.0;
            double ex = a.X + t * dx - p.X, ey = a.Y + t * dy - p.Y;
            return Math.Sqrt(ex * ex + ey * ey);
        }

        static List<Shape> shapes;

        /// <summary>Every character shape, parsed and laid on the glyph grid once.</summary>
        static List<Shape> Shapes()
        {
            if (shapes != null) return shapes;
            var all = new List<Shape>();
            foreach (var def in ShapeDefs)
            {
                // parse the polylines into segments
                var a = new List<Pt>();
                var b = new List<Pt>();
                foreach (var polyline in def.Value.Split(';'))
                {
                    var line = new List<Pt>();
                    foreach (var point in polyline.Split(new[] { ' ' }, StringSplitOptions.RemoveEmptyEntries))
                    {
                        var xy = point.Split(',');
                        line.Add(new Pt(double.Parse(xy[0], CultureInfo.InvariantCulture), double.Parse(xy[1], CultureInfo.InvariantCulture)));
                    }
                    for (var i = 0; i + 1 < line.Count; i++)
                    {
                        a.Add(line[i]);
                        b.Add(line[i + 1]);
                    }
                }
                var shape = new Shape();
                for (var i = 0; i + 1 < a.Count; i++)
                {
                    var join = a[i + 1].X == b[i].X && a[i + 1].Y == b[i].Y;
                    var levelUpright = (a[i].Y == b[i].Y && a[i + 1].X == b[i + 1].X) || (a[i].X == b[i].X && a[i + 1].Y == b[i + 1].Y);
                    shape.Square = shape.Square || (join && levelUpright);
                }
                double x0 = 1e9, x1 = -1e9, y0 = 1e9, y1 = -1e9;
                for (var i = 0; i < a.Count; i++)
                {
                    x0 = Math.Min(x0, Math.Min(a[i].X, b[i].X));
                    x1 = Math.Max(x1, Math.Max(a[i].X, b[i].X));
                    y0 = Math.Min(y0, Math.Min(a[i].Y, b[i].Y));
                    y1 = Math.Max(y1, Math.Max(a[i].Y, b[i].Y));
                }
                var h = Math.Max(y1 - y0, 1e-6);
                var sx = Math.Max(x1 - x0, 0.3 * h);
                shape.Char = def.Key;
                shape.Aspect = sx / h;
                for (var i = 0; i < a.Count; i++)
                {
                    a[i] = Normal(a[i].X, a[i].Y, (x0 + x1) / 2.0, y0, sx, h);
                    b[i] = Normal(b[i].X, b[i].Y, (x0 + x1) / 2.0, y0, sx, h);
                    double dx = b[i].X - a[i].X, dy = b[i].Y - a[i].Y;
                    var steps = Math.Max(1, RoundToInt(Math.Sqrt(dx * dx + dy * dy) / 0.02));
                    for (var k = (i > 0 && a[i].X == b[i - 1].X && a[i].Y == b[i - 1].Y) ? 1 : 0; k <= steps; k++)
                        shape.Samples.Add(new Pt(a[i].X + dx * k / steps, a[i].Y + dy * k / steps));
                }
                var length = 0.0;
                for (var i = 0; i < a.Count; i++)
                {
                    // lengths in heights: x back from the normalised width
                    double dx = (b[i].X - a[i].X) / Width * sx / h, dy = b[i].Y - a[i].Y;
                    length += Math.Sqrt(dx * dx + dy * dy);
                }
                shape.Step = length / Math.Max(1, shape.Samples.Count);
                shape.Dist = new float[GridW * GridH];
                for (var cy = 0; cy < GridH; cy++)
                    for (var cx = 0; cx < GridW; cx++)
                    {
                        var p = new Pt(GridX0 + (cx + 0.5) * Cell, GridY0 + (cy + 0.5) * Cell);
                        var d = 1e9;
                        for (var i = 0; i < a.Count; i++) d = Math.Min(d, SegDist(p, a[i], b[i]));
                        shape.Dist[cy * GridW + cx] = (float)d;
                    }
                all.Add(shape);
            }
            shapes = all;
            return shapes;
        }

        /// <summary>Thins a binary image (1 = mark, a blank border of one pixel) to lines one pixel wide (Zhang-Suen).</summary>
        static void Thin(byte[] im, int w, int h)
        {
            var del = new List<int>();
            var p = new byte[8];
            var changed = true;
            while (changed)
            {
                changed = false;
                for (var pass = 0; pass < 2; pass++)
                {
                    del.Clear();
                    for (var y = 1; y < h - 1; y++)
                        for (var x = 1; x < w - 1; x++)
                        {
                            var i = y * w + x;
                            if (im[i] == 0) continue;
                            p[0] = im[i - w]; p[1] = im[i - w + 1]; p[2] = im[i + 1]; p[3] = im[i + w + 1];
                            p[4] = im[i + w]; p[5] = im[i + w - 1]; p[6] = im[i - 1]; p[7] = im[i - w - 1];
                            int count = 0, turns = 0;
                            for (var k = 0; k < 8; k++)
                            {
                                count += p[k];
                                turns += (p[k] == 0 && p[(k + 1) % 8] != 0) ? 1 : 0;
                            }
                            if (count < 2 || count > 6 || turns != 1) continue;
                            // p: 0 north, 2 east, 4 south, 6 west
                            if (pass == 0
                                ? (p[0] != 0 && p[2] != 0 && p[4] != 0) || (p[2] != 0 && p[4] != 0 && p[6] != 0)
                                : (p[0] != 0 && p[2] != 0 && p[6] != 0) || (p[0] != 0 && p[4] != 0 && p[6] != 0))
                                continue;
                            del.Add(i);
                        }
                    foreach (var i in del) im[i] = 0;
                    changed = changed || del.Count > 0;
                }
            }
        }

        /// <summary>A connected mark (8-connected pixels), its box (inclusive) and pixels.</summary>
        sealed class Mark
        {
            public int X0, Y0, X1, Y1;
            public readonly List<int> Pixels = new List<int>();
            public bool Edge;  // touches the image's edge
            public int W => X1 - X0 + 1;
            public int H => Y1 - Y0 + 1;
        }

        /// <summary>How a glyph scores against one character's shapes (Scores): the best of all its shapes [0], of those
        /// without square corners [1] and of those with [2]; Fit loose, Detail tight (lengths in heights; lower is better).</summary>
        sealed class Score
        {
            public char Char;
            public readonly double[] Fit = { 1e9, 1e9, 1e9 };
            public readonly double[] Detail = { 1e9, 1e9, 1e9 };
            public readonly Shape[] Shape = new Shape[3];
        }

        /// <summary>A glyph: marks side by side merged, its box (inclusive), how it scored, and what it read as (0: nothing).</summary>
        sealed class Glyph
        {
            public int X0, Y0, X1, Y1;
            public readonly List<int> Marks = new List<int>();
            public readonly List<Score> Scores = new List<Score>();
            public double Stroke, CentreX, Top, ScaleX, Height, Loose;  // its centre lines' frame
            public char Char;
            public int W => X1 - X0 + 1;
            public int H => Y1 - Y0 + 1;
        }

        /// <summary>Which pixels are marks: the image's edge must be one even colour (its median), the marks must stand far
        /// apart from it (Otsu's split of the colour distance to it, the two classes well separated) and be the fewer.
        /// False when not. `px` is row by row from the top.</summary>
        static bool Marks(Color32[] px, int w, int h, out byte[] mask)
        {
            mask = null;
            if (w < 8 || h < 8 || px.Length < w * h) return false;
            var rs = new List<int>();
            var gs = new List<int>();
            var bs = new List<int>();
            void Edge(int x, int y)
            {
                var c = px[y * w + x];
                rs.Add(c.r);
                gs.Add(c.g);
                bs.Add(c.b);
            }
            for (var x = 0; x < w; x++)
            {
                Edge(x, 0);
                Edge(x, h - 1);
            }
            for (var y = 1; y < h - 1; y++)
            {
                Edge(0, y);
                Edge(w - 1, y);
            }
            int Median(List<int> v)
            {
                v.Sort();
                return v[v.Count / 2];
            }
            int br = Median(rs), bg = Median(gs), bb = Median(bs);
            var d = new float[w * h];
            var hist = new int[256];
            for (var i = 0; i < w * h; i++)
            {
                double dr = px[i].r - br, dg = px[i].g - bg, db = px[i].b - bb;
                d[i] = (float)Math.Sqrt((dr * dr + dg * dg + db * db) / 3.0);
                hist[Clamp(FloorToInt(d[i]), 0, 255)]++;
            }
            // Otsu's split
            var n = (double)w * h;
            double sum = 0.0, sumSq = 0.0;
            for (var k = 0; k < 256; k++)
            {
                sum += (k + 0.5) * hist[k];
                sumSq += (k + 0.5) * (k + 0.5) * hist[k];
            }
            var total = sumSq / n - (sum / n) * (sum / n);
            double bestBetween = -1.0, below = 0.0, sumBelow = 0.0;
            var split = 0;
            for (var k = 0; k < 255; k++)
            {
                below += hist[k];
                sumBelow += (k + 0.5) * hist[k];
                if (below <= 0.0 || below >= n) continue;
                double m0 = sumBelow / below, m1 = (sum - sumBelow) / (n - below);
                var between = below * (n - below) / (n * n) * (m1 - m0) * (m1 - m0);
                if (between > bestBetween)
                {
                    bestBetween = between;
                    split = k + 1;  // marks: distance >= split
                }
            }
            if (total <= 1.0 || bestBetween / total < 0.8) return false;  // no clear split between the background and the marks
            var fore = new List<float>();
            var back = new List<float>();
            for (var i = 0; i < w * h; i++) (d[i] >= split ? fore : back).Add(d[i]);
            if (fore.Count < 8 || fore.Count > 0.45 * n) return false;
            fore.Sort();
            back.Sort();
            double ink = fore[(int)(fore.Count * 0.9)];
            double paper = back[(int)(back.Count * 0.98)];
            if (ink < 40.0 || ink < 3.0 * paper) return false;  // too faint, or a background that varies
            // marks at a third of the way from the background to the ink (a thin line half on two rows still reads);
            // faint ink from a sixth of the way, to see strokes the marks lost
            double cut = paper + CutShare * (ink - paper), faint = paper + 0.16 * (ink - paper);
            mask = new byte[w * h];
            var edgeMarks = 0;
            for (var i = 0; i < w * h; i++) mask[i] = (byte)(d[i] >= cut ? 2 : (d[i] >= faint ? 1 : 0));
            for (var x = 0; x < w; x++) edgeMarks += (mask[x] == 2 ? 1 : 0) + (mask[(h - 1) * w + x] == 2 ? 1 : 0);
            for (var y = 1; y < h - 1; y++) edgeMarks += (mask[y * w] == 2 ? 1 : 0) + (mask[y * w + w - 1] == 2 ? 1 : 0);
            return edgeMarks <= 0.1 * (2 * w + 2 * h);
        }

        /// <summary>Scores one glyph against every character shape (Glyph.Scores), by how much of the glyph's centre lines
        /// lies far from the shape's and how much of the shape's lies far from the glyph's (lengths in capital heights):
        /// at a loose distance whether it fits at all (the larger of the two), at a tight one the detail that tells near
        /// shapes apart (the two added). False when the glyph is too small or too bold to read.</summary>
        static bool GlyphScores(Glyph g, List<Mark> marks, int w)
        {
            // the glyph alone, with a blank border, thinned to its centre lines
            int gw = g.W + 2, gh = g.H + 2;
            var im = new byte[gw * gh];
            var area = 0;
            foreach (var m in g.Marks)
                foreach (var p in marks[m].Pixels)
                {
                    im[(p / w - g.Y0 + 1) * gw + p % w - g.X0 + 1] = 1;
                    area++;
                }
            Thin(im, gw, gh);
            var skel = new List<Pt>();
            for (var y = 0; y < gh; y++)
                for (var x = 0; x < gw; x++)
                    if (im[y * gw + x] != 0) skel.Add(new Pt(x - 1 + 0.5, y - 1 + 0.5));
            if (skel.Count < 4) return false;
            // stroke width, and the box of the centre lines (the glyph's box less half a stroke on each side)
            g.Stroke = Math.Max(1.0, (double)area / skel.Count);
            var cx0 = 0.5 * Math.Min(g.Stroke, (double)g.W);
            g.CentreX = g.W / 2.0;
            g.Top = 0.5 * g.Stroke;
            g.Height = g.H - g.Stroke;
            if (g.Height < 4.0) return false;
            // how far a centre line may stray (in heights): a little, a pixel's rounding and half a stroke. A glyph too
            // small or too bold for that to stay small reads nothing.
            g.Loose = Loose + 0.6 / g.Height + 0.5 * g.Stroke / g.Height;
            var tight = Tight * g.Loose;
            if (g.Loose > 0.15) return false;
            g.ScaleX = Math.Max(g.W - 2.0 * cx0, 0.3 * g.Height);
            var aspect = g.ScaleX / g.Height;
            for (var i = 0; i < skel.Count; i++) skel[i] = Normal(skel[i].X, skel[i].Y, g.CentreX, g.Top, g.ScaleX, g.Height);
            // distance from every cell of the grid to the glyph's centre lines
            var dist = new float[GridW * GridH];
            for (var cy = 0; cy < GridH; cy++)
                for (var cx = 0; cx < GridW; cx++)
                {
                    double px = GridX0 + (cx + 0.5) * Cell, py = GridY0 + (cy + 0.5) * Cell;
                    var d = 1e9;
                    foreach (var s in skel) d = Math.Min(d, (s.X - px) * (s.X - px) + (s.Y - py) * (s.Y - py));
                    dist[cy * GridW + cx] = (float)Math.Sqrt(d);
                }
            // each character's best shapes: of all, of those without square corners, of those with
            foreach (var shape in Shapes())
            {
                if (Math.Max(aspect, shape.Aspect) / Math.Min(aspect, shape.Aspect) > 1.8) continue;  // far too narrow or too wide for it
                int farG = 0, farS = 0, offG = 0, offS = 0;
                foreach (var p in skel)
                {
                    double d = shape.Dist[CellAt(p)];
                    farG += d > g.Loose ? 1 : 0;
                    offG += d > tight ? 1 : 0;
                }
                foreach (var p in shape.Samples)
                {
                    double d = dist[CellAt(p)];
                    farS += d > g.Loose ? 1 : 0;
                    offS += d > tight ? 1 : 0;
                }
                double l = Math.Max(farG / g.Height, farS * shape.Step), t = offG / g.Height + offS * shape.Step;
                var c = 0;
                while (c < g.Scores.Count && g.Scores[c].Char != shape.Char) c++;
                if (c == g.Scores.Count) g.Scores.Add(new Score { Char = shape.Char });
                var sc = g.Scores[c];
                sc.Fit[0] = Math.Min(sc.Fit[0], l);
                if (t < sc.Detail[0])
                {
                    sc.Detail[0] = t;
                    sc.Shape[0] = shape;
                }
                var k = shape.Square ? 2 : 1;
                sc.Fit[k] = Math.Min(sc.Fit[k], l);
                if (t < sc.Detail[k])
                {
                    sc.Detail[k] = t;
                    sc.Shape[k] = shape;
                }
            }
            return true;
        }

        /// <summary>Reads a scored glyph: the character whose shape fits and is best in detail, when every other
        /// character's best shape both misses by some length when loose and is far worse in detail, and no ink around the
        /// glyph (faint ink too) lies away from that shape (a stroke the marks lost); else 0. When the glyph shows cut or
        /// round corners (its character's best shape has none square, and its square-cornered shapes are worse in detail),
        /// other characters' square-cornered shapes are not near it: a 5 with cut corners is not a seven-segment S, while
        /// a 5 drawn with square segments is one, and reads nothing.</summary>
        static char GlyphDecide(Glyph g, byte[] mask, int w, int h)
        {
            var best = -1;
            for (var c = 0; c < g.Scores.Count; c++)
                if (g.Scores[c].Fit[0] <= Fits && (best == -1 || g.Scores[c].Detail[0] < g.Scores[best].Detail[0])) best = c;
            if (best == -1 || g.Scores[best].Detail[0] > Detail) return '\0';  // nothing fits, or nothing fits in detail
            var b = g.Scores[best];
            var cut = !b.Shape[0].Square && b.Shape[2] != null && b.Detail[2] - b.Detail[0] >= Corner;
            var k = cut ? 1 : 0;
            for (var c = 0; c < g.Scores.Count; c++)
            {
                var s = g.Scores[c];
                if (c != best && s.Shape[k] != null && (s.Fit[k] < Apart || s.Detail[k] - b.Detail[0] < Margin)) return '\0';  // another character comes near
            }
            // ink around the glyph (faint too) away from the lines of every shape of the character: a stroke the marks
            // lost, so it may be another
            var ink = new List<Pt>();
            for (var y = Math.Max(0, g.Y0 - 1); y <= Math.Min(h - 1, g.Y1 + 1); y++)
                for (var x = Math.Max(0, g.X0 - 1); x <= Math.Min(w - 1, g.X1 + 1); x++)
                    if (mask[y * w + x] != 0) ink.Add(Normal(x - g.X0 + 0.5, y - g.Y0 + 0.5, g.CentreX, g.Top, g.ScaleX, g.Height));
            var stray = ink.Count;
            foreach (var shape in Shapes())
            {
                if (shape.Char != b.Char) continue;
                var far = 0;
                foreach (var p in ink) far += shape.Dist[CellAt(p)] > g.Loose + 0.5 * g.Stroke / g.Height ? 1 : 0;
                stray = Math.Min(stray, far);
            }
            return stray <= Math.Max(2.0, 0.03 * ink.Count) ? b.Char : '\0';
        }

        /// <summary>A glyph shorter than the line's capitals: a full stop, a hyphen or a colon by its place and shape, else 0.</summary>
        static char SmallChar(Glyph g, List<Mark> marks, int top, int bottom)
        {
            double cap = bottom - top + 1;
            bool Dot(Mark m)
            {
                var f = (double)m.Pixels.Count / (m.W * m.H);
                return m.H <= 0.3 * cap && m.W <= 0.35 * cap && m.W <= 2.5 * m.H && m.H <= 2.5 * m.W && f >= 0.5;
            }
            if (g.Marks.Count == 1)
            {
                var m = marks[g.Marks[0]];
                var fill = (double)m.Pixels.Count / (m.W * m.H);
                if (Dot(m) && bottom - m.Y1 <= 0.12 * cap) return '.';
                var mid = (m.Y0 + m.Y1) / 2.0 - top;
                if (m.H <= 0.25 * cap && m.W >= 2 * m.H && m.W >= 0.25 * cap && m.W <= 0.9 * cap && fill >= 0.6 && mid >= 0.3 * cap && mid <= 0.7 * cap)
                    return '-';
            }
            if (g.Marks.Count == 2)
            {
                var a = marks[g.Marks[0]].Y0 < marks[g.Marks[1]].Y0 ? marks[g.Marks[0]] : marks[g.Marks[1]];
                var b = ReferenceEquals(a, marks[g.Marks[0]]) ? marks[g.Marks[1]] : marks[g.Marks[0]];
                if (Dot(a) && Dot(b) && b.Y0 > a.Y1 && bottom - b.Y1 <= 0.12 * cap && a.Y0 - top >= 0.15 * cap) return ':';
            }
            return '\0';
        }

        /// <summary>Reads the text lines in an image (w x h, `px` row by row from the top): each line of glyphs read
        /// whole, or not at all.</summary>
        public static void Read(Color32[] px, int w, int h, List<Line> output)
        {
            if (!Marks(px, w, h, out var mask)) return;
            // connected marks
            var all = new List<Mark>();
            var label = new int[w * h];
            for (var i = 0; i < label.Length; i++) label[i] = -1;
            var stack = new Stack<int>();
            for (var start = 0; start < w * h; start++)
            {
                if (mask[start] != 2 || label[start] != -1) continue;
                var m = new Mark { X0 = start % w, X1 = start % w, Y0 = start / w, Y1 = start / w };
                var id = all.Count;
                stack.Clear();
                stack.Push(start);
                label[start] = id;
                while (stack.Count > 0)
                {
                    var p = stack.Pop();
                    m.Pixels.Add(p);
                    int x = p % w, y = p / w;
                    m.X0 = Math.Min(m.X0, x);
                    m.X1 = Math.Max(m.X1, x);
                    m.Y0 = Math.Min(m.Y0, y);
                    m.Y1 = Math.Max(m.Y1, y);
                    for (var dy = -1; dy <= 1; dy++)
                        for (var dx = -1; dx <= 1; dx++)
                        {
                            int nx = x + dx, ny = y + dy;
                            if (nx < 0 || ny < 0 || nx >= w || ny >= h) continue;
                            var q = ny * w + nx;
                            if (mask[q] == 2 && label[q] == -1)
                            {
                                label[q] = id;
                                stack.Push(q);
                            }
                        }
                }
                m.Edge = m.X0 == 0 || m.Y0 == 0 || m.X1 == w - 1 || m.Y1 == h - 1;
                all.Add(m);
            }
            // set aside: specks (two pixels or less), frames (a hollow mark around others a quarter to 0.7 of its height)
            // and rules (long marks a fifth of a glyph's height thin or less), and marks the edge cuts. Each refuses a
            // line it crosses, unless it is around the line or a speck inside one of its glyphs.
            var kept = new List<int>();
            var aside = new List<int>();
            var heights = new List<int>();
            foreach (var m in all)
                if (m.Pixels.Count > 2 && m.W < 4 * m.H) heights.Add(m.H);
            heights.Sort();
            var typical = heights.Count == 0 ? 0 : heights[heights.Count / 2];
            for (var i = 0; i < all.Count; i++)
            {
                var m = all[i];
                var isAside = m.Pixels.Count <= 2 || m.Edge;
                if (!isAside && typical > 0 && m.W >= 2.5 * typical && m.H <= Math.Max(2.0, 0.2 * typical)) isAside = true;  // a rule
                if (!isAside)
                {
                    var inner = 0;
                    for (var j = 0; j < all.Count; j++)
                    {
                        var o = all[j];
                        if (j != i && o.Pixels.Count > 2 && o.X0 > m.X0 && o.X1 < m.X1 && o.Y0 > m.Y0 && o.Y1 < m.Y1) inner = Math.Max(inner, o.H);
                    }
                    if (inner >= 0.25 * m.H && m.H >= 1.4 * inner)
                    {
                        var band = Math.Max(2, RoundToInt(0.12 * Math.Min(m.W, m.H)));
                        var rim = 0;
                        foreach (var p in m.Pixels)
                        {
                            int x = p % w, y = p / w;
                            rim += (x - m.X0 < band || m.X1 - x < band || y - m.Y0 < band || m.Y1 - y < band) ? 1 : 0;
                        }
                        isAside = rim >= 0.95 * m.Pixels.Count;  // a frame
                    }
                }
                (isAside ? aside : kept).Add(i);
            }
            // lines: marks that overlap in height by at least half the shorter one
            var parent = new int[kept.Count];
            for (var k = 0; k < kept.Count; k++) parent[k] = k;
            int Root(int k)
            {
                while (parent[k] != k) k = parent[k] = parent[parent[k]];
                return k;
            }
            for (var a = 0; a < kept.Count; a++)
                for (var b = a + 1; b < kept.Count; b++)
                {
                    var ma = all[kept[a]];
                    var mb = all[kept[b]];
                    var over = Math.Min(ma.Y1, mb.Y1) - Math.Max(ma.Y0, mb.Y0) + 1;
                    if (over >= 0.5 * Math.Min(ma.H, mb.H)) parent[Root(a)] = Root(b);
                }
            for (var r = 0; r < kept.Count; r++)
            {
                if (Root(r) != r) continue;
                var line = new List<int>();
                for (var k = 0; k < kept.Count; k++)
                    if (Root(k) == r) line.Add(kept[k]);
                line.Sort((l, rr) => all[l].X0.CompareTo(all[rr].X0));
                // glyphs: marks that overlap side to side by at least 0.4 of the narrower
                var glyphs = new List<Glyph>();
                foreach (var i in line)
                {
                    var m = all[i];
                    if (glyphs.Count > 0)
                    {
                        var g = glyphs[glyphs.Count - 1];
                        var over = Math.Min(g.X1, m.X1) - Math.Max(g.X0, m.X0) + 1;
                        if (over > 0 && over >= 0.4 * Math.Min(g.W, m.W))
                        {
                            g.X0 = Math.Min(g.X0, m.X0);
                            g.X1 = Math.Max(g.X1, m.X1);
                            g.Y0 = Math.Min(g.Y0, m.Y0);
                            g.Y1 = Math.Max(g.Y1, m.Y1);
                            g.Marks.Add(i);
                            continue;
                        }
                    }
                    var ng = new Glyph { X0 = m.X0, X1 = m.X1, Y0 = m.Y0, Y1 = m.Y1 };
                    ng.Marks.Add(i);
                    glyphs.Add(ng);
                }
                int top = h, bottom = -1, cap = 0;
                foreach (var g in glyphs) cap = Math.Max(cap, g.H);
                foreach (var g in glyphs)
                    if (g.H >= 0.75 * cap)
                    {
                        top = Math.Min(top, g.Y0);
                        bottom = Math.Max(bottom, g.Y1);
                    }
                if (cap < 7 || bottom - top + 1 > 1.25 * cap) continue;  // too small to read, or capitals not on one line
                // a mark set aside that crosses the line: a cut glyph, a stroke through it, a speck between its glyphs
                var crossed = false;
                var firstGlyph = glyphs[0];
                var lastGlyph = glyphs[glyphs.Count - 1];
                foreach (var i in aside)
                {
                    var m = all[i];
                    if (m.X0 <= firstGlyph.X0 && m.X1 >= lastGlyph.X1 && m.Y0 <= top && m.Y1 >= bottom) continue;  // around the line
                    if (m.Y1 < top || m.Y0 > bottom || m.X1 < firstGlyph.X0 - cap || m.X0 > lastGlyph.X1 + cap) continue;  // clear of it
                    var inGlyph = false;
                    foreach (var g in glyphs)
                        inGlyph = inGlyph || (m.Pixels.Count <= 2 && m.X0 >= g.X0 - 1 && m.X1 <= g.X1 + 1 && m.Y0 >= g.Y0 - 1 && m.Y1 <= g.Y1 + 1);
                    crossed = crossed || !inGlyph;
                }
                if (crossed) continue;
                foreach (var g in glyphs)
                {
                    if (g.H < 0.75 * cap) g.Char = SmallChar(g, all, top, bottom);
                    else if (g.Y0 - top <= 0.2 * cap && bottom - g.Y1 <= 0.2 * cap && GlyphScores(g, all, w)) g.Char = GlyphDecide(g, mask, w, h);
                }
                // spaces: a gap of half a capital's height where glyphs stand further apart than the line's usual pitch;
                // items: glyphs two and a half capitals' heights apart are separate texts
                var pitch = new List<double>();
                for (var gi = 1; gi < glyphs.Count; gi++)
                    pitch.Add((glyphs[gi].X0 + glyphs[gi].X1 - glyphs[gi - 1].X0 - glyphs[gi - 1].X1) / 2.0);
                var sorted = new List<double>(pitch);
                sorted.Sort();
                var usual = sorted.Count == 0 ? 0.0 : sorted[(sorted.Count - 1) / 2];
                var first = 0;
                for (var gi = 1; gi <= glyphs.Count; gi++)
                {
                    var gap = gi < glyphs.Count ? glyphs[gi].X0 - glyphs[gi - 1].X1 - 1 : 0;
                    if (gi < glyphs.Count && gap < 2.5 * cap) continue;
                    // one item: glyphs first .. gi-1
                    var text = new StringBuilder();
                    int lx0 = w, ly0 = h, lx1 = 0, ly1 = 0;
                    var whole = true;
                    var letters = 0;
                    for (var k = first; k < gi; k++)
                    {
                        var g = glyphs[k];
                        if (k > first)
                        {
                            var space = g.X0 - glyphs[k - 1].X1 - 1;
                            if (space >= 0.9 * cap || (space >= 0.45 * cap && pitch[k - 1] >= 1.45 * usual && glyphs.Count > 2)) text.Append(' ');
                        }
                        whole = whole && g.Char != '\0';
                        text.Append(g.Char != '\0' ? g.Char : '?');
                        letters += (g.Char >= 'A' && g.Char <= 'Z') || (g.Char >= '0' && g.Char <= '9') ? 1 : 0;
                        lx0 = Math.Min(lx0, g.X0);
                        ly0 = Math.Min(ly0, g.Y0);
                        lx1 = Math.Max(lx1, g.X1 + 1);
                        ly1 = Math.Max(ly1, g.Y1 + 1);
                    }
                    // two glyphs at least: a lone shape (a bar, a ring, a cross, an icon) is as likely a mark as a character
                    if (whole && letters > 0 && gi - first >= 2)
                        output.Add(new Line { Text = text.ToString(), X0 = lx0, Y0 = ly0, X1 = lx1, Y1 = ly1 });
                    first = gi;
                }
            }
        }

        /// <summary>ui text read from the frame as drawn inside a select rect (viewport fractions, y down): the rect cut
        /// from the frame and read, each line a text element of source "ocr". A line where a text element already reads
        /// (`found`) is left to that element, so nothing reads twice.</summary>
        public static void Elements(FrameImage frame, double[] rect, List<UiElement> found, List<UiElement> output)
        {
            int w = frame.Width, h = frame.Height;
            var x0 = Clamp(FloorToInt(Math.Min(rect[0], rect[2]) * w), 0, w - 1);
            var y0 = Clamp(FloorToInt(Math.Min(rect[1], rect[3]) * h), 0, h - 1);
            var x1 = Clamp((int)Math.Ceiling(Math.Max(rect[0], rect[2]) * w), x0 + 1, w);
            var y1 = Clamp((int)Math.Ceiling(Math.Max(rect[1], rect[3]) * h), y0 + 1, h);
            int cw = x1 - x0, ch = y1 - y0;
            var crop = new Color32[cw * ch];
            for (var y = 0; y < ch; y++)
                for (var x = 0; x < cw; x++)
                    crop[y * cw + x] = frame.At(x0 + x, y0 + y);
            var lines = new List<Line>();
            Read(crop, cw, ch, lines);
            foreach (var l in lines)
            {
                var e = new UiElement
                {
                    Source = "ocr", Kind = "text", Name = "ScreenText", Class = "ScreenText", Text = l.Text, HasRect = true,
                    X = (double)(x0 + l.X0) / w, Y = (double)(y0 + l.Y0) / h, W = (double)(l.X1 - l.X0) / w, H = (double)(l.Y1 - l.Y0) / h,
                };
                var read = false;
                foreach (var t in found)
                    read = read || (t.Kind == "text" && t.HasRect && t.X < e.X + e.W && e.X < t.X + t.W && t.Y < e.Y + e.H && e.Y < t.Y + t.H);
                if (!read) output.Add(e);
            }
        }
    }
}
