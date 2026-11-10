"""The core family: the play loop itself (the clock, the track and the camera rows, screenshots, the end)."""

SETUP = ["ProbeTests.Core.CoreScenes.Build"]
SCENES = ["Assets/ProbeTests/core/Made/Clock.unity"]


def clock(t, play):
    """The play's clock is the game's: an object moving 1 m/s is t metres along at play time t."""
    probe = play.probe
    t.eq("format", probe.get("format"), "unity-probe/1")
    t.eq("scene", probe.get("scene"), "Assets/ProbeTests/core/Made/Clock.unity")
    t.eq("player", probe.get("player"), "Hero")
    t.near("seconds", probe.get("seconds"), 3.5, 0.2)
    t.eq("the samples' times: the first frame, then every 0.5 s", [row[0] for row in probe["track"]],
         [1 / 30, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5])
    for row in probe["track"]:
        t.near(f"the hero's x at {row[0]:.3f} s", row[1], row[0], 1e-4)
    t.eq("the camera row at 2 s", play.camera(2.0)[1:], [0.0, 2.0, -8.0, 0.0, 0.0, 60.0])
    t.eq("screenshots", probe.get("screenshots"), ["shot_00.png", "shot_01.png"])
    shot = play.image("shot_00.png")
    t.eq("a screenshot's size", (shot.width, shot.height), (960, 540))
    t.ok("the frame has light in it", (play.value("frame", 2.0) or {}).get("luminance", 0) > 0.01, play.value("frame", 2.0))


PLAYS = {
    "clock": {"check": clock},
}
