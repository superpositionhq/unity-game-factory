# Writes the play specs of the objects family's test plays.
import json

def q(id, kind, **kw):
    d = {"id": id, "kind": kind}
    d.update(kw)
    return d

drive = [
    {"t": 1.0, "key": "<Keyboard>/w", "press": True}, {"t": 6.0, "key": "<Keyboard>/w", "press": False},
    {"t": 6.0, "key": "<Keyboard>/d", "press": True}, {"t": 8.0, "key": "<Keyboard>/d", "press": False},
    {"t": 8.0, "key": "<Keyboard>/w", "press": True},
    {"t": 9.0, "key": "<Keyboard>/space", "press": True}, {"t": 9.3, "key": "<Keyboard>/space", "press": False},
    {"t": 13.0, "key": "<Keyboard>/w", "press": False},
    {"t": 13.0, "key": "<Keyboard>/a", "press": True}, {"t": 15.0, "key": "<Keyboard>/a", "press": False},
]

main = [
    q("o_hero", "objects", select={"player": True}, fields=["count", "x", "y", "z", "yaw", "pitch", "roll", "scale", "extent_x", "extent_y", "extent_z",
        "active", "hidden", "collision", "speed", "facing_vs_velocity", "simulating", "rel_yaw:Visor", "world_yaw:Visor", "world_pitch:Visor",
        "world_roll:Visor", "forward:Visor.x", "forward:Visor.z", "spin"]),
    q("o_phys", "objects", select={"component": "Rigidbody"}, fields=["y", "speed", "simulating", "spin", "changed", "bounds_change", "collision"]),
    q("o_fan", "objects", select={"name": "Fan"}, fields=["spin", "changed", "bounds_change", "spread", "extent_x", "extent_z", "lit"]),
    q("o_gone", "objects", select={"name": "Vanisher", "inactive": True}, fields=["active", "hidden", "changed", "extent_x", "collision"]),
    q("o_ghost", "objects", select={"name": "Ghost"}, fields=["active", "hidden", "changed", "extent_x", "collision"]),
    q("o_lamps", "objects", select={"tag": "Lamp"}, fields=["lit", "glow"]),
    q("o_props", "objects", select={"layer": "Props"}, fields=[]),
    q("o_haslit", "objects", select={"has": {"lit": True}}, fields=["lit"]),
    q("o_bulb_hi", "objects", select={"name": "Bulb", "near": {"point": {"xyz": [8, 0, 8]}, "radius": 5, "y_min": 2}}, fields=["y", "scale", "glow"]),
    q("o_bulb_lo", "objects", select={"name": "Bulb", "near": {"point": {"xyz": [8, 3, 8]}, "radius": 5, "y_max": -1, "y_relative": True}}, fields=["y"]),
    q("o_enemy", "objects", select={"tag": "Enemy"}, fields=["prop:Health.current", "prop:Health.armour", "prop:Health.state", "prop:Health.label",
        "prop:Health.items", "prop:Health.items[1]", "prop:Health.tint.g", "prop:Health.target", "prop:activeSelf", "prop:localScale.y", "prop:Health.nothing"]),
    q("o_arm", "objects", select={"name": "Arm"}, fields=["anim:Speed", "anim:Open", "anim:Count", "anim:Missing", "clip", "bone:SkinnedMeshRenderer.Upper.x",
        "bone:Animator.Upper.y", "pose_change", "changed", "bounds_change", "extent_x"]),
    q("o_sun", "objects", select={"name": "Sun"}, fields=["world_pitch:Light", "world_yaw:Sun", "forward:Light.y", "lit", "glow"]),
    q("o_rock", "objects", select={"name": "Rock"}, fields=["extent_x", "spread", "hidden"]),
    q("o_bad", "objects", select={"name": "Rock"}, fields=["nonsense"]),
    q("c_lights", "components", select={"component": "Light"}, fields=["intensity", "on", "lit", "glow", "active", "visible", "x"]),
    q("c_lamp_r", "components", select={"component": "Renderer", "owner": {"tag": "Lamp"}}, fields=["lit", "glow", "visible", "active"]),
    q("c_effects", "components", select={"effect": True}, fields=["active", "count", "lit"]),
    q("c_decal", "components", select={"component": "DecalProjector"}, fields=["active", "visible"]),
    q("c_decal_live", "components", select={"component": "DecalProjector", "effect": True}, fields=["active"]),
    q("c_ps_live", "components", select={"component": "ParticleSystem", "effect": True}, fields=["active"]),
    q("c_ps", "components", select={"component": "ParticleSystem"}, fields=["active", "lit", "glow", "visible", "prop:particleCount"]),
    q("c_blade", "components", select={"component": "MeshRenderer", "name": "Blade"}, fields=["spin", "x", "z", "speed", "changed", "bounds_change", "extent_x", "visible"]),
    q("c_spheres", "components", select={"component": "MeshRenderer", "mesh": "Sphere"}, fields=[]),
    q("c_visible", "components", select={"component": "Renderer", "visible": True, "near": {"point": {"xyz": [-6, 0.5, 1]}, "radius": 1.5}}, fields=["visible"]),
    q("c_health", "components", select={"component": "Health"}, fields=["prop:current", "active", "speed"]),
    q("c_smr", "components", select={"component": "SkinnedMeshRenderer"}, fields=["pose_change", "changed", "bounds_change", "lit"]),
    q("c_rb", "components", select={"component": "Rigidbody"}, fields=["simulating", "speed", "spin", "extent_y"]),
    q("c_col", "components", select={"component": "BoxCollider", "name": "Crate"}, fields=["extent_y", "y"]),
    q("c_trail", "components", select={"component": "TrailRenderer"}, fields=["active", "visible", "x"]),
    q("c_bad", "components", select={"component": "NoSuchType"}, fields=["count"]),
    q("cam", "camera"),
    q("sp", "spawns", component="Projectile"),
    q("sp_bad", "spawns", component="Nope"),
    q("p_all", "pieces"),
    q("p_terrain", "pieces", select={"component": "Terrain"}),
    q("p_sphere", "pieces", select={"mesh": "Sphere"}),
    q("p_rock", "pieces", select={"owner": {"name": "Rock"}}),
    q("p_near", "pieces", select={"near": {"point": {"player": True}, "radius": 6}}),
    q("p_trees_near", "pieces", select={"component": "Terrain", "near": {"point": {"xyz": [70, 0, -10]}, "radius": 8}}),
    q("g_origin", "ground", xz=[0, 0]),
    q("g_roof", "ground", xz=[-20, -20]),
    q("g_roof_floor", "ground", xz=[-20, -20], select={"name": "Floor"}),
    q("g_ramp", "ground", xz=[30, 30]),
    q("g_none", "ground", xz=[500, 500]),
    q("g_hills", "ground", box=[62, -18, 98, 18], grid=8),
    q("g_hills_sel", "ground", box=[62, -18, 98, 18], grid=8, select={"component": "TerrainCollider"}),
]

def spec(scene, seconds, queries, inputs, every=0.5, shots=2):
    return {"seconds": seconds, "shots": shots, "every": every, "scene": scene, "sound": False, "player": None, "inputs": inputs,
            "queries": {"format": "game-probe-queries/1", "every": every, "queries": queries}}

json.dump(spec("Assets/Scenes/ObjTest.unity", 16, main, drive), open("play_main.json", "w"), indent=1)

# stress: 3000 boxes; each kind alone, sampled every 0.1 s, so its cost per sample shows in the play's wall clock
stress = {
    "none": [],
    "objects_all": [q("s", "objects", select={}, fields=["x", "y", "z", "speed", "extent_x", "hidden", "collision", "spin"])],
    "objects_glow": [q("s", "objects", select={}, fields=["lit", "glow"])],
    "objects_change": [q("s", "objects", select={}, fields=["changed", "bounds_change", "spread"])],
    "objects_haslit": [q("s", "objects", select={"has": {"lit": True}}, fields=[])],
    "objects_tag": [q("s", "objects", select={"tag": "Enemy"}, fields=["x", "prop:Transform.position.y"])],
    "components": [q("s", "components", select={"component": "MeshRenderer"}, fields=["x", "spin", "lit", "glow", "changed", "visible"])],
    "pieces": [q("s", "pieces")],
    "ground": [q("s", "ground", box=[-60, -50, 60, 50], grid=32)],
    "spawns": [q("s", "spawns", component="Spinner")],
    "camera": [q("s", "camera")],
}
for name, qs in stress.items():
    json.dump(spec("Assets/Scenes/ObjStress.unity", 10, qs, [], every=0.1, shots=0), open(f"stress_{name}.json", "w"), indent=1)
