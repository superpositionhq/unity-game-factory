# asset: the editor pass (`TaskProbe.EditorTools.AssetPass.Run`)

Files:
- `BuildAssetTest.cs` (goes in `proj/Assets/Editor/AssetTest/`): `Run` builds `Assets/AssetTest/`: `Road.mat` (URP Lit,
  base colour (0.2, 0.4, 0.6), smoothness 0.75, metallic 0.25, `_BaseMap` = Grass, emission (1, 0.5, 0) with
  `_EMISSION`), `Glow.mat` (URP Unlit, alpha 0.5, cutoff 0.3, `_ALPHATEST_ON`), `Fx.mat` (the test's own
  `Params.shader`: a Vector `_Wind` (1, 2, 3, 4), an Integer `_Steps` 5), `Broken.mat` (the error shader), `Grass.png`
  (readable, uncompressed, max 256), `Beep.wav` (force to mono, streaming), `Box.obj` (global scale 2, no animation),
  `Waves.asset` (a `WaveSet` ScriptableObject), `Lamp.prefab` (Pole with a collider, Bulb without, Base with a
  disabled collider and the default material, a Light of intensity 3, a `Spinner` of speed 90 on the root) and
  `AssetLevel.unity` (tagged `Terrace` cubes A-D: A on Road with a collider, B on the default material without one, C
  inactive, D with slots [Road, empty]; a Group with Wall1 (collider) > Trim, Wall2 (none), Wall3 (trigger); a Lamp
  instance on layer Water; Broken; FanObj with a `Spinner` and FxQuad). `RunDirty` opens a dirty untitled scene first,
  then runs the pass.
- `WaveSet.cs`, `Spinner.cs` (go in `proj/Assets/Scripts/AssetTest/`), `Params.shader` (in `Assets/AssetTest/Shaders/`).
- `make_request.py` writes `request.json` (107 measures: every field form and every error case) and `expected.json`.
- `check.py` compares the result file with `expected.json` (numbers to 1e-5, errors by substring).

Run:

```
python C:\ugf-smoke\probe.py exec C:\ugf-c5\proj AssetTestEditor.BuildAssetTest.Run
python C:\ugf-smoke\probe.py exec C:\ugf-c5\proj TaskProbe.EditorTools.AssetPass.Run -- -taskProbeAssets <this folder>\request.json
python check.py
python C:\ugf-smoke\probe.py exec C:\ugf-c5\proj AssetTestEditor.BuildAssetTest.RunDirty -- -taskProbeAssets <this folder>\request.json
python check.py
```

Results (Unity 6000.3.28f1, URP 17.3): both runs 107/107 as expected, exit code 0, the `TASK_PROBES {...}` line in the
log, and the SHA-256 of every file under `Assets/` and `ProjectSettings/` the same before and after each pass (nothing
saved). Floats come back as stored (`_BaseColor.r` of 0.2 reads 0.19999995827674866).

What it proves, by field:
- `shader:` floats, ranges, Integer, colour channels (`.r/.b/.a`, `.g` of a colour), vector channels (`.x-.w` and
  `.r` alias), textures set/unset, `.name` of a texture, `shader:name`; a colour or vector without a channel, an unknown
  property and a non-material are errors.
- `keyword:` on (`_EMISSION`, `_ALPHATEST_ON`) and off.
- `import:` TextureImporter (`isReadable`, `textureCompression`, `maxTextureSize`), AudioImporter (`forceToMono`,
  `loadType` through `defaultSampleSettings`), ModelImporter (`globalScale`, `animationType`, serialized
  `m_GlobalScale`); an unknown setting is an error.
- `prop:` on a ScriptableObject (int, float, string, bool, enum, list length, `[i].member`, colour channel, set/unset
  reference, private field, `m_Name` and `waves.Array.size` through SerializedObject), on a material
  (`renderQueue`, `m_Shader`), on a prefab asset (`Spinner.speed`, `Light.intensity` from a child, `m_Name`).
- `no asset`, `no scene`, `no prefab`, unknown fields, a measure without asset/scene/prefab.
- scene selects: tag, tag + inactive, name wildcard, layer, component, near `xyz` with and without `y_min`, near an
  object point with offset, an unknown tag (no rows); `player`, `has` and a player point are errors.
- `count`, `material_default` (default material, empty slot, error shader, a child's default material, clean ones),
  `material:<prop>` (per slot, per descendant renderer, `<object>/<renderer object>` names, null for an empty slot,
  `material:shader`, `material:keyword:`), `mesh_collision` (own collider, ancestor's collider, none, a trigger, a
  disabled collider), `prop:` (public, private, list length and element, string, vector channel,
  `MeshRenderer.material.name` read as `sharedMaterial`, serialized `m_Materials.Array.size`, `Transform.position.x`,
  an unknown member as null) in a scene and in a prefab. Rows are in hierarchy order.
