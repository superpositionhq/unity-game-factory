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

What each field means, for a task's author, is `docs/task-probes.md` section 2, and this section doesn't repeat it.
It says, kind by kind, what of the original the measure maps to, where the probe reads it (the class, its constants),
what it writes for the logs beyond the fields, and what was measured. The reduction (`window`, `at`, `agg`, `of`,
`match`, `to_angle`, `to_axis`; every match counted past the 200 rows through the sample's `total` and `full`) is the
original's, unchanged (`probes.py`).

- **Selects and rows** (`Find`, `Reflect`, `RowSet`). Matches come in hierarchy order: by scene (its build index, then
  its handle), then the root's place in the scene's root list (a built player reports every root's sibling index as
  0), then sibling indices (`Find.SortByHierarchy`): the same in every play of one build. Every match is read;
  `RowSet` keeps the first 200 as rows and sums every match's numbers into `full`. Every row has `name` and `class`,
  for the logs: an object row's `class` is its first MonoBehaviour's type, else its first Behaviour or Renderer, else
  its first other component (Transform and MeshFilter aside), else `GameObject` (`ObjectRead.ClassOf`); a component
  row's `class` is its type, and its `name` and `owner` are both its object's name (a Unity component has no name of
  its own). A field with no value is left out of its row. Every trace the probe casts (the camera's, the light's wall
  checks, the ground's) uses `Physics.DefaultRaycastLayers` and ignores triggers, so the Ignore Raycast layer never
  blocks one.
- **player**, **camera** (the original's pawn and player camera manager): the checker computes every field but two from
  the track rows `[t, x, y, z]` (the player's transform position, its pivot; `[t]` without a player) and the camera
  rows `[t, x, y, z, pitch, yaw, fov]` of the player camera (section 1) the probe writes every sample (`probes.series`;
  a camera row against the track row nearest in time). `fov` is the vertical field of view (Unreal's is horizontal), 0
  for an orthographic camera. A player `dist` to an `{"object": ...}` point reads an `objects` query of that select's
  `x`, `y`, `z`. `occluded` and `player_on_screen` come from a `camera` query (`CameraQuery`; its value repeats the
  row's fields): a `Physics.RaycastAll` from the camera to the player's centre, the player's colliders and those under
  the camera skipped; the centre's viewport point inside 0-1, in front of the camera. The player's centre is the bounds
  centre of its enabled colliders that aren't triggers (its descendants' too), else of its drawn renderers, else its
  position (`Find.Centre`; the original's: its colliding components' bounds centre).
- **objects** (the original's `actors`; `ObjectsQuery`, `ObjectRead`):
  - the drawn box of `extent_*` and `spread`: the renderers drawn (`Find.Drawn`: enabled, active in the hierarchy, not
    `forceRenderingOff`) with non-empty bounds, ParticleSystemRenderers and TrailRenderers left out
    (`ObjectRead.Geometry`); a LODGroup's lower LODs stay enabled, so they count. `spread` counts each renderer by its
    bounds centre; the original also counts each physics body of a skeletal mesh, which Unity has no counterpart of in
    one renderer (a ragdoll is one SkinnedMeshRenderer over its bones' Rigidbodies, so it reads one part);
  - the mesh parts of `spin`, `changed`, `bounds_change`, `pose_change` and `lit`: MeshRenderers whose MeshFilter's
    mesh has vertices, and SkinnedMeshRenderers with a mesh, inactive ones included (`Find.MeshParts`);
  - `speed`: the first velocity source the object has (`ObjectRead.OwnVelocity`: a non-kinematic Rigidbody's
    `linearVelocity`, a Dynamic, simulated Rigidbody2D's, an enabled CharacterController's `velocity`, an enabled
    NavMeshAgent's on its NavMesh), else its displacement since the query's previous sample (`Places`);
  - `spin`: `Spins` follows each transform a sample read, frame by frame until the next sample (`Quaternion.Angle`
    between frames, summed), so a part turning many times a second still reads; a first sample has a non-kinematic
    Rigidbody's angular velocity, or no value;
  - `changed`, `bounds_change`, `pose_change`: `Changes`, each part against the first sample it was seen in, with the
    original's thresholds in metres (`Changes.Bounds` 0.01 m, `Changes.Pose` 0.05 m);
  - `prop:` (`Reflect.Prop`, `Reflect.ReadPath`): instance fields and properties, public or not, along the class
    hierarchy (no statics, no indexers); `[i]` an element; a dictionary's entry by its key; a vector's `.x` and a
    colour's `.r` by their own member names (no aliases at run time; the editor pass has them). A path that doesn't
    resolve on the named component is tried on the GameObject, then on its Transform; `prop:<Component>` alone is 1
    when the object has one, no value when not. The value as the checker takes it (`Reflect.Plain`): numbers and bools
    as numbers, an enum its value, a Unity object 1 when set and 0 when not (an unset reference reads 0), a string, an
    array, list or dictionary its count; anything else (a vector or colour without its part) no value;
  - `bone:<Component>.<Bone>.x|y|z` (the original's `<BoneOrSocket>`; `ObjectRead.Bone`): a SkinnedMeshRenderer's bone
    of that name, else an Animator's human bone (a `HumanBodyBones` name, any case), else a descendant transform of
    that name under the component, then under the object;
  - a **Part** (`rel_yaw:`, `world_yaw:`/`world_pitch:`/`world_roll:`, `forward:`; the original names a component):
    `Reflect.Part`, a transform in the object (itself and inactive ones included) of exactly that name, else the object
    in it that carries a component of that type name. A Light shines along its forward;
  - `anim:<Parameter>` (the original's `bb:<Key>`, an AI blackboard Unity doesn't have) and `clip`: the first enabled
    Animator with a controller in the object (`ObjectRead.AnimParameter`, `ObjectRead.Clip`); `clip` is the heaviest
    clip on layer 0 (`GetCurrentAnimatorClipInfo(0)`);
  - measured: a whole-scene sample of 3000 objects takes about 20 ms.
- **components** (`ComponentsQuery`; the original's registered components of a class): with `component`,
  `FindObjectsByType` of that Component type (its subtypes too); with `effect` alone, of every effect type the build has
  (`Effects.Types`: ParticleSystem, TrailRenderer, VisualEffect, DecalProjector; the last two by reflection, so the
  probe needs neither package), `effect: true` keeping the live ones (`Effects.Live`). A field reads the component as an
  object's reads one part, with Unity's components in the original's places: `extent_*` a Renderer's, Collider's or
  Collider2D's world bounds; `simulating` the Rigidbody or Rigidbody2D it is or is attached to (`Find.Simulates`);
  `changed`, `bounds_change`, `pose_change` a Renderer; `intensity` and `on` a Light (`Glow.LightOn`, the `light`
  probe's test); `active` adds a ParticleSystem's `isPlaying || particleCount > 0` and an AudioSource's `isPlaying`.
- **lit, glow** (`Glow`, `DrawnRender.Glow`; the original reads light components, mesh components through their
  material graphs, and particle systems):
  - the sources: a Light that is on (`Glow.LightOn`); a drawn mesh part; a live particle system with a drawn renderer.
    Sprites, lines and trails are no source. A Light's glow is its intensity in Unity's own units (the original's:
    candelas) times its colour's luminance (Rec. 709, linear), times its temperature's colour when the project
    (`GraphicsSettings.lightsUseColorTemperature`) and the Light use it;
  - a mesh renderer is read from its material properties when every material's shader has an interface the probe
    knows, decided by the shader alone, never by its values (`Glow.FaceOf`; the original evaluates its material
    graphs): unlit (a name containing `unlit` in any case, with `_BaseColor` or `_Color`: that colour times the mean of
    `_BaseMap` or `_MainTex`) or emissive (`_EmissionColor` and a declared `_EMISSION` keyword: with the keyword
    enabled, the emission colour times the mean of `_EmissionMap`). A shader named `Shader Graphs/...` has neither,
    whatever its properties. MaterialPropertyBlocks count (the slot's, then the renderer's); colours are linear in a
    linear project; a texture's mean is read on the GPU (halved down to 16 x 16, so an unreadable texture reads too).
    The brightest material counts over the renderer's whole local bounds: lit above a luminance of 0.01 (`Glow.Floor`,
    the original's), glow that luminance times a quarter of the surface of its local bounds, scaled (m2);
  - any other shader, and every particle system: as rendered (`DrawnRender.Glow`, the `drawn` render below; the
    original's scene capture): the renderer alone with every Light off and a black ambient, from the four corners of a
    tetrahedron in its own frame (a mesh's local box turned and scaled with it, a skinned mesh's in its root bone's
    frame, a particle system's world box), orthographic, 128 x 128, HDR. Lit when its brightest pixel's luminance is
    above 0.01; glow the views' luminance x pixel area summed, over the area of the box they see, times a quarter of
    the box's surface. At most 64 such renders a frame across every query (`DrawnRender.GlowBudget`), each renderer
    once a frame; past that a source has no value that sample;
  - a row with `lit` or `glow` carries `glow_sources` (the kinds lit: `light`, `emissive`, `unlit`, `effect`) and
    `glow_read` (`props`, `render`, or `unread`: no way to read one; the original's `graph`, `render`, `bound`);
  - measured: about 3 ms a glow render.
- **widgets** (the original's UMG widgets; `WidgetsQuery`, `UiScan`): uGUI (`UnityEngine.UI` Graphics and Selectables,
  TextMeshPro) on every canvas of the loaded scenes, world-space ones included (their rect projected through the
  player camera), and every element of every `UIDocument`'s panel (UI Toolkit). One row per GameObject or element:
  `class` the matched component's type, else the object's Selectable, else its text or graphic (an element: its type).
  `component` matches by `Reflect.IsA`, so `Button` takes uGUI and UI Toolkit buttons alike. A rect is in viewport
  fractions, y down from the top, whatever render mode or panel scale placed it. On screen (`visible`, and `ui` below)
  means active, enabled, every Canvas up the chain enabled, an alpha above 0.004 all the way up (`UiScan.AlphaFloor`:
  CanvasGroups, the graphic's colour, its CanvasRenderer), not culled by a RectMask2D, at least partly inside the
  frame; for a UI Toolkit element, displayed, visible and of an opacity above 0.004 up the chain. Text is read without
  rich text tags, TextMeshPro's `maxVisibleCharacters` honoured. No `slate` select: Unity has no lower-level widget
  tree under the UI to walk.
- **ui** (`UiQuery`, `UiScan`, `UiOcr`; the original's Slate tree, HUD canvas and paint elements): the elements on
  screen in the frame drawn right after the sample (`FrameNeed`: the sample is completed once that frame is drawn; one
  whose frame never came has no `rows` key). uGUI graphics on screen-space canvases (Overlay or Camera; text: `Text`,
  `TMP_Text`; image: an `Image` with a sprite or a `RawImage` with a texture; box: any other drawn graphic) and UI
  Toolkit elements of screen panels (text: a `TextElement` with text; image: an `Image` element's image or a background
  image; box: a background colour or a border). World-space canvases and 3D text are no elements. Rows carry `source`
  (`ugui`, `uitk`, `ocr`; the original's `umg`, `slate`, `canvas`, `paint`, `ocr`) and `kind`; there is no `line`
  kind, since Unity keeps no list of what `GL`, `OnGUI` or a mesh draws. A select of text in a rect also reads the
  frame's pixels inside the rect (`UiOcr`, the original's glyph reader ported with its constants and decisions; only
  such a query has the frame read back): each line it reads for sure, where no element already reads text, joins as a
  `text` row of source `ocr`, named `ScreenText`. This is the only reading of an `OnGUI`, `GL` or custom-mesh readout.
  `signature`, `number` and `clock` are computed by the checker from the rows (`probes.ui_signature`, `ui_number`,
  `ui_clock`), as in the original.
- **screen** (`ScreenQuery`; the original's frame had the HUD canvas on it but not the UMG and Slate UI): the frame as
  displayed, read back once it is drawn, every UI on it included (Screen Space - Overlay too), over `rect`. The value
  also holds `pixels` and `size`.
- **light** (`LightQuery`, `LightKit`; the original's lux from the renderer's lights and the sky light):
  `illuminance` is in Unity's own light units, not lux. Each Light that is on (`LightKit.On`) adds the luminance of
  its final colour (colour x intensity, the intensity linear in a linear project, x its temperature colour), a point
  or spot light times URP's distance and cone attenuation as `RealtimeLights.hlsl` computes it
  (`LightQuery.Attenuation`), a directional one as it is; each passes a wall check (`LightKit.Blocked`: from the light
  to the point, stopping 0.01 m short of it; from the point toward a directional light, 2000 m) that runs for lights
  with shadows off too and skips the player's colliders and the light's own (on its object or under it). Area lights
  are skipped (URP only bakes them). The ambient: `RenderSettings.ambientProbe` evaluated straight up, in every
  ambient mode, times the open share of 9 upward rays (straight up and 8 at 45 degrees, 2000 m each). `exposure` is
  2^postExposure of the volume stack at the camera (as `grading` finds it), 1 without one or when the camera's
  post-processing is off: URP has no auto-exposure, the original's eye adaptation. The value also holds `local`,
  `directional`, `sky`, `lights` (the sources that lit it, the ambient counting as one) and `point`.
- **grading** (`GradingQuery`, `LightKit.StackAt`, `tools/task_check/colour.py`; the original's post-process settings
  of the player's view): the URP volume stack at the camera, blended by the probe for the camera's volume trigger and
  layer mask at each sample as URP's UpdateVolumeFramework does (`source: "camera"`), or the camera's own stack when
  it updates by script (`camera_stack`); read as the constants URP's ColorGradingLutPass prepares: `color_balance`
  (`ColorUtils.ColorBalanceToLMSCoeffs`), `contrast` and `saturation` (multipliers, 1 neutral), `color_filter` (linear
  rgb), `post_exposure` (EV), `hue_shift` (degrees), `lift`, `gamma`, `gain` (`ColorUtils.PrepareLiftGammaGain`, rgb),
  `tonemapping` (its mode's name). A camera with post-processing off gives neutral constants. The value also holds
  `sun` (`{name, color, intensity, temperature, use_temperature, lit_color}` of the strongest directional light that
  is on, or null), `sky` (`{mode, color, intensity}`), `fog` (`{enabled, density, color, mode}`), `source`,
  `pipeline`, `post_processing`, `grading_mode` (`ldr`, `hdr`); colours are linear. A `post:<Component>.<parameter>`
  asked for is the parameter's value after blending (one no volume overrides reads the component's default): the
  component by its type's name among `VolumeManager.baseComponentTypeArray` (any case as a fallback), the parameter a
  field of that name, a third part a member of its value (`.r`-`.a` of a colour, `.x`-`.w` of a vector); a name that
  doesn't resolve, or a colour or vector without its part, is null and a `query_errors` line. The checker computes
  `grey`, `cast`, `warmth`, `tint`, `saturation`, `contrast` (`colour.colour`) from a neutral grey 0.18 lit by the key
  light's hue (the sun's `lit_color`, else its colour, else the sky's), run through URP's ColorGrade order: post
  exposure (2^EV, which URP applies before the grading lookup) and LDR grading's saturate, LMS balance, contrast in
  LogC around 0.4135884 (ACEScc mid-grey, about 0.2248 linear), colour filter, gain and lift, gamma, hue shift,
  saturation and the lookup's saturate (the LDR order; the tonemapper is left out, a tonemapping change is read through
  `post:Tonemapping.mode`; constants from the URP package source in
  `Library/PackageCache/com.unity.render-pipelines.*`). An untouched stack gives exactly grey 0.18, and cast 0 under a
  white key light.
- **spawns** (`SpawnsQuery`; the original counts actors of a class spawned and destroyed): every frame of the play's
  clock, a wait's frames included, the objects carrying the component type (active ones; subtypes too) are compared
  with the frame before: one there now and not then is spawned (instantiated, activated, or in a scene loaded during
  the play), one gone is destroyed (destroyed or deactivated), so a pooled object reused with SetActive counts each
  time. The counts are cumulative from the clock's start (what is there then isn't counted) and the checker
  differences them per sample (`probes.series`).
- **pieces** (`PiecesQuery`; the original counts instanced meshes (ISM, HISM, foliage) one per instance and procedural
  mesh sections): a MeshRenderer whose mesh has triangles is 1, a SkinnedMeshRenderer with a mesh is 1, a Terrain's
  tree instances 1 each (Unity's counterpart of instanced meshes; detail grass and `Graphics.RenderMesh*` draws aren't
  renderers and count 0); renderers of active objects only; under a LODGroup only LOD 0's renderers. Triangles: index
  count / 3 over the triangle submeshes (cached per mesh); a tree's, its prototype prefab's at full detail (its LOD 0,
  else every mesh renderer in it), and its `mesh` name the prototype's first mesh's. Counted over every piece, never
  cut at the rows cap.
- **audio** (`AudioQuery`, `AudioTap`; the original's active sounds of the audio device): every AudioSource enabled
  and playing (and matching the select) at its volume at the listener (the first enabled AudioListener on an active
  object): its `volume` (0 when muted) x ((1 - `spatialBlend`) + `spatialBlend` x its rolloff at the listener's
  distance: logarithmic min distance / distance, linear down to 0 at max distance, or its custom curve over distance /
  max distance). Mixer group volumes and `AudioListener.volume` are left out (the original multiplies its sound
  classes' and mixes' volumes in). `level` has no counterpart in the original: the RMS of the listener's mixed output
  since the previous sample, from `AudioTap`, an `OnAudioFilterRead` filter the probe keeps on the enabled listener
  (it looks again every 4 frames), which sums the final mix (mixers and effects applied) and then zeroes it, in every
  play, so no play is ever heard. A play that measures audio is paced to real time at 30 fps (the play spec's
  `sound`); every other play runs as fast as the machine renders. The value also holds `loudest` (the loudest source's
  own clip's name, "" when it has none), `peak` and `listener` (its object's name). What was measured of Unity's audio
  (one-shot sounds, rolloff past max distance, `AudioListener.pause`, mixer volumes) is in `docs/task-probes.md`
  section 2.16.
- **ground** (`GroundQuery`; the original traces the visibility channel, every pawn ignored): a ray straight down from
  y = 2000 m (4000 m long) at `xz`, or at each point of a `grid` x `grid` lattice over `box` (2-32, default 8, corners
  and edges included), takes the first collider it meets, the player's always skipped; with `select`, only colliders
  of the matched objects or their descendants are ground, the rest traced through. The value also holds `points`
  (grid x grid).
- **drawn** (`DrawnQuery`, `DrawnRender`; the original's scene capture): every renderer drawn in game whose world
  bounds reach the place, at most 1024, but one that encloses the whole place and is at least 20 times its size,
  rendered alone from fixed orthographic views: four from the corners of a tetrahedron around a point (64 x 64), two
  square to a line (128 x 128), the cameras 0.5 m outside the place, the far plane at its far side.
  - How: a disabled camera of the probe's own (`HideAndDontSave`, so no select finds it), rendered by hand through
    URP's `SingleCameraRequest` (else the pipeline's `StandardRequest`, else `Camera.Render`) into float textures
    (ARGBFloat); the depth from a second render, copied into a float texture by the package's own shader
    (`Runtime/Resources/TaskProbeDepthCopy.shader`). Its culling mask is the chosen renderers' layers. For the render,
    every other drawn renderer on those layers inside the views is forced off (`forceRenderingOff`: a layer change
    would refilter a collider's physics contacts), terrains on those layers stop drawing, every Light and reflection
    probe is off, fog off, the default reflection a black cubemap, the chosen renderers' lightmaps and light probes off,
    the ambient flat (white for motion and base colour, 1 / 0.96 so a URP Lit surface reads its own albedo; black for
    glow), and post-processing, shadows, anti-aliasing, volumes, render scale and renderer features (but RenderObjects)
    off, HDR on. All of it is put back before the sample returns: the game's frames are identical with and without the
    query.
  - Where the original lights the place with direct lights and the sky light and reads the base colour from the
    GBuffer, the port takes the base colour as the render under the white ambient less the render under black, so
    emission cancels. A pixel is in the place when its depth puts it there, or when it shows colour with nothing
    opaque behind it and its ray crosses the place (translucent particles). `motion`: a pixel changed when it came in
    or went out, or a channel of its colour c / (1 + c) moved more than 1/255 (the original's); `length` counts up to
    128 steps along the line, none finer than a pixel.
  - The value always holds `pixels` and `primitives` (the renderers rendered); the base colour is null unless a
    `base_` field is asked for (`motion`, `reach`, `length` are always computed). Its limits, as measured, are in
    `docs/task-probes.md` section 2.19.
  - Measured: 5 to 8 ms a sample near a point, 4 ms along a line.
- **log**: the lines of the play's player log (`-logFile`, kept as `play.log`) that match, read by the checker as the
  original reads its game log.
- **asset** (`play: "editor"`; `AssetPass`, `AssetValues`, `SceneRows`; the original runs a Python script in its
  headless editor): one batchmode editor pass per side over the project as saved (section 5). An `asset` is loaded
  with `AssetDatabase.LoadMainAssetAtPath`, a `scene` opened alone (`OpenSceneMode.Single`), a `prefab` loaded with
  `PrefabUtility.LoadPrefabContents` and unloaded unsaved; each scene and prefab once for every measure on it. The
  pass never saves.
  - A select is the run time's (`Sel`, `Find.Matches`) over the scene's or prefab's objects in hierarchy order:
    `player`, `has`, and a `near` around the player or the camera are errors (a scene as saved has none of them); a
    `near` around `{"object": ...}` resolves in the same scene or prefab.
  - `prop:` reads by reflection (`Reflect.ReadPath`), else as a SerializedObject property path (`waves[2].count` read
    as `waves.Array.data[2].count`); on a prefab asset and on a scene object, as a run time `prop:` reads an object,
    with `material`, `materials` and `mesh` read as their `shared...` versions (the plain getters would copy the asset
    into the scene). `import:` reads the importer, falling back to an AudioImporter's `defaultSampleSettings`.
  - `shader:` and `material:` read a material as `AssetValues.MaterialValue` does: a float, range or int as it is; a
    colour's or vector's channel in either spelling (`.r` or `.x` ... `.a` or `.w`); a texture 1 when set, its name
    with `.name`; `shader:name` and `material:shader` the shader's name; `keyword:<NAME>` and
    `material:keyword:<NAME>` 1 when enabled. `material_default` finds a renderer with no slot, an empty or missing
    slot, the error shader or one that doesn't compile (`ShaderUtil.ShaderHasError`), or Unity's built-in default
    material or the pipeline's (`AssetValues.IsDefault`). Rows of `material:` are named `<object>/<renderer's object>`,
    of `mesh_collision` `<object>/<mesh's object>`.
  - A missing asset, scene or prefab is an error (`no asset <path>`, `no scene <path>`, `no prefab <path>`). An
    unknown member, an unknown shader property, a colour or vector without its channel, or `shader:` / `keyword:` on
    something that isn't a material is an error for an `asset`, and a row with no value on a scene's or prefab's
    objects (`SceneRows` keeps the row). Every message is in `docs/task-probes.md` section 2.11.

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
