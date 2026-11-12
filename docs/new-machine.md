# Setting up a new machine

Goal: a teammate with a fresh Windows 11 PC goes from nothing to building Unity games with **one command** plus the
few sign-ins and installs that cannot be scripted. A few hours, most of it downloads (the Unity editor with its
Windows modules is about 10 GB; game repos are several GB each with their store packs). `machine/setup.ps1` does the
rest; it is idempotent and resumable: after any manual step or a reboot, run it again and it continues where it
stopped.

> **Not yet proven on a clean PC.** setup.ps1 has been tested only as dry runs against scratch roots on a machine that
> already had the toolchain (resume from saved answers included); a standalone copy that clones the repo, the winget
> installs, UAC steps, Unity Hub steps and sign-ins have not yet run end to end on a fresh Windows install. Report what
> breaks on the first real clean run.

**Another factory on the same PC.** Both can live on one machine. This one has its own root
(`%USERPROFILE%\UnityWork`), config (`%USERPROFILE%\.unity-game-factory\config.json`), hooks folder
(`%USERPROFILE%\.unity-game-factory\hooks\`) and skills (`unity-commit-always`, `unity-game-session`, `unity-sound`,
`unity-write-tasks`); setup and bootstrap add their entries next to the other factory's and never change them. A
session is recorded by the factory whose `games\<slug>` folder one of its tool calls names. The two share one thing on
purpose: the
machine-wide job slots (`unity-heavy.ps1` takes the same named mutexes as that factory's `ue-heavy.ps1`, and also
holds its GPU jobs back while the other factory records), so together they never run more heavy or GPU jobs than the PC holds.

## Before you start

| You need | Why |
|---|---|
| Windows 11, 8+ logical cores, 16 GB RAM (32 GB recommended), 200 GB free (100 GB at the very least) on the drive that will hold the root, a DirectX 11/12 GPU | building Unity 6.3 games; setup checks these first |
| An NVIDIA GPU (8 GB+ VRAM) | only for recording gameplay videos (NVENC); without one, recording falls back to slower encoders (AMF, then the CPU) |
| A GitHub account. Contractors need no membership of `<org>`: the skill pack is public, the game stays on your PC, and the agent saying it could not create a GitHub repo for the game is expected. Staff who push the private `unity-game-<slug>` repos need an account that is a member of `<org>` (the organisation, or user, that owns `unity-game-factory`), allowed to create private repos there | setup signs you in and clones the skill pack; for staff, an owner of `<org>` adds you |
| A Unity ID with an active licence (Unity Personal is fine where its terms allow; otherwise the seat the org gives you) | Unity Hub and the editor need a signed-in, licensed account; the Asset Store uses the same account |
| A coding-agent account: Claude, or OpenAI (a ChatGPT plan or an API key) | the agent that builds the game: Claude Code in a terminal or the Claude desktop app (Code tab), or the Codex CLI in a terminal (`setup.ps1 -Agent claude\|codex\|both`) |
| Admin rights on the PC | a few UAC prompts (some of the installs, long paths) |

## 1. Run setup

The repo is private, so fetch the script with your GitHub account. Either:

- on github.com (signed in), open `<org>/unity-game-factory`, **Code > Download ZIP**, unzip it anywhere and run
  `machine\setup.ps1` from it (setup then clones the repo properly into the root), or
- in PowerShell, with the GitHub CLI (open a new terminal after installing it):

```bash
winget install -e --id GitHub.cli
```
```bash
gh auth login --web
```
```bash
gh api -H "Accept: application/vnd.github.raw" repos/<org>/unity-game-factory/contents/machine/setup.ps1 > setup.ps1
```

Then the one command (in the folder holding `setup.ps1`):

```bash
powershell -ExecutionPolicy Bypass -File setup.ps1 -Org <org>
```

Options: `-Agent claude|codex|both` (the coding agent; asked on the first run, remembered), `-Root D:\UnityWork` (the
machine root; default `%USERPROFILE%\UnityWork`, asked on the first run; a short path such as `C:\UnityWork` helps
with deep package paths), `-CloneGames` (clone every `<org>/unity-game-*` repo; asked otherwise), `-Yes` (answer yes
to every question).

What it does, in order (log: `<root>\.setup\setup.log`; answers remembered in `<root>\.setup\state.json`):

1. **Hardware precheck** against the minimums above.
2. **Software through winget**, after one question (winget accepts each package's licence; some show a UAC prompt):
   Git + Git LFS, GitHub CLI, Python 3.12, 7-Zip, Unity Hub (`Unity.UnityHub`); with Codex the Codex CLI
   (`OpenAI.Codex`); with Claude Code the Claude desktop app is offered separately (optional).
3. **Windows settings, each asked first**: long paths (one UAC prompt) and no sleep for the PC and the display while
   plugged in (long builds and overnight queues).
4. **GitHub sign-in** (`gh auth login` in the browser) and your git `user.name` / `user.email`; checks that you can
   see `<org>/unity-game-factory`. With Codex, **Codex sign-in** (`codex login` in the browser; `codex login status`
   tells).
5. **unity-game-factory**: cloned into `<root>\unity-game-factory`, then `machine\bootstrap.ps1` (config with
   `github_org`, job slots, layout, tools, pinned ffmpeg, skills, root `CLAUDE.md` and/or `AGENTS.md`, and the
   recording hooks for your agent after it has shown what they record and asked; the games when you said so) and
   `machine\check.ps1`.
6. **A PASS / TODO list.** Each TODO says exactly what to do; do it and run setup again.

## 2. What only you can do

Setup prints these as TODOs (as notes where a PC may not need them) and detects them on the next run.

| Step | How | Detected by |
|---|---|---|
| Unity Hub sign-in and licence | Open Unity Hub, sign in with your Unity ID (create one if needed), then **Preferences > Licenses > Add** (Personal, or the org's seat). Every editor run needs it, batchmode too. | the licence file Unity Hub writes (`%LOCALAPPDATA%\Unity\licenses\`) or a serial activation's (`%ProgramData%\Unity\Unity_lic.ulf`); a licence server's floating seat leaves neither, so `check.ps1` only warns |
| Unity 6.3 LTS editor | In Unity Hub: **Installs > Install Editor > Unity 6.3 (LTS)**, the newest 6000.3 patch (new games use the newest installed one; the config's `unity_version` set to an exact version pins it, and older patches are under **Archive**), with the module **Windows Build Support (IL2CPP)**. Default folder `C:\Program Files\Unity\Hub\Editor\<version>`; another works (set `unity_hub_editors`, or `"unity_editors": {"<version>": "<path to Unity.exe>"}` in the config). Each game builds with the exact version its `ProjectSettings\ProjectVersion.txt` names, so keep the versions your games use installed (`check.ps1` lists any that are missing). | `<unity_hub_editors>\6000.3.*\Editor\Unity.exe` |
| C++ tools (IL2CPP builds only) | Visual Studio 2022 or its Build Tools with **Desktop development with C++** (or **Game development with Unity** with its C++ option). Mono player builds and the editor need none. | `check.ps1` (WARN only) |
| NVIDIA driver (if you have an NVIDIA GPU; for recording) | the current Game Ready or Studio driver, 610 or newer, from nvidia.com/drivers or the NVIDIA app | `nvidia-smi` |
| Display (for recording) | a multiple of 60 Hz (60/120/240) and a primary display that holds a 1920x1080 window: Settings > System > Display | `check.ps1` |
| Asset Store | only to download store packs for a **new** game: in the editor, **Window > Package Manager > My Assets** (signed in with the account that owns them) > Download. Downloads land in `%APPDATA%\Unity\Asset Store-5.x\`. Purchases and licence choices stay with their owner. | `check.ps1` counts the downloads |
| Agent sign-in | Claude Code: run `claude` once (or open the desktop app) and sign in. Codex: `codex login` (setup runs it; `--device-auth` without a browser) | Claude: not detectable; Codex: `codex login status` |

Cloned games carry their store packs (committed through Git LFS in each private repo), so the Asset Store cache and
the shared asset library (`<root>\asset-library`) are only needed for new games.

## 3. The first session

- **Desktop app, several games at once (Claude only):** open the Code tab in the root folder and start a coordinator
  session; add its session id to `<hooks dir>\recording-exclude.txt`. It starts the game sessions (`CONTINUE` for
  cloned games, `NEW` for new ones) from [briefs/game-session.md](briefs/game-session.md).
- **Solo, one game in a terminal:** `cd <root>`, run `claude` or `codex -s danger-full-access`, and paste
  [briefs/solo-game.md](briefs/solo-game.md) with its placeholders filled. Same rules and the same recording with
  either agent; you take the coordinator's decisions (pushes, recordings). What differs between the agents:
  [AGENTS.md](../AGENTS.md), "Agents".

Start sessions in the UnityWork root (or a game folder under it), never in another factory's root: the root's
`CLAUDE.md` / `AGENTS.md` decides which factory's rules a session follows.

## Reference: what bootstrap writes

`machine/bootstrap.ps1` (run by setup; can be run on its own any time):

- `%USERPROFILE%\.unity-game-factory\config.json`: `root`, `ugb` (`C:\UGB`: the release builds' private clones and
  build temp, outside the user profile), `unity_hub_editors`, `unity_version` (the editor new games use: `6000.3`, its
  newest installed patch, unless set to an exact version), `github_org`, `record_extra_projects`, `agents`,
  `hooks_dir`; the job slots `heavy_slots` / `gpu_slots` sized from the hardware (the same formula another factory on
  the machine uses), with their basis in `slots_auto` (values edited by hand are kept, `-Force` recomputes);
- the layout `games\ tasks\ builds\_queue\ builds\_logs\ recordings\ .recording\ deliverables\ asset-library\ tools\`
  and `<ugb>\src`, `<ugb>\tmp` (`builds\` and `recordings\` are the recording pipeline's, `deliverables\` holds the
  creation replay's packages and, per game, the dataset packager's commit maps, audit files and run lock; a machine
  set up before `ugb` existed gets it from this bootstrap, and until then `check.ps1` fails the layout);
- `tools\unity-heavy.ps1` (the machine-wide job limiter) with `tools\ugf-root.ps1`, the pinned ffmpeg 8.1.2 (SHA-256
  verified);
- the recording hooks in the hooks dir (`hooks_dir` in the config, default `~\.unity-game-factory\hooks\`), wired into
  `~\.claude\settings.json` for Claude Code and `~\.codex\hooks.json` + trust entries in `~\.codex\config.toml` for
  Codex (backup first; asked first, `-Yes` skips the question; only the handlers that run `record-unity-action.ps1`
  are added or updated, any other hook stays); the `unity-*` skills from `skills\` in
  `~\.claude\skills\` and/or `~\.agents\skills\` (other skill folders untouched); `<root>\CLAUDE.md` importing
  `unity-game-factory/CLAUDE.md` and/or `<root>\AGENTS.md` naming `unity-game-factory\AGENTS.md`;
- Git LFS filters, the post-commit hook in every game repo (the commit recorder and the live creation replay), and
  with `-CloneGames` every `<org>/unity-game-*` repo.

`machine/check.ps1` reports PASS / WARN / FAIL for the toolchain (Unity Hub, the 6.3 LTS editor new games use with
IL2CPP support, the editors the games here name, C++ tools for IL2CPP), GitHub access, display and power, disk, the
pinned ffmpeg (NVENC test), config, job slots, layout,
hooks, skills, game repo hooks and the asset library; its exit code is the number of FAILs; for each agent it also
checks the install, the sign-in (Codex) and that the hooks are wired (and, for Codex, trusted). Details of every file:
[../machine/README.md](../machine/README.md).

## Toolchain notes

- A project opens and builds only with the **exact** editor version in its `ProjectSettings\ProjectVersion.txt`
  (`m_EditorVersion`); the tools never upgrade a project silently. Moving a game to a newer 6000.3 patch is a
  deliberate step: open it once with the new editor in batchmode, commit the changed `ProjectVersion.txt` and the
  re-serialized files together.
- Each project's `Library\` folder is a local cache (git-ignored) that the first open rebuilds: a fresh clone's first
  editor run takes several minutes, run it through `unity-heavy.ps1` like any heavy job.
- The editor keeps its own log in `%LOCALAPPDATA%\Unity\Editor\Editor.log` and Unity Hub its logs in
  `%APPDATA%\UnityHub\logs\`; batchmode runs pass `-logFile <path>` (`Scripts/unity.ps1` does) so a run's log is kept
  with it.
- Vendor RGB/lighting services can leak commit memory; if free commit keeps falling, find the process whose commit
  grows and restart or disable it. Windows Firewall prompts dim the screen and block capture; a release player opens
  no network port, so recording one never prompts.

## Scratch test (without touching a live setup)

`-DryRun` reports installs, Windows settings, sign-ins and game clones without doing them. It runs bootstrap only when
it is given a scratch config, hooks dir and agent folders (bootstrap writes to all of them), and then against those
only:

```bash
powershell -ExecutionPolicy Bypass -File machine/setup.ps1 -Org <org> -DryRun -Agent both -Root C:/ugf-test/UnityWork -ClaudeDir C:/ugf-test/home/.claude -CodexDir C:/ugf-test/home/.codex -AgentsSkillsDir C:/ugf-test/home/.agents/skills -HooksDir C:/ugf-test/home/.unity-game-factory/hooks -ConfigPath C:/ugf-test/home/.unity-game-factory/config.json
```

With `UGF_CONFIG` set to the scratch config, `powershell -ExecutionPolicy Bypass -File templates/new-game.ps1 -Slug
<game> -Path C:/ugf-test/UnityWork/games/<game> -NoGitHub -Root C:/ugf-test/UnityWork -HooksDir
C:/ugf-test/home/.unity-game-factory/hooks` creates a game without creating a GitHub repo.
