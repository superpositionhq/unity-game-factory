"""Probe 1.5.0 with no Unity: a measure's `since` (its window and at counted from an event read from the play's
samples), a shot's `when` as the play spec hands it to the probe, and the new misses (a click or tap on a control
something is drawn over; a shot whose event never came), which no click mark allows."""

import unittest

from helpers import probe, task_with

from task_check import probes, tasks, unity

HUD = {"probe": "objects", "select": {"name": "HudDriver"}, "field": "prop:UiHudDriver.frames", "of": "first"}
SCORE = {"probe": "objects", "select": {"name": "HudDriver"}, "field": "prop:UiHudDriver.score", "of": "first"}
TIMES = [round(0.1 * k, 1) for k in range(41)]


def driver():
    """A play whose one query of the HudDriver (fields are no part of a query's id) read frames = 30 t, score = 10
    frames, every 0.1 s for 4 s."""
    (query,) = probes.needs(tasks.measure(HUD))
    rows = [{"t": t, "rows": [{"name": "HudDriver", HUD["field"]: round(t * 30), SCORE["field"]: round(t * 30) * 10}]}
            for t in TIMES]
    return {"format": "unity-probe/1", "seconds": 4.0, "measures": {probes.query_id(query): rows}, "inputs_missed": []}


def since(value=45, within=None, **outer):
    event = {"measure": HUD, "expect": {"op": ">=", "value": value}}
    if within is not None:
        event["within"] = within
    return tasks.measure({**SCORE, **outer, "since": event})


class Since(unittest.TestCase):
    def test_window_and_at_count_from_the_event(self):
        played = driver()
        self.assertEqual(probes.event_time(since()["since"], played), (1.5, None))
        self.assertEqual(probes.measured(since(at=[0]), played), (450.0, None))
        self.assertEqual(probes.measured(since(window=[0.5, 1.0], agg="first"), played), (600.0, None))
        self.assertEqual(probes.measured(since(window=[0.5, 1.0], agg="last"), played), (750.0, None))
        self.assertEqual(probes.measured(since(agg="first"), played), (450.0, None))
        self.assertEqual(probes.measured(since(at="end"), played), (1200.0, None))

    def test_an_event_that_never_happens_reads_nothing(self):
        value, why = probes.measured(since(value=100000, at=[0]), driver())
        self.assertIsNone(value)
        self.assertTrue(why.startswith("its event never happened"), why)
        self.assertEqual(probes.measured(since(within=1.0, at=[0]), driver()),
                         (None, "its event never happened (its objects prop:UiHudDriver.frames never read >= 45 in the "
                                "play's first 1 s)"))

    def test_the_play_samples_the_events_measure(self):
        t = task_with(probe(play={"name": "events", "seconds": 10, "every": 0.1}, measure={**SCORE, "at": [0], "since": {
            "measure": {"probe": "ui", "field": "count", "select": {"kind": "text"}}, "expect": {"op": ">=", "value": 1}}}))
        self.assertEqual(sorted(q["kind"] for q in probes.plan(t)["events"]), ["objects", "ui"])


class When(unittest.TestCase):
    def test_a_shots_when_goes_to_the_probe_as_its_own_query(self):
        shot = {"t": 1, "shot": "win", "when": {"measure": {"probe": "ui", "field": "count",
                                                             "select": {"kind": "text", "text": "SCORE 690$"}},
                                                 "expect": {"op": ">=", "value": 1}, "within": 5}}
        task_with(probe(play={"name": "events", "seconds": 10, "inputs": [shot]}, measure=SCORE))
        (sent,) = probes.probe_inputs(tasks.inputs([shot]))
        query = {"kind": "ui", "select": {"kind": "text", "text": "SCORE 690$"}, "fields": []}
        self.assertEqual(sent["when"], {"query": {"id": probes.query_id(query), **query}, "field": "count", "of": "count",
                                        "match": None, "op": ">=", "value": 1.0, "within": 5.0})
        self.assertEqual(probes.probe_inputs([{"t": 1.0, "shot": "plain"}]), [{"t": 1.0, "shot": "plain"}])
        self.assertIs(unity.probes, probes)


class Misses(unittest.TestCase):
    def test_the_new_misses_are_plain_misses(self):
        click = {"t": 1.0, "widget": "Play", "click": True, "optional": True, "disabled": True}
        covered = {"t": 1.0, "kind": "click", "target": "Play", "why": "covered by another control"}
        never = {"t": 2.0, "kind": "shot_when", "target": "win", "why": "its event never happened"}
        self.assertEqual(probes.missed({"inputs_missed": [covered, never]}, {"name": "p", "inputs": [click]}),
                         [covered, never])


if __name__ == "__main__":
    unittest.main()
