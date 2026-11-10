"""One task checked end to end (docs/task-check.md).

1. The task is read and validated (tasks.problems); its start (seed.commit) and reference (seed.reference) are
   materialized into a scratch folder outside the repo, each with the TaskProbe package (seeds.py).
2. The start is built first (a player build with the scenes the task plays). A start that doesn't build makes the task
   INVALID, unless a build check says it doesn't (`fails_at_start`): then not building is the start failing the task,
   and the start is never played.
3. With a reference, the reference is checked as a solution would be: its checks in the task's order (a check whose
   `needs` failed isn't run and fails), build, boot, log_absent, file_exists and every probe against its threshold. A
   calibrated or start-relative threshold measures the start (its plays, played once) and, calibrated, the reference.
4. The start is checked on its probes (and on a `fails_at_start` build check).
5. verdict.verdict decides VALID or INVALID from the two sides' check rows.

A run of several tasks shares one scratch copy per commit (Builds): a commit that is one task's start and another's
reference, or two tasks' start, is materialized and built once and kept until the last task that needs it is done.
The copy is the commit exactly as committed either way, so sharing it changes no result. A player holds only the
scenes its build was given, so a later task that plays a scene the shared build lacks has the copy built again with
every scene asked for so far (Built.build).

The plays a probe names: "look", the idle play (20 s, no input, 6 screenshots); "drive", the scripted drive (22 s:
<Keyboard>/w 1-6 s, /d 6-8 s, /w 8-13 s with a jump (/space) at 9 s, /a 13-15 s, /w 15-21 s; 8 screenshots); a task
play (its own seconds, inputs, scene, args and sampling; 2 screenshots); "editor", one batchmode editor pass per side
over every asset measure. Each is played once per side, with the probe's queries for every probe it serves, on the
task's play_scene and play_args unless a task play names its own, with the task's `player` as the player. A boot
check plays boot_<seconds>s (2 screenshots, no queries). Every task's boot is a 60 s idle play and "look" is the first
20 s of the same idle game, so when no look probe reads the log, a side that boots (the reference; a start is never
booted) plays one 60 s idle play with look's queries for both (Side.idle): the boot check reads it whole, and look
reads its first 20 s only (first_seconds), one game launch instead of two. Judges, trace probes and packaging are
never part of a task check."""

import json
import math
import re
import secrets
import time
from pathlib import Path

from . import FORMAT, probes, seeds, tasks, unity, verdict

DRIVE = [{"t": 1.0, "key": "<Keyboard>/w", "press": True}, {"t": 6.0, "key": "<Keyboard>/w", "press": False},
         {"t": 6.0, "key": "<Keyboard>/d", "press": True}, {"t": 8.0, "key": "<Keyboard>/d", "press": False},
         {"t": 8.0, "key": "<Keyboard>/w", "press": True}, {"t": 9.0, "key": "<Keyboard>/space", "press": True},
         {"t": 9.3, "key": "<Keyboard>/space", "press": False}, {"t": 13.0, "key": "<Keyboard>/w", "press": False},
         {"t": 13.0, "key": "<Keyboard>/a", "press": True}, {"t": 15.0, "key": "<Keyboard>/a", "press": False},
         {"t": 15.0, "key": "<Keyboard>/w", "press": True}, {"t": 21.0, "key": "<Keyboard>/w", "press": False}]
PLAYS = {"look": (20, 6, None), "drive": (22, 8, DRIVE)}  # seconds, screenshots, inputs
JUDGES = ("judge", "code_judge", "actions_judge")
NOT_JUDGED = "not asked: judges never decide a task check"
SKIP = {"Library", "Temp", "Obj", "Logs", "Build", "Builds", "UserSettings", ".git", ".vs"}  # left out of file_exists


def fatal(log):
    return bool(re.search(unity.FATAL, log or ""))


def first_seconds(probe, seconds):
    """`probe` (a play's probe.json) as a play of only its first `seconds` would have written it: rows and samples after
    that dropped, its length cut to them."""
    if not isinstance(probe, dict):
        return probe
    cut = dict(probe)
    for name in ("track", "camera"):
        rows = probe.get(name)
        if isinstance(rows, list):
            cut[name] = [r for r in rows if not (isinstance(r, list) and r and isinstance(r[0], int | float)
                                                 and r[0] > seconds + 1e-6)]
    if isinstance(probe.get("measures"), dict):
        cut["measures"] = {q: [s for s in samples if not (isinstance(s, dict) and isinstance(s.get("t"), int | float)
                                                          and s["t"] > seconds + 1e-6)] if isinstance(samples, list)
                           else samples for q, samples in probe["measures"].items()}
    length = probe.get("seconds")
    if isinstance(length, int | float) and not isinstance(length, bool) and length >= seconds - 1e-6:
        cut["seconds"], cut["ended"] = float(seconds), "time"
    return cut


class Built:
    """A scratch project shared by every task of a run whose start or reference is its commit: built at most once per
    set of scenes, played as often as the tasks ask (each task's plays carry its own queries). A task that plays a
    scene the build lacks has it built again with every scene asked for so far (a player only holds the scenes its
    build was given), so the copy's build always serves every task before it too."""

    def __init__(self, project, log=print):
        self.project, self.log = project, log
        self._build = None
        self._scenes = set()  # the scenes the current build was given

    def has_built(self, scenes=()):
        """Whether a build that holds `scenes` is already made."""
        return self._build is not None and set(scenes) <= self._scenes

    def build(self, timeout, scenes=()):
        if not self.has_built(scenes):
            if self._build is not None:
                more = sorted(set(scenes) - self._scenes)
                self.log(f"  {self.project.label}: building again, for scene(s) the earlier build lacks: "
                         f"{', '.join(more)}")
            self._scenes |= set(scenes)
            self._build = self.project.build(timeout, sorted(self._scenes))
        return self._build

    def __getattr__(self, name):
        return getattr(self.project, name)


class Builds:
    """The scratch copies of one run, one per commit under `scratch`, each a Built. `get` materializes and adds the
    TaskProbe package on first use; `release` deletes a copy no later task needs; `close` deletes them all."""

    def __init__(self, repo, scratch, direct=False, log=print):
        self.repo, self.scratch, self.direct, self.log = repo, Path(scratch), direct, log
        self.copies = {}  # sha -> (Built, info) or the seeds.WrongEngine its probe package refused

    def get(self, sha, needed=()):
        """(Built, info) for commit `sha`; raises seeds.WrongEngine for a project that isn't Unity 6000.3 and
        seeds.PathTooLong for a scratch folder Unity can't build in. When the disk is below the machine's floor, copies
        other than `needed` (this task's commits) are deleted first."""
        if sha in self.copies:
            self.log(f"  {sha[:12]}: reusing the copy already made in this run")
        else:
            folder = seeds.check_length(self.scratch / sha[:12])
            self._room(set(needed) | {sha})
            self.log(f"  {sha[:12]}: materializing into {folder}")
            made = seeds.materialize(self.repo, sha, folder)
            try:
                seeds.add_probe(folder)
            except seeds.WrongEngine as exc:
                self.copies[sha] = exc
            else:
                machine = unity.Machine.for_project(folder, self.direct)
                self.copies[sha] = (Built(unity.Project(folder, machine, sha[:12]), self.log),
                                    {"files": made["files"], "lfs_linked": made["linked"],
                                     "lfs_copied": made["copied"], "engine": str(machine.editor),
                                     "slots": "unity-heavy" if machine.heavy else "direct"})
        found = self.copies[sha]
        if isinstance(found, Exception):
            raise found
        return found

    def _room(self, needed):
        try:
            unity.ugfroot.check_free(str(self.scratch), "task check")
            return
        except SystemExit:
            for sha in [s for s in self.copies if s not in needed]:
                self.log(f"  {sha[:12]}: low on disk, deleting its copy (a later task rebuilds it)")
                self.release(sha)
        unity.ugfroot.check_free(str(self.scratch), "task check")

    def release(self, sha):
        if self.copies.pop(sha, None) is not None:
            seeds.remove(self.scratch / sha[:12])

    def close(self):
        self.copies.clear()
        seeds.remove(self.scratch)


def task_scenes(task):
    """The scenes the task's plays open: its play_scene and every task play's own scene (a play's key, when it has
    one, takes the task's place)."""
    found = [task.get("play_scene")] + [tasks.place(task, p)[0] for p in probes.task_plays(task).values()]
    return sorted({s for s in found if s})


class Side:
    """One side of a check ("start" or "reference"): its scratch project, built once, each play played once.
    `evidence`: where each play's probe.json, screenshots and log are kept (None: not kept)."""

    def __init__(self, name, project, task, timeout, build_timeout, evidence=None, log=print):
        self.name, self.project, self.task = name, project, task
        self.timeout, self.build_timeout = timeout, build_timeout
        self.evidence, self.log = evidence, log
        self.plan = probes.plan(task)
        self.scenes = task_scenes(task)
        self.player = tasks.player(task)
        self._build = None
        self.played = {}  # play name -> unity.Played
        self._editor = None

    # -- the build ---------------------------------------------------------------------------------------------------

    def build(self):
        if self._build is None:
            again = getattr(self.project, "has_built", lambda *a: False)(self.scenes)
            if not again:
                self.log(f"  {self.name}: building")
            self._build = self.project.build(self.build_timeout, self.scenes)
            waited = getattr(self._build, "waited", 0.0)
            self.log(f"  {self.name}: {'built' if self._build.exit_code == 0 else 'build FAILED'} "
                     f"({self._build.seconds:.0f} s{', built earlier in this run' if again else ''}"
                     f"{f', {waited:.0f} s of it waiting for a machine slot' if waited >= 1 and not again else ''})")
            if self.evidence is not None and self._build.exit_code != 0:
                self._keep("build", {"build.log": self._build.output.encode("utf-8")})
        return self._build

    def built(self):
        return self.build().exit_code == 0

    def why_unbuilt(self):
        r = self.build()
        what = {"start": "the game as the task started", "reference": "the reference game"}.get(
            self.name, f"the agent's game ({self.name})")
        return f"{what} didn't build ({'timed out' if r.timed_out else f'exit {r.exit_code}'})"

    def missing_assets(self):
        """{scene: {"missing": [asset GUIDs], "names": how many it names}} of the scenes this task plays that name
        assets the commit lacks (a store pack committed only later, say), from the build's result; {} before a build.
        The checker never fills them in: a task is built exactly as committed."""
        report = getattr(self._build, "report", None) if self._build is not None else None
        found = (report or {}).get("missing") if isinstance(report, dict) else None
        if not isinstance(found, dict):
            return {}
        return {scene: {"missing": list(gap.get("missing") or []), "names": gap.get("names")}
                for scene, gap in sorted(found.items())
                if scene in self.scenes and isinstance(gap, dict) and gap.get("missing")}

    # -- plays ---------------------------------------------------------------------------------------------------------

    def _keep(self, name, files):
        folder = Path(self.evidence) / self.name / name
        folder.mkdir(parents=True, exist_ok=True)
        for f, data in files.items():
            (folder / f).write_bytes(data)

    def _play(self, name, seconds, shots, inputs=None, play=None, queries=None, every=None, waits=0.0):
        """A play, once per name, on the scene and args `play` (a task play, or None for the checker's own) opens;
        `waits`: the real seconds its waits add (a task play's), which its timeout gets on top."""
        if name not in self.played:
            self.log(f"  {self.name}: playing {name} ({seconds} s" + (f", {waits:g} s waiting" if waits else "") + ")")
            scene, args = tasks.place(self.task, play)
            found = self.project.play(seconds, shots, self.timeout + math.ceil(waits), scene=scene, inputs=inputs,
                                      queries=queries, args=args, every=every, player=self.player)
            self.played[name] = found
            waited = getattr(found, "waited", 0.0)
            self.log(f"  {self.name}: played {name} in {found.seconds:.0f} s"
                     + (f" ({waited:.0f} s of it waiting for a machine slot)" if waited >= 1 else ""))
            if self.evidence is not None:
                self._keep(name, {**found.files, "play.log": found.log.encode("utf-8"),
                                  "output.txt": found.output.encode("utf-8")})
        return self.played[name]

    def idle(self, seconds):
        """Whether the boot play of `seconds` also serves "look": look is the first part of the same idle game, so one
        play does when the boot is at least as long and no look probe reads the play's log (a log covers the whole
        play, so it can't be cut to look's seconds)."""
        return "look" in self.plan and seconds >= PLAYS["look"][0] and not any(
            tasks.play_name(c) == "look" and c["measure"]["probe"] == "log" for c in probes.probes(self.task))

    def boot(self, seconds):
        """The boot play of `seconds`: {ok, crashed, timed_out, log}."""
        if self.idle(seconds) and "look" not in self.played:
            p = self._play(f"boot_{seconds}s", seconds, PLAYS["look"][1],
                           queries=probes.query_file(self.plan["look"]))
        else:
            p = self._play(f"boot_{seconds}s", seconds, 2)
        crashed = fatal(p.log)
        return {"ok": p.probe is not None and p.probe.get("ended") == "time" and not crashed, "crashed": crashed,
                "timed_out": p.timed_out, "log": p.log}

    def probe_play(self, play):
        """The play a probe names ("look", "drive", a task play), played once with the queries of every probe it
        serves."""
        name = play if isinstance(play, str) else play["name"]
        every = None if isinstance(play, str) else play["every"]
        queries = probes.query_file(self.plan.get(name, []), every)
        if isinstance(play, str):
            seconds, shots, inputs = PLAYS[play]
            booted = next((b for b in self.boots() if play == "look" and self.idle(b)
                           and f"boot_{b}s" in self.played), None)
            if booted is not None:
                p = self.played[f"boot_{booted}s"]
                return unity.Played(p.exit_code, p.timed_out, p.output, p.seconds, first_seconds(p.probe, seconds),
                                    p.log, p.files)
            return self._play(name, seconds, shots, inputs, queries=queries)
        return self._play(f"play_{name}", play["seconds"], 2, play["inputs"] or None, play=play, queries=queries,
                          every=every, waits=tasks.waited(play))

    def boots(self):
        """The boot plays this task's checks run (seconds): its boot checks, and 60 s for a log_absent check."""
        found = []
        for _, check in tasks.checks(self.task):
            seconds = check.get("seconds") if check["kind"] == "boot" else 60 if check["kind"] == "log_absent" else None
            if seconds is not None and seconds not in found:
                found.append(seconds)
        return found

    def editor(self):
        """(the editor pass's results {measure id: result} or None; why none): one pass over every asset measure."""
        if self._editor is None:
            if not self.built():
                self._editor = None, "the project didn't build, so the editor couldn't open it"
            else:
                self.log(f"  {self.name}: editor pass")
                nonce = secrets.token_hex(16)
                ran = self.project.editor_assets(probes.editor_request(probes.editor_items(self.task), nonce),
                                                 self.timeout)
                results = probes.editor_results(self.project.read(probes.EDITOR_FILE), nonce, ran.output)
                why = None if results is not None else \
                    f"the editor pass gave no result (exit {ran.exit_code}{', timed out' if ran.timed_out else ''})"
                if self.evidence is not None:
                    self._keep("editor", {"output.txt": ran.output.encode("utf-8")})
                self._editor = results, why
        return self._editor

    def value(self, check):
        """(probe `check`'s number on this side, or None; why none)."""
        measure = check["measure"]
        if measure["probe"] == "asset":
            results, why = self.editor()
            if results is None:
                return None, why
            return probes.reduce_asset(measure, results.get(probes.editor_id(measure)))
        if not self.built():
            return None, f"{self.why_unbuilt()}, so it wasn't played"
        p = self.probe_play(check["play"])
        return probes.measured(measure, p.probe, p.log)


class Grade:
    """The checks of one side as a solution's grade would run them. `mode` "reference": every check but judges, trace
    probes and packaging, of the reference or of `side` (an agent's game, task-try.py); "start": its probes and a
    `fails_at_start` build check. Thresholds are shared between the grades (`thresholds`)."""

    def __init__(self, task, mode, start, reference, thresholds, side=None):
        self.task, self.mode, self.start, self.reference = task, mode, start, reference
        self.side = side or (reference if mode == "reference" else start)  # `side`: an agent's game graded as a solution
        self.thresholds = thresholds
        self.measured = {}

    def threshold(self, check):
        if check["name"] not in self.thresholds:
            try:
                self.thresholds[check["name"]] = verdict.make_threshold(
                    check, lambda: self.start.value(check),
                    lambda: self.reference.value(check) if self.reference else (None, "the task has no reference"))
            except verdict.Uncalibrated as exc:
                self.thresholds[check["name"]] = exc
        found = self.thresholds[check["name"]]
        if isinstance(found, verdict.Uncalibrated):
            raise found
        return found

    def probe_check(self, check):
        try:
            limit, start, fix = self.threshold(check)
        except verdict.Uncalibrated as exc:
            value, _ = self.side.value(check)
            self.measured[check["name"]] = {"value": value, "threshold": None, "start": exc.start, "fix": exc.fix}
            return False, f"uncalibrated: {exc}"
        value, why = self.side.value(check)
        self.measured[check["name"]] = {"value": value, "threshold": limit, "start": start, "fix": fix}
        passed = value is not None and verdict.passes(value, check["expect"]["op"], limit)
        return passed, verdict.describe(check, value, limit, start, fix, why)

    def check(self, check):
        kind = check["kind"]
        if kind in JUDGES:
            return True, NOT_JUDGED
        if kind == "probe" and check["measure"]["probe"] == "trace":
            return True, "not asked: a trace probe reads an agent's own calls"
        if self.mode == "start":
            if kind == "build" and check["fails_at_start"]:
                return (True, "the start built") if self.start.built() else (False, self.start.why_unbuilt())
            if kind != "probe":
                return True, "not asked: the start is checked on its probes"
            return self.probe_check(check)
        side = self.side
        if kind == "build":
            r = side.build()
            return r.exit_code == 0, "built" if r.exit_code == 0 else \
                f"build failed ({'timed out' if r.timed_out else f'exit {r.exit_code}'})"
        if kind == "boot":
            if not side.built():
                return False, f"{side.why_unbuilt()}, so it wasn't played"
            p = side.boot(check["seconds"])
            if p["ok"]:
                return True, f"ran {check['seconds']} s with no crash or fatal error"
            return False, "crashed" if p["crashed"] else ("timed out" if p["timed_out"] else "didn't finish its run")
        if kind == "log_absent":
            if not side.built():
                return False, f"{side.why_unbuilt()}, so it wasn't played"
            hits = [line for line in side.boot(60)["log"].splitlines() if re.search(check["pattern"], line)]
            return not hits, f"{len(hits)} matching log line(s)" + (f": {hits[0][:200]}" if hits else "")
        if kind == "file_exists":
            root = side.project.folder
            found = [p for p in root.glob(check["glob"]) if p.is_file()
                     and not SKIP.intersection(p.relative_to(root).parts)]
            return len(found) >= check["min_count"], f"{len(found)} file(s) match"
        if kind == "package":
            return True, "not asked: a task check never packages the game"
        if kind == "probe":
            return self.probe_check(check)
        raise ValueError(f"no check kind {kind}")

    def run(self):
        """{"checks": [{name, kind, passed, required, detail, group}], "probes": {name: {value, threshold, start,
        fix}}}."""
        rows, passed = [], {}
        for group, check in tasks.checks(self.task):
            missing = [n for n in check["needs"] if not passed.get(n)]
            if missing:
                ok, detail = False, f"not run: needs {missing[0]}"
            else:
                try:
                    ok, detail = self.check(check)
                except unity.MachineError:
                    raise  # the machine can't run Unity (its limiter, the licence): no verdict on the game
                except (OSError, RuntimeError, ValueError) as exc:
                    ok, detail = False, f"the checker failed ({type(exc).__name__}: {str(exc)[:200]})"
            passed[check["name"]] = bool(ok)
            rows.append({"name": check["name"], "kind": check["kind"], "passed": bool(ok),
                         "required": check["required"], "weight": check["weight"], "detail": str(detail)[:700],
                         "group": group})
        return {"checks": rows, "probes": self.measured}


def start_unbuilt(task, why):
    """The start's grade when it doesn't build and the task says so: that build check failed, nothing else run."""
    group, build = next((g, c) for g, c in tasks.checks(task) if c["kind"] == "build" and c["fails_at_start"])
    return {"checks": [{"name": build["name"], "kind": "build", "passed": False, "required": build["required"],
                        "weight": build["weight"], "detail": str(why)[:700], "group": group}], "probes": {}}


def probe_values(task, reference, start):
    """{probe: {group, required, op, expect, start, reference, threshold, start_passed, reference_passed}} from the two
    grades' measures (trace probes left out)."""

    def passed(grade, name):
        return next((r["passed"] for r in (grade or {}).get("checks", []) if r["name"] == name), None)

    out = {}
    for group, check in tasks.checks(task):
        if check["kind"] != "probe" or check["measure"]["probe"] == "trace":
            continue
        name = check["name"]
        ref = ((reference or {}).get("probes") or {}).get(name) or {}
        own = ((start or {}).get("probes") or {}).get(name) or {}
        out[name] = {"group": group, "required": check["required"], "op": check["expect"]["op"],
                     "expect": check["expect"], "start": own.get("value", ref.get("start")),
                     "reference": ref.get("value") if reference else None,
                     "threshold": ref.get("threshold", own.get("threshold")),
                     "start_passed": passed(start, name), "reference_passed": passed(reference, name) if reference
                     else None}
    return out


def gap_notes(result):
    """A note per side and scene that names assets the commit lacks."""
    notes = []
    for side in ("start", "reference"):
        for name, gap in ((result.get(side) or {}).get("missing_assets") or {}).items():
            notes.append(f"{side}: {name} names {len(gap['missing'])} of its {gap['names']} assets that the commit "
                         f"doesn't have (e.g. GUID {gap['missing'][0]}): they load as missing; commit them with the "
                         "task's commit or pick a commit that has them")
    return notes


def check_task(repo, task, raw, scratch, out_dir, keep=False, direct=False, timeout=1800, build_timeout=3600,
               log=print, clock=time.time, builds=None):
    """Check one task (a dict read from `repo`'s tasks branch, its file's bytes `raw`): its result (written to
    <out_dir>/<name>.json, its plays' files under <out_dir>/<name>/). `builds`: a run's shared copies (Builds), which
    the run deletes; without it the task gets its own under `scratch`, deleted when it is done unless `keep`."""
    started = clock()
    name = task.get("name", "?")
    result = {"format": FORMAT, "task": name, "game": (task.get("seed") or {}).get("game"),
              "task_sha256": tasks.digest(raw), "verdict": None, "reasons": [], "notes": [], "start": None,
              "reference": None, "probes": {}, "start_checks": [], "reference_checks": [],
              "evidence": f"{name}/", "at": None, "seconds": None}
    sides = {}

    def gaps():
        """Each side's missing_assets, from its build (none before it built)."""
        for side, found in sides.items():
            if result.get(side) is not None:
                result[side]["missing_assets"] = found.missing_assets()

    def finish(state, reasons, notes=()):
        gaps()
        result.update(verdict=state, reasons=list(reasons), notes=list(notes), seconds=round(clock() - started, 1),
                      at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
        Path(out_dir).mkdir(parents=True, exist_ok=True)
        (Path(out_dir) / f"{name}.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        return result

    found = tasks.problems(task)
    if found:
        return finish("INVALID", [f"the task doesn't validate: {p}" for p in found[:5]])
    seed = task["seed"]
    evidence = Path(out_dir) / name
    seeds.remove(evidence)
    own = builds is None
    if own:
        builds = Builds(repo, scratch, direct, log)
    try:
        shas = {}
        for side, commit in (("start", seed["commit"]), ("reference", seed.get("reference"))):
            if commit is None:
                continue
            try:
                shas[side] = seeds.resolve(repo, commit)
            except RuntimeError:
                return finish("INVALID", [f"seed.{'commit' if side == 'start' else 'reference'} {commit[:12]} isn't a "
                                          f"commit of {Path(repo).name} (fetch it, or fix the task)"])
        for side, sha in shas.items():
            try:
                project, info = builds.get(sha, shas.values())
            except seeds.WrongEngine as exc:
                return finish("INVALID", [f"{side}: {exc}"])
            sides[side] = Side(side, project, task, timeout, build_timeout, evidence, log)
            result[side] = {"commit": sha, **info, "missing_assets": {}}
        start, reference = sides["start"], sides.get("reference")
        build = tasks.fails_at_start(task)
        if not start.built():
            result["start"]["built"] = False
            if build is None:
                return finish("INVALID", [f"start doesn't build: {start.why_unbuilt()}"])
        else:
            result["start"]["built"] = True
        thresholds = {}
        ref_grade = None
        if reference is not None:
            ref_grade = Grade(task, "reference", start, reference, thresholds).run()
            result["reference"]["built"] = reference.built()
        if build is not None and not start.built():
            start_grade = start_unbuilt(task, start.why_unbuilt())
        else:
            start_grade = Grade(task, "start", start, reference, thresholds).run()
        valid, why, notes = verdict.verdict(task, ref_grade, start_grade)
        gaps()
        notes += gap_notes(result)
        result.update(probes=probe_values(task, ref_grade, start_grade), start_checks=start_grade["checks"],
                      reference_checks=ref_grade["checks"] if ref_grade else [])
        return finish("VALID" if valid else "INVALID", why, notes)
    except (OSError, RuntimeError, ValueError) as exc:
        return finish("ERROR", [f"the checker couldn't check it: {type(exc).__name__}: {str(exc)[:400]}"])
    finally:
        if own and not keep:
            builds.close()
