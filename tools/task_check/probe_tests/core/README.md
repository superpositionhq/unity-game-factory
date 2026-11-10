# Probe tests: the play loop

What `Runtime/Core/Probe.cs`, `ProbeLate.cs`, `Inputs.cs` and `Window.cs` do in a real play: the clock, sampling,
screenshots, every kind of input, teleports and holds, waits, who the player and the camera are, scenes, the ends of
a play, saved data, the errors of the queries list. The checks are in `tests.py`; this page says what the scenes hold
and what each play is for.

## Scenes (made by `Editor/CoreScenes.cs`)

- **First.unity**: made the project's first build scene, so it is what a play without a scene opens and what wakes up
  before any play's own scene is asked for. One object, `FirstMarker` (`CoreFirst`), says in the player's log what
  it lives through (`CORE First Awake`, `OnEnable`, `Start`, `Update`, `OnDestroy`); with `-corekeeper` it leaves an
  object marked `DontDestroyOnLoad`; with `-coreselftest` (the player started without `-taskProbe`) it says what the
  probe did to the game, which must be nothing, and quits.
- **Clock.unity** (also built a second time as a player of its own with another company name, `Build/ProbeTestsForeign/`): `Hero` (tagged Player, `CoreMover`) moves 1 m along x every second of game time, so its x is the
  game's clock; it also keeps how far `Time.time`, `Time.unscaledTime` and `Time.realtimeSinceStartup` went. `Director`
  (`CoreDirector`) does what a game may do in mid-play, by the play's arguments: quit, refuse to quit, load a scene
  (at once, in the background, or parked with `allowSceneActivation = false`), write saved data, destroy every
  object it finds, set vertical sync and frame rates of its own.
- **Stage.unity**: `Hero` (`CoreWalker`) walks 2 m/s along z while W or S is down, drifts 1 m/s along x with
  `-coredrift` (the game moving the player by itself), and keeps what it saw of the keyboard, the mouse, the gamepad
  and the window's focus. `Main Camera` (`CoreFollow`) follows it in `LateUpdate`. Two cubes named `Post` to be
  teleported to, a uGUI `PushButton` that counts its clicks, and a magenta `Badge` of UI in the frame's top left.
- **Bodies.unity**: three players the game moves by itself, 1 m/s along x under gravity (`CoreStroll`), each through
  another kind of body and on ground of its own kind: `BodyCc` (a CharacterController), `BodyRb` (a Rigidbody),
  `Body2d` (a Rigidbody2D).
- **Who.unity**: every kind of object the player can be, in the order the probe looks for them (`Tagged` and `Tagged2`
  under one parent, `Crowd`: a player lists a scene's roots in an order of its own, siblings in the scene's;
  `Inputter` with a PlayerInput, `Body` with a CharacterController, `Rig` holding the main camera), and `Director`
  (`CoreWho`), which takes the first ones away when asked; a second camera `High` of higher depth, inactive unless
  asked for.

## Plays

| Play | What it proves |
|---|---|
| `clock` | The play's clock is the game's (x = t at every sample); samples at the first frame and then every `every`; the track and camera rows; `seconds`; screenshots; the play ran on a desktop of its own; the game's first scene got `Awake`, `OnEnable` and `OnDestroy` and never `Start` or `Update`. |
| `clocks` | `Time.time` runs on the play's clock; `Time.unscaledTime` goes with the wall clock. |
| `fine` | `seconds` below 1 is 1; `every` below 0.1 is 0.1. The player's log holds what the game logged in the play's last frame (the process ends as soon as the play's files are written). |
| `inputs` | Keys reach the game one frame after they are sent; two keys sent in one frame are both down; a mouse delta and a scroll are seen once; a mouse button; the cursor; no gamepad unless named; a widget click and a click on no button; an unknown key, and a control the docs don't list (`<Mouse>/position/x`), are one error each; `inputs_sent`; the game counts itself focused throughout. |
| `pad` | A gamepad is there when an input names it; a stick keeps its value; a button; a button by a name the docs don't list (`<Gamepad>/a`) is an error. |
| `teleport` | `teleport` with a yaw; `teleport_to` the nearer of two matches, on the player's side, `distance`, `offset`, `face`; a select matching nothing. |
| `hold` | A held player stays at the spot while the game moves it, and a camera that follows in `LateUpdate` stands where it stands for a player at the spot; the hold ends on time. |
| `body_cc`, `body_rb`, `body_2d` | A teleport with a hold on a player moved by a CharacterController, a Rigidbody, a Rigidbody2D: it hangs at the spot against the game's own movement and gravity, facing the yaw asked for; when the hold ends it falls and the game moves it on. |
| `hold_wait` | A hold lasts through a wait: no frame of the game finds the player anywhere else. Also: the probe's `Update` runs before the game's. |
| `wait` | A wait holds the clock for its seconds of real time while the game runs; the sample of the frame it starts in is taken first; the inputs after it wait. |
| `shots` | Screenshots: their number, 960x540, no alpha channel, the UI in them. |
| `first` | A play without a scene plays the first build scene. A spec that can't be read (no file, another format): the player says why and exits with 2. |
| `missing_scene` | A scene that isn't in the build: an error, and the first build scene is played. |
| `keeper` | An object the first scene marks `DontDestroyOnLoad` in `Awake` is there in the play's scene. |
| `shutdown` | The game quits by itself: `ended` is `shutdown`, with every sample and screenshot up to then. |
| `refuse` | A game that refuses to quit (`Application.wantsToQuit`) still ends at the play's end, with exit code 0. |
| `load_sync`, `load_async`, `load_parked` | A scene load in mid-play: no sample lost or late, the player and camera found anew; the clock holds while a scene loads, for at most 300 frames (a parked load never finishes). |
| `saves_a`, `saves_b` | Saved data is the build's own (company `TaskProbe.<hash>`, the name the checker deletes by) and is gone at the next play's start. The same player started without `-taskProbe`: no probe, no fixed frame rate, no virtual device, nothing wiped. A second player of the project built with a company name of its own (`CoreScenes.Foreign`, as a real project builds with the package in it) and started with `-taskProbe`: the play runs and its saved data is still there at the next play. |
| `errors` | The checks of the queries list and their messages; an unknown kind samples null values; at most 256 queries. |
| `who_*`, `cam_*` | Each rule for the player (the first tagged object in hierarchy order, a PlayerInput, a CharacterController, the main camera's root, none; the spec's `player` select) and for the camera (the main one; orthographic: fov 0; without a main one, the highest depth). |
| `settings` | A game that sets vertical sync, a target frame rate and a capture frame rate of its own: the probe sets its own again before every frame's scripts. |
| `wipe` | A game that destroys every object it finds doesn't find the probe. |

`hold_wait`, `wait` and `load_async` are played once: how many frames the game runs during a wait or a background
load depends on real time. `clocks` reads the wall clock on purpose, so its measure is left out of the comparison of
the two plays.

Not covered by a play: a teleport of a player on a NavMeshAgent (`Inputs.Place` warps the agent; it would need a
baked NavMesh), the window code on the user's own desktop (a play started by hand, not by the checker), and a
project without the Input System or the ImageConversion module (`probe_tests/variants.py`).
