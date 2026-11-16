"""A mobile game's plays in the task check (docs/task-probes.md 1.1): a copy whose game has a Platform.json is played
at the phone's size, its spec saying `size` and `touch`; a copy without one is a desktop game's, launched as always."""

import json
import sys
import tempfile
import unittest
from pathlib import Path

import helpers  # noqa: F401  (puts the tools folder on the path)

from task_check import tasks, unity


class FakeMachine:
    def __init__(self):
        self.argvs = []

    def job(self, label, argv, cwd, timeout, gpu=False):
        self.argvs.append([str(a) for a in argv])
        return unity.Result(0, "", 1.0)


def launched(platform=None):
    """(the argument list, the spec) of one play of a copy whose Platform.json holds `platform` (None: no such file)."""
    with tempfile.TemporaryDirectory() as tmp:
        if platform is not None:
            (Path(tmp) / "Platform.json").write_text(platform if isinstance(platform, str) else json.dumps(platform))
        machine = FakeMachine()
        project = unity.Project(tmp, machine, "game start")
        project.player().parent.mkdir(parents=True)
        project.player().write_bytes(b"")
        project.play(5, 2, 60)
        spec = json.loads((Path(tmp) / unity.LOGS / unity.SPEC).read_text())
        logs = (Path(tmp) / unity.LOGS)
        argv = [a.replace(str(logs / "play.log"), "<log>").replace(str(logs / unity.SPEC), "<spec>")
                .replace(str(project.player()), "<exe>") for a in machine.argvs[0]]
        return argv, spec


class MobilePlay(unittest.TestCase):
    def test_a_desktop_games_play_is_launched_as_before(self):
        argv, spec = launched()
        self.assertEqual(argv, [sys.executable, str(unity.DESK), "<exe>", "-screen-fullscreen", "0", "-screen-width", "960",
                                "-screen-height", "540", "-logFile", "<log>", "-taskProbe", "<spec>"])
        self.assertEqual(sorted(spec), ["every", "format", "inputs", "out", "player", "queries", "scene", "seconds",
                                        "shots", "sound"])

    def test_a_mobile_games_play_is_at_the_phones_size_by_touch(self):
        portrait, spec = launched({"platform": "mobile", "orientation": "portrait"})
        self.assertEqual(portrait[3:9], ["-screen-fullscreen", "0", "-screen-width", "1080", "-screen-height", "1920"])
        self.assertEqual((spec["size"], spec["touch"]), ([1080, 1920], True))
        landscape, spec = launched({"platform": "mobile", "orientation": "landscape"})
        self.assertEqual(landscape[5:9], ["-screen-width", "1920", "-screen-height", "1080"])
        self.assertEqual(spec["size"], [1920, 1080])
        self.assertEqual(portrait[9:], launched()[0][9:], "everything after the window is a desktop play's")

    def test_a_platform_file_that_says_neither_is_never_read_as_desktop(self):
        read = tasks.validator().read_platform
        for bad in ("not json", {"platform": "mobile"}, {"platform": "desktop", "orientation": "portrait"},
                    {"platform": "mobile", "orientation": "sideways"}, {"platform": "mobile", "orientation": "portrait", "x": 1},
                    ["mobile", "portrait"]):
            with tempfile.TemporaryDirectory() as tmp:
                (Path(tmp) / "Platform.json").write_text(bad if isinstance(bad, str) else json.dumps(bad))
                with self.assertRaises(ValueError, msg=str(bad)):
                    read(tmp)
                with self.assertRaises(ValueError, msg=str(bad)):
                    launched(bad)
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(read(tmp))
            (Path(tmp) / "Platform.json").write_text('{"platform": "mobile", "orientation": "landscape"}')
            self.assertEqual(read(tmp), "landscape")


if __name__ == "__main__":
    unittest.main()
