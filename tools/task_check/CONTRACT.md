# Unity task verifier: engineering contract

The Unity port of game-factory's task verifier: the checker (`tools/task-check.py`, `tools/task-try.py`,
`tools/task_check/*.py`), the validator (`tools/validate-game.py`), the task schema
(`docs/schemas/game-task.schema.json`) and the probe, the Unity package `tools/task_check/TaskProbe/` that the checker
adds to its copy of a game. A change to any of them is checked against this file: what of the Unreal original maps to
what in Unity and why, where the port differs from the original on purpose, and the files the probe and the checker
exchange. The Unreal original is the reference for behaviour: the same rules, the same verdict logic and the same
result files, unless this file says otherwise (section 2 lists the rules that differ, section 5 the files). Where the
Unreal docs say "actor", "pawn", "map", "cm", "Z up", read the Unity term of section 1.

The users' documents describe the same behaviour for their readers and must agree with this file:
`docs/task-probes.md` (what each measure means, for a task's author), `docs/task-check.md` and `docs/task-try.md`. What
a field means is there; this file holds what an implementer needs beyond it.

## 1. Terms and units

| Unreal | Unity (this verifier) |
|---|---|
| actor | **object**: a GameObject. Its **parts** are the components of itself and its descendants |
| pawn (the player pawn) | **player**: the first object the task's `player` select matches (when it matches nothing there is no player: no fallback), else an active object tagged `Player` (`GameObject.FindGameObjectWithTag`), else an object with a `PlayerInput`, else one with a `CharacterController` (`FindFirstObjectByType`), else the root of the player camera (next row); looked up again every frame |
| player camera | `Camera.main` (an enabled camera tagged MainCamera), else the enabled camera of highest depth that renders to the screen (no target texture) |
| map, `play_map` (`/Game/Maps/L_X?Scenario=2`) | scene: `play_scene` (`Assets/Scenes/X.unity`) and `play_args` (`["-scenario", "2"]`) |
| component class | **component**: a C# type, by its name (`Projectile`, `MeshRenderer`) or full name (`MyGame.Projectile`). An object select's `component`, a `has`, a pieces or widgets select, a widget click and a Part match the type, its base types and its interfaces; a components select's and `spawns`' `component` must name a Component type, which its subtypes match (an interface gives "no component type <name>") |
| UMG / Slate widget | **widget**: a uGUI component's object or a UI Toolkit element |
| cm, cm/s | **m, m/s** (Unity units). Every default and limit scales: 200 cm -> 2 m, 1 cm -> 0.01 m, 2 km -> 2000 m; a near's radius up to 100,000 m (its `y_min`/`y_max` within +-100,000), a teleport's `distance` and a camera point's `forward` up to 1000 m, a line's radius up to 100 m |
| Z up; yaw about Z | **Y up**. `yaw`, `pitch`, `roll` are the euler Y, X and Z angles of the world rotation (`transform.eulerAngles`; the Inspector shows a child's local rotation), normalised to (-180, 180]; a positive `pitch` looks down (Unreal's looks up) |
| `xy` (ground), `z_min`/`z_max`/`z_relative` (near) | `xz`, `y_min`/`y_max`/`y_relative` |
| editor target build | **player build**: Windows x64, Mono, non-development, of the scratch copy (section 5) |
| `-game` offscreen | the built player, windowed 960x540, started by the checker on a Windows desktop of its own (`desk.py`): nothing on the user's screen, no keyboard or cursor taken, the game counts itself focused throughout, the frame identical to a normal window's. Only a player started by hand on the user's own desktop has its window moved off every screen and never activated, by the probe (`Window.cs`) |
| engine 5.7 | Unity 6.3 LTS: `ProjectSettings/ProjectVersion.txt` `m_EditorVersion: 6000.3.*`; task `"engine": "unity-6000.3"` |
| `GF_ROOT`, `gfroot` (`engine(project)`), `ue-heavy.ps1`, `GF_NO_RECORDING` | `UGF_ROOT`, `ugfroot` (`machine/lib/ugfroot.py`: `root()`, `unity_editor(project)` for the Unity.exe a project's `ProjectVersion.txt` names, `check_free(path, what)`), `unity-heavy.ps1` (`machine/tools/`, run as `<root>\tools\unity-heavy.ps1`), `UGF_NO_RECORDING` (the task try sets it and `GF_NO_RECORDING` for its agent; the Unity hooks skip on either) |

Forward vector from a camera row: `[cos(pitch) * sin(yaw), -sin(pitch), cos(pitch) * cos(yaw)]` (degrees in; the
probe's own `{"camera": true}` point uses the camera's `transform.forward`, the same direction). "Height" is `y`
(index 2 of a `[t, x, y, z]` row).

## 2. The task format (Unity flavour of game-task/1)

`docs/schemas/game-task.schema.json` is the Unreal schema, definition by definition, except for what this section
lists (a structural diff of the two files finds nothing else). The validator's rules beyond the schema
(`tools/validate-game.py`: `probe_errors`, `task_semantic_errors`, the repo checks) and the task check's rules
(`verdict.py`, `probes.py`) are the original's in Unity terms, except where this section says.

The task:

- `engine`: const and default `"unity-6000.3"`. No `template` (the original's is a const its checker reads past).
- `play_scene` (string or null; `^Assets/[A-Za-z0-9_ /.()-]+\.unity$`, at most 300 characters) and `play_args` (at most
  16 strings; default `[]`), in place of `play_map`.
- `player` (optional): an object select that names the player object (section 1) for every play of the task. It stays
  in the agent's half of a split task (`tools/split-tasks.py`: it names an object; it isn't an answer).
- Every check names its `kind`: required, with no default. The original's kinds carry a default, so a check without
  `kind` passed its schema as three shapes at once and then stopped the checker.

Plays and inputs:

- A task play: `name`, `seconds`, `every`, `inputs`, `scene` (in place of `map`) and `args`. `scene` and `args` have no
  default: a play's own key, when it is there, takes the place of the task's `play_scene` / `play_args` for that play
  (`"scene": null` opens the project's first build scene).
- Play arguments (`play_args`, a play's `args`): each `^-?[A-Za-z0-9_.:=,/-]{1,60}$`, at most 16 (the original's are
  `-Name[=value]` only, at most 8). An element starting with `-` and a letter is a flag, anything else a value
  (`["-scenario", "2"]`). The validator refuses, in both, the flags the checker sets itself (the window, the log, the
  probe's own; `DENIED_PLAY_ARGS`, `DENIED_PLAY_PREFIXES`; case-insensitive, after one dash or more, the name before
  any `=`): `batchmode`, `nographics`, `quit`, `logfile`, `projectpath`, `executemethod`, `popupwindow`, `monitor`,
  `parentHWND`, `single-instance`, and any flag starting with `screen-`, `force-` or `taskprobe`.
- Inputs (section 4): `key` (key and axis rows) is an Input System control path,
  `^<(Keyboard|Mouse|Gamepad)>/[A-Za-z0-9/]{1,40}$`, in place of an FKey name; a widget click's `widget` is a wildcard
  on a name, or a type name (`^[A-Za-z0-9_.*?() -]{1,120}$`; the original's: a plain name); `teleport_to`'s `distance`
  defaults to 2 m.

Selects and points:

- `component` in place of `class` in every select (object select, `has`, components, pieces, widgets) and in `spawns`:
  a C# type's name or full name, `^[A-Za-z_][A-Za-z0-9_]{0,120}(\.[A-Za-z_][A-Za-z0-9_]{0,120}){0,8}$` (what it
  matches: section 1).
- Object select (`Select`): `component`, `tag`, `layer` (new: a layer, by name), `name` (a wildcard on the GameObject's
  whole name), `near`, `has`, `player` (true), `inactive` (new: true lets inactive objects match; by default only
  objects active in the hierarchy). `has`: `component`, `lit`, `visible`, `near`, `simulating`, `movable` (at least one
  key; `lit`, `visible`, `simulating`, `movable` only `true`).
- Component select: `component` or `effect` or both, `name` (a wildcard on its object's name), `owner` (an object
  select), `near`, `mesh`, `visible`, `inactive` (new).
- Widget select: `component`, `name`, `text` (a regular expression on its text), `visible`. No `slate`.
- UI select: `kind` (`text`, `box`, `image`), `text`, `rect`. No `line` kind (Unity keeps no list of line draws).
- Audio select: `sound` (a wildcard on the AudioClip's name), `sound_class` (a wildcard on the name of the
  AudioMixerGroup the source outputs to), `owner`. Piece select: `component`, `name`, `mesh`, `owner`, `near`.
- A name a wildcard reads (`name`, `mesh`, `sound`, `sound_class`) may hold parentheses: `^[A-Za-z0-9_.*?() -]{1,120}$`
  (`Coin(Clone)`, `Lamp (1)`).
- Points: `{"xyz": [x, y, z]}`, `{"player": true, "offset": [x, y, z]}` (was `pawn`), `{"camera": true, "forward": m}`,
  `{"object": <object select>, "offset": [x, y, z]}` (was `actor`). `near`: `{"point", "radius", "y_min", "y_max",
  "y_relative"}`.

Measures:

- Probe kinds: `player` (was `pawn`) and `objects` (was `actors`); `camera`, `components`, `widgets`, `light`,
  `grading`, `spawns`, `log`, `asset`, `trace`, `pieces`, `screen`, `audio`, `ground`, `ui`, `drawn` keep their names.
- `objects` fields: the original's, plus `active` and `clip`, and `anim:<Parameter>` in place of `bb:<Key>` (Unity has
  no built-in AI blackboard). Bone, Part and Animator parameter names may hold spaces, dots, colons, parentheses and
  hyphens, as Unity and the tools that make models name them (`[A-Za-z0-9_][A-Za-z0-9_ .:()-]{0,63}`:
  `mixamorig:Hips`, `Lamp (1)`, Blender's `Cube.001` and `hand.L`); a `bone:`'s component is a plain type name, so
  `bone:Animator.hand.L.y` splits at its first and its last dot.
- `components` fields: the original's, plus `prop:<path>` (on the component itself); the measure takes `match` (a
  `prop:` string).
- `widgets` fields: the original's, plus `value` and `interactable`. `camera`: `player_on_screen` in place of
  `pawn_on_screen`. `pieces`: `objects` in place of `actors`. `audio`: `level` added. `ground`: `xz` in place of `xy`.
- `grading`: `post:<Component>.<parameter>` and `post:<Component>.<parameter>.<channel>`
  (`^post:[A-Za-z_][A-Za-z0-9_]{0,63}\.[A-Za-z_][A-Za-z0-9_]{0,63}(\.[rgbaxyzw])?$`) in place of `post:<Property>`: a
  URP volume parameter belongs to its component.
- `spawns`: `{"probe": "spawns", "component": "<type>", "field": "spawned|destroyed"}`.
- `asset`: one of `asset` (`^(Assets|Packages)/[A-Za-z0-9_][A-Za-z0-9_ /.()@-]{0,299}$`), `scene`
  (`^Assets/[A-Za-z0-9_ /.()-]+\.unity$`) and `prefab` (`^(Assets|Packages)/[A-Za-z0-9_ /.()-]+\.prefab$`), in place
  of `asset` and `map`. Fields: the original's `count`, `material_default`, `mesh_collision`, `material:<property>` and
  `prop:<path>`, plus a channel or `.name` after `material:<property>`, `material:keyword:<NAME>`, `import:<path>`,
  `shader:<Property>` (with a channel `.r`-`.a` or `.x`-`.w`, or `.name`) and `keyword:<NAME>`.

The validator's rules beyond the original's (`probe_errors`):

- an asset measure reads exactly one of `asset`, `scene`, `prefab`, and that one's fields (`prop:`, `import:`,
  `shader:`, `keyword:` of one asset; `count`, `material_default`, `material:`, `mesh_collision`, `prop:` of a scene's
  or prefab's objects); its select takes no `player` and no `near` around the player or the camera (as the original's
  takes no `has`), since a scene as saved has neither;
- a screen rect has x0 < x1 and y0 < y1; a player measure's `dist` has its `to`; a measure sets `to_angle` or
  `to_axis`, not both;
- every regular expression of a measure compiles (`match`, a log's `pattern`, a select's `text`; the original compiles
  a ui select's only), so none can stop the task check.

Fields whose threshold is never a literal (calibrated or relative to the start only), as in the original with the
renames, plus audio `level` (`NEVER_LITERAL`, `PIECE_TRIANGLES`): components `intensity`, `extent_*`,
`bounds_change`, `pose_change`, `glow`, `spin`; objects `spin`, `spread`, `bounds_change`, `pose_change`, `glow`;
pieces `triangles`, `visible_triangles`; `screen` (all); audio `volume`, `max_volume`, `level`; ground `range`; drawn
everything but `drawn`.

The task check's rules differ from the original's in four places, each a case the original gets wrong:

- a still-works probe is excused only when its start play has no samples ("no samples in the window": the play
  crashed, ended early or wrote no probe file); one that finds nothing to measure in a start that ran counts against
  the task (the original excused any "measured nothing", which hid a broken still-works probe) (`verdict.verdict`);
- a check without a reference needs a threshold for every required probe outside `still_works`: an uncalibrated one
  is a reason, "<name> has no threshold: <detail>", since no solution could pass it (`verdict.verdict`);
- a calibrated threshold anchored on the reference alone (the start measured nothing) needs a reference other than 0:
  a share of 0 is no margin, so the probe is uncalibrated, "<name>: the start measured nothing (<why>) and the
  reference measured 0, so there is no threshold" (`verdict.make_threshold`);
- "no value in the window (nothing it selects was measured); the probe said: <error>" quotes only an error about that
  measure's own query (a `query_errors` line starting `<kind> <id>:`, `<kind> <id> (` or `<kind>: `), never another
  query's (`probes._own_errors`; the original quotes the play's first error).

Everything else is the original's: the checks (`build`, `boot`, `log_absent`, `file_exists`, `package`, `probe`,
judges), milestones, `expect` (`value`, `calibrate`, `start_times`, `start_plus`),
`window`/`at`/`agg`/`of`/`match`/`to_angle`/`to_axis`, seeds, limits, weights and the no-op rule. A `file_exists` glob
leaves out Unity's generated folders (`Library`, `Temp`, `Obj`, `Logs`, `Build`, `Builds`, `UserSettings`, `.git`,
`.vs`) as the original leaves out Unreal's (`check.SKIP`).

## 3. Measures in Unity terms

Reduction (`window`, `at`, `agg`, `of`, `match`, `to_angle`, `to_axis`, rows capped at 200 with `total` and `full`) is
the original's, unchanged.

- **player**: `x`, `y`, `z`, `speed`, `moved`, `dist` (+ `to`), from the track.
- **camera**: `distance`, `height` (camera y minus player y; both to the player's transform position, its pivot,
  as the track has it), `pitch`, `yaw`, `fov` (vertical, degrees; 0 for an
  orthographic camera) from the camera rows; `occluded` (a ray from the camera to the player's centre hits a collider;
  triggers, the player's colliders and colliders under the camera are ignored), `player_on_screen` (the centre
  projects inside the viewport, in front) from a `camera` query. The player's centre: the centre of its colliders'
  bounds, else its renderers', else its position.
- Selects match in hierarchy order (scene, the root's place in the scene's root list, sibling indices): the same in
  every play of one build. Rows: an object row's `class` is its first script's type, else its first Behaviour or
  Renderer, else `GameObject`; a component row's `name` and `owner` are both its object's name.
- **objects** fields: `count`; `x`, `y`, `z`; `yaw`, `pitch`, `roll`; `scale` (mean of |lossyScale|); `extent_x|y|z`
  (world-aligned half-size of the union of its drawn renderers' bounds, descendants included, particle and trail
  renderers left out, a LODGroup's lower LODs counted; no value when it draws nothing); `active` (activeInHierarchy);
  `hidden` (1 when inactive, or it has renderers and none is drawn); `collision` (any enabled non-trigger collider in
  it); `speed` (its own velocity when not zero: a non-kinematic Rigidbody, a Dynamic Rigidbody2D, an enabled
  CharacterController, a NavMeshAgent on its NavMesh; else how far it moved since the previous sample over that time;
  0 on the first sample for one with a velocity source at rest, else no value the first time); `spin` (deg/s; the
  fastest of its mesh parts, else its own transform; no value on the first sample, except a non-kinematic Rigidbody's
  angular velocity); `simulating` (a non-kinematic Rigidbody or a Dynamic Rigidbody2D in it); `spread` (m; the
  diagonal of the box around its drawn renderers' bounds centres, particle and trail renderers left out; 0 with one,
  no value with none); `changed`, `bounds_change` (m), `pose_change` (m) against the first sample it was seen in
  (parts: its MeshRenderers with a mesh and SkinnedMeshRenderers; changed when a part was hidden or shown, removed or
  added drawn, a part's world bounds moved more than 0.01 m, or a skinned mesh's bones moved more than 0.05 m in all
  in its own space or its local bounds more than 0.01 m); `lit`, `glow` (below); `prop:<Component>.<member>[.<sub>]`
  (reflection: fields and properties, public or not; a component by type name on the object, else the first in its
  descendants; `prop:<member>` alone reads the GameObject, else its Transform; numbers and bools as numbers, enums as
  their value, object references 1 when set, strings through `match`; an array or list without an index gives its
  length, `[i]` its element; `.x`/`.r` and the like of vectors and colours); `bone:<Component>.<Bone>.x|y|z` (world
  position of a bone of a SkinnedMeshRenderer, a human bone of an Animator, or a descendant transform of that name;
  Bone, Part and Animator parameter names as Unity has them, spaces, colons, parentheses and hyphens included:
  `mixamorig:Hips`, `Lamp (1)`); `rel_yaw:<Part>`, `world_yaw:`/`world_pitch:`/`world_roll:<Part>`,
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
  enabled DecalProjector, a TrailRenderer drawing points. A components select leaves out components of inactive
  objects unless it says `"inactive": true`; `mesh` matches a renderer's, MeshFilter's or MeshCollider's mesh.
- **lit / glow**: a source is lit when it is (a) a Light that is on; (b) a drawn mesh Renderer whose material gives
  off light (one that isn't drawn reads dark without being read): read from its properties for a shader named
  `*unlit*` with `_BaseColor` or `_Color` (that colour times its main texture's mean) and for one with
  `_EmissionColor` that declares an `_EMISSION` keyword (when the material enables it: the emission colour times the
  mean of `_EmissionMap` when set), MaterialPropertyBlock overrides included, colours in linear space (an HDR
  emission held as (4, 3, 2) has luminance 12.9); a Shader Graph or any other shader **as rendered**: the renderer
  drawn alone with every light off, ambient black, reflections and fog off, orthographic from four fixed views (128 x
  128), HDR: lit when its brightest pixel's luminance is above 0.01; (c) a live particle system, as rendered. At most
  64 glow renders a frame; past that a source has no value that sample. `glow`: a Light's intensity in Unity's own
  units (not candelas) times its colour's luminance (and its colour temperature when used); a mesh's emissive
  luminance times a quarter of its local bounds' surface (m2); as rendered, the views' luminance x pixel area over the
  seen bounds area times a quarter of the box's surface (a mesh framed by its local box, a skinned mesh by its root
  bone's frame, particles, lines, trails and sprites by their world box). A row with either field carries
  `glow_sources` (`light`, `emissive`, `unlit`, `effect`) and `glow_read` (`props`, `render`, `unread`: no way to read
  it).
- **widgets**: uGUI (`UnityEngine.UI` Graphics and Selectables, TextMeshPro) and UI Toolkit (every `UIDocument`
  panel), world-space canvases included (projected through the player's camera). One row per GameObject or element;
  `class` the matched component's type, else the Selectable, else the text or graphic; `component` may name a game's
  own component. Fields: `count`, `visible`, `text` (+ `match`; rich text stripped, `maxVisibleCharacters` honoured,
  a Selectable without text of its own reads its first child label's), `percent` (a Slider's normalizedValue, a filled
  Image's fillAmount, a ProgressBar's share, a Scrollbar's value), `value` (a Slider's value, a Toggle's 1/0, a
  ProgressBar's, Scrollbar's or Dropdown's value), `interactable`, `has_brush` (a sprite, texture or background image
  is set), `brush` (its name, + `match`), `x`, `y`, `w`, `h` (viewport fractions 0-1, **y down from the top**; no value
  for a zero-size rect).
- **ui**: every element on screen in the frame drawn right after the sample: uGUI graphics on screen-space canvases
  (text: `Text`, `TMP_Text`; image: an `Image`/`RawImage` with a sprite or texture; box: any other drawn graphic) and
  UI Toolkit elements (text: a `TextElement` with text; image: a background image; box: a background colour or
  border). Only what is on screen: active, enabled, alpha above 0.004 up the chain (CanvasGroup, colour, opacity),
  displayed and visible (UI Toolkit), inside the frame. World-space canvases and 3D text are not UI elements. Rows
  carry `source` (`ugui`, `uitk`, `ocr`) and `kind`. Fields `count`, `text`, `x`, `y`, `w`, `h`, `signature`,
  `number`, `clock` (the last three computed by the checker from the rows). A select of text in a rect also reads the
  frame as drawn inside the rect (the original's glyph reader, ported): lines it reads for sure join as `text` rows
  of source `ocr`. This is how OnGUI, GL and custom-mesh readouts are read. A UI Toolkit Button gives a `box` and a
  `text` row. The frame reader refuses a line whose strokes touch the rect's edge.
- **screen**: `luminance`, `luma` of the frame as displayed (UI included: keep the rect off the HUD), over `rect`.
- **light**: `illuminance` in Unity's own light units, not lux (sum over lights that are on: point and spot by
  intensity x colour luminance x URP's distance and cone attenuation, directional by intensity x luminance, each with
  a wall check that also runs for lights with shadows off and ignores triggers, the player's and the lamp's own
  colliders; area lights skipped, URP only bakes them; ambient by the ambient probe's upward value in every mode,
  so flat ambient ignores `ambientIntensity` and gradient ambient mixes sky, equator and ground, x the open share of
  9 upward rays), `exposure` (2^postExposure of the volume stack at the camera; 1 without one or when the camera's
  post-processing is off; URP has no auto-exposure), `brightness` (illuminance x exposure). Value also holds `local`,
  `directional`, `sky`, `lights`, `point`.
- **grading**: the volume stack at the camera, as the shader constants URP itself prepares: `color_balance` (LMS
  coefficients, `ColorUtils.ColorBalanceToLMSCoeffs`), `contrast` and `saturation` (multipliers, 1 neutral),
  `color_filter` (linear rgb), `post_exposure` (EV), `lift`, `gamma`, `gain` (`ColorUtils.PrepareLiftGammaGain`, rgb),
  `tonemapping`, `sun` (`{name, color, intensity, temperature, use_temperature, lit_color}` of the strongest
  directional light that is on) or null, `sky` (`{mode, color, intensity}`), `fog` (`{enabled, density, color}`), and
  every `post:<Component>.<parameter>` asked for (a volume parameter's value after blending, e.g.
  `post:Bloom.intensity`, `post:Vignette.intensity`, `post:ColorAdjustments.postExposure`). The checker computes
  `grey`, `cast`, `warmth`, `tint`, `saturation`, `contrast` from a neutral grey 0.18 lit by the key light's hue and
  run through URP's ColorGrade order: post exposure (2^EV, which URP applies before the grading lookup), LMS balance,
  contrast in LogC around 0.4135884 (ACEScc mid-grey, about 0.2248 linear), colour filter, gain and lift, gamma,
  saturation (`tools/task_check/colour.py`, the LDR order; constants from the URP package source in
  `Library/PackageCache/com.unity.render-pipelines.*`). An untouched stack gives exactly grey 0.18 and cast 0. The
  stack is blended by the probe for the main camera's volume trigger and layer mask at each sample (`source:
  "camera"`), or is the camera's own when it updates by script (`camera_stack`); a camera with post-processing off
  gives neutral constants and exposure 1. Extra value keys: `source`, `pipeline`, `post_processing`, `grading_mode`
  (`ldr`, `hdr`), `hue_shift` (degrees), `fog.mode`. Colours are linear. A `post:` value no volume overrides reads
  the component's default; a `post:` name that doesn't exist is null and a `query_errors` line.
- **spawns**: objects carrying the component that appeared (became active) or went, counted every frame since the
  play started (cumulative; the checker differences them): instantiated clones and pooled objects reused with
  SetActive alike.
- **pieces**: a MeshRenderer with a mesh that has triangles is 1; a SkinnedMeshRenderer is 1; a Terrain's tree
  instances 1 each; renderers of active objects only. Under a LODGroup only LOD 0's renderers count. A tree's `mesh`
  name is its prototype's first mesh; trees are visible when the Terrain is enabled with trees drawn.
  `Graphics.RenderMesh*` and detail grass are no pieces. Fields `count`, `visible`, `components`,
  `objects`, `triangles` (index count / 3 over its submeshes), `visible_triangles`.
- **audio**: every AudioSource that is playing (and matches the select) at its **volume at the listener**: its
  volume (0 when muted) times its distance attenuation by its rolloff (its 3D share by `spatialBlend`); mixer volumes
  and `AudioListener.volume` left out. Fields `count`, `audible` (at 0.001 or more), `volume` (sum), `max_volume`,
  and `level` (the RMS of the listener's mixed output since the previous sample, mixers and effects included). The
  probe's tap on the AudioListener measures the mix and then silences it, so no play is ever heard. A play that
  measures audio is paced to real time (30 fps); other plays run as fast as the machine renders. `level` is null for
  the first frames and up to 4 frames after the listener changes. `PlayOneShot` sounds count but have no clip name
  (`loudest` "", no `sound` match; `level` hears them); `PlayClipAtPoint` sounds read normally. Logarithmic rolloff
  keeps falling past max distance (measured: 1/80 at 80 m with max 50). `AudioListener.pause` makes every source read
  as not playing; `timeScale` 0 doesn't. A mixer group's volume changes `level`, not `volume`. Extra value keys:
  `loudest`, `peak`, `listener`.
- **ground**: a ray straight down from 2000 m up at `xz` (every collider but triggers and the player's; with
  `select`, only colliders of objects it matches or their descendants, the rest traced through; the player's
  colliders always skipped): `height` (y), `hit`; over a `box` on a
  `grid` x `grid` lattice: `min`, `max`, `mean`, `range`, `hits`.
- **drawn**: every drawn renderer whose bounds reach the place, rendered alone from fixed orthographic views (four
  around a point, 64 x 64; two across a line, 128 x 128): `drawn`, `motion`, `base_r|g|b` (rendered under flat white
  ambient light minus the render under black ambient, so emission cancels: a URP Lit surface reads its albedo, a metal
  near black, an unlit surface 0), `base_change`, `reach`, `length`; the value always holds `pixels` and `primitives`,
  and a field that wasn't asked for is null. How: a hidden orthographic camera of the probe's own, rendered by hand
  through URP's single-camera render request into float textures, culling mask the chosen renderers' layers (UI layer
  out); every other drawn renderer on those layers inside the views forced off, terrains there stop drawing; every
  Light and reflection probe off, fog off, default reflection black, the chosen renderers' lightmaps and light probes
  off, flat ambient (white for motion and base, black for glow); post-processing, shadows, anti-aliasing and volumes
  off; all put back before the sample returns (the game's frames are identical with and without the queries). The far
  plane sits at the place's far side. A renderer enclosing the place and 20 times its size is left out. Same values
  under Forward, Forward+ and Deferred. Limits: camera callbacks see the probe's render; `OnBecameVisible` /
  `isVisible` may fire for it; adaptive probe volumes and realtime GI lightmaps stay on; layers only a filtered URP
  renderer draws, world-space canvases and terrain aren't read; a forward-only shader draws nothing under Deferred.
  Cost: 5-8 ms a sample near a point, 4 ms along a line, 3 ms a glow render.
- **log**: lines of the play's player log that match.
- **asset** (`play: "editor"`): one batchmode editor pass. `asset` + `prop:<path>` (reflection on the main asset,
  else a SerializedObject property path), `import:<path>` (its importer), `shader:<Property>` (a material's shader
  property: floats, `.r|g|b|a` of colours, a texture 1 when set), `keyword:<NAME>` (1 when enabled); `scene` or
  `prefab` + `select`: `count`, `material_default` (1 when any renderer of the object or its descendants, inactive
  included, has a slot that is empty or missing, uses the error shader or one that doesn't compile, or is Unity's
  built-in default material or the pipeline's default material), `material:<property>` (one row per slot),
  `mesh_collision` (one row per mesh, 1 when it or a parent up to the object has an enabled non-trigger collider),
  `prop:<Component>.<path>`. Exactly one of `asset`, `scene`, `prefab`. Errors, not values: `no asset|scene|prefab
  <path>`; a select using `player` or `has` or a `near` around the player or camera (a `near` around `{"object"}`
  resolves in the same scene or prefab); a colour or vector without a channel; an unknown shader property; `shader:` or
  `keyword:` on a non-material; an unknown member on an asset (on a scene object: a row with no value). Also accepted
  by the code: `.r`-`.a` as aliases of `.x`-`.w`; `import:` falling back to an AudioImporter's
  `defaultSampleSettings`; `prop:` on a prefab asset reading it like a scene object; `material`, `materials`, `mesh` in
  a `prop:` path read as `shared...`; `shader:name`; `material:keyword:<NAME>` and a texture's `.name` (the schema
  allows neither). Floats come back as stored (0.2 reads 0.19999995827674866). The pass never saves.

## 4. Plays and inputs

`look`: 20 s idle, 6 screenshots. `drive`: 22 s, 8 screenshots: `<Keyboard>/w` 1-6 s, `<Keyboard>/d` 6-8 s,
`<Keyboard>/w` 8-13 s with `<Keyboard>/space` 9-9.3 s, `<Keyboard>/a` 13-15 s, `<Keyboard>/w` 15-21 s. A task play: 2
screenshots. A boot: `seconds` idle (the 60 s boot serves `look` as in the original). Sampled every 0.5 s (`every`
0.1-1.0). The play's clock is a fixed 30 fps (`Time.captureFramerate = 30`; play time = frames / 30), starting when
the play's scene has loaded, holding while any scene is still loading and during a `wait`, counting on when the game
sets `timeScale` 0. The probe asks for the play's `scene` before the game's first build scene has woken up: that scene's
objects get `Awake` and `OnEnable`, then are destroyed before `Start`. `play_args` apply to every play (look, drive,
boot, task plays); a task play's `args` key replaces them; `"scene": null` opens the first build scene. Every play
starts from clean saved data (the build's company name is `TaskProbe.<hash>`; the probe clears PlayerPrefs and
`persistentDataPath` at the start, the checker deletes them with the copy).

Inputs go through the **Input System** on the probe's own virtual Keyboard, Mouse and Gamepad (real devices are not
read; the old Input Manager cannot be driven). Keys and buttons are queued before the game's scripts and processed by
the Input System at the next frame's start, so the game reads them one frame later. The Gamepad is added only when an
input names `<Gamepad>`.

- key: `{"t", "key": "<Keyboard>/w", "press": true|false}`; `key` is an Input System control path on `<Keyboard>`,
  `<Mouse>` or `<Gamepad>` (`<Keyboard>/space`, `<Keyboard>/leftShift`, `<Keyboard>/f2`, `<Mouse>/leftButton`,
  `<Gamepad>/buttonSouth`); pattern `^<(Keyboard|Mouse|Gamepad)>/[A-Za-z0-9/]{1,40}$`.
- axis: `{"t", "key": "<Mouse>/delta/x", "axis": 4.0}`. `<Mouse>/delta/*` and `<Mouse>/scroll/*` are one-frame
  impulses; any other axis (`<Gamepad>/leftStick/x`) keeps its value until set again.
- widget click: `{"t", "widget": "RetryButton", "click": true}`: the first visible, interactable uGUI Selectable or UI
  Toolkit Button whose name (wildcard) or type matches, clicked as a player's click fires it (UI Toolkit: a submit
  event, which fires `Button.clicked`; a raw `ClickEvent` handler needs the cursor path).
- cursor: `{"t", "cursor": [fx, fy]}` (viewport fractions, y down): moves the virtual mouse; a following
  `<Mouse>/leftButton` press clicks there (uGUI through an EventSystem with an InputSystemUIInputModule, UI Toolkit
  buttons, the game through `Mouse.current`).
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

The probe also writes `probe.log` into `out`: its own lines (teleports, clicks, waits, errors) with play time and real
time; the game's own log is `play.log`.

**Player command line**: `python tools\task_check\desk.py <copy>\Build\TaskProbe\Game.exe -screen-fullscreen 0
-screen-width 960 -screen-height 540 -logFile <copy>\Logs\TaskProbe\play.log -taskProbe <spec file> <play args...>`,
working directory the build folder, through `unity-heavy.ps1 -Gpu` when the machine has it. `desk.py` starts the
player on a Windows desktop of its own (`WinSta0\TaskProbe`) and returns its exit code.

**Build**: `Unity.exe -batchmode -nographics -quit -projectPath <copy> -logFile <copy>\Logs\TaskProbe\build.log
-executeMethod TaskProbe.EditorTools.Build.Player -taskProbeBuild <request file>`; the request is `{"out":
"<copy>/Build/TaskProbe", "scenes": ["Assets/Scenes/X.unity", ...], "result": "<copy>/Logs/TaskProbe/build.json"}`
(`scenes`: every scene the task's plays open, added to the build after the project's own enabled build scenes). The
result: `{"ok": true, "exe": "...", "scenes": [...], "errors": 0, "seconds": 41, "error": null, "missing":
{"Assets/Scenes/X.unity": {"missing": ["<guid>", ...], "names": 57}}}` (`missing`: asset GUIDs a played scene names
that the project has no asset for). The build passed when the exit code is 0 and the result says `ok`. The build sets,
for the copy only: company name `TaskProbe.<12 hex of sha256 of the copy's folder>`, no splash screen, no static
batching (a batched renderer's mesh would hide its own mesh name and triangle count), windowed 960x540, not resizable,
run and visible in background, several instances allowed, the Mono backend, not a development build. Within one run, a
copy's first build starts from the `Library/` of a copy already built (its compiled scripts and build caches left
out), so it imports only what differs.

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
- `Runtime/Core/`: `Probe.cs` (the play loop, `Probe` and `ProbeLate`), `Json.cs` (parse and write:
  `Dictionary<string, object>`, `List<object>`, `double`, `bool`, `string`, null), `Find.cs` (`Sel`, `NearSel`,
  points, hierarchy order), `Query.cs` (`Query`, `RowSet`: rows, `total`, `full`; `FrameImage`: the frame drawn
  after a sample), `Reflect.cs` (`prop:` paths), `Inputs.cs`, `Window.cs` (the user's-desktop fallback), `AudioTap.cs`,
  `Hooks.cs` (cross-family hooks such as the glow render).
- `Runtime/Queries/`: one class per query kind, `[ProbeQuery("kind")] class XQuery : Query`, found by reflection, and
  their helpers (`ObjectRead`, `Glow`, `LightKit`, `UiScan`, `UiOcr`, `DrawnRender`).
- `Editor/` (assembly `TaskProbe.Editor`, namespace `TaskProbe.EditorTools`): `Build`, `AssetPass`, `AssetValues`,
  `SceneRows`.
- `probe_tests/<family>/`: per family, the editor scripts that build its test scenes, the game scripts, the play specs
  and a README with what each play proved and the values read. In a test project each MonoBehaviour must be in its own
  file named after it (several in one file made the player fail to load the scene).
- Anything unknown (a type, a member, a widget, a kind) gives empty rows or null values and an entry in
  `query_errors`; it never stops the play.
