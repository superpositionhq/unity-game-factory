"""The task check's rules: thresholds and the VALID/INVALID verdict from the two sides' check rows."""

import unittest

from helpers import NO_FIX, SEED, FakeProject, checked, first_check, measuring, probe, record, side, task_with

from task_check import check, tasks, verdict


def broken_start_task(*checks, seed=SEED):
    """A task whose start doesn't build: making it build is the task."""
    return task_with(milestones=[{"name": "builds", "checks": [{"kind": "build", "name": "player_builds",
                                                                "fails_at_start": True}]},
                                 {"name": "graded", "checks": [{"kind": "boot", "name": "boots_clean", "seconds": 60,
                                                                "needs": ["player_builds"]}, *checks]}], seed=seed)


class Thresholds(unittest.TestCase):
    def test_literal_calibrated_and_start_relative_thresholds(self):
        self.assertEqual(verdict.threshold({"op": ">=", "value": 3}), 3.0)
        self.assertEqual(verdict.threshold({"op": ">=", "calibrate": 0.5}, -500.0, 100.0), -200.0)
        self.assertEqual(verdict.threshold({"op": ">=", "start_times": 2}, 60.0), 120.0)
        self.assertEqual(verdict.threshold({"op": ">=", "start_plus": 50}, 60.0), 110.0)

    def test_a_start_that_measures_nothing_anchors_a_calibrated_threshold_on_the_reference(self):
        self.assertEqual(verdict.threshold({"op": ">=", "calibrate": 0.5}, None, 100.0), 75.0)
        self.assertEqual(verdict.threshold({"op": "<=", "calibrate": 0.5}, None, -40.0), -30.0)
        self.assertEqual(verdict.threshold({"op": "<=", "calibrate": 0.5}, None, 40.0), 50.0)

    def test_make_threshold_refuses_what_it_cant_calibrate(self):
        check = first_check(task_with(probe(expect={"op": ">=", "calibrate": 0.5})))
        self.assertEqual(verdict.make_threshold(check, (-500.0, None), (100.0, None)), (-200.0, -500.0, 100.0))
        with self.assertRaisesRegex(verdict.Uncalibrated, "both measure 100"):
            verdict.make_threshold(check, (100.0, None), (100.0 + 1e-5, None))
        with self.assertRaisesRegex(verdict.Uncalibrated, "the reference measured nothing"):
            verdict.make_threshold(check, (0.0, None), (None, "the play wrote no probe file"))
        relative = first_check(task_with(probe(expect={"op": ">=", "start_plus": 5}), seed=NO_FIX))
        with self.assertRaisesRegex(verdict.Uncalibrated, "the start measured nothing"):
            verdict.make_threshold(relative, (None, "crashed"), (None, None))
        literal = first_check(task_with(probe()))
        asked = []
        self.assertEqual(verdict.make_threshold(literal, lambda: asked.append(1), lambda: asked.append(2)),
                         (0.0, None, None))
        self.assertEqual(asked, [], "a literal threshold measures neither side")

    def test_a_start_that_measures_nothing_and_a_reference_of_0_leave_no_threshold(self):
        """A quarter of nothing is no margin: anchored on a reference of 0, the threshold would be 0 and pass a
        reference that read nothing useful, the same non-information as both sides measuring the same."""
        for op in (">=", ">", "<=", "<"):
            check = first_check(task_with(probe(expect={"op": op, "calibrate": 0.5})))
            with self.assertRaisesRegex(verdict.Uncalibrated, r"hero_on_ground: the start measured nothing \(crashed\) "
                                                              "and the reference measured 0, so there is no threshold"):
                verdict.make_threshold(check, (None, "crashed"), (1e-12, None))
            self.assertEqual(verdict.make_threshold(check, (None, "crashed"), (2.0, None))[1:], (None, 2.0), op)

    def test_passes_and_equality_within_1e_9(self):
        self.assertTrue(verdict.passes(1.0 + 1e-12, "==", 1.0))
        self.assertTrue(verdict.passes(2.0, "!=", 1.0))
        self.assertFalse(verdict.passes(1.0, ">", 1.0))
        self.assertTrue(verdict.passes(1.0, ">=", 1.0))

    def test_a_detail_names_the_measure_the_threshold_and_the_sides(self):
        check = first_check(task_with(probe(expect={"op": ">=", "calibrate": 0.5})))
        self.assertEqual(verdict.describe(check, 80.0, -200.0, -500.0, 100.0),
                         "The hero stands on the ground. | measured 80, threshold >= -200 (start -500, fix 100)")
        self.assertEqual(verdict.describe(check, None, 110.0, 60.0, None, "no samples in the window"),
                         "The hero stands on the ground. | measured nothing, threshold >= 110 (start 60): no samples "
                         "in the window")


class Verdict(unittest.TestCase):
    def test_the_reference_passes_every_required_probe_and_the_start_fails_one(self):
        task = task_with(probe(), probe("extra", required=False, weight=0))
        ref = record(checked("hero_on_ground", "probe", True), checked("extra", "probe", False, "measured 3"))
        start = record(checked("hero_on_ground", "probe", False), checked("extra", "probe", True))
        self.assertEqual(verdict.verdict(task, ref, start), (True, [], ["reference fails extra (probe): measured 3"]))
        ref["checks"][0] = checked("hero_on_ground", "probe", False, "measured -500, threshold >= 0")
        start["checks"][0] = checked("hero_on_ground", "probe", True)
        valid, why, _ = verdict.verdict(task, ref, start)
        self.assertFalse(valid)
        self.assertEqual(why, ["reference fails hero_on_ground: measured -500, threshold >= 0",
                               "start already passes every required probe"])

    def test_a_retired_check_makes_the_task_invalid_required_or_not(self):
        """The Lab's Unity grader has no `trace` play (a task with a trace probe gets reward 0 on every run) and no
        `actions_judge` kind (that check fails every run), so either makes the task INVALID, even optional; the
        reference's failing row of it is no second reason."""
        trace = probe("built", play="trace", required=False, weight=0,
                      measure={"probe": "trace", "fact": "build_ok_at_end"})
        acts = {"name": "worked_well", "kind": "actions_judge", "required": False, "weight": 0, "question": "q",
                "rubric": [{"key": "k", "criterion": "c"}]}
        task = task_with(probe(), trace, acts)
        for c in (trace, acts):
            self.assertTrue(tasks.retired(c))
            self.assertFalse(check.Grade(task, "reference", None, None, {}).check(c)[0])
        ref = record(checked("hero_on_ground", "probe", True),
                     checked("built", "probe", False, verdict.retired_detail(trace)),
                     checked("worked_well", "actions_judge", False, verdict.retired_detail(acts)))
        start = record(checked("hero_on_ground", "probe", False))
        valid, why, notes = verdict.verdict(task, ref, start)
        self.assertFalse(valid)
        self.assertEqual(why, ["built is retired: a trace probe: the Lab's grader has no trace play, so every run of "
                               "the task gets reward 0: remove it",
                               "worked_well is retired: an actions_judge check: the Lab's grader has no such check "
                               "kind, so it fails every run: remove it"])
        self.assertEqual(notes, [])

    def test_the_start_fails_every_outcome_probe(self):
        task = task_with(milestones=[{"name": "fixed", "checks": [probe("hud"), probe("camera"), probe("spawns")]}])
        ref = record(checked("hud", "probe", True), checked("camera", "probe", True), checked("spawns", "probe", True))
        start = record(checked("hud", "probe", False), checked("camera", "probe", True), checked("spawns", "probe", False))
        self.assertEqual(verdict.verdict(task, ref, start), (False, ["start already passes required probe camera"], []))

    def test_a_task_with_no_reference_is_checked_on_its_start_alone(self):
        task = task_with(probe(expect={"op": ">=", "start_plus": 50}), seed=NO_FIX)
        self.assertTrue(verdict.verdict(task, None, record(checked("hero_on_ground", "probe", False)))[0])
        self.assertEqual(verdict.verdict(task, None, record(checked("hero_on_ground", "probe", True)))[1],
                         ["start already passes every required probe"])

    def test_a_start_only_task_needs_a_threshold_for_every_required_probe(self):
        """A required probe the start can't set a threshold for is not the start failing the task: no solution could
        pass it (with a reference, the reference's row says so)."""
        task = task_with(probe(expect={"op": ">=", "start_plus": 5}), seed=NO_FIX)
        detail = "uncalibrated: hero_on_ground: the start measured nothing (no samples in the window (the play ended at " \
                 "3.1 s)), and the threshold is relative to it"
        valid, why, _ = verdict.verdict(task, None, record(checked("hero_on_ground", "probe", False, detail)))
        self.assertFalse(valid)
        self.assertEqual(why, [f"hero_on_ground has no threshold: {detail[:160]}"])
        kept = task_with(milestones=[{"name": "done", "checks": [probe("roofs")]},
                                     {"name": "still_works", "checks": [probe("fps_kept", weight=0, expect={
                                         "op": ">=", "start_times": 0.9})]}], seed=NO_FIX)
        unset = detail.replace("hero_on_ground", "fps_kept")
        self.assertEqual(verdict.verdict(kept, None, record(checked("roofs", "probe", False),
                                                            checked("fps_kept", "probe", False, unset))),
                         (False, [f"fps_kept has no threshold: {unset[:160]}"], []),
                         "a still-works one too: the crash excuses its failing at the start, not its missing threshold")

    def test_the_reference_passes_every_required_check_and_only_optional_ones_are_notes(self):
        """The Lab's grader holds the task's own fix to every required check, so a required file_exists or log_absent
        the reference fails is a reason, as a required probe is; one that isn't required stays a note."""
        task = task_with(probe(), {"kind": "file_exists", "name": "route_left", "glob": "Tests/*.json"},
                         {"kind": "log_absent", "name": "no_errors", "pattern": "NullReference", "weight": 0},
                         {"kind": "file_exists", "name": "notes_left", "glob": "Docs/*.md", "required": False},
                         {"kind": "boot", "name": "boots_clean"})
        ref = record(checked("hero_on_ground", "probe", True), checked("route_left", "file_exists", False, "0 file(s)"),
                     checked("no_errors", "log_absent", False, "1 matching log line(s)"),
                     checked("notes_left", "file_exists", False, "0 file(s)"),
                     checked("boots_clean", "boot", False, "crashed"))
        start = record(checked("hero_on_ground", "probe", False))
        valid, why, notes = verdict.verdict(task, ref, start)
        self.assertFalse(valid)
        self.assertEqual(why, ["reference fails route_left: 0 file(s)", "reference fails no_errors: 1 matching log line(s)",
                               "reference fails boots_clean: crashed"])
        self.assertEqual(notes, ["reference fails notes_left (file_exists): 0 file(s)"], "an optional one never decides")
        rows = record(*(dict(c, required=c["name"] != "route_left") for c in ref["checks"]))
        self.assertNotIn("reference fails route_left: 0 file(s)", verdict.verdict(task, rows, start)[1],
                         "a row's own `required` is read first, as the checker writes it")

    def test_a_required_package_check_is_never_valid(self):
        """The Lab's grader has no package step for a Unity game and fails a package check closed, so a required one
        keeps every run from passing: the checker fails it on every side too."""
        task = task_with(probe(), {"kind": "package", "name": "ships", "weight": 0})
        ref = check.Grade(task, "reference", side("start", FakeProject(measuring(-1)), task),
                          side("reference", FakeProject(measuring(1)), task), {}).run()
        self.assertEqual([(r["name"], r["passed"]) for r in ref["checks"]], [("hero_on_ground", True), ("ships", False)])
        self.assertIn("no package step", ref["checks"][1]["detail"])
        start = record(checked("hero_on_ground", "probe", False), checked("ships", "package", True, "not asked"))
        valid, why, _ = verdict.verdict(task, ref, start)
        self.assertFalse(valid)
        self.assertEqual([w.split(":")[0] for w in why], ["reference fails ships"])
        optional = task_with(probe(), {"kind": "package", "name": "ships", "weight": 0, "required": False})
        ref = check.Grade(optional, "reference", side("start", FakeProject(measuring(-1)), optional),
                          side("reference", FakeProject(measuring(1)), optional), {}).run()
        self.assertTrue(verdict.verdict(optional, ref, start)[0], "an optional one is a note")

    def test_every_probe_needs_a_threshold_required_or_not(self):
        """A probe the checker can't calibrate fails the Lab's grade of the task whole, a probe that isn't required
        too, so it is a reason, never a note."""
        task = task_with(probe(), probe("extra", required=False, weight=0, expect={"op": ">=", "calibrate": 0.5}))
        same = "uncalibrated: extra: the start and the reference both measure 0, so there is no threshold between them"
        ref = record(checked("hero_on_ground", "probe", True), checked("extra", "probe", False, same))
        start = record(checked("hero_on_ground", "probe", False), checked("extra", "probe", False, same))
        self.assertEqual(verdict.verdict(task, ref, start), (False, [f"extra has no threshold: {same}"], []))
        ref["checks"][1] = checked("extra", "probe", False, "measured 3, threshold >= 4")
        start["checks"][1] = checked("extra", "probe", False, "measured 0, threshold >= 4")
        self.assertEqual(verdict.verdict(task, ref, start),
                         (True, [], ["reference fails extra (probe): measured 3, threshold >= 4"]),
                         "an optional probe with a threshold the reference fails stays a note")
        required = task_with(probe(expect={"op": ">=", "calibrate": 0.5}))
        both = same.replace("extra", "hero_on_ground")
        self.assertEqual(verdict.verdict(required, record(checked("hero_on_ground", "probe", False, both)),
                                         record(checked("hero_on_ground", "probe", False, both)))[1],
                         [f"reference fails hero_on_ground: {both}"], "a required one is named once")

    def test_a_check_the_checker_couldnt_run_is_no_verdict(self):
        """A row the checker couldn't make (`the checker failed`) is the machine's or the checker's, never the task's:
        the task check is an ERROR, as the Lab asks such a check again."""
        ref = record(checked("hero_on_ground", "probe", False, "the checker failed (OSError: disk full)"))
        start = record(checked("hero_on_ground", "probe", False))
        self.assertEqual(verdict.failures(ref, start),
                         ["reference hero_on_ground: the checker failed (OSError: disk full)"])
        self.assertEqual(verdict.failures(record(checked("hero_on_ground", "probe", True)), start), [])
        self.assertEqual(verdict.failures(None, start), [])

    def test_a_no_op_scores_zero(self):
        """What is true of the start carries no weight, whether or not it is required (owner, 2026-11-04)."""
        task = task_with(milestones=[{"name": "builds", "checks": [{"kind": "build", "name": "player_builds"}]},
                                     {"name": "fixed", "checks": [probe("hud")]},
                                     {"name": "still_works", "checks": [probe("runs")]}])
        ref = record(checked("player_builds", "build", True), checked("hud", "probe", True), checked("runs", "probe", True))
        start = record(checked("player_builds", "build", True), checked("hud", "probe", False),
                       checked("runs", "probe", True))
        valid, why, _ = verdict.verdict(task, ref, start)
        self.assertFalse(valid)
        self.assertEqual(why, ['a no-op scores 0.667, not 0: give player_builds, runs "weight": 0, or drop them'])
        weightless = task_with(milestones=[{"name": "builds", "checks": [{"kind": "build", "name": "player_builds",
                                                                          "weight": 0}]},
                                           {"name": "fixed", "checks": [probe("hud")]},
                                           {"name": "still_works", "checks": [probe("runs", weight=0)]}])
        self.assertEqual(verdict.verdict(weightless, ref, start), (True, [], []))
        self.assertEqual(verdict.noop_score(weightless, start), (0.0, []))

    def test_a_judge_is_not_counted_in_a_no_op(self):
        task = task_with(probe("hud"), {"kind": "judge", "name": "taste", "question": "q", "required": False, "rubric": [{"key": "k", "criterion": "c"}]})
        start = record(checked("hud", "probe", False), checked("taste", "judge", False, "not asked"))
        self.assertEqual(verdict.noop_score(task, start), (0.0, []))

    def test_a_still_works_probe_must_hold_at_the_start(self):
        """A still-works probe that never finds what it looks for would make a start-only task look valid."""
        task = task_with(milestones=[{"name": "done", "checks": [probe("roofs")]},
                                     {"name": "still_works", "checks": [probe("hud_shown", weight=0)]}], seed=NO_FIX)
        broken = record(checked("roofs", "probe", True), checked("hud_shown", "probe", False, "measured 0"))
        valid, why, _ = verdict.verdict(task, None, broken)
        self.assertFalse(valid)
        self.assertEqual(why, ["start fails still-works hud_shown: measured 0",
                               "start already passes every required probe"], "a still-works failure is no gate")
        good = record(checked("roofs", "probe", False), checked("hud_shown", "probe", True))
        self.assertEqual(verdict.verdict(task, None, good), (True, [], []))
        crashed = record(checked("roofs", "probe", False, "x | measured nothing, threshold >= 1: no samples in the "
                                                         "window (the play wrote no probe file)"),
                         checked("hud_shown", "probe", False, "x | measured nothing, threshold >= 1: no samples in the "
                                                             "window (the play ended at 3.1 s)"))
        self.assertEqual(verdict.verdict(task, None, crashed), (True, [], []), "a start the bug crashes measures nothing")

    def test_a_still_works_probe_that_finds_nothing_at_a_start_that_ran_is_broken(self):
        """Only a play that left no samples (it crashed, ended early, wrote no probe file) excuses a still-works probe:
        one whose select finds nothing in a start that ran is the broken probe the rule is there for."""
        task = task_with(milestones=[{"name": "done", "checks": [probe("roofs")]},
                                     {"name": "still_works", "checks": [probe("hud_shown", weight=0)]}], seed=NO_FIX)
        empty = "x | measured nothing, threshold >= 1: no value in the window (nothing it selects was measured)"
        valid, why, _ = verdict.verdict(task, None, record(checked("roofs", "probe", False),
                                                           checked("hud_shown", "probe", False, empty)))
        self.assertFalse(valid)
        self.assertEqual(why, [f"start fails still-works hud_shown: {empty[:160]}"])
        unread = "uncalibrated: hud_shown: the start measured nothing (no value in the window (nothing it selects " \
                 "was measured)), and the threshold is relative to it"
        self.assertFalse(verdict.verdict(task, None, record(checked("roofs", "probe", False),
                                                            checked("hud_shown", "probe", False, unread)))[0])

    def test_the_start_rows_are_read_as_the_checker_words_them(self):
        """The still-works excuse and the start-only rule read the start's rows in the words check.py and
        probes.measured write them: a start whose play crashed or ended before the window excuses its still-works probe,
        one that ran and found no player doesn't, and each leaves a threshold relative to it unset."""
        task = task_with(milestones=[{"name": "done", "checks": [probe("roofs"), probe(
                             "climbs", expect={"op": ">=", "start_plus": 5})]},
                                     {"name": "still_works", "checks": [probe("hud_shown", weight=0)]}], seed=NO_FIX)

        def nobody(seconds, shots, queries):  # the play ran to its end and never found a player
            return {"format": "unity-probe/1", "ended": "time", "seconds": seconds + 0.5,
                    "track": [[i / 2] for i in range(2 * seconds + 2)], "camera": [], "measures": {}}, ""

        def quits(seconds, shots, queries):  # the game quit at 2 s, before the probes' window [3, 18]
            return {"format": "unity-probe/1", "ended": "shutdown", "seconds": 2.0,
                    "track": [[i / 2, 0.0, 1.0, 0.0] for i in range(5)], "camera": [], "measures": {}}, ""

        for answer, reasons in ((measuring(0, crash=True), ["climbs has no threshold"]),
                                (quits, ["climbs has no threshold"]),
                                (nobody, ["start fails still-works hud_shown", "climbs has no threshold"])):
            start = check.Grade(task, "start", side("start", FakeProject(answer), task), None, {}).run()
            valid, why, _ = verdict.verdict(task, None, start)
            self.assertEqual((valid, [w.split(":")[0] for w in why]), (False, reasons), why)

    def test_a_still_works_probe_counts_with_a_reference_too(self):
        task = task_with(milestones=[{"name": "fixed", "checks": [probe("fixed")]},
                                     {"name": "still_works", "checks": [probe("runs", weight=0)]}])
        ref = record(checked("fixed", "probe", True), checked("runs", "probe", True))
        start = record(checked("fixed", "probe", False), checked("runs", "probe", False, "measured 3"))
        self.assertEqual(verdict.verdict(task, ref, start)[1], ["start fails still-works runs: measured 3"])
        only_still = record(checked("fixed", "probe", True), checked("runs", "probe", False, "measured 3"))
        self.assertEqual(verdict.verdict(task, ref, only_still)[1], ["start fails still-works runs: measured 3",
                                                                    "start already passes every required probe"])

    def test_a_start_that_doesnt_build_by_design_is_the_start_failing_the_task(self):
        task = broken_start_task(probe("roofs"))
        ref = record(checked("player_builds", "build", True), checked("boots_clean", "boot", True),
                     checked("roofs", "probe", True))
        start = record(checked("player_builds", "build", False, "the game as the task started didn't build (exit 6)"))
        self.assertEqual(verdict.verdict(task, ref, start), (True, [], []))
        builds = record(checked("player_builds", "build", True, "the start built"), checked("roofs", "probe", False))
        self.assertEqual(verdict.verdict(task, ref, builds),
                         (False, ["start builds, though player_builds says it doesn't (fails_at_start)"], []))

    def test_a_start_that_doesnt_build_by_design_trips_no_still_works_probe(self):
        task = task_with(milestones=[{"name": "builds", "checks": [{"kind": "build", "name": "player_builds",
                                                                    "fails_at_start": True}]},
                                     {"name": "still_works", "checks": [probe("hud_shown")]}])
        start = record(checked("player_builds", "build", False, "exit 6"))
        ref = record(checked("player_builds", "build", True), checked("hud_shown", "probe", True))
        self.assertEqual(verdict.verdict(task, ref, start), (True, [], []))
        self.assertFalse(verdict.verdict(task, ref, record(checked("hud_shown", "probe", True)))[0],
                         "a start that passes everything is still no task")
        feature = task_with(milestones=task["milestones"], seed={**NO_FIX})
        self.assertEqual(verdict.verdict(feature, None, start), (True, [], []), "start-only")

    def test_a_weight_0_required_guard_outside_still_works_may_pass_at_the_start(self):
        task = task_with(milestones=[{"name": "fixed", "checks": [probe("hud"), probe("camera", weight=0)]}])
        ref = record(checked("hud", "probe", True), checked("camera", "probe", True))
        start = record(checked("hud", "probe", False), checked("camera", "probe", True))
        self.assertEqual(verdict.verdict(task, ref, start), (True, [], []))
        start["checks"][0] = checked("hud", "probe", True)
        self.assertEqual(verdict.verdict(task, ref, start)[1], ["start already passes every required probe"],
                         "guards alone never make a task: one weighted outcome must still fail at the start")
        weighted = task_with(milestones=[{"name": "fixed", "checks": [probe("hud"), probe("camera"), probe("door")]}])
        ref = record(*(checked(n, "probe", True) for n in ("hud", "camera", "door")))
        start = record(checked("hud", "probe", False), checked("camera", "probe", True), checked("door", "probe", False))
        self.assertIn("start already passes required probe camera", verdict.verdict(weighted, ref, start)[1],
                      "a weighted outcome the start passes is refused as before")

    def test_a_task_whose_start_doesnt_build_never_plays_it(self):
        for check, said in [({**probe("roofs"), "expect": {"op": ">=", "calibrate": 0.5}}, "relative to the start"),
                            ({**probe("roofs"), "expect": {"op": ">=", "start_plus": 1}}, "relative to the start")]:
            with self.assertRaisesRegex(ValueError, said):
                broken_start_task(check)
            task_with(check)


if __name__ == "__main__":
    unittest.main()
