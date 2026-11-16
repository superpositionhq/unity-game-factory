"""The sounds that start (docs/task-probes.md 2.16): an audio measure counts the sounds that started in each sample's
interval (`started`, `started_audible`, summed by default), reads their names (`sounds`, `repeats`) and may select by
the place a sound plays at (`select.near`)."""

import itertools
import unittest

from helpers import probe, task_with

from task_check import probes, tasks

NEAR = {"near": {"point": {"object": {"tag": "Anvil"}}, "radius": 3}}


def audio(field, **over):
    return {"probe": "audio", "select": NEAR, "field": field, "window": [2.0, 3.0], **over}


def measure_of(field, **over):
    task = task_with(probe(measure=audio(field, **over), expect={"op": ">=", "start_plus": 1}))
    return tasks.checks(task)[0][1]["measure"]


def played(measure, *values):
    qid = probes.query_id(probes.needs(measure)[0])
    return {"seconds": 5.5, "measures": {qid: [{"t": 2.0 + 0.5 * i, "value": v} for i, v in enumerate(values)]}}


def heard(*names, total=None, clock=itertools.count()):
    rows = [{"t": 2.0 + 0.01 * next(clock), "sound": n, "named": n is not None} for n in names]   # each later than the last
    return {"started": float(len(rows)), "started_audible": float(len(rows)), "starts": rows,
            "starts_total": float(len(rows) if total is None else total)}


class Starts(unittest.TestCase):
    def test_a_select_takes_a_place(self):
        measure = measure_of("started_audible")
        self.assertEqual(probes.needs(measure), [{"kind": "audio", "select": {"near": {
            "point": {"object": {"tag": "Anvil"}, "offset": [0.0, 0.0, 0.0]}, "radius": 3.0}}}])

    def test_starts_are_summed_over_the_window(self):
        for field in ("started", "started_audible"):
            measure = measure_of(field)
            probe_json = played(measure, heard("Clang"), heard(), heard("Clang", "Thud"))
            self.assertEqual(probes.measured(measure, probe_json), (3.0, None))
        self.assertEqual(probes.measured(measure_of("started", agg="max"), played(measure_of("started", agg="max"),
                                                                                 heard("a"), heard("a", "b"))), (2.0, None))

    def test_a_level_is_still_the_last_sample(self):
        measure = measure_of("count")
        self.assertEqual(probes.measured(measure, played(measure, {"count": 2.0}, {"count": 1.0})), (1.0, None))

    def test_sounds_counts_the_names_and_repeats_the_same_one_twice_running(self):
        takes = (heard("Clang_1", "Clang_2"), heard("Clang_2"), heard("Clang_1"))
        self.assertEqual(probes.measured(measure_of("sounds"), played(measure_of("sounds"), *takes)), (2.0, None))
        self.assertEqual(probes.measured(measure_of("repeats"), played(measure_of("repeats"), *takes)), (1.0, None))
        self.assertEqual(probes.measured(measure_of("repeats"), played(measure_of("repeats"), heard())), (0.0, None))

    def test_a_start_without_a_name_reads_nothing(self):
        for field in ("sounds", "repeats"):
            measure = measure_of(field)
            value, why = probes.measured(measure, played(measure, heard("Clang", None)))
            self.assertIsNone(value)
            self.assertIn("no name the probe can tell", why)
            value, why = probes.measured(measure, played(measure, heard("Clang", total=70)))
            self.assertIsNone(value)
            self.assertIn("more sounds started than the probe lists", why)
            value, why = probes.measured(measure, played(measure, None))
            self.assertIsNone(value)
            self.assertIn("no audio listener", why)

    def test_a_volume_is_never_a_literal_and_a_start_count_may_be(self):
        task_with(probe(measure=audio("started_audible"), expect={"op": ">=", "value": 1}))
        with self.assertRaises(ValueError):
            task_with(probe(measure=audio("volume"), expect={"op": ">=", "value": 0.5}))
        with self.assertRaises(ValueError):
            task_with(probe(measure=audio("heard"), expect={"op": ">=", "value": 1}))


if __name__ == "__main__":
    unittest.main()
