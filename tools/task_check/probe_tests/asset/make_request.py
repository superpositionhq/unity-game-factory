"""Writes request.json (every asset field form and the error cases) and expected.json (the values the test assets
built by BuildAssetTest.Run must give). An expected error is {"error": "<text it contains>"}."""
import json

M = "Assets/AssetTest/Materials/"
ROAD, GLOW, FX = M + "Road.mat", M + "Glow.mat", M + "Fx.mat"
TEX, WAV, OBJ = "Assets/AssetTest/Textures/Grass.png", "Assets/AssetTest/Audio/Beep.wav", "Assets/AssetTest/Models/Box.obj"
SO, PREFAB, SCENE = "Assets/AssetTest/Data/Waves.asset", "Assets/AssetTest/Prefabs/Lamp.prefab", "Assets/AssetTest/Scenes/AssetLevel.unity"
LIT, UNLIT = "Universal Render Pipeline/Lit", "Universal Render Pipeline/Unlit"

cases = []  # (measure, expected)


def a(asset, field, expect):
    cases.append(({"probe": "asset", "asset": asset, "field": field}, expect))


def s(where, select, field, expect, key="scene"):
    m = {"probe": "asset", key: where, "field": field}
    if select is not None:
        m["select"] = select
    cases.append((m, expect))


def v(x):
    return {"value": x}


def rows(*pairs):
    return {"rows": [{"name": n, "value": x} for n, x in pairs]}


def err(text):
    return {"error": text}


# shader: and keyword: on materials
a(ROAD, "shader:_Smoothness", v(0.75))
a(ROAD, "shader:_Metallic", v(0.25))
a(ROAD, "shader:_BaseColor.r", v(0.2))
a(ROAD, "shader:_BaseColor.b", v(0.6))
a(ROAD, "shader:_EmissionColor.g", v(0.5))
a(ROAD, "shader:_BaseMap", v(1))
a(ROAD, "shader:_BaseMap.name", v("Grass"))
a(ROAD, "shader:name", v(LIT))
a(ROAD, "keyword:_EMISSION", v(1))
a(ROAD, "keyword:_ALPHATEST_ON", v(0))
a(GLOW, "shader:_BaseColor.a", v(0.5))
a(GLOW, "shader:_Cutoff", v(0.3))
a(GLOW, "shader:_BaseMap", v(0))
a(GLOW, "keyword:_ALPHATEST_ON", v(1))
a(GLOW, "shader:name", v(UNLIT))
a(FX, "shader:_Wind.z", v(3))
a(FX, "shader:_Wind.w", v(4))
a(FX, "shader:_Wind.r", v(1))
a(FX, "shader:_Steps", v(5))
a(FX, "shader:_Tint.g", v(1))
a(FX, "shader:_Wind", err("is a vector"))
a(FX, "shader:name", v("AssetTest/Params"))
a(ROAD, "shader:_BaseColor", err("is a colour"))
a(ROAD, "shader:_Nope", err("no shader property _Nope"))
a(TEX, "shader:_BaseColor.r", err("is not a material"))
# import:
a(TEX, "import:isReadable", v(1))
a(TEX, "import:textureCompression", v(0))   # TextureImporterCompression.Uncompressed
a(TEX, "import:maxTextureSize", v(256))
a(WAV, "import:forceToMono", v(1))
a(WAV, "import:loadType", v(2))             # AudioClipLoadType.Streaming, from defaultSampleSettings
a(WAV, "import:defaultSampleSettings.loadType", v(2))
a(OBJ, "import:globalScale", v(2))
a(OBJ, "import:animationType", v(0))        # ModelImporterAnimationType.None
a(OBJ, "import:m_GlobalScale", v(2))        # a serialized path on the importer
a(TEX, "import:nope", err("no import setting nope"))
# prop: on a ScriptableObject, a material, a prefab asset
a(SO, "prop:level", v(3))
a(SO, "prop:speed", v(2.5))
a(SO, "prop:title", v("Night"))
a(SO, "prop:boss", v(1))
a(SO, "prop:difficulty", v(2))
a(SO, "prop:waves", v(3))
a(SO, "prop:waves[2].count", v(15))
a(SO, "prop:waves[2].delay", v(1.5))
a(SO, "prop:tint.g", v(0.2))
a(SO, "prop:skin", v(1))
a(SO, "prop:none", v(0))
a(SO, "prop:secret", v(7))                  # private, by reflection
a(SO, "prop:m_Name", v("Waves"))            # SerializedObject fallback
a(SO, "prop:waves.Array.size", v(3))        # SerializedObject array path
a(SO, "prop:nothing", err("no property nothing"))
a(ROAD, "prop:renderQueue", v(2000))
a(ROAD, "prop:m_Shader", v(1))
a(PREFAB, "prop:Spinner.speed", v(90))      # a prefab asset reads as an object
a(PREFAB, "prop:Light.intensity", v(3))     # first in its descendants
a(PREFAB, "prop:m_Name", v("Lamp"))
a("Assets/AssetTest/Missing.mat", "shader:_BaseColor.r", err("no asset Assets/AssetTest/Missing.mat"))
a(TEX, "bogus:x", err("unknown asset field"))

# scene + select
t = {"tag": "Terrace"}
ti = {"tag": "Terrace", "inactive": True}
s(SCENE, t, "count", rows(("Terrace_A", 1), ("Terrace_B", 1), ("Terrace_D", 1)))
s(SCENE, ti, "count", rows(("Terrace_A", 1), ("Terrace_B", 1), ("Terrace_C", 1), ("Terrace_D", 1)))
s(SCENE, {"name": "Terrace_*"}, "count", rows(("Terrace_A", 1), ("Terrace_B", 1), ("Terrace_D", 1)))
s(SCENE, ti, "material_default", rows(("Terrace_A", 0), ("Terrace_B", 1), ("Terrace_C", 0), ("Terrace_D", 1)))
s(SCENE, {"name": "Broken"}, "material_default", rows(("Broken", 1)))
s(SCENE, {"name": "Lamp"}, "material_default", rows(("Lamp", 1)))
s(SCENE, {"name": "Pole"}, "material_default", rows(("Pole", 0)))
s(SCENE, {"name": "Group"}, "material_default", rows(("Group", 0)))
s(SCENE, {"name": "Terrace_A"}, "material:_BaseColor.r", rows(("Terrace_A/Terrace_A", 0.2)))
s(SCENE, {"name": "Terrace_A"}, "material:_BaseMap.name", rows(("Terrace_A/Terrace_A", "Grass")))
s(SCENE, {"name": "Terrace_A"}, "material:keyword:_EMISSION", rows(("Terrace_A/Terrace_A", 1)))
s(SCENE, {"name": "Terrace_D"}, "material:shader", rows(("Terrace_D/Terrace_D", LIT), ("Terrace_D/Terrace_D", None)))
s(SCENE, {"name": "Terrace_B"}, "material:shader", rows(("Terrace_B/Terrace_B", LIT)))
s(SCENE, {"name": "Group"}, "material:_Smoothness",
  rows(("Group/Wall1", 0.75), ("Group/Trim", 0.75), ("Group/Wall2", 0.75), ("Group/Wall3", 0.75)))
s(SCENE, {"name": "Lamp"}, "material:shader", rows(("Lamp/Pole", LIT), ("Lamp/Bulb", UNLIT), ("Lamp/Base", LIT)))
s(SCENE, {"name": "Group"}, "mesh_collision", rows(("Group/Wall1", 1), ("Group/Trim", 1), ("Group/Wall2", 0), ("Group/Wall3", 0)))
s(SCENE, {"name": "Terrace_B"}, "mesh_collision", rows(("Terrace_B/Terrace_B", 0)))
s(SCENE, {"name": "Lamp"}, "mesh_collision", rows(("Lamp/Pole", 1), ("Lamp/Bulb", 0), ("Lamp/Base", 0)))
s(SCENE, {"component": "Spinner"}, "prop:Spinner.speed", rows(("Lamp", 90), ("FanObj", 45)))
s(SCENE, {"name": "FanObj"}, "prop:Spinner.steps", rows(("FanObj", 4)))
s(SCENE, {"name": "FanObj"}, "prop:Spinner.steps[3]", rows(("FanObj", 4)))
s(SCENE, {"name": "FanObj"}, "prop:Spinner.label", rows(("FanObj", "fan")))
s(SCENE, {"name": "FanObj"}, "prop:Spinner.hiddenCount", rows(("FanObj", 9)))
s(SCENE, {"name": "FanObj"}, "prop:Spinner.axis.y", rows(("FanObj", 1)))
s(SCENE, {"name": "Terrace_A"}, "prop:MeshRenderer.material.name", rows(("Terrace_A", "Road")))
s(SCENE, {"name": "Terrace_D"}, "prop:MeshRenderer.materials", rows(("Terrace_D", 2)))
s(SCENE, {"name": "Terrace_D"}, "prop:MeshRenderer.m_Materials.Array.size", rows(("Terrace_D", 2)))
s(SCENE, {"name": "Terrace_D"}, "prop:Transform.position.x", rows(("Terrace_D", 20)))
s(SCENE, {"name": "Terrace_D"}, "prop:MeshRenderer.nothing", rows(("Terrace_D", None)))
s(SCENE, {"name": "Group"}, "prop:BoxCollider.isTrigger", rows(("Group", 0)))   # Wall1's, the first in its descendants
s(SCENE, {"layer": "Water"}, "count", rows(("Lamp", 1)))
s(SCENE, {"component": "Light"}, "count", rows(("LightSrc", 1)))
s(SCENE, {"near": {"point": {"xyz": [0, 0, 0]}, "radius": 6}}, "count",
  rows(("Terrace_A", 1), ("Terrace_B", 1), ("Lamp", 1), ("Pole", 1), ("Bulb", 1), ("Base", 1), ("LightSrc", 1)))
s(SCENE, {"near": {"point": {"xyz": [0, 0, 0]}, "radius": 6, "y_min": 1.5}}, "count", rows(("Bulb", 1), ("LightSrc", 1)))
s(SCENE, {"near": {"point": {"object": {"name": "FanObj"}, "offset": [0, 1, 0]}, "radius": 0.5}}, "count", rows(("FxQuad", 1)))
s(SCENE, {"tag": "NoSuchTag"}, "count", rows())
s(SCENE, {"player": True}, "count", err("running game"))
s(SCENE, {"has": {"component": "Light"}}, "count", err("running game"))
s(SCENE, {"near": {"point": {"player": True}, "radius": 3}}, "count", err("running game"))
s(SCENE, t, "bogus", err("unknown field bogus"))
s("Assets/AssetTest/Scenes/Nowhere.unity", t, "count", err("no scene Assets/AssetTest/Scenes/Nowhere.unity"))
# prefab + select
s(PREFAB, None, "count", rows(("Lamp", 1), ("Pole", 1), ("Bulb", 1), ("Base", 1), ("LightSrc", 1)), key="prefab")
s(PREFAB, {"name": "Lamp"}, "material_default", rows(("Lamp", 1)), key="prefab")
s(PREFAB, {"name": "Pole"}, "material_default", rows(("Pole", 0)), key="prefab")
s(PREFAB, {"name": "Lamp"}, "mesh_collision", rows(("Lamp/Pole", 1), ("Lamp/Bulb", 0), ("Lamp/Base", 0)), key="prefab")
s(PREFAB, {"component": "Light"}, "prop:Light.intensity", rows(("LightSrc", 3)), key="prefab")
s(PREFAB, {"name": "Bulb"}, "material:shader", rows(("Bulb/Bulb", UNLIT)), key="prefab")
s(PREFAB, {"name": "Lamp"}, "prop:Spinner.speed", rows(("Lamp", 90)), key="prefab")
s("Assets/AssetTest/Prefabs/Nowhere.prefab", {}, "count", err("no prefab Assets/AssetTest/Prefabs/Nowhere.prefab"), key="prefab")
# malformed
cases.append(({"probe": "asset", "field": "count"}, err("needs `asset`, `scene` or `prefab`")))

request = {"nonce": "n-asset-test-1", "measures": {}, "result": "C:/ugf-c5/proj/Logs/TaskProbe/probes_editor.json"}
expected = {}
for i, (m, e) in enumerate(cases):
    mid = "a%03d" % i
    request["measures"][mid] = m
    expected[mid] = e
json.dump(request, open("request.json", "w"), indent=1)
json.dump(expected, open("expected.json", "w"), indent=1)
print(len(cases), "measures")
