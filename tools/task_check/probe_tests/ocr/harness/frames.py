"""Synthetic frames for the frame reader (UiOcr) outside Unity: text drawn with strokes along the centre lines of the
reader's own glyph table, every way a HUD draws them (round caps, square caps as OnGUI's rotated textures give, butt
ends; anti-aliased or not, blended in sRGB or in linear light; light on dark and dark on light; many sizes and stroke
widths), and frames for each of the reader's rules (edges, spacing, refusals, rects, two marks of one left edge).

    python frames.py <out dir>   writes <name>.raw (width, height as uint32 LE, then RGB rows from the top) and
                                 cases.txt (one line a reading: <name>.raw x0 y0 x1 y1, the rect in viewport fractions)

Deterministic (the same bytes on every machine). Standard library only."""
import json
import math
import os
import re
import struct
import sys

# the reader's reference glyph table, one ["character", "lines"] a line: kept here, not read
# from the UiOcr.cs under test, so a changed table can't change the frames it is tested on
with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "table.txt"), encoding="utf-8") as _table:
    TABLE = [tuple(json.loads(line)) for line in _table if line.strip()]
assert len(TABLE) == 121, len(TABLE)
FIRST = {}
for _c, _s in TABLE:
    FIRST.setdefault(_c, _s)
# shapes it reads at the sizes a HUD uses (a slashed 0, a 1 with a flag, a flat-topped 3, ...); letters: their first
CLEAR = dict(FIRST)
CLEAR.update({"0": TABLE[3][1], "1": TABLE[16][1], "3": TABLE[31][1], "5": TABLE[41][1], "6": TABLE[50][1],
              "8": TABLE[64][1], "9": TABLE[70][1], "I": TABLE[19][1], "M": TABLE[95][1], "W": TABLE[113][1]})
# a stroke readout's font whose 3 has short hooks at both ends
HOOKED = dict(CLEAR)
HOOKED["3"] = TABLE[29][1]


def polylines(spec):
    return [[tuple(float(v) for v in p.split(",")) for p in poly.split()] for poly in spec.split(";")]


class Canvas:
    """Coverage at s x s samples a pixel; a shape fills the samples whose centres it holds, row by row."""

    def __init__(self, w, h, s):
        self.w, self.h, self.s, self.sw, self.sh = w, h, s, w * s, h * s
        self.bits = bytearray(self.sw * self.sh)

    def fill(self, ylo, yhi, span):
        s = self.s
        for j in range(max(0, math.ceil(ylo * s - 0.5)), min(self.sh - 1, math.floor(yhi * s - 0.5)) + 1):
            got = span((j + 0.5) / s)
            if got is None:
                continue
            i0, i1 = max(0, math.ceil(got[0] * s - 0.5)), min(self.sw - 1, math.floor(got[1] * s - 0.5))
            if i1 >= i0:
                self.bits[j * self.sw + i0:j * self.sw + i1 + 1] = b"\x01" * (i1 - i0 + 1)

    def polygon(self, pts):
        def span(y):
            xs = []
            for (x0, y0), (x1, y1) in zip(pts, pts[1:] + pts[:1]):
                if (y0 - y) * (y1 - y) <= 0:
                    xs += [x0, x1] if y1 == y0 else [x0 + (y - y0) * (x1 - x0) / (y1 - y0)]
            return (min(xs), max(xs)) if xs else None
        self.fill(min(p[1] for p in pts), max(p[1] for p in pts), span)

    def segment(self, a, b, width, cap):
        """A stroke: cap "round" (a capsule), "square" (half a width longer at both ends), "butt"."""
        (ax, ay), (bx, by), r = a, b, width / 2.0
        length = math.hypot(bx - ax, by - ay)
        ux, uy = ((bx - ax) / length, (by - ay) / length) if length > 0 else (1.0, 0.0)
        nx, ny, ext = -uy, ux, (r if cap == "square" else 0.0)
        p, q = (ax - ux * ext, ay - uy * ext), (bx + ux * ext, by + uy * ext)
        if length > 0 or cap != "round":
            self.polygon([(p[0] + nx * r, p[1] + ny * r), (q[0] + nx * r, q[1] + ny * r),
                          (q[0] - nx * r, q[1] - ny * r), (p[0] - nx * r, p[1] - ny * r)])
        if cap == "round":
            for cx, cy in (a, b):
                self.fill(cy - r, cy + r, lambda y, cx=cx, cy=cy: (
                    cx - math.sqrt(max(0.0, r * r - (y - cy) ** 2)), cx + math.sqrt(max(0.0, r * r - (y - cy) ** 2))))

    def box(self, x0, y0, x1, y1):
        self.polygon([(x0, y0), (x1, y0), (x1, y1), (x0, y1)])

    def coverage(self, x, y):
        s = self.s
        return sum(sum(self.bits[j * self.sw + x * s:j * self.sw + x * s + s]) for j in range(y * s, y * s + s)) / (s * s)


def to_linear(c):
    c /= 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def to_srgb(v):
    v = min(max(v, 0.0), 1.0)
    return round(255 * (v * 12.92 if v <= 0.0031308 else 1.055 * v ** (1 / 2.4) - 0.055))


class Frame:
    def __init__(self, w, h, bg=(20, 20, 31), aa=1, blend="srgb", base=None):
        self.w, self.h, self.bg, self.aa, self.blend, self.base = w, h, bg, aa, blend, base
        self.layers = []

    def layer(self, ink):
        canvas = Canvas(self.w, self.h, self.aa)
        self.layers.append((canvas, ink))
        return canvas

    def text(self, s, x, y, cap, stroke, style="square", font=CLEAR, gap=None, space=None, ink=(255, 255, 255), shear=0.0):
        """A line of text: the top left of the first glyph's centre lines at (x, y); a glyph is 4 x 6 units of cap / 6."""
        c, unit = self.layer(ink), cap / 6.0
        gap = 0.33 * cap + stroke if gap is None else gap
        space = cap if space is None else space
        dot = stroke + 1.0
        for ch in s:
            if ch == " ":
                x += space
            elif ch in ":.":
                if ch == ":":
                    c.box(x, y + 2 * unit - dot / 2, x + dot, y + 2 * unit + dot / 2)
                c.box(x, y + cap + stroke / 2 - dot, x + dot, y + cap + stroke / 2)
                x += dot + 0.33 * cap
            elif ch == "-":
                c.box(x, y + 3 * unit - stroke / 2, x + 2.4 * unit, y + 3 * unit + stroke / 2)
                x += 2.4 * unit + 0.33 * cap
            else:
                for poly in polylines(font[ch]):
                    pts = [(x + (px + shear * (6 - py)) * unit, y + py * unit) for px, py in poly]
                    for a, b in zip(pts, pts[1:]):
                        c.segment(a, b, stroke, style)
                x += 4 * unit + gap
        return c

    def save(self, path):
        out = bytearray(self.w * self.h * 3)
        for y in range(self.h):
            for x in range(self.w):
                out[(y * self.w + x) * 3:(y * self.w + x) * 3 + 3] = bytes(self.base(x, y) if self.base else self.bg)
        for canvas, ink in self.layers:
            lin = [to_linear(v) for v in ink]
            for y in range(self.h):
                for x in range(self.w):
                    a = canvas.coverage(x, y) if canvas.s > 1 else canvas.bits[y * canvas.sw + x]
                    if a <= 0:
                        continue
                    i = (y * self.w + x) * 3
                    old = out[i:i + 3]
                    if self.blend == "linear":
                        new = [to_srgb(to_linear(o) + a * (li - to_linear(o))) for o, li in zip(old, lin)]
                    else:
                        new = [int(round(o + a * (v - o))) for o, v in zip(old, ink)]
                    out[i:i + 3] = bytes(new)
        with open(path, "wb") as f:
            f.write(struct.pack("<II", self.w, self.h) + out)


def width_of(s, cap, stroke, gap=None, space=None):
    unit, gap = cap / 6.0, (0.33 * cap + stroke if gap is None else gap)
    return sum((cap if space is None else space) if ch == " " else stroke + 1 + 0.33 * cap if ch in ":." else
               2.4 * unit + 0.33 * cap if ch == "-" else 4 * unit + gap for ch in s)


def cases():
    """(name, Frame, rect) for every reading."""
    out = []

    def one(name, s, cap, stroke, style="square", font=CLEAR, aa=1, blend="srgb", bg=(20, 20, 31), ink=(255, 255, 255),
            margin=None, gap=None, space=None, shear=0.0):
        m = margin if margin is not None else max(6, int(cap * 0.6))
        fr = Frame(int(math.ceil(width_of(s, cap, stroke, gap, space) + 2 * m + stroke)), int(math.ceil(cap + 2 * m + stroke)),
                   bg=bg, aa=aa, blend=blend)
        fr.text(s, m + stroke / 2, m + stroke / 2, cap, stroke, style, font, gap, space, ink, shear)
        out.append((name, fr, (0, 0, 1, 1)))

    # every shape of the table, twice on a line (signs beside a 4): square caps, and round caps anti-aliased
    for i, (c, spec) in enumerate(TABLE):
        pair = {"%": "4%", "/": "4/4"}.get(c, c + c)
        one(f"tab{i:03d}_sq", pair, 24, 3, "square", {c: spec, "4": TABLE[32][1]})
        one(f"tab{i:03d}_rd", pair, 20, 2, "round", {c: spec, "4": TABLE[32][1]}, aa=4)
    # HUD strings at HUD sizes
    for s in ("TIME 1:23.4", "HP 97%", "LAP 2/3", "PTS 4096", "-42", "0123456789", "ACEFGHJKLMNPRTUVWXYZ"):
        for cap, stroke in ((12, 1), (16, 1), (24, 2), (36, 3), (48, 4)):
            tag = re.sub(r"[^A-Z0-9]", "_", s)
            one(f"hud_{tag}_{cap}_sq", s, cap, stroke, "square")
            one(f"hud_{tag}_{cap}_rd", s, cap, stroke, "round", aa=4, blend="linear")
    # the 3 with short hooks at both ends
    for cap, stroke in ((24, 2), (36, 2), (36, 4), (48, 4)):
        for style in ("square", "round", "butt"):
            one(f"hooked3_{cap}_{stroke}_{style}", "HP 3", cap, stroke, style, HOOKED)
    # colours
    for bg, ink, blend in (((255, 255, 255), (0, 0, 0), "srgb"), ((30, 60, 150), (250, 220, 40), "linear"),
                           ((128, 128, 128), (0, 0, 0), "srgb"), ((10, 10, 10), (90, 90, 90), "srgb"),
                           ((40, 40, 40), (60, 60, 60), "srgb")):
        for aa in (1, 4):
            one(f"col_{bg[0]}_{ink[0]}_{aa}", "PTS 4096", 20, 2, "round", aa=aa, blend=blend, bg=bg, ink=ink)
    # the rect's edge 0 to 4 px from the strokes
    for margin in range(5):
        for style in ("square", "round"):
            one(f"edge_{margin}_{style}", "LAP 2/3", 24, 3, style, margin=margin)
    # spacing: letters close and far, word gaps, items apart
    for gap in (0.5, 1, 2, 4, 8, 16):
        one(f"gap_{gap}", "AX 12", 24, 3, "round", aa=4, gap=gap)
    for space in (6, 10, 14, 20, 30, 60, 70):
        one(f"space_{space}", "AX 12", 24, 3, "round", aa=4, space=space)
    # refusals: slanted, lone, too small or too bold
    for shear in (0.1, 0.2, 0.3):
        one(f"slanted_{shear}", "HP 42", 24, 3, "round", aa=4, shear=shear)
    for s in ("7", "A", "%"):
        one(f"lone_{ord(s)}", s, 24, 3, "round", aa=4)
    for cap, stroke in ((6, 1), (7, 1), (8, 1), (9, 1), (8, 2), (12, 3), (16, 4), (20, 5), (24, 6), (28, 7)):
        one(f"bold_{cap}_{stroke}", "HP 42", cap, stroke, "round", aa=4)

    # whole frames: two lines in a box, rects of every kind, a rule, a frame, a background that varies, specks
    def big(name, build, rects):
        fr = Frame(960, 540, bg=(52, 72, 98))
        build(fr)
        for tag, rect in rects:
            out.append((name + tag, fr, rect))

    def boxed(fr):
        fr.layer((20, 20, 31)).box(20, 390, 420, 520)
        fr.text("TIME 1:42", 30, 405, 36, 4, "square", HOOKED)
        fr.text("HP 81%", 30, 465, 36, 4, "square", HOOKED)

    big("boxed", boxed, [("", (0.022, 0.73, 0.43, 0.96)), ("_swapped", (0.43, 0.96, 0.022, 0.73)),
                         ("_cut", (0.03, 0.73, 0.43, 0.96)), ("_zero", (0.2, 0.8, 0.2, 0.8)), ("_out", (1.2, 1.2, 1.5, 1.5)),
                         ("_before", (-0.5, -0.5, -0.1, -0.1)), ("_whole", (0, 0, 1, 1)), ("_far", (0.022, 0.73, 1e7, 0.96))])

    def ruled(fr):
        boxed(fr)
        fr.layer((255, 255, 255)).box(25, 423, 410, 425)

    big("ruled", ruled, [("", (0.022, 0.73, 0.43, 0.96))])

    def framed(fr):
        fr.layer((20, 20, 31)).box(20, 390, 420, 520)
        rim = fr.layer((255, 255, 255))
        for b in ((24, 394, 416, 396), (24, 514, 416, 516), (24, 394, 26, 516), (414, 394, 416, 516)):
            rim.box(*b)
        fr.text("TIME 1:42", 40, 410, 36, 4, "square")

    big("framed", framed, [("", (0.022, 0.73, 0.43, 0.96))])

    def shaded(fr):
        fr.base = lambda x, y: (min(255, x // 4), 40, 60)
        fr.text("TIME 1:42", 30, 405, 36, 4, "square")

    big("shaded", shaded, [("", (0.022, 0.73, 0.43, 0.96))])

    def specks(fr):
        boxed(fr)
        sp = fr.layer((255, 255, 255))
        sp.box(140, 430, 141, 431)
        sp.box(300, 470, 301, 472)

    big("specks", specks, [("", (0.022, 0.73, 0.43, 0.96))])

    def items(fr):
        fr.text("12", 30, 405, 36, 4, "square")
        fr.text("34", 260, 405, 36, 4, "square")

    big("items", items, [("", (0.0, 0.7, 0.5, 0.9))])

    # two marks that start at one column, the narrow one over the glyph before: which glyph it joins is the sort's
    tie = Frame(240, 160)
    lay = tie.layer((255, 255, 255))
    for b in ((100, 100, 111, 102), (100, 118, 111, 120), (100, 100, 104, 120), (109, 106, 110, 114),
              (109, 103, 131, 105), (128, 103, 131, 120)):
        lay.box(*b)
    out.append(("tie", tie, (0, 0, 1, 1)))
    return out


def main(folder):
    os.makedirs(folder, exist_ok=True)
    lines, saved = [], {}
    for name, frame, rect in cases():
        file = saved.get(id(frame))
        if file is None:
            file = saved[id(frame)] = name + ".raw"
            frame.save(os.path.join(folder, file))
        lines.append(file + " " + " ".join(repr(float(v)) for v in rect) + " " + name)
    with open(os.path.join(folder, "cases.txt"), "w", newline="\n") as f:
        f.write("\n".join(lines) + "\n")
    print(len(lines), "readings of", len(saved), "frames in", folder)


if __name__ == "__main__":
    main(sys.argv[1])
