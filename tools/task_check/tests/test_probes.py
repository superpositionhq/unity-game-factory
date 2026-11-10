"""Probes with no Unity: the measures' defaults, the probe's queries, every reducer, the grading probe's colour fields,
the editor pass's request and results."""

import json
import tempfile
import types
import unittest
from pathlib import Path

from helpers import NO_FIX, SEED, first_check, measure_of, probe, task_with

from task_check import colour, probes, tasks, unity

WALLS = {"component": "CastlePiece", "tag": "Wall"}
TRACK = [[0.0, 0, 1.0, 0], [0.5, 0.3, 1.0, 0.4], [1.0, 0.6, 0.9, 0.8], [1.5, 0.6, -5.0, 0.8]]  # [t, x, y (up), z]


def m(**data):
    return measure_of(data)


def sampled(values, key="value"):
    return [{"t": i * 0.5, key: v} for i, v in enumerate(values)]


def objects_play(measure, rows):
    qid = probes.query_id(probes.needs(measure)[0])
    return {"measures": {qid: sampled(rows, "rows")}}


class Tasks(unittest.TestCase):
    def test_the_measures_defaults(self):
        found = m(probe="objects", select={"component": "Wall"}, field="y")
        self.assertEqual((found["of"], found["agg"]), ("count", None))
        self.assertEqual(probes.default_agg(found), "last")
        self.assertEqual(probes.default_agg(m(probe="spawns", component="Projectile", field="spawned")), "sum")
        self.assertEqual(m(probe="player", field="dist", to={"player": True})["to"]["offset"], [0, 0, 0])

    def test_a_task_play_teleport_turns_the_player_even_without_a_yaw(self):
        play = tasks.play({"name": "spot", "seconds": 8, "inputs": [{"t": 0.2, "teleport": [1, 2, 3]},
                                                                     {"t": 1, "key": "<Keyboard>/w", "press": True}]})
        self.assertEqual(play["inputs"], [{"t": 0.2, "teleport": [1.0, 2.0, 3.0], "yaw": 0.0},
                                          {"t": 1.0, "key": "<Keyboard>/w", "press": True}])
        self.assertEqual(play["every"], None)
        self.assertNotIn("scene", play, "a play without a scene opens the task's")
        self.assertNotIn("args", play, "a play without args passes the task's")

    def test_a_task_plays_scene_and_args_take_the_tasks_place_only_where_it_has_them(self):
        task = {"play_scene": "Assets/Scenes/Town.unity", "play_args": ["-scenario", "1"]}
        self.assertEqual(tasks.place(task, "look"), ("Assets/Scenes/Town.unity", ["-scenario", "1"]))
        self.assertEqual(tasks.place(task, tasks.play({"name": "a", "seconds": 5})),
                         ("Assets/Scenes/Town.unity", ["-scenario", "1"]))
        own = tasks.play({"name": "a", "seconds": 5, "scene": "Assets/Scenes/Arena.unity", "args": []})
        self.assertEqual(tasks.place(task, own), ("Assets/Scenes/Arena.unity", []), "an empty args is the play's own")
        first = tasks.play({"name": "a", "seconds": 5, "scene": None})
        self.assertEqual(tasks.place(task, first), (None, ["-scenario", "1"]), "scene null: the first build scene")
        self.assertEqual(tasks.place({}, "drive"), (None, []))

    def test_the_tasks_player_select_is_filled_in(self):
        self.assertIsNone(tasks.player({}))
        self.assertEqual(tasks.player({"player": {"tag": "Hero", "near": {"point": {"xyz": [0, 0, 0]}, "radius": 5}}}),
                         {"tag": "Hero", "near": {"point": {"xyz": [0.0, 0.0, 0.0]}, "radius": 5.0}})
        task_with(probe(), player={"name": "Hero*"})
        with self.assertRaises(ValueError):
            task_with(probe(), player={"near": {"point": {"player": True}, "radius": 1, "y_relative": True}})

    def test_the_checks_defaults_and_their_kinds(self):
        task = task_with(probe(), probe("b", required=False, expect={"op": ">=", "calibrate": 0.5}))
        checks = [c for _, c in tasks.checks(task)]
        self.assertEqual([(c["required"], c["weight"], c["needs"]) for c in checks], [(True, 1, []), (False, 1, [])])
        self.assertEqual([tasks.relative(c) for c in checks], [None, "calibrate"])
        self.assertEqual(tasks.gating(task), {"hero_on_ground"})

    def test_the_task_rules_beyond_the_schema_are_refused(self):
        for checks, seed, said in [
            ([probe(play="editor")], SEED, "asset measures are taken by the editor pass"),
            ([probe(play="trace")], SEED, "trace measures are read from the trace"),
            ([probe(measure={"probe": "trace", "fact": "build_ok_at_end"}, play="trace")], SEED, "never gates"),
            ([probe("a", play={"name": "fire", "seconds": 10}), probe("b", play={"name": "fire", "seconds": 12})],
             SEED, "task play fire differs"),
            ([probe(expect={"op": "==", "calibrate": 0.5})], SEED, "== and != take a literal value"),
            ([probe(expect={"op": ">=", "calibrate": 0.5})], NO_FIX, "calibrates against a reference"),
        ]:
            with self.assertRaisesRegex(ValueError, said):
                task_with(*checks, seed=seed)
        for arg in ("-taskProbe", "-taskprobeseconds=99", "-batchmode", "-logFile", "-screen-width", "-force-d3d12",
                    "-popupwindow", "--quit", "-projectPath", "-executeMethod", "-monitor", "-parentHWND",
                    "-single-instance"):
            with self.assertRaisesRegex(ValueError, "can't set", msg=arg):
                task_with(probe(play={"name": "fire", "seconds": 10, "args": [arg]}))
        with self.assertRaisesRegex(ValueError, "play_args can't set"):
            task_with(probe(), play_args=["-nographics"])
        task_with(probe(play={"name": "fire", "seconds": 10, "args": ["-autoPlay", "-scenario", "2"]}),
                  play_scene="Assets/Scenes/Town.unity", play_args=["-scenario", "1"])
        task_with(probe("a", play={"name": "fire", "seconds": 10}), probe("b", play={"name": "fire", "seconds": 10}))
        task_with(probe(expect={"op": ">=", "start_times": 1.3}), seed=NO_FIX)

    def test_a_screen_measure_takes_a_threshold_from_the_start_never_a_literal(self):
        screen = {"probe": "screen", "rect": [0.25, 0.25, 0.75, 0.75], "field": "luminance", "window": [10, 20]}
        with self.assertRaisesRegex(ValueError, "never a literal value"):
            task_with(probe(measure=screen, expect={"op": ">=", "value": 0.1}))
        task_with(probe(measure=screen, expect={"op": ">=", "calibrate": 0.5}))
        task_with(probe(measure=screen, expect={"op": ">=", "start_times": 1.3}), seed=NO_FIX)
        for bad in ({**screen, "rect": [0.5, 0, 1.2, 1]}, {**screen, "field": "brightness"}):
            with self.assertRaises(ValueError):
                task_with(probe(measure=bad, expect={"op": ">=", "calibrate": 0.5}))

    def test_the_new_readings_are_task_fields(self):
        pieces = {"probe": "pieces", "select": {"component": "MeshRenderer", "mesh": "SM_Rock*",
                                                "near": {"point": {"player": True}, "radius": 30}}, "field": "count"}
        task_with(probe(measure=pieces, expect={"op": ">=", "value": 300}))
        task_with(probe(measure={"probe": "pieces", "field": "visible"}, expect={"op": ">=", "value": 1}))
        for field in ("world_yaw:Light", "world_pitch:Moon", "world_roll:Moon", "forward:Moon.z"):
            task_with(probe(measure={"probe": "objects", "select": {"tag": "Moon"}, "field": field, "of": "first"}))
        for bad in ({"probe": "pieces", "field": "instances"},
                    {"probe": "objects", "select": {"tag": "Moon"}, "field": "forward:Moon.w"}):
            with self.assertRaises(ValueError):
                task_with(probe(measure=bad))

    def test_a_pieces_triangle_threshold_comes_from_the_start_never_a_literal(self):
        forest = {"probe": "pieces", "select": {"component": "ForestChunk"}, "at": "end"}
        for field in ("triangles", "visible_triangles"):
            dense = {**forest, "field": field}
            with self.assertRaisesRegex(ValueError, "never a literal value"):
                task_with(probe(measure=dense, expect={"op": ">=", "value": 100000}))
            task_with(probe(measure=dense, expect={"op": ">=", "calibrate": 0.5}))
            task_with(probe(measure=dense, expect={"op": ">=", "start_times": 1.5}), seed=NO_FIX)
        for field in ("count", "visible", "components", "objects"):
            task_with(probe(measure={**forest, "field": field}, expect={"op": ">=", "value": 423}))
        with self.assertRaises(ValueError):
            task_with(probe(measure={**forest, "field": "tris"}, expect={"op": ">=", "calibrate": 0.5}))


class Queries(unittest.TestCase):
    def test_queries_are_merged_per_play_and_selection_under_stable_ids(self):
        task = task_with(
            probe("a", measure={"probe": "objects", "select": WALLS, "field": "y"}),
            probe("b", measure={"probe": "objects", "select": WALLS, "field": "prop:CameraRig.distance"}),
            probe("c", measure={"probe": "objects", "select": WALLS, "field": "count"}),
            probe("d", measure={"probe": "camera", "field": "occluded"}),
            probe("e", measure={"probe": "camera", "field": "player_on_screen"}),
            probe("f", measure={"probe": "camera", "field": "pitch"}),
            probe("g", play="drive", measure={"probe": "light", "point": {"player": True, "offset": [0, 0.9, 0]},
                                              "field": "brightness"}),
            probe("h", play="drive", measure={"probe": "grading", "field": "warmth"}),
            probe("i", play="drive", measure={"probe": "player", "field": "dist", "to": {"object": {"name": "Kiln*"}}}),
            probe("j", play={"name": "fire", "seconds": 10}, measure={"probe": "spawns", "component": "Projectile",
                                                                        "field": "destroyed"}),
            probe("k", play={"name": "fire", "seconds": 10}, measure={"probe": "log", "pattern": "NullReference"}),
            probe("l", play="editor", measure={"probe": "asset", "asset": "Assets/Materials/Road.mat",
                                               "field": "shader:_Cull"}))
        plan = probes.plan(task)
        self.assertEqual(set(plan), {"look", "drive", "fire"})
        look = {q["kind"]: q for q in plan["look"]}
        self.assertEqual(len(plan["look"]), 2, "one objects query for the walls, one camera query")
        self.assertEqual(look["objects"]["fields"], ["prop:CameraRig.distance", "y"])
        self.assertEqual(look["objects"]["select"], {"component": "CastlePiece", "tag": "Wall"})
        self.assertEqual(look["camera"]["fields"], ["occluded", "player_on_screen"])
        drive = {q["kind"]: q for q in plan["drive"]}
        self.assertEqual(drive["light"]["point"], {"player": True, "offset": [0.0, 0.9, 0.0]})
        self.assertEqual(drive["objects"], {"id": drive["objects"]["id"], "kind": "objects",
                                            "select": {"name": "Kiln*"}, "fields": ["x", "y", "z"]})
        self.assertEqual(plan["fire"], [{"id": plan["fire"][0]["id"], "kind": "spawns", "component": "Projectile"}])
        alone = probes.plan(task_with(probe("z", measure={"probe": "objects", "select": WALLS, "field": "hidden"})))
        self.assertEqual(alone["look"][0]["id"], look["objects"]["id"], "an id names its selection")
        self.assertEqual([q["id"] for q in plan["look"]], sorted(q["id"] for q in plan["look"]))
        self.assertEqual(probes.query_file(plan["look"]),
                         {"format": "game-probe-queries/1", "every": 0.5, "queries": plan["look"]})
        self.assertIsNone(probes.query_file([]))
        self.assertEqual(probes.plan(task_with(probe())), {"look": []}, "the track needs no query")

    def test_a_query_id_is_the_hash_of_the_query_without_its_fields(self):
        query = {"kind": "objects", "select": {"tag": "Wall"}, "fields": ["y"]}
        import hashlib
        want = "q" + hashlib.sha256(json.dumps({"kind": "objects", "select": {"tag": "Wall"}},
                                               sort_keys=True).encode()).hexdigest()[:10]
        self.assertEqual(probes.query_id(query), want)
        self.assertEqual(probes.query_id({**query, "fields": ["x", "count"]}), want)
        self.assertEqual(want, "q64b05254ef", "the same in every run and every Python")

    def test_post_fields_are_asked_for_by_name_beside_the_colour_settings(self):
        task = task_with(probe("a", measure={"probe": "grading", "field": "post:Vignette.intensity"}),
                         probe("b", measure={"probe": "grading", "field": "post:Bloom.intensity"}),
                         probe("c", measure={"probe": "grading", "field": "warmth"}),
                         probe("d", measure={"probe": "components", "select": {"component": "DecalProjector"},
                                             "field": "visible"}))
        found = {q["kind"]: q for q in probes.plan(task)["look"]}
        self.assertEqual(found["grading"]["fields"], ["post:Bloom.intensity", "post:Vignette.intensity"])
        self.assertEqual(found["components"], {"id": found["components"]["id"], "kind": "components",
                                               "select": {"component": "DecalProjector"}, "fields": ["visible"]})

    def test_component_types_and_names_reach_the_queries(self):
        found = probes.plan(task_with(probe(measure={"probe": "components", "select": {"component": "ParticleSystem",
                                                                                       "name": "Rain*"},
                                                     "field": "count"})))
        self.assertTrue(any(q.get("select", {}).get("name") == "Rain*" for qs in found.values() for q in qs))


class Reducers(unittest.TestCase):
    def test_the_players_fields_come_from_the_track(self):
        play = {"track": TRACK}
        self.assertEqual(probes.reduce(m(probe="player", field="y"), play), -5, "last by default")
        self.assertEqual(probes.reduce(m(probe="player", field="y", agg="min", window=[0, 1]), play), 0.9)
        self.assertEqual(probes.reduce(m(probe="player", field="x", at=[0.5, 1.4]), play), 0.6)
        self.assertAlmostEqual(probes.reduce(m(probe="player", field="speed", agg="first"), play), 1.0)
        self.assertAlmostEqual(probes.reduce(m(probe="player", field="moved", at="end"), play),
                               (0.6 ** 2 + 6.0 ** 2 + 0.8 ** 2) ** 0.5)
        self.assertEqual(probes.reduce(m(probe="player", field="dist", to={"xyz": [0, 1, 0]}, agg="first"), play), 0)
        self.assertIsNone(probes.reduce(m(probe="player", field="y", window=[5, 9]), play), "no sample in the window")
        self.assertIsNone(probes.reduce(m(probe="player", field="y"), None), "no probe file")

    def test_a_players_distance_to_an_object_reads_the_objects_query(self):
        measure = m(probe="player", field="dist", to={"object": {"name": "Kiln*"}, "offset": [0, 1, 0]}, agg="min")
        (query,) = probes.plan(task_with(probe(measure={"probe": "player", "field": "dist", "agg": "min",
                                                        "to": {"object": {"name": "Kiln*"},
                                                               "offset": [0, 1, 0]}})))["look"]
        rows = [[{"name": "Kiln_2", "x": 0.6, "y": 0, "z": 0.8}]] * 4
        play = {"track": TRACK, "measures": {query["id"]: sampled(rows, "rows")}}
        self.assertAlmostEqual(probes.reduce(measure, play), 0.1)
        play["measures"][query["id"]] = sampled([[]] * 4, "rows")
        self.assertIsNone(probes.reduce(measure, play), "no kiln, no distance")

    def test_the_cameras_fields_come_from_its_rows_and_its_query(self):
        camera = [[t, -7, 4, 0, 12.0, 5.0, 60.0] for t in (0.0, 0.5)]  # [t, x, y, z, pitch, yaw, fov]
        play = {"track": [[0.0, 0, 1, 0], [0.5, 0, 1, 0]], "camera": camera}
        self.assertAlmostEqual(probes.reduce(m(probe="camera", field="distance"), play), (7 ** 2 + 3 ** 2) ** 0.5)
        self.assertEqual(probes.reduce(m(probe="camera", field="height"), play), 3, "camera y minus player y")
        self.assertEqual(probes.reduce(m(probe="camera", field="pitch"), play), 12)
        self.assertEqual(probes.reduce(m(probe="camera", field="fov"), play), 60)
        occluded = m(probe="camera", field="occluded", agg="count")
        qid = probes.query_id(probes.needs(occluded)[0])
        play["measures"] = {qid: sampled([{"occluded": True, "player_on_screen": 1}, {"occluded": False}])}
        self.assertEqual(probes.reduce(occluded, play), 1)
        self.assertEqual(probes.reduce(m(probe="camera", field="player_on_screen", agg="all"), play), 1)

    def test_objects_combine_by_of_and_samples_by_agg(self):
        rows = [[{"name": "A", "y": 0}, {"name": "B", "y": 120.0}, {"name": "C", "y": None}],
                [{"name": "A", "y": 50}, {"name": "B", "y": 130.0}]]
        expected = {"count": [1, 2], "any": [1, 1], "all": [0, 1], "min": [0, 50], "max": [120, 130],
                    "mean": [60, 90], "sum": [120, 180], "first": [0, 50]}
        for of, values in expected.items():
            for agg, want in (("first", values[0]), ("last", values[1]), ("delta", values[1] - values[0]),
                              ("sum", sum(values)), ("max", max(values))):
                measure = m(probe="objects", select={"tag": "T"}, field="y", of=of, agg=agg)
                self.assertAlmostEqual(probes.reduce(measure, objects_play(measure, rows)), want, msg=(of, agg))
        count = m(probe="objects", select={"tag": "T"}, field="count", agg="mean")
        self.assertEqual(probes.reduce(count, objects_play(count, rows)), 2.5)
        empty = m(probe="objects", select={"tag": "T"}, field="y", of="min")
        self.assertIsNone(probes.reduce(empty, objects_play(empty, [[], []])))
        named = m(probe="objects", select={"tag": "T"}, field="prop:MeshFilter.sharedMesh.name", match="SM_Tower",
                  of="all")
        self.assertEqual(probes.reduce(named, objects_play(named, [[{"prop:MeshFilter.sharedMesh.name": "SM_Tower"},
                                                                    {"prop:MeshFilter.sharedMesh.name": "SM_Tower_B"}]])),
                         1)
        self.assertEqual(probes.reduce(named, objects_play(named, [[{"prop:MeshFilter.sharedMesh.name": "SM_Hut"}]])),
                         0)

    def test_of_defaults_to_count(self):
        """A probe that reads a field without `of` counts the rows whose value isn't 0."""
        measure = m(probe="objects", select={"tag": "T"}, field="y")
        self.assertEqual(probes.reduce(measure, objects_play(measure, [[{"y": 1.2}, {"y": 0.0}, {"y": 0.05}]])), 2)

    def test_every_agg_and_of(self):
        values = [0.0, 2.0, None, 5.0, 0.0]
        want = {"min": 0, "max": 5, "mean": 1.75, "first": 0, "last": 0, "delta": 0, "any": 1, "all": 0, "count": 2,
                "sum": 7, "range": 5, "changes": 3, "rises": 2, "falls": 1}
        for agg, value in want.items():
            self.assertEqual(probes.aggregate(values, agg), value, agg)
        self.assertAlmostEqual(probes.aggregate(values, "std"), 2.0463, places=4)
        self.assertIsNone(probes.aggregate([None], "sum"))
        self.assertEqual(probes.aggregate([3.0, 4.0], "all"), 1)
        self.assertEqual({of: probes.combine([3.0, 0.0, None], of) for of in
                          ("count", "any", "all", "min", "max", "mean", "sum", "first")},
                         {"count": 1, "any": 1, "all": 0, "min": 0, "max": 3, "mean": 1.5, "sum": 3, "first": 3})
        self.assertEqual((probes.combine([], "all"), probes.combine([], "count")), (0, 0))
        self.assertIsNone(probes.combine([], "max"))

    def test_widgets_light_spawns_and_the_log(self):
        ammo = m(probe="widgets", select={"component": "TMP_Text", "name": "AmmoText"}, field="text",
                 match=r"^\d+ / \d+$", of="any", agg="all")
        self.assertEqual(probes.reduce(ammo, objects_play(ammo, [[{"name": "AmmoText", "text": "12 / 30"}]] * 3)), 1)
        self.assertEqual(probes.reduce(ammo, objects_play(ammo, [[{"name": "AmmoText", "text": "AMMO"}]])), 0)
        light = m(probe="light", point={"camera": True, "forward": 3}, field="brightness", agg="mean")
        qid = probes.query_id(probes.needs(light)[0])
        play = {"measures": {qid: sampled([{"illuminance": 100, "exposure": 0.5, "brightness": 50},
                                           {"illuminance": 300, "exposure": 0.5, "brightness": 150}])}}
        self.assertEqual(probes.reduce(light, play), 100)
        shots = m(probe="spawns", component="Projectile", field="spawned", window=[1, 2])
        qid = probes.query_id(probes.needs(shots)[0])
        play = {"measures": {qid: sampled([{"spawned": n, "destroyed": 0} for n in (0, 1, 1, 4, 6, 6)])}}
        self.assertEqual(probes.reduce(shots, play), 5, "spawned in (0.5, 2] s: 3 + 2")
        self.assertEqual(probes.reduce(m(probe="spawns", component="Projectile", field="spawned"), play), 6)
        log = "NullReferenceException: Object reference not set\nInitialize engine\nNullReferenceException: again\n"
        self.assertEqual(probes.reduce(m(probe="log", pattern="NullReferenceException"), None, log), 2)

    def test_a_point_on_the_camera_follows_its_view(self):
        """Y is up and Z forward: pitch is positive looking down, yaw turns about Y."""
        play = {"camera": [[0.0, 0, 0, 0, -90.0, 0.0, 60.0], [0.5, 0, 0, 0, 0.0, 90.0, 60.0],
                           [1.0, 0, 0, 0, 0.0, 0.0, 60.0], [1.5, 0, 1, 0, 30.0, 0.0, 60.0]],
                "track": [[0.0, 0, 0, 0]]}
        for t, want in ((0.0, [0, 1, 0]), (0.5, [1, 0, 0]), (1.0, [0, 0, 1]),
                        (1.5, [0, 1 - 0.5, 3 ** 0.5 / 2])):
            found = probes.point_at(tasks.point({"camera": True, "forward": 1}), t, play)
            for a, b in zip(found, want):
                self.assertAlmostEqual(a, b, msg=t)
        self.assertEqual(probes.point_at(tasks.point({"player": True, "offset": [0, 0.5, 0]}), 0.1, play), [0, 0.5, 0])
        self.assertIsNone(probes.point_at(tasks.point({"player": True}), 3.0, play))

    def test_a_play_that_ended_before_the_window_fails_saying_when_it_ended(self):
        play = {"seconds": 6.0, "track": [[t * 0.5, 0, 1, 0] for t in range(13)]}
        self.assertEqual(probes.measured(m(probe="player", field="y", window=[10, 18]), play),
                         (None, "no samples in the window (the play ended at 6 s)"))
        self.assertEqual(probes.measured(m(probe="player", field="y", at=[15]), {"track": TRACK}),
                         (None, "no samples in the window (the play ended at 1.5 s)"))
        empty = m(probe="objects", select={"tag": "T"}, field="y", of="min")
        self.assertEqual(probes.measured(empty, objects_play(empty, [[]])),
                         (None, "no value in the window (nothing it selects was measured)"))

    def test_a_play_that_ran_without_a_player_or_a_camera_has_samples_with_no_value(self):
        """A sample that found no player is a track row [t], one that found no camera has no camera row: the play
        ran, so its measures have no value there, never "no samples"."""
        nobody = {"seconds": 20.5, "track": [[0.0333], [0.5], [1.0], [20.5]], "camera": []}
        nothing = (None, "no value in the window (nothing it selects was measured)")
        for measure in (m(probe="player", field="moved"), m(probe="player", field="y"),
                        m(probe="player", field="dist", to={"camera": True, "forward": 2}),
                        m(probe="camera", field="pitch"), m(probe="camera", field="height")):
            self.assertEqual(probes.measured(measure, nobody), nothing, measure["field"])
        self.assertEqual(probes.ended({"track": [[0.5], [1.0], [1.5]]}), 1.5, "a sample without a player is a sample")
        gaps = {"track": [[0.0, 0, 1, 0], [0.5], [1.0, 0.6, 1, 0.8]],
                "camera": [[0.0, 0, 3, 0, 10.0, 0.0, 60.0], [1.0, 0, 3, 0, 20.0, 0.0, 60.0]]}
        self.assertIsNone(probes.reduce(m(probe="player", field="x", at=[0.5]), gaps))
        self.assertAlmostEqual(probes.reduce(m(probe="player", field="speed"), gaps), 1.0, msg="over the gap")
        self.assertIsNone(probes.reduce(m(probe="camera", field="pitch", at=[0.5]), gaps))
        self.assertEqual(probes.reduce(m(probe="camera", field="pitch", agg="max"), gaps), 20.0)

    def test_a_probe_with_no_value_says_what_the_probe_could_not_read(self):
        """Its own query's error only: one naming the query's kind and id, else one naming its kind alone (the probe
        writes a select's own errors so), never another query's or the play's."""
        measure = m(probe="components", select={"component": "Nowhere"}, field="y", of="max")
        qid = probes.query_id(probes.needs(measure)[0])
        found = {"format": "unity-probe/1", "ended": "time", "seconds": 20.0, "track": [[0.5, 0, 0, 0]], "camera": [],
                 "measures": {qid: [{"t": 0.5, "rows": []}]},
                 "query_errors": ["spawns: no component type Coin", "components: no component type Nowhere"]}
        value, why = probes.measured(measure, found)
        self.assertIsNone(value)
        self.assertEqual(why, "no value in the window (nothing it selects was measured); the probe said: components: "
                              "no component type Nowhere")
        found["query_errors"] = ["components qffffffffff: not this one", "components: no component type Nowhere",
                                 f"components {qid} (frame): this one"]
        self.assertTrue(probes.measured(measure, found)[1].endswith(f"; the probe said: components {qid} (frame): "
                                                                    "this one"))
        found["query_errors"] = ["spawns: no component type Coin", "components qffffffffff: not this one",
                                 "the frame couldn't be read: no"]
        self.assertEqual(probes.measured(measure, found), (None, "no value in the window (nothing it selects was "
                                                                 "measured)"), "another query's error is not quoted")


class FairReadings(unittest.TestCase):
    def test_a_count_reads_every_match_past_the_rows_cap(self):
        """The probe keeps 200 rows a sample; a count of 389 is 389, not 200."""
        crates = m(probe="objects", select={"component": "Crate"}, field="count")
        qid = probes.query_id(probes.needs(crates)[0])
        rows = [{"name": f"Crate{i}", "count": 1} for i in range(200)]
        self.assertEqual(probes.reduce(crates, {"measures": {qid: [{"t": 0.0, "rows": rows, "total": 389}]}}), 389)
        self.assertEqual(probes.reduce(crates, {"measures": {qid: [{"t": 0.0, "rows": rows[:12]}]}}), 12)

    def test_of_reads_the_probes_summary_of_every_match_past_the_rows_cap(self):
        rows = [{"y": 1.0, "hidden": 0} for _ in range(200)]
        full = {"y": {"n": 389, "nonzero": 388, "sum": 400.0, "min": 0.0, "max": 9.0},
                "hidden": {"n": 389, "nonzero": 189, "sum": 189.0, "min": 0.0, "max": 1.0}}
        sample = {"t": 0.0, "rows": rows, "total": 389, "full": full}

        def read(**kw):
            measure = m(probe="objects", select={"component": "Crate"}, **kw)
            return probes.reduce(measure, {"measures": {probes.query_id(probes.needs(measure)[0]): [sample]}})

        self.assertEqual(read(field="y", of="max"), 9.0)
        self.assertEqual(read(field="y", of="min"), 0.0)
        self.assertEqual(read(field="y", of="sum"), 400.0)
        self.assertAlmostEqual(read(field="y", of="mean"), 400.0 / 389)
        self.assertEqual(read(field="hidden"), 189, "of defaults to count: the non-zero values of every match")
        self.assertEqual(read(field="hidden", of="any"), 1.0)
        self.assertEqual(read(field="y", of="all"), 0.0, "one crate sits at 0")
        self.assertEqual(read(field="y", of="first"), 1.0, "first is the first row")
        self.assertEqual(read(field="yaw", of="max"), None, "a field the summary lacks reads the rows (none here)")

    def test_values_read_through_match_or_an_angle_read_the_rows_alone(self):
        rows = [{"prop:Ore.label": "Gold", "yaw": 170.0}, {"prop:Ore.label": "Iron", "yaw": -170.0}]
        full = {"prop:Ore.label": {"n": 0, "nonzero": 0, "sum": 0.0, "min": None, "max": None},
                "yaw": {"n": 300, "nonzero": 300, "sum": 0.0, "min": -179.0, "max": 179.0}}
        for measure, want in ((m(probe="objects", select={"component": "Ore"}, field="prop:Ore.label", match="Gold"),
                               1.0),
                              (m(probe="objects", select={"component": "Ore"}, field="yaw", to_angle=180, of="max"),
                               10.0)):
            qid = probes.query_id(probes.needs(measure)[0])
            found = probes.reduce(measure, {"measures": {qid: [{"t": 0.0, "rows": rows, "total": 300, "full": full}]}})
            self.assertAlmostEqual(found, want)

    def test_pieces_count_placed_mesh_pieces_whatever_their_form(self):
        rocks = m(probe="pieces", select={"mesh": "SM_Rock*"}, field="count")
        self.assertEqual(rocks["agg"], None)
        (query,) = probes.needs(rocks)
        self.assertEqual(query, {"kind": "pieces", "select": {"mesh": "SM_Rock*"}})
        self.assertEqual(m(probe="pieces", field="count")["select"], {})
        value = {"count": 1450, "visible": 1400, "components": 3, "objects": 2}
        play = {"measures": {probes.query_id(query): sampled([value, {**value, "count": 1460}])}}
        self.assertEqual(probes.reduce(rocks, play), 1460)
        self.assertEqual(probes.reduce(m(probe="pieces", select={"mesh": "SM_Rock*"}, field="objects", agg="first"),
                                       play), 2)

    def test_pieces_read_the_triangles_they_hold_and_draw(self):
        """A forest merged into 3 meshes reads 3 pieces but every triangle it draws."""
        forest = m(probe="pieces", select={"component": "ForestChunk"}, field="visible_triangles")
        (query,) = probes.needs(forest)
        self.assertEqual(query, {"kind": "pieces", "select": {"component": "ForestChunk"}},
                         "one query per selection; the probe answers every field")
        value = {"count": 3, "visible": 3, "components": 1, "objects": 1, "triangles": 960000,
                 "visible_triangles": 900000}
        play = {"measures": {probes.query_id(query): sampled([{**value, "visible_triangles": 0}, value])}}
        self.assertEqual(probes.reduce(forest, play), 900000)
        self.assertEqual(probes.reduce(m(probe="pieces", select={"component": "ForestChunk"},
                                         field="visible_triangles", agg="first"), play), 0)
        self.assertEqual(probes.reduce(m(probe="pieces", select={"component": "ForestChunk"},
                                         field="triangles"), play), 960000)
        self.assertEqual(probes.reduce(m(probe="pieces", select={"component": "ForestChunk"},
                                         field="count"), play), 3, "the count reads as before")
        older = {k: v for k, v in value.items() if "triangles" not in k}
        self.assertIsNone(probes.reduce(forest, {"measures": {probes.query_id(query): sampled([older])}}),
                          "a probe without the reading gives no value, never 0")

    def test_screen_luminance_is_sampled_like_the_other_probes(self):
        dark = m(probe="screen", field="luminance", window=[1, 1.5], agg="mean")
        self.assertEqual(dark["rect"], [0.0, 0.0, 1.0, 1.0])
        (query,) = probes.needs(m(probe="screen", rect=[0, 0.5, 1, 1], field="luma"))
        self.assertEqual(query, {"kind": "screen", "rect": [0.0, 0.5, 1.0, 1.0]})
        qid = probes.query_id(probes.needs(dark)[0])
        frames = [{"luminance": 0.5, "luma": 0.7}, None, {"luminance": 0.1, "luma": 0.3},
                  {"luminance": 0.2, "luma": 0.4}, {"luminance": 0.9, "luma": 0.9}]
        self.assertAlmostEqual(probes.reduce(dark, {"measures": {qid: sampled(frames)}}), 0.15)

    def test_a_parts_world_rotation_reads_as_an_angle(self):
        moon = m(probe="objects", select={"tag": "Moon"}, field="world_yaw:Light", to_angle=-90, of="first")
        play = objects_play(moon, [[{"world_yaw:Light": 280.0}]])
        self.assertAlmostEqual(probes.reduce(moon, play), 10.0)
        self.assertTrue(all(tasks.is_angle(f) for f in ("world_yaw:Moon", "world_pitch:Moon", "world_roll:Moon")))
        self.assertFalse(tasks.is_angle("forward:Moon.y"))
        down = m(probe="objects", select={"tag": "Moon"}, field="forward:Light.y", of="first")
        self.assertEqual(probes.reduce(down, objects_play(down, [[{"forward:Light.y": -0.5}]])), -0.5)


LAMP = {"probe": "components", "select": {"component": "Light", "owner": {"tag": "Lamp"}}, "at": "end"}
CRATE = {"probe": "objects", "select": {"tag": "Crate"}, "at": "end"}


class MoreFairReadings(unittest.TestCase):
    """docs/task-probes.md: lights that are off, what is on screen, what the player hears, the ground, a teleport next
    to an object, moving components, whole or broken."""

    def test_the_readings_a_build_chooses_take_a_threshold_from_the_start_never_a_literal(self):
        never = [{**LAMP, "field": "intensity", "of": "max"}, {**LAMP, "field": "extent_y", "of": "max"},
                 {**CRATE, "field": "spread", "of": "max"},
                 {"probe": "audio", "select": {"sound_class": "Ambience"}, "field": "volume"},
                 {"probe": "audio", "field": "max_volume"}, {"probe": "audio", "field": "level"},
                 {"probe": "ground", "box": [0, 0, 50, 50], "grid": 16, "field": "range"}]
        for measure in never:
            with self.assertRaisesRegex(ValueError, "never a literal value", msg=json.dumps(measure)):
                task_with(probe(measure=measure, expect={"op": ">=", "value": 1}))
            task_with(probe(measure=measure, expect={"op": ">=", "calibrate": 0.5}))
            task_with(probe(measure=measure, expect={"op": ">=", "start_times": 2}), seed=NO_FIX)
        for measure in ({**LAMP, "field": "on"}, {**LAMP, "field": "simulating"},
                        {**LAMP, "field": "speed", "of": "max"}, {**LAMP, "field": "x", "of": "min"},
                        {**CRATE, "field": "simulating"}, {"probe": "audio", "field": "count"},
                        {"probe": "audio", "field": "audible"}, {"probe": "ground", "xz": [1, 2], "field": "height"},
                        {"probe": "ground", "xz": [0, 0], "field": "hit"},
                        {"probe": "ground", "box": [0, 0, 10, 10], "field": "max"},
                        {"probe": "widgets", "select": {"name": "Warn*", "visible": True}, "field": "count"}):
            task_with(probe(measure=measure, expect={"op": ">=", "value": 1}))

    def test_the_new_readings_refuse_what_they_cant_read(self):
        for bad in ({"probe": "components", "select": {"component": "Light"}, "field": "lumens"},
                    {"probe": "objects", "select": {"tag": "A"}, "field": "spread_x"},
                    {"probe": "audio", "select": {"sound": "Rain/*"}, "field": "count"},
                    {"probe": "audio", "field": "loudest"},
                    {"probe": "ground", "field": "height"},
                    {"probe": "ground", "xz": [0, 0], "box": [0, 0, 1, 1], "field": "height"},
                    {"probe": "ground", "xz": [0, 0], "field": "range"},
                    {"probe": "ground", "box": [0, 0, 1, 1], "field": "height"},
                    {"probe": "ground", "box": [5, 0, 1, 1], "field": "max"},
                    {"probe": "ground", "box": [0, 0, 1, 1], "grid": 64, "field": "max"},
                    {"probe": "ground", "xy": [0, 0], "field": "height"},
                    {"probe": "widgets", "select": {"name": "Warn*", "visible": False}, "field": "count"}):
            with self.assertRaises(ValueError, msg=json.dumps(bad)):
                task_with(probe(measure=bad))

    def test_lights_read_on_and_their_intensity_as_components(self):
        lamp = m(**{**LAMP, "field": "on", "of": "any", "at": None})
        (query,) = probes.needs(lamp)
        self.assertEqual(query["fields"], ["on"])
        play = objects_play(lamp, [[{"name": "L", "on": 1, "intensity": 5.0}], [{"name": "L", "on": 0,
                                                                                 "intensity": 0.0}]])
        self.assertEqual(probes.reduce(lamp, play), 0)
        bright = m(**{**LAMP, "field": "intensity", "of": "max", "at": None, "agg": "first"})
        self.assertEqual(probes.query_id(probes.needs(bright)[0]), probes.query_id(query), "one query, both fields")
        self.assertEqual(probes.reduce(bright, play), 5.0)

    def test_a_visible_widget_select_is_its_own_query(self):
        shown = m(probe="widgets", select={"name": "Warn*", "visible": True}, field="count")
        every = m(probe="widgets", select={"name": "Warn*"}, field="count")
        self.assertEqual(probes.needs(shown)[0]["select"], {"name": "Warn*", "visible": True})
        self.assertEqual(probes.needs(every)[0]["select"], {"name": "Warn*"}, "a select without it is as it was")
        self.assertNotEqual(probes.query_id(probes.needs(shown)[0]), probes.query_id(probes.needs(every)[0]))
        self.assertEqual(probes.reduce(shown, objects_play(shown, [[{"name": "WarnVisible"}]])), 1)

    def test_what_the_player_hears_reduces_from_the_audio_samples(self):
        jungle = m(probe="audio", select={"sound_class": "Jungle*", "owner": {"tag": "Zone2"}}, field="volume",
                   agg="mean")
        (query,) = probes.needs(jungle)
        self.assertEqual(query, {"kind": "audio", "select": {"sound_class": "Jungle*", "owner": {"tag": "Zone2"}}})
        self.assertEqual(probes.needs(m(probe="audio", field="count"))[0], {"kind": "audio", "select": {}})
        value = {"count": 2, "audible": 1, "volume": 0.6, "max_volume": 0.5, "level": 0.08, "loudest": "Birds"}
        qid = probes.query_id(query)
        play = {"measures": {qid: sampled([value, {**value, "volume": 0.2, "level": 0.02}])}}
        self.assertAlmostEqual(probes.reduce(jungle, play), 0.4)
        level = m(probe="audio", select={"sound_class": "Jungle*", "owner": {"tag": "Zone2"}}, field="level",
                  agg="max")
        self.assertEqual(probes.query_id(probes.needs(level)[0]), qid, "one query, every field")
        self.assertAlmostEqual(probes.reduce(level, play), 0.08)
        self.assertIsNone(probes.reduce(jungle, {"measures": {qid: sampled([None])}}),
                          "a play that measured no audio measures nothing, never 0")

    def test_the_ground_reads_a_height_and_a_relief(self):
        hill = m(probe="ground", xz=[12, -3], field="height")
        self.assertEqual(probes.needs(hill), [{"kind": "ground", "xz": [12.0, -3.0]}])
        relief = m(probe="ground", box=[0, 0, 80, 80], select={"component": "TerrainCollider"}, field="range")
        self.assertEqual(probes.needs(relief), [{"kind": "ground", "box": [0.0, 0.0, 80.0, 80.0], "grid": 8,
                                                 "select": {"component": "TerrainCollider"}}])
        qid = probes.query_id(probes.needs(relief)[0])
        self.assertEqual(probes.reduce(relief, {"measures": {qid: sampled([{"min": 0, "max": 3, "range": 3,
                                                                            "hits": 64, "points": 64}])}}), 3)
        pid = probes.query_id(probes.needs(hill)[0])
        self.assertIsNone(probes.reduce(hill, {"measures": {pid: sampled([{"height": None, "hit": 0}])}}))

    def test_a_task_play_teleports_next_to_an_object(self):
        play = {"name": "ore", "seconds": 12, "inputs": [
            {"t": 1, "teleport_to": {"tag": "Ore"}},
            {"t": 3, "teleport_to": {"component": "OreChunk"}, "distance": 3.5, "offset": [0, 1, 0],
             "face": {"object": {"tag": "Tug"}}}]}
        first, second = first_check(task_with(probe(play=play, measure={"probe": "player", "field": "y"})))["play"][
            "inputs"]
        self.assertEqual(first, {"t": 1.0, "teleport_to": {"tag": "Ore"}, "distance": 2.0, "offset": [0, 0, 0]})
        self.assertEqual(second["face"], {"object": {"tag": "Tug"}, "offset": [0, 0, 0]})
        self.assertEqual((second["distance"], second["offset"]), (3.5, [0.0, 1.0, 0.0]))
        with self.assertRaises(ValueError):
            task_with(probe(play={**play, "inputs": [{"t": 1, "teleport_to": {"tag": "Ore"}, "yaw": 90}]},
                            measure={"probe": "player", "field": "y"}))

    def test_only_a_play_that_measures_audio_says_so_in_its_spec(self):
        heard = task_with(probe(measure={"probe": "audio", "select": {"sound": "Rain*"}, "field": "count"}),
                          probe("quiet", play={"name": "quiet", "seconds": 10},
                                measure={"probe": "player", "field": "y"}))
        plays = probes.plan(heard)
        self.assertTrue(probes.hears(plays["look"]) and probes.hears(probes.query_file(plays["look"])))
        self.assertFalse(probes.hears(plays["quiet"]) or probes.hears(None))
        specs = []

        def job(label, argv, cwd, timeout, gpu=False):
            specs.append(json.loads(Path(str(argv[argv.index("-taskProbe") + 1])).read_text(encoding="utf-8")))
            return types.SimpleNamespace(exit_code=0, timed_out=False, output="", seconds=1.0, waited=0.0)

        with tempfile.TemporaryDirectory() as folder:
            exe = Path(folder, unity.BUILD_DIR, unity.PLAYER)
            exe.parent.mkdir(parents=True)
            exe.write_bytes(b"")
            project = unity.Project(folder, types.SimpleNamespace(job=job), "start")
            project.play(5, 0, 60, queries=probes.query_file(plays["look"]))
            project.play(5, 0, 60)
        loud, quiet = specs
        self.assertEqual((loud["sound"], quiet["sound"]), (True, False))
        with self.assertRaisesRegex(ValueError, "can't set -taskProbeSound"):
            task_with(probe(play={"name": "x", "seconds": 5, "args": ["-taskProbeSound"]},
                            measure={"probe": "player", "field": "y"}))


BOX = {"probe": "objects", "select": {"tag": "Box"}, "at": "end"}
BOX_PART = {"probe": "components", "select": {"component": "SkinnedMeshRenderer", "owner": {"tag": "Box"}},
            "at": "end"}


class ChangedSinceTheStart(unittest.TestCase):
    """docs/task-probes.md: whether an object changed since the play began, so one that breaks by hiding a part or by
    animating its pieces reads as broken."""

    def test_changed_takes_a_literal_and_the_amounts_behind_it_never_do(self):
        for measure in ({**BOX, "field": "changed", "of": "any"}, {**BOX_PART, "field": "changed", "of": "any"}):
            task_with(probe(measure=measure, expect={"op": ">=", "value": 1}))
        for measure in ({**BOX, "field": "bounds_change", "of": "max"},
                        {**BOX, "field": "pose_change", "of": "max"},
                        {**BOX_PART, "field": "bounds_change", "of": "max"},
                        {**BOX_PART, "field": "pose_change", "of": "max"}):
            with self.assertRaisesRegex(ValueError, "never a literal value"):
                task_with(probe(measure=measure, expect={"op": ">=", "value": 1}))
            task_with(probe(measure=measure, expect={"op": ">=", "calibrate": 0.5}))
            task_with(probe(measure=measure, expect={"op": ">=", "start_times": 2}), seed=NO_FIX)
        for bad in ({**BOX, "field": "changed_since"}, {**BOX_PART, "field": "pose"}):
            with self.assertRaises(ValueError, msg=json.dumps(bad)):
                task_with(probe(measure=bad))

    def test_one_query_reads_changed_and_its_amounts(self):
        broken = m(**{**BOX, "field": "changed", "of": "any", "at": None})
        (query,) = probes.needs(broken)
        self.assertEqual((query["kind"], query["fields"]), ("objects", ["changed"]))
        posed = m(**{**BOX, "field": "pose_change", "of": "max", "at": None})
        self.assertEqual(probes.query_id(probes.needs(posed)[0]), probes.query_id(query), "one query, both fields")
        play = objects_play(broken, [[{"name": "Box", "changed": 0, "bounds_change": 0.0, "pose_change": 0.0}],
                                     [{"name": "Box", "changed": 1, "bounds_change": 0.0, "pose_change": 24.0}]])
        self.assertEqual(probes.reduce(broken, play), 1)
        self.assertEqual(probes.reduce(m(**{**BOX, "field": "changed", "of": "any", "at": None, "agg": "first"}),
                                       play), 0)
        self.assertEqual(probes.reduce(posed, play), 24.0)
        bare = m(**{**BOX, "field": "pose_change", "of": "max", "at": None})
        self.assertIsNone(probes.reduce(bare, objects_play(bare, [[{"name": "Crate", "pose_change": None}]])),
                          "no skinned mesh: no value, never 0")


GLOW_LAMP = {"probe": "objects", "select": {"tag": "Lamp"}, "at": "end"}
GLOW_BULB = {"probe": "components", "at": "end",
             "select": {"component": "MeshRenderer", "owner": {"tag": "Lamp"}, "mesh": "SM_Bulb*", "visible": True}}


class LitWhateverMadeTheLight(unittest.TestCase):
    """docs/task-probes.md: one reading for whether something gives off light and how much, whether a build lit it with
    a Light or with a mesh drawn by an emissive or unlit material."""

    def test_lit_takes_a_literal_and_glow_never_does(self):
        for measure in ({**GLOW_LAMP, "field": "lit", "of": "any"}, {**GLOW_BULB, "field": "lit", "of": "any"}):
            task_with(probe(measure=measure, expect={"op": ">=", "value": 1}))
        for measure in ({**GLOW_LAMP, "field": "glow", "of": "sum"}, {**GLOW_BULB, "field": "glow", "of": "max"}):
            with self.assertRaisesRegex(ValueError, "never a literal value"):
                task_with(probe(measure=measure, expect={"op": ">=", "value": 1}))
            task_with(probe(measure=measure, expect={"op": ">=", "calibrate": 0.5}))
            task_with(probe(measure=measure, expect={"op": ">=", "start_times": 2}), seed=NO_FIX)
        for bad in ({**GLOW_LAMP, "field": "glow_sources"}, {**GLOW_LAMP, "field": "emissive"},
                    {**GLOW_BULB, "field": "glow_sources"},
                    {**GLOW_BULB, "select": {"component": "MeshRenderer", "visible": False}, "field": "lit"},
                    {**GLOW_BULB, "select": {"component": "MeshRenderer", "mesh": "Bulb/SM_Bulb"}, "field": "lit"}):
            with self.assertRaises(ValueError, msg=json.dumps(bad)):
                task_with(probe(measure=bad))

    def test_one_query_reads_lit_and_glow_over_every_kind_of_source(self):
        lit = m(**{**GLOW_LAMP, "field": "lit", "of": "any", "at": None})
        (query,) = probes.needs(lit)
        self.assertEqual((query["kind"], query["fields"]), ("objects", ["lit"]))
        glow = m(**{**GLOW_LAMP, "field": "glow", "of": "sum", "at": None})
        self.assertEqual(probes.query_id(probes.needs(glow)[0]), probes.query_id(query), "one query, both fields")
        # a light, a mesh whose emission went up, an unlit mesh and a hidden glowing mesh, as the probe reads them
        # (glow_sources and glow_read ride along for the logs)
        play = objects_play(lit, [[{"name": "Light", "lit": 1, "glow": 8.0, "glow_sources": "light",
                                    "glow_read": "props"},
                                   {"name": "Param", "lit": 0, "glow": 0.0, "glow_sources": ""},
                                   {"name": "Hidden", "lit": 0, "glow": 0.0, "glow_sources": ""}],
                                  [{"name": "Light", "lit": 0, "glow": 0.0, "glow_sources": ""},
                                   {"name": "Param", "lit": 1, "glow": 2.5, "glow_sources": "emissive",
                                    "glow_read": "props"},
                                   {"name": "Unlit", "lit": 1, "glow": 0.5, "glow_sources": "unlit",
                                    "glow_read": "render"},
                                   {"name": "Hidden", "lit": 0, "glow": 0.0, "glow_sources": ""}]])
        self.assertEqual(probes.reduce(lit, play), 1)
        self.assertEqual(probes.reduce(m(**{**GLOW_LAMP, "field": "lit", "of": "count", "at": None}), play), 2)
        self.assertEqual(probes.reduce(glow, play), 3.0)
        first = m(**{**GLOW_LAMP, "field": "glow", "of": "sum", "at": None, "agg": "first"})
        self.assertEqual(probes.reduce(first, play), 8.0)
        bare = m(**{**GLOW_LAMP, "field": "glow", "of": "max", "at": None})
        self.assertIsNone(probes.reduce(bare, objects_play(bare, [[{"name": "Fx", "lit": None, "glow": None}]])),
                          "unread: no value, never 0")

    def test_a_component_select_by_mesh_or_drawn_is_its_own_query(self):
        bulbs = m(**{**GLOW_BULB, "field": "lit", "of": "any", "at": None})
        (query,) = probes.needs(bulbs)
        self.assertEqual(query["select"], {"component": "MeshRenderer", "owner": {"tag": "Lamp"}, "mesh": "SM_Bulb*",
                                           "visible": True})
        every = m(probe="components", select={"component": "MeshRenderer", "owner": {"tag": "Lamp"}}, field="lit",
                  of="any")
        self.assertNotEqual(probes.query_id(probes.needs(every)[0]), probes.query_id(query))


LIT_HERE = {"has": {"lit": True, "near": {"point": {"xyz": [5, 1, 0]}, "radius": 3}}}
LIT_HERE_SENT = {"has": {"lit": True, "near": {"point": {"xyz": [5.0, 1.0, 0.0]}, "radius": 3.0}}}


class ObjectsByAComponent(unittest.TestCase):
    """docs/task-probes.md: an object select's `has` picks objects by a component they carry (one that gives light, a
    drawn mesh near a point), whatever type or name a build gave them."""

    def test_has_works_wherever_an_object_select_does(self):
        play = {"name": "away", "seconds": 10, "inputs": [
            {"t": 2, "teleport_to": LIT_HERE, "distance": 4},
            {"t": 4, "teleport_to": {"tag": "Prop", "has": {"component": "Light", "visible": True}},
             "face": {"object": {"has": {"lit": True}}}}]}
        task = task_with(
            probe("a", measure={"probe": "objects", "select": LIT_HERE, "field": "count"}),
            probe("b", play=play, measure={"probe": "player", "field": "dist", "to": {"object": {"has": {"lit": True}}}}),
            probe("c", measure={"probe": "components", "select": {"component": "MeshRenderer",
                                                                  "owner": {"has": {"component": "Light"}}},
                                "field": "count"}),
            probe("d", measure={"probe": "ground", "xz": [0, 0], "select": {"has": {"visible": True}},
                                "field": "height"}))
        first, second = tasks.checks(task)[1][1]["play"]["inputs"]
        self.assertEqual(first["teleport_to"], LIT_HERE_SENT)
        self.assertEqual(second["teleport_to"], {"tag": "Prop", "has": {"component": "Light", "visible": True}})
        self.assertEqual(second["face"], {"object": {"has": {"lit": True}}, "offset": [0, 0, 0]})
        found = m(probe="objects", select=LIT_HERE, field="count")
        (query,) = probes.needs(found)
        self.assertEqual(query["select"], LIT_HERE_SENT)
        owner = m(probe="components", select={"component": "MeshRenderer", "owner": {"has": {"component": "Light"}}},
                  field="count")
        self.assertEqual(probes.needs(owner)[0]["select"]["owner"], {"has": {"component": "Light"}})
        plain = m(probe="objects", select={"tag": "Prop"}, field="count")
        self.assertEqual(probes.needs(plain)[0]["select"], {"tag": "Prop"}, "a select without has is sent as before")
        lit = m(probe="objects", select={"tag": "Prop", "has": {"lit": True}}, field="count")
        self.assertNotEqual(probes.query_id(probes.needs(lit)[0]), probes.query_id(probes.needs(plain)[0]))
        self.assertEqual(probes.reduce(found, objects_play(found, [[{"count": 1}], [{"count": 1}] * 2])), 2)

    def test_has_refuses_what_it_cant_read(self):
        for has in ({}, {"lit": False}, {"visible": False}, {"tag": "Lamp"}, {"component": "Point Light"},
                    {"near": {"point": {"xyz": [0, 0, 0]}}}):
            with self.assertRaises(ValueError, msg=json.dumps(has)):
                task_with(probe(measure={"probe": "objects", "select": {"has": has}, "field": "count"}))
        with self.assertRaises(ValueError):
            task_with(probe(measure={"probe": "components", "select": {"component": "MeshRenderer",
                                                                       "has": {"lit": True}}, "field": "count"}))
        with self.assertRaisesRegex(ValueError, "takes no `has`"):
            task_with(probe(play="editor", measure={"probe": "asset", "scene": "Assets/Scenes/A.unity",
                                                    "select": {"tag": "Lamp", "has": {"lit": True}}, "field": "count"}))


UI_TEXT = {"probe": "ui", "select": {"kind": "text"}, "field": "text", "match": r"AMMO\s*\d+", "of": "any"}
# one sample's elements as the probe reads them: a uGUI text, a UI Toolkit label, a string read off the frame (an
# OnGUI readout) and a uGUI panel (a hidden text is not on screen, so not a row); source and kind ride along for the logs
UI_ROWS = [{"text": "HP 75%", "x": 0.021, "y": 0.203, "w": 0.083, "h": 0.035, "source": "ugui", "kind": "text"},
           {"text": "ITEMS 7", "x": 0.021, "y": 0.278, "w": 0.05, "h": 0.015, "source": "uitk", "kind": "text"},
           {"text": "AMMO 30", "x": 0.042, "y": 0.225, "w": 0.106, "h": 0.033, "source": "ocr", "kind": "text"},
           {"text": None, "x": 0.042, "y": 0.296, "w": 0.208, "h": 0.03, "source": "ugui", "kind": "box"}]


class UiWhateverDrawsIt(unittest.TestCase):
    """docs/task-probes.md: one reading for what the UI shows on screen, whether a build drew it with uGUI, UI Toolkit
    or straight onto the frame (OnGUI, GL, a custom mesh: read off the frame)."""

    def test_text_takes_match_and_every_field_a_literal(self):
        for measure in (UI_TEXT, {**UI_TEXT, "of": "count", "select": {"text": "AMMO", "rect": [0, 0, 0.5, 0.5]}},
                        {"probe": "ui", "field": "count"},
                        {"probe": "ui", "select": {"kind": "box", "rect": [0, 0.2, 0.5, 0.4]}, "field": "count"},
                        {"probe": "ui", "select": {"kind": "image"}, "field": "count"},
                        {"probe": "ui", "select": {"text": "AMMO"}, "field": "y", "of": "first"}):
            task_with(probe(measure=measure, expect={"op": ">=", "value": 1}))
        for bad, said in [({**UI_TEXT, "match": None}, "exactly when its field is text"),
                          ({"probe": "ui", "field": "count", "match": "x"}, "exactly when its field is text"),
                          ({**UI_TEXT, "match": "AMMO("}, "isn't a regular expression"),
                          ({"probe": "ui", "select": {"rect": [0.5, 0, 0.2, 1]}, "field": "count"}, "x0 < x1"),
                          ({"probe": "ui", "select": {"kind": "box", "text": "x"}, "field": "count"}, "picks text"),
                          ({"probe": "ui", "field": "source"}, "allowed"),
                          ({"probe": "ui", "field": "kind"}, "allowed"),
                          ({"probe": "ui", "select": {"kind": "line"}, "field": "count"}, ""),
                          ({"probe": "ui", "select": {"kind": "stroke"}, "field": "count"}, ""),
                          ({"probe": "ui", "select": {"source": "ugui"}, "field": "count"}, "")]:
            with self.assertRaisesRegex(ValueError, said, msg=json.dumps(bad)):
                task_with(probe(measure=bad))

    def test_one_query_per_select_its_fields_merged(self):
        text = m(**UI_TEXT)
        (query,) = probes.needs(text)
        self.assertEqual(query, {"kind": "ui", "select": {"kind": "text"}, "fields": ["text"]})
        count = m(probe="ui", select={"kind": "text"}, field="count")
        self.assertEqual(probes.query_id(probes.needs(count)[0]), probes.query_id(query))
        self.assertEqual(m(probe="ui", field="count")["select"], {})
        boxes = m(probe="ui", select={"kind": "box", "rect": [0, 0.2, 0.5, 0.4]}, field="count")
        self.assertNotEqual(probes.query_id(probes.needs(boxes)[0]), probes.query_id(query))

    def test_ugui_ui_toolkit_and_the_frame_read_the_same(self):
        text = m(**UI_TEXT)
        play = objects_play(text, [UI_ROWS, [r for r in UI_ROWS if r["source"] != "ocr"], None])
        self.assertEqual(probes.reduce({**text, "at": [0]}, play), 1, "the string read off the frame")
        self.assertEqual(probes.reduce({**text, "at": [0.5]}, play), 0, "no matching text on screen: 0")
        self.assertIsNone(probes.reduce({**text, "at": [1.0]}, play), "no frame drawn after the sample: no value")
        shown = m(**{**UI_TEXT, "match": r"HP\s*\d+%|ITEMS|AMMO", "of": "count"})
        self.assertEqual(probes.reduce({**shown, "at": [0]}, objects_play(shown, [UI_ROWS])), 3)
        place = m(probe="ui", select={"text": "AMMO"}, field="y", of="first")
        self.assertEqual(probes.reduce(place, objects_play(place, [[UI_ROWS[2]]])), 0.225)
        count = m(probe="ui", select={"kind": "box"}, field="count")
        self.assertEqual(probes.reduce(count, objects_play(count, [[UI_ROWS[3]] * 3])), 3)
        many = objects_play(count, [[{"count": 1}] * 200])
        many["measures"][probes.query_id(probes.needs(count)[0])][0]["total"] = 260
        self.assertEqual(probes.reduce(count, many), 260, "every element counts, past the rows cap")

    def test_images_and_boxes_count_by_rect(self):
        # one sample of a HUD: three heart sprites (images), a panel behind them (a box) and a label
        hearts = [{"text": None, "x": 0.02 + 0.03 * i, "y": 0.02, "w": 0.025, "h": 0.04, "source": "ugui",
                   "kind": "image"} for i in range(3)]
        panel = {"text": None, "x": 0.01, "y": 0.01, "w": 0.2, "h": 0.06, "source": "uitk", "kind": "box"}
        label = {"text": "LIVES", "x": 0.12, "y": 0.02, "w": 0.06, "h": 0.03, "source": "ugui", "kind": "text"}
        images = m(probe="ui", select={"kind": "image", "rect": [0, 0, 0.25, 0.1]}, field="count")
        self.assertEqual(images["select"], {"kind": "image", "rect": [0, 0, 0.25, 0.1]})
        self.assertEqual(probes.reduce(images, objects_play(images, [hearts])), 3)
        every = m(probe="ui", field="count")
        self.assertEqual(probes.reduce(every, objects_play(every, [hearts + [panel, label]])), 5)

    def test_text_read_from_the_frame_joins_the_text_elements(self):
        # a select of text in a rect also reads the frame as drawn there: one sample of an OnGUI readout "125 M", the
        # line read as a text element of source "ocr"
        rect = [0.031, 0.167, 0.208, 0.259]
        read = {"text": "125 M", "x": 0.046, "y": 0.183, "w": 0.143, "h": 0.059, "source": "ocr", "kind": "text"}
        measure = {"probe": "ui", "select": {"kind": "text", "rect": rect}, "field": "text", "match": r"^125\s*M$",
                   "of": "any"}
        task_with(probe(measure=measure, expect={"op": ">=", "value": 1}))
        text = m(**measure)
        self.assertEqual(text["select"], {"kind": "text", "rect": rect})
        self.assertEqual(probes.reduce(m(**measure, at=[0]), objects_play(text, [[read], []])), 1)
        self.assertEqual(probes.reduce(m(**measure, at=[0.5]), objects_play(text, [[read], []])), 0, "nothing read: 0")
        count = m(probe="ui", select={"kind": "text", "rect": rect}, field="count")
        ugui = {**UI_ROWS[0], "x": 0.042, "y": 0.556}
        self.assertEqual(probes.reduce(count, objects_play(count, [[read, ugui]])), 2)
        regex = m(probe="ui", select={"text": r"\d+\s*M", "rect": rect}, field="count")
        self.assertEqual(probes.reduce(regex, objects_play(regex, [[read]])), 1)


READOUT = [0.02, 0.02, 0.3, 0.12]


def text_readout(value, source="ugui"):
    return [{"text": f"SCORE {value}", "x": 0.05, "y": 0.04, "w": 0.01 * len(str(value)) + 0.06, "h": 0.03,
             "source": source, "kind": "text"}]


def digit_readout(digits):
    """A readout drawn as one digit sprite per digit, read off the frame: the sprites (images) and what was read."""
    sprites = [{"text": None, "x": 0.05 + 0.015 * i, "y": 0.04, "w": 0.012, "h": 0.03, "source": "ugui",
                "kind": "image"} for i in range(len(digits))]
    return sprites + [{"text": digits, "x": 0.05, "y": 0.04, "w": 0.015 * len(digits), "h": 0.03, "source": "ocr",
                       "kind": "text"}]


class UiSignature(unittest.TestCase):
    """docs/task-probes.md: whether what a ui select shows updates, however it is drawn."""

    def changes(self, rows, agg="changes", **extra):
        measure = m(probe="ui", select={"rect": READOUT}, field="signature", agg=agg, **extra)
        return probes.reduce(measure, objects_play(measure, rows))

    def test_takes_agg_changes_any_all_or_count(self):
        measure = {"probe": "ui", "select": {"rect": READOUT}, "field": "signature", "window": [2, 10],
                   "agg": "changes"}
        task_with(probe(measure=measure, expect={"op": ">=", "value": 1}))
        for agg in ("any", "all", "count"):
            task_with(probe(measure={**measure, "agg": agg}, expect={"op": ">=", "value": 1}))
        for agg in (None, "last", "max", "delta", "range"):
            with self.assertRaisesRegex(ValueError, "signature", msg=str(agg)):
                task_with(probe(measure={**measure, "agg": agg}))
        with self.assertRaisesRegex(ValueError, "exactly when its field is text"):
            task_with(probe(measure={**measure, "match": "x"}))
        (query,) = probes.needs(m(**measure))
        self.assertEqual(query, {"kind": "ui", "select": {"rect": READOUT}, "fields": ["h", "text", "w", "x", "y"]})
        count = m(probe="ui", select={"rect": READOUT}, field="count")
        self.assertEqual(probes.query_id(probes.needs(count)[0]), probes.query_id(query), "one select, one reading")

    def test_a_text_readout_changing_counts(self):
        rows = [text_readout(v) for v in (0, 0, 12, 12, 25, 140, 140)]
        self.assertEqual(self.changes(rows), 3)
        self.assertEqual(self.changes(rows, window=[0, 1.5]), 1)

    def test_a_readout_read_off_the_frame_changing_counts(self):
        self.assertEqual(self.changes([digit_readout(d) for d in ("10", "10", "12", "13", "13", "70")]), 3)
        self.assertEqual(self.changes([digit_readout("10")] * 6), 0)

    def test_a_static_readout_never_changes(self):
        still = text_readout(120)
        self.assertEqual(self.changes([still] * 8), 0)
        jitter = [[{**still[0], "x": 0.05 + d}] for d in (0, 0.0001, -0.0001, 0.0002)]
        self.assertEqual(self.changes(jitter), 0, "geometry is read to 0.002 of the viewport")
        restyled = [still, [{**still[0], "source": "uitk"}], [{**still[0], "name": "Other"}]]
        self.assertEqual(self.changes(restyled), 0, "how a build drew it is not what it shows")
        reordered = [text_readout(1) + digit_readout("1"), digit_readout("1") + text_readout(1)]
        self.assertEqual(self.changes(reordered), 0, "the elements are a set")

    def test_nothing_shown_reads_zero(self):
        rows = [[], text_readout(5), [], None]
        self.assertEqual(self.changes(rows, agg="count"), 1, "samples showing something")
        self.assertEqual(self.changes(rows, agg="all"), 0)
        self.assertEqual(self.changes(rows, agg="any"), 1)
        self.assertEqual(self.changes(rows), 2, "appearing and going are changes; no frame drawn is no value")


SPOT = {"point": {"xyz": [1, 0.5, 0]}, "radius": 3}
SPOT_SENT = {"point": {"xyz": [1.0, 0.5, 0.0]}, "radius": 3.0}
BEAM = {"from": {"player": True, "offset": [0, 0.6, 0]}, "to": {"camera": True, "forward": 30}, "radius": 0.4}


def number_rows(*texts):
    """Text elements of one sample, given right to left so reading order must be restored."""
    return [{"text": t, "x": 0.05 + 0.1 * i, "y": 0.04, "w": 0.08, "h": 0.03, "source": "ocr", "kind": "text"}
            for i, t in enumerate(texts)][::-1]


class OutcomeReadings(unittest.TestCase):
    """docs/task-probes.md: what is drawn in a place, how fast a part spins, live effects, which way a number or a
    clock on screen moved, an object a player can shove, a height band, a held teleport and a wait in real time."""

    def test_drawn_reads_a_place_near_a_point_or_along_a_line(self):
        near = [{"probe": "drawn", "near": SPOT, "field": f, "window": [2, 10], "agg": "mean"}
                for f in ("motion", "base_r", "base_g", "base_b", "base_change")]
        line = [{"probe": "drawn", "line": BEAM, "field": f, "at": "end"} for f in ("reach", "length")]
        for measure in near + line:
            with self.assertRaisesRegex(ValueError, "never a literal value"):
                task_with(probe(measure=measure, expect={"op": ">=", "value": 1}))
            task_with(probe(measure=measure, expect={"op": ">=", "start_times": 2}), seed=NO_FIX)
        task = task_with(*[probe(f"d{i}", measure=x, expect={"op": ">=", "calibrate": 0.5})
                           for i, x in enumerate(near + line)],
                         probe("shown", measure={"probe": "drawn", "near": SPOT, "field": "drawn"},
                               expect={"op": "==", "value": 1}))
        plan = probes.plan(task)["look"]
        self.assertEqual(sorted(len(q["fields"]) for q in plan), [2, 6], "one query per place, its fields merged")
        self.assertEqual(next(q for q in plan if "near" in q)["near"], SPOT_SENT)
        along = next(q for q in plan if "line" in q)["line"]
        self.assertEqual(along, {"from": {"player": True, "offset": [0, 0.6, 0]},
                                 "to": {"camera": True, "forward": 30.0}, "radius": 0.4})
        motion = m(probe="drawn", near=SPOT, field="motion", agg="mean")
        qid = probes.query_id(probes.needs(motion)[0])
        values = [{"drawn": 1, "motion": None}, {"drawn": 1, "motion": 0.2}, {"drawn": 1, "motion": 0.4}, None]
        self.assertAlmostEqual(probes.reduce(motion, {"measures": {qid: sampled(values)}}), 0.3)
        for bad in ({"probe": "drawn", "field": "drawn"}, {"probe": "drawn", "near": SPOT, "line": BEAM, "field": "drawn"},
                    {"probe": "drawn", "near": SPOT, "field": "reach"}, {"probe": "drawn", "line": BEAM, "field": "motion"},
                    {"probe": "drawn", "line": {**BEAM, "radius": 0}, "field": "reach"},
                    {"probe": "drawn", "near": SPOT, "field": "colour"}):
            with self.assertRaises(ValueError, msg=str(bad)):
                task_with(probe(measure=bad))

    def test_spin_is_a_field_of_components_and_objects_and_never_a_literal(self):
        fan = {"probe": "components", "select": {"component": "Renderer", "near": SPOT}, "field": "spin",
               "of": "max", "agg": "mean"}
        for measure in (fan, {"probe": "objects", "select": {"tag": "Fan"}, "field": "spin", "at": "end"}):
            with self.assertRaisesRegex(ValueError, "never a literal value"):
                task_with(probe(measure=measure, expect={"op": ">=", "value": 90}))
            task_with(probe(measure=measure, expect={"op": ">=", "calibrate": 0.5}))
        turning = m(**fan)
        rows = [[{"name": "Blade", "spin": None}], [{"name": "Blade", "spin": 360.0}, {"name": "Hub", "spin": 0.0}],
                [{"name": "Blade", "spin": 720.0}]]
        self.assertEqual(probes.reduce(turning, objects_play(turning, rows)), 540)

    def test_a_components_select_takes_live_effects_with_or_without_a_component(self):
        live = {"probe": "components", "select": {"effect": True, "near": SPOT}, "field": "count", "at": "end"}
        task_with(probe(measure=live, expect={"op": "<=", "value": 3}),
                  probe("b", measure={**live, "select": {"component": "ParticleSystem", "effect": True}}))
        (query,) = probes.needs(m(**live))
        self.assertEqual(query["select"], {"effect": True, "near": SPOT_SENT})
        for bad in ({"near": SPOT}, {"effect": False}):
            with self.assertRaises(ValueError, msg=str(bad)):
                task_with(probe(measure={**live, "select": bad}))

    def shown(self, field, samples, agg="last", **extra):
        measure = m(probe="ui", select={"kind": "text", "rect": READOUT}, field=field, agg=agg, **extra)
        return probes.reduce(measure, objects_play(measure, samples))

    def test_ui_number_reads_the_first_number_shown_in_reading_order(self):
        self.assertEqual(self.shown("number", [number_rows("SCORE", "3,450")]), 3450)
        self.assertEqual(self.shown("number", [number_rows("x3", "120")]), 3, "the first in reading order")
        self.assertEqual(self.shown("number", [number_rows("TEMP -12.5")]), -12.5)
        self.assertEqual(self.shown("number", [number_rows("LAP 2-3")]), 2, "a dash between numbers is no sign")
        self.assertIsNone(self.shown("number", [number_rows("READY")]))
        (query,) = probes.needs(m(probe="ui", select={"kind": "text", "rect": READOUT}, field="number"))
        signature = m(probe="ui", select={"kind": "text", "rect": READOUT}, field="signature", agg="changes")
        self.assertEqual(query, probes.needs(signature)[0], "one select, one query")
        with self.assertRaisesRegex(ValueError, "exactly when its field is text"):
            task_with(probe(measure={"probe": "ui", "select": {"rect": READOUT}, "field": "number", "match": "x"}))

    def test_ui_number_tells_which_way_it_moved(self):
        scores = [number_rows(f"SCORE {v}") for v in (0, 0, 10, 25, 25, 0, 5)] + [None]
        self.assertEqual(self.shown("number", scores, agg="rises"), 3)
        self.assertEqual(self.shown("number", scores, agg="falls"), 1, "a reset is a fall")
        self.assertEqual(self.shown("number", scores, agg="changes"), 4)
        task_with(probe(measure={"probe": "ui", "select": {"kind": "text", "rect": READOUT}, "field": "number",
                                 "window": [2, 10], "agg": "falls"}, expect={"op": "==", "value": 0}))

    def test_ui_clock_reads_a_timer_as_seconds_through_a_pause_and_a_retry(self):
        self.assertEqual(self.shown("clock", [number_rows("TIME 1:05.5")]), 65.5)
        self.assertEqual(self.shown("clock", [number_rows("1:02:03")]), 3723)
        self.assertEqual(self.shown("clock", [number_rows("12.5s")]), 12.5, "a plain number is seconds")
        run = [number_rows(f"0:{s:02d}") for s in (1, 2, 3)] + [number_rows("0:03")] * 4 + \
            [number_rows(f"0:{s:02d}") for s in (0, 1)]
        self.assertEqual(self.shown("clock", run, agg="range", window=[1.0, 3.0]), 0, "held through the pause")
        self.assertEqual(self.shown("clock", run, agg="falls"), 1, "reset on the retry")

    def test_has_finds_an_object_by_what_it_can_do(self):
        shovable = {"has": {"simulating": True, "movable": True, "near": {"point": {"player": True}, "radius": 20}}}
        play = {"name": "shove", "seconds": 10, "inputs": [{"t": 1, "teleport_to": shovable, "distance": 1.5}]}
        task = task_with(probe(play=play, measure={"probe": "objects", "select": shovable, "field": "x", "at": "end"}))
        self.assertTrue(probes.plan(task)["shove"][0]["select"]["has"]["simulating"])
        with self.assertRaises(ValueError):
            task_with(probe(measure={"probe": "objects", "select": {"has": {"movable": False}}, "field": "count"}))

    def test_near_takes_a_height_band_wherever_it_works(self):
        band = {"point": {"xyz": [0, 0, 0]}, "radius": 5, "y_min": 1, "y_max": 3}
        rel = {"point": {"player": True}, "radius": 5, "y_min": -0.5, "y_relative": True}
        task = task_with(
            probe("a", measure={"probe": "objects", "select": {"near": band}, "field": "count"}),
            probe("b", measure={"probe": "components", "select": {"component": "Light", "near": rel},
                                "field": "count"}),
            probe("c", measure={"probe": "pieces", "select": {"near": band}, "field": "count"}),
            probe("d", measure={"probe": "objects", "select": {"has": {"visible": True, "near": rel}},
                                "field": "count"}),
            probe("e", measure={"probe": "drawn", "near": band, "field": "drawn"}))
        sent = [json.dumps(q, sort_keys=True) for q in probes.plan(task)["look"]]
        self.assertEqual(sum('"y_max": 3.0, "y_min": 1.0' in q for q in sent), 3)
        self.assertEqual(sum('"y_relative": true' in q for q in sent), 2)
        plain = m(probe="objects", select={"near": SPOT}, field="count")
        self.assertEqual(probes.needs(plain)[0]["select"], {"near": SPOT_SENT}, "a near without a band as before")
        for bad in ({**band, "y_min": 3}, {"point": {"player": True}, "radius": 1, "y_relative": True},
                    {**band, "z_min": 1}):
            with self.assertRaises(ValueError, msg=str(bad)):
                task_with(probe(measure={"probe": "objects", "select": {"near": bad}, "field": "count"}))

    def test_a_teleport_holds_and_a_play_waits_in_real_time(self):
        play = {"name": "tour", "seconds": 60, "inputs": [
            {"t": 1, "teleport": [0, 1, 0], "hold": 5}, {"t": 2, "teleport_to": {"tag": "Pad"}, "hold": 3},
            {"t": 4, "key": "<Keyboard>/enter", "press": True}, {"t": 8, "wait": 90}, {"t": 20, "wait": 30}]}
        task = task_with(probe(play=play, measure={"probe": "player", "field": "y"}))
        sent = first_check(task)["play"]
        self.assertEqual(tasks.waited(sent), 120)
        self.assertEqual(sent["inputs"][0], {"t": 1.0, "teleport": [0.0, 1.0, 0.0], "yaw": 0.0, "hold": 5.0})
        self.assertEqual(sent["inputs"][3], {"t": 8.0, "wait": 90.0})
        self.assertEqual(tasks.play({"name": "tp", "seconds": 9, "inputs": [{"t": 1, "teleport": [0, 0, 0]}]})["inputs"],
                         [{"t": 1.0, "teleport": [0.0, 0.0, 0.0], "yaw": 0.0}], "sent as before")
        for bad in ([{"t": 1, "wait": 200}, {"t": 2, "wait": 150}], [{"t": 1, "wait": 0}], [{"t": 1, "wait": 301}],
                    [{"t": 1, "teleport": [0, 0, 0], "hold": 0}], [{"t": 1, "teleport": [0, 0, 0], "hold": 121}]):
            with self.assertRaises(ValueError, msg=str(bad)):
                task_with(probe(play={**play, "inputs": bad}, measure={"probe": "player", "field": "y"}))

    def test_inputs_are_input_system_control_paths(self):
        play = {"name": "keys", "seconds": 10, "inputs": [
            {"t": 1, "key": "<Keyboard>/leftShift", "press": True}, {"t": 2, "key": "<Mouse>/leftButton", "press": True},
            {"t": 3, "key": "<Gamepad>/buttonSouth", "press": False}, {"t": 4, "key": "<Mouse>/delta/x", "axis": 4},
            {"t": 5, "key": "<Gamepad>/leftStick/x", "axis": -1}, {"t": 6, "cursor": [0.5, 0.25]},
            {"t": 7, "widget": "RetryButton", "click": True}]}
        sent = first_check(task_with(probe(play=play, measure={"probe": "player", "field": "y"})))["play"]["inputs"]
        self.assertEqual(sent[3], {"t": 4.0, "key": "<Mouse>/delta/x", "axis": 4.0})
        self.assertEqual(sent[5], {"t": 6.0, "cursor": [0.5, 0.25]})
        self.assertEqual(sent[6], {"t": 7.0, "widget": "RetryButton", "click": True})
        for key in ("W", "LeftMouseButton", "<Joystick>/trigger", "<Keyboard>/"):
            with self.assertRaises(ValueError, msg=key):
                task_with(probe(play={**play, "inputs": [{"t": 1, "key": key, "press": True}]},
                                measure={"probe": "player", "field": "y"}))


class Angles(unittest.TestCase):
    def test_angles_aggregates_and_the_new_query_kinds_reduce(self):
        self.assertEqual([probes.normal(a) for a in (270, -270, 180, -180, 540, 0)], [-90, 90, 180, 180, 180, 0])
        camera = {"camera": [[0.0, 0, 0, 0, 0.0, 270.0, 60.0], [0.5, 0, 0, 0, 0.0, -100.0, 60.0]]}
        self.assertEqual(probes.reduce(m(probe="camera", field="yaw", agg="first"), camera), -90)
        self.assertAlmostEqual(probes.reduce(m(probe="camera", field="yaw", to_angle=-90, agg="max"), camera), 10)
        turret = m(probe="objects", select={"tag": "Tank"}, field="rel_yaw:Turret", to_angle=180, of="max")
        self.assertEqual(probes.reduce(turret, objects_play(turret, [[{"rel_yaw:Turret": -170},
                                                                      {"rel_yaw:Turret": 175}]])), 10)
        self.assertEqual(probes.aggregate([1.0, 3.0, 3.0, 5.0], "range"), 4)
        self.assertAlmostEqual(probes.aggregate([1.0, 3.0, 3.0, 5.0], "std"), 2 ** 0.5)
        self.assertEqual(probes.aggregate([1.0, 1.0, 0.0, 0.0, 1.0, None], "changes"), 2)
        torches = m(probe="components", select={"component": "ParticleSystem", "owner": {"tag": "Torch"}},
                    field="active", of="count")
        self.assertEqual(probes.reduce(torches, objects_play(torches, [[{"active": True}, {"active": False},
                                                                        {"active": 1}]])), 2)
        hint = m(probe="widgets", select={"component": "TMP_Text", "text": "^Press E"}, field="y", of="max")
        self.assertEqual(probes.reduce(hint, objects_play(hint, [[{"y": 0.9}, {"y": 0.4}]])), 0.9)
        blur = m(probe="grading", field="post:MotionBlur.intensity", agg="max")
        qid = probes.query_id(probes.needs(blur)[0])
        self.assertEqual(probes.reduce(blur, {"measures": {qid: sampled([{"post:MotionBlur.intensity": 0.5},
                                                                         {"post:MotionBlur.intensity": 0.0}])}}), 0.5)

    def test_a_property_that_holds_an_angle_takes_to_angle_live_and_as_saved(self):
        live = m(probe="objects", select={"component": "TrackGrid"}, field="prop:TrackGrid.straightYaw", to_angle=90)
        self.assertEqual((probes.angled(live, 450.0), probes.angled(live, -270.0), probes.angled(live, 0.0)),
                         (0.0, 0.0, 90.0))
        self.assertEqual(probes.angled(live, 270.0), 180.0)
        self.assertEqual(probes.angled(live, -90.0), 180.0)
        saved = m(probe="asset", scene="Assets/Scenes/L2.unity", select={"name": "ChimeRack"},
                  field="prop:Transform.localEulerAngles.y", to_angle=0, of="max")
        self.assertEqual(probes.reduce_asset(saved, {"rows": [{"name": "ChimeRack", "value": -90.0}]}), (90.0, None))
        plain = m(probe="objects", select={"component": "TrackGrid"}, field="prop:TrackGrid.straightYaw")
        self.assertEqual(probes.angled(plain, 450.0), 450.0, "a property is an angle only with to_angle")

    def test_to_axis_folds_a_direction_and_its_opposite_into_one_axis(self):
        axis = m(probe="objects", select={"component": "TrackGrid"}, field="prop:TrackGrid.straightYaw", to_axis=90)
        self.assertEqual({probes.angled(axis, a) for a in (90.0, -90.0, 270.0)}, {0.0})
        self.assertEqual((probes.angled(axis, 0.0), probes.angled(axis, 180.0), probes.angled(axis, 45.0)),
                         (90.0, 90.0, 45.0))


class Grading(unittest.TestCase):
    def test_the_colour_fields_come_from_the_grading_samples(self):
        grading = m(probe="grading", field="warmth", at="end")
        (query,) = probes.needs(grading)
        self.assertEqual(query, {"kind": "grading", "fields": []}, "the colour settings always come")
        qid = probes.query_id(query)
        warm = {"color_balance": colour.lms_coeffs(50, 0)}
        self.assertGreater(probes.reduce(grading, {"measures": {qid: sampled([{}, warm])}}), 0.1)
        self.assertAlmostEqual(probes.reduce(m(probe="grading", field="grey", agg="first"),
                                             {"measures": {qid: sampled([{}, warm])}}), 0.18)
        self.assertEqual(probes.reduce(m(probe="grading", field="contrast", at="end"),
                                       {"measures": {qid: sampled([{"contrast": 1.3}])}}), 1.3)
        unread = m(probe="grading", field="cast", at="end")
        self.assertIsNone(probes.reduce(unread, {"measures": {qid: [{"t": 0.0}]}}),
                          "a sample the probe couldn't read reads nothing, never a neutral grade")


# -- the editor pass ------------------------------------------------------------------------------------------------------


EDITOR_TASK_CHECKS = [
    probe("double", play="editor", measure={"probe": "asset", "asset": "Assets/Materials/Road.mat",
                                            "field": "shader:_Cull"}, expect={"op": "==", "value": 0}),
    probe("emits", play="editor", measure={"probe": "asset", "asset": "Assets/Materials/Road.mat",
                                           "field": "keyword:_EMISSION"}, expect={"op": "==", "value": 1}),
    probe("named", play="editor", measure={"probe": "asset", "asset": "Assets/Data/Road.asset",
                                           "field": "prop:label", "match": "^Road"}, expect={"op": "==", "value": 1}),
    probe("compressed", play="editor", measure={"probe": "asset", "asset": "Assets/Textures/Road.png",
                                                "field": "import:textureCompression"}),
    probe("terraces", play="editor", measure={"probe": "asset", "scene": "Assets/Scenes/Level6.unity",
                                              "select": {"component": "MeshRenderer", "tag": "Terrace"},
                                              "field": "material_default", "of": "any"},
          expect={"op": "==", "value": 0}),
    probe("colliding", play="editor", measure={"probe": "asset", "scene": "Assets/Scenes/Level6.unity",
                                               "select": {"name": "Terrace*"}, "field": "mesh_collision", "of": "all"},
          expect={"op": "==", "value": 1}),
    probe("prefab", play="editor", measure={"probe": "asset", "prefab": "Assets/Prefabs/Lamp.prefab",
                                            "select": {"component": "Light"}, "field": "prop:Light.intensity",
                                            "of": "max"}, expect={"op": ">=", "value": 1})]


class Editor(unittest.TestCase):
    def test_the_request_names_every_asset_measure_once_by_its_id(self):
        task = task_with(*EDITOR_TASK_CHECKS)
        items = probes.editor_items(task)
        self.assertEqual(len(items), 7)
        self.assertEqual([i for i, _ in items], sorted(i for i, _ in items))
        request = probes.editor_request(items, "n0nce")
        self.assertEqual(set(request), {"nonce", "measures"})
        self.assertEqual(request["nonce"], "n0nce")
        terraces = first_check(task_with(EDITOR_TASK_CHECKS[4]))["measure"]
        self.assertEqual(request["measures"][probes.editor_id(terraces)],
                         {"probe": "asset", "scene": "Assets/Scenes/Level6.unity",
                          "select": {"component": "MeshRenderer", "tag": "Terrace"}, "field": "material_default",
                          "of": "any"})
        again = task_with(*EDITOR_TASK_CHECKS, probe("double_again", play="editor",
                                                     measure={"probe": "asset", "asset": "Assets/Materials/Road.mat",
                                                              "field": "shader:_Cull"},
                                                     expect={"op": "==", "value": 0}))
        self.assertEqual(len(probes.editor_items(again)), 7, "the same measure is asked once")

    def test_the_results_reduce_to_each_probes_number(self):
        task = task_with(*EDITOR_TASK_CHECKS)
        checks = {c["name"]: c["measure"] for _, c in tasks.checks(task)}
        answers = {"double": {"value": 0}, "emits": {"value": True}, "named": {"value": "Road (wet)"},
                   "compressed": {"error": "no importer property textureCompression"},
                   "terraces": {"rows": [{"name": "Terrace_1", "value": 0}, {"name": "Terrace_2", "value": 1}]},
                   "colliding": {"rows": [{"name": "Terrace_1", "value": 1}, {"name": "Terrace_2", "value": 0}]},
                   "prefab": {"rows": [{"name": "Lamp/Bulb", "value": 2.5}, {"name": "Lamp/Fill", "value": None}]}}
        line = json.dumps({"nonce": "n0nce", "measures": {probes.editor_id(checks[n]): r for n, r in answers.items()}})
        results = probes.editor_results(line.encode(), "n0nce")
        log = f"Refreshing native plugins\n{probes.MARKER} {line}\nExiting batchmode successfully now!\n"
        self.assertEqual(results, probes.editor_results(None, "n0nce", log), "the file and the printed line agree")
        values = {n: probes.reduce_asset(checks[n], results[probes.editor_id(checks[n])]) for n in checks}
        self.assertEqual((values["double"], values["emits"], values["named"]), ((0.0, None), (1.0, None), (1.0, None)))
        self.assertEqual(values["compressed"],
                         (None, "the editor couldn't measure it: no importer property textureCompression"))
        self.assertEqual(values["terraces"], (1.0, None), "Terrace_2 shows the default material")
        self.assertEqual(values["colliding"][0], 0.0, "Terrace_2 has no collider")
        self.assertEqual(values["prefab"], (2.5, None))
        none = m(probe="asset", prefab="Assets/Prefabs/Lamp.prefab", select={"component": "Light"},
                 field="prop:Light.intensity", of="max")
        self.assertEqual(probes.reduce_asset(none, {"rows": [{"name": "a", "value": None}]}),
                         (None, "no selected object has a value"))
        self.assertEqual(probes.reduce_asset(checks["double"], {"value": None}), (None, "the property has no number"))

    def test_the_editor_results_need_the_checkers_nonce(self):
        line = json.dumps({"nonce": "mine", "measures": {"a1": {"value": 1}}})
        planted = json.dumps({"nonce": "guess", "measures": {"a1": {"value": 0}}})
        output = f"{probes.MARKER} {line}\n{probes.MARKER} {planted}\n"
        self.assertEqual(probes.editor_results(None, "mine", output), {"a1": {"value": 1}})
        self.assertEqual(probes.editor_results(planted.encode(), "mine", output), {"a1": {"value": 1}})
        self.assertIsNone(probes.editor_results(None, "mine", "Crash!!!"))
        self.assertIsNone(probes.editor_results(b"nor this", "mine", f"{probes.MARKER} not json"))
        self.assertEqual(probes.editor_results(line.encode(), "mine"), {"a1": {"value": 1}})
        self.assertIsNone(probes.editor_results(planted.encode(), "mine"))
        self.assertIsNone(probes.editor_results(json.dumps({"nonce": "mine"}).encode(), "mine"))
        measure = m(probe="asset", scene="Assets/Scenes/L.unity", select={"tag": "T"}, field="count")
        self.assertEqual(probes.reduce_asset(measure, {"rows": [{"name": "a", "value": 1}] * 3}), (3.0, None))
        self.assertEqual(probes.reduce_asset(measure, None), (None, "the editor pass gave nothing for it"))

    def test_an_asset_measures_id_is_its_set_fields(self):
        check = first_check(task_with(probe("road", play="editor", measure={"probe": "asset", "asset": "Assets/M.mat",
                                                                            "field": "shader:_Cull"})))
        (item,) = probes.editor_items(task_with(probe("road", play="editor",
                                                      measure={"probe": "asset", "asset": "Assets/M.mat",
                                                               "field": "shader:_Cull"})))
        self.assertEqual(item, (probes.editor_id(check["measure"]),
                                {"probe": "asset", "asset": "Assets/M.mat", "field": "shader:_Cull", "of": "count"}))

    def test_an_asset_measure_reads_one_asset_or_one_scene_or_prefab(self):
        for bad in ({"probe": "asset", "asset": "Assets/M.mat", "scene": "Assets/Scenes/A.unity", "field": "count"},
                    {"probe": "asset", "field": "prop:x"},
                    {"probe": "asset", "asset": "Assets/M.mat", "field": "count"},
                    {"probe": "asset", "scene": "Assets/Scenes/A.unity", "select": {"tag": "T"},
                     "field": "shader:_Cull"}):
            with self.assertRaises(ValueError, msg=json.dumps(bad)):
                task_with(probe(play="editor", measure=bad))


if __name__ == "__main__":
    unittest.main()
