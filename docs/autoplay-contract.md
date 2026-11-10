# AutoPlay contract (Unity, v1 draft)

> **State:** the contract is fixed here so games can be built against it; the shared drop-in
> (`tools/unity-pipeline/autoplay/AutoPlay.cs`, copied unchanged into each game) and the recorder that drives it come
> with the recording pipeline. Until then a game implements the game side (section 6) and tests by hand (section 7).
> The run files and their schemas are the Unreal game-factory's (`autoplay-*/2`), with `"engine": "unity"` in every
> header, so one pipeline reads both.

**Scenario** = a defined start state plus a win/lose condition, numbered 1..n in the game's design doc and named by the
game. It may be a level, a chapter, a race stage or an open-world start setup. A run plays exactly one scenario from
its start state until it is won, lost or times out.

> **AutoPlay's goal is NOT to win (user rule).** The bot only drives the game with human-like input so a recording
> shows the game running. Never tune, fix or re-test the bot to win, score, finish, reach targets, resupply or avoid
> getting stuck; losing, timing out or wandering is fine (metadata). Fix only game bugs (crash, hang, broken scene,
> missing art, lighting, camera); then one AutoPlay run per scenario and the recording request.

Every game implements this once its first scenario is playable. The pipeline then builds the release player, launches
it with the flags below, captures the window with ffmpeg and turns each run into a gameplay bundle (`video.mkv`,
`system_audio.mka`, `inputs.jsonl`, `telemetry.jsonl`, `outcome.json`, `metadata.json`, `validation.json`,
`manifest.json`, `stills/`, `gameplay.mp4`).

The game plays itself: an in-game **bot** reads game state and acts **only by injecting input through the Input
System**: virtual devices that the drop-in adds and drives (`InputSystem.AddDevice<Keyboard>`, `<Mouse>`,
`<Gamepad>`; state events queued with `InputSystem.QueueStateEvent` / `QueueDeltaStateEvent`). The game's own
`InputAction`s read those devices exactly as they read real ones, and the drop-in logs every injected input. Nothing
uses OS-level input (`SendInput`), the bot never calls gameplay code to act, and real devices are disabled during a
run.

## 1. Command line

```
<Game>.exe -autoplay -scenario <n> -seed <s> -skill <0..1> -outputDir <abs dir> -maxSeconds <n>
           -buildCommit <sha> -runId <id> -screen-fullscreen 0 -screen-width 1920 -screen-height 1080
           -logFile <outputDir>\game.log
```

Arguments are Unity style (one dash, value as the next argument), read with `Environment.GetCommandLineArgs()`.
The `-screen-*` and `-logFile` arguments are Unity's own.

| Flag | Meaning | Default |
|---|---|---|
| `-autoplay` | enable AutoPlay (ignored in the editor's Play mode unless the drop-in's editor toggle is on) | off |
| `-scenario <n>` | scenario number, 1-based, as listed in the design doc | 1 |
| `-seed <s>` | integer seed for the bot's RNG and the game's randomness (`UnityEngine.Random.InitState` is seeded for you; seed your own `System.Random`s from `AutoPlay.Seed`). Determinism is not required | 0 |
| `-skill <0..1>` | bot skill: 0 = clumsy novice (slow reactions, noisy aim, poor choices, still trying), 1 = a competent human (it need not win). Document what it does in the design doc | 1 |
| `-outputDir <dir>` | absolute directory for the run's files (created if missing) | `<persistentDataPath>/AutoPlay/<timestamp>` |
| `-maxSeconds <n>` | hard limit from "go"; the run ends with result `timeout` | 600 |
| `-buildCommit <sha>`, `-runId <id>` | echoed into the files | empty |
| `-goTimeout <s>` | how long to wait for the pipeline's `go` file; `0` when testing by hand | 60 |
| `-autoplayAllowInput` | debugging only: keep real devices enabled | off |
| `-autoplayWatchdog <s>` | exit watchdog (section 3, step 8); 0 = off | 120 |

## 2. Display and timing (enforced by the drop-in)

- **Windowed 1920x1080** (`Screen.SetResolution(1920, 1080, FullScreenMode.Windowed)`; the player's saved settings
  are untouched).
- **60 fps cap, vsync off**: `QualitySettings.vSyncCount = 0`, `Application.targetFrameRate = 60`.
- The quality level fixed to the game's highest shipped level; no auto-detect.
- **Never pause or mute on focus loss**: `Application.runInBackground = true` (the template sets it too); the game's
  `OnApplicationFocus` / `OnApplicationPause` handlers must not pause, open a menu or set `AudioListener.pause` while
  `AutoPlay.IsActive`.
- Window title stays the product name (the pipeline finds the window by PID).
- **Real input is ignored**: keyboard, mouse and gamepads are disabled (`InputSystem.DisableDevice`) and the cursor is
  never locked or confined, because the machine is in use while runs are recorded. The virtual devices are not
  affected.

## 3. Run flow

1. Boot into the normal first scene. The drop-in (a `[RuntimeInitializeOnLoadMethod]` bootstrap and a
   `DontDestroyOnLoad` object) parses the flags, opens the files, writes the `start` clock sample.
2. After the first rendered frame it applies the display settings, waits 1 s, writes `outputDir/ready.json` (pid,
   window size) and emits telemetry `autoplay_ready`.
3. The pipeline starts video capture, then creates `outputDir/go`. (No `go` within `-goTimeout` → start anyway,
   `go_timed_out: true`.)
4. On go: clock sample `go`, `Random.InitState(seed)`, audio capture starts (clock sample `audio_start`), telemetry
   `run_start`, then the game's **`StartScenario(n)`** handler is called: load the scenario's scene and apply its start
   state. Skip menus, tutorials and popups in AutoPlay.
5. When gameplay begins, the game calls **`AutoPlay.ScenarioStarted(name)`** (telemetry `scenario_start`) and the bot
   starts. The bot acts only while `AutoPlay.IsRunning`.
6. The game emits telemetry as things happen (section 5) and calls `AutoPlay.SetScore` when the score changes.
7. The run ends with **`AutoPlay.FinishRun(result, score, extra)`**: `win`, `lose`, `abort` (bot stuck, the game's
   call), or `timeout`, called by the drop-in when `maxSeconds` passes since go (subscribe to `AutoPlay.Timeout` to
   compute a final score). Held inputs are released (logged), telemetry `scenario_end`. A restart inside a run
   ("caught → checkpoint") is **not** the end of the run.
8. The drop-in keeps the result screen up 2 s, stops audio capture, writes `outcome.json` and `clock.json`, telemetry
   `run_end`, then `Application.Quit(0)`. Its exit watchdog (a background thread) ends a process that hangs: still
   alive 30 s after `run_end`, or `-autoplayWatchdog` seconds after `maxSeconds` from go → `watchdog.json`
   (`autoplay-watchdog/1`, `reason` `shutdown` or `run`) and exit code **124**.

## 4. Input rules

- The bot acts **only** through the drop-in: `AutoPlay.Hold(control, value)` / `AutoPlay.Release(control)` for keys,
  buttons and sticks (`"<Keyboard>/w"`, `"<Mouse>/leftButton"`, `"<Gamepad>/leftStick"`), `AutoPlay.MouseDelta(x, y)`
  for look, `AutoPlay.Scroll(y)`, `AutoPlay.SetCursor(screenPos)` for pointing. Never call gameplay methods to act (no
  `SpawnTower()`, no teleporting, no setting velocity), and never queue Input System events yourself (they would not
  be logged). Reading game state directly is fine.
- A held control stays down until released; the drop-in logs `down`, `hold` (sampled once per frame while held, with
  the current value) and `up`.
- Every decision the bot needs must be reachable by input. If something is only reachable by clicking UI (build
  panels, upgrade buttons), add hotkey actions for it, or point and click with `SetCursor` + `<Mouse>/leftButton`
  (the virtual mouse moves the UI's pointer, so uGUI and UI Toolkit both see the click).
- **Cursor-based picking**: the game reads the pointer through the Input System (`Mouse.current.position` or a
  `<Pointer>/position` action), never `UnityEngine.Input.mousePosition` (the old Input Manager is off). In AutoPlay
  `Mouse.current` is the virtual mouse. Draw a visible cursor at it so the video shows where the bot points.
- Inject from `Update` of a script ordered before the game's input readers (`[DefaultExecutionOrder(-100)]`), or
  accept one frame of delay.

## 5. Files in outputDir

All JSON is UTF-8; `*.jsonl` has one object per line. Every row carries the same stamp:

- `qpc`: `System.Diagnostics.Stopwatch.GetTimestamp()` (= `QueryPerformanceCounter` on Windows, the clock the
  pipeline and the recorder use);
- `t_ns`: `qpc * 1e9 / Stopwatch.Frequency`;
- `frame`: `Time.frameCount`.

| File | Writer | What |
|---|---|---|
| `inputs.jsonl` | drop-in | `header` (schema `autoplay-inputs/2`, `engine: "unity"`, game, run_id, scenario, seed, skill, max_seconds, qpc_frequency, build_commit), then `inject` rows `{key: "<Keyboard>/w", value, edge: down/hold/up}`, `cursor` rows `{key: "<Mouse>/position", value: [x, y]}`, `release` rows |
| `telemetry.jsonl` | drop-in + game | drop-in: `header`, `autoplay_ready`, `run_start`, `scenario_start`, `scenario_end`, `run_end`, `run_aborted`, `error`. Game, through `AutoPlay.Telemetry(event, fields)`: `score` {score, delta, reason} on every change; `state` at 10 Hz {player position `[x, y, z]` m (Y up), rotation `[pitch, yaw, roll]`, velocity, plus the game's own numbers}; `restart` {reason}; the genre's own events (waves, checkpoints, laps, detections...) |
| `outcome.json` | drop-in (`FinishRun`'s arguments) | `autoplay-outcome/2`: result, score, duration_s (scenario_start → scenario_end), run_duration_s (go → scenario_end), frames, inputs_injected, go_timed_out, build_config, engine_version (`Application.unityVersion`), extra |
| `clock.json` | drop-in | `autoplay-clock/2`: samples `start`, `go`, `audio_start`, `audio_stop`, `end`, each QPC (before/after) paired with UTC wall time |
| `audio.wav`, `audio_clock.jsonl` | drop-in | the mixed game audio from go to the end of the result hold: `OnAudioFilterRead` on the AudioListener's object, 16-bit PCM at `AudioSettings.outputSampleRate`, every buffer stamped with QPC; a renderer stall is written as silence so WAV position = time since the first buffer |
| `ready.json`, `go`, `game.log` | handshake, Unity's player log | kept in the raw run directory, not in the dataset bundle |

## 6. The game's side

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

1. Build the player: `Scripts/unity.ps1 build` (release) or `-Development`.
2. Run one scenario rendered through the limiter:
   `Scripts/unity.ps1 play -Scenario 1 -Render -Seconds 180 -Extra "-autoplay -goTimeout 0 -maxSeconds 120 -outputDir <abs dir>"`.
3. Check the run's files: every file of section 5 present and well formed, `inputs.jsonl` has injected input,
   `telemetry.jsonl` has `scenario_start` and `scenario_end`, `outcome.json` has a result. (The run checker comes with
   the pipeline.) The bot plays like a human, but its score never holds up a release.
4. Tag `milestone/autoplay-<n>` (scenarios 1..n work), take the framing-gate screenshots (unity-game-session skill)
   and send the request.

## Naming rule (game side)

Nothing in the game's AutoPlay code, telemetry or files names the studio, the tool repos or the agent (the
unity-game-session skill's "Names").
