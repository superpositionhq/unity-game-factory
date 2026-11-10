"""The light family: `light` (each term against URP's own light maths written out here, and against the frame: the
camera looks at a white diffuse card at the point), `grading` (the volume stack's constants through the checker's own
colour.py against the frame), `audio` (every kind of source against the mix the probe's tap measures) and the tap
itself (it silences every probe play, and nothing outside one)."""

import math
import re
import subprocess
import sys

from task_check import colour, unity

MADE = "Assets/ProbeTests/light/Made/"
SETUP = ["ProbeTests.Lighting.LightScenes.Build"]
SCENES = [MADE + name + ".unity" for name in
          ("LightLab", "BakeLab", "SkyLab", "GradeLab", "AudioLab", "AudioLab2", "AudioRolloff", "Stray")]

FLOAT = 1e-5  # a float of the engine widened to a double, through a few operations
LUM = colour.LUMA  # URP's luminance weights (core Color.hlsl): the light measure's
REC709 = (0.2126, 0.7152, 0.0722)  # the screen measure's
SUN_UP = math.sin(math.radians(50))  # the cosine between an upward card and LightLab's sun (50 degrees up)
LAB_SUN, SKY_SUN = 0.8, 0.6  # the intensities of LightLab's and SkyLab's suns: no card above 1 in a channel


# -- colour and URP's light maths, written out here ---------------------------------------------------------------------


def linear(v):
    """A colour channel from the colour picker in linear (Color.linear: the sRGB curve)."""
    return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4


def encode(v):
    """A linear channel as an sRGB-encoded one, 0-1."""
    return 12.92 * v if v <= 0.0031308 else 1.055 * v ** (1 / 2.4) - 0.055


def decode8(b):
    """An 8-bit sRGB value of a screenshot in linear."""
    return linear(b / 255)


def lum(rgb, weights=LUM):
    return sum(w * c for w, c in zip(weights, rgb))


def frame_tol(v):
    """How far the frame's linear luminance can sit from `v` with nothing wrong: URP draws into an HDR target of 11- and
    10-bit floats (red and green rounded to 2^-7 of their value, blue to 2^-6), the screenshot holds 8-bit sRGB (half
    a step), and the screen measure weighs the channels by Rec. 709's four digits (under 4e-4 of the value). The frame
    clips each channel at 1: the scenes keep every card below 1 in each channel."""
    s = encode(v)
    half = (linear(min(1.0, s + 0.5 / 255)) - linear(max(0.0, s - 0.5 / 255))) / 2
    return v * ((LUM[0] + LUM[1]) * 2 ** -7 + LUM[2] * 2 ** -6 + 4e-4) + half


def punctual(light, point, reach):
    """URP's distance attenuation of a point or spot light (RealtimeLights.hlsl DistanceAttenuation with the constants
    UniversalRenderPipelineCore.GetPunctualLightDistanceAttenuation prepares): saturate(1 - (d^2/r^2)^2)^2 / d^2."""
    d2 = max(sum((a - b) ** 2 for a, b in zip(light, point)), 6.103515625e-5)
    f = d2 / reach ** 2
    return max(0.0, min(1.0, 1 - f * f)) ** 2 / d2


def cone(light, forward, point, outer, inner):
    """URP's spot cone (AngleAttenuation with GetSpotAngleAttenuation's constants): saturate((cos a - cos outer/2) /
    (cos inner/2 - cos outer/2))^2."""
    to = [p - q for p, q in zip(point, light)]
    s = sum(f * c for f, c in zip(forward, to)) / math.sqrt(sum(c * c for c in to))
    co, ci = math.cos(math.radians(outer / 2)), math.cos(math.radians(inner / 2))
    inv = 1 / max(0.001, ci - co)
    return max(0.0, min(1.0, s * inv - co * inv)) ** 2


def facing_up(light, point):
    """The cosine between an upward card at `point` and the way to `light`."""
    to = [a - b for a, b in zip(light, point)]
    return to[1] / math.sqrt(sum(c * c for c in to))


def engine(play):
    """{Light name: its VisibleLight.finalColor} as the engine logged it (LightCull)."""
    return {m.group(1): [float(m.group(i)) for i in (2, 3, 4)]
            for m in re.finditer(r"LIGHT visible (\S+) (\S+) (\S+) (\S+)", play.log)}


def bakes(play):
    """{Light name: (isBaked, lightmapBakeType, mixedLightingMode)} of Light.bakingOutput as logged (LightCull)."""
    return {m.group(1): (m.group(2), m.group(3), m.group(4))
            for m in re.finditer(r"LIGHT bake (\S+) (\S+) (\S+) (\S+)", play.log)}


def at(play, qid, when, field):
    return (play.value(qid, when) or {}).get(field)


def frame_is(t, play, when, want, what):
    """The frame's luminance at the card in view at `when` (the screen measure over the middle of the frame)."""
    t.near(f"the frame at {when:g} s: {what}", at(play, "frame", when, "luminance"), want, frame_tol(want))


# -- light ---------------------------------------------------------------------------------------------------------------


POINT_A = 2 * punctual((0, 3, 0), (0, 1, 0), 10)
SPOT_B1 = 3 * punctual((20, 3, 0), (20, 1, 0), 10)
SPOT_B2 = 3 * punctual((20, 3, 0), (20.8, 1, 0), 10) * cone((20, 3, 0), (0, -1, 0), (20.8, 1, 0), 60, 30)
SWITCHED_FALLOFF = punctual((3, 3, 3), (0, 1, 0), 8)
FAR = 2 * punctual((0, 3, -3), (0, 1, 3), 12)  # a lamp 3 m from the split wall, the point 3 m past it
NEAR_C = 2 * punctual((40, 3, -3), (40, 1, -1), 12)
GADGET = punctual((0, 3, 0), (0, 0.5, 0), 3)  # a lamp of intensity 1 and range 3, 2.5 m above its point
FLAT = lum([linear(c) for c in (0.2, 0.3, 0.4)])  # LightLab's flat ambient, as the ambient probe holds it
GADGETS = {"lantern": False, "crate": True, "trigger": False, "ignore": False, "flat2d": False, "hero": False, "slab": True}


def lamps(t, play):
    """Each term of `light` against URP's maths, and against the frame: the camera visits a white diffuse card at each
    point, one a second (LightTour), so the frame's luminance at whole seconds is each Light's contribution times the
    cosine of its angle to the card, plus the ambient. The ambient is the ambient probe, walls or not (URP doesn't
    shade it at run time). A wall stops only a Light whose shadows URP draws: the project's URP asset has none for
    point and spot lights (switched on at 7.5 s for the measure), and at half strength a shadow lets half through."""
    lights = engine(play)
    t.ok("the engine logged the colours it lights with", {"Sun", "PointA", "SwitchedA", "SpotB"} <= set(lights), sorted(lights))
    sun = lum(lights.get("Sun", [0, 0, 0]))
    switched = lum(lights.get("SwitchedA", [0, 0, 0])) * SWITCHED_FALLOFF
    t.near("PointA lights with its colour x intensity, linear (VisibleLight.finalColor)", lum(lights.get("PointA", [0, 0, 0])), 2.0, FLOAT)

    # the terms (before LightEvents changes anything)
    for qid, want in (("A", POINT_A), ("B1", SPOT_B1), ("B2", SPOT_B2), ("B3", 0.0), ("C1", FAR), ("C2", NEAR_C),
                      ("D", FAR), ("E", FAR)):
        t.near(f"{qid}: local at 1 s, URP's attenuation written out", at(play, qid, 1.0, "local"), want, FLOAT)
        t.eq(f"{qid}: no sun in a closed room", at(play, qid, 1.0, "directional"), 0.0)
    for qid in ("A", "C1", "F2"):
        t.near(f"{qid}: the ambient is the flat colour's luminance (linear), walls or not", at(play, qid, 1.0, "sky"), FLAT, FLOAT)
    t.near("A at 4 s: the switched lamp adds the engine's own colour (its 2700 K applied) x URP's falloff",
           at(play, "A", 4.0, "local"), POINT_A + switched, FLOAT)
    t.eq("A: lights counts the lamps that reached it and the ambient", [at(play, "A", 2.0, "lights"), at(play, "A", 4.0, "lights")], [2.0, 3.0])
    t.eq("B3: outside the cone: only the ambient", at(play, "B3", 1.0, "lights"), 1.0)
    for qid, want in (("F1", sun), ("F3", sun)):
        t.near(f"{qid}: the sun in the open, its colour the engine's (4000 K)", at(play, qid, 1.0, "directional"), want, FLOAT)
    t.eq("F2: under the shelter the sun's shadow (main light, shadows on) stops it", at(play, "F2", 1.0, "directional"), 0.0)
    t.near("F2: ... at shadow strength 0.5 half of it through", at(play, "F2", 8.0, "directional"), sun / 2, FLOAT)
    t.eq("F2: ... back at strength 1", at(play, "F2", 10.0, "directional"), 0.0)
    value = play.value("A", 1.0) or {}
    t.near("illuminance is local + directional + sky", value.get("illuminance"),
           sum(value.get(k, 0) for k in ("local", "directional", "sky")), 1e-12)
    t.eq("exposure 1: the camera renders no post-processing", value.get("exposure"), 1.0)
    t.eq("brightness = illuminance x exposure", value.get("brightness"), value.get("illuminance"))
    t.eq("point", value.get("point"), [0.0, 1.0, 0.0])
    obj = play.value("obj", 1.0) or {}
    t.eq("a point at an object, offset: the same place and light", [obj.get("point"), obj.get("illuminance")],
         [[0.0, 1.0, 0.0], value.get("illuminance")])
    t.eq("a point at an object that doesn't exist: no value, every sample", {s.get("value") is None for s in play.samples("none")}, {True})
    t.eq("a light query without a point: no value", {s.get("value") is None for s in play.samples("nopoint")}, {True})

    # shadows switched on for point and spot lights at 7.5 s (in the measure: the build has no shader variants for them,
    # so the frame can't show them; the sun's shadow shows the rule in the frame), the sun's at strength 0.5 from 7.5 to
    # 9.5 s: the sun's own checks read 10 s
    t.near("D: a lamp with shadows behind a wall lights through it while URP draws none", at(play, "D", 7.0, "local"), FAR, FLOAT)
    t.eq("D: ... and once URP draws them the wall stops it", at(play, "D", 8.0, "local"), 0.0)
    t.eq("D: ... only the ambient reaches it (10 s: the roof stops the sun)", [at(play, "D", 10.0, "local"), at(play, "D", 10.0, "lights")], [0.0, 1.0])
    t.near("E: shadows of strength 0.5: half its light through the wall", at(play, "E", 8.0, "local"), FAR / 2, FLOAT)
    t.near("C1: a lamp without shadows lights through the wall after it too", at(play, "C1", 8.0, "local"), FAR, FLOAT)
    for qid, stopped in GADGETS.items():
        t.near(f"{qid}: lit before its shadows count", at(play, qid, 7.0, "local"), GADGET, FLOAT)
        t.near(f"{qid}: " + ("stopped" if stopped else "not stopped") + " once they count", at(play, qid, 8.0, "local"),
               0.0 if stopped else GADGET, FLOAT)
        t.near(f"{qid}: the sun " + ("stopped by it" if stopped else "not stopped"), at(play, qid, 10.0, "directional"),
               0.0 if stopped else sun, FLOAT)

    # the frame: each card's luminance is what the light measure says reaches it
    def sky(when):
        return at(play, "A", when, "sky")
    stations = [
        (1, POINT_A, "PointA straight above the card"),
        (2, SPOT_B1, "the spot straight above"),
        (3, SPOT_B2 * facing_up((20, 3, 0), (20.8, 1, 0)), "the spot 0.8 m off its axis"),
        (4, POINT_A + switched * facing_up((3, 3, 3), (0, 1, 0)), "the switched lamp added"),
        (5, FAR * facing_up((40, 3, -3), (40, 1, 3)), "a lamp without shadows, through a wall"),
        (6, NEAR_C * facing_up((40, 3, -3), (40, 1, -1)), "the same lamp on its own side"),
        (7, FAR * facing_up((120, 3, -3), (120, 1, 3)), "a lamp with shadows URP doesn't draw, through a wall"),
        (8, sun / 2 * SUN_UP, "under the shelter, the sun's shadow at strength 0.5: half"),
        (9, sun, "the sun, the card facing it"),
        (10, 0.0, "under the shelter, the sun's shadow at full strength"),
        (11, sun * SUN_UP, "flat ambient"),
        (12, sun * SUN_UP, "gradient ambient"),
        (13, sun * SUN_UP, "skybox ambient, the environment not made yet"),
        (14, sun * SUN_UP, "skybox ambient after DynamicGI.UpdateEnvironment"),
        (15, sun * SUN_UP, "flat ambient at intensity 2"),
        (16, 0.0, "additional lights off in the URP asset: the lamps light nothing"),
        (17, sun * SUN_UP, "main light off: the sun lights as an additional light, without shadows"),
    ]
    for when, lamps_part, what in stations:
        frame_is(t, play, when, lamps_part + sky(when), what)

    # the ambient through its modes (the probe reads the ambient probe; the frame above shows the same)
    t.ok("gradient ambient: the probe's upward value, not the flat colour", abs(sky(12.0) - FLAT) > 0.005, sky(12.0))
    t.near("flat ambient at intensity 2 reads as at 1 (the ambient probe doesn't change)", sky(15.0), FLAT, FLOAT)
    t.eq("additional lights off: no lamp counts", [at(play, "A", 16.0, "local"), at(play, "A", 16.0, "lights")], [0.0, 1.0])
    t.near("additional lights off: the main light still lights", at(play, "F1", 16.0, "directional"), sun, FLOAT)
    t.near("main light off: the sun counts unshadowed under the shelter", at(play, "F2", 17.0, "directional"), sun, FLOAT)
    t.near("main light off, additional lights on: the lamps count again", at(play, "A", 17.0, "local"), POINT_A + switched, FLOAT)

    # grading's neutral constants for a camera without post-processing, and its key lights
    grade = play.value("grade", 1.0) or {}
    t.eq("grading: no post-processing on the camera", [grade.get("post_processing"), grade.get("source")], [0.0, "camera"])
    t.eq("grading: neutral constants", [grade.get(k) for k in ("contrast", "saturation", "color_filter", "lift", "gamma", "gain",
                                                              "post_exposure", "hue_shift", "tonemapping")],
         [1.0, 1.0, [1.0, 1.0, 1.0], [0.0, 0.0, 0.0], [1.0, 1.0, 1.0], [1.0, 1.0, 1.0], 0.0, 0.0, "None"])
    found = grade.get("sun") or {}
    t.eq("grading's sun: the strongest directional light", [found.get("name"), found.get("use_temperature"), found.get("temperature")],
         ["Sun", 1.0, 4000.0])
    t.ok("grading's sun lit_color: its colour x the engine's 4000 K colour",
         all(abs(a * LAB_SUN - b) < FLOAT for a, b in zip(found.get("lit_color") or [9, 9, 9], lights.get("Sun", [0, 0, 0]))), found.get("lit_color"))
    t.eq("grading's sky: the flat ambient", [(grade.get("sky") or {}).get("mode"), (grade.get("sky") or {}).get("intensity")], ["Flat", 1.0])
    t.ok("grading's sky colour: the flat colour, linear",
         all(abs(a - linear(b)) < FLOAT for a, b in zip((grade.get("sky") or {}).get("color") or [9, 9, 9], (0.2, 0.3, 0.4))))

    # a play that doesn't measure sound (it runs as fast as it renders) is silenced as well
    ears = play.row("ears", 17.0, "LabEars") or {}
    t.eq("the probe's tap is on the scene's listener", ears.get("prop:LightEar.tapped"), 1.0)
    t.ok("the hum reaches the tap", (ears.get("prop:LightEar.peak") or 0) > 0.03, ears.get("prop:LightEar.peak"))
    t.eq("nothing leaves the tap", ears.get("prop:LightEarAfter.peak"), 0.0)
    t.ok("... though buffers pass", (ears.get("prop:LightEarAfter.buffers") or 0) > 0, ears.get("prop:LightEarAfter.buffers"))


def lamps_builtin(t, play):
    """Without URP (the pipeline switched off before the first frame): light is still URP's falloff with the light's
    colour as the engine computes it, grading neutral and without post: values, and each query says so once. URP
    turns the project's linear light intensity on (GraphicsSettings.lightsUseLinearIntensity); without it a light's
    intensity counts in gamma: (2 x white).linear, 2^2.2."""
    t.ok("the pipeline was off", "LIGHT builtin: pipeline none" in play.log)
    t.near("A: URP's falloff, the lamp's colour the engine's without URP (intensity in gamma)", at(play, "A", 1.0, "local"),
           POINT_A / 2 * gamma_to_linear(2.0), FLOAT)
    grade = play.value("grade", 1.0) or {}
    t.eq("grading: no pipeline, no stack, neutral", [grade.get(k) for k in ("pipeline", "source", "post_processing", "contrast", "post:Bloom.intensity")],
         ["builtin", "none", 0.0, 1.0, None])


def baked(t, play):
    """What URP draws at run time for a baked Light: nothing (its light is in the lightmaps and the light probes), and
    the measure reads the probes there as a moving card is lit; a Light set to Baked but never baked lights in real
    time; a Mixed one lights in real time, its bounce baked. Ambient black, so only the lamps light."""
    found = bakes(play)
    t.eq("BakedLamp: its bake stored its light", found.get("BakedLamp", ("?",) * 3)[:2], ("True", "Baked"))
    t.eq("MixedLamp: baked as Mixed, indirect only", found.get("MixedLamp"), ("True", "Mixed", "IndirectOnly"))
    t.eq("LateLamp: set to Baked after the bake: never baked", found.get("LateLamp", ("?",) * 3)[0], "False")
    visible = set(engine(play))
    t.eq("the engine draws MixedLamp and LateLamp at run time, not BakedLamp",
         sorted(visible & {"BakedLamp", "MixedLamp", "LateLamp"}), ["LateLamp", "MixedLamp"])
    lamp = 2 * punctual((0, 3, 0), (0, 1, 0), 6)
    t.eq("baked: no real-time light", [at(play, "baked", 1.0, "local"), at(play, "baked", 1.0, "directional")], [0.0, 0.0])
    t.ok("baked: the light probes hold its light", (at(play, "baked", 1.0, "sky") or 0) > 0.05, at(play, "baked", 1.0, "sky"))
    for qid in ("mixed", "late"):
        t.near(f"{qid}: lights in real time", at(play, qid, 1.0, "local"), lamp, FLOAT)
    t.ok("mixed: its baked bounce reaches the card", (at(play, "mixed", 1.0, "sky") or 0) > 0, at(play, "mixed", 1.0, "sky"))
    t.ok("late: nothing of it in the probes", (at(play, "late", 1.0, "sky") or 0) < 0.01, at(play, "late", 1.0, "sky"))
    for when, qid in ((1, "baked"), (2, "mixed"), (3, "late")):
        frame_is(t, play, when, at(play, qid, when, "illuminance") or 0, f"the moving card under the {qid} lamp")
    for when, qid in ((4, "baked"), (5, "mixed"), (6, "late")):
        t.ok(f"the frame at {when} s: the static floor under the {qid} lamp is lit", (at(play, "frame", when, "luminance") or 0) > 0.03,
             at(play, "frame", when, "luminance"))


def sky(t, play):
    """A scene saved with skybox ambient and never baked: the measure reads the ambient probe as it is (the frame shows
    the same), before and after the environment is made at 2 s. Its camera renders post-processing with no volume in
    the scene: an untouched stack is exactly grey 0.18, cast 0 through colour.py."""
    for when in (1.0, 3.0):
        value = play.value("card", when) or {}
        t.near(f"the sun at {when:g} s: a white sun of intensity {SKY_SUN:g}", value.get("directional"), SKY_SUN * sum(LUM), FLOAT)
        frame_is(t, play, when, SKY_SUN * sum(LUM) * SUN_UP + (value.get("sky") or 0), "the card: the sun and the ambient probe")
    grade = play.value("grade", 1.0) or {}
    t.eq("grading: the camera's stack, post-processing on", [grade.get("source"), grade.get("post_processing")], ["camera", 1.0])
    found = colour.colour(grade)
    t.eq("an untouched stack: grey exactly 0.18, cast 0", [found["grey"], found["cast"]], [0.18, 0.0])
    t.eq("post:Tonemapping.mode of the project's default profile: None", grade.get("post:Tonemapping.mode"), 0.0)
    t.eq("an object whose only script is the probe's tap (a listener of its own): its row's class isn't the probe's",
         [r.get("class") for r in play.rows("ears", 1.0)], ["AudioListener"])


# -- grading -------------------------------------------------------------------------------------------------------------


def gamma_to_linear(v):
    """Mathf.GammaToLinearSpace: the sRGB curve below 1, v ** 2.2 from 1."""
    return linear(v) if v < 1.0 else v ** 2.2


def lift_gamma_gain(lift, gamma, gain):
    """ColorUtils.PrepareLiftGammaGain (as tools/task_check/tests/test_colour.py writes it out)."""
    lt = [gamma_to_linear(v) * 0.15 for v in lift[:3]]
    gm = [gamma_to_linear(v) * 0.8 for v in gamma[:3]]
    gn = [gamma_to_linear(v) * 0.8 for v in gain[:3]]
    return {"lift": [c - lum(lt) + lift[3] for c in lt],
            "gamma": [1.0 / max(c - lum(gm) + gamma[3] + 1.0, 1e-3) for c in gm],
            "gain": [c - lum(gn) + gain[3] + 1.0 for c in gn]}


def weight(when):
    """The local volume's weight on the camera at play time `when` (VolumeManager: 1 - d^2 / blend^2): the player
    walks +z at 2 m/s from z -30 at 6 s; the box is z -5..5, blend distance 10."""
    z = -30 + 2 * max(0.0, when - 6)
    d = max(0.0, -5 - z)
    return max(0.0, 1 - d * d / 100)


GRADE_ERRORS = [r"^grading grade: post:Vignette\.color is a Color: name a part", r"^grading grade: post:Vignette\.center\.z: Vignette\.center has no channel z$",
                r"^grading grade: post:Bloom\.intensity\.x: Bloom\.intensity has no channel x$",
                r"^grading grade: post:ColorCurves\.master is a TextureCurve: it has no single number$",
                r"^grading grade: no volume component Nope$", r"^grading grade: Bloom has no parameter nope$",
                r"^grading grade: no volume component bloom$", r"^grading grade: Bloom has no parameter Intensity$"]


def white_key(value):
    """The grading value with a white key light: the grey card is unlit, so the frame carries no key light's hue."""
    return {**value, "sun": {"lit_color": [1.0, 1.0, 1.0]}}


def pixel_is(t, play, shot, value, what):
    """A screenshot's centre pixel against colour.grade of `value`, channel by channel: within one 8-bit step (half a
    step of rounding, and the HDR target's rounding of the card's 0.18, a tenth of a step)."""
    image = play.image(shot)
    got = image.at(image.width // 2, image.height // 2)
    want = [255 * encode(c) for c in colour.grade(white_key(value))]
    t.ok(f"{shot}'s centre pixel is colour.py's grade: {what}", all(abs(g - w) <= 1.0 for g, w in zip(got, want)),
         (got, [round(w, 2) for w in want]))


def grade_common(t, play):
    v = play.value("grade", 3.0) or {}
    for a, b in zip(v.get("color_balance") or [], colour.lms_coeffs(30, -20)):
        t.near("color_balance: ColorBalanceToLMSCoeffs(30, -20)", a, b, 1e-6)
    t.eq("contrast and saturation as multipliers", [v.get("contrast"), round(v.get("saturation", 0), 6)], [1.25, 0.7])
    t.ok("color_filter: (1, 0.9, 0.8) in linear",
         all(abs(a - linear(b)) < FLOAT for a, b in zip(v.get("color_filter") or [9, 9, 9], (1, 0.9, 0.8))), v.get("color_filter"))
    want = lift_gamma_gain((1, 1, 0.9, 0.02), (0.95, 1, 1.05, 0), (1.05, 1, 0.95, 0.1))
    for key in ("lift", "gamma", "gain"):
        t.ok(f"{key}: PrepareLiftGammaGain of the trackballs", all(abs(a - b) < 1e-6 for a, b in zip(v.get(key) or [9, 9, 9], want[key])), v.get(key))
    t.eq("the rest of the value", [v.get(k) for k in ("pipeline", "post_processing", "grading_mode", "tonemapping", "hue_shift")],
         ["urp", 1.0, "ldr", "None", 0.0])
    sun = v.get("sun") or {}
    t.eq("sun: of two directional lights of one intensity the first in hierarchy order", [sun.get("name"), sun.get("intensity")], ["SunTwin", 1.5])
    t.eq("sky: flat ambient", [(v.get("sky") or {}).get("mode"), (v.get("sky") or {}).get("intensity")], ["Flat", 1.0])
    t.ok("sky colour: 0.1 grey in linear", all(abs(c - linear(0.1)) < FLOAT for c in (v.get("sky") or {}).get("color") or [9]))
    fog = v.get("fog") or {}
    t.eq("fog: enabled, its mode", [fog.get("enabled"), fog.get("mode")], [1.0, "ExponentialSquared"])
    t.near("fog density", fog.get("density"), 0.001, 1e-9)
    t.ok("fog colour in linear", all(abs(a - linear(b)) < FLOAT for a, b in zip(fog.get("color") or [9, 9, 9], (0.5, 0.55, 0.6))))
    posts = {"post:Vignette.center.x": 0.5, "post:Vignette.center.r": 0.5, "post:Tonemapping.mode": 0.0,
             "post:Bloom.highQualityFiltering": 0.0, "post:Bloom.maxIterations": 6.0, "post:Bloom.dirtTexture": 0.0,
             "post:MotionBlur.intensity": 0.0, "post:PaniniProjection.distance": 0.3, "post:ChromaticAberration.intensity": 0.0}
    for field, want in posts.items():
        t.near(f"{field} (a vector's channel either spelling; an enum, a bool, an int, an unset texture; a default; a volume of weight 0.5; a disabled volume and one off the camera's mask)",
               v.get(field), want, FLOAT)
    t.near("post:LiftGammaGain.lift.w (a Vector4's w)", v.get("post:LiftGammaGain.lift.w"), 0.02, FLOAT)
    for field in ("post:Vignette.color", "post:Vignette.center.z", "post:Bloom.intensity.x", "post:ColorCurves.master",
                  "post:Nope.x", "post:Bloom.nope", "post:bloom.intensity", "post:Bloom.Intensity"):
        t.eq(f"{field}: no value", field in v and v[field] is None, True)
    frame = at(play, "frame", 3.0, "luminance")
    t.near("the frame's luminance at 3 s: colour.py's grey (white key light)", frame, colour.colour(white_key(v))["grey"],
           frame_tol(colour.colour(white_key(v))["grey"]))
    pixel_is(t, play, "shot_00.png", v, "the global grade")


def grade(t, play):
    """The global grade's constants (URP's own: ColorBalanceToLMSCoeffs, PrepareLiftGammaGain) and every kind of post:
    value; through the checker's colour.py they give the frame. The local volume blends in as the camera walks into it
    (VolumeManager's weight), and inside it the post exposure moves the frame as colour.py says."""
    grade_common(t, play)
    for when in (3.0, 14.0, 16.0, 17.0, 18.0, 19.5):
        w = weight(when)
        v = play.value("grade", when) or {}
        t.near(f"post exposure at {when:g} s: the local volume's weight {w:.4f}", v.get("post:ColorAdjustments.postExposure"), w, FLOAT)
        t.near(f"bloom at {when:g} s: 0.5 + 1.5 x weight", v.get("post:Bloom.intensity"), 0.5 + 1.5 * w, FLOAT)
        t.near(f"vignette at {when:g} s: 0.4 x weight", v.get("post:Vignette.intensity"), 0.4 * w, FLOAT)
        t.near(f"vignette colour .r and .x at {when:g} s: 0.2 x weight", v.get("post:Vignette.color.r"), 0.2 * w, FLOAT)
        t.eq(f"vignette colour .x is .r at {when:g} s", v.get("post:Vignette.color.x"), v.get("post:Vignette.color.r"))
        t.near(f"the light measure's exposure at {when:g} s: 2^post exposure", at(play, "exposure", when, "exposure"), 2 ** w, FLOAT)
        t.eq(f"the stack at {when:g} s: blended for the camera", v.get("source"), "camera")
    inside = play.value("grade", 19.5) or {}
    pixel_is(t, play, "shot_03.png", inside, "inside the local volume, post exposure 1")


def grade_script(t, play):
    """The camera's volumes updated by script only: URP renders with the stack it made at the first frame (outside the
    local volume), and so does the measure: the post exposure stays 0 inside the local volume, as the frame does."""
    grade_common(t, play)
    for when in (0.5, 16.0, 19.5):
        v = play.value("grade", when) or {}
        t.eq(f"the stack at {when:g} s: the camera's own", v.get("source"), "camera_stack")
        t.eq(f"post exposure at {when:g} s: never updated", v.get("post:ColorAdjustments.postExposure"), 0.0)
    inside = play.value("grade", 19.5) or {}
    pixel_is(t, play, "shot_03.png", inside, "inside the local volume, still the global grade")


def grade_first(t, play):
    """A play's first sample comes before URP has drawn a frame, and so before its volume framework is up: grading has
    no value then and the light's exposure none, never the neutral grade no frame shows; from the next sample on, the
    grade the frame gets (the global grade here with a post exposure of 1, -gradeexposed)."""
    first = play.samples("grade")[0]
    v = first.get("value")
    t.ok(f"the first sample ({first['t']:.3f} s): no grade, or the frame's own", v is None or (v.get("source") == "camera"
         and v.get("post:ColorAdjustments.postExposure") == 1.0 and v.get("contrast") == 1.25), v and {k: v.get(k) for k in ("source", "contrast")})
    light = play.samples("exposure")[0].get("value") or {}
    t.ok("the first sample: no exposure, or the frame's own (2)", light.get("exposure") in (None, 2.0), light.get("exposure"))
    t.ok("... and brightness with it", (light.get("brightness") is None) == (light.get("exposure") is None), light)
    for when in (0.5, 1.0):
        v = play.value("grade", when) or {}
        t.eq(f"grading at {when:g} s: the camera's stack, post exposure 1", [v.get("source"), v.get("post:ColorAdjustments.postExposure")],
             ["camera", 1.0])
        t.eq(f"the light's exposure at {when:g} s: 2^1", at(play, "exposure", when, "exposure"), 2.0)


# -- audio -----------------------------------------------------------------------------------------------------------------


LEVEL = 0.25  # the mix's RMS for a 0.5-amplitude sine at volume 1: 0.5 / sqrt(2), panned -3 dB into each channel
FIRST = {"Loop3D": 0.8 / 5, "Music2D": 0.5, "Muted": 0.0, "Mixed": 1.0, "Custom": 0.4, "Stream": 0.3, "Menu": 0.2, "Faint": 0.0009}
STEADY = sum(FIRST.values()) + 0.75  # with Late, once Pausable is paused


def audio_value(play, qid, when):
    return play.value(qid, when)


def audio(t, play):
    """Every source that plays, at its volume at the listener, through LightAudioDirector's events: a clip that ends,
    a source started and one paused, PlayOneShot on a source without a clip and on one with its own, PlayClipAtPoint,
    AudioListener.pause (a source that ignores it plays on), timeScale 0, two listeners, the second alone, none, and a
    scene load. The tap: on every enabled listener, hidden from FindObjectsByType, and nothing leaves it."""
    def v(qid, when, field):
        return (play.value(qid, when) or {}).get(field)

    base = sum(FIRST.values()) + 0.1
    t.eq("at 1 s: 9 sources playing, 7 of them audible (one muted, one at 0.0009, under 0.001)",
         [v("all", 1.0, "count"), v("all", 1.0, "audible")], [9.0, 7.0])
    t.near("at 1 s: their volumes at the listener summed", v("all", 1.0, "volume"), base, FLOAT)
    t.eq("at 1 s: the loudest and the listener", [v("all", 1.0, "max_volume"), v("all", 1.0, "loudest"), v("all", 1.0, "listener")],
         [1.0, "Mixed550", "PlayerCamera"])
    t.eq("a clip that ends: playing at 2.5 s, over at 3 s", [v("all", 2.5, "count"), v("all", 3.0, "count")], [10.0, 9.0])
    t.near("a source started at 4 s (linear, half 3D): 0.75", v("late", 4.5, "volume"), 0.75, FLOAT)
    t.near("a source paused at 5 s leaves the sum", v("all", 5.5, "volume"), STEADY, FLOAT)
    t.eq("PlayOneShot on a source without a clip: counted, no clip name", [v("shooter", 6.5, "count"), v("shooter", 6.5, "loudest")], [1.0, ""])
    t.near("... at its source's volume", v("shooter", 6.5, "volume"), 0.9, FLOAT)
    t.eq("... over by 7 s", [v("shooter", 7.0, "count"), v("shooter", 7.0, "loudest")], [0.0, None])
    t.eq("PlayOneShot reads as its source's own clip", [v("shooter_clip", 7.5, "loudest"), v("main", 7.5, "count"), v("main", 8.0, "count")],
         ["Main605", 1.0, 0.0])
    t.eq("a sound select never sees the one-shot's clip", {v("shot", w, "count") for w in (6.5, 7.5)}, {0.0})
    t.near("PlayClipAtPoint at 3 m: 1/3 (Unity's one-shot source: 3D, logarithmic)", v("point", 8.5, "volume"), 1 / 3, FLOAT)
    t.eq("PlayClipAtPoint: its clip's name; gone by 9 s", [v("point", 8.5, "loudest"), v("point", 9.0, "count")], ["Point990", 0.0])
    t.eq("AudioListener.pause: only the source that ignores it plays", [v("all", 10.0, "count"), v("all", 10.0, "loudest"), v("menu", 10.0, "count")],
         [1.0, "Menu495", 1.0])
    t.near("... and the mix is that source alone", v("all", 10.0, "level"), LEVEL * 0.2, LEVEL * 0.2 * 0.01)
    t.eq("every audio query of a sample reads the one level (reading the tap resets it)",
         {v(qid, 10.0, "level") for qid in ("all", "tone", "menu", "shot")}, {v("all", 10.0, "level")})
    t.near("timeScale 0: everything plays on", v("all", 12.0, "volume"), STEADY, FLOAT)
    t.near("a streaming clip reads like any other", v("stream", 1.0, "volume"), 0.3, FLOAT)
    t.eq("the mixer group by its name", [v("sfx", 1.0, "count"), v("sfx", 1.0, "loudest")], [1.0, "Mixed550"])
    t.eq("... its parent group's name doesn't match", v("master", 1.0, "count"), 0.0)
    t.near("the select's owner", v("owner", 1.0, "volume"), 0.16, FLOAT)
    t.eq("an owner select naming a component type no project has owns nothing (its query_errors line: PLAYS)",
         v("ghost", 1.0, "count"), 0.0)
    near = 0.5 / 2
    second = (0.8 / math.dist((0, 0, 5), (100, 0, 0)) + 0.5 + 1.0 + 0.3 + 0.2 + 0.0009 + 0.5 + near)
    t.eq("the second listener alone", [v("all", 15.0, "listener"), v("all", 15.0, "count"), v("all", 15.0, "audible")], ["SecondCamera", 10.0, 7.0])
    t.near("... the volumes at it", v("all", 15.0, "volume"), second, FLOAT)
    t.eq("no listener: no value", [play.value("all", 16.5), play.value("all", 17.0)], [None, None])
    t.eq("after the scene load: its listener and source", [v("all", 19.0, "listener"), v("all", 19.0, "count"), v("all", 19.0, "loudest")],
         ["Player2Camera", 1.0, "Room523"])
    t.near("... the mix measured on the new listener", v("all", 20.0, "level"), LEVEL * 0.3, LEVEL * 0.3 * 0.01)

    def ear(when, name, field):
        row = play.row("ears", when, name) or {}
        return row.get(field)
    for when, name in ((5.0, "PlayerCamera"), (12.0, "PlayerCamera"), (15.5, "SecondCamera"), (20.0, "Player2Camera")):
        t.eq(f"{name} at {when:g} s: the probe's tap is on it", ear(when, name, "prop:LightEar.tapped"), 1.0)
        t.ok(f"{name} at {when:g} s: the mix reaches the tap", (ear(when, name, "prop:LightEar.peak") or 0) > 0.05, ear(when, name, "prop:LightEar.peak"))
        t.eq(f"{name} at {when:g} s: nothing leaves the tap", ear(when, name, "prop:LightEarAfter.peak"), 0.0)
        t.ok(f"{name} at {when:g} s: ... though buffers pass", (ear(when, name, "prop:LightEarAfter.buffers") or 0) > 0)
    # two listeners on, 13 to 14.5 s (Unity warns): the filters of both run one after the other on the one mix, the
    # second tap getting the first's silence; Unity places the sound at the listener that came on last (SecondCamera)
    t.eq("two listeners on: both have a tap from the frame the second came on", [ear(13.0, "PlayerCamera", "prop:LightEar.tapped"),
         ear(13.0, "SecondCamera", "prop:LightEar.tapped")], [1.0, 1.0])
    t.eq("... nothing leaves either", [ear(14.0, name, "prop:LightEarAfter.peak") for name in ("PlayerCamera", "SecondCamera")], [0.0, 0.0])
    t.eq("... the measure's listener: the first in hierarchy order", v("all", 14.0, "listener"), "PlayerCamera")
    both, alone, near_ms = v("all", 14.0, "level") or 0, v("all", 15.0, "level") or 0, (near * LEVEL) ** 2
    t.near("... the level is the whole mix Unity makes at SecondCamera: the second alone at 15 s hears it and Near "
           "(level(15 s)^2 - level(14 s)^2 is Near's; with the second tap's silence counted it came out 0.023)",
           alone ** 2 - both ** 2, near_ms, near_ms * 0.1)
    t.eq("the game's own FindObjectsByType doesn't find the tap (it is hidden from it); its GetComponents does (the keeper's after-ears)",
         [(play.row("keeper", w, "EarKeeper") or {}).get("prop:LightEarKeeper.seen") for w in (2.0, 14.0, 20.0)], [0.0, 0.0, 0.0])


def audio_again(t, play):
    """Two plays of one build measure the same, every field but the mix's (real time): this play against `audio`."""
    first = play.earlier("audio")
    for qid in ("all", "tone", "sfx", "owner", "shooter", "shooter_clip", "shot", "main", "point", "late", "stream", "menu"):
        a = [{k: x for k, x in (s.get("value") or {}).items() if k not in ("level", "peak")} for s in first.samples(qid)]
        b = [{k: x for k, x in (s.get("value") or {}).items() if k not in ("level", "peak")} for s in play.samples(qid)]
        t.eq(f"{qid}: the same as the first play but for the mix", b, a)
    t.eq("the taps: on the same listeners at the same times",
         [[(r.get("name"), r.get("prop:LightEar.tapped")) for r in s.get("rows") or []] for s in play.samples("ears")],
         [[(r.get("name"), r.get("prop:LightEar.tapped")) for r in s.get("rows") or []] for s in first.samples("ears")])


ROLLOFF = [1.0, 0.5, 0.25, 0.125, 1 / 80, 1.0, 0.75, 0.5, 0.25, 1 - 0.75 * 0.01 / 20 / 0.5, 0.4, 0.15, 0.625, 1.0, 1.0, 1.0]
IN_MIX = [1.0] * 14 + [0.1, 0.5]  # the -20 dB mixer group, then AudioListener.volume 0.5: in the mix, not the volume


def rolloff(t, play):
    """One tone moved through the rolloff modes (LightRolloff), 2 s a step: the measure's volume against the formula,
    and the mix's RMS (the tap) against the volume: 0.25 a unit (a 0.5 sine, -3 dB into each channel), the mixer's
    -20 dB and AudioListener.volume in the mix only. Logarithmic rolloff goes on falling past max distance (1/80 at
    80 m, max 50)."""
    for i, want in enumerate(ROLLOFF):
        for when in (2 * i + 1.0, 2 * i + 1.5):
            t.near(f"step {i} at {when:g} s: volume", at(play, "all", when, "volume"), want, FLOAT)
        level = want * IN_MIX[i] * LEVEL
        t.near(f"step {i}: the mix's RMS is the volume's", at(play, "all", 2 * i + 1.5, "level"), level, level * 0.01)


def stray(t, play):
    """The tap acts only in a probe play. In this one it silences the tone; the player started without -taskProbe
    (-lightstray), carrying a tap the game added itself, lets it through (its own LightMute keeps the machine quiet)."""
    row = play.row("ears", 2.0, "StrayCamera") or {}
    t.eq("in a probe play the probe's tap is on the listener", row.get("prop:LightEar.tapped"), 1.0)
    t.ok("... the tone reaches the tap", (row.get("prop:LightEar.peak") or 0) > 0.03, row.get("prop:LightEar.peak"))
    t.eq("... and nothing leaves it", row.get("prop:LightEarAfter.peak"), 0.0)
    t.ok("... though buffers pass", (row.get("prop:LightEarAfter.buffers") or 0) > 0, row.get("prop:LightEarAfter.buffers"))
    t.near("... its level: a 0.05 sine at volume 1", at(play, "all", 2.0, "level"), LEVEL / 10, LEVEL / 10 * 0.01)
    exe = t.project / "Build" / "TaskProbe" / "Game.exe"
    log = t.project / "Logs" / "ProbeTests" / "light.stray_run.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    log.unlink(missing_ok=True)
    subprocess.run([sys.executable, str(unity.DESK), str(exe), "-screen-fullscreen", "0", "-screen-width", "960", "-screen-height", "540",
                    "-logFile", str(log), "-lightstray"], cwd=str(exe.parent), timeout=120)
    text = log.read_text(encoding="utf-8", errors="replace") if log.is_file() else ""
    found = re.search(r"LIGHT stray tap=(\S+) before=(\S+) after=(\S+)", text)
    t.ok("without a probe play: the run reported", found, text[-300:])
    if found:
        t.eq("... the game's own tap was on the listener", found.group(1), "True")
        t.ok("... and let the tone through", float(found.group(3)) > 0.03, found.group(3))


PLAYS = {
    # the ears hear the mix, which runs in real time
    "lamps": {"check": lamps, "errors": [r"^light nopoint: no point$"], "varies": ["ears"]},
    "lamps_builtin": {"check": lamps_builtin, "args": ["-lightbuiltin"],
                      "errors": [r"^light A: the render pipeline isn't URP", r"^light F2: the render pipeline isn't URP",
                                 r"^grading grade: the render pipeline isn't URP"]},
    "baked": {"check": baked},
    "sky": {"check": sky},
    "grade": {"check": grade, "errors": GRADE_ERRORS},
    "grade_script": {"check": grade_script, "args": ["-gradescript"], "errors": GRADE_ERRORS},
    "grade_first": {"check": grade_first, "args": ["-gradeexposed"]},
    # audio plays run in real time and the mix's level with it: each is played once, and audio_again compares two
    "audio": {"check": audio, "varies": True, "errors": [r"^audio ghost: no component type NoSuchType$"]},
    "audio_again": {"check": audio_again, "varies": True},
    "rolloff": {"check": rolloff, "varies": True},
    "stray": {"check": stray, "varies": True},
}
