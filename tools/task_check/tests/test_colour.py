"""The grading probe's colour pipeline (colour.py) against URP's own formulas and against a frame measured in a play:
neutral settings leave the grey alone, each grading step moves it the way URP's LUT builder does, and the GradeLab play
(probe_tests/light/README.md) reads what its frame showed."""

import colorsys
import math
import struct
import unittest

import helpers  # noqa: F401  (puts the tools folder on the path)

from task_check import colour


def f32(v):
    return struct.unpack("f", struct.pack("f", v))[0]


def gamma_to_linear(v):
    """Mathf.GammaToLinearSpace: the sRGB curve below 1, v ** 2.2 from 1 (with it GradeLab's prepared trackballs are
    Unity's to 1e-7; with the sRGB curve above 1 they are 3e-3 off)."""
    if v <= 0.04045:
        return v / 12.92
    return ((v + 0.055) / 1.055) ** 2.4 if v < 1.0 else v ** 2.2


def lift_gamma_gain(lift=(1, 1, 1, 0), gamma=(1, 1, 1, 0), gain=(1, 1, 1, 0)):
    """ColorUtils.PrepareLiftGammaGain: the Lift Gamma Gain override's trackballs (rgb and the w offset) as the shader
    constants the probe sends ({lift, gamma, gain}, rgb each; gamma is the exponent)."""
    def lum(v):
        return sum(w * c for w, c in zip(colour.LUMA, v))

    lt = [gamma_to_linear(v) * 0.15 for v in lift[:3]]
    gm = [gamma_to_linear(v) * 0.8 for v in gamma[:3]]
    gn = [gamma_to_linear(v) * 0.8 for v in gain[:3]]
    return {"lift": [c - lum(lt) + lift[3] for c in lt],
            "gamma": [1.0 / max(c - lum(gm) + gamma[3] + 1.0, 1e-3) for c in gm],
            "gain": [c - lum(gn) + gain[3] + 1.0 for c in gn]}


def neutral_from_the_probe(balance):
    """What the probe sends for a volume stack with no grading overrides: URP's own neutral constants, in float32."""
    lgg = lift_gamma_gain()
    return {"color_balance": balance, "contrast": 1.0, "saturation": 1.0, "color_filter": [1.0, 1.0, 1.0],
            "post_exposure": 0.0, "hue_shift": 0.0, "lift": [f32(v) for v in lgg["lift"]],
            "gamma": [f32(v) for v in lgg["gamma"]], "gain": [f32(v) for v in lgg["gain"]], "tonemapping": "None",
            "sun": {"name": "Sun", "color": [1, 1, 1], "intensity": 2, "temperature": 6570, "use_temperature": 0,
                    "lit_color": [1, 1, 1]},
            "sky": {"mode": "Skybox", "color": [0.2, 0.2, 0.2], "intensity": 1}, "fog": {"enabled": 0}}


class Neutral(unittest.TestCase):
    def test_no_settings_leave_grey_exactly_neutral(self):
        self.assertEqual(colour.colour({}), {"grey": 0.18, "cast": 0.0, "warmth": 0.0, "tint": 0.0,
                                             "saturation": 1.0, "contrast": 1.0})
        self.assertEqual(colour.colour(None)["grey"], 0.18)

    def test_urps_own_neutral_constants_leave_grey_exactly_neutral(self):
        """URP's neutral isn't the identity (6-digit LMS matrices, luminance weights summing to 1.0000001, float32):
        the checker takes that rounding out."""
        for balance in ([f32(v) for v in colour.NEUTRAL_LMS],  # ColorBalanceToLMSCoeffs(0, 0) in double, then float32
                        [1.0000003576278687, 0.9999992847442627, 1.000003457069397]):  # each operation in float32
            found = colour.colour(neutral_from_the_probe(balance))
            self.assertEqual((found["grey"], found["cast"], found["warmth"], found["tint"]), (0.18, 0.0, 0.0, 0.0))
            self.assertEqual((found["saturation"], found["contrast"]), (1.0, 1.0))

    def test_the_neutral_constants_are_urps(self):
        self.assertTrue(all(abs(c - 1) < 4e-6 for c in colour.NEUTRAL_LMS), "ColorBalanceToLMSCoeffs(0, 0) ~ 1")
        lgg = lift_gamma_gain()
        for v in lgg["lift"]:
            self.assertAlmostEqual(v, 0.0, places=7)
        for v in lgg["gamma"] + lgg["gain"]:
            self.assertAlmostEqual(v, 1.0, places=6)
        self.assertEqual(colour.ACESCC_MIDGRAY, 0.4135884)
        self.assertEqual(colour.LUMA, (0.2126729, 0.7151522, 0.0721750))


class Steps(unittest.TestCase):
    def test_white_balance_warms_with_temperature_and_turns_magenta_with_tint(self):
        warm = colour.colour({"color_balance": colour.lms_coeffs(50, 0)})
        cool = colour.colour({"color_balance": colour.lms_coeffs(-50, 0)})
        self.assertGreater(warm["warmth"], 0.3)
        self.assertLess(cool["warmth"], -0.5)
        self.assertGreater(cool["cast"], 0.5)
        self.assertLess(colour.colour({"color_balance": colour.lms_coeffs(0, 50)})["tint"], -0.05, "magenta")
        self.assertGreater(colour.colour({"color_balance": colour.lms_coeffs(0, -50)})["tint"], 0.05, "green")

    def test_white_balance_is_urps_lms_round_trip_relative_to_its_neutral(self):
        coeffs = colour.lms_coeffs(40, -20)
        grey = [0.18] * 3
        lms = [sum(colour.LIN_2_LMS[i][j] * grey[j] for j in range(3)) * coeffs[i] for i in range(3)]
        urp = [sum(colour.LMS_2_LIN[i][j] * lms[j] for j in range(3)) for i in range(3)]
        mine = colour.white_balance(grey, coeffs)
        for a, b in zip(mine, urp):
            self.assertAlmostEqual(a, b, delta=2e-5, msg="within URP's own rounding of its neutral")

    def test_contrast_works_in_logc_around_acescc_midgray(self):
        """URP's contrast pivots on ACEScc_MIDGRAY in LogC, a linear ~0.2248, so it darkens a grey of 0.18."""
        pivot = colour.logc_to_linear(colour.ACESCC_MIDGRAY)
        self.assertAlmostEqual(pivot, 0.2248, places=3)
        for con in (0.5, 1.3):
            want = colour.logc_to_linear((colour.linear_to_logc(0.18) - colour.ACESCC_MIDGRAY) * con
                                         + colour.ACESCC_MIDGRAY)
            found = colour.colour({"contrast": con})
            self.assertAlmostEqual(found["grey"], want, places=12)
            self.assertEqual((found["contrast"], found["cast"]), (con, 0.0))
        self.assertLess(colour.colour({"contrast": 1.3})["grey"], 0.18)
        self.assertGreater(colour.colour({"contrast": 0.5})["grey"], 0.18)
        self.assertAlmostEqual(colour.linear_to_logc(0.18), 0.244161 * math.log10(5.555556 * 0.18 + 0.047996)
                               + 0.386036, places=12)

    def test_the_colour_filter_multiplies_unclipped(self):
        found = colour.colour({"color_filter": [1.0, 0.5, 0.5, 1.0]})
        self.assertGreater(found["warmth"], 0.5)
        self.assertLess(found["grey"], 0.18)
        self.assertAlmostEqual(colour.colour({"color_filter": [2, 2, 2]})["grey"], 0.36, places=12)

    def test_gain_lift_and_gamma_as_urp_prepares_them(self):
        self.assertAlmostEqual(colour.colour({"gain": [2, 2, 2]})["grey"], 0.36, places=12)
        self.assertAlmostEqual(colour.colour({"lift": [0.02, 0.02, 0.02]})["grey"], 0.20, places=12)
        self.assertAlmostEqual(colour.colour({"gamma": [0.5, 0.5, 0.5]})["grey"], 0.18 ** 0.5, places=12)
        brighter = lift_gamma_gain(gain=(1, 1, 1, 0.5))
        self.assertAlmostEqual(brighter["gain"][0], 1.5, places=6, msg="the trackball's w adds to the gain")
        self.assertAlmostEqual(colour.colour(brighter)["grey"], 0.27, places=6)
        warm_gain = lift_gamma_gain(gain=(1.0, 0.9, 0.7, 0))
        self.assertGreater(colour.colour(warm_gain)["warmth"], 0.1)
        darker = lift_gamma_gain(gamma=(1, 1, 1, 0.5))
        self.assertAlmostEqual(darker["gamma"][0], 1 / 1.5, places=6, msg="gamma is sent as the exponent")
        self.assertGreater(colour.colour(darker)["grey"], 0.18, "a gamma trackball raised brightens the mid-tones")

    def test_saturation_scales_around_the_luminance(self):
        lit = {"sun": {"lit_color": [1.0, 0.6, 0.3]}}
        flat = colour.colour({**lit, "saturation": 0.0})
        self.assertAlmostEqual(flat["cast"], 0, places=9)
        self.assertEqual(flat["saturation"], 0)
        rich = colour.colour({**lit, "saturation": 1.5})
        self.assertAlmostEqual(rich["warmth"], colour.colour(lit)["warmth"] * 1.5, places=6)

    def test_the_key_light_gives_the_grey_its_hue_only(self):
        sunset = colour.colour({"sun": {"color": [1, 1, 1], "lit_color": [1.0, 0.6, 0.3]}})
        self.assertGreater(sunset["warmth"], 0.5)
        self.assertAlmostEqual(sunset["grey"], 0.18, places=12)
        self.assertGreater(colour.colour({"sun": {"color": [1.0, 0.6, 0.3]}})["warmth"], 0.5, "else its colour")
        self.assertLess(colour.colour({"sun": None, "sky": {"color": [0.3, 0.5, 1.0]}})["warmth"], 0, "else the sky")
        self.assertEqual(colour.colour({"sun": {"lit_color": [0, 0, 0]}})["grey"], 0.18, "a black light: no hue")

    def test_the_order_is_urps(self):
        """Balance, contrast, filter, gain and lift, gamma, saturation: a lift before the gamma is raised by it."""
        settings = {"lift": [0.1, 0.1, 0.1], "gamma": [0.5, 0.5, 0.5], "gain": [2, 2, 2], "contrast": 1.2}
        c = colour.logc_to_linear((colour.linear_to_logc(0.18) - colour.ACESCC_MIDGRAY) * 1.2 + colour.ACESCC_MIDGRAY)
        self.assertAlmostEqual(colour.colour(settings)["grey"], (c * 2 + 0.1) ** 0.5, places=12)

    def test_the_hue_shift_turns_a_lit_greys_hue(self):
        """URP turns the hue in HSV between gamma and saturation (LutBuilderLdr.shader); a grey has no hue to turn."""
        self.assertEqual(colour.colour({"hue_shift": 120.0}), colour.colour({}), "a neutral grey stays as it is")
        lit = {"sun": {"lit_color": [1.0, 0.6, 0.3]}}
        h, s, v = colorsys.rgb_to_hsv(*colour.grade(lit))
        for shift in (60.0, 180.0, -90.0):
            want = colorsys.hsv_to_rgb((h + shift / 360.0) % 1.0, s, v)
            for a, b in zip(colour.grade({**lit, "hue_shift": shift}), want):
                self.assertAlmostEqual(a, b, delta=2e-4, msg=f"{shift} degrees (URP's HSV has a 1e-4 epsilon)")
        self.assertLess(colour.colour({**lit, "hue_shift": 180.0})["warmth"], -0.5, "a warm grey turned cool")

    def test_a_channel_lifted_below_zero_goes_through_the_shaders_hsv_step(self):
        """The shader goes to HSV and back whatever the hue shift. Above 0 that is its 1e-4 epsilon; a colour whose
        largest channel sits just below 0 comes back with the others above 0 (S = d / (V + 1e-4) is huge and V is
        negative), which the frame shows: (0.18 - 0.18003, 0.18 - 0.21, 0.18 - 0.21) draws (0, 0.0128, 0.0128)."""
        lifted = colour.grade({"lift": [-0.18003, -0.21, -0.21]})
        for got, shader in zip(lifted, (0.0, 0.0128143, 0.0128143), strict=True):
            self.assertAlmostEqual(got, shader, places=6)
        self.assertEqual(colour.grade({"lift": [0.02, 0.02, 0.02]}), [0.18 + 0.02] * 3, "above 0: nothing moves")

    def test_ldr_grading_saturates_the_frame_before_and_after_the_lookup(self):
        """URP's LDR uber pass saturates the exposed frame before the grading lookup (ApplyTonemap) and the lookup holds
        0..1 (LutBuilderLdr.shader): an over-exposed grey reads white, never more, and is graded as white."""
        self.assertEqual(colour.colour({"post_exposure": 3.0})["grey"], 1.0)
        softer = colour.logc_to_linear((colour.linear_to_logc(1.0) - colour.ACESCC_MIDGRAY) * 0.8
                                       + colour.ACESCC_MIDGRAY)
        self.assertAlmostEqual(colour.colour({"post_exposure": 3.0, "contrast": 0.8})["grey"], softer, places=12)
        self.assertEqual(colour.colour({"gain": [10.0, 10.0, 10.0]})["grey"], 1.0)
        blue = colour.grade({"sun": {"lit_color": [0, 0, 1]}})
        self.assertEqual(blue, [0.0, 0.0, 1.0], "the blue light's grey (0, 0, 2.49) clipped before the grading")

    def test_no_setting_stops_the_checker(self):
        """Where the shader's float gives -inf (the LogC of a channel below LogC's floor) or inf (a power that
        overflows), so does the pipeline, and saturate makes it 0 or 1: a red sun under a warm white balance with some
        contrast, a blue one tinted, contrast at its -100, an exposure or a gamma no one would set."""
        red = {"sun": {"lit_color": [1, 0, 0]}, "color_balance": colour.lms_coeffs(100, 0), "contrast": 1.2}
        for settings in (red, {**red, "contrast": 0.0},
                         {"sun": {"lit_color": [0, 0, 1]}, "color_balance": colour.lms_coeffs(0, 100), "contrast": 1.2},
                         {"post_exposure": 2000.0}, {"post_exposure": -2000.0},
                         {"post_exposure": 3.0, "gain": [3.0, 3.0, 3.0], "gamma": [1000.0, 1000.0, 1000.0]},
                         {"gain": [1e300] * 3, "gamma": [1000.0] * 3, "hue_shift": 90.0}):
            found = colour.colour(settings)
            self.assertTrue(all(math.isfinite(v) for v in found.values()), msg=settings)
            self.assertTrue(0.0 <= found["grey"] <= 1.0, msg=settings)
        self.assertEqual(min(colour.grade(red)), 0.0, "the channel the balance took below LogC's floor is black")
        self.assertEqual(colour.colour({"post_exposure": 2000.0})["grey"], 1.0)
        self.assertEqual(colour.colour({"post_exposure": -2000.0})["grey"], 0.0)


class PostExposure(unittest.TestCase):
    def test_post_exposure_scales_the_grey_before_the_grading(self):
        # URP multiplies the frame by 2^postExposure before the grading lookup: one stop doubles a neutral grey
        self.assertAlmostEqual(colour.colour({"post_exposure": 1.0})["grey"], 0.36, places=9)
        self.assertAlmostEqual(colour.colour({"post_exposure": -1.0})["grey"], 0.09, places=9)
        self.assertEqual(colour.colour({"post_exposure": 0.0})["grey"], 0.18)


# GradeLab (probe_tests/light/README.md): the probe's grading value at 1 s (results/grade/probe.json) with a white key
# light. A global volume sets white balance (30, -20), contrast 25, saturation -30, colour filter (1, .9, .8),
# lift/gamma/gain (1, 1, .9, .02) / (.95, 1, 1.05, 0) / (1.05, 1, .95, .1) and tonemapping None; an unlit quad of linear
# 0.18 grey fills the view
GRADE_LAB = {"color_balance": [1.0238763093948364, 1.0338650941848755, 0.7500864863395691], "contrast": 1.25,
             "saturation": 0.7, "color_filter": [1, 0.7874123454093933, 0.6038274168968201], "post_exposure": 0,
             "hue_shift": 0, "lift": [0.022301513701677322, 0.022301513701677322, -0.0095866359770298],
             "gamma": [1.0820449590682983, 0.9879747629165649, 0.9067660570144653],
             "gain": [1.1777211427688599, 1.087072491645813, 0.9990769028663635], "tonemapping": "None",
             "sun": {"lit_color": [1, 1, 1]}}


def srgb8(c):
    """A linear channel as an 8-bit sRGB frame holds it, before rounding."""
    return 255 * (1.055 * c ** (1 / 2.4) - 0.055 if c > 0.0031308 else 12.92 * c)


class MeasuredInAPlay(unittest.TestCase):
    def test_the_probes_constants_are_urps(self):
        """GradeLab's volume as the probe read it: ColorBalanceToLMSCoeffs and PrepareLiftGammaGain of its settings."""
        for a, b in zip(colour.lms_coeffs(30, -20), GRADE_LAB["color_balance"]):
            self.assertAlmostEqual(a, b, delta=1e-6)
        found = lift_gamma_gain(lift=(1, 1, .9, .02), gamma=(.95, 1, 1.05, 0), gain=(1.05, 1, .95, .1))
        for key in ("lift", "gamma", "gain"):
            for a, b in zip(found[key], GRADE_LAB[key]):
                self.assertAlmostEqual(a, b, delta=1e-6, msg=key)

    def test_gradelab_reads_what_its_frame_showed(self):
        """Step by step as the README lists them; the frame's centre read sRGB (121, 117, 91) and screen luminance
        0.17543 (8-bit precision: half a step is 0.0016 here). Inside the local volume (post exposure 1) the frame read
        0.38889, 1 % below the grade: the vignette and bloom active there."""
        steps = [("color_balance", (0.18260, 0.18644, 0.12681)), ("contrast", (0.17331, 0.17788, 0.10958)),
                 ("color_filter", (0.17331, 0.14007, 0.06617)), ("lift", None), ("gain", (0.22641, 0.17456, 0.05652)),
                 ("gamma", (0.20043, 0.17827, 0.07388)), ("saturation", (0.19293, 0.17742, 0.10435))]
        settings = {"sun": GRADE_LAB["sun"]}
        for key, want in steps:
            settings[key] = GRADE_LAB[key]
            for a, b in zip(colour.grade(settings), want or ()):
                self.assertAlmostEqual(a, b, places=5, msg=key)
        for c, shown in zip(colour.grade(GRADE_LAB), (121, 117, 91)):
            self.assertLess(abs(srgb8(c) - shown), 1.0, "within a step of the frame")
        found = colour.colour(GRADE_LAB)
        self.assertAlmostEqual(found["grey"], 0.175445, places=6)
        self.assertAlmostEqual(found["grey"], 0.17543, delta=0.0016, msg="the frame's screen luminance")
        exposed = colour.colour({**GRADE_LAB, "post_exposure": 1.0})["grey"]
        self.assertAlmostEqual(exposed, 0.39275, places=5)
        self.assertAlmostEqual(exposed / 0.38889, 1.0, delta=0.015)


if __name__ == "__main__":
    unittest.main()
