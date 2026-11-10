"""The colour pipeline of the grading probe: a neutral grey (0.18) lit by the key light's hue and run through Unity
URP's colour grading as its LUT builder does it, from the constants the probe reads off the volume stack at the camera
(the values URP itself hands the shader). Nothing here runs Unity.

The order and the constants are URP's (Unity 6.3, com.unity.render-pipelines.* in a project's Library/PackageCache):
- ColorGradingLutPass.cs prepares `_ColorBalance` (ColorUtils.ColorBalanceToLMSCoeffs), `_HueSatCon` (saturation and
  contrast as multipliers, 1 neutral), `_ColorFilter` (linear rgb) and `_Lift`, `_Gamma`, `_Gain`
  (ColorUtils.PrepareLiftGammaGain): the probe sends them as `color_balance`, `saturation`, `contrast`,
  `color_filter`, `lift`, `gamma`, `gain`;
- LutBuilderLdr.shader applies them in this order: white balance in LMS (LinearToLMS, * _ColorBalance, LMSToLinear,
  core Color.hlsl), contrast in LogC around ACEScc_MIDGRAY (LinearToLogC / LogCToLinear, the fast form,
  USE_PRECISE_LOGC 0), the colour filter, max(0), gain and lift (c * gain + lift), gamma (sign(c) * |c|^gamma), the
  global saturation around GetLuminance. Split toning, the channel mixer, shadows/midtones/highlights and the curves
  are left out (the probe doesn't read them; at their defaults they change nothing).

Two of URP's numbers are rounded, so its neutral isn't exactly the identity: the LMS matrices are given to 6 digits
(their round trip is off by up to 4e-6) and ColorBalanceToLMSCoeffs(0, 0) is off 1 by up to 4e-6. The white balance is
therefore taken relative to URP's own neutral (as the engine draws it at its defaults). URP's luminance weights sum to
1.0000001, so a Lift Gamma Gain override at its defaults prepares a gain of 1 - 8e-8 and a lift of -1.5e-8, and the
probe sends float32: every setting within NEUTRAL_TOLERANCE of its neutral value is that value, and `grey` divides by
the weights' sum. Untouched settings leave the grey at exactly 0.18 with no cast."""

import math

GREY = 0.18
LUMA = (0.2126729, 0.7151522, 0.0721750)  # core Color.hlsl Luminance (ColorUtils.Luminance), linear sRGB
LIN_2_LMS = [[3.90405e-1, 5.49941e-1, 8.92632e-3],  # core Color.hlsl LinearToLMS
             [7.08416e-2, 9.63172e-1, 1.35775e-3],
             [2.31082e-2, 1.28021e-1, 9.36245e-1]]
LMS_2_LIN = [[2.85847e+0, -1.62879e+0, -2.48910e-2],  # core Color.hlsl LMSToLinear
             [-2.10182e-1, 1.15820e+0, 3.24281e-4],
             [-4.18120e-2, -1.18169e-1, 1.06867e+0]]
LOGC = {"cut": 0.011361, "a": 5.555556, "b": 0.047996, "c": 0.244161, "d": 0.386036, "e": 5.301883,
        "f": 0.092819}  # core Color.hlsl ParamsLogC (Alexa LogC, El 1000)
ACESCC_MIDGRAY = 0.4135884  # core ACES.hlsl: the pivot of URP's contrast, in LogC
D65_LMS = (0.949237, 1.03542, 1.08728)  # ColorUtils.ColorBalanceToLMSCoeffs: the D65 white point in LMS
NEUTRAL_TOLERANCE = 1e-6  # a setting this close to its neutral value (relative for the LMS coefficients) is neutral


def _mul(m, v):
    return [sum(m[i][j] * v[j] for j in range(3)) for i in range(3)]


def _matmul(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)] for i in range(3)]


def _inverse(m):
    (a, b, c), (d, e, f), (g, h, i) = m
    det = a * (e * i - f * h) - b * (d * i - f * g) + c * (d * h - e * g)
    return [[(e * i - f * h) / det, (c * h - b * i) / det, (b * f - c * e) / det],
            [(f * g - d * i) / det, (a * i - c * g) / det, (c * d - a * f) / det],
            [(d * h - e * g) / det, (b * g - a * h) / det, (a * e - b * d) / det]]


def lms_coeffs(temperature=0.0, tint=0.0):
    """ColorUtils.ColorBalanceToLMSCoeffs: the white balance's LMS multipliers from the White Balance override's
    temperature and tint (-100..100; positive temperature warms the image, positive tint turns it magenta)."""
    t1, t2 = temperature / 65.0, tint / 65.0
    x = 0.31271 - t1 * (0.1 if t1 < 0 else 0.05)
    y = 2.87 * x - 3 * x * x - 0.27509507 + t2 * 0.05
    big_x, big_z = x / y, (1 - x - y) / y
    lms = (0.7328 * big_x + 0.4296 - 0.1624 * big_z, -0.7036 * big_x + 1.6975 + 0.0061 * big_z,
           0.0030 * big_x + 0.0136 + 0.9834 * big_z)
    return [w / v for w, v in zip(D65_LMS, lms, strict=True)]


def _gamma_to_linear(v):
    """Mathf.GammaToLinearSpace (the sRGB curve)."""
    return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4


def lift_gamma_gain(lift=(1, 1, 1, 0), gamma=(1, 1, 1, 0), gain=(1, 1, 1, 0)):
    """ColorUtils.PrepareLiftGammaGain: the Lift Gamma Gain override's trackballs (rgb and the w offset) as the shader
    constants the probe sends ({lift, gamma, gain}, rgb each; gamma is the exponent)."""
    def lum(v):
        return sum(w * c for w, c in zip(LUMA, v))

    lt = [_gamma_to_linear(v) * 0.15 for v in lift[:3]]
    out_lift = [c - lum(lt) + lift[3] for c in lt]
    gm = [_gamma_to_linear(v) * 0.8 for v in gamma[:3]]
    out_gamma = [1.0 / max(c - lum(gm) + gamma[3] + 1.0, 1e-3) for c in gm]
    gn = [_gamma_to_linear(v) * 0.8 for v in gain[:3]]
    out_gain = [c - lum(gn) + gain[3] + 1.0 for c in gn]
    return {"lift": out_lift, "gamma": out_gamma, "gain": out_gain}


NEUTRAL_LMS = lms_coeffs(0.0, 0.0)


def _balance_matrix(coeffs):
    """LMSToLinear(LinearToLMS(c) * coeffs) as a matrix."""
    scaled = [[coeffs[i] * LIN_2_LMS[i][j] for j in range(3)] for i in range(3)]
    return _matmul(LMS_2_LIN, scaled)


_NEUTRAL_INVERSE = _inverse(_balance_matrix(NEUTRAL_LMS))


def white_balance(rgb, coeffs):
    """`rgb` white-balanced by the LMS `coeffs`, relative to URP's neutral (whose rounding is taken out); coefficients
    within NEUTRAL_TOLERANCE of the neutral leave `rgb` as it is."""
    if all(abs(c / n - 1.0) <= NEUTRAL_TOLERANCE for c, n in zip(coeffs, NEUTRAL_LMS, strict=True)):
        return list(rgb)
    return _mul(_matmul(_NEUTRAL_INVERSE, _balance_matrix(coeffs)), rgb)


def linear_to_logc(x):
    """core Color.hlsl LinearToLogC (the fast form URP compiles)."""
    return LOGC["c"] * math.log10(max(LOGC["a"] * x + LOGC["b"], 0.0)) + LOGC["d"]


def logc_to_linear(x):
    """core Color.hlsl LogCToLinear (the fast form URP compiles)."""
    return (10.0 ** ((x - LOGC["d"]) / LOGC["c"]) - LOGC["b"]) / LOGC["a"]


def _luminance(rgb):
    """GetLuminance as URP grades with it (no ACES tonemapping)."""
    return sum(a * b for a, b in zip(LUMA, rgb, strict=True))


def _luma(rgb):
    """A colour's luminance, URP's weights normalised to sum to 1: a grey's luminance is the grey."""
    if rgb[0] == rgb[1] == rgb[2]:
        return rgb[0]
    return _luminance(rgb) / sum(LUMA)


def _finite(v):
    return isinstance(v, int | float) and not isinstance(v, bool) and math.isfinite(v)


def _numbers(found):
    """The first three numbers of a list (a Vector4's w left out), or None."""
    if isinstance(found, list) and len(found) >= 3 and all(_finite(v) for v in found[:3]):
        return [float(v) for v in found[:3]]
    return None


def _snap(v, neutral):
    return neutral if abs(v - neutral) <= NEUTRAL_TOLERANCE else v


def _number(found, neutral):
    """A scalar setting: `neutral` when unset or within NEUTRAL_TOLERANCE of it."""
    return _snap(float(found), neutral) if _finite(found) else neutral


def _vec3(found, neutral):
    """An rgb setting, each value `neutral` within NEUTRAL_TOLERANCE of it; [neutral] * 3 when unset."""
    return [_snap(v, neutral) for v in _numbers(found) or [neutral] * 3]


def _rgb(found):
    found = _numbers(found)
    return [max(0.0, v) for v in found] if found else None


def colour(settings):
    """A neutral grey (0.18) lit by the key light's colour (the sun's lit_color, else its colour, else the sky's; its
    luminance taken out, so only its hue counts), times the post exposure (2^EV: URP multiplies the frame by it before
    the grading lookup), through URP's colour grading in the LUT builder's order: {grey, cast, warmth, tint,
    saturation, contrast}. `settings` is the probe's grading value; a setting it lacks is neutral."""
    settings = settings if isinstance(settings, dict) else {}
    sun = settings.get("sun") if isinstance(settings.get("sun"), dict) else {}
    sky = settings.get("sky") if isinstance(settings.get("sky"), dict) else {}
    light = _rgb(sun.get("lit_color")) or _rgb(sun.get("color")) or _rgb(sky.get("color")) or [1.0, 1.0, 1.0]
    luma = _luma(light)
    rgb = [GREY * c / luma for c in light] if luma > 0 else [GREY] * 3
    exposure = _number(settings.get("post_exposure"), 0.0)
    if exposure != 0.0:
        rgb = [c * 2.0 ** exposure for c in rgb]
    rgb = white_balance(rgb, _numbers(settings.get("color_balance")) or NEUTRAL_LMS)
    con = _number(settings.get("contrast"), 1.0)
    if con != 1.0:  # LogC and back is the identity, up to rounding
        rgb = [logc_to_linear((linear_to_logc(c) - ACESCC_MIDGRAY) * con + ACESCC_MIDGRAY) for c in rgb]
    rgb = [max(0.0, c * f) for c, f in zip(rgb, _vec3(settings.get("color_filter"), 1.0), strict=True)]
    gain, lift = _vec3(settings.get("gain"), 1.0), _vec3(settings.get("lift"), 0.0)
    rgb = [c * g + lf for c, g, lf in zip(rgb, gain, lift, strict=True)]
    rgb = [math.copysign(abs(c) ** g, c) for c, g in zip(rgb, _vec3(settings.get("gamma"), 1.0), strict=True)]
    sat = _number(settings.get("saturation"), 1.0)
    if sat != 1.0:
        luma = _luminance(rgb)
        rgb = [luma + sat * (c - luma) for c in rgb]
    grey = _luma(rgb)
    over = grey if grey > 1e-9 else 1e-9
    return {"grey": grey, "cast": (max(rgb) - min(rgb)) / over, "warmth": (rgb[0] - rgb[2]) / over,
            "tint": (rgb[1] - (rgb[0] + rgb[2]) / 2) / over, "saturation": sat, "contrast": con}
