"""AudioRolloff: the probe's volume per step against the measured level (RMS of the listener's mix), normalised to
the first step. Usage: python check_rolloff.py <probe.json>"""
import json, sys
p = json.load(open(sys.argv[1], encoding="utf-8"))
s = p["measures"]["qAll"]
steps = ["log1", "log2", "log4", "log8", "log80", "lin0.5", "lin5.75", "lin10.5", "lin15.25", "cus0", "cus8", "cus14",
         "log4 blend.5", "2D", "2D mixer-20dB"]
ref = None
for i, name in enumerate(steps):
    w = [x["value"] for x in s if 2 * i + 1.0 <= x["t"] <= 2 * i + 2.0 and x["value"] and x["value"]["level"] is not None]
    if not w:
        print(name, "no samples")
        continue
    vol = w[-1]["volume"]
    lev = sum(v["level"] for v in w) / len(w)
    if ref is None:
        ref = lev / vol
    print(f"{name:14s} probe volume {vol:.4f}  level {lev:.5f}  level/ref {lev / ref:.4f}")
