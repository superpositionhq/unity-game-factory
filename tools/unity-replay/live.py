"""live: the creation replay while a game is being built (docs/unity-replay.md, "Live replay").

  python unity_replay.py live --game <slug>       catch the replay up with the game repo's HEAD, check what the new
                                                  commits did, write findings for the game session (background job)
  python unity_replay.py live-status              every live game: head, replayed windows, last result
  python unity_replay.py truth --game <slug>      the truth project at the settings' final commit, imported
  python unity_replay.py release --game <slug>    at release: catch up, truth, full dumps, verify, package (minutes when
                                                  the live replay kept up)

A game takes part unless its ReplayConfig.json says "live": false (a game without one takes part). Its post-commit hook
(live-hook.ps1, installed by machine/install-git-hook.ps1) starts `live` in the background after every commit and
prints the last job's findings, so the game session sees them at its next commit. The job:

  1. builds the ledger up to HEAD and compares it with the ledger already replayed; when history was rewritten (an
     amend, a rebase) or the settings changed a replayed window, the replay project goes back to the last unchanged
     commit (that commit's tree; listed as an event) and replays from there;
  2. replays the new windows into the persistent replay project (runner.cmd_run: resumable, work/STOP pauses it);
     every editor process runs through unity-heavy.ps1 -Low (yields to every other job, below-normal priority);
  3. checks them: each run against its original (exit code, workflow rows, compile errors), each window's content
     against its commit, and the assets and scenes the new commits touched against the truth project at HEAD
     (structure dumps of just those);
  4. reads the recording for work the replay cannot redo (editor runs it does not recognise, .unitypackage imports from
     the command line, steps outside the repo or naming the live project folder, runs that log no workflow row);
  5. writes work/live/reports/<sha8>.md/.json, work/live/status.json and, when something needs the builder's attention,
     work/live/feedback.md, which the hook prints once.

One job per game (work/live/lock); a commit made while it runs is picked up before it exits.
"""
import collections
import ctypes
import glob
import json
import os
import re
import shutil
import sys
import time
import traceback

import ledger
import runner
import unity_replay

SCHEMA = "unity-replay.live/v1"
KEEP_DUMPS = 3


# ------------------------------------------------------------------------------------------------ helpers
def live_dir(cfg):
    return os.path.join(cfg["work_dir"], "live")


def pid_alive(pid):
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return False
    if os.name == "nt":
        k = ctypes.windll.kernel32
        h = k.OpenProcess(0x1000, False, pid)   # PROCESS_QUERY_LIMITED_INFORMATION
        if not h:
            return False
        code = ctypes.c_ulong()
        ok = k.GetExitCodeProcess(h, ctypes.byref(code))
        k.CloseHandle(h)
        return bool(ok) and code.value == 259   # STILL_ACTIVE
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


class Lock:
    """work/live/lock: one live or release job per game; a lock whose process is gone is taken over."""

    def __init__(self, cfg):
        self.path = os.path.join(live_dir(cfg), "lock")
        self.held = False

    def acquire(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        for _ in range(2):
            try:
                fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            except FileExistsError:
                try:
                    with open(self.path, encoding="utf-8") as f:
                        info = json.load(f)
                except (OSError, ValueError):
                    info = {}
                if pid_alive(info.get("pid")):
                    return False
                try:
                    os.remove(self.path)
                except OSError:
                    return False
                continue
            os.write(fd, json.dumps({"pid": os.getpid(), "time": runner.now()}).encode())
            os.close(fd)
            self.held = True
            return True
        return False

    def release(self):
        if self.held:
            try:
                os.remove(self.path)
            except OSError:
                pass
            self.held = False


def head_of(cfg):
    return runner.git(cfg["repo"], "rev-parse", cfg.get("live_ref") or "HEAD").strip()


def fingerprint(w):
    """What a replayed window depends on: its commit, its runs (methods, texts, flags), drops and shell steps."""
    runs = [[r["id"], r["method"], r.get("args"), r.get("texts"), r.get("unknown"), r.get("absent"), r.get("readonly"),
             r.get("not_run"), r.get("quit"), r.get("env"), r.get("reason")] for r in w["runs"]]
    drops = [[d["id"], [[it.get("from"), it.get("to"), it.get("from_git"), it.get("ref")] for it in d["items"]]] for d in w["drops"]]
    return json.dumps([w["sha"], runs, drops, [s.get("argv") for s in w["shell"]]], sort_keys=True)


def last_unchanged(old, new, done):
    """The last window k <= done whose windows 1..k are unchanged in the new ledger; -1 when the first commit differs."""
    if not old or old["windows"][0]["sha"] != new["windows"][0]["sha"]:
        return -1
    for i in range(1, done + 1):
        if i >= len(new["windows"]) or i >= len(old["windows"]) or fingerprint(old["windows"][i]) != fingerprint(new["windows"][i]):
            return i - 1
    return done


def trim_jsonl(path, keep):
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        lines = [l for l in f if l.strip()]
    out = []
    for l in lines:
        try:
            if keep(json.loads(l)):
                out.append(l)
        except ValueError:
            out.append(l)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write("".join(out))


def reset_to(cfg, old, new, k, why):
    """Put the replay project at window k's commit (the new first commit when k == -1) and forget later windows."""
    ctx = runner.Ctx(cfg)
    k0 = max(k, 0)
    sha = new["windows"][k0]["sha"]
    runner.git(ctx.proj, "checkout", "-q", "-f", "--detach", sha, env={"GIT_LFS_SKIP_SMUDGE": "1"})
    # Store packs dropped in windows 1..k0 may never have been committed: git clean must not take them, and files of
    # theirs that a later window deleted come back (copied only where missing). Library/ and Temp/ are git-ignored and
    # stay (the editor's import cache).
    drops = [d for w in new["windows"][1:k0 + 1] for d in w["drops"]]
    excl = []
    for d in drops:
        for it in d["items"]:
            excl += ["-e", "/" + (it.get("from_git") or it["to"]).strip("/") + "/"]
    runner.git(ctx.proj, "clean", "-fdq", *excl)
    restored = 0
    for d in drops:
        for it in d["items"]:
            if it.get("from_git"):
                continue   # restored from git by the drop itself when a later window needs it again
            src, dst = it["from"], ctx.p(it["to"])
            if os.path.isfile(src):
                if not os.path.exists(dst):
                    os.makedirs(os.path.dirname(dst), exist_ok=True)
                    shutil.copy2(src, dst)
                    restored += 1
                continue
            for dp, _, fns in os.walk(src):
                for fn in fns:
                    t = os.path.join(dst, os.path.relpath(os.path.join(dp, fn), src))
                    if not os.path.exists(t):
                        os.makedirs(os.path.dirname(t), exist_ok=True)
                        shutil.copy2(os.path.join(dp, fn), t)
                        restored += 1
    runner.fix_lfs_pointers(ctx, ["Assets", "ProjectSettings", "Packages"])
    dropped = [r["id"] for w in (old or {"windows": []})["windows"][k0 + 1:] for r in w["runs"]]
    for rid in dropped:
        p = os.path.join(ctx.work, "rows", rid + ".jsonl")
        if os.path.exists(p):
            os.remove(p)
        shutil.rmtree(os.path.join(ctx.work, "scenedumps", rid), ignore_errors=True)
    trim_jsonl(os.path.join(ctx.work, "windows.jsonl"), lambda r: r.get("window", 0) <= k0)
    trim_jsonl(os.path.join(ctx.work, "runs.jsonl"), lambda r: r.get("window", 0) <= k0)
    ctx.state.update({"window": k0, "done": [], "code_failed": [], "window_outputs": [],
                      "provenance": {p: "git:" + sha[:10] for p in runner.scan(ctx.proj)}})
    ctx.save()
    ev = {"time": runner.now(), "kind": "replay_restarted_from_commit", "window": k0, "commit": sha, "reason": why,
          "dropped_runs": len(dropped), "drops_kept": [d["id"] for d in drops], "drop_files_restored": restored}
    runner.jappend(os.path.join(live_dir(cfg), "events.jsonl"), ev)
    print("reset: replay project at window %d (%s): %s" % (k0, sha[:8], why), flush=True)
    return ev


class RunArgs:
    until = None
    force = False


# ------------------------------------------------------------------------------------------------ findings
def finding(level, kind, msg, **where):
    return dict({"level": level, "kind": kind, "message": msg}, **{k: v for k, v in where.items() if v is not None})


def live_tree_regex(cfg):
    parts = [p for p in os.path.abspath(cfg["repo"]).replace("\\", "/").split("/") if p]
    return re.compile(r"(?i)" + r"(?:/|\\{1,2})".join(re.escape(p) for p in parts) + r"(?![\w-])")


def editor_wrappers(cfg, sha):
    """Scripts in the repo (at sha) other than Scripts/unity.ps1 that start the editor with -executeMethod: the
    commands that should yield runs."""
    names = []
    for p in runner.git(cfg["repo"], "ls-tree", "-r", "--name-only", sha, "--", "Scripts").splitlines():
        if not p.endswith((".sh", ".ps1", ".bat", ".cmd", ".py")) or p == "Scripts/unity.ps1":
            continue
        try:
            t = runner.git(cfg["repo"], "show", "%s:%s" % (sha, p))
        except RuntimeError:
            continue
        if re.search(r"(?i)unity(?:\.exe)?\b", t) and re.search(r"(?i)-executeMethod", t):
            names.append(os.path.basename(p))
    return names


def recording_findings(cfg, led, wins):
    """Commands in the new windows that changed the project in a way the replay cannot redo."""
    out = []
    path = os.path.join(cfg["recording"], "actions.jsonl")
    if not wins or not os.path.exists(path):
        return out
    ws = [led["windows"][i] for i in wins]
    lo = ledger.parse_time(led["windows"][wins[0] - 1]["time"]) if wins[0] > 0 else None
    hi = ledger.parse_time(ws[-1]["time"])
    run_tools = set(r.get("action_tool_use_id") for w in ws for r in w["runs"])
    wrappers = editor_wrappers(cfg, ws[-1]["sha"])
    call = (r"(?:^|[;&|(\n]\s*|(?:^|[\s;&|(])(?:sh|bash|source|\.)\s+|-File\s+|&\s*)['\"]?(?:[\w./\\:$~{}-]*[/\\])?"
            r"(?:%s)['\"]?(?=\s|$)")
    wrap_rx = re.compile(call % "|".join(re.escape(n) for n in wrappers)) if wrappers else None
    quoted = re.compile(r"\"(?:[^\"\\]|\\.){40,}\"|'[^']{40,}'")
    # commit messages and row reasons (long quoted prose) name wrappers and editor flags without calling them;
    # quoted program paths ("C:/Program Files/Unity/...") have fewer spaces
    unprose = lambda s: quoted.sub(lambda q: '""' if q.group(0).count(" ") >= 4 else q.group(0), s)
    import_rx = re.compile(r"(?i)Unity(?:\.exe)?['\"]?\s[^\n]*?-importPackage\b")
    for o in led.get("editor_opens", []):
        t = ledger.parse_time(o["time"])
        if (lo and t <= lo) or t > hi or o["kind"] != "unreadable":
            continue
        w = next((x["index"] for x in ws if ledger.parse_time(x["time"]) >= t), ws[-1]["index"])
        out.append(finding("error", "editor_run_not_recognised", "this command started an editor step whose method the "
                           "replay cannot read: run steps as Scripts/unity.ps1 step -Method <Namespace.Class.Method>, with "
                           "the method written out", window=w, command=re.sub(r"\s+", " ", o["command"])[:160]))
    import shellfx
    with open(path, encoding="utf-8") as f:
        for line in f:
            try:
                a = json.loads(line)
            except ValueError:
                continue
            if a.get("tool") not in ("Bash", "PowerShell") or a.get("event") not in ("PostToolUse", "PostToolUseFailure"):
                continue
            t = ledger.parse_time(a["time"])
            if (lo and t <= lo) or t > hi:
                continue
            cmd = (a.get("input") or {}).get("command", "")
            if not isinstance(cmd, str):
                continue
            cmd = shellfx.protect_heredocs(cmd)[0]
            bare = unprose(cmd)
            w = next((x["index"] for x in ws if ledger.parse_time(x["time"]) >= t), ws[-1]["index"])
            short = re.sub(r"\s+", " ", cmd)[:160]
            if import_rx.search(bare):
                out.append(finding("error", "package_import_not_replayable", "a .unitypackage was imported from the command "
                                   "line (-importPackage): the replay redoes editor steps only; import it in an editor step "
                                   "(AssetDatabase.ImportPackage, run with -NoQuit: Assets/Editor/Steps/README.md)",
                                   window=w, command=short))
            if a.get("tool_use_id") in run_tools:
                continue
            if wrap_rx and wrap_rx.search(bare):
                out.append(finding("error", "editor_run_not_recognised", "this command started the editor through a "
                                   "wrapper the replay does not know: run editor steps through Scripts/unity.ps1 step "
                                   "-Method <Namespace.Class.Method> (or add the wrapper to ReplayConfig.json run_patterns)",
                                   window=w, command=short))
    for i in wins:
        for u in led["windows"][i].get("shell_unreadable") or []:
            out.append(finding("warn", "shell_content_unreadable", "a shell command copied, moved or deleted content files "
                               "the replay cannot follow (%s): name the files in the command, or do it in an editor step"
                               % u.get("why"), window=i, command=re.sub(r"\s+", " ", u.get("command", ""))[:160]))
    return out


def ledger_findings(cfg, led, wins):
    out = []
    live_rx = live_tree_regex(cfg)
    chdir_rx = re.compile(r"(?:Directory\.SetCurrentDirectory|Environment\.CurrentDirectory\s*=)\s*\(?\s*@?\"(?:[A-Za-z]:|/)")
    seen = set()
    for i in wins:
        w = led["windows"][i]
        for c in w.get("reconstruction", []):
            if c.get("reconstructed") and not c.get("match"):
                out.append(finding("warn", "step_text_mismatch", "the recorded writes and edits of %s do not make the text "
                                   "commit %s has: it was changed in a way the recording does not hold (an editor or "
                                   "tool outside the agent's file tools); edit code with the agent's file tools only"
                                   % (c["path"], w["sha"][:8]), window=i, script=c["path"]))
        for r in w["runs"]:
            if r.get("not_run") or r.get("readonly"):
                continue   # never replayed: nothing to fix
            where = {"window": i, "run": r["id"], "script": r.get("script") or r["method"]}
            if r.get("script_version") in ("external", "unknown_file"):
                out.append(finding("error", "step_outside_repo", "%s is not declared in a file of the game repo under "
                                   "Assets/: commit every editor step under Assets/Editor/Steps/ and run it from there"
                                   % r["method"], **where))
                continue
            if r.get("script_version") in ("unknown_use_commit", "commit_text") and (i, r["script"]) not in seen:
                seen.add((i, r["script"]))
                out.append(finding("warn", "step_text_unknown", "the text %s had when it ran is not in the recording "
                                   "(edited with a shell command, or outside this session): edit steps with the agent's "
                                   "file tools, or write a new step (BuildTownV2) instead of changing one that already ran"
                                   % r["script"], **where))
            for p, h in (r.get("texts") or {}).items():
                key = (p, h)
                if key in seen:
                    continue
                seen.add(key)
                try:
                    with open(os.path.join(cfg["work_dir"], "blobs", h), encoding="utf-8", errors="replace") as f:
                        txt = f.read()
                except OSError:
                    continue
                if live_rx.search(txt) or chdir_rx.search(txt):
                    out.append(finding("error", "absolute_project_path", "%s names a folder by its absolute path (the game "
                                       "folder, or a SetCurrentDirectory): a replay in another folder would read or write "
                                       "the live project; reach files through the project (\"Assets/...\" asset paths, "
                                       "Application.dataPath, the current directory)" % p, window=i, script=p))
            if not r.get("rows") and r.get("exit_code") in (0, None) and not r.get("via_wrapper"):
                out.append(finding("warn", "no_workflow_rows", "%s logged no workflow.jsonl row: every editor-step run logs "
                                   "at least one row (WorkflowLog.Row)" % r["method"], **where))
    return out


def run_findings(cfg, wins):
    """Each replayed run against the original, each window's content against its commit (runs.jsonl, windows.jsonl)."""
    out = []
    work = cfg["work_dir"]
    ws = set(wins)
    for path, kind in ((os.path.join(work, "runs.jsonl"), "run"), (os.path.join(work, "windows.jsonl"), "window")):
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8") as f:
            recs = [json.loads(l) for l in f if l.strip()]
        prev_extra = set()
        for x in recs:
            if kind == "window":
                # an extra file is reported in the window it appears in, not again in every later window
                extra_now = set((x.get("detail") or {}).get("extra") or [])
                new_extra, prev_extra = sorted(extra_now - prev_extra), extra_now
            if x.get("window") not in ws:
                continue
            if kind == "window":
                d = dict(x.get("detail") or {}, extra=new_extra)
                fb = d.get("fallback") or []
                if fb:
                    out.append(finding("warn", "content_not_replayed", "%d content file(s) in commit %s were made by no "
                                       "replayed step (taken from the commit). Store packs copied in need an asset_drops "
                                       "entry in ReplayConfig.json (docs/unity-replay.md); anything else was made in the "
                                       "editor GUI, by hand-editing a serialized file, by a step that is not committed or "
                                       "not recognised, or by a step whose name marks it read-only. e.g. %s" % (
                                           len(fb), x["commit"][:8], ", ".join(f["path"] for f in fb[:5])), window=x["window"]))
                if d.get("extra"):
                    out.append(finding("warn", "content_extra", "the replay has %d file(s) under Assets/ or ProjectSettings/ "
                                       "that commit %s does not (a step's output that was not committed, or files deleted "
                                       "by hand), e.g. %s" % (len(d["extra"]), x["commit"][:8], ", ".join(d["extra"][:5])),
                                       window=x["window"]))
                continue
            if x.get("kind") != "run" or x.get("skipped"):
                continue
            where = {"window": x["window"], "run": x.get("run"), "script": x.get("method")}
            short = x.get("rows_replayed", 0) < len(x.get("rows_original") or [])
            if x.get("timed_out"):
                out.append(finding("error", "run_timed_out", "%s did not end within the run time limit in the replay (a step "
                                   "started with -NoQuit has to call EditorApplication.Exit itself)" % x.get("method"), **where))
            elif x.get("compile_errors") and x.get("exit_code_original") == 0:
                out.append(finding("error", "run_compile_errors", "the project did not compile when %s ran in the replay, "
                                   "though it did for the builder: the code at that moment depends on something outside "
                                   "the recording. %s" % (x.get("method"), first_errors(os.path.join(work, x.get("log") or ""))), **where))
            elif short and x.get("exit_code") not in (0, None) and x.get("exit_code") != x.get("exit_code_original"):
                out.append(finding("error", "run_failed", "%s exited %s in the replay (original %s) and logged %d of %d "
                                   "workflow rows: it may depend on something outside the repo (an absolute path, an "
                                   "uncommitted file, the live project). %s" % (
                                       x.get("method"), x.get("exit_code"), x.get("exit_code_original"), x.get("rows_replayed", 0),
                                       len(x.get("rows_original") or []), first_errors(os.path.join(work, x.get("log") or ""))), **where))
            elif short:
                out.append(finding("warn", "rows_short", "%s logged %d workflow row(s) in the replay, %d originally" % (
                    x.get("method"), x.get("rows_replayed", 0), len(x.get("rows_original") or [])), **where))
            if str(x.get("code_at_run_time") or "").startswith("commit code ("):
                out.append(finding("info", "code_at_run_time_not_buildable", "the code as it stood when %s ran did not "
                                   "compile here; the run used the commit's code" % x.get("method"), **where))
    return out


def first_errors(log):
    """The step's own errors first (exceptions, compiler errors), editor errors only when there are none."""
    try:
        with open(log, encoding="utf-8", errors="replace") as f:
            lines = [l.strip() for l in f]
    except OSError:
        return ""
    errs = [l for l in lines if re.search(r"error CS\d+|\w+Exception: ", l)][:2] or \
        [l for l in lines if re.search(r"\bError\b|Aborting batchmode", l)][:2]
    return ("First error: " + " | ".join(e[-200:] for e in errs)) if errs else ""


# ------------------------------------------------------------------------------------------------ structure check
def touched_assets(cfg, led, wins, head):
    """Assets (and scenes) the new windows added or changed that exist at head, under the asset and scene roots."""
    in_head = set(runner.git(cfg["repo"], "ls-tree", "-r", "--name-only", head, "--", "Assets").splitlines())
    roots = [r.rstrip("/") + "/" for r in cfg.get("asset_roots", ["Assets"])]
    sroots = [r.rstrip("/") + "/" for r in cfg.get("scene_roots", ["Assets"])]
    assets, scenes = set(), set()
    for i in wins:
        w = led["windows"][i]
        for x in w["content"] + w["inputs"]:
            p = x["path"]
            a = p[:-5] if p.endswith(".meta") else p
            if x["status"] == "D" or a not in in_head or not any(a.startswith(r) for r in roots):
                continue
            if a.endswith(".unity"):
                if any(a.startswith(r) for r in sroots):
                    scenes.add(a)
            else:
                assets.add(a)
    return sorted(assets), sorted(scenes)


def sync_truth(cfg, sha):
    """The truth project (a shared clone of the game repo) at sha; True when it was cloned now."""
    t = cfg["truth_dir"]
    if runner.clone_at(cfg, t, sha):
        return True
    if runner.git(t, "rev-parse", "HEAD").strip() != sha:
        runner.git(t, "checkout", "-q", "-f", "--detach", sha, env={"GIT_LFS_SKIP_SMUDGE": "1"})
        runner.git(t, "clean", "-fdq")
        runner.fix_lfs_pointers_at(t, ["Assets", "ProjectSettings", "Packages"])
    return False


def structure_check(cfg, led, wins, head, lst):
    assets, scenes = touched_assets(cfg, led, wins, head)
    if not assets and not scenes:
        return None, []
    ctx = runner.Ctx(cfg)
    res = {"assets": len(assets), "scenes": scenes}
    sync_truth(cfg, head)
    base = os.path.join(live_dir(cfg), "dumps", head[:8])
    shutil.rmtree(base, ignore_errors=True)
    rd, td = os.path.join(base, "replay"), os.path.join(base, "truth")
    c1, _, _ = runner.dump(ctx, rd, assets=bool(assets), scenes=scenes, only=assets, label="live_dump_replay_" + head[:8])
    c2, _, _ = runner.dump(ctx, td, project=cfg["truth_dir"], assets=bool(assets), scenes=scenes, only=assets,
                           label="live_dump_truth_" + head[:8])
    lst["truth_at"] = head
    out = []
    if not (os.path.exists(os.path.join(rd, "done.json")) and os.path.exists(os.path.join(td, "done.json"))):
        return res, [finding("warn", "dump_failed", "the structure dump did not finish (exit %s / %s): see %s" % (c1, c2, ctx.logs))]
    import verify
    verify.add_project_path_rule(cfg)
    counts = collections.Counter()
    if assets:
        a = verify.verify_assets(runner.jload(os.path.join(rd, "assets.json")), runner.jload(os.path.join(td, "assets.json")), counts)
        res["assets_result"] = a["total"]
        bad = [d for d in a["diffs"] if d["result"] != "extra" or d["asset"] in assets]
        if bad:
            out.append(finding("warn", "assets_differ", "%d of %d touched asset(s) differ from commit %s after the replay, "
                               "so a change to them was made outside the replayed steps (a hand edit of a serialized file, "
                               "a change in the editor GUI, a step that is not recorded): make such changes in an editor "
                               "step. %s" % (len(bad), len(assets), head[:8], "; ".join(
                                   "%s %s%s" % (d["asset"], d["result"], (" (" + ", ".join(map(str, d.get("keys", [])[:3])) + ")") if d.get("keys") else "")
                                   for d in bad[:6]))))
    res["scenes_result"] = {}
    for s in scenes:
        fn = s.replace("/", "__") + ".json"
        rp, tp = os.path.join(rd, "scenes", fn), os.path.join(td, "scenes", fn)
        if not os.path.exists(tp):
            continue
        if not os.path.exists(rp):
            out.append(finding("warn", "scene_differs", "scene %s is missing in the replay" % s))
            continue
        v = verify.verify_scene(runner.jload(rp), runner.jload(tp), counts)
        res["scenes_result"][s] = {k: v[k] for k in ("truth_objects", "replay_objects", "identical", "differs", "missing", "extra")}
        if v["differs"] or v["missing"] or v["extra"] or not v["settings_same"]:
            out.append(finding("warn", "scene_differs", "scene %s after the replay: %d object(s) differ, %d missing, %d extra "
                               "(of %d in commit %s)%s" % (s, v["differs"], v["missing"], v["extra"], v["truth_objects"], head[:8],
                                                           ("; e.g. " + ", ".join(str(x) for x in (v["detail"]["missing"] + v["detail"]["extra"])[:4]))
                                                           if v["missing"] or v["extra"] else "")))
    res["normalised"] = dict(counts)
    dumps = sorted(glob.glob(os.path.join(live_dir(cfg), "dumps", "*")), key=os.path.getmtime)
    for d in dumps[:-KEEP_DUMPS]:
        shutil.rmtree(d, ignore_errors=True)
    return res, out


# ------------------------------------------------------------------------------------------------ report
def render(rep):
    lines = ["# Live replay: %s at %s" % (rep["game"], rep["head"][:8]), "",
             "- Time: %s (%.0f s)" % (rep["time"], rep.get("seconds", 0)),
             "- Replayed windows: %s of %d; this job: %s" % (rep["replayed_to"], rep["total_windows"],
                                                             ", ".join("w%02d" % i for i in rep["windows"]) or "none"),
             "- Result: **%s**" % rep["result"]]
    if rep.get("reset"):
        lines.append("- Restarted from commit %s (window %d): %s" % (rep["reset"]["commit"][:8], rep["reset"]["window"], rep["reset"]["reason"]))
    if rep.get("error"):
        lines.append("- Error: %s" % rep["error"])
    st = rep.get("structure")
    if st:
        lines.append("- Structure check: %d touched asset(s), scenes %s; assets %s" % (
            st["assets"], ", ".join(st["scenes"]) or "none", st.get("assets_result")))
    lines += ["", "## Findings", ""]
    if not rep["findings"]:
        lines.append("None.")
    for f in rep["findings"]:
        where = ", ".join("%s %s" % (k, f[k]) for k in ("window", "run", "script") if f.get(k) is not None)
        lines.append("- [%s] %s: %s%s" % (f["level"], f["kind"], f["message"], (" (%s)" % where) if where else ""))
        if f.get("command"):
            lines.append("  - command: `%s`" % f["command"].replace("`", "'"))
    return "\n".join(lines) + "\n"


def feedback(rep, report_md):
    act = [f for f in rep["findings"] if f["level"] in ("error", "warn")]
    if not act:
        return None
    lines = ["# Replay feedback: %s at %s (%s)" % (rep["game"], rep["head"][:8], rep["time"][:16]), "",
             "The background creation replay of your latest commits found %d thing(s) that keep the dataset from being "
             "replayed exactly. Fix them in your next commits (unity-game-session skill, \"Replay-friendly work\"):" % len(act), ""]
    for f in act[:20]:
        where = ", ".join("%s %s" % (k, f[k]) for k in ("window", "script") if f.get(k) is not None)
        lines.append("- [%s] %s%s" % (f["level"], f["message"], (" (%s)" % where) if where else ""))
    if len(act) > 20:
        lines.append("- ... %d more" % (len(act) - 20))
    lines += ["", "Full report: %s" % report_md]
    return "\n".join(lines) + "\n"


def write_report(cfg, rep):
    d = live_dir(cfg)
    os.makedirs(os.path.join(d, "reports"), exist_ok=True)
    stem = os.path.join(d, "reports", rep["head"][:8])
    runner.jdump(stem + ".json", rep)
    with open(stem + ".md", "w", encoding="utf-8", newline="\n") as f:
        f.write(render(rep))
    status = {k: rep[k] for k in ("game", "head", "time", "result", "replayed_to", "total_windows")}
    status["findings"] = dict(collections.Counter(f["level"] for f in rep["findings"]))
    status["report"] = stem + ".md"
    runner.jdump(os.path.join(d, "status.json"), status)
    # the session hears about a finding once: a window replayed again after a reset gives the same findings, which
    # stay in the report but not in the feedback
    seen_p = os.path.join(d, "reported.json")
    seen = set(runner.jload(seen_p, []) or [])
    key = lambda f: "%s|%s|%s|%s" % (f["kind"], f.get("window"), f.get("script"), re.sub(r"\d+", "#", f["message"])[:160])
    fresh = [f for f in rep["findings"] if key(f) not in seen]
    runner.jdump(seen_p, sorted(seen | set(key(f) for f in rep["findings"])))
    fb = feedback(dict(rep, findings=fresh), (stem + ".md").replace("\\", "/"))
    fbp = os.path.join(d, "feedback.md")
    if fb:
        with open(fbp, "w", encoding="utf-8", newline="\n") as f:
            f.write(fb)
    elif os.path.exists(fbp) and rep["result"] == "ok":
        os.remove(fbp)   # nothing open any more


# ------------------------------------------------------------------------------------------------ job
def catch_up(cfg, lst):
    """One pass: ledger to HEAD, reset when needed, replay, checks. Returns the report."""
    t0 = time.time()
    head = head_of(cfg)
    cfg = dict(cfg, final=head)
    old = runner.jload(os.path.join(cfg["work_dir"], "ledger.json"))
    new, blobs = ledger.build(cfg)
    rep = {"schema": SCHEMA, "game": cfg["game"], "head": head, "time": runner.now(), "windows": [], "findings": [],
           "total_windows": len(new["windows"]) - 1}
    ctx = runner.Ctx(cfg)
    have_project = os.path.isdir(os.path.join(cfg["project_dir"], ".git"))
    done = ctx.state.get("window", 0) if have_project else 0
    k = last_unchanged(old, new, done) if have_project else done
    forced = lst.pop("restart", None)
    if forced is not None and have_project and forced < k:
        k = forced
    unity_replay.save_ledger(cfg, new, blobs)
    if not have_project:
        runner.cmd_prepare(cfg, RunArgs)
        # the project was removed (disk cleanup) while state.json kept its windows: replay again from the first commit
        if runner.Ctx(cfg).state.get("window", 0) > 0:
            rep["reset"] = reset_to(cfg, old, new, -1, "the replay project was removed: replaying from the first commit")
    elif k < done:
        why = ("the first commit changed" if k < 0 else
               "replay again from window %d (requested: --restart)" % (k + 1) if forced is not None and k == forced else
               "window %d changed (history rewritten, or the settings or recording changed what it replays)" % (k + 1))
        rep["reset"] = reset_to(cfg, old, new, k, why)
    w0 = runner.Ctx(cfg).state.get("window", 0)
    rep["result"] = "ok"
    try:
        rc = runner.cmd_run(cfg, RunArgs)
        if rc == 3:
            rep["result"] = "paused"
    except SystemExit as e:
        rep["result"], rep["error"] = "stopped", str(e.code)
    except Exception as e:   # noqa: BLE001 - a job error becomes a finding, the lock is released by the caller
        rep["result"], rep["error"] = "error", "%s: %s" % (type(e).__name__, e)
        traceback.print_exc()
    w1 = runner.Ctx(cfg).state.get("window", 0)
    rep["windows"] = list(range(w0 + 1, w1 + 1))
    rep["replayed_to"] = w1
    if rep.get("error"):
        rep["findings"].append(finding("error", "replay_stopped", "the replay stopped in window %d: %s" % (w1 + 1, rep["error"])))
    rep["findings"] += ledger_findings(cfg, new, rep["windows"])
    rep["findings"] += recording_findings(cfg, new, rep["windows"])
    rep["findings"] += run_findings(cfg, rep["windows"])
    if rep["windows"] and cfg.get("live_structure", True) and rep["result"] == "ok" and w1 == len(new["windows"]) - 1:
        try:
            rep["structure"], more = structure_check(cfg, new, rep["windows"], head, lst)
            rep["findings"] += more
        except Exception as e:   # noqa: BLE001
            rep["findings"].append(finding("warn", "structure_check_failed", "%s: %s" % (type(e).__name__, e)))
            traceback.print_exc()
    if rep["result"] == "ok" and any(f["level"] in ("error", "warn") for f in rep["findings"]):
        rep["result"] = "issues"
    rep["seconds"] = round(time.time() - t0, 1)
    if rep["windows"] or rep.get("reset") or rep.get("error") or not os.path.exists(os.path.join(live_dir(cfg), "status.json")):
        write_report(cfg, rep)
    print("live %s %s: %s, windows %s, %d finding(s), %.0f s" % (cfg["game"], head[:8], rep["result"], rep["windows"] or "-",
                                                                 len(rep["findings"]), rep["seconds"]), flush=True)
    return rep


def cmd_live(cfg, a):
    if getattr(a, "log", None):
        os.makedirs(os.path.dirname(a.log), exist_ok=True)
        sys.stdout = sys.stderr = open(a.log, "a", encoding="utf-8", buffering=1)
    if not cfg.get("live") and not getattr(a, "force", False):
        raise SystemExit("%s: ReplayConfig.json has \"live\": false (--force runs it anyway)" % cfg["game"])
    os.environ["UGF_HEAVY_LOW"] = "1"   # every editor process yields to the game sessions' own jobs
    lock = Lock(cfg)
    if not lock.acquire():
        print("live %s: another job holds %s; it picks up the new commit" % (cfg["game"], lock.path), flush=True)
        return 0
    lst_path = os.path.join(live_dir(cfg), "state.json")
    lst = runner.jload(lst_path, {})
    if getattr(a, "restart", None) is not None:
        # replay again from window N+1 (the project goes back to window N's commit), e.g. after a tool fix
        lst["restart"] = int(a.restart)
    try:
        print("== %s live job (pid %d)" % (runner.now(), os.getpid()), flush=True)
        while True:
            # settings as committed now: a ReplayConfig.json change (asset_drops, run_patterns) made while this job
            # ran must reach the next pass, which then replays the windows it changes
            cfg = unity_replay.load_cfg(cfg["_source"])
            rep = catch_up(cfg, lst)
            lst.update({"head": rep["head"], "result": rep["result"], "time": rep["time"]})
            runner.jdump(lst_path, lst)
            if rep["result"] in ("paused", "stopped", "error") or head_of(cfg) == rep["head"]:
                break
    finally:
        lock.release()
    return 0


def cmd_truth(cfg, a):
    """The truth project at the settings' final commit, imported once (an editor open), so its dumps are quick."""
    sha = runner.git(cfg["repo"], "rev-parse", cfg["final"]).strip()
    made = sync_truth(cfg, sha)
    print("truth %s at %s (%s)" % (cfg["truth_dir"], sha[:8], "cloned" if made else "checked out"), flush=True)
    ctx = runner.Ctx(cfg)
    log = os.path.join(ctx.logs, "truth_import.log")
    code, secs = runner.heavy("%s replay truth import" % cfg["game"],
                              runner.editor_argv(ctx, cfg["truth_dir"], log, None), timeout=cfg.get("run_timeout_s") or None)
    print("truth import: exit %s (%.0f s) %s" % (code, secs, log), flush=True)
    return code or 0


def cmd_release(cfg, a):
    """Release: the live replay caught up (normal priority), truth at the final commit, full dumps, verify, package.
    The verdict is metadata: a FAIL is packaged like a PASS (READY), with its report saying why."""
    import package
    import verify
    lock = Lock(cfg)
    if not lock.acquire():
        raise SystemExit("a live job runs for %s (work/live/lock): run release when it is done" % cfg["game"])
    lst = runner.jload(os.path.join(live_dir(cfg), "state.json"), {})
    try:
        final = runner.git(cfg["repo"], "rev-parse", cfg["final"]).strip()
        rcfg = dict(cfg, live_ref=final, live_structure=False)
        rep = catch_up(rcfg, lst)
        if rep["result"] not in ("ok", "issues") or rep["replayed_to"] != rep["total_windows"]:
            raise SystemExit("release: the replay did not reach %s (%s): see %s" % (final[:8], rep["result"], live_dir(cfg)))
        rcfg = dict(cfg, final=final)
        sync_truth(rcfg, final)
        for which in ("truth", "replay"):
            if runner.cmd_dump(rcfg, type("A", (), {"which": which, "only": None})) != 0:
                raise SystemExit("release: the %s dump did not finish (work/logs/dump_%s.log)" % (which, which))
        v = verify.cmd_verify(rcfg, a)
        print("release: verification %s; packaging ReplayScripts/ with its report" % ("PASS" if v == 0 else "FAIL"))
        return package.cmd_package(rcfg, a)
    finally:
        lock.release()


def cmd_live_status(root):
    rows = []
    for g in sorted(glob.glob(os.path.join(root, "games", "*", ".git"))):
        repo = os.path.dirname(g)
        try:
            cfg = unity_replay.load_cfg(repo)
        except SystemExit:
            continue
        if not cfg.get("live"):
            continue
        st = runner.jload(os.path.join(live_dir(cfg), "status.json"), {}) or {}
        lock = runner.jload(os.path.join(live_dir(cfg), "lock"), None) if os.path.exists(os.path.join(live_dir(cfg), "lock")) else None
        try:
            head = head_of(cfg)
        except RuntimeError:
            head = "?"
        rows.append((cfg["game"], head[:8], (st.get("head") or "-")[:8], "%s/%s" % (st.get("replayed_to", "-"), st.get("total_windows", "-")),
                     st.get("result", "never run"), json.dumps(st.get("findings", {})),
                     "running" if lock and pid_alive(lock.get("pid")) else "idle", st.get("time", "")[:16]))
    print("%-16s %-9s %-9s %-8s %-9s %-26s %-8s %s" % ("game", "HEAD", "replayed", "windows", "result", "findings", "job", "time"))
    for r in rows:
        print("%-16s %-9s %-9s %-8s %-9s %-26s %-8s %s" % r)
    if not rows:
        print("(no live game under %s)" % os.path.join(root, "games"))
    return 0
