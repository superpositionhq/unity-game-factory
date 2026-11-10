// The UI as the widgets and ui queries read it (contract section 3): uGUI (UnityEngine.UI graphics and selectables,
// TextMeshPro) on the scene's canvases, and UI Toolkit (every UIDocument's panel). Rectangles are viewport fractions 0-1
// with y down from the top, whatever render mode or panel scale placed them. On screen means: active, enabled, every
// Canvas up the chain enabled, an alpha above 0.004 all the way up (CanvasGroups, the graphic's colour, its
// CanvasRenderer, not culled by a RectMask2D), at least partly inside the frame; in UI Toolkit, in a screen panel,
// displayed, visible and of an opacity above 0.004 up the chain.
using System;
using System.Collections.Generic;
using System.Text.RegularExpressions;
using UnityEngine;
#if TASKPROBE_UGUI
using UnityEngine.EventSystems;
using UnityEngine.UI;
#endif
#if TASKPROBE_UITK
using UIE = UnityEngine.UIElements;
#endif

namespace TaskProbe
{
    /// <summary>One element on screen (a ui row): what it shows and where.</summary>
    public sealed class UiElement
    {
        public string Name, Class, Source, Kind, Text;
        public bool HasRect;
        public double X, Y, W, H;
    }

    /// <summary>A widget (a widgets row): a uGUI component's object or a UI Toolkit element.</summary>
    public abstract class UiWidget
    {
        public string Name, Class;
        /// <summary>The field's value (double, string) or null when the widget has none.</summary>
        public abstract object Field(string field);
        public abstract bool Visible();
        public abstract string Text();
    }

    public static class UiScan
    {
        public const float AlphaFloor = 0.004f;  // an element drawn at this alpha or less is not on screen
        static readonly Regex Tags = new Regex(@"</?[A-Za-z_#][^<>]*>|</>", RegexOptions.CultureInvariant);

        /// <summary>Rich text as shown: its tags left out.</summary>
        public static string Plain(string marked) => string.IsNullOrEmpty(marked) || marked.IndexOf('<') < 0 ? marked : Tags.Replace(marked, "");

        public static bool IsRectField(string f) => f == "x" || f == "y" || f == "w" || f == "h";

        static bool InFrame(double x, double y, double w, double h) => x + w > 0.0 && x < 1.0 && y + h > 0.0 && y < 1.0;

        // ---------------------------------------------------------------- elements on screen (ui)

        static int elementsFrame = -1;
        static readonly List<UiElement> elements = new List<UiElement>();

        /// <summary>Every element on screen now (cached for the frame: several ui queries read the same).</summary>
        public static List<UiElement> Elements()
        {
            if (elementsFrame == Time.frameCount) return elements;
            elementsFrame = Time.frameCount;
            elements.Clear();
#if TASKPROBE_UGUI
            try { UguiElements(elements); }
            catch (Exception e) { Probe.Active?.Error("ui: the uGUI canvases couldn't be read: " + e.Message); }
#endif
#if TASKPROBE_UITK
            try { UitkElements(elements); }
            catch (Exception e) { Probe.Active?.Error("ui: the UI Toolkit panels couldn't be read: " + e.Message); }
#endif
            return elements;
        }

        // ---------------------------------------------------------------- uGUI

#if TASKPROBE_UGUI
        static readonly Vector3[] Corners = new Vector3[4];

        /// <summary>A RectTransform's rectangle in viewport fractions (y down). `screenOnly`: false for a world-space
        /// canvas (none is read for ui). A world-space canvas projects through the player's camera; false when behind it.</summary>
        public static bool RectOf(RectTransform rt, Canvas canvas, bool screenOnly, out double x, out double y, out double w, out double h)
        {
            x = y = w = h = 0.0;
            if (rt == null || canvas == null) return false;
            var root = canvas.rootCanvas;
            Camera cam = null;
            switch (root.renderMode)
            {
                case RenderMode.ScreenSpaceOverlay: break;
                case RenderMode.ScreenSpaceCamera: cam = root.worldCamera; break;  // none: drawn as an overlay
                default:
                    if (screenOnly) return false;
                    cam = Probe.Active != null ? Probe.Active.View : Camera.main;
                    if (cam == null) return false;
                    break;
            }
            rt.GetWorldCorners(Corners);
            float x0 = float.MaxValue, y0 = float.MaxValue, x1 = float.MinValue, y1 = float.MinValue;
            for (var i = 0; i < 4; i++)
            {
                Vector2 p;
                if (root.renderMode == RenderMode.WorldSpace)
                {
                    var v = cam.WorldToScreenPoint(Corners[i]);
                    if (v.z <= 0f) return false;
                    p = v;
                }
                else p = RectTransformUtility.WorldToScreenPoint(cam, Corners[i]);
                x0 = Mathf.Min(x0, p.x); x1 = Mathf.Max(x1, p.x);
                y0 = Mathf.Min(y0, p.y); y1 = Mathf.Max(y1, p.y);
            }
            double sw = Screen.width, sh = Screen.height;
            if (sw <= 0 || sh <= 0) return false;
            x = x0 / sw;
            y = (sh - y1) / sh;
            w = (x1 - x0) / sw;
            h = (y1 - y0) / sh;
            return true;
        }

        /// <summary>The alpha of the CanvasGroups above (and on) `t`, and whether every Canvas up the chain is enabled.</summary>
        static float GroupAlpha(Transform t, out bool canvasesOn)
        {
            canvasesOn = true;
            var alpha = 1f;
            var groupsDone = false;
            var groups = new List<CanvasGroup>();
            var canvases = new List<Canvas>();
            for (var p = t; p != null; p = p.parent)
            {
                p.GetComponents(canvases);
                foreach (var c in canvases)
                    if (!c.enabled) canvasesOn = false;
                if (groupsDone) continue;
                p.GetComponents(groups);
                foreach (var g in groups)
                {
                    if (!g.enabled) continue;
                    alpha *= g.alpha;
                    if (g.ignoreParentGroups) groupsDone = true;
                }
            }
            return alpha;
        }

        /// <summary>On screen: active, enabled, its canvases on, alpha above the floor up the chain, not culled, partly in
        /// the frame. `behaviour`: the component whose enabled state counts; `graphic` (may be null) adds its own alpha.</summary>
        public static bool UguiVisible(GameObject go, Behaviour behaviour, Graphic graphic, bool screenOnly)
        {
            if (go == null || !go.activeInHierarchy || (behaviour != null && !behaviour.enabled)) return false;
            var canvas = go.GetComponentInParent<Canvas>();
            if (canvas == null || !canvas.isActiveAndEnabled) return false;
            var root = canvas.rootCanvas;
            if (root.renderMode == RenderMode.ScreenSpaceOverlay && root.targetDisplay != 0) return false;
            var alpha = GroupAlpha(go.transform, out var canvasesOn);
            if (!canvasesOn) return false;
            if (graphic != null)
            {
                if (!graphic.enabled) return false;
                alpha *= graphic.color.a;
                var cr = graphic.canvasRenderer;
                if (cr != null)
                {
                    if (cr.cull) return false;
                    alpha *= cr.GetAlpha();
                }
            }
            if (alpha <= AlphaFloor) return false;
            return RectOf(go.transform as RectTransform, canvas, screenOnly, out var x, out var y, out var w, out var h) && InFrame(x, y, w, h);
        }

        static bool IsTmpPart(Graphic g)
        {
#if TASKPROBE_TMP
            return g is TMPro.TMP_SubMeshUI;
#else
            return g.GetType().Name == "TMP_SubMeshUI";
#endif
        }

        /// <summary>A Text's or TextMeshPro's text as shown; null when the graphic isn't text.</summary>
        public static string GraphicText(Graphic g)
        {
            if (g is Text t) return t.supportRichText ? Plain(t.text) : t.text;
#if TASKPROBE_TMP
            if (g is TMPro.TMP_Text tmp)
            {
                string shown = null;
                try { shown = tmp.GetParsedText(); } catch { }
                if (string.IsNullOrEmpty(shown)) shown = tmp.richText ? Plain(tmp.text) : tmp.text;
                if (shown != null && tmp.maxVisibleCharacters >= 0 && tmp.maxVisibleCharacters < shown.Length) shown = shown.Substring(0, tmp.maxVisibleCharacters);  // a typewriter reveal
                return shown ?? "";
            }
#endif
            return null;
        }

        static bool MaskHides(Graphic g)
        {
            var mask = g.GetComponent<Mask>();
            return mask != null && mask.enabled && !mask.showMaskGraphic;
        }

        static void UguiElements(List<UiElement> output)
        {
            var graphics = new List<Graphic>(UnityEngine.Object.FindObjectsByType<Graphic>(FindObjectsInactive.Exclude, FindObjectsSortMode.None));
            Find.SortByHierarchy(graphics);
            foreach (var g in graphics)
            {
                if (g == null || IsTmpPart(g) || MaskHides(g) || Probe.IsOwn(g.gameObject)) continue;
                if (!UguiVisible(g.gameObject, g, g, true)) continue;
                var e = new UiElement { Name = g.gameObject.name, Class = g.GetType().Name, Source = "ugui" };
                var text = GraphicText(g);
                if (text != null)
                {
                    if (text.Trim().Length == 0) continue;
                    e.Kind = "text";
                    e.Text = text;
                }
                else if (g is Image image)
                {
                    if (image.type == Image.Type.Filled && image.fillAmount <= 0f) continue;
                    e.Kind = image.sprite != null ? "image" : "box";
                }
                else if (g is RawImage raw) e.Kind = raw.texture != null ? "image" : "box";
                else e.Kind = "box";
                e.HasRect = RectOf((RectTransform)g.transform, g.canvas, true, out e.X, out e.Y, out e.W, out e.H);
                output.Add(e);
            }
        }
#endif

        // ---------------------------------------------------------------- UI Toolkit

#if TASKPROBE_UITK
        /// <summary>Every UIDocument's tree once (documents nested in another's tree are walked with it).</summary>
        public static IEnumerable<UIE.VisualElement> UitkRoots()
        {
            var docs = new List<UIE.UIDocument>(UnityEngine.Object.FindObjectsByType<UIE.UIDocument>(FindObjectsInactive.Exclude, FindObjectsSortMode.None));
            Find.SortByHierarchy(docs);  // a stable order from play to play
            var roots = new List<UIE.VisualElement>();
            foreach (var d in docs)
            {
                if (d == null || !d.isActiveAndEnabled || Probe.IsOwn(d.gameObject)) continue;
                var root = d.rootVisualElement;
                if (root != null && !roots.Contains(root)) roots.Add(root);
            }
            foreach (var r in roots)
            {
                var nested = false;
                foreach (var other in roots)
                    if (other != r && other.Contains(r)) nested = true;
                if (!nested) yield return r;
            }
        }

        /// <summary>Every element under `root` (itself included), shadow children too, depth first.</summary>
        public static void Walk(UIE.VisualElement root, List<UIE.VisualElement> output, int depth = 0)
        {
            if (root == null || depth > 256) return;
            output.Add(root);
            var children = root.hierarchy;
            for (var i = 0; i < children.childCount; i++) Walk(children[i], output, depth + 1);
        }

        /// <summary>Whether the element's panel is drawn on the screen (not world-space, not into a texture).</summary>
        static bool ScreenPanel(UIE.VisualElement e)
        {
            if (e.panel == null) return false;
            foreach (var d in UnityEngine.Object.FindObjectsByType<UIE.UIDocument>(FindObjectsInactive.Exclude, FindObjectsSortMode.None))
            {
                if (d.rootVisualElement == null || d.rootVisualElement.panel != e.panel) continue;
                var settings = d.panelSettings;
                if (settings == null) return false;
                return settings.renderMode == UIE.PanelRenderMode.ScreenSpaceOverlay && settings.targetTexture == null && settings.targetDisplay == 0;
            }
            return true;
        }

        /// <summary>An element's rectangle in viewport fractions: its panel's coordinates scaled to the frame.</summary>
        public static bool RectOf(UIE.VisualElement e, out double x, out double y, out double w, out double h)
        {
            x = y = w = h = 0.0;
            if (e?.panel == null) return false;
            var whole = e.panel.visualTree.worldBound;
            var b = e.worldBound;
            if (!(whole.width > 0f) || !(whole.height > 0f) || float.IsNaN(b.x) || float.IsNaN(b.width)) return false;
            x = (b.x - whole.x) / whole.width;
            y = (b.y - whole.y) / whole.height;
            w = b.width / whole.width;
            h = b.height / whole.height;
            return true;
        }

        /// <summary>Displayed, visible, of an opacity above the floor up the chain, in a screen panel, partly in the frame.</summary>
        public static bool UitkVisible(UIE.VisualElement e, bool checkPanel = true)
        {
            if (e?.panel == null) return false;
            var opacity = 1f;
            for (var p = e; p != null; p = p.hierarchy.parent)
            {
                var s = p.resolvedStyle;
                if (s.display == UIE.DisplayStyle.None || s.visibility != UIE.Visibility.Visible) return false;
                opacity *= s.opacity;
            }
            if (opacity <= AlphaFloor) return false;
            if (checkPanel && !ScreenPanel(e)) return false;
            return RectOf(e, out var x, out var y, out var w, out var h) && InFrame(x, y, w, h);
        }

        static UnityEngine.Object BackgroundAsset(UIE.Background b)
        {
            if (b.texture != null) return b.texture;
            if (b.sprite != null) return b.sprite;
            if (b.renderTexture != null) return b.renderTexture;
            if (b.vectorImage != null) return b.vectorImage;
            return null;
        }

        /// <summary>The image an element shows: an Image element's, else its background image; null when none.</summary>
        public static UnityEngine.Object UitkBrush(UIE.VisualElement e)
        {
            if (e is UIE.Image im)
            {
                if (im.image != null) return im.image;
                if (im.sprite != null) return im.sprite;
                if (im.vectorImage != null) return im.vectorImage;
            }
            return BackgroundAsset(e.resolvedStyle.backgroundImage);
        }

        public static string UitkText(UIE.VisualElement e)
        {
            if (e is UIE.TextField field) return field.value;
            if (e is UIE.TextElement t) return t.text;
            return null;
        }

        static void UitkElements(List<UiElement> output)
        {
            var all = new List<UIE.VisualElement>();
            foreach (var root in UitkRoots())
            {
                if (!ScreenPanel(root)) continue;
                all.Clear();
                Walk(root, all);
                foreach (var e in all)
                {
                    if (!UitkVisible(e, false)) continue;
                    var s = e.resolvedStyle;
                    var name = string.IsNullOrEmpty(e.name) ? e.GetType().Name : e.name;
                    var cls = e.GetType().Name;
                    RectOf(e, out var x, out var y, out var w, out var h);
                    // what it paints behind: an image, else a background colour or a border (a box)
                    string paint = null;
                    if (UitkBrush(e) != null) paint = "image";
                    else if (s.backgroundColor.a > AlphaFloor) paint = "box";
                    else if ((s.borderLeftWidth > 0f && s.borderLeftColor.a > AlphaFloor) || (s.borderRightWidth > 0f && s.borderRightColor.a > AlphaFloor) ||
                             (s.borderTopWidth > 0f && s.borderTopColor.a > AlphaFloor) || (s.borderBottomWidth > 0f && s.borderBottomColor.a > AlphaFloor))
                        paint = "box";
                    if (paint != null)
                        output.Add(new UiElement { Name = name, Class = cls, Source = "uitk", Kind = paint, HasRect = true, X = x, Y = y, W = w, H = h });
                    // a TextElement with text is also a text element (a uGUI button is a box and a text too)
                    if (e is UIE.TextElement te && !string.IsNullOrEmpty(te.text) && te.text.Trim().Length > 0 && s.color.a > AlphaFloor)
                        output.Add(new UiElement { Name = name, Class = cls, Source = "uitk", Kind = "text", Text = te.enableRichText ? Plain(te.text) : te.text, HasRect = true, X = x, Y = y, W = w, H = h });
                }
            }
        }
#endif

        // ---------------------------------------------------------------- widgets

        /// <summary>The widgets a select picks: uGUI objects in hierarchy order, then UI Toolkit elements in tree order.
        /// `component`: a type name the object's components or the element's type (or a base type) must carry; `name`:
        /// a wildcard on the object's or element's name; `text`: a regex its text must match; `visible`: on screen only.</summary>
        public static List<UiWidget> Widgets(string component, string name, Regex text, bool visibleOnly)
        {
            var found = new List<UiWidget>();
#if TASKPROBE_UGUI
            UguiWidgets(component, name, text, visibleOnly, found);
#endif
#if TASKPROBE_UITK
            UitkWidgets(component, name, text, visibleOnly, found);
#endif
            return found;
        }

#if TASKPROBE_UGUI
        static void UguiWidgets(string component, string name, Regex text, bool visibleOnly, List<UiWidget> found)
        {
            // the objects that carry a graphic or a selectable, and those carrying the asked type when it is another kind
            // of component (a game's own HUD script)
            var seen = new HashSet<GameObject>();
            var candidates = new List<Transform>();
            void Take(Component c)
            {
                if (c == null || Probe.IsOwn(c.gameObject) || !seen.Add(c.gameObject)) return;
                if (c.GetComponentInParent<Canvas>(true) == null) return;
                candidates.Add(c.transform);
            }
            foreach (var g in UnityEngine.Object.FindObjectsByType<Graphic>(FindObjectsInactive.Include, FindObjectsSortMode.None))
                if (!IsTmpPart(g)) Take(g);
            foreach (var s in UnityEngine.Object.FindObjectsByType<Selectable>(FindObjectsInactive.Include, FindObjectsSortMode.None)) Take(s);
            if (!string.IsNullOrEmpty(component))
            {
                var type = Reflect.TypeNamed(component);
                if (type != null && typeof(Component).IsAssignableFrom(type) && !typeof(Graphic).IsAssignableFrom(type) && !typeof(Selectable).IsAssignableFrom(type))
                    foreach (var o in UnityEngine.Object.FindObjectsByType(type, FindObjectsInactive.Include, FindObjectsSortMode.None))
                        Take(o as Component);
            }
            Find.SortByHierarchy(candidates);
            var comps = new List<Component>();
            foreach (var t in candidates)
            {
                if (t == null) continue;
                var go = t.gameObject;
                if (name != null && !Find.Wild(name, go.name)) continue;
                Component matched = null;
                if (!string.IsNullOrEmpty(component))
                {
                    go.GetComponents(comps);
                    foreach (var c in comps)
                        if (c != null && Reflect.IsA(c.GetType(), component)) { matched = c; break; }
                    if (matched == null) continue;
                }
                var w = new UguiWidget(go, matched);
                if (text != null)
                {
                    var shown = w.Text();
                    if (shown == null || !text.IsMatch(shown)) continue;
                }
                if (visibleOnly && !w.Visible()) continue;
                found.Add(w);
            }
        }

        sealed class UguiWidget : UiWidget
        {
            readonly GameObject go;
            readonly Selectable selectable;
            readonly Graphic graphic;  // its own text if it has one, else its first graphic
            readonly Component main;

            public UguiWidget(GameObject go, Component matched)
            {
                this.go = go;
                selectable = go.GetComponent<Selectable>();
                Graphic text = null, first = null;
                foreach (var g in go.GetComponents<Graphic>())
                {
                    if (IsTmpPart(g)) continue;
                    if (first == null) first = g;
                    if (text == null && GraphicText(g) != null) text = g;
                }
                graphic = text ?? first;
                main = matched != null ? matched : selectable != null ? selectable : (Component)graphic;
                Name = go.name;
                Class = main != null ? main.GetType().Name : "GameObject";
            }

            public override bool Visible()
            {
                var behaviour = main as Behaviour;
                return UguiVisible(go, behaviour, graphic, false);
            }

            public override string Text()
            {
                var own = graphic != null ? GraphicText(graphic) : null;
                if (own != null) return own;
                if (selectable == null) return null;
                // a button's or toggle's label: its first text below it
                foreach (var g in go.GetComponentsInChildren<Graphic>(true))
                {
                    if (g.gameObject == go) continue;
                    var label = GraphicText(g);
                    if (label != null) return label;
                }
                return null;
            }

            public override object Field(string f)
            {
                switch (f)
                {
                    case "count": return 1.0;
                    case "visible": return Visible() ? 1.0 : 0.0;
                    case "text": return Text();
                    case "percent":
                        if (go.GetComponent<Slider>() is Slider slider) return (double)slider.normalizedValue;
                        if (go.GetComponent<Scrollbar>() is Scrollbar bar) return (double)bar.value;
                        if (go.GetComponent<Image>() is Image fill && fill.type == Image.Type.Filled) return (double)fill.fillAmount;
                        return null;
                    case "value":
                        if (go.GetComponent<Slider>() is Slider s) return (double)s.value;
                        if (go.GetComponent<Toggle>() is Toggle toggle) return toggle.isOn ? 1.0 : 0.0;
                        if (go.GetComponent<Scrollbar>() is Scrollbar sb) return (double)sb.value;
                        if (go.GetComponent<Dropdown>() is Dropdown dd) return (double)dd.value;
#if TASKPROBE_TMP
                        if (go.GetComponent<TMPro.TMP_Dropdown>() is TMPro.TMP_Dropdown tdd) return (double)tdd.value;
#endif
                        return null;
                    case "interactable":
                        return selectable != null ? (selectable.IsInteractable() && selectable.enabled ? 1.0 : 0.0) : (object)null;
                    case "has_brush":
                    case "brush":
                        UnityEngine.Object brush = null;
                        var known = false;
                        if (go.GetComponent<Image>() is Image image) { brush = image.sprite; known = true; }
                        else if (go.GetComponent<RawImage>() is RawImage raw) { brush = raw.texture; known = true; }
                        if (!known) return null;
                        if (f == "has_brush") return brush != null ? 1.0 : 0.0;
                        return brush != null ? brush.name : null;
                }
                if (IsRectField(f))
                {
                    var canvas = go.GetComponentInParent<Canvas>(true);
                    if (!RectOf(go.transform as RectTransform, canvas, false, out var x, out var y, out var w, out var h) || (w <= 0.0 && h <= 0.0)) return null;  // not laid out
                    return f == "x" ? x : f == "y" ? y : f == "w" ? w : h;
                }
                return null;
            }
        }
#endif

#if TASKPROBE_UITK
        static void UitkWidgets(string component, string name, Regex text, bool visibleOnly, List<UiWidget> found)
        {
            var all = new List<UIE.VisualElement>();
            foreach (var root in UitkRoots()) Walk(root, all);
            foreach (var e in all)
            {
                if (!string.IsNullOrEmpty(component) && !Reflect.IsA(e.GetType(), component)) continue;
                if (name != null && !Find.Wild(name, e.name ?? "")) continue;
                if (text != null)
                {
                    var shown = UitkText(e);
                    if (shown == null || !text.IsMatch(shown)) continue;
                }
                if (visibleOnly && !UitkVisible(e)) continue;
                found.Add(new UitkWidget(e));
            }
        }

        sealed class UitkWidget : UiWidget
        {
            readonly UIE.VisualElement e;

            public UitkWidget(UIE.VisualElement e)
            {
                this.e = e;
                Name = string.IsNullOrEmpty(e.name) ? e.GetType().Name : e.name;
                Class = e.GetType().Name;
            }

            public override bool Visible() => UitkVisible(e);
            public override string Text() => UitkText(e);

            static double Share(double value, double low, double high) => high != low ? (value - low) / (high - low) : 0.0;

            public override object Field(string f)
            {
                switch (f)
                {
                    case "count": return 1.0;
                    case "visible": return Visible() ? 1.0 : 0.0;
                    case "text": return Text();
                    case "percent":
                        if (e is UIE.AbstractProgressBar pb) return Share(pb.value, pb.lowValue, pb.highValue);
                        if (e is UIE.Slider sl) return Share(sl.value, sl.lowValue, sl.highValue);
                        if (e is UIE.SliderInt si) return Share(si.value, si.lowValue, si.highValue);
                        if (e is UIE.Scroller sc) return Share(sc.value, sc.lowValue, sc.highValue);
                        return null;
                    case "value":
                        if (e is UIE.Slider s) return (double)s.value;
                        if (e is UIE.SliderInt sInt) return (double)sInt.value;
                        if (e is UIE.Toggle t) return t.value ? 1.0 : 0.0;
                        if (e is UIE.AbstractProgressBar bar) return (double)bar.value;
                        if (e is UIE.Scroller scr) return (double)scr.value;
                        return null;
                    case "interactable": return e.enabledInHierarchy ? 1.0 : 0.0;
                    case "has_brush": return UitkBrush(e) != null ? 1.0 : 0.0;
                    case "brush":
                        var brush = UitkBrush(e);
                        return brush != null ? brush.name : null;
                }
                if (IsRectField(f))
                {
                    if (!RectOf(e, out var x, out var y, out var w, out var h) || (w <= 0.0 && h <= 0.0)) return null;  // not laid out (display: none)
                    return f == "x" ? x : f == "y" ? y : f == "w" ? w : h;
                }
                return null;
            }
        }
#endif

        // ---------------------------------------------------------------- widget click

        /// <summary>Clicks the first visible, interactable uGUI Selectable whose object's name matches `want` (a wildcard)
        /// or whose type is named `want`, else such a UI Toolkit Button: as a player's click fires it. False when none.</summary>
        public static bool Click(string want)
        {
#if TASKPROBE_UGUI
            var selectables = new List<Selectable>(UnityEngine.Object.FindObjectsByType<Selectable>(FindObjectsInactive.Exclude, FindObjectsSortMode.None));
            Find.SortByHierarchy(selectables);
            foreach (var s in selectables)
            {
                if (s == null || Probe.IsOwn(s.gameObject)) continue;
                if (!Find.Wild(want, s.gameObject.name) && !Reflect.IsA(s.GetType(), want)) continue;
                if (!s.IsInteractable() || !UguiVisible(s.gameObject, s, s.targetGraphic != null && s.targetGraphic.gameObject == s.gameObject ? s.targetGraphic : null, false)) continue;
                UguiClick(s);
                return true;
            }
#endif
#if TASKPROBE_UITK
            var all = new List<UIE.VisualElement>();
            foreach (var root in UitkRoots()) Walk(root, all);
            foreach (var e in all)
            {
                if (!(e is UIE.Button button)) continue;
                if (!Find.Wild(want, e.name ?? "") && !Reflect.IsA(e.GetType(), want)) continue;
                if (!e.enabledInHierarchy || !UitkVisible(e)) continue;
                // a submit is what Button reacts to with its clicked (Clickable.SimulateSingleClick), as a keyboard or pad press does
                using (var submit = UIE.NavigationSubmitEvent.GetPooled())
                {
                    submit.target = button;
                    button.SendEvent(submit);
                }
                return true;
            }
#endif
            return false;
        }

#if TASKPROBE_UGUI
        /// <summary>A pointer enter, down, up and click on the selectable's object, at its centre, through ExecuteEvents: the
        /// events an input module sends for a click, so onClick, toggles and custom IPointer*Handlers react.</summary>
        static void UguiClick(Selectable s)
        {
            var go = s.gameObject;
            var system = EventSystem.current;
            var data = new PointerEventData(system) { button = PointerEventData.InputButton.Left, clickCount = 1, clickTime = Time.unscaledTime };
            var canvas = go.GetComponentInParent<Canvas>();
            if (RectOf(go.transform as RectTransform, canvas, false, out var x, out var y, out var w, out var h))
                data.position = new Vector2((float)((x + w / 2) * Screen.width), (float)((1.0 - (y + h / 2)) * Screen.height));
            data.pressPosition = data.position;
            data.pointerEnter = go;
            data.pointerCurrentRaycast = data.pointerPressRaycast = new RaycastResult { gameObject = go, module = canvas != null ? canvas.GetComponent<BaseRaycaster>() : null, screenPosition = data.position };
            ExecuteEvents.ExecuteHierarchy(go, data, ExecuteEvents.pointerEnterHandler);
            var pressed = ExecuteEvents.ExecuteHierarchy(go, data, ExecuteEvents.pointerDownHandler);
            var clickHandler = ExecuteEvents.GetEventHandler<IPointerClickHandler>(go);
            if (pressed == null) pressed = clickHandler;
            data.pointerPress = pressed;
            data.rawPointerPress = go;
            data.eligibleForClick = true;
            if (system != null && pressed != null) system.SetSelectedGameObject(pressed, data);
            ExecuteEvents.Execute(pressed, data, ExecuteEvents.pointerUpHandler);
            if (clickHandler != null && clickHandler == pressed) ExecuteEvents.Execute(clickHandler, data, ExecuteEvents.pointerClickHandler);
            data.eligibleForClick = false;
            data.pointerPress = null;
        }
#endif
    }
}
