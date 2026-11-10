"""The ocr family: the ui query's frame reader (UiOcr, the Unreal probe's glyph reader ported) in the real engine. What
it reads of readouts drawn without UI components (a mesh, GL quads, OnGUI textures), every character it knows at the
sizes a HUD uses, what it refuses and why, the rows it makes, and which selects read the frame."""

from task_check import probes

MADE = "Assets/ProbeTests/ocr/Made/"
SETUP = ["ProbeTests.Ocr.OcrScenes.Build"]
SCENES = [MADE + "OcrLab.unity"]
W, H = 960, 540
ITEMS = ["00", "11", "22", "33", "44", "55", "66", "77", "88", "99", "AA", "BB", "CC", "DD", "EE", "FF", "GG", "HH",
         "II", "JJ", "KK", "LL", "MM", "NN", "OO", "PP", "QQ", "RR", "SS", "TT", "UU", "VV", "WW", "XX", "YY", "ZZ",
         "4%", "4/4", "4.4", "-4", "4:4"]  # OcrLab.Items


def px(rect):
    """A play's rect in viewport fractions as the pixels it starts and ends at."""
    return round(rect[0] * W), round(rect[1] * H), round(rect[2] * W), round(rect[3] * H)


def ink(play, shot, region):
    """The box (x0, y0 inclusive, x1, y1 exclusive) of what is drawn in `region` (pixels) of a screenshot: the pixels
    far from the background (the region's corner), as a line's marks are."""
    image = play.image(shot)
    bg = image.at(region[0], region[1])
    found = None
    for y in range(region[1], region[3]):
        for x in range(region[0], region[2]):
            if sum((a - b) ** 2 for a, b in zip(image.at(x, y), bg)) > 3 * 64 ** 2:
                found = (x, y, x + 1, y + 1) if found is None else (
                    min(found[0], x), min(found[1], y), max(found[2], x + 1), max(found[3], y + 1))
    return found


def box_of(row):
    """A row's x, y, w, h as pixels of the 960 x 540 frame: x0, y0, x1, y1."""
    return round(row["x"] * W), round(row["y"] * H), round((row["x"] + row["w"]) * W), round((row["y"] + row["h"]) * H)


def ocr_rows(rows):
    return [r for r in rows if r.get("source") == "ocr"]


def reads(t, what, rows, text, play=None, shot=None, region=None):
    """The rows hold one line read from the frame, `text`, a text row of source ocr named ScreenText; with a screenshot
    of the same frame, its box is the drawn ink's, pixel for pixel (the frame's rows from the top, the rect's pixels)."""
    ocr = ocr_rows(rows)
    t.eq(f"{what}: what it reads", [r.get("text") for r in ocr], [text])
    if len(ocr) != 1:
        return
    row = ocr[0]
    t.eq(f"{what}: name, class, source, kind", [row.get(k) for k in ("name", "class", "source", "kind")],
         ["ScreenText", "ScreenText", "ocr", "text"])
    t.ok(f"{what}: x, y, w, h are whole pixels of the frame",
         all(abs(row[k] * n - round(row[k] * n)) < 1e-9 for k, n in (("x", W), ("y", H), ("w", W), ("h", H))),
         [row.get(k) for k in "xywh"])
    if play is not None:
        t.eq(f"{what}: its box is the ink drawn in the screenshot", box_of(row), ink(play, shot, region))


def refuses(t, what, rows, why):
    """No line read from the frame; `why` is the reader's rule (or the measure) that refuses it."""
    t.eq(f"{what} reads nothing: {why}", [r.get("text") for r in ocr_rows(rows)], [])


def rect_of(play, qid):
    return next(q["select"]["rect"] for q in play.spec["queries"] if q["id"] == qid)


# -- the plays -------------------------------------------------------------------------------------------------------

def clock(t, play):
    """A clock (TIME m:ss.f, tenths of a second) and a number (HP n, 97 less every half second) that change at every
    sample read at every sample, drawn as a mesh and as GL quads, through a select of text in a rect and through a
    regex with a rect; the checker's clock and number read them; at each screenshot their boxes are the ink's."""
    samples = play.samples("clock")
    t.eq("a sample every half second to half a second past the end, the first frame's too",
         [round(s["t"], 6) for s in samples], [round(1 / 30, 6)] + [k / 2 for k in range(1, 22)])
    for s in samples:
        at = s["t"]
        frames = round(at * 30)
        tenths = frames // 3
        text = f"TIME {tenths // 600}:{tenths // 10 % 60:02d}.{tenths % 10}"
        number = 4096 - 97 * (frames // 15)
        shot = f"shot_{int(at):02d}.png" if at % 1 == 0.5 and at < 10 else None  # shots at 0.5, 1.5, ... 9.5
        for qid, what, want in (("clock", "mesh clock", text), ("points", "HP", f"HP {number}"), ("clock_gl", "GL clock", text)):
            rows = play.rows(qid, at)
            reads(t, f"{what} at {at:.2f} s", rows, want, play if shot else None, shot, px(rect_of(play, qid)))
            if qid == "clock":
                t.eq(f"mesh clock at {at:.2f} s: the checker's clock", probes.ui_clock(probes.ui_text(rows)), tenths / 10)
            if qid == "points":
                t.eq(f"HP at {at:.2f} s: the checker's number", probes.ui_number(probes.ui_text(rows)), float(number))
        t.eq(f"the regex select at {at:.2f} s", [(r.get("source"), r.get("text")) for r in play.rows("clock_regex", at)],
             [("ocr", text)])
    t.eq("the frame as displayed: the camera's background, set as 0.08, 0.08, 0.12, is the bytes 20, 20, 31",
         play.image("shot_00.png").at(600, 500), (20, 20, 31))
    t.eq("and the strokes are white", play.image("shot_00.png").at(52, 40), (255, 255, 255))


# per size, what the reader refuses of OnGUI's drawing of the items, and why (the rest read as drawn)
REFUSED = {
    16: {"DD": "the 0 and O come too near (they fit within 0.03)",
         "II": "its serifs are too small for its detail (over 0.4)",
         "OO": "an O is a 0 without its slash: two characters fit",
         "QQ": "the 0 and O come too near (within 0.2 in detail)",
         "WW": "its 1 px slanted strokes come apart in OnGUI's rotated textures, and the pieces cross the line"},
    24: {"OO": "an O is a 0 without its slash: two characters fit"},
    36: {"22": "its fit is 0.106, over the limit of 0.1 (OnGUI's slanted strokes)",
         "BB": "the 8 comes too near (it fits within 0.03)",
         "DD": "the 0 and O come too near (they fit within 0.03)",
         "OO": "an O is a 0 without its slash: two characters fit",
         "QQ": "the 0 and O come too near (they read better)",
         "SS": "the 5 comes too near (within 0.2 in detail)"},
}


def glyphs(cap):
    """Every character the reader knows, two of a kind (a sign beside a 4), each item in a query of its own, at `cap`
    px with OnGUI: each reads as drawn, or nothing (never another character)."""
    def check(t, play):
        for i, item in enumerate(ITEMS):
            qid = f"g{i:02d}"
            rows = play.rows(qid, 0.5)
            if item in REFUSED[cap]:
                refuses(t, f"{item} at {cap} px", rows, REFUSED[cap][item])
            else:
                reads(t, f"{item} at {cap} px", rows, item, play, "shot_00.png", px(rect_of(play, qid)))
    return check


def limits(t, play):
    """What the reader refuses, each beside the same readout read."""
    def at(qid):
        return play.rows(qid, 0.5)

    def read(what, qid, text):
        reads(t, what, at(qid), text, play, "shot_00.png", px(rect_of(play, qid)))

    read("HP 42 with three pixels of background inside the rect", "edge_clear", "HP 42")
    refuses(t, "HP 42 with the rect's edge on its first stroke", at("edge_touch"),
            "a mark that touches the rect's edge is cut, and a cut mark refuses the line it crosses")
    refuses(t, "HP 42 with the rect's edge in its first stroke", at("edge_cut"), "the same, cut")
    refuses(t, "HP 3 whose 3 has short hooks at both ends, OnGUI, 4 px strokes at 36 px", at("hooked3"),
            "its centre lines stop short of the hooks' ends: six of the 3's samples lie past the loose distance, a "
            "fit of 0.127 over the limit of 0.1")
    read("HP 3 with a flat-topped 3, the same strokes", "flat3", "HP 3")
    refuses(t, "HP 42 at 20 px with 5 px strokes", at("bold"),
            "too bold for its size: the loose distance, 0.04 + (0.6 + half the stroke) / height, is over 0.15")
    read("HP 42 at 20 px with 2 px strokes", "thin", "HP 42")
    refuses(t, "HP 42 slanted a quarter", at("slanted"), "slanted glyphs fit no upright shape")
    refuses(t, "a lone 7", at("lone"), "a line is two glyphs at least: a lone shape is as likely a mark")
    refuses(t, "HP 42 eleven levels brighter than the background", at("faint"),
            "ink less than 40 from the background is too faint")
    refuses(t, "HP 42 with a rule across it", at("ruled"), "a mark that crosses the line refuses it")
    read("HP 42 inside a frame", "framed", "HP 42")
    refuses(t, "HP 42 on a background that grows lighter", at("shaded"), "the rect's edge is not one even colour")
    refuses(t, "HP 42 at 8 px", at("small"), "too small for its strokes: the loose distance is over 0.15")


def found(t, play):
    """A line an element already reads as text is left to that element; a box over a line doesn't hide it."""
    rows = play.rows("found_text", 0.5)
    t.eq("the uGUI text over HP 42 reads, the line under it doesn't, the two other lines do",
         [(r.get("source"), r.get("text")) for r in rows], [("ugui", "HP"), ("ocr", "XP 17"), ("ocr", "LAP 2")])
    lines = {r.get("text"): r for r in ocr_rows(rows)}
    for text, top, what in (("XP 17", 110, "XP 17 under a uGUI box"), ("LAP 2", 190, "LAP 2 alone")):
        if text in lines:
            reads(t, what, [lines[text]], text, play, "shot_00.png", (30, top, 290, top + 60))
    t.eq("a select with a rect but no kind or text: the elements only",
         [(r.get("source"), r.get("kind")) for r in play.rows("found_any", 0.5)], [("ugui", "text"), ("ugui", "box")])


def select(t, play):
    """Only a select of text in a rect (kind text, or a text regex, with a rect) reads the frame."""
    region = px(rect_of(play, "text_rect"))
    reads(t, "kind text with a rect", play.rows("text_rect", 0.5), "HP 42", play, "shot_00.png", region)
    t.eq("a text regex with a rect", [(r.get("source"), r.get("text")) for r in play.rows("regex_rect", 0.5)],
         [("ocr", "HP 42")])
    reads(t, "the rect's corners the other way round", play.rows("swapped", 0.5), "HP 42", play, "shot_00.png", region)
    t.eq("kind text without a rect: the uGUI label only",
         [(r.get("source"), r.get("text")) for r in play.rows("text_only", 0.5)], [("ugui", "LABEL")])
    for qid, what in (("rect_only", "a rect without kind or text"), ("box_rect", "kind box with a rect"),
                      ("image_regex_rect", "kind image with a regex and a rect"), ("regex_only", "a regex without a rect")):
        t.eq(f"{what}: no row read from the frame", ocr_rows(play.rows(qid, 0.5)), [])
    for qid, what in (("outside", "a rect past the frame"), ("zero", "a rect of no size"), ("before", "a rect before the frame")):
        t.eq(f"{what}: no row, no error", play.rows(qid, 0.5), [])
    t.eq("a uGUI label in the rect: its row, and no line read from its pixels",
         [(r.get("source"), r.get("text")) for r in play.rows("label", 0.5)], [("ugui", "LABEL")])


def cap(t, play):
    """More lines read than a sample keeps: 200 rows, every match counted in total and summed in full."""
    sample = play.sample("cap", 0.5)
    rows = sample.get("rows") or []
    t.eq("280 items of 12 read", sample.get("total"), 280)
    t.eq("200 rows kept", len(rows), 200)
    t.eq("every row reads 12", sorted({r.get("text") for r in rows}), ["12"])
    full = (sample.get("full") or {}).get("x") or {}
    t.eq("full x counts every match", full.get("n"), 280)
    left = [ink(play, "shot_00.png", (col * 66 + 4, row * 26 + 4, col * 66 + 50, row * 26 + 30))[0]
            for row in range(20) for col in range(14)]
    t.near("full x sums every match's x: each item's ink, left edge over 960", full.get("sum"), sum(left) / W, 1e-9)
    t.eq("the rows kept are the first 200 lines, from the top", [box_of(r)[0] for r in rows], left[:200])


PLAYS = {
    "clock": {"check": clock, "args": ["-ocrlab", "clock"]},
    "glyphs16": {"check": glyphs(16), "args": ["-ocrlab", "glyphs", "-ocrsize", "16"]},
    "glyphs24": {"check": glyphs(24), "args": ["-ocrlab", "glyphs", "-ocrsize", "24"]},
    "glyphs36": {"check": glyphs(36), "args": ["-ocrlab", "glyphs", "-ocrsize", "36"]},
    "limits": {"check": limits, "args": ["-ocrlab", "limits"]},
    "found": {"check": found, "args": ["-ocrlab", "found"]},
    "select": {"check": select, "args": ["-ocrlab", "select"]},
    "cap": {"check": cap, "args": ["-ocrlab", "cap"]},
}
