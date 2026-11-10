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
lists and the limits section 1 scales (a structural diff of the two files finds nothing else). The validator's rules
beyond the schema (`tools/validate-game.py`: `probe_errors`, `task_semantic_errors`, the repo checks) and the task
check's rules (`verdict.py`, `probes.py`) are the original's in Unity terms, except where this section says.

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
  `-Name[=value]` only, at most 8). An element starting with one dash or more and a letter is a flag, anything else a
  value (`["-scenario", "2"]`). The validator refuses, in both, the flags the checker sets itself (the window, the
  log, the probe's own) and those that would undo them (`DENIED_PLAY_ARGS`, `DENIED_PLAY_PREFIXES`; case-insensitive,
  written with one dash or more: `-quit`, `--quit`; the name before any `=`; a word without a dash is a value, never
  refused): `batchmode`, `nographics`, `quit`, `logfile`, `nolog`, `projectpath`, `executemethod`, `popupwindow`,
  `monitor`, `parentHWND`, `single-instance`, `window-mode`, and any flag starting with `screen-`, `force-` or
  `taskprobe`. `-nolog` would undo the checker's `-logFile` (`play.log` is where a crash, a `log` measure and
  `log_absent` are read) and `-window-mode` its windowed 960x540; no game needs either as a play argument, so refusing
  them costs nothing, as the original's list refuses `log` and `windowed` among the engine's flags.
- Inputs (section 4): `key` (key and axis rows) is an Input System control path,
  `^<(Keyboard|Mouse|Gamepad)>/[A-Za-z0-9/]{1,40}$`, in place of an FKey name; a widget click's `widget` is a wildcard
  on a name, or a type name (`^[A-Za-z0-9_.*?() -]{1,120}$`; the original's: a plain name); `teleport_to`'s `distance`
  defaults to 2 m.

Selects and points:

- `component` in place of `class` in every select (object select, `has`, components, pieces, widgets) and in `spawns`:
  a C# type's name or full name, `^[A-Za-z_][A-Za-z0-9_]{0,120}(\.[A-Za-z_][A-Za-z0-9_]{0,120}){0,8}$` (what it
  matches: section 1).
- Object select (`Select`): `component`, `tag`, `layer` (new: a layer, by name, `^[A-Za-z0-9_. -]{1,80}$`), `name` (a
  wildcard on the GameObject's whole name), `near`, `has`, `player` (true), `inactive` (new: true lets inactive
  objects match; by default only objects active in the hierarchy). `has`: `component`, `lit`, `visible`, `near`,
  `simulating` (at least one key; `lit`, `visible`, `simulating` only `true`). The original's `movable` has no Unity
  counterpart: a non-kinematic Rigidbody can always move, so `simulating` says what the pair said, and a built player
  keeps no Static flag (`GameObject.isStatic` reads false there for an object saved static: measured).
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
  (`^Assets/[A-Za-z0-9_ /.()-]+\.unity$`) and `prefab` (`^(Assets|Packages)/[A-Za-z0-9_ /.()-]+\.prefab$`; these two
  at most 300 characters), in place of `asset` and `map`. Fields: the original's `count`, `material_default`,
  `mesh_collision`, `material:<property>` and `prop:<path>`, plus a channel or `.name` after `material:<property>`,
  `material:keyword:<NAME>`, `import:<path>`, `shader:<Property>` (with a channel `.r`-`.a` or `.x`-`.w`, or `.name`)
  and `keyword:<NAME>`.

The validator's rules beyond the original's (`probe_errors`, `task_semantic_errors`, `task_warnings`):

- an asset measure reads exactly one of `asset`, `scene`, `prefab`, and that one's fields (`prop:`, `import:`,
  `shader:`, `keyword:` of one asset; `count`, `material_default`, `material:`, `mesh_collision`, `prop:` of a scene's
  or prefab's objects); its select takes no `player` and no `near` around the player or the camera, since a scene as
  saved has neither, as it takes no `has` (the original's rule);
- a screen rect has x0 < x1 and y0 < y1; a player measure's `dist` has its `to`; a measure sets `to_angle` or
  `to_axis`, not both, and `window` or `at`, not both;
- every regular expression of a measure compiles (`match`, a log's `pattern`, a select's `text`; the original compiles
  a ui select's only), so none can stop the task check;
- the task's `player` select names no `player` and no point on the player (it says which object the player is);
- a warning, never an error, when a `teleport_to`, an object point or an `"of": "first"` measure takes its one object
  by a wildcard name and nothing else: a spawner, a pool or a parent named like the things fits too (the sample game's
  `teleport_to` `Coin*` went to `CoinSpawner`).

Fields whose threshold is never a literal (calibrated or relative to the start only), as in the original with the
renames, plus audio `level` (`NEVER_LITERAL`, `PIECE_TRIANGLES`): components `intensity`, `extent_*`,
`bounds_change`, `pose_change`, `glow`, `spin`; objects `spin`, `spread`, `bounds_change`, `pose_change`, `glow`;
pieces `triangles`, `visible_triangles`; `screen` (all); audio `volume`, `max_volume`, `level`; ground `range`; drawn
everything but `drawn`.

The task check's rules differ from the original's in six places, each a case the original gets wrong:

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
  query's (`probes._own_errors`; the original quotes the play's first error);
- a sample without the player (a `[t]` track row) or without a camera row has no value for the player's and the
  camera's own fields, so a play that ran but never found them fails "no value in the window", not "no samples" (the
  original drops those rows, and the still-works excuse above would then cover a broken `player` select)
  (`probes.series`);
- a look cut from the reference's boot keeps its samples up to its seconds + 0.5, where a look of its own stops
  sampling, so `"at": "end"` and a measure without a window read the same span on both sides (`check.first_seconds`,
  `check.OVERRUN`; the original cuts at its seconds, though its plugin samples to Seconds + 0.5 as well).

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
    bounds centre (the original also counts each physics body of a skeletal mesh by its place; here a ragdoll, one
    SkinnedMeshRenderer over its bones' Rigidbodies, is one part);
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
  it updates by script (`camera_stack`); `source` is `none` when there is no stack to read (no URP, no camera, or
  URP's volume framework not set up yet, as at a play's first sample). The stack is read as the constants URP's
  ColorGradingLutPass prepares: `color_balance` (`ColorUtils.ColorBalanceToLMSCoeffs`), `contrast` and `saturation`
  (multipliers, 1 neutral), `color_filter` (linear rgb), `post_exposure` (EV), `hue_shift` (degrees), `lift`, `gamma`,
  `gain` (`ColorUtils.PrepareLiftGammaGain`, rgb), `tonemapping` (its mode's name). A camera with post-processing off
  gives neutral constants. The value also holds `sun` (`{name, color, intensity, temperature, use_temperature,
  lit_color}` of the strongest directional light that is on, or null), `sky` (`{mode, color, intensity}`), `fog`
  (`{enabled, density, color, mode}`), `source`, `pipeline`, `post_processing`, `grading_mode` (`ldr`, `hdr`); colours
  are linear. A `post:<Component>.<parameter>` asked for is the parameter's value after blending (one no volume
  overrides reads the component's default): the component by its type's name among
  `VolumeManager.baseComponentTypeArray` (any case as a fallback), the parameter a field of that name, a third part a
  member of its value (`.r`-`.a` of a colour, `.x`-`.w` of a vector); a name that doesn't resolve, or a colour or
  vector without its part, is null and a `query_errors` line. The checker computes
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

The checker's plays are the original's in Unity's keys (`check.PLAYS`, `check.DRIVE`): `look`, 20 s idle, 6
screenshots; `drive`, 22 s, 8 screenshots: `<Keyboard>/w` 1-6 s, `<Keyboard>/d` 6-8 s, `<Keyboard>/w` 8-13 s with
`<Keyboard>/space` 9-9.3 s, `<Keyboard>/a` 13-15 s, `<Keyboard>/w` 15-21 s (the original's W, D, SpaceBar, A). A task
play: 2 screenshots. A boot check: `seconds` idle, 2 screenshots. A boot of 20 s or more also serves `look` when no look
probe reads the play's log (`check.Side.idle`): it then takes 6 screenshots and look's queries, and look reads its first
20.5 s, as far as a look of its own samples (`check.first_seconds`); a `log_absent` check reads the 60 s boot. Samples
every 0.5 s (a task play's `every`, 0.1-1.0). `play_args` apply to every play (look, drive, boot, task plays); a task
play's `args` key replaces them, its `scene` key the `play_scene` (`tasks.place`).

The play's clock (`Probe.cs`) is a fixed 30 fps (`Time.captureFramerate = 30`; play time is frames / 30), run as fast
as the machine renders (vSync off, `Application.targetFrameRate` -1), but paced to real time at 30 fps in a play that
measures audio (the spec's `sound`), during a `wait` and while a scene loads. It starts when the play's scene is the
active scene and no scene is loading (after 600 frames without the play's scene, a `query_errors` line, and it starts
in the scene that plays), holds while any scene is still loading and during a `wait`, and counts on when the game sets
`timeScale` 0. The game's `Time.time` runs on it; `Time.unscaledTime`, `Time.unscaledDeltaTime`,
`Time.realtimeSinceStartup` and the system clock follow the wall clock (measured by the probe's core tests: from play
time 0.5 s to 3.5 s, `Time.unscaledTime` went 0.13 s, as `Time.realtimeSinceStartup` did). The probe asks for the
play's `scene` at `BeforeSceneLoad`, before the game's first build scene has woken up: that scene's objects get `Awake`
and `OnEnable`, then are destroyed before `Start` (a scene the build lacks: a `query_errors` line, and the game's own
first scene plays). Every play starts from clean saved data: the build gives the copy a company name of its own
(`TaskProbe.<hash>`, section 5), the probe clears PlayerPrefs and `persistentDataPath` when the play starts, and the
checker deletes what the plays left outside the copy with it (section 5).

Inputs go through the **Input System** on the probe's own virtual devices (`Inputs.cs`; the original sends FKey
events): `TaskProbeKeyboard` and `TaskProbeMouse`, added before the game's first frame, and `TaskProbeGamepad` only when
an input names `<Gamepad>` (a gamepad switches many games' prompts); `InputSystem.settings.backgroundBehavior` is
`IgnoreFocus`, since the window never has the focus. Real devices are not read, and the old Input Manager can't be
driven (a project without the Input System package gets one `query_errors` line for its keys, axes and cursor moves).
Each device's whole state is queued with every change, before the game's scripts (the probe runs at execution order
-32000), and the Input System processes it at the next frame's start, so the game reads an input one frame after its
time. Inputs of one time go in the order the task wrote them. An unknown control is a `query_errors` line (`inputs:
the keyboard has no key <x>`, `the mouse has no control <x>`, `the gamepad has no control <x>`), never a stop.

- key: `{"t", "key": "<Keyboard>/w", "press": true|false}`: a key by its Input System name (`<Keyboard>/space`,
  `<Keyboard>/leftShift`, `<Keyboard>/f2`), a mouse button (`<Mouse>/leftButton`, `rightButton`, `middleButton`,
  `forwardButton`, `backButton`), a gamepad button by its Input System name or the usual alias (`<Gamepad>/buttonSouth`,
  `a`, `cross`; `start`, `select`, the shoulders, the stick presses, `dpad/up` and the rest).
- axis: `{"t", "key": "<Mouse>/delta/x", "axis": 4.0}`: `<Mouse>/delta/x|y` and `<Mouse>/scroll/x|y` are one-frame
  impulses; `<Mouse>/position/x|y` set the pointer, in pixels; `<Gamepad>/leftStick/x|y`, `rightStick/x|y`,
  `leftTrigger` and `rightTrigger` keep their value until set again.
- widget click: `{"t", "widget": "RetryButton", "click": true}`: the first visible, interactable uGUI Selectable in
  hierarchy order whose name (a wildcard) or type (base types and interfaces too) matches, else such a UI Toolkit
  Button (`UiScan.Click`). A uGUI one gets the pointer enter, down, up and click a player's click sends, at its centre
  (`ExecuteEvents`), so `onClick`, toggles and the game's own `IPointer*Handler`s react; a UI Toolkit one a
  `NavigationSubmitEvent`, which fires `Button.clicked` (a raw `ClickEvent` handler needs the cursor path).
  `probe.log` says `clicked <widget>` or `no visible button matches '<widget>'`.
- cursor: `{"t", "cursor": [fx, fy]}` (viewport fractions, y down): moves the virtual mouse there (it starts at the
  window's centre); a following `<Mouse>/leftButton` press and release clicks there (uGUI through an EventSystem with
  an InputSystemUIInputModule, UI Toolkit buttons, the game through `Mouse.current`).
- teleport: `{"t", "teleport": [x, y, z], "yaw": deg, "hold": s}`; teleport_to: `{"t", "teleport_to": <object
  select>, "distance": 2.0, "offset": [x, y, z], "face": <Point>, "hold": s}`. The original moves the pawn with
  Unreal's TeleportTo, which finds a free spot near the point; the port sets the player's transform, its pivot, to
  the point (`Inputs.Place`), through its CharacterController (disabled for the move), its NavMeshAgent (`Warp`, on its
  NavMesh) or its Rigidbody (and a Rigidbody2D's position), with no free-spot search and no snap to the ground, and
  stills its bodies. `yaw` turns it (the checker writes 0 when unset, as the original's does). teleport_to takes the
  match nearest the player, the player and its children left out; the spot is `distance` from the target along the
  level line toward the player (in front of the target when the player is right above it), plus `offset`; it faces
  `face`, else the target (it keeps its yaw when what it faces is within a centimetre on the level). `hold`: after
  every frame's game logic, for that many seconds, the player is put back at the spot and stilled. `probe.log` says
  where each went (`teleported next to <name>: asked (...) yaw ..., now at (...)`, `teleport_to skipped (no object
  matches)`).
- wait: `{"t", "wait": s}`: the play's clock holds while the game runs paced to real time, until `wait` seconds of
  both real and game time have passed; the inputs after it wait for its end (the original's).

## 5. Files the probe and the checker exchange

The original passes its plugin a flag for each setting (`-TaskProbeOut`, `-TaskProbeSeconds`, `-TaskProbeInputs`
...) and runs its editor pass as a Python script in its headless editor. The port hands the player one play spec and
runs an editor method, so those requests are its own formats; `probe.json` is the original's `game-probe/1` under the
name `unity-probe/1`, with `scene` in place of `map` and `player` added, and the editor pass's result is the
original's. The checker's files of a copy are under `<copy>/Logs/TaskProbe/` (`unity.LOGS`; a game never keeps
anything in Unity's `Logs/`), each made fresh before its job. The examples below are of the sample game's task
`lamp-keeper-fix-lamps-hud-camera`, its reference commit's copy written as a run with `--scratch C:\tc` places it
(`C:\tc\38e8bcd7\ff49e5194fe4`): the requests are what the checker's own functions write for it, the results the real
ones, unless one says otherwise.

**The play spec** (`<copy>/Logs/TaskProbe/play_spec.json`, written by `unity.Project.play`, read by `Probe.Begin`). The
task play `scenario_two`, with its queries as `probes.plan` makes them (the ids are those of the play's real
`probe.json`):

```json
{"format": "unity-probe-play/1", "out": "C:/tc/38e8bcd7/ff49e5194fe4/Logs/TaskProbe/play", "seconds": 8,
 "shots": 2, "every": 0.5, "scene": "Assets/Scenes/Yard.unity", "sound": false, "player": null,
 "inputs": [{"t": 2.0, "wait": 2.0}, {"t": 4.0, "key": "<Keyboard>/space", "press": true},
            {"t": 4.3, "key": "<Keyboard>/space", "press": false}],
 "queries": {"format": "game-probe-queries/1", "every": 0.5, "queries": [
   {"id": "q0515f1b44e", "kind": "ui", "select": {"kind": "text", "rect": [0.0, 0.0, 0.4, 0.09]},
    "fields": ["h", "text", "w", "x", "y"]},
   {"id": "q2af780091d", "kind": "objects", "select": {"name": "Lamp_3"}, "fields": ["lit"]},
   {"id": "qe2fd69dd75", "kind": "widgets", "select": {"component": "Slider", "name": "FuelBar"},
    "fields": ["percent"]}]}}
```

- What varies: `out` (the copy's), the play's `seconds`, `shots`, `every`, `scene` (null: the game's first build
  scene), the task's `player` select (null: the probe finds the player, section 1), its `inputs` with the checker's
  defaults filled in (`tasks.inputs`), `sound` (true when a query is `audio`) and the queries.
- The probe reads `out` (default: `persistentDataPath/TaskProbe`), `seconds` (clamped to 1-600; default 20), `every`
  (0.1-1.0; 0.5), `shots` (0-64; 0), `scene`, `sound`, `player` (its own `player` key ignored), `inputs` and
  `queries.queries`; the queries' `format` and `every` ride along unread. A play without queries has an empty list.
- A query holds `id`, `kind`, its kind's keys and `fields`: `objects`, `components`, `widgets`, `ui` take `select` and
  `fields`; `camera` `fields`; `light` `point`; `grading` `fields` (the `post:` names asked for); `spawns`
  `component`; `pieces` `select`; `screen` `rect`; `audio` `select`; `ground` `xz` or `box` and `grid`, and `select`
  when set; `drawn` `near` or `line`, and `fields` (`probes.needs`). `fields` is the sorted union of what the play's
  probes read of it (`[]` for a count). Its id is `"q"` and the first 10 hex digits of the sha256 of
  `json.dumps(<the query without its id and fields>, sort_keys=True)` (`probes.query_id`), so probes reading other
  fields of one selection share it; the queries are merged per play and sorted by id (`probes.plan`). The probe takes
  any id (the probe tests name theirs) and at most 256 queries.

**probe.json** (written by the probe into `out` when the play ends, UTF-8 without a BOM, compact; read by
`unity.Project.play`, then `probes.py`). The start of that play's real file on the reference, spaced out here: its
first two track and camera rows (of 18) and the first sample of each query:

```json
{"format": "unity-probe/1", "ended": "time", "seconds": 8.5333333333333332, "scene": "Assets/Scenes/Yard.unity",
 "player": "Keeper", "inputs_sent": 3, "screenshots": ["shot_00.png", "shot_01.png"],
 "track": [[0.033333333333333333, 3.7999999523162842, 0.079999983310699463, -14],
           [0.5, 3.7999999523162842, 0.079999983310699463, -14]],
 "camera": [[0.033333333333333333, 10.30000114440918, 3.2799999713897705, -13.999999046325684, 10.459908485412598,
             -90, 55],
            [0.5, 10.30000114440918, 3.2799999713897705, -13.999999046325684, 10.459908485412598, -90, 55]],
 "measures": {
  "q0515f1b44e": [{"t": 0.033333333333333333, "rows": [{"name": "ScoreText", "class": "TextMeshProUGUI",
                   "source": "ugui", "kind": "text", "h": 0.064814814814814811, "text": "SCORE 100",
                   "w": 0.27083333333333331, "x": 0.020833333333333332, "y": 0.027777777777777776}]}],
  "q2af780091d": [{"t": 0.033333333333333333, "rows": [{"name": "Lamp_3", "class": "Lamp",
                   "glow_read": "props,render", "lit": 1, "glow_sources": "light,emissive,effect"}]}],
  "qe2fd69dd75": [{"t": 0.033333333333333333, "rows": [{"name": "FuelBar", "class": "Slider",
                   "percent": 0.1496296226978302}]}]}}
```

- `ended`: `time` (the clock passed its seconds + 0.5) or `shutdown` (the game quit first: `Application.quitting`).
  `seconds`: the play time at the end, its seconds + 0.5 plus the frames (at most 5) a last sample that reads the
  drawn frame waits for. `scene`: the active scene's path at the end; `player`: the player's name then, or null.
  `screenshots`: 960x540 PNGs of the frame as displayed, UI included, taken at the middle of each of `shots` equal
  parts of the play.
- Samples fall on frames: the first at 1/30 s (the clock's first frame), then every `every` s, on the frame that
  reaches it. Every sample adds a `track` row, `[t, x, y, z]` (the player's transform position) or `[t]` while there
  is no player (no value there for the checker), and a `camera` row `[t, x, y, z, pitch, yaw, fov]` when there is a
  player camera (a sample without one has no value for the camera's fields).
- `measures` (only when the spec has queries): each query's id and its samples, one per sample time, each with its
  `t`: `rows` for `objects`, `components`, `widgets` and `ui` (`RowSet`: at most 200; when more matched, also `total`,
  how many, and `full`, for each field its `n`, `nonzero`, `sum`, `min` and `max` over every match's numeric value), or
  `value`, an object or null, for the others. A `ui` sample whose frame never came has no `rows`; a `screen` sample's
  value is then null.
- `query_errors` (only when there was one): each line once, at most 50: `<kind> <id>: <message>` (or `<kind> <id>
  (frame): ...`) for a query's own error, `<kind>: <message>` for a select's (`spawns: no component type Coin`),
  and the loop's own (`a query has no id or kind`, `no query kind <kind>`, `the play's scene <scene> isn't in the build:
  the game's own first scene is played`, `inputs: ...`).
- Numbers: whole ones without a fraction, the rest in their round-trip form; NaN and infinities are written null
  (`Json.Write`).

**probe.log** (beside it in `out`): the probe's own lines, each with the play time and the real time since the player
started (`Probe.Log`): the start, the clock's start, waits, teleports, holds, clicks, cursor moves, errors (`error:
...`), `drawn`'s cost every 10 samples, and the end. The game's own log is `play.log`. The real one of the task play
`reach_lamp` (it measures audio, so it ran paced to real time):

```
0.00 [0.2 s] play: 10.0 s, every 0.25 s, 2 shot(s), 7 query(ies), scene Assets/Scenes/Yard.unity, on its own desktop
0.00 [0.2 s] the play's clock starts in Assets/Scenes/Yard.unity
1.00 [3.3 s] teleported next to Lamp_1: asked (-6.94, 0.00, 4.94) yaw -45.0, now at (-6.94, 0.00, 4.94)
1.00 [3.3 s] holding the player at (-6.94, 0.00, 4.94) for 1.0 s
10.53 [12.9 s] the play ended: time
```

**The player command line** (`unity.Project.play`; one command, in the build folder):

```
python tools\task_check\desk.py <copy>\Build\TaskProbe\Game.exe -screen-fullscreen 0 -screen-width 960
    -screen-height 540 -logFile <copy>\Logs\TaskProbe\play.log -taskProbe <copy>\Logs\TaskProbe\play_spec.json
    <play args...>
```

It runs with the checker's own Python and the player `Build/TaskProbe/Game.exe`, where the build was asked to put it
(never a path the build's result names: the game's own editor code runs during the build and could write any), through
`unity-heavy.ps1 -Label "task-check play <commit[:12]>" -Gpu` when the machine has the limiter (a GPU slot), with a
timeout of `--timeout` (1800 s) plus the play's waits, counted from when the job starts. `desk.py` starts the player
on a Windows desktop of its own (`WinSta0\TaskProbe`, made when it isn't there), in a job object that kills it and
everything it started when `desk.py` goes, and exits with the player's exit code. What the play wrote into `out` is
read back, then the folder deleted.

**The build** (`unity.Project.build`, `TaskProbe.EditorTools.Build.Player`; one command, in the copy):

```
<Unity.exe> -batchmode -nographics -quit -projectPath <copy> -logFile <copy>\Logs\TaskProbe\build.log
    -executeMethod TaskProbe.EditorTools.Build.Player -taskProbeBuild <copy>\Logs\TaskProbe\build_request.json
```

`<Unity.exe>` is the one the copy's `ProjectVersion.txt` names (`ugfroot.unity_editor`), through
`unity-heavy.ps1 -Label "task-check build <commit[:12]>"` when the machine has it, with a timeout of `--build-timeout`
(3600 s). The request (the reference's; a copy built for several tasks of a run lists every scene asked of it so far,
and a build that failed serves only the scenes it was given: `check.Built`):

```json
{"out": "C:/tc/38e8bcd7/ff49e5194fe4/Build/TaskProbe", "scenes": ["Assets/Scenes/Yard.unity"],
 "result": "C:/tc/38e8bcd7/ff49e5194fe4/Logs/TaskProbe/build.json"}
```

A real result (of a small two-scene project, its folder written as a copy's):

```json
{"ok": true, "scenes": ["Assets/Scenes/Menu.unity", "Assets/Scenes/Smoke.unity"], "missing": {},
 "exe": "C:/tc/9d1f2a3b/5c1e0a7f2b44/Build/TaskProbe/Game.exe", "errors": 0, "warnings": 0, "seconds": 20}
```

- The request: `out` (default `<project>/Build/TaskProbe`, deleted first), `scenes` (the scenes the task's plays open:
  `check.task_scenes`), `result` (default `<project>/Logs/TaskProbe/build.json`). An unreadable request: exit 2, no
  result.
- The result, written by `Build.Player` (compact): `ok` always; before the build `scenes` (the project's enabled build
  scenes that exist, then the requested ones they lack that exist; a missing one only warns in the log) and `missing`
  (each requested scene that names assets the project lacks, with its own `missing`, the GUIDs its file names, built-in
  ones aside, with no file behind them in the AssetDatabase, and `names`, how many it names); after it `exe`,
  `errors`, `warnings`, `seconds`; `error` only on a failure (`no scene to build: ...`, an exception, or `the player
  build failed: <its first error>`). Unity exits 0 when `ok`, else 1; scripts that don't compile stop it before the
  method runs (exit 1, no result).
- The checker counts a build passed when Unity exited 0 and the result says `ok`; a result that says it failed fails
  the build whatever the exit code, its `error` at the head of the kept `build.log`. A failed build's reason names its
  first cause in one line (`unity._cause`): the result's `error`, else the log's first compiler error
  (`<file>(<line>,<column>): error CS<n>: ...`), else its first `## Script Compilation Error for:` line. The result's
  `exe` is never started, and a `missing` of any other shape is left out. A Unity without a licence (exit 198, or `No
  valid Unity Editor license` in its log) is the machine's error, never the game's: the task reads ERROR
  (`unity.Unlicensed`).
- The build sets, for the copy only: the company name `TaskProbe.<the first 12 hex digits of the sha256 of the copy's
  folder, lower-cased>` (`seeds.saves_company` computes the same); no splash screen; no static batching (a batched
  renderer's mesh would hide its own mesh name and triangle count; set through PlayerSettings' internal
  `SetBatchingForPlatform`, a warning in the log when it can't); windowed 960x540, not resizable; run and visible in
  the background; several instances allowed; the player log on; the Mono backend; Windows x64; `BuildOptions.None`,
  not a development build (no watermark on the frame). The game's assets and code are untouched.

**The editor pass** (`unity.Project.editor_assets`, `TaskProbe.EditorTools.AssetPass.Run`; one command, in the copy):

```
<Unity.exe> -batchmode -nographics -quit -projectPath <copy> -logFile <copy>\Logs\TaskProbe\editor.log
    -executeMethod TaskProbe.EditorTools.AssetPass.Run
    -taskProbeAssets <copy>\Logs\TaskProbe\probes_editor_request.json
```

The request (the reference's, as `probes.editor_request` makes it, with the nonce of its real result):

```json
{"nonce": "497e337e009dd028c5fc3d519d88e08a",
 "measures": {"a1d1b52ff50": {"probe": "asset", "prefab": "Assets/Prefabs/LampPost.prefab",
                              "select": {"component": "Light"}, "field": "prop:Light.range", "of": "max"},
              "a69f3386782": {"probe": "asset", "asset": "Assets/Materials/M_Bulb.mat", "field": "keyword:_EMISSION",
                              "of": "count"}},
 "result": "C:/tc/38e8bcd7/ff49e5194fe4/Logs/TaskProbe/probes_editor.json"}
```

Its result, written to `result` (compact) and printed as one line of the log after `TASK_PROBES `:

```json
{"measures": {"a1d1b52ff50": {"rows": [{"name": "LampLight", "value": 9}]}, "a69f3386782": {"value": 1}},
 "nonce": "497e337e009dd028c5fc3d519d88e08a"}
```

- A measure's id is `"a"` and the first 10 hex digits of the sha256 of `json.dumps(<its set fields>, sort_keys=True)`
  (`probes.editor_id`); each measure is the task's, every set field written, the checker's defaults included (`of`).
  The nonce is new for every pass (`secrets.token_hex(16)`), so a result another pass left in the copy is never read.
- A result per id: `value` (an `asset`), `rows`, each with `name` and `value` (a scene's or prefab's objects), or
  `error`; the keys sorted. The checker takes the file, else the last `TASK_PROBES` line of the output,
  whichever carries its nonce (`probes.editor_results`); with neither, the side's asset probes fail "the editor pass
  gave no result (exit <code>)". Unity exits 0 when the pass ran, 2 for an unreadable request, 1 when scripts don't
  compile (no result); a missing licence is the machine's error, as for a build. The pass never saves.

**The scratch copy** (`seeds.py`): `<scratch>/<run tag>/<commit[:12]>`, where `--scratch` defaults to the machine
root's `.task-check` when it is on the repo's drive, else a `.task-check` beside the repo's parent folder
(`cli.default_scratch`; never inside the repo).

- The commit as committed, read from the repo's git objects and its local Git LFS store (`seeds.materialize`): each LFS
  file a hardlink of its object on the repo's volume, else a copy; an object missing from the store stops the copy
  (`git lfs fetch` it). Never written: `Tasks/`, `History/`, `Dataset/`, `Dataset.zip` at the root, in any case.
- The probe added as `Packages/com.taskprobe/` (`seeds.add_probe`): an embedded package (Unity loads every folder under
  `Packages/` that holds a `package.json`), so `Packages/manifest.json` and every other file of the game stay as
  committed. An IDE's `obj`, `bin`, `.vs` and `__pycache__` in the package folder are left out.
- Refused (`seeds.WrongEngine`, the task INVALID) when `ProjectVersion.txt` isn't `6000.3.*`: `<side>:
  ProjectSettings/ProjectVersion.txt names Unity <version>: a task's commits must be Unity 6000.3 projects as
  committed`. Unity fails on paths past 260 characters and a project's own deepest paths take most of them, so the
  checker refuses a run whose copies' folders would be longer than 90 characters and says to pass `--scratch`
  (`seeds.MAX_FOLDER`).
- Deleted with what its plays left outside it (`seeds.forget_saves`, names of the form `TaskProbe.<12 hex>` alone):
  the registry key `HKCU\Software\TaskProbe.<hash>` (PlayerPrefs), `TaskProbe_<hash>` in LocalLow and in the temp
  folder (persistent data, the cache) and the crash handler's `TaskProbe.<hash>` in the temp folder.

**Results**: `task-check/1` (`<out>/<task>.json`), `task-check-progress/1` (`progress.json`) and `task-try/1` are the
original's formats (`check.check_task`, `cli.write_progress`, `trial.try_task`), with Unity's values in a side's
entry: `engine` the Unity.exe, `slots` `unity-heavy` or `direct` (the original's UE root and `ue-heavy`), and
`missing_assets` in place of `missing_packages`: the build result's `missing` for the scenes the task plays (the
original reads a map's packages when it materializes the copy).

A crash in a play: the player log matches `Crash!!!|OUTPUTTING STACK TRACE|Fatal error|Out of memory` (`unity.FATAL`;
the original's `Fatal error|Assertion failed|Unhandled Exception`). A managed exception the game survives is not a
crash: `log_absent` checks for those.

## 6. The probe package (`tools/task_check/TaskProbe/` -> `Packages/com.taskprobe/`)

The original is a plugin of two source files (`TaskProbe.cpp`, the play loop; `TaskProbeQueries.cpp`, every measure).
The port is a package of small files, because Unity wants each MonoBehaviour in a file of its own and each query kind
is one class; one part still calls another directly, as in the original (`Inputs` calls `UiScan.Click`, `Find` calls
`Glow.Of`, `Glow` calls `DrawnRender.Glow`). The checker copies the folder into the copy as it is (section 5); the
package holds no `.meta` files, which Unity makes in the copy.

- `package.json`: the package `com.taskprobe`, for Unity 6000.0 and later.
- `Runtime/` (`Runtime/TaskProbe.asmdef`: assembly `TaskProbe`, root namespace `TaskProbe`, not auto-referenced): no
  hard dependency on any package or optional module. It references the Input System, uGUI, TextMeshPro and URP
  assemblies and compiles the code that uses each, and each optional built-in module (physics, 2D physics, audio,
  animation, particle systems, terrain, AI, UI Toolkit, image conversion), only under its `versionDefines` symbol
  (`TASKPROBE_INPUTSYSTEM`, `TASKPROBE_UGUI`, `TASKPROBE_TMP`, `TASKPROBE_URP`, `TASKPROBE_PHYSICS` and the like);
  the VFX Graph and URP decals are read by reflection. So a project without one of them still compiles it, and a
  measure whose part the project lacks has no value. `Runtime/AssemblyInfo.cs`: `[assembly: AlwaysLinkAssembly]` and
  `[assembly: Preserve]` keep it through managed stripping, since nothing in the game references it. It does nothing
  unless the player's command line has `-taskProbe`.
- `Runtime/Core/`: `Probe.cs` (the play loop: `Probe`, at execution order -32000, before the game's scripts, and its
  late half `ProbeLate`, at 32000, after them), `Json.cs` (the files' JSON: `Dictionary<string, object>`,
  `List<object>`, `double`, `bool`, `string`, null), `Find.cs` (selects, points, hierarchy order), `Query.cs`
  (`Query`, `ProbeQueryAttribute`, `RowSet`, `FrameImage`: the frame drawn after a sample), `Reflect.cs` (types and
  members by name, `prop:` paths), `Inputs.cs`, `Window.cs` (the user's-desktop fallback), `AudioTap.cs`.
- `Runtime/Queries/`: one class per query kind, `[ProbeQuery("kind")] public sealed class XQuery : Query`, found by
  reflection when a play starts (a new kind touches no other file): `ObjectsQuery`, `ComponentsQuery`, `WidgetsQuery`,
  `UiQuery`, `CameraQuery`, `LightQuery`, `GradingQuery`, `SpawnsQuery`, `PiecesQuery`, `ScreenQuery`, `AudioQuery`,
  `GroundQuery`, `DrawnQuery`; and their helpers `ObjectRead`, `Glow` (with `Effects`), `LightKit`, `UiScan`, `UiOcr`,
  `DrawnRender`.
- `Runtime/Resources/TaskProbeDepthCopy.shader`: the depth copy `drawn` needs, under `Resources/` so a non-development
  player ships it.
- `Editor/` (`Editor/TaskProbe.Editor.asmdef`: assembly `TaskProbe.Editor`, root namespace `TaskProbe.EditorTools`,
  Editor only, referencing `TaskProbe`): `Build.cs` (the player build), `AssetPass.cs` (the editor pass), and its
  readers `AssetValues.cs` and `SceneRows.cs`.
- A query never stops the play: anything unknown (a type, a member, a widget, a kind) gives empty rows or null values
  and a `query_errors` line, and an exception out of a query's `Load`, `Frame`, `Sample` or `FrameDrawn` is caught by
  the loop and becomes one.
- `probe_tests/` (beside the package; never copied into a game): the probe's regression run on the real engine.
  `run.py <scratch project>` adds the package and every family's material to the project, makes the families' scenes
  in one editor start (`Setup.cs`), builds the player once as the checker does, runs each family's plays (each twice:
  two plays of one build must write the same probe.json) and editor pass through the checker's own `unity.py` and
  `desk.py`, checks every value and prints a pass/fail table (`probe_tests/README.md`). One folder per family of
  measures; README.md gives a family's layout: `<family>/tests.py` (the manifest and the checks), `Editor/` (scene
  builders), `Scripts/` (game scripts), `plays/` (play specs: section 5's without `format` and `out`, each query with
  an id of its own) and a README saying what each play proves. In a test project each MonoBehaviour must be in its own
  file named after it (several in one file made the player fail to load the scene).
