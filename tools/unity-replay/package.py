"""package: assemble the replay deliverable for the dataset packager (docs/unity-replay.md, "ReplayScripts").

Output: <out>/_replay/<game>/<final sha8>/   (<out>: env UGF_OUT, config "out", else <root>/deliverables)
  ReplayScripts/            the replay tooling (it runs outside the tool checkout), the game's settings, ledger,
                            initial-assets manifest, reconstructed step and code texts, verification
  verification.json         summary: windows, verdict, verify report
  READY                     written last, only when every window was replayed and verified (report.json with its
                            verdict; PASS or FAIL is metadata); the dataset packager takes ReplayScripts/ from here

Unscrubbed: the dataset packager copies ReplayScripts/ into the dataset, scrubs it like every other text file of the
delivery and maps its commit ids to the delivered history. --force assembles an incomplete copy without READY (for
checks only).
"""
import datetime
import hashlib
import json
import os
import shutil

import runner
import unity_replay

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = ["unity_replay.py", "runner.py", "ledger.py", "derive.py", "verify.py", "shellfx.py", "patchfx.py", "package.py", "live.py"]
EDITOR = list(runner.TOOL_FILES)


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def total_windows(led):
    """Windows to replay: the ledger's list starts with window 0, the first commit itself."""
    return (led.get("counts") or {}).get("windows", max(0, len(led.get("windows", [])) - 1))


def copytree(src, dst, skip_ext=()):
    n = 0
    for root, _dirs, files in os.walk(src):
        for fn in files:
            if fn.lower().endswith(skip_ext):
                continue
            s = os.path.join(root, fn)
            d = os.path.join(dst, os.path.relpath(s, src))
            os.makedirs(os.path.dirname(d), exist_ok=True)
            shutil.copy2(s, d)
            n += 1
    return n


def package_dir(cfg, led):
    return os.path.join(unity_replay.out_root(), "_replay", cfg["game"], led["final"][:8]).replace("/", os.sep)


def readme(cfg, led, state, parts, report):
    win_total = total_windows(led) if led else 0
    editors = sorted(set(os.path.basename(os.path.dirname(os.path.dirname(e))) for e in [state.get("editor") or ""] if e))
    lines = [
        "# ReplayScripts: creation replay of %s" % cfg["game"], "",
        "Replays how the game was built, from its git history, the builder's recorded actions and `workflow.jsonl`,",
        "in an isolated copy of the project, and checks the result against the final commit. The supplied project is",
        "not changed.", "",
        "## What is observed and what is derived", "",
        "- Observed: the commits (code, editor steps, settings, source art), the exact text of every step and code file",
        "  at the moment each step ran (rebuilt from the recorded writes and edits, `Blobs/`), the editor-step runs in",
        "  their original order with their workflow rows, the shell copies of content, and the store packs copied in",
        "  (`initial-assets.manifest.json`).",
        "- Verified: the replayed project against the final commit (`Verification/`: report, per-window checks, JSON",
        "  structure dumps of both projects).", "",
        "## How to replay", "",
        "Requirements: Windows, the Unity editor each commit's `ProjectSettings/ProjectVersion.txt` names%s, installed" % (
            " (here %s)" % ", ".join(editors) if editors else ""),
        "through Unity Hub with an activated licence, Python 3.10+, git with Git LFS, and the game repository with its",
        "LFS objects. Point `game.json` at the repository (`repo`, `work_root`; `{root}` is the folder in the",
        "environment variable `UGF_ROOT`). The ledger and the step and code texts it names are here: copy `ledger.json`",
        "to `<work_root>/work/ledger.json` and `Blobs/` to `<work_root>/work/blobs/` (`ledger` builds them again from a",
        "recording: `recording` names a folder that holds its `actions.jsonl`). Then:", "",
        "```",
        "python unity_replay.py prepare --game game.json   # isolated project at the first commit",
        "python unity_replay.py run     --game game.json   # every window headless; resumable",
        "python unity_replay.py dump    --game game.json --which replay",
        "python unity_replay.py dump    --game game.json --which truth   # the final commit in a project of its own",
        "python unity_replay.py verify  --game game.json   # final state vs the final commit",
        "```", "",
        "## Results", "",
        "- Windows replayed: %d of %d (first commit `%s`, final `%s`)." % (state.get("window", 0), win_total,
                                                                           (led or {}).get("first", "?")[:8], (led or {}).get("final", "?")[:8]),
    ]
    if report:
        v = report.get("verdict") or {}
        lines.append("- Verification (`Verification/report.md`): **%s**." % ("PASS" if v.get("pass") else "FAIL"))
        for c in v.get("criteria", []):
            lines.append("  - %s: %s (%s)" % (c["id"], "yes" if c["pass"] else "no", c.get("result", "")))
    missing = [k for k, ok in parts.items() if not ok]
    if missing:
        lines.append("- Not included yet: " + ", ".join(missing) + ".")
    if report:
        import verify
        lines += [""] + verify.render_deviations(report.get("deviations") or [])
    return "\n".join(lines) + "\n"


def cmd_package(cfg, a):
    ctx = runner.Ctx(cfg)
    led = ctx.ledger
    if not led:
        raise SystemExit("no ledger: run `unity_replay.py ledger` first")
    work = ctx.work
    final = led["final"]
    out = package_dir(cfg, led)
    rs = os.path.join(out, "ReplayScripts")
    report = runner.jload(os.path.join(work, "Verification", "report.json"), None)
    src = {
        "windows complete": ctx.state.get("window", 0) >= total_windows(led) > 0,
        "Verification/report.json": bool(report and report.get("verdict") and report.get("final_commit") == final),
    }
    complete = all(src.values())
    for k, v in src.items():
        print("  %-36s %s" % (k, "ok" if v else "MISSING"))
    if not complete and not getattr(a, "force", False):
        raise SystemExit("incomplete: nothing written (--force assembles a copy without READY, for checks)")
    if os.path.isdir(out):
        shutil.rmtree(out)
    os.makedirs(os.path.join(rs, "editor"))
    for f in TOOLS:
        shutil.copy2(os.path.join(HERE, f), os.path.join(rs, f))
    for f in EDITOR:
        shutil.copy2(os.path.join(HERE, "editor", f), os.path.join(rs, "editor", f))
    unity_replay.write_json(os.path.join(rs, "game.json"), {k: v for k, v in cfg["_raw"].items()})   # {root} placeholders
    for name in ("ledger.json", "initial-assets.manifest.json"):
        if os.path.isfile(os.path.join(work, name)):
            shutil.copy2(os.path.join(work, name), os.path.join(rs, name))
    nblobs = copytree(os.path.join(work, "blobs"), os.path.join(rs, "Blobs")) if os.path.isdir(os.path.join(work, "blobs")) else 0
    vdir = os.path.join(rs, "Verification")
    os.makedirs(vdir)
    for name in ("report.md", "report.json"):
        p = os.path.join(work, "Verification", name)
        if os.path.isfile(p):
            shutil.copy2(p, os.path.join(vdir, name))
    if os.path.isfile(os.path.join(work, "windows.jsonl")):
        shutil.copy2(os.path.join(work, "windows.jsonl"), os.path.join(vdir, "windows.jsonl"))
    for d in ("dump-replay", "dump-truth"):
        if os.path.isdir(os.path.join(work, d)):
            copytree(os.path.join(work, d), os.path.join(vdir, d))
    with open(os.path.join(rs, "README.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write(readme(cfg, led, ctx.state, src, report))
    # the build machine's per-session folders and ids in the recorded data become neutral names (unity_replay.
    # SESSION_PATH_RULES); the settings templates still match them, so a replay from this folder works the same
    neutral = {}
    sids = unity_replay.recording_session_ids(cfg)
    for dp, _, fns in os.walk(rs):
        for fn in fns:
            if not fn.lower().endswith((".json", ".jsonl", ".md", ".py", ".txt", ".cs", ".ps1")) and os.path.basename(dp) != "Blobs":
                continue
            fp = os.path.join(dp, fn)
            with open(fp, "rb") as f:
                b = f.read()
            if b"\0" in b[:8000]:
                continue
            t = b.decode("utf-8", "surrogateescape")
            t2, c = unity_replay.neutral_session_paths(t, sids)
            if c:
                with open(fp, "wb") as f:
                    f.write(t2.encode("utf-8", "surrogateescape"))
                for k, v in c.items():
                    neutral[k] = neutral.get(k, 0) + v
    summary = {
        "schema": "unity-replay.package/v1", "game": cfg["game"], "first_commit": led.get("first"), "final_commit": final,
        "created": datetime.datetime.now().astimezone().isoformat(timespec="seconds"), "complete": complete, "parts": src,
        "windows": {"done": ctx.state.get("window", 0), "total": total_windows(led)}, "blobs": nblobs,
        "verdict": (report or {}).get("verdict"), "report": "ReplayScripts/Verification/report.md",
        "session_paths_neutralised": neutral,
    }
    runner.jdump(os.path.join(out, "verification.json"), summary)
    if complete:
        with open(os.path.join(out, "READY"), "w", encoding="utf-8", newline="\n") as f:
            f.write(summary["created"] + "\n")
    print("%s %s -> %s (verdict %s)" % ("READY" if complete else "INCOMPLETE (no READY)", cfg["game"], out,
                                       "PASS" if ((report or {}).get("verdict") or {}).get("pass") else "FAIL" if report else "none"))
    return 0 if complete else 1


def cmd_clean(cfg, a):
    """Free the disk a finished replay holds: the replay project, the truth project and the work files the package
    copied (dumps, blobs, rows, logs). Only after `package` wrote READY for the settings' final commit; lists what it
    would remove unless --yes is given. The ledger, state and verification report stay in work/."""
    led = runner.Ctx(cfg).ledger
    out = package_dir(cfg, led)
    if not os.path.exists(os.path.join(out, "READY")):
        raise SystemExit("no READY replay package at %s: nothing removed" % out)
    work = cfg["work_dir"]
    targets = [cfg["project_dir"], cfg["truth_dir"]] + [os.path.join(work, d) for d in
                                                         ("blobs", "rows", "logs", "scenedumps", "dump-replay", "dump-truth", "world")]
    targets = [t for t in targets if os.path.exists(t)]
    total = 0
    for t in targets:
        size = sum(os.path.getsize(os.path.join(r, f)) for r, _, fs in os.walk(t) for f in fs)
        total += size
        print("  %-8s %7.2f GB  %s" % ("remove" if a.yes else "would rm", size / 1e9, t))
        if a.yes:
            def writable(fn, p, _exc):   # git objects are read-only on Windows
                os.chmod(p, 0o666)
                fn(p)
            shutil.rmtree(t, onerror=writable)
    print("%s %.2f GB for %s" % ("freed" if a.yes else "would free (add --yes)", total / 1e9, cfg["game"]))
