"""A `seen` probe (docs/task-probes.md, section 2.22): text the Lab's grader reads from a named screenshot with the
visual checks' model. The task check asks no model, so it is a visual check here as a judge is: never planned as a
query of the probe, never played or measured, `not asked` on both sides, and counted in no gate and no score."""

import unittest

from helpers import SEED, FakeProject, checked, measuring, probe, record, side, task_with

from task_check import check, probes, tasks, trial, verdict

PLAY = {"name": "combo", "seconds": 10, "inputs": [{"t": 3, "shot": "hud"}, {"t": 5, "shot": "hud_later"}]}


def seen(name="combo_shows", measure=None, expect=None, **extra):
    return probe(name, play=PLAY, measure=measure or {"probe": "seen", "shot": "hud", "read": "number"},
                 expect=expect or {"op": ">=", "value": 3}, **extra)


class Seen(unittest.TestCase):
    def test_the_probe_is_asked_nothing_for_it(self):
        lone = task_with(probe(), seen())
        self.assertEqual(probes.plan(lone), probes.plan(task_with(probe())))
        self.assertNotIn("combo", probes.plan(lone))
        listed = task_with(probe(), seen(measure={"probe": "seen", "shot": ["hud", "hud_later"], "read": "clock",
                                                  "agg": "delta"}))
        self.assertNotIn("combo", probes.plan(listed))
        self.assertEqual(probes.editor_items(lone), [])
        self.assertTrue(tasks.seen(tasks.checks(lone)[1][1]))
        self.assertFalse(tasks.seen(tasks.checks(lone)[0][1]))

    def test_it_is_not_asked_on_either_side_and_nothing_is_played_for_it(self):
        task = task_with(probe(), seen(), seen("combo_calibrated", expect={"op": ">=", "calibrate": 0.5}))
        start, reference = FakeProject(measuring(-500)), FakeProject(measuring(0))
        sides = side("start", start, task), side("reference", reference, task)
        for mode in ("reference", "start"):
            rows = check.Grade(task, mode, *sides, {}).run()["checks"]
            self.assertEqual([(r["name"], r["passed"], r["detail"]) for r in rows[1:]],
                             [("combo_shows", True, check.NOT_SEEN), ("combo_calibrated", True, check.NOT_SEEN)],
                             mode)
        self.assertTrue(check.NOT_SEEN.startswith("not asked"))
        self.assertEqual([p["seconds"] for p in start.plays + reference.plays], [20, 20],
                         "the look of the other probe, once a side: never the seen probe's own play")

    def test_it_gates_nothing_and_counts_in_no_no_op(self):
        task = task_with(probe(), seen())
        self.assertEqual(tasks.gating(task), {"hero_on_ground"})
        ref = record(checked("hero_on_ground", "probe", True), checked("combo_shows", "probe", True, check.NOT_SEEN))
        start = record(checked("hero_on_ground", "probe", False), checked("combo_shows", "probe", True, check.NOT_SEEN))
        self.assertEqual(verdict.verdict(task, ref, start), (True, [], []))
        self.assertEqual(verdict.noop_score(task, start), (0.0, []))
        weighed = task_with(probe(weight=1), seen(weight=3))
        self.assertEqual(verdict.noop_score(weighed, record(checked("hero_on_ground", "probe", True),
                                                            checked("combo_shows", "probe", True, check.NOT_SEEN))),
                         (1.0, ["hero_on_ground"]), "its weight is in neither share")

    def test_a_try_scores_without_it(self):
        task = task_with(probe(weight=1), seen(weight=3))
        grade = record(dict(checked("hero_on_ground", "probe", False), required=True, weight=1, group="graded"),
                       dict(checked("combo_shows", "probe", True, check.NOT_SEEN), required=True, weight=3,
                            group="graded"))
        self.assertEqual(trial.score(task, grade)["score"], 0.0)
        grade["checks"][0]["passed"] = True
        self.assertEqual(trial.score(task, grade)["score"], 1.0)

    def test_the_probe_values_leave_it_out(self):
        task = task_with(probe(), seen())
        ref = record(checked("hero_on_ground", "probe", True), checked("combo_shows", "probe", True, check.NOT_SEEN))
        self.assertEqual(list(check.probe_values(task, ref, ref)), ["hero_on_ground"])


if __name__ == "__main__":
    unittest.main()
