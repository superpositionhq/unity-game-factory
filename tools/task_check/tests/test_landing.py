"""A probe of a task play reads only a play that did what the task says: an input of the play that didn't land fails the
check, and is the task's error when the reference's own play missed one too, as in the Lab's grader. Unity is faked."""

import unittest

from helpers import FakeProject, measuring, probe, side, task_with

from task_check import check, probes, tasks, verdict

DOOR = {"name": "open_door", "seconds": 10, "inputs": [{"t": 1.0, "widget": "Continue", "click": True}]}
MISS = {"t": 1.0, "kind": "click", "target": "Continue", "why": "no visible button takes it"}
MAYBE = {"name": "open_door", "seconds": 10, "inputs": [{"t": 1.0, "widget": "Continue", "click": True},
                                                        {"t": 2.0, "widget": "Overwrite", "click": True,
                                                         "optional": True}]}
CONFIRM = {"t": 2.0, "kind": "click", "target": "Overwrite", "why": "no visible button matches it"}


def missing(y, rows):
    """measuring(y), its plays' probe.json listing `rows` as inputs_missed."""
    plain = measuring(y)

    def play(seconds, shots, queries):
        found, log = plain(seconds, shots, queries)
        found["inputs_missed"] = list(rows)
        return found, log

    return play


def graded(task, start_rows, reference_rows, start_y=-5, reference_y=5):
    start = side("start", FakeProject(missing(start_y, start_rows)), task)
    reference = side("reference", FakeProject(missing(reference_y, reference_rows)), task)
    thresholds = {}
    ref = check.Grade(task, "reference", start, reference, thresholds).run()
    return ref, check.Grade(task, "start", start, reference, thresholds).run()


class Missed(unittest.TestCase):
    def test_missed_reads_inputs_missed_and_leaves_named_shots_out(self):
        self.assertIsNone(probes.missed(None))
        self.assertIsNone(probes.missed({"track": []}), "a probe file without the list can't say")
        self.assertEqual(probes.missed({"inputs_missed": []}), [])
        shot = {"t": 2.0, "kind": "shot", "target": "door", "why": "not written"}
        self.assertEqual(probes.missed({"inputs_missed": [MISS, shot]}), [MISS])
        bad = {**MAYBE, "inputs": [{**MAYBE["inputs"][1], "optional": "yes"}]}
        self.assertTrue(tasks.problems({**task_with(probe(play=MAYBE)), "milestones": [
            {"name": "graded", "checks": [probe(play=bad)]}]}), "the validator takes optional as true or false only")
        play = tasks.play(MAYBE)
        self.assertEqual(play["inputs"][1], {"t": 2.0, "widget": "Overwrite", "click": True, "optional": True})
        self.assertNotIn("optional", play["inputs"][0])
        self.assertEqual(probes.missed({"inputs_missed": [MISS, CONFIRM]}, play), [MISS],
                         "an optional click that found nothing is no miss")
        self.assertEqual(probes.missed({"inputs_missed": [MISS, CONFIRM]}), [MISS, CONFIRM],
                         "without the play: every row")
        other = [{**CONFIRM, "t": 3.0}, {**CONFIRM, "target": "Continue"}, {**CONFIRM, "kind": "tap"}]
        self.assertEqual(probes.missed({"inputs_missed": other}, play), other,
                         "only the optional click's own row: its time, kind click and its widget")
        self.assertEqual(probes.missed_text([MISS] * 5),
                         "click Continue at 1 s (no visible button takes it); click Continue at 1 s (no visible button "
                         "takes it); click Continue at 1 s (no visible button takes it); and 2 more")


class Landing(unittest.TestCase):
    def test_a_missed_input_on_the_graded_side_fails_its_check(self):
        """The start's play missed its click: what it measured is of a play that never did what the task says, so the
        check fails saying so, whatever the value (it would pass here), never as the task's error."""
        task = task_with(probe(play=DOOR, expect={"op": ">=", "value": 0}))
        ref, start = graded(task, [MISS], [], start_y=5)
        self.assertTrue(ref["checks"][0]["passed"], ref["checks"][0]["detail"])
        self.assertFalse(start["checks"][0]["passed"])
        self.assertEqual(start["checks"][0]["detail"], "The hero stands on the ground. | the play's input did not land: "
                                                       "click Continue at 1 s (no visible button takes it)")

    def test_a_missed_input_on_the_reference_is_the_tasks_error(self):
        task = task_with(probe(play=DOOR, expect={"op": ">=", "value": 0}))
        ref, start = graded(task, [], [MISS])
        detail = ref["checks"][0]["detail"]
        self.assertFalse(ref["checks"][0]["passed"])
        self.assertTrue(detail.startswith("task error: The hero stands on the ground. | in the reference's play "
                                          "open_door, an input did not land (click Continue at 1 s"), detail)
        valid, why, _ = verdict.verdict(task, ref, start)
        self.assertFalse(valid)
        self.assertTrue(why[0].startswith("reference fails hero_on_ground: task error:"), why)

    def test_a_calibrated_probe_whose_reference_missed_an_input_is_the_tasks_error_on_both_sides(self):
        task = task_with(probe(play=DOOR, expect={"op": ">=", "calibrate": 0.5}))
        ref, start = graded(task, [], [MISS])
        for grade in (ref, start):
            self.assertTrue(grade["checks"][0]["detail"].startswith("task error:"), grade["checks"][0]["detail"])
            self.assertFalse(grade["checks"][0]["passed"])
        same = task_with(probe(play=DOOR, expect={"op": ">=", "calibrate": 0.5}))
        ref, _ = graded(same, [], [MISS], start_y=5)  # both sides measure the same: still the missed input it names
        self.assertTrue(ref["checks"][0]["detail"].startswith("task error:"), ref["checks"][0]["detail"])

    def test_an_optional_click_that_found_nothing_is_no_missed_input(self):
        """A click marked optional may find no widget (a confirmation shown only in some states): its row in
        inputs_missed is left out on either side, so the check reads what the play measured; any other miss of the
        same play still fails it."""
        task = task_with(probe(play=MAYBE, expect={"op": ">=", "value": 0}))
        ref, start = graded(task, [CONFIRM], [CONFIRM])
        self.assertTrue(ref["checks"][0]["passed"], ref["checks"][0]["detail"])
        self.assertFalse(start["checks"][0]["passed"])
        self.assertNotIn("did not land", start["checks"][0]["detail"])
        ref, start = graded(task, [CONFIRM, MISS], [CONFIRM], start_y=5)
        self.assertTrue(ref["checks"][0]["passed"], ref["checks"][0]["detail"])
        self.assertEqual(start["checks"][0]["detail"], "The hero stands on the ground. | the play's input did not land: "
                                                       "click Continue at 1 s (no visible button takes it)")

    def test_the_checkers_own_plays_and_a_play_that_landed_are_read_as_measured(self):
        task = task_with(probe(play="look", expect={"op": ">=", "value": 0}), probe("door", play=DOOR))
        ref, start = graded(task, [], [], start_y=-5)
        self.assertEqual([r["passed"] for r in ref["checks"]], [True, True])
        self.assertEqual([r["passed"] for r in start["checks"]], [False, False])
        self.assertNotIn("did not land", " ".join(r["detail"] for r in start["checks"]))


if __name__ == "__main__":
    unittest.main()
