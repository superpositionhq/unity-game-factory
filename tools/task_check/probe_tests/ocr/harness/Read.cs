// The frame reader (Runtime/Queries/UiOcr.cs, compiled as it is) on frames.py's frames, outside Unity: each reading of
// cases.txt as the ui query makes it (UiOcr.Elements on a frame whose rows come from the bottom, as Unity reads one
// back), printed as expected.txt has the original's: <name>: | <text> <x>,<y>,<w>,<h> (pixels of the frame).
using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using TaskProbe;

namespace UnityEngine
{
    public struct Color32
    {
        public byte r, g, b, a;
    }
}

namespace TaskProbe
{
    // as Runtime/Core/Query.cs and Runtime/Queries/UiScan.cs have them
    public sealed class FrameImage
    {
        public int Width, Height;
        public UnityEngine.Color32[] Pixels;
        public UnityEngine.Color32 At(int x, int yFromTop) => Pixels[(Height - 1 - yFromTop) * Width + x];
    }

    public sealed class UiElement
    {
        public string Name, Class, Source, Kind, Text;
        public bool HasRect;
        public double X, Y, W, H;
    }
}

static class Read
{
    static int Main(string[] args)
    {
        var folder = Path.GetDirectoryName(Path.GetFullPath(args[0]));
        foreach (var line in File.ReadAllLines(args[0]))
        {
            var parts = line.Split(new[] { ' ' }, StringSplitOptions.RemoveEmptyEntries);
            var bytes = File.ReadAllBytes(Path.Combine(folder, parts[0]));
            int w = BitConverter.ToInt32(bytes, 0), h = BitConverter.ToInt32(bytes, 4);
            var pixels = new UnityEngine.Color32[w * h];
            for (var y = 0; y < h; y++)
                for (var x = 0; x < w; x++)
                {
                    var at = 8 + (y * w + x) * 3;
                    pixels[(h - 1 - y) * w + x] = new UnityEngine.Color32 { r = bytes[at], g = bytes[at + 1], b = bytes[at + 2], a = 255 };
                }
            var rect = new double[4];
            for (var i = 0; i < 4; i++) rect[i] = double.Parse(parts[1 + i], CultureInfo.InvariantCulture);
            var read = new List<UiElement>();
            UiOcr.Elements(new FrameImage { Width = w, Height = h, Pixels = pixels }, rect, new List<UiElement>(), read);
            var said = parts[5] + ":";
            foreach (var e in read)
                said += string.Format(CultureInfo.InvariantCulture, " | {0} {1},{2},{3},{4}", e.Text, Pixel(e.X, w), Pixel(e.Y, h), Pixel(e.W, w), Pixel(e.H, h));
            Console.Out.Write(said + "\n");
        }
        return 0;
    }

    // the reader's boxes are whole pixels; anything else is printed as it is, to show as a difference
    static string Pixel(double v, int size) =>
        Math.Abs(v * size - Math.Round(v * size)) < 1e-9 ? Math.Round(v * size).ToString(CultureInfo.InvariantCulture) : v.ToString("R", CultureInfo.InvariantCulture);
}
