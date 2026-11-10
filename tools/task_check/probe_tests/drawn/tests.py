"""The drawn family: what `drawn` reads in a place, lit / glow as rendered, and that a probe render puts back everything
it changes (the game's frames are the same with and without the renders, whatever the game's camera callbacks do);
the same values under URP's Forward, Forward+ and Deferred renderers, HDR off and render scale 0.75, D3D11 and D3D12;
one error and no value where the probe can't render (no URP, the 2D renderer, no graphics device); a coin that spins
and bobs; the cap on renderers in a place; the cost of a render."""

import math
import re

MADE = "Assets/ProbeTests/drawn/Made/"
SETUP = ["ProbeTests.Drawn.DrawnScenes.Build"]
SCENES = [MADE + "DrawnLab.unity", MADE + "DrawnBaked.unity", MADE + "DrawnCoin.unity"]

COLOUR = 1e-4  # a base colour through the shader's float maths, against the material's colour made linear
EDGE = 0.01  # a glow render's pixel counts whole or not at all: a box's outline is off by about one pixel (1%)
FLAT = 0.02  # the same for a flat quad seen at a slant: all of it is outline (about 290 pixels a view against 4,500)
HALF = 5e-4  # the terrain shader blends its layers in half precision: two of its steps near 0.3
GLOW = 1.5  # the luminance the family's glow shader gives off (_Glow 1.5 grey)
TIMES = [2.0, 4.0, 5.5]  # when the pipeline plays are compared with the main play
THREW = r"^rendering: InvalidOperationException in a render: no value that sample \(the exception is in probe\.log\)$"


def linear(c):
    """An sRGB channel as the shader gets it (Unity makes a material's colour linear)."""
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def colour(play, qid, t):
    v = play.value(qid, t) or {}
    return [v.get("base_r"), v.get("base_g"), v.get("base_b")]


def base(t, play, qid, at, want, what, tol=COLOUR):
    for name, got, w in zip("rgb", colour(play, qid, at), want):
        t.near(f"{what}: base_{name} at {at} s", got, w, tol)


def values(play, qid):
    return [(s["t"], s.get("value")) for s in play.samples(qid)]


def row(play, qid, t, name):
    return play.row(qid, t, name) or {}


def costs(play):
    """{query id or "glow render": (ms a sample or render, over how many)} from the last cost line of each in probe.log."""
    found = {}
    for line in play.probe_log.splitlines():
        m = re.search(r"\] drawn (\S+): [\d.]+ ms this sample, ([\d.]+) ms a sample over (\d+)", line)
        if m:
            found[m.group(1)] = (float(m.group(2)), int(m.group(3)))
        m = re.search(r"\] glow render: [\d.]+ ms this render, ([\d.]+) ms a render over (\d+)", line)
        if m:
            found["glow render"] = (float(m.group(1)), int(m.group(2)))
    return found


def still(t, play, qid, what):
    """No value the first sample, then 0 at every sample: nothing in the place changes."""
    got = values(play, qid)
    t.ok(f"{what}: motion has no value the first sample", got and got[0][1] is not None and got[0][1]["motion"] is None, got[:1])
    t.ok(f"{what}: motion is 0 at every later sample", all(v is not None and v["motion"] == 0.0 for _, v in got[1:]),
         [v and v["motion"] for _, v in got])


def moving(t, play, qid, what, floor=0.0):
    got = values(play, qid)
    t.ok(f"{what}: motion is above {floor} at every sample after the first",
         len(got) > 2 and all(v is not None and v["motion"] is not None and v["motion"] > floor for _, v in got[1:]),
         [v and v["motion"] for _, v in got])


def same_frames(t, play, other):
    """Every pixel of each screenshot is the other play's."""
    for shot in play.probe.get("screenshots") or []:
        a, b = play.image(shot), other.image(shot)
        if a.rows == b.rows:
            t.ok(f"{shot} is the same pixel for pixel", True)
            continue
        differ = sum(1 for y in range(a.height) for x in range(a.width) if a.at(x, y) != b.at(x, y))
        t.ok(f"{shot} is the same pixel for pixel", False, f"{differ} pixels differ")


def no_leak(t, play, at):
    r = row(play, "leak", at, "LeakWatch")
    t.ok("the leak watch compared the state before and after the samples in every frame",
         (r.get("prop:DrawnLeakWatch.frames") or 0) >= 30 * at - 5, r)
    t.eq("no frame where a render left anything changed", r.get("prop:DrawnLeakWatch.leaks"), 0)
    t.eq("and nothing changed from one frame to the next (nothing outlasts a render)", r.get("prop:DrawnLeakBefore.drifts"), 0)


# ---------------------------------------------------------------- the main play


def plain(t, play):
    """The scene without a single render of the probe's: the frames the main play must match."""
    t.eq("two screenshots", play.probe.get("screenshots"), ["shot_00.png", "shot_01.png"])
    no_leak(t, play, 16.0)


def main(t, play):
    """Everything `drawn` reads and everything a glow render reads, and that none of it shows in the game."""
    red = [linear(0.8), linear(0.2), linear(0.1)]
    base(t, play, "red", 2.0, red, "a red URP Lit cube reads its material's colour, linear")
    still(t, play, "red", "a still cube")
    t.eq("no base_ field asked: no base colour", colour(play, "red_motion", 2.0), [None, None, None])
    still(t, play, "red_motion", "a still cube read without base")
    whole, band = (play.value("red", 2.0) or {}).get("pixels"), (play.value("red_band", 2.0) or {}).get("pixels")
    t.ok("the height band y 1.2 to 3 keeps only the cube's top part", whole and band and 0 < band < whole / 2, (band, whole))
    base(t, play, "red_band", 2.0, red, "the band reads the same colour")
    got = colour(play, "checker", 2.0)
    t.near("a red and blue checker texture: no green", got[1], 0.0, COLOUR)
    t.near("its red and blue add up to 1 (filtering mixes the two)", (got[0] or 0) + (got[2] or 0), 1.0, 1e-3)
    t.near("its red and blue in about equal parts", got[0], 0.5, 0.02)
    base(t, play, "tint", 2.0, [linear(0.1), linear(0.6), linear(0.3)], "a white material tinted by a property block")
    base(t, play, "two_top", 2.0, [1.0, 0.0, 0.0], "the band above y 1: the red upper half only")
    base(t, play, "two_low", 2.0, [0.0, 0.0, 1.0], "the band 0.3 below the point: the blue lower half only (the views aren't flipped)")
    moving(t, play, "spin", "a cube turning 90 degrees a second", 0.5)
    moving(t, play, "pan", "a quad whose texture pans", 0.3)
    t.ok("its base colour hardly changes as the checker pans",
         all(v is not None and v["base_change"] is not None and v["base_change"] < 0.005 for _, v in values(play, "pan")))
    sparks = [v for at, v in values(play, "sparks") if at >= 1.0]
    t.ok("translucent particles are drawn", all(v and v["drawn"] == 1.0 for v in sparks), sparks[:2])
    t.ok("and have no base colour (nothing opaque)", all(v and v["base_r"] is None for v in sparks))
    moving(t, play, "sparks", "particles that play", 0.3)
    late = values(play, "late")
    t.ok("a cube activated at 5 s: nothing drawn before", all(v and v["drawn"] == 0.0 for at, v in late if at <= 4.5), late[:3])
    t.ok("and drawn after", all(v and v["drawn"] == 1.0 for at, v in late if at >= 5.5))
    first = next((v for at, v in late if v and v["drawn"] == 1.0), {})
    t.eq("the sample it appears in: every pixel changed", first.get("motion"), 1.0)
    t.eq("and its base colour is the first one: no change", first.get("base_change"), 0.0)
    base(t, play, "late", 6.0, [linear(0.9), linear(0.8), linear(0.1)], "the late cube's colour")
    empty = values(play, "empty")
    t.ok("inside a sphere 64 m across, 20 times the place and more: nothing rendered",
         all(v and v["primitives"] == 0.0 and v["drawn"] == 0.0 for _, v in empty), empty[:2])
    wide = values(play, "empty_wide")
    t.ok("a place 4 m wide in it (the sphere under 20 times its size): the sphere is rendered, and from inside it draws nothing",
         all(v and v["primitives"] == 1.0 and v["drawn"] == 0.0 for _, v in wide), wide[:2])
    for qid, what in (("beam", "a cube growing along the line"), ("line", "a LineRenderer growing the same way")):
        pixel = (10 + 2 * 0.3 + 0.2) / 128  # the views' width over their pixels
        step = 10 / min(128, math.floor(10 / max(10 / 128, pixel)))
        for at in (5.0, 10.0, 14.0):
            true = 0.5 + 8.5 * min(max((at - 2.0) / 10.0, 0.0), 1.0)
            v = play.value(qid, at) or {}
            t.near(f"{what}: reach at {at} s, within a pixel", v.get("reach"), true, pixel + 0.03)
            t.near(f"{what}: length at {at} s, within two steps", v.get("length"), true, 2 * step + 0.03)
    base(t, play, "glow_base", 2.0, [linear(0.2), linear(0.4), linear(0.6)], "an emissive Lit cube: the albedo, the emission cancelled")
    base(t, play, "lit_white", 2.0, [1.0, 1.0, 1.0], "a white Lit cube: white (the white ambient is 1/0.96)")
    base(t, play, "sh_probe", 2.0, [1 / 0.96] * 3, "a shader showing the ambient itself: 1/0.96")
    cube, canvas = (play.value("canvas_ui", 2.0) or {}).get("pixels"), (play.value("canvas", 2.0) or {}).get("pixels")
    t.ok("a world-space canvas on the UI layer beside a cube: the cube alone", cube and cube > 0, cube)
    t.ok("one on the cube's own layer is drawn with it", canvas and cube and canvas > cube, (canvas, cube))
    ui = play.value("ui_cube", 2.0) or {}
    t.ok("a cube on the UI layer isn't rendered", ui.get("primitives") == 0.0 and ui.get("drawn") == 0.0, ui)
    t.eq("a cube on a layer only a RenderObjects pass draws (here every layer is drawn)", (play.value("only_cube", 2.0) or {}).get("drawn"), 1.0)
    t.eq("a cube on the layer the family's renderer filters out (here every layer is drawn)", (play.value("never_cube", 2.0) or {}).get("drawn"), 1.0)
    t.eq("a cube on a terrain: both are rendered", (play.value("terrain", 2.0) or {}).get("primitives"), 2.0)
    ground = play.value("terrain_ground", 2.0) or {}
    t.ok("bare terrain: the terrain alone, drawn", ground.get("primitives") == 1.0 and ground.get("drawn") == 1.0, ground)
    base(t, play, "terrain_ground", 2.0, [linear(0.6), linear(0.4), linear(0.2)], "and it reads its layer's colour", HALF)
    still(t, play, "terrain_ground", "a still terrain")
    t.eq("the place behind the player's camera has things drawn", (play.value("behind", 2.0) or {}).get("drawn"), 1.0)
    glow(t, play, 2.0)
    watchers(t, play, 16.0)
    no_leak(t, play, 16.0)
    same_frames(t, play, play.earlier("plain"))
    cost = costs(play)
    t.ok("cost: drawn near a point with base, at most 32 ms a sample (contract 5-8 ms)", cost.get("red", (99,))[0] < 32, cost.get("red"))
    t.ok("cost: drawn along a line, at most 16 ms a sample (contract 4 ms)", cost.get("beam", (99,))[0] < 16, cost.get("beam"))
    t.ok("cost: a glow render, at most 12 ms (contract 3 ms)", cost.get("glow render", (99,))[0] < 12, cost.get("glow render"))


def glow(t, play, at):
    """lit / glow read as rendered, through an objects query; and the budget of 64 renders a frame."""
    def g(name):
        return row(play, "glow", at, name)

    def rendered(name, want, what, tol=EDGE):
        r = g(name)
        t.eq(f"{what}: read as rendered", r.get("glow_read"), "render")
        t.eq(f"{what}: lit", r.get("lit"), 1.0)
        t.near(f"{what}: glow", r.get("glow"), want, tol * want)

    rendered("G_Custom", GLOW * 1.5, "a 1 m cube glowing 1.5 all over: 1.5 x a quarter of its 6 m2")
    rendered("G_CustomBig", GLOW * 6.0, "the same, 2 m: four times")
    # Unity's sphere mesh is a polygon of 24 sides around: its outline is about 1% smaller than a circle's
    rendered("G_CustomSphere", GLOW * (math.pi / 4) / math.sqrt(3) * 1.5, "a 1 m sphere glowing 1.5: the share of its box's seen area it covers", 0.02)
    rendered("G_Skinned", GLOW * 2.5, "a skinned cube stretched 2 x 1 x 1 by its root bone: framed in that bone's space")
    rendered("G_Quad", GLOW * 0.25, "a one-sided quad: half the views see its front, a quarter of 2 m2 x half", FLAT)
    rendered("G_Huge", GLOW * 1.5e6, "a 1000 m cube: 1.5 x a quarter of its 6 km2")
    r = g("G_LitRendered")
    t.eq("a URP Lit emissive cube with a second material that draws nothing: read as rendered", r.get("glow_read"), "render")
    t.eq("and lit", r.get("lit"), 1.0)
    t.near("its glow is the emission's luminance (2, 1, 0.5 as the shader gets it) x 1.5", r.get("glow"),
           (0.2126 * 2 + 0.7152 * 1 + 0.0722 * 0.5) * 1.5, EDGE * 1.765)
    for name, where in (("G_WhiteRendered", "in the realtime reflection probe's box"), ("G_WhiteOutside", "outside it (the sky's reflection)")):
        r = g(name)
        t.ok(f"a white Lit cube {where}, under the sun, a lamp and the ambient, as rendered: dark",
             r.get("glow_read") == "render" and r.get("lit") == 0.0 and r.get("glow") == 0.0, r)
    r = g("G_Zero")
    t.ok("a cube scaled to nothing: rendered, dark", r.get("glow_read") == "render" and r.get("lit") == 0.0 and r.get("glow") == 0.0, r)
    r = g("G_Ui")
    t.ok("a cube on the UI layer: not rendered, no value", r.get("glow_read") == "unread" and "lit" not in r and "glow" not in r, r)
    for name in ("G_Only", "G_Never"):
        r = g(name)
        t.ok(f"{name} (here its layer is drawn): lit as rendered", r.get("glow_read") == "render" and r.get("lit") == 1.0, r)
    r = g("G_Sparks")
    t.ok("live particles: lit, some glow, read as rendered", r.get("glow_read") == "render" and r.get("lit") == 1.0 and (r.get("glow") or 0) > 0, r)
    c = (play.rows("sparks_glow", at) or [{}])[0]
    t.ok("the particle system read by a components query in the same frame: the same reading",
         c.get("lit") == r.get("lit") and c.get("glow") == r.get("glow"), (c, r))
    renders = sum(1 for x in play.rows("glow", at) if x.get("glow_read") == "render")
    budget = play.rows("budget", at)
    read = [x["name"] for x in budget if x.get("glow_read") == "render"]
    t.eq("70 budget cubes", len(budget), 70)
    t.eq(f"the budget: 64 renders a frame, {renders} spent by the light sources first, the next cubes in hierarchy order",
         read, ["B_%02d" % i for i in range(64 - renders)])
    t.ok("the cubes past the budget have no value that sample",
         all(x.get("glow_read") == "unread" and "lit" not in x for x in budget[64 - renders:]), budget[64 - renders:][:2])


def watchers(t, play, at):
    """What the game sees of the probe's renders (the limits the docs state)."""
    inside, away = row(play, "watch", at, "Watch_In"), row(play, "watch", at, "Watch_Away")
    p = "prop:DrawnWatcher."
    t.eq("the game counts one enabled camera (the probe's is disabled)", inside.get(p + "allCameras"), 1)
    t.eq("and finds one camera (the probe's is hidden)", inside.get(p + "foundCameras"), 1)
    t.eq("Camera.main is the game's", inside.get(p + "mainIsGame"), 1)
    t.ok("the game's camera callbacks see the probe's renders", (inside.get(p + "otherRenders") or 0) > 0, inside)
    t.eq("by the probe's camera's name", inside.get(p + "otherCamera"), "TaskProbe.Render")
    # the twins in no place are seen once too, before any sample: the scene's realtime reflection probe draws everything
    # for its first picture (so they are compared with themselves at 2 s)
    t.ok("an object only the probe renders becomes visible to the game at each sample",
         (inside.get(p + "becameVisible") or 0) > (away.get(p + "becameVisible") or 0) + 10, (inside, away))
    t.ok("and gets OnWillRenderObject at each render", (inside.get(p + "willRender") or 0) > (away.get(p + "willRender") or 0) + 10, (inside, away))
    t.ok("its twin in no place: no more than the reflection probe's picture", (away.get(p + "becameVisible") or 0) <= 1, away)
    # rows come in an order the select doesn't promise (the two arms, both named Arm, came Away first): the arms by z,
    # the particle systems by name
    arms, early_arms = ({r.get("z"): r for r in play.rows("arms", when)} for when in (at, 2.0))
    t.eq("two animated arms", sorted(arms), [-60.0, -45.0])
    if len(arms) == 2 and len(early_arms) == 2:
        t.ok("an Animator culled when unseen animates when only the probe renders it",
             (arms[-45.0].get("x") or 0) > (early_arms[-45.0].get("x") or 0) + 1e-4, (early_arms[-45.0], arms[-45.0]))
        t.eq("one nothing renders stays still (its x from 2 s to the end)", arms[-60.0].get("x"), early_arms[-60.0].get("x"))
    time = "prop:ParticleSystem.time"
    fx_in, fx_away = row(play, "fx", at, "Fx_In"), row(play, "fx", at, "Fx_Away")
    early_in, early_away = row(play, "fx", 2.0, "Fx_In"), row(play, "fx", 2.0, "Fx_Away")
    t.ok("a particle system paused when unseen runs on when only the probe renders it", (fx_in.get(time) or 0) > (early_in.get(time) or 0),
         (early_in.get(time), fx_in.get(time)))
    t.eq("one nothing renders stays paused (its time from 2 s to the end)", fx_away.get(time), early_away.get(time))
    t.eq("an objects select of cameras finds the game's camera only", [r.get("name") for r in play.rows("cameras", at)], ["Main Camera"])
    t.eq("no select finds the probe's objects", play.rows("hidden", at), [])


# ---------------------------------------------------------------- the game's callbacks in the way


def callbacks(t, play):
    """A callback that throws at the probe's camera, one that turns the sun and fog back on inside its render, one that
    destroys a renderer it is drawing, and the probe's camera object destroyed: one error, everything put back, the play
    goes on."""
    c = row(play, "callbacks", 13.5, "Callbacks")
    p = "prop:DrawnCallbacks."
    t.ok("the callback threw, changed things and destroyed the victim and the probe's camera",
         c.get(p + "thrown", 0) > 0 and c.get(p + "changed", 0) > 0 and c.get(p + "destroyed", 0) > 0 and c.get(p + "rigs") == 1, c)
    red = values(play, "red")
    t.ok("while the callback throws (3 and 3.5 s) the red cube has no value", all(v is None for at, v in red if 2.75 < at < 3.75), red[5:9])
    t.ok("before and after it, a value every sample", all(v is not None for at, v in red if not 2.75 < at < 3.75), red)
    base(t, play, "red", 2.0, [linear(0.8), linear(0.2), linear(0.1)], "before")
    t.ok("with the sun and fog switched on inside the render by the game: a value (the game's light is in it)", play.value("red", 6.0) is not None)
    t.eq("and the sample after that window reads as before it: nothing was left on", colour(play, "red", 7.0), colour(play, "red", 2.0))
    base(t, play, "red", 13.0, [linear(0.8), linear(0.2), linear(0.1)], "after the probe's camera was destroyed and made again")
    lit = [(at, (r or {}).get("glow_read")) for at, r in ((s["t"], (s.get("rows") or [None])[0]) for s in play.samples("glow_custom"))]
    t.ok("a glow render while the callback throws: no value", all(how == "unread" for at, how in lit if 2.75 < at < 3.75), lit[5:9])
    t.ok("and rendered again after it", all(how == "render" for at, how in lit if at >= 4.0), lit[8:10])
    victim = values(play, "victim")
    t.ok("the victim is drawn before it is destroyed (but while the callback throws)",
         all(v and v["drawn"] == 1.0 for at, v in victim if at < 8.75 and not 2.75 < at < 3.75), victim[:2])
    t.ok("the sample whose render destroyed it still has a value, and nothing is drawn after",
         all(v is not None and v["drawn"] == 0.0 for at, v in victim if at >= 9.5), victim[-2:])
    t.ok("the exception's stack is in probe.log", "InvalidOperationException" in play.probe_log, play.probe_log[-300:])
    no_leak(t, play, 13.5)


# ---------------------------------------------------------------- pipelines and players


def same_values(t, play, what, custom=True, filtered=False):
    """The main play's values at the same times."""
    main = play.earlier("main")
    for at in TIMES:
        for qid in ("red", "checker", "tint", "two_top"):
            want = colour(main, qid, at)
            got = colour(play, qid, at)
            for name, g, w in zip("rgb", got, want):
                t.near(f"{what}: {qid} base_{name} at {at} s as in the main play", g, w, COLOUR)
        same = [("red", "pixels"), ("spin", "motion"), ("spin", "pixels"), ("sparks", "pixels"), ("beam", "reach"), ("beam", "length"), ("only_cube", "drawn")]
        if not filtered:
            same.append(("never_cube", "drawn"))
        for qid, field in same:
            t.eq(f"{what}: {qid} {field} at {at} s as in the main play", (play.value(qid, at) or {}).get(field), (main.value(qid, at) or {}).get(field))
        if custom:
            want, got = row(main, "glow", at, "G_Custom").get("glow"), row(play, "glow", at, "G_Custom").get("glow")
            t.near(f"{what}: the custom glow at {at} s as in the main play", got, want, 1e-4 * (want or 1))
        for name in ("G_Skinned", "G_LitRendered", "G_WhiteRendered", "G_WhiteOutside"):
            want, got = row(main, "glow", at, name).get("glow"), row(play, "glow", at, name).get("glow")
            if custom or name != "G_Skinned":
                t.near(f"{what}: {name} glow at {at} s as in the main play", got, want, 1e-4 * (want or 1))
    no_leak(t, play, 5.5)


def forward(t, play):
    """The family's own Forward renderer: a full-screen tint feature the render leaves out, a RenderObjects pass that
    alone draws a layer (kept), on another URP asset: the same values."""
    t.ok("the play drew with the family's asset", "DRAWN pipeline DrawnUrp renderer 0" in play.log)
    same_values(t, play, "Forward with features", filtered=True)
    for at in TIMES:
        t.eq(f"a layer only a RenderObjects pass draws: drawn, as in the game, at {at} s", (play.value("only_cube", at) or {}).get("drawn"), 1.0)
        t.eq(f"a layer the renderer filters out and nothing draws: not drawn, as in the game, at {at} s",
             (play.value("never_cube", at) or {}).get("drawn"), 0.0)
        r = row(play, "glow", at, "G_Only")
        t.ok(f"glow as rendered on the RenderObjects layer: lit at {at} s", r.get("glow_read") == "render" and r.get("lit") == 1.0, r)
        r = row(play, "glow", at, "G_Never")
        t.ok(f"glow as rendered on the filtered layer: rendered, dark (the game draws nothing there) at {at} s",
             r.get("glow_read") == "render" and r.get("lit") == 0.0, r)


def forward_plus(t, play):
    t.ok("the play drew with Forward+", "DRAWN pipeline DrawnUrp renderer 1" in play.log)
    same_values(t, play, "Forward+")


def deferred(t, play):
    t.ok("the play drew with Deferred", "DRAWN pipeline DrawnUrp renderer 2" in play.log)
    same_values(t, play, "Deferred", custom=False)
    for at in TIMES:
        r = row(play, "glow", at, "G_Custom")
        t.ok(f"a shader with only a forward pass draws nothing under Deferred (in the game as in the probe) at {at} s",
             r.get("lit") == 0.0 and r.get("glow") == 0.0, r)


def hdr_off(t, play):
    t.ok("the play drew with HDR off and render scale 0.75", "DRAWN pipeline DrawnUrpPlain renderer 0" in play.log)
    same_values(t, play, "HDR off, render scale 0.75")


def d3d11(t, play):
    t.ok("the player ran on Direct3D 11", "Direct3D 11" in play.log, re.findall(r"Version: .*", play.log)[:1])
    same_values(t, play, "D3D11")


def nothing(t, play, what):
    """No drawn value and no glow as rendered; what is read from properties still reads."""
    for qid in ("red", "checker", "spin", "sparks", "beam", "only_cube"):
        got = values(play, qid)
        t.ok(f"{what}: {qid} has no value at any sample", got and all(v is None for _, v in got), got[:2])
    for at in TIMES:
        for name in ("G_Custom", "G_Skinned"):
            r = row(play, "glow", at, name)
            t.ok(f"{what}: {name} as rendered has no value at {at} s", r.get("glow_read") == "unread" and "glow" not in r, r)
        r = row(play, "glow", at, "G_LitRendered")
        t.ok(f"{what}: G_LitRendered isn't rendered at {at} s", r.get("glow_read") != "render", r)
        t.eq(f"{what}: a lamp read from its properties still reads at {at} s", row(play, "glow", at, "G_Lit").get("lit"), 1.0)


def builtin(t, play):
    t.ok("the play drew with no render pipeline asset", "DRAWN pipeline built-in" in play.log)
    nothing(t, play, "the built-in pipeline")


def renderer_2d(t, play):
    t.ok("the play drew with URP's 2D renderer", "DRAWN pipeline DrawnUrp renderer 3" in play.log)
    nothing(t, play, "the 2D renderer")


# ---------------------------------------------------------------- other scenes


def baked(t, play):
    """A lightmapped cube and a light-probe-lit sphere under a red baked light read their albedo."""
    log = t.project / "Logs" / "TaskProbe" / "probe_tests_setup.log"
    said = log.read_text(encoding="utf-8", errors="replace") if log.is_file() else ""
    t.ok("the bake gave the cube a lightmap and the scene its light probes (setup log)",
         re.search(r"drawn bake: BakedCube lightmapIndex [0-9]+, lightmaps [1-9][0-9]*, light probes [1-9]", said),
         re.findall(r"drawn bake: .*", said))
    for qid, what in (("baked_cube", "a lightmapped cube"), ("probe_sphere", "a sphere lit by light probes")):
        base(t, play, qid, 2.0, [linear(0.9)] * 3, what + " reads its albedo, not the red light")
        still(t, play, qid, what)
    no_leak(t, play, 5.5)


def coin(t, play):
    """A coin as the sample game makes it (a gold disc on its edge turning 90 degrees between samples, its place
    following it as it bobs) reads motion at every sample; a place at the coins' parent, where nothing moves, reads 0."""
    for qid, what in (("coin", "the place around the coin, as the task asks"), ("coin_all", "every field"),
                      ("coin_small", "a place 0.4 m around it"), ("coin_fixed", "a fixed place where it hovers")):
        moving(t, play, qid, what)
    v = play.value("coin_all", 5.0) or {}
    t.eq("the coin's place holds the disc and the ground", v.get("primitives"), 2.0)
    t.eq("0.4 m around it, the disc alone", (play.value("coin_small", 5.0) or {}).get("primitives"), 1.0)
    base(t, play, "coin_small", 5.0, [1.0 * 0.1, linear(0.78) * 0.1, linear(0.25) * 0.1],
         "the gold disc alone: its albedo times 1 - 0.9 metallic, the share URP Lit gives as diffuse")
    named = play.rows("named", 5.0)
    t.eq("a name select Coin* matches the coins' parent first", [r["name"] for r in named][:1], ["CoinSpawner"])
    still(t, play, "coin_old", "the place at the first Coin* match (the parent at the origin)")
    old = play.value("coin_old", 5.0) or {}
    t.ok("where only the still ground is drawn", old.get("drawn") == 1.0 and old.get("primitives") == 1.0, old)


def crowd(t, play):
    """3000 cubes more in the scene, and 1100 in one place: the first 1024 in hierarchy order are rendered."""
    caps = values(play, "crowd_cap")
    t.ok("a place with 1100 renderers renders 1024 of them", caps and all(v and v["primitives"] == 1024.0 for _, v in caps), caps[:2])
    cost = costs(play)
    t.ok("cost in a scene of 4000 renderers: drawn near a point, at most 40 ms a sample", cost.get("red", (99,))[0] < 40, cost.get("red"))
    t.ok("drawn along a line, at most 24 ms", cost.get("beam", (99,))[0] < 24, cost.get("beam"))


PLAYS = {  # in the order they run: the main play's values are compared with later plays'
    "plain": {"check": plain},
    "main": {"check": main},
    "callbacks": {"check": callbacks, "args": ["-drawnCallback"], "errors": [THREW]},
    "forward": {"check": forward, "args": ["-drawnPipeline", "forward"]},
    "forward_plus": {"check": forward_plus, "args": ["-drawnPipeline", "forwardplus"]},
    "deferred": {"check": deferred, "args": ["-drawnPipeline", "deferred"]},
    "hdr_off": {"check": hdr_off, "args": ["-drawnPipeline", "plain"]},
    "d3d11": {"check": d3d11, "args": ["-force-d3d11"]},
    "builtin": {"check": builtin, "args": ["-drawnPipeline", "builtin"],
                "errors": [r"^rendering: the render pipeline isn't URP: drawn and glow as rendered have no value$"]},
    "renderer_2d": {"check": renderer_2d, "args": ["-drawnPipeline", "2d"],
                    "errors": [r"^rendering: the player's camera draws with a URP renderer that isn't the Universal Renderer: drawn and glow as rendered have no value$"]},
    "baked": {"check": baked},
    "coin": {"check": coin},
    "crowd": {"check": crowd, "args": ["-drawnCrowd"]},
}
