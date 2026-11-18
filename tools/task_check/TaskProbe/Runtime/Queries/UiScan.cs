// The UI as the widgets and ui queries read it (contract section 3): uGUI (UnityEngine.UI graphics and selectables,
// TextMeshPro) on the scene's canvases, and UI Toolkit (every UIDocument's panel); and the widget click input.
// Rectangles are viewport fractions 0-1 with y down from the top, whatever render mode, scaler or panel scale placed
// them. Two rules say whether a widget shows. Visible (the widgets field and select, and the widget click) is a state:
// active, every Canvas up the chain enabled, its graphic enabled, the CanvasGroups' alpha above
// 0.004 (in UI Toolkit: displayed all the way up, its own visibility visible, an opacity above 0.004 down the tree),
// on a canvas or panel drawn on the screen, inside the frame, and not wholly outside a RectMask2D or an enabled Mask up
// the chain (in UI Toolkit: an element up the tree that clips, overflow: hidden, as a ScrollView's viewport does): a
// control scrolled out of its scroll area is not visible; its colour and its size don't count. On screen (a ui
// element) is drawn: visible on a screen canvas or panel, and also its colour and CanvasRenderer alpha above 0.004
// with the CanvasGroups', not culled by a RectMask2D, and of some size. A click on a control scrolled out of its own
// scroll area first scrolls that area to it, as a player would (Scroll), and a click reaches a control only when a
// pointer at its centre would (Covered: nothing drawn over it takes the pointer first).
using System;
using System.Collections.Generic;
using System.Reflection;
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
        /// <summary>The uGUI object or the UI Toolkit element it is (what Covered reads).</summary>
        internal abstract object Target { get; }
        /// <summary>When it is visible but for the scroll areas it is in (Scrolled), those scrolled to it; what was
        /// scrolled, for probe.log, else null.</summary>
        internal abstract string ScrollIntoView();
    }

    public static class UiScan
    {
        const float AlphaFloor = 0.004f;  // an element drawn at this alpha or less is not on screen
        static readonly Regex Tags = new Regex(@"</?[A-Za-z_#][^<>]*>|</>", RegexOptions.CultureInvariant);

        /// <summary>Rich text as shown: its tags left out.</summary>
        static string Plain(string marked) => string.IsNullOrEmpty(marked) || marked.IndexOf('<') < 0 ? marked : Tags.Replace(marked, "");

        static bool IsRectField(string f) => f == "x" || f == "y" || f == "w" || f == "h";

        /// <summary>A rectangle with a size that lies at least partly inside the frame.</summary>
        static bool OnScreen(double x, double y, double w, double h) => w > 0.0 && h > 0.0 && x + w > 0.0 && x < 1.0 && y + h > 0.0 && y < 1.0;

        /// <summary>A rectangle inside the frame, at least partly; one without a size by its place.</summary>
        static bool InFrame(double x, double y, double w, double h) => Within(x, y, w, h, 0.0, 0.0, 1.0, 1.0);

        /// <summary>A rectangle inside the rectangle (cx, cy, cw, ch), at least partly; one without a size by its place.
        /// Nothing is inside a rectangle without a size.</summary>
        static bool Within(double x, double y, double w, double h, double cx, double cy, double cw, double ch) =>
            cw > 0.0 && ch > 0.0 && x < cx + cw && y < cy + ch && (w > 0.0 ? x + w > cx : x >= cx) && (h > 0.0 ? y + h > cy : y >= cy);

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
            // a scan that throws leaves none of its elements
#if TASKPROBE_UGUI
            try { UguiElements(Scanned); }
            catch (Exception e)
            {
                Scanned.Clear();
                Probe.Active?.Failed("ui: the uGUI canvases couldn't be read: {0}", e);
            }
#endif
#if TASKPROBE_UITK
            var before = Scanned.Count;
            try { UitkElements(Scanned); }
            catch (Exception e)
            {
                Scanned.RemoveRange(before, Scanned.Count - before);
                Probe.Active?.Failed("ui: the UI Toolkit panels couldn't be read: {0}", e);
            }
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
        /// into a texture, on another display or by a camera that is off: it isn't on the screen.</summary>
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
                    if (cam != null && (!cam.isActiveAndEnabled || cam.targetTexture != null || cam.targetDisplay != 0)) return false;
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

        /// <summary>Visible, a state: active, every Canvas up the chain enabled, `graphic` (when it has
        /// one) enabled, the CanvasGroups' alpha above the floor (up to one that ignores its parents), on a canvas drawn
        /// on the screen (a world-space one through the player's camera, unless `screenOnly`), inside the frame, and
        /// not clipped: at least partly inside the rectangle of every enabled RectMask2D and enabled Mask on an object
        /// above it (a scroll area's viewport; a stencil Mask is taken as its rectangle), up to a Canvas that overrides
        /// sorting (uGUI doesn't mask what such a canvas holds by a mask above it). Its colour and its size don't count.
        /// `alpha` is the CanvasGroups' product, `canvas` its canvas, the rectangle its own. With `scrolls`: whether it
        /// would be visible but for the scroll areas it is in, those listed there (innermost first): a mask that clips
        /// it is the view of an enabled ScrollRect above it whose content holds it (ScrollOf), that view inside the
        /// frame; the widget itself may be outside the frame (scrolled there).</summary>
        static bool UguiShown(GameObject go, Graphic graphic, bool screenOnly, out float alpha, out Canvas canvas,
                              out double x, out double y, out double w, out double h, List<ScrollRect> scrolls = null)
        {
            alpha = 1f;
            canvas = null;
            x = y = w = h = 0.0;
            if (go == null || !go.activeInHierarchy || (graphic != null && !graphic.enabled)) return false;
            canvas = go.GetComponentInParent<Canvas>();
            if (canvas == null) return false;
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
            if (!(alpha > AlphaFloor) || !RectOf(go.transform as RectTransform, canvas, screenOnly, out x, out y, out w, out h)
                || (scrolls == null && !InFrame(x, y, w, h)))
                return false;
            for (var p = go.transform; p != null; p = p.parent)
            {
                if (p != go.transform
                    && ((p.TryGetComponent<RectMask2D>(out var rectMask) && rectMask.enabled) || (p.TryGetComponent<Mask>(out var mask) && mask.MaskEnabled()))
                    && RectOf(p as RectTransform, canvas, screenOnly, out var mx, out var my, out var mw, out var mh) && !Within(x, y, w, h, mx, my, mw, mh))
                {
                    var area = scrolls != null ? ScrollOf(p, go.transform) : null;
                    if (area == null || !InFrame(mx, my, mw, mh)) return false;
                    if (!scrolls.Contains(area)) scrolls.Add(area);
                }
                if (p.TryGetComponent<Canvas>(out var own) && own.overrideSorting) break;
            }
            return true;
        }

        /// <summary>The ScrollRect whose view is `clip` (its viewport, or itself without one), at `clip` or above it,
        /// enabled, scrolling some way, its content holding `control`; else null.</summary>
        static ScrollRect ScrollOf(Transform clip, Transform control)
        {
            for (var p = clip; p != null; p = p.parent)
                if (p.TryGetComponent<ScrollRect>(out var area) && area.isActiveAndEnabled && (area.horizontal || area.vertical)
                    && area.content != null && control.IsChildOf(area.content)
                    && (area.viewport != null ? area.viewport == clip : area.transform == clip))
                    return area;
            return null;
        }

        static readonly List<ScrollRect> ScrollsUp = new List<ScrollRect>();

        /// <summary>A uGUI widget visible but for the scroll areas it is in (UguiShown with scrolls), scrolled into view as
        /// a player scrolls to it: each area, innermost first, the least way that shows it whole (its start when it is
        /// larger than the view), along the axes the area scrolls and as far as its movement type lets the content go
        /// (ScrollInto). Only with an EventSystem: without one a player can't scroll a uGUI area either. What was
        /// scrolled, "Area (ScrollRect) to show `named`", else null.</summary>
        static string UguiScroll(GameObject go, Graphic graphic, string named)
        {
            if (EventSystem.current == null) return null;
            ScrollsUp.Clear();
            if (!UguiShown(go, graphic, false, out _, out _, out _, out _, out _, out _, ScrollsUp) || ScrollsUp.Count == 0) return null;
            var areas = new List<string>();
            foreach (var area in ScrollsUp)
            {
                ScrollInto(area, (RectTransform)go.transform);
                areas.Add(area.gameObject.name + " (ScrollRect)");
            }
            return string.Join(", ", areas) + " to show " + named;
        }

        /// <summary>The ScrollRect's content moved so `target` shows inside its view (Shift on each axis it scrolls, in
        /// the view's own space), its movement stopped.</summary>
        static void ScrollInto(ScrollRect area, RectTransform target)
        {
            var view = area.viewport != null ? area.viewport : (RectTransform)area.transform;
            var content = area.content;
            BoundsIn(target, view, out var lo, out var hi);
            BoundsIn(content, view, out var clo, out var chi);
            var r = view.rect;
            var shift = Vector2.zero;
            if (area.horizontal) shift.x = Shift(lo.x, hi.x, r.xMin, r.xMax, clo.x, chi.x, false, area.movementType);
            if (area.vertical) shift.y = Shift(lo.y, hi.y, r.yMin, r.yMax, clo.y, chi.y, true, area.movementType);
            if (shift == Vector2.zero) return;
            var world = view.TransformVector(shift);
            var parent = content.parent;
            var local = parent != null ? parent.InverseTransformVector(world) : world;
            area.StopMovement();
            content.anchoredPosition += new Vector2(local.x, local.y);
        }

        /// <summary>A RectTransform's corners in `space`'s local coordinates: their least and greatest.</summary>
        static void BoundsIn(RectTransform rt, Transform space, out Vector2 lo, out Vector2 hi)
        {
            rt.GetWorldCorners(Corners);
            lo = new Vector2(float.MaxValue, float.MaxValue);
            hi = new Vector2(float.MinValue, float.MinValue);
            for (var i = 0; i < 4; i++)
            {
                Vector2 p = space.InverseTransformPoint(Corners[i]);
                lo = Vector2.Min(lo, p);
                hi = Vector2.Max(hi, p);
            }
        }

        /// <summary>How far the content moves along one axis so a target [lo, hi] shows inside the view [vlo, vhi]: not
        /// at all when it shows whole; else the least way that shows it whole, or so its start shows (the top: `fromHigh`;
        /// the left) when it is larger than the view. Unless the movement is unrestricted, the content [clo, chi] still
        /// covers the view after it (a content no larger than the view doesn't move).</summary>
        static float Shift(float lo, float hi, float vlo, float vhi, float clo, float chi, bool fromHigh, ScrollRect.MovementType movement)
        {
            float d;
            if (hi - lo > vhi - vlo) d = fromHigh ? vhi - hi : vlo - lo;
            else if (lo < vlo) d = vlo - lo;
            else if (hi > vhi) d = vhi - hi;
            else return 0f;
            if (movement == ScrollRect.MovementType.Unrestricted) return d;
            if (chi - clo <= vhi - vlo) return 0f;
            return Mathf.Clamp(d, vhi - chi, vlo - clo);
        }

        static readonly List<RaycastResult> Hits = new List<RaycastResult>();

        /// <summary>The centre of a uGUI widget's visible part, viewport fractions (y down): its rectangle within the
        /// frame and within every enabled RectMask2D and Mask above it (as UguiShown reads them). False when none of it
        /// is visible.</summary>
        static bool UguiCentre(GameObject go, out double cx, out double cy)
        {
            cx = cy = 0.0;
            var canvas = go.GetComponentInParent<Canvas>();
            if (!RectOf(go.transform as RectTransform, canvas, false, out var x, out var y, out var w, out var h)) return false;
            double x0 = Math.Max(x, 0.0), y0 = Math.Max(y, 0.0), x1 = Math.Min(x + w, 1.0), y1 = Math.Min(y + h, 1.0);
            for (var p = go.transform; p != null; p = p.parent)
            {
                if (p != go.transform
                    && ((p.TryGetComponent<RectMask2D>(out var rectMask) && rectMask.enabled) || (p.TryGetComponent<Mask>(out var mask) && mask.MaskEnabled()))
                    && RectOf(p as RectTransform, canvas, false, out var mx, out var my, out var mw, out var mh))
                {
                    x0 = Math.Max(x0, mx);
                    y0 = Math.Max(y0, my);
                    x1 = Math.Min(x1, mx + mw);
                    y1 = Math.Min(y1, my + mh);
                }
                if (p.TryGetComponent<Canvas>(out var own) && own.overrideSorting) break;
            }
            if (!(x1 >= x0 && y1 >= y0)) return false;
            cx = (x0 + x1) / 2.0;
            cy = (y0 + y1) / 2.0;
            return true;
        }

        /// <summary>Whether a player's pointer at (fx, fy) (viewport fractions, y down) reaches `go`: the first hit of the
        /// EventSystem's raycasters there (EventSystem.RaycastAll, as the UI module takes it) is `go` or an object under
        /// it (its label). 0 when it is; 1 when another object is hit first and `go` further down (drawn under it); 2
        /// when another is hit and `go` not at all (it takes no pointer there); -1 when it can't be told: no EventSystem
        /// (no pointer reaches a uGUI widget then), or nothing is hit there. `over`: what is hit first, "parent/name
        /// (type)".</summary>
        static int UguiCover(GameObject go, double fx, double fy, out string over)
        {
            over = null;
            var events = EventSystem.current;
            if (events == null) return -1;
            var data = new PointerEventData(events) { position = new Vector2((float)(fx * Screen.width), (float)((1.0 - fy) * Screen.height)) };
            events.RaycastAll(data, Hits);
            if (Hits.Count == 0 || Hits[0].gameObject == null) return -1;
            var top = Hits[0].gameObject;
            if (top.transform.IsChildOf(go.transform)) return 0;
            // its parent's name and its own, "GoToggle/Label (Text)" (a root object: its own name alone)
            var parent = top.transform.parent;
            over = (parent != null ? parent.name + "/" : "") + top.name + " (" + (top.TryGetComponent<Graphic>(out var g) ? g.GetType().Name : "GameObject") + ")";
            foreach (var hit in Hits)
                if (hit.gameObject != null && hit.gameObject.transform.IsChildOf(go.transform)) return 1;
            return 2;
        }

        /// <summary>Visible (UguiShown): a widget's visible, and what the widget click takes.</summary>
        static bool UguiVisible(GameObject go, Graphic graphic) => UguiShown(go, graphic, false, out _, out _, out _, out _, out _, out _);

        /// <summary>Drawn on screen (a ui element): visible on a screen canvas (so not wholly outside an enabled Mask up
        /// the chain: a stencil Mask, as on uGUI's Scroll View and Dropdown list, draws nothing outside its rect and,
        /// unlike a RectMask2D, never culls), and its colour and CanvasRenderer alpha above the floor with the
        /// CanvasGroups', not culled by a RectMask2D, of some size. The rectangle is the graphic's.</summary>
        static bool UguiDrawn(Graphic graphic, out double x, out double y, out double w, out double h)
        {
            if (!UguiShown(graphic.gameObject, graphic, true, out var alpha, out _, out x, out y, out w, out h)) return false;
            alpha *= graphic.color.a;
            var cr = graphic.canvasRenderer;
            if (cr != null)
            {
                if (cr.cull) return false;
                alpha *= cr.GetAlpha();
            }
            return alpha > AlphaFloor && OnScreen(x, y, w, h);
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
                if (!UguiDrawn(g, out var x, out var y, out var w, out var h)) continue;
                var e = new UiElement { Name = g.gameObject.name, Class = g.GetType().Name, Source = "ugui", HasRect = true, X = x, Y = y, W = w, H = h };
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

        /// <summary>Every element under `root` (itself included), depth first: the parts a control builds inside itself
        /// too (a Slider's tracker and dragger, a ProgressBar's bar, a TextField's input). UI Toolkit keeps them in the
        /// control's own children (only a container such as a ScrollView puts what it holds elsewhere), so no rule tells
        /// them from what a UXML or a script adds.</summary>
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

        /// <summary>Visible in a panel on the screen (`onScreen`): displayed all the way up (display: none takes an
        /// element and everything under it out), visible (visibility is inherited, and a child may be visible again
        /// under a hidden parent: its own resolved value decides), of an opacity above the floor down the tree, inside
        /// the frame, and at least partly inside the box of every element up the tree that clips (UitkClips: a
        /// ScrollView's viewport); `drawn` (a ui element): of some size there too. With `views`: whether it would be
        /// visible but for the ScrollViews it is in, those listed there (innermost first): an element that clips it is
        /// a ScrollView whose content holds it, or a part of one between it and its content (ScrollViewOf), inside the
        /// frame; the element itself may be outside the frame (scrolled there).</summary>
        static bool UitkVisible(UIE.VisualElement e, bool onScreen, bool drawn, List<UIE.ScrollView> views = null)
        {
            if (!onScreen || e?.panel == null || e.resolvedStyle.visibility != UIE.Visibility.Visible) return false;
            var opacity = 1f;
            for (var p = e; p != null; p = p.hierarchy.parent)
            {
                var s = p.resolvedStyle;
                if (s.display == UIE.DisplayStyle.None) return false;
                opacity *= s.opacity;
            }
            if (!(opacity > AlphaFloor) || !RectOf(e, out var x, out var y, out var w, out var h)
                || (views == null && !(drawn ? OnScreen(x, y, w, h) : InFrame(x, y, w, h))))
                return false;
            var b = e.worldBound;
            for (var p = e.hierarchy.parent; p != null; p = p.hierarchy.parent)
            {
                if (!UitkClips(p)) continue;
                var c = p.worldBound;
                if (Within(b.x, b.y, b.width, b.height, c.x, c.y, c.width, c.height)) continue;
                var view = views != null ? ScrollViewOf(p, e) : null;
                if (view == null || !RectOf(p, out var vx, out var vy, out var vw, out var vh) || !InFrame(vx, vy, vw, vh)) return false;
                if (!views.Contains(view)) views.Add(view);
            }
            return true;
        }

        /// <summary>The ScrollView that clips `e` at `clip`: the first ScrollView at `clip` or above it, when its content
        /// container holds `e` and `clip` is the ScrollView or lies between it and that container (its viewport); else
        /// null.</summary>
        static UIE.ScrollView ScrollViewOf(UIE.VisualElement clip, UIE.VisualElement e)
        {
            for (var p = clip; p != null; p = p.hierarchy.parent)
                if (p is UIE.ScrollView view)
                {
                    var content = view.contentContainer;
                    var between = clip == view || (view.Contains(clip) && (clip == content || clip.Contains(content)));
                    return content != null && content.Contains(e) && between ? view : null;
                }
            return null;
        }

        static readonly List<UIE.ScrollView> ViewsUp = new List<UIE.ScrollView>();

        /// <summary>A UI Toolkit element visible but for the ScrollViews it is in (UitkVisible with views), each
        /// scrolled to it by ScrollView.ScrollTo, innermost first. What was scrolled, "View (ScrollView) to show
        /// `named`", else null.</summary>
        static string UitkScroll(UIE.VisualElement e, bool onScreen, string named)
        {
            ViewsUp.Clear();
            if (!UitkVisible(e, onScreen, false, ViewsUp) || ViewsUp.Count == 0) return null;
            var views = new List<string>();
            foreach (var view in ViewsUp)
            {
                view.ScrollTo(e);
                views.Add(NameOf(view) + " (ScrollView)");
            }
            return string.Join(", ", views) + " to show " + named;
        }

        static readonly List<UIE.VisualElement> Picked = new List<UIE.VisualElement>();

        /// <summary>The centre of an element's visible part, viewport fractions (y down): its box within its panel and
        /// within every element above it that clips. False when none of it is visible.</summary>
        static bool UitkCentre(UIE.VisualElement e, out double cx, out double cy)
        {
            cx = cy = 0.0;
            if (e?.panel == null) return false;
            var whole = e.panel.visualTree.worldBound;
            var b = e.worldBound;
            float x0 = Mathf.Max(b.xMin, whole.xMin), y0 = Mathf.Max(b.yMin, whole.yMin), x1 = Mathf.Min(b.xMax, whole.xMax), y1 = Mathf.Min(b.yMax, whole.yMax);
            for (var p = e.hierarchy.parent; p != null; p = p.hierarchy.parent)
            {
                if (!UitkClips(p)) continue;
                var c = p.worldBound;
                x0 = Mathf.Max(x0, c.xMin);
                y0 = Mathf.Max(y0, c.yMin);
                x1 = Mathf.Min(x1, c.xMax);
                y1 = Mathf.Min(y1, c.yMax);
            }
            if (!(x1 >= x0 && y1 >= y0) || !(whole.width > 0f) || !(whole.height > 0f)) return false;
            cx = ((x0 + x1) / 2f - whole.x) / whole.width;
            cy = ((y0 + y1) / 2f - whole.y) / whole.height;
            return true;
        }

        /// <summary>Whether a player's pointer at (fx, fy) (viewport fractions, y down) reaches `e` in its panel: the
        /// element the panel picks there (IPanel.PickAll, the topmost that takes the pointer) is `e` or one under it. 0
        /// when it is; 1 when another is picked and `e` further down; 2 when another is picked and `e` not at all; -1 when
        /// nothing is picked there. Only `e`'s own panel is read. `over`: what is picked, "parent/name (type)".</summary>
        static int UitkCover(UIE.VisualElement e, double fx, double fy, out string over)
        {
            over = null;
            if (e?.panel == null) return -1;
            var whole = e.panel.visualTree.worldBound;
            Picked.Clear();
            var top = e.panel.PickAll(new Vector2((float)(whole.x + fx * whole.width), (float)(whole.y + fy * whole.height)), Picked);
            if (top == null) return -1;
            if (top == e || e.Contains(top)) return 0;
            // its parent's name and its own, as a uGUI one's (an element with no parent: its own name alone)
            var parent = top.hierarchy.parent;
            over = (parent != null ? NameOf(parent) + "/" : "") + NameOf(top) + " (" + top.GetType().Name + ")";
            foreach (var v in Picked)
                if (v == e || e.Contains(v)) return 1;
            return 2;
        }

        static System.Reflection.MethodInfo shouldClip;
        static bool shouldClipLooked;

        /// <summary>Whether `p` clips what it holds to its box, by UI Toolkit's own rule (VisualElement.ShouldClip,
        /// internal: an overflow other than visible, its clipping not turned off; a ScrollView's viewport clips, its
        /// content container doesn't). A Unity without that method clips nothing here, and probe.log says so
        /// once.</summary>
        static bool UitkClips(UIE.VisualElement p)
        {
            if (!shouldClipLooked)
            {
                shouldClipLooked = true;
                shouldClip = typeof(UIE.VisualElement).GetMethod("ShouldClip", System.Reflection.BindingFlags.Instance | System.Reflection.BindingFlags.NonPublic,
                                                                 null, Type.EmptyTypes, null);
                if (shouldClip != null && shouldClip.ReturnType != typeof(bool)) shouldClip = null;
                if (shouldClip == null) Probe.Log("UI Toolkit: no VisualElement.ShouldClip in this Unity, so an element that clips hides no widget");
            }
            return shouldClip != null && (bool)shouldClip.Invoke(p, null);
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
                    if (!UitkVisible(e, true, true)) continue;
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
                    // field shows its placeholder, a password field its mask characters
                    if (!(e is UIE.TextElement te) || !(s.color.a > AlphaFloor)) continue;
                    var text = te.enableRichText ? Plain(te.text) : te.text;
                    var edit = (UIE.ITextEdition)te;
                    if (string.IsNullOrEmpty(text)) text = edit.placeholder;
                    else if (edit.isPassword) text = new string(edit.maskChar, text.Length);
                    if (!string.IsNullOrEmpty(text) && text.Trim().Length > 0)
                        output.Add(new UiElement { Name = name, Class = cls, Source = "uitk", Kind = "text", Text = text, HasRect = true, X = x, Y = y, W = w, H = h });
                }
            }
        }
#endif

        // ---------------------------------------------------------------- widgets

        /// <summary>The widgets a select picks: uGUI objects in hierarchy order, then UI Toolkit elements in tree order
        /// (a control's own parts too, an unnamed one named by its type). `component`: a type name a component
        /// of the object, or the element (a base type included), carries; with `name`, a component on an object above,
        /// or an element above, also matches (the row keeps its own class).
        /// `name`: a wildcard on the object's or element's name; without `component` it finds any object of a canvas
        /// (a panel with no graphic too). `text`: a regex its text must match (a Selectable's is its label's, so a text
        /// matches the Selectable and its label). `visibleOnly`: only the widgets on screen.</summary>
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
            // the components of the asked type (every type of that name, an interface's implementers); when no component
            // can be of it (a UI Toolkit element's type), no uGUI object has it
            var extra = new List<Component>();
            if (!string.IsNullOrEmpty(component) && !Find.Components(component, true, extra)) return;
            // the candidates, filtered by name before they are sorted
            var seen = new HashSet<GameObject>();
            var candidates = new List<Transform>();
            void Take(Component c)
            {
                if (c == null || !seen.Add(c.gameObject) || (name != null && !Find.Wild(name, c.gameObject.name))) return;
                if (Probe.IsOwn(c.gameObject) || (c.TryGetComponent<Graphic>(out var part) && IsTmpPart(part)) || c.GetComponentInParent<Canvas>(true) == null)
                    return;
                candidates.Add(c.transform);
            }
            if (string.IsNullOrEmpty(component) && name != null)
            {
                // by name: any object of a canvas, a panel with no graphic or selectable too (a menu root that is only a
                // CanvasGroup or a layout group)
                foreach (var r in UnityEngine.Object.FindObjectsByType<RectTransform>(FindObjectsInactive.Include, FindObjectsSortMode.None)) Take(r);
            }
            else if (string.IsNullOrEmpty(component) || name != null)
            {
                // the objects that carry a graphic or a selectable (with a name, those under the asked component count)
                foreach (var g in UnityEngine.Object.FindObjectsByType<Graphic>(FindObjectsInactive.Include, FindObjectsSortMode.None)) Take(g);
                foreach (var s in UnityEngine.Object.FindObjectsByType<Selectable>(FindObjectsInactive.Include, FindObjectsSortMode.None)) Take(s);
            }
            foreach (var c in extra) Take(c);
            Find.SortByHierarchy(candidates);
            foreach (var t in candidates)
            {
                if (t == null) continue;
                var go = t.gameObject;
                Component matched = null;
                if (!string.IsNullOrEmpty(component))
                {
                    matched = Reflect.ComponentNamed(go, component, false);
                    // with a name, a component on an object above also matches
                    if (matched == null && (name == null || !CarriedAbove(t, component))) continue;
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

        /// <summary>Whether an object above `t` carries a component whose type is named `component`.</summary>
        static bool CarriedAbove(Transform t, string component)
        {
            for (var p = t.parent; p != null; p = p.parent)
                if (Reflect.ComponentNamed(p.gameObject, component, false) != null) return true;
            return false;
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
                Class = main != null ? main.GetType().Name : "RectTransform";  // an object found by its name alone
            }

            public override bool Visible() => UguiVisible(go, graphic);
            internal override object Target => go;
            internal override string ScrollIntoView() => UguiScroll(go, graphic, Name + " (" + Class + ")");

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
                    case "covered":
                        return Visible() && UguiCentre(go, out var cx, out var cy) ? CoverField(UguiCover(go, cx, cy, out _)) : null;
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
                    if (name != null && !Find.Wild(name, NameOf(e))) continue;
                    // with a name, an element above of that type also matches
                    if (!string.IsNullOrEmpty(component) && !Reflect.IsA(e.GetType(), component) && (name == null || !AboveIsA(e, component))) continue;
                    if (text != null)
                    {
                        var shown = UitkText(e);
                        if (shown == null || !text.IsMatch(shown)) continue;
                    }
                    if (visibleOnly && !UitkVisible(e, root.Value, false)) continue;
                    found.Add(new UitkWidget(e, root.Value));
                }
            }
        }

        static bool AboveIsA(UIE.VisualElement e, string component)
        {
            for (var p = e.parent; p != null; p = p.parent)
                if (Reflect.IsA(p.GetType(), component)) return true;
            return false;
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

            public override bool Visible() => UitkVisible(e, onScreen, false);
            public override string Text() => UitkText(e);
            internal override object Target => e;
            internal override string ScrollIntoView() => UitkScroll(e, onScreen, Name + " (" + Class + ")");

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
                    case "covered":
                        return Visible() && UitkCentre(e, out var cx, out var cy) ? CoverField(UitkCover(e, cx, cy, out _)) : null;
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

        // ---------------------------------------------------------------- what a pointer reaches, and scrolling to a control

        /// <summary>The widgets field `covered`: 1 when a pointer at the centre of its visible part reaches something
        /// drawn over it first (it is hit further down), 0 when it reaches the widget; no value when that can't be
        /// told (no EventSystem for a uGUI widget, nothing hit there, or the widget itself takes no pointer there).</summary>
        static object CoverField(int cover) => cover == 0 ? 0.0 : cover == 1 ? 1.0 : (object)null;

        /// <summary>Whether a player's pointer at `pixel` (screen pixels from the bottom left) would reach something other
        /// than `target` first (a uGUI object: UguiCover; a UI Toolkit element: UitkCover): `over` says what, for
        /// probe.log. False when it reaches `target`, or when that can't be told (no EventSystem for a uGUI object,
        /// nothing hit there).</summary>
        public static bool Covered(object target, Vector2 pixel, out string over)
        {
            over = null;
            double fx = Screen.width > 0 ? pixel.x / Screen.width : 0.0, fy = Screen.height > 0 ? 1.0 - pixel.y / Screen.height : 0.0;
#if TASKPROBE_UGUI
            if (target is GameObject go) return UguiCover(go, fx, fy, out over) > 0;
#endif
#if TASKPROBE_UITK
            if (target is UIE.VisualElement e) return UitkCover(e, fx, fy, out over) > 0;
#endif
            return false;
        }

        /// <summary>For a click that found nothing (Click, ShownDisabled): the first uGUI Selectable, else UI Toolkit
        /// Button, that `want` names as Click compares them and that is hidden only by the scroll areas it is in, scrolled
        /// into their view as a player scrolls to it (UguiScroll: only with an EventSystem; UitkScroll). Nothing is
        /// clicked: the click is made again once the layout has followed (the next frame: Inputs). What was scrolled,
        /// for probe.log, else null.</summary>
        public static string Scroll(string want) => Scroll(want, By.Name) ?? Scroll(want, By.Shown) ?? Scroll(want, By.Caption);

        /// <summary>For a tap on a widget that isn't on screen (Inputs.Spot): the first widget of that name (a wildcard),
        /// else of that type, whatever its kind, else the first button that reads so (Caption), that is hidden only by
        /// the scroll areas it is in, scrolled into their view. What was scrolled, for probe.log, else null.</summary>
        public static string ScrollToWidget(string named)
        {
            foreach (var byType in new[] { false, true })
                foreach (var w in Widgets(byType ? named : null, byType ? null : named, null, false))
                {
                    var scrolled = w.ScrollIntoView();
                    if (scrolled != null) return scrolled;
                }
            return Scroll(named, By.Caption);
        }

        static string Scroll(string want, By by)
        {
            var how = by != By.Name ? " by its caption" : "";
#if TASKPROBE_UGUI
            var selectables = new List<Selectable>(UnityEngine.Object.FindObjectsByType<Selectable>(FindObjectsInactive.Exclude, FindObjectsSortMode.None));
            Find.SortByHierarchy(selectables);
            foreach (var s in selectables)
            {
                if (s == null || Probe.IsOwn(s.gameObject)) continue;
                if (!Matches(by, want, s.gameObject.name, s.GetType(), () => CaptionOf(s))) continue;
                var own = s.targetGraphic != null && s.targetGraphic.gameObject == s.gameObject ? s.targetGraphic : null;
                var scrolled = UguiScroll(s.gameObject, own, s.gameObject.name + " (" + s.GetType().Name + ")" + how);
                if (scrolled != null) return scrolled;
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
                    if (!(e is UIE.Button)) continue;
                    if (!Matches(by, want, NameOf(e), e.GetType(), () => UitkText(e))) continue;
                    var scrolled = UitkScroll(e, root.Value, NameOf(e) + " (" + e.GetType().Name + ")" + how);
                    if (scrolled != null) return scrolled;
                }
            }
#endif
            return null;
        }

        // ---------------------------------------------------------------- widget click

        /// <summary>Clicks the first visible, interactable uGUI Selectable whose object's name matches `want` (a wildcard)
        /// or whose type is named `want`, else such a UI Toolkit Button: as a player's click fires it
        /// (pressed, released, clicked). Visible is the widgets' state (a fully transparent button
        /// takes a click; one scrolled out of its scroll area's viewport doesn't: Scroll brings it into view first).
        /// It is clicked only when a player's pointer at the centre of its visible part reaches it (UguiCover through
        /// the EventSystem's raycasters, UitkCover through its panel's picking): when something drawn over it takes
        /// the pointer first, nothing is clicked and `covered` says what ("X (Image) is over it"), and the control is
        /// still returned. Without an EventSystem a player's click reaches no uGUI widget, and neither does this one
        /// (probe.log says so). What it clicked, "name (type)" (a wildcard or a type name may match several: the log
        /// names the one), or null when none. When no name and no type matches, the first such widget whose caption is
        /// `want` exactly as shown (Shown) is clicked, else the first whose caption reads as `want` (Caption): a button
        /// the task itself adds has no name at the start, and the instruction names it by what it reads.</summary>
        public static string Click(string want, out string covered) =>
            Click(want, By.Name, true, out covered) ?? Click(want, By.Shown, true, out covered) ?? Click(want, By.Caption, true, out covered);

        /// <summary>For a click that found nothing (Click): the first visible uGUI Selectable or UI Toolkit Button that
        /// `want` names as Click compares them, shown but disabled (not interactable, its Selectable off, a Button not
        /// enabled in its hierarchy: a player's click on it does nothing), "name (type)"; else null. Nothing is
        /// clicked. `covered`: as Click's, when something drawn over it takes the pointer first.</summary>
        public static string ShownDisabled(string want, out string covered) =>
            Click(want, By.Name, false, out covered) ?? Click(want, By.Shown, false, out covered) ?? Click(want, By.Caption, false, out covered);

        /// <summary>How a click compares `want`: with the widget's name (a wildcard) or type; with its caption as shown,
        /// whole and in the same case (spaces at either end of the caption left out); with its caption as Caption
        /// compares it.</summary>
        enum By { Name, Shown, Caption }

        static bool Matches(By by, string want, string name, Type type, Func<string> caption)
        {
            if (by == By.Name) return Find.Wild(want, name) || Reflect.IsA(type, want);
            var text = caption();
            return by == By.Shown ? text != null && string.Equals(text.Trim(), want, StringComparison.Ordinal) : Reads(text, want);
        }

        /// <summary>A name or a caption as a click compares them: in lower case, every run of characters that are
        /// neither letters nor digits one `_`, none at either end ("New_expedition" is a button reading
        /// "New expedition!").</summary>
        public static string Caption(string text)
        {
            var found = new System.Text.StringBuilder();
            foreach (var c in text ?? "")
            {
                if (char.IsLetterOrDigit(c)) found.Append(char.ToLowerInvariant(c));
                else if (found.Length > 0 && found[found.Length - 1] != '_') found.Append('_');
            }
            return found.ToString().TrimEnd('_');
        }

        static bool Reads(string caption, string want)
        {
            var wanted = Caption(want);
            return wanted.Length > 0 && Caption(caption) == wanted;
        }

#if TASKPROBE_UGUI
        /// <summary>What a Selectable reads: its own text, else the first text below it that shows with it.</summary>
        static string CaptionOf(Selectable s)
        {
            foreach (var g in s.GetComponentsInChildren<Graphic>(true))
            {
                if (!g.enabled || (g.gameObject != s.gameObject && !ActiveBelow(g.transform, s.transform))) continue;
                var label = GraphicText(g);
                if (label != null) return label;
            }
            return null;
        }
#endif

        /// <summary>Where the first visible, interactable uGUI Selectable or UI Toolkit Button whose caption is `want`
        /// is on the screen (fractions, y down), for a finger: a tap's spot when no widget has the name or the
        /// type. `target`: its object or element (Covered).</summary>
        public static bool CaptionSpot(string want, out double x, out double y, out double w, out double h, out string named, out object target)
        {
            x = y = w = h = 0.0;
            named = null;
            target = null;
#if TASKPROBE_UGUI
            var selectables = new List<Selectable>(UnityEngine.Object.FindObjectsByType<Selectable>(FindObjectsInactive.Exclude, FindObjectsSortMode.None));
            Find.SortByHierarchy(selectables);
            foreach (var s in selectables)
            {
                if (s == null || Probe.IsOwn(s.gameObject) || !Reads(CaptionOf(s), want)) continue;
                var own = s.targetGraphic != null && s.targetGraphic.gameObject == s.gameObject ? s.targetGraphic : null;
                if (!s.isActiveAndEnabled || !s.IsInteractable() || !UguiVisible(s.gameObject, own)) continue;
                if (!RectOf(s.transform as RectTransform, s.GetComponentInParent<Canvas>(), false, out x, out y, out w, out h) || w <= 0.0 || h <= 0.0) continue;
                named = s.gameObject.name + " (" + s.GetType().Name + ") by its caption";
                target = s.gameObject;
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
                    if (!(e is UIE.Button) || !Reads(UitkText(e), want)) continue;
                    if (!e.enabledInHierarchy || !UitkVisible(e, root.Value, false)) continue;
                    if (!RectOf(e, out x, out y, out w, out h) || w <= 0.0 || h <= 0.0) continue;
                    named = NameOf(e) + " (" + e.GetType().Name + ") by its caption";
                    target = e;
                    return true;
                }
            }
#endif
            return false;
        }

        /// <summary>The first visible uGUI Selectable, else UI Toolkit Button, that `want` names (`by`): clicked when
        /// `press` and it is interactable, unless something drawn over it takes the pointer first (`covered` says what;
        /// it is returned, not clicked); when not `press`, only found, and only when it is not.</summary>
        static string Click(string want, By by, bool press, out string covered)
        {
            covered = null;
            var how = by != By.Name ? " by its caption" : "";
#if TASKPROBE_UGUI
            var selectables = new List<Selectable>(UnityEngine.Object.FindObjectsByType<Selectable>(FindObjectsInactive.Exclude, FindObjectsSortMode.None));
            Find.SortByHierarchy(selectables);
            foreach (var s in selectables)
            {
                if (s == null || Probe.IsOwn(s.gameObject)) continue;
                if (!Matches(by, want, s.gameObject.name, s.GetType(), () => CaptionOf(s))) continue;
                var own = s.targetGraphic != null && s.targetGraphic.gameObject == s.gameObject ? s.targetGraphic : null;
                if ((s.isActiveAndEnabled && s.IsInteractable()) != press || !UguiVisible(s.gameObject, own)) continue;
                var found = s.gameObject.name + " (" + s.GetType().Name + ")" + how;
                if (!press)
                {
                    covered = UguiOver(s.gameObject);
                    return found;
                }
                if (EventSystem.current == null)
                {
                    // (an InputField's pointer down would also throw into the game's log)
                    Probe.Log("no EventSystem: a click reaches no uGUI widget, so " + s.gameObject.name + " isn't clicked");
                    break;
                }
                covered = UguiOver(s.gameObject);
                if (covered == null) UguiClick(s);
                return found;
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
                    if (!Matches(by, want, NameOf(e), e.GetType(), () => UitkText(e))) continue;
                    if (e.enabledInHierarchy != press || !UitkVisible(e, root.Value, false)) continue;
                    covered = UitkOver(e);
                    if (!press || covered != null) return NameOf(e) + " (" + e.GetType().Name + ")" + how;
                    // a submit is what Button reacts to with its clicked (Clickable.SimulateSingleClick), as a keyboard or
                    // pad press does; a ClickEvent callback needs a pointer's click (the cursor)
                    using (var submit = UIE.NavigationSubmitEvent.GetPooled())
                    {
                        submit.target = button;
                        button.SendEvent(submit);
                    }
                    return NameOf(e) + " (" + e.GetType().Name + ")" + how;
                }
            }
#endif
            return null;
        }

#if TASKPROBE_UITK
        /// <summary>What a UI Toolkit control's panel picks first at the centre of its visible part (UitkCover), in words
        /// for probe.log; null when it picks the control, or nothing.</summary>
        static string UitkOver(UIE.VisualElement e)
        {
            if (!UitkCentre(e, out var cx, out var cy)) return null;
            var cover = UitkCover(e, cx, cy, out var over);
            return cover == 1 ? over + " is over it" : cover == 2 ? "the pointer at its centre reaches " + over + " and never it" : null;
        }
#endif

#if TASKPROBE_UGUI
        /// <summary>What takes a player's pointer first at the centre of a uGUI control's visible part (UguiCover), in
        /// words for probe.log ("X (Image) is over it"); null when the pointer reaches the control, or that can't be
        /// told.</summary>
        static string UguiOver(GameObject go)
        {
            if (!UguiCentre(go, out var cx, out var cy)) return null;
            var cover = UguiCover(go, cx, cy, out var over);
            return cover == 1 ? over + " is over it" : cover == 2 ? "the pointer at its centre reaches " + over + " and never it" : null;
        }

        /// <summary>A pointer's click at the selectable's centre as the Input System's UI module makes it, through
        /// ExecuteEvents: the pointer enters; the press lets go of a selection the pressed object wouldn't take, then
        /// pointer down and the start of a possible drag; the release pointer up and click; the pointer leaves. onClick,
        /// toggles, EventTrigger entries and a game's own IPointer*Handlers react as to a player's click.</summary>
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

            // the pointer goes again: the UI module follows its own pointer's hover, so this object would never get an exit
            ExecuteEvents.ExecuteHierarchy(go, data, ExecuteEvents.pointerExitHandler);
            data.pointerEnter = null;
        }
#endif

        // ---------------------------------------------------------------- a key to the control with the keyboard focus

        const BindingFlags Members = BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic;

#if TASKPROBE_UGUI || TASKPROBE_UITK
        /// <summary>A keyboard key (`key`: a KeyDown or KeyUp as IMGUI gives a real key, its key code, the character
        /// it types and its modifiers) to the control that has the keyboard focus, as the UI takes a real key: from
        /// IMGUI's event queue, which the Input System's device state never reaches. With an EventSystem: the uGUI
        /// InputField or TMP_InputField it has selected, while that is being edited (Edit), else the focused element of
        /// the UI Toolkit panel it has selected (its PanelEventHandler's), as a KeyDownEvent or KeyUpEvent. With none:
        /// the focused element of the UI Toolkit panel that has one, else every panel drawn over the screen, the
        /// highest sorting order first, until one stops the event or takes the focus, as UI Toolkit's own event
        /// system sends a key. What took it, "name (type)", else null.</summary>
        public static string TypeKey(Event key)
        {
#if TASKPROBE_UGUI
            var events = EventSystem.current;
            var selected = events != null ? events.currentSelectedGameObject : null;
            if (selected != null && selected.TryGetComponent<InputField>(out var field) && field.isFocused)
            {
                Edit(field, key, () => field.DeactivateInputField(), field.ForceLabelUpdate);
                return selected.name + " (InputField)";
            }
#if TASKPROBE_TMP
            if (selected != null && selected.TryGetComponent<TMPro.TMP_InputField>(out var tmp) && tmp.isFocused)
            {
                Edit(tmp, key, () => tmp.DeactivateInputField(), tmp.ForceLabelUpdate);
                return selected.name + " (TMP_InputField)";
            }
#endif
#endif
#if TASKPROBE_UITK
            var panels = new List<KeyValuePair<UIE.IPanel, float>>();
            foreach (var d in UnityEngine.Object.FindObjectsByType<UIE.UIDocument>(FindObjectsInactive.Exclude, FindObjectsSortMode.None))
            {
                var panel = d != null && d.isActiveAndEnabled && !Probe.IsOwn(d.gameObject) ? d.rootVisualElement?.panel : null;
                if (panel == null || panels.Exists(p => p.Key == panel)) continue;
                var settings = d.panelSettings;
                // drawn over the screen (UI Toolkit's own event system sends a key nobody has focused to these alone)
                var overlay = settings != null && settings.renderMode == UIE.PanelRenderMode.ScreenSpaceOverlay;
                panels.Add(new KeyValuePair<UIE.IPanel, float>(panel, overlay ? settings.sortingOrder : float.NaN));
            }
#if TASKPROBE_UGUI
            if (events != null)
            {
                var handler = selected != null ? selected.GetComponent<UIE.PanelEventHandler>() : null;
                if (handler == null || handler.panel == null || !panels.Exists(p => p.Key == handler.panel)) return null;
                var at = Focused(handler.panel);
                SendKey(handler.panel, at, key);
                return at != null ? FocusName(at) : "the panel of " + selected.name;
            }
#endif
            foreach (var p in panels)
            {
                var at = Focused(p.Key);
                if (at == null) continue;
                SendKey(p.Key, at, key);
                return FocusName(at);
            }
            panels.RemoveAll(p => float.IsNaN(p.Value));
            panels.Sort((a, b) => b.Value.CompareTo(a.Value));  // stable enough: a sort of a few panels by their order
            foreach (var p in panels)
            {
                if (SendKey(p.Key, null, key)) return "the panel " + p.Key.visualTree.name + " (it stopped the key)";
                if (Focused(p.Key) is UIE.Focusable now) return FocusName(now);
            }
            return panels.Count > 0 ? "every panel (none took the key)" : null;
#else
            return null;
#endif
        }
#endif

#if TASKPROBE_UGUI
        /// <summary>A key into a uGUI InputField or TMP_InputField being edited, as its OnUpdateSelected takes one from
        /// IMGUI's queue: a key down through its KeyPressed; when that ends the edit (Enter on a single line, Escape),
        /// its onSubmit unless Escape cancelled it (a field without onSubmit submits as the edit ends), then the edit
        /// ended (DeactivateInputField: Escape puts the text back); else its label shown again. A key up does
        /// nothing, as there.</summary>
        static void Edit(Selectable field, Event key, Action deactivate, Action label)
        {
            if (key.type != EventType.KeyDown) return;
            var type = field.GetType();
            var pressed = type.GetMethod("KeyPressed", Members, null, new[] { typeof(Event) }, null);
            if (pressed == null)
            {
                Probe.Active?.Error("inputs: " + type.Name + " has no KeyPressed, so a key types nothing into it");
                return;
            }
            var state = pressed.Invoke(field, new object[] { key });
            if (state != null && state.ToString() == "Finish")
            {
                var canceled = type.GetProperty("wasCanceled", Members)?.GetValue(field) is bool c && c;
                if (!canceled && type.GetProperty("onSubmit", BindingFlags.Instance | BindingFlags.Public) != null)
                    type.GetMethod("SendOnSubmit", Members, null, Type.EmptyTypes, null)?.Invoke(field, null);
                deactivate();
                return;
            }
            for (var t = type; t != null; t = t.BaseType)  // TMP_InputField's own flag, as its OnUpdateSelected sets it
                t.GetField("m_IsTextComponentUpdateRequired", Members | BindingFlags.DeclaredOnly)?.SetValue(field, true);
            label();
        }
#endif

#if TASKPROBE_UITK
        /// <summary>The element of a panel that has the keyboard focus: the innermost (a TextField's text input, not
        /// the field), as UI Toolkit sends a key to it; null when none has.</summary>
        static UIE.Focusable Focused(UIE.IPanel panel)
        {
            var focus = panel.focusController;
            if (focus == null) return null;
            var leaf = typeof(UIE.FocusController).GetMethod("GetLeafFocusedElement", Members, null, Type.EmptyTypes, null);
            return (leaf != null ? leaf.Invoke(focus, null) as UIE.Focusable : null) ?? focus.focusedElement;
        }

        static string FocusName(UIE.Focusable at) =>
            at is UIE.VisualElement e ? NameOf(e) + " (" + e.GetType().Name + ")" : at.GetType().Name;

        /// <summary>A key to `at` (null: the panel's root) as a KeyDownEvent or KeyUpEvent made from the IMGUI event, as
        /// UI Toolkit makes one from a real key's. Whether it was stopped.</summary>
        static bool SendKey(UIE.IPanel panel, UIE.Focusable at, Event key)
        {
            using (var e = key.type == EventType.KeyDown ? (UIE.EventBase)UIE.KeyDownEvent.GetPooled(key) : UIE.KeyUpEvent.GetPooled(key))
            {
                e.target = (UIE.IEventHandler)at ?? panel.visualTree;
                panel.visualTree.SendEvent(e);
                return e.isPropagationStopped;
            }
        }
#endif
    }
}
