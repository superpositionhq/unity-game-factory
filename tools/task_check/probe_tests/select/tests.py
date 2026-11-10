"""The select family: object selects (every key alone and together, points, `near`, `has`, the depth limit, the
probe's own objects), the order matches come in, `prop:` paths, rows past 200 with `total` and `full`, JSON in and out
(numbers, a decimal-comma locale, a deep spec), and what a select costs on a large scene."""

import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

MADE = "Assets/ProbeTests/select/Made/"
SETUP = ["ProbeTests.Select.SelScenes.Build"]
SCENES = [MADE + "SelSide.unity", MADE + "SelLab.unity", MADE + "SelBig.unity"]  # SelSide first: a lower build index
FLOAT = 1e-5  # a float of the game widened to a double


def names(play, qid, t=1.0):
    return [r.get("name") for r in play.rows(qid, t)]


def same(t, what, got, want):
    """The rows' names, in any order (the order of roots in one scene is the player's: see `order`)."""
    t.eq(what, sorted(got), sorted(want))


def keys(t, play):
    """Each key of an object select alone and with others, every point form, `has`, the depth limit, and the probe's
    own objects (never a row)."""
    t.eq("component: a short name two scripts share takes both", names(play, "twin"), ["TwinA", "TwinB"])
    t.eq("and each reads its own", [r.get("prop:SelTwin.which") for r in play.rows("twin", 1.0)], [1, 2])
    t.eq("component: a full name takes one", names(play, "twin_full"), ["TwinB"])
    t.eq("that one's prop:SelTwin reads it", play.row("twin_full", 1.0, "TwinB").get("prop:SelTwin.which"), 2)
    same(t, "component: an interface takes the scripts implementing it (the additive scene's and clones too)",
         names(play, "pickup"), ["Coin1", "Coin2", "CoinT", "CoinT(Clone)", "CoinT(Clone)", "SideCoin"])
    same(t, "has.component: an interface, on the object or a descendant (Coins by its children)", names(play, "pickup_has"),
         ["Coin1", "Coin2", "CoinT", "Coins"])
    same(t, "component: a base type takes the types derived from it", names(play, "base"), ["Based", "Derived", "PropsKid"])
    t.eq("component: a nested type by its own name", names(play, "nested"), ["Nester"])
    same(t, "tag", names(play, "tag"), ["Tagged1", "Tagged2"])
    t.eq("a tag the project doesn't define matches nothing", names(play, "tag_undefined"), [])
    t.eq("layer by name", names(play, "layer"), ["Layered"])
    t.eq("a layer's number is not its name", names(play, "layer_number"), [])
    t.eq("a layer's name in another case is not its name", names(play, "layer_case"), [])
    t.eq("layer and name together", names(play, "layer_default"), [])
    same(t, "name: a wildcard, any case", names(play, "name_lamp"), ["Lamp (1)", "Lamp.Post", "LampXPost", "lamp_low", "LAMP_HIGH"])
    t.eq("name: ? is one character, parentheses are themselves", names(play, "name_one"), ["Lamp (1)"])
    t.eq("name: a dot is a dot", names(play, "name_dot"), ["Lamp.Post"])
    t.eq("name: any case", names(play, "name_case"), ["lamp_low"])
    t.eq("name: other scripts' letters (an escaped \\u in the spec)", names(play, "name_unicode"), ["Snö☃"])
    t.eq("a clone's name ends in (Clone): the template alone", names(play, "clone_exact"), ["CoinT"])
    same(t, "the template and its clones", names(play, "clone_any"), ["CoinT", "CoinT(Clone)", "CoinT(Clone)"])
    t.eq("the clones alone", names(play, "clone_only"), ["CoinT(Clone)", "CoinT(Clone)"])
    t.eq("inactive objects don't match", names(play, "sleeper"), [])
    t.eq("with inactive: true they do, in hierarchy order", names(play, "sleeper_all"), ["Sleeper", "SleeperKid"])
    t.eq("and read active 0", [r.get("active") for r in play.rows("sleeper_all", 1.0)], [0, 0])
    t.eq("an inactive child of an active object", names(play, "napper"), [])
    t.eq("with inactive: true", names(play, "napper_all"), ["Napper"])
    same(t, "near a point: within the radius, its edge included", names(play, "near_xyz"), ["Near_0", "Near_1", "Near_3"])
    same(t, "near with y_min", names(play, "near_ymin"), ["Near_1", "Near_2"])
    same(t, "near with y_max", names(play, "near_ymax"), ["Near_0", "Near_3"])
    same(t, "near with y_max relative to the point's y", names(play, "near_relative"), ["Near_0", "Near_3"])
    t.eq("near the player's point with an offset", names(play, "near_player"), ["Near_0"])
    t.eq("near the camera's point, forward along its view", names(play, "near_camera"), ["CamMark"])
    same(t, "near an object's point", names(play, "near_object"), ["Near_Anchor", "NearObj"])
    t.eq("near an object's point with an offset", names(play, "near_offset"), ["Near_0"])
    t.eq("a point whose object matches nothing: nothing is near it", names(play, "near_nothing"), [])
    t.eq("a near without a point matches nothing", names(play, "near_no_point"), [])
    same(t, "two selects nested inside a select's points resolve", names(play, "nest2"), ["Near_Anchor", "NearObj"])
    t.eq("a third doesn't (the depth limit)", names(play, "nest3"), [])
    same(t, "has.lit: a Light that is on (not one at intensity 0, not a disabled one)", names(play, "has_lit"),
         ["Light_On", "Light_On_Bulb"])
    same(t, "has.visible: a drawn renderer (not a disabled one)", names(play, "has_visible"), ["Shown", "Shown_Mesh"])
    same(t, "has.component: the object and its child that carries it", names(play, "has_component"), ["Carrier", "CarrierLamp"])
    same(t, "has.near: a part's own place, not its object's", names(play, "has_near"), ["Holder", "Far_Part"])
    t.eq("has.near: an object with nothing but its transform is near too", names(play, "has_transform"), ["EmptyNear"])
    same(t, "has.simulating: a body that isn't kinematic, 3D or 2D (not one on an inactive child)",
         names(play, "has_simulating"), ["Crate", "Crate_Body", "Flat2D", "Flat2D_Body"])
    same(t, "the same with inactive: true (an inactive body simulates nothing)", names(play, "has_simulating_inactive"),
         ["Crate", "Crate_Body", "Flat2D", "Flat2D_Body"])
    t.eq("has.movable is no key (read as any unknown key: ignored)", names(play, "has_movable"), ["Statue"])
    t.eq("an object saved Static reads isStatic 0 in the player", play.row("statics", 1.0, "Statue").get("prop:isStatic"), 0)
    t.eq("as does one that isn't", play.row("pawns", 1.0, "Pawn").get("prop:isStatic"), 0)
    t.eq("player", names(play, "player"), ["SelHero"])
    t.eq("player and a name it doesn't have", names(play, "player_named"), [])
    t.eq("the probe's tap on the listener is no component of the game's", names(play, "own_tap"), [])
    t.eq("nor a part", names(play, "own_has_tap"), [])
    camera = play.row("own_prop", 1.0, "Main Camera") or {}
    t.ok("nor read by prop:", "prop:AudioTap.enabled" not in camera, camera)
    t.eq("while the listener is", camera.get("prop:AudioListener.enabled"), 1)
    t.eq("the probe's hidden camera is no camera of the game's", names(play, "own_cameras"), ["Main Camera"])
    t.eq("no object of the probe's matches a name", names(play, "own_names"), [])
    sample = play.sample("everything", 1.0)
    t.ok("a select with no keys matches everything: more than 200", sample.get("total", 0) > 300, sample.get("total"))
    t.ok("and no row is the probe's", not [n for n in names(play, "everything") if n.startswith("TaskProbe")])
    t.eq("a ground select of a type no component can be: nothing is ground", play.value("unknown_ground", 1.0),
         {"height": None, "hit": 0})
    t.eq("nor of a has.component no type has", play.value("unknown_has", 1.0), {"height": None, "hit": 0})
    t.ok("an undefined tag puts no line in the game's log", "NoSuchTag" not in play.log, play.log.count("NoSuchTag"))


def _yaml_text(raw):
    r"""A name as a saved scene or prefab writes it: plain, single-quoted ('' for a quote; Unity quotes a name that starts
    with a sign such as > or ends in a space) or double-quoted with escapes (Unity saves "Snö☃" as
    "Sn\xF6\u2603")."""
    if len(raw) >= 2 and raw[0] == raw[-1] == "'":
        return raw[1:-1].replace("''", "'")
    if len(raw) >= 2 and raw[0] == raw[-1] == '"':
        return raw[1:-1].encode("ascii", "backslashreplace").decode("unicode_escape")
    return raw


def _fileids(project, scene, wanted):
    """{GameObject name: its fileID} for `wanted` names in a saved scene, and the scene's root list as SceneRoots holds it
    (the Hierarchy's order) as names."""
    text = (project / scene).read_text(encoding="utf-8")
    ids, transforms = {}, {}
    for block in re.split(r"(?m)^--- ", text):
        head = re.match(r"!u!(\d+) &(-?\d+)", block)
        if not head:
            continue
        kind, fid = head.group(1), int(head.group(2))
        if kind == "1":
            name = re.search(r"(?m)^  m_Name: (.*)$", block)
            if name and _yaml_text(name.group(1)) in wanted:
                ids[_yaml_text(name.group(1))] = fid
        elif kind == "4":
            go = re.search(r"m_GameObject: \{fileID: (-?\d+)\}", block)
            transforms[fid] = int(go.group(1)) if go else None
    roots = re.search(r"SceneRoots:\s+m_ObjectHideFlags: \d+\s+m_Roots:((?:\s+- \{fileID: -?\d+\})*)", text)
    by_id = {v: k for k, v in ids.items()}
    hierarchy = [by_id.get(transforms.get(int(f))) for f in re.findall(r"fileID: (-?\d+)", roots.group(1))] if roots else []
    return ids, [n for n in hierarchy if n]


MASK = (1 << 63) - 1


def _documents(text):
    """(class id, file id, stripped, text) of each object of a saved scene or prefab."""
    for block in re.split(r"(?m)^--- ", text):
        head = re.match(r"!u!(\d+) &(-?\d+)( stripped)?", block)
        if head:
            yield int(head.group(1)), int(head.group(2)), bool(head.group(3)), block


def _ref(block, field):
    found = re.search(field + r": \{fileID: (-?\d+)", block)
    return int(found.group(1)) if found else None


def _saved_roots(project, scene, prefab):
    """The roots of a saved scene, each {name, class (4 Transform, 224 RectTransform), id (its transform's file id)}; a
    prefab instance's root (of `prefab`) has instead its PrefabInstance's file id, its stripped transform's if the file
    has one, and (instance id ^ the prefab object's id) & MASK for its transform and GameObject."""
    gos, roots = {}, []
    docs = list(_documents((project / scene).read_text(encoding="utf-8")))
    for kind, fid, _, block in docs:
        if kind == 1:
            gos[fid] = _yaml_text(re.search(r"(?m)^  m_Name: (.*)$", block).group(1))
    for kind, fid, stripped, block in docs:
        if kind in (4, 224) and not stripped and _ref(block, "m_Father") == 0:
            roots.append({"name": gos[_ref(block, "m_GameObject")], "class": kind, "id": fid})
    source = {}
    for kind, fid, _, block in _documents((project / prefab).read_text(encoding="utf-8")):
        source.setdefault(kind, []).append((fid, block))
    top_tr, top_go = next((fid, _ref(block, "m_GameObject")) for fid, block in source[4] if _ref(block, "m_Father") == 0)
    strips = {_ref(block, "m_PrefabInstance"): fid for kind, fid, strip, block in docs
              if strip and kind == 4 and _ref(block, "m_CorrespondingSourceObject") == top_tr}
    for kind, fid, _, block in docs:
        if kind == 1001 and _ref(block, "m_TransformParent") == 0:
            name = _yaml_text(re.search(r"propertyPath: m_Name\s+value: (.*)", block).group(1))
            roots.append({"name": name, "class": 4, "instance": fid, "stripped": strips.get(fid),
                          "xor": (fid ^ top_tr) & MASK, "xor_go": (fid ^ top_go) & MASK})
    return roots


ROOT_RULES = {  # candidate keys for the player's root list, a prefab instance's root by ...
    "its PrefabInstance's id": lambda r: (r["class"], r.get("id", r.get("instance"))),
    "instance id ^ prefab transform id": lambda r: (r["class"], r.get("id", r.get("xor"))),
    "instance id ^ prefab GameObject id": lambda r: (r["class"], r.get("id", r.get("xor_go"))),
    "its stripped transform's id": lambda r: (r["class"], r.get("id", r.get("stripped") or 0)),
    "after the scene's own roots, by its PrefabInstance's id": lambda r: ("id" not in r, r["class"],
                                                                         r.get("id", r.get("instance"))),
}


def order(t, play):
    """The order matches come in, as the Hierarchy window lists a playing game: the scenes in the order they were
    loaded, the DontDestroyOnLoad scene last; in a scene its roots in the player's root list, sibling order below;
    objects made at run time; several components of one object; more matches than the rows hold."""
    rows = play.rows("roots", 0.5)
    got = [r["name"] for r in rows]
    t.eq("four roots of one scene", sorted(got), ["Root_A", "Root_B", "Root_C", "Root_D"])
    t.eq("in the order of the player's root list", [r.get("prop:SelRootInfo.rootIndex") for r in rows],
         sorted(r.get("prop:SelRootInfo.rootIndex") for r in rows))
    ids, hierarchy = _fileids(t.project, MADE + "SelLab.unity", set(got))
    t.eq("which is the order of their fileIDs in the saved scene", got, sorted(got, key=lambda n: ids.get(n, 0)))
    t.ok("(the Hierarchy's order, from the scene's SceneRoots: " + ", ".join(hierarchy) + ")", True)
    saved = _saved_roots(t.project, MADE + "SelLab.unity", MADE + "SelRootPrefab.prefab")
    named = {r["name"] for r in saved}
    listed = [n for n in ((play.row("scenes", 0.5, "Root_A") or {}).get("prop:SelRootInfo.roots") or "").split("|")
              if n in named]
    t.eq("the player's root list of a scene: every root saved in it but Keeper (gone to the DontDestroyOnLoad scene) and "
         "Doomed (destroyed at the start)", sorted(named - set(listed)), ["Doomed", "Keeper"])
    held = [rule for rule, key in ROOT_RULES.items()
            if [r["name"] for r in sorted(saved, key=key) if r["name"] in listed] == listed]
    t.ok("the roots with a Transform by its file id, then the UI roots (a RectTransform) by theirs; a prefab instance's "
         "root by: " + (", ".join(held) or "none of the rules tried"), held,
         {"listed": listed, "roots": saved} if not held else None)
    t.eq("every root reports sibling index 0 in a player", [r.get("prop:SelRootInfo.sibling") for r in rows], [0, 0, 0, 0])
    t.eq("children in sibling order", names(play, "kids", 0.5), ["Kid_C", "Kid_A", "Kid_B"])
    early, late = names(play, "scenes", 0.5), names(play, "scenes", 2.0)
    t.eq("the DontDestroyOnLoad scene last, after the scene loaded additively after SelLab", early[-2:], ["Side_Root", "Keeper"])
    side, lab = play.row("scenes", 0.5, "Side_Root") or {}, play.row("scenes", 0.5, "Root_A") or {}
    t.ok("(which has the lower build index: scenes come in the order they were loaded, not by build index)",
         side.get("prop:SelRootInfo.buildIndex", 99) < lab.get("prop:SelRootInfo.buildIndex", -1), (side, lab))
    keeper = play.row("scenes", 0.5, "Keeper") or {}
    t.eq("(it is in no place of SceneManager's list; its build index is -1)",
         (keeper.get("prop:SelRootInfo.sceneAt"), keeper.get("prop:SelRootInfo.buildIndex")), (-1, -1))
    t.eq("before 1 s: no Late_Root, Moved_Child under its parent", [n for n in early if n in ("Late_Root", "Moved_Child")],
         ["Moved_Child"])
    roots = [r for r in play.rows("scenes", 2.0) if r["name"] not in ("Side_Root", "Keeper")]
    t.eq("at 2 s, the roots of SelLab in the order of the player's root list", [r.get("prop:SelRootInfo.rootIndex") for r in roots],
         sorted(r.get("prop:SelRootInfo.rootIndex") for r in roots))
    t.eq("a root made at run time and a child made a root come after the saved roots, in that order",
         [r["name"] for r in roots][-2:], ["Late_Root", "Moved_Child"])
    bursts = names(play, "bursts", 1.5)
    t.eq("roots made in the frame of a sample, after an input searched before the game's scripts: in the order made",
         bursts, sorted(bursts, key=lambda n: int(n.split("_")[1])))
    t.ok("(one was made in that frame)", len(bursts) >= 3, bursts)
    t.eq("components of one type on one object: in the Inspector's order",
         [r.get("extent_x") for r in play.rows("two_boxes", 1.0)], [0.5, 1.5])
    sample = play.sample("fill", 1.0)
    t.eq("300 matches: the first 200 rows kept, in sibling order", names(play, "fill"), [f"Fill_{i:03d}" for i in range(200)])
    t.eq("total", sample.get("total"), 300)
    full = sample.get("full") or {}
    t.eq("full: every field asked for, in the order asked", list(full), ["x", "prop:SelProps.f", "active"])
    t.eq("full.x over every match", full.get("x"), {"n": 300, "nonzero": 299, "sum": 44850, "min": 0, "max": 299})
    t.eq("full of a field no match has a number for", full.get("prop:SelProps.f"),
         {"n": 0, "nonzero": 0, "sum": 0, "min": None, "max": None})
    t.eq("full of a 0/1 field", full.get("active"), {"n": 300, "nonzero": 300, "sum": 300, "min": 1, "max": 1})
    count = play.sample("fill_count", 1.0)
    t.eq("a count (no fields): 200 rows, total 300, an empty full",
         (len(count.get("rows") or []), count.get("total"), count.get("full")), (200, 300, {}))


HARD = 0.84551240822557006


def _props_expected():
    p = "prop:SelProps."
    want = {
        p + "f": 1.5, p + "d": 0.1, p + "third": 1.0 / 3.0, p + "hard": HARD, p + "i": -3, p + "big": 9007199254740992.0,
        p + "huge": 18446744073709551615.0, p + "u": 4000000000, p + "s": -7, p + "b": 200, p + "sb": -100,
        p + "money": 12.25, p + "c": "x", p + "on": 1, p + "text": "Lamp (1) \"q\" \\ é ✓ \U0001F600\n\ttab",
        p + "empty": "", p + "nothing": "", p + "mode": 9, p + "flags": 5, p + "v.y": 2, p + "col.b": 0.75,
        p + "q.w": 0.7071067690849304, p + "pair.a": 2.5, p + "pair.b": 3, p + "arr": 3, p + "arr[1]": 5, p + "list": 2,
        p + "list[1]": 8, p + "points[1].y": 4, p + "counts": 1, p + "counts.coins": 3, p + "set": 3, p + "target": 1,
        p + "target.transform.position.y": 0.5, p + "none": 0, p + "gone": 0, p + "data": 1, p + "data.size": 4,
        p + "noData": 0, p + "negZero": 0, p + "e21": 1e21, p + "small": 1e-07, p + "fmax": 3.4028234663852886e38,
        p + "priv": 17, p + "hidden": 11, p + "guarded": 12, p + "inherited": 13, p + "Getter": -6,
        "prop:SelProps": 1, "prop:SelBase.level": 5, "prop:name": "Props", "prop:activeSelf": 1, "prop:localScale.y": 1,
        "prop:position.x": -62, "prop:isStatic": 0,
    }
    absent = [p + f for f in ("v", "arr[5]", "arr.[0]", "counts.missing", "none.position.x", "nan", "inf", "ninf",
                              "stat", "Throws", "Item", "missing", "target.transform" + ".root" * 14 + ".position.x")] + ["prop:NoSuch"]
    return want, absent


def props(t, play):
    """prop: paths: every kind of member and value; a read never copies an asset; a deep spec is refused, not a crash."""
    row = play.row("props", 1.0, "Props") or {}
    want, absent = _props_expected()
    for field, value in want.items():
        t.eq(field, row.get(field), value)
    for field in absent:
        t.ok(f"{field} has no value", field not in row, row.get(field))
    clocks = [(play.row("props", s, "Props") or {}).get("prop:SelProps.clock") for s in (0.5, 1.0)]
    t.near("a double the game sets every frame (Time.time) moves 0.5 s from sample to sample", clocks[1] - clocks[0], 0.5, 1e-4)
    counted = [r.get("prop:SelProps.Counted") for r in (play.row("props", s, "Props") for s in (0.5, 1.0, 1.5))]
    t.eq("a getter runs at each read, once a sample (its side effects happen)", counted, [counted[0], counted[0] + 1, counted[0] + 2])
    paint = play.row("paint", 1.5, "Painted") or {}
    t.eq("material is read as sharedMaterial: no copy", paint.get("prop:MeshRenderer.material.name"), "Lit")
    t.eq("materials as sharedMaterials", paint.get("prop:MeshRenderer.materials"), 1)
    t.eq("materials[0] as sharedMaterials[0]", paint.get("prop:MeshRenderer.materials[0].name"), "Lit")
    t.eq("mesh as sharedMesh", paint.get("prop:MeshFilter.mesh.name"), "Cube")
    t.eq("a collider's material as its sharedMaterial (none)", paint.get("prop:BoxCollider.material"), 0)
    t.eq("the renderer still draws the shared material", paint.get("prop:SelPaint.sharedMaterialName"), "Lit")
    t.eq("no material instance", paint.get("prop:SelPaint.instancedMaterials"), 0)
    t.eq("the filter still holds the shared mesh", paint.get("prop:SelPaint.sharedMeshName"), "Cube")
    t.eq("the collider got no physics material", paint.get("prop:SelPaint.colliderMaterial"), 0)
    text = play.row("text_like", 1.5, "TextLike") or {}
    t.eq("fontMaterial (as TextMeshPro has it) as fontSharedMaterial", text.get("prop:SelTextLike.fontMaterial.name"), "Lit")
    t.eq("its copying getter never ran", text.get("prop:SelTextLike.copies"), 0)
    t.eq("the culture is the machine's", (play.row("locale", 1.0, "Locale") or {}).get("prop:SelLocale.separator"), ".")
    _deep(t)


def _deep(t):
    """A spec nested 100,000 deep: the player says it can't read it and ends with exit code 2 (no stack overflow, which
    no catch stops)."""
    exe = t.project / "Build" / "TaskProbe" / "Game.exe"
    folder = Path(tempfile.mkdtemp(prefix="seldeep"))
    spec = folder / "deep.json"
    spec.write_text('{"format": "unity-probe-play/1", "out": ' + json.dumps(str(folder)) + ', "deep": '
                    + "[" * 100000 + "]" * 100000 + "}", encoding="utf-8")
    log = folder / "play.log"
    from task_check import unity  # the checker's own module (run.py has loaded it): where its desk.py is
    desk = unity.DESK
    try:
        ran = subprocess.run([sys.executable, str(desk), str(exe), "-screen-fullscreen", "0", "-screen-width", "960",
                              "-screen-height", "540", "-logFile", str(log), "-taskProbe", str(spec)], cwd=str(exe.parent),
                             timeout=60)
        code = ran.returncode - (1 << 32) if ran.returncode >= 1 << 31 else ran.returncode
    except subprocess.TimeoutExpired:
        code = "still running after 60 s"
    text = log.read_text(encoding="utf-8", errors="replace") if log.is_file() else ""
    t.eq("a spec nested 100,000 deep: exit code", code, 2)
    t.ok("and the player says why it can't read it",
         "couldn't be read: JSON: nested deeper than 512" in text, text[-400:])
    t.ok("and doesn't crash", not re.search(r"Crash!!!|OUTPUTTING STACK TRACE|Fatal error", text), text[-400:])


def locale(t, play):
    """The same reads in a game that runs in a decimal-comma culture (de-DE): every value is the same."""
    t.eq("the game's culture writes a decimal comma", (play.row("locale", 1.0, "Locale") or {}).get("prop:SelLocale.separator"), ",")
    before = play.earlier("props")
    for qid, name in (("props", "Props"), ("paint", "Painted"), ("text_like", "TextLike")):
        for when in (0.5, 1.0, 1.5):
            t.eq(f"{qid} at {when} s as in the props play", play.row(qid, when, name), before.row(qid, when, name))


def _cost(play, qid="timer"):
    """(ms the probe's late half took a frame, mean; ms its update half took; KB the heap grew in the late half a
    frame) over the play, from SelLateAfter/SelEarlyAfter."""
    samples = play.samples(qid)
    last = ((samples[-1].get("rows") or [{}])[0]) if samples else {}
    late = last.get("prop:SelLateAfter.totalMs", 0) / max(last.get("prop:SelLateAfter.frames", 1), 1)
    early = last.get("prop:SelEarlyAfter.totalMs", 0) / max(last.get("prop:SelEarlyAfter.frames", 1), 1)
    alloc = last.get("prop:SelLateAfter.allocKb", 0) / max(last.get("prop:SelLateAfter.frames", 1), 1)
    return late, early, alloc, len(samples)


def _per_sample(t, play, what, bound):
    """The probe's work per sample (ms): the late half's time over the play minus the idle play's, per sample."""
    late, early, alloc, samples = _cost(play)
    idle = _cost(play.earlier("cost_idle"))
    frames = 5 * 30
    ms = (late - idle[0]) * frames / max(samples, 1)
    kb = (alloc - idle[2]) * frames / max(samples, 1)
    t.ok(f"{what}: {ms:.1f} ms a sample (bound {bound} ms), heap grew about {kb:.0f} KB a sample", ms < bound, ms)
    return ms


def cost_idle(t, play):
    """The crowd of 3000 with no query but the timer's own: the baseline."""
    late, early, alloc, samples = _cost(play)
    t.ok(f"idle: {late:.3f} ms a frame in the late half, {early:.3f} ms in the update half", late < 5, late)


def cost3k_all(t, play):
    """A select with no keys over 3000 objects, every 0.1 s."""
    t.eq("every object matched", play.sample("all", 1.0).get("total"), 3000 + 4)
    _per_sample(t, play, "objects select {} over 3000 objects, field x", 60)


def cost3k_mark(t, play):
    """A component select over 3000 objects (300 carry it)."""
    t.eq("300 matched", play.sample("marks", 1.0).get("total"), 300)
    _per_sample(t, play, "objects select {component: SelMark} over 3000 objects (300 match)", 20)


def cost3k_spawns(t, play):
    """spawns of a component 300 of 3000 objects carry, counted every frame."""
    _spawns_cost(t, play, "spawns over 300 of 3000 objects", 5)


def _spawns_cost(t, play, what, bound):
    late, early, alloc, samples = _cost(play)
    idle = _cost(play.earlier("cost_idle"))
    ms = early - idle[1]
    t.ok(f"{what}: {ms:.2f} ms a frame (bound {bound} ms)", ms < bound, ms)
    t.eq("nothing spawned or went", play.value("spawns", 4.0), {"spawned": 0, "destroyed": 0})


def cost3k_interface(t, play):
    """spawns of an interface 300 of 3000 objects' scripts implement, counted every frame (the game's scripts are
    searched)."""
    _spawns_cost(t, play, "spawns of an interface over 300 of 3000 objects", 5)


def cost20k_interface(t, play):
    """spawns of an interface 2000 of 20,000 objects' scripts implement."""
    _spawns_cost(t, play, "spawns of an interface over 2000 of 20,000 objects", 20)


def cost20k_all(t, play):
    """A select with no keys over 20,000 objects."""
    t.eq("every object matched", play.sample("all", 1.0).get("total"), 20000 + 4)
    _per_sample(t, play, "objects select {} over 20,000 objects, field x", 400)


def cost20k_mark(t, play):
    """A component select over 20,000 objects (2000 carry it)."""
    t.eq("2000 matched", play.sample("marks", 1.0).get("total"), 2000)
    _per_sample(t, play, "objects select {component: SelMark} over 20,000 objects (2000 match)", 100)


def cost20k_spawns(t, play):
    """spawns of a component 2000 of 20,000 objects carry, counted every frame."""
    _spawns_cost(t, play, "spawns over 2000 of 20,000 objects", 20)


TIMED = ["timer"]  # real time: left out of the twice-the-same comparison
PLAYS = {
    "keys": {"check": keys, "errors": [r"^ground unknown_ground: no component type SelData$",
                                       r"^ground unknown_has: no component type NoSuchType$"]},
    "order": {"check": order},
    "props": {"check": props},
    "locale": {"check": locale, "args": ["-selLocale", "de-DE"]},
    "cost_idle": {"check": cost_idle, "args": ["-selCrowd", "3000"], "varies": TIMED},
    "cost3k_all": {"check": cost3k_all, "args": ["-selCrowd", "3000"], "varies": TIMED},
    "cost3k_mark": {"check": cost3k_mark, "args": ["-selCrowd", "3000"], "varies": TIMED},
    "cost3k_spawns": {"check": cost3k_spawns, "args": ["-selCrowd", "3000"], "varies": TIMED},
    "cost3k_interface": {"check": cost3k_interface, "args": ["-selCrowd", "3000"], "varies": TIMED},
    "cost20k_all": {"check": cost20k_all, "args": ["-selCrowd", "20000"], "varies": TIMED},
    "cost20k_mark": {"check": cost20k_mark, "args": ["-selCrowd", "20000"], "varies": TIMED},
    "cost20k_spawns": {"check": cost20k_spawns, "args": ["-selCrowd", "20000"], "varies": TIMED},
    "cost20k_interface": {"check": cost20k_interface, "args": ["-selCrowd", "20000"], "varies": TIMED},
}
