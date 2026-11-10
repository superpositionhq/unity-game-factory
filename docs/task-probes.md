# Task probes: the contract for `probe` checks

How a task author writes the checks that decide whether a game task passes. It goes with the task format
([schemas/game-task.schema.json](schemas/game-task.schema.json), `GameTask`, game-task/1) and the `unity-write-tasks`
skill ([skills/unity-write-tasks/SKILL.md](../skills/unity-write-tasks/SKILL.md)), and `tools/validate-game.py` checks
every rule below that can be checked without running the game.

**Pass/fail is deterministic (owner's decision, 2026-10-19).** A task passes or fails only on checks the checker
computes from the running game or from the project: `build`, `boot`, `log_absent` and `probe`. A model judge never
decides pass/fail, and nothing is graded from pixel statistics of the game's frames except one: the frame's mean
luminance (`screen`, section 2.15; the owner, 2026-11-06), whose threshold is always calibrated or relative to the
start, so the same machine measures both sides. Judges (`judge`, `code_judge`, `actions_judge`) stay as **non-gating**
quality checks (`"required": false`).

Words used here:
- **the start**: the game at the task's `seed.commit`, as the agent receives it;
- **the fix**: the developers' own solution, `seed.reference` (for a feature or a change, their own implementation of
  it; `tools/validate-game.py` refuses a task without one);
- **the checker**: what builds, plays and measures a game for a task, the same way for the start, the fix and an
  agent's result;
- **the task check**: what makes a task valid before any agent is given it (section 4);
- **an object**: a GameObject. Its **parts** are the components on it and on its descendants;
- **the player**: the first object the task's `player` select matches (an object select, section 2.4), when the task
  has one; then nothing else is tried, so a select that matches nothing leaves the play without a player. Else an
  active object tagged `Player`, else one with a `PlayerInput`, else one with a `CharacterController`, else the root
  object of the camera below. Where that could find the wrong object (two tagged `Player`, say), name it with the
  task's `player`;
- **the camera**: `Camera.main` (tagged `MainCamera`, enabled), else the enabled camera of highest depth that renders
  to the screen.

Units are Unity's: metres, metres per second, degrees. Y is up. `yaw`, `pitch` and `roll` are the euler Y, X and Z
angles of the world rotation (`transform.eulerAngles`; the Inspector shows a child's rotation relative to its parent
instead), normalised to (-180, 180]; a positive `pitch` looks down.

## 1. The check

```json
{
  "name": "hero_on_ground",
  "kind": "probe",
  "required": true,
  "weight": 3,
  "needs": ["boots_clean"],
  "describe": "Two seconds after the scenario starts, the hero stands on ground near the west kiln tower instead of falling under the town.",
  "play": "look",
  "measure": { "probe": "player", "field": "y", "window": [3, 18], "agg": "min" },
  "expect": { "op": ">=", "calibrate": 0.5 }
}
```

- `describe` (required, at most 400 characters): the assertion in plain English, shown in the grade (never to the
  agent).
- `play`: where the measurement is taken (section 1.1).
- `measure`: what to measure (section 2). Every measure reduces to **one number** (booleans are 0/1).
- `expect`: the threshold that number is compared with (section 1.2).

### 1.1 Plays

- `"look"`: the checker's idle play of the task's `play_scene`: 20 s, no input, sampled every 0.5 s.
- `"drive"`: the checker's scripted drive of `play_scene`: 22 s, `<Keyboard>/w` 1-6 s, `<Keyboard>/d` 6-8 s,
  `<Keyboard>/w` 8-13 s with a jump (`<Keyboard>/space`) at 9-9.3 s, `<Keyboard>/a` 13-15 s, `<Keyboard>/w` 15-21 s;
  sampled every 0.5 s.
- A **task play**, when the outcome needs other input or another start:
  ```json
  {"name": "aim_left", "seconds": 12, "every": 0.5,
   "scene": "Assets/Scenes/Level2.unity", "args": ["-scenario", "2", "-devmenu", "2:quest=bull,6:fell"],
   "inputs": [{"t": 0.2, "teleport": [12.0, 1.8, -3.4], "yaw": 90},
              {"t": 1.0, "key": "<Keyboard>/w", "press": true}, {"t": 3.0, "key": "<Keyboard>/w", "press": false},
              {"t": 4.0, "key": "<Mouse>/delta/x", "axis": -40.0},
              {"t": 6.0, "cursor": [0.5, 0.6]}, {"t": 6.1, "key": "<Mouse>/leftButton", "press": true},
              {"t": 6.2, "key": "<Mouse>/leftButton", "press": false},
              {"t": 8.0, "widget": "RetryButton", "click": true}]}
  ```
  - `name`: lowercase letters, digits and `_`, at most 32, and not `look`, `drive`, `editor` or `trace`. Plays with
    the same name in one task must be identical.
  - `seconds`: a whole number, 5-120. No input at or after the end.
  - `every`: the sampling step, 0.1-1.0 s (default 0.5). A play samples on the first frame at or after each step, from
    1/30 s to its `seconds` plus 0.5, so a step that isn't a whole number of frames alternates (0.25 s: 0.267, 0.5,
    0.767, 1.0, ...): keep window edges off the exact moment something happens.
  - `scene` (optional): the scene this play opens instead of the task's `play_scene` (`null`: the game's first build
    scene).
  - `args` (optional): the player's command-line arguments for this play instead of the task's `play_args` (`[]`:
    none), at most 16, each `^-?[A-Za-z0-9_.:=,/-]{1,60}$`. An element starting with `-` and a letter is a flag
    (`-scenario`, `-devmenu`); anything else is a value (`2`, `2:quest=bull,6:fell`). Never a flag the checker sets
    itself or one that changes how the player runs (any case, after one dash or more): `batchmode`, `nographics`,
    `quit`, `logfile`, `projectpath`, `executemethod`, `popupwindow`, `monitor`, `parentHWND`, `single-instance`, any
    flag starting with `screen-` or `force-`, nor the probe's own (any flag starting with `taskprobe`);
    `tools/validate-game.py` lists what it refuses.
  - `inputs` (at most 400), each at time `t` (seconds of play, 0-120). Keys, buttons and axes go through the **Input
    System**, on the probe's own virtual Keyboard, Mouse and Gamepad: a game that reads the old Input Manager
    (`UnityEngine.Input`) sees none of them (section 5). One sent at `t` is queued before the game's scripts run and
    processed by the Input System at the next frame's start, so the game reads it one frame (1/30 s) after `t`. The
    Gamepad is added only when an input names `<Gamepad>` (a gamepad switches many games' button prompts).
    - a key: `{"t": 1.0, "key": "<Keyboard>/w", "press": true}` and later `"press": false`. `key` is an Input System
      control path, `^<(Keyboard|Mouse|Gamepad)>/[A-Za-z0-9/]{1,40}$`: any key of `<Keyboard>/` by its Input System
      name (`w`, `space`, `leftShift`, `f2`, `escape`); on `<Mouse>/`, `leftButton`, `rightButton`, `middleButton`,
      `forwardButton`, `backButton`; on `<Gamepad>/`, `buttonSouth`, `buttonEast`, `buttonWest`, `buttonNorth`,
      `leftShoulder`, `rightShoulder`, `start`, `select`, `leftStickPress`, `rightStickPress`, `dpad/up`, `dpad/down`,
      `dpad/left`, `dpad/right`. Any other control is a line in the play's `query_errors`, and nothing is pressed;
    - an axis event: `{"t": 2.0, "key": "<Mouse>/delta/x", "axis": 40.0}` (`axis` -1000 to 1000), on `<Mouse>/`
      `delta/x`, `delta/y`, `scroll/x`, `scroll/y` or `<Gamepad>/` `leftStick/x`, `leftStick/y`, `rightStick/x`,
      `rightStick/y`, `leftTrigger`, `rightTrigger`. The mouse's delta and scroll are one-frame impulses; a stick or a
      trigger keeps its value until set again (see the lessons on mouse axes in section 5);
    - a widget click: `{"t": 6.0, "widget": "RetryButton", "click": true}` clicks the first visible, interactable uGUI
      Selectable or UI Toolkit Button whose name (a wildcard) or type matches, as a player's click fires it: a uGUI
      Selectable gets the pointer events of a click at its centre (enter, down, up, click), a UI Toolkit Button a
      submit event, which fires `Button.clicked` (a game that handles a raw `ClickEvent` instead needs the cursor,
      below). No match: nothing happens (the play's `probe.log` says `no visible button matches '<widget>'`);
    - the cursor: `{"t": 1.0, "cursor": [0.5, 0.6]}` moves the virtual mouse to a viewport point (fractions 0-1, y down
      from the top; it starts at the centre); a following `<Mouse>/leftButton` press and release clicks there: uGUI
      through an EventSystem with an `InputSystemUIInputModule`, UI Toolkit buttons, and the game through
      `Mouse.current`;
    - a teleport: `{"t": 0.2, "teleport": [x, y, z], "yaw": 90}` puts the player's own position (its pivot) at that
      point (m), facing `yaw` (degrees; 0 when left out: a teleport always turns the player): the way to reach a test
      spot. The probe doesn't move it to the ground or out of a collider afterwards: take the point from where the
      player stands in a play (the `track` of its `probe.json`);
    - a teleport next to an object: `{"t": 0.2, "teleport_to": <object select>, "distance": 2.0, "offset": [x, y, z],
      "face": <Point>}` places the player `distance` m (default 2) from the object the select matches nearest to the
      player (the player and its own children left out; of two as near, the first in hierarchy order), on the
      player's side and level with it, plus `offset` (default none), facing `face` (a point, section 2.13) or else
      that object. The way to reach a spot each build chooses itself (the ore a fix placed, a door it moved).
      **Level is pivot to pivot**: the player's own position goes to the height of the object's position plus
      `offset`'s y, and nothing then moves it to the ground or out of a collider (next to a coin hovering 0.8 m up,
      `"offset": [0, -0.8, 0]` puts a player whose pivot is at its feet on the ground). **A select matches every
      object that fits it, and the nearest wins**: `{"name": "Coin*"}` also takes a `CoinSpawner`, and a player
      standing beside the spawner goes there; select the instances themselves (their exact name, their own component,
      or `has`: section 2.4). No match: nothing happens. The play's `probe.log` says what each one did,
      `teleported next to <name>: asked (x, y, z) yaw <degrees>, now at (x, y, z)` or
      `teleport_to skipped (no object matches)`: check it in the fix's play;
    - holding the player there: `"hold": 5` on a `teleport` or `teleport_to` (seconds, up to 120) puts the player back
      at the spot (its position; its view stays free) after every frame's game logic for that many seconds of play.
      For a game that sets its player's ground position every frame, which would otherwise undo a teleport at once.
      Without `hold`, a teleport places the player once;
    - a wait in real time: `{"t": 8.0, "wait": 30}` (seconds, more than 0). Plays run on a fixed 30 fps clock as fast
      as the machine renders, so what runs on the wall clock (a menu that pages on `Time.unscaledTime` or
      `Time.realtimeSinceStartup`, a timer on the system clock) sees less real time than the play's seconds. At `t`
      the play's clock holds while the game keeps running, paced to real time (each frame waits for the wall clock to
      catch up with the game's own time), until `wait` real seconds and `wait` seconds of game time have both passed;
      nothing is sampled, sent or screenshot meanwhile; then the play goes on from `t`. A play's waits add at most
      300 s in all, and its timeout grows by them; `seconds`, windows and `at` stay in play time, within 120 s.
  - A play that measures audio (an `audio` measure, section 2.16) runs paced to real time, so its sounds keep time
    with the game; every other play runs as fast as the machine renders. No play is heard on the machine (section
    2.16).
- `"editor"`: one batchmode editor pass over the project as saved; takes only `asset` measures, and `asset` measures
  are taken only there.
- `"trace"`: the agent's own trace; takes only `trace` measures, and `trace` measures are read only there. Trace
  probes never gate (section 3).

Every play of the game, the checker's own (look, drive, a boot check's) and a task play alike:

- **The scene.** It opens the task's `play_scene`, with the task's `play_args` on the player's command line
  (`"play_scene": "Assets/Scenes/Harbor.unity"`, `"play_args": ["-scenario", "2"]`; `play_args` hold at most 16
  items, under the same rules as a task play's `args`), unless a task play has its own `scene` or `args` key. With
  `play_scene` null, the game's own first build scene plays.
- **The game's first build scene** doesn't run when the play opens another one. The probe asks for the play's scene
  before the first build scene has woken up: that scene's objects still get `Awake` and `OnEnable` (Unity has loaded
  it already), then are destroyed before their `Start` and first `Update`. So a singleton a boot scene makes in
  `Awake` with `DontDestroyOnLoad` exists in the play; anything it sets up in `Start` does not. A game that needs its
  boot scene to run is started through its own `play_args` (`["-scenario", "2"]`) with `play_scene` null.
- **The clock.** A play runs at a fixed 30 frames a second (`Time.captureFramerate`: play time is frames / 30, and
  every `t`, `window` and `at` is play time), as fast as the machine renders. It starts at 0 when the play's scene has
  loaded, **holds while any scene is still loading** (an async load takes real time, not game time; for one load at
  most 300 frames, about 10 s of real time, since a load the game parks never finishes: then the clock goes on and
  `probe.log` says so) and during a `wait`, and keeps counting when the game pauses itself (`timeScale` 0). The game's
  `Time.time` runs on this clock. `Time.unscaledTime`, `Time.unscaledDeltaTime`, `Time.realtimeSinceStartup` and the
  system clock follow the wall clock instead: a 20 s play takes a few seconds of them, a different number every time,
  so whatever a game drives by them hardly advances in a play and differs between two plays. Give it real time with a
  `wait`.
- **Saved data.** Every play starts from clean saved data. The checker's build gives the copy's player a company name
  of its own (`TaskProbe.<hash>`, which `Application.companyName` reads in a play), so its PlayerPrefs and
  `Application.persistentDataPath` are its own, never the real game's; the probe clears both when the play starts.
- **Focus.** The player runs windowed at 960x540 on a Windows desktop of its own ([task-check.md](task-check.md),
  "The plays"), where it counts itself focused for the whole play (`Application.isFocused` is true, no object gets
  `OnApplicationFocus(false)`): a game that pauses when it loses focus plays on.
- **The build.** The player is the checker's own build of the commit (task-check.md, "What it does", step 3): without
  static batching, so each renderer keeps its own mesh name and triangle count for `mesh` selects and `pieces`, and not
  a development build, so no watermark sits on the frame.

### 1.2 Thresholds (`expect`)

`op` is one of `>`, `>=`, `<`, `<=`, `==`, `!=`. The threshold is one of:

- **A literal value**, `{"op": ">=", "value": 1}`: for facts that don't depend on the scene (counts, booleans, "not
  the default material"). `==` and `!=` take literals only (they compare within 1e-9).
- **Calibrated**, `{"op": ">=", "calibrate": 0.5}` with `0 < f < 1`: for continuous quantities. The checker measures
  the start (`s`) and the fix (`r`) in its own environment and sets the threshold `s + f * (r - s)`; `op` says on which
  side the fix lies (`>`/`>=` when `r > s`). Needs `seed.reference`. A required calibrated check whose start and fix
  measure the same (within 1e-6 relative) makes the task invalid. Calibrated thresholds are kept by the checker, never
  written into the task.
- **Relative to the start**, for an outcome the fix is only one fair way of reaching (most features and changes), or a
  task with no fix: `{"op": ">=", "start_times": 1.3}` (threshold `s * 1.3`) or `{"op": ">=", "start_plus": 5}`
  (threshold `s + 5`), measured on the start.

Where the number depends on what a build chose, the threshold is calibrated or relative to the start, never a literal
value, and `tools/validate-game.py` refuses a literal: `objects` `spread`, `bounds_change`, `pose_change`, `glow` and
`spin`; `components` `intensity`, `extent_*`, `bounds_change`, `pose_change`, `glow` and `spin`; `pieces` `triangles`
and `visible_triangles`; every `screen` field; `audio` `volume`, `max_volume` and `level`; `ground` `range`; every
`drawn` field but `drawn`. Each section says why.

When the start can't be measured (its play ended before the window), a calibrated threshold anchors on the fix alone:
`r - 0.25 * |r|` for `>`/`>=`, `r + 0.25 * |r|` for `<`/`<=` (a fix of 0 leaves no threshold, as a quarter of
nothing is no margin). When the fix can't be measured, or the start of a `start_times`/`start_plus` check can't, the
task is invalid for that check if it is required. A probe left without a threshold, this way or by a start and fix
that measure the same, fails as `uncalibrated` on every side; one that isn't required is only a note (section 4).

## 2. Measures

Which measure answers which question (each section has its fields, defaults and limits):

| To check | Measure |
|---|---|
| where the player is, how far it moved, how fast | `player` (2.2) |
| where the camera sits, whether the player is in view or hidden from it | `camera` (2.3) |
| an object: there or not, where, its state (`prop:`, `anim:`), whether it moved or broke, whether it gives light (`lit`: a lamp, whatever lights it) | `objects` (2.4) |
| one part of an object: a Light that is on, a live effect, a renderer, a part that spins | `components` (2.5) |
| one UI widget's own state: a slider's value, a toggle, a sprite | `widgets` (2.6) |
| how much light reaches a point | `light` (2.7) |
| the colour grade, a post-processing setting | `grading` (2.8) |
| how many objects appeared or went | `spawns` (2.9) |
| a line in the player log | `log` (2.10) |
| an asset, a material, a prefab or a scene as saved | `asset` (2.11) |
| how the agent worked (never gating) | `trace` (2.12) |
| how many meshes are placed, and their triangles | `pieces` (2.14) |
| how bright the frame looks on screen | `screen` (2.15) |
| what plays, and how loud at the listener | `audio` (2.16) |
| the height of the ground, its relief | `ground` (2.17) |
| what the HUD or a menu shows, whatever draws it: text, a number, a clock, whether it updates | `ui` (2.18) |
| what is drawn at a spot or along a line: motion, colour, a beam's reach | `drawn` (2.19) |

How a play gets there (keys, clicks, teleports, waits): section 1.1. Literal or calibrated: section 1.2. Points and
`near`: section 2.13. Why a probe has no value: section 3.

### 2.1 Common fields

- `window`: `[t0, t1]` seconds of play time (ends inclusive), or `at`: `[t, ...]` (at most 40 times, each 0-120; the
  sample nearest each time, when one is within 0.26 s of it) or `"end"` (the last sample); not both. Default: the
  whole play.
- `agg`: how the samples reduce to one number: `min`, `max`, `mean`, `first`, `last`, `delta` (last minus first),
  `any` (1 if any sample is non-zero), `all` (1 if every sample is non-zero), `count` (number of non-zero samples),
  `sum`, `range` (max minus min), `std` (standard deviation), `changes` (how many times the value changes between
  consecutive samples), `rises` and `falls` (how many samples read more, or less, than the sample before: which way a
  value moved, a score that only rises reads `falls` 0, a reset reads as a fall). Default `last` (`sum` for `spawns`).
- `of` (`objects`, `components`, `widgets`, `ui`, and `asset` with a `select`): how the selected objects, components,
  widgets or UI elements combine within one sample: `count` (how many match and have a non-zero value), `any`, `all`,
  `min`, `max`, `mean`, `sum`, `first`. **Default `count`.** A measure that reads a value (a position, an extent, a
  `prop:`, a text match, a percent) needs `"of": "first"` or another value reducer, or it counts instead of reading.
  With `"field": "count"`, `of` is ignored. Objects and components match in hierarchy order: by scene, then the root's
  place in its scene, then sibling order. That order is the same in every play of one build, but the fix may change
  the scene: select the one you mean (by name, tag or `near`) rather than take the first of a broad select.
- **Every match counts, past 200.** The probe keeps at most 200 rows a sample in `probe.json` but reads every match:
  `"field": "count"` is the whole selection's size, and `of` (`count`, `any`, `all`, `min`, `max`, `mean`, `sum`) reads
  every match's value from the probe's summary of them (the sample's `total` and `full`). Only `"of": "first"` and
  values read through `match`, `to_angle` or `to_axis` read the first 200 rows alone.
- `to_angle` / `to_axis` (angle fields only: `yaw`, `pitch`, `roll`, `rel_yaw:<Part>`,
  `world_yaw:`/`world_pitch:`/`world_roll:<Part>`, and a `prop:` that holds an angle): angles are normalised to
  (-180, 180]. `"to_angle": -90` turns the field into its shortest absolute angular distance to that angle, 0-180 (so
  270 and -90 are the same). `"to_axis": 90` turns it into the distance to that axis, 0-90: a direction and its
  opposite are one axis (a straight road piece turned 90 or -90). One or the other, not both.
- `match` (string values: text, names, enum-like strings, sprite and clip names): a regular expression, searched for
  anywhere in the string (`^...$` to match all of it); the value is 1 when it matches, 0 when not. A string without
  `match` has no value.

Rows with no value are skipped by `of`: `count`, `any`, `sum` and `all` of none are 0, the others have no value.
Samples with no value are skipped by `agg`, and a window where no sample has a value has no value, whatever the `agg`.
A probe whose measure has no value fails, with the reason in its detail (section 3). Anything the probe doesn't know (a
component type, a member, a widget, a kind) gives empty rows or no value and a line in the play's `query_errors`; it
never stops the play. (The editor pass is stricter: section 2.11.)

### 2.2 `player`: the player

`{"probe": "player", "field": "x|y|z|speed|moved", ...}`, sampled through the play: the player's position (its
transform's, so its pivot). `speed` in m/s between samples; `moved` = distance from the first sample (m).
`"field": "dist", "to": <Point>`: distance to a point (section 2.13).

### 2.3 `camera`: the player's camera

`{"probe": "camera", "field": "distance|height|pitch|yaw|fov|occluded|player_on_screen", ...}`: `distance` (m) from
the camera to the player's position (its pivot, as `player` reads it, not its centre); `height` = the camera's y minus
that position's y (m); `pitch`, `yaw` (degrees, of the camera's world rotation); `fov` the vertical field of view in
degrees (0 for an orthographic camera); `occluded` = 1 when a ray from the camera to the player's centre hits a
collider (triggers, the Ignore Raycast layer, the player's colliders and colliders under the camera itself are
ignored); `player_on_screen` = 1 when the player's centre projects inside the viewport, in front of the camera. The
player's centre: the centre of its enabled colliders that aren't triggers (its descendants' too), else of its drawn
renderers, else its position.

### 2.4 `objects`: GameObjects in the scene

```json
{"probe": "objects",
 "select": {"component": "CastlePiece", "tag": "Wall", "name": "Tower*", "near": {"point": {"xyz": [0, 0, 0]}, "radius": 50}},
 "field": "y", "at": "end", "of": "first", "agg": "last"}
```

- `select`: every key given must match. By default only objects active in the hierarchy match.
  - `component`: a component on the object itself (one on a descendant is found with `has`, below), by its C# type
    name (`CastlePiece`, `MeshRenderer`, `Rigidbody`) or full name (`MyGame.CastlePiece`); the type, any of its base
    types and its interfaces match (`Collider` takes in `BoxCollider`; `MonoBehaviour` every script).
  - `tag`: the object's tag. `layer`: its layer, by name. `name`: a wildcard on the GameObject's whole name (`*` any
    run of characters, `?` one character, any case). Every object whose name fits matches: `Coin*` takes a
    `CoinSpawner` or a `CoinPool` as well as the coins, and a select that picks one match (`teleport_to`, a point,
    `"of": "first"`) may pick the spawner. To pick the things themselves, select them by their own component
    (`"component": "Coin"`) or by their full name: an object instantiated at run time is named `<Prefab>(Clone)`
    (`Coin(Clone)`).
  - `near`: its position (its transform's, the pivot) within `radius` m of a point. `{"player": true}`: the player.
  - `has`: a part the object carries, `{"has": {"component": ..., "lit": true, "visible": true, "near": {"point":
    <Point>, "radius": m}}}`: the object matches when at least one of its parts (a component on it or on any of its
    descendants, inactive ones included) matches every key given. `component` is the part's type or a base type, as a
    `components` select names it; `lit: true` reads it as the components `lit` field does (a Light that lights the
    scene, a drawn mesh renderer whose material gives off light, from its material properties or else as rendered, or
    a live particle system that draws light; section 2.5); `visible: true` keeps a Renderer that is drawn, as the
    components `visible` field reads a Renderer; `near` measures from the part's own place, not the object's. At least
    one key, and only `true` for `lit`, `visible` and `simulating` (below). The way to select by what an object does
    ("an object that gives light", "an object with a drawn mesh near here") rather than by the type or name a build
    gave it. It works in every object select: these, other measures' (`owner`, `ground`), points (section 2.13) and
    `teleport_to` (section 1.1). A scene as saved (`asset`) takes no `has`. `"simulating": true` (the part is, or
    belongs to, a non-kinematic Rigidbody or a Dynamic Rigidbody2D) finds an object by what it can do:
    `{"teleport_to": {"has": {"simulating": true, "near": ...}}}` reaches the nearest object a player can shove,
    whichever component a build used.
  - `inactive: true`: inactive objects match too (they read `active` 0).
- `field`:
  - `count`: the selection's size (`of` ignored);
  - `x`, `y`, `z` (m), `yaw`, `pitch`, `roll` (degrees), `scale` (the mean of the absolute lossy scale's axes);
  - `extent_x`, `extent_y`, `extent_z`: **the object's drawn renderers' world-aligned half-size** (m). The box is the
    union of the bounds of the renderers in the object and its descendants that are drawn (enabled, active, not
    forced off). Colliders, lights, audio, particle and trail renderers (they span where their particles went) and
    renderers with empty bounds (a MeshRenderer without a mesh) don't count; no value when the object draws nothing.
    A LODGroup's lower LODs stay enabled, so their renderers count here (and in `spread` and `hidden`) too.
    World-aligned, so a rotated object's extent mixes its own axes (an object turned 90 degrees reports its width as
    `extent_z`);
  - `active` (active in the hierarchy); `hidden` (1 when it is inactive, or it has renderers and none is drawn);
    `collision` (it or a descendant has an enabled collider that isn't a trigger); `speed` (m/s): its own velocity
    when it reports one that isn't zero (the first of these it has: a non-kinematic Rigidbody, a Dynamic Rigidbody2D,
    an enabled CharacterController, a NavMeshAgent on its NavMesh), else how far it moved since the previous sample
    over that time. One with such a velocity source at rest reads 0 on its first sample; one without has no value the
    first time it is seen;
  - `spin` (deg/s): how fast the object turns, the fastest of its mesh parts (its MeshRenderers with a mesh and its
    SkinnedMeshRenderers, in it and its descendants, drawn or not; none: its own transform), each read as a
    component's `spin` (section 2.5). **Its threshold is calibrated or relative to the start, never a literal value**;
  - `simulating`: 1 when the object or a descendant has a non-kinematic Rigidbody or a Dynamic Rigidbody2D (pieces
    that broke loose, a ragdoll);
  - `spread` (m): how far apart the object's parts are, the diagonal of the world-aligned box around their centres:
    each renderer `extent_*` counts by its bounds centre; 0 with one part, no value when it draws nothing. A whole
    crate reads its pieces' own layout; one broken into pieces that fell apart reads more, though its pieces stay
    drawn and tagged. **Its threshold is calibrated or relative to the start, never a literal value**;
  - `changed`: 1 when the object differs from the first sample it was seen in (the play's first sample, for an object
    there from the start), else 0. Its parts are its mesh parts, as `spin` counts them, drawn or not. It reads 1 when
    a part was hidden or shown (drawn: enabled, active, not forced off), a part drawn then is gone or a part drawn now
    was not there, a part's world bounds moved more than 0.01 m (moved, turned, scaled), or a skinned mesh's pose
    moved: its bones more than 0.05 m in all, in the mesh's own space, or its local bounds more than 0.01 m. So an
    object that breaks by hiding a part, or by animating its pieces in place with no physics, reads 1, as one that
    moves does; one left alone reads 0. An object animated from the start (a looping idle) reads 1 too: read it after
    the start of the play that matters, or read `pose_change`. Its descendants' parts count as its own: a spawner
    with no renderer reads 1 once the things it spawns as its children appear or move;
  - `bounds_change` (m): the furthest any face of a part's world bounds moved since that first sample, the largest
    over its parts; `pose_change` (m): how far its skinned meshes' bones moved since then in their own space, summed
    over every bone (no value without a SkinnedMeshRenderer). **Their thresholds are calibrated or relative to the
    start, never a literal value**; `changed` takes a literal;
  - `lit`: 1 when the object gives off light, whatever made it: any of its Lights lights the scene (as `on` reads it,
    section 2.5, and its colour isn't black), any of its mesh parts is drawn with a material whose light is above a
    luminance of 0.01 (an emissive material, or an unlit one, whose colour is what it gives off), or any of its
    particle systems is live and draws light (section 2.5). **This is the way to check for light**: a lamp lit by a
    Light and a lamp drawn by a glowing material read the same. Takes a literal;
  - `glow`: how much light, one amount summed over its lit sources so either kind compares: a Light's intensity in
    Unity's own units (not candelas) times its colour's luminance (linear, and its colour temperature when the
    project and the Light use it); a mesh's brightest material's luminance times a quarter of the surface of its
    local bounds in m2, scaled (what a glowing surface that size gives every way); a source read as rendered, as
    section 2.5 says. **Its threshold is calibrated or relative to the start, never a literal value**. A row with
    `lit` or `glow` also carries `glow_sources`, the kinds lit (`light`, `emissive`, `unlit`, `effect`), and
    `glow_read`, how its renderers were read (`props`, `render`, or `unread`: there was no way to read one, and then
    the row has no value unless another source is lit), for the logs; neither is a field to measure. How a renderer's
    light is read, and its limits: section 2.5;
  - `prop:<Component>.<member>[.<sub>]` or `prop:<member>`: read by reflection, instance fields and properties,
    public or not (static members and indexers are not read). The component by type name on the object, else the
    first in its descendants (`prop:Health.current`, `prop:Rigidbody.mass`, `prop:Light.intensity`); `prop:<member>`
    alone reads the GameObject, else its Transform (`prop:activeSelf`, `prop:localScale.y`). Numbers and booleans as
    numbers, enums as their number, object references as 1 when set and 0 when not, strings through `match`; an array
    or list without an index gives its length, `[i]` its element (`prop:Inventory.items[0]`); a dictionary's entry by
    its key (`prop:Inventory.counts.coins`); a vector's `.x`, `.y`, `.z` and a colour's `.r`, `.g`, `.b`, `.a`. Read a
    renderer's `sharedMaterial` and a MeshFilter's `sharedMesh`: the plain `material`, `materials` and `mesh` give
    that object a copy of its own, which changes the game;
  - `bone:<Component>.<Bone>.x|y|z`: the world position of a bone of a SkinnedMeshRenderer, a human bone of an
    Animator (`bone:Animator.Head.y`), or a descendant transform of that name. Bone, Part (below) and Animator
    parameter names are written as Unity has them, dots, spaces, colons, parentheses and hyphens included
    (`bone:SkinnedMeshRenderer.mixamorig:Hips.y`, `bone:Animator.hand.L.y`, `world_yaw:Lamp (1)`);
  - `rel_yaw:<Part>`: the part's world yaw minus the object's (turning the whole object doesn't change it);
  - `world_yaw:<Part>`, `world_pitch:<Part>`, `world_roll:<Part>`: the part's own rotation in the world (degrees),
    whether its object or the part itself turned; `forward:<Part>.x|y|z`: its forward unit vector in the world. For a
    Light this is the way its light travels: a directional light pointing down has a positive `world_pitch` and a
    negative `forward:<Part>.y`. A **Part** is the object itself or a descendant, by its GameObject name, else the
    first of them carrying a component of that type name (`world_pitch:Light`, `forward:Sun.y`);
  - `facing_vs_velocity`: degrees between the object's forward and its velocity (0 when it moves forward; no value
    under 0.1 m/s);
  - `anim:<Parameter>`: a parameter of its Animator (on it, else the first in its descendants, enabled and with a
    controller): floats and ints as numbers, bools as 1/0, a trigger has no value; `clip`: the name of that Animator's
    current clip on layer 0 (the heaviest while it blends), through `match`. Unity has no built-in AI blackboard: read
    an AI's state with `anim:` or a `prop:` of the component that holds it.

A row (in `probe.json`, for the logs) holds the object's `name` and a `class`: its first script's type, else its first
Behaviour or Renderer, else its first other component (its Transform and MeshFilter aside), else `GameObject`.

### 2.5 `components`: components in the scene

`{"probe": "components", "select": {"component": "ParticleSystem", "owner": <object select>, "near": ...}, "field":
"count|active|visible|...", ...}`: components of a type (particle systems, decals, audio sources, lights, renderers,
the moving parts of an object), optionally of an owner object (on it or on its descendants) and near a point (by its
object's position), so effects that are not objects of their own count too. `"name": "<wildcard>"` keeps components
whose object's name matches (as an object select's `name`, section 2.4), `"mesh": "<wildcard>"` keeps components whose
mesh asset's name matches (a renderer's, a MeshFilter's or a MeshCollider's, as `pieces` has it), and `"visible": true`
only the components drawn (as the `visible` field reads them), so one part, a lamp's bulb, can be picked out.
Components of inactive objects are left out unless the select says `"inactive": true`. `"effect": true` keeps only live
effects, with or without `component`: a ParticleSystem that is alive (playing or holding particles), a VisualEffect
holding particles, an enabled DecalProjector, a TrailRenderer drawing points; a pooled or finished system not at all.
With `near` and `count`, how many effects play at a spot: read before and after a restart (an input of a task play), it
catches effects that pile up. A select names its `component`, or `effect`, or both.
A Terrain is one component however many trees it draws: count placed meshes with `pieces` (section 2.14).
A row (in `probe.json`, for the logs) holds its object's name as both `name` and `owner` (a Unity component has no
name of its own; `owner` is not the object the `owner` select matched) and the component's type as `class`.

- `field`: `count`; `active` (enabled and active in the hierarchy; a ParticleSystem also playing or holding
  particles; an AudioSource also playing); `visible` (a Renderer that is enabled, active and not forced off; any other
  component: 1 when its object is active);
- `x`, `y`, `z` (m) and `speed` (m/s) of the component's transform, as objects have them (section 2.4): `speed` is its
  object's own velocity when that isn't zero, else how far it moved since the previous sample. Cars that are parts of
  one road object read here;
- `spin` (deg/s): how fast the component's transform turns in the world, from its rotation read every frame and summed
  since the previous sample (so a part turning many times a second still reads); the first time it is seen, the
  angular velocity of a non-kinematic Rigidbody on its object, else no value then. Any part near a point: select
  `Renderer` with `near`; each part of one object: select by `owner`. No name is needed. A turn drawn by bones (a
  skinned rotor) or by a material reads 0 here: `drawn`'s `motion` (section 2.19) sees it;
- `extent_x`, `extent_y`, `extent_z` (a Renderer's or Collider's world bounds half-size, m) and `simulating` (it is,
  or belongs to, a non-kinematic Rigidbody or a Dynamic Rigidbody2D; a collider by the body it is attached to);
- `changed`, `bounds_change`, `pose_change`: a Renderer against the first sample it was seen in, as an object's
  (section 2.4) for one part: hidden or shown, its world bounds moved, a skinned mesh's pose moved (`pose_change` has
  no value unless it is a SkinnedMeshRenderer);
- `lit` and `glow`: as an object's (section 2.4), for one source: a Light, a MeshRenderer or SkinnedMeshRenderer with
  its materials, or a particle system (its ParticleSystem or its renderer); no value for any other component (a
  SpriteRenderer, a LineRenderer or a TrailRenderer among them). A particle system is read as rendered, as a mesh is
  below (its world bounds for the box), lit when it is live (playing or holding particles), its renderer drawn and its
  brightest pixel above 0.01. A row it lights names `effect` in `glow_sources`. **Check for light with these**,
  whatever the build made it with;
- `intensity` (a Light's own intensity, in its units) and `on` (1 when the Light lights the scene: enabled, active in
  the hierarchy, of an intensity above 0; the `light` probe counts the same lights). A lamp switched off by intensity 0
  or by disabling the Light reads 0. One switched off by deactivating its object reads 0 when the select says
  `"inactive": true`; without it, the Light is no longer selected (no row: `count` drops, `"of": "max"` has no value).
  They see Lights only: use them when a task really needs a Light, else `lit` and `glow`;
- `prop:<path>`: a member of the component itself by reflection, as an object's `prop:` reads it
  (`{"component": "AudioSource"}` with `prop:pitch`);
- **`intensity`, `extent_*`, `bounds_change`, `pose_change`, `glow` and `spin` thresholds are calibrated or relative
  to the start, never a literal value**; `on`, `lit`, `simulating`, `changed`, positions and speeds take a literal.

How `lit` and `glow` read a mesh renderer, one of two ways; which one depends on its materials' shaders alone, never
on their values. A renderer that isn't drawn (disabled, inactive, forced off) reads dark without being read either
way.
- **From its material properties**, when every material it draws with has a shader of one of two kinds (a Shader
  Graph is neither, whatever its properties): a shader whose name contains `unlit` in any case (URP's
  `Universal Render Pipeline/Unlit`) and that has `_BaseColor` or `_Color` gives that colour times its main texture's
  mean; a shader with `_EmissionColor` that declares an `_EMISSION` keyword gives, when the material has the keyword
  enabled, its emission colour times the mean of its `_EmissionMap` when one is set (keyword off: no light, whatever
  the colour). Colours are read in linear space, as the shader gets them (an HDR emission colour the material holds
  as (4, 3, 2) has a luminance of 12.9). MaterialPropertyBlock overrides on the renderer count. The brightest material
  counts, over the renderer's whole local bounds; lit above a luminance of 0.01. `glow_read` is `props`.
- **As rendered**, when any material has another shader (a Shader Graph, or a custom shader whose glow comes from its
  own code): the renderer is drawn alone with every light off, ambient black, reflections and fog off, orthographic
  from four fixed views around it (128 x 128, in HDR), so what is left is what it gives off itself. The views frame
  its own local bounds box (a skinned mesh's in its root bone's frame). `lit`: its brightest pixel's luminance above
  0.01. `glow`: the views' luminance x pixel area summed, over the area of its bounds box they see, times a quarter of
  the box's surface: the same amount as from the properties for a mesh glowing all over, that part's share for a mesh
  glowing in part (a lamp that is one region of a larger mesh's material, say). `glow_read` is `render`. What such a
  render can't switch off, and its other limits: section 2.19.

Limits:
- a renderer read from its properties counts its brightest material over its whole bounds, so a lamp post with a small
  glowing bulb reads the post's size: compare a `glow` with itself, calibrated or relative to the start, or select the
  bulb by `mesh` or by its object's name;
- a mesh drawn only on its inside (a sky dome, a room seen from within) is rendered from outside, usually as nothing,
  so it reads dark that way; one on a layer only a filtered URP renderer draws (section 2.19) reads dark that way too;
- rendering is done at the sample, each renderer once a sample, at most 64 renders a sample over every query (past
  that, a source isn't read that sample: no value, `glow_read` `unread`);
- a Light's cookie is not read; decals and UI are not sources, nor are sprites, lines and trails (3D text is a mesh
  source: it draws with a MeshRenderer); select the lamp (by owner, tag, `mesh` or `near`), not every renderer in the
  scene.

### 2.6 `widgets`: the UI on screen

`{"probe": "widgets", "select": {"component": "TextMeshProUGUI", "name": "AmmoText"}, "field": "text", "match":
"AMMO\\s*\\d+", "of": "any"}`.

- What is searched: uGUI (the `UnityEngine.UI` Graphics and Selectables, TextMeshPro text) on every canvas of the
  loaded scenes, and UI Toolkit (every element of every `UIDocument`'s panel), hidden and inactive widgets included.
  World-space canvases are included too, their rectangle projected through the camera (`ui` leaves them out). A
  widget is a uGUI component's object or a UI Toolkit element: one row per GameObject or element, not per component.
  A row's `class` is the matched component's type, else the object's Selectable, else its text or graphic (a UI
  Toolkit element's: its type).
- `select`: `component` (a uGUI component's type: `Image`, `Slider`, `TextMeshProUGUI`, a game's own component on a
  canvas object; or a UI Toolkit element's type: `Label`, `ProgressBar`, a game's own element; base types match too,
  so `Button` takes uGUI and UI Toolkit buttons alike), `name` (a wildcard on the GameObject's or the element's name),
  `text` (a regular expression its text must match), `visible`.
- **To check what a HUD shows, whatever draws it, use `ui` (section 2.18).** `widgets` reads a named widget's own
  state, so it sees a HUD only when a build made it with that widget; a HUD made with the other UI system, or drawn
  with `OnGUI`, reads as absent.
- `"visible": true` in the select keeps only the widgets the `visible` field reads 1 for: never an inactive, disabled
  or fully transparent one, nor one under an inactive object, a disabled Canvas, a CanvasGroup at alpha 0 or a UI
  Toolkit element with `display: none` or `visibility: hidden`, nor one culled by a RectMask2D or entirely outside the
  frame, so `count` counts what is on screen (a warning bar's shown messages, not the ones the game keeps hidden).
- `field`: `count`; `visible`; `text` (a Text's, a TextMeshPro's or a TextElement's text, with `match`: rich text tags
  stripped, a TextMeshPro typewriter reveal (`maxVisibleCharacters`) honoured; a Selectable with no text of its own
  reads its first child label's, so a Button reads its label); `percent` (0-1: a Slider's normalized value, a filled
  Image's fill amount, a ProgressBar's share, a Scrollbar's or Scroller's position); `value` (a Slider's value, a
  Toggle's 1/0, a ProgressBar's, Scrollbar's or Scroller's value, a Dropdown's selected index); `interactable` (1 when
  a uGUI Selectable is interactable and enabled, no value for another uGUI widget; a UI Toolkit element's enabled
  state); `has_brush` (1 when an Image's sprite, a RawImage's texture, or a UI Toolkit element's image or background
  image is set; no value for another uGUI widget); `brush` (that image's name, with `match`); `x`, `y`, `w`, `h` (the
  widget's rectangle in viewport fractions 0-1, **y down from the top**, whatever anchor or layout placed it; no value
  for a widget with a zero-size rect, such as one under `display: none`, or a world-space one behind the camera).
- A project without the TextMeshPro essential resources draws no TMP text, but `widgets` and `ui` still report its
  `.text`.

### 2.7 `light`: light reaching a point, as the engine computes it

`{"probe": "light", "point": <Point>, "field": "illuminance|exposure|brightness", ...}`:
- `illuminance`: the sum over the Lights that are on of their contribution at the point (point and spot lights by
  intensity x colour luminance x URP's distance and cone attenuation; directional lights by intensity x colour
  luminance; the colour linear, its colour temperature applied when used), each with a wall check: a ray from the
  light to the point (from the point toward a directional light, 2000 m) that any collider stops but a trigger, one
  on the Ignore Raycast layer, the player's and the Light's own (on its object or under it). The wall check runs for
  lights with shadows off too, though URP itself lights through walls then. Area lights are skipped (URP only bakes
  them). Plus the ambient light: the ambient probe's upward value in every mode (flat ambient ignores
  `ambientIntensity`; gradient ambient is a mix of the sky, equator and ground colours, not the sky colour), times the
  open share of 9 upward rays (straight up and 8 around it at 45 degrees, 2000 m each, stopped as the wall check is).
  It is in Unity's own light units, not lux;
- `exposure`: `2^postExposure` of the URP volume stack at the camera (section 2.8); 1 without one (so at a play's
  first sample: section 2.8), or when the camera's post-processing is off. URP has no auto-exposure;
- `brightness`: `illuminance * exposure`, what the player sees at that point.

The sample's value also holds the parts of `illuminance` (`local`: point and spot lights, `directional`, `sky`: the
ambient), `lights` (how many sources lit it) and `point`, for the logs. A point that doesn't resolve: no value.

A Light counts when it is on: enabled, active in the hierarchy, of an intensity above 0 (`grading`'s sun the same).

It sees no post-processing beyond post exposure (no colour grading, vignette, ambient occlusion, bloom); for what
reaches the screen, use `screen` (section 2.15). It sees Lights only: whether a lamp is on, whatever lit it (a Light,
or a renderer drawn with a glowing material), is `lit` of the lamp (section 2.4).

### 2.8 `grading`: the colour pipeline

`{"probe": "grading", "field": "cast|warmth|tint|saturation|contrast|grey|post:<Component>.<parameter>", ...}`: the
URP volume stack in effect at the camera (global and local volumes by priority and blend weight), read as the shader
constants URP itself prepares (colour balance as LMS coefficients, contrast, saturation, colour filter, post exposure,
lift, gamma and gain, tonemapping), and the key lights: the strongest directional light that is on (the sun), the
`RenderSettings` ambient (the sky) and fog. The checker runs a neutral grey (0.18), lit by the key light's hue (the
sun's colour, else the sky's), through URP's own LDR grading in its order (post exposure, then clipped to 0-1, white
balance, contrast, colour filter, gain and lift, gamma, hue shift, saturation, then clipped to 0-1): `grey` = the
resulting luminance; `cast` = its chroma, (max - min) / luminance (0 = neutral); `warmth` = (R - B) / luminance;
`tint` = (G - (R + B) / 2) / luminance; `saturation`, `contrast` = the effective multipliers (1 = neutral: a Color
Adjustments saturation of -30 reads 0.7). `post:<Component>.<parameter>` (`post:Bloom.intensity`,
`post:Vignette.intensity`, `post:ColorAdjustments.postExposure`, `post:MotionBlur.intensity`, ...): a volume
parameter's effective value at the camera after blending.

- The stack: the probe blends the volumes for the camera's volume trigger and volume layer mask at each sample
  (`source: "camera"`), or takes the camera's own stack when the camera updates it by script (`camera_stack`). A camera
  with post-processing off draws ungraded: neutral constants and exposure 1 (its `post:` values still read the stack).
  Without URP the constants are neutral and a `post:` field has no value.
- A play's first sample comes before URP has set up its volumes: it reads no stack (its `source` is "none"), so
  neutral constants, exposure 1 and no `post:` value, whatever the scene's volumes hold (the next sample reads them).
  Start a window that reads the grade, `exposure` or `brightness` after it (`"window": [0.5, 20]`), and never read
  them `"at": [0]`.
- Post exposure moves `grey`: URP multiplies the frame by 2^postExposure before the grading lookup. Contrast pivots on
  ACEScc mid-grey (about 0.2248 linear), so a contrast above 1 darkens a 0.18 grey: that is URP's own behaviour. An
  untouched volume stack gives exactly `grey` 0.18, whatever the key light (only its hue counts), and `cast` 0 under a
  white one; a coloured sun or sky casts its hue even then (a sun of linear colour (1, 0.57, 0.26): `cast` and
  `warmth` 1.16). LDR grading clips: a deep blue key light (blue above about twice its red plus 6.6 times its green)
  puts the grey's blue above 1, so its `grey` reads below 0.18, and an over-exposed grey reads white (`grey` 1), as the
  frame shows it. The checker's colour maths follows URP's LDR grading (under HDR grading, which doesn't clip before the
  grading, only a colour above 1 there reads differently) and leaves out tonemapping, split toning, the channel mixer,
  shadows/midtones/highlights and the curves: read a tonemapping change with `post:Tonemapping.mode`.
- A `post:` parameter no volume overrides reads the component's default. A number reads as it is, a boolean 1/0, an
  enum its value (`post:Tonemapping.mode` None reads 0), an object 1 when set, a colour by its channel `.r`, `.g`,
  `.b` or `.a` (`post:Vignette.color.r`), a vector by its `.x`, `.y`, `.z` or `.w` (`post:Vignette.center.x`). A
  `post:` name that doesn't exist (a component, a parameter or a channel), or a colour or vector without its channel,
  has no value and gives a `query_errors` line.
- The sample's value also holds, for the logs: `post_processing`, `grading_mode` (`ldr` or `hdr`), `source`,
  `pipeline`, the constants (linear colours; `hue_shift` in degrees), `sun`, `sky` and `fog` (with its `mode`).

### 2.9 `spawns`: objects appearing and disappearing

`{"probe": "spawns", "component": "Projectile", "field": "spawned|destroyed", "window": [0, 22]}`: how many objects
carrying that component appeared or disappeared in each sample's interval; the default `agg` is `sum` (the count in
the window).

- `spawned`: an object carrying the component became active in the hierarchy (instantiated, activated, or in a scene
  loaded during the play); `destroyed`: one was destroyed or deactivated. The probe compares every frame with the one
  before.
- Objects already there when the play's clock starts are not counted as spawned.
- Pooled objects reused with `SetActive` count as instantiated clones do: a pooled projectile that is deactivated and
  reused counts each time it comes and goes.
- What counts is each GameObject carrying the component (or a component of a type derived from it): a prefab instance
  counts once for each of its objects that carries it. Name a component that sits once per thing (the coin's own
  script), not one its children also carry (`MeshRenderer`), or each child counts too.
- A component type the build doesn't have (one a feature adds, at the start) gives no value, not 0.

### 2.10 `log`: the play's player log

`{"probe": "log", "pattern": "Scenario \\d+ started", "field": "count"}`: lines of the play's player log (`Debug.Log`
output, warnings, exceptions and Unity's own lines) that match, during the play: the whole log of the player's run, from
its start-up to its exit (a `log` measure takes no `window`, `at` or `agg`).

### 2.11 `asset`: the project as saved (`play: "editor"`)

```json
{"probe": "asset", "asset": "Assets/Materials/M_Road.mat", "field": "shader:_Smoothness"}
{"probe": "asset", "asset": "Assets/Textures/T_Grass.png", "field": "import:maxTextureSize"}
{"probe": "asset", "scene": "Assets/Scenes/Level6.unity", "select": {"component": "MeshRenderer", "tag": "Terrace"},
 "field": "material_default", "of": "all"}
```

One batchmode editor pass per side reads the project as saved. It never saves: every file under `Assets/` and
`ProjectSettings/` is unchanged after it. A measure names exactly one of `asset`, `scene` and `prefab`.

- `asset` (its path) with a `prop:`, `import:`, `shader:` or `keyword:` field and no `select`: one value (`of` doesn't
  apply; a string reads through `match`):
  - `prop:<path>`: the main asset's member by reflection, else a SerializedObject property path (a ScriptableObject's
    field `prop:waves[2].count`; `prop:waves`, a list, is its length; `prop:m_Name`). On a prefab asset it reads the
    prefab's root as a scene object's `prop:` does (`prop:Light.intensity`, the first Light in it). `material`,
    `materials` and `mesh` in a path are read as their `shared...` versions (the plain getters would copy the asset);
  - `import:<path>`: its importer's setting (`import:maxTextureSize`, `import:textureCompression`), falling back to
    an AudioImporter's `defaultSampleSettings` (so `import:loadType` works);
  - `shader:<Property>`: a material's shader property: a float, range or int as it is (`shader:_Smoothness`); a
    colour's channel `.r`, `.g`, `.b`, `.a` or a vector's `.x`, `.y`, `.z`, `.w`, either spelling for either
    (`shader:_BaseColor.r`); a texture 1 when set (`shader:_BaseMap`), its name with `.name` and `match`
    (`shader:_BaseMap.name`; an unset texture's name has no value); `shader:name`, the shader's name, with `match`;
  - `keyword:<NAME>`: 1 when the material has that shader keyword enabled, else 0 (`keyword:_EMISSION`).
- `scene` or `prefab` (its path) with a `count`, `material_default`, `material:`, `mesh_collision` or `prop:` field
  and a `select` (an object select, as for `objects`; none: every object): the objects it matches in that scene or
  prefab as saved, in hierarchy order, the active ones unless the select says `"inactive": true`. Each field gives
  rows, and `of` combines them (default `count`: how many rows have a value other than 0):
  - `count`: how many objects match (`of` ignored);
  - `material_default`: one row per object, 1 when any renderer of it or its descendants (inactive ones included)
    has no material slot, a slot that is empty or missing, a material with the error shader (or one that doesn't
    compile), or Unity's built-in default material or the render pipeline's default material (what a new primitive
    gets in URP);
  - `material:<property>`: one row per material slot of every renderer of the object and its descendants (inactive
    ones included; rows named `<object>/<renderer's object>`), the slot's material read as `shader:` reads it
    (`material:_BaseColor.r`, `material:_BaseMap.name`, `material:shader` for the shader's name), or
    `material:keyword:<NAME>`, 1 when that slot's material has the keyword enabled. An empty slot, a property its
    shader lacks or a colour without a channel is a row with no value, not an error;
  - `mesh_collision`: one row per mesh (a MeshFilter with a mesh) in the object (rows named
    `<object>/<mesh's object>`), 1 when its object or a parent up to the matched object has an enabled collider that
    isn't a trigger;
  - `prop:<Component>.<path>`: one row per object, read as an object's `prop:` is (section 2.4), else as a
    SerializedObject property path of that component (`prop:MeshRenderer.m_Materials.Array.size`); an unknown member
    is a row with no value.
- A select that needs a running game is an error for that measure, not empty rows: `player`, `has`, or a `near`
  around the player or the camera. A `near` around `{"xyz": [x, y, z]}` or `{"object": <select>}` works (the object
  resolved in the same scene or prefab; when nothing there matches it, nothing is near it).
- Errors: the probe fails with "the editor couldn't measure it: " and the editor's message, one of these (`<...>` stands
  for the names in question):
  - `no asset <path>`, `no scene <path>`, `no prefab <path>`;
  - `the scene <path> couldn't be opened: <type>: <message>`, `the prefab <path> couldn't be loaded: <type>:
    <message>` (the file is there, but Unity can't open it);
  - `no property <path> on <asset type> <asset path>` (a `prop:` of an asset);
  - `no import setting <path> on <importer type> <asset path>`, `no importer for <asset path>`;
  - `<asset path> is not a material (<asset type>)` (`shader:` or `keyword:` on another asset);
  - `no shader property <name> on <shader> (<material>)`;
  - `<name> is a colour: name a channel (<name>.r, .g, .b or .a)`;
  - `<name> is a vector: name a channel (<name>.x, .y, .z or .w)`;
  - `no <part> on the shader property <name>` (`.name` of a float, a channel of a texture);
  - "`player` selects need a running game: the editor pass can't match them";
  - "`has` needs a running game: the editor pass can't match it";
  - "a `near` point on the player or the camera needs a running game: use {"xyz": [x, y, z]}".
  Any other failure in the pass reads as its exception's type and message (`<type>: <message>`). A value that reads no
  number fails too: "the property has no number" (an `asset` field without a value, or a string read without
  `match`), "no selected object has a value" (rows without a value, or none, under `of` `min`, `max`, `mean` or
  `first`).
- Floats come back as stored (`_BaseColor.r` set to 0.2 reads 0.19999995827674866): compare with a tolerance
  (`>=`/`<=` a little either side), never `==` on a fraction.
- URP rewrites some material values on import: a material created with `_EMISSION` but default global illumination
  flags has the keyword turned off again. Read what the saved asset really holds, at both seeds.
- A project that doesn't build fails its editor probes ("the project didn't build, so the editor couldn't open it"),
  and so does a pass that ends without its result ("the editor pass gave no result (exit <code>)", or "(exit <code>,
  timed out)" when it ran out of time).

### 2.12 `trace`: the agent's own trace (`play: "trace"`, never gating)

`{"probe": "trace", "fact": "build_ok_at_end"}`, a fact of the agent's trace: `built_after_last_change` or
`played_after_last_change` (a successful build / game run after the last change), `read_before_first_edit` (a read
before the first edit), `build_ok_at_end` (the last build succeeded), `edits_outside_project` (edits refused for a
path outside the project). Only as `"required": false` quality notes with a literal threshold.

### 2.13 Points

`{"xyz": [12.0, 1.5, -3.0]}`, `{"player": true, "offset": [0, 1.6, 0]}` (the player's position plus `offset`),
`{"camera": true, "forward": 30}` (`forward` m ahead of the camera along its view), or
`{"object": {"name": "Lamp_1"}, "offset": [0, 4.5, 0]}` (the first match's position plus `offset`; section 2.1 says
which is first). `offset` defaults to `[0, 0, 0]` and `forward` to 0. A point is found again at every sample; one that
doesn't resolve then (no player or camera yet, nothing matched) makes what uses it read nothing: a `near` around it
matches nothing.

A `near` is `{"point": <Point>, "radius": m}`, and may also hold a height band: `"y_min"` and/or `"y_max"` (m, world
y; with `"y_relative": true`, offsets from the point's y). Wherever `near` works (object selects, `has`, `components`,
`pieces`, `drawn`), a thing then matches only when its place's y is within the band too: the lamp on the ceiling, not
the one on the floor below it. `y_min < y_max`; `y_relative` goes with one of them.

### 2.14 `pieces`: placed mesh pieces, whatever their form

```json
{"probe": "pieces", "select": {"component": "MeshRenderer", "mesh": "Rock*",
                               "near": {"point": {"player": true}, "radius": 30}},
 "field": "count", "at": "end"}
```

How many mesh pieces are placed, however the scene holds them: trees painted on a Terrain read as one object and one
component to `objects` and `components`, but as their real number of pieces here.

- A piece: a MeshRenderer whose mesh has triangles is 1; a SkinnedMeshRenderer with a mesh is 1; a Terrain's tree
  instances are 1 each. Empty meshes (no mesh, or no triangles), other renderers (sprites, lines, trails, particles),
  meshes drawn from code with `Graphics.RenderMesh*` and a Terrain's detail grass count 0. Only renderers of objects
  active in the hierarchy count (a disabled renderer is a piece that isn't drawn). Under a LODGroup only LOD 0's
  renderers count, so an object with three LODs is one piece.
- `select` (optional; every key given must match, none means every mesh piece in the scene):
  - `component`: the renderer's type or a base type (`MeshRenderer`, `SkinnedMeshRenderer`; `Renderer` takes in
    both), or `Terrain` for a Terrain's trees; default every one;
  - `name`: a wildcard on the renderer's object's name (a tree's: its Terrain's); `mesh`: a wildcard on its mesh
    asset's name (`Rock*`; a tree's is its prototype's first mesh's);
  - `owner`: an object select the renderer's object (a tree's: its Terrain's) or an ancestor must match (as in
    `objects`);
  - `near`: within `radius` m of a point, **each piece by its own place** (a tree instance's position, else its
    renderer's object's position).
- `field`: `count` (pieces), `visible` (pieces drawn: renderer enabled and active, not forced off; trees when their
  Terrain is enabled and draws its trees), `components` (how many renderers or terrains hold them), `objects` (how many
  objects), `triangles` (the triangles the pieces hold), `visible_triangles` (the triangles of the pieces drawn, as
  `visible`).
- A piece's triangles: its mesh's index count / 3 over the submeshes drawn as triangles; a tree's, its prototype
  prefab's at full detail (the renderers of its LODGroup's LOD 0, else every mesh renderer in it).
- Counted over every piece in the probe, never cut at the rows cap. A literal threshold is fine on `count`, `visible`,
  `components` and `objects` (a count doesn't depend on the machine).
- **A `triangles` or `visible_triangles` threshold is calibrated or relative to the start, never a literal value**
  (`tools/validate-game.py` refuses one): how many triangles a fair build draws depends on the meshes it chose (1500
  low-poly trees combined into three meshes, or 300 detailed ones), so the number only means something against the
  same game's start or reference. Read it where a count of pieces can't tell a fair build: "the forest is dense" built
  either way reads as many drawn triangles, but as 3 pieces when combined.

### 2.15 `screen`: what the player sees, after post-processing

```json
{"probe": "screen", "rect": [0.25, 0.25, 0.75, 0.75], "field": "luminance", "window": [10, 20], "agg": "mean"}
```

The mean brightness of the frame the player's window displays, sampled with the play like every other probe: after
post-processing and tonemapping (post exposure, colour grading, vignette, ambient occlusion, bloom, fog), so "the cave
is too dark to see" or "the night is too bright" is measured on what reaches the screen. The `light` probe measures
light arriving at a point and sees none of that.

- `rect`: `[x0, y0, x1, y1]` in viewport fractions 0-1, y down from the top, x0 < x1 and y0 < y1 (default
  `[0, 0, 1, 1]`, the whole frame). The frame is read **as displayed, UI included**: keep the rect on the scene the
  task is about and off the HUD. What the HUD shows is `ui` (section 2.18), not luminance.
- `field`: `luminance`, the mean linear Rec. 709 luminance of the displayed pixels (sRGB decoded, 0-1); `luma`, the
  mean Rec. 709 luma of the encoded values (0-1, closer to perceived brightness).
- What is read: the frame drawn right after each sample (the sample's own frame, read once it is drawn: no play time
  passes in between). No value when no frame is drawn. The value also holds `pixels` (how many the rect covers) and
  `size` (the frame's width and height), for the logs.
- **The threshold is calibrated or relative to the start, never a literal value** (`tools/validate-game.py` refuses
  one): the numbers depend on the GPU, the driver and the resolution, so they compare only within one machine's plays.
  Two plays of one build on one machine read the same (measured: identical series), to about 1e-5 with a realtime
  reflection probe that refreshes every frame. A fade-in, a teleport or a scene's own exposure animation takes time to
  settle: put the window after it.

### 2.16 `audio`: what the player hears

```json
{"probe": "audio", "select": {"sound": "Amb_Jungle*", "sound_class": "Ambience", "owner": {"tag": "Zone2"}},
 "field": "volume", "window": [4, 8], "agg": "mean"}
```

The AudioSources playing: a source on an object, a 2D source for music, a temporary one-shot source; so ambience a
game drives from code reads as well as a source placed in the scene. `PlayClipAtPoint` sounds read like any other
(Unity makes a "One shot audio" source with the clip). A `PlayOneShot` sound counts (its source reads as playing), but
the probe sees only its source's own clip, not the one-shot's: on a source without a clip, `loudest` is "" and no
`sound` select matches it; `level` hears it.

- `select` (optional; none: every source playing): `sound` a wildcard on the AudioClip's name, `sound_class` a
  wildcard on the name of the AudioMixerGroup the source outputs to (that group's own name: a parent group's doesn't
  match), `owner` an object select the source's object is in.
- Each source reads its **volume at the listener** (the first enabled AudioListener on an active object): its volume
  (0 when muted) times its distance attenuation by its rolloff, for its 3D share by `spatialBlend`; mixer volumes and
  `AudioListener.volume` are left out (a mixer group's volume changes `level`, never `volume`). Logarithmic rolloff is
  min distance / distance and keeps falling past max distance, whatever Unity's documentation says (measured: 1/80 at
  80 m with max 50); linear falls to 0 at max distance; a custom curve runs over distance / max distance.
- `field`: `count` (how many sources), `audible` (how many at 0.001, -60 dB, or louder), `volume` (their volumes'
  sum), `max_volume` (the loudest), and `level` (the RMS of the listener's mixed output since the previous sample,
  mixers and effects included: everything the player would hear, whatever plays it). For the first frames of a play,
  and for up to 4 frames after the listener changes, there is no tap on it yet: `level` has no value then. No
  listener: no value at all.
- While `AudioListener.pause` is on, every source reads as not playing (`count` and `level` 0); with `timeScale` 0
  sounds keep playing.
- The sample's value also holds `loudest` (the loudest source's clip name), `peak` and `listener` (its object's name),
  for the logs.
- **A `volume`, `max_volume` or `level` threshold is calibrated or relative to the start, never a literal value**: how
  loud depends on the sounds a build chose. `count` and `audible` take a literal. Compare places by their own plays or
  windows: teleport into each zone (section 1.1) and read the zone's sound there.
- Every play runs with its sound on, and in every play the probe's tap on the enabled AudioListener measures the mix
  and then silences it, so nothing is heard on the machine. A play with an `audio` measure is paced to real time
  (still 30 fps), so a sound lasts as long in play time as on a clock. Every other play runs as fast as the machine
  renders, often many times faster than real time, and a sound, which plays in real time, then lasts many times longer
  in play time: read sound only in a play with an `audio` measure.

### 2.17 `ground`: the lie of the land

```json
{"probe": "ground", "xz": [12.0, -3.0], "field": "height"}
{"probe": "ground", "box": [0, 0, 80, 80], "grid": 12, "select": {"component": "TerrainCollider"}, "field": "range"}
```

- At a point `xz`: `height` (m), the y where a ray straight down from 2000 m up first meets a collider (every collider
  but triggers, those on the Ignore Raycast layer and the player's); `hit` (1 when it met anything).
- Over a `box` `[x0, z0, x1, z1]` (x0 < x1, z0 < z1), the same on a `grid` x `grid` lattice (2-32, default 8; corners
  and edges included): `min`, `max`, `mean` of the heights, `range` (max - min, the relief: rolling hills against a
  flat plain), `hits` (how many points met ground). The value also holds `points` (grid x grid), for the logs. A
  measure takes `xz` or `box`, and only that one's fields.
- `select` (an object select, optional): only colliders of the objects it matches, or of their descendants, are
  ground; anything else (trees, rocks, roofs) is traced through. The player's colliders are always skipped, with or
  without `select`.
- **A `range` threshold is calibrated or relative to the start, never a literal value**; heights take a literal, as
  an object's `y` does.

### 2.18 `ui`: what the UI shows on screen, whatever draws it

```json
{"probe": "ui", "select": {"kind": "text"}, "field": "text", "match": "AMMO\\s*\\d+", "of": "any", "at": "end"}
{"probe": "ui", "select": {"kind": "box", "rect": [0, 0.8, 1, 1]}, "field": "count", "window": [5, 10], "agg": "min"}
{"probe": "ui", "select": {"rect": [0.02, 0.02, 0.3, 0.12]}, "field": "signature", "window": [5, 15], "agg": "changes"}
```

One reading for the UI on screen, however a build drew it: uGUI (with TextMeshPro) and UI Toolkit read the same. A HUD
one build made with uGUI, and one another build made with UI Toolkit, both pass a check written with `ui`. **This is
the way to check what a HUD or menu shows**; `widgets` (section 2.6) stays for a widget's own state (a slider's
percent, a sprite).

- What is read: the elements on screen in the frame drawn right after each sample (the sample's own frame, read once it
  is drawn: no play time passes in between). Only what is on screen: an inactive object, a disabled Canvas, a
  CanvasGroup at an alpha of 0.004 or less, a UI Toolkit element hidden (`display: none`, `visibility: hidden`) or at
  an opacity that low, and everything under them, are not read; nor is a disabled graphic, one whose own colour is
  that transparent, one culled by a RectMask2D, a blank text, an Image filled to 0, or an element entirely off the
  frame. No value when no frame is drawn.
- Each element is one row: on a screen-space canvas (Overlay or Camera), a `Text` or `TMP_Text` is `text`, an `Image`
  or `RawImage` with a sprite or texture is `image`, any other drawn Graphic is `box`; in a UI Toolkit panel drawn on
  the screen, a `TextElement` with text is `text`, an element with an image (an `Image` element's, or a background
  image) is `image`, one with a background colour or a border is `box`. An element can be two rows: a UI Toolkit Button
  gives a `box` row and a `text` row, as a uGUI button gives its image and its child text. Text is read as shown: rich
  text tags stripped, a TextMeshPro typewriter reveal (`maxVisibleCharacters`) honoured. Rows come in this order:
  uGUI elements in hierarchy order, then UI Toolkit elements in tree order, then the lines read from the frame (below).
- `select` (optional; default every element): `kind` (`text`, `box`, `image`); `text` (a regular expression the
  element's text must match; text elements only, so with `kind` `text` or none); `rect` `[x0, y0, x1, y1]` in viewport
  fractions, y down from the top, x0 < x1 and y0 < y1 (the element's centre inside). There is no `line` kind: Unity
  keeps no list of line draws.
- `field`: `count` (one per element); `text` (the string shown, with `match`: a `ui` measure takes `match` when its
  field is `text`, and only then); `x`, `y`, `w`, `h` (the element's rectangle in viewport fractions 0-1, y down);
  `signature` (whether what the select shows updates, below); `number` and `clock` (the number or time it shows,
  below). `of` combines the elements, as for widgets: `"field": "text", "match": ..., "of": "any"` is 1 when some
  element shows matching text, `"of": "count"` how many do.
- Whether a readout updates, however it is drawn: `"field": "signature"` is one value a sample for everything the
  `select` picks: each element's `kind`, `text` and rectangle (`x`, `y`, `w`, `h` rounded to 0.002 of the viewport),
  taken as a set, and how many matched. It is 0 when the select picks nothing, otherwise a number that means nothing
  but itself; `source`, names and the order of the rows are left out. Read it with `"agg": "changes"`: how many
  samples (every 0.5 s) show something other than the sample before. A text readout whose string changes counts,
  whether an element or the frame reader (below) reads it; a readout that stays the same reads 0. Appearing or going
  (to or from 0) is a change; a sample with no frame drawn has no value.
  - A signature takes `agg` `changes`, `any`, `all` or `count` (`all`: something shown in every sample; `count`:
    samples showing something), nothing else, so it always names one (the default `last` is refused). `of` is ignored.
  - A literal threshold on a count of changes is valid, but a calibrated or start-relative threshold is the safer
    choice: a readout that also moves, blinks or animates changes for reasons of its own, and one that updates more
    slowly than the samples changes less often. Keep the `rect` on the readout alone, with a margin, and the
    `window` where its value is known to change.
  - Limits: geometry right at a 0.002 step can flip between samples on sub-pixel motion; a change that changes back
    before the next sample is not seen; a readout no `ui` element reads (below) has no signature but 0, unless its
    text reads from the frame.
- Which way a number on screen moved, however it is drawn: `"field": "number"` is the first number the select's text
  elements show in one sample, in reading order (top to bottom, a line within 0.01 of the viewport's height; left to
  right): digits with a decimal point and comma thousands (`3,450` is 3450), negative when a minus stands before it
  after no letter or digit (`LAP 2-3` reads 2). Its text comes from every text element the select picks (uGUI,
  TextMeshPro, UI Toolkit, and the frame when the select is of text in a rect), so the select is best
  `{"kind": "text", "rect": [0.01, 0.01, 0.4, 0.09]}` around the readout alone. No number shown: no value. Read it
  with `rises`, `falls` (section 2.1), `changes`, `range` or `max`: a score that only rises reads `falls` 0 over its
  window; a reset reads as a fall.
- A clock on screen as a clock: `"field": "clock"` is the first time shown, in seconds: `h:mm:ss` or `m:ss` (a
  fraction after `.` or `,` added), else the first number, as seconds. A timer that holds through a pause reads
  `range` 0 over the pause's window; one that resets on a retry reads a fall there (a count-down: a rise).
- `number` and `clock` share the signature's query (one select, one reading), take any `agg` and a literal (what is
  shown is a fact), ignore `of` and take no `match`.
- Each row also carries `source` (`ugui`, `uitk` or `ocr`) and `kind`, for the logs; they are not fields a check
  reads, so a threshold never depends on how a build drew its HUD.
- Text however it is drawn, read from the frame. A `select` of text in a `rect` (`"kind": "text"`, or a `text`
  regex, with a `rect`) also reads the frame as drawn inside that rect: text drawn with `OnGUI`, with `GL` lines, on a
  custom mesh, with a texture or as segments reads there too. **This is how a readout that is no uGUI or UI Toolkit
  element is read**: Unity keeps no list of what `OnGUI`, `GL` or a mesh draws, so such a readout is no element, and
  only its text, through this reader, is seen. Each line it can read for sure joins the text elements as one `text`
  element (`source` `ocr`, named `ScreenText`; glyphs two and a half capital heights apart or more are two elements),
  so `match` and `of` read it like any other; a line another element already reads as text is left to that element,
  so nothing reads twice. It reads digits 0-9, capital letters A-Z and `%`, `/`, `.`, `-`, `:`, in the shapes
  line-drawn and segment fonts give them (plain strokes, cut or rounded corners, seven segments, a slashed 0, diagonals
  in 1, 4 and 7). Only such a select reads the frame's pixels; any other select reads the elements alone.
  - It reads nothing rather than guess: text that doesn't stand out in one colour from an even background behind it;
    a line that runs out of the rect or that another mark crosses; a glyph two characters fit (an unslashed 0 and O,
    a 5 and S or an 8 and B drawn as segments, a plain bar for 1 and I); a lone character; lower case; slanted
    (italic) text; glyphs too small or too bold for their strokes to be told apart. A line with any glyph it can't
    read reads as nothing, not in part.
  - Give the rect a margin around the text so its edge is background: a stroke that touches the rect's edge makes the
    line refused, and a stroke's caps reach half the stroke width beyond the glyph. Write `\s*` where the text has a
    space (spaces are read from the gaps between glyphs).
  - Measured limits: TextMeshPro at 32 px in its default font is too bold for its size and reads nothing through the
    frame (it reads as a `ugui` element anyway); with strokes drawn as rectangles the reader can refuse a "3" (the
    thickened joins put its fit just over the limit). Where a readout drawn without UI components matters, check in
    the fix's play that it reads.
  - Where a line-drawn readout still doesn't read as text, `ui` has nothing else to read it by: there are no line
    elements to count. Grade another outcome of the same issue.
- Limits: world-space canvases and text in the 3D scene (a `TextMeshPro` 3D text, a `TextMesh`) are not UI elements
  (their text can still read from the frame, above).

### 2.19 `drawn`: what is drawn in a place, whatever draws it

```json
{"probe": "drawn", "near": {"point": {"xyz": [12.0, 1.5, -3.0]}, "radius": 2.5}, "field": "motion", "window": [4, 12], "agg": "mean"}
{"probe": "drawn", "near": {"point": {"object": {"tag": "Wall"}}, "radius": 2}, "field": "base_r", "at": "end"}
{"probe": "drawn", "line": {"from": {"player": true, "offset": [0, 0.6, 0]}, "to": {"camera": true, "forward": 30}, "radius": 0.4}, "field": "reach", "window": [6, 8], "agg": "max"}
```

One reading for what is drawn at a spot, whatever draws it: a mesh, a particle system, a VFX Graph effect, a trail, a
surface whose material pans or animates, no name needed. Every renderer drawn in game (enabled, active, not forced
off) whose world bounds reach the place is rendered alone, by a camera of the probe's own that shows only those
renderers: orthographic, from fixed views (four around a point at 64 x 64, two across a line at 128 x 128), lit by a
flat white ambient light alone, with no Lights, shadows, lightmaps, light probes, reflections, fog, post-processing or
anti-aliasing, so a still scene renders the same every sample. At most 1024 renderers are rendered. A renderer whose
bounds enclose the whole place and are at least 20 times its size (a sky dome, a room seen from inside) is left out.
A pixel is in the place when its depth puts it there, or when it shows colour with nothing opaque behind it
(translucent particles); the views reach no further than the place's far side, so an opaque wall behind the place
doesn't hide translucent particles in front of it. Everything the render changes is put back before the sample
returns: the game's own frames are the same with and without the measure.

- The place: `near` (section 2.13: a point, a radius and, optionally, a height band), or `line`: `{"from": <Point>,
  "to": <Point>, "radius": m}` (0 < radius <= 100), the segment and how far from it counts as on it. One of them.
- Near a point, `field`:
  - `drawn`: 1 when anything is drawn there, else 0;
  - `motion`: the share of the place's pixels (in either sample) that changed since the previous sample, covered or
    not, or a colour channel by more than one 8-bit step: 0 for a still scene, more when a mesh moves or turns,
    particles play, or a material pans or animates. No value the first sample;
  - `base_r`, `base_g`, `base_b`: the mean base colour (linear 0-1) of the place's opaque pixels, the surface's colour
    or tint with no light in it, from a texture, a property or a property block alike: the render under the white
    ambient light less one under none, so what a surface emits cancels out. A URP Lit surface reads its albedo (a
    lightmapped or probe-lit one too), a metallic one a near-black colour; `base_change`: that colour's distance (RGB)
    from the first one the play read (the first sample's, when something opaque was there).
- Along a line, `field`: `drawn`; `reach` (m): from `from` along the line to the furthest point drawn within `radius`
  of it; `length` (m): how much of the line is drawn. A beam drawn as a mesh, a particle beam, a LineRenderer or a
  trail read alike.
- **Every field but `drawn` depends on what a build drew: its threshold is calibrated or relative to the start, never
  a literal value**; `drawn` takes a literal. A point that doesn't resolve: no value. The sample's value always holds
  `pixels` and `primitives` (pixels in the place, renderers rendered), for the logs; its base colour is null unless a
  `base_` field is asked for.
- Limits: the player's own object counts like anything else in the place (keep it out, or teleport away); a lit
  translucent particle shows as lit by the white ambient light only; a surface that writes no base colour has none
  (an unlit one reads 0, a translucent one is left out); what isn't a renderer (`GL` drawing, `Graphics.RenderMesh*`
  from code, UI) reads nothing, nor do layers only a filtered URP renderer draws, world-space canvases on the chosen
  layers, or terrain; URP's Forward, Forward+ and Deferred renderers read the same, but a shader with only a forward
  pass draws nothing under Deferred, in the game as in the probe. Game code hooked to the render pipeline's camera
  callbacks also sees the probe's render, and an object the probe renders may report itself visible to the game that
  frame (`OnBecameVisible`, `Renderer.isVisible`). URP adaptive probe volumes and realtime GI lightmaps are not
  switched off (they would add light to a glow reading). Keep the place tight around what the task is about: a floor
  or a wall inside it counts too.

## 3. What gates, and how a probe fails

- **At least one required probe.** Every task has at least one `probe` check with `"required": true` (the default);
  the validator refuses a task without one. Every bug fix and correction has at least one required probe that the start
  fails for the reported reason and the fix passes.
- **`still_works` probes already pass at the start.** A required probe in the `still_works` milestone (the player
  still moves, the HUD still shows, the scene still loads its scenario) must pass on the start: what still works must
  already work there, or the probe itself is broken and would fail every correct solution. (A still-works probe the
  start has no samples for, because its play crashed or ended early on the very bug the task fixes, doesn't count
  against it; one that finds nothing to measure in a start that ran does.)
- **Trace probes never gate**: `"required": false`, with a literal threshold.
- **No samples, no pass.** When a play ends early or a measure has no samples in its window (the game quit, crashed or
  never reached that time), the probe fails with
  "no samples in the window (the play ended at X s)" or "no samples in the window (the play wrote no probe file)";
  when samples exist but nothing selected has a value (nothing matched, the play found no player or no camera, the
  field had nothing to read), it fails with
  "no value in the window (nothing it selects was measured)", followed by "; the probe said: " and the probe's first
  error about that measure's own query, when it logged one (the play's `probe.json` holds them all in
  `query_errors`).
- **`needs`** names only earlier checks; check names are unique in the task.

### 3.1 A start that doesn't compile: `fails_at_start`

When making the start build is the task (its scripts don't compile, or the player build fails), mark its build check:

```json
{"name": "player_builds", "kind": "build", "fails_at_start": true}
```

The start is then never played, so nothing in the task may need it played: **no start-relative thresholds**
(`calibrate`, `start_times`, `start_plus`; use literal values) and **no judges comparing with the start**
(`"before": true`). The task check requires the start not to build; a start that builds makes the task invalid.

## 4. The task check

Before any agent is given a task, the checker grades the start and the fix with every probe
([task-check.md](task-check.md)). A task is valid when:

- the start builds (unless the task says it doesn't, section 3.1: then it must not);
- the fix builds, boots and passes every required probe (its other checks only add notes: a `log_absent` or
  `file_exists` it fails, a probe that isn't required);
- the start fails every required probe outside `still_works`, of which there is at least one (or the `fails_at_start`
  build check);
- a no-op scores zero: no check the start passes carries weight, so build, boot and `still_works` checks take
  `"weight": 0`, as does any other check true of the start, a `log_absent` or `file_exists` check or a probe,
  `"required": false` ones included (the score is the weighted share of checks passed);
- every required `still_works` probe passes at the start;
- every required calibrated probe measures differently on the start and the fix (one that isn't required and can't
  be calibrated fails as a note, never making the task invalid).

A task with no fix is checked on its start alone: the start builds, fails every required probe outside `still_works`
(thresholds literal or relative to the start) and passes its still-works probes. Only a draft has no fix: the
validator refuses a task without `seed.reference`. A task that fails the task check is not run; a run on an invalid
task is void.

## 5. Lessons

- **Mouse axes go through the game's input scale.** An axis event's value is not degrees: `<Mouse>/delta/x` is a mouse
  movement in pixels over one frame, and the game's input actions (processors such as Scale) and its own look
  sensitivity scale it. A play that assumes `"axis": 90` turns the camera 90 degrees barely moves it. Read the game's
  look scale at the seed and size the axis values (or send several events) so the camera really turns, then measure
  the turn.
- **Only the Input System can be driven.** The probe sends keys, buttons, axes and the cursor through its own virtual
  Input System devices. A game that reads `UnityEngine.Input` (the old Input Manager: `Input.GetKey`, `Input.GetAxis`)
  sees none of them; teleports, widget clicks and waits still work, as they don't go through the Input System. Check
  the game's input code at the seed before writing a task play.
- **Check that a play really reaches the situation.** A probe of a moment the play never reaches measures nothing
  useful. Teleport to the spot (`teleport` input), use a scenario (`scene`/`args`) that starts there, and check on
  the fix that the play gets there before trusting its threshold: the fix's `probe.json` holds the player's `track`,
  and its `probe.log` names what each `teleport_to` reached.
- **A boot scene doesn't run before `play_scene`.** Its objects get `Awake` and `OnEnable`, then go before `Start`
  (section 1.1): what a boot scene sets up in `Start` (a save loaded, a manager filled in) is missing in a play that
  opens a later scene. Such a game is started through its own `play_args` with `play_scene` null.
- **A measure that reads the same on the start and the fix can't gate.** If both sides give the same value, the probe
  doesn't see the bug (a required calibrated one makes the task invalid outright). Pick a measure the fix actually
  changes.
- **Calibrate thresholds between the start and the fix.** Use `calibrate` (or literal values that sit clearly between
  what the start and the fix measure), never a threshold guessed from the fix alone: another valid fix must pass and
  the start must fail.
- **Angles compare as angles.** Yaw, pitch and roll wrap at 180; comparing raw values fails across the wrap (179 and
  -179 are 2 degrees apart). Use `to_angle` (a direction) or `to_axis` (an axis, either way along it).
- **Value-reading measures need a reducer.** `of` defaults to `count`; to read an object's or a widget's value write
  `"of": "first"` (or `min`, `max`, `mean`, ...).
- **Test the outcome a player sees, never the implementation.** "The hero stands on ground", not "spawnHeight is
  0.92"; another valid fix must pass.
- **Read names from the game.** Component types, tags, layers, object and UI element names and scene paths come from
  the code and assets at `seed.commit` and `seed.reference`, never guessed. An instantiated prefab is named
  `<Prefab>(Clone)`, and a wildcard takes in every name it fits (`Coin*` matches `CoinSpawner` too): select the
  objects you mean, and check in the fix's play what a select reached.
- **Count what the player sees placed.** A fix that moves props onto a Terrain as painted trees has fewer objects and
  components but as many pieces: count with `pieces`, so a fair build that dressed the scene another way still passes.
  When a fair build may also merge them (many props combined into a few meshes, or one), count the geometry drawn:
  `visible_triangles`, calibrated or relative to the start.
- **Off is not hidden from the counts.** A lamp switched off by disabling its Light or by intensity 0 is still a
  component of an active object: read `lit` of the lamp, not `count` of the objects or `visible` of its Light.
- **A lamp need not be a Light.** A build may light a lamp with a Light, or draw it with an emissive material switched
  by a property, with no Light at all: read `lit` (and `glow`, calibrated or relative to the start), which see both.
  `on`, `intensity` and the `light` probe see Lights only.
- **A broken object still draws.** A crate broken into pieces may keep every piece drawn and tagged, so `count` and
  `visible` can't see it go: read `simulating` of the crate, or its `spread` calibrated or relative to the start.
- **An object can break without physics.** A build may break it by hiding a part, or by playing an animation on its
  skinned pieces, so nothing simulates and no part moves apart: read `changed` of the object (1 when anything about it
  changed since the start), so either way of breaking it reads the same.
- **A light's direction is a world direction.** `rel_yaw:` reads a part against its own object, so a fix that turns
  the object instead of the part reads unchanged. "The moon points the same way" is `world_yaw:`, `world_pitch:` or
  `forward:` of the Light.
- **A HUD need not be one UI system.** A build may draw its HUD with uGUI or with UI Toolkit: check what it shows with
  `ui` (text with `match`, counts by `kind` and `rect`), which reads both the same; `widgets` sees only the widget it
  names. A HUD drawn with `OnGUI` or `GL` is no element: `ui` reads only its text, from the frame (a select of text in
  a `rect`).
- **Brightness on screen goes through calibration.** A `screen` threshold is always calibrated between the start and
  the fix (or relative to the start), and its window starts after the scene has settled (a fade-in, a teleport).
- **The screen includes the UI.** A `screen` rect over the HUD measures the HUD: keep it on the scene.
- **A material asset holds floats as stored.** An editor `shader:` value set to 0.2 reads 0.19999995827674866: compare
  with `>=`/`<=` a little either side, never `==`.
- **A one-shot sound has no name.** A sound played with `PlayOneShot` counts, but the probe sees only its source's own
  clip, so no `sound` select finds it by the one-shot's name: read `level` (calibrated or relative to the start) in a
  play that hears it, or select its source by `owner`.
