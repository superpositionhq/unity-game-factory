"""The core family: the play loop itself (the clock, sampling, screenshots, every kind of input, teleports and holds,
waits, who the player and the camera are, scenes, the ends of a play, saved data, errors)."""

import re
import subprocess
import sys
from pathlib import Path

MADE = "Assets/ProbeTests/core/Made/"
SETUP = ["ProbeTests.Core.CoreScenes.Build"]
SCENES = [MADE + "First.unity", MADE + "Clock.unity", MADE + "Stage.unity", MADE + "Who.unity", MADE + "Bodies.unity"]
HALF_SECONDS = [1 / 30, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5]  # a 3 s play's samples: the first frame, then every 0.5 s
FLOAT = 1e-5  # a float of the game widened to a double


def times(play):
    return [round(row[0], 6) for row in play.probe["track"]]


def walker(play, t, field):
    """What the Stage's hero saw (CoreWalker's fields) at play time t."""
    return play.row("hero", t, "Hero").get("prop:CoreWalker." + field)


def clock(t, play):
    """The play's clock is the game's: an object moving 1 m/s is t metres along at play time t. The play's scene was
    asked for before the game's first scene woke up."""
    probe = play.probe
    t.eq("format", probe.get("format"), "unity-probe/1")
    t.eq("scene", probe.get("scene"), MADE + "Clock.unity")
    t.eq("player", probe.get("player"), "Hero")
    t.near("seconds: the play's 3 s, half a second more, and the frame its last screen sample waits for",
           probe.get("seconds"), 3.5 + 1 / 30, 1e-9)
    t.eq("the samples' times: the first frame, then every 0.5 s", times(play), [round(x, 6) for x in HALF_SECONDS])
    for row in probe["track"]:
        t.near(f"the hero's x at {row[0]:.3f} s", row[1], row[0], FLOAT)
    t.eq("the camera row at 2 s", play.camera(2.0)[1:], [0.0, 2.0, -8.0, 0.0, 0.0, 60.0])
    t.eq("screenshots", probe.get("screenshots"), ["shot_00.png", "shot_01.png"])
    t.ok("the frame has light in it", (play.value("frame", 2.0) or {}).get("luminance", 0) > 0.01, play.value("frame", 2.0))
    t.ok("the play ran on a desktop of its own", "on its own desktop" in play.probe_log, play.probe_log[:200])
    for line in ("CORE First Awake", "CORE First OnEnable", "CORE First OnDestroy"):
        t.ok(f"the game's first scene got as far as: {line}", line in play.log)
    for line in ("CORE First Start", "CORE First Update"):
        t.ok(f"the game's first scene never got to: {line}", line not in play.log)


def clocks(t, play):
    """Which of the game's clocks is the play's: Time.time is (a frame is 1/30 s of it, however fast the machine
    renders); Time.unscaledTime goes with the wall clock, as Time.realtimeSinceStartup does."""
    def at(when, field):
        return play.row("clocks", when, "Hero")["prop:CoreMover." + field]

    for when in (0.5, 2.0, 3.5):
        t.near(f"Time.time at {when} s, counted from the game's first Update", at(when, "game"), when - 1 / 30, FLOAT)
    wall = at(3.5, "real") - at(0.5, "real")
    t.near("Time.unscaledTime went as far as the wall clock from 0.5 s to 3.5 s", at(3.5, "unscaled") - at(0.5, "unscaled"), wall, 0.05)


def _start(t, name, *args, build="TaskProbe"):
    """A built player started by hand, as the checker starts a play (on its own desktop): (exit code, its log)."""
    exe = t.project / "Build" / build / "Game.exe"
    log = t.project / "Logs" / "ProbeTests" / f"core.{name}.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    log.unlink(missing_ok=True)
    desk = Path(__file__).resolve().parents[2] / "desk.py"
    ran = subprocess.run([sys.executable, str(desk), str(exe), "-screen-fullscreen", "0", "-screen-width", "960",
                          "-screen-height", "540", "-logFile", str(log), *args], cwd=str(exe.parent), timeout=180)
    code = ran.returncode - (1 << 32) if ran.returncode >= 1 << 31 else ran.returncode
    return code, log.read_text(encoding="utf-8", errors="replace") if log.is_file() else ""


def fine(t, play):
    """`seconds` below 1 is 1 and `every` below 0.1 is 0.1. The player's log holds what the game logged in the play's
    very last frame (the process ends as soon as the play's files are written)."""
    t.near("seconds", play.probe.get("seconds"), 1.5, 1e-9)
    t.ok("the last frame's log line is in the player's log", "CORE the last frame of a 1 s play" in play.log, play.log[-300:])
    t.eq("the samples' times", times(play), [round(1 / 30, 6)] + [round(k / 10, 6) for k in range(1, 16)])


def inputs(t, play):
    """Keys, mouse axes and buttons, the cursor and widget clicks reach the game, one frame after they are sent."""
    t.near("W went down at 1 s and the game saw it the frame after: z at 1.5 s", play.track(1.5)[3], 1.0, FLOAT)
    t.near("W went up at 2 s: z at 2 s", play.track(2.0)[3], 2.0, FLOAT)
    t.near("W down again 3 to 3.5 s: z at 6 s", play.track(6.0)[3], 3.0, FLOAT)
    t.eq("W and D sent in one frame were both down for the 15 frames", walker(play, 6.0, "both"), 15)
    t.near("a mouse delta of 4 is seen once", walker(play, 6.0, "mouseX"), 4.0, FLOAT)
    t.near("a scroll of 3 is seen once", walker(play, 6.0, "scrollY"), 3.0, FLOAT)
    t.eq("the left button was down for 15 frames", walker(play, 6.0, "left"), 15)
    t.near("the cursor at [0.25, 0.75] is 240 px from the left", walker(play, 6.0, "cursorX"), 240.0, FLOAT)
    t.near("and 135 px from the bottom", walker(play, 6.0, "cursorY"), 135.0, FLOAT)
    t.eq("no gamepad unless an input names one", walker(play, 6.0, "pad"), 0)
    t.eq("the widget click clicked the button once", play.row("button", 6.0, "PushButton").get("prop:CoreButton.clicks"), 1)
    t.ok("the click is in probe.log", "clicked PushButton" in play.probe_log)
    t.ok("a click on no button says so", "no visible button matches 'NoSuchButton'" in play.probe_log)
    t.eq("inputs_sent counts every input", play.probe.get("inputs_sent"), 15)
    t.eq("the game counted itself focused in every frame", walker(play, 6.0, "unfocused"), 0)
    t.eq("and never lost the focus", walker(play, 6.0, "focusLost"), 0)


def pad(t, play):
    """A gamepad is there when an input names it; a stick keeps its value, a button is down while pressed."""
    t.eq("a gamepad", walker(play, 2.0, "pad"), 1)
    t.near("the stick at 1.5 s", walker(play, 1.5, "stickX"), 1.0, FLOAT)
    t.near("the stick still at 2 s", walker(play, 2.0, "stickX"), 1.0, FLOAT)
    t.eq("the south button was down for 15 frames", walker(play, 2.0, "south"), 15)


def teleport(t, play):
    """teleport puts the player at a place facing a yaw; teleport_to puts it next to the nearest match, on its own
    side of it, facing it or a point."""
    t.eq("teleport: the place", play.track(1.0)[1:], [5.0, 0.0, 5.0])
    t.near("teleport: the yaw", play.row("hero", 1.0, "Hero")["yaw"], 90.0, 1e-3)
    t.eq("teleport_to: 2 m from the nearer Post, on the player's side", play.track(2.0)[1:], [8.0, 0.0, 5.0])
    t.near("teleport_to: facing it", play.row("hero", 2.0, "Hero")["yaw"], 90.0, 1e-3)
    t.eq("teleport_to: distance 3, offset 1 m up", play.track(3.0)[1:], [7.0, 1.0, 5.0])
    t.near("teleport_to: facing the point", play.row("hero", 3.0, "Hero")["yaw"], 0.60309, 1e-3)
    t.eq("the camera follows", play.camera(3.5)[1:4], [7.0, 4.0, -1.0])
    t.ok("a select matching nothing is skipped and said", "teleport_to skipped (no object matches)" in play.probe_log)
    t.eq("inputs_sent", play.probe.get("inputs_sent"), 4)


def hold(t, play):
    """A held player stays at the spot whatever the game does with it (here it drifts 1 m/s), the camera with it."""
    t.near("before: it drifts", play.track(0.5)[1], 0.5, FLOAT)
    for at in (1.0, 1.5, 2.0, 2.5):
        t.eq(f"held at {at} s", play.track(at)[1:], [0.0, 0.0, 0.0])
        t.eq(f"the follow camera at {at} s stands where it stands for a player at the spot", play.camera(at)[1:4], [0.0, 3.0, -6.0])
    t.near("the hold is over at 3 s: that frame's drift stays", play.track(3.0)[1], 1 / 30, FLOAT)
    t.near("and it drifts on", play.track(4.0)[1], 31 / 30, FLOAT)
    t.ok("the hold is in probe.log", "holding the player at (0.00, 0.00, 0.00) for 2.0 s" in play.probe_log)


def body(lane, yaw=True):
    """A player the game moves through a CharacterController, a Rigidbody or a Rigidbody2D (1 m/s along x, under
    gravity): teleported 4 m up at 1 s and held for 1.5 s it hangs there, still; then it falls and goes on."""
    def check(t, play):
        t.ok("before: the game moves it along x", lane + 0.2 < play.track(0.5)[1] < lane + 0.7, play.track(0.5))
        for at in (1.0, 1.5, 2.0):
            t.eq(f"held at {at} s, 4 m up", play.track(at)[1:], [float(lane), 4.0, 0.0])
        if yaw:
            t.near("facing the teleport's yaw", play.row("body", 1.5, play.probe["player"])["yaw"], 90.0, 1e-3)
        t.ok("after the hold it falls", play.track(3.5)[2] < 3.0, play.track(3.5))
        t.ok("and the game moves it on", play.track(3.5)[1] > lane + 0.5, play.track(3.5))
    return check


def hold_wait(t, play):
    """A hold goes on through a wait: the clock stands still, the game runs, the player stays held."""
    t.eq("held after the wait", play.track(1.0)[1:], [-10.0, 0.0, 0.0])
    t.near("no frame of the game found the player anywhere but at the spot", walker(play, 1.0, "strayed"), -10.0, FLOAT)


def wait(t, play):
    """A wait holds the play's clock for its seconds of real time while the game runs on; the sample of the frame it
    starts in is taken first; the inputs after it wait for its end."""
    t.near("the sample at 1 s is of the frame the wait starts in", play.track(1.0)[1], 1.0, FLOAT)
    ran = play.track(1.5)[1] - 1.5
    t.ok("the game ran at least 2 s more than the play's clock (and not much more)", 2.0 - FLOAT <= ran <= 3.0, ran)
    t.ok("in at least 2 s of real time", play.seconds >= 2.0, play.seconds)
    t.ok("probe.log: the clock holds", "the play's clock holds at 1.00 s for 2.0 s of real time" in play.probe_log)
    t.ok("probe.log: the wait is over", "the wait is over" in play.probe_log)
    t.eq("the input after the wait was sent too", play.probe.get("inputs_sent"), 2)


def shots(t, play):
    """Screenshots are 960x540, opaque, with the UI."""
    t.eq("three shots", play.probe.get("screenshots"), ["shot_00.png", "shot_01.png", "shot_02.png"])
    for name in play.probe.get("screenshots"):
        shot = play.image(name)
        t.eq(f"{name}: size", (shot.width, shot.height), (960, 540))
        t.eq(f"{name}: no alpha channel", shot.channels, 3)
        t.eq(f"{name}: the UI's magenta badge is in the top left corner", shot.at(48, 27), (255, 0, 255))
        t.ok(f"{name}: and not in the middle", shot.at(480, 270) != (255, 0, 255), shot.at(480, 270))


def first(t, play):
    """A play without a scene plays the game's first build scene. A play whose spec can't be read doesn't run as a
    game until someone kills it: the player says why and exits with code 2."""
    t.eq("scene", play.probe.get("scene"), MADE + "First.unity")
    for line in ("CORE First Start", "CORE First Update"):
        t.ok(f"the first scene runs: {line}", line in play.log)

    code, said = _start(t, "nospec", "-taskProbe", str(t.project / "Logs" / "ProbeTests" / "no-such-spec.json"))
    t.eq("-taskProbe with a spec file that isn't there: exit code", code, 2)
    t.ok("and the reason in the player's log", "TaskProbe: the play spec" in said and "couldn't be read" in said, said[-300:])
    bad = t.project / "Logs" / "ProbeTests" / "bad-spec.json"
    bad.write_text('{"format": "something-else/1", "seconds": 1}', encoding="utf-8")
    code, said = _start(t, "badspec", "-taskProbe", str(bad))
    t.eq("-taskProbe with a spec of another format: exit code", code, 2)
    t.ok("and the reason in the player's log", "its format isn't unity-probe-play/1" in said, said[-300:])


def missing_scene(t, play):
    """A scene that isn't in the build: an error, and the game's first scene is played."""
    t.eq("scene", play.probe.get("scene"), MADE + "First.unity")


def keeper(t, play):
    """An object the game's first scene marks DontDestroyOnLoad in Awake is there in the play's scene."""
    t.eq("the keeper", [r.get("name") for r in play.rows("kept", 0.5)], ["CoreKeeper"])
    t.eq("scene", play.probe.get("scene"), MADE + "Clock.unity")


def shutdown(t, play):
    """The game quits by itself after 1 s: probe.json holds everything up to then."""
    t.near("seconds", play.probe.get("seconds"), 1.0, 1 / 30 + 1e-9)
    t.eq("the samples up to then", times(play), [round(1 / 30, 6), 0.5, 1.0])
    t.eq("the one screenshot that was due", play.probe.get("screenshots"), ["shot_00.png"])
    t.ok("and its file", "shot_00.png" in play.files)


def refuse(t, play):
    """A game that refuses to quit (Application.wantsToQuit) still ends: the play is complete and the process goes."""
    t.near("seconds", play.probe.get("seconds"), 1.5, 1e-9)
    t.ok("probe.log says the play ended", "the play ended: time" in play.probe_log)


def load_sync(t, play):
    """The game loads another scene in mid-play: the probe goes on in it, the player and the camera found anew."""
    t.eq("no sample is lost or late", times(play), [round(x, 6) for x in HALF_SECONDS])
    t.near("before: the Clock's hero", play.track(1.0)[1], 1.0, FLOAT)
    t.eq("after: the Stage's hero", play.track(1.5)[1:], [0.0, 0.0, 0.0])
    t.eq("and the Stage's follow camera", play.camera(1.5)[1:4], [0.0, 3.0, -6.0])
    t.eq("scene at the end", play.probe.get("scene"), MADE + "Stage.unity")


def load_async(t, play):
    """An additive load in the background: the clock holds while it loads, so the game is ahead of the clock by
    the frames the load took and no sample is lost."""
    t.eq("no sample is lost or late", times(play), [round(x, 6) for x in HALF_SECONDS])
    ahead = play.track(3.5)[1] - 3.5
    t.ok("the game ran no less than the clock, and at most a few seconds more", -FLOAT <= ahead <= 5.0, ahead)
    t.eq("scene at the end", play.probe.get("scene"), MADE + "Clock.unity")


def load_parked(t, play):
    """A load the game parks (allowSceneActivation false) never finishes: the clock holds for ten seconds of frames,
    says so, and goes on; the play ends."""
    t.eq("no sample is lost", times(play), [round(x, 6) for x in HALF_SECONDS])
    ahead = play.track(3.5)[1] - 3.5
    t.near("the game is ahead of the clock by the 300 frames it held", ahead, 10.0, 0.05)
    t.ok("probe.log says the clock goes on", "has been loading for 300 frames" in play.probe_log, play.probe_log[-400:])


def _saves(log):
    found = re.search(r"CORE saves prefs=(\w+) file=(\w+) company=(\S+) path=(.+)", log)
    return found.groups() if found else (None, None, None, None)


def saves_a(t, play):
    """The game writes PlayerPrefs and a file. Its saved data is the build's own (company TaskProbe.<hash>). The same
    player started without -taskProbe is left alone: no probe, no device, nothing wiped."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
    from task_check import seeds

    prefs, file, company, path = _saves(play.log)
    t.eq("it started without saved data", (prefs, file), ("False", "False"))
    t.eq("the company name is the one the checker deletes saved data by", company, seeds.saves_company(t.project))
    t.ok("the saved-data folder is that company's under LocalLow",
         re.search(r"[/\\]LocalLow[/\\]" + re.escape(company.replace(".", "_")) + r"[/\\][^/\\]+$", path.strip()) is not None, path)
    t.ok("it wrote its saves", "CORE wrote saves" in play.log)

    code, said = _start(t, "noflag", "-coreselftest")
    line = next((x for x in said.splitlines() if x.startswith("CORE selftest")), "")
    t.eq("without -taskProbe: the player's exit code", code, 0)
    t.eq("without -taskProbe: no probe object, no fixed frame rate, no virtual device, the saves still there", line,
         "CORE selftest probe=False capture=0 devices=0 prefs=True file=True")


def saves_b(t, play):
    """The next play starts from clean saved data. And only the checker's own build does that."""
    prefs, file, _, _ = _saves(play.log)
    t.eq("the saves of the play before are gone", (prefs, file), ("False", "False"))
    _foreign(t)


FOREIGN = "ProbeTestsForeignCo"  # the company name CoreScenes.Foreign builds the second player with


def _forget_foreign():
    """What the foreign player saved: its registry key and its folder, by their exact names."""
    import shutil
    import winreg

    def drop(root, name):
        try:
            with winreg.OpenKey(root, name, 0, winreg.KEY_ALL_ACCESS) as key:
                while True:
                    try:
                        drop(key, winreg.EnumKey(key, 0))
                    except OSError:
                        break
            winreg.DeleteKey(root, name)
        except OSError:
            pass

    drop(winreg.HKEY_CURRENT_USER, "Software\\" + FOREIGN)
    shutil.rmtree(Path.home() / "AppData" / "LocalLow" / FOREIGN, ignore_errors=True)


def _foreign(t):
    """The wipe of saved data can only happen in the checker's own build. The same scene built with a company name
    of its own (as a real project builds, with the probe's package in it) and started with -taskProbe: the play
    runs, and what the game saved is still there at the next play."""
    import json

    out = t.project / "Logs" / "ProbeTests" / "core.foreign"
    spec = t.project / "Logs" / "ProbeTests" / "core.foreign_spec.json"
    spec.write_text(json.dumps({"format": "unity-probe-play/1", "out": out.as_posix(), "seconds": 1, "shots": 0, "every": 0.5,
                                "scene": MADE + "Clock.unity", "sound": False, "player": None, "inputs": [],
                                "queries": {"format": "game-probe-queries/1", "every": 0.5, "queries": []}}), encoding="utf-8")
    _forget_foreign()
    try:
        code, said = _start(t, "foreign_a", "-taskProbe", str(spec), "-coresave", build="ProbeTestsForeign")
        prefs, file, company, _ = _saves(said)
        t.eq("another build of the project, started with -taskProbe: exit code", code, 0)
        t.eq("another build of the project: its company name is its own", company, FOREIGN)
        t.ok("it wrote its saves", "CORE wrote saves" in said)
        log = (out / "probe.log").read_text(encoding="utf-8", errors="replace") if (out / "probe.log").is_file() else ""
        t.ok("probe.log says the saved data is kept", "the saved data is kept" in log, log[:300])
        code, said = _start(t, "foreign_b", "-taskProbe", str(spec), build="ProbeTestsForeign")
        prefs, file, _, _ = _saves(said)
        t.eq("the second play: exit code", code, 0)
        t.eq("the second play finds what the first saved", (prefs, file), ("True", "True"))
        t.ok("and it played to its end", (out / "probe.json").is_file() and json.loads((out / "probe.json").read_text(encoding="utf-8")).get("ended") == "time")
    finally:
        _forget_foreign()


def errors(t, play):
    """Queries the probe can't use each give one error and never stop the play; an unknown kind samples null values;
    at most 256 queries."""
    measures = play.probe.get("measures") or {}
    t.eq("256 queries are kept", len(measures), 256)
    t.eq("the unknown kind samples null values", [s.get("value", "no key") for s in play.samples("bogus")], [None, None, None, None])
    t.ok("the first of two queries of one id is sampled", len(play.samples("twice")) == 4 and all("value" in s for s in play.samples("twice")),
         play.samples("twice")[:1])
    t.ok("c253 is the last one kept", "c253" in measures and "c254" not in measures)


def settings(t, play):
    """A game that sets vertical sync, a target frame rate and a capture frame rate of its own in Start: the probe
    sets its own again before every frame's scripts."""
    row = play.row("director", 2.0, "Director")
    t.eq("vertical sync, as the game's Update finds it", row.get("prop:CoreDirector.vsync"), 0)
    t.eq("the capture frame rate, as the game's Update finds it", row.get("prop:CoreDirector.capture"), 30)
    t.near("the play's clock is still the game's (but for the one frame the game's 60 was in force)", play.track(2.0)[1], 2.0, 1 / 60 + FLOAT)


def wipe(t, play):
    """A game that destroys every object it finds (but its hero and camera) after 1 s doesn't find the probe: the play
    goes on to its end."""
    t.ok("the game's search didn't find the probe", "CORE wipe found the probe=False" in play.log)
    t.eq("every sample is there", times(play), [round(x, 6) for x in (1 / 30, 0.5, 1.0, 1.5, 2.0, 2.5)])


def who(name, place):
    def check(t, play):
        t.eq("player", play.probe.get("player"), name)
        t.eq("its place in the track", play.track(0.5)[1:], place)
    return check


def who_none(t, play):
    """No player and no camera: the track holds times only, there are no camera rows, and the play goes on."""
    t.eq("player", play.probe.get("player"), None)
    t.eq("the track rows", play.probe.get("track"), [[1 / 30], [0.5], [1.0], [1.5]])
    t.eq("the camera rows", play.probe.get("camera"), [])


def cam_main(t, play):
    """The main camera's row: its place, pitch and yaw in (-180, 180], vertical field of view."""
    row = play.camera(0.5)
    t.eq("place", row[1:4], [5.0, 2.0, -8.0])
    t.near("pitch", row[4], 10.0, 1e-3)
    t.near("yaw 200 reads -160", row[5], -160.0, 1e-3)
    t.near("fov", row[6], 60.0, FLOAT)
    who("Tagged", [1.0, 0.0, 0.0])(t, play)


def cam_ortho(t, play):
    """An orthographic camera has field of view 0."""
    t.eq("fov", play.camera(0.5)[6], 0)


def cam_high(t, play):
    """Without a main camera: the enabled screen camera of highest depth."""
    t.eq("place", play.camera(0.5)[1:4], [0.0, 9.0, 0.0])


PLAYS = {
    "clock": {"check": clock},
    # this play reads the wall clock on purpose
    "clocks": {"check": clocks, "varies": ["clocks"]},
    "fine": {"check": fine, "args": ["-corelast"]},
    "inputs": {"check": inputs, "errors": [r"^inputs: the keyboard has no key nokey$", r"^inputs: the mouse has no control position/x$"]},
    "pad": {"check": pad, "errors": [r"^inputs: the gamepad has no control a$"]},
    "teleport": {"check": teleport},
    "hold": {"check": hold, "args": ["-coredrift"]},
    "body_cc": {"check": body(0)},
    "body_rb": {"check": body(10)},
    "body_2d": {"check": body(20, yaw=False)},
    # a wait lasts its seconds of real time: how many frames the game runs in it differs from play to play
    "hold_wait": {"check": hold_wait, "args": ["-coredrift"], "varies": True},
    "wait": {"check": wait, "varies": True},
    "shots": {"check": shots},
    "first": {"check": first},
    "missing_scene": {"check": missing_scene, "errors": [r"^the play's scene Assets/ProbeTests/core/Made/NoSuch\.unity isn't in the build"]},
    "keeper": {"check": keeper, "args": ["-corekeeper"]},
    "shutdown": {"check": shutdown, "args": ["-corequit"], "ended": "shutdown"},
    "refuse": {"check": refuse, "args": ["-corerefuse"]},
    "load_sync": {"check": load_sync, "args": ["-coreload", "sync"]},
    # a load takes real time: how many frames the clock holds differs from play to play
    "load_async": {"check": load_async, "args": ["-coreload", "async"], "varies": True},
    "load_parked": {"check": load_parked, "args": ["-coreload", "parked"]},
    "saves_a": {"check": saves_a, "args": ["-coresave"]},
    "saves_b": {"check": saves_b},
    "errors": {"check": errors, "errors": [
        r"^query 'bogus': unknown kind 'nonsense' \(null values\)$", r"^a query has a missing or repeated id 'twice'$",
        r"^a query has a missing or repeated id ''$", r"^a query is not an object$",
        r"^more than 256 queries: 'c254' and later ones dropped$"]},
    "who_tag": {"check": cam_main},
    "who_input": {"check": who("Inputter", [3.0, 0.0, 0.0]), "args": ["-corewho", "input"]},
    "who_controller": {"check": who("Body", [4.0, 0.0, 0.0]), "args": ["-corewho", "controller"]},
    "who_camera": {"check": who("Rig", [5.0, 0.0, 0.0]), "args": ["-corewho", "camera"]},
    "who_none": {"check": who_none, "args": ["-corewho", "none"]},
    "who_select": {"check": who("Body", [4.0, 0.0, 0.0])},
    "cam_ortho": {"check": cam_ortho, "args": ["-corecam", "ortho"]},
    "cam_high": {"check": cam_high, "args": ["-corecam", "high"]},
    "settings": {"check": settings, "args": ["-coresettings"]},
    "wipe": {"check": wipe, "args": ["-corewipe"]},
}
