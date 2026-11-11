# AGENTS.md — unity-game-factory: instructions for every session

This repo coordinates coding-agent sessions (Claude Code or OpenAI Codex CLI) that build Unity 6.3 LTS games
(`%UGF_ROOT%\games\<slug>`, private `<org>/unity-game-<slug>` repos, `<org>` = `github_org` in the machine config) and
turn them into game-creation datasets. `%UGF_ROOT%` is the machine root (env `UGF_ROOT`, else
`%USERPROFILE%\.unity-game-factory\config.json`, else `%USERPROFILE%\UnityWork`); see
[machine/README.md](machine/README.md). Claude Code reads this file through [CLAUDE.md](CLAUDE.md); Codex reads it
directly (and through `<root>\AGENTS.md`).

**Before every new game, update unity-game-factory:** `git -C <UGF_ROOT>\unity-game-factory pull`, then
`powershell -ExecutionPolicy Bypass -File <UGF_ROOT>\unity-game-factory\machine\bootstrap.ps1` so the skills your
agent reads are the new ones. The tools, task rules and validators change often; a game made with old ones can fail
the Lab's checks. A game already in progress keeps its own copies of the template's files: bootstrap adds the live
creation replay to its post-commit hook, and a game made before the AutoPlay drop-in gets it with one run of
`powershell -ExecutionPolicy Bypass -File <UGF_ROOT>\unity-game-factory\tools\unity-pipeline\autoplay\install.ps1 -Game <UGF_ROOT>\games\<slug>`
(its own commit; [docs/autoplay-contract.md](docs/autoplay-contract.md), "Getting the drop-in"). Every release starts
by running it again to ensure AutoPlay, a required step (unity-game-session skill, "Dataset", release step 1).

Skills (one source, [skills/](skills/); `machine/bootstrap.ps1` copies them to `~\.claude\skills\` for Claude Code and
`~\.agents\skills\` for Codex; read the `SKILL.md` named here before the work it covers, whichever agent you are). They
carry a `unity-` prefix so they install next to another factory's skills on a machine that also runs one:

- **unity-commit-always** ([skills/unity-commit-always/SKILL.md](skills/unity-commit-always/SKILL.md)): every session.
  Commit after every meaningful step, never end a turn with uncommitted work, every asset with its `.meta`, LFS for
  binaries, push only when the coordinator says.
- **unity-game-session** ([skills/unity-game-session/SKILL.md](skills/unity-game-session/SKILL.md)): sessions that
  build a game (art style, art, UI, story, naming, unity-heavy/GPU, editor steps, workflow.jsonl, AutoPlay, framing screenshots,
  dataset).
- **unity-sound** ([skills/unity-sound/SKILL.md](skills/unity-sound/SKILL.md)): sessions that build a game, whenever it
  needs sound (the design doc's audio direction, every UI, player, combat, world or ambience sound): finding, choosing
  and importing sound effects through `tools/sfx.py`.
- **unity-write-tasks** ([skills/unity-write-tasks/SKILL.md](skills/unity-write-tasks/SKILL.md)): sessions that write,
  move or review a game's tasks (the orphan `tasks` branch, never on main; at least 5 and up to about 10 per game,
  every one a long thread of multiple edits from the real history, never a single fix, hard: at most one of a game's
  tasks may be medium, none easy; seed and reference commits, observation-only briefs, milestones with deterministic
  probe checks).

**Only these skills (owner's rule, 2026-10-21).** Contractors and every agent session working for unity-game-factory
use the four skills above and no others. Never install, enable or invoke any other skill: not the person's own
personal or project skills, not a plugin's or a marketplace's skills, not the skills bundled with the agent (Claude
Code's built-in skills and slash-command skills, Codex's system skills), and not another factory's skills
(`commit-always`, `game-session`, `sound`, `write-tasks`) even when the machine has them installed. A skill the agent
offers by name or description that is not one of the four is ignored. Work no skill here covers is done by hand under
these rules, or asked about (the coordinator, or the person in a solo session). _(why: the recorded sessions are the
dataset, so how a game gets made must follow these rules only; another skill brings instructions and habits nobody
here reviewed into the creation record, and another factory's skills give answers for another engine to Unity
questions)_

Session briefs: [docs/briefs/](docs/briefs/README.md). New machine: [docs/new-machine.md](docs/new-machine.md).
Pipeline: [docs/unity-pipeline.md](docs/unity-pipeline.md). AutoPlay:
[docs/autoplay-contract.md](docs/autoplay-contract.md). Creation replay: [docs/unity-replay.md](docs/unity-replay.md).

**Priorities (user decision).** What ships is what matters, in this order: the game plays; the game builds (editor and
the Windows release player); the dataset holds the replay scripts and the git log. The AutoPlay bot should still play
like a human (human-like input, aim and camera), but bot work never blocks a release: one recorded scenario per game
(one video) that shows the game running is enough, whatever the result (win/lose/timeout is metadata). No tuning for
win rates, seed sweeps or "clean" runs, and no re-runs or re-recordings to improve how the bot plays. No retest loops:
every GPU or editor run costs the shared machine and holds up delivery, so run the minimum once and report; re-run only
when the user asks. Game-session work never blocks dataset packaging or sharing.

**AutoPlay's goal is NOT to win (user rule).** The bot only drives the game with human-like input so a recording shows
the game running. Never tune, fix or re-test the bot to win, score, finish, reach targets, resupply or avoid getting
stuck; losing, timing out or wandering is fine (metadata). Fix only game bugs (crash, hang, broken scene, missing art,
lighting, camera); then one AutoPlay run per scenario and the recording request, which only the coordinator queues
(`tools/unity-pipeline/enqueue.ps1`, [docs/unity-pipeline.md](docs/unity-pipeline.md#queue)). Every game has the
AutoPlay drop-in in `Assets/AutoPlay/`, unchanged (new games from `templates/new-game.ps1`, older ones through
`tools/unity-pipeline/autoplay/install.ps1`). Once scenario 1 plays, wire it and write the bot
([docs/autoplay-contract.md](docs/autoplay-contract.md), sections 6-7), test once with `Scripts/unity.ps1 autoplay`
and the run checker, tag `milestone/autoplay-<n>` and report to the coordinator (unity-game-session skill). No game is
released before AutoPlay is ensured: the current drop-in, every scenario wired, the bot, a passing hand test per
scenario and the milestone tag (unity-game-session skill, "Dataset", release step 1).

**Dataset.** Each game's full dataset is `games\<slug>\Dataset.zip`: the same name everywhere, git-ignored
(`/Dataset.zip`, `/Dataset.pending.zip`, `/.dataset/`), produced by the packager, never committed. The committed
`Dataset\` is the same minus `UnityProject/`, `Build/`, `History/` and `Tasks/`. The packager is
`python tools/package-dataset.py <slug>` ([docs/unity-pipeline.md](docs/unity-pipeline.md#dataset-packager)). It packs
the release commit with three products of it: the pipeline's release build, the gameplay video of each scenario's
first valid recording of that commit (`Gameplay/`) and the creation replay's package (`ReplayScripts/`, made by
`python tools/unity-replay/unity_replay.py release --game <slug>`, [docs/unity-replay.md](docs/unity-replay.md)). With
a video and the replay it writes `Dataset.zip` (a FAIL verdict too); while the replay is missing it writes
`Dataset.pending.zip` and lists it as pending; without a video it refuses (a game without a gameplay video is rejected
at upload). The release steps are in the unity-game-session skill ("Dataset").
Before its first run a game's `Dataset\` stays as the template made it, and nobody assembles a dataset by hand.

This checkout is shared by several sessions at once: stage explicit paths only and never commit another session's
changes.

## What is here and what is coming

| Part | State |
|---|---|
| skills (`skills/`) | available |
| machine setup, recording hooks, job limiter (`machine/`) | available |
| game template + `new-game.ps1` (`templates/`) | available |
| sound tool, workflow scrub, thread counter (`tools/sfx.py`, `scrub-workflow-rows.py`, `thread-stats.py`) | available |
| game format: the repo and dataset rules, their schemas, `validate-game.py`, `validate-dataset.ps1`, `split-tasks.py` | available: [docs/game-format.md](docs/game-format.md) |
| task verifier: the task schema, the TaskProbe package, `task-check.py`, `task-try.py` (`tools/task_check/`) | available: [docs/task-check.md](docs/task-check.md), [docs/task-probes.md](docs/task-probes.md) |
| AutoPlay drop-in (`tools/unity-pipeline/autoplay/`, `install.ps1`, `Scripts/unity.ps1 autoplay`) | available: [docs/autoplay-contract.md](docs/autoplay-contract.md) |
| recording pipeline: release build from a commit, recorder, queue, run checker, stills, gameplay videos (`tools/unity-pipeline/`) | available: [docs/unity-pipeline.md](docs/unity-pipeline.md) |
| creation replay, live after every commit and at release (`tools/unity-replay/`) | available: [docs/unity-replay.md](docs/unity-replay.md) |
| dataset packager (`tools/package-dataset.py`) | available: `Dataset.zip` from the release commit, its pipeline build, its recordings and its creation replay; `Dataset.pending.zip` while the replay is missing, no package without a recording ([docs/unity-pipeline.md](docs/unity-pipeline.md#dataset-packager)) |

Where a skill or doc names a part that is not available yet, it says what to do instead: do that, and report the rest
as open. Never stand in for a missing tool by hand or with another factory's tool.

## Agents

Both agents run the same skills, the same recording hooks and the same workflow; what differs:

| | Claude Code | Codex CLI |
|---|---|---|
| start | `claude` in `<root>` (reads `<root>\CLAUDE.md`) | `codex -s danger-full-access` in `<root>` (reads `<root>\AGENTS.md`) |
| skills | `~\.claude\skills\unity-*` (also offered by name) | `~\.agents\skills\unity-*` (`$<name>` or `/skills`; also offered by description) |
| recording hooks | `~\.claude\settings.json`: PostToolUse, PostToolUseFailure, Stop, UserPromptSubmit, SessionEnd | `~\.codex\hooks.json`: PostToolUse, Stop, UserPromptSubmit, SessionEnd (trusted in `config.toml`; `/hooks` shows them) |
| file edits in `actions.jsonl` | `Write` / `Edit` rows | `apply_patch` rows (the patch text) |
| permissions | as set in Claude Code (asks before commands by default) | `codex -s danger-full-access`: the default workspace sandbox blocks what game sessions need (Unity's `%LOCALAPPDATA%` and `%APPDATA%` caches and licence, the machine-wide job-slot mutexes, `git push` / `gh`) |
| transcript (backfill) | `~\.claude\projects\…\<session>.jsonl` | `~\.codex\sessions\YYYY\MM\DD\rollout-…-<session>.jsonl` |

Under Codex, the shell tool is recorded as `Bash` whatever shell ran the command. Read a skill by opening its
`SKILL.md` when the task matches, even if the agent did not offer it. Both agents' hooks also store every prompt the
person typed and every reply the model wrote (`messages.jsonl`, read from the session's transcript), and a dataset
carries them in `History/sessions/`. The person's directions are still `user.direction` rows that the session writes
itself (unity-commit-always skill).

Commands with Windows paths in these docs are written as PowerShell reads them. Typed in Git Bash (the shell of Claude
Code's Bash tool on Windows), put each Windows path in single quotes: bash drops unquoted backslashes, so
`C:\Users\<you>\UnityWork` arrives as `C:Users<you>UnityWork` and the command fails.

## Rules

Rules for agents working in this repository. Each rule says what went wrong without it (on earlier games, where
these were learned). Background is in `docs/`; keep this section to rules.

### Data

- Never commit a full package, a project snapshot, `git.log` with asset diffs, or package zips here; only
  tools and docs. _(failure: a package is tens of GB, far past GitHub's 100 MB file limit)_
- Keep this repository private. _(failure: the docs describe a private repository and its asset data)_
- Step reasons are the builder's own narration or notes, or the commit message; never write them with a
  model. _(failure: reasons written after the fact make a package a reconstruction rather
  than a record)_
- Anonymize authors as `dev_NN` and run the leak scan (real names, e-mails, `C:\Users\…`, `/Users/…`, `/home/…`)
  over every text file of a package before calling it done (`tools/package-dataset.py` does both, and refuses a
  package with a name left in a text file or a path: never make a package another way). _(failure: commit metadata
  and asset files can carry real names and machine paths)_
