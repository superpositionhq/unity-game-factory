# Unity editor, build and recording pipeline

How heavy Unity work runs on a shared machine, and the plan for the recording pipeline. The parts marked **later**
come with the recording pipeline (after the task verifier); everything else is in the repo now.

## Paths

| What | Where |
|---|---|
| machine root | `%UGF_ROOT%` (machine/README.md) |
| games | `%UGF_ROOT%\games\<slug>` (one git repo each, `<org>/unity-game-<slug>`) |
| task worktrees | `%UGF_ROOT%\tasks\<slug>` (the orphan `tasks` branch) |
| job limiter | `%UGF_ROOT%\tools\unity-heavy.ps1` (+ `ugf-root.ps1` beside it) |
| ffmpeg | `%UGF_ROOT%\tools\ffmpeg-8.1.2\ffmpeg-8.1.2-full_build\bin\ffmpeg.exe` |
| recordings, builds, deliverables | `%UGF_ROOT%\recordings\`, `builds\`, `deliverables\` (config `out`) |
| Unity editors | Unity Hub's folder (`C:\Program Files\Unity\Hub\Editor\<version>\Editor\Unity.exe`, config `unity_hub_editors`), or `unity_editors` in the config |
| a game's run logs | `<game>\Logs\unity-ps1\` (Unity's own `Logs/` folder, git-ignored) |

## A game's Unity runs: `Scripts/unity.ps1`

Every game has `Scripts/unity.ps1` from the template; sessions use it rather than calling `Unity.exe` themselves. It
finds the editor for the project's `ProjectSettings/ProjectVersion.txt` (`ugf-root.ps1` `Get-UGFUnity`), runs every job
through the limiter, writes the log to `Logs/unity-ps1/` and prints the lines that matter (compile errors, exceptions,
licence errors, `[workflow]` rows) and the exit code.

| Mode | Runs | GPU |
|---|---|---|
| `setup` | the first open: `ProjectSetup.AddPackages`, `Urp.UrpSetup.Apply`, `ProjectSetup.Configure` (three runs) | no |
| `compile` | open, import, compile, quit | no |
| `step -Method <Ns.Class.Method> -Reason "..."` | one editor step (`-executeMethod`); `-Render` for steps that need the GPU (lightmaps, screenshots) | only with `-Render` |
| `test [-Platform EditMode\|PlayMode] [-Filter]` | Unity Test Framework (`-runTests`, results XML summarized) | no |
| `build [-Development] [-Backend mono\|il2cpp]` | `BuildPlayer.BuildWindows`: the Windows x64 player in `Build/Windows/` | no |
| `play [-Scenario n] [-Render] [-Seconds] [-Extra]` | the built player, headless (`-batchmode -nographics`) or rendered at 1280x720, stopped after `-Seconds` | only with `-Render` |

Facts that cost time before:

- **One Unity process per project**: the project lock (`Temp/UnityLockfile`) makes a second process fail at once.
  The person may have the GUI editor open; then wait or ask.
- **Licence**: batchmode needs an activated licence (Unity Hub, signed in). A licensing error in the log means the
  person has to sign in again; it is not a game bug.
- **Compile errors abort batchmode** before `-executeMethod` runs: `error CS` lines first.
- **`-runTests` quits by itself**; with `-quit` the tests never run.
- **`-nographics` renders nothing**: no screenshots, no lightmap bakes, no `ScreenCapture`.
- **IL2CPP** needs the Windows Build Support (IL2CPP) module and Visual Studio's C++ workload (`machine/check.ps1`
  warns when either is missing); `-Backend mono` builds without them.

## One heavy job at a time: the limiter

### Machine-wide slots

Every heavy job of every session goes through one limiter, `<root>\tools\unity-heavy.ps1` (rows in
`.recording\_heavy-jobs.jsonl`): `& <root>\tools\unity-heavy.ps1 -Label "<slug> <what>" [-Gpu] [-Low] -- <exe> <args>`.
From Git Bash, wrap it in `powershell -Command "& '<path>' ... ; exit $LASTEXITCODE"` (`powershell -File ... --`
misparses `--`).

Each slot is a named mutex. A job killed before it releases its slot leaves the mutex abandoned, and the next job takes
it over, so no slot leaks. The counts are read from the config at every call.

| Slots | Named mutexes | Taken by | Count |
|---|---|---|---|
| general | `Global\ue-heavy-slot-<n>` | every job | config `heavy_slots`, else the formula |
| GPU | `Global\ue-gpu-slot-<n>` | jobs that render (`Unity.exe` without `-nographics`, a player without `-nographics`, anything run with `-Gpu`), together with a general slot | config `gpu_slots`, else the formula |

**The mutex names are the Unreal game-factory's on purpose:** a machine that runs both factories has one set of slots,
so a Unity build and an Unreal build never overcommit the same RAM and GPU. A recording waiting in either factory holds
back new GPU jobs in both.

The formula (`ugf-root.ps1` `Get-UGFComputedSlots`; bootstrap.ps1 writes its result to the config, and a value set by
hand stays unless `bootstrap.ps1 -Force`):

- `heavy_slots = clamp(1..8, min(floor((RAM GB - 6) / 6), floor(logical cores / 4), floor((commit limit GB - 6) / 8)))`
- `gpu_slots = clamp(1..4, min(floor(VRAM GB of the largest NVIDIA GPU / 4), heavy_slots - 1))`, 1 without nvidia-smi

Dynamic guards: a GPU job starts only while used VRAM is under `gpu_vram_limit_mb` (default half the VRAM) and no
other GPU job started in the last 60 s; recordings take every GPU slot; `-Low` jobs (background work) take a slot only
while nobody else waits. `machine/check.ps1` shows the slots in effect and where each comes from.

## Recording pipeline (later)

The plan, mirroring the Unreal factory's pipeline:

1. **Build** the release player from a commit in a private clone (`builds\<slug>\<sha>\`), never in the session's
   working copy.
2. **Record** one run per scenario: launch the player with the AutoPlay flags ([autoplay-contract.md](autoplay-contract.md)),
   wait for `ready.json`, start ffmpeg's window capture (`gdigrab`/`ddagrab` by PID) at 60 fps, write `go`, stop
   after `outcome.json`; the recording takes every GPU slot.
3. **Bundle** each run: `video.mkv`, `system_audio.mka` (from `audio.wav` + `audio_clock.jsonl`), `inputs.jsonl`,
   `telemetry.jsonl`, `outcome.json`, `metadata.json`, `validation.json`, `manifest.json`, `stills/`, `gameplay.mp4`.
4. **Validate** each run (files well formed, inputs injected, video and audio aligned). A run's score never fails it.
5. Only the coordinator queues recordings, one at a time.

## Names that must not reach the games

Superposition, game-factory, unity-game-factory, and agent, model and provider names never appear in a game's code,
assets, settings, commits or builds (unity-game-session skill, "Names"); `new-game.ps1` refuses them in the names it
writes, and the packager scrubs what ships.
