"""A task checked end to end with fake Unity: the sides' plays and builds, calibration, the grades, a whole check's
result file; a commit materialized from a real git repo; the files and command lines a build, a play and the editor
pass hand Unity."""

import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from helpers import NO_FIX, FakeProject, measuring, probe, ran, side, task_with

from task_check import check, cli, probes, seeds, tasks, unity

WALLS = {"component": "CastlePiece", "tag": "Wall"}
VERSION = "m_EditorVersion: 6000.3.26f1\nm_EditorVersionWithRevision: 6000.3.26f1 (0123456789ab)\n"
_probe_patch = None


def fake_probe_package(root):
    """A stand-in for tools/task_check/TaskProbe (the real package is C#, built by Unity): its files, and an IDE's
    leftovers that never reach a copy."""
    source = Path(root) / "TaskProbe"
    (source / "Runtime").mkdir(parents=True)
    (source / "package.json").write_text('{"name": "com.taskprobe", "version": "1.0.0"}', encoding="utf-8")
    (source / "Runtime" / "Probe.cs").write_text("namespace TaskProbe {}\n", encoding="utf-8")
    (source / "Runtime" / "Probe.cs.meta").write_text("guid: 0\n", encoding="utf-8")
    (source / "obj").mkdir()
    (source / "obj" / "junk.dll").write_bytes(b"x")
    return source


def setUpModule():
    global _probe_patch
    folder = tempfile.mkdtemp()
    _probe_patch = mock.patch.object(seeds, "PROBE_SOURCE", fake_probe_package(folder))
    _probe_patch.start()
    _probe_patch.folder = folder


def tearDownModule():
    _probe_patch.stop()
    shutil.rmtree(_probe_patch.folder, ignore_errors=True)


def grade(task, mode, start, reference=None, thresholds=None):
    return check.Grade(task, mode, start, reference, {} if thresholds is None else thresholds).run()


class Grades(unittest.TestCase):
    def test_a_literal_probe_passes_on_the_measured_number_and_its_queries_reach_the_probe(self):
        task = task_with(probe(), probe("walls", measure={"probe": "objects", "select": WALLS, "field": "y",
                                                          "of": "max"}, expect={"op": ">", "value": 100}),
                         probe("seen", measure={"probe": "camera", "field": "occluded", "agg": "any"},
                               expect={"op": "==", "value": 0}))
        game = FakeProject(measuring(120))
        found = grade(task, "reference", side("start", FakeProject(), task), side("reference", game, task))
        self.assertTrue(all(c["passed"] for c in found["checks"]), found["checks"])
        details = [c["detail"] for c in found["checks"]]
        self.assertEqual(details[0], "The hero stands on the ground. | measured 120, threshold >= 0")
        self.assertTrue(details[1].endswith("| measured 120, threshold > 100"))
        self.assertEqual(found["probes"]["walls"], {"value": 120.0, "threshold": 100.0, "start": None, "fix": None})
        (look,) = game.plays
        self.assertEqual((look["seconds"], look["shots"], look["inputs"]), (20, 6, None))
        self.assertEqual((look["scene"], look["args"], look["player"]), (None, [], None))
        self.assertEqual({q["kind"] for q in look["queries"]["queries"]}, {"objects", "camera"})

    def test_a_play_that_wrote_no_probe_fails_its_probes_saying_why(self):
        task = task_with(probe())
        found = grade(task, "reference", side("start", FakeProject(), task),
                      side("reference", FakeProject(measuring(0, crash=True)), task))
        self.assertFalse(found["checks"][0]["passed"])
        self.assertTrue(found["checks"][0]["detail"].endswith(
            "measured nothing, threshold >= 0: no samples in the window (the play wrote no probe file)"))

    def test_a_task_play_is_played_once_with_its_inputs_scene_args_and_sampling(self):
        play = {"name": "arena", "seconds": 8, "scene": "Assets/Scenes/Arena.unity", "args": ["-autoPlay"],
                "every": 0.25, "inputs": [{"t": 0.2, "teleport": [1, 2, 3], "yaw": 90},
                                          {"t": 1, "key": "<Mouse>/leftButton", "press": True}]}
        task = task_with(probe("a", play=play, measure={"probe": "objects", "select": WALLS, "field": "count"},
                               expect={"op": ">=", "value": 1}),
                         probe("b", play=play, measure={"probe": "log", "pattern": "Initialize engine"},
                               expect={"op": "==", "value": 1}),
                         play_scene="Assets/Scenes/Town.unity", play_args=["-scenario", "2"])
        game = FakeProject(measuring(5))
        found = grade(task, "reference", side("start", FakeProject(), task), side("reference", game, task))
        self.assertTrue(all(c["passed"] for c in found["checks"]), found["checks"])
        (played,) = game.plays
        self.assertEqual((played["seconds"], played["shots"], played["scene"], played["args"], played["every"]),
                         (8, 2, "Assets/Scenes/Arena.unity", ["-autoPlay"], 0.25), "the play's own scene and args")
        self.assertEqual(played["queries"]["every"], 0.25)
        self.assertEqual(played["inputs"], [{"t": 0.2, "teleport": [1.0, 2.0, 3.0], "yaw": 90.0},
                                            {"t": 1.0, "key": "<Mouse>/leftButton", "press": True}])

    def test_a_task_play_without_a_scene_or_args_plays_the_tasks(self):
        task = task_with(probe("a", play={"name": "a", "seconds": 5}),
                         probe("b", play={"name": "b", "seconds": 5, "args": []}),
                         probe("c", play={"name": "c", "seconds": 5, "scene": None}),
                         play_scene="Assets/Scenes/Town.unity", play_args=["-scenario", "2"])
        game = FakeProject(measuring(5))
        grade(task, "reference", side("start", FakeProject(), task), side("reference", game, task))
        self.assertEqual([(p["scene"], p["args"]) for p in game.plays],
                         [("Assets/Scenes/Town.unity", ["-scenario", "2"]), ("Assets/Scenes/Town.unity", []),
                          (None, ["-scenario", "2"])])

    def test_the_drive_plays_its_scripted_inputs_on_the_tasks_scene_with_its_player(self):
        task = task_with(probe(play="drive"), play_scene="Assets/Scenes/Town.unity", play_args=["-scenario", "1"],
                         player={"tag": "Player", "name": "Hero*"})
        game = FakeProject(measuring(5))
        grade(task, "reference", side("start", FakeProject(), task), side("reference", game, task))
        (drive,) = game.plays
        self.assertEqual((drive["seconds"], drive["shots"], drive["scene"], drive["args"]),
                         (22, 8, "Assets/Scenes/Town.unity", ["-scenario", "1"]))
        self.assertEqual(drive["inputs"], check.DRIVE)
        self.assertEqual(drive["player"], {"tag": "Player", "name": "Hero*"})
        self.assertEqual({i["key"] for i in check.DRIVE},
                         {"<Keyboard>/w", "<Keyboard>/a", "<Keyboard>/d", "<Keyboard>/space"})
        self.assertEqual(tasks.inputs(check.DRIVE), check.DRIVE, "the drive's inputs are as a task play's are sent")

    def test_a_calibrated_threshold_is_made_from_the_start_and_the_reference(self):
        task = task_with(probe(expect={"op": ">=", "calibrate": 0.5}))
        start, reference = FakeProject(measuring(-500)), FakeProject(measuring(100))
        sides, kept = (side("start", start, task), side("reference", reference, task)), {}
        ref = grade(task, "reference", *sides, kept)
        own = grade(task, "start", *sides, kept)
        self.assertEqual(ref["checks"][0]["detail"],
                         "The hero stands on the ground. | measured 100, threshold >= -200 (start -500, fix 100)")
        self.assertTrue(ref["checks"][0]["passed"])
        self.assertFalse(own["checks"][0]["passed"])
        self.assertEqual(own["probes"]["hero_on_ground"],
                         {"value": -500.0, "threshold": -200.0, "start": -500.0, "fix": 100.0})
        self.assertEqual((len(start.plays), len(reference.plays)), (1, 1), "each side played once")

    def test_a_start_and_reference_that_measure_the_same_fail_as_uncalibrated(self):
        task = task_with(probe(expect={"op": ">=", "calibrate": 0.5}),
                         probe("walls", measure={"probe": "objects", "select": WALLS, "field": "y", "of": "max"}))
        sides = (side("start", FakeProject(measuring(100)), task),
                 side("reference", FakeProject(measuring(100 + 1e-5)), task))
        found = grade(task, "reference", *sides)
        self.assertFalse(found["checks"][0]["passed"])
        self.assertTrue(found["checks"][0]["detail"].startswith(
            "uncalibrated: hero_on_ground: the start and the reference both measure 100"))
        self.assertEqual(found["probes"]["hero_on_ground"]["start"], 100.0)
        self.assertTrue(found["checks"][1]["passed"], "every other probe is still measured")

    def test_a_reference_that_measures_nothing_or_a_start_relative_start_that_measures_nothing(self):
        task = task_with(probe(expect={"op": ">=", "calibrate": 0.5}))
        found = grade(task, "reference", side("start", FakeProject(measuring(0)), task),
                      side("reference", FakeProject(measuring(0, crash=True)), task))
        self.assertIn("the reference measured nothing", found["checks"][0]["detail"])
        relative = task_with(probe(expect={"op": ">=", "start_plus": 5}), seed=NO_FIX)
        found = grade(relative, "start", side("start", FakeProject(measuring(0, crash=True)), relative))
        self.assertIn("the start measured nothing", found["checks"][0]["detail"])

    def test_a_start_that_measures_nothing_anchors_a_calibrated_threshold_on_the_reference(self):
        task = task_with(probe(expect={"op": ">=", "calibrate": 0.5}))
        found = grade(task, "reference", side("start", FakeProject(measuring(0, crash=True)), task),
                      side("reference", FakeProject(measuring(100)), task))
        self.assertTrue(found["checks"][0]["detail"].endswith("measured 100, threshold >= 75 (start nothing, fix 100)"))

    def test_a_threshold_relative_to_the_start_needs_only_the_start(self):
        task = task_with(probe(expect={"op": ">=", "start_plus": 50}),
                         probe("twice", expect={"op": ">=", "start_times": 2}), seed=NO_FIX)
        start = FakeProject(measuring(60))
        found = grade(task, "start", side("start", start, task))
        self.assertEqual([c["passed"] for c in found["checks"]], [False, False])
        self.assertTrue(found["checks"][0]["detail"].endswith("measured 60, threshold >= 110 (start 60)"))
        self.assertEqual(len(start.plays), 1, "the start played once")

    def test_needs_and_the_checks_a_start_isnt_asked(self):
        task = task_with({"kind": "build", "name": "player_builds"},
                         {"kind": "boot", "name": "boots_clean", "seconds": 10, "needs": ["player_builds"]},
                         {"kind": "judge", "name": "looks_right", "question": "q", "required": False,
                          "rubric": [{"key": "k", "criterion": "c"}]},
                         probe(needs=["boots_clean"]))
        broken = FakeProject(measuring(5), build_exit=6)
        found = grade(task, "reference", side("start", FakeProject(), task), side("reference", broken, task))
        self.assertEqual([(c["passed"], c["detail"]) for c in found["checks"]],
                         [(False, "build failed (exit 6)"), (False, "not run: needs player_builds"),
                          (True, check.NOT_JUDGED), (False, "not run: needs boots_clean")])
        start = grade(task, "start", side("start", FakeProject(measuring(-5)), task))
        self.assertEqual([c["passed"] for c in start["checks"]], [True, True, True, False])
        self.assertEqual(start["checks"][0]["detail"], "not asked: the start is checked on its probes")

    def test_a_boot_and_its_log(self):
        task = task_with({"kind": "boot", "name": "boots_clean", "seconds": 10},
                         {"kind": "log_absent", "name": "no_exceptions", "pattern": "NullReferenceException"},
                         probe())
        found = grade(task, "reference", side("start", FakeProject(), task),
                      side("reference", FakeProject(measuring(5)), task))
        self.assertEqual([c["detail"] for c in found["checks"][:2]],
                         ["ran 10 s with no crash or fatal error", "0 matching log line(s)"])
        crashed = grade(task, "reference", side("start", FakeProject(), task),
                        side("reference", FakeProject(measuring(5, crash=True)), task))
        self.assertEqual(crashed["checks"][0]["detail"], "crashed")

    def test_a_crash_is_unitys_crash_lines_never_a_managed_exception(self):
        for line in ("Crash!!!", "========== OUTPUTTING STACK TRACE ==================", "Fatal error in GC",
                     "Could not allocate memory: System out of memory!\nOut of memory"):
            self.assertTrue(check.fatal(line), line)
        for line in ("NullReferenceException: Object reference not set to an instance of an object",
                     "UnityEngine.Debug:LogError (object)", "", None):
            self.assertFalse(check.fatal(line), line)

    def test_editor_probes_run_one_pass_per_side_and_a_build_failure_fails_them(self):
        asset = {"probe": "asset", "asset": "Assets/Materials/Road.mat", "field": "shader:_Cull"}
        task = task_with(probe("road", play="editor", measure=asset, expect={"op": "==", "value": 1}),
                         probe("road_again", play="editor", measure={**asset, "field": "keyword:_EMISSION"},
                               expect={"op": "==", "value": 0}))

        def editor(request, timeout):
            return ran("[TaskProbe] asset pass done"), {"nonce": request["nonce"],
                                                        "measures": {i: {"value": 1} for i in request["measures"]}}

        game = FakeProject(editor=editor)
        found = grade(task, "reference", side("start", FakeProject(), task), side("reference", game, task))
        self.assertEqual([c["passed"] for c in found["checks"]], [True, False])
        self.assertEqual(len(game.requests), 1, "one pass for both")
        self.assertEqual(len(game.requests[0]["measures"]), 2)
        broken = grade(task, "reference", side("start", FakeProject(), task),
                       side("reference", FakeProject(editor=editor, build_exit=6), task))
        self.assertTrue(broken["checks"][0]["detail"].endswith("the project didn't build, so the editor couldn't "
                                                               "open it"))
        silent = grade(task, "reference", side("start", FakeProject(), task),
                       side("reference", FakeProject(editor=lambda r, t: (ran("error CS0246", 1), None)), task))
        self.assertTrue(silent["checks"][0]["detail"].endswith("the editor pass gave no result (exit 1)"))
        planted = grade(task, "reference", side("start", FakeProject(), task), side(
            "reference", FakeProject(editor=lambda r, t: (ran(""), {"nonce": "guess", "measures": {}})), task))
        self.assertTrue(planted["checks"][0]["detail"].endswith("the editor pass gave no result (exit 0)"),
                        "a result without the checker's nonce isn't the pass's")


def git(repo, *args, data=None):
    return subprocess.run(["git", "-C", str(repo), *args], input=data, capture_output=True, check=True).stdout


def make_game(root, version=VERSION):
    """A tiny Unity game repo: main with an LFS texture (its object in .git/lfs/objects), a Tasks/ folder that never
    reaches a copy, and a fix commit."""
    repo = Path(root) / "metro-runner"
    repo.mkdir()
    git(repo, "init", "-q", "-b", "main")
    git(repo, "config", "user.email", "dev@example.invalid")
    git(repo, "config", "user.name", "dev")
    (repo / "ProjectSettings").mkdir()
    if version is not None:
        (repo / "ProjectSettings" / "ProjectVersion.txt").write_text(version, encoding="utf-8")
    (repo / "Packages").mkdir()
    (repo / "Packages" / "manifest.json").write_text('{"dependencies": {}}\n', encoding="utf-8")
    (repo / "Assets" / "Scripts").mkdir(parents=True)
    (repo / "Assets" / "Scripts" / "Metro.cs").write_text("class Metro {}\n", encoding="utf-8")
    (repo / "Tasks").mkdir()
    (repo / "Tasks" / "x.json").write_text("{}", encoding="utf-8")
    data = b"a texture's bytes"
    import hashlib
    oid = hashlib.sha256(data).hexdigest()
    store = repo / ".git" / "lfs" / "objects" / oid[:2] / oid[2:4]
    store.mkdir(parents=True)
    (store / oid).write_bytes(data)
    (repo / "Assets" / "Textures").mkdir()
    (repo / "Assets" / "Textures" / "Wall.png").write_bytes(
        f"version https://git-lfs.github.com/spec/v1\noid sha256:{oid}\nsize {len(data)}\n".encode())
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "start")
    start = git(repo, "rev-parse", "HEAD").decode().strip()
    (repo / "Assets" / "Scripts" / "Metro.cs").write_text("class Metro { int a = 1; }\n", encoding="utf-8")
    git(repo, "commit", "-q", "-am", "fix")
    fix = git(repo, "rev-parse", "HEAD").decode().strip()
    return repo, start, fix, data


class Seeds(unittest.TestCase):
    def test_a_commit_is_materialized_with_its_lfs_objects_the_probe_and_no_answers(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo, start, fix, data = make_game(tmp)
            made = seeds.materialize(repo, start, Path(tmp) / "copy")
            copy = Path(tmp) / "copy"
            self.assertEqual((copy / "Assets" / "Textures" / "Wall.png").read_bytes(), data)
            self.assertEqual((copy / "Assets" / "Scripts" / "Metro.cs").read_text(encoding="utf-8"), "class Metro {}\n")
            self.assertFalse((copy / "Tasks").exists(), "a task's answers never reach a copy")
            self.assertEqual(made["linked"] + made["copied"], 1)
            seeds.add_probe(copy)
            package = copy / "Packages" / "com.taskprobe"
            self.assertTrue((package / "package.json").is_file())
            self.assertTrue((package / "Runtime" / "Probe.cs.meta").is_file(), "the package's own files, .meta too")
            self.assertFalse((package / "obj").exists(), "an IDE's leftovers stay out")
            self.assertEqual((copy / "Packages" / "manifest.json").read_text(encoding="utf-8"), '{"dependencies": {}}\n',
                             "the game's own files stay as committed: an embedded package needs no manifest entry")
            seeds.add_probe(copy)
            self.assertTrue((package / "package.json").is_file(), "added again over the first")
            seeds.remove(copy)
            self.assertTrue((repo / ".git" / "lfs" / "objects").is_dir())

    def test_a_missing_lfs_object_and_another_unity_are_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo, start, _, _ = make_game(tmp)
            shutil.rmtree(repo / ".git" / "lfs")
            with self.assertRaisesRegex(FileNotFoundError, "lfs fetch"):
                seeds.materialize(repo, start, Path(tmp) / "copy")
            for name, version in (("old", "m_EditorVersion: 2022.3.10f1\n"), ("next", "m_EditorVersion: 6000.4.0f1\n"),
                                  ("none", None)):
                folder = Path(tmp) / name / "ProjectSettings"
                folder.mkdir(parents=True)
                if version:
                    (folder / "ProjectVersion.txt").write_text(version, encoding="utf-8")
                with self.assertRaisesRegex(seeds.WrongEngine, "must be Unity 6000.3 projects", msg=name):
                    seeds.add_probe(folder.parent)
            self.assertEqual(seeds.engine_of(Path(tmp) / "old"), "2022.3.10f1")
            (Path(tmp) / "ok" / "ProjectSettings").mkdir(parents=True)
            (Path(tmp) / "ok" / "ProjectSettings" / "ProjectVersion.txt").write_text("\ufeff" + VERSION,
                                                                                     encoding="utf-8")
            seeds.add_probe(Path(tmp) / "ok")

    def test_a_scratch_folder_unity_cant_build_in_is_refused(self):
        self.assertIsNone(seeds.too_long("C:\\tc\\abcd1234\\0123456789ab"))
        long = "C:\\" + "x" * 80 + "\\abcd1234\\0123456789ab"
        why = seeds.too_long(long)
        self.assertIn("longer than 90 characters", why)
        self.assertIn("--scratch", why)
        with self.assertRaisesRegex(seeds.PathTooLong, "260"):
            seeds.check_length(long)
        self.assertTrue(issubclass(seeds.PathTooLong, ValueError), "a check_task reports it as an ERROR")
        builds = check.Builds(".", "C:\\" + "x" * 80, log=lambda *a: None)
        with self.assertRaises(seeds.PathTooLong):
            builds.get("a" * 40)
        self.assertEqual(builds.copies, {}, "nothing materialized")


def missing(*scenes, names=57):
    return {"ok": True, "exe": "Game.exe", "errors": 0, "error": None, "scenes": list(scenes),
            "missing": {s: {"missing": ["4f1c2a9e0b8d4c3a9f7e6d5c4b3a2910"], "names": names} for s in scenes}}


class Whole(unittest.TestCase):
    def check(self, task, projects, tmp):
        """check_task with the scratch copies made for real and Unity faked: `projects` {side: FakeProject}."""
        repo, start, fix, _ = make_game(tmp)
        task["seed"] = {**task["seed"], "commit": start}
        if "reference" in task["seed"]:
            task["seed"]["reference"] = fix
        raw = json.dumps(task).encode()

        names = {start[:12]: "start", fix[:12]: "reference"}

        def project(folder, machine, label):
            found = projects[names[Path(folder).name]]
            found.folder, found.label = Path(folder), label
            return found

        with mock.patch.object(unity, "Project", project), \
                mock.patch.object(unity.Machine, "for_project", classmethod(lambda cls, p, d=False: cls(Path(p), None))):
            return check.check_task(repo, task, raw, Path(tmp) / "scratch", Path(tmp) / "out", log=lambda *a: None)

    def test_a_valid_task_with_a_reference(self):
        with tempfile.TemporaryDirectory() as tmp:
            task = task_with({"kind": "build", "name": "player_builds"},
                             {"kind": "boot", "name": "boots_clean", "seconds": 10, "needs": ["player_builds"]},
                             probe(expect={"op": ">=", "calibrate": 0.5}, needs=["boots_clean"]))
            result = self.check(task, {"start": FakeProject(measuring(-500)),
                                       "reference": FakeProject(measuring(100))}, tmp)
            self.assertEqual((result["verdict"], result["reasons"], result["notes"]), ("VALID", [], []))
            self.assertEqual(result["probes"]["hero_on_ground"]["start"], -500.0)
            self.assertEqual(result["probes"]["hero_on_ground"]["reference"], 100.0)
            self.assertEqual(result["probes"]["hero_on_ground"]["threshold"], -200.0)
            self.assertEqual((result["start"]["missing_assets"], result["start"]["slots"]), ({}, "direct"))
            kept = json.loads((Path(tmp) / "out" / "probe-task.json").read_text(encoding="utf-8"))
            self.assertEqual(kept["verdict"], "VALID")
            self.assertTrue((Path(tmp) / "out" / "probe-task" / "start" / "look" / "probe.json").is_file())
            self.assertFalse((Path(tmp) / "scratch").exists(), "the scratch copies are deleted")

    def test_a_start_that_doesnt_build_or_already_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            task = task_with({"kind": "build", "name": "player_builds"}, probe())
            result = self.check(task, {"start": FakeProject(build_exit=6), "reference": FakeProject()}, tmp)
            self.assertEqual(result["reasons"], ["start doesn't build: the game as the task started didn't build "
                                                 "(exit 6)"])
            self.assertEqual(result["start"]["missing_assets"], {})
        with tempfile.TemporaryDirectory() as tmp:
            task = task_with({"kind": "build", "name": "player_builds", "weight": 0}, probe(), seed=NO_FIX)
            result = self.check(task, {"start": FakeProject(measuring(10))}, tmp)
            self.assertEqual((result["verdict"], result["reasons"]),
                             ("INVALID", ["start already passes every required probe"]))

    def test_a_start_that_doesnt_build_by_design(self):
        with tempfile.TemporaryDirectory() as tmp:
            task = task_with(milestones=[{"name": "builds", "checks": [{"kind": "build", "name": "player_builds",
                                                                        "fails_at_start": True}]},
                                         {"name": "graded", "checks": [probe(needs=["player_builds"])]}])
            start = FakeProject(measuring(-5), build_exit=6)
            result = self.check(task, {"start": start, "reference": FakeProject(measuring(5))}, tmp)
            self.assertEqual(result["verdict"], "VALID", result["reasons"])
            self.assertEqual(start.plays, [], "a start that doesn't build is never played")

    def test_another_unity_is_invalid(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo, start, fix, _ = make_game(tmp, version="m_EditorVersion: 6000.0.40f1\n")
            task = task_with(probe())
            task["seed"] = {**task["seed"], "commit": start, "reference": fix}
            result = check.check_task(repo, task, b"{}", Path(tmp) / "scratch", Path(tmp) / "out", log=lambda *a: None)
            self.assertEqual(result["verdict"], "INVALID")
            self.assertTrue(result["reasons"][0].startswith("start: ProjectSettings/ProjectVersion.txt names Unity "
                                                            "6000.0.40f1"), result["reasons"])

    def test_a_machine_that_cant_run_unity_is_an_error_never_a_verdict(self):
        def unlicensed(*args, **kwargs):
            raise unity.Unlicensed('Unity has no active licence (exit 198, "No valid Unity Editor license")')

        def editor(request, timeout):
            return ran(""), {"nonce": request["nonce"], "measures": {i: {"value": 1} for i in request["measures"]}}

        asset = {"probe": "asset", "asset": "Assets/Materials/Road.mat", "field": "shader:_Cull"}
        task = task_with({"kind": "build", "name": "player_builds"},
                         probe("road", play="editor", measure=asset, expect={"op": "==", "value": 1}))
        for side_, job in (("start", "build"), ("reference", "build"), ("reference", "editor_assets")):
            with tempfile.TemporaryDirectory() as tmp:  # the reference's jobs are rows of its grade: never failed ones
                projects = {"start": FakeProject(measuring(-500), editor=editor),
                            "reference": FakeProject(measuring(100), editor=editor)}
                setattr(projects[side_], job, unlicensed)
                result = self.check(json.loads(json.dumps(task)), projects, tmp)
                self.assertEqual(result["verdict"], "ERROR", (side_, job))
                self.assertIn("exit 198", result["reasons"][0])

    def test_the_scenes_a_task_plays_are_built_and_the_assets_they_lack_are_noted(self):
        with tempfile.TemporaryDirectory() as tmp:
            play = {"name": "arena", "seconds": 8, "scene": "Assets/Scenes/Arena.unity"}
            task = task_with({"kind": "build", "name": "player_builds", "weight": 0},
                             probe(expect={"op": ">=", "calibrate": 0.5}),
                             probe("arena", play=play, expect={"op": ">=", "calibrate": 0.5}),
                             play_scene="Assets/Scenes/Town.unity")
            self.assertEqual(check.task_scenes(task), ["Assets/Scenes/Arena.unity", "Assets/Scenes/Town.unity"])
            start = FakeProject(measuring(-500), report=missing("Assets/Scenes/Town.unity", "Assets/Scenes/Menu.unity"))
            reference = FakeProject(measuring(100), report={"ok": True, "missing": {}})
            result = self.check(task, {"start": start, "reference": reference}, tmp)
            self.assertEqual(start.scenes, [["Assets/Scenes/Arena.unity", "Assets/Scenes/Town.unity"]])
            self.assertEqual(result["verdict"], "VALID", result["reasons"])
            self.assertEqual(result["start"]["missing_assets"],
                             {"Assets/Scenes/Town.unity": {"missing": ["4f1c2a9e0b8d4c3a9f7e6d5c4b3a2910"],
                                                           "names": 57}}, "only the scenes the task plays")
            self.assertEqual(result["reference"]["missing_assets"], {})
            (note,) = result["notes"]
            self.assertTrue(note.startswith("start: Assets/Scenes/Town.unity names 1 of its 57 assets that the commit "
                                            "doesn't have (e.g. GUID 4f1c2a9e0b8d4c3a9f7e6d5c4b3a2910)"), note)
            self.assertEqual(check.gap_notes({"start": {"missing_assets": {}}, "reference": None}), [])

    def test_a_run_builds_a_commit_its_tasks_share_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo, start, fix, _ = make_game(tmp)
            built = {start[:12]: FakeProject(measuring(-500)), fix[:12]: FakeProject(measuring(100))}
            checks = [{"kind": "build", "name": "player_builds", "weight": 0},
                      {"kind": "boot", "name": "boots_clean", "seconds": 10, "needs": ["player_builds"], "weight": 0},
                      probe(expect={"op": ">=", "calibrate": 0.5}, needs=["boots_clean"])]
            one, two = task_with(*checks), task_with(*checks)
            for task, name in ((one, "a-fix-one"), (two, "a-fix-two")):
                task["name"], task["seed"] = name, {**task["seed"], "commit": start, "reference": fix}
            with mock.patch.object(unity, "Project", lambda folder, machine, label: built[Path(folder).name]), \
                    mock.patch.object(unity.Machine, "for_project",
                                      classmethod(lambda cls, p, d=False: cls(Path(p), None))), \
                    mock.patch.object(unity.ugfroot, "check_free", lambda *a: 100.0):
                builds = check.Builds(repo, Path(tmp) / "scratch", log=lambda *a: None)
                verdicts = [check.check_task(repo, task, json.dumps(task).encode(), Path(tmp) / "unused",
                                             Path(tmp) / "out", log=lambda *a: None, builds=builds)["verdict"]
                            for task in (one, two)]
                self.assertEqual(verdicts, ["VALID", "VALID"])
                self.assertEqual([p.builds for p in built.values()], [1, 1], "each commit built once for both tasks")
                self.assertEqual(len(built[start[:12]].plays), 2, "each task plays with its own queries")
                self.assertTrue((Path(tmp) / "scratch" / start[:12]).is_dir(), "the run, not the task, deletes")
                builds.release(start)
                self.assertFalse((Path(tmp) / "scratch" / start[:12]).exists())
                builds.close()
                self.assertFalse((Path(tmp) / "scratch").exists())

    def test_a_shared_copy_is_built_again_for_a_scene_its_build_lacks(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo, start, fix, _ = make_game(tmp)
            built = {start[:12]: FakeProject(measuring(-500)), fix[:12]: FakeProject(measuring(100))}
            checks = [{"kind": "build", "name": "player_builds", "weight": 0},
                      probe(expect={"op": ">=", "calibrate": 0.5}, needs=["player_builds"])]
            runs = []
            for name, scene in (("a-town", "Assets/Scenes/Town.unity"), ("a-arena", "Assets/Scenes/Arena.unity"),
                                ("a-town-again", "Assets/Scenes/Town.unity"), ("a-first-scene", None)):
                task = task_with(*checks, **({"play_scene": scene} if scene else {}))
                task["name"], task["seed"] = name, {**task["seed"], "commit": start, "reference": fix}
                runs.append(task)
            said = []
            with mock.patch.object(unity, "Project", lambda folder, machine, label: built[Path(folder).name]), \
                    mock.patch.object(unity.Machine, "for_project",
                                      classmethod(lambda cls, p, d=False: cls(Path(p), None))), \
                    mock.patch.object(unity.ugfroot, "check_free", lambda *a: 100.0):
                builds = check.Builds(repo, Path(tmp) / "scratch", log=said.append)
                verdicts = [check.check_task(repo, task, json.dumps(task).encode(), Path(tmp) / "unused",
                                             Path(tmp) / "out", log=said.append, builds=builds)["verdict"]
                            for task in runs]
                builds.close()
            self.assertEqual(verdicts, ["VALID"] * 4)
            self.assertEqual(built[start[:12]].scenes,
                             [["Assets/Scenes/Town.unity"], ["Assets/Scenes/Arena.unity", "Assets/Scenes/Town.unity"]],
                             "built again once, with every scene asked for so far; then it serves the rest")
            self.assertEqual([p.builds for p in built.values()], [2, 2])
            again = [s for s in said if "building again" in s]
            self.assertEqual(len(again), 2, "one line per copy")
            self.assertIn("Assets/Scenes/Arena.unity", again[0])
            self.assertIn("  reference: built (1 s, built earlier in this run)", said,
                          "the third task's reference build is the second's")

    def test_an_unreadable_task_is_invalid(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = check.check_task(tmp, {"name": "x"}, b"{}", Path(tmp) / "s", Path(tmp) / "out",
                                      log=lambda *a: None)
            self.assertEqual(result["verdict"], "INVALID")
            self.assertTrue(result["reasons"][0].startswith("the task doesn't validate"))


def rising(log="Initialize engine version: 6000.3.26f1\n"):
    """A play answer whose player rises 0.1 m a second, for the play's whole length."""

    def play(seconds, shots, queries):
        return {"format": "unity-probe/1", "ended": "time", "seconds": float(seconds), "scene": None, "inputs_sent": 0,
                "screenshots": [], "track": [[i * 0.5, 0.0, i * 0.05, 0.0] for i in range(int(seconds * 2) + 1)],
                "camera": [], "measures": {}}, log

    return play


class IdlePlay(unittest.TestCase):
    BOOT = {"kind": "boot", "name": "boots_clean", "seconds": 60, "weight": 0}

    def test_the_60_s_boot_serves_look_and_look_sees_only_its_first_20_s(self):
        task = task_with(self.BOOT, probe("highest", measure={"probe": "player", "field": "y", "agg": "max"},
                                          expect={"op": ">=", "value": 0}, needs=["boots_clean"]))
        game = FakeProject(rising())
        found = grade(task, "reference", side("start", FakeProject(), task), side("reference", game, task))
        self.assertTrue(all(c["passed"] for c in found["checks"]), found["checks"])
        self.assertEqual([(p["seconds"], p["shots"]) for p in game.plays], [(60, 6)], "one launch for both")
        self.assertAlmostEqual(found["probes"]["highest"]["value"], 2.0,
                               msg="the highest point of the first 20 s, not 3")

    def test_a_look_probe_reading_the_log_keeps_its_own_play(self):
        task = task_with(self.BOOT, probe("no_warnings", measure={"probe": "log", "pattern": "Warning"},
                                          expect={"op": "==", "value": 0}, needs=["boots_clean"]))
        game = FakeProject(rising())
        grade(task, "reference", side("start", FakeProject(), task), side("reference", game, task))
        self.assertEqual([p["seconds"] for p in game.plays], [60, 20], "a log covers the whole play")

    def test_a_boot_shorter_than_look_keeps_its_own_play(self):
        task = task_with({**self.BOOT, "seconds": 10}, probe(needs=["boots_clean"]))
        game = FakeProject(rising())
        grade(task, "reference", side("start", FakeProject(), task), side("reference", game, task))
        self.assertEqual([p["seconds"] for p in game.plays], [10, 20])

    def test_a_play_logs_its_time_and_the_wait_for_a_slot(self):
        task = task_with(probe())
        game = FakeProject(rising())
        game.play = lambda *a, **k: unity.Played(0, False, "", 95.0, None, "", {}, 40.0)
        said = []
        check.Side("reference", game, task, 60, 60, None, said.append).probe_play("look")
        self.assertEqual(said, ["  reference: playing look (20 s)",
                                "  reference: played look in 95 s (40 s of it waiting for a machine slot)"])

    def test_first_seconds_cuts_rows_samples_and_length(self):
        probe_ = {"seconds": 60.0, "ended": "time", "track": [[0.0, 0, 1, 0], [20.0, 0, 2, 0], [20.5, 0, 3, 0]],
                  "camera": [], "measures": {"q": [{"t": 19.5, "value": 1}, {"t": 30, "value": 2}]}}
        cut = check.first_seconds(probe_, 20)
        self.assertEqual((cut["seconds"], cut["ended"], len(cut["track"]), cut["measures"]["q"]),
                         (20.0, "time", 2, [{"t": 19.5, "value": 1}]))
        self.assertEqual(probe_["seconds"], 60.0, "the boot's own probe is left whole")
        quit_ = check.first_seconds({"seconds": 12.0, "ended": "shutdown", "track": []}, 20)
        self.assertEqual((quit_["seconds"], quit_["ended"]), (12.0, "shutdown"), "a play that ended early stays so")


class FakeMachine:
    """Records each job and answers it with `answer(argv, cwd)` (writing what Unity would), exit code `code`."""

    def __init__(self, editor="C:/Unity/6000.3.26f1/Editor/Unity.exe", answer=None, code=0):
        self.editor, self.answer, self.code, self.jobs = Path(editor), answer, code, []

    def job(self, label, argv, cwd, timeout, gpu=False):
        argv = [str(a) for a in argv]
        self.jobs.append({"label": label, "argv": argv, "cwd": Path(cwd), "timeout": timeout, "gpu": gpu})
        output = self.answer(argv, Path(cwd)) if self.answer else ""
        return unity.Result(self.code, output or "", 1.0)


def after(argv, flag):
    return argv[argv.index(flag) + 1]


class Plays(unittest.TestCase):
    def test_a_play_hands_the_player_its_spec_and_the_play_args(self):
        with tempfile.TemporaryDirectory() as tmp:
            exe = Path(tmp) / "Build" / "TaskProbe" / "Game.exe"
            exe.parent.mkdir(parents=True)
            exe.write_bytes(b"")
            specs = []

            def answer(argv, cwd):
                spec = json.loads(Path(after(argv, "-taskProbe")).read_text(encoding="utf-8"))
                specs.append(spec)
                out = Path(spec["out"])
                (out / "probe.json").write_text(json.dumps({"format": "unity-probe/1", "ended": "time"}),
                                                encoding="utf-8")
                (out / "shot_00.png").write_bytes(b"png")
                Path(after(argv, "-logFile")).write_bytes(b"Initialize engine\r\nCrash!!!\r\n")
                return "player output"

            machine = FakeMachine(answer=answer)
            project = unity.Project(tmp, machine, "t")
            asked = probes.query_file(probes.plan(task_with(probe(measure={"probe": "grading",
                                                                           "field": "warmth"})))["look"], 0.25)
            inputs = [{"t": 1.0, "key": "<Keyboard>/w", "press": True}]
            found = project.play(5, 2, 60, scene="Assets/Scenes/L.unity", inputs=inputs, queries=asked,
                                 args=["-scenario", "1"], every=0.25, player={"tag": "Hero"})
            (job,) = machine.jobs
            argv = job["argv"]
            self.assertEqual((Path(argv[0]), Path(argv[1])), (Path(sys.executable), unity.DESK),
                             "started through desk.py: on a desktop of its own")
            self.assertEqual(Path(argv[2]), exe)
            self.assertEqual(argv[3:9], ["-screen-fullscreen", "0", "-screen-width", "960", "-screen-height", "540"])
            self.assertEqual(Path(after(argv, "-logFile")), Path(tmp) / "Logs" / "TaskProbe" / "play.log")
            self.assertEqual(argv[-2:], ["-scenario", "1"], "the play's args after the spec")
            self.assertEqual((job["cwd"], job["gpu"]), (exe.parent, True), "in the build folder, in a GPU slot")
            spec = specs[0]
            self.assertEqual(spec, {"format": "unity-probe-play/1", "out": (Path(tmp) / "Logs/TaskProbe/play").as_posix(),
                                    "seconds": 5, "shots": 2, "every": 0.25, "scene": "Assets/Scenes/L.unity",
                                    "sound": False, "player": {"tag": "Hero"}, "inputs": inputs, "queries": asked})
            self.assertEqual(found.probe, {"format": "unity-probe/1", "ended": "time"})
            self.assertEqual(set(found.files), {"probe.json", "shot_00.png"}, "the spec isn't one of the play's files")
            self.assertEqual((found.log, found.output), ("Initialize engine\nCrash!!!\n", "player output"))
            self.assertTrue(check.fatal(found.log))
            self.assertFalse((Path(tmp) / "Logs" / "TaskProbe" / "play").exists(), "the play's folder is cleared")
            project.play(5, 0, 60)
            self.assertEqual({k: specs[1][k] for k in ("scene", "player", "inputs", "every", "sound")},
                             {"scene": None, "player": None, "inputs": [], "every": 0.5, "sound": False})
            self.assertEqual(specs[1]["queries"], {"format": "game-probe-queries/1", "every": 0.5, "queries": []})

    def test_a_play_without_a_built_player_says_so(self):
        with tempfile.TemporaryDirectory() as tmp:
            machine = FakeMachine()
            found = unity.Project(tmp, machine, "t").play(5, 0, 60)
            self.assertEqual((found.exit_code, found.probe, machine.jobs), (1, None, []))
            self.assertIn("no built player", found.output)

    def test_a_build_names_the_tasks_scenes_and_passes_only_with_its_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            requests = []

            def answer(argv, cwd):
                request = json.loads(Path(after(argv, "-taskProbeBuild")).read_text(encoding="utf-8"))
                requests.append(request)
                Path(after(argv, "-logFile")).write_text("Build Finished, Result: Success.\n", encoding="utf-8")
                if result is not None:
                    Path(request["result"]).write_text(json.dumps(result), encoding="utf-8")
                return ""

            machine = FakeMachine(answer=answer)
            project = unity.Project(tmp, machine, "t")
            exe = (Path(tmp) / "Build" / "TaskProbe" / "Game.exe").as_posix()
            result = {"ok": True, "exe": exe, "scenes": ["Assets/Scenes/A.unity"], "errors": 0, "seconds": 41,
                      "error": None, "missing": {}}
            found = project.build(60, ["Assets/Scenes/A.unity"])
            argv = machine.jobs[0]["argv"]
            self.assertEqual(argv[:7], [str(machine.editor), "-batchmode", "-nographics", "-quit", "-projectPath",
                                        str(Path(tmp)), "-logFile"])
            self.assertEqual(Path(argv[7]), Path(tmp) / "Logs" / "TaskProbe" / "build.log")
            self.assertEqual(argv[8:11], ["-executeMethod", "TaskProbe.EditorTools.Build.Player", "-taskProbeBuild"])
            self.assertEqual((machine.jobs[0]["cwd"], machine.jobs[0]["gpu"]), (Path(tmp), False))
            self.assertEqual(requests[0], {"out": (Path(tmp) / "Build/TaskProbe").as_posix(),
                                           "scenes": ["Assets/Scenes/A.unity"],
                                           "result": (Path(tmp) / "Logs/TaskProbe/build.json").as_posix()})
            self.assertEqual((found.exit_code, found.report), (0, result))
            self.assertIn("Build Finished", found.output, "the build log is the build's output")
            result = {**result, "ok": False, "error": "3 compiler errors"}
            failed = project.build(60, [])
            self.assertEqual(failed.exit_code, 1)
            self.assertIn("the build's result says it failed: 3 compiler errors", failed.output)
            result = None
            silent = project.build(60, [])
            self.assertEqual((silent.exit_code, silent.report), (1, None), "no result from an earlier build is read")
            self.assertIn("wrote no result", silent.output)
            machine.code = 3
            result = {"ok": True}
            self.assertEqual(project.build(60, []).exit_code, 3)
            machine.code = 1
            result = {"ok": False, "error": "no scene to build: the project lists no enabled build scene and the task "
                                            "plays none"}
            unbuilt = project.build(60, [])
            self.assertEqual(unbuilt.exit_code, 1)
            self.assertTrue(unbuilt.output.startswith("[task-check] the build's result says it failed: no scene to "
                                                      "build"), "Unity's own log never says it: only the result does")

    def test_a_unity_without_a_licence_is_the_machines_error_not_a_failed_build(self):
        with tempfile.TemporaryDirectory() as tmp:
            def answer(argv, cwd):
                Path(after(argv, "-logFile")).write_text(log, encoding="utf-8")
                if "-taskProbeBuild" in argv:
                    request = json.loads(Path(after(argv, "-taskProbeBuild")).read_text(encoding="utf-8"))
                    Path(request["result"]).write_text('{"ok": true}', encoding="utf-8")
                return ""

            machine = FakeMachine(answer=answer, code=198)
            project = unity.Project(tmp, machine, "t")
            log = ("[Licensing::Module] Error: Access token is unavailable; failed to update\n"
                   "No valid Unity Editor license found. Please activate your license.\n")
            with self.assertRaisesRegex(unity.Unlicensed, "exit 198"):
                project.build(60, [])
            with self.assertRaisesRegex(unity.Unlicensed, "Unity Hub"):
                project.editor_assets(probes.editor_request([], "n0nce"), 60)
            machine.code = 1
            with self.assertRaises(unity.Unlicensed, msg="the line with another failing exit code"):
                project.build(60, [])
            log = "[Licensing::Module] Error: Access token is unavailable\nerror CS0103: The name 'x' does not exist\n"
            self.assertEqual(project.build(60, []).exit_code, 1, "a licensed machine's Licensing errors are no sign")
            machine.code, log = 0, "No valid Unity Editor license found.\n"
            self.assertEqual(project.build(60, []).exit_code, 0, "a job that went on and built is no failure")
        self.assertTrue(issubclass(unity.Unlicensed, unity.MachineError))
        self.assertTrue(issubclass(unity.LimiterRefused, unity.MachineError))

    def test_the_editor_pass_writes_its_request_and_reads_its_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            asked = []

            def answer(argv, cwd):
                request = json.loads(Path(after(argv, "-taskProbeAssets")).read_text(encoding="utf-8"))
                asked.append(request)
                Path(request["result"]).write_text(json.dumps({"nonce": request["nonce"], "measures": {}}),
                                                   encoding="utf-8")
                Path(after(argv, "-logFile")).write_text("[TaskProbe] 2 measures\n", encoding="utf-8")
                return ""

            machine = FakeMachine(answer=answer)
            project = unity.Project(tmp, machine, "t")
            stale = Path(tmp) / probes.EDITOR_FILE
            stale.parent.mkdir(parents=True)
            stale.write_text("{}", encoding="utf-8")
            items = [("a1", {"probe": "asset", "asset": "Assets/M.mat", "field": "shader:_Cull", "of": "count"})]
            found = project.editor_assets(probes.editor_request(items, "n0nce"), 60)
            argv = machine.jobs[0]["argv"]
            self.assertEqual(argv[8:11], ["-executeMethod", "TaskProbe.EditorTools.AssetPass.Run", "-taskProbeAssets"])
            self.assertIn("-nographics", argv)
            self.assertEqual(asked[0], {"nonce": "n0nce", "measures": dict(items), "result": stale.as_posix()})
            self.assertEqual(probes.editor_results(project.read(probes.EDITOR_FILE), "n0nce"), {})
            self.assertIn("[TaskProbe] 2 measures", found.output)

    def test_a_job_goes_through_the_limiter_a_play_in_its_gpu_slot(self):
        seen = []
        with mock.patch.object(unity, "run", lambda argv, cwd, timeout, wrapper=False: seen.append(argv) or
                               unity.Result(0, "", 1.0)):
            machine = unity.Machine(Path("C:/U/Unity.exe"), Path("C:/Work/tools/unity-heavy.ps1"))
            machine.job("task-check play x", ["C:/c/Game.exe", "-taskProbe", "C:/c/it's.json"], ".", 60, gpu=True)
            machine.job("task-check build x", ["C:/U/Unity.exe", "-batchmode"], ".", 60)
            unity.Machine(Path("C:/U/Unity.exe"), None).job("direct", [Path("C:/U/Unity.exe"), "-quit"], ".", 60)
        play, build, direct = seen
        self.assertEqual(play[:6], ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                                    "-Command"])
        self.assertIn("-Label 'task-check play x' -Gpu -- 'C:/c/Game.exe' '-taskProbe' 'C:/c/it''s.json'", play[6])
        self.assertNotIn("-Gpu", build[6])
        self.assertEqual(direct, [str(Path("C:/U/Unity.exe")), "-quit"])

    def test_a_unity_that_isnt_installed_is_an_error_not_an_exit(self):
        def missing_unity(project):
            raise SystemExit("Unity 6000.3.26f1 is not installed: install it through Unity Hub")

        with mock.patch.object(unity.ugfroot, "unity_editor", missing_unity):
            with self.assertRaisesRegex(RuntimeError, "6000.3.26f1 is not installed"):
                unity.Machine.for_project(".")

    def test_the_machine_finds_unity_and_the_limiter(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "tools").mkdir()
            (Path(tmp) / "tools" / "unity-heavy.ps1").write_text("", encoding="utf-8")
            with mock.patch.object(unity.ugfroot, "unity_editor", lambda project: "C:/U/Unity.exe"), \
                    mock.patch.object(unity.ugfroot, "root", lambda: tmp):
                found = unity.Machine.for_project(".")
                self.assertEqual((found.editor, found.heavy), (Path("C:/U/Unity.exe"),
                                                               Path(tmp) / "tools" / "unity-heavy.ps1"))
                self.assertIsNone(unity.Machine.for_project(".", direct=True).heavy)


class Cli(unittest.TestCase):
    def test_the_results_folder_is_git_ignored_in_the_repo(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo, _, _, _ = make_game(tmp)
            cli.ignore_results(repo, repo / ".task-checks")
            self.assertEqual(subprocess.run(["git", "-C", str(repo), "check-ignore", "-q", ".task-checks/a.json"])
                             .returncode, 0)
            self.assertEqual(git(repo, "status", "--porcelain"), b"", "no tracked file changed")
            exclude = (repo / ".git" / "info" / "exclude").read_text(encoding="utf-8")
            cli.ignore_results(repo, repo / ".task-checks")
            self.assertEqual((repo / ".git" / "info" / "exclude").read_text(encoding="utf-8"), exclude, "once")

    def test_a_task_file_not_committed_yet_is_checked_too(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo, _, _, _ = make_game(tmp)
            path = Path(tmp) / "metro-runner-fix-x.json"
            path.write_text(json.dumps({**task_with(probe()), "name": "metro-runner-fix-x"}), encoding="utf-8")
            seen = []

            def fake(repo_, task, raw, scratch, out, **kw):
                seen.append(task["name"])
                return {"task": task["name"], "verdict": "VALID", "reasons": []}

            with mock.patch.object(check, "check_task", fake), \
                    mock.patch.object(unity.ugfroot, "check_free", lambda *a: 100.0), \
                    contextlib.redirect_stdout(io.StringIO()) as out, contextlib.redirect_stderr(io.StringIO()):
                code = cli.main([str(repo), "--task", str(path), "--scratch", str(Path(tmp) / "s")])
            self.assertEqual((code, seen), (0, ["metro-runner-fix-x"]))
            self.assertEqual(out.getvalue(), "VALID   metro-runner-fix-x\n")

    def test_a_scratch_folder_too_long_for_unity_is_refused_before_anything_runs(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo, _, _, _ = make_game(tmp)
            path = Path(tmp) / "metro-runner-fix-x.json"
            path.write_text(json.dumps({**task_with(probe()), "name": "metro-runner-fix-x"}), encoding="utf-8")
            seen = []
            with mock.patch.object(check, "check_task", lambda *a, **k: seen.append(a)), \
                    mock.patch.object(unity.ugfroot, "check_free", lambda *a: 100.0), \
                    contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()) as err:
                with self.assertRaises(SystemExit) as stopped:
                    cli.main([str(repo), "--task", str(path), "--scratch", str(Path(tmp) / ("s" * 80))])
            self.assertEqual((stopped.exception.code, seen), (2, []))
            self.assertIn("--scratch", err.getvalue())
            self.assertIn("longer than 90 characters", err.getvalue())

    def test_a_run_deletes_a_shared_copy_after_its_last_task_and_writes_its_progress(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo, start, fix, _ = make_game(tmp)
            paths, released, progress = [], [], []
            for name, seed in (("g-fix-one", {"commit": start, "reference": fix}),
                               ("g-fix-two", {"commit": fix, "reference": fix})):
                path = Path(tmp) / f"{name}.json"
                task = task_with(probe())
                path.write_text(json.dumps({**task, "name": name, "seed": {**task["seed"], **seed}}),
                                encoding="utf-8")
                paths.append(str(path))
            out = Path(tmp) / "out"

            def fake(repo_, task, raw, scratch, out_, **kw):
                progress.append((out / "progress.txt").read_text(encoding="utf-8"))
                return {"task": task["name"], "verdict": "VALID", "reasons": [], "seconds": 60}

            with mock.patch.object(check, "check_task", fake), \
                    mock.patch.object(check.Builds, "release", lambda self, sha: released.append(sha)), \
                    mock.patch.object(unity.ugfroot, "check_free", lambda *a: 100.0), \
                    contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                code = cli.main([str(repo), "--task", paths[0], "--task", paths[1], "--scratch",
                                 str(Path(tmp) / "s"), "--out", str(out)])
            self.assertEqual(code, 0)
            self.assertEqual(released, [start, fix], "start after task one; fix, shared, only after task two")
            self.assertIn("0 of 2 task(s) done", progress[0])
            self.assertIn("checking g-fix-two", progress[1])
            final = (out / "progress.txt").read_text(encoding="utf-8")
            self.assertIn("2 of 2 task(s) done", final)
            self.assertIn("finished", final)
            self.assertIn("VALID   g-fix-one  (1 min)", final)
            self.assertTrue(json.loads((out / "progress.json").read_text(encoding="utf-8"))["finished"])

    def test_the_default_scratch_is_on_the_repos_own_drive(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repos" / "metro-runner"
            repo.mkdir(parents=True)
            drive = os.path.splitdrive(os.path.realpath(tmp))[0]
            self.assertEqual(cli.default_scratch(repo, root=Path(tmp) / "root"),
                             Path(os.path.realpath(tmp)) / "root" / ".task-check", "the machine root when it is there")
            other = "Z:" if drive.upper() != "Z:" else "Y:"
            self.assertEqual(cli.default_scratch(repo, root=other + "\\Work"),
                             Path(os.path.realpath(tmp)) / ".task-check", "else beside the repos' folder")
            link = Path(tmp) / "games"
            if subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(Path(tmp) / "repos")],
                              capture_output=True).returncode == 0:
                self.assertEqual(cli.default_scratch(link / "metro-runner", root=other + "\\Work"),
                                 Path(os.path.realpath(tmp)) / ".task-check", "a junction is followed")

    def test_one_line_per_task(self):
        self.assertEqual(cli.line({"task": "a", "verdict": "VALID", "reasons": []}), "VALID   a")
        self.assertEqual(cli.line({"task": "b", "verdict": "INVALID", "reasons": ["x", "y"]}), "INVALID b: x; y")


class SavedData(unittest.TestCase):
    def test_a_copys_saves_go_under_its_own_company_name(self):
        # TaskProbe/Editor/Build.cs Tag: the same name from the same folder, whatever its case
        name = seeds.saves_company("C:/Scratch/ABC123")
        self.assertRegex(name, r"^TaskProbe\.[0-9a-f]{12}$")
        self.assertEqual(name, seeds.saves_company(r"c:\scratch\abc123" if os.name == "nt" else "C:/Scratch/ABC123"))
        self.assertNotEqual(name, seeds.saves_company("C:/Scratch/ABC124"))

    def test_removing_a_folder_forgets_the_saves_of_the_projects_in_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "run" / "copy"
            (project / "ProjectSettings").mkdir(parents=True)
            (project / "ProjectSettings" / "ProjectVersion.txt").write_text("m_EditorVersion: 6000.3.1f1\n")
            forgotten = []
            with mock.patch.object(seeds, "forget_saves", forgotten.append):
                seeds.remove(Path(tmp) / "run")
            self.assertEqual(forgotten, [project])
            self.assertFalse((Path(tmp) / "run").exists())

    @unittest.skipUnless(sys.platform == "win32", "the Windows registry and known folders")
    def test_forgetting_a_copy_deletes_only_names_of_its_own_form(self):
        """Whatever the copy's path (empty, a drive's root, with .., a trailing separator, a junction), the only
        things deleted are HKCU\\Software\\TaskProbe.<12 hex> and TaskProbe_<12 hex> / TaskProbe.<12 hex> directly in
        LocalLow and the temp folder."""
        import winreg

        keys, folders = [], []
        with tempfile.TemporaryDirectory() as tmp:
            link = Path(tmp) / "junction"
            subprocess.run(["cmd", "/c", "mklink", "/J", str(link), tmp], capture_output=True)
            odd = ["", ".", "..", "C:", "C:\\", "\\", "C:\\tc\\x\\", "C:/tc/x/", "a\\..\\..\\b", str(link),
                   "TaskProbe_0123456789ab", "\\\\?\\C:\\tc\\x"]
            with mock.patch.object(seeds, "_drop_key", lambda root, name: keys.append((root, name))), \
                    mock.patch.object(seeds, "_saves_folders", lambda: ("C:\\L", "C:\\T\\")), \
                    mock.patch.object(seeds.shutil, "rmtree", lambda path, **kw: folders.append(path)):
                for path in odd:
                    seeds.forget_saves(path)
        self.assertEqual(len(keys), len(odd))
        for root, name in keys:
            self.assertEqual(root, winreg.HKEY_CURRENT_USER)
            self.assertRegex(name, r"^Software\\TaskProbe\.[0-9a-f]{12}$")
        self.assertEqual(len(folders), 3 * len(odd))
        for path in folders:
            self.assertRegex(path, r"^(C:\\L\\TaskProbe_|C:\\T\\TaskProbe[._])[0-9a-f]{12}$")

    @unittest.skipUnless(sys.platform == "win32", "Windows known folders")
    def test_locallow_is_windows_own_whatever_the_profile_variables_say(self):
        low, temp = seeds._saves_folders()
        self.assertTrue(os.path.isabs(low) and low.lower().endswith("\\appdata\\locallow"), low)
        self.assertTrue(os.path.isabs(temp), temp)
        for env in ({}, {"USERPROFILE": "C:\\nowhere", "LOCALAPPDATA": "C:\\nowhere\\AppData\\Local"}):
            kept = {k: v for k, v in os.environ.items()
                    if k.upper() not in ("USERPROFILE", "HOMEDRIVE", "HOMEPATH", "HOME", "APPDATA", "LOCALAPPDATA")}
            with mock.patch.dict(os.environ, {**kept, **env}, clear=True):
                self.assertEqual(seeds._saves_folders()[0], low, f"never ~ (a relative path) or {env}")

    def test_a_folder_goes_only_by_its_exact_name_in_an_absolute_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            parent, outside = Path(tmp) / "LocalLow", Path(tmp) / "TaskProbe_0123456789ab"
            names = ["TaskProbe_0123456789ab", "TaskProbe.0123456789ab", "TaskProbe_0123456789a",
                     "TaskProbe_0123456789abc", "TaskProbe-0123456789ab", "other"]
            for folder in [outside, parent / "rel" / names[0]] + [parent / name for name in names]:
                folder.mkdir(parents=True)
            for name in names + ["..", ".", "", "..\\TaskProbe_0123456789ab", "other\\..\\..\\TaskProbe_0123456789ab"]:
                seeds._drop_folder(str(parent), name)
            for relative in (None, "", "rel"):
                with contextlib.chdir(parent):
                    seeds._drop_folder(relative, names[0])
            self.assertEqual(sorted(p.name for p in parent.iterdir()), sorted(names[2:] + ["rel"]))
            self.assertTrue(outside.is_dir(), "nothing outside the folder")
            self.assertTrue((parent / "rel" / names[0]).is_dir(), "nothing in a relative folder")
        with tempfile.TemporaryDirectory() as tmp:  # (Windows folder names ignore case: one folder for both spellings)
            (Path(tmp) / "TaskProbe_0123456789AB").mkdir()
            for name in ("TaskProbe_0123456789AB", "taskprobe_0123456789ab"):
                seeds._drop_folder(tmp, name)
            self.assertTrue((Path(tmp) / "TaskProbe_0123456789AB").is_dir(), "only the name as saves_company spells it")

    @unittest.skipUnless(sys.platform == "win32", "junctions")
    def test_a_folder_is_deleted_without_going_through_a_link(self):
        with tempfile.TemporaryDirectory() as tmp:
            outside, parent = Path(tmp) / "outside", Path(tmp) / "LocalLow"
            outside.mkdir()
            (outside / "keep.txt").write_text("not the copy's", encoding="utf-8")
            parent.mkdir()
            linked, real = parent / "TaskProbe_0123456789ab", parent / "TaskProbe.0123456789ab"
            junction = lambda at: subprocess.run(["cmd", "/c", "mklink", "/J", str(at), str(outside)],  # noqa: E731
                                                 capture_output=True).returncode == 0
            if not junction(linked):
                self.skipTest("no junctions here")
            real.mkdir()
            self.assertTrue(junction(real / "inner"))
            seeds._drop_folder(str(parent), linked.name)
            seeds._drop_folder(str(parent), real.name)
            self.assertTrue((outside / "keep.txt").is_file(), "never through a junction, in the name's place or inside")
            self.assertFalse(real.exists())
            os.rmdir(linked)

    def test_the_registry_walk_ends_and_never_goes_through_a_link(self):
        """A subkey that can't be deleted ends the walk (it looped for ever); a symbolic link is neither followed nor
        deleted (through one, the walk deleted a key that wasn't the company's)."""
        fake = FakeRegistry({"Software": {"TaskProbe.0123456789ab": {"Smoke Test": {"Sub": {}}, "Locked": "locked",
                                                                     "Link": ("link", ("Software", "Other"))},
                                          "Other": {"Keep": {}}}})
        with mock.patch.dict(sys.modules, {"winreg": fake}):
            seeds._drop_key(fake.HKEY_CURRENT_USER, "Software\\TaskProbe.0123456789ab")
        self.assertEqual(fake.deleted, [("Software", "TaskProbe.0123456789ab", "Smoke Test", "Sub"),
                                        ("Software", "TaskProbe.0123456789ab", "Smoke Test")])
        self.assertIn("Keep", fake.tree["Software"]["Other"], "the link's target is left alone")
        self.assertLess(fake.listed, 20, "each key's subkeys listed once")

    @unittest.skipUnless(sys.platform == "win32", "the Windows registry and known folders")
    def test_forgetting_a_copy_deletes_its_key_and_folders_and_nothing_beside_them(self):
        """Real ones, made by the test under names of the guarded form, for a copy that never existed."""
        import winreg

        with tempfile.TemporaryDirectory() as tmp:
            project, other = Path(tmp) / "copy", Path(tmp) / "other copy"
            company, neighbour = seeds.saves_company(project), seeds.saves_company(other)
            low, temp = seeds._saves_folders()
            made = []
            try:
                for name in (company, neighbour):
                    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, f"Software\\{name}\\Smoke Test\\Sub") as key:
                        winreg.SetValueEx(key, "score_h1", 0, winreg.REG_DWORD, 3)
                    for folder in (Path(low) / name.replace(".", "_"), Path(temp) / name.replace(".", "_"),
                                   Path(temp) / name / "Smoke Test" / "Crashes"):
                        folder.mkdir(parents=True)
                        (folder / "saved.bin").write_bytes(b"x")
                        made.append(folder)
                seeds.forget_saves(project)
                self.assertEqual([f.exists() for f in made], [False] * 3 + [True] * 3, "the copy's, not the other's")
                with self.assertRaises(OSError):
                    winreg.OpenKey(winreg.HKEY_CURRENT_USER, f"Software\\{company}").Close()
                winreg.OpenKey(winreg.HKEY_CURRENT_USER, f"Software\\{neighbour}\\Smoke Test\\Sub").Close()
            finally:
                for name in (company, neighbour):
                    seeds.forget_saves(project if name == company else other)


class FakeRegistry:
    """Just enough of winreg for seeds._drop_key over `tree`: a key is a dict of its subkeys, "locked" one that can't be
    deleted, ("link", path) a symbolic link to the key at `path` (followed unless opened with REG_OPTION_OPEN_LINK)."""

    HKEY_CURRENT_USER, KEY_READ, REG_OPTION_OPEN_LINK = (), 0x20019, 8

    def __init__(self, tree):
        self.tree, self.deleted, self.listed = tree, [], 0

    def _node(self, path):
        node = self.tree
        for part in path:
            node = node[part] if isinstance(node, dict) and part in node else None
            if node is None:
                raise FileNotFoundError(path)
        return node

    def OpenKey(self, root, name, reserved=0, access=0):  # noqa: N802 (winreg's names)
        path = tuple(root) + tuple(name.split("\\"))
        node = self._node(path)
        if isinstance(node, tuple) and not reserved & self.REG_OPTION_OPEN_LINK:
            path = node[1]
        return contextlib.nullcontext(path)

    def QueryValueEx(self, key, name):  # noqa: N802
        node = self._node(key)
        if name == "SymbolicLinkValue" and isinstance(node, tuple):
            return "\\Registry\\User\\S-1\\" + "\\".join(node[1]), 6
        raise FileNotFoundError(name)

    def EnumKey(self, key, index):  # noqa: N802
        self.listed += 1
        node = self._node(key)
        names = list(node) if isinstance(node, dict) else []
        if index >= len(names):
            raise OSError("no more")
        return names[index]

    def DeleteKey(self, root, name):  # noqa: N802
        path = tuple(root) + tuple(name.split("\\"))
        node = self._node(path)
        if isinstance(node, tuple):
            path, node = node[1], self._node(node[1])  # RegDeleteKey goes through a link to its target
        if node == "locked" or (isinstance(node, dict) and node):
            raise PermissionError(path)
        del self._node(path[:-1])[path[-1]]
        self.deleted.append(path)


class Limiter(unittest.TestCase):
    def test_a_limiter_that_cant_be_started_is_an_error_not_a_failed_build(self):
        refused = "& : File C:\\Work\\tools\\unity-heavy.ps1 cannot be loaded because running scripts is disabled"
        with mock.patch.object(unity, "run", lambda argv, cwd, timeout, wrapper=False: unity.Result(1, refused, 0.1)):
            machine = unity.Machine(Path("C:/U/Unity.exe"), Path("C:/Work/tools/unity-heavy.ps1"))
            with self.assertRaises(unity.LimiterRefused) as raised:
                machine.job("task-check build x", ["C:/U/Unity.exe", "-batchmode"], ".", 60)
        self.assertIn("--direct", str(raised.exception))
        self.assertTrue(issubclass(unity.LimiterRefused, RuntimeError), "check_task reports it as ERROR")


# A stand-in player: writes its pid and its parent's (desk.py's) to argv[1], then sleeps argv[2] seconds.
PLAYER = ("import json, os, sys, time\n"
          "with open(sys.argv[1] + '.tmp', 'w') as f:\n"
          "    json.dump({'pid': os.getpid(), 'parent': os.getppid()}, f)\n"
          "os.replace(sys.argv[1] + '.tmp', sys.argv[1])\n"
          "time.sleep(float(sys.argv[2]))\n")
# A stand-in for unity-heavy.ps1: while it waits for a slot it runs a helper of its own (the real one runs nvidia-smi),
# then starts its job as the real one does and exits with its code; STAND_IN_EXIT: it gives up without starting it.
LIMITER = """[CmdletBinding(PositionalBinding = $false)]
param([string]$Label, [switch]$Gpu, [Parameter(ValueFromRemainingArguments = $true)][string[]]$Command)
if ($Command.Count -and $Command[0] -eq '--') { $Command = $Command[1..($Command.Count - 1)] }
& ping -n 3 127.0.0.1 | Out-Null
if ($env:STAND_IN_EXIT) { exit [int]$env:STAND_IN_EXIT }
Start-Sleep -Seconds ([int]$env:STAND_IN_WAIT)
$psi = New-Object Diagnostics.ProcessStartInfo $Command[0], ((@($Command | Select-Object -Skip 1) | ForEach-Object { '"' + $_ + '"' }) -join ' ')
$psi.UseShellExecute = $false
$proc = [Diagnostics.Process]::Start($psi)
$proc.WaitForExit()
exit $proc.ExitCode
"""


def alive(pid, seconds=5.0):
    """Whether process `pid` still runs after up to `seconds` (a killed process takes a moment to go). Never os.kill:
    on Windows it terminates the process."""
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    end = time.monotonic() + seconds
    while True:
        handle = kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not handle:
            return False
        code = wintypes.DWORD()
        running = kernel32.GetExitCodeProcess(handle, ctypes.byref(code)) and code.value == 259  # STILL_ACTIVE
        kernel32.CloseHandle(handle)
        if not running:
            return False
        if time.monotonic() > end:
            return True
        time.sleep(0.1)


@unittest.skipUnless(sys.platform == "win32", "Windows processes")
class Jobs(unittest.TestCase):
    """unity.run on real processes: a stand-in limiter, and a stand-in player started through desk.py."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        (self.tmp / "player.py").write_text(PLAYER, encoding="utf-8")
        (self.tmp / "unity-heavy.ps1").write_text(LIMITER, encoding="utf-8")
        self.direct = unity.Machine(Path("C:/U/Unity.exe"), None)
        self.limited = unity.Machine(Path("C:/U/Unity.exe"), self.tmp / "unity-heavy.ps1")
        self.pids = []

    def tearDown(self):
        for pid in self.pids:  # a failed test leaves nothing running
            if alive(pid, 0):
                subprocess.run(["taskkill", "/F", "/PID", str(pid)], capture_output=True)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def play(self, seconds):
        """The argv of a play (desk.py and the stand-in player) and the file its player writes its pids to."""
        info = self.tmp / f"player{len(self.pids)}.json"
        return [sys.executable, unity.DESK, sys.executable, self.tmp / "player.py", info, str(seconds)], info

    def ran(self, info):
        found = json.loads(info.read_text(encoding="utf-8"))
        self.pids += [found["pid"], found["parent"]]
        return found["pid"], found["parent"]

    def test_the_wait_for_a_slot_isnt_the_jobs_time(self):
        with mock.patch.object(unity, "QUEUE_POLL", 0.5), mock.patch.dict(os.environ, {"STAND_IN_WAIT": "3"}):
            found = self.limited.job("t", [sys.executable, "-c", "import time; time.sleep(2)"], self.tmp, 3)
        self.assertEqual((found.exit_code, found.timed_out), (0, False), "its 3 s count from the job's start")
        self.assertGreater(found.waited, 3, "the limiter's wait, its own helper's run included")

    def test_a_limiter_that_never_starts_its_job_still_ends(self):
        with mock.patch.object(unity, "QUEUE_POLL", 0.5), mock.patch.dict(os.environ, {"STAND_IN_EXIT": "2"}):
            found = self.limited.job("t", [sys.executable, "-c", "import time; time.sleep(60)"], self.tmp, 60)
        self.assertEqual((found.exit_code, found.timed_out, found.waited), (2, False, 0.0))

    def test_a_timeout_kills_the_job_and_the_player_desk_py_started(self):
        for machine in (self.direct, self.limited):
            argv, info = self.play(60)
            with mock.patch.object(unity, "QUEUE_POLL", 0.5), mock.patch.dict(os.environ, {"STAND_IN_WAIT": "0"}):
                found = machine.job("t", argv, self.tmp, 4, gpu=True)
            player, desk_py = self.ran(info)
            self.assertEqual((found.exit_code, found.timed_out), (None, True))
            self.assertFalse(alive(player), "the player")
            self.assertFalse(alive(desk_py), "desk.py")

    def test_an_interrupt_kills_the_job_and_the_player_desk_py_started(self):
        run = unity.run
        for machine in (self.direct, self.limited):
            argv, info = self.play(60)

            def clock():  # Ctrl+C once the player runs
                if info.exists():
                    raise KeyboardInterrupt
                return time.monotonic()

            with mock.patch.object(unity, "QUEUE_POLL", 0.5), mock.patch.dict(os.environ, {"STAND_IN_WAIT": "0"}), \
                    mock.patch.object(unity, "run", lambda *a, **k: run(*a, clock=clock, **k)):
                with self.assertRaises(KeyboardInterrupt):
                    machine.job("t", argv, self.tmp, 120, gpu=True)
            player, desk_py = self.ran(info)
            self.assertFalse(alive(player), "the player")
            self.assertFalse(alive(desk_py), "desk.py")


@unittest.skipUnless(sys.platform == "win32", "Windows desktops")
class Desk(unittest.TestCase):
    """desk.py with real stand-in players."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(suffix=" with space"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def desk(self, *argv, **kw):
        return subprocess.run([sys.executable, unity.DESK, *[str(a) for a in argv]], capture_output=True, text=True,
                              **kw)

    def test_it_exits_with_the_players_exit_code(self):
        self.assertEqual(self.desk(sys.executable, "-c", "import sys; sys.exit(7)").returncode, 7)
        crashed = self.desk(sys.executable, "-c", "import ctypes; ctypes.windll.kernel32.ExitProcess(0xC0000005)")
        self.assertEqual(crashed.returncode, 0xC0000005, "an NTSTATUS, as Windows gives it")

    def test_the_player_gets_its_arguments_folder_and_environment(self):
        show = self.tmp / "show args.py"
        show.write_text("import json, os, sys\njson.dump({'argv': sys.argv[1:-1], 'cwd': os.getcwd(), "
                        "'marker': os.environ.get('DESK_MARKER')}, open(sys.argv[-1], 'w'))\n", encoding="utf-8")
        args = ["plain", "with space", 'with "quotes"', "trailing\\", "trailing space\\", "", "-x=C:\\a b\\"]
        work = self.tmp / "build folder"
        work.mkdir()
        out = self.tmp / "seen.json"
        self.desk(sys.executable, show, *args, out, cwd=work, env={**os.environ, "DESK_MARKER": "x"})
        seen = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual(seen, {"argv": args, "cwd": str(work), "marker": "x"},
                         "quoted by the Windows rules (subprocess.list2cmdline); desk.py's folder and environment")

    def test_a_call_that_fails_is_named_with_windows_reason(self):
        found = self.desk(self.tmp / "no such.exe")
        self.assertEqual(found.returncode, 1)
        self.assertIn("desk.py: [WinError 2] CreateProcessW", found.stderr)
        self.assertIn("cannot find the file", found.stderr)

    def test_a_player_never_outlives_desk_py(self):
        info = self.tmp / "player.json"
        (self.tmp / "player.py").write_text(PLAYER, encoding="utf-8")
        started = subprocess.Popen([sys.executable, unity.DESK, sys.executable, self.tmp / "player.py", info, "60"])
        try:
            for _ in range(200):
                if info.exists():
                    break
                time.sleep(0.1)
            player = json.loads(info.read_text(encoding="utf-8"))["pid"]
            subprocess.run(["taskkill", "/F", "/PID", str(started.pid)], capture_output=True)  # desk.py alone
            started.wait()
            self.assertFalse(alive(player), "the job object takes the player with desk.py")
        finally:
            if info.exists() and alive(json.loads(info.read_text(encoding="utf-8"))["pid"], 0):
                subprocess.run(["taskkill", "/F", "/PID", str(json.loads(info.read_text())["pid"])],
                               capture_output=True)

    def test_two_plays_share_the_desktop_and_leave_nothing_behind(self):
        import ctypes

        from task_check import desk

        outs = [self.tmp / f"{i}.json" for i in range(2)]
        both = [subprocess.Popen([sys.executable, unity.DESK, sys.executable, "-c",
                                  f"import json, time; time.sleep(1); json.dump(1, open(r'{o}', 'w'))"]) for o in outs]
        self.assertEqual([p.wait() for p in both], [0, 0])
        self.assertTrue(all(o.is_file() for o in outs))
        kernel32, user32 = ctypes.WinDLL("kernel32"), ctypes.WinDLL("user32")
        kernel32.GetCurrentProcess.restype = ctypes.c_void_p
        kernel32.GetProcessHandleCount.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint32)]
        user32.OpenDesktopW.restype = ctypes.c_void_p
        user32.OpenDesktopW.argtypes = [ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32]
        user32.CloseDesktop.argtypes = [ctypes.c_void_p]

        def handles():
            count = ctypes.c_uint32()
            kernel32.GetProcessHandleCount(kernel32.GetCurrentProcess(), ctypes.byref(count))
            return count.value

        name = f"TaskProbeTest{os.getpid()}"  # a desktop of the test's own: real plays may be on TaskProbe now
        desk.run([sys.executable, "-c", "pass"], name)  # the first call loads what it needs once
        before = handles()
        self.assertEqual(desk.run([sys.executable, "-c", "import sys; sys.exit(3)"], name), 3)
        with self.assertRaisesRegex(OSError, "CreateProcessW"):
            desk.run([self.tmp / "no such.exe"], name)
        self.assertEqual(handles(), before, "every handle closed, on success and on failure")
        left = user32.OpenDesktopW(name, 0, False, 0x0001)
        if left:
            user32.CloseDesktop(left)
        self.assertFalse(left, "the desktop goes with its last play")


if __name__ == "__main__":
    unittest.main()
