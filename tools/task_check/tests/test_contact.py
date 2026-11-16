"""Staging a contact and reading it (docs/task-probes.md 1.4 and 2.21): a task play may pin an object where the
player's blow lands, deal damage through the game's own damage entry and write a start-named member; a select may
compare members (`where`) and leave the player out; a probe may read the game's time scale, an object's short stops
and the damage it took. A task with none of them is read as it always was."""

import unittest

from helpers import probe, task_with

FOE = {"component": "Foe", "where": [{"prop": "Foe.dead", "op": "==", "value": False}]}
ALIVE = {"probe": "objects", "select": FOE, "of": "count", "field": "count", "agg": "min"}
RELATIVE = {"op": "<=", "start_plus": -1.0}


def play(inputs, seconds=10):
    return {"name": "duel", "seconds": seconds, "inputs": inputs}


def refused(*checks):
    try:
        task_with(*checks)
    except ValueError as e:
        return str(e)
    return None


class Stages(unittest.TestCase):
    STAGED = [{"t": 1.0, "set": "Foe.health", "on": FOE, "value": 1},
              {"t": 1.5, "pin": FOE, "hold": 4, "front": 1.5},
              {"t": 2.0, "key": "<Mouse>/leftButton", "press": True},
              {"t": 5.0, "damage": 10, "to": {"player": True}, "from": FOE}]

    def test_a_staged_contact_is_a_task_play(self):
        task_with(probe(play=play(self.STAGED), measure=ALIVE, expect=RELATIVE))

    def test_the_stages_reach_the_probe_as_its_rows(self):
        from task_check import tasks
        more = [{"t": 6.0, "pin": {"player": False, "name": "Dummy*"}, "hold": 1, "at": {"player": True}, "offset": [0, 0, 2]},
                {"t": 7.0, "set": "Foe.state", "on": {"tag": "Foe"}, "value": "Stunned", "all": True},
                {"t": 8.0, "damage": 5, "to": {"tag": "Foe"}}]
        task = task_with(probe(play=play(self.STAGED + more), measure=ALIVE, expect=RELATIVE))
        self.assertEqual(tasks.checks(task)[0][1]["play"]["inputs"], [
            {"t": 1.0, "set": "Foe.health", "on": FOE, "value": 1},
            {"t": 1.5, "pin": FOE, "hold": 4.0, "front": 1.5},
            {"t": 2.0, "key": "<Mouse>/leftButton", "press": True},
            {"t": 5.0, "damage": 10.0, "to": {"player": True}, "from": FOE},
            {"t": 6.0, "pin": {"player": False, "name": "Dummy*"}, "hold": 1.0,
             "at": {"player": True, "offset": [0.0, 0.0, 0.0]}, "offset": [0.0, 0.0, 2.0]},
            {"t": 7.0, "set": "Foe.state", "on": {"tag": "Foe"}, "value": "Stunned", "all": True},
            {"t": 8.0, "damage": 5.0, "to": {"tag": "Foe"}}])

    def test_a_pin_never_holds_the_player(self):
        pinned = play([{"t": 1.0, "pin": {"player": True}, "hold": 2}])
        self.assertIn("pins the player", refused(probe(play=pinned, measure=ALIVE, expect=RELATIVE)) or "")

    def test_a_pin_is_set_ahead_or_at_a_point_never_both(self):
        both = play([{"t": 1.0, "pin": FOE, "hold": 2, "front": 1.5, "at": {"xyz": [0, 0, 0]}}])
        self.assertIn("not both", refused(probe(play=both, measure=ALIVE, expect=RELATIVE)) or "")

    def test_a_malformed_stage_is_refused(self):
        for bad in ({"t": 1.0, "pin": FOE}, {"t": 1.0, "pin": FOE, "hold": 0}, {"t": 1.0, "pin": FOE, "hold": 1, "front": -1},
                    {"t": 1.0, "damage": 0, "to": FOE}, {"t": 1.0, "damage": 5}, {"t": 1.0, "set": "Foe.health", "on": FOE},
                    {"t": 1.0, "set": "Foe.parts[0].health", "on": FOE, "value": 1},
                    {"t": 1.0, "set": "Foe.health", "on": FOE, "value": [1]},
                    {"t": 1.0, "pin": dict(FOE, where=[{"prop": "Foe.dead", "op": "is", "value": False}]), "hold": 1},
                    {"t": 1.0, "pin": dict(FOE, where=[]), "hold": 1}):
            self.assertIsNotNone(refused(probe(play=play([bad]), measure=ALIVE, expect=RELATIVE)), bad)


class Readings(unittest.TestCase):
    def test_the_time_scale_is_asked_of_the_probe_and_read_back(self):
        from task_check import probes, tasks
        slow = {"probe": "world", "field": "time_scale", "agg": "min", "window": [2.0, 3.0]}
        task = task_with(probe(name="hit_stop", play=play(Stages.STAGED), measure=slow, expect={"op": "<=", "start_times": 0.5}),
                         probe(name="not_paused", play=play(Stages.STAGED), expect={"op": "==", "value": 0},
                               measure={"probe": "world", "field": "paused", "agg": "max"}))
        measure = tasks.checks(task)[0][1]["measure"]
        self.assertEqual(probes.needs(measure), [{"kind": "world", "fields": ["time_scale"]}])
        qid = probes.query_id(probes.needs(measure)[0])
        played = {"measures": {qid: [{"t": 2.0, "value": {"time_scale": 1.0, "paused": 0.0}},
                                     {"t": 2.1, "value": {"time_scale": 0.05, "paused": 0.0}}]}}
        self.assertEqual(probes.series(measure, played), [(2.0, 1.0), (2.1, 0.05)])

    def test_an_objects_short_stop_and_the_damage_it_took_are_fields(self):
        from task_check import probes, tasks
        for field in ("frozen", "damage_taken"):
            measure = {"probe": "objects", "select": FOE, "of": "max", "field": field, "agg": "max"}
            task = task_with(probe(play=play(Stages.STAGED), measure=measure, expect={"op": ">=", "start_plus": 0.05}))
            self.assertEqual(probes.needs(tasks.checks(task)[0][1]["measure"]),
                             [{"kind": "objects", "select": FOE, "fields": [field]}])


if __name__ == "__main__":
    unittest.main()
