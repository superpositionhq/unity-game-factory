# machine/

Everything a Windows machine needs outside this repo, kept in the repo and installed by `bootstrap.ps1`. Step-by-step
setup, including the manual sign-ins: [../docs/new-machine.md](../docs/new-machine.md).

## The machine root

All machine paths hang off one root, the "UnityWork" folder that holds `unity-game-factory\`, `games\`, `tasks\`,
`builds\`, `recordings\`, `.recording\`, `deliverables\`, `asset-library\` and `tools\`. Docs write it as `%UGF_ROOT%`.
`builds\` and `recordings\` are the recording pipeline's (`tools/unity-pipeline/`,
[../docs/unity-pipeline.md](../docs/unity-pipeline.md)): release builds, the queue and the gameplay bundles. The
creation replay ([../docs/unity-replay.md](../docs/unity-replay.md)) keeps each game's isolated project and work files
in `unity-replay\<slug>\` and writes its packages to `deliverables\_replay\`; the dataset packager,
`tools/package-dataset.py`, writes into the game repo's own folder.
`lib/ugf-root.ps1` (PowerShell, dot-source it) and `lib/ugfroot.py` (Python: `sys.path.insert(0, <repo>/machine/lib)`,
`ugfroot.root()`) resolve it in this order:

1. env `UGF_ROOT`;
2. `root` in the config file: env `UGF_CONFIG`, else `%USERPROFILE%\.unity-game-factory\config.json` (bootstrap writes it);
3. `%USERPROFILE%\UnityWork`.

The config also holds `ugb` (default `C:\UGB`: the release builds' private clones and build temp, outside the user
profile so the user name is not compiled into a player; `bootstrap.ps1 -Ugb` sets it and creates `<ugb>\src` and
`<ugb>\tmp`), `unity_hub_editors` (default `C:\Program Files\Unity\Hub\Editor`: where Unity Hub installs
editors), `unity_version` (default `6000.3`, Unity 6.3 LTS: new games use its newest installed patch; an exact version
such as `6000.3.28f1` pins them to it), optional `unity_editors`
(`{"6000.3.28f1": "D:\\Unity\\6000.3.28f1\\Editor\\Unity.exe"}`: editors installed elsewhere, which then count as
installed), `github_org` (the GitHub organisation or user that owns unity-game-factory and the private
`unity-game-<slug>` repos: `bootstrap.ps1 -Org` writes it, env `UGF_ORG` overrides it; new-game.ps1, `-CloneGames` and
check.ps1 read it), and `record_extra_projects` (default `[]`: extra top-level folders the recording hooks treat as
projects besides `games\<slug>`). Optional: `out` (env `UGF_OUT`; default `<root>\deliverables`: where the creation
replay's packages go, `_replay\<slug>\<sha8>\`, GBs per game, so point it at a roomy drive; the dataset packager writes
next to the game repo, or where its `--out` says) and `min_free_gb` (env `UGF_MIN_FREE_GB`, default 50: the task
check, the task try, the creation replay and the dataset packager refuse to start on a drive with less free).

Editor per project: a project's `ProjectSettings\ProjectVersion.txt` names its editor (`m_EditorVersion: 6000.3.28f1`),
and the tools use exactly that install (`lib/ugf-root.ps1` `Get-UGFUnity`, `lib/ugfroot.py` `unity_editor`):
`unity_editors[<version>]` if set, else `<unity_hub_editors>\<version>\Editor\Unity.exe`; a missing version gives
`$null` and a warning naming the version to install through Unity Hub (`ugfroot.py` exits with that message), so a
project never silently opens in another editor, which would re-serialize its assets. Without a project, the version new
games use: `Get-UGFUnityVersion` (`ugfroot.py` `unity_version`), which turns the series `6000.3` into its newest
installed final patch and gives `''` when none is installed (Unity Hub installs each patch beside the others, so a
pinned default would go stale). `Get-UGFNewestUnity -Series 6000.3` gives the newest installed 6.3 LTS patch as
`.Version` / `.Path` (versions compared numerically), or `$null`. `templates/new-game.ps1` writes the version new games
use into a new project.

Job slots (unity-heavy.ps1, docs/unity-pipeline.md "Machine-wide slots"):

| Key | Meaning | Without it |
|---|---|---|
| `heavy_slots` | general slots: batchmode editor runs, player builds, tests (GPU jobs hold one too) | `clamp(1..8, min(floor((RAM GB - 6) / 6), floor(logical cores / 4), floor((commit limit GB - 6) / 8)))` |
| `gpu_slots` | concurrent rendering jobs; a recording takes all of them | `clamp(1..4, min(floor(VRAM GB of the largest NVIDIA GPU / 4), heavy_slots - 1))`, 1 without nvidia-smi |
| `gpu_vram_limit_mb` | a GPU job starts only while less VRAM than this is in use | half the GPU's VRAM |
| `slots_auto` | written by bootstrap.ps1: the computed values and the hardware they came from | |

bootstrap.ps1 writes the computed `heavy_slots` / `gpu_slots` (and `slots_auto`); a value that differs from
`slots_auto` was set by hand and stays unless `bootstrap.ps1 -Force`. check.ps1 shows the slots in effect and their
source (config set by hand, config from bootstrap, or computed at run time). The formula lives in
`lib/ugf-root.ps1` (`Get-UGFComputedSlots`) and `lib/ugfroot.py` (`computed_slots`).

```json
{ "root": "C:\\Users\\<name>\\UnityWork", "ugb": "C:\\UGB", "unity_hub_editors": "C:\\Program Files\\Unity\\Hub\\Editor", "unity_version": "6000.3",
  "github_org": "<org>", "record_extra_projects": [], "agents": ["claude"], "hooks_dir": "C:\\Users\\<name>\\.unity-game-factory\\hooks",
  "heavy_slots": 3, "gpu_slots": 2, "slots_auto": { "heavy_slots": 3, "gpu_slots": 2, "basis": "<hardware>" } }
```

### Next to another factory

A PC may also run another factory (root `%USERPROFILE%\Work`, config `%USERPROFILE%\.game-factory\`). The two
keep separate roots, configs, hooks folders, session maps and skills, and each one's bootstrap adds its hook entries
next to the other's in `~\.claude\settings.json` / `~\.codex\hooks.json` without touching them (ours run
`record-unity-action.ps1`, theirs `record-action.ps1`). A session is recorded by the factory whose `games\<slug>` (or
extra project) one of its tool calls names, by both if its calls name a game of each, and from then on every call of it
is recorded there (see Recording below). What they share on purpose:

- **Job slots.** `unity-heavy.ps1` takes the same machine-wide mutexes as `ue-heavy.ps1` (`Global\ue-heavy-slot-<n>`,
  `Global\ue-gpu-slot-<n>`, `Global\ue-heavy-low-slot`), so the jobs of both draw from one set of slots. Both use
  the same slot formula; if the two configs set different counts, each limiter enforces its own count over the shared
  mutexes, so keep them equal.
- **Recordings.** `unity-heavy.ps1` holds back its GPU jobs while either factory's `builds\_queue\_recording-wants-gpu`
  flag is fresh, and reads both factories' job logs for waiting jobs and recent GPU starts (`Get-UGFOtherFactoryRoot` finds
  the other root from `GF_ROOT`, its config (`GF_CONFIG`, else `%USERPROFILE%\.game-factory\config.json`), else
  `%USERPROFILE%\Work` when that holds a clone named `game-factory`); `ue-heavy.ps1` reads only its own root's. A running
  recording holds every GPU slot, which stops the GPU jobs of both.

## Files

| Path | Installed to | What |
|---|---|---|
| `setup.ps1` | | the one entry point for a clean PC: hardware precheck, winget installs (Git, Git LFS, gh, Python, 7-Zip, Unity Hub, the agent), long paths + no sleep (asked), gh sign-in + git identity, unity-game-factory clone, the coding agent (`-Agent claude\|codex\|both`: the Codex CLI and `codex login` for Codex), then bootstrap.ps1 and check.ps1; manual steps (Unity Hub sign-in and licence, the 6.3 LTS editor, NVIDIA driver, Claude Code sign-in) detected on re-run; PASS/TODO list, log `<root>\.setup\setup.log` |
| `bootstrap.ps1` | | idempotent setup: config + layout, tools, ffmpeg, hooks + each agent's settings merge (`-Agent claude\|codex\|both`; prints what the hooks record and asks first; `-Yes` skips the question), the `unity-*` skills, root CLAUDE.md / AGENTS.md, LFS, gh, game repo hooks (`-CloneGames`) |
| `check.ps1` | | read-only PASS/WARN/FAIL report (toolchain, GPU/display, disk, agents, setup, asset library) |
| `get-ffmpeg.ps1` | `<root>\tools\ffmpeg-8.1.2\` | downloads gyan.dev ffmpeg 8.1.2 full_build .7z, verifies SHA-256 `0fff1889...7059`, unpacks |
| `lib/ugf-root.ps1` | `<root>\tools\`, the hooks dir | root/config resolver (also `Get-UGFHooksDir`, `Get-UGFAgents`, `Get-UGFUnity`, `Get-UGFNewestUnity`, the slot mutexes), dot-sourced by every script |
| `lib/ugfroot.py` | | the same for Python tools (`root`, `org`, `unity_editor`, `unity_version`, `computed_slots`, `slot_plan`, `out`, `check_free`) |
| `lib/codex-hooks.ps1` | | Codex hook trust: the `[hooks.state]` entries Codex needs in `config.toml` before it runs a hook (bootstrap writes ours, check compares) |
| `tools/unity-heavy.ps1` | `<root>\tools\unity-heavy.ps1` | machine-wide job limiter: `heavy_slots` general slots + `gpu_slots` GPU slots, one named mutex per slot (shared with another factory, see above: a killed job leaks none; VRAM guard; a recording takes all GPU slots), counts from the config or the hardware formula above, `-Low` for background work, GPU auto-detected (`Unity.exe` without `-nographics`, a packaged player; `-Gpu` forces it, `-nographics` always rules it out), yields to `builds\_queue\_recording-wants-gpu`, log `.recording\_heavy-jobs.jsonl`. Installed next to a copy of `lib\ugf-root.ps1` |
| `hooks/record-unity-action.ps1` | the hooks dir | the agent hook (Claude Code: PostToolUse / PostToolUseFailure / Stop, and UserPromptSubmit / SessionEnd with `-Messages`; Codex: PostToolUse / Stop, and UserPromptSubmit / SessionEnd with `-Messages`, all with `-Agent codex`): every tool call of a game session to `.recording\<project>\actions.jsonl` (earlier calls backfilled from the transcript, see Recording), every prompt the person typed and every reply the model wrote to `.recording\<project>\messages.jsonl` (read from the transcript); Stop auto-commits leftovers as `WIP` (none while conflicts are unresolved or HEAD is detached) |
| `hooks/record-unity-commit.ps1` | the hooks dir | called by each game repo's post-commit hook: `.recording\<repo>\commits.jsonl` |
| `hooks/settings-hooks.json` | merged into `~\.claude\settings.json` | Claude Code: the five hook entries (PostToolUse, PostToolUseFailure, Stop, UserPromptSubmit, SessionEnd; `{{HOOKS_DIR}}` filled in) |
| `hooks/codex-hooks.json` | merged into `~\.codex\hooks.json` | Codex: the four hook entries (PostToolUse, Stop, UserPromptSubmit, SessionEnd; `{{HOOKS_DIR}}` filled in), trusted in `~\.codex\config.toml` |
| `hooks/recording-exclude.txt` | the hooks dir (once) | session ids never recorded (the coordinator) |
| `install-git-hook.ps1` | `<game>\.git\hooks\post-commit` | appends the commit recorder and the live creation replay's line (`tools/unity-replay/live-hook.ps1` of this checkout; it acts only for `<root>\games\<slug>`) after Git LFS's own lines (before another tool's final `exit` or `exec`); warns when the recorder isn't in the hooks dir, the live hook isn't in the checkout, or another tool's hook can end before them. bootstrap.ps1 runs it for every game under `<root>\games` |

The hooks dir is `hooks_dir` in the config, default `~\.unity-game-factory\hooks\`. One copy serves both agents.
`recording-sessions.json` (session id -> project map) is runtime state: bootstrap creates it empty next to the hooks
and never overwrites it. The hook keeps two more state files there: `recording-backfill.json` (the sessions whose
earlier tool calls were imported) and `recording-messages.json` (transcript file -> bytes read, for `messages.jsonl`).

The recording pipeline is here (`tools/unity-pipeline/`, [../docs/unity-pipeline.md](../docs/unity-pipeline.md)): its
builds and recordings go through `unity-heavy.ps1`'s slots like every other heavy job. So is the creation replay
(`tools/unity-replay/`, [../docs/unity-replay.md](../docs/unity-replay.md)): each game's post-commit line starts its
live replay after every commit, whose editor runs go through `unity-heavy.ps1 -Low` (one low-priority job
machine-wide). The task checker is here (`tools/task-check.py`, [../docs/task-check.md](../docs/task-check.md)): its
builds and plays go through `unity-heavy.ps1` like every other heavy job. So is the dataset packager (`tools/package-dataset.py`,
[../docs/unity-pipeline.md](../docs/unity-pipeline.md#dataset-packager)), which reads a game's `actions.jsonl` and
`messages.jsonl` into the dataset's `History/sessions/`.

### Recording

- **Mapping.** A session is filed under a project the first time a tool call's input (command, file path, cwd) names
  `<root>\games\<slug>` (or an extra project) as an absolute path, in any spelling (`C:\...`, `C:/...`, `/c/...`),
  starting a word: `D:/backup/c/...` or a path glued to an option (`git -C/c/...`) does not count.
  Variables such as `%UGF_ROOT%` are seen unexpanded and do not count. `templates/new-game.ps1` therefore requires the
  written-out `-Path <root>\games\<slug>`, and that call maps a new game's session.
- **Backfill.** At that first mapping the hook imports the session's earlier tool calls (reading docs, drafting the
  design) from its transcript (`transcript_path` in the hook input; Claude Code: plus `<session>\subagents\*.jsonl`
  beside it; Codex: the rollout file's completed shell, file-change and MCP items, shell calls as `Bash` with the
  command, file changes as `apply_patch` with `input.changes` since the rollout keeps no patch text). They
  are written in order, just before the mapping call's own row, with `"status": "from_transcript"` and the transcript's
  times (`time` = the call, `result_time` = its result). Only calls with a result, logged under this session id and no
  older than the transcript file are imported (a fork's copied context predates the file). Each session is backfilled
  once (`recording-backfill.json` next to the hooks: count, transcript, imported tool_use_ids), and a call imported this
  way is never written again by its own live hook.
- **Sessions mapped before the backfill existed:** `powershell -ExecutionPolicy Bypass -File
  <hooks dir>\record-unity-action.ps1 -Backfill <session id> [-TranscriptPath <file>] [-Agent codex]` inserts the rows
  before that session's first row in `actions.jsonl` (finds the transcript under `~\.claude\projects\`, or
  `~\.codex\sessions\` with `-Agent codex`, when not given); a second run does nothing. The same call also imports
  that session's messages.
- Live rows carry no `status`; every row of a backfill carries `from_transcript`, so the two are never confused.
- **Messages.** Every prompt the person typed and every reply the model wrote goes to
  `<root>\.recording\<project>\messages.jsonl`, one row each: `time`, `project`, `session_id`, `agent`, `role`
  (`user` or `assistant`), `message_id`, `text`, and where they apply `model`, `images` (pictures attached to a
  prompt), `mid_turn` (a prompt typed while the model was working), `phase` (Codex) and `subagent` (a Claude Code
  subagent's transcript, where `user` is the prompt the session gave it). They are read from the session's transcript,
  never from the hook input, so each is written once, with the transcript's own id and time. Every `Stop`, and the
  `UserPromptSubmit` and `SessionEnd` hooks (which call the script with `-Messages` and write no `actions.jsonl` row),
  read what the transcript gained since the last read (`recording-messages.json` next to the hooks: transcript file ->
  bytes read), so a session mapped late gets its earlier messages too. Not recorded: tool calls and results
  (`actions.jsonl` has them), the model's reasoning, text the agent tool puts into a turn itself (meta rows,
  compaction summaries, background-task notices, API error notices) and a fork's copied context.
- **Sessions recorded before messages were:** `record-unity-action.ps1 -Backfill all` imports the messages of every
  mapped session whose transcript is still on this machine (either agent), and nothing else.
- Row schemas: `actions.jsonl` rows carry `"schema": "agent-action/v0"`, `messages.jsonl` rows
  `"schema": "agent-message/v0"`, `commits.jsonl` rows `"schema": "commit/v0"`.
- Every row carries `agent` (`claude` or `codex`). Codex rows differ in two ways: file edits are `apply_patch` rows
  (`input.command` = the patch), and there is no `PostToolUseFailure` (a failed call is a `PostToolUse` whose response
  shows the exit code).
- Nothing is recorded (and nothing replayed) while `UGF_NO_RECORDING` (or another factory's `GF_NO_RECORDING`) is
  set: a task try's agent is not a game session.
- **Codex hook trust.** Codex runs a hook from `hooks.json` only after it is trusted (a hash of the hook in
  `config.toml` `[hooks.state."<hooks.json>:<event>:<group>:<handler>"]`); an untrusted or edited hook is skipped
  without a word. bootstrap.ps1 writes the entries for the record-unity-action.ps1 hooks (`lib/codex-hooks.ps1`),
  check.ps1 compares them, and `/hooks` inside Codex shows (and can set) the same state.

Installed copies are plain copies: after changing a file here, run `bootstrap.ps1` again (it backs up what it
replaces under `_backup\<time>\`). `check.ps1` reports installed copies that differ from the repo.
