"""Unity creation replay: rebuild a game from its first commit by re-running what its builder ran.

  python unity_replay.py ledger  --game <game> [-v]                 windows, runs, script texts -> work/ledger.json
  python unity_replay.py prepare --game ...                         isolated project at the first commit
  python unity_replay.py run     --game ... [--until <window>]      execute the plan (resumable; work/STOP pauses it)
  python unity_replay.py dump    --game ... --which replay|truth    structure dump (assets, scenes) through the editor
  python unity_replay.py verify  --game ...                         final state vs the final commit
  python unity_replay.py report  --game ...                         refresh report.md/json deviations (no editor)
  python unity_replay.py derive  --game ...                         world ops from the per-run scene exports
  python unity_replay.py world   --game ... [--only <ops.jsonl>]    rebuild the scenes from the world ops, compare
  python unity_replay.py status  --game ...
  python unity_replay.py package --game ... [--force]               <out>/_replay/<game>/<sha8>/ (READY when verified)
  python unity_replay.py clean   --game ... [--yes]                 free the disk of a packaged replay
  python unity_replay.py live    --game ... [--log <file>] [--restart N]   per-commit replay of a live game
  python unity_replay.py live-status                                every live game: HEAD, replayed windows, result
  python unity_replay.py truth   --game ...                         truth project at the final commit, imported
  python unity_replay.py release --game ... [--force]               catch up, truth, dumps, verify, package

See docs/unity-replay.md. Every editor process runs through <root>/tools/unity-heavy.ps1 when the machine has it
(machine root: machine/lib/ugfroot.py), headless. --game is a game slug (<root>/games/<slug>), a game repo folder, or
a settings file (the repo's ReplayConfig.json, or a delivered ReplayScripts/game.json). A game without a
ReplayConfig.json replays with the defaults (DEFAULTS below, derived from the repo). Settings may use {root} (the
machine root), {home} (the user profile) and {editor} (the editor each commit's ProjectSettings/ProjectVersion.txt
names).
"""
import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "..", "machine", "lib"))

SETTINGS_FILE = "ReplayConfig.json"
HUB_EDITORS = "C:/Program Files/Unity/Hub/Editor"

# The settings a game gets when its repo has no ReplayConfig.json (the template's file holds the same values).
DEFAULTS = {
    "live": True,
    "final": "HEAD",
    "editor": "{editor}",
    # headless: a general slot of the limiter, never a GPU slot (-quit is added per run unless the step ran -NoQuit)
    "editor_args": ["-batchmode", "-nographics"],
    "reason_env": "UNITY_RUN_REASON",
    "steps_dir": "Assets/Editor/Steps",
    # steps that only look (class names): listed, not replayed
    "readonly_patterns": ["Inspect*", "Measure*", "Check*", "Analyze*", "Scan*", "*Probe*"],
    "not_readonly": [],
    "asset_roots": ["Assets"],
    "scene_roots": ["Assets"],
    "run_patterns": [],
    "asset_drops": [],
    "shell_replay": [],
    # the .meta of a new file the builder wrote (code, source art): "commit" = the commit's whole .meta; "guid" = only
    # its GUID from the commit (Unity then imports it with its default settings and keeps the .meta as written, so
    # every one whose .meta holds settings is taken from the commit at the window's end, and listed)
    "input_meta": "commit",
    # an editor run that lasts longer is stopped and counted as failed (a step started without -quit that never exits)
    "run_timeout_s": 3600,
    # true: after each run that changed a scene, export it (an extra headless editor run) for `derive` and `world`
    "scene_exports": False,
}


def _ugfroot():
    try:
        import ugfroot
        return ugfroot
    except ImportError:   # a delivered ReplayScripts/ outside the tool checkout: env UGF_ROOT or ~/UnityWork
        return None


def machine_root():
    m = _ugfroot()
    r = m.root() if m else (os.environ.get("UGF_ROOT") or os.path.join(os.path.expanduser("~"), "UnityWork"))
    return r.replace("\\", "/")


def out_root():
    """Where packages go: env UGF_OUT, config "out", else <root>/deliverables (machine/lib/ugfroot.py out())."""
    m = _ugfroot()
    if m:
        return m.out().replace("\\", "/")
    return (os.environ.get("UGF_OUT") or machine_root() + "/deliverables").replace("\\", "/")


def check_free(path, what):
    """Stop before a disk-heavy step when the drive is below the free-space floor (env UGF_MIN_FREE_GB, default 50)."""
    m = _ugfroot()
    if m:
        return m.check_free(path, what)
    import shutil
    p = os.path.abspath(path)
    while not os.path.exists(p) and os.path.dirname(p) != p:
        p = os.path.dirname(p)
    free, floor = shutil.disk_usage(p).free / 2 ** 30, float(os.environ.get("UGF_MIN_FREE_GB") or 50)
    if free < floor:
        sys.exit("%s: only %.1f GB free (floor %.0f GB, UGF_MIN_FREE_GB)" % (what, free, floor))
    return free


def project_version(project):
    """m_EditorVersion of <project>/ProjectSettings/ProjectVersion.txt ('' without one)."""
    pv = os.path.join(project or "", "ProjectSettings", "ProjectVersion.txt")
    if not project or not os.path.isfile(pv):
        return ""
    with open(pv, encoding="utf-8-sig", errors="replace") as f:
        for line in f:
            m = re.match(r"\s*m_EditorVersion:\s*(\S+)", line)
            if m:
                return m.group(1)
    return ""


def editor_for_version(version):
    """Unity.exe of an exact version: the machine config's unity_editors / unity_hub_editors (ugfroot), else the Hub's
    default folder. '' when that version is not installed."""
    m = _ugfroot()
    if m:
        return m.unity_for_version(version)
    p = "%s/%s/Editor/Unity.exe" % (HUB_EDITORS, version)
    return p if version and os.path.isfile(p) else ""


def machine_editor(project):
    """The editor a project folder names (its ProjectVersion.txt), as it stands on disk; exits naming the version to
    install when it is missing."""
    v = project_version(project)
    exe = editor_for_version(v)
    if not exe:
        sys.exit("Unity %s (named by %s/ProjectSettings/ProjectVersion.txt) is not installed: install it through Unity "
                 "Hub (Installs > Install Editor, or the archive for an older patch)" % (v or "?", project))
    return exe.replace("\\", "/")


# {pipeline}: this checkout's tools/unity-pipeline folder, for run_patterns scripts that are pipeline tools: a game's
# settings then name no tool checkout, and the runner takes the tool's version at the run time from its history.
PIPELINE = os.path.join(os.path.dirname(HERE), "unity-pipeline").replace("\\", "/")

# Settings keys that describe what the RECORDING says (commands and paths of the machine the game was built on), not
# places on this machine: they stay templates and are matched with recorded_regex().
RECORDED_KEYS = ("match", "recorded")


def expand(v, root):
    """{root}, {home}, {pipeline} expanded; {editor} stays for the runner (it follows each commit's editor)."""
    if isinstance(v, str):
        v = v.replace("{pipeline}", PIPELINE)
        return v.replace("{root}", root).replace("{home}", os.path.expanduser("~").replace("\\", "/"))
    if isinstance(v, list):
        return [expand(x, root) for x in v]
    if isinstance(v, dict):
        return {k: (x if k in RECORDED_KEYS else expand(x, root)) for k, x in v.items()}
    return v


def recorded_regex(template):
    """A settings template for text in the recording, as a regex that matches it on any machine: {home} = any user
    profile (C:/Users/<name>, C:\\Users\\<name>, /c/Users/<name>), {root} = any path prefix, "/" = either slash;
    everything else literal."""
    out, i = [], 0
    while i < len(template):
        if template.startswith("{home}", i):
            out.append(r"(?:[A-Za-z]:|/[A-Za-z])[\\/]+Users[\\/]+[^\\/\s'\"]+")
            i += 6
        elif template.startswith("{root}", i):
            out.append(r"(?:[A-Za-z]:|/[A-Za-z])(?:[\\/]+[^\\/\s'\"]+)*?")
            i += 6
        elif template[i] == "/":
            out.append(r"[\\/]")
            i += 1
        else:
            out.append(re.escape(template[i]))
            i += 1
    return re.compile("".join(out), re.I)


def recorded_path_regex(template):
    """recorded_regex for a path: also * = one path component, /**/ = any number of them, and / = any separator
    (/, \\, or an escaped \\\\)."""
    sep = r"(?:/|\\{1,2})+"
    out, i = [], 0
    while i < len(template):
        if template.startswith("{home}", i):
            out.append(r"(?:[A-Za-z]:|/[A-Za-z])%sUsers%s[^\\/\s'\"]+" % (sep, sep))
            i += 6
        elif template.startswith("{root}", i):
            out.append(r"(?:[A-Za-z]:|/[A-Za-z])(?:%s[^\\/\s'\"]+)*?" % sep)
            i += 6
        elif template.startswith("/**/", i):
            out.append(r"(?:%s[^\\/\s'\"]+)*?%s" % (sep, sep))
            i += 4
        elif template[i] == "/":
            out.append(sep)
            i += 1
        elif template[i] == "*":
            out.append(r"[^\\/\s'\"]*")
            i += 1
        else:
            out.append(re.escape(template[i]))
            i += 1
    return re.compile("".join(out), re.I)


def has_recorded(match, text):
    """Where the settings' match string occurs in a recorded command: a plain substring, or with {home}/{root} any
    machine's path. Returns the start index or -1."""
    if "{home}" not in match and "{root}" not in match:
        return text.find(match)
    m = recorded_regex(match).search(text)
    return m.start() if m else -1


# Packaged copies of recorded data (ReplayScripts: ledger, step texts, settings, reports) name the build machine's
# per-session folders; those names are noise for a buyer and identify the session. They become neutral names that the
# settings templates ({home}/AppData/Local/Temp/**/...) still match.
_UUID = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
SESSION_PATH_RULES = [
    # Temp/<tool>/<project-dir>/<session uuid>[/scratch-pad] -> Temp/session[/scratch]
    ("session_temp", re.compile(r"(?i)(?P<head>AppData(?P<s>[\\/]{1,2})Local(?P=s)Temp(?P=s))[^\\/\s'\"]+(?P=s)"
                                r"[^\\/\s'\"]+(?P=s)(?:%s|[0-9a-f]{8}(?:-[0-9a-f]{0,12}){0,4}(?=[\"']|\\\"|$))"
                                r"(?P<pad>(?P=s)scratc[h]pad(?![\w-]))?" % _UUID),
     lambda m: m.group("head") + "session" + ((m.group("s") + "scratch") if m.group("pad") else "")),
    ("session_id", re.compile(r"\blocal[_]%s\b" % _UUID), lambda m: "session"),
]


def neutral_session_paths(text, session_ids=()):
    """(new text, {rule: count}) with the build machine's session folders and ids replaced, and the recording's own
    session ids wherever they still stand alone. Other uuids (asset guids are 32 hex, not uuids) are content and stay."""
    counts = {}
    for rid, rx, f in SESSION_PATH_RULES:
        text, n = rx.subn(f, text)
        if n:
            counts[rid] = n
    if session_ids:
        rx = re.compile(r"(?i)\b(?:%s)\b" % "|".join(re.escape(s) for s in session_ids))
        text, n = rx.subn("session", text)
        if n:
            counts["session_uuid"] = n
    return text, counts


def recording_session_ids(cfg):
    """The session ids in a game's recording (actions.jsonl session_id): the ids neutral_session_paths replaces."""
    ids = set()
    p = os.path.join(cfg.get("recording", ""), "actions.jsonl")
    if os.path.isfile(p):
        with open(p, encoding="utf-8", errors="replace") as f:
            for line in f:
                m = re.search(r'"session_id"\s*:\s*"([^"]+)"', line)
                if m:
                    ids.add(m.group(1).lower())
    return sorted(i for i in ids if re.fullmatch(_UUID, i))


def under_root(path, root):
    """path written with {root} when it lies under the machine root, so settings name no machine path."""
    p, r = path.replace("\\", "/").rstrip("/"), root.replace("\\", "/").rstrip("/")
    return "{root}" + p[len(r):] if p.lower().startswith(r.lower() + "/") else p


def default_settings(repo):
    """The settings of a game repo that has no ReplayConfig.json: DEFAULTS, the slug from the folder name, the
    recording and work folders under the machine root."""
    root = machine_root()
    slug = os.path.basename(os.path.abspath(repo).rstrip("\\/"))
    raw = {"game": slug, "repo": under_root(os.path.abspath(repo), root), "recording": "{root}/.recording/" + slug,
           "work_root": "{root}/unity-replay/" + slug}
    raw.update({k: v for k, v in DEFAULTS.items() if k not in raw})
    return raw


def resolve_cfg(game):
    """(settings file or None, repo folder or None) for --game: a settings file; a repo folder (its ReplayConfig.json,
    else defaults); a slug under <root>/games (the same)."""
    for cand in (game, os.path.join(HERE, game)):
        if os.path.isfile(cand):
            return os.path.abspath(cand), None
    repo = game if os.path.isdir(os.path.join(game, ".git")) else os.path.join(machine_root(), "games", game)
    if os.path.isdir(os.path.join(repo, ".git")):
        p = os.path.join(repo, SETTINGS_FILE)
        return (os.path.abspath(p), None) if os.path.isfile(p) else (None, os.path.abspath(repo))
    raise SystemExit("no replay settings for %r: expected a game repo %s, a repo folder or a settings file" % (game, repo))


def load_cfg(game):
    path, repo = resolve_cfg(game)
    if path:
        with open(path, encoding="utf-8-sig") as f:
            raw = json.load(f)
        raw = dict({k: v for k, v in DEFAULTS.items()}, **raw)   # a key the file leaves out takes its default
    else:
        raw = default_settings(repo)
    root = machine_root()
    if "repo" not in raw or "game" not in raw:
        here = os.path.dirname(path)
        raw.setdefault("game", os.path.basename(here))
        raw.setdefault("repo", under_root(here, root))
    raw.setdefault("recording", "{root}/.recording/" + raw["game"])
    raw.setdefault("work_root", "{root}/unity-replay/" + raw["game"])
    cfg = expand(raw, root)
    cfg["_raw"] = raw
    cfg["_editor_per_commit"] = "{editor}" in str(raw.get("editor", ""))
    cfg["root"] = root
    cfg["_path"] = path
    cfg["_source"] = path or repo
    cfg["_defaults"] = path is None
    w = cfg["work_root"]
    # the replay project and the truth clone carry the game folder's name: Unity names a new project's ProjectSettings
    # values after its folder (metroPackageName, metroApplicationDescription)
    name = os.path.basename(os.path.abspath(cfg["repo"]).rstrip("\\/"))
    cfg.setdefault("project_dir", os.path.join(w, name))
    cfg.setdefault("truth_dir", os.path.join(w, "truth", name))
    cfg.setdefault("work_dir", os.path.join(w, "work"))
    os.makedirs(cfg["work_dir"], exist_ok=True)
    return cfg


def write_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
        f.write("\n")


def save_ledger(cfg, led, blobs):
    bd = os.path.join(cfg["work_dir"], "blobs")
    os.makedirs(bd, exist_ok=True)
    for h, b in blobs.items():
        p = os.path.join(bd, h)
        if not os.path.exists(p):
            with open(p, "wb") as f:
                f.write(b)
    write_json(os.path.join(cfg["work_dir"], "ledger.json"), led)


def cmd_ledger(cfg, a):
    import ledger
    led, blobs = ledger.build(cfg)
    save_ledger(cfg, led, blobs)
    print(json.dumps(led["counts"], indent=1))
    if a.verbose:
        for w in led["windows"][1:]:
            print("== %02d %s %s %s" % (w["index"], w["sha"][:7], w["time"][11:19], w["subject"][:70]))
            print("   inputs %d, content %d, events %s, reconstruction %d/%d" % (
                len(w["inputs"]), len(w["content"]), w["events"],
                sum(1 for c in w["reconstruction"] if c["match"]), len(w["reconstruction"])))
            for d in w["drops"]:
                print("   drop", d["id"], d["time"][11:19])
            for s in w["shell"]:
                print("   shell", s["argv"], s["time"][11:19], "(auto)" if s.get("auto") else "")
            for r in w["runs"]:
                print("   %s %s %-44s %-18s ro=%d ec=%s rows=%d unknown=%s" % (
                    r["id"], r["start"][11:19], r["method"][-44:], r["script_version"], r["readonly"], r["exit_code"],
                    len(r["rows"]), ",".join(os.path.basename(u) for u in r["unknown"])))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command")
    ap.add_argument("--game", default=None)
    ap.add_argument("--log", default=None)
    ap.add_argument("--restart", type=int, default=None)   # live: replay again from window N+1 (project back to window N)
    ap.add_argument("--verbose", "-v", action="store_true")
    ap.add_argument("--until", type=int, default=None)
    ap.add_argument("--which", default="replay")
    ap.add_argument("--only", default=None)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--yes", action="store_true")
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    if a.command == "live-status":
        import live
        return live.cmd_live_status(machine_root())
    if not a.game:
        ap.error("--game is required for " + a.command)
    cfg = load_cfg(a.game)
    fn = globals().get("cmd_" + a.command.replace("-", "_"))
    if fn is None:
        import importlib
        for mod in ("runner", "verify", "derive", "package", "live"):
            fn = getattr(importlib.import_module(mod), "cmd_" + a.command.replace("-", "_"), None)
            if fn:
                break
    if fn is None:
        ap.error("unknown command " + a.command)
    # disk-heavy steps refuse to start on a nearly full drive (a disk that filled mid-run corrupts a replay)
    if a.command in ("prepare", "run", "dump", "live", "truth", "release", "world"):
        check_free(cfg["work_root"], "unity_replay " + a.command)
    elif a.command == "package":
        check_free(out_root(), "unity_replay package")
    return fn(cfg, a)


if __name__ == "__main__":
    sys.exit(main() or 0)
