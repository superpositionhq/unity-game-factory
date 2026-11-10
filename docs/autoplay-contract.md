# AutoPlay contract (Unity, v1 draft)

> **Not available yet: the AutoPlay drop-in, the recorder and the run checker.** The contract is fixed here so games
> are built ready for it, but a game cannot implement or test it today: its code needs the drop-in's `AutoPlay` class
> (the shared implementation every game will copy unchanged), and that class is not in the repo. Until it is, do not
> implement AutoPlay, do not write a bot, and do not write a stand-in `AutoPlay` class of your own (it would not match
> the drop-in): do what "Until the drop-in is here" below says instead. The drop-in and the recorder come with the
> recording pipeline ([unity-pipeline.md](unity-pipeline.md)); their run files will be the Unreal game-factory's
> (schemas `autoplay-*/2`) with `"engine": "unity"` in every header, so one pipeline reads both.

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

## Until the drop-in is here

What a game does today, so that it is ready for AutoPlay (the task check's plays already rely on the first two):

- **Every scenario starts from the command line.** The player started with `-scenario <n>` (1-based, the numbers of the
  design doc; Unity style: one dash, the value as the next argument, read with `Environment.GetCommandLineArgs()`)
  goes straight into scenario n's start state, past menus, tutorials and popups. `Scripts/unity.ps1 play -Scenario <n>`
  passes exactly this, and a task's `play_args` use it (`["-scenario", "2"]`; how the task check opens a play:
  [task-probes.md](task-probes.md), section 1.1).
- **All input through the Input System** (the template makes it the only active input handling): the game's own
  `InputAction`s, and the pointer through `Mouse.current.position` or a `<Pointer>/position` action, never
  `UnityEngine.Input`. The drop-in's virtual devices and the task check's probe both drive the Input System only.
- **No pause or mute on focus loss**: `Application.runInBackground` stays on (the template sets it), and no
  `OnApplicationFocus` / `OnApplicationPause` handler pauses the game, opens a menu or sets `AudioListener.pause`.
- **Every action reachable by input**: what is otherwise only reachable by clicking UI (build panels, upgrade buttons)
  also gets a hotkey action.
- The design doc lists the scenarios 1..n (name, start state, win/lose; the README's Scenarios table too), and its
  status section says AutoPlay is open.

Report what is ready to the coordinator (the commit sha, the scenarios that start with `-scenario <n>`, the release
build's result); never queue, request or wait for a recording, since there is no recorder yet. The framing check and the
README's screenshots, which come from a bot run once the drop-in is here, come from one short rendered play of the
built player until then (unity-game-session skill).

Everything below is the plan: what the drop-in will do, and what a game adds once it is here.

Every game will implement this once its first scenario is playable and the drop-in is here. The pipeline then builds
the release player, launches it with the flags below, captures the window with ffmpeg and turns each run into a
gameplay bundle (`video.mkv`, `system_audio.mka`, `inputs.jsonl`, `telemetry.jsonl`, `outcome.json`, `metadata.json`,
`validation.json`, `manifest.json`, `stills/`, `gameplay.mp4`; see
[unity-pipeline.md, Bundle](unity-pipeline.md#bundle)).

The game plays itself: an in-game **bot** reads game state and acts **only by injecting input through the Input
System**: virtual devices that the drop-in adds and drives (`InputSystem.AddDevice<Keyboard>`, `<Mouse>`,
`<Gamepad>`; state events queued with `InputSystem.QueueStateEvent` / `QueueDeltaStateEvent`). The game's own
`InputAction`s read those devices exactly as they read real ones, and the drop-in logs every injected input. Nothing
uses OS-level input (`SendInput`), the bot never calls gameplay code to act, and real devices are disabled during a
run.

Use the drop-in (not available yet) unchanged, so all games write identical files. Your game supplies two things: the
`StartScenario` handler (set up scenario n) plus the `ScenarioStarted` call, and the bot.

## 1. Command line

Not available yet: the recorder will launch the release player like this and the drop-in will read the flags; today a
game reads only `-scenario <n>` ("Until the drop-in is here").

```
<Game>.exe -autoplay -scenario <n> -seed <s> -skill <0..1> -outputDir <abs dir> -maxSeconds <n>
           -buildCommit <sha> -runId <id> -screen-fullscreen 0 -screen-width 1920 -screen-height 1080
           -logFile <outputDir>\game.log
```

Arguments are Unity style (one dash, value as the next argument), read with `Environment.GetCommandLineArgs()`.
The `-screen-*` and `-logFile` arguments are Unity's own.

**Recording builds are release players** (`Scripts/unity.ps1 build`, not `-Development`): a development build draws
"Development Build" on every frame, and the recording would show it.

| Flag | Meaning | Default |
|---|---|---|
| `-autoplay` | enable AutoPlay (a player only; ignored in the editor's Play mode) | off |
| `-scenario <n>` | scenario number, 1-based, as listed in the design doc; read by the game itself, with or without `-autoplay` | 1 |
| `-seed <s>` | integer seed for the bot's RNG and the game's randomness (`UnityEngine.Random.InitState` is seeded for you; seed your own `System.Random`s from `AutoPlay.Seed`). Determinism is not required | 0 |
| `-skill <0..1>` | bot skill: 0 = clumsy novice (slow reactions, noisy aim, poor choices, still trying), 1 = best the bot can do (a competent human; it need not win). Interpolate reaction time, aim/steering noise, decision quality. Document what it does in the design doc | 1 |
| `-outputDir <dir>` | absolute directory for the run's files (created if missing) | `<persistentDataPath>/AutoPlay/<timestamp>` |
| `-maxSeconds <n>` | hard limit from "go"; the run ends with result `timeout` | 600 |
| `-buildCommit <sha>` | echoed into outcome.json | empty |
| `-runId <id>` | echoed into every header | empty |
| `-goTimeout <s>` | how long to wait for the pipeline's `go` file; `0` when testing by hand | 60 |
| `-autoplayAllowInput` | debugging only: keep real devices enabled and the cursor free | off |
| `-autoplayWatchdog <s>` | exit watchdog: the process is terminated if still alive `<s>` after `maxSeconds` from go, or 30 s after `run_end` (section 3, step 8); 0 = off | 120 |

## 2. Display and timing (enforced by the drop-in)

Not available yet: the drop-in will enforce these in AutoPlay; today a game only keeps `Application.runInBackground` on
and never pauses or mutes on focus loss.

- **Windowed 1920x1080** (`Screen.SetResolution(1920, 1080, FullScreenMode.Windowed)`; the player's saved settings
  are untouched).
- **60 fps cap, vsync off**: `QualitySettings.vSyncCount = 0`, `Application.targetFrameRate = 60`. Vsync is off so frame
  pacing does not depend on the monitor's refresh rate; in windowed mode DWM composes the window, so captured frames
  don't tear.
- The quality level fixed to the game's highest shipped level; no auto-detect.
- **Never pause or mute on focus loss**: `Application.runInBackground = true` (the template sets it too); the game's
  `OnApplicationFocus` / `OnApplicationPause` handlers must not pause, open a menu or set `AudioListener.pause` while
  `AutoPlay.IsActive`.
- Window title stays the product name (the pipeline finds the window by PID).
- **Real input is ignored**: keyboard, mouse and gamepads are disabled (`InputSystem.DisableDevice`) and the cursor is
  never locked or confined, because the machine is in use while runs are recorded. The virtual devices are not
  affected.

## 3. Run flow

Not available yet: the drop-in and the recorder run this; today a game only starts scenario n from `-scenario <n>`.

1. Boot into the normal first scene. The drop-in (a `[RuntimeInitializeOnLoadMethod]` bootstrap and a
   `DontDestroyOnLoad` object) parses the flags, opens the files, writes the `start` clock sample.
2. After the first rendered frame it applies the display settings, waits 1 s, writes `outputDir/ready.json` (pid,
   window size) and emits telemetry `autoplay_ready`.
3. The pipeline starts video capture, then creates `outputDir/go`. (No `go` within `-goTimeout` → start anyway,
   `go_timed_out: true`.)
4. On go: clock sample `go`, `Random.InitState(seed)`, audio capture starts (clock sample `audio_start`), telemetry
   `run_start`, then the game's **`StartScenario(n)`** handler is called: load the scenario's scene and apply its start
   state. Skip menus, tutorials and popups in AutoPlay.
5. When gameplay begins, the game calls **`AutoPlay.ScenarioStarted(name)`** (telemetry `scenario_start`, with the
   scenario's name, e.g. "First Night") and the bot starts. The bot acts only while `AutoPlay.IsRunning`.
6. The game emits telemetry as things happen (section 5) and calls `AutoPlay.SetScore` when the score changes.
7. The run ends with **`AutoPlay.FinishRun(result, score, extra)`**: `win`, `lose`, `abort` (bot stuck, the game's
   call), or `timeout`, called by the drop-in when `maxSeconds` passes since go (subscribe to `AutoPlay.Timeout` to
   compute a final score). Held inputs are released (logged), telemetry `scenario_end`. A restart inside a run
   ("caught → checkpoint") is **not** the end of the run.
8. The drop-in keeps the result screen up 2 s, stops audio capture (finishes `audio.wav` and `audio_clock.jsonl`),
   writes `outcome.json` and `clock.json`, telemetry `run_end`, then `Application.Quit(0)`. The pipeline kills the
   process at `maxSeconds + 90 s` and marks the run failed. The drop-in's **exit watchdog** (a background thread, any
   caller: recorder, test scripts) ends a process that hangs instead: still alive 30 s after `run_end` (a hang in
   shutdown) or `-autoplayWatchdog` seconds after `maxSeconds` from go (a hang in gameplay) → it writes
   `outputDir/watchdog.json` (`autoplay-watchdog/1`: `reason` `shutdown` or `run`) and exits with code **124**. The
   recorder treats `shutdown` after a complete run as a warning, `run` as a failure.

## 4. Input rules

Not available yet: the bot's input API is the drop-in's; today a game reads all input through the Input System, makes
every action reachable by input, and writes no bot.

- The bot acts **only** through the drop-in: `AutoPlay.Hold(control, value)` / `AutoPlay.Release(control)` for keys,
  buttons and sticks (`"<Keyboard>/w"`, `"<Mouse>/leftButton"`, `"<Gamepad>/leftStick"`), `AutoPlay.MouseDelta(x, y)`
  for look, `AutoPlay.Scroll(y)`, `AutoPlay.SetCursor(screenPos)` for pointing. Never call gameplay methods to act (no
  `SpawnTower()`, no teleporting, no setting velocity), and never queue Input System events yourself (they would not
  be logged). Reading game state directly is fine.
- A held control stays down until released; the drop-in logs `down`, `hold` (once per frame while held, with the
  current value) and `up`.
- Every decision the bot needs must be reachable by input. If something is only reachable by clicking UI (build
  panels, upgrade buttons), add hotkey actions for it, or point and click with `SetCursor` + `<Mouse>/leftButton`
  (the virtual mouse moves the UI's pointer, so uGUI and UI Toolkit both see the click).
- **Cursor-based picking**: the game reads the pointer through the Input System (`Mouse.current.position` or a
  `<Pointer>/position` action), never `UnityEngine.Input.mousePosition` (the old Input Manager is off). In AutoPlay
  `Mouse.current` is the virtual mouse. Draw a visible cursor at it so the video shows where the bot points.
- Input the bot queues in a frame reaches the game at the Input System's next update, at the start of the next frame,
  whatever the script order (the task check's probe measured the same one-frame delay for its own virtual devices): a
  bot that needs an exact frame plans one frame ahead, or accepts one frame of delay.

## 5. Files in outputDir

Not available yet: the drop-in writes these files; today no run writes them.

All JSON is UTF-8; `*.jsonl` has one object per line. Every row carries the same stamp:

- `qpc`: `QueryPerformanceCounter`, read through P/Invoke, the clock the pipeline and the recorder use. Not
  `Stopwatch.GetTimestamp()`: under IL2CPP that is the counter rescaled to 100 ns ticks (libil2cpp's Windows
  `Time.cpp`: counter x 10,000,000 / its frequency), the same number only on a PC whose counter runs at 10 MHz;
- `t_ns`: `qpc * 1e9 / qpc_frequency` (absolute QPC time in ns, not relative to the run; `qpc_frequency` from
  `QueryPerformanceFrequency`), computed as `(qpc / f) * 1e9 + (qpc % f) * 1e9 / f` with `f = qpc_frequency`, because
  `qpc * 1e9` overflows 64 bits;
- `frame`: `Time.frameCount`.

### `inputs.jsonl` (written by the drop-in)

```json
{"t_ns":3911283311000,"qpc":39112833110,"frame":512,"type":"header","schema":"autoplay-inputs/2","autoplay_version":1,"engine":"unity","game":"Stealth","run_id":"...","scenario":1,"scenario_name":"","seed":7,"skill":0.6,"max_seconds":600,"qpc_frequency":10000000,"build_commit":"a1b2c3d"}
{"t_ns":...,"qpc":...,"frame":901,"type":"inject","key":"<Keyboard>/w","value":1,"edge":"down"}
{"t_ns":...,"qpc":...,"frame":902,"type":"inject","key":"<Keyboard>/w","value":1,"edge":"hold"}
{"t_ns":...,"qpc":...,"frame":960,"type":"inject","key":"<Keyboard>/w","value":0,"edge":"up"}
{"t_ns":...,"qpc":...,"frame":975,"type":"cursor","key":"<Mouse>/position","value":[812.5,433]}
```

`type`: `header` | `inject` (`edge` = `down` when a control is pressed, `hold` once per frame while it is held, `up`
when it is released) | `release` (an `up` the drop-in writes itself for a control still held when the run ends) |
`cursor`. `key` is the control's Input System path; `value` is what the control reads (1/0 for a key or button, a
number for an axis, `[x, y]` for a stick, a mouse delta or a position).

### `telemetry.jsonl` (drop-in rows + your game's rows)

```json
{"t_ns":...,"qpc":...,"frame":1200,"event":"scenario_start","scenario":1,"scenario_name":"Warehouse","scene":"Assets/Scenes/Warehouse.unity"}
{"t_ns":...,"qpc":...,"frame":1874,"event":"guard_state","guard":"Guard_2","from":"patrol","to":"suspicious"}
```

Written by the drop-in: `header`, `autoplay_ready`, `run_start`, `scenario_start`, `scenario_end`, `run_end`,
`run_aborted`, `error`. Written by the game with `AutoPlay.Telemetry(event, fields)`: on every game, `score` {score,
delta, reason} on every change, `state` at 10 Hz {player position `[x, y, z]` m (Y up), rotation `[pitch, yaw, roll]`,
velocity, plus the game's own numbers} and `restart` {reason} for in-run restarts; add the genre's own events (waves,
checkpoints, laps, detections...) freely.

### `outcome.json` (drop-in; your part is the arguments of `FinishRun`)

```json
{"schema":"autoplay-outcome/2","autoplay_version":1,"engine":"unity","game":"TowerDefense","run_id":"...","scenario":2,"scenario_name":"Canyon","seed":7,
 "skill":0.6,"max_seconds":600,"qpc_frequency":10000000,"build_commit":"a1b2c3d","result":"win",
 "score":1840,"duration_s":512.3,"run_duration_s":514.9,"go_qpc":...,"scenario_start_qpc":...,"scenario_end_qpc":...,
 "frames":30893,"inputs_injected":20411,"go_timed_out":false,"build_config":"release","engine_version":"6000.3.28f1",
 "audio_frames":...,"audio_silence_frames":0,"audio_gaps":0,"extra":{"stars":2,"lives":14}}
```

`duration_s` = scenario_start → scenario_end; `run_duration_s` = go → scenario_end; `frames` = frames from
scenario_start to scenario_end (so `frames / duration_s` is the gameplay fps); `engine_version` =
`Application.unityVersion`. Put game-specific results in `extra` (stars, lap times, times spotted, shots used).

### `clock.json` (drop-in)

```json
{"schema":"autoplay-clock/2","scenario":2,"scenario_name":"Canyon","qpc_frequency":10000000,"t_ns_definition":"qpc * 1e9 / qpc_frequency",
 "samples":[{"label":"start","qpc":...,"qpc_after":...,"t_ns":...,"unix_ns":...,"utc":"2026-10-11T07:12:13.123Z","frame":3}, "go", "audio_start", "audio_stop", "end"]}
```

Each sample pairs QPC (read before and after) with UTC wall time (`DateTime.UtcNow`, ms resolution).

### `audio.wav` and `audio_clock.jsonl` (drop-in)

The mixed game audio from go until the result hold ends: `OnAudioFilterRead` on the AudioListener's object, 16-bit
PCM at `AudioSettings.outputSampleRate` with the output's channel count. Each buffer is stamped with QPC when it arrives
on the audio thread; if it arrives later than the wall clock allows (more than max(2048, 2 buffers) frames behind), the
missing time is written as silence first, so WAV sample position = time since the first buffer. The listener usually
changes with the scene (it sits on the camera): the drop-in follows it to the new one and writes the frames in between
as silence (the task check's probe measured up to 4 frames without a tap after a listener change). One
`audio_clock.jsonl` row per buffer, in WAV order:

```json
{"frame":2048,"frames":1024,"qpc":13605553354491,"t_ns":1360555335449100,"silence_before":0,"audio_clock":2.70933333,"channels":2,"rate":48000}
```

`frame` = index of the buffer's first sample frame in `audio.wav`; `frames` = its length; `qpc`/`t_ns` = QPC time of
that first frame (arrival time minus the buffer's duration); `silence_before` = silent frames inserted before it (a
renderer stall); `audio_clock` = the mixer's own clock in seconds (`AudioSettings.dspTime`). Map a WAV position to the
shared clock with the last row whose `frame` ≤ it: `t_ns = row.t_ns + (pos − row.frame) / rate · 1e9`. `outcome.json`
adds `audio_frames`, `audio_silence_frames` and `audio_gaps`. The pipeline anchors the WAV with these rows and turns it
into `system_audio.mka` (`aligned` when the clock drift stays ≤ 250 ms). (In the Unreal factory a mixer recording
without per-buffer stamps dropped buffers under load: runs lost 8-23 s of audio, and the sound no longer lined up with
the video.)

### `ready.json`, `go`, `game.log`

Handshake files and Unity's player log (`-logFile`); kept in the raw run directory, not part of the dataset bundle.

## 6. The game's side

Not available yet: this code needs the drop-in's `AutoPlay` class and does not compile without it; today write none of
it (no stand-in class), only what "Until the drop-in is here" says.

```csharp
// Somewhere that exists from boot (a bootstrap scene object, or a [RuntimeInitializeOnLoadMethod]):
AutoPlay.StartScenario += n =>
{
    var scene = ScenarioCatalog.SceneFor(n);              // the game's own list, scenario 1 first
    SceneManager.LoadScene(scene);                         // apply the start state after it loads
};

// When gameplay begins in the loaded scene:
AutoPlay.ScenarioStarted(ScenarioCatalog.NameFor(n));     // e.g. "First Night"; the bot starts now

// When it ends:
AutoPlay.FinishRun("win", score, new Dictionary<string, object> { ["stars"] = 2 });
```

The bot is the game's own `MonoBehaviour`, active only when `AutoPlay.IsActive`, reading game state and calling the
input API of section 4, scaled by `AutoPlay.Skill` and human-like: eased camera turns (no snapping), reaction delays,
aim noise, no jump spam.

## 7. Testing by hand and declaring readiness

Not available yet: the hand test needs the drop-in, and the `milestone/autoplay-<n>` tag means its runs work; today
report what is ready to the coordinator instead, and take the framing stills from one short rendered play
("Until the drop-in is here").

1. Build the player: `Scripts/unity.ps1 build` (release) or `-Development`.
2. Run one scenario rendered through the limiter:
   `Scripts/unity.ps1 play -Scenario 1 -Render -Seconds 180 -Extra "-autoplay -goTimeout 0 -maxSeconds 120 -outputDir <abs dir>"`
   (`-Extra` is split at spaces, so the `-outputDir` path must have none).
3. Check the run's files: every file of section 5 present and well formed, `inputs.jsonl` has injected input,
   `telemetry.jsonl` has `scenario_start` and `scenario_end`, `outcome.json` has a result, `audio.wav` is not silent.
   The run checker comes with the pipeline (not available yet). The bot plays like a human, but its score never holds
   up a release.
4. When scenario 1 passes, commit and tag it `milestone/autoplay-1` (later: `milestone/autoplay-<n>` = scenarios 1..n
   work; the pipeline records scenarios 1..n of the newest such tag), take the framing-gate screenshots
   (unity-game-session skill) and send the request; only the coordinator queues recordings.

Changes to this contract go through the coordinating session; the drop-in's version (`autoplay_version`) goes up when
the files change shape.

## Naming rule (game side)

The names **Superposition**, **game-factory** and **unity-game-factory** (case-insensitive, including `game_factory` /
`gamefactory`) must not appear anywhere in a game: repo files, code, comments, settings (e.g. `companyName` in
`ProjectSettings/ProjectSettings.asset`, which also becomes the exe's company and the `persistentDataPath` folder),
scripts, commit messages, builds, logs, in-game files, or anything passed to the game process; agent, model and
provider names stay out too (the unity-game-session skill's "Names"). Everything else stays as it is: recording and
workflow traces are fine and `workflow.jsonl` stays in the repo. The drop-in will follow this. Words like recording,
dataset, pipeline, workflow row ids in commit messages and `workflow.jsonl` are fine.
