"""derive and world: scene-building ops from the replayed step runs, and a check that they rebuild the scenes.

derive (docs/unity-replay.md, "World ops"): for every run that changed a scene, its export
(work/scenedumps/<run>/scenes/<scene>.json, settings "scene_exports": true) is compared with the scene's previous
export:
  - the run made the scene anew (it logged scene.build / scene.create for it, or no object survived by path):
    scene.create, then object.spawn for every GameObject in hierarchy order, then scene.save
  - otherwise: object.spawn for new objects, object.remove for gone ones, object.update for changed ones
Without per-run exports, each scene of the final replay dump (work/dump-replay) is one scene.create with all its
objects. Each object op carries the object as dumped (components with every serialized value, references as paths).
Ops are written in the workflow field set (id, chapter, op, target, params, reason, source, expected, presentation)
with status "derived_from_replayed_step_run"; reasons are the builder's own workflow rows of that run.

world: editor/ReplayWorld.cs plays the ops headless in the replay project (each scene rebuilt under
Assets/CreationReplayWorld/, then dumped and removed again) and the rebuilt scenes are compared with the scenes the
steps built (work/world/report.json): the ops hold everything the scenes are.
"""
import collections
import json
import math
import os
import shutil

import runner

WORLD_DIR = "Assets/CreationReplayWorld"


def camera_for(locs):
    """A view that frames a group of object positions from the front-left, looking down (Unity: y up)."""
    if not locs:
        return None
    xs, ys, zs = zip(*locs)
    cx, cy, cz = sum(xs) / len(xs), sum(ys) / len(ys), sum(zs) / len(zs)
    ext = max(max(xs) - min(xs), max(zs) - min(zs), 4.0)
    dist = min(max(ext * 1.1, 9.0), 120.0)
    pitch, yaw = 32.0, 55.0
    r = math.radians(yaw)
    back = (math.sin(r) * dist * 0.85, math.cos(r) * dist * 0.85)
    return {"position": [round(cx - back[0], 2), round(cy + dist * 0.55, 2), round(cz - back[1], 2)], "pitch": pitch, "yaw": yaw}


def view(o):
    return json.dumps({k: o.get(k) for k in ("name", "active", "tag", "layer", "static", "prefab", "components")}, sort_keys=True)


def ops_for_scene_state(scene, dump, prev, created, src, seq, reason, chapter):
    """Ops turning `prev` (previous export or None) into `dump` (this export)."""
    objs = {o["path"]: o for o in dump["objects"]}
    order = [p for p in dump.get("order", []) if p in objs]
    ops = []

    def op(kind, target, params, extra=None):
        seq[0] += 1
        o = {"schema": "unity-replay.world-op/v1", "id": "WOP%05d" % seq[0], "chapter": chapter, "op": kind, "target": target,
             "params": params, "reason": reason, "status": "derived_from_replayed_step_run", "source": src}
        if extra:
            o.update(extra)
        ops.append(o)
        return o

    groups = collections.OrderedDict()
    for p in order:
        groups.setdefault(p.rsplit("/", 1)[0] if "/" in p else "(root)", []).append(p)
    cams = {g: camera_for([objs[p].get("position") or [0, 0, 0] for p in ps]) for g, ps in groups.items()}

    def spawn(p, kind="object.spawn"):
        o = objs[p]
        g = p.rsplit("/", 1)[0] if "/" in p else "(root)"
        hold = max(0.03, min(0.25, 6.0 / (len(groups.get(g, [])) or 1)))   # a group of any size takes 1-6 s on screen
        return op(kind, scene, {"path": p, "object": o},
                  {"group": "%s|%s" % (scene, g), "hold": hold, "expected": {"path": p, "components": len(o.get("components", []))},
                   "presentation": {"camera": cams.get(g), "group": g, "hold_seconds": hold}})

    if created or prev is None:
        # each build gets its own scene (scene path + run id), so a rebuild never overwrites the scene it was made from
        op("scene.create", scene, {"scene": scene, "as": "%s__%s.unity" % (scene[:-len(".unity")], src.get("run", "x"))},
           {"hold": 1.5, "presentation": {"hold_seconds": 1.5}})
        for p in order:
            spawn(p)
    else:
        pa = {o["path"]: o for o in prev["objects"]}
        for p in order:
            if p not in pa:
                spawn(p)
            elif view(pa[p]) != view(objs[p]):
                spawn(p, "object.update")
        for p in pa:
            if p not in objs:
                op("object.remove", scene, {"path": p}, {"hold": 0.05})
    op("scene.save", scene, {"settings": dump.get("settings")}, {"hold": 0.8, "expected": {"objects": len(order)}})
    return ops


def cmd_derive(cfg, a):
    ctx = runner.Ctx(cfg)
    led = ctx.ledger
    runs, ran = {}, {}
    if os.path.exists(os.path.join(ctx.work, "runs.jsonl")):
        with open(os.path.join(ctx.work, "runs.jsonl"), encoding="utf-8") as f:
            for l in f:
                r = json.loads(l)
                if r.get("run") and not r.get("skipped"):
                    ran[r["run"]] = r
                if r.get("run") and r.get("scene_dump"):
                    runs[r["run"]] = r
    orig_rows = {}
    for l in runner.git(ctx.repo, "show", "%s:workflow.jsonl" % led["final"], check=False).splitlines():
        if l.strip():
            x = json.loads(l)
            orig_rows[x.get("id")] = x
    seq = [0]
    out = []
    last = {}
    for w in led["windows"]:
        for run in w["runs"]:
            rr = runs.get(run["id"])
            rows = [orig_rows[i] for i in run["rows"] if i in orig_rows]
            if not rr:
                if run["id"] in ran:
                    # a run that changed no scene: one caption (what ran, what it logged)
                    seq[0] += 1
                    out.append({"schema": "unity-replay.world-op/v1", "id": "WOP%05d" % seq[0], "chapter": "other", "op": "ui.caption",
                                "target": run["method"], "params": {"rows": dict(collections.Counter(x["op"] for x in rows)),
                                                                     "exit_code": ran[run["id"]].get("exit_code")},
                                "reason": rows[0].get("reason") if rows else None, "status": "derived_from_replayed_step_run",
                                "source": {"run": run["id"], "method": run["method"], "commit": w["sha"], "commit_subject": w["subject"],
                                           "workflow_rows": run["rows"][:50], "time_original": run["start"]},
                                "hold": 0.7, "presentation": {"hold_seconds": 0.7}})
                continue
            rep_rows = []
            rp = os.path.join(ctx.work, "rows", run["id"] + ".jsonl")
            if os.path.exists(rp):
                rep_rows = [json.loads(l) for l in open(rp, encoding="utf-8") if l.strip()]
            created = set(x.get("target") for x in rows + rep_rows if x.get("op") in ("scene.create", "scene.build") and x.get("status") == "observed")
            reason = next((x.get("reason") for x in rows if x.get("op") in ("scene.create", "scene.build")), None) or (rows[0].get("reason") if rows else None)
            src = {"run": run["id"], "method": run["method"], "commit": w["sha"], "commit_subject": w["subject"],
                   "workflow_rows": run["rows"][:50], "time_original": run["start"]}
            sd = os.path.join(ctx.work, rr["scene_dump"]["dir"], "scenes")
            for s in rr.get("scenes_changed", []):
                jp = os.path.join(sd, s.replace("/", "__") + ".json")
                if not os.path.exists(jp):
                    continue
                d = runner.jload(jp)
                prev = last.get(s)
                fresh = s in created or prev is None or not (set(o["path"] for o in d["objects"]) & set(o["path"] for o in prev["objects"]))
                out += ops_for_scene_state(s, d, prev, fresh, src, seq, reason, chapter=os.path.basename(s))
                last[s] = d
    if not last:
        # no per-run exports: every scene of the final replay dump, made in one go
        dd = os.path.join(ctx.work, "dump-replay")
        for s in runner.jload(os.path.join(dd, "scenes.json"), []) or []:
            if s.get("file"):
                d = runner.jload(os.path.join(dd, "scenes", s["file"]))
                out += ops_for_scene_state(s["scene"], d, None, True, {"run": "final", "dump": "dump-replay"}, seq, None,
                                           chapter=os.path.basename(s["scene"]))
    path = os.path.join(ctx.work, "world-ops.jsonl")
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        for o in out:
            f.write(json.dumps(o, ensure_ascii=False) + "\n")
    c = collections.Counter(o["op"] for o in out)
    print("world ops: %d %s -> %s (%s)" % (len(out), dict(c), path, "per-run scene exports" if last else "the final replay dump"))
    return 0


def cmd_world(cfg, a):
    """Rebuild every scene from the world ops (editor/ReplayWorld.cs, headless), dump the rebuilt scenes in the same run,
    remove them again, and compare each with the scene the steps built (its last state in the ops)."""
    import verify
    ctx = runner.Ctx(cfg)
    if not ctx.editor:
        ctx.editor = ctx.editor_for(ctx.proj)
    ops_path = a.only or os.path.join(ctx.work, "world-ops.jsonl")
    if not os.path.exists(ops_path):
        raise SystemExit("run derive first")
    out = os.path.join(ctx.work, "world")
    shutil.rmtree(out, ignore_errors=True)
    os.makedirs(out)
    req = {"ops": ops_path.replace("\\", "/"), "prefix": WORLD_DIR, "out": out.replace("\\", "/"),
           "log": os.path.join(out, "ops-played.jsonl").replace("\\", "/")}
    try:
        code, secs, log = runner.run_tool(ctx, ctx.proj, "CreationReplay.ReplayWorld.Run", req, "world",
                                          timeout=cfg.get("run_timeout_s") or None)
    finally:
        shutil.rmtree(ctx.p(WORLD_DIR), ignore_errors=True)
        if os.path.exists(ctx.p(WORLD_DIR + ".meta")):
            os.remove(ctx.p(WORLD_DIR + ".meta"))
    # the expected state of each scene: its last export in the ops (the object as the steps left it)
    want = {}
    with open(ops_path, encoding="utf-8") as f:
        for l in f:
            o = json.loads(l)
            if o["op"] == "scene.create":
                want[o["target"]] = {"as": o["params"]["as"], "objects": collections.OrderedDict(), "settings": None}
            elif o["op"] in ("object.spawn", "object.update") and o["target"] in want:
                want[o["target"]]["objects"][o["params"]["path"]] = o["params"]["object"]
            elif o["op"] == "object.remove" and o["target"] in want:
                want[o["target"]]["objects"].pop(o["params"]["path"], None)
            elif o["op"] == "scene.save" and o["target"] in want:
                want[o["target"]]["settings"] = o["params"].get("settings")
    counts = collections.Counter()
    res = {}
    for scene, w in want.items():
        rebuilt = WORLD_DIR + "/" + w["as"][len("Assets/"):]
        p = os.path.join(out, "scenes", rebuilt.replace("/", "__") + ".json")
        if not os.path.exists(p):
            res[scene] = {"result": "not rebuilt (see %s)" % os.path.relpath(log, ctx.work)}
            continue
        got = runner.jload(p)
        # the rebuilt scene's paths start with the same roots: compared as they are
        res[scene] = verify.verify_scene(got, {"objects": list(w["objects"].values()), "settings": w["settings"] or got.get("settings")}, counts)
    played = [json.loads(l) for l in open(req["log"], encoding="utf-8")] if os.path.exists(req["log"]) else []
    rep = {"schema": "unity-replay.world/v1", "game": cfg["game"], "time": runner.now(), "exit_code": code, "seconds": secs,
           "ops": sum(1 for _ in open(ops_path, encoding="utf-8")), "ops_played": len(played),
           "ops_failed": sum(1 for x in played if (x.get("result") or {}).get("error")), "scenes": res, "normalised": dict(counts),
           "pass": bool(res) and all("truth_objects" in v and not (v["differs"] or v["missing"] or v["extra"]) for v in res.values())}
    runner.jdump(os.path.join(out, "report.json"), rep)
    for s, v in res.items():
        print("%s: %s" % (s, v.get("result") or "%d/%d identical, %d differ, %d missing, %d extra" % (
            v["identical"], v["truth_objects"], v["differs"], v["missing"], v["extra"])))
    print("world ops %s: %d played, %d failed -> %s" % ("rebuild the scenes" if rep["pass"] else "DIFFER from the scenes",
                                                        rep["ops_played"], rep["ops_failed"], os.path.join(out, "report.json")))
    return 0 if rep["pass"] else 1
