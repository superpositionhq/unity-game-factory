"""verify: the replayed project against the final commit (docs/unity-replay.md, "What is checked").

  files      every tracked file: identical bytes (sha256 for LFS objects, git blob id otherwise), differs, missing; extras
  assets     dump-replay/assets.json vs dump-truth/assets.json: type, importer and its settings, source file, every
             serialized object, a prefab's hierarchy, per asset path
  scenes     per scene: GameObjects matched by hierarchy path (then nearest position); active, tag, layer, static flags,
             prefab source, every component with its values; references compared as paths; the scene's settings
  rows       each replayed step run's workflow rows vs the original run's rows (op, target, status, params, the step
             text's sha256)
  verdict    PASS / FAIL against the criteria below; metadata of the dataset either way
Writes work/Verification/report.json (docs/schemas/replay-report.schema.json) and report.md.

Pass criteria (all must hold):
  1. every tracked file outside Assets/ is byte-identical to the final commit, none missing, no extra files except
     git-ignored ones;
  2. every asset of the final commit exists in the replay with the same type, import settings and structure;
  3. every scene (settings scene_roots) has the same GameObjects (by hierarchy path) with the same components and values,
     and the same scene settings.
Known differences that are not content are normalised before comparing, counted and listed in the report (NORMALISE);
the bytes of Unity's serialized files under Assets/ are not compared for the verdict (Unity gives every new object a
random file id), they are compared by structure instead.
"""
import collections
import json
import math
import os
import re

import runner

IGNORED_DIRS = ("library/", "temp/", "obj/", "logs/", "usersettings/", "memorycaptures/", "build/", "builds/", ".git/",
                ".vs/", ".idea/", ".vscode/", ".dataset/", runner.TOOL_DIR.lower() + "/")
TOL = 0.0011
SCHEMA_ID = "unity-replay.verification/v1"


def close(a, b):
    if isinstance(a, float) or isinstance(b, float):
        try:
            return math.isclose(float(a), float(b), rel_tol=1e-4, abs_tol=TOL)
        except (TypeError, ValueError):
            return a == b
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(close(x, y) for x, y in zip(a, b))
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(close(a[k], b[k]) for k in a)
    return a == b


def diff_keys(a, b, prefix=""):
    out = []
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b)):
            if k not in a or k not in b:
                out.append(prefix + k)
            elif not close(a[k], b[k]):
                if isinstance(a[k], dict) and isinstance(b[k], dict):
                    out += diff_keys(a[k], b[k], prefix + k + ".")
                else:
                    out.append(prefix + k)
    elif not close(a, b):
        out.append(prefix.rstrip(".") or "value")
    return out


# Known non-content differences, normalised before comparing (each counted in the report):
NORMALISE = [
    ("guid", "GUID strings Unity writes into values at random (an id field of a serialized object)",
     lambda s: re.sub(r"(?i)(?<![0-9a-f])[0-9a-f]{32}(?![0-9a-f])", "<guid>", s)),
]


def add_project_path_rule(cfg):
    """Absolute paths under the project folder (import sources in importer settings) name the folder the editor ran in:
    the truth clone for truth, the replay project for the replay. Compared as <project>/... ; counted as project_path."""
    if any(r[0] == "project_path" for r in NORMALISE):
        return
    pats = []
    for root in (cfg.get("repo"), cfg.get("project_dir"), cfg.get("truth_dir")):
        if not root:
            continue
        parts = [p for p in os.path.abspath(root).replace("\\", "/").split("/") if p]
        rx = []
        for i, p in enumerate(parts):
            # the profile folder after Users/ may hold any (or a scrubbed) user name
            rx.append(r"[^/\\\"]+" if i > 0 and parts[i - 1].lower() == "users" else re.escape(p))
        pats.append(r"(?:/|\\\\)+".join(rx))
    big = re.compile("(?i)(?:%s)(?=/|\\\\)" % "|".join(pats))
    NORMALISE.append(("project_path", "paths into the folder the editor ran in (game repo, truth clone or replay "
                      "project) in import-source fields", lambda s: big.sub("<project>", s)))


def norm_with(obj, rules):
    s = json.dumps(obj, ensure_ascii=False, sort_keys=True)
    for _, _, f in rules:
        s = f(s)
    return json.loads(s)


def tolerant_diff(a, b, counts):
    """diff_keys after the known non-content differences are taken out; counts[rule] += 1 for each rule that removed
    a difference."""
    dk = diff_keys(a, b)
    if not dk:
        return []
    na, nb = norm_with(a, NORMALISE), norm_with(b, NORMALISE)
    rest = diff_keys(na, nb)
    if len(rest) < len(dk):
        for rid, _, f in NORMALISE:   # attribute to the first rule that alone removes some difference
            if len(diff_keys(norm_with(a, [(rid, "", f)]), norm_with(b, [(rid, "", f)]))) < len(dk):
                counts[rid] += 1
                break
    return rest


# ------------------------------------------------------------------------------------------------ files
def verify_files(ctx, final):
    ids = runner.tree_ids(ctx.proj, final)
    have = {}
    for dp, dns, fns in os.walk(ctx.proj):
        rel_d = os.path.relpath(dp, ctx.proj).replace("\\", "/")
        if rel_d != "." and (rel_d.lower() + "/").startswith(IGNORED_DIRS):
            dns[:] = []
            continue
        for fn in fns:
            rel = os.path.relpath(os.path.join(dp, fn), ctx.proj).replace("\\", "/")
            if rel == runner.TOOL_DIR + ".meta":
                continue
            have[rel] = os.path.join(dp, fn)
    res = {"assets": collections.Counter(), "other": collections.Counter(), "differs": [], "missing": [], "extra": []}
    for p, ident in ids.items():
        cat = "assets" if p.startswith("Assets/") else "other"
        if p not in have:
            res[cat]["missing"] += 1
            res["missing"].append(p)
        elif runner.file_matches(have[p], ident):
            res[cat]["identical"] += 1
        else:
            res[cat]["differs"] += 1
            res["differs"].append(p)
    res["extra"] = sorted(p for p in have if p not in ids)
    res["assets"] = dict(res["assets"])
    res["other"] = dict(res["other"])
    return res


# ------------------------------------------------------------------------------------------------ scenes and prefabs
def object_view(x):
    v = {k: x.get(k) for k in ("name", "active", "tag", "layer", "static", "prefab")}
    v["components"] = {("%s#%d" % (c["type"], c.get("index", 0))): c.get("props", {}) for c in x.get("components", [])}
    return v


def match_objects(ra, ta):
    """Pairs (replay, truth): same hierarchy path; among objects that share one, nearest position first."""
    groups = collections.defaultdict(lambda: ([], []))
    for x in ra:
        groups[x["path"]][0].append(x)
    for x in ta:
        groups[x["path"]][1].append(x)
    pairs, missing, extra = [], [], []
    for key, (rs, ts) in groups.items():
        rs = list(rs)
        for t in ts:
            if not rs:
                missing.append(t)
                continue
            best = min(rs, key=lambda r: sum((a - b) ** 2 for a, b in zip(r.get("position") or [0, 0, 0], t.get("position") or [0, 0, 0])))
            rs.remove(best)
            pairs.append((best, t))
        extra += rs
    return pairs, missing, extra


def verify_objects(rep_objs, tru_objs, counts):
    pairs, missing, extra = match_objects(rep_objs, tru_objs)
    exact, differs = 0, []
    field_counts = collections.Counter()
    for r, t in pairs:
        dk = tolerant_diff(object_view(r), object_view(t), counts)
        if dk:
            differs.append({"path": t["path"], "fields": dk[:12]})
            for k in dk:
                # components.<Namespace.Type>#<k>.<field path>: the type's short name and the field's first part
                m = re.match(r"components\.(.+?)#\d+\.([^.]+)", k)
                field_counts[("%s.%s" % (m.group(1).rsplit(".", 1)[-1], m.group(2))) if m else k.split(".")[0]] += 1
        else:
            exact += 1
    return {"truth_objects": len(tru_objs), "replay_objects": len(rep_objs), "matched": len(pairs), "identical": exact,
            "differs": len(differs), "missing": len(missing), "extra": len(extra),
            "differing_fields": dict(field_counts.most_common(20)),
            "detail": {"differs": differs[:200], "missing": [x["path"] for x in missing][:200],
                       "extra": [x["path"] for x in extra][:200]}}


def verify_scene(rep, tru, counts):
    v = verify_objects(rep.get("objects", []), tru.get("objects", []), counts)
    v["settings_same"] = not tolerant_diff(rep.get("settings"), tru.get("settings"), counts)
    return v


# ------------------------------------------------------------------------------------------------ assets
def asset_view(x):
    return {k: x.get(k) for k in ("type", "importer", "importer_settings", "source_sha256", "objects")}


def verify_assets(rep, tru, counts=None):
    counts = counts if counts is not None else collections.Counter()
    a = {x["path"]: x for x in rep["assets"]}
    b = {x["path"]: x for x in tru["assets"]}
    by_type = collections.defaultdict(collections.Counter)
    diffs, load_err = [], []
    for k, t in b.items():
        cls = (t.get("type") or "?").rsplit(".", 1)[-1]
        if k not in a:
            by_type[cls]["missing"] += 1
            diffs.append({"asset": k, "type": cls, "result": "missing"})
            continue
        r = a[k]
        if r.get("type") != t.get("type"):
            by_type[cls]["type_differs"] += 1
            diffs.append({"asset": k, "type": cls, "result": "type", "replay_type": r.get("type")})
            continue
        if r.get("error") or t.get("error"):
            # an asset that cannot be read: equal only when it fails the same way on both sides
            dk = [] if r.get("error") == t.get("error") else ["error"]
            if not dk:
                counts["asset_load_error_both"] += 1
                load_err.append({"asset": k, "type": cls, "error": t.get("error")})
        else:
            dk = tolerant_diff(asset_view(r), asset_view(t), counts)
            if "hierarchy" in t or "hierarchy" in r:
                hv = verify_objects(r.get("hierarchy") or [], t.get("hierarchy") or [], counts)
                if hv["differs"] or hv["missing"] or hv["extra"]:
                    dk.append("hierarchy: %d differ, %d missing, %d extra" % (hv["differs"], hv["missing"], hv["extra"]))
        if dk:
            by_type[cls]["differs"] += 1
            diffs.append({"asset": k, "type": cls, "result": "differs", "keys": dk[:20]})
        else:
            by_type[cls]["same"] += 1
    for k, r in a.items():
        if k not in b:
            cls = (r.get("type") or "?").rsplit(".", 1)[-1]
            by_type[cls]["extra"] += 1
            diffs.append({"asset": k, "type": cls, "result": "extra"})
    total = collections.Counter()
    for c in by_type.values():
        total.update(c)
    return {"total": dict(total), "by_type": {k: dict(v) for k, v in sorted(by_type.items())}, "diffs": diffs,
            "load_error_both": load_err}


# ------------------------------------------------------------------------------------------------ rows
def mask(v, roots):
    s = json.dumps(v, ensure_ascii=False, sort_keys=True)
    for r in roots:
        s = s.replace(r, "<project>").replace(r.replace("/", "\\\\"), "<project>")
    s = re.sub(r"\d+\.\d{3,}", lambda m: "%.2f" % float(m.group(0)), s)
    return json.loads(s)


def original_rows(ctx, final):
    out = {}
    for l in runner.git(ctx.repo, "show", "%s:workflow.jsonl" % final, check=False).splitlines():
        if l.strip():
            try:
                r = json.loads(l)
            except ValueError:
                continue
            out[r.get("id")] = r
    return out


def verify_rows(ctx, ledger):
    orig = original_rows(ctx, ledger["final"])
    roots = [os.path.abspath(ctx.proj).replace("\\", "/"), os.path.abspath(ctx.repo).replace("\\", "/")]
    out = []
    totals = collections.Counter()
    texts = collections.Counter()
    for w in ledger["windows"]:
        for run in w["runs"]:
            p = os.path.join(ctx.work, "rows", run["id"] + ".jsonl")
            if not os.path.exists(p):
                continue
            with open(p, encoding="utf-8") as f:
                rep = [json.loads(l) for l in f if l.strip()]
            org = [orig[i] for i in run["rows"] if i in orig]
            key = lambda r: (r.get("op"), r.get("target"), r.get("status"))
            same_ops = [key(r) for r in rep] == [key(r) for r in org]
            same_params = same_ops and all(mask(a.get("params"), roots) == mask(b.get("params"), roots) for a, b in zip(rep, org))
            res = "identical" if same_params else ("same_ops" if same_ops else "different")
            if not org and not rep:
                res = "none_logged"
            totals[res] += 1
            # the step text that ran: the sha256 WorkflowLog wrote of the step's file, as the builder had it and as
            # the replay had it
            sh_o = sorted(set((r.get("source") or {}).get("sha256") for r in org if (r.get("source") or {}).get("sha256")))
            sh_r = sorted(set((r.get("source") or {}).get("sha256") for r in rep if (r.get("source") or {}).get("sha256")))
            text = "same" if sh_o and sh_o == sh_r else ("differs" if sh_o and sh_r else "not_logged")
            texts[text] += 1
            out.append({"run": run["id"], "method": run["method"], "result": res, "step_text": text,
                        "replayed": len(rep), "original": len(org),
                        "replayed_ops": [list(key(r)) for r in rep][:30], "original_ops": [list(key(r)) for r in org][:30]})
    return {"totals": dict(totals), "step_text": dict(texts), "runs": out}


# ------------------------------------------------------------------------------------------------ verdict
def verdict(report, ctx, counts):
    f = report["files"]
    extra = f.get("extra", [])
    ignored = set()
    if extra:
        try:
            out = runner.git(ctx.proj, "check-ignore", "--stdin", inp=("\n".join(extra) + "\n").encode("utf-8"), check=False)
            ignored = set(l.strip() for l in (out or "").splitlines() if l.strip())
        except Exception:
            ignored = set()
    extra_real = [p for p in extra if p not in ignored]
    other_missing = [p for p in f.get("missing", []) if not p.startswith("Assets/")]
    other_diff = [p for p in f.get("differs", []) if not p.startswith("Assets/")]
    crit = []
    crit.append({"id": "files", "text": "every tracked file outside Assets/ byte-identical; none missing; no extra files except git-ignored ones",
                 "pass": not other_missing and not other_diff and not extra_real,
                 "result": "%d identical, %d differ, %d missing; %d extra (%d git-ignored)" % (
                     f["other"].get("identical", 0), len(other_diff), len(other_missing), len(extra), len(ignored)),
                 "failures": (other_diff + other_missing + extra_real)[:50]})
    if report.get("assets", {}).get("diffs") is not None and report.get("scenes") is not None:
        t = report["assets"]["total"]
        bad = report["assets"]["diffs"]
        crit.append({"id": "assets", "text": "every asset of the final commit present with the same type, import settings and structure",
                     "pass": not bad, "result": "%d same, %d differ, %d missing, %d extra, %d type changed" % (
                         t.get("same", 0), t.get("differs", 0), t.get("missing", 0), t.get("extra", 0), t.get("type_differs", 0)),
                     "failures": [[d["asset"], d["result"], d.get("keys")] for d in bad][:50]})
        sfail, ssum = [], []
        for s, v in report["scenes"].items():
            if "truth_objects" not in v:
                sfail.append([s, v.get("result")])
                continue
            ok = v["missing"] == 0 and v["extra"] == 0 and v["differs"] == 0 and v["settings_same"]
            ssum.append("%s %d/%d" % (s.rsplit("/", 1)[-1], v["identical"], v["truth_objects"]))
            if not ok:
                sfail.append([s, "differs %d, missing %d, extra %d, scene settings %s" % (
                    v["differs"], v["missing"], v["extra"], "same" if v["settings_same"] else "differ")])
        crit.append({"id": "scenes", "text": "every scene: the same GameObjects (hierarchy path) with the same components, "
                                             "values and scene settings",
                     "pass": not sfail, "result": "; ".join(ssum) or "no scenes", "failures": sfail[:50]})
    else:
        crit.append({"id": "assets", "text": "structure dumps of replay and truth", "pass": False, "result": "no structure dumps",
                     "failures": ["run dump --which replay and --which truth"]})
    exclusions = [
        {"id": "asset_bytes", "what": "bytes of Unity's serialized files under Assets/ (scenes, prefabs, materials, "
                                      ".asset): Unity gives every new object a random file id; compared by structure "
                                      "instead (criteria assets, scenes)", "count": f["assets"].get("differs", 0)},
        {"id": "git_ignored_extra_files", "what": "files in the replay project its .gitignore leaves out", "count": len(ignored),
         "items": sorted(ignored)[:200]},
        {"id": "scenes_not_compared", "what": (report.get("scenes_excluded") or {}).get("reason", ""),
         "count": len((report.get("scenes_excluded") or {}).get("scenes", [])),
         "items": (report.get("scenes_excluded") or {}).get("scenes", [])},
    ]
    if ctx.cfg.get("dump_exclusions"):
        # folders left out of the structure dump (reading them fails, in the final commit too); their files are still
        # compared byte for byte under criterion files / asset bytes
        exclusions.append({"id": "structure_dump_excluded", "what": "; ".join("%s: %s" % (d["path"], d["reason"]) for d in ctx.cfg["dump_exclusions"]),
                           "count": len(ctx.cfg["dump_exclusions"])})
    for rid, what, _ in NORMALISE:
        exclusions.append({"id": rid, "what": what, "count": counts.get(rid, 0)})
    if counts.get("asset_load_error_both"):
        exclusions.append({"id": "asset_load_error_both", "what": "assets that fail to load the same way in truth and replay "
                           "(the final commit's own content): compared by type and error only", "count": counts["asset_load_error_both"]})
    adopted = sum((w.get("content") or {}).get("adopted_guids", 0) for w in report.get("windows", []))
    exclusions.append({"id": "guids_adopted", "what": "GUIDs of assets the replay created, given the ones the commit has at "
                       "the same paths at each boundary (Unity makes a random one in every editor; identity, not content)",
                       "count": adopted})
    rows = report.get("rows", {})
    return {"pass": all(c["pass"] for c in crit), "criteria": crit, "exclusions": exclusions,
            "informational": {"workflow_rows_per_run": rows.get("totals", {}), "step_text_per_run": rows.get("step_text", {}),
                              "note": "row comparison is informational: rows carry times, ids and per-run counts"}}


# ------------------------------------------------------------------------------------------------ report
def deviations(ctx, report):
    """Every place the replay departs from the raw recording, for buyers: what, which runs/items, which commit, why."""
    cfg, led = ctx.cfg, ctx.ledger
    runs = [dict(r, _w=w) for w in led["windows"] for r in w["runs"]]
    out = []

    def add(kind, what, items, reason=None):
        if items:
            out.append({"kind": kind, "what": what, "items": items, **({"reason": reason} if reason else {})})

    for u in cfg.get("use_commit_text", []):
        hit = [r for r in runs if u["script"] in (r.get("texts") or {}) or u["script"] in (r.get("unknown") or [])
               if r["_w"]["index"] in u.get("windows", [r["_w"]["index"]])]
        add("commit_text_substituted", "code text taken from the commit instead of the recorded edits",
            [{"script": u["script"], "window": w, "commit": next(r["_w"]["sha"] for r in hit if r["_w"]["index"] == w),
              "runs": [r["id"] for r in hit if r["_w"]["index"] == w]} for w in sorted(set(r["_w"]["index"] for r in hit))],
            u.get("reason"))
    forced = set((u["script"], wi) for u in cfg.get("use_commit_text", []) for wi in u.get("windows", []))
    other = [r for r in runs if r.get("script_version") in ("unknown_use_commit", "commit_text")
             and (r["script"], r["_w"]["index"]) not in forced]
    add("commit_text_unrebuildable", "step text the recording could not rebuild (e.g. perl -i edits, edits outside "
        "the recording): the window's commit text is used", [{"script": r["script"], "window": r["_w"]["index"],
                                                              "commit": r["_w"]["sha"], "run": r["id"]} for r in other])
    add("code_at_run_time_unknown", "runs whose code at that moment the recording cannot rebuild (a shell edit it cannot "
        "follow): those files had the window's commit text", [{"run": r["id"], "method": r["method"], "files": r["unknown"]}
                                                             for r in runs if r.get("unknown") and not r.get("readonly")])
    ro = set(cfg.get("not_readonly", []))
    add("readonly_step_replayed", "steps a read-only pattern matches, replayed because a later run reads what they write",
        [{"method": r["method"], "run": r["id"]} for r in runs if not r.get("readonly") and (r.get("cls") in ro or any(
            n.get("tool_use_id") == r.get("action_tool_use_id") for n in cfg.get("not_readonly_runs", [])))])
    add("runs_not_replayed", "runs listed in the recording that never started (settings not_run, a first open that "
        "stopped before them, or a wrapper that logged no start)",
        [{"method": r["method"], "run": r["id"], "reason": r.get("not_run") or "no wrapper row and no exit code"}
         for r in runs if r.get("not_run") or (r.get("via_wrapper") and r.get("wrapper_rows") == 0 and r.get("exit_code") is None)])
    add("runs_from_rows", "runs the recorded actions missed (a gap in the recording), rebuilt from the workflow row the "
        "step wrote (settings runs_from_rows)",
        [{"method": r["method"], "run": r["id"], "row": r["from_row"], "window": r["_w"]["index"]} for r in runs if r.get("from_row")])
    add("readonly_runs_skipped", "probes and checks (settings readonly_patterns) listed but not replayed",
        [{"method": r["method"], "run": r["id"]} for r in runs if r.get("readonly")])
    add("setup_runs", "the first open (Scripts/unity.ps1 setup, also run by new-game.ps1) replayed as its runs, from the "
        "game's own setup table", [{"run": r["id"], "method": r["method"], "window": r["_w"]["index"]} for r in runs if r.get("kind") == "setup"])
    add("render_runs_headless", "steps the builder ran with -Render (the GPU), replayed headless like every replay run: "
        "what they rendered (screenshots, baked lighting) can differ",
        [{"run": r["id"], "method": r["method"]} for r in runs if r.get("render") and not r.get("readonly")])
    add("shell_steps", "shell commands of the builder replayed from settings (delete, move-merge, copy, keep-committed, "
        "host-python), each matched to its recorded command",
        [{"match": s["match"], "argv": s["argv"], "reason": s.get("reason")} for s in cfg.get("shell_replay", [])])
    auto = [dict(s, window=w["index"]) for w in led["windows"] for s in w["shell"] if s.get("auto")]
    add("shell_content_steps", "shell copies, moves and deletes of content files in the recorded commands, done to the "
        "replay's own files at the same point",
        [{"window": s["window"], "op": s["op"], "src": s["src"], "dst": s.get("dst")} for s in auto])
    add("asset_drops", "store packs restored into the project where the builder copied them in",
        [{"id": d["id"], "packs": [it.get("pack") or it.get("to") or it.get("from_git") for it in d["items"]], "reason": d.get("reason")}
         for d in cfg.get("asset_drops", [])])
    log = [json.loads(l) for l in open(os.path.join(ctx.work, "runs.jsonl"), encoding="utf-8")] \
        if os.path.exists(os.path.join(ctx.work, "runs.jsonl")) else []
    add("editor_switch", "commits that name another editor version (an upgrade): from that window on the replay runs on "
        "the editor the commit names, with the project imported again",
        [{"window": x.get("window"), "commit": (x.get("commit") or "")[:10], "from": x.get("from"), "to": x.get("to")}
         for x in log if x.get("kind") == "editor_switch"])
    add("code_at_run_time", "runs replayed with the code as it stood when they started (the window's commit has later code)",
        [{"run": x.get("run"), "method": x.get("method"), "code": x["code_at_run_time"]} for x in log
         if x.get("code_at_run_time") and not str(x["code_at_run_time"]).startswith("commit code")])
    add("code_at_run_time_not_buildable", "runs whose run-time code did not compile here: they got the window's commit code",
        [{"run": x.get("run"), "method": x.get("method"), "detail": x["code_at_run_time"]} for x in log
         if str(x.get("code_at_run_time") or "").startswith("commit code (")])
    add("code_from_commit", "runs whose commit's code does not compile on its editor (a mid-upgrade commit): they ran with "
        "the code of the nearest later commit under which they compile; the commit's code came back at the boundary",
        [dict(x["code_from_commit"], run=x.get("run"), window=x.get("window")) for x in log if x.get("code_from_commit")])
    add("runs_retried_after_editor_crash", "runs the editor crashed in before the step finished, run once more",
        [{"run": x.get("run"), "method": x.get("method"), "retries": x["retried_after_editor_crash"]} for x in log if x.get("retried_after_editor_crash")])
    add("runs_timed_out", "runs stopped at the run time limit (settings run_timeout_s)",
        [{"run": x.get("run"), "method": x.get("method"), "seconds": x.get("seconds")} for x in log if x.get("timed_out")])
    wins = report.get("windows") or []
    add("content_from_commit", "content files the commit added or changed that no replayed step produced, taken from the "
        "commit at the window's end (a GUI edit, a hand edit of a serialized file, a step that is not recorded)",
        [{"window": w["window"], "commit": w["commit"][:10], "files": (w.get("detail") or {}).get("fallback") or w["content"].get("fallback")}
         for w in wins if w["content"].get("fallback")])
    add("structure_dump_excluded", "folders left out of the structure dump", cfg.get("dump_exclusions", []))
    add("assets_failing_to_load", "assets that fail to load the same way in both projects (compared by type and error only)",
        (report.get("assets") or {}).get("load_error_both", []))
    return out


def validate_report(report, schema_path=None):
    """The report against docs/schemas/replay-report.schema.json (the subset of JSON Schema it uses): a list of
    problems, empty when valid. Without the schema file (a delivered ReplayScripts/), nothing is checked."""
    schema_path = schema_path or os.path.join(os.path.dirname(os.path.dirname(runner.HERE)), "docs", "schemas", "replay-report.schema.json")
    if not os.path.isfile(schema_path):
        return []
    with open(schema_path, encoding="utf-8") as f:
        schema = json.load(f)
    problems = []

    def check(v, s, where):
        t = s.get("type")
        types = t if isinstance(t, list) else [t] if t else []
        pytypes = {"object": dict, "array": list, "string": str, "boolean": bool, "integer": int, "number": (int, float)}
        if types and not any(isinstance(v, pytypes[x]) and not (x in ("integer", "number") and isinstance(v, bool)) for x in types):
            problems.append("%s: not %s" % (where, "/".join(types)))
            return
        if "const" in s and v != s["const"]:
            problems.append("%s: not %r" % (where, s["const"]))
        if "pattern" in s and isinstance(v, str) and not re.search(s["pattern"], v):
            problems.append("%s: does not match %s" % (where, s["pattern"]))
        if "minLength" in s and isinstance(v, str) and len(v) < s["minLength"]:
            problems.append("%s: too short" % where)
        if "minimum" in s and isinstance(v, (int, float)) and v < s["minimum"]:
            problems.append("%s: below %s" % (where, s["minimum"]))
        if isinstance(v, dict):
            for k in s.get("required", []):
                if k not in v:
                    problems.append("%s: no %s" % (where, k))
            for k, sub in (s.get("properties") or {}).items():
                if k in v:
                    check(v[k], sub, where + "." + k)
        if isinstance(v, list):
            if "minItems" in s and len(v) < s["minItems"]:
                problems.append("%s: fewer than %d items" % (where, s["minItems"]))
            if "items" in s:
                for i, x in enumerate(v):
                    check(x, s["items"], "%s[%d]" % (where, i))
    check(report, schema, "report")
    return problems


def cmd_report(cfg, a):
    """Refresh an existing verification report without verifying again (the replay project may be gone): recompute
    the deviations from the current settings and re-render report.md. Verdict, criteria and counts stay as verified."""
    ctx = runner.Ctx(cfg)
    vdir = os.path.join(ctx.work, "Verification")
    report = runner.jload(os.path.join(vdir, "report.json"), None)
    if not report:
        raise SystemExit("no Verification/report.json to refresh: run verify")
    report["deviations"] = deviations(ctx, report)
    report["report_refreshed"] = runner.now()
    runner.jdump(os.path.join(vdir, "report.json"), report)
    with open(os.path.join(vdir, "report.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write(render_md(report, ctx))
    print("report refreshed: %d deviation kinds; verdict %s (as verified %s)" % (
        len(report["deviations"]), "PASS" if report["verdict"]["pass"] else "FAIL", report.get("time")))
    return 0 if report["verdict"]["pass"] else 1


def cmd_verify(cfg, a):
    ctx = runner.Ctx(cfg)
    final = ctx.ledger["final"]
    add_project_path_rule(cfg)
    vdir = os.path.join(ctx.work, "Verification")
    os.makedirs(vdir, exist_ok=True)
    rep_d, tru_d = os.path.join(ctx.work, "dump-replay"), os.path.join(ctx.work, "dump-truth")
    report = {"schema": SCHEMA_ID, "game": cfg["game"], "final_commit": final, "time": runner.now()}
    report["files"] = verify_files(ctx, final)
    counts = collections.Counter()
    have_dumps = os.path.exists(os.path.join(rep_d, "done.json")) and os.path.exists(os.path.join(tru_d, "done.json"))
    if have_dumps:
        report["assets"] = verify_assets(runner.jload(os.path.join(rep_d, "assets.json")), runner.jload(os.path.join(tru_d, "assets.json")), counts)
        scenes, excluded = {}, []
        roots = [r.rstrip("/") + "/" for r in cfg.get("scene_roots", ["Assets"])]
        for s in runner.jload(os.path.join(tru_d, "scenes.json"), []):
            name = s["scene"]
            if roots and not any(name.startswith(r) for r in roots):
                excluded.append(name)
                continue
            if s.get("error"):
                scenes[name] = {"result": "scene does not open in the final commit: %s" % s["error"]}
                continue
            t = runner.jload(os.path.join(tru_d, "scenes", s["file"]))
            rp = os.path.join(rep_d, "scenes", s["file"])
            scenes[name] = verify_scene(runner.jload(rp), t, counts) if os.path.exists(rp) else {"result": "scene missing in the replay"}
        report["scenes"] = scenes
        report["scenes_excluded"] = {"reason": "outside the scene roots %s (settings scene_roots): store packs' demo scenes "
                                               "the builder never made" % cfg.get("scene_roots", ["Assets"]), "scenes": excluded}
    else:
        report["assets"] = {"total": {}, "note": "no structure dumps (run dump --which replay and --which truth)"}
        report["scenes"] = None
    report["rows"] = verify_rows(ctx, ctx.ledger)
    report["windows"] = [json.loads(l) for l in open(os.path.join(ctx.work, "windows.jsonl"), encoding="utf-8")] \
        if os.path.exists(os.path.join(ctx.work, "windows.jsonl")) else []
    for w in report["windows"]:
        w["detail"] = {"fallback": (w.get("detail") or {}).get("fallback", [])}
    report["verdict"] = verdict(report, ctx, counts)
    if report["scenes"] is None:
        report["scenes"] = {}
    report["deviations"] = deviations(ctx, report)
    problems = validate_report(report)
    if problems:
        print("report.json does not match docs/schemas/replay-report.schema.json: %s" % "; ".join(problems[:10]))
    runner.jdump(os.path.join(vdir, "report.json"), report)
    md = render_md(report, ctx)
    with open(os.path.join(vdir, "report.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write(md)
    print(md[:6000])
    print("VERDICT: %s" % ("PASS" if report["verdict"]["pass"] else "FAIL"))
    return 0 if report["verdict"]["pass"] else 1


def render_deviations(devs):
    """Markdown: every place the replay departs from the raw recording (also used by package.py's README)."""
    L = ["## Deviations from the recording", ""]
    if not devs:
        return L + ["None: every step was replayed from the recording as recorded.", ""]
    L += ["Everything below is done from the game's replay settings (`game.json`) or by a rule of the replay rather than",
          "straight from the recorded actions; each entry says why.", ""]
    for d in devs:
        L.append("### %s (%d)" % (d["kind"], len(d["items"])))
        L += ["", d["what"] + (". Why: " + d["reason"] if d.get("reason") else "."), ""]
        for it in d["items"][:60]:
            if isinstance(it, dict):
                L.append("- " + "; ".join("%s: %s" % (k, ", ".join(map(str, v)) if isinstance(v, list) else
                                                      (v[:12] if k == "commit" and isinstance(v, str) else v))
                                          for k, v in it.items() if v not in (None, "", [])))
            else:
                L.append("- %s" % it)
        if len(d["items"]) > 60:
            L.append("- ... %d more (report.json)" % (len(d["items"]) - 60))
        L.append("")
    return L


def render_md(r, ctx):
    L = ["# Replay verification: %s at %s" % (r["game"], r["final_commit"][:10]), ""]
    v = r.get("verdict")
    if v:
        L += ["## Verdict: %s" % ("PASS" if v["pass"] else "FAIL"), "", "| criterion | result | pass |", "|---|---|---|"]
        for c in v["criteria"]:
            L.append("| %s | %s | %s |" % (c["text"], c["result"], "yes" if c["pass"] else "**no**"))
        fails = [c for c in v["criteria"] if not c["pass"] and c.get("failures")]
        for c in fails:
            L += ["", "Why %s fails (first %d):" % (c["id"], min(len(c["failures"]), 12)), ""]
            L += ["- %s" % (json.dumps(x, ensure_ascii=False) if not isinstance(x, str) else x) for x in c["failures"][:12]]
        L += ["", "Known differences that are not content (normalised or not compared):", ""]
        for e in v["exclusions"]:
            L.append("- %s: %s (%d)" % (e["id"], e["what"], e["count"]))
        L.append("")
    L += render_deviations(r.get("deviations") or [])
    f = r["files"]
    L += ["## Files against the final commit", "",
          "| | identical | differs | missing |", "|---|---:|---:|---:|",
          "| outside Assets/ | %d | %d | %d |" % (f["other"].get("identical", 0), f["other"].get("differs", 0), f["other"].get("missing", 0)),
          "| Assets/ (bytes) | %d | %d | %d |" % (f["assets"].get("identical", 0), f["assets"].get("differs", 0), f["assets"].get("missing", 0)),
          "", "Files in the replay project that the commit does not have: %d." % len(f["extra"]), ""]
    if r.get("assets", {}).get("diffs") is not None:
        t = r["assets"]["total"]
        L += ["## Assets (structure dump)", "",
              "Same: %d; differs: %d; missing: %d; extra: %d." % (t.get("same", 0), t.get("differs", 0), t.get("missing", 0), t.get("extra", 0)), "",
              "| type | same | differs | missing | extra |", "|---|---:|---:|---:|---:|"]
        for c, x in r["assets"]["by_type"].items():
            L.append("| %s | %d | %d | %d | %d |" % (c, x.get("same", 0), x.get("differs", 0), x.get("missing", 0), x.get("extra", 0)))
        L += ["", "## Scenes (GameObjects)", "",
              "| scene | objects (truth / replay) | matched | identical | differs | missing | extra | fields that differ |",
              "|---|---|---:|---:|---:|---:|---:|---|"]
        for s, x in (r.get("scenes") or {}).items():
            if "truth_objects" not in x:
                L.append("| %s | %s | | | | | | |" % (s, x.get("result")))
                continue
            L.append("| %s | %d / %d | %d | %d | %d | %d | %d | %s |" % (
                s, x["truth_objects"], x["replay_objects"], x["matched"], x["identical"], x["differs"], x["missing"],
                x["extra"], ", ".join("%s %d" % kv for kv in list(x["differing_fields"].items())[:6])))
        ex = r.get("scenes_excluded") or {}
        if ex.get("scenes"):
            L += ["", "Not compared (%d): %s." % (len(ex["scenes"]), ex["reason"])]
    rt = r["rows"]["totals"]
    L += ["", "## Step runs: workflow rows replayed vs original", "",
          ", ".join("%s %d" % kv for kv in sorted(rt.items())) or "none",
          "", "Step text (the sha256 each row carries): " + (", ".join("%s %d" % kv for kv in sorted(r["rows"].get("step_text", {}).items())) or "none"), ""]
    if r["windows"]:
        L += ["## Windows", "", "| # | commit | runs | seconds | fallback | exact | differs | missing | extra | guids adopted |",
              "|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
        for w in r["windows"]:
            c = w["content"]
            L.append("| %d | %s | %d | %.0f | %d | %d | %d | %d | %d | %d |" % (
                w["window"], w["commit"][:7], w["runs"], w["seconds"], c.get("fallback", 0), c.get("exact", 0),
                c.get("differs", 0), c.get("missing", 0), c.get("extra", 0), c.get("adopted_guids", 0)))
    return "\n".join(L) + "\n"
