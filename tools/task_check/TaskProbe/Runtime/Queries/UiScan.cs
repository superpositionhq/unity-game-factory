// The UI as the widgets and ui queries read it (contract section 3): uGUI (UnityEngine.UI graphics and selectables,
// TextMeshPro) on the scene's canvases, and UI Toolkit (every UIDocument's panel); and the widget click input.
// Rectangles are viewport fractions 0-1 with y down from the top, whatever render mode, scaler or panel scale placed
// them. On screen means: drawn (active, enabled, every Canvas up the chain enabled, an alpha above 0.004 all the way
// up: CanvasGroups, the graphic's colour, its CanvasRenderer, not culled by a RectMask2D; in UI Toolkit displayed,
// visible and of an opacity above 0.004 down the tree, in a panel drawn on the screen) and of some size inside the
// frame.
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
    /// <summary>One element of the UI on screen (a ui row): its source (ugui, uitk, ocr), kind (text, box, image), name
    /// and class (for the logs), text, and its rectangle in viewport fractions.</summary>
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
        const float AlphaFloor = 0.004f;  // an element drawn at this alpha or less is not on screen
        static readonly Regex Tags = new Regex(@"</?[A-Za-z_#][^<>]*>|</>", RegexOptions.CultureInvariant);

        /// <summary>Rich text as shown: its tags left out.</summary>
        static string Plain(string marked) => string.IsNullOrEmpty(marked) || marked.IndexOf('<') < 0 ? marked : Tags.Replace(marked, "");

        public static bool IsRectField(string f) => f == "x" || f == "y" || f == "w" || f == "h";

        /// <summary>A rectangle with a size that lies at least partly inside the frame.</summary>
        static bool OnScreen(double x, double y, double w, double h) => w > 0.0 && h > 0.0 && x + w > 0.0 && x < 1.0 && y + h > 0.0 && y < 1.0;

        static object RectField(string f, double x, double y, double w, double h) => f == "x" ? x : f == "y" ? y : f == "w" ? w : h;

        // ---------------------------------------------------------------- elements on screen (ui)

        static int scannedStamp = -1;
        static readonly List<UiElement> Scanned = new List<UiElement>();

        /// <summary>Every element on screen now, once a pass (every ui query of the frame drawn reads the same).</summary>
        public static List<UiElement> Elements()
        {
            if (scannedStamp == Probe.Stamp) return Scanned;
            scannedStamp = Probe.Stamp;
            Scanned.Clear();
#if TASKPROBE_UGUI
            try { UguiElements(Scanned); }
            catch (Exception e) { Probe.Active?.Failed("ui: the uGUI canvases couldn't be read: {0}", e); }
#endif
#if TASKPROBE_UITK
            try { UitkElements(Scanned); }
            catch (Exception e) { Probe.Active?.Failed("ui: the UI Toolkit panels couldn't be read: {0}", e); }
#endif
            return Scanned;
        }

        // ---------------------------------------------------------------- uGUI

#if TASKPROBE_UGUI
        static readonly Vector3[] Corners = new Vector3[4];
        static readonly List<Canvas> CanvasesUp = new List<Canvas>();
        static readonly List<CanvasGroup> GroupsUp = new List<CanvasGroup>();

        /// <summary>A RectTransform's rectangle in viewport fractions (y down). A world-space canvas (when `screenOnly` is
        /// false) projects through the player's camera; false when a corner is behind it. False for a canvas drawn
        /// into a texture or on another display: it isn't on the screen.</summary>
        static bool RectOf(RectTransform rt, Canvas canvas, bool screenOnly, out double x, out double y, out double w, out double h)
        {
            x = y = w = h = 0.0;
            if (rt == null || canvas == null) return false;
            var root = canvas.rootCanvas;
            Camera cam = null;
            switch (root.renderMode)
            {
                case RenderMode.ScreenSpaceOverlay:
                    if (root.targetDisplay != 0) return false;
                    break;
                case RenderMode.ScreenSpaceCamera:
                    cam = root.worldCamera;  // none: drawn as an overlay
                    if (cam != null && (cam.targetTexture != null || cam.targetDisplay != 0)) return false;
                    break;
                default:
                    if (screenOnly) return false;
                    cam = Probe.Active != null ? Probe.Active.View : null;
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

        /// <summary>Drawn on screen: active, every Canvas up the chain enabled, an alpha above the floor up the chain
        /// (CanvasGroups until one ignores its parents; `graphic`'s own colour and CanvasRenderer when it has one, which
        /// must be enabled and not culled), with a rectangle on screen.</summary>
        static bool UguiVisible(GameObject go, Graphic graphic, bool screenOnly)
        {
            if (go == null || !go.activeInHierarchy) return false;
            var canvas = go.GetComponentInParent<Canvas>();
            if (canvas == null) return false;
            var alpha = 1f;
            var groupsDone = false;
            for (var p = go.transform; p != null; p = p.parent)
            {
                p.GetComponents(CanvasesUp);
                foreach (var c in CanvasesUp)
                    if (!c.enabled) return false;
                if (groupsDone) continue;
                p.GetComponents(GroupsUp);
                foreach (var g in GroupsUp)
                {
                    if (!g.enabled) continue;
                    alpha *= g.alpha;
                    if (g.ignoreParentGroups) groupsDone = true;
                }
            }
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
            return alpha > AlphaFloor && RectOf(go.transform as RectTransform, canvas, screenOnly, out var x, out var y, out var w, out var h)
                && OnScreen(x, y, w, h);
        }

        static bool IsTmpPart(Graphic g)
        {
#if TASKPROBE_TMP
            return g is TMPro.TMP_SubMeshUI;
#else
            return false;
#endif
        }

        /// <summary>A Text's or TextMeshPro's text as shown: rich text tags left out, a TextMeshPro typewriter
        /// (maxVisibleCharacters) applied. The text as set, not as TextMeshPro last laid it out: that is a frame old
        /// until the frame is drawn, and never laid out again while the text is hidden. Null when not text.</summary>
        static string GraphicText(Graphic g)
        {
            if (g is Text t) return t.supportRichText ? Plain(t.text) : t.text;
#if TASKPROBE_TMP
            if (g is TMPro.TMP_Text tmp)
            {
                // a TextMeshPro input field puts a zero-width space after the typed text to place its caret
                var shown = ((tmp.richText ? Plain(tmp.text) : tmp.text) ?? "").Replace("\u200B", "");
                return tmp.maxVisibleCharacters >= 0 && tmp.maxVisibleCharacters < shown.Length ? shown.Substring(0, tmp.maxVisibleCharacters) : shown;
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
                if (!UguiVisible(g.gameObject, g, true)) continue;
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
        /// <summary>Every UIDocument's tree once (a document nested in another's tree is walked with it), in hierarchy
        /// order, and whether its panel is drawn on the screen.</summary>
        static List<KeyValuePair<UIE.VisualElement, bool>> UitkRoots()
        {
            var docs = new List<UIE.UIDocument>(UnityEngine.Object.FindObjectsByType<UIE.UIDocument>(FindObjectsInactive.Exclude, FindObjectsSortMode.None));
            Find.SortByHierarchy(docs);
            var roots = new List<KeyValuePair<UIE.VisualElement, bool>>();
            foreach (var d in docs)
            {
                if (d == null || !d.isActiveAndEnabled || Probe.IsOwn(d.gameObject)) continue;
                var root = d.rootVisualElement;
                if (root == null || roots.Exists(r => r.Key == root)) continue;
                // drawn on the screen: not in world space, not into a texture, on the first display
                var settings = d.panelSettings;
                var onScreen = settings != null && settings.renderMode == UIE.PanelRenderMode.ScreenSpaceOverlay && settings.targetTexture == null
                    && settings.targetDisplay == 0;
                roots.Add(new KeyValuePair<UIE.VisualElement, bool>(root, onScreen));
            }
            var top = new List<KeyValuePair<UIE.VisualElement, bool>>();
            foreach (var r in roots)
                if (!roots.Exists(o => o.Key != r.Key && o.Key.Contains(r.Key))) top.Add(r);
            return top;
        }

        /// <summary>Every element under `root` (itself included), shadow children too, depth first.</summary>
        static void Walk(UIE.VisualElement root, List<UIE.VisualElement> output, int depth = 0)
        {
            if (root == null || depth > 256) return;
            output.Add(root);
            var children = root.hierarchy;
            for (var i = 0; i < children.childCount; i++) Walk(children[i], output, depth + 1);
        }

        /// <summary>An element's rectangle in viewport fractions: its panel's coordinates over the panel's own size (its
        /// scale mode left out).</summary>
        static bool RectOf(UIE.VisualElement e, out double x, out double y, out double w, out double h)
        {
            x = y = w = h = 0.0;
            if (e?.panel == null) return false;
            var whole = e.panel.visualTree.worldBound;
            var b = e.worldBound;
            if (!(whole.width > 0f) || !(whole.height > 0f) || float.IsNaN(b.x) || float.IsNaN(b.y) || float.IsNaN(b.width) || float.IsNaN(b.height))
                return false;
            x = (b.x - whole.x) / whole.width;
            y = (b.y - whole.y) / whole.height;
            w = b.width / whole.width;
            h = b.height / whole.height;
            return true;
        }

        /// <summary>Drawn on screen, in a panel on the screen (`onScreen`): displayed all the way up (display: none takes
        /// an element and everything under it out), visible (visibility is inherited, and a child may be visible again
        /// under a hidden parent: its own resolved value decides), of an opacity above the floor down the tree, with a
        /// rectangle on screen.</summary>
        static bool UitkVisible(UIE.VisualElement e, bool onScreen)
        {
            if (!onScreen || e?.panel == null || e.resolvedStyle.visibility != UIE.Visibility.Visible) return false;
            var opacity = 1f;
            for (var p = e; p != null; p = p.hierarchy.parent)
            {
                var s = p.resolvedStyle;
                if (s.display == UIE.DisplayStyle.None) return false;
                opacity *= s.opacity;
            }
            return opacity > AlphaFloor && RectOf(e, out var x, out var y, out var w, out var h) && OnScreen(x, y, w, h);
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
        static UnityEngine.Object UitkBrush(UIE.VisualElement e)
        {
            if (e is UIE.Image im)
            {
                if (im.image != null) return im.image;
                if (im.sprite != null) return im.sprite;
                if (im.vectorImage != null) return im.vectorImage;
            }
            return BackgroundAsset(e.resolvedStyle.backgroundImage);
        }

        /// <summary>An element's text as shown: a field's string value (a TextField's, a DropdownField's caption), a
        /// Toggle's text, a TextElement's text with its rich text tags left out; null when it has none.</summary>
        static string UitkText(UIE.VisualElement e)
        {
            if (e is UIE.BaseField<string> field) return field.value;
            if (e is UIE.Toggle toggle) return Plain(toggle.text);
            if (e is UIE.TextElement t) return t.enableRichText ? Plain(t.text) : t.text;
            return null;
        }

        /// <summary>The name a row shows and a select's name matches: the element's, else its type's.</summary>
        static string NameOf(UIE.VisualElement e) => string.IsNullOrEmpty(e.name) ? e.GetType().Name : e.name;

        static void UitkElements(List<UiElement> output)
        {
            var all = new List<UIE.VisualElement>();
            foreach (var root in UitkRoots())
            {
                if (!root.Value) continue;
                all.Clear();
                Walk(root.Key, all);
                foreach (var e in all)
                {
                    if (!UitkVisible(e, true)) continue;
                    var s = e.resolvedStyle;
                    var name = NameOf(e);
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
                    // a TextElement with text is also a text element (a uGUI button is a box and a text too); an empty
                    // field shows its placeholder
                    if (!(e is UIE.TextElement te) || !(s.color.a > AlphaFloor)) continue;
                    var text = te.enableRichText ? Plain(te.text) : te.text;
                    if (string.IsNullOrEmpty(text)) text = ((UIE.ITextEdition)te).placeholder;
                    if (!string.IsNullOrEmpty(text) && text.Trim().Length > 0)
                        output.Add(new UiElement { Name = name, Class = cls, Source = "uitk", Kind = "text", Text = text, HasRect = true, X = x, Y = y, W = w, H = h });
                }
            }
        }
#endif

        // ---------------------------------------------------------------- widgets

        /// <summary>The widgets a select picks: uGUI objects in hierarchy order, then UI Toolkit elements in tree order.
        /// `component`: a type name a component of the object, or the element (a base type included), carries; `name`:
        /// a wildcard on the object's or element's name; `text`: a regex its text must match; `visible`: on screen
        /// only.</summary>
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
            var type = string.IsNullOrEmpty(component) ? null : Reflect.TypeNamed(component);
            // no type of that name, or a class no component derives from (a UI Toolkit element's): no uGUI object has it
            if (!string.IsNullOrEmpty(component) && (type == null || (!type.IsInterface && !typeof(Component).IsAssignableFrom(type)))) return;
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
            if (type != null && typeof(Component).IsAssignableFrom(type) && !typeof(Graphic).IsAssignableFrom(type) && !typeof(Selectable).IsAssignableFrom(type))
                foreach (var o in UnityEngine.Object.FindObjectsByType(type, FindObjectsInactive.Include, FindObjectsSortMode.None))
                    Take(o as Component);
            Find.SortByHierarchy(candidates);
            foreach (var t in candidates)
            {
                if (t == null) continue;
                var go = t.gameObject;
                if (name != null && !Find.Wild(name, go.name)) continue;
                Component matched = null;
                if (!string.IsNullOrEmpty(component))
                {
                    matched = Reflect.ComponentNamed(go, component, false);
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

        /// <summary>Whether everything from `t` up to (not including) `top` is active itself: shown whenever `top` is.</summary>
        static bool ActiveBelow(Transform t, Transform top)
        {
            for (var p = t; p != null && p != top; p = p.parent)
                if (!p.gameObject.activeSelf) return false;
            return true;
        }

        sealed class UguiWidget : UiWidget
        {
            readonly GameObject go;
            readonly Selectable selectable;
            readonly Graphic graphic;  // its own text if it has one, else its first graphic

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
                var main = matched != null ? matched : selectable != null ? selectable : (Component)graphic;
                Name = go.name;
                Class = main != null ? main.GetType().Name : "GameObject";
            }

            public override bool Visible() => UguiVisible(go, graphic, false);

            public override string Text()
            {
                var own = graphic != null ? GraphicText(graphic) : null;
                if (own != null) return own;
                // an input field's text is what was typed (its placeholder is a label of its own)
                if (selectable is InputField field) return field.text;
#if TASKPROBE_TMP
                if (selectable is TMPro.TMP_InputField tmpField) return tmpField.text;
#endif
                if (selectable == null) return null;
                // a button's or toggle's label: the first text below it that shows with it (enabled, active below it)
                foreach (var g in go.GetComponentsInChildren<Graphic>(true))
                {
                    if (g.gameObject == go || !g.enabled || !ActiveBelow(g.transform, go.transform)) continue;
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
                        UnityEngine.Object brush;
                        if (go.GetComponent<Image>() is Image image) brush = image.sprite;
                        else if (go.GetComponent<RawImage>() is RawImage raw) brush = raw.texture;
                        else return null;
                        if (f == "has_brush") return brush != null ? 1.0 : 0.0;
                        return brush != null ? brush.name : null;
                }
                if (IsRectField(f))
                {
                    // no value before it is laid out (no size)
                    if (!RectOf(go.transform as RectTransform, go.GetComponentInParent<Canvas>(true), false, out var x, out var y, out var w, out var h) ||
                        (w <= 0.0 && h <= 0.0))
                        return null;
                    return RectField(f, x, y, w, h);
                }
                return null;
            }
        }
#endif

#if TASKPROBE_UITK
        static void UitkWidgets(string component, string name, Regex text, bool visibleOnly, List<UiWidget> found)
        {
            var all = new List<UIE.VisualElement>();
            foreach (var root in UitkRoots())
            {
                all.Clear();
                Walk(root.Key, all);
                foreach (var e in all)
                {
                    if (!string.IsNullOrEmpty(component) && !Reflect.IsA(e.GetType(), component)) continue;
                    if (name != null && !Find.Wild(name, NameOf(e))) continue;
                    if (text != null)
                    {
                        var shown = UitkText(e);
                        if (shown == null || !text.IsMatch(shown)) continue;
                    }
                    if (visibleOnly && !UitkVisible(e, root.Value)) continue;
                    found.Add(new UitkWidget(e, root.Value));
                }
            }
        }

        sealed class UitkWidget : UiWidget
        {
            readonly UIE.VisualElement e;
            readonly bool onScreen;  // its panel is drawn on the screen

            public UitkWidget(UIE.VisualElement e, bool onScreen)
            {
                this.e = e;
                this.onScreen = onScreen;
                Name = NameOf(e);
                Class = e.GetType().Name;
            }

            public override bool Visible() => UitkVisible(e, onScreen);
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
                        if (e is UIE.DropdownField dd) return (double)dd.index;
                        return null;
                    case "interactable": return e.enabledInHierarchy ? 1.0 : 0.0;
                    case "has_brush": return UitkBrush(e) != null ? 1.0 : 0.0;
                    case "brush":
                        var brush = UitkBrush(e);
                        return brush != null ? brush.name : null;
                }
                if (IsRectField(f))
                {
                    // no value before it is laid out (no size, display: none), nor in a panel off the screen
                    if (!onScreen || !RectOf(e, out var x, out var y, out var w, out var h) || (w <= 0.0 && h <= 0.0)) return null;
                    return RectField(f, x, y, w, h);
                }
                return null;
            }
        }
#endif

        // ---------------------------------------------------------------- widget click

        /// <summary>Clicks the first visible, interactable uGUI Selectable whose object's name matches `want` (a wildcard)
        /// or whose type is named `want`, else such a UI Toolkit Button: as a player's click fires it (the original's
        /// FindButton and its pressed, released, clicked). No raycast: an image over it doesn't stop it. False when
        /// none.</summary>
        public static bool Click(string want)
        {
#if TASKPROBE_UGUI
            var selectables = new List<Selectable>(UnityEngine.Object.FindObjectsByType<Selectable>(FindObjectsInactive.Exclude, FindObjectsSortMode.None));
            Find.SortByHierarchy(selectables);
            foreach (var s in selectables)
            {
                if (s == null || Probe.IsOwn(s.gameObject)) continue;
                if (!Find.Wild(want, s.gameObject.name) && !Reflect.IsA(s.GetType(), want)) continue;
                var own = s.targetGraphic != null && s.targetGraphic.gameObject == s.gameObject ? s.targetGraphic : null;
                if (!s.isActiveAndEnabled || !s.IsInteractable() || !UguiVisible(s.gameObject, own, false)) continue;
                UguiClick(s);
                return true;
            }
#endif
#if TASKPROBE_UITK
            var all = new List<UIE.VisualElement>();
            foreach (var root in UitkRoots())
            {
                all.Clear();
                Walk(root.Key, all);
                foreach (var e in all)
                {
                    if (!(e is UIE.Button button)) continue;
                    if (!Find.Wild(want, NameOf(e)) && !Reflect.IsA(e.GetType(), want)) continue;
                    if (!e.enabledInHierarchy || !UitkVisible(e, root.Value)) continue;
                    // a submit is what Button reacts to with its clicked (Clickable.SimulateSingleClick), as a keyboard or
                    // pad press does; a ClickEvent callback needs a pointer's click (the cursor)
                    using (var submit = UIE.NavigationSubmitEvent.GetPooled())
                    {
                        submit.target = button;
                        button.SendEvent(submit);
                    }
                    return true;
                }
            }
#endif
            return false;
        }

#if TASKPROBE_UGUI
        /// <summary>A pointer's click at the selectable's centre as the Input System's UI module makes it, through
        /// ExecuteEvents: the pointer enters; the press lets go of a selection the pressed object wouldn't take, then
        /// pointer down and the start of a possible drag; the release pointer up and click. onClick, toggles, EventTrigger
        /// entries and a game's own IPointer*Handlers react as to a player's click.</summary>
        static void UguiClick(Selectable s)
        {
            var go = s.gameObject;
            var events = EventSystem.current;
            var canvas = go.GetComponentInParent<Canvas>();
            var data = new PointerEventData(events) { button = PointerEventData.InputButton.Left };
            if (RectOf(go.transform as RectTransform, canvas, false, out var x, out var y, out var w, out var h))
                data.position = new Vector2((float)((x + w / 2) * Screen.width), (float)((1.0 - (y + h / 2)) * Screen.height));
            data.pointerCurrentRaycast = new RaycastResult
            {
                gameObject = go, module = canvas != null ? canvas.GetComponent<BaseRaycaster>() : null, screenPosition = data.position,
            };
            ExecuteEvents.ExecuteHierarchy(go, data, ExecuteEvents.pointerEnterHandler);
            data.pointerEnter = go;

            data.eligibleForClick = true;
            data.delta = Vector2.zero;
            data.dragging = false;
            data.useDragThreshold = true;
            data.pressPosition = data.position;
            data.pointerPressRaycast = data.pointerCurrentRaycast;
            if (events != null && ExecuteEvents.GetEventHandler<ISelectHandler>(go) != events.currentSelectedGameObject)
                events.SetSelectedGameObject(null, data);
            var pressed = ExecuteEvents.ExecuteHierarchy(go, data, ExecuteEvents.pointerDownHandler);
            var clicked = ExecuteEvents.GetEventHandler<IPointerClickHandler>(go);
            data.pointerPress = pressed != null ? pressed : clicked;
            data.pointerClick = clicked;
            data.rawPointerPress = go;
            data.pointerDrag = ExecuteEvents.GetEventHandler<IDragHandler>(go);
            if (data.pointerDrag != null) ExecuteEvents.Execute(data.pointerDrag, data, ExecuteEvents.initializePotentialDrag);

            data.clickCount = 1;
            data.clickTime = Time.unscaledTime;
            ExecuteEvents.Execute(data.pointerPress, data, ExecuteEvents.pointerUpHandler);
            if (data.pointerClick != null) ExecuteEvents.Execute(data.pointerClick, data, ExecuteEvents.pointerClickHandler);
            data.eligibleForClick = false;
            data.pointerPress = null;
            data.rawPointerPress = null;
            data.pointerDrag = null;
        }
#endif
    }
}
