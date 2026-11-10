"""task-try.py's parts that need no Unity and no harness: the brief, the command lines, the workspace, the transcript
readers and a run's score."""

import contextlib
import json
import os

try:
    import _winapi  # junctions, as an agent can make them without the right to make symlinks
except ImportError:
    _winapi = None
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

from unittest import mock

from helpers import FakeProject, checked, measuring, probe, task_with
from test_check import fake_probe_package, make_game

from task_check import seeds, trial, unity

_probe_patch = None


def setUpModule():
    global _probe_patch
    folder = tempfile.mkdtemp()
    _probe_patch = mock.patch.object(seeds, "PROBE_SOURCE", fake_probe_package(folder))
    _probe_patch.start()
    _probe_patch.folder = folder


def tearDownModule():
    _probe_patch.stop()
    shutil.rmtree(_probe_patch.folder, ignore_errors=True)


def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=True).stdout.strip()


def alive(pid):
    """Whether process `pid` still runs (Windows: os.kill would end it)."""
    import ctypes

    kernel = ctypes.windll.kernel32
    handle = kernel.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
    if not handle:
        return False
    code = ctypes.c_ulong()
    kernel.GetExitCodeProcess(handle, ctypes.byref(code))
    kernel.CloseHandle(handle)
    return code.value == 259  # STILL_ACTIVE


# An agent that starts a job of its own (a Unity editor, say), writes the job's pid to argv[1] and works on.
STARTS_A_JOB = ("import subprocess, sys, time; job = subprocess.Popen([sys.executable, '-c', 'import time; "
                "time.sleep(60)']); open(sys.argv[1], 'w').write(str(job.pid)); time.sleep(60)")


def tried(tmp, **seed):
    """The sample game and a calibrated task on it (start and fix commits)."""
    repo, start, fix, _ = make_game(tmp)
    task = task_with(probe(expect={"op": ">=", "calibrate": 0.5}))
    task["seed"] = {**task["seed"], "commit": start, "reference": fix, **seed}
    return repo, task


@contextlib.contextmanager
def faked(agent, projects=None, editor="C:/U/Unity.exe"):
    """Unity and the harness faked: a side's project by its folder's name (a run's by its run folder), `agent` in place
    of run_agent. Yields the projects."""
    projects = projects or {"start": FakeProject(measuring(-500)), "reference": FakeProject(measuring(100)),
                            "run1": FakeProject(measuring(-500)), "run2": FakeProject(measuring(90))}

    def project(folder, machine, label):
        folder = Path(folder)
        return projects[folder.name if folder.name in projects else folder.parent.name]

    with mock.patch.object(unity, "Project", project), mock.patch.object(trial, "run_agent", agent), \
            mock.patch.object(unity.Machine, "for_project", classmethod(lambda cls, p, d=False: cls(Path(editor), None))):
        yield projects


def answered(argv, cwd, prompt, transcript, minutes, env_extra=None):
    """An agent that changes nothing and stops."""
    Path(transcript).write_text(json.dumps({"type": "result", "num_turns": 1}))
    return {"exit_code": 0, "seconds": 60.0, "timed_out": False}


class Brief(unittest.TestCase):
    EDITOR = "C:/Program Files/Unity/Hub/Editor/6000.3.26f1/Editor/Unity.exe"

    def test_the_brief_is_the_instruction_where_qa_plays_and_where_unity_is(self):
        task = task_with(probe(), play_scene="Assets/Scenes/Town.unity", play_args=["-scenario", "2"])
        text = trial.brief(task, self.EDITOR)
        self.assertTrue(text.startswith("Keep the hero on the ground."))
        self.assertIn("QA plays the game from the scene `Assets/Scenes/Town.unity`, with the arguments "
                      "`-scenario 2`.", text)
        self.assertIn("the Unity 6000.3 project in the current folder", text)
        self.assertIn(f"`{self.EDITOR}`", text)
        self.assertNotIn("hero_on_ground", text, "nothing of the grader's half")

    def test_a_brief_names_only_what_the_task_sets(self):
        plain = trial.brief(task_with(probe()), self.EDITOR)
        self.assertNotIn("QA plays", plain, "no scene: the project's first build scene, as a player starts it")
        scene = trial.brief(task_with(probe(), play_scene="Assets/Scenes/Town.unity"), self.EDITOR)
        self.assertIn("from the scene `Assets/Scenes/Town.unity`.", scene)
        args = trial.brief(task_with(probe(), play_args=["-autoPlay"]), self.EDITOR)
        self.assertIn("QA plays the game with the arguments `-autoPlay`.", args)

    def test_the_task_limits_override_the_schemas_defaults(self):
        self.assertEqual(trial.limits_of(task_with(probe())), {"max_turns": 200, "max_minutes": 240})
        task = dict(task_with(probe()), limits={"max_turns": 400, "max_minutes": 480})
        self.assertEqual(trial.limits_of(task)["max_minutes"], 480)


class Harness(unittest.TestCase):
    def test_claude_runs_headless_with_its_turn_limit_and_no_hooks(self):
        argv = trial.agent_argv("claude", "claude.cmd", {"max_turns": 400}, "s.json", model="opus")
        self.assertEqual(argv[:2], ["claude.cmd", "-p"])
        self.assertIn("400", argv)
        self.assertEqual(argv[argv.index("--settings") + 1], "s.json")
        self.assertEqual(argv[argv.index("--model") + 1], "opus")

    def test_codex_runs_exec_with_full_access_reading_the_prompt_from_stdin(self):
        argv = trial.agent_argv("codex", "codex.cmd", {"max_turns": 400}, "s.json", extra=["-c", "x=1"])
        self.assertEqual(argv[:2], ["codex.cmd", "exec"])
        self.assertIn("danger-full-access", argv)
        self.assertEqual(argv[-3:], ["-c", "x=1", "-"])

    def test_an_unknown_agent_is_refused(self):
        with self.assertRaises(ValueError):
            trial.agent_argv("cursor", "x", {"max_turns": 1}, "s.json")

    def test_the_agent_gets_the_prompt_on_stdin_recording_off_and_no_machine_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            names = ("UGF_NO_RECORDING", "GF_NO_RECORDING", "UGF_ROOT", "GF_ROOT", "UNITY_RUN_REASON", "UE_RUN_REASON")
            script = ("import os,sys; print(sys.stdin.read().upper()); "
                      f"print(' '.join(os.environ.get(n, '-') for n in {names!r}))")
            out = Path(tmp) / "t.jsonl"
            planted = {"UGF_ROOT": "C:/UnityWork", "GF_ROOT": "C:/Work", "UNITY_RUN_REASON": "x", "UE_RUN_REASON": "y"}
            with mock.patch.dict(os.environ, planted):
                ran = trial.run_agent([sys.executable, "-c", script], tmp, "fix it", out, 1)
            self.assertEqual(ran["exit_code"], 0)
            self.assertFalse(ran["timed_out"])
            self.assertEqual(out.read_text().split(), ["FIX", "IT", "1", "1", "-", "-", "-", "-"])

    @unittest.skipUnless(os.name == "nt", "taskkill")
    def test_an_agent_past_its_time_limit_is_stopped_with_what_it_started(self):
        with tempfile.TemporaryDirectory() as tmp:
            job = Path(tmp) / "job.pid"
            ran = trial.run_agent([sys.executable, "-c", STARTS_A_JOB, str(job)], tmp, "fix it", Path(tmp) / "t.jsonl",
                                  0.1)
            self.assertEqual((ran["exit_code"], ran["timed_out"]), (None, True))
            self.assertFalse(alive(int(job.read_text())), "the agent's own job goes with it")

    @unittest.skipUnless(os.name == "nt", "taskkill")
    def test_an_interrupted_try_stops_the_agent_and_what_it_started(self):
        """Ctrl+C reaches the try only: the agent runs in a process group of its own, which Windows gives no Ctrl+C."""
        with tempfile.TemporaryDirectory() as tmp:
            job = Path(tmp) / "job.pid"
            started = {}
            real_wait = subprocess.Popen.wait

            def interrupted(proc, timeout=None):
                if timeout is None:
                    return real_wait(proc)
                started["agent"] = proc.pid
                for _ in range(600):  # the agent has started its job
                    if job.is_file() and job.read_text():
                        break
                    time.sleep(0.05)
                raise KeyboardInterrupt

            try:
                with mock.patch.object(subprocess.Popen, "wait", interrupted), self.assertRaises(KeyboardInterrupt):
                    trial.run_agent([sys.executable, "-c", STARTS_A_JOB, str(job)], tmp, "fix it",
                                    Path(tmp) / "t.jsonl", 60)
                time.sleep(0.5)
                self.assertFalse(alive(started["agent"]), "no agent works on unattended")
                self.assertFalse(alive(int(job.read_text())), "nor anything it started")
            finally:
                for pid in [started.get("agent")] + ([int(job.read_text())] if job.is_file() else []):
                    if pid:
                        subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)], capture_output=True)

    def test_an_agent_that_never_reads_its_prompt_is_stopped_on_time(self):
        with tempfile.TemporaryDirectory() as tmp:
            began = time.monotonic()
            ran = trial.run_agent([sys.executable, "-c", "import time; time.sleep(20)"], tmp, "x" * 20000,
                                  Path(tmp) / "t.jsonl", 0.05)
            self.assertTrue(ran["timed_out"])
            self.assertLess(time.monotonic() - began, 15, "a long prompt never holds the try past the time limit")

    def test_an_agent_that_stops_before_reading_its_prompt_is_a_run_that_says_why(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "t.jsonl"
            ran = trial.run_agent([sys.executable, "-c", "import sys; print('error: unknown option'); sys.exit(1)"],
                                  tmp, "x" * 20000, out, 1)
            self.assertEqual(ran["exit_code"], 1)
            self.assertIn("unknown option", out.read_text())


class Transcript(unittest.TestCase):
    def test_usage_reads_claudes_result_and_counts_codexs_turns(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / "t.jsonl"
            f.write_text("not json\n" + json.dumps({"type": "result", "num_turns": 37, "total_cost_usd": 4.2}) + "\n")
            self.assertEqual(trial.usage("claude", f), {"turns": 37, "usd": 4.2})
            f.write_text("\n".join(json.dumps({"type": t}) for t in ("turn.started", "turn.completed",
                                                                       "turn.completed")))
            self.assertEqual(trial.usage("codex", f), {"turns": 2, "usd": None})
            self.assertEqual(trial.usage("codex", Path(tmp) / "none"), {"turns": None, "usd": None})

    def test_a_transcript_naming_the_game_repo_is_flagged(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / "t.jsonl"
            f.write_text(json.dumps({"cmd": "git -C C:\\UnityWork\\games\\stealth log"}))
            self.assertEqual(trial.peeked(f, ["C:\\UnityWork\\games\\stealth", "C:\\UnityWork\\tasks\\stealth"]),
                             ["C:\\UnityWork\\games\\stealth"])
            f.write_text(json.dumps({"cmd": "cat c:/unitywork/tasks/stealth/Tasks/x.json"}))
            self.assertEqual(trial.peeked(f, ["C:\\UnityWork\\games\\stealth", "C:\\UnityWork\\tasks\\stealth"]),
                             ["C:\\UnityWork\\tasks\\stealth"])

    def test_a_workspace_inside_the_root_or_the_repo_is_not_outside(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertFalse(trial.outside(os.path.join(tmp, "a", "b"), [tmp]))
            self.assertTrue(trial.outside(tmp + "-other", [tmp]))


class Score(unittest.TestCase):
    def test_a_score_is_the_weighted_share_as_the_cloud_scores_it(self):
        grade = {"checks": [dict(checked("player_builds", "build", True), required=True, group="builds", weight=0),
                            dict(checked("hud", "probe", False), required=True, group="fixed", weight=3),
                            dict(checked("camera", "probe", False), required=True, group="fixed", weight=1),
                            dict(checked("runs", "probe", True), required=True, group="still_works", weight=0)]}
        self.assertEqual(trial.score(None, grade)["score"], 0.0, "a no-op scores nothing")
        grade["checks"][1]["passed"] = True
        self.assertEqual(trial.score(None, grade)["score"], 0.75)

    def test_solved_only_when_every_required_check_passes(self):
        grade = {"checks": [dict(checked("player_builds", "build", True), required=True, group="builds"),
                            dict(checked("hud", "probe", True), required=True, group="fixed"),
                            dict(checked("camera", "probe", False), required=True, group="fixed"),
                            dict(checked("taste", "judge", False), required=False, group="quality")]}
        self.assertEqual(trial.score(None, grade), {"solved": False, "score": 0.667, "required_passed": 2, "required": 3,
                                                    "milestones": {"builds": True, "fixed": False}})
        grade["checks"][2]["passed"] = True
        self.assertTrue(trial.score(None, grade)["solved"])


class Workspace(unittest.TestCase):
    def test_the_workspace_is_the_start_alone_in_a_fresh_repo(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "game"
            repo.mkdir()
            git(repo, "init", "-q", "-b", "main")
            (repo / "Assets" / "Scripts").mkdir(parents=True)
            (repo / "Assets" / "Scripts" / "Hero.cs").write_text("broken")
            (repo / "Tasks").mkdir()
            (repo / "Tasks" / "t.json").write_text("{}")
            git(repo, "add", "-A")
            git(repo, "-c", "user.name=a", "-c", "user.email=a@b", "commit", "-q", "-m", "start")
            start = git(repo, "rev-parse", "HEAD")
            (repo / "Assets" / "Scripts" / "Hero.cs").write_text("fixed")
            git(repo, "-c", "user.name=a", "-c", "user.email=a@b", "commit", "-qam", "the fix")
            dest = Path(tmp) / "ws" / "game"
            trial.workspace(repo, start, dest)
            self.assertEqual((dest / "Assets" / "Scripts" / "Hero.cs").read_text(), "broken")
            self.assertFalse((dest / "Tasks").exists(), "no tasks reach the agent")
            self.assertEqual(git(dest, "rev-list", "--count", "HEAD"), "1", "one commit, no history")
            self.assertEqual(git(dest, "status", "--porcelain"), "")

    def test_the_build_outputs_go_before_a_grade_and_the_import_cache_stays(self):
        self.assertEqual(set(trial.BUILT), {"Temp", "Obj", "Logs", "Build", "Builds"})
        self.assertNotIn("Library", trial.BUILT)


class Whole(unittest.TestCase):
    def test_runs_graded_against_the_start_and_the_reference(self):
        """Two runs: the first leaves the game as it started, the second fixes it; Unity and the harness faked."""
        with tempfile.TemporaryDirectory() as tmp:
            repo, start, fix, _ = make_game(tmp)
            task = task_with({"kind": "build", "name": "player_builds"},
                             probe(expect={"op": ">=", "calibrate": 0.5}, needs=["player_builds"]),
                             play_scene="Assets/Scenes/Town.unity")
            task["seed"] = {**task["seed"], "commit": start, "reference": fix}
            projects = {"start": FakeProject(measuring(-500)), "reference": FakeProject(measuring(100)),
                        "run1": FakeProject(measuring(-500)), "run2": FakeProject(measuring(90))}
            left = {}

            def project(folder, machine, label):
                folder = Path(folder)
                return projects[folder.name if folder.name in projects else folder.parent.name]

            def agent(argv, cwd, prompt, transcript, minutes, env_extra=None):
                Path(transcript).write_text(json.dumps({"type": "result", "num_turns": 12, "total_cost_usd": 1.5}))
                for d in ("Library", "Temp", "Build"):  # what an agent that opened Unity and built leaves behind
                    (Path(cwd) / d).mkdir()
                    (Path(cwd) / d / "x").write_text("x")
                left[Path(cwd).parent.name] = Path(cwd)
                return {"exit_code": 0, "seconds": 60.0, "timed_out": False}

            def graded(name, folder, *rest):
                if name.startswith("run"):
                    left[name] = sorted(p.name for p in Path(folder).iterdir() if p.name in ("Library", "Temp", "Build"))
                return original(name, folder, *rest)

            original = trial.side
            with mock.patch.object(unity, "Project", project), mock.patch.object(trial, "run_agent", agent), \
                    mock.patch.object(trial, "side", graded), \
                    mock.patch.object(unity.Machine, "for_project",
                                      classmethod(lambda cls, p, d=False: cls(Path("C:/U/Unity.exe"), None))):
                result = trial.try_task(repo, task, json.dumps(task).encode(), Path(tmp) / "scratch",
                                        Path(tmp) / "out", "claude", "claude", runs=2, places=[repo],
                                        log=lambda *a: None)
            self.assertEqual((result["status"], result["solved"]), ("DONE", 1), result["reasons"])
            self.assertEqual([r["solved"] for r in result["runs"]], [False, True])
            self.assertEqual(result["runs"][1]["turns"], 12)
            self.assertEqual(result["runs"][0]["milestones"], {"graded": False})
            self.assertEqual(left["run1"], ["Library"], "the build outputs are removed, the import cache kept")
            self.assertEqual(projects["run2"].scenes, [["Assets/Scenes/Town.unity"]])
            brief = (Path(tmp) / "out" / "probe-task" / "brief.md").read_text(encoding="utf-8")
            self.assertIn("`Assets/Scenes/Town.unity`", brief)
            self.assertIn(str(Path("C:/U/Unity.exe")), brief)
            self.assertFalse((Path(tmp) / "scratch").exists(), "the workspaces are deleted")
            self.assertIn("1/2 solved", trial.line(result))

    def test_a_task_without_a_reference_is_not_tried(self):
        with tempfile.TemporaryDirectory() as tmp:
            task = task_with(probe(), seed={"game": "metro-runner", "commit": "a" * 40, "kind": "feature"})
            result = trial.try_task(tmp, task, b"{}", Path(tmp) / "s", Path(tmp) / "out", "codex", "codex",
                                    log=lambda *a: None)
            self.assertEqual(result["status"], "ERROR")
            self.assertIn("seed.reference", result["reasons"][0])

    def test_a_workspace_path_too_long_for_unity_stops_the_try_before_it_builds(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo, start, fix, _ = make_game(tmp)
            task = task_with(probe(expect={"op": ">=", "calibrate": 0.5}))
            task["seed"] = {**task["seed"], "commit": start, "reference": fix}
            with mock.patch.object(trial, "side", lambda *a: self.fail("nothing is built")):
                result = trial.try_task(repo, task, b"{}", Path(tmp) / ("s" * 80), Path(tmp) / "out", "claude",
                                        "claude", log=lambda *a: None)
            self.assertEqual(result["status"], "ERROR")
            self.assertIn("PathTooLong", result["reasons"][0])
            self.assertIn("--scratch", result["reasons"][0])


class LongEnough(unittest.TestCase):
    def test_the_line_says_when_the_longest_run_is_too_short(self):
        run = {"required_passed": 2, "required": 3, "peeked": [], "seconds": 24.9 * 60}
        result = {"status": "DONE", "task": "t", "solved": 0, "runs": [run]}
        self.assertIn("longest run 24.9 min: under the 25-minute guide (a guide, not a requirement)", trial.line(result))
        run["seconds"] = 25 * 60
        self.assertNotIn("25-minute guide", trial.line(result))

    def test_a_run_stopped_by_its_time_limit_says_nothing_about_length(self):
        run = {"required_passed": 2, "required": 3, "peeked": [], "seconds": 10 * 60, "timed_out": True}
        result = {"status": "DONE", "task": "t", "solved": 0, "runs": [run]}
        self.assertNotIn("25-minute guide", trial.line(result))


class CleanUp(unittest.TestCase):
    @unittest.skipUnless(os.name == "nt", "taskkill, Win32_Process")
    def test_an_interrupted_try_stops_what_still_runs_in_its_folder_and_deletes_it(self):
        """Ctrl+C reaches the try, not its Unity jobs (each has a process group of its own): one that holds a file in
        the try's folder is stopped before the folder goes, and the interruption goes on up."""
        with tempfile.TemporaryDirectory() as tmp:
            repo, task = tried(tmp)
            jobs = []

            def agent(argv, cwd, prompt, transcript, minutes, env_extra=None):
                held = Path(cwd) / "held.txt"
                jobs.append(subprocess.Popen([sys.executable, "-c", "import sys, time; f = open(sys.argv[1], 'w'); "
                                              "f.write('x'); f.flush(); time.sleep(60)", str(held)],
                                             creationflags=subprocess.CREATE_NEW_PROCESS_GROUP))
                for _ in range(200):
                    if held.is_file() and held.stat().st_size:
                        break
                    time.sleep(0.05)
                raise KeyboardInterrupt

            try:
                with faked(agent), self.assertRaises(KeyboardInterrupt):
                    trial.try_task(repo, task, b"{}", Path(tmp) / "scratch", Path(tmp) / "out", "claude", "claude",
                                   log=lambda *a: None)
                self.assertFalse(alive(jobs[0].pid), "nothing of the try runs on")
                self.assertFalse((Path(tmp) / "scratch").exists(), "the try's folder is deleted")
            finally:
                for job in jobs:
                    subprocess.run(["taskkill", "/F", "/T", "/PID", str(job.pid)], capture_output=True)
                    job.wait(timeout=30)

    @unittest.skipUnless(os.name == "nt", "Windows keeps an open file")
    def test_a_folder_the_try_cant_delete_is_reported_and_the_result_kept(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo, task = tried(tmp)
            held, said = [], []

            def agent(argv, cwd, prompt, transcript, minutes, env_extra=None):
                held.append(open(Path(cwd) / "Assets" / "held.txt", "w"))  # something the try can't stop holds it
                return answered(argv, cwd, prompt, transcript, minutes)

            try:
                with faked(agent):
                    result = trial.try_task(repo, task, b"{}", Path(tmp) / "scratch", Path(tmp) / "out", "claude",
                                            "claude", log=said.append)
                self.assertEqual((result["status"], len(result["runs"])), ("DONE", 1), result["reasons"])
                self.assertTrue(any("couldn't delete" in s and "run1" in s for s in said), said)
            finally:
                for f in held:
                    f.close()

    @unittest.skipUnless(hasattr(_winapi, "CreateJunction"), "junctions")
    def test_a_link_in_place_of_a_build_output_goes_as_a_link_never_followed(self):
        """An agent may link Temp or Build elsewhere (or leave a junction inside them): the grade removes the link,
        never what it points at, and its Unity never writes through it."""
        with tempfile.TemporaryDirectory() as tmp:
            repo, task = tried(tmp)
            outside = {d: Path(tmp) / "elsewhere" / d for d in ("temp", "deep")}
            for folder in outside.values():
                folder.mkdir(parents=True)
                (folder / "keep.txt").write_text("x")
            at_grade = {}

            def agent(argv, cwd, prompt, transcript, minutes, env_extra=None):
                _winapi.CreateJunction(str(outside["temp"]), str(Path(cwd) / "Temp"))
                (Path(cwd) / "Build").mkdir()
                _winapi.CreateJunction(str(outside["deep"]), str(Path(cwd) / "Build" / "cache"))
                return answered(argv, cwd, prompt, transcript, minutes)

            def graded(name, folder, *rest):
                if name.startswith("run"):
                    at_grade.update(temp=os.path.lexists(Path(folder) / "Temp"), build=(Path(folder) / "Build").exists())
                return original(name, folder, *rest)

            original = trial.side
            with faked(agent), mock.patch.object(trial, "side", graded):
                result = trial.try_task(repo, task, b"{}", Path(tmp) / "scratch", Path(tmp) / "out", "claude",
                                        "claude", log=lambda *a: None)
            self.assertEqual(result["status"], "DONE", result["reasons"])
            self.assertEqual(at_grade, {"temp": False, "build": False}, "no link left for the grade to write through")
            self.assertTrue(all((f / "keep.txt").is_file() for f in outside.values()), "nothing outside is deleted")

    @unittest.skipUnless(hasattr(_winapi, "CreateJunction"), "junctions")
    def test_a_workspace_swapped_for_a_link_is_neither_cleaned_nor_graded(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo, task = tried(tmp)
            elsewhere = Path(tmp) / "elsewhere"
            (elsewhere / "Temp").mkdir(parents=True)
            (elsewhere / "Temp" / "keep.txt").write_text("x")

            def agent(argv, cwd, prompt, transcript, minutes, env_extra=None):
                Path(cwd).rename(Path(cwd).with_name("moved"))
                _winapi.CreateJunction(str(elsewhere), str(cwd))
                return answered(argv, cwd, prompt, transcript, minutes)

            # someone else's process at work in the other folder
            bystander = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)", str(elsewhere / "x")],
                                         creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))
            try:
                with faked(agent):
                    result = trial.try_task(repo, task, b"{}", Path(tmp) / "scratch", Path(tmp) / "out", "claude",
                                            "claude", log=lambda *a: None)
                self.assertTrue(alive(bystander.pid), "the try stops only what runs in its own folder")
            finally:
                bystander.kill()
                bystander.wait(timeout=30)
            self.assertEqual(result["status"], "DONE", result["reasons"])
            self.assertFalse(result["runs"][0]["solved"])
            self.assertIn("link", result["runs"][0]["why"])
            self.assertTrue((elsewhere / "Temp" / "keep.txt").is_file(), "the other folder's files stay")
            self.assertFalse((elsewhere / "Packages").exists(), "nothing is added to it either")

    def test_a_try_never_deletes_a_folder_it_did_not_make(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo, task = tried(tmp)
            mine = Path(tmp) / "mine"
            mine.mkdir()
            (mine / "keep.txt").write_text("x")
            with faked(answered):
                result = trial.try_task(repo, task, b"{}", mine, Path(tmp) / "out", "claude", "claude",
                                        log=lambda *a: None)
                self.assertEqual(result["status"], "ERROR")
                self.assertTrue((mine / "keep.txt").is_file())
                here = os.getcwd()
                os.chdir(mine)
                try:  # an empty path is the current folder
                    result = trial.try_task(repo, task, b"{}", "", Path(tmp) / "out", "claude", "claude",
                                            log=lambda *a: None)
                finally:
                    os.chdir(here)
            self.assertEqual(result["status"], "ERROR")
            self.assertIn("exists", result["reasons"][0])
            self.assertTrue((mine / "keep.txt").is_file(), "the working folder is never emptied")


if __name__ == "__main__":
    unittest.main()
