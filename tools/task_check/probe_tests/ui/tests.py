"""The ui family: widgets (uGUI and UI Toolkit widgets' own state), ui (the UI on screen in the frame drawn after a
sample), screen (the frame's brightness) and the clicks (widget clicks, and cursor clicks under each input module)."""

import math
import re

MADE = "Assets/ProbeTests/ui/Made/"
SETUP = ["ProbeTests.Ui.UiScenes.Build"]
SCENES = [MADE + name + ".unity" for name in ("Hud", "Clicks", "ClicksOld", "ClicksNone", "Grey", "Crowd")]
W, H = 960, 540  # the frame
FLOAT = 1e-5  # a float of the game widened to a double
TURNED = 1e-4  # a rectangle turned or projected in floats
TIMES = (0.5, 1.0, 1.5, 2.0)


def frac(x, y, w, h):
    """A rectangle in pixels of the frame (y down) as viewport fractions."""
    return (x / W, y / H, w / W, h / H)


def turned(cx, cy, side):
    """The box around a square of `side` pixels turned 45 degrees about (cx, cy)."""
    half = side / math.sqrt(2.0)
    return frac(cx - half, cy - half, 2 * half, 2 * half)


def world():
    """WorldCanvas, 3 x 1 m at 10 m straight ahead of a 60-degree camera, centred: its rectangle on the frame."""
    half_h = 10.0 * math.tan(math.radians(30.0))
    half_w = half_h * W / H
    return (0.5 - 1.5 / (2 * half_w), 0.5 - 0.5 / (2 * half_h), 3.0 / (2 * half_w), 1.0 / (2 * half_h))


def lin(byte):
    """An 8-bit sRGB value as linear light."""
    c = byte / 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def srgb(linear):
    """Linear light as an 8-bit sRGB value (not rounded)."""
    c = linear * 12.92 if linear <= 0.0031308 else 1.055 * linear ** (1 / 2.4) - 0.055
    return c * 255.0


def get(play, qid, t, name, field, index=0):
    """`field` of the `index`th row named `name` in the sample of `qid` at `t` (None when there is no such row or key)."""
    rows = [r for r in play.rows(qid, t) if r.get("name") == name]
    return rows[index].get(field) if len(rows) > index else None


def names(play, qid, t):
    return [r.get("name") for r in play.rows(qid, t)]


def driver(play, t, field):
    return get(play, "driver", t, "HudDriver", "prop:UiHudDriver." + field)


def uitk(play, t, field):
    return get(play, "uitkdriver", t, "UitkDoc", "prop:UiToolkitHud." + field)


def rect(t, what, row, want, tol):
    for key, value in zip("xywh", want):
        t.near(f"{what}: {key}", (row or {}).get(key), value, tol)


def no_rect(t, what, row):
    t.eq(f"{what}: no x, y, w, h", [(row or {}).get(k) for k in "xywh"], [None] * 4)


# ---------------------------------------------------------------- widgets

VISIBLE = {  # widgets' visible: drawn on screen or not
    "VisUnder": 1, "VisClear": 0, "VisFaint": 0, "VisDim": 1, "VisHalfText": 1, "VisZero": 0, "VisOff": 0, "VisEdge": 1,
    "VisClipped": 0, "VisClippedIn": 1, "VisOffCanvasText": 0, "VisOffGraphic": 0, "VisMuted": 1, "VisLocked": 1,
    "VisHidden": 0, "VisHiddenText": 0, "VisInactive": 0, "VisInactiveText": 0, "VisMask": 1, "VisMaskedText": 1,
    "VisUitkHidden": 0, "VisUitkInvisible": 0, "VisUitkHiddenParent": 0, "VisUitkShownChild": 1, "VisUitkClear": 0,
    "VisUitkFaint": 0, "VisUitkOff": 0, "VisUitkZero": 0, "VisUitkDisabled": 1,
}
WHY = {
    "VisUnder": "under another canvas's box", "VisClear": "a text of alpha 0", "VisFaint": "a text of alpha 0.004",
    "VisDim": "a text of alpha 0.01", "VisHalfText": "alpha 0.5 in a CanvasGroup of 0.5", "VisZero": "scale 0",
    "VisOff": "off the frame", "VisEdge": "half off the frame", "VisClipped": "outside its RectMask2D",
    "VisClippedIn": "inside its RectMask2D", "VisOffCanvasText": "under a disabled Canvas", "VisOffGraphic": "its Text disabled",
    "VisMuted": "its Button disabled, its Image on", "VisLocked": "not interactable", "VisHidden": "a CanvasGroup at 0",
    "VisHiddenText": "under a CanvasGroup at 0", "VisInactive": "inactive", "VisInactiveText": "under an inactive object",
    "VisMask": "a Mask that hides its graphic", "VisMaskedText": "inside a Mask", "VisUitkHidden": "display: none",
    "VisUitkInvisible": "visibility: hidden", "VisUitkHiddenParent": "visibility: hidden, with a visible child",
    "VisUitkShownChild": "visibility: visible under a hidden parent", "VisUitkClear": "opacity 0",
    "VisUitkFaint": "opacity 0.004", "VisUitkOff": "off the frame", "VisUitkZero": "width 0",
    "VisUitkDisabled": "a disabled Button",
}
RECTS = {
    "RectTurned": turned(520, 360, 60), "RectScaled": (0.3, 0.8, 0.1, 0.1), "RectCam": frac(20, 420, 240, 60),
    "RectWorld": world(), "RectUitkScaled": (0.7, 0.8, 0.1, 0.1), "RectUitkTurned": turned(900, 360, 60),
}
NOT_ON_SCREEN = {"RectBack": "a world-space canvas behind the camera", "RectTv": "a camera canvas drawn into a texture",
                 "RectUitkTv": "a panel drawn into a texture"}


def widgets(t, play):
    """Every field of each widget type of both systems, visibility in each way, rectangles of every kind of placement,
    the selects, and the order of the rows."""
    for at in TIMES:
        t.eq(f"TMP text at {at} s: the score this frame set, tags stripped", get(play, "score", at, "ScoreText", "text"),
             f"SCORE {driver(play, at, 'score')}")
        t.eq(f"UI Toolkit label at {at} s: tags stripped", get(play, "uitk", at, "UitkLabel", "text"), f"UITK {uitk(play, at, 'frames')}")
    t.eq("a TMP typewriter (maxVisibleCharacters 5)", get(play, "type", 1.0, "TypeText", "text"), "HELLO")
    t.eq("a Text's rich text stripped", get(play, "legacy", 1.0, "LegacyLabel", "text"), "LEGACY TEXT")
    t.eq("a Text without rich text keeps what looks like tags", get(play, "rawtag", 1.0, "RawTagText", "text"), "<b>RAW</b>")
    t.eq("a TMP text changed while hidden reads its new text", get(play, "stale", 1.5, "StaleText", "text"), "AFTER")
    t.eq("... and isn't visible", get(play, "stale", 1.5, "StaleText", "visible"), 0)

    score = (play.rows("score", 1.0) or [{}])[0]
    t.eq("ScoreText: class", score.get("class"), "TextMeshProUGUI")
    t.eq("ScoreText: count", score.get("count"), 1)
    t.eq("ScoreText: visible", score.get("visible"), 1)
    rect(t, "ScoreText", score, frac(20, 10, 240, 30), FLOAT)
    t.eq("a text has no percent, value, interactable, has_brush or brush",
         [score.get(k) for k in ("percent", "value", "interactable", "has_brush", "brush")], [None] * 5)

    sliders = names(play, "sliders", 1.0)
    t.ok("Slider rows: uGUI's, then UI Toolkit's (the Scroller's own Slider too)", sliders[:2] == ["HealthSlider", "UitkSlider"], sliders)
    for at in TIMES:
        health = driver(play, at, "health")
        t.near(f"uGUI Slider value at {at} s", get(play, "sliders", at, "HealthSlider", "value"), health, FLOAT)
        t.near(f"uGUI Slider percent at {at} s", get(play, "sliders", at, "HealthSlider", "percent"), health / 100, FLOAT)
        t.near(f"filled Image percent at {at} s", get(play, "fills", at, "FillBar", "percent"), driver(play, at, "fill"), FLOAT)
        t.near(f"ProgressBar value at {at} s", get(play, "progress", at, "UitkProgress", "value"), uitk(play, at, "progress"), FLOAT)
        t.near(f"ProgressBar percent at {at} s", get(play, "progress", at, "UitkProgress", "percent"), uitk(play, at, "progress") / 100, FLOAT)
    t.eq("uGUI Slider: class, interactable, visible, text",
         [get(play, "sliders", 1.0, "HealthSlider", k) for k in ("class", "interactable", "visible", "text")], ["Slider", 1, 1, None])
    t.eq("UI Toolkit Slider: class, value, percent, interactable, visible",
         [get(play, "sliders", 1.0, "UitkSlider", k) for k in ("class", "value", "percent", "interactable", "visible")],
         ["Slider", 2.5, 0.25, 1, 1])
    t.eq("SliderInt: value, percent", [get(play, "sliderints", 1.0, "UitkSliderInt", k) for k in ("value", "percent")], [1, 0.25])
    t.eq("an Image filled to 0: percent 0, still a visible widget",
         [get(play, "fills", 1.0, "EmptyFill", k) for k in ("percent", "visible")], [0, 1])
    t.eq("FillBar: has_brush, brush", [get(play, "fills", 1.0, "FillBar", k) for k in ("has_brush", "brush")], [1, "UISprite"])
    t.eq("a ProgressBar has no text of its own", get(play, "progress", 1.0, "UitkProgress", "text"), None)

    t.eq("uGUI Toggle: value, its label's text, interactable, class",
         [get(play, "toggles", 1.0, "SoundToggle", k) for k in ("value", "text", "interactable", "class")], [1, "Sound", 1, "Toggle"])
    t.eq("UI Toolkit Toggle: value, its text", [get(play, "toggles", 1.0, "UitkToggle", k) for k in ("value", "text")], [1, "MUSIC"])
    t.eq("an InputField's text", get(play, "fields", 1.0, "NameField", "text"), "BOB")
    t.eq("an empty InputField's text (not its placeholder)", get(play, "fields", 1.0, "EmptyField", "text"), "")
    t.eq("a TMP_InputField's text", get(play, "tmpfields", 1.0, "TmpField", "text"), "TMPNAME")
    t.eq("a TextField's value", get(play, "uitkfields", 1.0, "UitkField", "text"), "ABC")
    t.eq("an empty TextField's value", get(play, "uitkfields", 1.0, "UitkEmptyField", "text"), "")
    for name, text, value in (("ModeDropdown", "HARD", 1), ("TmpDropdown", "ONE", 0), ("UitkDropdown", "BLUE", 1)):
        t.eq(f"{name}: its caption and selected index", [get(play, "dropdowns", 1.0, name, k) for k in ("text", "value")], [text, value])
    t.eq("Scrollbar: percent, value", [get(play, "bars", 1.0, "PageBar", k) for k in ("percent", "value")], [0.25, 0.25])
    t.eq("Scroller: percent, value", [get(play, "scrollers", 1.0, "UitkScroller", k) for k in ("percent", "value")], [0.5, 50])

    for qid, name, has, brush in (("pictures", "PictureRaw", 1, "UiChecker"), ("pictures", "BlankRaw", 0, None),
                                  ("images", "SpriteImage", 1, "UISprite"), ("images", "PlainImage", 0, None),
                                  ("images", "UitkImage", 1, "UiChecker"), ("uitk", "UitkBox", 0, None),
                                  ("uitk", "UitkLabel", 0, None)):
        t.eq(f"{name}: has_brush, brush", [get(play, qid, 1.0, name, k) for k in ("has_brush", "brush")], [has, brush])
    t.eq("UI Toolkit label: interactable, visible", [get(play, "uitk", 1.0, "UitkLabel", k) for k in ("interactable", "visible")], [1, 1])

    t.eq("a game's own component on an Image: class, visible, text",
         [get(play, "own", 1.0, "ScorePanel", k) for k in ("class", "visible", "text")], ["UiScoreKeeper", 1, None])
    t.eq("a game's own component on an object without a graphic: class, visible",
         [get(play, "marker", 1.0, "HudRoot", k) for k in ("class", "visible")], ["UiHudMarker", 1])
    rect(t, "HudRoot", (play.rows("marker", 1.0) or [{}])[0], frac(250, 195, 30, 30), FLOAT)

    for name, want in VISIBLE.items():
        t.eq(f"visible: {name} ({WHY[name]})", get(play, "vis", 1.0, name, "visible"), want)
    t.eq("visible: true keeps exactly the visible ones", sorted(names(play, "visonly", 1.0)),
         sorted(n for n, v in VISIBLE.items() if v))
    t.eq("interactable: a disabled Button, a non-interactable one, a disabled UI Toolkit Button",
         [get(play, "vis", 1.0, n, "interactable") for n in ("VisMuted", "VisLocked", "VisUitkDisabled")], [0, 0, 0])
    rect(t, "VisOff (off the frame, still has a rectangle)", play.row("vis", 1.0, "VisOff"), frac(-300, 230, 100, 20), FLOAT)
    rect(t, "VisEdge", play.row("vis", 1.0, "VisEdge"), frac(-50, 255, 100, 20), FLOAT)
    no_rect(t, "VisZero (scale 0)", play.row("vis", 1.0, "VisZero"))
    no_rect(t, "VisUitkHidden (display: none)", play.row("vis", 1.0, "VisUitkHidden"))
    rect(t, "VisInactive (inactive, still placed)", play.row("vis", 1.0, "VisInactive"), frac(180, 300, 150, 30), FLOAT)

    for name, want in RECTS.items():
        rect(t, name, play.row("rects", 1.0, name), want, TURNED)
        t.eq(f"{name}: visible", get(play, "rects", 1.0, name, "visible"), 1)
    for name, why in NOT_ON_SCREEN.items():
        no_rect(t, f"{name} ({why})", play.row("rects", 1.0, name))
        t.eq(f"{name}: not visible", get(play, "rects", 1.0, name, "visible"), 0)

    t.eq("a text regex picks only the matching widget", names(play, "regex", 1.0), ["ScoreText"])
    t.eq("a text regex sees a UI Toolkit label without its tags", names(play, "uitkregex", 1.0), ["UitkLabel"])
    t.eq("component Button: uGUI's Buttons, then UI Toolkit's", names(play, "buttons", 1.0),
         ["VisMuted", "VisLocked", "VisUitkDisabled", "UitkButton"])
    t.eq("a Button reads its label", get(play, "buttons", 1.0, "VisMuted", "text"), "Button")
    t.ok("an element without a name is named by its type, and a select by that name finds it",
         "ANON" in [r.get("text") for r in play.rows("anon", 1.0)], play.rows("anon", 1.0))

    order = names(play, "order", 1.0)
    t.eq("rows in hierarchy order: the first uGUI widgets", order[:6],
         ["ScoreText", "TypeText", "VisUnder", "LegacyLabel", "RawTagText", "DoomedText"])
    t.ok("uGUI widgets (a world canvas last) come before UI Toolkit's", "RectBack" in order and "UitkLabel" in order
         and order.index("RectBack") < order.index("UitkLabel"), order)
    shown, bg = (play.value("shown", 1.0) or {}).get("luma"), (play.value("bg", 1.0) or {}).get("luma")
    t.ok("the frame shows UI Toolkit's visible child of a hidden parent (green there)", shown is not None and shown > 0.5, shown)
    t.ok("... against the camera's dark background", bg is not None and bg < 0.2, bg)


# ---------------------------------------------------------------- ui

UI_KINDS = {  # (name, kind) of elements on screen
    ("ScoreText", "text"), ("TypeText", "text"), ("LegacyLabel", "text"), ("RawTagText", "text"), ("VisUnder", "text"),
    ("CoverBox", "box"), ("SpriteImage", "image"), ("PlainImage", "box"), ("PictureRaw", "image"), ("BlankRaw", "box"),
    ("FillBar", "image"), ("ScorePanel", "box"), ("RectCam", "box"), ("CamText", "text"), ("RectScaled", "box"),
    ("RectTurned", "box"), ("VisDim", "text"), ("VisHalfText", "text"), ("VisEdge", "box"), ("VisClippedIn", "box"),
    ("VisMaskedText", "text"), ("TmpSprite", "text"), ("UitkLabel", "text"), ("UitkBox", "box"), ("UitkBorder", "box"),
    ("UitkImage", "image"), ("UitkButton", "box"), ("UitkButton", "text"), ("VisUitkShownChild", "box"),
    ("RectUitkScaled", "box"), ("RectUitkTurned", "box"), ("VisUitkDisabled", "box"),
}
UI_ABSENT = (  # not on screen, or not UI
    "RectWorld", "RectBack", "RectTv", "RectUitkTv", "EmptyFill", "VisClear", "VisFaint", "VisZero", "VisOff",
    "VisClipped", "VisOffCanvasText", "VisOffGraphic", "VisHidden", "VisHiddenText", "VisInactive", "VisInactiveText",
    "VisMask", "UitkPlain", "VisUitkHidden", "VisUitkInvisible", "VisUitkHiddenParent", "VisUitkClear", "VisUitkFaint",
    "VisUitkOff", "VisUitkZero", "StaleText",
)


def ui(t, play):
    """The elements on screen, uGUI and UI Toolkit alike: which are there, their kind, source, text and rectangle;
    the selects; the frame reader's lines left to the elements that already read them."""
    for s in play.samples("all"):
        t.ok(f"the sample at {s['t']:.3f} s has rows (its frame was drawn)", isinstance(s.get("rows"), list))
    rows = play.rows("all", 1.0)
    found = {(r.get("name"), r.get("kind")) for r in rows}
    for name, kind in sorted(UI_KINDS):
        t.ok(f"on screen: {name} as {kind}", (name, kind) in found)
    for name in UI_ABSENT:
        t.ok(f"not an element on screen: {name}", name not in {r.get("name") for r in rows})
    t.ok("TMP's sub-mesh of a sprite is no element of its own", "TMP_SubMeshUI" not in {r.get("class") for r in rows},
         sorted({r.get("class") for r in rows}))
    for r in rows:
        if r.get("name", "").startswith(("Uitk", "VisUitk", "RectUitk")):
            t.eq(f"{r.get('name')} ({r.get('kind')}): source", r.get("source"), "uitk")
    t.eq("ScoreText: source, class", [get(play, "all", 1.0, "ScoreText", k) for k in ("source", "class")], ["ugui", "TextMeshProUGUI"])
    for at in TIMES:
        t.eq(f"ScoreText at {at} s: the score this frame set", get(play, "all", at, "ScoreText", "text"), f"SCORE {driver(play, at, 'score')}")
        t.eq(f"UitkLabel at {at} s, tags stripped", get(play, "all", at, "UitkLabel", "text"), f"UITK {uitk(play, at, 'frames')}")
    for name, text in (("TypeText", "HELLO"), ("LegacyLabel", "LEGACY TEXT"), ("RawTagText", "<b>RAW</b>"), ("TmpSprite", "STAR "),
                       ("CamText", "CAMERA")):
        t.eq(f"{name}: text", get(play, "all", 1.0, name, "text"), text)
    texts = [r.get("text") for r in rows if r.get("kind") == "text"]
    for text in ("BOB", "TYPE HERE", "ABC", "HINT", "HARD", "ONE", "TMPNAME", "Sound", "MUSIC"):
        t.ok(f"a text element shows {text!r}", text in texts, texts)
    t.ok("an InputField with text doesn't show its placeholder", "Enter name..." not in texts)
    t.eq("UitkButton's text", [r.get("text") for r in rows if r.get("name") == "UitkButton" and r.get("kind") == "text"], ["GO"])
    t.eq("a box has no text", [r.get("text") for r in rows if r.get("name") == "UitkButton" and r.get("kind") == "box"], [None])
    rect(t, "ScoreText", play.row("all", 1.0, "ScoreText"), frac(20, 10, 240, 30), FLOAT)
    rect(t, "UitkLabel", play.row("all", 1.0, "UitkLabel"), frac(620, 10, 200, 30), FLOAT)
    rect(t, "VisEdge (half off the frame)", play.row("all", 1.0, "VisEdge"), frac(-50, 255, 100, 20), FLOAT)
    for name in ("RectCam", "RectScaled", "RectTurned", "RectUitkScaled", "RectUitkTurned"):
        rect(t, name, play.row("all", 1.0, name), RECTS[name], TURNED)
    t.eq("kinds add up: text + image + box rows are every row",
         len(play.rows("texts", 1.0)) + len(play.rows("images", 1.0)) + len(play.rows("boxes", 1.0)), len(rows))
    t.ok("kind text: only text rows", all(r.get("kind") == "text" for r in play.rows("texts", 1.0)))
    t.eq("rect: the elements whose centre is inside", sorted((r.get("name"), r.get("kind")) for r in play.rows("corner", 1.0)),
         [("UitkBox", "box"), ("UitkImage", "image"), ("UitkLabel", "text")])
    t.eq("text in a rect reads the frame too, and a line ScoreText reads isn't read twice",
         [(r.get("name"), r.get("source")) for r in play.rows("scoreocr", 1.0)], [("ScoreText", "ugui")])
    t.eq("a text regex, UI Toolkit", names(play, "uitkrx", 1.0), ["UitkLabel"])
    t.eq("a text regex, TMP", names(play, "scorerx", 1.0), ["ScoreText"])
    # a layout change in a sample's frame (at 1 s LayoutA leaves its row, UitkMover moves): ui reads the frame drawn after
    # the sample, laid out; a widgets sample reads the place before the frame's layout pass
    for at, row, mover in ((0.5, 360, 620), (1.0, 300, 700), (1.5, 300, 700)):
        t.near(f"ui at {at} s: LayoutB's x", get(play, "all", at, "LayoutB", "x"), row / W, FLOAT)
        t.near(f"ui at {at} s: UitkMover's x", get(play, "all", at, "UitkMover", "x"), mover / W, FLOAT)
    for at, row, mover in ((0.5, 360, 620), (1.0, 360, 620), (1.5, 300, 700)):
        t.near(f"widgets at {at} s: LayoutB's x", get(play, "layout_w", at, "LayoutB", "x"), row / W, FLOAT)
        t.near(f"widgets at {at} s: UitkMover's x", get(play, "mover_w", at, "UitkMover", "x"), mover / W, FLOAT)


def life(t, play):
    """Objects destroyed between a sample and its frame, a canvas and an element made in mid-play, a scene load."""
    t.eq("0.5 s: DoomedText is a widget and an element", (names(play, "doomed_w", 0.5), names(play, "doomed_u", 0.5)),
         (["DoomedText"], ["DoomedText"]))
    t.eq("1 s: destroyed after the sample: still a widget at the sample, gone from the frame drawn after it",
         (names(play, "doomed_w", 1.0), names(play, "doomed_u", 1.0)), (["DoomedText"], []))
    t.eq("1.5 s: gone", (names(play, "doomed_w", 1.5), names(play, "doomed_u", 1.5)), ([], []))
    t.eq("1 s: a canvas and a UI Toolkit element made this frame are widgets", names(play, "born_w", 1.0), ["BornText", "UitkBorn"])
    t.eq("... and elements on screen", sorted(names(play, "born_u", 1.0)), ["BornText", "UitkBorn"])
    times = [round(s["t"], 4) for s in play.samples("grey_w")]
    t.eq("the game loads the Grey scene in the 1.5 s frame: the clock holds, that sample comes once it has loaded",
         times, [round(1 / 30, 4), 0.5, 1.0, round(46 / 30, 4), 2.0, 2.5, 3.0, 3.5])
    for at in (46 / 30, 2.0):
        t.eq(f"{at:.3f} s: the Grey scene's UI, read by widgets and ui alike", (names(play, "grey_w", at), sorted(names(play, "grey_u", at))),
             (["GreyRight"], ["BlackBox", "GreyRight", "WhiteBox"]))
    t.eq("... and nothing of the Hud", (names(play, "doomed_w", 2.0), names(play, "born_w", 2.0)), ([], []))
    t.eq("scene", play.probe.get("scene"), MADE + "Grey.unity")


def errors(t, play):
    """A select that can't work and a field that doesn't exist each give one line; the rest of the query still reads."""
    t.eq("the known field is still read", get(play, "w_field", 0.5, "ScoreText", "text"), "SCORE 150")
    t.ok("the unknown field is no key", get(play, "w_field", 0.5, "ScoreText", "percnt") is None)
    t.eq("a bad regex matches nothing", (play.rows("w_badrx", 0.5), play.rows("u_badrx", 0.5)), ([], []))
    t.eq("a kind that isn't one matches nothing", play.rows("u_badkind", 0.5), [])


# ---------------------------------------------------------------- clicks

def count(play, t, name, field, index=0):
    return get(play, "counts", t, name, "prop:UiClickCount." + field, index)


def clicks_for(module):
    """The widget clicks (the same under every input module: they need none) and the cursor clicks (only through the
    Input System's UI module, `module` "system")."""
    def check(t, play):
        system = module == "system"
        end = 5.0
        for name in ("GoButton", "TriggerButton", "LockedButton2", "BlockedButton"):
            t.eq(f"widget click on {name}: pointer enter, down, up, click once, and onClick once",
                 [count(play, end, name, f) for f in ("enters", "downs", "ups", "clicks", "fired")], [1, 1, 1, 1, 1])
        t.eq("widget click by type (Toggle): the first Toggle switched off", get(play, "toggle", 1.0, "GoToggle", "value"), 0)
        t.eq("... its onValueChanged once", count(play, end, "GoToggle", "fired"), 1)
        t.near("widget click on a Slider: it takes the value at its centre", get(play, "slider", 1.0, "GoSlider", "value"), 5.0, 1e-4)
        t.eq("EventTrigger entries: down, up, click", [get(play, "trigger", end, "TriggerButton", "prop:UiTriggerCount." + f)
                                                      for f in ("downs", "ups", "clicks")], [1, 1, 1])
        for name, why in (("LockedButton", "not interactable"), ("MutedButton", "its Button disabled"),
                          ("OffButton", "off the frame")):
            t.eq(f"not clicked: {name} ({why})", [count(play, end, name, f) for f in ("downs", "fired")], [0, 0])
        t.eq("Twin: the first in hierarchy order clicked, the second not", [count(play, end, "Twin", "fired", i) for i in (0, 1)], [1, 0])
        t.eq("UI Toolkit: Button.clicked by a widget click", get(play, "uitk", end, "UitkClicks", "prop:UiToolkitClicks.go"), 1)
        t.eq("UI Toolkit: a disabled Button and one off the frame not clicked",
             [get(play, "uitk", end, "UitkClicks", "prop:UiToolkitClicks." + f) for f in ("no", "off")], [0, 0])
        t.eq("UI Toolkit: a ClickEvent handler: not by the widget click (2 s)", get(play, "uitk", 2.5, "UitkClicks", "prop:UiToolkitClicks.evt"), 0)
        log = play.probe_log
        for widget in ("GoButton", "Toggle", "UGoButton", "UEvtButton"):
            t.ok(f"probe.log: clicked {widget}", f"clicked {widget}" in log)
        for widget in ("MutedButton", "OffButton", "UNoButton", "UOffButton", "NoSuchButton"):
            t.ok(f"probe.log: no visible button matches '{widget}'", f"no visible button matches '{widget}'" in log)
        t.eq("an EventSystem in the scene", get(play, "watch", 1.0, "Watch", "prop:UiClickWatch.system"), 0 if module == "none" else 1)
        t.eq("a click on a button that takes no selection leaves nothing selected", get(play, "watch", 1.5, "Watch", "prop:UiClickWatch.selected"), "")
        cursor = 1 if system else 0
        t.eq("cursor click on a uGUI button", count(play, end, "CursorButton", "fired"), cursor)
        t.eq("cursor click on a UI Toolkit button", get(play, "uitk", end, "UitkClicks", "prop:UiToolkitClicks.cursor"), cursor)
        t.eq("cursor click on a UI Toolkit ClickEvent handler", get(play, "uitk", end, "UitkClicks", "prop:UiToolkitClicks.evt"), cursor)
        t.eq("cursor click on BlockedButton: the image over it takes it", count(play, end, "BlockedButton", "downs"), 1)
        if system:
            t.eq("widget click on an InputField: focused", get(play, "field", 1.0, "GoField", "prop:InputField.isFocused"), 1)
            t.eq("widget click on a Dropdown: its list is open", get(play, "dropdown", end, "GoDropdown", "prop:Dropdown.m_Dropdown"), 1)
    return check


# ---------------------------------------------------------------- screen

def screen_for(post):
    """Known greys: the frame read back holds the sRGB bytes as authored in this linear project, the UI's (white, black,
    sRGB 192) and the camera's clear colour (sRGB 64, through the pipeline's float target) alike; the rect rounds out to
    whole pixels, is clamped to the frame and never empty. With post exposure +1 the camera's part doubles in linear
    light (sRGB 90) and the UI's, drawn after post-processing, doesn't change."""
    def check(t, play):
        def v(qid, key):
            return (play.value(qid, 0.5) or {}).get(key)

        camera = round(srgb(2 * lin(64))) if post else 64
        t.eq("size", v("whole", "size"), [W, H])
        for qid, lum, pixels in (("white", 1.0, 5184), ("black", 0.0, 5184), ("outside", 1.0, 5184)):
            t.near(f"{qid}: luminance", v(qid, "luminance"), lum, 1e-9)
            t.near(f"{qid}: luma", v(qid, "luma"), lum, 1e-9)
            t.eq(f"{qid}: pixels", v(qid, "pixels"), pixels)
        for qid, pixels in (("right", 259200), ("inverted", 259200), ("empty", 1), ("edge", 1), ("beyond", 540)):
            t.near(f"{qid}: luma of sRGB 192", v(qid, "luma"), 192 / 255, 1e-9)
            t.near(f"{qid}: luminance of sRGB 192", v(qid, "luminance"), lin(192), 1e-9)
            t.eq(f"{qid}: pixels", v(qid, "pixels"), pixels)
        for qid, pixels in (("camera", 129600), ("fraction", 97 * 55)):
            t.near(f"{qid}: luma of the camera's sRGB {camera}", v(qid, "luma"), camera / 255, 1e-9)
            t.near(f"{qid}: luminance of the camera's sRGB {camera}", v(qid, "luminance"), lin(camera), 1e-9)
            t.eq(f"{qid}: pixels (the rect rounded out to whole pixels)", v(qid, "pixels"), pixels)
        whole = (5184 * 255 + (259200 - 2 * 5184) * camera + 259200 * 192) / (518400 * 255)
        t.near("whole frame: luma", v("whole", "luma"), whole, 1e-9)
        t.eq("whole frame: pixels", v("whole", "pixels"), W * H)
        t.eq("a ui query in the same play reads its elements", sorted(names(play, "boxes", 0.5)), ["BlackBox", "GreyRight", "WhiteBox"])
    return check


def quit_check(t, play):
    """The game quits in the frame of the 1 s sample, before the probe takes it: the sample is taken, and the frame it
    waits for is still drawn before the player stops, so a sample without a frame isn't reached this way."""
    times = [s["t"] for s in play.samples("right")]
    t.eq("samples up to the quit", [round(x, 6) for x in times], [round(1 / 30, 6), 0.5, 1.0])
    t.near("seconds", play.probe.get("seconds"), 1.0, 1e-9)
    last_screen, last_ui = play.sample("right", 1.0) or {}, play.sample("boxes", 1.0) or {}
    t.near("the last screen sample has its value", (last_screen.get("value") or {}).get("luma"), 192 / 255, 1e-9)
    t.eq("the last ui sample has its rows", sorted(r.get("name") for r in last_ui.get("rows") or []), ["BlackBox", "GreyRight", "WhiteBox"])


# ---------------------------------------------------------------- the cap and the cost

def _real(play):
    """Seconds of real time from the clock's start to the play's end (probe.log)."""
    stamps = [float(m.group(1)) for m in re.finditer(r"^\S+ \[([\d.]+) s\] (?:the play's clock starts|the play ended)", play.probe_log, re.M)]
    return stamps[-1] - stamps[0] if len(stamps) >= 2 else None


def crowd_ui(t, play):
    """500 text elements: 200 rows kept, every one counted and summed up."""
    s = play.sample("texts", 1.0) or {}
    t.eq("total", s.get("total"), 500)
    t.eq("rows kept", len(s.get("rows") or []), 200)
    t.eq("the rows are the first 200 in order: uGUI's T000-T199", [r.get("name") for r in s.get("rows") or []],
         ["T%03d" % i for i in range(200)])
    full = (s.get("full") or {}).get("x") or {}
    t.eq("full x: n, nonzero", (full.get("n"), full.get("nonzero")), (500, 500))
    t.near("full x: min", full.get("min"), 10 / W, FLOAT)
    t.near("full x: max", full.get("max"), (10 + 47 * 19) / W, FLOAT)
    t.near("full x: sum", full.get("sum"), 25 * sum(10 + 47 * c for c in range(20)) / W, 1e-6)


def crowd(t, play):
    """widgets over 300 uGUI texts and 200 UI Toolkit labels, with ui: the cap; the cost of a sample of each."""
    crowd_ui(t, play)
    s = play.sample("uguitexts", 1.0) or {}
    t.eq("widgets Text: total, rows kept", (s.get("total"), len(s.get("rows") or [])), (300, 200))
    t.eq("... in order", [r.get("name") for r in s.get("rows") or []], ["T%03d" % i for i in range(200)])
    t.eq("... full is empty: text isn't a number", s.get("full"), {})
    labels = play.sample("labels", 1.0) or {}
    t.eq("widgets Label: every one, no total", (len(labels.get("rows") or []), labels.get("total")), (200, None))
    bare, alone, both = _real(play.earlier("crowd_bare")), _real(play.earlier("crowd_ui")), _real(play)
    samples = len(play.samples("texts"))
    if None not in (bare, alone, both) and samples:
        ui_ms, widgets_ms = 1000 * (alone - bare) / samples, 1000 * (both - alone) / samples
        t.ok(f"cost of a ui sample over 500 elements: {ui_ms:.1f} ms; of the two widgets samples: {widgets_ms:.1f} ms "
             "(each under 20 ms)", ui_ms < 20 and widgets_ms < 20, (ui_ms, widgets_ms))
    else:
        t.ok("probe.log gives the plays' real times", False, (bare, alone, both))


PLAYS = {
    "widgets": {"check": widgets},
    "ui": {"check": ui},
    "life": {"check": life, "args": ["-uilife"]},
    "errors": {"check": errors, "errors": [
        r"^widgets w_badrx: the text regex \(\[ doesn't compile$", r"^ui u_badrx: the text regex \(\[ doesn't compile$",
        r"^ui u_badkind: no element kind line \(text, box, image\)$", r"^widgets w_field: no field percnt$",
        r"^ui u_field: no field bogus$", r"^widgets w_type: no component type NoSuchWidgetType$"]},
    "clicks": {"check": clicks_for("system")},
    "clicks_old": {"check": clicks_for("old")},
    "clicks_none": {"check": clicks_for("none")},
    "screen": {"check": screen_for(False)},
    "screen_post": {"check": screen_for(True), "args": ["-uipost"]},
    "quit": {"check": quit_check, "args": ["-uiquit"], "ended": "shutdown"},
    # the cost is measured in real time; probe.json is the same in two plays
    "crowd_bare": {"check": lambda t, play: None},
    "crowd_ui": {"check": crowd_ui},
    "crowd": {"check": crowd},
}
