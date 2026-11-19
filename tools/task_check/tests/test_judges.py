"""A judge check's screenshots saved for a person to answer: which ones the cloud's judge is shown (evenly spaced plus
named, 20 at most), where they are saved, the blind copy, and the --no-judge-shots flag. Unity is faked."""

import contextlib
import io
import json
import random
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from helpers import FakeProject, measuring, probe, side, task_with
from test_check import fake_probe_package, make_game

from task_check import check, cli, judges, seeds, trial, unity



def setUpModule():
    global _probe_patch
    _probe_patch = mock.patch.object(seeds, "PROBE_SOURCE", fake_probe_package(tempfile.mkdtemp()))
    _probe_patch.start()


def tearDownModule():
    _probe_patch.stop()


RUBRIC = [{"key": "door_open", "criterion": "The door stands open.", "required": True},
          {"key": "lit", "criterion": "The room is lit.", "weight": 2}]


def play(name="open_door", seconds=10, shots=(), **extra):
    inputs = [{"t": 1.0, "key": "<Keyboard>/e", "press": True}, {"t": 1.2, "key": "<Keyboard>/e", "press": False}]
    inputs += [{"t": 2.0 + i, "shot": s} for i, s in enumerate(shots)]
    return {"name": name, "seconds": seconds, "inputs": inputs, **extra}


def judge(name="door_looks_open", plays=None, **extra):
    found = {"kind": "judge", "name": name, "question": "Does the door open?", "rubric": RUBRIC, **extra}
    if plays is not None:
        found["plays"] = plays
    return found


class Shooting(FakeProject):
    """A fake project whose plays also write their screenshots: shot_NN.png, and shot_<name>.png per `shot` input."""

    def play(self, seconds, shots, timeout, scene=None, inputs=None, queries=None, args=(), every=None, player=None,
             keep_saves=False):
        self.plays.append({"seconds": seconds, "shots": shots, "scene": scene, "inputs": inputs, "queries": queries,
                           "args": list(args), "every": every, "player": player})
        named = [f"shot_{i['shot']}.png" for i in inputs or [] if "shot" in i]
        even = [f"shot_{i:02d}.png" for i in range(shots)]
        probe, log = (self.answer or measuring(0))(seconds, shots, queries)
        probe["screenshots"] = even[:1] + named + even[1:]  # a named one taken between the first two even ones
        files = {"probe.json": json.dumps(probe).encode(),
                 **{n: f"{self.folder.name}:{seconds}:{n}".encode() for n in even + named}}
        return unity.Played(0, False, "", 1.0, probe, log, files)


class Selection(unittest.TestCase):
    def test_the_evenly_spaced_ones_are_picked_evenly_and_every_named_one_kept_in_order(self):
        names = [f"shot_{i:02d}.png" for i in range(10)]
        names.insert(3, "shot_door.png")
        self.assertEqual(judges.chosen(names, 5), ["shot_01.png", "shot_door.png", "shot_03.png", "shot_05.png",
                                                   "shot_07.png", "shot_09.png"])
        self.assertEqual(judges.chosen(names[:3], 5), names[:3], "fewer than asked: all of them")

    def test_the_plugin_takes_them_at_the_middle_of_each_slice(self):
        self.assertEqual(judges.even_times(20, 4), [2.5, 7.5, 12.5, 17.5])
        self.assertEqual(judges.spread(list(range(8)), 4), [1, 3, 5, 7])

    def test_a_side_shows_twenty_at_most(self):
        check_ = judges.judge(judge(plays=[play(f"p{i}", shots=["a", "b"]) for i in range(4)], shots=5))
        played = {f"p{i}": ({"screenshots": [f"shot_{j:02d}.png" for j in range(5)] + ["shot_a.png", "shot_b.png"]},
                            {f"shot_{j:02d}.png": b"x" for j in range(5)} | {"shot_a.png": b"x", "shot_b.png": b"x"})
                  for i in range(4)}
        rows = judges.selection(check_, played)
        self.assertEqual([len(p) for _, _, p in rows], [7, 7, 6, 0])
        self.assertEqual(rows[0][2][0], ("shot_00.png", "p0_01.png"))

    def test_without_plays_a_judge_is_shown_the_idle_play_and_the_drive_whole(self):
        check_ = judges.judge(judge())
        self.assertEqual([(p, s) for p, _, s in judges.plays(check_)], [("look", None), ("drive", None)])

    def test_a_task_play_is_played_with_the_most_screenshots_a_judge_asks(self):
        task = task_with(probe(play=play()), judge("a", plays=[play()], shots=4),
                         judge("b", plays=[play()], shots=8, required=False))
        self.assertEqual(judges.play_shots(task), {"open_door": 8})
        project = Shooting(folder="start")
        s = side("start", project, task)
        s.probe_play(check.tasks.play(play()))
        self.assertEqual(project.plays[0]["shots"], 8)


class Saved(unittest.TestCase):
    def sides(self, task):
        return {name: side(name, Shooting(folder=name), task) for name in ("start", "reference")}

    def test_the_layout_the_ask_and_the_blind_copy(self):
        task = task_with(probe(play=play(shots=["door"])), judge(plays=[play(shots=["door"])], before=True))
        sides = self.sides(task)
        sides["start"].probe_play(check.tasks.play(play(shots=["door"])))  # the probe's play, made by the grade
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "probe-task" / "judge-shots"
            records = check.save_judge_shots(task, sides, folder, "probe-task/judge-shots/", blind=True,
                                             log=lambda *a: None, rng=random.Random(1))
            base = folder / "door_looks_open"
            self.assertEqual(sorted(p.name for p in (base / "start").iterdir()),
                             [f"open_door_{i:02d}.png" for i in range(1, 7)])
            self.assertEqual((base / "start" / "open_door_02.png").read_bytes(), b"start:10:shot_door.png",
                             "the named shot in the order taken")
            self.assertEqual(len(sides["start"].project.plays), 1, "the probe's own play is reused")
            key = json.loads((base / "blind" / "key.json").read_text())
            self.assertEqual(sorted(key.values()), ["reference", "start"])
            self.assertEqual(sorted(key), ["A", "B"])
            for letter, name in key.items():
                self.assertEqual([p.read_bytes() for p in sorted((base / "blind" / letter).iterdir())],
                                 [p.read_bytes() for p in sorted((base / name).iterdir())])
            ask = (base / "ask.md").read_text()
            for text in ("Does the door open?", "| door_open | yes | 1 | The door stands open. |",
                         "| lit | no | 2 | The room is lit. |", "Keep the hero on the ground.", "blind/key.json",
                         "start fails every required rubric item", "the start as BEFORE"):
                self.assertIn(text, ask)
            self.assertNotIn("picture(s)", ask, "a blind ask never tells a side's picture count")
            self.assertIn("`start/`: 6 picture(s)", (base / "sides.md").read_text())
            record = records["door_looks_open"]
            self.assertEqual(record["status"], "shots saved for start/reference, answer needed")
            self.assertEqual(record["folder"], "probe-task/judge-shots/door_looks_open/")
            self.assertEqual(judges.line("door_looks_open", record),
                             "judge door_looks_open: shots saved for start/reference, answer needed")

    def test_the_blind_copy_holds_only_pictures_both_sides_have(self):
        task = task_with(probe(), judge(before=True))
        chk = next(iter(judges.judges(task)))
        shots = lambda n: {f"shot_{i:02d}.png": f"{i}".encode() for i in range(n)}  # noqa: E731
        played = {"start": {"look": (None, shots(6)), "drive": (None, shots(5))},
                  "reference": {"look": (None, shots(6)), "drive": (None, shots(8))}}
        with tempfile.TemporaryDirectory() as tmp:
            record = judges.save(task, chk, played, tmp, blind=True, rng=random.Random(1))
            base = Path(tmp) / chk["name"]
            a, b = (sorted(p.name for p in (base / "blind" / x).iterdir()) for x in "AB")
            self.assertEqual(a, b, "both blind folders hold the same picture names")
            self.assertEqual(len(a), 6 + 5)
            self.assertTrue(any("left out of the blind copy" in n for n in record["notes"]))
            self.assertNotIn("left out", (base / "ask.md").read_text(), "side notes stay out of the blind ask")
            self.assertIn("left out of the blind copy", (base / "sides.md").read_text())

    def test_the_shared_plays_are_played_whole_not_cut_from_the_boot(self):
        task = task_with({"kind": "boot", "name": "boots", "seconds": 60}, probe(), judge())
        s = side("reference", Shooting(folder="reference"), task)
        s.boot(60)
        s.probe_play("look")
        with tempfile.TemporaryDirectory() as tmp:
            check.save_judge_shots(task, {"reference": s}, Path(tmp), log=lambda *a: None)
            saved = sorted(p.name for p in (Path(tmp) / "door_looks_open" / "reference").iterdir())
        self.assertEqual(saved, sorted([f"look_{i:02d}.png" for i in range(1, 7)]
                                       + [f"drive_{i:02d}.png" for i in range(1, 9)]))
        self.assertEqual([(p["seconds"], p["shots"]) for p in s.project.plays], [(60, 6), (20, 6), (22, 8)])

    def test_a_side_that_didnt_build_is_noted_and_no_blind_copy_is_made(self):
        task = task_with(judge())
        sides = {"start": side("start", Shooting(build_exit=6, folder="start"), task),
                 "reference": side("reference", Shooting(folder="reference"), task)}
        with tempfile.TemporaryDirectory() as tmp:
            record = check.save_judge_shots(task, sides, Path(tmp), blind=True, log=lambda *a: None)["door_looks_open"]
            self.assertFalse((Path(tmp) / "door_looks_open" / "blind").exists())
            self.assertEqual(record["status"], "shots saved for reference, answer needed")
            self.assertIn("didn't build", record["notes"][0])


class Cloud(unittest.TestCase):
    """ask.md says what the cloud's judge is given beside the pictures, without writing a file."""

    @staticmethod
    def made(n_look=6, n_drive=8, probe_=None):
        shots = lambda n: {f"shot_{i:02d}.png": b"x" for i in range(n)}  # noqa: E731
        return {"look": (probe_, shots(n_look)), "drive": (probe_, shots(n_drive))}

    def test_readings_are_the_cloud_prompts_track_and_camera_lines(self):
        """The track is about ten rows as JSON; the camera line is judging.camera_text's, word for word (its z as
        height and centimetres, the Unreal grader's, kept as the cloud says it)."""
        track = [[t / 10, 1.0, 2.0, 300.0] for t in range(30)]
        camera = [[t / 10, 1.0, 2.0, 500.0, 20.0, 0.0, 60.0] for t in range(30)]
        chk = judges.judge(judge())
        said = judges.readings(chk, self.made(probe_={"track": track, "camera": camera}))
        self.assertEqual([label for label, _ in said], ["idle play, 20 s, no input", "scripted drive, 22 s"])
        self.assertEqual(said[0][1], "player position track (seconds, x, y, z in cm): "
                         + json.dumps(track[::3])[:1200] + "; camera (median of 30 samples): 2.00 m above the player, "
                         "0.00 m from it horizontally, pitch 20.0°, field of view 60°")
        self.assertEqual(judges.readings(chk, self.made())[0][1],
                         "player position track (seconds, x, y, z in cm): none (no player pawn)")

    def test_a_route_note_says_what_the_cloud_adds_never_4_of_6(self):
        """The Unity grader shows a route's 8 screenshots after the plays: alone, within the 20 the judge is shown
        (the idle play keeps all 6); compared, as panels too, and never played on the reference."""
        alone = judges.judge(judge(route="Tools/route.json"))
        saved = {"reference": judges.selection(alone, self.made())}
        text = judges.ask_text({"instruction": "x"}, alone, ["reference"], saved=saved)
        self.assertNotIn("4 of", text)
        self.assertIn("route file `Tools/route.json` (8 screenshots, after the plays above) on the developer's game: "
                      "with the 14 pictures above, 6 of its 8 fit in the 20 the judge is shown", text)
        both = judges.judge(judge(route="Tools/route.json", before=True))
        text = judges.ask_text({"instruction": "x"}, both, ["reference"], saved=saved)
        self.assertIn("and on the start (BEFORE), never on the reference, and shows them as panels too", text)

    def test_a_comparing_judge_shows_its_panels_and_no_20_picture_limit(self):
        """A judge with `before` or `reference` is shown every screenshot as a panel in the cloud: no 20 limit, and
        ask.md lays out BEFORE | AFTER | REFERENCE for each side scored, "no screenshot" where a side has fewer."""
        chk = judges.judge(judge(plays=[play(seconds=30)], shots=24, before=True, reference=True))
        made = {"start": {"open_door": (None, {f"shot_{i:02d}.png": b"s" for i in range(23)})},
                "reference": {"open_door": (None, {f"shot_{i:02d}.png": b"r" for i in range(24)})}}
        saved = {side: judges.selection(chk, m) for side, m in made.items()}
        self.assertEqual([len(saved[s][0][2]) for s in ("start", "reference")], [23, 24])
        key = {"A": "start", "B": "reference"}
        text = judges.ask_text({"instruction": "x"}, chk, list(saved), blind=True, saved=saved, key=key)
        self.assertIn("## The panels the cloud's judge is shown", text)
        self.assertIn("### A as AFTER", text)
        self.assertIn("| task play open_door, 30 s, 1/24 | ![](start/open_door_01.png) | ![](blind/A/open_door_01.png) "
                      "| ![](reference/open_door_01.png) |", text)
        self.assertIn("| task play open_door, 30 s, 24/24 | no screenshot | no screenshot | "
                      "![](reference/open_door_24.png) |", text)
        alone = judges.judge(judge(plays=[play(seconds=30)], shots=24))
        self.assertEqual(len(judges.selection(alone, made["reference"])[0][2]), 20, "alone: 20 at most")
        self.assertNotIn("panels the cloud", judges.ask_text({"instruction": "x"}, alone, list(saved), saved=saved))


class Alone(unittest.TestCase):
    def test_a_start_never_played_leaves_the_reference_to_score_alone(self):
        """A start that doesn't build by design is never played: the reference alone is saved, blind as A, and its
        scores alone decide."""
        task = task_with(probe(), judge())
        chk = next(iter(judges.judges(task)))
        shots = {f"shot_{i:02d}.png": f"{i}".encode() for i in range(6)}
        with tempfile.TemporaryDirectory() as tmp:
            record = judges.save(task, chk, {"reference": {"look": (None, shots), "drive": (None, shots)}}, tmp,
                                 blind=True, rng=random.Random(1))
            self.assertTrue(record["blind"])
            self.assertEqual(json.loads((Path(tmp) / chk["name"] / "blind" / "key.json").read_text()), {"A": "reference"})
            (Path(tmp) / chk["name"] / "blind" / "answers.json").write_text('{"A": {"door_open": 1, "lit": 1}}')
            held = judges.kept(tmp, task)[chk["name"]]
            record = judges.save(task, chk, {"reference": {"look": (None, shots), "drive": (None, shots)}}, tmp,
                                 blind=True, held=held)
            self.assertEqual((record["status"], judges.decide(chk, record)), (judges.ANSWERED, []))


class Whole(unittest.TestCase):
    def run_check(self, tmp, judged=None, game=None, **kw):
        """check_task on a game made once under `tmp` (`game`, from an earlier call, to check it again), its task's
        judge `judged` (else a required one shown BEFORE and REFERENCE): (result, game)."""
        repo, start, fix, _ = game or make_game(tmp)
        task = task_with(probe(expect={"op": ">=", "calibrate": 0.5}), judged or judge(reference=True))
        task["seed"] = {**task["seed"], "commit": start, "reference": fix}
        names = {start[:12]: "start", fix[:12]: "reference"}
        projects = {"start": Shooting(measuring(-500), folder="start"),
                    "reference": Shooting(measuring(100), folder="reference")}
        with mock.patch.object(unity, "Project", lambda folder, m, label: projects[names[Path(folder).name]]), \
                mock.patch.object(unity.Machine, "for_project",
                                  classmethod(lambda cls, p, d=False, **_: cls(Path(p), None))), \
                mock.patch.object(unity.ugfroot, "check_free", lambda *a: 100.0):
            return check.check_task(repo, task, json.dumps(task).encode(), Path(tmp) / "scratch", Path(tmp) / "out",
                                    log=lambda *a: None, **kw), (repo, start, fix, _)

    @staticmethod
    def score(tmp, start, reference, name="door_looks_open"):
        """Write the writer's scores of the start and the reference into blind/answers.json, by the key's letters."""
        base = Path(tmp) / "out" / "probe-task" / "judge-shots" / name / "blind"
        key = json.loads((base / "key.json").read_text())
        (base / "answers.json").write_text(json.dumps({letter: {"start": start, "reference": reference}[side]
                                                       for letter, side in key.items()}), encoding="utf-8")

    def test_a_task_check_saves_both_sides_and_a_required_judge_waits_for_its_scores(self):
        """The Lab's model decides a required judge on the task's own fix; here the writer's blind scores do, so the
        task isn't VALID until they are written."""
        with tempfile.TemporaryDirectory() as tmp:
            result, _ = self.run_check(tmp)
            self.assertEqual(result["verdict"], "INVALID")
            self.assertEqual(result["reasons"], ["judge door_looks_open: shots saved for start/reference, answer needed"])
            self.assertIn("judge door_looks_open: shots saved for start/reference, answer needed", result["notes"])
            base = Path(tmp) / "out" / "probe-task" / "judge-shots" / "door_looks_open"
            for folder in ("start", "reference", "blind/A", "blind/B"):
                self.assertEqual(len(list((base / folder).iterdir())), 14, folder)
            ask = (base / "ask.md").read_text()
            self.assertIn('{"A": {"door_open": 0, "lit": 0}, "B": {"door_open": 0, "lit": 0}}', ask)
            self.assertIn("the start fails every required rubric item", ask)
            self.assertEqual(sorted(json.loads((base / "pictures.json").read_text())), ["reference", "start"])

    def test_the_scores_decide_once_written_and_stand_while_the_pictures_do(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, game = self.run_check(tmp)
            self.score(tmp, {"door_open": 0, "lit": 0.2}, {"door_open": 1, "lit": 0.5})
            result, _ = self.run_check(tmp, game=game)
            self.assertEqual((result["verdict"], result["reasons"]), ("VALID", []))
            self.assertEqual(result["judges"]["door_looks_open"]["status"], "scored in blind/answers.json")
            again, _ = self.run_check(tmp, game=game)
            self.assertEqual(again["verdict"], "VALID", "the scores were carried over to the folder made again")
            pictures = Path(tmp) / "out" / "probe-task" / "judge-shots" / "door_looks_open" / "pictures.json"
            changed = json.loads(pictures.read_text())
            changed["reference"]["look_01.png"] = "0" * 64
            pictures.write_text(json.dumps(changed))
            dropped, _ = self.run_check(tmp, game=game)
            self.assertEqual(dropped["reasons"], ["judge door_looks_open: shots saved for start/reference, answer "
                                                  "needed"])
            self.assertIn("reference: its pictures changed since they were scored, so its scores were dropped",
                          dropped["judges"]["door_looks_open"]["notes"])

    def test_a_reference_that_fails_or_a_start_that_passes_is_invalid(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, game = self.run_check(tmp)
            self.score(tmp, {"door_open": 0, "lit": 0}, {"door_open": 0.4, "lit": 1})
            result, _ = self.run_check(tmp, game=game)
            self.assertEqual(result["reasons"], ["reference fails judge door_looks_open on your scores (weighted 0.80; "
                                                 "below 0.5: door_open)"])
            self.score(tmp, {"door_open": 0.5, "lit": 0}, {"door_open": 1, "lit": 1})
            result, _ = self.run_check(tmp, game=game)
            self.assertEqual(result["reasons"], ["start already passes judge door_looks_open on your scores "
                                                 "(door_open)"])

    def test_scores_that_cant_be_read_stay_as_written_and_hold_the_task(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, game = self.run_check(tmp)
            self.score(tmp, {"door_open": 2}, {"door_open": 1, "lit": 1})
            result, _ = self.run_check(tmp, game=game)
            self.assertEqual(result["verdict"], "INVALID")
            record = result["judges"]["door_looks_open"]
            self.assertTrue(any(n.startswith("blind/answers.json: ") for n in record["notes"]), record["notes"])
            kept = Path(tmp) / "out" / "probe-task" / "judge-shots" / "door_looks_open" / "blind" / "answers.json"
            self.assertIn('"door_open": 2', kept.read_text(), "kept as written, to fix")

    def test_an_optional_judge_never_holds_the_task(self):
        with tempfile.TemporaryDirectory() as tmp:
            result, _ = self.run_check(tmp, judged=judge(reference=True, required=False))
            self.assertEqual((result["verdict"], result["reasons"]), ("VALID", []))

    def test_no_judge_shots_skips_them_and_leaves_a_required_judge_unscored(self):
        with tempfile.TemporaryDirectory() as tmp:
            result, _ = self.run_check(tmp, judge_shots=False)
            self.assertEqual((result["verdict"], result["judges"]), ("INVALID", {}))
            self.assertEqual(result["reasons"], ["judge door_looks_open: its shots weren't saved (--no-judge-shots), so "
                                                 "it can't be scored"])
            self.assertFalse((Path(tmp) / "out" / "probe-task" / "judge-shots").exists())
            result, _ = self.run_check(tmp, judged=judge(required=False), judge_shots=False, game=_)
            self.assertEqual(result["verdict"], "VALID")

    def test_the_progress_names_each_judge_waiting_for_an_answer(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = {"task": "probe-task", "verdict": "VALID", "reasons": [], "seconds": 60,
                      "judges": {"door_looks_open": {"status": "shots saved for start/reference, answer needed"}}}
            cli.write_progress(tmp, 0, ["probe-task"], [result], now=60)
            self.assertIn("    judge door_looks_open: shots saved for start/reference, answer needed: "
                          "probe-task/judge-shots/door_looks_open/ask.md",
                          (Path(tmp) / "progress.txt").read_text())


class Decide(unittest.TestCase):
    RECORD = {"status": judges.ANSWERED}

    def decide(self, group, start, reference):
        found = {**judges.judge(judge()), "group": group}
        return judges.decide(found, {**self.RECORD, "scores": {"start": start, "reference": reference}})

    def test_a_judge_passes_as_its_model_would(self):
        found = judges.judge(judge())
        self.assertTrue(judges.passes(found, {"door_open": 0.5, "lit": 0.65}), "weighted 0.6, required at 0.5")
        self.assertFalse(judges.passes(found, {"door_open": 0.4, "lit": 1}), "a required item below 0.5")
        self.assertFalse(judges.passes(found, {"door_open": 1, "lit": 0.3}), "weighted 0.53, under 0.6")

    def test_the_pass_mark_is_the_cloud_judges_to_the_last_bit(self):
        """No tolerance: a weighted score that falls a hair under 0.6 in floating point fails, as the Lab's
        judging.sampled fails it (`value >= PASS`); a score outside 0..1 counts as the cloud clamps it."""
        found = judges.judge({**judge(), "rubric": [{"key": k, "criterion": "c", "weight": w} for k, w in
                                                    (("a", 3), ("b", 2), ("c", 2))]})
        scores = {"a": 0.3, "b": 0.7, "c": 0.95}
        self.assertEqual(judges.weighted(found, scores), 0.5999999999999999)
        self.assertFalse(judges.passes(found, scores))
        self.assertEqual(judges.weighted(found, {"a": 2, "b": 0.6, "c": 0}), 0.6)

    def test_a_no_op_earns_on_a_judge_its_start_passes(self):
        """judges.noop_passes: the judges the writer's scores pass on the start (what a no-op earns on them), and the
        weighted ones whose start isn't scored yet."""
        task = task_with(probe(), judge("taste", required=False), judge("tidy", required=False),
                         judge("free", required=False, weight=0))
        records = {"taste": {"scores": {"start": {"door_open": 1, "lit": 1}}},
                   "tidy": {"scores": {"start": {"door_open": 0, "lit": 0}}}}
        self.assertEqual(judges.noop_passes(task, records), (["taste"], []))
        self.assertEqual(judges.noop_passes(task, {}), ([], ["taste", "tidy"]))

    def test_the_start_fails_it_but_passes_a_judge_of_what_still_works(self):
        fails, passes_ = {"door_open": 0, "lit": 0}, {"door_open": 1, "lit": 1}
        self.assertEqual(self.decide("fixed", fails, passes_), [])
        self.assertEqual(self.decide("still_works", passes_, passes_), [])
        self.assertEqual(self.decide("still_works", fails, passes_),
                         ["start fails still-works judge door_looks_open on your scores (weighted 0.00)"])

    def test_a_score_out_of_range_or_an_item_missing_is_a_problem(self):
        found = judges.judge(judge())
        self.assertIsNone(judges.score_problem(found, {"door_open": 1, "lit": 0}))
        self.assertIn("for the items door_open, lit", judges.score_problem(found, {"door_open": 1}))
        self.assertEqual(judges.score_problem(found, {"door_open": 1, "lit": True}), "a score is a number from 0 to 1")


class Flags(unittest.TestCase):
    def test_task_check_passes_no_judge_shots_through(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo, _, _, _ = make_game(tmp)
            path = Path(tmp) / "g-fix-x.json"
            path.write_text(json.dumps({**task_with(probe()), "name": "g-fix-x"}), encoding="utf-8")
            seen = []

            def fake(repo_, task, raw, scratch, out, **kw):
                seen.append(kw["judge_shots"])
                return {"task": task["name"], "verdict": "VALID", "reasons": []}

            with mock.patch.object(check, "check_task", fake), \
                    mock.patch.object(seeds, "too_long", lambda *a: None), \
                    mock.patch.object(unity.ugfroot, "check_free", lambda *a: 100.0), \
                    contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                for extra in ([], ["--no-judge-shots"]):
                    cli.main([str(repo), "--task", str(path), "--scratch", str(Path(tmp) / "s"), *extra])
            self.assertEqual(seen, [True, False])

    def test_task_try_passes_no_judge_shots_through(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo, _, _, _ = make_game(tmp)
            path = Path(tmp) / "tasks" / "Tasks" / "g-fix-x.json"
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps({**task_with(probe()), "name": "g-fix-x"}), encoding="utf-8")
            seen = []

            def fake(*a, **kw):
                seen.append(kw["judge_shots"])
                return {"task": "g-fix-x", "status": "DONE", "reasons": [], "runs": [], "solved": 0}

            with mock.patch.object(trial, "try_task", fake), mock.patch.object(shutil, "which", lambda n: n), \
                    mock.patch.object(unity.ugfroot, "check_free", lambda *a: 100.0), \
                    mock.patch.object(unity.ugfroot, "root", lambda: str(Path(tmp) / "root")), \
                    contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                for extra in ([], ["--no-judge-shots"]):
                    trial.main([str(repo), "--task", str(path), "--agent", "codex", "--scratch",
                                str(Path(tmp) / "elsewhere"), *extra])
            self.assertEqual(seen, [True, False])


class Try(unittest.TestCase):
    def test_a_try_saves_the_agents_side_and_lists_the_judge_as_pending(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo, start, fix, _ = make_game(tmp)
            task = task_with(probe(expect={"op": ">=", "calibrate": 0.5}),
                             judge(plays=[play(shots=["door"])], shots=3))
            task["seed"] = {**task["seed"], "commit": start, "reference": fix}
            projects = {"start": Shooting(measuring(-500), folder="start"),
                        "reference": Shooting(measuring(100), folder="reference"),
                        "run1": Shooting(measuring(100), folder="run1")}

            def project(folder, machine, label):
                folder = Path(folder)
                return projects[folder.name if folder.name in projects else folder.parent.name]

            def agent(argv, cwd, prompt, transcript, minutes, env_extra=None):
                Path(transcript).write_text("")
                return {"exit_code": 0, "seconds": 60.0, "timed_out": False}

            with mock.patch.object(unity, "Project", project), mock.patch.object(trial, "run_agent", agent), \
                    mock.patch.object(unity.Machine, "for_project",
                                      classmethod(lambda cls, p, d=False, **_: cls(Path(p), None))):
                result = trial.try_task(repo, task, json.dumps(task).encode(), Path(tmp) / "scratch",
                                        Path(tmp) / "out", "claude", "claude", places=[repo], log=lambda *a: None)
            self.assertEqual((result["status"], result["solved"]), ("DONE", 1))
            self.assertEqual(result["runs"][0]["score"], 1.0, "the number leaves judges out")
            self.assertEqual(result["judges_pending"], ["door_looks_open"])
            base = Path(tmp) / "out" / "probe-task" / "run1" / "judge-shots" / "door_looks_open"
            self.assertEqual(sorted(p.name for p in (base / "agent").iterdir()),
                             [f"open_door_{i:02d}.png" for i in range(1, 5)])
            self.assertFalse((base / "blind").exists())
            self.assertIn("before calling the task too easy or held", (base / "ask.md").read_text())
            self.assertIn("answer needed", trial.line(result))


if __name__ == "__main__":
    unittest.main()
