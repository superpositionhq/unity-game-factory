# unity-game-factory

Game-**creation** data: how a game gets made, step by step, with the finished project as ground truth.

We build new 3D games in Unity 6.3 LTS (Universal Render Pipeline) and record the creation as it happens: real
editor operations with timestamps, code commits, every tool call, prompt and reply of the sessions that build the game,
and recorded playtests of each scenario by an in-game bot (screen video, game audio and inputs). Every part of that is
here; the dataset packager is a first version that does not take the gameplay videos and the replay scripts yet
([AGENTS.md](AGENTS.md), "What is here and what is coming").

**Priorities (user decision).** What ships is what matters, in this order: the game plays; the game builds (editor and
the Windows release player); the dataset holds the replay scripts and the git log. The AutoPlay bot should still play
like a human (human-like input, aim and camera), but bot work never blocks a release: one recorded scenario per game
(one video) that shows the game running is enough, whatever the result (win/lose/timeout is metadata). No tuning for
win rates, seed sweeps or "clean" runs, and no re-runs or re-recordings to improve how the bot plays. No retest loops:
every GPU or editor run costs the shared machine and holds up delivery, so run the minimum once and report; re-run only
when the user asks. Game-session work never blocks dataset packaging or sharing.

## Getting started

**Before every new game, update unity-game-factory:** `git -C <UGF_ROOT>\unity-game-factory pull`, then
`powershell -ExecutionPolicy Bypass -File <UGF_ROOT>\unity-game-factory\machine\bootstrap.ps1` so the skills your
agent reads are the new ones. The tools, task rules and validators change often; a game made with old ones can fail
the Lab's checks. A game already in progress keeps its own copies of the template's files: bootstrap adds the live
creation replay to its post-commit hook, and a game made before the AutoPlay drop-in gets it with one run of
`powershell -ExecutionPolicy Bypass -File <UGF_ROOT>\unity-game-factory\tools\unity-pipeline\autoplay\install.ps1 -Game <UGF_ROOT>\games\<slug>`
([docs/autoplay-contract.md](docs/autoplay-contract.md), "Getting the drop-in").

On a fresh Windows 11 PC (8+ threads, 16 GB RAM or more, 200 GB free; an NVIDIA GPU only for recording), with a
GitHub account in `<org>` (the organisation that owns this repo and the private `unity-game-<slug>` repos), a Unity ID
with a licence (Unity Personal where its terms allow, otherwise the seat the org gives you) and an account for the
coding agent (Claude Code, or OpenAI Codex CLI with a ChatGPT account or API key):

1. Get `machine/setup.ps1` (Download ZIP on github.com, or `gh api`; [docs/new-machine.md](docs/new-machine.md)) and
   run the one command: `powershell -ExecutionPolicy Bypass -File setup.ps1 -Org <org>` (add `-Agent codex` or
   `-Agent both`; it asks otherwise). It installs the toolchain (Unity Hub included, and the Codex CLI for Codex)
   through winget, asks before changing Windows settings, signs in to GitHub (and Codex), clones this repo into the
   root, runs `machine/bootstrap.ps1` (which asks before installing the recording hooks) and `machine/check.ps1`, and
   ends with a PASS / TODO list.
2. Do the TODOs only you can do (sign in to Unity Hub and activate a licence, the Unity 6.3 LTS editor with Windows
   Build Support (IL2CPP), the NVIDIA driver, the Asset Store, and signing in to Claude Code or Codex) and run setup
   again until nothing is left.
3. Start the first session: solo in a terminal in the root (`claude`, or `codex -s danger-full-access`), one game with
   [docs/briefs/solo-game.md](docs/briefs/solo-game.md).

## How a game goes from idea to dataset

1. **Story bible and design doc**: `docs/games/<slug>.md` (pitch, systems, scenes, scenarios, art and story).
2. **New project**: `templates/new-game.ps1` creates `%UGF_ROOT%\games\<slug>` from the Unity 6.3 LTS template: the
   AutoPlay drop-in (`Assets/AutoPlay/`) and the scenario list, `ReplayConfig.json` (`"live": true`),
   `Scripts/unity.ps1`, hooks that record every action and commit and start the live replay, the first editor open
   (packages, URP, TextMeshPro, player settings), a private GitHub repo.
3. **Build**: the session (Claude Code or Codex) follows the `unity-commit-always`, `unity-game-session` and
   `unity-sound` skills; every action is recorded (`workflow.jsonl`, the action hooks of either agent, git history).
4. **Creation replay in the background**: after every commit, the post-commit hook starts the live replay
   (`tools/unity-replay`, `unity_replay.py live`). It replays the new commits into an isolated copy of the project at
   low priority and checks them against the commit. Anything that keeps the history from replaying comes back to the
   session at its next commit ([docs/unity-replay.md](docs/unity-replay.md), section 3).
5. **AutoPlay, the framing check, then the recording queue**: once scenario 1 plays, the game wires the drop-in and its
   bot ([docs/autoplay-contract.md](docs/autoplay-contract.md)), tests one run by hand (`Scripts/unity.ps1 autoplay`,
   `tools/unity-pipeline/validate-run.ps1`), tags `milestone/autoplay-<n>` and sends the coordinator its framing
   screenshots. The coordinator queues the recording (`tools/unity-pipeline/enqueue.ps1`): the release player of the
   commit, one recorded run per scenario, one gameplay mp4 each ([docs/unity-pipeline.md](docs/unity-pipeline.md)).
6. **Scrub and privacy**: no user names, machine paths or tool names in anything that ships (the packager's scrub rules
   and scan, the release build's leak scan; `tools/validate-game.py` checks a repo's tracked text for the names).
7. **Dataset v1**: `tools/package-dataset.py` writes the dataset and the repo's `Dataset/`. The recorder makes the
   gameplay videos and the creation replay's release run (`unity_replay.py release`: with the live replay current,
   only the last commits and a full final check remain) makes `ReplayScripts/`; until the packager takes both, it
   writes `games\<slug>\Dataset.pending.zip`, and with them `Dataset.zip`.

## Dataset format (layout v1, all games)

Every game is delivered in **dataset layout `unity-dataset-layout/v1`** ([docs/game-format.md](docs/game-format.md)):
the creation record (`git.log`, `workflow.jsonl` with the person's directions, `ReplayScripts/`, the full git history
and the recorded sessions in `History/`), the brief and design doc, the game's tasks, the project, per-scenario gameplay
videos, README screenshots and the built player:

```
<game>/                          games\<game>\Dataset.zip (store content included; git-ignored)
  README.md
  git.log
  workflow.jsonl                 editor operations + user.direction rows (the person's directions)
  Brief/                         brief.md (the original brief), design.md (design doc, story bible, status)
  History/                       <game>.bundle (main up to the release, and each task's start branch) + lfs/objects/ (every LFS object) + sessions/ (every prompt, reply and tool call); not in the repo Dataset/
  Tasks/                         the game's tasks, each <name>/task.json (agent) + grader.json; from the tasks branch
  UnityProject/                  not in the repo Dataset/
  ReplayScripts/                 the creation replayed headless, with its verification report
  Gameplay/<game>_S<n>.mp4       one video per recorded scenario of the release version (one is enough), game audio muxed
  Screenshots/                   the README's hero and gallery
  Build/                         the Windows release player, no .pdb; not in the repo Dataset/
  manifest.json
```

Each game repo keeps the same delivery in `Dataset/`, minus `UnityProject/`, `Build/`, `History/` and `Tasks/` (its
tasks live in `Tasks/` on the repo's orphan `tasks` branch, never on main). The game repo itself follows the same
format's repo rules (one `assets.manifest.json` format, every asset committed with its `.meta`). Machine-readable:
[docs/game-format-v1.json](docs/game-format-v1.json), [docs/dataset-layout-v1.json](docs/dataset-layout-v1.json),
[docs/schemas/](docs/schemas/). Build it with `python tools/package-dataset.py <slug>`: today it writes
`Dataset.pending.zip`, without `Gameplay/` and `ReplayScripts/`; before its first run a repo's `Dataset/` stays as the
template made it. Check a repo and its datasets with `python tools/validate-game.py <repo>` (or `--dataset <zip>`); its
"not packaged yet" warning is expected before the packager's first run.

## Read first

- [docs/autoplay-contract.md](docs/autoplay-contract.md): what each game implements so a bot can play and record it
  (the AutoPlay drop-in, its install step for older games, the hand test).
- [docs/unity-pipeline.md](docs/unity-pipeline.md): Unity editor and player runs (`Scripts/unity.ps1`), the
  machine-wide job slots, the build and gameplay recording pipeline (`tools/unity-pipeline/`) and its queue.
- [docs/unity-replay.md](docs/unity-replay.md): the creation replay (`tools/unity-replay/`), live after every commit
  and at release, and the rules that keep a game's history replayable.
- [docs/game-format.md](docs/game-format.md): the final game format (repo + Dataset.zip layout v1), its schemas and
  `tools/validate-game.py`.
- [docs/task-check.md](docs/task-check.md): checking a game's task on your own machine (`tools/task-check.py`: the
  start fails, the reference passes). [docs/task-try.md](docs/task-try.md) is internal: we run `tools/task-try.py` on
  submitted tasks to measure how long a strong agent takes; contractors don't run it.
- [docs/unity-pipeline.md, Dataset packager](docs/unity-pipeline.md#dataset-packager): the per-game dataset
  (`tools/package-dataset.py`) and its scrub.
- [AGENTS.md](AGENTS.md): what every session reads first (Claude Code through [CLAUDE.md](CLAUDE.md), Codex
  directly): the skills in `skills/` (unity-commit-always, unity-game-session, unity-sound, unity-write-tasks), the
  priorities, how the two agents differ, and the rules for agents working here (each with the failure behind it).
- [docs/new-machine.md](docs/new-machine.md): setting up another Windows machine (`machine/setup.ps1`, which runs
  `machine/bootstrap.ps1` and `machine/check.ps1`).
- [docs/briefs/](docs/briefs/README.md): the prompts that start a game session (solo and coordinated).

## Layout

```
tools/unity-pipeline/              release player from a commit, recorder, queue, run checker, stills, gameplay videos; autoplay/ = the AutoPlay drop-in
tools/unity-replay/                creation replay: per commit (live) and at release; ReplayScripts/ of the dataset
tools/package-dataset.py           a game's dataset: Dataset.pending.zip and the repo's Dataset/ (first version)
tools/task-check.py, task-try.py   a task checked on the engine; tried with a coding agent (internal) (task_check/)
tools/thread-stats.py              a thread's own commits counted against the task floors (git only)
tools/sfx.py                       sound effects for a game: search Freesound, fetch into the repo, measure (unity-sound skill)
machine/                           machine setup: setup (entry point), bootstrap/check, unity-heavy limiter, recording hooks, ffmpeg
templates/                         Unity 6.3 LTS game skeleton + new-game.ps1
skills/                            unity-commit-always, unity-game-session, unity-sound, unity-write-tasks (agent-neutral; bootstrap installs them for each agent)
docs/                              everything learned so far; docs/briefs/ = session prompts
```

Machine paths in docs are written `%UGF_ROOT%` (the UnityWork root: env `UGF_ROOT`, else
`%USERPROFILE%\.unity-game-factory\config.json`, else `%USERPROFILE%\UnityWork`); see
[machine/README.md](machine/README.md).

Full packages (tens of GB with the project snapshot) do not go in this repository.
