"""The world family: the camera against the player (camera), objects appearing and going (spawns), placed mesh
pieces of every form (pieces) and the lie of the land (ground)."""

import math

MADE = "Assets/ProbeTests/world/Made/"
SETUP = ["ProbeTests.World.WldScenes.Build"]
SCENES = [MADE + "WorldLab.unity", MADE + "WorldSide.unity"]
FLOAT = 1e-5  # a float of the game widened to a double
RAY = 1e-3  # a height from a single-precision ray cast from 2000 m up (a float's step there is 1.2e-4 m)


def close(t, what, got, want, tol=RAY):
    """A value object: the same keys, numbers within `tol`, everything else equal."""
    ok = isinstance(got, dict) and set(got) == set(want) and all(
        (abs(got[k] - w) <= tol if isinstance(w, (int, float)) and isinstance(got[k], (int, float)) else got[k] == w)
        for k, w in want.items())
    t.ok(f"{what}: {want} (numbers within {tol})", ok, got)


def camera(t, play):
    """The camera 6 m behind the player and 1.5 m up, looking along +z: a wall between them from 1.25 to 1.75 s (a
    trigger, a pane on the Ignore Raycast layer and the camera's own collider always there); at 3.25 s it turns
    round."""
    v = play.value("camera", 0.5)
    t.eq("pitch, yaw (degrees), fov (vertical)", (v["pitch"], v["yaw"], v["fov"]), (0, 0, 60))
    t.near("distance to the player's pivot", v["distance"], math.sqrt(1.5 ** 2 + 6 ** 2), FLOAT)
    t.near("height above the player's pivot", v["height"], 1.5, FLOAT)
    t.eq("not occluded by a trigger, the Ignore Raycast layer or the camera's own collider", v["occluded"], 0)
    t.eq("the player's centre on screen", v["player_on_screen"], 1)
    t.eq("occluded while the wall stands", [play.value("camera", s)["occluded"] for s in (1.0, 1.5, 2.0)], [0, 1, 0])
    back = play.value("camera", 3.5)
    t.eq("turned round: yaw 180", back["yaw"], 180)
    t.eq("the player behind the camera is not on screen", back["player_on_screen"], 0)
    row, track = play.camera(0.5), play.track(0.5)
    t.near("the checker's distance from the camera and track rows is the same", math.dist(row[1:4], track[1:4]), v["distance"], FLOAT)
    t.near("and its height", row[2] - track[2], v["height"], FLOAT)


def camera_none(t, play):
    """No player (the play's player select matches nothing): the camera's own fields only; a point on the player
    doesn't resolve, so nothing is near it."""
    t.eq("the player's fields are null", play.value("camera", 0.5),
         {"pitch": 0, "yaw": 0, "fov": 60, "distance": None, "height": None, "occluded": None, "player_on_screen": None})
    t.eq("an object select near the player: no rows", play.rows("objects_near_player", 0.5), [])
    t.eq("pieces near the player: no value", play.value("pieces_near_player", 0.5), None)


def camera_ortho(t, play):
    """An orthographic camera reads fov 0; a field the camera kind doesn't have is said once."""
    t.eq("fov of an orthographic camera", play.value("camera", 0.5)["fov"], 0)
    t.eq("the camera's value is the same with an unknown field", play.value("camera_field", 0.5)["fov"], 0)


SPAWNS = {  # play time: (spawned, destroyed) since the play started; WldDirector's timeline
    0.5: (2, 0), 1.0: (3, 1), 1.5: (5, 3), 2.0: (6, 4), 2.5: (8, 6), 3.0: (10, 7), 3.5: (10, 9), 4.0: (12, 9),
    4.5: (12, 11), 5.0: (12, 11),
}


def spawns(t, play):
    """Shots made and destroyed, a pool reused with SetActive, one made and destroyed in one frame (never seen), a
    component added to an object, a disabled one destroyed, an additive scene loaded and unloaded; counted by the
    component's type, its base type and its interface alike."""
    for qid in ("shots", "bases", "iface"):
        got = {s: (play.value(qid, s) or {}).get("spawned") for s in SPAWNS}
        t.eq(f"{qid}: spawned", got, {s: v[0] for s, v in SPAWNS.items()})
        got = {s: (play.value(qid, s) or {}).get("destroyed") for s in SPAWNS}
        t.eq(f"{qid}: destroyed", got, {s: v[1] for s, v in SPAWNS.items()})
    t.eq("the first sample: what is there when the clock starts doesn't count", play.value("shots", 1 / 30),
         {"spawned": 0, "destroyed": 0})
    t.eq("an unknown component type has no value", play.value("unknown", 1.0), None)
    t.eq("nor a query without one", play.value("nameless", 1.0), None)


AREA = {"count": 18, "visible": 17, "components": 11, "objects": 11, "triangles": 231, "visible_triangles": 219}


def pieces(t, play):
    """Under PieceArea: 3 cubes, a mesh of two triangle submeshes (1 piece), a line mesh and a point mesh (none), one
    of triangles and lines, an unreadable mesh, a skinned mesh and one whose mesh has only lines (none), a LODGroup
    (LOD 0 only), a disabled renderer (not visible), an inactive one (none), a static one, a mesh drawn from code (none),
    and a terrain of 8 trees."""
    v = lambda qid: play.value(qid, 0.5)
    t.eq("every piece under PieceArea", v("area"), AREA)
    t.eq("component SkinnedMeshRenderer (one with a mesh of lines only is no piece)", v("skinned"),
         {"count": 1, "visible": 1, "components": 1, "objects": 1, "triangles": 12, "visible_triangles": 12})
    t.eq("component Terrain: its trees, a LOD tree's LOD 0 and a two-cube bush", v("trees"),
         {"count": 8, "visible": 8, "components": 1, "objects": 1, "triangles": 132, "visible_triangles": 132})
    t.eq("component MeshRenderer", v("mesh_renderers")["count"], 9)
    t.eq("component Renderer takes in skinned ones, not trees", v("renderers")["count"], 10)
    t.eq("name", v("rocks")["count"], 3)
    t.eq("mesh (a tree's: its prototype's first mesh)", v("cubes")["count"], 15)
    t.eq("mesh of two submeshes: one piece, its triangles summed", v("multi"),
         {"count": 1, "visible": 1, "components": 1, "objects": 1, "triangles": 6, "visible_triangles": 6})
    t.eq("near: each piece by its own place", v("near_rocks")["count"], 2)
    t.eq("near: a tree by its own place", v("near_tree")["count"], 1)
    zero = {"count": 0, "visible": 0, "components": 0, "objects": 0, "triangles": 0, "visible_triangles": 0}
    t.eq("an owner that matches nothing: zeros", v("owner_none"), zero)
    t.eq("an owner whose point doesn't resolve matches nothing: zeros", v("owner_unresolved"), zero)
    t.eq("an unknown component type has no value", v("unknown"), None)
    t.eq("the query's own point doesn't resolve: no value", v("near_unresolved"), None)


def ground(t, play):
    """A floor at y 0 with a hole at x 118-122, a hill (y 2), a roof (y 5), a trigger, a pane on the Ignore Raycast
    layer, a 2D collider at y 3, a collider below -2000 under the hole; the player stands on its own floor."""
    v = lambda qid: play.value(qid, 0.5)
    for qid, y in (("floor", 0), ("hill", 2), ("roof", 5), ("roof_through", 0), ("fog", 0), ("pane", 0), ("hero", 0),
                   ("plate", 0)):
        close(t, f"{qid}: height", v(qid), {"height": y, "hit": 1})
    t.eq("the hole: nothing within 2000 m", v("hole"), {"height": None, "hit": 0})
    box = {"min": 0, "max": 5, "mean": 0.4375, "range": 5, "hits": 64, "points": 64}
    close(t, "a box on the default 8 x 8 lattice, corners and edges included", v("box"), box)
    close(t, "the box's corners in either order", v("box_reversed"), box)
    corners = {"min": 0, "max": 5, "mean": 1.75, "range": 5, "hits": 4, "points": 4}
    close(t, "grid 2: the four corners", v("grid2"), corners)
    close(t, "grid 1 is 2", v("grid1"), corners)
    close(t, "grid 40 is 32 (4 columns of 32 fall in the hole)", v("grid40"),
          {"min": 0, "max": 5, "mean": 0.5, "range": 5, "hits": 896, "points": 1024})
    t.eq("grid 7.6 rounds to 8", (v("grid_fraction") or {}).get("points"), 64)
    close(t, "select: only the floor is ground, the roof and the hill are traced through", v("box_select"),
          {"min": 0, "max": 0, "mean": 0, "range": 0, "hits": 64, "points": 64})
    t.eq("a select of an unknown type: nothing is ground", v("unknown"), {"height": None, "hit": 0})
    for qid in ("no_place", "short_box", "long_xz"):
        t.eq(f"{qid}: no place, no value", v(qid), None)


PLACE = "a ground query takes xz \\[x, z\\] or box \\[x0, z0, x1, z1\\] \\(null values\\)"
PLAYS = {
    "camera": {"check": camera},
    "camera_none": {"check": camera_none},
    "camera_ortho": {"check": camera_ortho, "args": ["-wldOrtho"], "errors": [r"^camera camera_field: no field zoom$"]},
    "spawns": {"check": spawns, "errors": [r"^spawns unknown: no component type NoSuchType$",
                                           r"^spawns nameless: no component named$"]},
    "pieces": {"check": pieces, "errors": [r"^pieces unknown: no component type NoSuchType$"]},
    "ground": {"check": ground, "errors": [r"^ground unknown: no component type NoSuchType$", "^ground no_place: " + PLACE + "$",
                                           "^ground short_box: " + PLACE + "$", "^ground long_xz: " + PLACE + "$"]},
}
