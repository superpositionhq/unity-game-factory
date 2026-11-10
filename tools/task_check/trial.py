"""A task tried with the contractor's own coding agent, on their own computer (docs/task-try.md).

For one task and each run:
1. The game at the task's start (seed.commit) is copied into a workspace outside the machine root and the game repo,
   as the agent gets it in the cloud: every file of that commit, without Tasks/, History/ or Dataset/, in a fresh git
   repository with one commit and no history (its Git LFS objects hardlinked from the game repo's store, the files
   themselves copies, since the agent edits them).
2. The contractor's harness (Claude Code or Codex, their own subscription and login) runs headless in the workspace
   with the brief as its prompt, within the task's limits (turns where the harness has a flag, minutes always), with
   the machine's recording hooks off (UGF_NO_RECORDING, and GF_NO_RECORDING for the Unreal factory's hooks). Its
   transcript is kept.
3. The workspace is graded as a solution: its build outputs and Library removed, TaskProbe added, built fresh,
   played, every check but judges, trace probes and packaging run against the thresholds the start and the reference
   give (both built and measured once for all runs, before the first agent starts, and deleted then: the reference copy
   is the answer, and it would lie two folders above the agent's).

The result says, per run, whether the agent solved the task (every required check passed), which milestones it
reached, its time, turns and cost when the harness reports them, and whether its transcript names the game repo or the
tasks worktree (it could have read the answer there). It is advice: the cloud's grade decides."""

import json
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from . import check, seeds, tasks, unity, verdict

FORMAT = "task-try/1"
LONG_MINUTES = 25  # a guide for a long task, not a requirement: what counts is that the agent can't solve it easily (owner, 2026-11-09)
LIMITS = {"max_turns": 200, "max_minutes": 240}  # the schema's defaults (game-task.schema.json Limits)
# Build outputs removed before a run is graded: the grade builds it fresh. Library too: besides Unity's import cache it
# holds the agent's editor state (build profiles with their own defines and scenes, compiled scripts, build caches),
# which a game's files never carry; the grade imports everything again, as the task check does for each copy.
BUILT = ("Library", "Temp", "Obj", "Logs", "Build", "Builds")
NO_RECORDING = ("UGF_NO_RECORDING", "GF_NO_RECORDING")  # the machines' record-action hooks record nothing when set
# Nothing points the agent at a machine root, its config (which names the root), its deliverables (every game's history)
# or the organisation that holds the game repos.
NO_ROOT = ("UGF_ROOT", "UGF_CONFIG", "UGF_OUT", "UGF_ORG", "GF_ROOT", "UNITY_RUN_REASON", "UE_RUN_REASON")
HOME = ("~", "$home", "${home}", "$env:userprofile", "%userprofile%")  # the home folder as the shells write it


def brief(task, editor):
    """The prompt: the task's instruction, where QA plays (the scene and its arguments, as the cloud harness says it),
    that the game is a Unity 6000.3 project, and where the Unity editor is, since a local harness has no build or play
    tools of ours."""
    text = task["instruction"].rstrip()
    scene, args = task.get("play_scene"), list(task.get("play_args") or [])
    if scene:
        text += f"\n\nQA plays the game from the scene `{scene}`" + (
            f", with the arguments `{' '.join(args)}`." if args else ".")
    elif args:
        text += f"\n\nQA plays the game with the arguments `{' '.join(args)}`."
    text += (f"\n\nThe game is the Unity 6000.3 project in the current folder. The Unity editor is `{editor}`. Build, "
             "run and test it yourself; leave your work in this folder.")
    return text


def agent_argv(agent, exe, limits, settings, model=None, extra=()):
    """The headless command line of `agent` ("claude" or "codex"); the prompt comes on stdin. `settings`: a Claude Code
    settings file that turns hooks off (a file, since a .cmd shim mangles JSON on its command line)."""
    if agent == "claude":
        argv = [exe, "-p", "--output-format", "stream-json", "--verbose", "--max-turns", str(limits["max_turns"]),
                "--permission-mode", "bypassPermissions", "--settings", str(settings)]
    elif agent == "codex":
        argv = [exe, "exec", "--json", "-s", "danger-full-access", "--skip-git-repo-check",
                "--disable", "apps", "--disable", "plugins"]
    else:
        raise ValueError(f"no agent {agent!r} (claude or codex)")
    if model:
        argv += ["--model", model] if agent == "claude" else ["-m", model]
    argv += list(extra)
    return argv + (["-"] if agent == "codex" else [])


def limits_of(task):
    return {**LIMITS, **(task.get("limits") or {})}


def workspace(repo, sha, dest):
    """The agent's folder: the game at `sha` (copies), a fresh git repo with one commit, its LFS objects hardlinked
    from the repo's store so committing them costs no disk. {"files", "copied"}."""
    made = seeds.materialize(repo, sha, dest, link=False)
    git = lambda *a: subprocess.run(["git", "-C", str(dest), *a], capture_output=True, text=True)
    git("init", "-q", "-b", "main")
    store = Path(dest) / ".git" / "lfs" / "objects"
    for oid, stored in made["objects"].items():
        target = store / oid[:2] / oid[2:4] / oid
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            seeds.place(stored, target, True)
    git("add", "-A")
    done = git("-c", "user.name=dev", "-c", "user.email=dev@localhost", "commit", "-q", "-m", "start")
    if done.returncode != 0:
        raise RuntimeError(f"couldn't commit the workspace: {done.stderr.strip()[:300]}")
    return {"files": made["files"], "copied": made["copied"]}


def clean_codex_home(folder, user_home=None):
    """A Codex home holding only the login and a config that turns off every skill installed for this user, so a try
    runs without the machine's skills, memories, history and settings. The login is a copy: put_login_back returns it
    (Codex may rotate it) and removes the copy. The folder must lie outside the evidence. Its path."""
    home = Path(user_home or os.path.expanduser("~"))
    real = Path(os.environ.get("CODEX_HOME") or home / ".codex")
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    shutil.copy2(real / "auth.json", folder / "auth.json")
    rows = []
    for skills in (home / ".agents" / "skills", real / "skills"):
        for found in sorted(skills.glob("*/SKILL.md")) if skills.is_dir() else []:
            rows.append(f"[[skills.config]]\npath = '{os.path.realpath(found)}'\nenabled = false\n")
    (folder / "config.toml").write_text("\n".join(rows), encoding="utf-8")
    return folder


def put_login_back(folder, user_home=None):
    """After a try: a login Codex refreshed goes back to the real home, and the copy goes. Never a copy Codex was
    still writing when it was stopped (its time limit, Ctrl+C): that would leave the user logged out."""
    home = Path(user_home or os.path.expanduser("~"))
    real = Path(os.environ.get("CODEX_HOME") or home / ".codex") / "auth.json"
    copy = Path(folder) / "auth.json"
    if copy.exists():
        data = copy.read_bytes()
        try:
            whole = isinstance(json.loads(data), dict)
        except ValueError:
            whole = False
        if whole and data != real.read_bytes():
            shutil.copy2(copy, real)
        copy.unlink()


def keep_codex_sessions(folder, dest):
    """Copy the temporary home's session files to the evidence: they hold the account's usage windows, which the
    transcript doesn't. Never the login, which isn't in that folder."""
    sessions = Path(folder) / "sessions"
    if sessions.is_dir():
        shutil.copytree(sessions, dest, dirs_exist_ok=True)


def run_agent(argv, cwd, prompt, transcript, minutes, clock=time.monotonic, env_extra=None):
    """Run the harness in `cwd` with `prompt` on stdin, its output to `transcript`; killed with its children after
    `minutes`, and when the try is stopped (Ctrl+C reaches only the try: the harness has a process group of its own).
    {"exit_code", "seconds", "timed_out"}."""
    env = dict(os.environ, **{name: "1" for name in NO_RECORDING})
    for name in NO_ROOT:
        env.pop(name, None)
    env.update(env_extra or {})
    started = clock()
    # The prompt comes from a file, not a pipe: writing a long one to a harness that doesn't read it would block past
    # the time limit, or fail when the harness stops first (an option it doesn't know); its transcript says why.
    with open(transcript, "wb") as out, tempfile.TemporaryFile() as stdin:
        stdin.write(prompt.encode("utf-8"))
        stdin.seek(0)
        proc = subprocess.Popen(argv, cwd=str(cwd), stdin=stdin, stdout=out, stderr=subprocess.STDOUT,
                                env=env, creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))
        try:
            proc.wait(timeout=minutes * 60)
            timed_out = False
        except subprocess.TimeoutExpired:
            unity._kill_tree(proc.pid)
            proc.wait()
            timed_out = True
        except BaseException:  # the try stopped: a harness left running would work on unattended
            unity._kill_tree(proc.pid)
            proc.wait()
            raise
    return {"exit_code": None if timed_out else proc.returncode, "seconds": round(clock() - started, 1),
            "timed_out": timed_out}


def kill_left_behind(folder):
    """Stop whatever the agent left running in its workspace (an editor it opened locks the project, a player holds its
    build, and the grade's build and the cleanup then fail). Finds processes by the workspace path in their command
    line. Their pids. Windows only: elsewhere nothing is stopped."""
    if os.name != "nt":
        return []
    # The path as the try made it (and gave it to the agent), never through a link the agent made there: that would
    # stop processes of the folder the link points at.
    needle = os.path.abspath(folder).lower()
    script = ("Get-CimInstance Win32_Process | Where-Object { $_.CommandLine } | ForEach-Object "
              "{ \"$($_.ProcessId)`t$($_.CommandLine)\" }")
    out = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script], capture_output=True,
                         text=True, encoding="utf-8", errors="replace", check=False).stdout
    pids = []
    for line in out.splitlines():
        pid, _, command = line.partition("	")
        command = command.lower().replace("/", "\\")
        if pid.isdigit() and needle in command and int(pid) != os.getpid() and "get-ciminstance" not in command:
            pids.append(int(pid))
    for pid in pids:
        unity._kill_tree(pid)
    return pids


def usage(agent, transcript):
    """{"turns", "usd"} as the harness reports them in its transcript (None when it doesn't)."""
    turns = usd = None
    try:
        lines = Path(transcript).read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return {"turns": None, "usd": None}
    for line in lines:
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if not isinstance(event, dict):
            continue
        if agent == "claude" and event.get("type") == "result":
            turns, usd = event.get("num_turns", turns), event.get("total_cost_usd", usd)
        elif agent == "codex" and event.get("type") == "turn.completed":
            turns = (turns or 0) + 1
    return {"turns": turns, "usd": usd}


def peeked(transcript, places):
    """The `places` (the game repo, the tasks worktree) the transcript names: the agent could have read the answer. A
    place counts with either slash, as Git Bash writes it (/c/..., Claude Code's shell on Windows) and from the home
    folder (~/..., $HOME/...)."""
    try:
        text = Path(transcript).read_text(encoding="utf-8", errors="replace").lower().replace("\\\\", "\\")
    except OSError:
        return []
    home = os.path.expanduser("~").lower().rstrip("\\/")
    found = []
    for place in places:
        path = str(place).lower()
        forms = {path}
        if path[1:3] in (":\\", ":/"):
            forms.add("/" + path[0] + path[2:])
        if path.startswith((home + "\\", home + "/")):
            forms.update(name + path[len(home):] for name in HOME)
        forms |= {f.replace("\\", "/") for f in forms}
        if any(f and f in text for f in forms):
            found.append(str(place))
    return found


def outside(path, folders):
    """Whether `path` lies outside every one of `folders`."""
    real = os.path.realpath(path).lower()
    for f in folders:
        root = os.path.realpath(f).lower().rstrip("\\/")
        if real == root or real.startswith(root + os.sep) or real.startswith(root + "/"):
            return False
    return True


def score(task, grade):
    """What a run reached: solved (every required check passed), its score (the weighted share of checks passed, as the
    cloud scores it, judges left out since a try doesn't run them), required checks passed, milestones reached."""
    rows = grade["checks"]
    weighed = [r for r in rows if r.get("kind") not in verdict.JUDGES]
    total = sum(r.get("weight", 1) for r in weighed)
    earned = sum(r.get("weight", 1) for r in weighed if r["passed"])
    required = [r for r in rows if r["required"]]
    groups = {}
    for r in required:
        groups.setdefault(r["group"], []).append(r["passed"])
    return {"solved": all(r["passed"] for r in required), "score": round(earned / total, 3) if total else 0.0,
            "required_passed": sum(r["passed"] for r in required),
            "required": len(required), "milestones": {g: all(v) for g, v in groups.items()}}


def clear(folder, names):
    """The folders `names` of the agent's `folder` deleted. One the agent made a link (a symlink or a junction) goes as
    a link: never what it points at, and never left for the grade's Unity to write through."""
    for name in names:
        path = Path(folder) / name
        if os.path.islink(path) or os.path.isjunction(path):
            os.unlink(path)
        elif path.is_dir():
            seeds.remove(path)


def discard(folder, log):
    """`folder` deleted. A file something still holds (a process the try couldn't find, the antivirus) is reported, not
    raised: the try's result matters more than its scratch folder."""
    try:
        seeds.remove(folder)
    except OSError as exc:
        log(f"  couldn't delete {folder} ({exc}): delete it by hand")


def side(name, folder, task, direct, timeout, build_timeout, evidence, log):
    seeds.add_probe(folder)
    machine = unity.Machine.for_project(folder, direct)
    return check.Side(name, unity.Project(folder, machine, f"{task['name']} {name}"), task, timeout, build_timeout,
                      evidence, log), machine


def try_task(repo, task, raw, scratch, out_dir, agent, exe, runs=1, model=None, extra=(), keep=False, direct=False,
             timeout=1800, build_timeout=3600, places=(), log=print, clock=time.time):
    """Try one task `runs` times with `agent`; its result (written to <out_dir>/<name>.json, each run's transcript and
    plays under <out_dir>/<name>/)."""
    started = clock()
    name = task.get("name", "?")
    evidence = Path(out_dir) / name
    result = {"format": FORMAT, "task": name, "game": (task.get("seed") or {}).get("game"),
              "task_sha256": tasks.digest(raw), "agent": agent, "model": model, "status": None, "reasons": [],
              "solved": 0, "runs": [], "limits": limits_of(task), "at": None, "seconds": None,
              "evidence": f"{name}/"}

    def finish(status, reasons=()):
        result.update(status=status, reasons=list(reasons), solved=sum(1 for r in result["runs"] if r.get("solved")),
                      seconds=round(clock() - started, 1), at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
        Path(out_dir).mkdir(parents=True, exist_ok=True)
        (Path(out_dir) / f"{name}.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        return result

    found = tasks.problems(task)
    if found:
        return finish("ERROR", [f"the task doesn't validate: {p}" for p in found[:5]])
    seed = task["seed"]
    if not seed.get("reference"):
        return finish("ERROR", ["the task has no seed.reference: a try is graded against the start and the reference"])
    scratch = Path(scratch)
    if scratch.exists():  # the try deletes it whole when it ends (an empty path is the current folder)
        return finish("ERROR", [f"the scratch folder {scratch.absolute()} exists already: a try makes its own"])
    seeds.remove(evidence)
    evidence.mkdir(parents=True)
    try:
        shas = {k: seeds.resolve(repo, seed[k]) for k in ("commit", "reference")}
        for folder in [scratch / "start", scratch / "reference"] + [scratch / f"run{i}" / seed["game"]
                                                                  for i in range(1, runs + 1)]:
            seeds.check_length(folder)  # before hours of building, not after
        sides, machines = {}, {}
        for label, sha in (("start", shas["commit"]), ("reference", shas["reference"])):
            log(f"  {label}: materializing {sha[:12]}")
            seeds.materialize(repo, sha, scratch / label)
            sides[label], machines[label] = side(label, scratch / label, task, direct, timeout, build_timeout, evidence,
                                                 log)
        start, reference = sides["start"], sides["reference"]
        if not start.built() and tasks.fails_at_start(task) is None:
            return finish("ERROR", [f"the start doesn't build: {start.why_unbuilt()} (run task-check.py first)"])
        if not reference.built():
            return finish("ERROR", [f"the reference doesn't build: {reference.why_unbuilt()} (run task-check.py first)"])
        thresholds = {}
        measure = check.Grade(task, "reference", start, reference, thresholds)
        for _, c in tasks.checks(task):  # every threshold now: neither copy is played once an agent has started
            if c["kind"] == "probe" and c["measure"]["probe"] != "trace":
                try:
                    measure.threshold(c)
                except verdict.Uncalibrated:
                    pass  # kept in `thresholds`: every run's grade fails that check the same way
        # Gone before an agent starts, as it could read them two folders above its own: the reference copy is the answer
        # and the copies' logs hold the grader's queries.
        for label in ("start", "reference"):
            seeds.remove(scratch / label)
        prompt = brief(task, machines["start"].editor)  # the workspace's: the reference may name another 6000.3 release
        (evidence / "brief.md").write_text(prompt, encoding="utf-8")
        limits = limits_of(task)
        for i in range(1, runs + 1):
            label = f"run{i}"
            folder = scratch / label / seed["game"]
            log(f"  {label}: preparing the workspace {folder}")
            workspace(repo, shas["commit"], folder)
            transcript = evidence / label / "transcript.jsonl"
            transcript.parent.mkdir(parents=True, exist_ok=True)
            settings = scratch / "claude-settings.json"  # on the agent's command line: never a path into the game repo
            settings.write_text(json.dumps({"disableAllHooks": True}), encoding="utf-8")
            argv = agent_argv(agent, exe, limits, settings, model, extra)
            log(f"  {label}: {agent} working (up to {limits['max_minutes']} min)")
            codex_home = folder.parent / (folder.name + ".codex-home") if agent == "codex" else None
            try:
                extra_env = {"CODEX_HOME": str(clean_codex_home(codex_home))} if codex_home else None
                ran = run_agent(argv, folder, prompt, transcript, limits["max_minutes"], env_extra=extra_env)
            finally:
                if codex_home:
                    put_login_back(codex_home)
                    keep_codex_sessions(codex_home, transcript.parent / "codex-sessions")
            row = {"run": i, **ran, **usage(agent, transcript), "peeked": peeked(transcript, places),
                   "workspace": str(folder) if keep else None}
            left = kill_left_behind(folder)
            if left:
                log(f"  {label}: stopped {len(left)} process(es) the agent left running")
            log(f"  {label}: {agent} stopped after {ran['seconds'] / 60:.0f} min"
                + (" (timed out)" if ran["timed_out"] else f" (exit {ran['exit_code']})"))
            try:
                if outside(folder, [scratch]):  # the agent swapped its folder for a link: nothing there is the try's
                    raise FileNotFoundError(f"the workspace is now a link to {os.path.realpath(folder)}: not graded")
                clear(folder, BUILT)
                tried, _ = side(label, folder, task, direct, timeout, build_timeout, evidence, log)
            except (seeds.WrongEngine, FileNotFoundError, RuntimeError) as exc:  # Unity version or project changed
                row.update(solved=False, score=0.0, required_passed=0, required=None, milestones={}, checks=[],
                           why=str(exc))
            else:
                grade = check.Grade(task, "reference", start, reference, thresholds, side=tried).run()
                row.update(score(task, grade), checks=grade["checks"])
            log(f"  {label}: {'SOLVED' if row['solved'] else 'not solved'} "
                f"({row['required_passed']}/{row['required'] or '?'} required checks)")
            result["runs"].append(row)
            if not keep:
                discard(scratch / label, log)
        return finish("DONE")
    except (OSError, RuntimeError, ValueError) as exc:
        return finish("ERROR", [f"the try couldn't run: {type(exc).__name__}: {str(exc)[:400]}"])
    finally:
        # Stopped (Ctrl+C), the try's own Unity jobs run on in their process groups, and what the agent left too.
        kill_left_behind(scratch)
        if not keep:
            discard(scratch, log)


def line(result):
    """The one line printed per task."""
    if result["status"] != "DONE":
        return f"ERROR   {result['task']}: " + "; ".join(result["reasons"])
    runs = result["runs"]
    head = f"{result['solved']}/{len(runs)} solved  {result['task']}"
    best = max((r["required_passed"] for r in runs), default=0)
    total = next((r["required"] for r in runs if r["required"]), "?")
    tail = f"  (best {best}/{total} required checks"
    peeks = sorted({p for r in runs for p in r["peeked"]})
    tail += f"; transcript names {', '.join(peeks)}: it may have read the answer)" if peeks else ")"
    # a run that hit its time limit or whose agent stopped with an error says nothing about length
    times = [r["seconds"] / 60 for r in runs if r.get("seconds") is not None and not r.get("timed_out")
             and r.get("exit_code", 0) == 0]
    if times and max(times) < LONG_MINUTES:
        tail += f"  longest run {max(times):.1f} min: under the {LONG_MINUTES}-minute guide (a guide, not a requirement)"
    return head + tail


def default_scratch(repo):
    """Where the workspaces go by default: a .task-try folder at the root of the repo's drive, so LFS objects hardlink,
    the agent's folder is outside the machine root (whose CLAUDE.md and AGENTS.md a harness would read) and the game
    repo, and its paths stay short (Unity fails past 260 characters)."""
    real = Path(os.path.realpath(repo))
    return Path(real.anchor or "/") / ".task-try"


def main(argv=None):
    import argparse
    import hashlib
    import sys

    from . import cli

    parser = argparse.ArgumentParser(prog="task-try.py", description=(
        "Try a game's task with your own coding agent (Claude Code or Codex): the game at the task's start in a fresh "
        "workspace, the agent given the brief, its result built, played and graded against the task's probes. "
        "docs/task-try.md"))
    parser.add_argument("repo", help="the game's repo (its tasks are read from its tasks branch, else origin/tasks)")
    parser.add_argument("--task", action="append", default=[], metavar="NAME",
                        help="a task on the tasks branch, or a task file (<name>.json) not committed yet (repeatable)")
    parser.add_argument("--agent", choices=("claude", "codex"), required=True, help="the harness to run")
    parser.add_argument("--runs", type=int, default=1, help="runs per task (default 1)")
    parser.add_argument("--model", help="the model the harness uses (default: its own)")
    parser.add_argument("--agent-arg", action="append", default=[], metavar="ARG",
                        help="an extra argument for the harness (repeatable)")
    parser.add_argument("--keep", action="store_true", help="keep the workspaces after the try (the start's and the "
                        "reference's copies go before an agent starts)")
    parser.add_argument("--out", help="where results go (default: <repo>\\.task-tries)")
    parser.add_argument("--scratch", help="where workspaces go (default: <repo's drive>\\.task-try)")
    parser.add_argument("--direct", action="store_true",
                        help="run Unity directly, not through the machine's unity-heavy.ps1 slots")
    parser.add_argument("--timeout", type=int, default=1800, help="seconds a play or the editor pass may run")
    parser.add_argument("--build-timeout", type=int, default=3600, help="seconds a build may run")
    args = parser.parse_args(argv)

    repo = Path(args.repo).resolve()
    if not (repo / ".git").exists():
        parser.error(f"{repo} isn't a git repo")
    if not args.task:
        parser.error("name a task with --task NAME (or --task <file>.json)")
    if args.runs < 1:
        parser.error("--runs must be at least 1")
    exe = shutil.which(args.agent)
    if exe is None:
        parser.error(f"{args.agent} isn't on PATH: install it and log in first")
    ref, found = tasks.read_tasks(repo)
    sources = {n: (t, raw, why) for n, (t, raw, why) in found.items()}
    tasks_dir = None
    for given in args.task:
        if given.lower().endswith(".json") and Path(given).is_file():
            raw = Path(given).read_bytes()
            try:
                data = json.loads(raw.decode("utf-8-sig"))
            except ValueError as e:
                data, why = None, f"{given} is not JSON ({e})"
            else:
                why = None if isinstance(data, dict) else f"{given} is not a task object"
            sources[given] = (data if why is None else None, raw, why)
            tasks_dir = Path(given).resolve().parent.parent
    unknown = [n for n in args.task if n not in sources]
    if unknown:
        parser.error(f"no task {', '.join(unknown)} on {ref or 'a tasks branch'}")
    root = Path(os.path.realpath(unity.ugfroot.root()))
    scratch_root = Path(args.scratch).resolve() if args.scratch else default_scratch(repo)
    if not outside(scratch_root, [root, repo] + ([tasks_dir] if tasks_dir else [])):
        parser.error(f"{scratch_root} is inside the machine root, the game repo or the tasks folder: the agent would "
                     "read their AGENTS.md / CLAUDE.md; pass --scratch outside them")
    out = Path(args.out).resolve() if args.out else repo / ".task-tries"
    cli.ignore_results(repo, out)
    unity.ugfroot.check_free(str(scratch_root), "task try")
    home = Path(os.path.expanduser("~"))
    places = [repo, root, out, home / ".agents", home / ".claude", home / ".codex"] + (
        [tasks_dir] if tasks_dir else [])

    def log(text):
        print(text, file=sys.stderr, flush=True)

    results = []
    for name in args.task:
        task, raw, why = sources[name]
        log(f"{name}: trying with {args.agent}, {args.runs} run(s)")
        if task is None:
            result = {"task": name, "status": "ERROR", "reasons": [why], "runs": [], "solved": 0}
        else:
            tag = hashlib.sha256(f"{repo}:{name}:{time.time()}".encode()).hexdigest()[:8]
            result = try_task(repo, task, raw, scratch_root / tag, out, args.agent, exe, runs=args.runs,
                              model=args.model, extra=args.agent_arg, keep=args.keep, direct=args.direct,
                              timeout=args.timeout, build_timeout=args.build_timeout, places=places, log=log)
            if args.keep:
                log(f"  kept the workspaces in {scratch_root / tag}")
        results.append(result)
        print(line(result), flush=True)
    log(f"results: {out}")
    return 0 if all(r["status"] == "DONE" for r in results) else 1
