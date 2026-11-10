# Unity editor, build and recording pipeline

How heavy Unity work runs on the shared machine, and the pipeline that builds a game's Windows release player from a
commit, records AutoPlay runs of it (an in-game bot playing through the Input System, see
[autoplay-contract.md](autoplay-contract.md)) as gameplay bundles ([Bundle](#bundle)) and queues this per game; then
the plan for the creation replay, and the dataset packager. The pipeline's scripts are `tools/unity-pipeline/`
(Windows PowerShell 5.1).

> **Not available yet: the creation replay.** Its section is the plan, with the rules earlier failures taught; nothing
> in it can be run today, and the replay-friendly rules of the unity-game-session skill keep a game's history ready for
> it. Every dataset is pending, without `Gameplay/` and `ReplayScripts/`, and nobody assembles a dataset by hand. What
> runs today: a game's `Scripts/unity.ps1`, the machine-wide job limiter, the recording pipeline below and the dataset
> packager ([Dataset packager](#dataset-packager)). A game is recorded once it has the AutoPlay drop-in and its own
> scenario wiring and bot ([autoplay-contract.md](autoplay-contract.md)); only the coordinator queues recordings
> ([Queue](#queue)). The task checker's own builds and plays (a scratch copy's player, started on a Windows desktop of
> its own) are in [task-check.md](task-check.md).

| Script | Does |
|---|---|
| `build.ps1 <game> [-Commit rev] [-Backend il2cpp\|mono] [-Force]` | the Windows release player of a commit, from a private clone; row in `builds.jsonl` |
| `record.ps1 <game> -Build <dir\|latest> [-Scenario n] [-Runs k] [-Skill s] [-Seed s] [-MaxSeconds n]` | launch, capture, validate, bundle; a row per run in `runs.jsonl` |
| `pipeline.ps1 <game> [-Runs k] [-Scenarios 1,2] [-Commit rev] [-MaxSeconds "1=300,3=900"] [-Backend mono]` | release build, then k recorded runs per scenario; row in `pipeline.jsonl` |
| `pipeline.ps1 -DrainQueue` | the requests `enqueue.ps1` wrote, one at a time |
| `enqueue.ps1 <game> -RequestedBy coordinator [-Runs k] [-Scenarios ..] [-MaxSeconds ..] [-Backend mono]` | queue a pipeline run and return at once (the coordinator's tool) |
| `validate-run.ps1 <outputDir>` | contract check of one run's files, no video (for game sessions testing by hand) |
| `mark-invalid.ps1 <game> -Commit sha \| -RunId id -Reason text` | exclude bundles from the dataset (INVALID file, validation status `invalid`); files kept |
| `leak-scan.ps1 <dir> [-Patterns ..]` | byte search (ASCII + UTF-16) for the user name or other strings that must not ship |
| `gameplay-mp4.ps1 <game> [-Commit sha..] [-RunId id] [-Force]` | a run's `gameplay.mp4` again (updates metadata/manifest) |
| `stills.ps1 <game> [-RunId id] [-Count n] [-Force]` | a run's README stills again (updates metadata/manifest) |
| `sync-check.ps1 <bundle>` | measures video/audio lag against sync markers that a pipeline test game emits |
| `autoplay/` | the AutoPlay drop-in every game copies unchanged; `autoplay/install.ps1 -Game <game>` installs or updates it in a game ([autoplay-contract.md](autoplay-contract.md)) |

## Paths

`%UGF_ROOT%` is the machine root: env `UGF_ROOT`, else `root` in `%USERPROFILE%\.unity-game-factory\config.json`
(written by `machine/bootstrap.ps1`), else `%USERPROFILE%\UnityWork`; `machine/lib/ugf-root.ps1` resolves it, and the
same file gives each project's editor: exactly the version its `ProjectSettings/ProjectVersion.txt` names
(`Get-UGFUnity`; Unity Hub's folder `C:\Program Files\Unity\Hub\Editor\<version>\Editor\Unity.exe`, config
`unity_hub_editors`, or `unity_editors` for an editor installed elsewhere) and `ugb` (default `C:\UGB`: the release
builds' private clones and their temp folder, outside the user profile). See
[../machine/README.md](../machine/README.md).

```
%UGF_ROOT%\
  games\<slug>\                     the game repos (<org>/unity-game-<slug>; read only for the pipeline)
  games\<slug>\Logs\unity-ps1\      a game's own run logs (Scripts/unity.ps1; Unity's Logs/ folder, git-ignored)
  tasks\<slug>\                     a game's orphan tasks branch, checked out as a worktree
  tools\unity-heavy.ps1             the job limiter (+ ugf-root.ps1 beside it); its log .recording\_heavy-jobs.jsonl
  tools\ffmpeg-8.1.2\               the pinned ffmpeg (machine/get-ffmpeg.ps1)
  builds\<slug>\<short-sha>\        release build: Windows\<Project>.exe, build_info.json, logs\
  builds\<slug>\_run\               the copy the recorder launches (a fixed path per game)
  builds\_pipeline-<slug>.lock      per-game build/record lock (holder in the .json beside it)
  builds\_queue\                    queued requests; done\ has results
  builds\_logs\                     transcripts of queue runs
  recordings\<slug>\<run-id>\       bundles
  recordings\<slug>\_stills\        every bundle's stills, <run-id>_NN.jpg
  .recording\<slug>\actions.jsonl   the recording hooks' rows (machine/README.md); the pipeline never touches them
  .recording\<slug>\messages.jsonl  the same hooks' rows for every prompt and every reply of a session
  .recording\<slug>\commits.jsonl   one row per commit (the post-commit hook)
  .recording\<slug>\builds.jsonl    one row per build.ps1 run
  .recording\<slug>\runs.jsonl      one row per recorded run
  .recording\<slug>\pipeline.jsonl  one row per pipeline run per game
  deliverables\                     packages and replay packages (config "out", env UGF_OUT)
<ugb>\src\<slug>\                   private clone the pipeline builds from (never the game's working copy); outside
                                    C:\Users so the user name isn't compiled into the player
<ugb>\tmp\                          TEMP and TMP of the build
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
| `autoplay [-Scenario <n>] [-MaxSeconds 120] [-Seed 0] [-Skill 1] [-Audible] [-Extra "..."]` | the built player as a recording runs it (the AutoPlay drop-in): the bot plays scenario n for at most `-MaxSeconds`, starting at once, on a Windows desktop of its own (nothing on the screen; muted unless `-Audible`); the run's files go to `Logs/autoplay/<time>_s<n>/`, which `tools/unity-pipeline/validate-run.ps1 <folder>` checks | yes |

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

`build.ps1` and `record.ps1` take an exclusive per-game lock on `builds\_pipeline-<slug>.lock` (an open file handle:
released by the OS if the process dies, visible across sessions and Task Scheduler) for the whole build or the whole
run, and wait for it otherwise (the holder is printed): a build and a recording of the same game share its clone, build
folder and `_run` copy. Different games only share the machine, which the general and GPU slots below ration, so a
rebuild of one game can run while another game records (watch the recording's fps warnings). Builds run at
below-normal priority so the game sessions' own editors stay responsive; the game and ffmpeg run at above-normal
priority during a recording.

### Machine-wide slots

Every heavy job of every session goes through one limiter, `<root>\tools\unity-heavy.ps1` (rows in
`.recording\_heavy-jobs.jsonl`): `& <root>\tools\unity-heavy.ps1 -Label "<slug> <what>" [-Gpu] [-Low] -- <exe> <args>`.
It returns the job's exit code, or 125 when it could not run the job itself (called wrongly, `ugf-root.ps1` missing
beside it, a machine config that is not JSON, an exe that would not start): Unity itself exits 2 for failed tests, so
the limiter's own failures have a code no job uses.
From Git Bash, wrap it in `powershell -ExecutionPolicy Bypass -Command "& '<path>' ... ; exit \$LASTEXITCODE"`
(`powershell -File ... --` misparses `--`; without `-ExecutionPolicy Bypass` Windows' default policy refuses the
script, and with the dollar sign unescaped bash expands `$LASTEXITCODE` to nothing: either way the call returns 0
whatever the job did). `build.ps1` runs its editor through this checkout's copy of the limiter
(`machine/tools/unity-heavy.ps1`, the same slots), so the pipeline and the limiter are always the same version.

Each slot is a named mutex (`machine/lib/ugf-root.ps1` `Get-UGFSlotMutexes`, `Enter-UGFSlot`). A job that is killed
before it releases its slot (a cancelled tool call, a killed editor) leaves the mutex abandoned, and the next job takes
it over, so no slot leaks (a counted semaphore would lose one slot per killed holder until someone released it by
hand). The counts are read from the config at every call, so a new `heavy_slots` / `gpu_slots`
applies at once.

| Slots | Named mutexes | Taken by | Count |
|---|---|---|---|
| general | `Global\ue-heavy-slot-<n>` | every job: batchmode editor runs, player builds, tests, players, and GPU jobs too | config `heavy_slots`, else the formula |
| GPU | `Global\ue-gpu-slot-<n>` | jobs that render (`Unity.exe` without `-nographics`, a player under a `Build`, `Builds` or `Packaged` folder or started with `-screen-*` / `-popupwindow`, anything run with `-Gpu`; `-nographics` in a command means no GPU slot, even with `-Gpu`), together with a general slot: a GPU job never holds one while waiting for the other; a recording takes all of them | config `gpu_slots`, else the formula |

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
- **Recordings have priority:** while a recorder waits for the GPU (`record.ps1`, a run) it keeps
  `builds\_queue\_recording-wants-gpu` fresh in its factory's root (rewritten every minute, removed once it holds the
  slots and in `finally`); `unity-heavy.ps1` holds back new GPU jobs while that file exists in either factory's root and
  is under 20 min old. A recording then takes every GPU slot (`common.ps1` `Enter-GpuSlot -Recording`), so a capture
  has the GPU to itself. The queue drainer holds the same flag for each whole job (from its first build step to the
  end of its last run, and across the gap to the next job; a timer rewrites it every 60 s) and removes it when the
  queue is empty. Before launching, `record.ps1` also waits while more than `-MaxVramInUseMB` (default 4096; 0 = half
  the GPU's VRAM) MB of VRAM is in use (nvidia-smi total; per-process numbers are N/A under WDDM), logging the
  GPU-heavy processes every 5 min; after 120 min the run fails. If the user returns while it waits for the slots, it
  gives them back and waits for idle again. Its waits, starts and ends go to `.recording\_heavy-jobs.jsonl` with
  `gpu: true`, like the limiter's.
- **`-Low`** (background work, such as the live creation replay will be): one low job machine-wide; it takes a general
  slot only while no other job waits for one and another slot stays free, at below-normal priority.

`machine/check.ps1` shows the slots in effect and where each comes from.

## Recording pipeline

### Build

`build.ps1 <game> [-Commit rev] [-Backend il2cpp|mono] [-Force]`:

1. Resolve `-Commit` (default `HEAD`) in the game repo; output goes to `builds\<slug>\<first 8 of sha>\`. A build that
   already succeeded for that sha (and backend, when one is asked) is reused unless `-Force`; a rebuild deletes the old
   `build_info.json` first, so a failed one never leaves an "ok" next to a player that is gone.
2. Source: `git clone --local --no-checkout` of the game repo into `<ugb>\src\<slug>` once (`--no-hardlinks` when the
   two are on different drives), then `fetch` + `checkout --force <sha>` + `clean -ffd` (its `Library\` is kept by
   name, whatever the game's `.gitignore` at that commit says, so later builds import only what changed). LFS files are
   checked out as pointers (`GIT_LFS_SKIP_SMUDGE=1`) and copied (never hard-linked: an import that rewrote a file in the
   clone would change the game's object) from the game repo's own store (`lfs.storage`, else `.git\lfs\objects`), so
   nothing is downloaded and the game repo is only read; an object missing from the store fails the build and names
   the `git lfs fetch` to run. Uncommitted work is not built.
3. The player as the commit builds it: the game's own `Assets/Editor/Tools/BuildPlayer.cs` names the method
   (`<Project>.EditorTools.BuildPlayer.BuildWindows`) and the exe (`<Project>.exe`), and the editor is the one its
   `ProjectSettings/ProjectVersion.txt` names (`Get-UGFUnity`; not installed: the build fails and says which).
   `Unity.exe -batchmode -nographics -quit -logFile <logs>\<stamp>-player.log -projectPath <clone> -executeMethod
   <method> -buildOut builds\<slug>\<sha8>\Windows [-backend il2cpp|mono]` runs through the limiter, at below-normal
   priority, with `TEMP` and `TMP` in `<ugb>\tmp`: the release player, IL2CPP unless `-Backend mono` (a machine
   without IL2CPP's C++ tools). The `Windows\` folder is fresh every time (Unity refuses to build IL2CPP over a Mono
   build in one folder). An editor that stops with no word about the game (no `error CS` line, no failed `build.player`
   row) is tried once more, as `player-retry`, the first attempt staying in `steps[]` marked `retried` (an IL post
   processor exited 1 without a message once, and the same commit built on a rerun); a missing licence (exit 198) is
   never retried. What `BuildPlayer` did comes from the `build.player` row it writes to the clone's `workflow.jsonl`
   (backend, bytes); the next checkout drops that row.
4. Leak scan of the build folder (`Windows\`): a case-insensitive byte search (ASCII and UTF-16LE) for the Windows user
   name inside paths (`\<name>\`, `/<name>/`) and for superposition / game-factory / game_factory / gamefactory /
   game factory / claude / anthropic / openai (`$ForbiddenNamePatterns` in `common.ps1`), one read per file; hits are
   warned about and recorded in `leak_scan` (a build with hits can still be recorded but must not be handed out).
   `leak-scan.ps1 <dir>` runs the same scan by hand. The clone sits under `<ugb>` because a player carries the folder
   it was built in: measured on a template game's IL2CPP build, `GameAssembly.dll` names the clone's path once and
   Unity's `*_BurstDebugInformation_DoNotShip` and `*_BackUpThisFolder_ButDontShipItWithYourGame` folders thousands of
   times, so a clone under `C:\Users\<name>` ships the user name.
5. The AutoPlay drop-in's version (the `Version` constant of the game's `AutoPlay.cs`, null without one) goes into the
   row: `record.ps1` refuses a build without it.

`builds.jsonl` row and `build_info.json` (next to the player, written only for an ok build; schema `unity-build/1`):
`game`, `project`, `commit`, `short_sha`, `requested`, `commit_subject`, `commit_time`, `command`,
`start`/`end`/`duration_s`, `status`, `exit_code`, `error_excerpt` (first matching error lines of the failing log),
`log_path`, `output_path`, `exe_path`, `config` (`release`), `backend`, `player_bytes`, `autoplay_version`,
`leak_scan {scanned, hits[] {file, pattern, count, example}}`, `unity_version`, `editor`, and `steps[]` (each with its
exact command line, times, exit code, log, and `retried` for a first attempt that was tried again).

Measured on this machine's 16 GB laptop beside other sessions' editors: the first IL2CPP build of a template game with
one scene, from a fresh clone (a full import), took 614 s, a later commit's build in the same clone 184 s; the leak
scan of a 1.2 GB `Windows\` takes 20 to 70 s.

### Record

`record.ps1 <game> -Build <dir|latest> [-Scenario n] [-Runs k] [-Skill s] [-Seed s] [-MaxSeconds n]` (also `-Capture`,
`-IdleMinutes`, `-MaxVramInUseMB`, `-ExtraArgs`, `-OutputFps 30|60`, `-CaptureNote`, `-NoStablePath`). Before the runs,
the build is mirrored (robocopy /MIR) into a stable `builds\<slug>\_run\` and launched from there: Windows Firewall asks
once per program path for a program that listens on the network, and a fixed path per game means one prompt per game
instead of one per build. A release player opens no socket (measured: no TCP or UDP endpoint), so a release build never
prompts and needs no Firewall pre-flight. Per run (seed = `-Seed + i`, or random; skill = `-Skill`, or cycling 1.0 /
0.75 / 0.5 / 0.25):

0. **Wait until the user is away** (default; the user's standing instruction overrides it, see below): no
   keyboard/mouse input for `-IdleMinutes` (default 5; `GetLastInputInfo`; the bot's Input System events don't count)
   and the session unlocked. From the start of that wait until the run ends the display is kept on
   (`SetThreadExecutionState`, like a video player; no settings change). Right before launch the display is also
   **woken** (a 1-pixel mouse move out and back, outside the game run): the display timeout can equal the idle gate,
   so when the user went away during a build the display is already off, `SetThreadExecutionState` doesn't turn it
   back on, and Desktop Duplication delivers no frames (ddagrab hangs, gdigrab gets ~4 fps). The wake counts as input,
   so the next run's idle wait starts from it. An unanswered Windows Firewall prompt dims the whole screen and blocks
   capture until it is answered. **Idle override:** `builds\_queue\_idle-override.txt` (JSON `{idle_minutes, reason}`,
   written by the coordinator) replaces the default when `-IdleMinutes` isn't given; `idle_minutes` 0 = record right
   away. It is standing (the user's "record now" instruction) unless it has `"one_drain": true`, which the drainer
   retires when the queue empties. The privacy guard and the display wake apply either way.
1. Launch `_run\Windows\<Project>.exe` with the contract's flags (autoplay-contract.md section 1): `-autoplay
   -scenario <n> -seed <s> -skill <s> -outputDir <bundle>\raw -maxSeconds <n> -buildCommit <sha> -runId <id>
   -goTimeout 300 -screen-fullscreen 0 -screen-width 1920 -screen-height 1080 -logFile <bundle>\raw\game.log`, plus
   `-ExtraArgs` (the drop-in's `-autoplayQuality <level>`, `-autoplayMute`). Background Unity work (batchmode editors,
   shader compilers, the build backend, IL2CPP) is lowered to below-normal for the run and put back after it. A Unity
   player saves the `-screen-*` window as its own setting before any script runs (the `Screenmanager` values under
   `HKCU\Software\<company>\<product>`), so after a recording that game's player starts 1920x1080 windowed, as it does
   after `Scripts/unity.ps1 play -Render` at 1280x720; the recorder leaves the setting so (every start with `-screen-*`
   flags overrides it), and a start with `-screen-fullscreen 1` puts a full-screen window back.
2. Wait for `ready.json`, find the window by PID (class `UnityWndClass`, titled with the product name), centre its
   client area on the primary screen (on a 1920x1200 display at (0, 60)), make it topmost (not activated), check the
   client area is exactly 1920x1080 and fully on screen (physical pixels; the recorder is per-monitor DPI aware, and so
   is a Unity player: measured at 125 % scaling, its client was 1920x1080 physical pixels). If anything covers it (e.g.
   a Firewall prompt), wait up to 240 s for it to clear.
3. Start ffmpeg on that screen rectangle, wait for 30 captured frames, write `go`. Each capture attempt has its own
   files (`video.<mode>.mkv`, `raw\ffmpeg-<mode>.log`, `raw\ffmpeg_progress-<mode>.txt`); a failed attempt is kept as
   `raw\failed-attempt-<mode>.mkv`.
4. Watch every 100 ms until `outcome.json` appears. **Privacy guard:** if the window moves, or another window covers
   its client area for â‰¥ 0.3 s (5x5 point test with `WindowFromPoint`; shorter blips are tooltips/ghost windows),
   ffmpeg is stopped at once, the game killed, the run failed, and the video cut to 0.5 s before the first sighting
   (`-c copy -t`). The problem names the covering window; moves are logged in `raw\window.jsonl` with whether a mouse
   button was held (user drag). A client-size change or a minimized window also fails the run, and so does a game
   that exits before writing `outcome.json` (its video is cut 0.5 s before that was seen, like the guard's). **Stop
   ffmpeg, then let the window close:** ffmpeg is stopped as soon as `outcome.json` is there, then the game is given
   60 s to quit (the drop-in ends its process at once after `outcome.json` and `clock.json`, with no engine shutdown,
   but that took up to 16 s beside a compiling editor); it is killed after `-MaxSeconds + 90 s`. The window is gone
   before ffmpeg has stopped, and a window that closes fades out over about 117 ms (measured: a run's last 7 frames
   showed one fading into what was behind it), so every normal run's video ends at the game's own `end` clock sample,
   which the drop-in takes before it ends: nothing behind the window reaches the video.
5. Validate and write the bundle (below), even for failed runs.

### Capture

ffmpeg: pinned to gyan.dev `ffmpeg-8.1.2-full_build.7z` in `%UGF_ROOT%\tools\ffmpeg-8.1.2\ffmpeg-8.1.2-full_build\bin\`,
SHA-256 `0fff188997a499b5382e0f66e845d4556c48c54f0113ebed4853d556dbdd7059` (`machine/get-ffmpeg.ps1` fetches and
verifies it; env `UGF_FFMPEG` overrides it; without either, an ffmpeg on PATH or the winget `Gyan.FFmpeg` package is
used). Desktop Duplication (`ddagrab`) of the window's client rectangle, **event-driven**, no mouse cursor, converted
to 60 fps CFR. With NVENC (needs NVIDIA driver â‰¥ 610) the D3D11 frames go straight to the encoder:

```
ffmpeg -hide_banner -loglevel +datetime+level+info -stats_period 1 -progress <raw>\ffmpeg_progress-ddagrab.txt -y
  -f lavfi -i "ddagrab=output_idx=0:framerate=240:dup_frames=0:offset_x=<x>:offset_y=<y>:video_size=1920x1080:draw_mouse=0,showinfo"
  -c:v h264_nvenc -preset p5 -tune hq -rc vbr -cq 19 -b:v 0 -maxrate 60M -bufsize 120M -g 120 -bf 0
  -color_primaries bt709 -color_trc bt709 -colorspace bt709 -color_range tv -fps_mode cfr -r 60 -an <bundle>\video.ddagrab.mkv
```

Why `framerate=240:dup_frames=0` and not `framerate=60`: ddagrab paces itself with `av_usleep`, which on Windows is
`Sleep()` at the default 15.6 ms timer resolution (since Windows 10 2004 a process only gets 1 ms if it asks for it
itself, and ffmpeg doesn't). At `framerate=60` that produced frames at 15.6/31 ms intervals, 57 fps, 5â€“7 % CFR
duplicates. With `dup_frames=0` and a rate above the display's, the pacing loop never sleeps and ddagrab waits inside
`AcquireNextFrame` for each new desktop image (timestamped when acquired); `-fps_mode cfr -r 60` then keeps the latest
image per 1/60 s slot. ffmpeg's `drop=` count is just these surplus samples; `dup=` counts slots without a new image.

**Encoder.** `record.ps1` probes at start and uses the first that opens: `h264_nvenc` (NVIDIA), `h264_amf` (AMD,
e.g. a CPU's integrated Radeon), `libx264` (CPU); `metadata.video.encoder` says which. The pinned ffmpeg 8.1.2 needs
NVENC API 13.1, i.e. NVIDIA driver â‰¥ 610; with an older driver it fails ("Required: 13.1 Found: 13.0") and recordings
use AMF. `h264_mf` does not work. AMF and libx264 take system-memory frames, so `fps=60` picks the 60 fps grid on the
GPU frames first and only those are downloaded and converted (BT.709 matrix, limited range):

```
  -f lavfi -i "ddagrab=output_idx=0:framerate=240:dup_frames=0:offset_x=<x>:offset_y=<y>:video_size=1920x1080:draw_mouse=0,showinfo,fps=60,hwdownload,format=bgra,scale=out_color_matrix=bt709:out_range=tv,format=nv12"
  -c:v h264_amf -quality quality -rc cqp -qp_i 18 -qp_p 20 -g 120 -bf 0
```

The libx264 variant is the same with `format=yuv420p` and `-c:v libx264 -preset ultrafast -crf 17 -g 120 -bf 0
-pix_fmt yuv420p` (`veryfast` only reached 0.977x on a shared CPU). Fallbacks (`-Capture`), as measured
on earlier games: `gdigrab-region` captures real content but only ~44 fps (24 % duplicates), `gdigrab-window` ~56 fps (8 %
duplicates, 23 % gap time); both fail validation, so they are for emergencies. `auto` tries ddagrab, then (after waking
the display) ddagrab once more, then gfxcapture, and gdigrab-region last, each only if the one before got fewer than 30
frames in 10 s; each failed attempt is logged with its frame count, whether ffmpeg hung or exited (exit code) and the
tail of its log. `gfxcapture` (Windows.Graphics.Capture of the game window by `hwnd`, ffmpeg 8's `gfxcapture` filter,
max 120 fps, then the same `fps=60` CFR + NVENC path) records only the game window, so other windows never reach the
video and the privacy guard does not apply; the window is still made topmost and brought to the foreground (a
synthetic Alt tap lifts the foreground lock). It needs no live display (a PC reached over remote desktop whose monitor
is off); its showinfo pts are in 1/10^7 s, not Âµs: `record.ps1` reads the unit from showinfo's `config in time_base`
line (misread, it looked like 2â€“6 frames/s and broke the start estimate). If the game window stays covered for 240 s
before capture, `auto` skips the screen-region modes and uses gfxcapture.

Display: run it at a multiple of 60 Hz (e.g. 120 Hz) for recording sessions; with vsync off the game's frames reach the
screen on the display's refresh grid, and a 60 Hz capture repeats some and misses some otherwise (measured
on earlier games: 13 % at 159 Hz, 7 % at 120 Hz on the AMF path, 0.3â€“1.1 % with NVENC). The recorder logs
`machine.display_refresh_hz` and warns (does not fail) when the rate is not a multiple of 60; `machine/check.ps1` checks
it too.

### Measured

On this machine (RTX 5060 Laptop, driver 617, NVENC; one 1920x1200 display at 125 % scaling and 144 Hz), a template
game's IL2CPP release player (Direct3D 12) with the AutoPlay drop-in, its bot and sync markers (`sync-check.ps1`),
recorded from the queue:

| | Result |
|---|---|
| Output | 1920x1080 H.264 Main yuv420p, 60/1 CFR, 0.59 % duplicated slots, duration within 8 ms of the span to the cut; the game at 59.95 fps |
| Capture input | 60 desktop images/s during the scenario; gaps > 25 ms 0.08 % of frames |
| Video lag | a game event shows on video 7.8 ms (âˆ’2.3â€“12.8) after its `t_ns` (the frame's slot on the 60 fps grid, so within a frame either way): game â†’ present â†’ DWM â†’ capture. `video_start_offset_ns` is the capture clock and does **not** subtract this. With `gfxcapture` a window's frames came 23 ms after its events |
| Game frame cadence | frame-code strip over 1202 frames: 0 repeated, 0 skipped game frames, at 144 Hz |
| Audio | 1033 buffers, no stall, 15 ms at most from the median anchor; a sound sits 10 ms (4â€“30 ms) before its `t_ns` in `system_audio`, since the drop-in stamps a buffer with its arrival less its length, so in `gameplay.mp4` the sound leads the picture by about 18 ms |

### Bundle

```
recordings\<slug>\<slug>_S<scenario>_<yyyyMMdd-HHmmss>_s<seed>\
  video.mkv           H.264 1920x1080 60 fps CFR, no audio, BT.709 tags
  system_audio.mka    FLAC from the game's audio.wav, aligned with audio_clock.jsonl
  inputs.jsonl        as written by the game (autoplay-contract.md section 5)
  telemetry.jsonl     as written by the game
  outcome.json        as written by the game
  metadata.json       schema unity-autoplay-bundle/v1: game, scenario, scenario_name, seed, skill, result, score, build
                      {commit, short_sha, config, backend, unity_version, path, exe, autoplay_version}, ffmpeg command +
                      version, encoder, capture mode and rect, video_start_offset_ns (+ estimate details), video.cut
                      (where the video was cut and why), system_audio {start_offset_ns, aligned, clock, stats}, clock
                      samples (game: start/go/audio_start/audio_stop/end; pipeline: record_start, capture_start_<mode>,
                      go_written, capture_stopped, record_end), machine (cpu, gpu, display, display_refresh_hz),
                      capture_notes, stills, gameplay_mp4, status
  validation.json     status ok | warn | failed, problems, warnings, per-check details (below)
  manifest.json       schema manifest/v1: sha256 + bytes of every file in the bundle (incl. raw\ and stills\)
  stills\NN.jpg       8 evenly spaced frames (t = duration * i / 9) for README screenshots, runs with status ok / warn
                      only; CPU decode with the pinned ffmpeg (-ss before -i, -frames:v 1, -q:v 2); also copied to
                      recordings\<slug>\_stills\<run_id>_NN.jpg; metadata.json `stills` lists them. A failed extraction
                      is logged and recorded in `stills.error`; it never changes the run's status.
  gameplay.mp4        the dataset's Gameplay/ file (packaged as <slug>_S<n>.mp4), runs with status ok / warn only:
                      video.mkv's H.264 stream copied (1080p60, no re-encode) + system_audio.mka as AAC 192k stereo,
                      aligned on the QPC clock: offset = system_audio.start_offset_ns (the median over
                      audio_clock.jsonl's rows of t_ns - frame / rate: its first buffers come in a burst)
                      âˆ’ video_start_offset_ns, applied with adelay (audio later) or atrim (earlier), then apad +
                      -shortest to the video's end; +faststart. CPU only, below-normal priority. Checked with ffprobe
                      (h264 + aac, duration within 0.5 s of video.mkv). metadata.json `gameplay_mp4` {audio_offset_s,
                      duration_s, bytes, error}; a failure is logged there and never changes the run's status.
  FAILED              only on failed runs (problems listed); failed runs are kept, never deleted
  INVALID             excluded from the dataset after the fact (reason inside), e.g. recorded from a broken build;
                      written by mark-invalid.ps1, which also sets validation.json status "invalid" and adds a
                      runs.jsonl row; files kept
  raw\                the game's outputDir: audio.wav, audio_clock.jsonl, clock.json, ready.json, go, game.log,
                      watchdog.json (when its watchdog fired), window.jsonl (moves), ffmpeg-<mode>.log,
                      ffmpeg_progress-<mode>.txt
```

`video.mkv` is H.264, 60 fps, no audio; `inputs.jsonl` has ns QPC timestamps; there is no microphone track (a bot has
no voice). `runs.jsonl` row (schema `unity-run/v1`): `run_id`, `game`, `scenario`, `scenario_name`, `seed`, `skill`,
`build_commit`, `build_path`, `status`, `result`, `score`, `duration_s`, `start`/`end`/`wall_s`, `capture`,
`video_start_offset_ns`, `dup_pct`, `problems`, `warnings`, `bundle`; `mark-invalid.ps1` adds `{event: "invalidated",
run_id, time, reason, status_before, bundle}` rows.

### Validation (per run)

| Check | Fails when | Warns when |
|---|---|---|
| outcome | missing, bad `result`, `go_timed_out` | result `abort` |
| inputs | no `inject` rows, unparseable lines, `t_ns` going backwards | |
| telemetry | missing `run_start`/`scenario_start`/`scenario_end`/`run_end`, unparseable lines | |
| audio | missing, or not aligned: `audio_clock.jsonl` drift over 250 ms or a WAV whose length differs from the span its rows cover by more than 0.25 s (without `audio_clock.jsonl`: anchored at the `audio_stop` sample, start lag outside âˆ’30â€¦10000 ms) | silent (max < âˆ’60 dB), stalls filled with silence |
| video | not 1920x1080, no frames, ffmpeg dup > 5 % of output frames, video longer than the capture span by â‰¥ 0.5 s or shorter by â‰¥ 2 s, doesn't cover the scenario (start..end), start time not estimable | dup > 1 %, capture gaps > 2 % of scenario frames, game < 55 fps (`frames` / `duration_s` of outcome.json), video ends 0.5â€“2 s early, display not a multiple of 60 Hz |
| process | game exit code â‰  0, killed at timeout, window moved, covered or minimized, game gone before `outcome.json`, ffmpeg died | |
| watchdog | `watchdog.json` with `reason` `run` | `watchdog.json` with `reason` `shutdown` after a complete run |

`validate-run.ps1 <outputDir>` checks the same files of a run made by hand (no video): every row stamped with `t_ns`,
`qpc` and `frame`, the inject rows, the four telemetry events (a note when `score` or `state` events are missing), the
outcome, the five clock samples, `audio.wav` (a note when it is silent) and `audio_clock.jsonl`'s drift; it prints PASS
or FAIL with the problems and notes and exits 1 on FAIL.

### Queue

`pipeline.ps1 <game>` resolves the commit (default HEAD) and the scenarios (default 1..n from the newest
`milestone/autoplay-<n>` tag reachable from it, meaning "scenarios 1..n are ready"), skips scenarios that already have
`-Runs` good runs (status `ok`/`warn`, not invalidated) of that commit unless `-Force`, then runs `build.ps1` and
`record.ps1` per scenario. Each step takes the lock itself, so other work can interleave between steps. `-Runs`
defaults to 1: one recorded run per scenario is enough (AGENTS.md, "Priorities").

**Queueing (the coordinator owns the queue).** Game sessions never enqueue; they send the coordinator what is ready
(commit sha, tag, scenarios, `validate-run.ps1` result, screenshot paths). `enqueue.ps1` refuses (exit 2, red message,
nothing queued) unless `-RequestedBy coordinator`; `-Force` overrides and the request still records its
`requested_by`. It pins the commit and checks `-MaxSeconds` before it writes, returns at once, and starts the one
hidden drainer (`pipeline.ps1 -DrainQueue`, transcript in `builds\_logs\queue-<time>.log`), which works through
`builds\_queue\*.json` in file-name order (the coordinator reorders by renaming; a request being processed must not be
renamed):

```
powershell -ExecutionPolicy Bypass -File %UGF_ROOT%\unity-game-factory\tools\unity-pipeline\enqueue.ps1 <game> -Scenarios 1,2 -RequestedBy coordinator
```

`builds\_queue\_paused.txt` (e.g. "stop recording" from the user) pauses it: no job starts, requests wait, and a new
request does not start a drainer. Dropping a queued request: move it to `builds\_queue\done\` with a `result` note
(status `dropped`). The drainer re-reads `build.ps1` and `record.ps1` for every job and hands over to a fresh drainer
between jobs when `pipeline.ps1` or `common.ps1` changed.

AutoPlay time limit: 600 s per run by default (the game gets `-maxSeconds`, the recorder kills it 90 s later), per
scenario as `1=300,2=600,3=900` (unlisted ones keep 600; `*=700` changes the rest) or one value for every scenario;
values 30..7200. The request stores it as `max_seconds`, and the job's `pipeline.jsonl` row lists the limit used per
scenario. A machine without IL2CPP's C++ tools records a Mono release player: `-Backend mono` (stored as `backend`).

**A game that is GPU-bound at its default quality** (coordinator rule 2026-10-18: the GPU 3D engine above ~95 % with
the game under ~55 fps, so the capture fails on duplicated frames) is recorded one quality level lower and says so:
`record.ps1 ... -ExtraArgs "-autoplayQuality <level>" -CaptureNote "<level> quality for 60 fps capture"` (the drop-in's
flag; a level's index or name). The note goes to the run's `metadata.json` (`extra_args`, `capture_notes`), then to the
dataset's manifest (`scenarios[].capture_notes`) and a "Recording note" line under the README's Scenarios table.
Nothing else changes (no game repo edit, no bot change, same validation).

Results: `.recording\<slug>\pipeline.jsonl` (schema `unity-pipeline/v1`: commit, scenarios, the time limit per
scenario, build {status, short_sha, output, backend, autoplay_version, leak_scan_hits}, runs[] {run_id, scenario,
status, result}, status `ok` / `partial` / `failed` / `skipped`, note), `runs.jsonl`,
`builds\_queue\done\<request>.json`.
The job summary's `build.leak_scan_hits` lists the build's leak-scan hits (`[]` = clean); warn-only here, the packager
blocks on them. If the session is locked (`LogonUI` running), recording is skipped and the row says so. There is no
nightly run: runs are queued on demand (the user's decision).

### Games started before the pipeline

A game made from any version of the template is built as it is: `build.ps1` needs only the game's
`Assets/Editor/Tools/BuildPlayer.cs`, which every template game has had, with the same `-buildOut` and `-backend`
arguments, since the first template; it keeps the clone's `Library\` by name whatever the game's `.gitignore` says,
and it does not use the game's `Scripts/unity.ps1`. Recording needs the AutoPlay drop-in in the game, which
`tools/unity-pipeline/autoplay/install.ps1 -Game <root>\games\<slug>` adds (its own commit and `workflow.jsonl` row;
autoplay-contract.md), and the game's own scenario wiring and bot: a game made from an earlier template than today's
got the drop-in that way, was wired, built and recorded from the queue. Changes to `machine/` reach a machine when it
pulls this repo and runs `machine/bootstrap.ps1` again (`ugb` and its folders, the installed limiter); the pipeline's
scripts run from the checkout, so a pull is enough for them.

### Machine notes and open items

- Any display and scaling that holds a 1920x1080 window works: a Unity player is per-monitor DPI aware, so its
  1920x1080 client is physical pixels at any scaling (measured at 125 %). Vsync off and a 60 fps cap in the game
  (the drop-in sets both) keep it at 60 fps whatever the refresh.
- The game window sits topmost with its 1920x1080 client area centred on the primary screen for the run. Runs start
  only after 5 min without user input; if you come back mid-run, leave the window alone (moving or covering it stops
  the run safely). Its audio plays on the speakers during runs (`-ExtraArgs -autoplayMute` keeps them silent;
  `audio.wav` is still whole).
- **Machine-path scrub before bundles leave the machine** (an open item). Bundles
  carry machine paths and the user name: `metadata.json` (build path, exe, ffmpeg command), `raw\game.log`,
  `raw\ffmpeg-<mode>.log`, `raw\ready.json`. Per AGENTS.md (leak scan for `C:\Users\â€¦`, real names, e-mails), a
  publish step must rewrite or drop these and re-hash `manifest.json` before any upload; the dataset itself takes only
  `gameplay.mp4`.

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
"Names"). Recording/workflow traces are fine and `workflow.jsonl` stays in the game repos. `templates/new-game.ps1`
refuses the names in what it writes, `tools/validate-game.py` checks a repo's tracked text for them and for the
account name, and `build.ps1`'s leak scan checks every file of a release build for them, the account name in paths and
`openai`.

- The flags the recorder passes to the game (`-autoplay -scenario -seed -skill -outputDir -maxSeconds -buildCommit
  -runId -goTimeout`, Unity's `-screen-*` and `-logFile`, autoplay-contract.md section 1) and the paths under
  `%UGF_ROOT%\recordings\`, `builds\` and `<ugb>\` contain none of the names.
- The pipeline's own files (`.recording\*.jsonl`, `build_info.json`, bundle `metadata.json`, docs) may name things
  freely.
