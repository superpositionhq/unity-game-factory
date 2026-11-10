"""Hand computation of LightLab's expected light values (URP's formulas, written out independently of the C# query),
compared with a play's probe.json. Usage: python expect_light.py <probe.json> [<play.log>]"""
import json, math, re, sys

LUM = (0.2126729, 0.7151522, 0.0721750)


def lin(v):
    return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4


def lum(rgb):
    return sum(w * c for w, c in zip(LUM, rgb))


def punctual(intensity, colour, light, point, rng):
    d2 = sum((a - b) ** 2 for a, b in zip(light, point))
    f = d2 / (rng * rng)
    smooth = max(0.0, min(1.0, 1 - f * f)) ** 2
    return intensity * lum([lin(c) for c in colour]) * smooth / d2


def spot_factor(light, fwd, point, outer, inner):
    d = [p - l for p, l in zip(point, light)]
    n = math.sqrt(sum(c * c for c in d))
    sdl = sum(a * b for a, b in zip(fwd, d)) / n
    co, ci = math.cos(math.radians(outer / 2)), math.cos(math.radians(inner / 2))
    inv = 1 / max(0.001, ci - co)
    a = max(0.0, min(1.0, sdl * inv - co * inv))
    return a * a


white = (1, 1, 1)
expect = {
    "qA (before 3 s)": ("qA", lambda t: t < 3, punctual(2, white, (0, 3, 0), (0, 1, 0), 10)),
    "qB1": ("qB1", None, punctual(3, white, (20, 3, 0), (20, 1, 0), 10)),
    "qB2": ("qB2", None, punctual(3, white, (20, 3, 0), (20.8, 1, 0), 10) * spot_factor((20, 3, 0), (0, -1, 0), (20.8, 1, 0), 60, 30)),
    "qB3": ("qB3", None, 0.0),
    "qC1": ("qC1", None, 0.0),
    "qC2": ("qC2", None, punctual(2, white, (40, 3, -3), (40, 1, -1), 12)),
}

probe = json.load(open(sys.argv[1], encoding="utf-8"))
m = probe["measures"]
for label, (qid, when, value) in expect.items():
    got = [s["value"]["local"] for s in m[qid] if s.get("value") and (when is None or when(s["t"]))]
    print(f"{label:16s} expected local {value:.6f}  probe {got[0] if got else None!r:.20}  (n={len(got)})")

# the warm light switched on at 3 s: point light, colour (1, .5, .25) at 2700 K: the temperature colour is read from the
# player log's finalColor line (the engine's own number), so the increase in qA is checked against it
if len(sys.argv) > 2:
    log = open(sys.argv[2], encoding="utf-8", errors="replace").read()
    fc = re.findall(r"visible SwitchedA finalColor \(([\d.]+),([\d.]+),([\d.]+)\) lum ([\d.]+)", log)
    if fc:
        lum_final = float(fc[-1][3])
        d2 = 9 + 4 + 9
        f = d2 / 64
        add = lum_final * (1 - f * f) ** 2 / d2
        before = [s["value"]["local"] for s in m["qA"] if s.get("value") and s["t"] < 3]
        after = [s["value"]["local"] for s in m["qA"] if s.get("value") and s["t"] > 3.5]
        print(f"qA after the switch: expected +{add:.6f} (engine finalColor lum {lum_final}); probe {before[-1]:.6f} -> {after[0]:.6f} (+{after[0] - before[-1]:.6f})")
    sun = re.findall(r"visible Sun finalColor \(([\d.]+),([\d.]+),([\d.]+)\) lum ([\d.]+)", log)
    if sun:
        print(f"sun: engine finalColor lum {sun[-1][3]}; probe directional at qD1 {m['qD1'][0]['value']['directional']:.6f}, at qD2 (under the roof) {m['qD2'][0]['value']['directional']:.6f}")
for qid in ("qD1", "qD2"):
    print(qid, [(s["t"], round(s["value"]["sky"], 5), round(s["value"]["directional"], 5)) for s in m[qid][::4]])
print("qObj", m["qObj"][0]["value"], "qNone", m["qNone"][0])
