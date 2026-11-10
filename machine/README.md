# machine/

Everything a Windows machine needs outside this repo, kept in the repo and installed by `bootstrap.ps1`. Step-by-step
setup, including the manual sign-ins: [../docs/new-machine.md](../docs/new-machine.md).

## The machine root

All machine paths hang off one root, the "UnityWork" folder that holds `unity-game-factory\`, `games\`, `tasks\`,
`builds\`, `recordings\`, `.recording\`, `deliverables\`, `asset-library\` and `tools\`. Docs write it as `%UGF_ROOT%`.
`lib/ugf-root.ps1` (PowerShell, dot-source it) and `lib/ugfroot.py` (Python: `sys.path.insert(0, <repo>/machine/lib)`,
`ugfroot.root()`) resolve it in this order:

1. env `UGF_ROOT`;
2. `root` in the config file: env `UGF_CONFIG`, else `%USERPROFILE%\.unity-game-factory\config.json` (bootstrap writes it);
3. `%USERPROFILE%\UnityWork`.

The config also holds `unity_hub_editors` (default `C:\Program Files\Unity\Hub\Editor`: where Unity Hub installs
editors), `unity_version` (default `6000.3.26f1`, Unity 6.3 LTS: the editor new games use), optional `unity_editors`
(`{"6000.3.26f1": "D:\\Unity\\6000.3.26f1\\Editor\\Unity.exe"}`: editors installed elsewhere), `github_org` (the
GitHub organisation or user that owns unity-game-factory and the private `unity-game-<slug>` repos: `bootstrap.ps1
-Org` writes it, env `UGF_ORG` overrides it; new-game.ps1, `-CloneGames` and check.ps1 read it), and
`record_extra_projects` (default `[]`: extra top-level folders the recording hooks treat as projects besides
`games\<slug>`). Optional: `out` (env `UGF_OUT`; default `<root>\deliverables`: packages, dataset zips and replay
packages, GBs per game, so point it at a roomy drive) and `min_free_gb` (env `UGF_MIN_FREE_GB`, default 50: packaging
refuses to start on a drive with less free).

Editor per project: a project's `ProjectSettings\ProjectVersion.txt` names its editor (`m_EditorVersion: 6000.3.26f1`),
and the tools use exactly that install (`lib/ugf-root.ps1` `Get-UGFUnity`, `lib/ugfroot.py` `unity_editor`):
`unity_editors[<version>]` if set, else `<unity_hub_editors>\<version>\Editor\Unity.exe`; a missing version gives
`$null` and a warning naming the version to install through Unity Hub (`ugfroot.py` exits with that message), so a
project never silently opens in another editor, which would re-serialize its assets. `Get-UGFUnityVersion` is the
configured default (`unity_version`). `Get-UGFNewestUnity -Series 6000.3` gives the newest installed 6.3 LTS patch as
`.Version` / `.Path` (versions compared numerically), or `$null`; `templates/new-game.ps1` writes it into a new
project.

Job slots (unity-heavy.ps1):

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
{ "root": "C:\\Users\\<name>\\UnityWork", "unity_hub_editors": "C:\\Program Files\\Unity\\Hub\\Editor", "unity_version": "6000.3.26f1",
  "github_org": "<org>", "record_extra_projects": [], "agents": ["claude"], "hooks_dir": "C:\\Users\\<name>\\.unity-game-factory\\hooks",
  "heavy_slots": 3, "gpu_slots": 2, "slots_auto": { "heavy_slots": 3, "gpu_slots": 2, "basis": "<hardware>" } }
```

### Next to the Unreal game-factory

A PC may also run the Unreal game-factory (root `%USERPROFILE%\Work`, config `%USERPROFILE%\.game-factory\`). The two
keep separate roots, configs, hooks folders, session maps and skills, and each one's bootstrap adds its hook entries
next to the other's in `~\.claude\settings.json` / `~\.codex\hooks.json` without touching them (ours are recognised by
our hooks dir in the command). A tool call is recorded by the factory whose root it names. What they share on purpose:

- **Job slots.** `unity-heavy.ps1` takes the same machine-wide mutexes as `ue-heavy.ps1` (`Global\ue-heavy-slot-<n>`,
  `Global\ue-gpu-slot-<n>`, `Global\ue-heavy-low-slot`), so Unity and Unreal jobs draw from one set of slots. Both use
  the same slot formula; if the two configs set different counts, each limiter enforces its own count over the shared
  mutexes, so keep them equal.
- **Recordings.** A recording in either factory (its `builds\_queue\_recording-wants-gpu` flag) holds back GPU jobs
  of both, and `unity-heavy.ps1` reads both job logs for waiting jobs and recent GPU starts (`Get-UGFUnrealRoot`
  finds the other root from `GF_ROOT` or `%USERPROFILE%\.game-factory\config.json`).

## Files

| Path | Installed to | What |
|---|---|---|
| `setup.ps1` | | the one entry point for a clean PC: hardware precheck, winget installs (Git, Git LFS, gh, Python, 7-Zip, Unity Hub, the agent), long paths + no sleep (asked), gh sign-in + git identity, unity-game-factory clone, the coding agent (`-Agent claude\|codex\|both`: the Codex CLI and `codex login` for Codex), then bootstrap.ps1 and check.ps1; manual steps (Unity Hub sign-in and licence, the 6.3 LTS editor, NVIDIA driver, Claude Code sign-in) detected on re-run; PASS/TODO list, log `<root>\.setup\setup.log` |
| `bootstrap.ps1` | | idempotent setup: config + layout, tools, ffmpeg, hooks + each agent's settings merge (`-Agent claude\|codex\|both`; prints what the hooks record and asks first; `-Yes` skips the question), the `unity-*` skills, root CLAUDE.md / AGENTS.md, LFS, gh, game repo hooks (`-CloneGames`) |
| `check.ps1` | | read-only PASS/WARN/FAIL report (toolchain, GPU/display, disk, agents, setup, asset library) |
| `get-ffmpeg.ps1` | `<root>\tools\ffmpeg-8.1.2\` | downloads gyan.dev ffmpeg 8.1.2 full_build .7z, verifies SHA-256 `0fff1889...7059`, unpacks |
| `lib/ugf-root.ps1` | `<root>\tools\`, the hooks dir | root/config resolver (also `Get-UGFHooksDir`, `Get-UGFAgents`, `Get-UGFUnity`, `Get-UGFNewestUnity`, the slot mutexes), dot-sourced by every script |
| `lib/ugfroot.py` | | the same for Python tools (`root`, `org`, `unity_editor`, `computed_slots`, `slot_plan`, `out`, `check_free`) |
| `lib/codex-hooks.ps1` | | Codex hook trust: the `[hooks.state]` entries Codex needs in `config.toml` before it runs a hook (bootstrap writes ours, check compares) |
| `tools/unity-heavy.ps1` | `<root>\tools\unity-heavy.ps1` | machine-wide job limiter: `heavy_slots` general slots + `gpu_slots` GPU slots, one named mutex per slot (shared with the Unreal factory, see above: a killed job leaks none; VRAM guard; a recording takes all GPU slots), counts from the config or the hardware formula above, `-Low` for background work, GPU auto-detected (`Unity.exe` without `-nographics`, a packaged player), log `.recording\_heavy-jobs.jsonl`. Installed next to a copy of `lib\ugf-root.ps1` |
| `hooks/record-unity-action.ps1` | the hooks dir | the agent hook (Claude Code: PostToolUse / PostToolUseFailure / Stop; Codex: PostToolUse / Stop with `-Agent codex`): every tool call of a game session to `.recording\<project>\actions.jsonl` (earlier calls backfilled from the transcript, see Recording); Stop auto-commits leftovers as `WIP` |
| `hooks/record-unity-commit.ps1` | the hooks dir | called by each game repo's post-commit hook: `.recording\<repo>\commits.jsonl` |
| `hooks/settings-hooks.json` | merged into `~\.claude\settings.json` | Claude Code: the three hook entries (`{{HOOKS_DIR}}` filled in) |
| `hooks/codex-hooks.json` | merged into `~\.codex\hooks.json` | Codex: the two hook entries (`{{HOOKS_DIR}}` filled in), trusted in `~\.codex\config.toml` |
| `hooks/recording-exclude.txt` | the hooks dir (once) | session ids never recorded (the coordinator) |
| `install-git-hook.ps1` | `<game>\.git\hooks\post-commit` | appends the commit recorder after Git LFS's own lines |

The hooks dir is `hooks_dir` in the config, default `~\.unity-game-factory\hooks\`. One copy serves both agents.
`recording-sessions.json` (session id -> project map) is runtime state: bootstrap creates it empty next to the hooks
and never overwrites it.

Not ported yet from the Unreal factory (they come with the verifier and the recording pipeline): the per-commit live
creation replay (its post-commit line), the recording queue and its recorder, packaging and the task checker.

### Recording

- **Mapping.** A session is filed under a project the first time a tool call's input (command, file path, cwd) names
  `<root>\games\<slug>` (or an extra project) as an absolute path, in any spelling (`C:\...`, `C:/...`, `/c/...`).
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
- **Sessions mapped before the backfill existed:** `powershell -File <hooks dir>\record-unity-action.ps1 -Backfill
  <session id> [-TranscriptPath <file>] [-Agent codex]` inserts the rows before that session's first row in
  `actions.jsonl` (finds the transcript under `~\.claude\projects\`, or `~\.codex\sessions\` with `-Agent codex`,
  when not given); a second run does nothing.
- Live rows carry no `status`; every row of a backfill carries `from_transcript`, so the two are never confused.
- Every row carries `agent` (`claude` or `codex`). Codex rows differ in two ways: file edits are `apply_patch` rows
  (`input.command` = the patch), and there is no `PostToolUseFailure` (a failed call is a `PostToolUse` whose response
  shows the exit code).
- Nothing is recorded while `UGF_NO_RECORDING` (or the Unreal factory's `GF_NO_RECORDING`) is set: a task try's agent
  is not a game session.
- **Codex hook trust.** Codex runs a hook from `hooks.json` only after it is trusted (a hash of the hook in
  `config.toml` `[hooks.state."<hooks.json>:<event>:<group>:<handler>"]`); an untrusted or edited hook is skipped
  without a word. bootstrap.ps1 writes the entries for our record-unity-action.ps1 hooks (`lib/codex-hooks.ps1`), check.ps1
  compares them, and `/hooks` inside Codex shows (and can set) the same state.

Installed copies are plain copies: after changing a file here, run `bootstrap.ps1` again (it backs up what it
replaces under `_backup\<time>\`). `check.ps1` reports installed copies that differ from the repo.
