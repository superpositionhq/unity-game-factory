"""A task play's `after` (docs/task-probes.md 1.1): the plays it names are played on the same side first, a failed one
too, and it starts on the saved data they left; every other play starts clean, so one that ran in between has them
played again; a task with no `after` plays in the order it always did; and a name that is no task play of the task,
the play itself, a cycle, or two plays of which the second would clear the first's saves, is refused."""

import unittest

from helpers import FakeProject, measuring, probe, side, task_with

from task_check import judges, tasks

MEASURE = {"probe": "player", "field": "y", "agg": "max"}


def play(name, seconds, after=None):
    found = {"name": name, "seconds": seconds, "inputs": [{"t": 1.0, "key": "<Keyboard>/e", "press": True}]}
    return {**found, "after": after} if after is not None else found


def reading(name, of):
    return probe(name=name, play=of, measure=MEASURE)


class PlayOrder(unittest.TestCase):
    def played(self, task, project):
        s = side("reference", project, task)
        for _, c in tasks.checks(task):
            s.value(c)
        return [(p["seconds"], p["keep_saves"]) for p in project.plays]

    def test_a_play_runs_after_the_plays_it_names_on_what_they_saved(self):
        task = task_with(reading("reads", play("reads", 20, ["writes"])), reading("writes", play("writes", 10)))
        self.assertEqual(self.played(task, FakeProject(measuring(0))), [(10, False), (20, True)])

    def test_with_no_after_the_plays_keep_their_order_and_start_clean(self):
        task = task_with(reading("reads", play("reads", 20)), reading("writes", play("writes", 10)))
        self.assertEqual(self.played(task, FakeProject(measuring(0))), [(20, False), (10, False)])
        self.assertEqual(tasks.task_plays(task)["reads"]["after"], [])

    def test_a_chain_is_played_in_order(self):
        task = task_with(reading("ends", play("ends", 30, ["reads"])), reading("reads", play("reads", 20, ["writes"])),
                         reading("writes", play("writes", 10)))
        self.assertEqual(tasks.chain(task, "ends"), ["writes", "reads"])
        self.assertEqual(self.played(task, FakeProject(measuring(0))), [(10, False), (20, True), (30, True)])

    def test_a_play_in_between_cleared_the_saves_so_they_are_written_again(self):
        task = task_with(reading("writes", play("writes", 10)), reading("other", play("other", 15)),
                         reading("reads", play("reads", 20, ["writes"])))
        project = FakeProject(measuring(0))
        self.assertEqual(self.played(task, project), [(10, False), (15, False), (10, False), (20, True)])
        s = side("reference", FakeProject(measuring(0)), task)
        first = s.probe_play(tasks.checks(task)[0][1]["play"])
        s.probe_play(tasks.checks(task)[1][1]["play"])
        s.probe_play(tasks.checks(task)[2][1]["play"])
        self.assertIs(s.probe_play(tasks.checks(task)[0][1]["play"]), first, "its checks read its first play")

    def test_a_play_after_a_failed_one_still_runs(self):
        task = task_with(reading("reads", play("reads", 20, ["writes"])), reading("writes", play("writes", 10)))
        crashes, fine = measuring(0, crash=True), measuring(0)
        project = FakeProject(lambda seconds, shots, queries: (crashes if seconds == 10 else fine)(seconds, shots,
                                                                                                    queries))
        s = side("reference", project, task)
        value, _ = s.value(tasks.checks(task)[0][1])
        self.assertEqual([p["seconds"] for p in project.plays], [10, 20])
        self.assertIsNotNone(value, "the dependant read what the failed play left")

    def test_a_judges_play_may_run_after_a_probes(self):
        judge = {"kind": "judge", "name": "looks_saved", "question": "Is the level kept?",
                 "rubric": [{"key": "kept", "criterion": "The level is kept."}],
                 "plays": [play("shown", 20, ["writes"])]}
        task = task_with(judge, reading("writes", play("writes", 10)))
        project = FakeProject(measuring(0))
        side("reference", project, task).judge_plays(judges.judge(tasks.checks(task)[0][1]))
        self.assertEqual([p["seconds"] for p in project.plays], [10, 20])

    def test_unknown_names_itself_and_cycles_are_refused(self):
        for checks, said in [
                ([reading("reads", play("reads", 20, ["nowhere"]))], "runs after nowhere, which is no task play"),
                ([reading("reads", play("reads", 20, ["look"]))], "runs after look, which is no task play"),
                ([reading("reads", play("reads", 20, ["reads"]))], "names itself in its after"),
                ([reading("one", play("one", 10, ["two"])), reading("two", play("two", 10, ["one"]))], "a cycle")]:
            with self.assertRaises(ValueError) as caught:
                task_with(*checks)
            self.assertIn(said, str(caught.exception))
        with self.assertRaises(ValueError):  # a check carries no after: it is a task play's alone
            task_with({**reading("reads", play("reads", 20)), "after": ["writes"]})

    def test_two_plays_named_together_must_follow_each_other(self):
        loose = [reading("reads", play("reads", 20, ["one", "two"])), reading("one", play("one", 10)),
                 reading("two", play("two", 12))]
        with self.assertRaises(ValueError) as caught:
            task_with(*loose)
        self.assertIn("runs after one and two, but neither runs after the other", str(caught.exception))
        self.assertIn('give two "after": ["one"], or one "after": ["two"]', str(caught.exception))
        loose[2] = reading("two", play("two", 12, ["one"]))
        task = task_with(*loose)
        self.assertEqual(self.played(task, FakeProject(measuring(0))), [(10, False), (12, True), (20, True)])

    def test_two_plays_named_in_either_order_play_in_their_own(self):
        task = task_with(reading("reads", play("reads", 20, ["two", "one"])), reading("one", play("one", 10)),
                         reading("two", play("two", 12, ["one"])))
        self.assertEqual(tasks.chain(task, "reads"), ["one", "two"])
        self.assertEqual(self.played(task, FakeProject(measuring(0))), [(10, False), (12, True), (20, True)])

    def test_a_name_twice_in_one_after_is_refused(self):
        with self.assertRaises(ValueError) as caught:
            task_with(reading("reads", play("reads", 20, ["one", "one"])), reading("one", play("one", 10)))
        self.assertIn("task play reads names one twice in its after", str(caught.exception))

    def test_a_replay_that_goes_otherwise_is_noted_on_the_reader(self):
        from task_check import check
        task = task_with(reading("writes", play("writes", 10)), reading("other", play("other", 15)),
                         reading("reads", play("reads", 20, ["writes"])))
        fine, cut = measuring(0), measuring(0)
        calls = []

        def answer(seconds, shots, queries):
            calls.append(seconds)
            probe, log = (cut if calls.count(10) == 2 and seconds == 10 else fine)(seconds, shots, queries)
            if calls.count(10) == 2 and seconds == 10:
                probe = dict(probe, ended="shutdown")
            return probe, log
        s = side("reference", FakeProject(answer), task)
        rows = {r["name"]: r for r in check.Grade(task, "reference", side("start", FakeProject(measuring(0)), task), s, {}).run()["checks"]}
        self.assertEqual(calls, [10, 15, 10, 20])
        self.assertIn("play_writes, played again for its saved data, did not go as its first play: it ended shutdown "
                      "(first: time)", rows["reads"]["detail"])
        self.assertNotIn("played again", rows["writes"]["detail"])
        same = side("reference", FakeProject(measuring(0)), task)
        graded = check.Grade(task, "reference", side("start", FakeProject(measuring(0)), task), same, {}).run()["checks"]
        self.assertNotIn("played again", {r["name"]: r for r in graded}["reads"]["detail"])
        self.assertIsNone(check.replay_note("play_x", *[s.played["play_other"]] * 2))


if __name__ == "__main__":
    unittest.main()
