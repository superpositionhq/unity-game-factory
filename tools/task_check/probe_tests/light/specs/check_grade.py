"""GradeLab: the frame's linear grey (screen query, and per channel from the screenshots) against tools/task_check/
colour.py's colour() run on the probe's grading value with a white key light, step by step. Also the local volume's
blend against VolumeManager's formula (1 - d^2/blend^2). Usage: python check_grade.py <play dir> <repo tools/task_check>"""
import json, math, os, sys

play, repo = sys.argv[1], sys.argv[2]
sys.path.insert(0, repo)
import colour as C  # noqa: E402

probe = json.load(open(os.path.join(play, "probe.json"), encoding="utf-8"))
m = probe["measures"]
g = m["qG"][2]["value"]  # t = 1.5, before the walk
print("grading value at t=1.5:", json.dumps({k: v for k, v in g.items() if not k.startswith("post:")}))

white = dict(g, sun={"lit_color": [1, 1, 1]})
res = C.colour(white)
print("colour() with a white key light:", res)

# the same steps, keeping the rgb (colour() reports only luminance and ratios)
rgb = [C.GREY] * 3
steps = [("start", list(rgb))]
rgb = C.white_balance(rgb, C._numbers(g["color_balance"]))
steps.append(("white balance", rgb))
con = C._number(g["contrast"], 1.0)
rgb = [C.logc_to_linear((C.linear_to_logc(c) - C.ACESCC_MIDGRAY) * con + C.ACESCC_MIDGRAY) for c in rgb]
steps.append(("contrast", rgb))
rgb = [max(0.0, c * f) for c, f in zip(rgb, C._vec3(g["color_filter"], 1.0))]
steps.append(("colour filter", rgb))
rgb = [c * gn + lf for c, gn, lf in zip(rgb, C._vec3(g["gain"], 1.0), C._vec3(g["lift"], 0.0))]
steps.append(("gain, lift", rgb))
rgb = [math.copysign(abs(c) ** gm, c) for c, gm in zip(rgb, C._vec3(g["gamma"], 1.0))]
steps.append(("gamma", rgb))
sat = C._number(g["saturation"], 1.0)
lu = C._luminance(rgb)
rgb = [lu + sat * (c - lu) for c in rgb]
steps.append(("saturation", rgb))
for name, v in steps:
    print(f"  {name:14s} rgb {[round(c, 5) for c in v]}  lum {C._luminance(v):.5f}")
print(f"  as sRGB 8-bit: {[round(255 * (1.055 * c ** (1 / 2.4) - 0.055 if c > 0.0031308 else 12.92 * c), 2) for c in rgb]}")

scr = [s for s in m["qS"] if s.get("value")]
print("screen luminance (linear, from 8-bit sRGB):", [(s["t"], round(s["value"]["luminance"], 5)) for s in scr[:6]], "...")
print("screen luminance later:", [(s["t"], round(s["value"]["luminance"], 5)) for s in scr[-12::2]])

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import png  # noqa: E402
for shot in probe.get("screenshots", []):
    img = png.read(os.path.join(play, shot))
    px = png.pixel(img, img[0] // 2, img[1] // 2)
    lin = [C._gamma_to_linear(c / 255) for c in px]
    print(f"{shot}: centre pixel sRGB {px} -> linear {[round(c, 5) for c in lin]} lum {C._luminance(lin):.5f}")

# the local volume's blend: box z in [-5, 5], blend distance 10; the player walks +z from -30 at 2 m/s from 6 s
print("post:ColorAdjustments.postExposure / Bloom.intensity / Vignette.intensity, expected exposure:")
for s in m["qG"][::4]:
    t = s["t"]
    z = -30 + 2 * max(0.0, t - 6)
    d = max(0.0, -5 - z)
    w = 0.0 if d > 10 else 1 - d * d / 100
    v = s["value"]
    print(f"  t={t:5.1f} z={z:6.1f} weight {w:.4f}: postExposure {v['post:ColorAdjustments.postExposure']} (expect {w:.4f}) "
          f"bloom {v['post:Bloom.intensity']} (expect {0.5 + 1.5 * w:.4f}) vignette {v['post:Vignette.intensity']} (expect {0.4 * w:.4f})")
print("other post fields at the end:", {k: v for k, v in m["qG"][-1]["value"].items() if k.startswith("post:")})
print("light exposure:", [(s["t"], round(s["value"]["exposure"], 4)) for s in m["qL"][::6]])
print("query_errors:", probe.get("query_errors"))
