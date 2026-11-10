"""The objects family: what the objects and components kinds read of a scene (every field and select key; lit and glow
from every kind of source; the state kept from sample to sample; what the queries must leave as they found it), what
the camera, spawns, pieces and ground kinds read of the same scene, and what a whole-scene sample costs."""

import math
import re

MADE = "Assets/ProbeTests/objects/Made/"
SETUP = ["ProbeTests.Objects.ObjScenes.Build"]
SCENES = [MADE + "ObjLab.unity", MADE + "ObjMore.unity", MADE + "ObjBudget.unity", MADE + "ObjStress.unity"]

FLOAT = 1e-5  # a float of the game widened to a double
RENDER = 0.02  # as rendered: 128 x 128 pixels a view, so a silhouette's edge pixels move the area by up to 2 %
STEP = 0.02  # s: a physics step (Unity's default fixed timestep)
G = 9.81  # m/s2


def steps(t):
    """Physics steps run by play time t: the first frame (1/30 s) runs two, then 25 every 0.5 s (measured: a body
    falling from rest reads 2 g dt at the first sample and 26 g dt at 0.5 s)."""
    return 2 if t < 0.1 else round(t / STEP) + 1


def fallen(t):
    """How far a body falls from rest by play time t, by semi-implicit Euler steps of STEP."""
    n = steps(t)
    return G * STEP ** 2 * n * (n + 1) / 2


def linear(v):
    """One colour channel as a linear-space project gives it to the shaders (Mathf.GammaToLinearSpace: the sRGB curve
    up to 1, v^2.2 above, for HDR values)."""
    if v <= 0.04045:
        return v / 12.92
    if v < 1.0:
        return ((v + 0.055) / 1.055) ** 2.4
    return v ** 2.2


def lum(r, g, b):
    """Rec. 709 luminance of a colour picked in gamma space, as the shader gets it (linear): a plain colour property's,
    and a colour set on a MaterialPropertyBlock."""
    return 0.2126 * linear(r) + 0.7152 * linear(g) + 0.0722 * linear(b)


def hdr(r, g, b):
    """Rec. 709 luminance of a colour property the shader marks [HDR] (URP Lit's _EmissionColor): Unity hands it to the
    shader as the material holds it (measured: (4, 4, 4) renders 4, not 4^2.2)."""
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def quarter(x, y, z):
    """A quarter of the surface of an x * y * z box (m2)."""
    return (x * y + y * z + z * x) / 2.0


CUBE = quarter(1, 1, 1)
TURNED6 = 1.5 * math.cos(math.radians(6)) + 0.15 * math.sin(math.radians(6))  # the blade's x half-size turned 6 degrees
EMISSIVE = hdr(4, 3, 2)  # LampEmissive's, the bulbs', TubeLit's URP Lit emission
HDR4 = hdr(4, 4, 4)  # LampKeyword's and the atlas's URP Lit emission
BLOCK4 = lum(4, 4, 4)  # (4, 4, 4) set on a property block with SetColor (LampSwitch, LampLate, LampTwoMat, BlockColour)
CUSTOM = lum(3, 2, 1)  # ProbeTests/ObjGlow's _Glow, a plain colour property


def rel(want, tol):
    return abs(want) * tol


def near_rel(t, what, got, want, tol):
    t.near(what, got, want, rel(want, tol))


def field(play, qid, t, name, key):
    row = play.row(qid, t, name)
    return None if row is None else row.get(key)


def names(play, qid, t):
    return [r.get("name") for r in play.rows(qid, t)]


def sorted_names(play, qid, t):
    """The rows' names, sorted: roots come in their scene's root list order, which in a player isn't the order the
    editor made them in (measured: Enemy_1 is root 14, Enemy_0 root 16)."""
    return sorted(names(play, qid, t))


def follows(found, parent, children):
    """Whether `children` come right after `parent` in `found`, in that order (hierarchy order below a root)."""
    if parent not in found:
        return False
    at = found.index(parent)
    return found[at + 1:at + 1 + len(children)] == list(children)


def keys(play, qid, t, name):
    row = play.row(qid, t, name) or {}
    return list(row.keys())


def real_seconds(play):
    """Real seconds between the play's clock starting and the play ending, from probe.log ("<t> [<real> s] ...")."""
    start = re.search(r"\[(\d+\.\d) s\] the play's clock starts", play.probe_log)
    end = re.search(r"\[(\d+\.\d) s\] the play ended", play.probe_log)
    return float(end.group(1)) - float(start.group(1)) if start and end else None


# ---------------------------------------------------------------------------------------------------------------- lab


def hero(t, play):
    q = "o_hero"
    for s in play.samples(q):
        row = (s.get("rows") or [{}])[0]
        if not (row.get("count") == 1 and abs(row.get("scale", 0) - 1) < FLOAT and row.get("active") == 1 and row.get("hidden") == 0
                and row.get("collision") == 1 and row.get("simulating") == 0):
            t.ok("the hero is one active, unhidden, colliding, unsimulated object of scale 1 at every sample", False, (s["t"], row))
            break
    else:
        t.ok("the hero is one active, unhidden, colliding, unsimulated object of scale 1 at every sample", True)
    t.ok("rel_yaw:Visor is 30 throughout (turning the whole object doesn't change it)",
         all(abs(v - 30) < 1e-3 for _, v in play.series(q, "rel_yaw:Visor", "Hero")), play.series(q, "rel_yaw:Visor", "Hero")[:3])
    t.near("world_yaw:Visor at 0.5 s (the visor's own 30)", field(play, q, 0.5, "Hero", "world_yaw:Visor"), 30, 1e-3)
    t.near("world_yaw:Visor at 7 s (turned to +x: 90 + 30)", field(play, q, 7.0, "Hero", "world_yaw:Visor"), 120, 1e-3)
    t.near("world_yaw:Visor at 16 s (turned to -x: -90 + 30)", field(play, q, 16.0, "Hero", "world_yaw:Visor"), -60, 1e-3)
    t.near("world_pitch:Visor", field(play, q, 0.5, "Hero", "world_pitch:Visor"), 0, 1e-3)
    t.near("world_roll:Visor", field(play, q, 7.0, "Hero", "world_roll:Visor"), 0, 1e-3)
    t.near("forward:Visor.x at 0.5 s (sin 30)", field(play, q, 0.5, "Hero", "forward:Visor.x"), 0.5, 1e-4)
    t.near("forward:Visor.z at 0.5 s (cos 30)", field(play, q, 0.5, "Hero", "forward:Visor.z"), math.cos(math.radians(30)), 1e-4)
    t.near("W held 1 to 2 s at 4 m/s, seen a frame late: z at 2 s", field(play, q, 2.0, "Hero", "z"), 4.0, 1e-3)
    t.near("speed while walking: the CharacterController's velocity", field(play, q, 2.0, "Hero", "speed"), 4.0, 1e-3)
    t.near("facing_vs_velocity while walking forward", field(play, q, 2.0, "Hero", "facing_vs_velocity"), 0.0, 1e-3)
    t.near("blocked by LampSwitch: z at 4 s (its face at 9.5, the capsule's radius 0.5, skin 0.08)",
           field(play, q, 4.0, "Hero", "z"), 8.92, 0.005)
    t.eq("speed while blocked", field(play, q, 4.0, "Hero", "speed"), 0.0)
    t.eq("facing_vs_velocity has no value while it stands", field(play, q, 4.0, "Hero", "facing_vs_velocity"), None)
    t.near("D held 6 to 7 s: x at 7 s", field(play, q, 7.0, "Hero", "x"), 4.0, 1e-3)
    t.near("yaw facing +x", field(play, q, 7.0, "Hero", "yaw"), 90, 1e-3)
    t.near("yaw facing -x at 16 s", field(play, q, 16.0, "Hero", "yaw"), -90, 1e-3)
    t.near("pitch and roll stay 0", abs(field(play, q, 7.0, "Hero", "pitch")) + abs(field(play, q, 7.0, "Hero", "roll")), 0, 1e-3)
    t.near("the jump seen at 9.03 s: up (75 - 120 g / 30) / 30 m over the 15 frames to 9.5 s (vy 5, g 9.81)",
           field(play, q, 9.5, "Hero", "y") - field(play, q, 9.0, "Hero", "y"), (75 - 120 * G / 30) / 30, 1e-3)
    t.ok("facing_vs_velocity at 10 s: falling while walking, between 0 and 90",
         0 < (field(play, q, 10.0, "Hero", "facing_vs_velocity") or 0) < 90, field(play, q, 10.0, "Hero", "facing_vs_velocity"))
    t.eq("spin has no value on the first sample (no body to read)", field(play, q, 1 / 30, "Hero", "spin"), None)
    t.near("spin over the sample that turned it 90 degrees (6.5 s)", field(play, q, 6.5, "Hero", "spin"), 180, 0.01)
    t.near("spin over a sample without a turn (7 s)", field(play, q, 7.0, "Hero", "spin"), 0, 0.01)
    t.near("spin over the turn back to +z (8.5 s)", field(play, q, 8.5, "Hero", "spin"), 180, 0.01)
    t.near("spin over the turn to -x (13.5 s)", field(play, q, 13.5, "Hero", "spin"), 180, 0.01)
    t.near("extent_x facing +z: the capsule's half-width", field(play, q, 2.0, "Hero", "extent_x"), 0.5, 1e-3)
    t.near("extent_y: the capsule's half-height (the visor inside it)", field(play, q, 2.0, "Hero", "extent_y"), 1.0, 1e-3)
    t.near("extent_x facing +x: the capsule's 0.5 and the visor 0.5 out, turned 120 (0.3 |cos| + 0.1 |sin|)",
           field(play, q, 7.0, "Hero", "extent_x"), (1 + 0.3 * 0.5 + 0.1 * math.sin(math.radians(120))) / 2, 1e-4)


def physics(t, play):
    q = "o_phys"
    t.eq("Rigidbody selects the crate and the lift", sorted_names(play, q, 0.5), ["Crate", "Lift"])
    for at in (1 / 30, 0.5, 1.0):
        t.near(f"the crate's y at {at:.2f} s (falling from 8 m, by physics steps)", field(play, q, at, "Crate", "y"), 8 - fallen(at), 1e-3)
        t.near(f"its speed at {at:.2f} s: its body's velocity", field(play, q, at, "Crate", "speed"), G * STEP * steps(at), 1e-3)
    t.near("at rest on the floor at 12 s", field(play, q, 12.0, "Crate", "y"), 0.5, 0.01)
    t.near("at rest: speed 0 (a resting body's solver leaves no more than mm/s)", field(play, q, 12.0, "Crate", "speed"), 0.0, 1e-3)
    t.eq("spin on the first sample: its body's angular velocity, not no value", field(play, q, 1 / 30, "Crate", "spin"), 0.0)
    t.eq("the crate simulates", field(play, q, 1.0, "Crate", "simulating"), 1.0)
    t.eq("the kinematic lift doesn't", field(play, q, 1.0, "Lift", "simulating"), 0.0)
    t.near("the lift's speed: moved 2 m/s (no velocity of its own)", field(play, q, 1.0, "Lift", "speed"), 2.0, 2 * STEP / 0.5 * 2)
    t.eq("the crate changed (it fell)", field(play, q, 1.0, "Crate", "changed"), 1.0)
    first = field(play, q, 1 / 30, "Crate", "y")
    t.near("bounds_change at 1 s: how far its box fell since the first sample", field(play, q, 1.0, "Crate", "bounds_change"), first - field(play, q, 1.0, "Crate", "y"), 1e-4)
    t.near("bounds_change at rest", field(play, q, 12.0, "Crate", "bounds_change"), first - 0.5, 0.01)
    t.eq("the first sample is the reference: unchanged", field(play, q, 1 / 30, "Crate", "changed"), 0.0)
    t.eq("collision", field(play, q, 1.0, "Crate", "collision"), 1.0)

    q = "o_fan"
    t.near("the blade's spin, summed frame by frame", field(play, q, 1.0, "Fan", "spin"), 180, 0.01)
    t.near("still 180 at 5 s (a part turning 3 times in a sample would read the same)", field(play, q, 5.0, "Fan", "spin"), 180, 0.01)
    t.eq("spin has no value on the first sample", field(play, q, 1 / 30, "Fan", "spin"), None)
    t.near("extent_x at 0.5 s: the blade turned 90 degrees", field(play, q, 0.5, "Fan", "extent_x"), 0.15, 1e-3)
    t.near("extent_x at 1 s: turned 180", field(play, q, 1.0, "Fan", "extent_x"), 1.5, 1e-3)
    t.near("extent_z at 0.5 s", field(play, q, 0.5, "Fan", "extent_z"), 1.5, 1e-3)
    t.eq("spread: one part (the trail is no part)", field(play, q, 1.0, "Fan", "spread"), 0.0)
    t.eq("changed: its blade's box turned", field(play, q, 0.5, "Fan", "changed"), 1.0)
    t.near("bounds_change at 0.5 s: its x faces from 6 degrees (the first sample) to 90", field(play, q, 0.5, "Fan", "bounds_change"), TURNED6 - 0.15, 1e-4)
    t.eq("lit: the trail at the blade's tip, a live effect read as rendered", field(play, q, 1.0, "Fan", "lit"), 1.0)
    t.eq("its source is the effect", field(play, q, 1.0, "Fan", "glow_sources"), "effect")

    q = "c_blade"
    t.near("components spin", field(play, q, 1.0, "Blade", "spin"), 180, 0.01)
    t.eq("x of its transform", field(play, q, 1.0, "Blade", "x"), 5.0)
    t.eq("z", field(play, q, 1.0, "Blade", "z"), -5.0)
    t.eq("speed: turning in place", field(play, q, 1.0, "Blade", "speed"), 0.0)
    t.eq("speed has no value the first time it is seen (no velocity of its own)", field(play, q, 1 / 30, "Blade", "speed"), None)
    t.eq("changed", field(play, q, 0.5, "Blade", "changed"), 1.0)
    t.near("bounds_change", field(play, q, 0.5, "Blade", "bounds_change"), TURNED6 - 0.15, 1e-4)
    t.near("extent_x at 1 s", field(play, q, 1.0, "Blade", "extent_x"), 1.5, 1e-3)
    t.eq("visible", field(play, q, 1.0, "Blade", "visible"), 1.0)

    q = "c_rb"
    t.eq("Rigidbody components", sorted_names(play, q, 0.5), ["Crate", "Lift"])
    t.eq("simulating: the crate", field(play, q, 1.0, "Crate", "simulating"), 1.0)
    t.eq("simulating: the lift", field(play, q, 1.0, "Lift", "simulating"), 0.0)
    t.near("the lift's speed", field(play, q, 1.0, "Lift", "speed"), 2.0, 2 * STEP / 0.5 * 2)
    t.eq("extent_y has no value for a Rigidbody (neither a renderer nor a collider)", field(play, q, 1.0, "Crate", "extent_y"), None)
    t.eq("spin on the first sample: the crate's body", field(play, q, 1 / 30, "Crate", "spin"), 0.0)
    t.near("a BoxCollider's extent_y", field(play, "c_col", 1.0, "Crate", "extent_y"), 0.5, 1e-3)
    t.near("and its y", field(play, "c_col", 1.0, "Crate", "y"), field(play, "o_phys", 1.0, "Crate", "y"), FLOAT)


def gone(t, play):
    q = "o_gone"
    t.eq("Vanisher active, then deactivated at 3 s (inactive: true keeps it)", [field(play, q, x, "Vanisher", "active") for x in (2.5, 3.5)], [1.0, 0.0])
    t.eq("hidden", [field(play, q, x, "Vanisher", "hidden") for x in (2.5, 3.5)], [0.0, 1.0])
    t.eq("changed", [field(play, q, x, "Vanisher", "changed") for x in (2.5, 3.5)], [0.0, 1.0])
    t.eq("collision", [field(play, q, x, "Vanisher", "collision") for x in (2.5, 3.5)], [1.0, 0.0])
    t.near("extent_x while it is drawn", field(play, q, 2.5, "Vanisher", "extent_x"), 0.5, 1e-3)
    t.eq("extent_x has no value once it draws nothing", field(play, q, 3.5, "Vanisher", "extent_x"), None)
    t.near("bounds_change while it stands", field(play, q, 2.5, "Vanisher", "bounds_change"), 0.0, FLOAT)
    t.near("and once deactivated: a hidden part keeps its bounds (Unity keeps an inactive renderer's)", field(play, q, 3.5, "Vanisher", "bounds_change"), 0.0, FLOAT)
    q = "o_ghost"
    t.eq("Ghost: its renderer disabled at 3 s: hidden", [field(play, q, x, "Ghost", "hidden") for x in (2.5, 3.5)], [0.0, 1.0])
    t.eq("changed", [field(play, q, x, "Ghost", "changed") for x in (2.5, 3.5)], [0.0, 1.0])
    t.eq("active stays", [field(play, q, x, "Ghost", "active") for x in (2.5, 3.5)], [1.0, 1.0])
    t.eq("collision stays", [field(play, q, x, "Ghost", "collision") for x in (2.5, 3.5)], [1.0, 1.0])
    t.eq("extent_x has no value once it draws nothing", field(play, q, 3.5, "Ghost", "extent_x"), None)
    t.near("bounds_change with its renderer off: a hidden part keeps its bounds", field(play, q, 3.5, "Ghost", "bounds_change"), 0.0, FLOAT)
    t.near("a disabled Renderer's extent_x: its bounds still", field(play, "c_ghost", 3.5, "Ghost", "extent_x"), 0.5, FLOAT)
    t.eq("Renderer visible: Ghost, then not", [field(play, "c_ghost", x, "Ghost", "visible") for x in (2.5, 3.5)], [1.0, 0.0])
    t.eq("c_visible: the drawn renderers near Vanisher and Ghost, before and after 3 s",
         [len(play.rows("c_visible", x)) for x in (2.5, 3.5)], [2, 0])
    t.eq("a components select leaves out the components of an inactive object", [len(play.rows("c_vanisher", x)) for x in (2.5, 3.5)], [1, 0])
    t.eq("unless it says inactive: true (they read active 0)", [field(play, "c_vanisher_all", x, "Vanisher", "active") for x in (2.5, 3.5)], [1.0, 0.0])


def lamps(t, play):
    q = "o_lamps"
    order = ["LampLight", "LampEmissive", "LampUnlit", "LampMapped", "LampSwitch", "LampLater", "LampOff", "LampCustom", "Dark"]
    t.eq("tag ObjLamp: the nine lamps", sorted_names(play, q, 3.5), sorted(order))
    t.eq("layer ObjProps: the same nine, in the same order", names(play, "o_props", 3.5), names(play, q, 3.5))
    before, after = 3.5, 4.5
    t.eq("lit before 4 s", [field(play, q, before, n, "lit") for n in order], [1.0, 1.0, 1.0, 1.0, 0.0, 0.0, 1.0, 1.0, 0.0])
    t.eq("lit after 4 s (LampSwitch's block, LampLater on, LampOff at 0)", [field(play, q, after, n, "lit") for n in order],
         [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 0.0, 1.0, 0.0])
    t.near("LampLight: intensity 5 x white", field(play, q, before, "LampLight", "glow"), 5.0, FLOAT)
    near_rel(t, "LampEmissive: (4, 3, 2) as the material holds it (URP Lit's emission is [HDR]) x a quarter of a unit cube's surface",
             field(play, q, before, "LampEmissive", "glow"), EMISSIVE * CUBE, 1e-4)
    near_rel(t, "LampUnlit: (1, 0.9, 0.5) linear x a unit sphere's box", field(play, q, before, "LampUnlit", "glow"), lum(1, 0.9, 0.5) * CUBE, 1e-4)
    near_rel(t, "LampMapped: (2, 2, 2) on half of each face, as rendered", field(play, q, before, "LampMapped", "glow"), hdr(2, 2, 2) * 0.5 * CUBE, RENDER)
    t.eq("LampSwitch before its block: dark", field(play, q, before, "LampSwitch", "glow"), 0.0)
    near_rel(t, "LampSwitch after: the block's colour (4, 4, 4), which the shader gets made linear, as rendered",
             field(play, q, after, "LampSwitch", "glow"), BLOCK4 * CUBE, RENDER)
    t.eq("glow_read: a colour a property block sets is rendered", field(play, q, after, "LampSwitch", "glow_read"), "render")
    near_rel(t, "LampLater after: 3 x (1, 0.5, 0.25) linear", field(play, q, after, "LampLater", "glow"), 3 * lum(1, 0.5, 0.25), 1e-4)
    t.near("LampOff before: intensity 2", field(play, q, before, "LampOff", "glow"), 2.0, FLOAT)
    t.eq("LampOff after: intensity 0 is off", field(play, q, after, "LampOff", "glow"), 0.0)
    near_rel(t, "LampCustom: its shader's (3, 2, 1), as rendered", field(play, q, before, "LampCustom", "glow"), CUSTOM * CUBE, RENDER)
    t.eq("Dark: lit plain", field(play, q, before, "Dark", "glow"), 0.0)
    t.eq("glow_read: properties for a shader with the interface and no texture", field(play, q, before, "LampEmissive", "glow_read"), "props")
    t.eq("glow_read: an emission map is rendered (an atlas, a spot)", field(play, q, before, "LampMapped", "glow_read"), "render")
    t.eq("glow_read: a custom shader is rendered", field(play, q, before, "LampCustom", "glow_read"), "render")
    t.eq("a Light reads no glow_read (no renderer read)", field(play, q, before, "LampLight", "glow_read"), None)
    t.eq("glow_sources of each", [field(play, q, after, n, "glow_sources") for n in order],
         ["light", "emissive", "unlit", "emissive", "emissive", "light", "", "emissive", ""])
    t.eq("row keys: identity, then the fields in the order asked, then the notes",
         keys(play, q, before, "LampEmissive"), ["name", "class", "lit", "glow", "glow_sources", "glow_read"])

    lit_before = set(names(play, "o_haslit", before))
    lit_after = set(names(play, "o_haslit", after))
    common = {"Sun", "LampLight", "LampEmissive", "LampUnlit", "LampMapped", "LampCustom", "Bulb", "Sparks", "Fan", "Blade", "Tracer"}
    t.eq("has lit before 4 s: the objects with a lit part (the fan and its blade by the trail at its tip)", lit_before, common | {"LampOff"})
    t.eq("has lit after 4 s: LampOff out, LampSwitch, LampLater and LampLate in", lit_after, common | {"LampSwitch", "LampLater", "LampLate"})

    t.eq("LampLate is dark before the game lights it", field(play, "o_late", 3.5, "LampLate", "lit"), 0.0)
    t.ok("an input selected it by has.lit at 4 s, before the game's scripts lit it that frame: it matched nothing",
         "teleport_to skipped (no object matches)" in play.probe_log, play.probe_log[-300:])
    t.eq("the sample at 4 s, after the game's scripts, reads it lit (not what the input's select read)",
         field(play, "o_late", 4.0, "LampLate", "lit"), 1.0)
    near_rel(t, "and its glow (its block's colour, as rendered)", field(play, "o_late", 4.0, "LampLate", "glow"), BLOCK4 * CUBE, RENDER)

    t.eq("near with y_min 2: the upper bulb", [r.get("y") for r in play.rows("o_bulb_hi", 1.0)], [3.0])
    near_rel(t, "its glow: (4, 3, 2) over a 0.4 m ball's box", field(play, "o_bulb_hi", 1.0, "Bulb", "glow"), EMISSIVE * quarter(0.4, 0.4, 0.4), 1e-4)
    t.near("its scale", field(play, "o_bulb_hi", 1.0, "Bulb", "scale"), 0.4, FLOAT)
    t.eq("near with y_relative and y_max -1 from y 3: the lower bulb", [r.get("y") for r in play.rows("o_bulb_lo", 1.0)], [0.5])

    q = "o_sun"
    t.near("world_pitch:Light (a Part by component type)", field(play, q, 1.0, "Sun", "world_pitch:Light"), 50, 1e-3)
    t.near("world_yaw:Sun (a Part by its own name)", field(play, q, 1.0, "Sun", "world_yaw:Sun"), -30, 1e-3)
    t.near("forward:Light.y: the way its light travels", field(play, q, 1.0, "Sun", "forward:Light.y"), -math.sin(math.radians(50)), 1e-4)
    t.near("the sun's glow: intensity 1.5", field(play, q, 1.0, "Sun", "glow"), 1.5, FLOAT)

    q = "c_lights"
    t.eq("Light components (one disabled on an active object counts)", sorted_names(play, q, before), ["LampLater", "LampLight", "LampOff", "Sun"])
    t.eq("intensity before", [field(play, q, before, n, "intensity") for n in ("Sun", "LampLight", "LampLater", "LampOff")], [1.5, 5.0, 3.0, 2.0])
    t.eq("on before", [field(play, q, before, n, "on") for n in ("Sun", "LampLight", "LampLater", "LampOff")], [1.0, 1.0, 0.0, 1.0])
    t.eq("on after", [field(play, q, after, n, "on") for n in ("Sun", "LampLight", "LampLater", "LampOff")], [1.0, 1.0, 1.0, 0.0])
    t.eq("active: LampLater's Light disabled, then enabled", [field(play, q, x, "LampLater", "active") for x in (before, after)], [0.0, 1.0])
    t.eq("visible: a component that isn't a renderer reads its object's activity", field(play, q, before, "LampLater", "visible"), 1.0)
    t.eq("lit as the objects read it", [field(play, q, after, n, "lit") for n in ("Sun", "LampLight", "LampLater", "LampOff")], [1.0, 1.0, 1.0, 0.0])
    t.eq("x of LampLight", field(play, q, before, "LampLight", "x"), -8.0)

    q = "c_lamp_r"
    renderers = ["LampEmissive", "LampUnlit", "LampMapped", "LampSwitch", "LampCustom", "Dark"]
    t.eq("Renderer components owned by objects tagged ObjLamp", sorted_names(play, q, before), sorted(renderers))
    t.eq("lit as the objects read it, one source each", [field(play, q, after, n, "lit") for n in renderers],
         [field(play, "o_lamps", after, n, "lit") for n in renderers])
    t.eq("glow as the objects read it", [field(play, q, after, n, "glow") for n in renderers],
         [field(play, "o_lamps", after, n, "glow") for n in renderers])

    q = "o_watch"
    t.eq("the queries left the active render texture as they found it", field(play, q, 15.0, "Watch", "prop:ObjWatch.activeChanged"), 0.0)
    t.eq("and no renderer's materials changed (no instance made)", field(play, q, 15.0, "Watch", "prop:ObjWatch.materialsChanged"), 0.0)
    t.eq("and no property block was set", field(play, q, 15.0, "Watch", "prop:ObjWatch.blocksChanged"), 0.0)


def reads(t, play):
    q = "o_enemy"
    enemies = ["Enemy_0", "Enemy_1", "Enemy_2"]
    t.eq("tag: the enemies", sorted_names(play, q, 1.0), enemies)
    t.ok("prop: a float, drained by game time (95, 90, 85 at 1 s, give or take the drain of the frame the scene starts in)",
         all(abs(field(play, q, 1.0, n, "prop:ObjHealth.current") - (100 - 5 * (i + 1))) <= 5 * (i + 1) / 30 + 1e-3 for i, n in enumerate(enemies)),
         [field(play, q, 1.0, n, "prop:ObjHealth.current") for n in enemies])
    t.eq("prop: a private serialized int", field(play, q, 1.0, "Enemy_0", "prop:ObjHealth.armour"), 7.0)
    t.eq("prop: an enum as its value (Idle, Hurt, Dead)", [field(play, q, x, "Enemy_2", "prop:ObjHealth.state") for x in (0.5, 2.0, 7.5)], [0.0, 1.0, 2.0])
    t.eq("prop: a string as it is", field(play, q, 1.0, "Enemy_0", "prop:ObjHealth.label"), "grunt")
    t.eq("prop: a list without an index is its length", field(play, q, 1.0, "Enemy_0", "prop:ObjHealth.items"), 3.0)
    t.eq("prop: [1] its element", field(play, q, 1.0, "Enemy_0", "prop:ObjHealth.items[1]"), 5.0)
    t.eq("prop: a colour's channel", field(play, q, 1.0, "Enemy_0", "prop:ObjHealth.tint.g"), 0.5)
    t.eq("prop: an object reference set, and unset", [field(play, q, 1.0, n, "prop:ObjHealth.target") for n in enemies], [1.0, 0.0, 0.0])
    t.eq("prop: a GameObject member", field(play, q, 1.0, "Enemy_0", "prop:activeSelf"), 1.0)
    t.eq("prop: a Transform member", field(play, q, 1.0, "Enemy_0", "prop:localScale.y"), 1.0)
    t.eq("prop: a member it doesn't have has no value", field(play, q, 1.0, "Enemy_0", "prop:ObjHealth.nothing"), None)
    t.eq("in a player every scene root reports sibling index 0 (why roots are ordered by the scene's root list)",
         [field(play, q, 1.0, n, "prop:ObjHealth.sibling") for n in enemies], [0.0, 0.0, 0.0])
    roots = [r.get("prop:ObjHealth.rootIndex") for r in play.rows(q, 1.0)]
    t.ok("rows come in the order of their places in the scene's root list", roots == sorted(roots) and len(set(roots)) == 3, roots)
    t.eq("an object select by an interface: the objects with a component that implements it", names(play, "o_hurt", 1.0), names(play, q, 1.0))
    t.eq("a components select by the same interface: the same three components", names(play, "c_hurt", 1.0), names(play, q, 1.0))
    t.eq("their class is the component's type", [r.get("class") for r in play.rows("c_hurt", 1.0)], ["ObjHealth"] * 3)
    t.eq("components prop: on the component itself", field(play, "c_health", 1.0, "Enemy_0", "prop:current"), field(play, q, 1.0, "Enemy_0", "prop:ObjHealth.current"))
    t.eq("components active: an enabled script", field(play, "c_health", 1.0, "Enemy_0", "active"), 1.0)
    t.eq("components speed: no velocity of its own, unmoved since the previous sample", field(play, "c_health", 1.0, "Enemy_0", "speed"), 0.0)

    q = "o_arm"
    t.near("anim: a float parameter (play time)", field(play, q, 2.0, "Arm", "anim:Speed"), 2.0, 1 / 30 + 1e-3)
    t.eq("anim: an int", field(play, q, 2.5, "Arm", "anim:Count"), 2.0)
    t.eq("anim: a bool, before and after 3 s", [field(play, q, x, "Arm", "anim:Open") for x in (2.0, 4.0)], [0.0, 1.0])
    t.eq("anim: a parameter it doesn't have has no value", field(play, q, 2.0, "Arm", "anim:Missing"), None)
    t.eq("clip: the current clip, before and after Open", [field(play, q, x, "Arm", "clip") for x in (2.0, 4.5)], ["Idle", "Bend"])
    t.near("bone: a SkinnedMeshRenderer's bone by name", field(play, q, 2.0, "Arm", "bone:SkinnedMeshRenderer.Upper.x"), 12.0, 1e-4)
    t.near("bone: after the bend (Upper slid 0.6 m)", field(play, q, 4.5, "Arm", "bone:SkinnedMeshRenderer.Upper.x"), 12.6, 1e-4)
    t.near("bone: a descendant of that name under an Animator that isn't humanoid", field(play, q, 2.0, "Arm", "bone:Animator.Upper.y"), 1.0, 1e-4)
    t.near("pose_change before the bend", field(play, q, 2.0, "Arm", "pose_change"), 0.0, 1e-4)
    t.near("pose_change after: its bone moved 0.6 m in the mesh's own space", field(play, q, 4.5, "Arm", "pose_change"), 0.6, 1e-4)
    t.eq("changed", [field(play, q, x, "Arm", "changed") for x in (2.0, 4.5)], [0.0, 1.0])
    t.near("bounds_change after", field(play, q, 4.5, "Arm", "bounds_change"), 0.6, 1e-4)
    t.near("extent_x before (a 0.4 m box)", field(play, q, 2.0, "Arm", "extent_x"), 0.2, 1e-4)
    t.near("extent_x after (0.4 + 0.6)", field(play, q, 4.5, "Arm", "extent_x"), 0.5, 1e-4)
    q = "c_smr"
    t.near("components pose_change of the arm's SkinnedMeshRenderer", field(play, q, 4.5, "Arm", "pose_change"), 0.6, 1e-4)
    t.eq("changed", field(play, q, 4.5, "Arm", "changed"), 1.0)
    t.near("bounds_change", field(play, q, 4.5, "Arm", "bounds_change"), 0.6, 1e-4)
    t.eq("lit: a plain Lit material is dark", field(play, q, 4.5, "Arm", "lit"), 0.0)

    q = "o_rock"
    t.near("a LODGroup: both LODs' renderers count for extent_x (they stay enabled)", field(play, q, 1.0, "Rock", "extent_x"), 0.5, 1e-4)
    t.eq("spread: two parts with one centre", field(play, q, 1.0, "Rock", "spread"), 0.0)
    t.eq("hidden", field(play, q, 1.0, "Rock", "hidden"), 0.0)
    t.ok("a field the kind doesn't have is left out of the rows", all("nonsense" not in r for r in play.rows("o_bad", 1.0)), play.rows("o_bad", 1.0))
    t.eq("but the rows are there", names(play, "o_bad", 1.0), ["Rock"])

    q = "o_all"
    classes = {r["name"]: r["class"] for r in play.rows(q, 0.5)}
    t.eq("class: the first script (the hero's)", classes.get("Hero"), "ObjTestPlayer")
    t.eq("class: a camera's first script over the Camera", classes.get("Main Camera"), "ObjFollowCam")
    t.eq("class: a Behaviour or Renderer before another component (a primitive's MeshRenderer, not its BoxCollider)", classes.get("Crate"), "MeshRenderer")
    t.eq("class: a Light", classes.get("Sun"), "Light")
    t.eq("class: else its first other component (a LODGroup)", classes.get("Rock"), "LODGroup")
    t.eq("class: nothing but a transform", classes.get("Fan"), "GameObject")
    every = names(play, q, 0.5)
    t.ok("rows in hierarchy order: a root, then its children depth first",
         follows(every, "Hero", ["Visor"]) and follows(every, "Fan", ["Blade", "Tracer"]) and follows(every, "Arm", ["Lower", "Upper"])
         and follows(every, "Rock", ["Rock_LOD0", "Rock_LOD1"]), every[:12])


def effects(t, play):
    live = {r["name"]: r for r in play.rows("c_effects", 1.0)}
    t.eq("effect: the live ones only (a trail drawing points, a playing system, an enabled decal)", sorted(live), ["Decal", "Sparks", "Tracer"])
    t.eq("their classes", [live.get(n, {}).get("class") for n in ("Tracer", "Sparks", "Decal")], ["TrailRenderer", "ParticleSystem", "DecalProjector"])
    t.eq("count: 1 a row", [live.get(n, {}).get("count") for n in ("Tracer", "Sparks", "Decal")], [1.0, 1.0, 1.0])
    t.eq("lit: the trail and the particles give light, the decal is no source", [live.get(n, {}).get("lit") for n in ("Tracer", "Sparks", "Decal")], [1.0, 1.0, None])
    t.eq("DecalProjector components: active, and disabled", {r["name"]: r.get("active") for r in play.rows("c_decal", 1.0)},
         {"Decal": 1.0, "DecalOff": 0.0})
    t.eq("visible: a component that isn't a renderer reads its object's activity", [r.get("visible") for r in play.rows("c_decal", 1.0)], [1.0, 1.0])
    t.eq("component and effect: the enabled decal only", names(play, "c_decal_live", 1.0), ["Decal"])
    t.eq("the playing particle system only", names(play, "c_ps_live", 1.0), ["Sparks"])
    q = "c_ps"
    t.eq("ParticleSystem active: playing, stopped", [field(play, q, 1.0, n, "active") for n in ("Sparks", "SparksOff")], [1.0, 0.0])
    t.eq("lit: the live one as rendered, the stopped one dark without rendering", [field(play, q, 1.0, n, "lit") for n in ("Sparks", "SparksOff")], [1.0, 0.0])
    t.eq("the stopped one's glow", field(play, q, 1.0, "SparksOff", "glow"), 0.0)
    t.eq("the live one's source", field(play, q, 1.0, "Sparks", "glow_sources"), "effect")
    t.eq("read as rendered", field(play, q, 1.0, "Sparks", "glow_read"), "render")
    t.ok("prop:particleCount on the component (20 a second for 1 s)", 15 <= (field(play, q, 3.0, "Sparks", "prop:particleCount") or 0) <= 21,
         field(play, q, 3.0, "Sparks", "prop:particleCount"))
    q = "c_trail"
    t.eq("a TrailRenderer: active, visible", [field(play, q, 1.0, "Tracer", k) for k in ("active", "visible")], [1.0, 1.0])
    t.ok("its x follows the blade's tip", len({round(v, 3) for _, v in play.series(q, "x", "Tracer") if v is not None}) > 3)
    t.eq("lit: drawing points, as rendered", field(play, q, 1.0, "Tracer", "lit"), 1.0)
    t.eq("the spheres' MeshRenderers by mesh name once the bullets are gone", sorted_names(play, "c_spheres", 12.0), ["Bulb", "Bulb", "LampUnlit", "Rock_LOD1"])
    t.eq("an unknown type: no rows", play.rows("c_bad", 1.0), [])
    t.eq("no component and no effect: no rows", play.rows("c_none", 1.0), [])


def lab(t, play):
    """Every objects and components field and select key on one scene of everything (the drive keys move the hero)."""
    hero(t, play)
    physics(t, play)
    gone(t, play)
    lamps(t, play)
    reads(t, play)
    effects(t, play)


# ---------------------------------------------------------------------------------------------------------------- world


def world(t, play):
    """camera, spawns, pieces and ground on the same scene (their own tests are probe_tests/world)."""
    cam = play.value("cam", 2.0)
    t.near("camera distance to the player's pivot (0, 3, -6) behind", cam["distance"], math.hypot(3, 6), 1e-3)
    t.near("height", cam["height"], 3.0, 1e-3)
    t.eq("occluded: the wall between them 6 to 8 s, else not", [play.value("cam", x)["occluded"] for x in (5.5, 7.0, 8.5)], [0.0, 1.0, 0.0])
    t.eq("player_on_screen: looking away 10 to 11 s", [play.value("cam", x)["player_on_screen"] for x in (9.5, 10.5, 11.5)], [1.0, 0.0, 1.0])
    for at in (2.0, 5.0):
        times = [1.0 + 0.5 * k for k in range(17) if 1.0 + 0.5 * k <= at]
        want = {"spawned": 2.0 * len(times), "destroyed": float(sum(x + 1.0 <= at for x in times) + sum(x + 0.7 <= at for x in times))}
        t.eq(f"spawns at {at} s: a clone and a pooled one every 0.5 s from 1 s, gone after 1 and 0.7 s", play.value("sp", at), want)
    t.eq("spawns at 12 s: 17 clones and 17 pool reuses, all gone", play.value("sp", 12.0), {"spawned": 34.0, "destroyed": 34.0})
    t.eq("spawns of an unknown type: no value", play.value("sp_bad", 2.0), None)
    t.eq("pieces of the terrain's trees", play.value("p_terrain", 1.0),
         {"count": 6.0, "visible": 6.0, "components": 1.0, "objects": 1.0, "triangles": 4680.0, "visible_triangles": 4680.0})
    t.eq("trees near a point", play.value("p_trees_near", 1.0)["count"], 2.0)
    t.eq("pieces by mesh Sphere once the bullets are gone (LOD 1 is no piece)", play.value("p_sphere", 12.0)["count"], 3.0)
    t.eq("a LODGroup is one piece of 12 triangles (LOD 0)", (play.value("p_rock", 1.0)["count"], play.value("p_rock", 1.0)["triangles"]), (1.0, 12.0))
    hidden = [play.value("p_all", x)["count"] - play.value("p_all", x)["visible"] for x in (2.5, 3.5)]
    t.eq("pieces not drawn: one more once Ghost's renderer is off (Vanisher, inactive, is no piece; bullets come and go drawn)",
         hidden[1] - hidden[0], 1.0)
    t.eq("ground at the origin", play.value("g_origin", 1.0), {"height": 0.0, "hit": 1.0})
    t.near("ground under the roof", play.value("g_roof", 1.0)["height"], 4.1, 1e-4)
    t.near("ground under the roof, the floor selected", play.value("g_roof_floor", 1.0)["height"], 0.0, 1e-4)
    t.eq("ground off the map", play.value("g_none", 1.0), {"height": None, "hit": 0.0})
    hills = play.value("g_hills", 1.0)
    t.eq("ground over the hills: 64 of 64 rays hit", hills["hits"], 64.0)
    t.ok("from about 0.58 to 5.55 m", abs(hills["min"] - 0.583) < 0.01 and abs(hills["max"] - 5.55) < 0.01, hills)
    t.eq("the same with only the TerrainCollider selected", play.value("g_hills_sel", 1.0), hills)


# ---------------------------------------------------------------------------------------------------------------- more


def more(t, play):
    """What ObjLab lacks: lit and glow of every kind of source, 2D physics, a NavMeshAgent, a humanoid, a ragdoll."""
    q = "m_lamps"
    kelvin = [field(play, q, 1.0, "LampTemp", "prop:ObjKelvin.rgb." + c) for c in "rgb"]
    t.eq("URP lights with colour temperature", field(play, q, 1.0, "LampTemp", "prop:ObjKelvin.uses"), 1.0)
    near_rel(t, "a Light at 3000 K: intensity 2 x its temperature's colour's luminance",
             field(play, q, 1.0, "LampTemp", "glow"), 2 * (0.2126 * kelvin[0] + 0.7152 * kelvin[1] + 0.0722 * kelvin[2]), 1e-5)
    t.eq("two materials, the second's emission off-black: dark before its block", field(play, q, 1.0, "LampTwoMat", "lit"), 0.0)
    near_rel(t, "a block on material 1 alone lights it (as rendered)", field(play, q, 2.5, "LampTwoMat", "glow"), BLOCK4 * CUBE, RENDER)
    standard = field(play, "m_facts", 1.0, "Facts", "prop:ObjFacts.standardHdr")
    near_rel(t, f"the built-in Standard shader reads by its properties too ((2, 2, 2), [HDR] {standard})",
             field(play, q, 1.0, "LampStandard", "glow"), (hdr if standard == 1.0 else lum)(2, 2, 2) * CUBE, 1e-4)
    t.eq("LampStandard: props", field(play, q, 1.0, "LampStandard", "glow_read"), "props")
    t.eq("_EMISSION off: dark whatever its colour", field(play, q, 1.0, "LampKeyword", "glow"), 0.0)
    near_rel(t, "the keyword switched on at 2 s (its own material copy): lit", field(play, q, 2.5, "LampKeyword", "glow"), HDR4 * CUBE, 1e-4)
    t.eq("a renderer forced off reads dark without being read", (field(play, q, 1.0, "LampForced", "lit"), field(play, q, 1.0, "LampForced", "glow_read")), (0.0, None))
    t.eq("an emission of luminance 0.009 is under the floor of 0.01: dark", field(play, q, 1.0, "LampDim", "lit"), 0.0)
    t.eq("0.011 is over it: lit", field(play, q, 1.0, "LampFaint", "lit"), 1.0)
    near_rel(t, "and glows that much over the cube", field(play, q, 1.0, "LampFaint", "glow"), hdr(0.011, 0.011, 0.011) * CUBE, 1e-4)
    t.eq("an unlit material with a main texture is rendered", field(play, q, 1.0, "LampUnlitMap", "glow_read"), "render")
    near_rel(t, "its colour on half of each face", field(play, q, 1.0, "LampUnlitMap", "glow"), lum(1, 0.9, 0.5) * 0.5 * CUBE, RENDER)
    t.eq("its source: unlit", field(play, q, 1.0, "LampUnlitMap", "glow_sources"), "unlit")
    if play.row(q, 1.0, "LampGraph") is not None:
        t.eq("a Shader Graph (path Unlit/..., _BaseColor) is rendered, not read by its properties", field(play, q, 1.0, "LampGraph", "glow_read"), "render")
        near_rel(t, "and gives its colour (0.5, 1, 0.25)", field(play, q, 1.0, "LampGraph", "glow"), lum(0.5, 1, 0.25) * CUBE, RENDER)
    q = "m_atlas"
    t.eq("a mesh showing the white half of its emission map: lit", field(play, q, 1.0, "AtlasWhite", "lit"), 1.0)
    near_rel(t, "with the map's white, (4, 4, 4), all over", field(play, q, 1.0, "AtlasWhite", "glow"), HDR4 * CUBE, RENDER)
    near_rel(t, "what the properties read of the same [HDR] colour (LampKeyword) is what the render shows",
             field(play, "m_lamps", 2.5, "LampKeyword", "glow") or 0, field(play, q, 2.5, "AtlasWhite", "glow") or 0, RENDER)
    t.eq("one showing the black half of the same map: dark (its mean would say lit)", field(play, q, 1.0, "AtlasBlack", "lit"), 0.0)
    t.eq("both rendered", [field(play, q, 1.0, n, "glow_read") for n in ("AtlasWhite", "AtlasBlack")], ["render", "render"])

    q = "m_facts"
    t.eq("URP Lit marks _EmissionColor [HDR]", field(play, q, 1.0, "Facts", "prop:ObjFacts.litHdr"), 1.0)
    t.near("a property block's GetColor gives back the colour set on it (0.5 grey)", field(play, q, 1.0, "Facts", "prop:ObjFacts.blockColour"), 0.5, 1e-6)
    t.near("and a vector set on it the same way (HasColor true): the block can't say which it holds",
           field(play, q, 1.0, "Facts", "prop:ObjFacts.vectorAsColour"), 0.5, 1e-6)
    q = "m_blocks"
    blocks = ("BlockColour", "BlockColourMap", "BlockVector", "BlockVectorMap")
    t.eq("before 2 s, no block, black: dark, the mapped ones without a render (their bound is 0)",
         [(field(play, q, 1.0, n, "lit"), field(play, q, 1.0, n, "glow_read")) for n in blocks],
         [(0.0, "props"), (0.0, "bound"), (0.0, "props"), (0.0, "bound")])
    t.eq("once a block sets the emission (2 s), every one is rendered", [field(play, q, 2.5, n, "glow_read") for n in blocks], ["render"] * 4)
    near_rel(t, "a colour (4, 4, 4) set on a block (SetColor): the shader gets it made linear", field(play, q, 2.5, "BlockColour", "glow"), BLOCK4 * CUBE, RENDER)
    near_rel(t, "the same over a white emission map", field(play, q, 2.5, "BlockColourMap", "glow"), BLOCK4 * CUBE, RENDER)
    near_rel(t, "a vector (4, 4, 4) set on a block (SetVector): the shader gets it as it is", field(play, q, 2.5, "BlockVector", "glow"), HDR4 * CUBE, RENDER)
    near_rel(t, "the same over a white emission map", field(play, q, 2.5, "BlockVectorMap", "glow"), HDR4 * CUBE, RENDER)

    q = "m_sprites"
    t.eq("a SpriteRenderer gives light, as rendered", field(play, q, 1.0, "SpriteLamp", "lit"), 1.0)
    t.eq("read as rendered", field(play, q, 1.0, "SpriteLamp", "glow_read"), "render")
    t.ok("its glow: a lit 1 x 1 m sprite", 0.0 < (field(play, q, 1.0, "SpriteLamp", "glow") or 0) < 0.5, field(play, q, 1.0, "SpriteLamp", "glow"))
    t.eq("a black sprite: dark", field(play, q, 1.0, "SpriteDark", "lit"), 0.0)
    t.near("a sprite is a part: its extent", field(play, q, 1.0, "SpriteLamp", "extent_x"), 0.5, 1e-4)
    t.eq("and changed reads it (unchanged)", field(play, q, 1.0, "SpriteLamp", "changed"), 0.0)
    t.eq("components lit of a SpriteRenderer", [field(play, "m_c_sprite", 1.0, n, "lit") for n in ("SpriteLamp", "SpriteDark")], [1.0, 0.0])
    t.eq("a LineRenderer gives light, as rendered", (field(play, "m_line", 1.0, "LineLamp", "lit"), field(play, "m_line", 1.0, "LineLamp", "glow_read")), (1.0, "render"))
    t.eq("components lit of a LineRenderer", field(play, "m_c_line", 1.0, "LineLamp", "lit"), 1.0)
    t.near("a line is a part: its extent (2 m along x)", field(play, "m_line", 1.0, "LineLamp", "extent_x"), 1.0, 0.11)

    q = "m_tubes"
    t.near("a SkinnedMeshRenderer's local bounds are in its root bone's frame: world extent 2 x local",
           field(play, q, 1.0, "TubeLit", "extent_x"), 2 * field(play, q, 1.0, "TubeLit", "prop:SkinnedMeshRenderer.localBounds.extents.x"), 1e-4)
    near_rel(t, "glow from properties over the box in the root bone's frame (0.4 x 2 x 0.4 m)",
             field(play, q, 1.0, "TubeLit", "glow"), EMISSIVE * quarter(0.4, 2, 0.4), 1e-4)
    near_rel(t, "as rendered over the same box", field(play, q, 1.0, "TubeCustom", "glow"), CUSTOM * quarter(0.4, 2, 0.4), RENDER)

    vfx = play.row("m_vfx", 1.0, "Vfx")
    if vfx is not None:  # the project has the VFX Graph package (the scene has the effect only then)
        t.eq("a VisualEffect holding particles is a live effect", "Vfx" in names(play, "m_effects", 1.0), True)
        t.eq("its component is active", field(play, "m_c_vfx", 1.0, "Vfx", "active"), 1.0)
        t.eq("it gives light, as rendered", (vfx.get("lit"), vfx.get("glow_sources"), vfx.get("glow_read")), (1.0, "effect", "render"))
        t.ok("some glow (its value is left out of the comparison of two plays)", (field(play, "m_vfx_glow", 1.0, "Vfx", "glow") or 0) > 0,
             field(play, "m_vfx_glow", 1.0, "Vfx", "glow"))
    else:
        t.eq("without the VFX Graph package: no VisualEffect", play.rows("m_c_vfx", 1.0), [])

    q = "m_2d"
    t.near("a Dynamic Rigidbody2D falls: y at 0.5 s", field(play, q, 0.5, "Box2D", "y"), 6 - fallen(0.5), 1e-3)
    t.near("its speed: its body's velocity", field(play, q, 0.5, "Box2D", "speed"), G * STEP * steps(0.5), 1e-3)
    t.eq("it simulates", field(play, q, 0.5, "Box2D", "simulating"), 1.0)
    t.near("at rest on the ground at 3 s (Physics2D keeps a 0.01 m contact offset)", field(play, q, 3.0, "Box2D", "y"), 1.0, 0.02)
    t.eq("a Collider2D collides", field(play, q, 0.5, "Box2D", "collision"), 1.0)
    t.near("a sprite's extent", field(play, q, 0.5, "Box2D", "extent_x"), 0.5, 1e-4)
    t.eq("a kinematic Rigidbody2D doesn't simulate", field(play, q, 1.0, "Kin2D", "simulating"), 0.0)
    t.near("its speed: moved 2 m/s", field(play, q, 1.0, "Kin2D", "speed"), 2.0, 2 * STEP / 0.5 * 2)
    t.near("a Rigidbody2D spun at 90 deg/s: spin on the first sample is its angular velocity", field(play, q, 1 / 30, "Spin2D", "spin"), 90.0, 1e-3)
    t.near("and later, summed frame by frame", field(play, q, 2.0, "Spin2D", "spin"), 90.0, 90 * STEP / 0.5)
    t.eq("the ground: no renderer, so not hidden", field(play, q, 0.5, "Ground2D", "hidden"), 0.0)
    t.eq("Rigidbody2D components simulating", [field(play, "m_c2d", 1.0, n, "simulating") for n in ("Box2D", "Kin2D", "Spin2D")], [1.0, 0.0, 1.0])

    t.near("a NavMeshAgent's speed: its velocity on its NavMesh", field(play, "m_walker", 2.0, "Walker", "speed"), 2.0, 0.02)
    t.ok("it walks toward its goal", field(play, "m_walker", 2.0, "Walker", "x") > field(play, "m_walker", 1.0, "Walker", "x"))
    t.near("components speed of the agent", field(play, "m_c_walker", 2.0, "Walker", "speed"), 2.0, 0.02)

    q = "m_human"
    t.eq("the stick figure is humanoid", field(play, q, 1.0, "Human", "prop:Animator.isHuman"), 1.0)
    skull = field(play, q, 1.0, "Human", "bone:Animator.Skull.y")
    foot = field(play, q, 1.0, "Human", "bone:Animator.LeftFoot.y")
    t.ok("bone: its head transform by name, above its left foot (a human bone)", None not in (skull, foot) and skull > foot + 1.0, (skull, foot))
    t.eq("bone: Head is the Animator's human head bone (named Skull)", field(play, q, 1.0, "Human", "bone:Animator.Head.y"), skull)
    t.eq("the human bone's name in any case", field(play, q, 1.0, "Human", "bone:Animator.head.y"), skull)
    t.eq("a number is no human bone's name", field(play, q, 1.0, "Human", "bone:Animator.5.y"), None)
    t.eq("a number out of the bones' range: no value, the row is there", (field(play, "m_human_far", 1.0, "Human", "bone:Animator.100.y"),
                                                                           field(play, "m_human_far", 1.0, "Human", "count")), (None, 1.0))

    q = "m_doll"
    t.near("a ragdoll's spread: its three bodies' places, 1.2 m apart", field(play, q, 0.5, "Ragdoll", "spread"), 1.2, 1e-3)
    t.ok("kicked apart at 1 s: spread grows", (field(play, q, 3.0, "Ragdoll", "spread") or 0) > 2.0, field(play, q, 3.0, "Ragdoll", "spread"))
    t.eq("and it changed", field(play, q, 3.0, "Ragdoll", "changed"), 1.0)
    t.ok("its bones moved in the mesh's own space", (field(play, q, 3.0, "Ragdoll", "pose_change") or 0) > 1.0, field(play, q, 3.0, "Ragdoll", "pose_change"))

    classes = {r["name"]: r["class"] for r in play.rows("m_class", 1.0)}
    t.eq("class of an object with a BoxCollider alone", classes.get("OnlyCollider"), "BoxCollider")
    t.eq("class of the listener's object: AudioListener, not the probe's AudioTap on it", classes.get("Ears"), "AudioListener")
    t.eq("class of the humanoid", classes.get("Human"), "Animator")
    t.eq("class of the ragdoll", classes.get("Ragdoll"), "SkinnedMeshRenderer")
    t.near("speed of an object moved by its transform alone", field(play, "m_slider", 2.0, "Slider", "speed"), 2.0, 1e-3)
    q = "m_watch"
    t.eq("the queries left the active render texture as they found it", field(play, q, 5.5, "Watch", "prop:ObjWatch.activeChanged"), 0.0)
    t.eq("no renderer's materials changed", field(play, q, 5.5, "Watch", "prop:ObjWatch.materialsChanged"), 0.0)
    t.eq("no property block set", field(play, q, 5.5, "Watch", "prop:ObjWatch.blocksChanged"), 0.0)


def wait_(t, play):
    """Across a wait the play's clock holds while the game runs on: speed and spin divide by the game time that passed."""
    for at in (0.5, 1.0, 1.5):
        t.near(f"speed at {at} s: 2 m/s whether or not the game ran a wait since the sample before", field(play, "w_slider", at, "Slider", "speed"), 2.0, 1e-3)
    ran = field(play, "w_slider", 1.5, "Slider", "x") - field(play, "w_slider", 0.5, "Slider", "x")
    t.ok("the slider ran on during the wait (1 s of the play's clock and 2 s of wait at 2 m/s)", ran > 5.9, ran)
    t.near("spin over the sample after the wait", field(play, "w_turner", 1.5, "Turner", "spin"), 180, 0.01)


def budget(t, play):
    """One sample renders at most 64 renderers for lit and glow; past that a mesh with properties reads its bound and
    anything else has no value. The budget is the same, in hierarchy order, at every sample."""
    for at in (0.5, 1.0):
        rows = play.rows("b_rows", at)
        t.eq(f"84 rows at {at} s", len(rows), 84)
        if len(rows) < 84:
            continue
        t.ok(f"at {at} s the first 64 are rendered and lit", all(r.get("lit") == 1.0 and r.get("glow_read") == "render" for r in rows[:64]), rows[:2])
        near_rel(t, f"each with its shader's colour at {at} s", rows[0].get("glow"), CUSTOM * CUBE, RENDER)
        t.ok(f"at {at} s the next 16 have no value", all("lit" not in r and "glow" not in r and r.get("glow_read") == "unread" for r in rows[64:80]), rows[64:66])
        t.ok(f"at {at} s the 4 with an emission map read their bound (the map taken as white)",
             all(r.get("glow_read") == "bound" and r.get("lit") == 1.0 for r in rows[80:]), rows[80:])
        near_rel(t, f"the bound at {at} s: (2, 2, 2) over the cube", rows[80].get("glow"), hdr(2, 2, 2) * CUBE, 1e-4)
    obj = play.row("b_obj", 1.0, "Lamps")
    t.eq("the object of them all is lit", obj.get("lit"), 1.0)
    t.eq("and says how its renderers were read", obj.get("glow_read"), "render,bound,unread")
    near_rel(t, "its glow: what was read", obj.get("glow"), sum(r.get("glow", 0) for r in play.rows("b_rows", 1.0)), 1e-9)


# ---------------------------------------------------------------------------------------------------------------- cost


def cost(limit_ms, rows=None):
    """A stress play: one query over 3000 boxes sampled every 0.1 s (101 samples); its cost a sample is the play's real
    time less the empty play's, over 101, and stays under `limit_ms` (a generous bound: the machine is shared)."""
    def check(t, play):
        if rows is not None:
            t.eq("rows kept: 200", len(play.rows("s", 5.0)), 200)
            t.eq("total: every match", play.sample("s", 5.0).get("total"), rows)
        empty = real_seconds(play.earlier("stress_none"))
        mine = real_seconds(play)
        per = None if empty is None or mine is None else (mine - empty) / 101 * 1000
        t.ok(f"the cost of a sample is under {limit_ms} ms", per is not None and per < limit_ms, per)
    return check


def stress_none(t, play):
    """The empty play the stress plays are measured against."""
    t.ok("its real time is in probe.log", real_seconds(play) is not None, play.probe_log[-300:])


def stress_haslit(t, play):
    """has.lit over 3000 boxes: the 1000 emissive ones, the 20 other boxes with a Light, the sun, and their root."""
    t.eq("matches", play.sample("s", 5.0).get("total"), 1000.0 + 20.0 + 1.0 + 1.0)
    cost(150)(t, play)


PLAYS = {
    "lab": {"check": lab, "errors": [
        r"^objects o_bad: no field nonsense$", r"^components c_bad: no component type NoSuchType$",
        r"^components c_none: the select names no component and no effect$"]},
    "world": {"check": world, "errors": [r"^spawns( sp_bad)?: no component type Nope$"]},
    # a VisualEffect simulates on the GPU: its glow differed between two plays before its seed was fixed, and a GPU
    # isn't promised to repeat itself
    "more": {"check": more, "varies": ["m_vfx_glow"]},
    # a wait lasts its seconds of real time: how many frames the game runs in it differs from play to play
    "wait": {"check": wait_, "varies": True},
    "budget": {"check": budget},
    "stress_none": {"check": stress_none},
    "stress_objects_all": {"check": cost(150, 3004.0)},
    "stress_objects_glow": {"check": cost(150, 3004.0)},
    "stress_objects_change": {"check": cost(150, 3004.0)},
    "stress_objects_haslit": {"check": stress_haslit},
    "stress_objects_tag": {"check": cost(50)},
    "stress_components": {"check": cost(150, 3001.0)},
    "stress_pieces": {"check": cost(50)},
    "stress_ground": {"check": cost(50)},
    "stress_spawns": {"check": cost(50)},
    "stress_camera": {"check": cost(50)},
}
