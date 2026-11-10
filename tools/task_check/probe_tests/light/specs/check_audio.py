"""AudioLab: every audio sample of the unfiltered query and the selects. Usage: python check_audio.py <probe.json>"""
import json, sys
p = json.load(open(sys.argv[1], encoding="utf-8"))
m = p["measures"]
for s in m["qAll"]:
    v = s["value"]
    print(round(s["t"], 2), v and {k: (round(x, 4) if isinstance(x, float) else x) for k, x in v.items()})
for q in ["qTone", "qSfx", "qOwner", "qShot", "qPoint", "qLate"]:
    print(q, [(round(s["t"], 1), s["value"]["count"], round(s["value"]["volume"], 4), s["value"]["loudest"]) for s in m[q] if s["value"] and s["value"]["count"]][:6])
print("query_errors:", p.get("query_errors"))
