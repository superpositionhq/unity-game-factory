"""The contact family: the stages of a contact (pin, damage, set) and every input that didn't land, a select's `where`
and "player": false, an object's `damage_taken` and `frozen`, and the `world` measure."""

MADE = "Assets/ProbeTests/contact/Made/"
SETUP = ["ProbeTests.Contact.ContactScenes.Build"]
SCENES = [MADE + "Duel.unity", MADE + "Stops.unity", MADE + "Bodies.unity", MADE + "Flat.unity"]
FLOAT = 1e-5  # a float of the game widened to a double
FRAME = 1 / 30


def foe(play, t, name, field):
    return (play.row("foes", t, name) or {}).get(field)


def count(play, qid, t):
    sample = play.sample(qid, t) or {}
    return sample.get("total", len(sample.get("rows") or []))


def stage(t, play):
    """A fight set up and struck at times the play knows: properties written, a foe pinned ahead of the player and at a
    point while it walks on, damage through the game's own TakeDamage with what it returned, selects that take the
    live ones and leave the player out, and every stage nothing took listed as a miss."""
    # set, at 0.2 s
    t.eq("set on the nearest match of a where: the nearer foe is dead, the live one is written", foe(play, 0.5, "FoeNear", "prop:ContactFoe.health"), 1.0)
    t.eq("the dead one is left", foe(play, 0.5, "FoeDead", "prop:ContactFoe.health"), 10.0)
    t.eq("and the one further off", foe(play, 0.5, "FoeFar", "prop:ContactFoe.health"), 10.0)
    t.eq("set with all: every match", [foe(play, 0.5, n, "prop:ContactFoe.label") for n in ("FoeNear", "FoeFar", "FoeDead")], ["marked"] * 3)
    t.eq("an enum by its name", foe(play, 0.5, "FoeFar", "prop:ContactFoe.state"), 2.0)
    t.eq("a property with a private setter", foe(play, 0.5, "FoeFar", "prop:ContactFoe.Armor"), 4.0)
    # where and "player": false
    t.eq("where: the foes not dead", count(play, "live", 0.5), 2)
    t.eq("where on text: the marked ones", count(play, "marked", 0.5), 3)
    t.eq("two conditions: both hold (health 5 or more, a label)", count(play, "hale", 0.5), 2)
    t.eq("everything with an IDamageable, whichever namespace declares it", count(play, "hurt", 0.5), 6)
    t.eq("player false: but the player", count(play, "others", 0.5), 5)
    t.eq("a setter with bounds takes a value inside them", foe(play, 0.5, "FoeFar", "prop:ContactFoe.Morale"), 4.0)
    # pin, at 1 s for 2 s, 1.5 m ahead of the player
    t.near("before the pin it walks", foe(play, 0.5, "FoeNear", "x"), 0.5, FRAME + FLOAT)
    for at in (1.5, 2.0, 2.5):
        row = play.row("foes", at, "FoeNear") or {}
        t.eq(f"pinned at {at} s: 1.5 m ahead of the player, at its height above the ground", [row.get(k) for k in "xyz"], [0.0, 0.5, 1.5])
        t.near(f"facing the player at {at} s", abs(row.get("yaw") or 0.0), 180.0, 1e-3)
    t.near("released at 3 s it walks on from there", foe(play, 3.5, "FoeNear", "x"), 0.5, FRAME + FLOAT)
    t.eq("where it was set", foe(play, 3.5, "FoeNear", "z"), 1.5)
    t.ok("the pin is in probe.log", "pinned FoeNear at (0.00, 0.50, 1.50) for 2.0 s" in play.probe_log)
    # damage, at 1.2 s
    t.eq("5 damage to a foe of health 1: it took 1", foe(play, 1.5, "FoeNear", "damage_taken"), 1.0)
    t.eq("through its own TakeDamage: its health", foe(play, 1.5, "FoeNear", "prop:ContactFoe.health"), 0.0)
    t.eq("and its death", foe(play, 1.5, "FoeNear", "prop:ContactFoe.dead"), 1.0)
    t.eq("struck from the player", foe(play, 1.5, "FoeNear", "prop:ContactFoe.lastSource"), "Hero")
    t.eq("where follows the game: one foe is left alive", count(play, "live", 1.5), 1)
    hero = (play.rows("hero", 1.5) or [{}])[0]
    t.eq("the player struck: what it took", hero.get("damage_taken"), 3.0)
    t.eq("its health", hero.get("prop:ContactHero.health"), 97.0)
    t.eq("from the nearest other object that takes damage", hero.get("prop:ContactHero.lastSource"), "FoeNear")
    t.eq("an object no stage struck has no damage_taken, not 0", foe(play, 1.0, "FoeFar", "damage_taken"), None)
    armored = play.row("armored", 3.5, "Armored") or {}
    t.eq("an entry with optional parameters after the two: called with their defaults", [armored.get("damage_taken"),
         armored.get("prop:ContactArmored.kind"), armored.get("prop:ContactArmored.combo"), armored.get("prop:ContactArmored.health")],
         [3.0, "blunt", 2.0, 7.0])
    # at 2.2 s: damage to the nearest live foe from the crate; that foe pinned at a point
    t.eq("damage to the nearest match of a where", foe(play, 2.5, "FoeFar", "damage_taken"), 2.0)
    t.eq("from what `from` selects", foe(play, 2.5, "FoeFar", "prop:ContactFoe.lastSource"), "Crate")
    t.eq("the fallen foe took no more", foe(play, 2.5, "FoeNear", "damage_taken"), 1.0)
    t.eq("pinned at a point, plus the offset", [foe(play, 2.5, "FoeFar", k) for k in "xyz"], [-3.0, 0.5, 2.0])
    t.near("released after its 0.5 s", foe(play, 3.0, "FoeFar", "x"), -2.7, 2 * FRAME + FLOAT)
    # what didn't land, from 4 s
    missed = play.probe.get("inputs_missed") or []
    t.eq("every stage nothing took is listed, in the order sent",
         [(m.get("t"), m.get("kind"), m.get("target")) for m in missed],
         [(4.0, "pin", "select"), (4.0, "pin", "at"), (4.1, "damage", "Crate"), (4.1, "damage", "to"),
          (4.2, "set", "ContactFoe.nothing"), (4.2, "set", "ContactFoe.Sealed"), (4.2, "set", "ContactFoe.born"),
          (4.3, "set", "ContactFoe.health"), (4.3, "set", "ContactFoe.gauge.level"), (4.3, "set", "ContactFoe.health"),
          (4.4, "set", "ContactFoe.health"), (4.5, "damage", "Odd"), (4.6, "set", "ContactFoe.Morale")])
    why = [m.get("why") or "" for m in missed]
    t.ok("an object without the damage entry", len(why) > 2 and "no component implementing IDamageable" in why[2], why)
    t.ok("no such member", len(why) > 4 and "no property nothing" in why[4], why)
    t.ok("a property without a setter", len(why) > 5 and "can't be written" in why[5], why)
    t.ok("a readonly field", len(why) > 6 and "can't be written" in why[6], why)
    t.ok("text for a number", len(why) > 7 and "it takes no text" in why[7], why)
    t.ok("a member of a struct", len(why) > 8 and "member of a struct" in why[8], why)
    t.ok("with all: how many didn't take it", len(why) > 10 and why[10].startswith("3 of 3 objects didn't take it"), why)
    t.ok("an IDamageable that isn't the contract's: a miss, never a call", len(why) > 11 and "has no TakeDamage(float, GameObject)" in why[11], why)
    t.eq("... it was not called", (play.row("odd", 5.0, "Odd") or {}).get("prop:ContactOdd.hits"), 0.0)
    t.ok("a setter that clamps the value didn't take it: read back", len(why) > 12 and "didn't take the value: it reads 5" in why[12], why)
    t.eq("a miss changes nothing", foe(play, 5.0, "FoeFar", "prop:ContactFoe.health"), 8.0)
    t.eq("the crate took none: no value", (play.row("crate", 5.0, "Crate") or {}).get("damage_taken"), None)


def stops(t, play):
    """A stop shorter than the 0.5 s between two samples is read: the object's own (six frames still between frames of
    motion), the game's time slowed for three frames, and stopped for two. What a hit dresses the object with during
    its stop is none of its motion: a child made and destroyed, one made that keeps moving, a part of it destroyed."""
    frozen = dict(play.series("stutter", "frozen", "Stutter"))
    times = sorted(frozen)
    t.eq("frozen has no value the first sample it is seen in", frozen[times[0]], None)
    t.eq("moving: no stop", [frozen[at] for at in times if 0.4 < at < 1.9], [0.0, 0.0, 0.0])
    t.near("its six still frames, told in the sample after them", max(frozen[at] for at in times if 1.9 < at < 2.8), 6 * FRAME, FLOAT)
    t.eq("told once", sum(1 for at in times if 1.9 < at < 2.8 and frozen[at] > 0), 1)
    scale = dict(play.series("time", "time_scale"))
    paused = dict(play.series("time", "paused"))
    t.eq("the game's time at its pace", [scale[at] for at in times if at < 3.1], [1.0] * len([at for at in times if at < 3.1]))
    t.near("slowed to a quarter for three frames: the lowest since the previous sample", min(scale[at] for at in times if 3.1 < at < 4.1), 0.25, FLOAT)
    t.eq("slowed is not paused", max(paused[at] for at in times if at < 4.1), 0.0)
    t.eq("stopped for two frames", min(scale[at] for at in times if 4.1 < at < 5.1), 0.0)
    t.eq("paused", max(paused[at] for at in times if 4.1 < at < 5.1), 1.0)
    t.eq("and on again", (scale[times[-1]], paused[times[-1]]), (1.0, 0.0))
    t.near("the game's stop stopped the object too: two frames", max(frozen[at] for at in times if 4.1 < at < 5.1), 2 * FRAME, FLOAT)
    pose = dict(play.series("skinned", "frozen", "Skinned"))
    t.near("a skinned thing that stands where it is: the six frames its bone held still", max(pose[at] for at in times if 1.9 < at < 2.8), 6 * FRAME, FLOAT)
    t.eq("its bone moves on through the game's stop: no stop of its own there", max(pose[at] for at in times if 4.1 < at < 5.1), 0.0)


def stop_real(t, play):
    """A hit stop timed as games time one, 0.1 s on the real-time clock with the game's time at 0: the play is paced to
    real time (it reads `world` and `frozen`), so the stop lasts about 0.1 s of play, three or four frames, and reads
    as a short stop. Unpaced it would last as many frames as the machine renders in 0.1 s, past the 0.5 s a stop may
    last."""
    scale = dict(play.series("time", "time_scale"))
    frozen = dict(play.series("stutter", "frozen", "Stutter"))
    window = [at for at in sorted(scale) if 4.0 < at <= 5.0 + 1e-6]
    t.eq("the game's time stood still", min(scale[at] for at in window), 0.0)
    held = max(frozen[at] or 0.0 for at in window)
    t.ok("the object's stop is read at about its real length: 2 to 8 frames", 2 * FRAME - FLOAT <= held <= 8 * FRAME + FLOAT, held)
    t.ok("the play ran at the pace of a clock: 6.5 s of play in at least 6 s", play.seconds >= 6.0, play.seconds)


def bodies(t, play):
    """A pin holds an object through the body that moves it: a cube under gravity hangs in the air, an agent stays
    where it was set while its path pulls it. A damage entry that throws is a miss; one that returns no number is
    called and leaves no damage_taken; a source no object matches is a miss; a whole-number member takes no fraction;
    and a stage's miss is listed past the 400th row."""
    def at(qid, when, name):
        row = play.row(qid, when, name) or {}
        return [row.get(k) for k in "xyz"]
    for when in (1.5, 2.0):
        t.eq(f"the cube hangs where it was pinned at {when} s", at("body", when, "Body"), [3.0, 3.0, 5.0])
    t.ok("released, it falls to the ground", (at("body", 4.0, "Body")[1] or 9) < 0.6, at("body", 4.0, "Body"))
    before = at("agent", 0.5, "Agent")
    t.ok("the agent walks its NavMesh before the pin", before[2] is not None and before[2] > 5.2, before)
    for when in (1.5, 2.0):
        x, y, z = at("agent", when, "Agent")
        t.ok(f"the agent stays 4 m ahead of the player at {when} s, at its height above the ground",
             None not in (x, y, z) and abs(x) < 0.02 and abs(z - 4.0) < 0.02 and abs(y - before[1]) < 0.02, (x, y, z))
    t.ok("released, it walks on", (at("agent", 4.0, "Agent")[2] or 0) > 5.0, at("agent", 4.0, "Agent"))
    missed = play.probe.get("inputs_missed") or []
    stages = [(m.get("t"), m.get("kind"), m.get("target")) for m in missed if m.get("kind") != "click"]
    t.eq("the stages that missed", stages, [(2.6, "damage", "Thrower"), (2.8, "damage", "from"), (2.9, "set", "ContactMute.hits"), (4.2, "pin", "select")])
    why = {m.get("target"): m.get("why") or "" for m in missed}
    t.ok("an entry that throws", "TakeDamage threw InvalidOperationException" in why.get("Thrower", ""), why.get("Thrower"))
    t.ok("a source no object matches", "no object matches it" in why.get("from", ""), why.get("from"))
    t.ok("a fraction for a whole-number member", "it takes a whole number" in why.get("ContactMute.hits", ""), why.get("ContactMute.hits"))
    mute = play.row("mute", 4.0, "Mute") or {}
    t.eq("an entry that returns no number was called once, and leaves no damage_taken", [mute.get("prop:ContactMute.hits"), mute.get("damage_taken")], [1.0, None])
    t.eq("the list keeps 400 rows, and a stage's miss after them", [len(missed), missed[-1].get("kind") if missed else None], [401, "pin"])


def flat(t, play):
    """In a 2D game a pin's `front` is along the player's facing in X (here -x: its scale is -1), the object is never
    turned and keeps its depth; a second pin on the object takes the first's place."""
    def row(when):
        r = play.row("foe", when, "Foe2D") or {}
        return [r.get(k) for k in ("x", "y", "z", "yaw")]
    t.near("before the pin it walks", row(0.5)[0], 5.5, FRAME + FLOAT)
    for when in (1.5, 2.0):
        t.eq(f"pinned 2 m ahead of a player that faces -x, on the floor, at its depth, not turned ({when} s)", row(when), [-2.0, 0.5, 2.0, 0.0])
    t.eq("a second pin takes the first's place: held at the new spot while the first would still hold", row(2.5), [3.0, 0.5, 2.0, 0.0])
    t.near("released at 2.7 s it walks on from there", row(3.5)[0], 3.8, 2 * FRAME + FLOAT)


PLAYS = {
    "stage": {"check": stage},
    "stops": {"check": stops},
    # a stop timed on the real-time clock: how long it lasts in frames is the machine's
    "stop_real": {"check": stop_real, "args": ["-contactreal"], "varies": True},
    "bodies": {"check": bodies},
    "flat": {"check": flat},
}
