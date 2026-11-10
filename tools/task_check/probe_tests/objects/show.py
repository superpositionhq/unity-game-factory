# Prints a play's probe.json compactly: per query, the samples at the given times (default a few), rows abbreviated.
import json, sys
p = json.load(open(sys.argv[1] if len(sys.argv) > 1 else r"C:\ugf-c1\proj\Logs\TaskProbe\play\probe.json", encoding="utf-8"))
times = [float(x) for x in sys.argv[2].split(",")] if len(sys.argv) > 2 else [0.0, 2.0, 5.0, 7.0, 10.5, 16.0]
only = sys.argv[3].split(",") if len(sys.argv) > 3 else None
print("errors:", p.get("query_errors"))
def fmt(v):
    if isinstance(v, float): return f"{v:.3g}"
    if isinstance(v, dict): return "{" + ", ".join(f"{k}:{fmt(x)}" for k, x in v.items()) + "}"
    return str(v)
for qid, samples in p.get("measures", {}).items():
    if only and qid not in only: continue
    print(f"== {qid}")
    for s in samples:
        if not any(abs(s["t"] - t) < 0.02 for t in times): continue
        if "rows" in s:
            print(f"  t={s['t']:.2f} total={s.get('total', len(s['rows']))}")
            for r in s["rows"][:12]:
                print("    " + ", ".join(f"{k}={fmt(v)}" for k, v in r.items()))
        else:
            print(f"  t={s['t']:.2f} value={fmt(s.get('value'))}")
