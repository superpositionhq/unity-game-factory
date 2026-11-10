"""The grading probe's colour pipeline (colour.py) against URP's own formulas: neutral settings leave the grey alone,
each grading step moves it the way URP's LUT builder does."""

import math
import unittest

import helpers  # noqa: F401  (puts the tools folder on the path)

from task_check import colour


def neutral_from_the_probe():
    """What the probe sends for a volume stack with no grading overrides: URP's own neutral constants, in float32."""
    def f32(v):
        return float(f"{v:.7g}")

    lgg = colour.lift_gamma_gain()
    return {"color_balance": [f32(v) for v in colour.lms_coeffs(0, 0)], "contrast": 1.0, "saturation": 1.0,
            "color_filter": [1.0, 1.0, 1.0, 1.0], "post_exposure": 0.0,
            "lift": [f32(v) for v in lgg["lift"]] + [0.0], "gamma": [f32(v) for v in lgg["gamma"]] + [0.0],
            "gain": [f32(v) for v in lgg["gain"]] + [0.0], "tonemapping": "None",
            "sun": {"name": "Sun", "color": [1, 1, 1], "intensity": 2, "temperature": 6570, "use_temperature": False,
                    "lit_color": [1, 1, 1]},
            "sky": {"mode": "Skybox", "color": [0.2, 0.2, 0.2], "intensity": 1}, "fog": {"enabled": False}}


class Neutral(unittest.TestCase):
    def test_no_settings_leave_grey_exactly_neutral(self):
        self.assertEqual(colour.colour({}), {"grey": 0.18, "cast": 0.0, "warmth": 0.0, "tint": 0.0,
                                             "saturation": 1.0, "contrast": 1.0})
        self.assertEqual(colour.colour(None)["grey"], 0.18)

    def test_urps_own_neutral_constants_leave_grey_exactly_neutral(self):
        """URP's neutral isn't the identity (6-digit LMS matrices, luminance weights summing to 1.0000001, float32):
        the checker takes that rounding out."""
        found = colour.colour(neutral_from_the_probe())
        self.assertEqual((found["grey"], found["cast"], found["warmth"], found["tint"]), (0.18, 0.0, 0.0, 0.0))
        self.assertEqual((found["saturation"], found["contrast"]), (1.0, 1.0))

    def test_the_neutral_constants_are_urps(self):
        self.assertTrue(all(abs(c - 1) < 4e-6 for c in colour.NEUTRAL_LMS), "ColorBalanceToLMSCoeffs(0, 0) ~ 1")
        lgg = colour.lift_gamma_gain()
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
        brighter = colour.lift_gamma_gain(gain=(1, 1, 1, 0.5))
        self.assertAlmostEqual(brighter["gain"][0], 1.5, places=6, msg="the trackball's w adds to the gain")
        self.assertAlmostEqual(colour.colour(brighter)["grey"], 0.27, places=6)
        warm_gain = colour.lift_gamma_gain(gain=(1.0, 0.9, 0.7, 0))
        self.assertGreater(colour.colour(warm_gain)["warmth"], 0.1)
        darker = colour.lift_gamma_gain(gamma=(1, 1, 1, 0.5))
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


if __name__ == "__main__":
    unittest.main()
