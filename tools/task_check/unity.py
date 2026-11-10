"""Unity for the checker: build a scratch copy's player with the TaskProbe package, play it, run the editor pass over its
assets. Every job goes through the machine's `<root>\\tools\\unity-heavy.ps1` when it has one (the machine's shared
CPU/GPU slots: the timeout then counts from when the job starts, never the wait for a slot), else runs directly. The
editor is the one the project's ProjectSettings/ProjectVersion.txt names (machine/lib/ugfroot.py `unity_editor`).
Unity locks a project while it has it open, so a scratch copy runs one job at a time (the checker is sequential).

- build: Unity.exe -batchmode -nographics -quit -projectPath <copy> -logFile <copy>/Logs/TaskProbe/build.log
  -executeMethod TaskProbe.EditorTools.Build.Player -taskProbeBuild <request>: a Windows x64 Mono player of the copy
  in Build/TaskProbe with the scenes the task plays added after the project's own enabled build scenes; its result
  file says whether it built and which assets the played scenes name that the project lacks (`missing`). It passed
  when the exit code is 0 and the result says `ok`;
- play: python desk.py <copy>/Build/TaskProbe/Game.exe -screen-fullscreen 0 -screen-width 960 -screen-height 540
  -logFile <copy>/Logs/TaskProbe/play.log -taskProbe <spec> <play args>, run in the build folder in one of the
  limiter's GPU slots: one spec file (unity-probe-play/1) says everything about the play (seconds, screenshots,
  sampling, scene, sound, player, inputs, queries). desk.py starts the player on a Windows desktop of its own, so the
  play shows nothing on the user's screen and never takes the keyboard or the mouse cursor;
- editor_assets: Unity.exe -batchmode -nographics -quit -projectPath <copy> -logFile ... -executeMethod
  TaskProbe.EditorTools.AssetPass.Run -taskProbeAssets <request>: every asset measure of a side, on the project as
  saved."""

import json
import re
import shutil
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

from . import probes, seeds

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent / "machine" / "lib"))
import ugfroot  # noqa: E402  (unity-game-factory's machine root and Unity resolver)

SHOT_SIZE = (960, 540)
OUTPUT_CHARS = 30_000
CAUSE_CHARS = 200  # a failed build's cause, as its reason quotes it
WRAPPER_GRACE = 60  # seconds unity-heavy.ps1 gets to release its slot once the job it runs is killed
QUEUE_POLL = 5  # seconds between looks at whether the wrapper has started its job
LOGS = "Logs/TaskProbe"  # in the copy: requests, results, logs and the play's folder (Logs/ is never the game's)
BUILD_DIR = "Build/TaskProbe"
PLAYER = "Game.exe"
DESK = HERE / "desk.py"  # runs the player on its own desktop
BUILD_METHOD = "TaskProbe.EditorTools.Build.Player"
ASSETS_METHOD = "TaskProbe.EditorTools.AssetPass.Run"
SPEC_FORMAT = "unity-probe-play/1"
# A crash in a player log. A managed exception the game survives isn't one: log_absent checks for those.
FATAL = r"Crash!!!|OUTPUTTING STACK TRACE|Fatal error|Out of memory"
# Unity without an active licence logs this and exits 198 (templates/unity-game/Scripts/unity.ps1). Not "Licensing ...
# Error" lines: every log on a licensed machine has some.
UNLICENSED = "No valid Unity Editor license"
UNLICENSED_EXIT = 198


@dataclass
class Result:
    exit_code: int | None  # None: killed at its timeout
    output: str
    seconds: float
    timed_out: bool = False
    waited: float = 0.0  # of `seconds`, waiting for a unity-heavy.ps1 slot before the job started
    report: dict | None = None  # a build's result file (ok, exe, scenes, missing, ...); None when it wrote none
    cause: str | None = None  # a failed build's first cause, one line (_cause)


@dataclass
class Played:
    exit_code: int | None
    timed_out: bool
    output: str
    seconds: float
    probe: dict | None  # the probe's probe.json; None when it wrote none (the game didn't get there)
    log: str
    files: dict = field(default_factory=dict)  # what the play wrote (probe.json, screenshots) by name
    waited: float = 0.0  # of `seconds`, waiting for a machine slot


def cut(text, limit=OUTPUT_CHARS):
    if len(text) <= limit:
        return text
    half = limit // 2
    return f"{text[:half]}\n... [{len(text) - limit} characters left out] ...\n{text[-half:]}"


def _kill_tree(pid):
    subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)], capture_output=True, check=False)


def _children(pid):
    """{parent pid: [child pids]} of every process (one CIM query)."""
    out = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command",
                          "Get-CimInstance Win32_Process | ForEach-Object { \"$($_.ProcessId) $($_.ParentProcessId) "
                          "$($_.Name)\" }"], capture_output=True, text=True, check=False).stdout
    children, names = {}, {}
    for line in out.splitlines():
        parts = line.split(None, 2)
        if len(parts) >= 2 and parts[0].isdigit() and parts[1].isdigit():
            children.setdefault(int(parts[1]), []).append(int(parts[0]))
            names[int(parts[0])] = parts[2] if len(parts) > 2 else ""
    return children, names


def _descendants(pid):
    children, _ = _children(pid)
    found, todo = [], list(children.get(pid, []))
    while todo:
        child = todo.pop()
        if child != pid and child not in found:
            found.append(child)
            todo += children.get(child, [])
    return list(reversed(found))


def _job_started(pid, name):
    """Whether unity-heavy.ps1's wrapper `pid` has started its job: a child process named `name`, the job's own
    executable. Not any child: while it waits for a slot the limiter runs helpers of its own (nvidia-smi for its VRAM
    guard), and one taken for the job started its timeout during the wait."""
    children, names = _children(pid)
    return any(names.get(c, "").strip().lower() == name.lower() for c in children.get(pid, []))


def run(argv, cwd, timeout, wrapper=None, clock=time.monotonic):
    """Run `argv` in `cwd`; its output, cut. Killed with its children after `timeout` seconds, or at once when the wait
    is interrupted; `wrapper`: `argv` is unity-heavy.ps1's and `wrapper` the file name of its job's executable, so
    `timeout` counts from when its job starts, only the job is killed, and the wrapper gets WRAPPER_GRACE seconds to
    release its slot."""
    started = clock()
    proc = subprocess.Popen(argv, cwd=str(cwd), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            stdin=subprocess.DEVNULL, creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))
    chunks = []
    reader = threading.Thread(target=lambda: chunks.append(proc.stdout.read()), daemon=True)
    reader.start()
    job = None if wrapper else started
    timed_out = False
    try:
        while True:
            try:
                proc.wait(timeout=QUEUE_POLL if job is None else max(0.05, min(QUEUE_POLL, timeout - (clock() - job))))
                break
            except subprocess.TimeoutExpired:
                if job is None:
                    if _job_started(proc.pid, wrapper):
                        job = clock()
                    continue
                if clock() - job < timeout:
                    continue
                timed_out = True
                if wrapper:
                    for child in _descendants(proc.pid):
                        subprocess.run(["taskkill", "/F", "/PID", str(child)], capture_output=True, check=False)
                    try:
                        proc.wait(timeout=WRAPPER_GRACE)
                    except subprocess.TimeoutExpired:
                        _kill_tree(proc.pid)
                        proc.wait()
                else:
                    _kill_tree(proc.pid)
                    proc.wait()
                break
    except BaseException:
        # Ctrl+C (or any error) while waiting: the job is in a process group of its own, so the interrupt never
        # reached it; it would go on building into a copy being deleted, or playing where nobody sees it.
        _kill_tree(proc.pid)
        proc.wait()
        raise
    reader.join(timeout=30)
    if not reader.is_alive():  # closing the pipe under a read that still waits would block until the read returns
        proc.stdout.close()
    text = (b"".join(chunks)).decode("utf-8", errors="replace").replace("\r\n", "\n")
    waited = job - started if wrapper and job is not None else 0.0  # a job seen start within its first poll: ~0
    return Result(None if timed_out else proc.returncode, cut(text), round(clock() - started, 3), timed_out,
                  round(waited, 3))


class MachineError(RuntimeError):
    """The machine can't run Unity's jobs: the run's error, never a verdict on the game."""


class LimiterRefused(MachineError):
    """The machine's job limiter couldn't be started at all."""


class Unlicensed(MachineError):
    """Unity has no active licence."""


def _licensed(found, log):
    """Raises Unlicensed when the batchmode Unity job `found` (`log`: its output and log) stopped for want of a
    licence."""
    if found.exit_code == UNLICENSED_EXIT or (found.exit_code not in (0, None) and UNLICENSED in log):
        raise Unlicensed(f'Unity has no active licence (exit {found.exit_code}, "{UNLICENSED}"): sign in to Unity Hub, '
                         "check the licence there (Settings > Licenses; a free Personal one will do), and run again")


def _ps_quote(value):
    return "'" + str(value).replace("'", "''") + "'"


@dataclass
class Machine:
    """Where Unity is and how jobs run: `editor` (the project's Unity.exe), `heavy` (the slot limiter, or None to run
    directly)."""

    editor: Path
    heavy: Path | None

    @classmethod
    def for_project(cls, project, direct=False):
        """The machine for a scratch copy: the Unity its ProjectVersion.txt names. Raises RuntimeError naming the
        version to install when that Unity isn't installed."""
        try:
            editor = Path(ugfroot.unity_editor(str(project)))
        except SystemExit as exc:  # ugfroot exits, as a command line would; the checker reports it per task
            raise RuntimeError(str(exc)) from None
        heavy = Path(ugfroot.root()) / "tools" / "unity-heavy.ps1"
        return cls(editor=editor, heavy=None if direct or not heavy.is_file() else heavy)

    def job(self, label, argv, cwd, timeout, gpu=False):
        """`argv` as one Unity job: through unity-heavy.ps1 when the machine has it (in a GPU slot too when `gpu`),
        else directly. The limiter is the machine's own installed script, started the way the skills start the
        machine's scripts (-ExecutionPolicy Bypass): a plain `powershell` started from another shell runs no script
        on a default Windows. A limiter PowerShell still refuses to load (a policy the organisation set) raises
        LimiterRefused: that is the machine's fault, never a game that doesn't build."""
        if self.heavy is None:
            return run([str(a) for a in argv], cwd, timeout)
        command = (f"& {_ps_quote(self.heavy)} -Label {_ps_quote(label)}{' -Gpu' if gpu else ''} -- "
                   + " ".join(_ps_quote(a) for a in argv)
                   + "; if ($null -eq $LASTEXITCODE) { exit 1 }; exit $LASTEXITCODE")
        found = run(["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", command],
                    cwd, timeout, wrapper=Path(str(argv[0])).name)
        if found.exit_code and ("cannot be loaded" in found.output or "not digitally signed" in found.output):
            raise LimiterRefused("PowerShell refused to run unity-heavy.ps1 (an execution policy set for this machine): "
                                 "pass --direct to run without the machine's job slots. " + found.output.strip()[:300])
        return found


def _read_json(path):
    """A JSON object from `path`, or None (no file, not JSON, not an object)."""
    try:
        found = json.loads(Path(path).read_bytes().decode("utf-8-sig"))
    except (OSError, ValueError):
        return None
    return found if isinstance(found, dict) else None


def _read_text(path):
    try:
        return Path(path).read_bytes().decode("utf-8", errors="replace").replace("\r\n", "\n")
    except OSError:
        return ""


def _cause(report, log):
    """A failed build's first cause in one line, for its reason (the log stays the evidence): its result's error, else
    the log's first compiler error as Unity prints it (`<file>(<line>,<column>): error CS<n>: ...`), else its first
    `## Script Compilation Error for:` line (an assembly a post-processor failed on), else None."""
    error = report.get("error") if isinstance(report, dict) else None
    found = error.strip() if isinstance(error, str) and error.strip() else None
    for pattern in (r"^.*\berror CS\d+\b.*$", r"^## Script Compilation Error for:.*$"):
        line = None if found else re.search(pattern, log, re.M)
        found = found or (line.group(0).strip() if line else None)
    return found if found is None or len(found) <= CAUSE_CHARS else found[:CAUSE_CHARS - 3] + "..."


def _fresh(path):
    """`path` (a file) gone and its folder there: what a job writes is never an earlier job's."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    seeds.remove(path)
    return path


class Project:
    """A scratch copy of the game (seeds.materialize + add_probe) the checker builds and plays."""

    def __init__(self, folder, machine, label):
        self.folder, self.machine, self.label = Path(folder), machine, label
        self.report = None  # the last build's result file

    def logs(self):
        return self.folder / LOGS

    def player(self):
        """The built player: the build result's exe when it is there, else Build/TaskProbe/Game.exe."""
        exe = (self.report or {}).get("exe")
        return Path(exe) if isinstance(exe, str) and exe and Path(exe).is_file() else self.folder / BUILD_DIR / PLAYER

    def _batch(self, log):
        return [self.machine.editor, "-batchmode", "-nographics", "-quit", "-projectPath", self.folder, "-logFile",
                log]

    def build(self, timeout, scenes=()):
        """The player build, `scenes` (the scenes the task's plays open, project paths) added after the project's own
        enabled build scenes. A Result whose `report` is the build's result file; it passed when Unity exited 0 and
        the result says `ok` (anything else has a non-zero exit code); `output` holds the build log."""
        logs = self.logs()
        result, log = _fresh(logs / "build.json"), _fresh(logs / "build.log")
        seeds.remove(self.folder / BUILD_DIR)  # a fresh build: never an older player to play
        request = _fresh(logs / "build_request.json")
        request.write_text(json.dumps({"out": (self.folder / BUILD_DIR).as_posix(), "scenes": list(scenes),
                                       "result": result.as_posix()}, indent=2), encoding="utf-8")
        argv = self._batch(log) + ["-executeMethod", BUILD_METHOD, "-taskProbeBuild", request]
        found = self.machine.job(f"task-check build {self.label}", argv, self.folder, timeout)
        output = (found.output + "\n" if found.output.strip() else "") + _read_text(log)
        _licensed(found, output)
        report = _read_json(result)
        self.report = report
        code, said = found.exit_code, ""
        if report is not None and report.get("ok") is not True:  # some failures are in the result file alone
            said = f"[task-check] the build's result says it failed: {report.get('error')}\n"
        elif report is None and code == 0:
            said = "[task-check] Unity exited 0 but the build wrote no result\n"
        if code == 0 and said:
            code = 1
        return Result(code, cut(said + output), found.seconds, found.timed_out, found.waited, report,
                      _cause(report, output) if code not in (0, None) else None)

    def play(self, seconds, shots, timeout, scene=None, inputs=None, queries=None, args=(), every=None, player=None):
        """The built player for `seconds` of game time through the probe: windowed at 960x540 on its own desktop, a fixed
        30 fps, `shots` screenshots, `inputs` sent at their times, `queries` (probes.query_file) sampled every `every`
        s, `scene` opened (None: the project's first build scene), `player` (an object select, or None: the probe
        finds the player) as the player, `args` after the spec on the command line; a Played."""
        logs = self.logs()
        out = logs / "play"
        seeds.remove(out)  # what an earlier play wrote is never this one's
        out.mkdir(parents=True)
        log_path = _fresh(logs / "play.log")
        every = every or probes.EVERY
        spec = {"format": SPEC_FORMAT, "out": out.as_posix(), "seconds": seconds, "shots": shots, "every": every,
                "scene": scene, "sound": probes.hears(queries), "player": player, "inputs": list(inputs or []),
                "queries": queries or {"format": probes.QUERIES_FORMAT, "every": every, "queries": []}}
        asked = _fresh(logs / "play_spec.json")  # beside the play's folder, so it isn't one of the files the play wrote
        asked.write_text(json.dumps(spec, indent=2), encoding="utf-8")
        exe = self.player()
        if not exe.is_file():
            return Played(1, False, f"[task-check] no built player at {exe}", 0.0, None, "", {})
        argv = [sys.executable, DESK, exe, "-screen-fullscreen", "0", "-screen-width", str(SHOT_SIZE[0]),
                "-screen-height", str(SHOT_SIZE[1]), "-logFile", log_path, "-taskProbe", asked, *args]
        found = self.machine.job(f"task-check play {self.label}", argv, exe.parent, timeout, gpu=True)
        files = {p.name: p.read_bytes() for p in out.iterdir() if p.is_file()} if out.is_dir() else {}
        probe = None
        if "probe.json" in files:
            try:
                probe = json.loads(files["probe.json"].decode("utf-8-sig"))
            except ValueError:
                probe = None
        log = _read_text(log_path)
        shutil.rmtree(out, ignore_errors=True)
        return Played(found.exit_code, found.timed_out, found.output, found.seconds,
                      probe if isinstance(probe, dict) else None, log, files, found.waited)

    def editor_assets(self, request, timeout):
        """The editor pass over `request` (probes.editor_request); its result goes to probes.EDITOR_FILE in the copy
        (`read` it). A Result whose output holds the pass's log, its result line whole."""
        logs = self.logs()
        result, log = _fresh(self.folder / probes.EDITOR_FILE), _fresh(logs / "editor.log")
        asked = _fresh(logs / "probes_editor_request.json")
        asked.write_text(json.dumps({**request, "result": result.as_posix()}, indent=2), encoding="utf-8")
        argv = self._batch(log) + ["-executeMethod", ASSETS_METHOD, "-taskProbeAssets", asked]
        found = self.machine.job(f"task-check editor {self.label}", argv, self.folder, timeout)
        output = (found.output + "\n" if found.output.strip() else "") + _read_text(log)
        _licensed(found, output)
        # the pass's result line whole (probes.editor_results' fallback): cut() keeps only the two ends of a long log
        line = next((at for at in reversed(output.splitlines()) if probes.MARKER + " " in at), "")
        kept = cut(output)
        return Result(found.exit_code, kept if line in kept else f"{kept}\n{line}", found.seconds, found.timed_out,
                      found.waited)

    def read(self, relative):
        path = self.folder / relative
        return path.read_bytes() if path.is_file() else None
