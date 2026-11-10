import json, sys
d = json.load(open(sys.argv[1] + "/probe.json"))
print("errors:", d.get("query_errors"))
for qid, samples in d["measures"].items():
    print("==", qid)
    for s in samples:
        if s["t"] in (0.0, 0.5, 1.0, 3.0, 4.5, 5.0, 5.5, 8.0, 10.0, 12.0, 15.5) or len(sys.argv) > 2:
            v = s.get("value")
            if isinstance(v, dict):
                v = {k: (round(x, 4) if isinstance(x, float) else x) for k, x in v.items() if k != "size"}
            print("  t=%.1f" % s["t"], v)
