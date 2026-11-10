"""task-try.py's parts that need no Unity and no harness: the brief, the command lines, the workspace, the transcript
readers and a run's score."""

import contextlib
import hashlib
import io
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


def gone(pid, seconds=15):
    """Whether process `pid` has ended within `seconds` (a kill is asynchronous: the process ends a moment later)."""
    for _ in range(int(seconds / 0.1)):
        if not alive(pid):
            return True
        time.sleep(0.1)
    return False


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
def faked(agent, projects=None, editor="C:/U/Unity.exe", kill=False):
    """Unity and the harness faked: a side's project by its folder's name (a run's by its run folder), `agent` in place
    of run_agent. Nothing is looked for or stopped unless `kill` (kill_left_behind's process query takes a second or
    two, twice a try). Yields the projects."""
    projects = projects or {"start": FakeProject(measuring(-500)), "reference": FakeProject(measuring(100)),
                            "run1": FakeProject(measuring(-500)), "run2": FakeProject(measuring(90))}

    def project(folder, machine, label):
        folder = Path(folder)
        return projects[folder.name if folder.name in projects else folder.parent.name]

    with mock.patch.object(unity, "Project", project), mock.patch.object(trial, "run_agent", agent), \
            mock.patch.object(unity.Machine, "for_project",
                              classmethod(lambda cls, p, d=False: cls(Path(editor), None))), \
            mock.patch.object(trial, "kill_left_behind", trial.kill_left_behind if kill else lambda folder: []):
        yield projects


def answered(argv, cwd, prompt, transcript, minutes, env_extra=None):
    """An agent that changes nothing and stops."""
    Path(transcript).write_text(json.dumps({"type": "result", "num_turns": 1}))
    return {"exit_code": 0, "seconds": 60.0, "timed_out": False}


def stopped(timeout, scenes=()):
    """A build that stopped twice with no compiler error and no result saying why (unity.Project.build's `stopped`)."""
    return unity.Result(1, "Scripts have compiler errors.", 2.0,
                        stopped="Unity stopped twice (exit 1) with no compiler error and no result saying why")


def write(folder, *names, text="x"):
    for name in names:
        (Path(folder) / name).parent.mkdir(parents=True, exist_ok=True)
        (Path(folder) / name).write_text(text)


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

    def test_the_task_limits_override_the_schemas_defaults(self):
        self.assertEqual(trial.limits_of(task_with(probe())), {"max_turns": 200, "max_minutes": 240})
        task = dict(task_with(probe()), limits={"max_turns": 400, "max_minutes": 480})
        self.assertEqual(trial.limits_of(task)["max_minutes"], 480)

    def test_a_brief_names_only_what_the_task_sets(self):
        plain = trial.brief(task_with(probe()), self.EDITOR)
        self.assertNotIn("QA plays", plain, "no scene: the project's first build scene, as a player starts it")
        scene = trial.brief(task_with(probe(), play_scene="Assets/Scenes/Town.unity"), self.EDITOR)
        self.assertIn("from the scene `Assets/Scenes/Town.unity`.", scene)
        args = trial.brief(task_with(probe(), play_args=["-autoPlay"]), self.EDITOR)
        self.assertIn("QA plays the game with the arguments `-autoPlay`.", args)


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

    def test_the_agent_gets_the_prompt_on_stdin_and_recording_off(self):
        with tempfile.TemporaryDirectory() as tmp:
            script = ("import os,sys; print(sys.stdin.read().upper()); print(os.environ.get('GF_NO_RECORDING'))")
            out = Path(tmp) / "t.jsonl"
            ran = trial.run_agent([sys.executable, "-c", script], tmp, "fix it", out, 1)
            self.assertEqual(ran["exit_code"], 0)
            self.assertFalse(ran["timed_out"])
            self.assertEqual(out.read_text().split(), ["FIX", "IT", "1"])

    def test_both_factories_record_nothing_and_nothing_points_the_agent_at_the_answer(self):
        """The machine root, its config (which names the root), the deliverables (every game's history) and the
        organisation of the game repos stay out of the agent's environment."""
        with tempfile.TemporaryDirectory() as tmp:
            names = ("UGF_NO_RECORDING", "GF_NO_RECORDING", "UGF_ROOT", "UGF_CONFIG", "UGF_OUT", "UGF_ORG", "GF_ROOT",
                     "UNITY_RUN_REASON", "UE_RUN_REASON")
            script = f"import os; print(' '.join(os.environ.get(n, '-') for n in {names!r}))"
            out = Path(tmp) / "t.jsonl"
            planted = {"UGF_ROOT": "C:/UnityWork", "UGF_CONFIG": "C:/ugf/config.json", "UGF_OUT": "D:/deliveries",
                       "UGF_ORG": "studio", "GF_ROOT": "C:/Work", "UNITY_RUN_REASON": "x", "UE_RUN_REASON": "y"}
            with mock.patch.dict(os.environ, planted):
                ran = trial.run_agent([sys.executable, "-c", script], tmp, "fix it", out, 1)
            self.assertEqual(ran["exit_code"], 0)
            self.assertEqual(out.read_text().split(), ["1", "1"] + ["-"] * 7)

    @unittest.skipUnless(os.name == "nt", "taskkill")
    def test_an_agent_past_its_time_limit_is_stopped_with_what_it_started(self):
        with tempfile.TemporaryDirectory() as tmp:
            job = Path(tmp) / "job.pid"
            ran = trial.run_agent([sys.executable, "-c", STARTS_A_JOB, str(job)], tmp, "fix it", Path(tmp) / "t.jsonl",
                                  0.1)
            self.assertEqual((ran["exit_code"], ran["timed_out"]), (None, True))
            self.assertTrue(gone(int(job.read_text())), "the agent's own job goes with it")

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
                self.assertTrue(gone(started["agent"]), "no agent works on unattended")
                self.assertTrue(gone(int(job.read_text())), "nor anything it started")
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

    def test_a_place_is_found_however_a_shell_spells_it(self):
        """Claude Code's shell on Windows is Git Bash (/c/Users/...); every shell writes the home folder its own way."""
        repo = os.path.join(os.path.expanduser("~"), "UnityWork", "games", "stealth")
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / "t.jsonl"
            git_bash = "/" + repo[0].lower() + repo[2:].replace("\\", "/")
            for said in (f"ls {git_bash}/Assets", "cat ~/UnityWork/games/stealth/README.md",
                         "dir $HOME\\UnityWork\\games\\stealth", "ls ${HOME}/UnityWork/games/stealth",
                         "Get-ChildItem $env:USERPROFILE\\UnityWork\\games\\stealth",
                         "type %USERPROFILE%\\UnityWork\\games\\stealth\\README.md",
                         "ls $USERPROFILE/UnityWork/games/stealth", "ls ${USERPROFILE}/UnityWork/games/stealth",
                         "Get-Item ${env:USERPROFILE}\\UnityWork\\games\\stealth",
                         "open " + os.path.join(repo.replace("\\", "/"), "Assets"), "cd " + repo.replace("\\", "/", 3),
                         json.dumps({"path": repo})):  # Python's join; a path half each way; JSON inside JSON
                f.write_text(json.dumps({"cmd": said}))
                self.assertEqual(trial.peeked(f, [repo]), [repo], said)
            f.write_text(json.dumps({"cmd": "ls ~/UnityWork/games/other"}))
            self.assertEqual(trial.peeked(f, [repo]), [])

    def test_a_place_counts_only_as_a_whole_name(self):
        """A watched place that begins another path's name is no mention of it: Claude Code's own config is
        ~/.claude.json, a game's neighbour may be named like it, and a scratch folder beside the machine root names
        it in every transcript (the agent's own folder)."""
        home = os.path.expanduser("~")
        repo, root, claude = (os.path.join(home, "UnityWork", "games", "stealth"), os.path.join(home, "UnityWork"),
                              os.path.join(home, ".claude"))
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / "t.jsonl"
            for said, place in (("cat ~/.claude.json", claude), (os.path.join(home, ".claude.json"), claude),
                                (repo + "-two\\Assets", repo), (repo + "_old", repo),
                                (os.path.join(root + "-tries", "1a2b3c4d", "run1", "stealth"), root)):
                f.write_text(json.dumps({"cwd": said}))
                self.assertEqual(trial.peeked(f, [place]), [], said)
            for said in (repo, repo + ".", f"'{repo}'", repo + "\\", os.path.join(claude, "projects")):
                f.write_text(json.dumps({"cmd": f"ls {said} and more"}))
                self.assertTrue(trial.peeked(f, [repo, root, claude]), said)


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

    def test_nothing_of_the_answer_reaches_the_workspace_and_its_lfs_files_are_copies(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo, _, _, data = make_game(tmp)
            write(repo, "History/git.log", "Dataset/manifest.json", "Dataset.zip")
            git(repo, "add", "-A")
            git(repo, "commit", "-q", "-m", "the dataset")
            start = git(repo, "rev-parse", "HEAD")
            write(repo, "Assets/Scripts/Metro.cs", text="class Metro { int fixedAtLast = 1; }\n")
            git(repo, "commit", "-q", "-am", "the fix")
            git(repo, "branch", "tasks")
            fix = git(repo, "rev-parse", "HEAD:Assets/Scripts/Metro.cs")
            dest = Path(tmp) / "ws" / "metro-runner"
            trial.workspace(repo, start, dest)
            self.assertEqual([n for n in ("Tasks", "History", "Dataset", "Dataset.zip") if (dest / n).exists()], [])
            self.assertNotEqual(subprocess.run(["git", "-C", str(dest), "cat-file", "-e", fix]).returncode, 0,
                                "no object of the fix")
            self.assertEqual(git(dest, "for-each-ref", "--format=%(refname)"), "refs/heads/main", "no tasks branch")
            self.assertEqual((git(dest, "remote"), len(git(dest, "reflog").splitlines())), ("", 1))
            texture = dest / "Assets" / "Textures" / "Wall.png"
            self.assertEqual(texture.read_bytes(), data)
            self.assertEqual(os.stat(texture).st_nlink, 1, "the agent edits a copy, never the repo's LFS object")
            oid = hashlib.sha256(data).hexdigest()
            self.assertEqual((dest / ".git" / "lfs" / "objects" / oid[:2] / oid[2:4] / oid).read_bytes(), data)


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

            def project(folder, machine, label):
                folder = Path(folder)
                return projects[folder.name if folder.name in projects else folder.parent.name]

            def agent(argv, cwd, prompt, transcript, minutes, env_extra=None):
                Path(transcript).write_text(json.dumps({"type": "result", "num_turns": 12, "total_cost_usd": 1.5}))
                return {"exit_code": 0, "seconds": 60.0, "timed_out": False}

            with mock.patch.object(unity, "Project", project), mock.patch.object(trial, "run_agent", agent), \
                    mock.patch.object(unity.Machine, "for_project",
                                      classmethod(lambda cls, p, d=False: cls(Path("C:/U/Unity.exe"), None))):
                result = trial.try_task(repo, task, json.dumps(task).encode(), Path(tmp) / "scratch",
                                        Path(tmp) / "out", "claude", "claude", runs=2, places=[repo],
                                        log=lambda *a: None)
            self.assertEqual((result["status"], result["solved"]), ("DONE", 1), result["reasons"])
            self.assertEqual([r["solved"] for r in result["runs"]], [False, True])
            self.assertEqual(result["runs"][1]["turns"], 12)
            self.assertEqual(result["runs"][0]["milestones"], {"graded": False})
            self.assertEqual(projects["run2"].scenes, [["Assets/Scenes/Town.unity"]], "the play scene is built")
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

    def test_the_answer_is_gone_before_an_agent_starts(self):
        """The reference copy (the fix) and the copies' logs (the grader's queries) would lie two folders above the
        agent's own: every threshold is measured first, then both copies go."""
        with tempfile.TemporaryDirectory() as tmp:
            repo, task = tried(tmp)
            scratch, seen = Path(tmp) / "scratch", {}

            def agent(argv, cwd, prompt, transcript, minutes, env_extra=None):
                seen.update(start=(scratch / "start").exists(), reference=(scratch / "reference").exists(),
                            measured=len(projects["start"].plays) + len(projects["reference"].plays))
                return answered(argv, cwd, prompt, transcript, minutes)

            with faked(agent) as projects:
                result = trial.try_task(repo, task, b"{}", scratch, Path(tmp) / "out", "claude", "claude",
                                        log=lambda *a: None)
            self.assertEqual(result["status"], "DONE", result["reasons"])
            self.assertEqual(seen, {"start": False, "reference": False, "measured": 2})
            self.assertEqual(result["runs"][0]["milestones"], {"graded": False}, "graded on the thresholds measured")

    def test_a_run_is_graded_without_the_agents_library_and_build_outputs(self):
        """Library holds the agent's editor state besides the import cache (build profiles with their own defines and
        scenes, compiled scripts), which a game's files never carry: the grade imports everything again."""
        with tempfile.TemporaryDirectory() as tmp:
            repo, task = tried(tmp)
            at_grade = {}

            def agent(argv, cwd, prompt, transcript, minutes, env_extra=None):
                write(cwd, "Library/BuildProfiles/PlatformProfile.asset", "Library/Artifacts/a2", "Temp/t",
                      "Build/Game.exe", "Assets/Scripts/Fix.cs", text="the agent's")
                return answered(argv, cwd, prompt, transcript, minutes)

            def graded(name, folder, *rest):
                if name.startswith("run"):
                    at_grade[name] = sorted(p.relative_to(folder).as_posix() for d in ("Library", "Temp", "Build")
                                            for p in (Path(folder) / d).rglob("*") if p.is_file())
                    at_grade["work"] = (Path(folder) / "Assets" / "Scripts" / "Fix.cs").is_file()
                return original(name, folder, *rest)

            original = trial.side
            with faked(agent), mock.patch.object(trial, "side", graded):
                result = trial.try_task(repo, task, b"{}", Path(tmp) / "scratch", Path(tmp) / "out", "claude",
                                        "claude", log=lambda *a: None)
            self.assertEqual(result["status"], "DONE", result["reasons"])
            self.assertEqual(at_grade, {"run1": [], "work": True}, "its work is graded, never its editor's state")

    def test_the_agents_command_line_names_neither_the_repo_nor_the_results(self):
        """An agent that lists processes (to stop a stray editor, say) sees its own command line: the settings file
        that turns its hooks off lies in the try's folder, not beside the results in the game repo."""
        with tempfile.TemporaryDirectory() as tmp:
            repo, task = tried(tmp)
            out, seen = Path(tmp) / "repo-results", {}

            def agent(argv, cwd, prompt, transcript, minutes, env_extra=None):
                settings = Path(argv[argv.index("--settings") + 1])
                seen.update(outside=trial.outside(settings, [repo, out]),
                            settings=json.loads(settings.read_text(encoding="utf-8")))
                return answered(argv, cwd, prompt, transcript, minutes)

            with faked(agent):
                result = trial.try_task(repo, task, b"{}", Path(tmp) / "scratch", out, "claude", "claude",
                                        log=lambda *a: None)
            self.assertEqual(result["status"], "DONE", result["reasons"])
            self.assertEqual(seen, {"outside": True, "settings": {"disableAllHooks": True}})

    def test_the_brief_names_the_editor_of_the_start(self):
        """The workspace is the start: when the thread moved the game to another 6000.3 release, the agent is still
        given the start's editor, not the reference's."""
        with tempfile.TemporaryDirectory() as tmp:
            repo, task = tried(tmp)
            editors = {"start": "C:/Unity/6000.3.26f1/Editor/Unity.exe",
                       "reference": "C:/Unity/6000.3.28f1/Editor/Unity.exe"}
            machine = classmethod(lambda cls, p, d=False: cls(Path(editors.get(Path(p).name, "C:/U/Unity.exe")), None))
            with faked(answered), mock.patch.object(unity.Machine, "for_project", machine):
                result = trial.try_task(repo, task, b"{}", Path(tmp) / "scratch", Path(tmp) / "out", "claude",
                                        "claude", log=lambda *a: None)
            self.assertEqual(result["status"], "DONE", result["reasons"])
            brief = (Path(tmp) / "out" / "probe-task" / "brief.md").read_text(encoding="utf-8")
            self.assertIn(str(Path(editors["start"])), brief)
            self.assertNotIn("6000.3.28f1", brief)

    def test_a_run_whose_unity_isnt_installed_is_not_solved_and_the_try_goes_on(self):
        """The agent moved the project to a 6000.3 release this machine doesn't have: that run fails, not the try."""
        with tempfile.TemporaryDirectory() as tmp:
            repo, task = tried(tmp)
            real = unity.Machine.for_project

            def agent(argv, cwd, prompt, transcript, minutes, env_extra=None):
                (Path(cwd) / "ProjectSettings" / "ProjectVersion.txt").write_text("m_EditorVersion: 6000.3.99f1\n")
                return answered(argv, cwd, prompt, transcript, minutes)

            def machine(cls, project, direct=False):
                return real(project, direct) if Path(project).parent.name.startswith("run") else \
                    cls(Path("C:/U/Unity.exe"), None)

            with faked(agent), mock.patch.object(unity.Machine, "for_project", classmethod(machine)):
                result = trial.try_task(repo, task, b"{}", Path(tmp) / "scratch", Path(tmp) / "out", "claude",
                                        "claude", runs=2, log=lambda *a: None)
            self.assertEqual(result["status"], "DONE", result["reasons"])
            self.assertEqual([(r["solved"], r["required"]) for r in result["runs"]], [(False, None), (False, None)])
            self.assertIn("6000.3.99f1", result["runs"][0]["why"])

    def test_a_run_whose_build_stops_with_no_word_fails_alone_and_the_machines_faults_stop_the_try(self):
        """A build stopped with no compiler error and no result (unity.BuildStopped) is no verdict on the start or the
        reference, but in a run the agent may be why (a broken Packages/manifest.json logs no compiler error either):
        that run fails with the reason and the next is tried. The machine's own faults stay the try's error."""
        with tempfile.TemporaryDirectory() as tmp:
            repo, task = tried(tmp)
            with faked(answered) as projects:
                projects["run1"].build = stopped
                result = trial.try_task(repo, task, b"{}", Path(tmp) / "scratch", Path(tmp) / "out", "claude",
                                        "claude", runs=2, log=lambda *a: None)
            self.assertEqual(result["status"], "DONE", result["reasons"])
            self.assertEqual([(r["solved"], r["required"]) for r in result["runs"]], [(False, None), (True, 1)])
            kept = Path(tmp) / "out" / "probe-task" / "run1" / "build" / "build.log"
            self.assertTrue(result["runs"][0]["why"].startswith("the agent's game (run1) didn't build: Unity stopped "
                                                                "twice"), result["runs"][0]["why"])
            self.assertIn(str(kept), result["runs"][0]["why"])
            self.assertTrue(kept.is_file(), "the log its reason names")

            def unlicensed(timeout, scenes=()):
                raise unity.Unlicensed('Unity has no active licence (exit 198, "No valid Unity Editor license")')

            with faked(answered) as projects:
                projects["run1"].build = unlicensed
                result = trial.try_task(repo, task, b"{}", Path(tmp) / "scratch2", Path(tmp) / "out", "claude",
                                        "claude", runs=2, log=lambda *a: None)
            self.assertEqual((result["status"], result["runs"]), ("ERROR", []))
            self.assertIn("Unlicensed", result["reasons"][0])

    def test_a_start_or_reference_whose_build_stops_with_no_word_is_the_trys_error_naming_its_log(self):
        for which, game in (("start", "the game as the task started"), ("reference", "the reference game")):
            with tempfile.TemporaryDirectory() as tmp:
                repo, task = tried(tmp)
                agents = []

                def agent(*args, **kwargs):
                    agents.append(args)
                    return answered(*args, **kwargs)

                with faked(agent) as projects:
                    projects[which].build = stopped
                    result = trial.try_task(repo, task, b"{}", Path(tmp) / "scratch", Path(tmp) / "out", "claude",
                                            "claude", log=lambda *a: None)
                self.assertEqual((result["status"], result["runs"], agents), ("ERROR", [], []), which)
                kept = Path(tmp) / "out" / "probe-task" / which / "build" / "build.log"
                self.assertIn(f"BuildStopped: {game} didn't build: Unity stopped twice", result["reasons"][0])
                self.assertIn(str(kept), result["reasons"][0])
                self.assertTrue(kept.is_file(), "the log the reason names is there after the try")


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

    def test_a_run_whose_agent_failed_says_nothing_about_length(self):
        """An agent that stopped with an error (one that couldn't start, or ran out of turns) says nothing either."""
        run = {"required_passed": 0, "required": 3, "peeked": [], "seconds": 0.2 * 60, "exit_code": 1}
        result = {"status": "DONE", "task": "t", "solved": 0, "runs": [run]}
        self.assertNotIn("25-minute guide", trial.line(result))
        run["exit_code"] = 0
        self.assertIn("longest run 0.2 min", trial.line(result))


class CodexHome(unittest.TestCase):
    def setUp(self):
        patched = mock.patch.dict(os.environ)
        patched.start()
        self.addCleanup(patched.stop)
        os.environ.pop("CODEX_HOME", None)

    def test_codex_runs_on_a_copy_of_the_login_without_the_users_skills(self):
        with tempfile.TemporaryDirectory() as tmp:
            home, folder, kept = Path(tmp) / "user", Path(tmp) / "run1" / "game.codex-home", Path(tmp) / "evidence"
            write(home, ".codex/auth.json", text='{"token": "a"}')
            write(home, ".codex/skills/one/SKILL.md", ".agents/skills/two/SKILL.md")
            trial.clean_codex_home(folder, home)
            self.assertEqual((folder / "auth.json").read_text(), '{"token": "a"}')
            self.assertEqual((folder / "config.toml").read_text().count("enabled = false"), 2)
            (folder / "auth.json").write_text('{"token": "b"}')  # Codex refreshed it during the run
            write(folder, "sessions/2026/11/rollout.jsonl")
            trial.put_login_back(folder, home)
            trial.keep_codex_sessions(folder, kept)
            self.assertEqual((home / ".codex" / "auth.json").read_text(), '{"token": "b"}', "the refreshed login")
            self.assertFalse((folder / "auth.json").exists(), "no copy of the login stays behind")
            self.assertTrue((kept / "2026" / "11" / "rollout.jsonl").is_file())

    def test_a_login_codex_was_writing_when_it_was_stopped_never_replaces_the_users(self):
        with tempfile.TemporaryDirectory() as tmp:
            home, folder = Path(tmp) / "user", Path(tmp) / "run1" / "game.codex-home"
            write(home, ".codex/auth.json", text='{"token": "a"}')
            trial.clean_codex_home(folder, home)
            (folder / "auth.json").write_text('{"tok')  # killed at its time limit mid-write
            trial.put_login_back(folder, home)
            self.assertEqual((home / ".codex" / "auth.json").read_text(), '{"token": "a"}')
            self.assertFalse((folder / "auth.json").exists())

    def test_a_skill_whose_path_has_an_apostrophe_is_turned_off_too(self):
        """Codex reads its config whole: a path it can't parse (a user named O'Brien) would stop every run at once."""
        import tomllib

        with tempfile.TemporaryDirectory() as tmp:
            home, folder = Path(tmp) / "O'Brien", Path(tmp) / "run1" / "game.codex-home"
            write(home, ".codex/auth.json", text='{"token": "a"}')
            write(home, ".agents/skills/it's/SKILL.md", ".codex/skills/one/SKILL.md")
            trial.clean_codex_home(folder, home)
            config = tomllib.loads((folder / "config.toml").read_text(encoding="utf-8"))
            self.assertEqual(config["skills"]["config"],
                             [{"path": os.path.realpath(home / ".agents" / "skills" / "it's" / "SKILL.md"),
                               "enabled": False},
                              {"path": os.path.realpath(home / ".codex" / "skills" / "one" / "SKILL.md"),
                               "enabled": False}])
            trial.put_login_back(folder, home)


class Main(unittest.TestCase):
    def test_the_transcript_is_read_for_every_place_that_holds_the_answer_or_its_measures(self):
        """The game repo, the machine root, the harnesses' homes (the game sessions' transcripts), the repo's other
        worktrees (its tasks branch is checked out in one), a task file's folder and the results folder (the start's
        and the reference's plays, earlier results) wherever it is."""
        with tempfile.TemporaryDirectory() as tmp:
            repo, task = tried(tmp)
            given = Path(tmp) / "tasks" / "metro-runner" / "Tasks" / "probe-task.json"
            given.parent.mkdir(parents=True)
            given.write_text(json.dumps(task), encoding="utf-8")
            elsewhere = Path(tmp) / "elsewhere" / "metro-runner-tasks"   # a tasks worktree outside the machine root
            git(repo, "worktree", "add", "--detach", str(elsewhere))
            seen = {}

            def try_task(repo, task, raw, scratch, out, agent, exe, **options):
                seen.update(places=[str(p) for p in options["places"]], scratch=scratch)
                return {"status": "DONE", "task": task["name"], "runs": [], "solved": 0}

            root, out = Path(tmp) / "root", Path(tmp) / "results"
            with mock.patch.object(trial, "try_task", try_task), \
                    mock.patch.object(trial.shutil, "which", lambda a: a), \
                    mock.patch.object(unity.ugfroot, "root", lambda: str(root)), \
                    mock.patch.object(unity.ugfroot, "check_free", lambda *a: 100.0), \
                    contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                code = trial.main([str(repo), "--task", str(given), "--agent", "claude", "--out", str(out),
                                   "--scratch", str(Path(tmp) / "tries")])
            self.assertEqual(code, 0)
            home = Path(os.path.expanduser("~"))
            self.assertEqual(seen["places"], [str(p) for p in (repo.resolve(), Path(os.path.realpath(root)),
                                                               out.resolve(), home / ".agents", home / ".claude",
                                                               home / ".codex", elsewhere.resolve(),
                                                               given.parent.parent.resolve())])
            self.assertEqual(seen["scratch"].parent, Path(tmp, "tries").resolve(), "a folder of its own in --scratch")

    def test_the_agents_folder_is_never_in_a_watched_place_nor_the_results_in_it(self):
        """The results hold the start's and the reference's plays and earlier results, and a tasks worktree the answers:
        an agent working in either could read them (and every transcript would name a watched place), and results
        inside the scratch folder lie a few folders above the agent's own."""
        with tempfile.TemporaryDirectory() as tmp:
            repo, task = tried(tmp)
            given = Path(tmp) / "given" / "Tasks" / "probe-task.json"
            given.parent.mkdir(parents=True)
            given.write_text(json.dumps(task), encoding="utf-8")
            tries, elsewhere = Path(tmp) / "tries", Path(tmp) / "elsewhere" / "metro-runner-tasks"
            git(repo, "worktree", "add", "--detach", str(elsewhere))
            for out, scratch in ((tries, tries), (tries, tries / "s"), (tries / "results", tries),
                                 (Path(tmp) / "results", elsewhere / "s")):
                said = io.StringIO()
                with mock.patch.object(trial, "try_task", lambda *a, **k: self.fail("no try")), \
                        mock.patch.object(trial.shutil, "which", lambda a: a), \
                        mock.patch.object(unity.ugfroot, "root", lambda: str(Path(tmp) / "root")), \
                        mock.patch.object(unity.ugfroot, "check_free", lambda *a: 100.0), \
                        contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(said), \
                        self.assertRaises(SystemExit) as stopped:
                    trial.main([str(repo), "--task", str(given), "--agent", "claude", "--out", str(out),
                                "--scratch", str(scratch)])
                self.assertEqual(stopped.exception.code, 2, (out, scratch))
                self.assertIn("pass --scratch", said.getvalue())


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
                with faked(agent, kill=True), self.assertRaises(KeyboardInterrupt):
                    trial.try_task(repo, task, b"{}", Path(tmp) / "scratch", Path(tmp) / "out", "claude", "claude",
                                   log=lambda *a: None)
                self.assertTrue(gone(jobs[0].pid), "nothing of the try runs on")
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
                with faked(agent), mock.patch.object(seeds, "HELD", 0.5):  # (not 10 s for each folder it can't delete)
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
                    at_grade.update(temp=os.path.lexists(Path(folder) / "Temp"),
                                    build=(Path(folder) / "Build").exists())
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
                with faked(agent, kill=True):
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

    @unittest.skipUnless(os.name == "nt", "junctions")
    def test_a_game_folder_swapped_for_a_link_is_not_graded_and_nothing_is_written_through_it(self):
        """The probe package goes into Packages/ and the grade's Unity writes under Assets/ and ProjectSettings/: with
        one of them a link, that would be someone else's folder."""
        with tempfile.TemporaryDirectory() as tmp:
            repo, task = tried(tmp)
            elsewhere = Path(tmp) / "elsewhere"
            elsewhere.mkdir()

            def agent(argv, cwd, prompt, transcript, minutes, env_extra=None):
                shutil.rmtree(Path(cwd) / "Packages", ignore_errors=True)
                _winapi.CreateJunction(str(elsewhere), str(Path(cwd) / "Packages"))
                return answered(argv, cwd, prompt, transcript, minutes)

            with faked(agent):
                result = trial.try_task(repo, task, b"{}", Path(tmp) / "scratch", Path(tmp) / "out", "claude",
                                        "claude", log=lambda *a: None)
            self.assertEqual(result["status"], "DONE", result["reasons"])
            self.assertFalse(result["runs"][0]["solved"])
            self.assertIn("Packages is now a link", result["runs"][0]["why"])
            self.assertEqual(list(elsewhere.iterdir()), [], "nothing is added to the folder the link points at")

    @unittest.skipUnless(os.name == "nt", "taskkill, Win32_Process")
    def test_what_the_try_stops_names_its_folder_whole_in_either_spelling(self):
        """A process names the folder when its command line has the folder's whole name, as Windows or Git Bash (Claude
        Code's shell) writes it; one in a folder whose name merely starts the same is someone else's."""
        with tempfile.TemporaryDirectory() as tmp:
            mine = Path(tmp) / "s"
            git_bash = "/" + str(mine)[0].lower() + str(mine)[2:].replace("\\", "/") + "/Logs/x"
            names = {"inside": str(mine / "Logs" / "x"), "git bash": git_bash, "bystander": str(mine) + "2\\x"}
            procs = {k: subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)", v],
                                         creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))
                     for k, v in names.items()}
            try:
                stopped = trial.kill_left_behind(mine)
                self.assertEqual(sorted(stopped), sorted([procs["inside"].pid, procs["git bash"].pid]))
                self.assertTrue(alive(procs["bystander"].pid), "someone else's folder s2")
            finally:
                for p in procs.values():
                    p.kill()
                    p.wait(timeout=30)

    def test_a_name_that_would_climb_out_of_the_try_removes_nothing(self):
        """The task's name and its game's name make the paths the try deletes (<out>\\<name>, <scratch>\\run1\\<game>):
        the task's schema refuses them before anything is removed."""
        with tempfile.TemporaryDirectory() as tmp:
            repo, task = tried(tmp)
            write(tmp, "keep.txt")
            for bad in (dict(task, name=".."), dict(task, seed={**task["seed"], "game": ".."})):
                with faked(answered):
                    result = trial.try_task(repo, bad, b"{}", Path(tmp) / "out" / "scratch", Path(tmp) / "out",
                                            "claude", "claude", log=lambda *a: None)
                self.assertEqual(result["status"], "ERROR")
                self.assertIn("doesn't validate", result["reasons"][0])
                self.assertTrue((Path(tmp) / "keep.txt").is_file())

    def test_a_task_that_doesnt_validate_names_no_file_outside_its_results(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "results" / "out"
            for task in ({"name": "a/b"}, {"name": "../../escaped"}, {"name": "con?"}, {"title": "no name"},
                         {"name": 7}):
                result = trial.try_task(tmp, task, b"{}", Path(tmp) / "s", out, "claude", "claude", log=lambda *a: None)
                self.assertEqual(result["status"], "ERROR", task)
            self.assertEqual([p.name for p in Path(tmp).rglob("*.json")], [], "no file under a name it can't have")
            trial.try_task(tmp, {"name": "fine-name"}, b"{}", Path(tmp) / "s", out, "claude", "claude",
                           log=lambda *a: None)
            self.assertTrue((out / "fine-name.json").is_file(), "a name of the schema's form has its result file")

    @unittest.skipUnless(sys.platform == "win32", "Windows file sharing")
    def test_an_earlier_tries_file_held_open_is_the_tasks_error_not_the_end_of_the_try(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo, task = tried(tmp)
            out = Path(tmp) / "out"
            shot = out / "probe-task" / "reference" / "look" / "shot_00.png"
            shot.parent.mkdir(parents=True)
            shot.write_bytes(b"png")
            ready = Path(tmp) / "ready"
            viewer = subprocess.Popen([sys.executable, "-c", "import sys, time; f = open(sys.argv[1], 'rb'); "
                                       "open(sys.argv[2], 'w').close(); time.sleep(60)", shot, ready])
            try:
                while viewer.poll() is None and not ready.exists():
                    time.sleep(0.05)
                with mock.patch.object(seeds, "HELD", 0.5), faked(answered):
                    result = trial.try_task(repo, task, b"{}", Path(tmp) / "s", out, "claude", "claude",
                                            log=lambda *a: None)
                self.assertEqual(result["status"], "ERROR")
                self.assertIn("shot_00.png", result["reasons"][0])
            finally:
                viewer.kill()
                viewer.wait()

    def test_a_try_in_a_folder_with_spaces_runs_its_agent_there_and_deletes_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo, task = tried(tmp)
            scratch, seen = Path(tmp) / "my tries" / "try 1", {}
            script = ("import json, os; open('agent was here.txt', 'w').write(os.getcwd()); "
                      "print(json.dumps({'type': 'result', 'num_turns': 3}))")

            def graded(name, folder, *rest):
                if name.startswith("run"):
                    seen["cwd"] = (Path(folder) / "agent was here.txt").read_text()
                return original(name, folder, *rest)

            original = trial.side
            with faked(trial.run_agent, kill=True), mock.patch.object(trial, "side", graded), \
                    mock.patch.object(trial, "agent_argv", lambda *a: [sys.executable, "-c", script]):
                result = trial.try_task(repo, task, b"{}", scratch, Path(tmp) / "out", "claude", "claude",
                                        log=lambda *a: None)
            self.assertEqual(result["status"], "DONE", result["reasons"])
            self.assertEqual((result["runs"][0]["exit_code"], result["runs"][0]["turns"]), (0, 3))
            self.assertEqual(seen["cwd"].lower(), str(scratch / "run1" / "metro-runner").lower())
            self.assertFalse(scratch.exists())

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
