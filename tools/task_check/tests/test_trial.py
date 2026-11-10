"""task-try.py's parts that need no Unity and no harness: the brief, the command lines, the workspace, the transcript
readers and a run's score."""

import json
import os
import shutil
import subprocess
import sys
import tempfile
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


if __name__ == "__main__":
    unittest.main()
