"""Compares the editor pass's result (argv[1], default the request's result file) with expected.json."""
import json
import sys

expected = json.load(open("expected.json"))
request = json.load(open("request.json"))
path = sys.argv[1] if len(sys.argv) > 1 else request["result"]
got = json.load(open(path, encoding="utf-8"))
bad = 0
if got.get("nonce") != request["nonce"]:
    print("nonce differs")
    bad += 1


def same(a, b):
    if isinstance(a, (int, float)) and isinstance(b, (int, float)) and not isinstance(a, bool):
        return abs(a - b) < 1e-5
    return a == b


for mid, e in expected.items():
    g = got["measures"].get(mid)
    ok = False
    if g is None:
        pass
    elif "error" in e:
        ok = "error" in g and e["error"] in g["error"]
    elif "value" in e:
        ok = "value" in g and same(g["value"], e["value"])
    else:
        gr, er = g.get("rows"), e["rows"]
        ok = isinstance(gr, list) and len(gr) == len(er) and all(
            x["name"] == y["name"] and same(x["value"], y["value"]) for x, y in zip(gr, er))
    if not ok:
        bad += 1
        print("FAIL", mid, json.dumps(request["measures"][mid]), "\n   expected", json.dumps(e), "\n   got     ", json.dumps(g))
print(f"{len(expected) - bad}/{len(expected)} as expected")
sys.exit(1 if bad else 0)
