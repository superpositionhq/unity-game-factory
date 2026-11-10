# AutoPlay contract (Unity, v1)

> **The AutoPlay drop-in is here (v1):** `tools/unity-pipeline/autoplay/AutoPlay/`, copied unchanged into every game
> as `Assets/AutoPlay/` ([Getting the drop-in](#getting-the-drop-in)). A game implements its side (section 6), tests
> one scenario by hand (section 7) and tags `milestone/autoplay-<n>`. The recorder, the run checker
> (`tools/unity-pipeline/validate-run.ps1`) and the recording queue are the recording pipeline's
> ([unity-pipeline.md](unity-pipeline.md)); a session sends the coordinator what is ready, and only the coordinator
> queues recordings ([Queue](unity-pipeline.md#queue)).

**Scenario** = a defined start state plus a win/lose condition, numbered 1..n in the game's design doc and named by the
game. It may be a level, a chapter, a race stage or an open-world start setup. A run plays exactly one scenario from
its start state until it is won, lost or times out.

> **AutoPlay's goal is NOT to win (user rule).** The bot only drives the game with human-like input so a recording
> shows the game running. Never tune, fix or re-test the bot to win, score, finish, reach targets, resupply or avoid
> getting stuck; losing, timing out or wandering is fine (metadata). Fix only game bugs (crash, hang, broken scene,
> missing art, lighting, camera); then one AutoPlay run per scenario and the recording request.

**Priorities (user decision).** What ships is what matters, in this order: the game plays; the game builds (editor and
the Windows release player); the dataset holds the replay scripts and the git log. The AutoPlay bot should still play
like a human (human-like input, aim and camera), but bot work never blocks a release: one recording per scenario that
shows the game running is enough, whatever the result (win/lose/timeout is metadata). No tuning for win rates, seed
sweeps or "clean" runs, and no re-runs or re-recordings to improve how the bot plays. No retest loops: every GPU or
editor run costs the shared machine and holds up delivery, so run the minimum once and report; re-run only when the
user asks. Game-session work never blocks dataset packaging or sharing.

Every game implements this once its first scenario is playable. The recording pipeline then builds the release
player, launches it with the flags below, captures the window with ffmpeg and turns each run into a gameplay bundle
(`video.mkv`, `system_audio.mka`, `inputs.jsonl`, `telemetry.jsonl`, `outcome.json`, `metadata.json`,
`validation.json`, `manifest.json`, `stills/`, `gameplay.mp4`; see
[unity-pipeline.md, Bundle](unity-pipeline.md#bundle)).

The game plays itself: an in-game **bot** reads game state and acts **only by injecting input through the Input
System**: a virtual Keyboard, Mouse and Gamepad that the drop-in adds and feeds with state events
(`InputSystem.AddDevice`, `InputSystem.QueueStateEvent`). The game's own `InputAction`s, `Keyboard.current` and
`Mouse.current` read those devices exactly as they read real ones, and the drop-in logs every injected input. Nothing
uses OS-level input (`SendInput`), the bot never calls gameplay code to act, and real devices are disabled during a
run.

Use the drop-in unchanged, so all games write identical files. Your game supplies three things: a `StartScenario`
handler (set up scenario n), the calls `ScenarioStarted(name)` and `FinishRun(result, score)`, and the bot.

## Getting the drop-in

The drop-in is the folder `tools/unity-pipeline/autoplay/AutoPlay/` with its `.meta` files and `AutoPlay.meta` beside
it: one assembly, `AutoPlay` (`AutoPlay.asmdef`, auto-referenced, so the game's scripts in `Assembly-CSharp` see it; a
game assembly of its own lists `AutoPlay` in its `references`). It needs the Input System package (the template
installs it) and compiles without it, the bot's input then reaching nothing. It holds runtime code only (no
`UnityEditor` API) and runs in IL2CPP and Mono Windows players. The `.meta` files carry fixed GUIDs, so every game
has the same drop-in, and copying it again keeps them.

- **A new game** (`templates/new-game.ps1`) has it from its first commit, in `Assets/AutoPlay/`, with the template's
  scenario list `Assets/Scripts/Scenarios.cs` (section 6), which already calls it.
- **A game made before the drop-in, and every game when the drop-in changes** (a new `autoplay_version`, or a fix):
  after pulling unity-game-factory, run once

  ```
  powershell -ExecutionPolicy Bypass -File <root>\unity-game-factory\tools\unity-pipeline\autoplay\install.ps1 -Game <root>\games\<slug>
  ```

  It copies the drop-in unchanged into `Assets/AutoPlay/` (only the files that differ), and replaces the game's
  `Scripts/unity.ps1` with the template's current one when the game's is an unchanged copy of any earlier template
  (its `autoplay` mode runs the hand test, section 7); a `Scripts/unity.ps1` the game changed itself is kept and named.
  It writes one `workflow.jsonl` row (op `autoplay.install`: the version, the files written with their sha256, what
  happened to `Scripts/unity.ps1`) and makes one commit of exactly those files. It refuses while `Assets/AutoPlay`,
  `Scripts/unity.ps1` or `workflow.jsonl` have uncommitted changes (commit first), touches nothing else, and leaves the
  rest of the game's work as it was, staged or not; files in `Assets/AutoPlay` that are not the drop-in's are left
  alone and named (keep the game's own code out of that folder). On an up-to-date game it changes nothing.
  `-DryRun` says what it would do. It wires nothing: the game's side is section 6.

## 1. Command line

The recorder launches the release player like this (the flags are read by the drop-in, `-scenario` by the game too):

```
<Game>.exe -autoplay -scenario <n> -seed <s> -skill <0..1> -outputDir <abs dir> -maxSeconds <n>
           -buildCommit <sha> -runId <id> -screen-fullscreen 0 -screen-width 1920 -screen-height 1080
           -logFile <outputDir>\game.log
```

Arguments are Unity style (one dash, value as the next argument, any case), read with
`Environment.GetCommandLineArgs()`. The `-screen-*` and `-logFile` arguments are Unity's own. A value that does not
read (a seed that is no integer, a skill outside 0..1) is held to its range or replaced by the default, with an
`error` telemetry row saying so.

**Recording builds are release players** (`Scripts/unity.ps1 build`, IL2CPP; not `-Development`): a development build
draws "Development Build" on its frames.

| Flag | Meaning | Default |
|---|---|---|
| `-autoplay` | enable AutoPlay (a player only; the editor's Play mode never is) | off |
| `-scenario <n>` | scenario number, 1-based, as listed in the design doc; read by the game itself, with or without `-autoplay` (`AutoPlay.ScenarioArgument`) | 1 |
| `-seed <s>` | integer seed for the bot's RNG and the game's randomness (`UnityEngine.Random.InitState(seed)` at boot and again at go; seed your own `System.Random`s from `AutoPlay.Seed`). Determinism is not required | 0 |
| `-skill <0..1>` | bot skill: 0 = clumsy novice (slow reactions, noisy aim, poor choices, still trying), 1 = best the bot can do (a competent human; it need not win). Interpolate reaction time, aim/steering noise, decision quality. Document what it does in the design doc | 1 |
| `-outputDir <dir>` | absolute directory for the run's files (created if missing) | `<persistentDataPath>/AutoPlay/<yyyyMMdd-HHmmss>` |
| `-maxSeconds <n>` | hard limit from go; the run ends with result `timeout`; 0 = no limit | 600 |
| `-buildCommit <sha>` | echoed into every header and outcome.json | empty |
| `-runId <id>` | echoed into every header and outcome.json | empty |
| `-scenarioName <text>` | the scenario's name in the files until the game calls `ScenarioStarted(name)` | empty |
| `-goTimeout <s>` | how long to wait for the pipeline's `go` file; `0` starts at once (testing by hand) | 60 |
| `-autoplayQuality <level>` | the run's quality level, an index or a name (`QualitySettings.names`): the recorder's way to record a GPU-bound game one level lower ([unity-pipeline.md](unity-pipeline.md#queue)) | the highest the build ships |
| `-autoplayMute` | the speakers get silence; `audio.wav` still gets the sound (hand tests on a shared machine) | off |
| `-autoplayAllowInput` | debugging only: real devices stay enabled and the drop-in leaves the cursor to the game | off |
| `-autoplayWatchdog <s>` | exit watchdog: the process is ended if still alive `<s>` after `maxSeconds` from go (section 3, step 8); 0 = off | 120 |

In a task check's play (a player started with `-taskProbe`, [task-probes.md](task-probes.md)) a task's `play_args` may
hold `-autoplay`: the bot then plays while the probe watches. The probe owns the window and the frame rate there, so
the drop-in leaves both alone, and `-goTimeout` defaults to 0.

## 2. Display and timing (enforced by the drop-in)

- **Windowed 1920x1080**: after the first rendered frame the drop-in calls
  `Screen.SetResolution(1920, 1080, FullScreenMode.Windowed)` when the window is not so already (the recorder's
  `-screen-*` flags make it so from the start), and again, with an `error` telemetry row, whenever the game changes it
  during the run. A Unity player is per-monitor DPI aware, so this is 1920x1080 physical pixels at any scaling
  (measured: client area 1920x1080 at 125 %).
- **A run changes the player's saved window.** A Unity player saves the window it is started with (the `-screen-*`
  flags, and a window the drop-in sets) as its own setting (`Screenmanager ...` in its `PlayerPrefs`), and its next
  normal start opens that way: measured, the flags were saved 1.1 s after launch, two seconds before the first script
  ran, so nothing inside the player can keep the earlier setting. After a recording on a machine, that player's
  normal start opens at 1920x1080 windowed (every rendered play does the same: `Scripts/unity.ps1 play -Render` saves
  1280x720); one normal start with Unity's own `-screen-*` flags (`-screen-fullscreen 1` and the screen's size) sets
  it again.
- **60 fps cap, vsync off**: `QualitySettings.vSyncCount = 0`, `Application.targetFrameRate = 60`, set at boot and
  kept every frame. Vsync is off so frame pacing does not depend on the monitor's refresh rate (measured: 60.0 fps on
  a 144 Hz display; in windowed mode DWM composes the window).
- The quality level fixed to the game's highest shipped level (`QualitySettings.names`, the last), set at boot; no
  auto-detect. `-autoplayQuality` names another.
- **Never pause or mute on focus loss**: `Application.runInBackground = true` (the template sets it too; the drop-in
  keeps it on every frame), and the Input System keeps delivering to an unfocused window
  (`InputSettings.BackgroundBehavior.IgnoreFocus`). The game's `OnApplicationFocus` / `OnApplicationPause` handlers
  must not pause, open a menu or set `AudioListener.pause` while `AutoPlay.IsActive`.
- Window title stays the product name (the pipeline finds the window by PID).
- **Real input is ignored**: every device the native backend reports (keyboard, mouse, gamepads, pens) is disabled
  (`InputSystem.DisableDevice`), at boot and again whenever one is added or enabled, and the cursor is never locked or
  confined (`Cursor.lockState` set back to `None` before and after the game's scripts every frame; a game that turns the
  camera only while the cursor is locked reads `AutoPlay.IsActive` too), because the machine is in use while runs are
  recorded. The virtual devices are not affected.

## 3. Run flow

1. Boot into the normal first scene. The drop-in (a `[RuntimeInitializeOnLoadMethod(BeforeSceneLoad)]` bootstrap and a
   hidden `DontDestroyOnLoad` object) parses the flags, opens the files, writes the `start` clock sample, adds the
   virtual devices and disables the real ones.
2. After the first rendered frame it applies the display settings, waits 1 s, writes `outputDir/ready.json` and
   emits telemetry `autoplay_ready` (measured: about 1.6 s after the start sample).
3. The pipeline starts video capture, then creates `outputDir/go`. (No `go` within `-goTimeout` → start anyway,
   `go_timed_out: true`.) The drop-in looks for it every 50 ms (measured: the `go` sample 12 to 64 ms after the file
   was written). A `go`, `ready.json`, `outcome.json`, `clock.json` or `watchdog.json` left in `outputDir` by an
   earlier run is deleted at boot.
4. On go: clock sample `go`, `Random.InitState(seed)`, audio capture starts (clock sample `audio_start`), telemetry
   `run_start`, then the game's **`StartScenario(n)`** handler is called: load the scenario's scene and apply its start
   state. Skip menus, tutorials and popups in AutoPlay. No handler, or one that throws, ends the run at once with
   result `error` (telemetry `error` says why).
5. When gameplay begins, the game calls **`AutoPlay.ScenarioStarted(name)`** (telemetry `scenario_start`, with the
   scenario's name, e.g. "First Night") and the bot starts. The bot acts only while `AutoPlay.IsRunning` (from go to
   `FinishRun`). The first call of a run marks the scenario's start; a later one (after an in-run restart) only adds a
   row. A call before go or after `FinishRun` is ignored.
6. The game emits telemetry as things happen (section 5) and calls `AutoPlay.SetScore` when the score changes.
7. The run ends with **`AutoPlay.FinishRun(result, score, extra)`**: `win`, `lose`, `abort` (bot stuck, the game's
   call), or `timeout`, called by the drop-in when `maxSeconds` passes since go (subscribe to `AutoPlay.Timeout` to
   compute a final score and call `FinishRun` yourself; otherwise the last `SetScore` is the score). `error` is the
   result of a run that could not start its scenario (no handler, a handler that threw, a scenario the game does not
   have). Held inputs are released (logged), telemetry `scenario_end`. A restart inside a run ("caught → checkpoint")
   is **not** the end of the run.
8. The drop-in keeps the result screen up 2 s, stops audio capture (finishes `audio.wav` and `audio_clock.jsonl`),
   writes `outcome.json` and `clock.json`, telemetry `run_end`, closes every file and then **ends the process itself,
   exit code 0** (`TerminateProcess`, not `Application.Quit`): the engine's shutdown is no part of a run (a game may
   refuse to quit, and on a busy machine it can take minutes), and the game's `OnApplicationQuit` does not run, so a
   run's progress never reaches the player's saves that way. A player that quits on its own during a run (the game
   quit, the window was closed) writes what it has the same way: `release` rows for the controls still held,
   telemetry `run_aborted` and `clock.json`, no `outcome.json` (but `outcome.json` too when the run had ended and only
   its result hold was left), then exit code 0. Measured: the process is gone 0.1 to 0.2 s after `outcome.json`
   appears, and up to 16 s later while an editor compiled on the same machine (Windows tears the process down). The
   pipeline kills the process at `maxSeconds + 90 s` and marks the run failed. The drop-in's **exit watchdog** (a
   background thread, any caller: recorder, test scripts) ends a process that hangs instead: still alive
   `-autoplayWatchdog` seconds after `maxSeconds` from go (a hang in gameplay), or 30 s after `run_end` (the process
   failed to end) → it writes `outputDir/watchdog.json` (`autoplay-watchdog/1`: `reason` `run` or `shutdown`) and
   exits with code **124** (measured: `run`, 10.3 s after go with `-maxSeconds 6 -autoplayWatchdog 4`). The recorder
   treats `shutdown` after a complete run as a warning, `run` as a failure. A crash ends the process with its exception
   code (e.g. -1073741819, an access violation) and leaves the files as far as they got: every row line whole (rows
   reach the disk every frame), `audio.wav` readable (its header is rewritten every frame, before that frame's
   `audio_clock.jsonl` rows), no `outcome.json`.

## 4. Input rules

- The bot acts **only** through the drop-in, and only while `AutoPlay.IsRunning`:
  `AutoPlay.Hold(control)` / `AutoPlay.Hold(control, value)` and `AutoPlay.Release(control)` for keys, buttons,
  triggers and sticks (`"<Keyboard>/w"`, `"<Keyboard>/space"`, `"<Mouse>/leftButton"`, `"<Gamepad>/buttonSouth"`,
  `"<Gamepad>/dpad/up"`, `"<Gamepad>/rightTrigger"` with 0..1, `"<Gamepad>/leftStick"` with a `Vector2`),
  `AutoPlay.ReleaseAll()`, `AutoPlay.MouseDelta(x, y)` for look (pixels of one frame; call it every frame the bot
  turns), `AutoPlay.Scroll(y)`, `AutoPlay.SetCursor(screenPos)` for pointing (screen pixels, origin bottom left, as
  `Mouse.current.position` reads it). Never call gameplay methods to act (no `SpawnTower()`, no teleporting, no setting
  velocity), and never queue Input System events yourself (they would not be logged). Reading game state directly is
  fine.
- A control path is the Input System's: `<Keyboard>/` and any key by its name, `<Mouse>/` `leftButton`,
  `rightButton`, `middleButton`, `forwardButton`, `backButton`; `<Gamepad>/` `buttonSouth`, `buttonEast`,
  `buttonWest`, `buttonNorth` (or their aliases `a`, `b`, `x`, `y`, `cross`, `circle`, `square`, `triangle`),
  `leftShoulder`, `rightShoulder`, `leftTrigger`, `rightTrigger`, `start`, `select`, `leftStickPress`,
  `rightStickPress`, `dpad/up|down|left|right`, `leftStick`, `rightStick`. Any other path does nothing and writes one
  `error` telemetry row per path.
- A held control stays down until released (Hold with 0, or `Vector2.zero` for a stick, releases it too); the drop-in
  logs `down`, `hold` (once per frame while it is held, with the current value) and `up`.
- The Gamepad is added the first time the bot uses one of its controls (a gamepad switches many games' button
  prompts); the Keyboard and Mouse exist from boot, and the Mouse starts at the window's centre.
- Every decision the bot needs must be reachable by input. If something is only reachable by clicking UI (build
  panels, upgrade buttons), add hotkey actions for it, or point and click with `SetCursor` + `<Mouse>/leftButton`
  (the virtual mouse moves the UI's pointer, so uGUI and UI Toolkit both see the click).
- **Cursor-based picking**: the game reads the pointer through the Input System (`Mouse.current.position` or a
  `<Pointer>/position` action), never `UnityEngine.Input.mousePosition` (the old Input Manager is off). In AutoPlay
  `Mouse.current` is the virtual mouse, and the video shows no system cursor: draw a visible cursor at it so the video
  shows where the bot points.
- Input the bot queues in a frame reaches the game at the Input System's next update, at the start of the next frame,
  whatever the script order (measured: `<Keyboard>/w` down in frame 208, the game's action read it in frame 209): a bot
  that needs an exact frame plans one frame ahead, or accepts one frame of delay.

## 5. Files in outputDir

All JSON is UTF-8 without a BOM, LF line ends; `*.jsonl` has one object per line. Every row carries the same stamp:

- `qpc`: `QueryPerformanceCounter`, read through P/Invoke, the clock the pipeline and the recorder use (and Python's
  `time.perf_counter_ns()` on Windows). Not `Stopwatch.GetTimestamp()`: under IL2CPP that is the counter rescaled to
  100 ns ticks (libil2cpp's Windows `Time.cpp`: counter x 10,000,000 / its frequency), the same number only on a PC
  whose counter runs at 10 MHz;
- `t_ns`: `qpc * 1e9 / qpc_frequency` (absolute QPC time in ns, not relative to the run; `qpc_frequency` from
  `QueryPerformanceFrequency`), computed as `(qpc / f) * 1e9 + (qpc % f) * 1e9 / f` with `f = qpc_frequency`, because
  `qpc * 1e9` overflows 64 bits;
- `frame`: `Time.frameCount`.

Rows reach the disk at the end of every frame; `ready.json`, `outcome.json` and `clock.json` are written whole and
then renamed into place, so whoever waits for one never reads half of it.

### `inputs.jsonl` (written by the drop-in)

```json
{"t_ns":437618858255400,"qpc":4376188582554,"frame":0,"type":"header","schema":"autoplay-inputs/2","autoplay_version":1,"engine":"unity","game":"TideFinal","run_id":"r1","scenario":1,"scenario_name":"","seed":7,"skill":0.6,"max_seconds":60,"qpc_frequency":10000000,"build_commit":"abc1234"}
{"t_ns":...,"qpc":...,"frame":208,"type":"control_info","key":"<Keyboard>/w","actions":["Move"]}
{"t_ns":...,"qpc":...,"frame":208,"type":"inject","key":"<Keyboard>/w","value":1,"edge":"down"}
{"t_ns":...,"qpc":...,"frame":209,"type":"inject","key":"<Keyboard>/w","value":1,"edge":"hold"}
{"t_ns":...,"qpc":...,"frame":248,"type":"inject","key":"<Mouse>/delta","value":[0.87,0],"edge":"impulse"}
{"t_ns":...,"qpc":...,"frame":488,"type":"cursor","key":"<Mouse>/position","value":[964.1,601.85]}
{"t_ns":...,"qpc":...,"frame":608,"type":"inject","key":"<Gamepad>/leftStick","value":[-0.4,1],"edge":"down"}
{"t_ns":...,"qpc":...,"frame":440,"type":"inject","key":"<Keyboard>/d","value":0,"edge":"up"}
{"t_ns":...,"qpc":...,"frame":3780,"type":"release","key":"<Keyboard>/w","value":0,"edge":"up"}
```

`type`: `header` | `control_info` (the bot's first use of a control: the game's enabled InputActions bound to it, as
`"Map/Action"` or `"Action"`) | `inject` (`edge` = `down` when a control is pressed, `hold` once per frame while it is
held (from the frame after its `down`, written at the end of the frame), `up` when it is released, `impulse` for a
mouse delta or scroll, which last one frame) | `release` (an `up` the drop-in writes itself for a control still held
when the run ends) | `cursor` (a `SetCursor` that moved the pointer). `key` is the control's Input System path (the
canonical name: `<Gamepad>/a` is logged as `<Gamepad>/buttonSouth`); `value` is what the bot put into the control's
state (1/0 for a key or button, 0..1 for a trigger, `[x, y]` for a stick, a mouse delta, a scroll or a position),
before the control's own processors (a stick's deadzone). An input logged in frame f reaches the game in frame f + 1
(section 4).

### `telemetry.jsonl` (drop-in rows + your game's rows)

```json
{"t_ns":...,"qpc":...,"frame":189,"event":"scenario_start","scenario":1,"scenario_name":"Tide Run","scene":"Assets/Scenes/Arena.unity"}
{"t_ns":...,"qpc":...,"frame":240,"event":"score","score":1,"delta":1,"reason":"progress"}
{"t_ns":...,"qpc":...,"frame":1874,"event":"guard_state","guard":"Guard_2","from":"patrol","to":"suspicious"}
```

Written by the drop-in: `header` (the same fields as inputs.jsonl's, `schema` `autoplay-telemetry/2`),
`autoplay_ready` {`window` [w, h], `fullscreen_mode`, `quality`, `quality_level`, `vsync_count`, `target_fps`},
`run_start` {`scenario`, `seed`, `skill`, `go_timed_out`}, `scenario_start` {`scenario`, `scenario_name`, `scene`: the
active scene's path}, `scenario_end` {`result`, `score`, `extra`}, `run_end` {`audio_ok`: any audio captured},
`run_aborted` {`phase`: `boot`, `waiting_for_go` or `running`}, `error` {`message`}. Written by the game with
`AutoPlay.Telemetry(event, fields)` (a dictionary: strings, numbers, bools, `Vector2`/`Vector3` as arrays, a
`Quaternion` as its euler angles `[pitch, yaw, roll]`, lists and dictionaries of those; the keys `t_ns`, `qpc`,
`frame` and `event` are the drop-in's and are left out), from boot to the end of the run: on every game, `score`
{score, delta, reason} on every change, `state` at 10 Hz {player position `[x, y, z]` m (Y up), rotation `[pitch,
yaw, roll]`, velocity, plus the game's own numbers} and `restart` {reason} for in-run restarts; add the genre's own
events (waves, checkpoints, laps, detections...) freely.

### `outcome.json` (drop-in; your part is the arguments of `FinishRun`)

```json
{"schema":"autoplay-outcome/2","autoplay_version":1,"engine":"unity","game":"TideFinal","run_id":"ok","scenario":1,"scenario_name":"Tide Run",
 "seed":7,"skill":0.6,"max_seconds":60,"qpc_frequency":10000000,"build_commit":"abc1234","result":"win","score":21,
 "duration_s":11.415671,"run_duration_s":11.445078,"go_qpc":4385959723793,"scenario_start_qpc":4385960017866,
 "scenario_end_qpc":4386074174573,"frames":682,"inputs_injected":920,"go_timed_out":false,"build_config":"release",
 "engine_version":"6000.3.28f1","scripting_backend":"il2cpp","audio_frames":646144,"audio_silence_frames":0,"audio_gaps":0,
 "extra":{"time_s":11.42,"reached_goal":true}}
```

`game` = the player's exe name (`<Game>.exe`); `duration_s` = scenario_start → scenario_end; `run_duration_s` = go →
scenario_end; `frames` = frames from scenario_start to scenario_end (so `frames / duration_s` is the gameplay fps);
`scenario_start_qpc` is null (and `duration_s`, `frames` count from go) when the game never called
`ScenarioStarted`; `inputs_injected` = the `inject` rows of inputs.jsonl; `build_config` = `release` or `development`;
`engine_version` = `Application.unityVersion`; `scripting_backend` = `il2cpp` or `mono`. Put game-specific results in
`extra` (stars, lap times, times spotted, shots used).

### `clock.json` (drop-in)

```json
{"schema":"autoplay-clock/2","scenario":1,"scenario_name":"Tide Run","qpc_frequency":10000000,"t_ns_definition":"qpc * 1e9 / qpc_frequency",
 "samples":[{"label":"start","qpc":4376188584008,"qpc_after":4376188584102,"t_ns":437618858400800,"unix_ns":1794343366960117500,"utc":"2026-11-10T20:42:46.960Z","frame":0}, "go", "audio_start", "audio_stop", "end"]}
```

Each sample pairs QPC (read before and after) with UTC wall time (`DateTime.UtcNow`, ms resolution). A run that ended
early has the samples it reached (`start`, ..., `end`).

### `audio.wav` and `audio_clock.jsonl` (drop-in)

The mixed game audio from go until the result hold ends: `OnAudioFilterRead` on the AudioListener's object (a hidden
component the drop-in adds), 16-bit PCM at `AudioSettings.outputSampleRate` with the output's channel count. Each
buffer is stamped with QPC when it arrives on the audio thread; if it arrives later than the wall clock allows (more
than max(2048, 2 buffers) frames behind), the missing time is written as silence first, so WAV sample position = time
since the first buffer. The listener usually changes with the scene (it sits on the camera): the drop-in follows it to
the new one and writes the frames in between as silence the same way (the task check's probe measured up to 4 frames
without a tap after a listener change). One `audio_clock.jsonl` row per buffer, in WAV order:

```json
{"frame":2048,"frames":1024,"qpc":4385960204700,"t_ns":438596020470000,"silence_before":0,"audio_clock":5.9733333333333336,"channels":2,"rate":48000}
```

`frame` = index of the buffer's first sample frame in `audio.wav`; `frames` = its length; `qpc`/`t_ns` = QPC time of
that first frame (arrival time minus the buffer's duration); `silence_before` = silent frames inserted before it (a
renderer stall or a listener change); `audio_clock` = the mixer's own clock in seconds (`AudioSettings.dspTime`).
Map a WAV position to the shared clock with the last row whose `frame` ≤ it: `t_ns = row.t_ns + (pos − row.frame) /
rate · 1e9`. `outcome.json` adds `audio_frames` (the WAV's frames), `audio_silence_frames` and `audio_gaps`. The
pipeline anchors the WAV with these rows and turns it into `system_audio.mka` (`aligned` when the clock drift stays ≤
250 ms). Measured on a 48 kHz device: 1024-frame buffers (21 ms) arrive about every 20 ms with up to one buffer of
jitter, two at once right after go; the drift stayed under 50 ms in every run, a listener swap included, and a sound
appeared in the WAV within 27 ms of the game's `PlayOneShot` call. (A mixer recording without per-buffer stamps
dropped buffers under load on earlier games: runs lost 8-23 s of audio, and the sound no longer lined up with the
video.)

### `ready.json`, `go`, `game.log`, `watchdog.json`

`ready.json` {`pid`, `title`, `window` [w, h], `fullscreen_mode`, `scenario`, `scenario_name`, `autoplay_version`,
`t_ns`, `qpc`, `frame`}; `go` (any content) from the pipeline; `game.log`, Unity's player log (`-logFile`), where the
drop-in's own lines start with `AutoPlay:`; `watchdog.json` only from the exit watchdog. Kept in the raw run directory,
not part of the dataset bundle.

## 6. The game's side

Before this, a game already starts every scenario from `-scenario <n>` alone (past menus, tutorials and popups),
reads all input through the Input System (the template makes it the only active input handling), never pauses or
mutes on focus loss (section 2) and has every action reachable by input (section 4); its design doc and the README's
Scenarios table list scenarios 1..n (name, start state, win/lose).

**A game made from the template** has `Assets/Scripts/Scenarios.cs`: fill in `Scenes` (scenario n's scene at index
n - 1, as in the build list) and `Names`. It already loads scenario n from `-scenario <n>` and from AutoPlay's
`StartScenario`, and finishes a run that names a scenario it does not have with result `error`. The scenario's code
then does the rest:

```csharp
// When gameplay begins in the loaded scene (Scenarios.Current says which scenario; 0 in normal play):
Scenarios.Started();                                       // AutoPlay.ScenarioStarted(<its name>): the bot starts

// When it ends:
AutoPlay.FinishRun("win", score, new Dictionary<string, object> { ["stars"] = 2 });
```

**A game made before the drop-in** already starts scenario n from `-scenario <n>` with code of its own. After
`install.ps1`, hand that code to AutoPlay and keep it from starting the scenario at boot in AutoPlay (the drop-in starts
it at go, so the recording shows it from its start):

```csharp
// Somewhere that exists from boot (a [RuntimeInitializeOnLoadMethod], or the first scene's Awake):
AutoPlay.StartScenario += n =>
{
    if (!MyScenarios.Has(n))
    {
        AutoPlay.FinishRun("error", 0, new Dictionary<string, object> { ["reason"] = $"no scenario {n}" });
        return;
    }
    MyScenarios.Start(n);                                  // load its scene, apply its start state
};
// The game's own -scenario jump at boot:
if (n > 0 && !AutoPlay.IsActive) MyScenarios.Start(n);

// When gameplay begins:  AutoPlay.ScenarioStarted("First Night");
// When it ends:          AutoPlay.FinishRun("win", score, extra);
```

`AutoPlay.IsActive`, `ScenarioArgument`, `Scenario`, `Seed`, `Skill` and `MaxSeconds` can be read from anywhere at any
time (the command line is read when first asked). Outside AutoPlay every call does nothing, so the game's code calls
them unconditionally.

The bot is the game's own `MonoBehaviour`, added when the scenario starts in AutoPlay, acting only while
`AutoPlay.IsRunning`, reading game state and calling the input API of section 4, scaled by `AutoPlay.Skill` and
human-like: eased camera turns (no snapping), reaction delays, aim noise, no jump spam.

## 7. Testing by hand and declaring readiness

1. Build the player: `Scripts/unity.ps1 build` (release, IL2CPP) or `-Development` (Mono).
2. Run one scenario as a recording would:
   `Scripts/unity.ps1 autoplay -Scenario 1 [-MaxSeconds 120] [-Seed 0] [-Skill 1]`. It starts the built player with
   the contract's flags plus `-goTimeout 0` (no recorder, so no `go` file; the run starts at once and
   `go_timed_out` is true) and `-autoplayMute`, through the limiter (a GPU slot), on a Windows desktop of its own:
   nothing shows on the screen and the keyboard, the cursor and the speakers stay with whoever uses the machine
   (`-Audible` lets the sound play). The run's files go to `Logs/autoplay/<time>_s<n>/`, and the mode prints a summary
   of them: which files are missing, the result, duration, frame rate, injected inputs and seconds of sound,
   the rows of each kind, the `error` rows, the watchdog's note and the player log's `AutoPlay:` and exception lines.
   A game whose `Scripts/unity.ps1` has no `autoplay` mode (changed by the game itself, so `install.ps1` kept it)
   runs `Scripts/unity.ps1 play -Scenario 1 -Render -Seconds 300 -Extra "-autoplay -goTimeout 0 -maxSeconds 120
   -autoplayMute"` instead: rendered on the screen, its files in `<persistentDataPath>/AutoPlay/<time>/` (the player
   log's first `AutoPlay:` line names the folder).
3. Check the run's files: every file of section 5 present and well formed, `inputs.jsonl` has injected input,
   `telemetry.jsonl` has `scenario_start` and `scenario_end`, `outcome.json` has a result and no `error` rows say
   something is wrong, `audio.wav` is not silent. The recording pipeline's run checker checks the same folder and must
   say PASS:
   `powershell -ExecutionPolicy Bypass -File <root>\unity-game-factory\tools\unity-pipeline\validate-run.ps1 <the run's folder>`
   ([unity-pipeline.md](unity-pipeline.md#validation-per-run); `go_timed_out` is only a note in a hand test). The bot
   plays like a human, but its score never holds up a release.
4. When scenario 1 passes, commit and tag it `milestone/autoplay-1` (later: `milestone/autoplay-<n>` = scenarios 1..n
   work; the recording queue records scenarios 1..n of the newest such tag reachable from the commit), take the
   framing-gate screenshots (unity-game-session skill) and report to the coordinator what is ready (the commit, the
   tag, the scenarios, the run checker's result, the screenshot paths). Only the coordinator queues recordings
   ([unity-pipeline.md](unity-pipeline.md#queue)).

Changes to this contract go through the coordinating session; the drop-in's version (`autoplay_version`) goes up when
the files change shape, and every game then runs `install.ps1` again.

## Naming rule (game side)

The names **Superposition**, **game-factory** and **unity-game-factory** (case-insensitive, including `game_factory` /
`gamefactory`) must not appear anywhere in a game: repo files, code, comments, settings (e.g. `companyName` in
`ProjectSettings/ProjectSettings.asset`, which the build carries in `<Game>_Data\app.info` and which names the player's
`persistentDataPath` folder), scripts, commit messages, builds, logs, in-game files, or anything passed to the game
process; agent, model and provider names stay out too (the unity-game-session skill's "Names"). Everything else stays
as it is: recording and workflow traces are fine and `workflow.jsonl` stays in the repo. The drop-in follows this: its
files, its rows and the commit and row `install.ps1` writes name none of them. Words like recording, dataset,
pipeline, workflow row ids in commit messages and `workflow.jsonl` are fine.

## Changes

- **v1** (`autoplay_version` 1): the first Unity drop-in. Files `autoplay-inputs/2`, `autoplay-telemetry/2`,
  `autoplay-outcome/2`, `autoplay-clock/2`, `autoplay-watchdog/1`, with `"engine": "unity"` in every header.
