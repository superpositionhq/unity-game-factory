using System;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.UI;

namespace ProbeTests.Ocr
{
    /// <summary>What a play of the ocr family shows, by its argument -ocrlab: "clock" (a clock that counts tenths of a
    /// second and a falling number, as a mesh, and the clock again in GL quads), "glyphs" (every character the reader
    /// knows, in pairs, one item to a cell, at -ocrsize 16, 24 or 36 px, with OnGUI), "limits" (readouts the reader
    /// refuses, each beside one it reads), "found" (three readouts: one under a uGUI text, one under a uGUI box, one alone),
    /// "select" (a readout, a uGUI label and a uGUI box), "cap" (more items than the 200 rows a sample keeps). Positions
    /// are pixels from the frame's top left; tests.py lays the same items out. Time is counted in frames (30 a second),
    /// so a sample at t sees t exactly. Readouts a play checks a rule with are quads (mesh or GL), whose pixels are their
    /// exact geometry's; OnGUI's rotated textures cover a slanted stroke's pixels a little differently.</summary>
    public sealed class OcrLab : MonoBehaviour
    {
        public const float Origin = 40.25f;  // a quarter pixel off the grid: no stroke edge on a pixel's centre
        public static readonly string[] Items =
        {
            "00", "11", "22", "33", "44", "55", "66", "77", "88", "99", "AA", "BB", "CC", "DD", "EE", "FF", "GG", "HH",
            "II", "JJ", "KK", "LL", "MM", "NN", "OO", "PP", "QQ", "RR", "SS", "TT", "UU", "VV", "WW", "XX", "YY", "ZZ",
            "4%", "4/4", "4.4", "-4", "4:4",
        };

        const OcrReadout.Way Mesh = OcrReadout.Way.Mesh;
        public Material glMaterial, meshMaterial;
        readonly List<OcrReadout> clocks = new List<OcrReadout>();
        OcrReadout points;
        int frames;

        void Awake()
        {
            Camera.main.orthographicSize = Screen.height / 2f;  // one unit a pixel, for the mesh readouts
            switch (Arg("-ocrlab"))
            {
                case "clock": Clock(); break;
                case "glyphs": Glyphs(int.Parse(Arg("-ocrsize") ?? "24")); break;
                case "limits": Limits(); break;
                case "found": Found(); break;
                case "select": Select(); break;
                case "cap": Cap(); break;
            }
        }

        void Update()
        {
            frames++;
            var tenths = frames / 3;
            foreach (var c in clocks) c.text = $"TIME {tenths / 600}:{tenths / 10 % 60:00}.{tenths % 10}";
            if (points != null) points.text = "HP " + (4096 - 97 * (frames / 15));
        }

        static string Arg(string name)
        {
            var args = Environment.GetCommandLineArgs();
            var at = Array.IndexOf(args, name);
            return at >= 0 && at + 1 < args.Length ? args[at + 1] : null;
        }

        /// <summary>A readout; drawn as quads (mesh or GL) it takes the steady font, with OnGUI the plain one.</summary>
        OcrReadout Readout(string text, float x, float y, float cap = 36f, float stroke = 3f, OcrReadout.Way way = OcrReadout.Way.Gui)
        {
            var r = new GameObject("Readout " + text).AddComponent<OcrReadout>();
            r.text = text;
            r.origin = new Vector2(x, y);
            r.cap = cap;
            r.stroke = stroke;
            r.way = way;
            r.font = way == OcrReadout.Way.Gui ? OcrReadout.Plain : OcrReadout.Steady;
            r.material = way == OcrReadout.Way.Gl ? glMaterial : meshMaterial;
            return r;
        }

        void Clock()
        {
            clocks.Add(Readout("", Origin, Origin, way: Mesh));
            points = Readout("", Origin, Origin + 80f, way: Mesh);
            clocks.Add(Readout("", Origin + 0.5f, Origin + 160.5f, way: OcrReadout.Way.Gl));
        }

        /// <summary>Where item i of a glyphs play starts, at a cap height (its stroke a twelfth of it): six items a row,
        /// each in a cell three glyphs and a cap wide.</summary>
        public static Vector2 ItemAt(int i, int cap)
        {
            var advance = 4f * cap / 6f + 0.33f * cap + cap / 12;
            return new Vector2(Origin + i % 6 * (3f * advance + cap), Origin + i / 6 * 2f * cap);
        }

        void Glyphs(int cap)
        {
            for (var i = 0; i < Items.Length; i++)
            {
                var at = ItemAt(i, cap);
                Readout(Items[i], at.x, at.y, cap, cap / 12);
            }
        }

        void Limits()
        {
            Readout("HP 42", Origin, Origin, way: Mesh);                        // the rect's edge: touching, cutting, clear
            Readout("HP 3", 40f, 110f, 36f, 4f).font = OcrReadout.Hooked;       // the hooked 3, OnGUI at 4 px
            Readout("HP 3", 300f, 110f, 36f, 4f);                               // the flat-topped 3, the same
            Readout("HP 42", Origin, 190.25f, 20f, 5f, Mesh);                   // too bold for its size
            Readout("HP 42", 300.25f, 190.25f, 20f, 2f, Mesh);                  // the same, thin
            Readout("HP 42", Origin, 250.25f, way: Mesh).shear = 0.25f;         // slanted
            Readout("7", 420.25f, 250.25f, way: Mesh);                          // a lone character
            Readout("HP 42", Origin, 330.25f, way: OcrReadout.Way.Gl).colour = new Color(0.12f, 0.12f, 0.16f, 1f);  // faint
            var ruled = Readout("HP 42", 300.25f, 330.25f, way: Mesh);          // a rule across it
            ruled.extra.Add(new Rect(290f, 345f, 220f, 1f));
            var framed = Readout("HP 42", Origin, 420.25f, way: Mesh);          // a frame around it
            framed.extra.Add(new Rect(26f, 406f, 210f, 2f));
            framed.extra.Add(new Rect(26f, 474f, 210f, 2f));
            framed.extra.Add(new Rect(26f, 406f, 2f, 70f));
            framed.extra.Add(new Rect(234f, 406f, 2f, 70f));
            var shaded = Readout("HP 42", 300.25f, 420.25f, way: OcrReadout.Way.Gl);  // on a background that varies
            shaded.backdrop = new Texture2D(2, 1) { wrapMode = TextureWrapMode.Clamp, filterMode = FilterMode.Bilinear };
            shaded.backdrop.SetPixels(new[] { new Color(0.08f, 0.08f, 0.12f), new Color(0.45f, 0.45f, 0.5f) });
            shaded.backdrop.Apply();
            shaded.backdropRect = new Rect(280f, 400f, 240f, 80f);
            Readout("HP 42", 600.25f, Origin, 8f, 1f, Mesh);                    // too small for its strokes
        }

        void Found()
        {
            Readout("HP 42", Origin, Origin, way: Mesh);
            Readout("XP 17", Origin, Origin + 80f, way: Mesh);
            Readout("LAP 2", Origin, Origin + 160f, way: Mesh);
            var canvas = Overlay();
            var text = Element<Text>(canvas, "CoverText", new Rect(30f, 30f, 220f, 60f), new Color(1f, 1f, 1f, 0.01f));
            text.font = Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf");
            text.fontSize = 30;
            text.text = "HP";
            Element<Image>(canvas, "CoverBox", new Rect(30f, 110f, 220f, 60f), new Color(1f, 1f, 1f, 0.01f));
        }

        void Select()
        {
            Readout("HP 42", Origin, Origin, way: Mesh);
            var canvas = Overlay();
            var label = Element<Text>(canvas, "Label", new Rect(500f, 40f, 200f, 40f), Color.white);
            label.font = Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf");
            label.fontSize = 30;
            label.text = "LABEL";
            Element<Image>(canvas, "Box", new Rect(500f, 120f, 100f, 40f), new Color(0.3f, 0.4f, 0.8f, 1f));
        }

        void Cap()
        {
            for (var row = 0; row < 20; row++)
                for (var col = 0; col < 14; col++)
                    Readout("12", 10.25f + col * 66f, 10.25f + row * 26f, 14f, 1f, Mesh);
        }

        static Canvas Overlay()
        {
            var canvas = new GameObject("Overlay", typeof(Canvas)).GetComponent<Canvas>();
            canvas.renderMode = RenderMode.ScreenSpaceOverlay;
            return canvas;
        }

        static T Element<T>(Canvas canvas, string name, Rect px, Color colour) where T : Graphic
        {
            var go = new GameObject(name, typeof(RectTransform), typeof(CanvasRenderer), typeof(T));
            go.transform.SetParent(canvas.transform, false);
            var rect = go.GetComponent<RectTransform>();
            rect.anchorMin = rect.anchorMax = rect.pivot = new Vector2(0f, 1f);
            rect.anchoredPosition = new Vector2(px.x, -px.y);
            rect.sizeDelta = new Vector2(px.width, px.height);
            var graphic = go.GetComponent<T>();
            graphic.color = colour;
            return graphic;
        }
    }
}
