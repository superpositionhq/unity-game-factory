# Unity editor, build and recording pipeline

How heavy Unity work runs on the shared machine today, and the plan for the pipeline that builds a game's release
player, records AutoPlay runs (an in-game bot playing through the Input System, see
[autoplay-contract.md](autoplay-contract.md)) as gameplay bundles ([Bundle](#bundle)), replays the creation and packages
the dataset.

> **Not available yet: the recording pipeline (the release build from a commit, the recorder, the queue, the run
> checker, stills and gameplay videos) and the creation replay.** The sections that say so are the
> plan, with the rules earlier failures taught; nothing in them can be run
> today. Until they are here, a session never queues, requests or waits for a recording and reports to the coordinator
> what is ready (the commit sha, the scenarios that start with `-scenario <n>`, the release build's result); every
> dataset is pending, without `Gameplay/` and `ReplayScripts/`, and nobody assembles a dataset by hand; the
> replay-friendly rules of the unity-game-session skill keep a game's history ready for the replay. What runs today: a
> game's `Scripts/unity.ps1`, the machine-wide job limiter and the dataset packager
> ([Dataset packager](#dataset-packager)). The task checker's own builds and plays (a scratch copy's player, started
> on a Windows desktop of its own) are in [task-check.md](task-check.md).

## Paths

`%UGF_ROOT%` is the machine root: env `UGF_ROOT`, else `root` in `%USERPROFILE%\.unity-game-factory\config.json`
(written by `machine/bootstrap.ps1`), else `%USERPROFILE%\UnityWork`; `machine/lib/ugf-root.ps1` resolves it, and the
same file gives each project's editor: exactly the version its `ProjectSettings/ProjectVersion.txt` names
(`Get-UGFUnity`; Unity Hub's folder `C:\Program Files\Unity\Hub\Editor\<version>\Editor\Unity.exe`, config
`unity_hub_editors`, or `unity_editors` for an editor installed elsewhere). See
[../machine/README.md](../machine/README.md).

```
%UGF_ROOT%\
  games\<slug>\                     the game repos (<org>/unity-game-<slug>; read only for the pipeline)
  games\<slug>\Logs\unity-ps1\      a game's own run logs (Scripts/unity.ps1; Unity's Logs/ folder, git-ignored)
  tasks\<slug>\                     a game's orphan tasks branch, checked out as a worktree
  tools\unity-heavy.ps1             the job limiter (+ ugf-root.ps1 beside it); its log .recording\_heavy-jobs.jsonl
  tools\ffmpeg-8.1.2\               the pinned ffmpeg (machine/get-ffmpeg.ps1)
  .recording\<slug>\actions.jsonl   the recording hooks' rows (machine/README.md); the pipeline never touches them
  .recording\<slug>\messages.jsonl  the same hooks' rows for every prompt and every reply of a session
  .recording\<slug>\commits.jsonl   one row per commit (the post-commit hook)
```

Not available yet, for the pipeline (bootstrap already creates the folders):

```
  builds\<slug>\<short-sha>\        release build: the player, build_info.json, logs\
  builds\_pipeline-<slug>.lock      per-game build/record lock (holder in the .json beside it)
  builds\_queue\                    queued requests; done\ has results
  builds\_logs\                     transcripts of queue runs
  recordings\<slug>\<run-id>\       bundles
  .recording\<slug>\builds.jsonl    one row per build
  .recording\<slug>\runs.jsonl      one row per recorded run
  .recording\<slug>\pipeline.jsonl  one row per pipeline run per game
  deliverables\                     packages and replay packages (config "out", env UGF_OUT)
```

## A game's Unity runs: `Scripts/unity.ps1`

Every game has `Scripts/unity.ps1` from the template; sessions use it rather than calling `Unity.exe` themselves. It
finds the editor for the project's `ProjectSettings/ProjectVersion.txt` (`$env:UNITY_EDITOR`, else `ugf-root.ps1`
`Get-UGFUnity`), runs every job through the limiter, writes the log to `Logs/unity-ps1/` and prints the lines that
matter (compile errors, exceptions, licence errors, `[workflow]` rows) and the exit code.

| Mode | Runs | GPU |
|---|---|---|
| `setup` | the first open, four runs, each needing what the one before installed: `ProjectSetup.AddPackages`, `Urp.UrpSetup.Apply`, `ProjectSetup.ImportTextEssentials`, `ProjectSetup.Configure` | no |
| `compile` | open, import, compile, quit | no |
| `step -Method <Ns.Class.Method> -Reason "..." [-Render] [-NoQuit]` | one editor step (`-executeMethod`); `-Render` for steps that need the GPU (lightmaps, screenshots, shader warm-up); `-NoQuit` for a step that exits the editor itself (a `.unitypackage` import finishes after the method returns) | only with `-Render` |
| `test [-Platform EditMode\|PlayMode] [-Filter <name>]` | Unity Test Framework (`-runTests`, results XML summarized) | no |
| `build [-Development] [-Backend mono\|il2cpp] [-Reason "..."]` | `BuildPlayer.BuildWindows`: the Windows x64 player in `Build/Windows/` (a release build is IL2CPP unless `-Backend mono`, a development build Mono) | no |
| `play [-Scenario <n>] [-Render] [-Seconds 60] [-Extra "..."] [-Tag <name>]` | the built player, headless (`-batchmode -nographics`) or rendered windowed at 1280x720, with `-scenario <n>` when `-Scenario` is given; stopped after `-Seconds` | only with `-Render` |

Keep the call shape `Scripts/unity.ps1 step -Method <Ns.Class.Method>`: the creation replay (not available yet) will
find each editor step's runs by it in the recorded commands.

Facts that cost time before:

- **One Unity process per project**: the project lock (`Temp/UnityLockfile`) makes a second process fail at once.
  The person may have the GUI editor open; then wait or ask.
- **Licence**: batchmode needs an activated licence (Unity Hub, signed in). Without one a run exits 198 with a
  licensing error in the log; `unity.ps1` says so. It is the person's to fix, not a game bug.
- **Compile errors abort batchmode** before `-executeMethod` runs: `error CS` lines first.
- **`-runTests` quits by itself**; with `-quit` the tests never run.
- **`-nographics` renders nothing**: no screenshots, no lightmap bakes, no `ScreenCapture`.
- **IL2CPP** needs the Windows Build Support (IL2CPP) module and Visual Studio's C++ workload (`machine/check.ps1`
  warns when either is missing); `-Backend mono` builds without them.
- **`play` exits 124** when it stops a player after `-Seconds`: the timeout doing its job, not a crash (read the
  player log for exceptions). `-Extra` is split at spaces, so a value in it cannot hold a space.

## One heavy job at a time

Not available yet, the pipeline's own lock: its build and its recording of a game will take an exclusive per-game
lock on `builds\_pipeline-<slug>.lock` (an open file handle: released by the OS if the process dies, visible across
sessions and Task Scheduler) for the whole build or the whole run, and wait for it otherwise (the holder is printed): a
build and a recording of the same game share its clone, build folder and `_run` copy. Different games only share the
machine, which the general and GPU slots below ration, so a rebuild of one game can run while another game records.
Builds will run at below-normal priority so the game sessions' own editors stay responsive; the game and ffmpeg at
above-normal priority during a recording.

### Machine-wide slots

Every heavy job of every session goes through one limiter, `<root>\tools\unity-heavy.ps1` (rows in
`.recording\_heavy-jobs.jsonl`): `& <root>\tools\unity-heavy.ps1 -Label "<slug> <what>" [-Gpu] [-Low] -- <exe> <args>`.
It returns the job's exit code, or 125 when it could not run the job itself (called wrongly, `ugf-root.ps1` missing
beside it, a machine config that is not JSON, an exe that would not start): Unity itself exits 2 for failed tests, so
the limiter's own failures have a code no job uses.
From Git Bash, wrap it in `powershell -ExecutionPolicy Bypass -Command "& '<path>' ... ; exit \$LASTEXITCODE"`
(`powershell -File ... --` misparses `--`; without `-ExecutionPolicy Bypass` Windows' default policy refuses the
script, and with the dollar sign unescaped bash expands `$LASTEXITCODE` to nothing: either way the call returns 0
whatever the job did).

Each slot is a named mutex (`machine/lib/ugf-root.ps1` `Get-UGFSlotMutexes`, `Enter-UGFSlot`). A job that is killed
before it releases its slot (a cancelled tool call, a killed editor) leaves the mutex abandoned, and the next job takes
it over, so no slot leaks (a counted semaphore would lose one slot per killed holder until someone released it by
hand). The counts are read from the config at every call, so a new `heavy_slots` / `gpu_slots`
applies at once.

| Slots | Named mutexes | Taken by | Count |
|---|---|---|---|
| general | `Global\ue-heavy-slot-<n>` | every job: batchmode editor runs, player builds, tests, players, and GPU jobs too | config `heavy_slots`, else the formula |
| GPU | `Global\ue-gpu-slot-<n>` | jobs that render (`Unity.exe` without `-nographics`, a player under a `Build`, `Builds` or `Packaged` folder or started with `-screen-*` / `-popupwindow`, anything run with `-Gpu`; `-nographics` in a command means no GPU slot, even with `-Gpu`), together with a general slot: a GPU job never holds one while waiting for the other | config `gpu_slots`, else the formula |

**The mutex names are another factory's on purpose:** a machine that runs both factories has one set of slots,
so the builds of the two never overcommit the same RAM and GPU. A recording waiting in either factory holds
back new Unity GPU jobs (the other factory's `ue-heavy.ps1` reads only its own root's flag), and a running
recording holds every GPU slot of both.

The formula (`ugf-root.ps1` `Get-UGFComputedSlots`, the same as another factory's; bootstrap.ps1 writes its result to the
config, and a value set by hand stays unless `bootstrap.ps1 -Force`):

- `heavy_slots = clamp(1..8, min(floor((RAM GB - 6) / 6), floor(logical cores / 4), floor((commit limit GB - 6) / 8)))`:
  a heavy process needs about 6 GB, and 6 GB stays for the desktop and the sessions themselves.
- `gpu_slots = clamp(1..4, min(floor(VRAM GB of the largest NVIDIA GPU / 4), heavy_slots - 1))`, 1 without nvidia-smi:
  about 4 GB per renderer, and one general slot always stays free for compiles.

Dynamic guards on top of the counts:

- **VRAM guard:** a GPU job starts only while the GPU's used VRAM is under `gpu_vram_limit_mb` (default half the VRAM)
  and no other GPU job that still runs started in the last 60 s (a new renderer's VRAM shows only once it has loaded;
  one that has ended holds none, and Unity plays last seconds); otherwise it hands its slot back and looks again every
  30 s (`vram_wait` rows).
- **Recordings have priority:** while a recorder waits for the GPU it keeps `builds\_queue\_recording-wants-gpu` fresh
  in its factory's root (rewritten every minute, removed once it holds the slots); `unity-heavy.ps1` holds back new GPU
  jobs while that file exists in either factory's root and is under 20 min old. A recording then takes every GPU slot,
  so a capture has the GPU to itself. Today only another factory's recorder can write the flag; ours is not available
  yet.
- **`-Low`** (background work, such as the live creation replay will be): one low job machine-wide; it takes a general
  slot only while no other job waits for one and another slot stays free, at below-normal priority.

`machine/check.ps1` shows the slots in effect and where each comes from.

## Recording pipeline

Not available yet: nothing in this section can be run; it is what the pipeline will do. Until it is here, a session
reports to the coordinator what is ready and never queues, requests or waits for a recording.

### Build

Not available yet (a session builds its own player with `Scripts/unity.ps1 build` meanwhile).

1. Resolve the commit (default `HEAD`); output goes to `builds\<slug>\<first 8 of sha>\`. A build that already
   succeeded for that sha is reused unless forced.
2. Source: a private clone of the game repo outside the user profile, never the game's working copy, updated to the
   commit (`fetch`, `checkout --force <sha>`, `clean -ffd`; its `Library/` stays, so later builds import only what
   changed). LFS files are checked out as pointers and copied from the game repo's own `.git\lfs\objects` store, so
   nothing is downloaded and the game repo is only read. Uncommitted work is not built.
3. The Windows x64 release player (`BuildPlayer.BuildWindows`, as `Scripts/unity.ps1 build` runs it), through the
   limiter.
4. Leak scan of the build folder: a case-insensitive byte search (ASCII and UTF-16LE) for the Windows user name inside
   paths (`\<name>\`, `/<name>/`) and for superposition / game-factory / game_factory / gamefactory / claude /
   anthropic; hits are warned about and recorded (a build with hits can still be recorded but must not be handed out).
   The clone sits outside `C:\Users` so the user name is not built in (source paths in macros and debug
   symbols can carry it into the exe).
5. A `builds.jsonl` row: `commit`, `short_sha`, `commit_subject`, `command`, `start`/`end`/`duration_s`, `status`,
   `exit_code`, `error_excerpt` (first matching error lines of the failing log), `log_path`, `output_path`,
   `exe_path`, `autoplay_version`, `leak_scan`, and `steps[]` (each with its exact command line, times, exit code,
   log).

### Record

Not available yet (the recorder). Before the runs, the build is mirrored into a stable `builds\<slug>\_run\` and
launched from there: Windows Firewall asks once per program path for a program that listens on the network, so a
fixed path per game means one prompt per game instead of one per build. Per run (seed = `-Seed + i`, or random; skill
= `-Skill`, or cycling 1.0 / 0.75 / 0.5 / 0.25):

0. **Wait until the user is away** (default; the user's standing instruction overrides it): no keyboard/mouse input for
   `-IdleMinutes` (default 5; `GetLastInputInfo`; the game's injected input doesn't count) and the session unlocked.
   From the start of that wait until the run ends the display is kept on (`SetThreadExecutionState`, like a video
   player; no settings change). Right before launch the display is also **woken** (a 1-pixel mouse move out and back,
   outside the game run): the display timeout can equal the idle gate, so when the user went away during a build the
   display is already off, `SetThreadExecutionState` doesn't turn it back on, and Desktop Duplication delivers no frames
   (ddagrab hangs, gdigrab gets ~4 fps). An unanswered Windows Firewall prompt dims the whole screen and blocks capture
   until it is answered. **Idle override:** `builds\_queue\_idle-override.txt` (JSON `{idle_minutes, reason}`, written
   by the coordinator once the recorder is here) replaces the default when `-IdleMinutes` isn't given; `idle_minutes`
   0 = record right away. It is standing (the user's "record now" instruction) unless it has `"one_drain": true`, which
   the drainer retires when the queue empties. The privacy guard and the display wake apply either way. Before
   launching, it also waits while more than 4096 MB of VRAM is in use (nvidia-smi total; per-process numbers are N/A
   under WDDM); after 120 min the run fails.
1. Launch the player from `_run\` with the contract's flags (autoplay-contract.md section 1) plus `-goTimeout 300`,
   windowed 1920x1080, `-logFile <raw>\game.log`.
2. Wait for `ready.json`, find the window by PID, move it so the client area is at (40,80) (whether a Unity player
   re-centres its window after launch is to be checked), make it topmost (not activated), check the client
   area is exactly 1920x1080 and fully on screen (physical pixels; the recorder is per-monitor DPI aware). If anything
   covers it (e.g. a first-run Firewall prompt), wait up to 240 s for it to clear.
3. Start ffmpeg on that screen rectangle, wait for 30 captured frames, write `go`. Each capture attempt has its own
   files (`video.<mode>.mkv`, `raw\ffmpeg-<mode>.log`); a failed attempt is kept as `raw\failed-attempt-<mode>.mkv`.
4. Watch every 100 ms until `outcome.json` appears (written while the result screen is still up).
   **Privacy guard:** if the window moves, or another window covers its client area for ≥ 0.3 s (5x5 point test with
   `WindowFromPoint`; shorter blips are tooltips/ghost windows), ffmpeg is stopped at once, the game killed, the run
   failed, and the video cut to 0.5 s before the first sighting (`-c copy -t`). The problem names the covering window;
   moves are logged in `raw\window.jsonl` with whether a mouse button was held (user drag). A client-size change or a
   minimized window also fails the run. **Stop ffmpeg before the window closes** (so nothing behind it is ever
   captured), wait for the game to quit. Kill after `maxSeconds + 90 s`.
5. Validate and write the bundle (below), even for failed runs.

### Capture

Not available yet (the recorder runs it); the pinned ffmpeg is here today. ffmpeg: gyan.dev
`ffmpeg-8.1.2-full_build.7z` in `%UGF_ROOT%\tools\ffmpeg-8.1.2\ffmpeg-8.1.2-full_build\bin\`, SHA-256
`0fff188997a499b5382e0f66e845d4556c48c54f0113ebed4853d556dbdd7059` (`machine/get-ffmpeg.ps1` fetches and verifies it).
Desktop Duplication (`ddagrab`) of the window's client rectangle, **event-driven**, no mouse cursor, converted to 60
fps CFR. With NVENC (needs NVIDIA driver ≥ 610) the D3D11 frames go straight to the encoder:

```
ffmpeg -hide_banner -loglevel +datetime+level+info -stats_period 1 -progress <raw>\ffmpeg_progress.txt -y
  -f lavfi -i "ddagrab=output_idx=0:framerate=240:dup_frames=0:offset_x=<x>:offset_y=<y>:video_size=1920x1080:draw_mouse=0,showinfo"
  -c:v h264_nvenc -preset p5 -tune hq -rc vbr -cq 19 -b:v 0 -maxrate 60M -bufsize 120M -g 120 -bf 0
  -color_primaries bt709 -color_trc bt709 -colorspace bt709 -color_range tv -fps_mode cfr -r 60 -an <bundle>\video.mkv
```

Why `framerate=240:dup_frames=0` and not `framerate=60`: ddagrab paces itself with `av_usleep`, which on Windows is
`Sleep()` at the default 15.6 ms timer resolution (since Windows 10 2004 a process only gets 1 ms if it asks for it
itself, and ffmpeg doesn't). At `framerate=60` that produced frames at 15.6/31 ms intervals, 57 fps, 5–7 % CFR
duplicates. With `dup_frames=0` and a rate above the display's, the pacing loop never sleeps and ddagrab waits inside
`AcquireNextFrame` for each new desktop image (timestamped when acquired); `-fps_mode cfr -r 60` then keeps the latest
image per 1/60 s slot. ffmpeg's `drop=` count is just these surplus samples; `dup=` counts slots without a new image.

**Encoder.** The recorder probes at start and uses the first that opens: `h264_nvenc` (NVIDIA), `h264_amf` (AMD,
e.g. a CPU's integrated Radeon), `libx264` (CPU); `metadata.video.encoder` says which. The pinned ffmpeg 8.1.2 needs
NVENC API 13.1, i.e. NVIDIA driver ≥ 610; with an older driver it fails ("Required: 13.1 Found: 13.0") and recordings
use AMF. `h264_mf` does not work. AMF and libx264 take system-memory frames, so `fps=60` picks the 60 fps grid on the
GPU frames first and only those are downloaded and converted (BT.709 matrix, limited range):

```
  -f lavfi -i "ddagrab=output_idx=0:framerate=240:dup_frames=0:offset_x=<x>:offset_y=<y>:video_size=1920x1080:draw_mouse=0,showinfo,fps=60,hwdownload,format=bgra,scale=out_color_matrix=bt709:out_range=tv,format=nv12"
  -c:v h264_amf -quality quality -rc cqp -qp_i 18 -qp_p 20 -g 120 -bf 0
```

The libx264 variant is the same with `format=yuv420p` and `-c:v libx264 -preset ultrafast -crf 17 -g 120 -bf 0
-pix_fmt yuv420p` (`veryfast` only reached 0.977x on the shared CPU). Fallbacks (`-Capture`), as measured
on earlier games: `gdigrab-region` captures real content but only ~44 fps (24 % duplicates), `gdigrab-window` ~56 fps (8 %
duplicates, 23 % gap time); both fail validation, so they are for emergencies. `auto` tries ddagrab, then (after waking
the display) ddagrab once more, then gfxcapture, and gdigrab-region last, each only if the one before got fewer than 30
frames in 10 s; each failed attempt is logged with its frame count, whether ffmpeg hung or exited (exit code) and the
tail of its log. `gfxcapture` (Windows.Graphics.Capture of the game window by `hwnd`, ffmpeg 8's `gfxcapture` filter,
max 120 fps, then the same `fps=60` CFR + NVENC path) records only the game window, so other windows never reach the
video, and it needs no live display (a PC reached over remote desktop whose monitor is off); its showinfo pts are in
1/10^7 s, not µs: read the unit from showinfo's `config in time_base` line (misread, it looked like 2–6 frames/s and
broke the start estimate). If the game window stays covered for 240 s before capture, `auto` skips the screen-region
modes and uses gfxcapture.

Display: run it at a multiple of 60 Hz (e.g. 120 Hz) for recording sessions; with vsync off the game's frames reach the
screen on the display's refresh grid, and a 60 Hz capture repeats some and misses some otherwise (measured
on earlier games: 13 % at 159 Hz, 7 % at 120 Hz on the AMF path, 0.3–1.1 % with NVENC). The recorder logs
`machine.display_refresh_hz` and warns (does not fail) when the rate is not a multiple of 60; `machine/check.ps1` checks
it today.

### Bundle

Not available yet (the recorder writes it):

```
recordings\<slug>\<slug>_S<scenario>_<yyyyMMdd-HHmmss>_s<seed>\
  video.mkv           H.264 1920x1080 60 fps CFR, no audio, BT.709 tags
  system_audio.mka    FLAC from the game's audio.wav, aligned with audio_clock.jsonl
  inputs.jsonl        as written by the game (autoplay-contract.md section 5)
  telemetry.jsonl     as written by the game
  outcome.json        as written by the game
  metadata.json       game, scenario, scenario_name, seed, skill, result, build sha, ffmpeg command + version, capture rect,
                      video_start_offset_ns (+ estimate details), system_audio.start_offset_ns,
                      clock samples (game: start/go/audio_start/audio_stop/end; pipeline: record_start,
                      capture_start, go_written, capture_stopped, record_end)
  validation.json     status ok | warn | failed, problems, warnings, per-check details
  manifest.json       sha256 + bytes of every file in the bundle (incl. raw\ and stills\)
  stills\NN.jpg       8 evenly spaced frames (t = duration * i / 9) for README screenshots, runs with status ok / warn
                      only; CPU decode with the pinned ffmpeg (-ss before -i, -frames:v 1, -q:v 2); also copied to
                      recordings\<slug>\_stills\<run_id>_NN.jpg; metadata.json `stills` lists them. A failed extraction
                      is logged and recorded in `stills.error`; it never changes the run's status.
  gameplay.mp4        the dataset's Gameplay/ file (packaged as <slug>_S<n>.mp4), runs with status ok / warn only:
                      video.mkv's H.264 stream copied (1080p60, no re-encode) + system_audio.mka as AAC 192k stereo,
                      aligned on the QPC clock: offset = system_audio.start_offset_ns (from audio_clock.jsonl)
                      − video_start_offset_ns, applied with adelay (audio later) or atrim (earlier), then apad +
                      -shortest to the video's end; +faststart. CPU only, below-normal priority. Checked with ffprobe
                      (h264 + aac, duration within 0.5 s of video.mkv). metadata.json `gameplay_mp4` {audio_offset_s,
                      duration_s, bytes, error}; a failure is logged there and never changes the run's status.
  FAILED              only on failed runs (problems listed); failed runs are kept, never deleted
  INVALID             excluded from the dataset after the fact (reason inside), e.g. recorded from a broken build;
                      validation.json status "invalid" and a runs.jsonl row; files kept
  raw\                the game's outputDir: audio.wav, audio_clock.jsonl, clock.json, ready.json, go, game.log,
                      ffmpeg.log, ffmpeg_progress.txt
```

`video.mkv` is H.264, 60 fps, no audio; `inputs.jsonl` has ns QPC timestamps; there is no microphone track (a bot has
no voice). `video_start_offset_ns` is the capture clock's and does **not** subtract the way from game to screen (game
thread → render thread → GPU → present → DWM → capture: a game event showed on video 14–29 ms after its `t_ns` with
NVENC on earlier games).

### Validation (per run)

Not available yet (the run checker):

| Check | Fails when | Warns when |
|---|---|---|
| outcome | missing, bad `result`, `go_timed_out` | result `abort` |
| inputs | no `inject` rows, unparseable lines, `t_ns` going backwards | |
| telemetry | missing `run_start`/`scenario_start`/`scenario_end`/`run_end`, unparseable lines | |
| audio | missing, or WAV duration doesn't fit the recorded span (start lag outside −30…10000 ms; the lag is the scenario load) | silent (max < −60 dB) |
| video | not 1920x1080, no frames, ffmpeg dup > 5 % of output frames, video longer than the capture span by ≥ 0.5 s or shorter by ≥ 2 s, doesn't cover the scenario (start..end), start time not estimable | dup > 1 %, capture gaps > 2 % of scenario frames, game < 55 fps, video ends 0.5–2 s before the stop, display not 60/120 Hz |
| process | game exit code ≠ 0, killed at timeout, window moved, ffmpeg died | |
| watchdog | `watchdog.json` with `reason` `run` | `watchdog.json` with `reason` `shutdown` after a complete run |

### Queue

Not available yet (the queue and its drainer); today a session reports what is ready to the coordinator instead.

A pipeline run of a game resolves the commit (default `HEAD`) and the scenarios (default 1..n from the newest
`milestone/autoplay-<n>` tag reachable from it, meaning "scenarios 1..n are ready"), skips scenarios that already have
enough good runs of that commit (unless forced), then builds and records per scenario. Each step takes the lock itself,
so other work can interleave between steps.

**Queueing (the coordinator owns the queue).** Game sessions never enqueue; once the queue is here they ask the
coordinating session, and until then they only report what is ready. The queue tool refuses (exit 2, red message,
nothing queued) unless the request says the coordinator made it, and records who did. It returns at once; one hidden
drainer works through `builds\_queue\*.json` in file-name order (the coordinator reorders by renaming; a request being
processed must not be renamed). Dropping a queued request: move it to `builds\_queue\done\` with a `result` note
(status `dropped`). The drainer holds the recordings' GPU flag for each whole job (from its first build step to the
end of its last run) and removes it when the queue is empty.

AutoPlay time limit: 600 s per run by default (the game gets `-maxSeconds`, the recorder kills it 90 s later), per
scenario as `1=300,2=600,3=900` (unlisted ones keep 600; `*=700` changes the rest) or one value for every scenario;
values 30..7200. The request stores it as `max_seconds`, and the job's `pipeline.jsonl` row lists the limit used per
scenario.

**A game that is GPU-bound at its default quality** (coordinator rule 2026-10-18: the GPU 3D
engine above ~95 % with the game under ~55 fps, so the capture fails on duplicated frames) is recorded one quality level
lower and says so: the note goes to the run's `metadata.json` (`capture_notes`), then to the dataset's manifest
(`scenarios[].capture_notes`) and a "Recording note" line under the README's Scenarios table. Nothing else changes (no
game repo edit, no bot change, same validation).

Results: `.recording\<slug>\pipeline.jsonl` (summary), `runs.jsonl`, `builds\_queue\done\<request>.json`; the job
summary lists the build's leak-scan hits (warn-only here; the packager blocks on them). No nightly run: runs are queued
on demand (the user's decision).

### Machine notes and open items

Not available yet (they apply once the recorder runs):

- Any display and scaling that holds a 1920x1080 window should work: a Unity player declares per-monitor DPI awareness
  (PerMonitorV2 in its exe's manifest, Mono and IL2CPP players of 6000.3 built from the template), so its 1920x1080
  should be physical pixels at any scaling (the window itself to check; a DPI-unaware game is
  stretched, e.g. to 2880x1620 at 150 %). Vsync off and a 60 fps cap in the game keep it at 60 fps whatever the refresh.
- The game window sits topmost with its 1920x1080 client area on the primary screen for the run. Runs start only after
  5 min without user input; if you come back mid-run, leave the window alone (moving or covering it stops the run
  safely). Its audio plays on the speakers during runs.
- **Machine-path scrub before bundles leave the machine** (an open item). Bundles
  carry machine paths and the user name: `metadata.json` (build path, exe, ffmpeg command), `raw\game.log`,
  `raw\ffmpeg.log`, `raw\ready.json`. Per AGENTS.md (leak scan for `C:\Users\…`, real names, e-mails), a publish step
  must rewrite or drop these and re-hash `manifest.json` before any upload.

## Creation replay

Not available yet: there is no replay tool to run or configure, and a game holds no replay configuration. Until it is
here, the replay-friendly rules of the unity-game-session skill keep a game's history replayable.

The plan: rebuild a game from its first commit by re-running, in order, what its
builder actually ran (each commit's inputs, the committed editor steps that created its scenes and placed every
object, the shell steps that changed content outside the editor), then check the result against the game's final
commit. It produces the dataset's `ReplayScripts/` with `Verification/report.json`
([schemas/replay-report.schema.json](schemas/replay-report.schema.json)): the dataset is complete only with that report,
and its verdict, PASS or FAIL, is metadata ([game-format.md](game-format.md), "Complete vs pending"). It will read
three records, all kept today:

| Record | What it gives the replay |
|---|---|
| git history (`games\<slug>`) | the exact inputs (code, editor steps, settings, source art) at every commit, and the committed content to compare against |
| `workflow.jsonl` | what each editor step run did (rows with `source.script`, `source.sha256`, time, `status`, params such as piece counts) |
| `.recording\<slug>\actions.jsonl` | the agent's tool calls in order: every editor step run (with the command line and its output), every `Write`/`Edit` (`apply_patch` under Codex) of a file, every shell copy |

What makes that work is what sessions do today: the unity-game-session skill's "Replay-friendly work" rules. Content
will never be copied from a commit when the replay produced it, so errors accumulate visibly instead of being reset.
Every editor run of the replay will go through the limiter, headless (a general slot, never a GPU slot); the live
replay, which each game's post-commit hook will start after every commit to check the new commits at low priority
(`-Low`), will report what keeps the history from replaying at the session's next commit. Each commit will replay on
the editor its `ProjectSettings/ProjectVersion.txt` names.

## Dataset packager

`python tools/package-dataset.py <slug>` builds a game's dataset in layout `unity-dataset-layout/v1`
([game-format.md](game-format.md), [dataset-layout-v1.json](dataset-layout-v1.json), manifest
[schemas/dataset-manifest.schema.json](schemas/dataset-manifest.schema.json)). It is the first version: it packs
everything except `Gameplay/` and `ReplayScripts/`, which wait for the recorder and the creation replay above. Every
dataset it makes therefore has status `pending`, lists both in `pending`, and is written as
`<repo>\Dataset.pending.zip`; a complete `Dataset.zip` still needs the recording pipeline and the creation replay.
Nobody assembles a dataset or `Dataset.zip` by hand, and before the packager's first run on a game its `Dataset/` stays
as the template made it and `tools/validate-game.py`'s "not packaged yet" warning is expected.

It reads three things: the game repo `<root>\games\<slug>` at the release commit (`--repo` names a repo elsewhere,
`--commit` another commit than `HEAD`), the game's recording `<root>\.recording\<slug>\` (`--recording`) and its player
build `<repo>\Build\Windows`, made with `Scripts\unity.ps1 build` (`--build` names another folder). Run it once the game
has its tasks and a player build: without a build, a brief, a design doc or a task it refuses before it writes
anything, and `--dry-run` prints what would go in and what is missing. What it packs:

| Entry | What goes in |
|---|---|
| `History/<slug>.bundle` | the history rewritten for delivery: authors and committers `dev_NN`, agent trailer lines dropped, the scrub rules on every message and text blob. It holds the release commit as `refs/heads/main` and each task's start branch as `refs/heads/starts/<task>`, nothing else |
| `History/lfs/objects/` | every Git LFS object of every commit of the bundle, from the repo's own store |
| `History/sessions/` | the creation sessions as recorded: `messages.jsonl` (every prompt the person typed and every reply the model wrote) and `actions.jsonl` (every tool call), rows up to the release commit, without the sessions that packaged and those named with `--exclude-sessions`, each session named `session_NN` in both files. `manifest.json` counts the rows in `history.sessions` |
| `git.log` | every commit of the delivered history up to the release, oldest first, with full diffs |
| `workflow.jsonl` | the creation record at the release commit |
| `UnityProject/` | the delivered tree at the release commit, LFS files as their real content, without `Dataset/` |
| `Tasks/` | the tasks of the repo's tasks branch (`--tasks-ref` names another ref), seeds mapped to the delivered history, each split into `task.json` and `grader.json` by the rule of `tools/split-tasks.py`, plus `README.md` |
| `Brief/` | `brief.md` and `design.md`: the files given with `--brief` and `--design`, else the game repo's `Brief/<kind>.md` or `Docs/<Kind>.md`, else this repo's `docs/briefs/original/game-<slug>.md`, then `docs/briefs/games/<slug>.md`, for the brief and `docs/games/<slug>.md` for the design doc |
| `Screenshots/` | the images the game's `README.md` shows |
| `Build/` | the Windows player, without `.pdb` files and Unity's "DoNotShip" and "BackUpThisFolder" folders |
| `README.md`, `manifest.json` | written by the packager (`--version` gives the release version) |

Every text file of the delivery is scrubbed (the studio and tool names, agent, model and provider names, the account
and machine name, e-mail addresses, git identities, the build machine's session folders and ids) and then scanned: a
name left in a text file or a path refuses the package (exit 2, nothing zipped; the hits are in
`<repo>\.dataset\<slug>.refused-hits.tsv`). Binary files are never changed: names found in them are listed in
`<repo>\.dataset\<slug>.binary-hits.tsv` and refuse the package only with `--strict-binaries`. Commit ids change with
the rewrite: the delivery uses the new ids everywhere, and `<repo>\.dataset\<slug>.commit-map.tsv` keeps original ->
delivered.

It ends with the checks a consumer runs: the dataset checks of `tools/validate-game.py` and, where PowerShell is
installed, `tools/validate-dataset.ps1`. An error refuses the package. Then it writes the zip (`--no-zip` stops after
the checks) and, unless `--no-repo-dataset`, the repo's `Dataset/` folder (`README.md`, `git.log`, `workflow.jsonl`,
`Brief/`, `Screenshots/`, `manifest.json`), which the game session then commits. It never commits and never changes the
game repo's history. Its scratch and reports are in `<repo>\.dataset\` (git-ignored); `--out` puts them and the zip in
another folder. It refuses a drive with less than `min_free_gb` free (env `UGF_MIN_FREE_GB`, default 50). Standard
library Python 3.10+, `git` and `git-lfs`; its tests are `tools/tests/test_package_dataset.py`.

## Names that must not reach the games

User's rule: the names **Superposition**, **game-factory** and **unity-game-factory** (case-insensitive, incl.
`game_factory`/`gamefactory`) must not appear in a game (repo files, code, commit messages, builds, logs, in-game files,
anything passed to the game process), and agent, model and provider names stay out too (unity-game-session skill,
"Names"). Recording/workflow traces are fine and `workflow.jsonl` stays in the game repos. Today
`templates/new-game.ps1` refuses the names in what it writes and `tools/validate-game.py` checks a repo's tracked text
for them and for the account name.

- The flags the recorder will pass to the game (autoplay-contract.md section 1) and the paths under
  `%UGF_ROOT%\recordings\` and `builds\` contain none of the names.
- The pipeline's own files (`.recording\*.jsonl`, bundle `metadata.json`, docs) may name things freely.
