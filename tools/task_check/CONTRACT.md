# Unity task verifier: engineering contract

The Unity port of game-factory's task verifier (`tools/task_check`, `tools/validate-game.py`, the task schema, the
TaskProbe plugin). Everyone building a part of it builds against this file. The Unreal original is the reference for
behaviour: same rules, same file formats, same verdict logic, unless this file says otherwise. Where the Unreal docs say
"actor", "pawn", "map", "cm", "Z up", read the Unity term below.

User-facing docs (written from this): `docs/task-probes.md`, `docs/task-check.md`, `docs/task-try.md`.

## 1. Terms and units

| Unreal | Unity (this verifier) |
|---|---|
| actor | **object**: a GameObject. Its **parts** are the components of itself and its descendants |
| pawn (the player pawn) | **player**: the task's `player` select, else the first active object tagged `Player`, else one with a `PlayerInput`, else one with a `CharacterController`, else the root of the main camera |
| player camera | `Camera.main` (tag MainCamera, enabled), else the enabled camera of highest depth that renders to the screen |
| map, `play_map` (`/Game/Maps/L_X?Scenario=2`) | scene: `play_scene` (`Assets/Scenes/X.unity`) and `play_args` (`["-scenario", "2"]`) |
| component class | **component**: a C# type name (`Projectile`, `MeshRenderer`); matches the type, its base types and interfaces, by `Type.Name` or full name |
| UMG / Slate widget | **widget**: a uGUI component's object or a UI Toolkit element |
| cm, cm/s | **m, m/s** (Unity units). Every default scales: 200 cm -> 2 m, 1 cm -> 0.01 m, 2 km -> 2000 m |
| Z up; yaw about Z | **Y up**. `yaw` = euler Y, `pitch` = euler X (positive looks down), `roll` = euler Z, as the Inspector shows them, normalised to (-180, 180] |
| `xy` (ground), `z_min`/`z_max`/`z_relative` (near) | `xz`, `y_min`/`y_max`/`y_relative` |
| editor target build | **player build**: Windows x64, Mono, non-development, of the scratch copy |
| `-game` offscreen | the built player, windowed 960x540, its window moved off-screen by the probe (it renders the same; verified) |
| engine 5.7 | Unity 6.3 LTS: `ProjectSettings/ProjectVersion.txt` `m_EditorVersion: 6000.3.*`; task `"engine": "unity-6000.3"` |
| `GF_ROOT`, `gfroot`, `ue-heavy.ps1`, `GF_NO_RECORDING` | `UGF_ROOT`, `ugfroot` (`machine/lib/ugfroot.py`: `root()`, `unity_editor(project)`, `check_free(path, what)`), `unity-heavy.ps1`, `UGF_NO_RECORDING` (set `GF_NO_RECORDING` too) |

Forward vector from a camera row: `[cos(pitch) * sin(yaw), -sin(pitch), cos(pitch) * cos(yaw)]` (degrees in). "Height" is
`y` (index 2 of a `[t, x, y, z]` row).

## 2. The task format (Unity flavour of game-task/1)

Same as the Unreal schema except:

- `engine`: const and default `"unity-6000.3"`. No `template`.
- `play_scene` (string or null; pattern `^Assets/[A-Za-z0-9_ /.()-]+\.unity$`, max 300) and `play_args` (array of at
  most 16 strings; default `[]`). They replace `play_map`.
- `player` (optional): an object select that names the player object (section 1) for every play of the task.
- A task play: `name`, `seconds`, `every`, `inputs`, and `scene` and `args` in place of `map` and `args`. A play's own
  `scene` / `args`, when the key is present, take the place of the task's `play_scene` / `play_args` for that play.
- Play arguments (`play_args`, a play's `args`): each `^-?[A-Za-z0-9_.:=,/-]{1,60}$`. An element starting with `-` and
  a letter is a flag; anything else is a value. Refused flags (case-insensitive, with or without the dash): `batchmode`,
  `nographics`, `quit`, `logfile`, `projectpath`, `executemethod`, `popupwindow`, `monitor`, `parentHWND`,
  `single-instance`, any flag starting with `screen-`, `force-` or `taskprobe`.
- Probe names: `player` (was `pawn`), `objects` (was `actors`), `components`, `widgets`, `camera`, `light`, `grading`,
  `spawns`, `log`, `asset`, `trace`, `pieces`, `screen`, `audio`, `ground`, `ui`, `drawn`.
- Points: `{"xyz": [x, y, z]}`, `{"player": true, "offset": [x, y, z]}`, `{"camera": true, "forward": m}`,
  `{"object": <object select>, "offset": [x, y, z]}`.
- `near`: `{"point", "radius", "y_min", "y_max", "y_relative"}`.
- Object select (`Select`): `component`, `tag`, `layer` (a layer name), `name` (wildcard on the GameObject's name),
  `near`, `has`, `player` (true), `inactive` (true: inactive objects match too; default only objects active in the
  hierarchy). `has`: `component`, `lit`, `visible`, `near`, `simulating`, `movable` (at least one key; `lit`,
  `visible`, `simulating`, `movable` only `true`).
- Component select: `component` (or `effect`, or both), `name`, `owner` (object select), `near`, `mesh`, `visible`,
  `effect`.
- Widget select: `component`, `name`, `text` (regex on its text), `visible`. No `slate`.
- UI select: `kind` (`text`, `box`, `image`), `text`, `rect`. No `line` kind (Unity keeps no list of line draws).
- Audio select: `sound` (wildcard on the AudioClip's name), `sound_class` (wildcard on the source's output
  AudioMixerGroup's name), `owner`.
- Piece select: `component`, `name`, `mesh`, `owner`, `near`.
- `spawns`: `{"probe": "spawns", "component": "<type>", "field": "spawned|destroyed"}`.
- `ground`: `xz` or `box` `[x0, z0, x1, z1]`, `grid`, `select`.
- `asset`: `asset` + `field` (`prop:`, `import:`, `shader:`, `keyword:`), or `scene` (or `prefab`) + `select` + `field`
  (`count`, `material_default`, `material:<property>`, `mesh_collision`, `prop:<Component>.<path>`).
- Inputs: section 4. Checks (`build`, `boot`, `log_absent`, `file_exists`, `package`, `probe`, judges), milestones,
  `expect` (`value`, `calibrate`, `start_times`, `start_plus`), `window`/`at`/`agg`/`of`/`match`/`to_angle`/`to_axis`,
  seeds, limits, weights and the no-op rule: unchanged.

Fields whose threshold is never a literal (calibrated or relative to the start only), as in the original, with the
renames: components `intensity`, `extent_*`, `bounds_change`, `pose_change`, `glow`, `spin`; objects `spin`, `spread`,
`bounds_change`, `pose_change`, `glow`; pieces `triangles`, `visible_triangles`; `screen` (all); audio `volume`,
`max_volume`, `level`; ground `range`; drawn everything but `drawn`.

## 3. Measures in Unity terms

Reduction (`window`, `at`, `agg`, `of`, `match`, `to_angle`, `to_axis`, rows capped at 200 with `total` and `full`) is
the original's, unchanged.

- **player**: `x`, `y`, `z`, `speed`, `moved`, `dist` (+ `to`), from the track.
- **camera**: `distance`, `height` (camera y minus player y), `pitch`, `yaw`, `fov` (vertical, degrees; 0 for an
  orthographic camera) from the camera rows; `occluded` (a `Physics.Linecast` from the camera to the player's centre
  hits a collider that isn't the player's), `player_on_screen` (the centre projects inside the viewport, in front) from
  a `camera` query. The player's centre: the centre of its colliders' bounds, else its renderers', else its position.
- **objects** fields: `count`; `x`, `y`, `z`; `yaw`, `pitch`, `roll`; `scale` (mean of |lossyScale|); `extent_x|y|z`
  (world-aligned half-size of the union of its drawn renderers' bounds, descendants included; no value when it draws
  nothing); `active` (activeInHierarchy); `hidden` (1 when inactive, or it has renderers and none is drawn);
  `collision` (any enabled non-trigger collider in it); `speed` (its Rigidbody's or Rigidbody2D's velocity, else its
  CharacterController's or NavMeshAgent's, else how far it moved since the previous sample over that time; no value
  the first time); `spin` (deg/s; the fastest of its renderer parts, else its own transform); `simulating` (a
  non-kinematic Rigidbody or a Dynamic Rigidbody2D in it); `spread` (m; the diagonal of the box around its drawn
  renderers' bounds centres; 0 with one, no value with none); `changed`, `bounds_change` (m), `pose_change` (m)
  against the first sample it was seen in (parts: its MeshRenderers with a mesh and SkinnedMeshRenderers; changed when
  a part was hidden or shown, removed or added drawn, a part's world bounds moved more than 0.01 m, or a skinned mesh's
  bones moved more than 0.05 m in all in its own space or its local bounds more than 0.01 m); `lit`, `glow` (below);
  `prop:<Component>.<member>[.<sub>]` (reflection: fields and properties, public or not; a component by type name on
  the object, else the first in its descendants; `prop:<member>` alone reads the GameObject, else its Transform;
  numbers and bools as numbers, enums as their value, object references 1 when set, strings through `match`; an array
  or list without an index gives its length, `[i]` its element; `.x`/`.r` and the like of vectors and colours);
  `bone:<Component>.<Bone>.x|y|z` (world position of a bone of a SkinnedMeshRenderer, a human bone of an Animator, or a
  descendant transform of that name); `rel_yaw:<Part>`, `world_yaw:`/`world_pitch:`/`world_roll:<Part>`,
  `forward:<Part>.x|y|z` (a **Part** is a descendant by its GameObject name, else the first object in it carrying a
  component of that type name; for a Light, forward is the way its light travels); `facing_vs_velocity` (degrees
  between its forward and its velocity; no value under 0.1 m/s); `anim:<Parameter>` (its Animator's float, int or bool
  parameter; takes the place of `bb:`), `clip` (the name of its Animator's current clip on layer 0, through `match`).
- **components** fields: `count`; `active` (enabled and active in the hierarchy; a ParticleSystem also playing or
  holding particles; an AudioSource playing); `visible` (a Renderer that is enabled, active and not forced off; any
  other component: 1 when its object is active); `x`, `y`, `z`, `speed`, `spin` (its transform's, as objects');
  `extent_x|y|z` (a Renderer's or Collider's bounds half-size); `simulating`; `changed`, `bounds_change`,
  `pose_change` (a Renderer); `lit`, `glow` (a Light, a mesh Renderer, a particle system; no value for anything else);
  `intensity`, `on` (a Light: enabled, active, intensity above 0); `prop:<path>` (on the component itself).
  `effect: true`: a ParticleSystem that is alive (playing or holding particles), a VisualEffect holding particles, an
  enabled DecalProjector, a TrailRenderer drawing points.
- **lit / glow**: a source is lit when it is (a) a Light that is on; (b) a drawn mesh Renderer whose material gives
  off light: read from its properties when its shader has the standard interface (`_EmissionColor` with emission
  enabled: the `_EMISSION` keyword, times the mean of `_EmissionMap` when set; an unlit shader's `_BaseColor`/`_Color`
  times its main texture's mean), MaterialPropertyBlock overrides included; else **as rendered**: the renderer drawn
  alone with every light off, ambient black, reflections and fog off, orthographic from four fixed views, HDR: lit
  when its brightest pixel's luminance is above 0.01; (c) a live particle system, as rendered. `glow`: a Light's
  intensity times its colour's luminance; a mesh's emissive luminance times a quarter of its local bounds' surface
  (m2); as rendered, the views' luminance x pixel area over the seen bounds area times a quarter of the box's surface.
  A row with either field carries `glow_sources` (`light`, `emissive`, `unlit`, `effect`) and `glow_read` (`props`,
  `render`).
- **widgets**: uGUI (`UnityEngine.UI` Graphics and Selectables, TextMeshPro) and UI Toolkit (every `UIDocument`
  panel). Fields: `count`, `visible`, `text` (+ `match`), `percent` (a Slider's normalizedValue, a filled Image's
  fillAmount, a ProgressBar's share, a Scrollbar's value), `value` (a Slider's value, a Toggle's 1/0), `interactable`,
  `has_brush` (a sprite, texture or background image is set), `brush` (its name, + `match`), `x`, `y`, `w`, `h`
  (viewport fractions 0-1, **y down from the top**).
- **ui**: every element on screen in the frame drawn right after the sample: uGUI graphics on screen-space canvases
  (text: `Text`, `TMP_Text`; image: an `Image`/`RawImage` with a sprite or texture; box: any other drawn graphic) and
  UI Toolkit elements (text: a `TextElement` with text; image: a background image; box: a background colour or
  border). Only what is on screen: active, enabled, alpha above 0.004 up the chain (CanvasGroup, colour, opacity),
  displayed and visible (UI Toolkit), inside the frame. World-space canvases and 3D text are not UI elements. Rows
  carry `source` (`ugui`, `uitk`, `ocr`) and `kind`. Fields `count`, `text`, `x`, `y`, `w`, `h`, `signature`,
  `number`, `clock` (the last three computed by the checker from the rows). A select of text in a rect also reads the
  frame as drawn inside the rect (the original's glyph reader, ported): lines it reads for sure join as `text` rows
  of source `ocr`. This is how OnGUI, GL and custom-mesh readouts are read.
- **screen**: `luminance`, `luma` of the frame as displayed (UI included: keep the rect off the HUD), over `rect`.
- **light**: `illuminance` (sum over lights that are on: point and spot by intensity x colour luminance x URP's
  distance and cone attenuation, directional by intensity x luminance, each with a `Physics.Linecast` visibility test;
  ambient by `RenderSettings` ambient x the open share of 9 upward rays), `exposure` (2^postExposure of the volume
  stack at the camera; 1 without one), `brightness` (illuminance x exposure). Value also holds `local`,
  `directional`, `sky`, `lights`, `point`.
- **grading**: the volume stack at the camera, as the shader constants URP itself prepares: `color_balance` (LMS
  coefficients, `ColorUtils.ColorBalanceToLMSCoeffs`), `contrast` and `saturation` (multipliers, 1 neutral),
  `color_filter` (linear rgb), `post_exposure` (EV), `lift`, `gamma`, `gain` (`ColorUtils.PrepareLiftGammaGain`, rgb),
  `tonemapping`, `sun` (`{name, color, intensity, temperature, use_temperature, lit_color}` of the strongest
  directional light that is on) or null, `sky` (`{mode, color, intensity}`), `fog` (`{enabled, density, color}`), and
  every `post:<Component>.<parameter>` asked for (a volume parameter's value after blending, e.g.
  `post:Bloom.intensity`, `post:Vignette.intensity`, `post:ColorAdjustments.postExposure`). The checker computes
  `grey`, `cast`, `warmth`, `tint`, `saturation`, `contrast` from a neutral grey 0.18 lit by the key light's hue and
  run through URP's ColorGrade order: LMS balance, contrast in LogC around 0.4135884, colour filter, gain and lift,
  gamma, saturation (`tools/task_check/colour.py`; constants from the URP package source in
  `Library/PackageCache/com.unity.render-pipelines.*`).
- **spawns**: objects carrying the component that appeared (became active) or went, counted every frame since the
  play started (cumulative; the checker differences them).
- **pieces**: a MeshRenderer with a mesh that has triangles is 1; a SkinnedMeshRenderer is 1; a Terrain's tree
  instances 1 each. Under a LODGroup only LOD 0's renderers count. Fields `count`, `visible`, `components`,
  `objects`, `triangles` (index count / 3 over its submeshes), `visible_triangles`.
- **audio**: every AudioSource that is playing (and matches the select) at its **volume at the listener**: its
  volume (0 when muted) times its distance attenuation by its rolloff (its 3D share by `spatialBlend`); mixer volumes
  and `AudioListener.volume` left out. Fields `count`, `audible` (at 0.001 or more), `volume` (sum), `max_volume`,
  and `level` (the RMS of the listener's mixed output since the previous sample, mixers and effects included). The
  probe's tap on the AudioListener measures the mix and then silences it, so no play is ever heard. A play that
  measures audio is paced to real time (30 fps); other plays run as fast as the machine renders.
- **ground**: a ray straight down from 2000 m up at `xz` (every collider but triggers and the player's; with
  `select`, only colliders of objects it matches, the rest traced through): `height` (y), `hit`; over a `box` on a
  `grid` x `grid` lattice: `min`, `max`, `mean`, `range`, `hits`.
- **drawn**: every drawn renderer whose bounds reach the place, rendered alone from fixed orthographic views (four
  around a point, 64 x 64; two across a line, 128 x 128): `drawn`, `motion`, `base_r|g|b` (rendered under flat white
  ambient light with no direct lights, fog or post-processing: the surface's own colour), `base_change`, `reach`,
  `length`. Thresholds and limits as the original's.
- **log**: lines of the play's player log that match.
- **asset** (`play: "editor"`): one batchmode editor pass. `asset` + `prop:<path>` (reflection on the main asset,
  else a SerializedObject property path), `import:<path>` (its importer), `shader:<Property>` (a material's shader
  property: floats, `.r|g|b|a` of colours, a texture 1 when set), `keyword:<NAME>` (1 when enabled); `scene` or
  `prefab` + `select`: `count`, `material_default` (1 when any renderer's slot is empty, missing or Unity's default
  material), `material:<property>`, `mesh_collision` (1 when a mesh object has a collider), `prop:<Component>.<path>`.

## 4. Plays and inputs

`look`: 20 s idle, 6 screenshots. `drive`: 22 s, 8 screenshots: `<Keyboard>/w` 1-6 s, `<Keyboard>/d` 6-8 s,
`<Keyboard>/w` 8-13 s with `<Keyboard>/space` 9-9.3 s, `<Keyboard>/a` 13-15 s, `<Keyboard>/w` 15-21 s. A task play: 2
screenshots. A boot: `seconds` idle (the 60 s boot serves `look` as in the original). Sampled every 0.5 s (`every`
0.1-1.0). The play's clock is a fixed 30 fps (`Time.captureFramerate = 30`), starting when the play's scene has
loaded.

Inputs go through the **Input System** on the probe's own virtual Keyboard, Mouse and Gamepad (real devices are not
read; the old Input Manager cannot be driven):

- key: `{"t", "key": "<Keyboard>/w", "press": true|false}`; `key` is an Input System control path on `<Keyboard>`,
  `<Mouse>` or `<Gamepad>` (`<Keyboard>/space`, `<Keyboard>/leftShift`, `<Keyboard>/f2`, `<Mouse>/leftButton`,
  `<Gamepad>/buttonSouth`); pattern `^<(Keyboard|Mouse|Gamepad)>/[A-Za-z0-9/]{1,40}$`.
- axis: `{"t", "key": "<Mouse>/delta/x", "axis": 4.0}`. `<Mouse>/delta/*` and `<Mouse>/scroll/*` are one-frame
  impulses; any other axis (`<Gamepad>/leftStick/x`) keeps its value until set again.
- widget click: `{"t", "widget": "RetryButton", "click": true}`: the first visible, interactable uGUI Selectable or UI
  Toolkit Button whose name (wildcard) or type matches, clicked as a player's click fires it.
- cursor: `{"t", "cursor": [fx, fy]}` (viewport fractions, y down): moves the virtual mouse; a following
  `<Mouse>/leftButton` press clicks there (UI through the Input System UI module, the game through `Mouse.current`).
- teleport: `{"t", "teleport": [x, y, z], "yaw": deg, "hold": s}`; teleport_to: `{"t", "teleport_to": <object
  select>, "distance": 2.0, "offset": [x, y, z], "face": <Point>, "hold": s}`; wait: `{"t", "wait": s}`. Semantics as
  the original (hold: put back after every frame's game logic; wait: the play's clock holds while the game runs paced
  to real time).

## 5. Files the probe and the checker exchange

**The play spec** (`-taskProbe <file>`; the checker writes it, one per play):

```json
{"format": "unity-probe-play/1", "out": "<dir>", "seconds": 20, "shots": 6, "every": 0.5,
 "scene": "Assets/Scenes/X.unity or null", "sound": false, "player": null,
 "inputs": [ ... section 4 rows, defaults filled in ... ],
 "queries": {"format": "game-probe-queries/1", "every": 0.5, "queries": [{"id": "q...", "kind": "objects", "select": {...}, "fields": [...]}, ...]}}
```

Query kinds and their keys: `objects` (`select`, `fields`), `components` (`select`, `fields`), `widgets` (`select`,
`fields`), `ui` (`select`, `fields`), `camera` (`fields`), `light` (`point`), `grading` (`fields`: the `post:` names),
`spawns` (`component`), `pieces` (`select`), `screen` (`rect`), `audio` (`select`), `ground` (`xz` | `box` + `grid`,
`select`), `drawn` (`near` | `line`, `fields`). A query's id is `"q" + sha256(json of the query without fields)[:10]`.

**probe.json** (the probe writes it into `out`, UTF-8, then exits):

```json
{"format": "unity-probe/1", "ended": "time", "seconds": 20.5, "scene": "Assets/Scenes/X.unity", "player": "Hero",
 "inputs_sent": 3, "screenshots": ["shot_00.png"],
 "track": [[t, x, y, z], [t]],
 "camera": [[t, x, y, z, pitch, yaw, fov]],
 "measures": {"q1a2b3c4d5e": [{"t": 0.5, "rows": [{"name": "...", "class": "...", "x": 1.0}], "total": 389, "full": {"x": {"n": 389, "nonzero": 380, "sum": 1.0, "min": 0.0, "max": 9.0}}},
                              {"t": 0.5, "value": {"illuminance": 1.2}}]},
 "query_errors": ["..."]}
```

`ended`: `time` (ran its seconds), `shutdown` (the game quit first). Selection samples have `rows` (at most 200),
and `total` and `full` when more matched; value samples have `value` (an object, or null). A `ui` sample with no
frame drawn has no `rows` key. Screenshots are 960x540 PNGs with the UI, evenly over the play.

**Player command line**: `<copy>\Build\TaskProbe\Game.exe -screen-fullscreen 0 -screen-width 960 -screen-height 540
-logFile <copy>\Logs\TaskProbe\play.log -taskProbe <spec file> <play args...>`, working directory the build folder,
through `unity-heavy.ps1 -Gpu` when the machine has it.

**Build**: `Unity.exe -batchmode -nographics -quit -projectPath <copy> -logFile <copy>\Logs\TaskProbe\build.log
-executeMethod TaskProbe.EditorTools.Build.Player -taskProbeBuild <request file>`; the request is
`{"out": "<copy>/Build/TaskProbe", "scenes": ["Assets/Scenes/X.unity", ...], "result": "<copy>/Logs/TaskProbe/build.json"}`
(`scenes`: every scene the task's plays open, added to the build after the project's own enabled build scenes). The
result: `{"ok": true, "exe": "...", "scenes": [...], "errors": 0, "seconds": 41, "error": null,
"missing": {"Assets/Scenes/X.unity": {"missing": ["<guid>", ...], "names": 57}}}` (`missing`: asset GUIDs a played
scene names that the project has no asset for). The build passed when the exit code is 0 and the result says `ok`.

**Editor pass**: `Unity.exe -batchmode -nographics -quit -projectPath <copy> -logFile ... -executeMethod
TaskProbe.EditorTools.AssetPass.Run -taskProbeAssets <request file>`; request
`{"nonce": "...", "measures": {"a<id>": {<asset measure>}}, "result": "<copy>/Logs/TaskProbe/probes_editor.json"}`;
result `{"nonce": "...", "measures": {"a<id>": {"value": v} | {"rows": [{"name", "value"}]} | {"error": "..."}}}`.

**Scratch copy**: the commit as committed (LFS objects hardlinked), without `Tasks/`, `History/`, `Dataset/`,
`Dataset.zip`; the probe added as `Packages/com.taskprobe/` (an embedded package: `Packages/manifest.json` untouched).
Refused when `ProjectVersion.txt` isn't `6000.3.*`. Unity fails past 260-character paths: the checker refuses a
scratch project folder longer than 90 characters and says to pass `--scratch`.

**Results**: `task-check/1`, `task-check-progress/1`, `task-try/1`: the original's, with `missing_assets` in place of
`missing_packages`.

A crash in a play: the player log matches `Crash!!!|OUTPUTTING STACK TRACE|Fatal error|Out of memory` (a managed
exception that the game survives is not a crash; `log_absent` checks for those).

## 6. The probe package (`tools/task_check/TaskProbe/` -> `Packages/com.taskprobe/`)

- `Runtime/` (assembly `TaskProbe`, namespace `TaskProbe`): no hard dependency on any package. Input System, uGUI,
  TextMeshPro, URP and UI Toolkit are used through `versionDefines` (`TASKPROBE_INPUTSYSTEM`, `TASKPROBE_UGUI`,
  `TASKPROBE_URP`) or reflection, so it compiles in any project. `[assembly: AlwaysLinkAssembly]` and `[Preserve]`
  keep it through stripping. It does nothing unless the command line has `-taskProbe`.
- `Runtime/Core/`: `Probe` (the play loop), `Json` (parse and write: `Dictionary<string, object>`, `List<object>`,
  `double`, `bool`, `string`, null), `Find` (object selects, points, `near`), `Rows` (rows, `total`, `full`),
  `Reflect` (`prop:` paths), `Inputs`, `Frames` (the frame drawn after a sample), `Window`, `AudioTap`.
- `Runtime/Queries/`: one class per query kind, `[ProbeQuery("kind")] class XQuery : Query`, found by reflection.
- `Editor/` (assembly `TaskProbe.Editor`, namespace `TaskProbe.EditorTools`): `Build`, `AssetPass`.
- Anything unknown (a type, a member, a widget, a kind) gives empty rows or null values and an entry in
  `query_errors`; it never stops the play.
