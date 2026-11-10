"""The asset family: the editor pass over the project as saved (TaskProbe.EditorTools.AssetPass: every field and error
of an `asset` measure, on assets, scenes and prefabs) and the player the checker builds (TaskProbe.EditorTools.Build),
as a play and the build's result show it."""

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[3]
MADE = "Assets/ProbeTests/asset/Made/"
SETUP = ["ProbeTests.Asset.AssetScenes.Build"]
SCENES = [MADE + "Facts.unity"]
FLOAT = 1e-5  # a float of the project widened to a double
LIT, UNLIT = "Universal Render Pipeline/Lit", "Universal Render Pipeline/Unlit"
RUNNING = "needs a running game"


def _tools():
    if str(TOOLS) not in sys.path:
        sys.path.insert(0, str(TOOLS))
    from task_check import probes, seeds, unity
    return probes, seeds, unity


def _equal(got, want):
    """A number within FLOAT of a float, an int exactly, anything else equal and of its type."""
    if isinstance(want, (int, float)) and not isinstance(want, bool):
        number = isinstance(got, (int, float)) and not isinstance(got, bool)
        return number and (abs(got - want) <= FLOAT if isinstance(want, float) else got == want)
    return type(got) is type(want) and got == want


def value(t, results, mid, want, what):
    """An asset measure's value."""
    found = results.get(mid)
    t.ok(f"{what} ({mid})", isinstance(found, dict) and set(found) == {"value"} and _equal(found["value"], want), found)


def error(t, results, mid, want, what):
    """An error, word for word (`want` ending in ...: its start)."""
    found = results.get(mid)
    text = found.get("error") if isinstance(found, dict) and set(found) == {"error"} else None
    ok = text is not None and (text.startswith(want[:-3]) if want.endswith("...") else text == want)
    t.ok(f"{what} ({mid}): {want}", ok, found)


def rows(t, results, mid, want, what):
    """A scene or prefab measure's rows, in order: [(name, value), ...]."""
    found = results.get(mid)
    got = found.get("rows") if isinstance(found, dict) and set(found) == {"rows"} else None
    ok = isinstance(got, list) and len(got) == len(want) and all(
        isinstance(r, dict) and set(r) == {"name", "value"} and r["name"] == n and _equal(r["value"], v)
        for r, (n, v) in zip(got, want))
    t.ok(f"{what} ({mid})", ok, got if got is not None else found)


def count(names):
    return [(n, 1) for n in names]


def saved(t, results):
    """Every measure of measures.json, as the editor pass read it; the pass opened each scene once, and what it loaded
    marked itself changed without anything being written back (the runner checks that no file changed)."""
    measures = json.loads((Path(__file__).resolve().parent / "measures.json").read_text(encoding="utf-8"))
    t.eq("one result per measure, no other", sorted(results), sorted(measures))
    assets(t, results)
    scenes(t, results)
    prefabs(t, results)

    log = (t.project / "Logs" / "TaskProbe" / "editor.log").read_text(encoding="utf-8", errors="replace")
    on = {where: sum(1 for x in measures.values() if isinstance(x, dict) and x.get("scene") == MADE + where)
          for where in ("Level.unity", "Big.unity")}
    t.eq(f"Big.unity (5,051 objects) was opened once for its {on['Big.unity']} measures", log.count("ASSET loaded BigMarker"), 1)
    t.eq(f"Level.unity was opened once for its {on['Level.unity']} measures", log.count("ASSET loaded Dirtier"), 1)
    t.ok("the ScriptableObject marked itself changed when the pass loaded it", "ASSET loaded Waves" in log)
    t.ok("the prefab marked itself changed when the pass loaded it", "ASSET loaded Dirty" in log)
    probes, _, _ = _tools()
    nonce = json.loads((t.project / probes.EDITOR_FILE).read_text(encoding="utf-8"))["nonce"]
    t.eq("the log's TASK_PROBES line carries the same result as the file", probes.editor_results(None, nonce, log), results)
    robust(t)


def assets(t, r):
    """`asset` measures: shader:, keyword:, import: and prop: on materials, a texture, a sound, a model, a
    ScriptableObject, an animator controller and prefabs; their errors; paths that aren't the project's."""
    m = MADE
    value(t, r, "a.road.smoothness", 0.75, "a float property")
    value(t, r, "a.road.metallic", 0.25, "another float property")
    value(t, r, "a.road.base_r", 0.2, "a colour's red, as stored")
    value(t, r, "a.road.base_b", 0.6, "a colour's blue")
    value(t, r, "a.road.base_x", 0.2, "a colour's first channel named .x")
    value(t, r, "a.road.emission_g", 0.5, "the emission colour's green")
    value(t, r, "a.road.base_map", 1, "a texture that is set: 1")
    value(t, r, "a.road.base_map_name", "Grass", "a texture's name")
    value(t, r, "a.road.shader", LIT, "shader:name, the shader's name")
    value(t, r, "a.road.emission", 1, "a keyword that is on")
    value(t, r, "a.road.alpha_test", 0, "a keyword that is off")
    value(t, r, "a.road.no_keyword", 0, "a keyword the shader hasn't")
    error(t, r, "a.road.base_whole", "_BaseColor is a colour: name a channel (_BaseColor.r, .g, .b or .a)", "a colour without a channel")
    error(t, r, "a.road.no_property", f"no shader property _Nope on {LIT} (Road)", "an unknown shader property")
    error(t, r, "a.road.float_name", "no name on the shader property _Smoothness", ".name of a float")
    error(t, r, "a.road.texture_channel", "no r on the shader property _BaseMap", "a channel of a texture")
    value(t, r, "a.road.queue", 2000, "prop: a material's member (renderQueue)")
    value(t, r, "a.road.shader_ref", 1, "prop: a serialized reference that is set (m_Shader)")
    value(t, r, "a.road.shader_name", LIT, "prop: through a reference (shader.name)")
    value(t, r, "a.road.importer", "", "import: a material's importer (userData)")
    value(t, r, "a.glow.alpha", 0.5, "an unlit colour's alpha")
    value(t, r, "a.glow.cutoff", 0.3, "a range property")
    value(t, r, "a.glow.base_map", 0, "a texture that is not set: 0")
    value(t, r, "a.glow.base_map_name", None, "the name of a texture that is not set: no value")
    value(t, r, "a.glow.alpha_test", 1, "a keyword that is on")
    value(t, r, "a.glow.shader", UNLIT, "shader:name")
    value(t, r, "a.fx.wind_z", 3, "a vector's z")
    value(t, r, "a.fx.wind_w", 4, "a vector's w")
    value(t, r, "a.fx.wind_r", 1, "a vector's first channel named .r")
    value(t, r, "a.fx.steps", 5, "an Integer property")
    value(t, r, "a.fx.tint_g", 1, "a colour left at the shader's default")
    value(t, r, "a.fx.shader", "ProbeTests/AssetParams", "shader:name of a shader of the project's own")
    error(t, r, "a.fx.wind_whole", "_Wind is a vector: name a channel (_Wind.x, .y, .z or .w)", "a vector without a channel")
    value(t, r, "a.broken.shader", "Hidden/InternalErrorShader", "the error shader's name")
    error(t, r, "a.broken.base", "no shader property _BaseColor on Hidden/InternalErrorShader (Broken)", "a property of the error shader")
    value(t, r, "a.spaces.smoothness", 0.5, "a path with a space and parentheses")
    value(t, r, "a.unicode.smoothness", 0.25, "a path with letters outside ASCII")
    value(t, r, "a.package.shader", LIT, "an asset of a package (Packages/...)")
    value(t, r, "a.tex.readable", 1, "import: a texture's bool")
    value(t, r, "a.tex.compression", 0, "import: an enum (TextureImporterCompression.Uncompressed)")
    value(t, r, "a.tex.max_size", 256, "import: an int")
    value(t, r, "a.tex.serialized", 1, "import: a serialized property of the importer (m_IsReadable)")
    error(t, r, "a.tex.no_setting", f"no import setting nope on TextureImporter {m}Grass.png", "an unknown import setting")
    value(t, r, "a.tex.width", 64, "prop: a texture's width")
    error(t, r, "a.tex.shader", f"{m}Grass.png is not a material (Texture2D)", "shader: on a texture")
    error(t, r, "a.tex.keyword", f"{m}Grass.png is not a material (Texture2D)", "keyword: on a texture")
    error(t, r, "a.tex.bogus", "unknown asset field bogus:x (prop:, import:, shader:, keyword:)", "an unknown field")
    value(t, r, "a.wav.mono", 1, "import: a sound's force to mono")
    value(t, r, "a.wav.load_type", 2, "import: a load type from the default sample settings (Streaming)")
    value(t, r, "a.wav.load_type_path", 2, "import: the same through its path")
    value(t, r, "a.wav.length", 0.2, "prop: a sound's length in seconds")
    value(t, r, "a.wav.channels", 1, "prop: a sound's channels after force to mono")
    value(t, r, "a.obj.scale", 2, "import: a model's global scale")
    value(t, r, "a.obj.animation", 0, "import: a model's animation type (None)")
    value(t, r, "a.obj.scale_serialized", 2, "import: a serialized property of a model's importer (m_GlobalScale)")
    value(t, r, "a.obj.name", "Box", "prop: a model's own object")
    value(t, r, "a.waves.level", 3, "prop: an int field")
    value(t, r, "a.waves.speed", 2.5, "prop: a float field")
    value(t, r, "a.waves.title", "Night", "prop: a string field")
    value(t, r, "a.waves.boss", 1, "prop: a bool field")
    value(t, r, "a.waves.difficulty", 4, "prop: an enum field reads its value (Hard = 4), not its index")
    value(t, r, "a.waves.waves", 3, "prop: a list is its length")
    value(t, r, "a.waves.third_count", 15, "prop: a list element's field")
    value(t, r, "a.waves.third_delay", 1.5, "prop: another field of it")
    value(t, r, "a.waves.tint_g", 0.2, "prop: a colour's channel")
    value(t, r, "a.waves.tint", None, "prop: a colour without a channel: no value")
    value(t, r, "a.waves.skin", 1, "prop: a reference that is set: 1")
    value(t, r, "a.waves.skin_name", "Road", "prop: through a reference")
    value(t, r, "a.waves.none", 0, "prop: a reference that is not set: 0")
    value(t, r, "a.waves.secret", 7, "prop: a private field")
    value(t, r, "a.waves.name", "Waves", "prop: a SerializedObject path (m_Name)")
    value(t, r, "a.waves.array_size", 3, "prop: a SerializedObject array path (waves.Array.size)")
    value(t, r, "a.waves.nan", None, "prop: NaN as saved: no value")
    value(t, r, "a.waves.inf", None, "prop: infinity as saved: no value")
    value(t, r, "a.waves.curve", 1, "prop: an AnimationCurve, an object that is set: 1")
    value(t, r, "a.waves.curve_keys", 3, "prop: an AnimationCurve's keys")
    value(t, r, "a.waves.past_unset", None, "prop: a step past a reference that is not set: no value, not an error")
    value(t, r, "a.waves.past_end", None, "prop: an index past a list's end: no value, not an error")
    error(t, r, "a.waves.unknown", f"no property nothing on AssetWaveSet {m}Waves.asset", "an unknown member")
    error(t, r, "a.waves.unknown_deeper", f"no property waves[1].nothing on AssetWaveSet {m}Waves.asset", "an unknown member of an element")
    error(t, r, "a.waves.index_of_number", f"no property speed[0] on AssetWaveSet {m}Waves.asset", "an index on a number")
    value(t, r, "a.anim.parameters", 2, "prop: an animator controller's parameters")
    value(t, r, "a.anim.second", "Run", "prop: one parameter's name")
    value(t, r, "a.anim.layer", "Base Layer", "prop: its first layer's name")
    value(t, r, "a.lamp.speed", 90, "prop: a prefab read as an object: its component's member")
    value(t, r, "a.lamp.light", 3, "prop: the first Light in the prefab's descendants")
    value(t, r, "a.lamp.name", "Lamp", "prop: the prefab's root, a SerializedObject path (m_Name)")
    value(t, r, "a.lamp.material", "Road", "prop: MeshRenderer.material read as the shared one (no copy)")
    value(t, r, "a.lamp.mesh", "Cylinder", "prop: MeshFilter.mesh read as the shared one (no copy)")
    value(t, r, "a.lamp.position", None, "prop: a vector without a channel: no value")
    error(t, r, "a.lamp.unknown", f"no property AssetSpinner.nothing on GameObject {m}Lamp.prefab", "an unknown member on a prefab")
    value(t, r, "a.lamp.target_name", None, "prop: a step past a component's reference that is not set: no value")
    value(t, r, "a.variant.speed", 120, "prop: a prefab variant's override")
    found = (r.get("a.dirty.loads") or {}).get("value")
    t.ok("prop: a prefab whose component changes itself when it loads still reads (a.dirty.loads)",
         isinstance(found, (int, float)) and found >= 1, r.get("a.dirty.loads"))
    error(t, r, "a.missing", f"no asset {m}Missing.mat", "an asset that isn't there")
    error(t, r, "a.guard.settings", "no asset Assets/../ProjectSettings/ProjectSettings.asset", "a path climbing out of Assets/")
    error(t, r, "a.guard.inside", f"no asset Packages/../{m}Road.mat", "a path with .. even when it lands inside")
    error(t, r, "a.guard.backslash", "no asset " + (m + "Road.mat").replace("/", "\\"), "a path with backslashes")
    error(t, r, "a.guard.absolute", "no asset C:/Windows/win.ini", "a path outside the project")
    error(t, r, "a.not_object", "not an asset measure", "a measure that isn't an object")
    error(t, r, "a.no_target", "an asset measure needs `asset`, `scene` or `prefab`", "a measure without a place")


def scenes(t, r):
    """`scene` measures: selects (tag, name, inactive, layer, component, near) over a saved scene with prefab
    instances, a variant, a nested prefab, a prefab that is gone and a material that is gone; every field; the errors;
    two more scenes in the same pass (one of 5,051 objects)."""
    m = MADE
    terraces = ["Terrace_A", "Terrace_B", "Terrace_D"]
    rows(t, r, "s.tag", count(terraces), "a tag, active objects only, in hierarchy order")
    rows(t, r, "s.tag_inactive", count(["Terrace_A", "Terrace_B", "Terrace_C", "Terrace_D"]), "a tag with inactive: true")
    rows(t, r, "s.name_wild", count(terraces), "a name wildcard")
    rows(t, r, "s.name_case", count(["Terrace_A"]), "a name in another case")
    rows(t, r, "s.inactive_out", [], "an inactive object without inactive: true")
    rows(t, r, "s.inactive_in", count(["Terrace_C"]), "an inactive object with inactive: true")
    rows(t, r, "s.unknown_tag", [], "a tag the project doesn't have")
    rows(t, r, "s.layer", count(["Lamp"]), "a layer")
    rows(t, r, "s.component", count(["LightSrc"] * 3), "a component (the lamp's, the variant's, the nested lamp's)")
    rows(t, r, "s.spinners", [("Lamp", 90), ("FanObj", 45), ("Variant", 120), ("Lamp", 90)],
         "prop: on every match of a component select (a prefab instance, a plain object, a variant, a nested prefab)")
    rows(t, r, "s.near", count(["Terrace_A", "Terrace_B", "Lamp", "Pole", "Bulb", "Base", "LightSrc"]), "near a point")
    rows(t, r, "s.near_high", count(["Bulb", "LightSrc"]), "near a point with y_min")
    rows(t, r, "s.near_band", count(["Pole", "Bulb", "LightSrc"]), "near another point with y_min")
    rows(t, r, "s.near_relative", count(["Bulb", "LightSrc"]), "the same with y_relative")
    rows(t, r, "s.near_object", count(["FxQuad"]), "near an object of the same scene, with an offset")
    rows(t, r, "s.near_nothing", [], "near an object the scene hasn't: nothing")
    rows(t, r, "s.default_terraces", [("Terrace_A", 0), ("Terrace_B", 1), ("Terrace_C", 0), ("Terrace_D", 1)],
         "material_default: own material, the pipeline's default, inactive, an empty slot")
    rows(t, r, "s.default_broken", [("Broken", 1)], "material_default: the error shader")
    rows(t, r, "s.default_lamps", [("Lamp", 1), ("Lamp", 1)], "material_default: a child with the default material")
    rows(t, r, "s.default_poles", [("Pole", 0)] * 3, "material_default: a clean object")
    rows(t, r, "s.default_group", [("Group", 0)], "material_default: clean descendants")
    rows(t, r, "s.default_two_parts", [("TwoParts", 1)], "material_default: a mesh part without a slot")
    rows(t, r, "s.default_lost", [("Lost", 1)], "material_default: a material that is gone")
    rows(t, r, "s.material_base_r", [("Terrace_A/Terrace_A", 0.2)], "material: a colour's channel")
    rows(t, r, "s.material_map_name", [("Terrace_A/Terrace_A", "Grass")], "material: a texture's name")
    rows(t, r, "s.material_keyword", [("Terrace_A/Terrace_A", 1)], "material:keyword:")
    rows(t, r, "s.material_shader_d", [("Terrace_D/Terrace_D", LIT), ("Terrace_D/Terrace_D", None)],
         "material:shader, one row per slot, an empty slot with no value")
    rows(t, r, "s.material_shader_b", [("Terrace_B/Terrace_B", LIT)], "material:shader of the pipeline's default")
    rows(t, r, "s.material_group", [("Group/Wall1", 0.75), ("Group/Trim", 0.75), ("Group/Wall2", 0.75), ("Group/Wall3", 0.75)],
         "material: every renderer of the object's descendants")
    rows(t, r, "s.material_variant", [("Variant/Pole", LIT), ("Variant/Bulb", UNLIT), ("Variant/Base", LIT)], "material: a variant's")
    rows(t, r, "s.material_nope", [("Terrace_A/Terrace_A", None)], "material: an unknown property: a row with no value")
    rows(t, r, "s.material_whole", [("Terrace_A/Terrace_A", None)], "material: a colour without a channel: no value")
    rows(t, r, "s.collision_group", [("Group/Wall1", 1), ("Group/Trim", 1), ("Group/Wall2", 0), ("Group/Wall3", 0)],
         "mesh_collision: own collider, a parent's, none, a trigger")
    rows(t, r, "s.collision_b", [("Terrace_B/Terrace_B", 0)], "mesh_collision: no collider")
    rows(t, r, "s.collision_variant", [("Variant/Pole", 1), ("Variant/Bulb", 0), ("Variant/Base", 0)],
         "mesh_collision: a disabled collider counts 0")
    rows(t, r, "s.collision_quad", [("FanObj/FxQuad", 1)], "mesh_collision: a mesh collider")
    rows(t, r, "s.collision_2d", [("Flat/Flat", 1)], "mesh_collision: a 2D collider")
    rows(t, r, "s.prop_steps", [("FanObj", 4)], "prop: a list's length")
    rows(t, r, "s.prop_step", [("FanObj", 4)], "prop: a list's element")
    rows(t, r, "s.prop_label", [("FanObj", "fan")], "prop: a string")
    rows(t, r, "s.prop_hidden", [("FanObj", 9)], "prop: a private serialized field")
    rows(t, r, "s.prop_axis", [("FanObj", 1)], "prop: a vector's channel")
    rows(t, r, "s.prop_target", [("FanObj", 0)], "prop: a reference that is not set: 0")
    rows(t, r, "s.prop_target_name", [("FanObj", None)], "prop: past a reference that is not set: no value")
    rows(t, r, "s.prop_material", [("Terrace_A", "Road")], "prop: MeshRenderer.material read as the shared one")
    rows(t, r, "s.prop_materials", [("Terrace_D", 2)], "prop: MeshRenderer.materials read as the shared ones")
    rows(t, r, "s.prop_serialized", [("Terrace_D", 2)], "prop: a SerializedObject path of a component")
    rows(t, r, "s.prop_x", [("Terrace_D", 20)], "prop: Transform.position.x")
    rows(t, r, "s.prop_nothing", [("Terrace_D", None)], "prop: an unknown member: a row with no value")
    rows(t, r, "s.prop_first_below", [("Group", 0)], "prop: a component found first in the descendants")
    rows(t, r, "s.prop_mesh", [("TwoParts", "TwoParts")], "prop: MeshFilter.mesh read as the shared one")
    rows(t, r, "s.prop_variant", [("Variant", 120)], "prop: a variant's override")
    rows(t, r, "s.prop_name", [("Terrace_A", "Terrace_A")], "prop: a SerializedObject path of the GameObject")
    gone = (r.get("s.gone") or {}).get("rows")
    t.ok("a prefab instance whose prefab is gone is one object (s.gone)",
         isinstance(gone, list) and len(gone) == 1 and gone[0]["name"].startswith("Gone"), gone)
    error(t, r, "s.player", "`player` selects need a running game: the editor pass can't match them", "a player select")
    error(t, r, "s.has", "`has` needs a running game: the editor pass can't match it", "a has select")
    near = 'a `near` point on the player or the camera needs a running game: use {"xyz": [x, y, z]}'
    error(t, r, "s.near_player", near, "near the player")
    error(t, r, "s.near_camera", near, "near the camera")
    fields = " (count, material_default, material:<property>, mesh_collision, prop:<Component>.<path>)"
    error(t, r, "s.bad_field", "unknown field bogus" + fields, "an unknown field")
    error(t, r, "s.no_field", "unknown field ...", "no field")
    error(t, r, "s.missing", f"no scene {m}Nowhere.unity", "a scene that isn't there")
    error(t, r, "s.guard", f"no scene Assets/../{m}Level.unity", "a scene path with ..")
    rows(t, r, "o.tag", count(["Other_A"]), "a second scene's own objects only")
    rows(t, r, "o.all", count(["Other_A", "Other_B"]), "no select: every object of it")
    for row in range(50):
        rows(t, r, "b.row_%02d" % row, count(["Row_%02d" % row]), "one row of the big scene")
    rows(t, r, "b.cells", count(["Cell_042"] * 50), "a name 50 objects share")
    rows(t, r, "b.all", count(["BigMarker"] + [n for row in range(50) for n in
                                               ["Row_%02d" % row] + ["Cell_%03d" % c for c in range(100)]]),
         "every object of 5,051, none capped")


def prefabs(t, r):
    """`prefab` measures: a prefab's own objects, a variant, a nested prefab, one that changes itself when it loads."""
    rows(t, r, "p.lamp.all", count(["Lamp", "Pole", "Bulb", "Base", "LightSrc"]), "a prefab's objects, no select")
    rows(t, r, "p.lamp.default", [("Lamp", 1)], "material_default in a prefab")
    rows(t, r, "p.lamp.pole_default", [("Pole", 0)], "material_default of a clean part")
    rows(t, r, "p.lamp.collision", [("Lamp/Pole", 1), ("Lamp/Bulb", 0), ("Lamp/Base", 0)], "mesh_collision in a prefab")
    rows(t, r, "p.lamp.light", [("LightSrc", 3)], "prop: in a prefab")
    rows(t, r, "p.lamp.light_type", [("LightSrc", 2)], "prop: a serialized enum of an engine component (m_Type: Point)")
    rows(t, r, "p.lamp.bulb_shader", [("Bulb/Bulb", UNLIT)], "material:shader in a prefab")
    rows(t, r, "p.lamp.speed", [("Lamp", 90)], "prop: of the root")
    rows(t, r, "p.variant.all", count(["LampVariant", "Pole", "Bulb", "Base", "LightSrc"]), "a variant's objects")
    rows(t, r, "p.variant.speed", [("LampVariant", 120)], "a variant's override")
    rows(t, r, "p.post.all", count(["Post", "Lamp", "Pole", "Bulb", "Base", "LightSrc"]), "a nested prefab's objects")
    rows(t, r, "p.dirty.all", count(["Dirty"]), "a prefab that changes itself when it loads")
    error(t, r, "p.missing", f"no prefab {MADE}Nowhere.prefab", "a prefab that isn't there")
    error(t, r, "p.guard", f"no prefab Packages/../{MADE}Lamp.prefab", "a prefab path with ..")


def _pass(t, name, request):
    """The editor pass as the checker starts it, on a request file of our own: (exit code, its log)."""
    _, _, unity = _tools()
    folder = t.project / "Logs" / "ProbeTests" / f"asset.{name}"
    shutil.rmtree(folder, ignore_errors=True)
    folder.mkdir(parents=True)
    asked, log = folder / "request.json", folder / "editor.log"
    asked.write_text(json.dumps(request), encoding="utf-8")
    machine = unity.Machine.for_project(t.project)
    found = machine.job(f"probe-tests asset {name}", [machine.editor, "-batchmode", "-nographics", "-quit", "-projectPath",
                        t.project, "-logFile", log, "-executeMethod", unity.ASSETS_METHOD, "-taskProbeAssets", asked],
                        t.project, 900)
    return found.exit_code, log.read_text(encoding="utf-8", errors="replace") if log.is_file() else ""


def robust(t):
    """The pass's entry point on requests the checker never writes: a result file that can't be written (the result
    then comes in the log's TASK_PROBES line), a number for the nonce, unknown keys; a request it can't read."""
    probes, _, _ = _tools()
    blocked = t.project / "Logs" / "ProbeTests" / "asset.blocked"
    blocked.parent.mkdir(parents=True, exist_ok=True)
    blocked.write_text("a file where the result's folder should be", encoding="utf-8")
    code, log = _pass(t, "unwritable", {
        "nonce": 7.5, "unknown": True, "result": (blocked / "result.json").as_posix(),
        "measures": {"x": [1, 2], "y": {"probe": "asset", "asset": MADE + "Road.mat", "field": "shader:_Smoothness", "z": 1}}})
    t.eq("a result that can't be written: the pass still exits 0", code, 0)
    t.ok("... and says so in its log", "the asset result couldn't be written" in log)
    t.eq("... and its result is the log's TASK_PROBES line, nonce 7.5 echoed",
         probes.editor_results(None, 7.5, log), {"x": {"error": "not an asset measure"}, "y": {"value": 0.75}})
    code, log = _pass(t, "unreadable", {"nonce": "n", "measures": ["not", "an", "object"]})
    t.eq("a request whose measures isn't an object: exit code 2", code, 2)
    t.ok("... saying why", "TaskProbe: the request has no `measures` object" in log)
    t.ok("... and no result line", "TASK_PROBES " not in log)


def _twins(t):
    """Two plays of the build at once, as two scratch copies' plays can run on one machine: each one's probe.json."""
    _, _, unity = _tools()
    exe = t.project / "Build" / "TaskProbe" / "Game.exe"
    procs, files = [], []
    for name in ("twin_a", "twin_b"):
        folder = t.project / "Logs" / "ProbeTests" / f"asset.{name}"
        shutil.rmtree(folder, ignore_errors=True)
        (folder / "out").mkdir(parents=True)
        spec = {"format": unity.SPEC_FORMAT, "out": (folder / "out").as_posix(), "seconds": 3, "shots": 0, "every": 0.5,
                "scene": MADE + "Facts.unity", "sound": False, "player": None, "inputs": [],
                "queries": {"format": "game-probe-queries/1", "every": 0.5, "queries": []}}
        (folder / "spec.json").write_text(json.dumps(spec), encoding="utf-8")
        procs.append(subprocess.Popen([sys.executable, str(unity.DESK), str(exe), "-screen-fullscreen", "0", "-screen-width",
                                       "960", "-screen-height", "540", "-logFile", str(folder / "play.log"), "-taskProbe",
                                       str(folder / "spec.json")], cwd=str(exe.parent)))
        files.append(folder / "out" / "probe.json")
    for proc in procs:
        proc.wait(timeout=300)
    return [json.loads(f.read_text(encoding="utf-8")) if f.is_file() else None for f in files]


def facts(t, play):
    """The checker's build of a project whose own player settings are a new project's least helpful (another company,
    a splash screen, full screen 1920x1080 resizable, one instance only, no player log, IL2CPP, static batching, high
    code stripping, a development build): the play gets what it needs, and the project keeps its own settings."""
    _, seeds, _ = _tools()
    row = play.row("facts", 1 / 30, "Facts") or {}
    t.eq("the company name is the one the checker deletes saved data by", row.get("prop:AssetFacts.company"),
         seeds.saves_company(t.project))
    t.eq("no splash screen showing when the play's scene wakes", row.get("prop:AssetFacts.splashDone"), 1)
    t.eq("the Mono backend", row.get("prop:AssetFacts.backend"), "mono")
    t.eq("not a development build", row.get("prop:AssetFacts.development"), 0)
    t.eq("windowed", row.get("prop:AssetFacts.mode"), "Windowed")
    t.eq("960 wide when the scene wakes", row.get("prop:AssetFacts.width"), 960)
    t.eq("540 high", row.get("prop:AssetFacts.height"), 540)
    t.eq("a game's property only reflection reads is in the player", row.get("prop:AssetFacts.Unread"), 42)
    statics = sorted((x["name"], x.get("prop:MeshFilter.sharedMesh.name"), x.get("prop:MeshRenderer.isPartOfStaticBatch"))
                     for x in play.rows("statics", 1 / 30))
    t.eq("two cubes marked static keep their own mesh, unbatched", statics, [("Static_A", "Cube", 0), ("Static_B", "Cube", 0)])
    shot = play.image("shot_00.png")
    t.eq("the screenshot is 960x540", (shot.width, shot.height), (960, 540))
    t.ok("the player wrote its log", "ASSET facts" in play.log, play.log[-300:])

    build = json.loads((t.project / "Logs" / "TaskProbe" / "build.json").read_text(encoding="utf-8"))
    t.eq("the build result's keys", sorted(build), sorted(["ok", "exe", "scenes", "errors", "seconds", "error", "missing"]))
    t.eq("ok, no error", (build.get("ok"), build.get("error")), (True, None))
    t.ok("the player is under the project's Build/TaskProbe", str(build.get("exe")).endswith("/Build/TaskProbe/Game.exe"), build.get("exe"))
    t.ok("the play's scene is built", MADE + "Facts.unity" in (build.get("scenes") or []), build.get("scenes"))
    deleted = dict(line.split(" ", 1) for line in (t.project / MADE / "Deleted.txt").read_text(encoding="utf-8").split("\n") if line)
    gap = (build.get("missing") or {}).get(MADE + "Facts.unity") or {}
    t.eq("missing: the material and the sound that are gone, not the scripts of packages", gap.get("missing"),
         sorted([deleted["Lost.mat"], deleted["LostBeep.wav"]]))
    t.ok("missing: and how many assets the scene names, more than those", (gap.get("names") or 0) > 2, gap.get("names"))

    settings = (t.project / "ProjectSettings" / "ProjectSettings.asset").read_text(encoding="utf-8")
    for line in ("companyName: DefaultCompany", "m_ShowUnitySplashScreen: 1", "forceSingleInstance: 1", "usePlayerLog: 0",
                 "    m_StaticBatching: 1"):
        t.ok(f"the project keeps its own setting: {line.strip()}", line in settings)
    t.ok("the project keeps its own scripting backend: IL2CPP", re.search(r"scriptingBackend:\n\s+Standalone: 1\b", settings))
    t.ok("the project keeps its own code stripping: High", re.search(r"managedStrippingLevel:\n\s+Standalone: 3\b", settings))

    twins = _twins(t)
    t.eq("two plays at once both run to their end (several instances allowed)",
         [(p or {}).get("ended") for p in twins], ["time", "time"])


PLAYS = {
    "facts": {"check": facts},
}

ASSETS = {"measures": "measures.json", "check": saved}
