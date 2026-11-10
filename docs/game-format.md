# Game format v1

The final format of a Unity game: its **repo** at the release commit and its **dataset** (`Dataset.zip`, layout
`unity-dataset-layout/v1`). It is the same for every game, whether a game session here made it or a contractor
delivered it. What the RL environment needs from a game (tasks that start from any commit, the person's directions,
the brief) is in it.

| Machine-readable | What |
|---|---|
| [game-format-v1.json](game-format-v1.json) | the rules for the repo and the dataset (this page in JSON) |
| [dataset-layout-v1.json](dataset-layout-v1.json) | the dataset's entries, names, video format, manifest keys, README sections |
| [schemas/dataset-manifest.schema.json](schemas/dataset-manifest.schema.json) | `manifest.json` |
| [schemas/workflow-row.schema.json](schemas/workflow-row.schema.json) | one row of `workflow.jsonl` (`unity-workflow/v0`) |
| [schemas/replay-report.schema.json](schemas/replay-report.schema.json) | `ReplayScripts/Verification/report.json` |
| [schemas/assets-manifest.schema.json](schemas/assets-manifest.schema.json) | the repo's `assets.manifest.json` (one format for every game) |
| [schemas/game-task.schema.json](schemas/game-task.schema.json) | one task (`GameTask`, game-task/1; probe checks: [task-probes.md](task-probes.md)) |

## Validate

```bash
python tools/validate-game.py <games>/<slug>
```
```bash
python tools/validate-game.py --dataset <path to Dataset.zip>
```

The first checks the repo and its tasks branch, then its `Dataset/` and `Dataset.zip`; the second checks a dataset
alone, the way a consumer receives it. Both run `tools/validate-dataset.ps1` (layout, sizes, sha256, videos) on
Windows. Verdict **VALID** or **INVALID** (exit 0 / 2); warnings never change it. After the verdict it prints one line
per finding: `x` an error, `!` a warning, `-` a note, then what it is about (`repo`, `repo: README`, `repo: Tasks`,
`dataset`, ...). Options: `--quick` (do not unpack the history), `--no-hash`, `--no-layout`, `--no-zip` (skip the
repo's `Dataset.zip`), `--json <file>`, `--quiet` (print only errors and warnings). Standard library Python 3.10+.

## The repo

Everything needed to rebuild the game from the repo alone, tracked in git (binaries in Git LFS):

| Path | Rule |
|---|---|
| `Assets/` | everything the game is made of, at least one scene (`.unity`); store packs in any folder (e.g. `Assets/ThirdParty/<Pack>/`), never git-ignored; **every file and folder with its `.meta`** (below) |
| `Assets/Editor/Steps/` | every editor step that ran, unchanged after it ran |
| `Packages/manifest.json`, `Packages/packages-lock.json` | the packages, versions locked; an embedded package `Packages/<name>/` with its `.meta` files |
| `ProjectSettings/ProjectVersion.txt` | `m_EditorVersion: 6000.3.x` (Unity 6.3 LTS) |
| `ProjectSettings/EditorSettings.asset`, `ProjectSettings/VersionControlSettings.asset` | `m_SerializationMode: 2` (Force Text) in the first; `m_Mode: Visible Meta Files` in the second, where Unity keeps the mode since 2020.1 (`m_ExternalVersionControlSupport` in EditorSettings is the obsolete place and isn't read) |
| `ProjectSettings/ProjectSettings.asset` | the player settings (the template sets `companyName` to the game's title) |
| `Scripts/unity.ps1` | from the template |
| `workflow.jsonl` | the creation record, one row per operation, written when it happened (`unity-workflow/v0` rows: ids unique, `seq` strictly increasing, every `"direction"` naming an earlier `user.direction` row) |
| `README.md` | hero image + captioned gallery of 5-7 real gameplay stills, every image committed (no gameplay image is an error; fewer or more than 5-7 is a warning) |
| `Docs/screenshots/` | the README's stills (JPG, LFS) |
| `assets.manifest.json` | every external asset in `assets-manifest/v1` (below) |
| `Docs/ThirdPartyNotices.md` | credits and licences |
| `.gitattributes` | the template's: every binary type in Git LFS (and `LightingData`, `NavMesh*`, `TerrainData*` `.asset` files under `Assets/` by path: `ProjectSettings/NavMeshAreas.asset` is YAML); Unity's YAML (`.unity`, `.prefab`, `.mat`, `.meta`, `.controller`, `.anim`, ...) and C# stay plain git text. A binary type in plain git, or YAML in LFS (an `.asset` Unity wrote as YAML included), is an error; binary content under any other name in plain git is a warning |
| `.gitignore` | the template's: Unity's generated folders (`Library/`, `Temp/`, `Obj/`, `Logs/`, `UserSettings/`, `Build/`, `Builds/`) and `/Dataset.zip`, `/Dataset.pending.zip`, `/.dataset/` ignored; nothing the game is made of (`Assets/` at any depth, a pack's own `Build/` or `Library/` folder included, `Packages/`, `ProjectSettings/`, `RawAssets/`, `Docs/`, `Scripts/`) |
| `Dataset/` | the dataset minus `UnityProject/`, `Build/`, `History/` and `Tasks/` (written by the packager, which is not available yet: until it is, the folder stays as the template made it) |

Never tracked: Unity's generated folders and build output at the root, the generated `*.csproj` / `*.sln`, Unity
licence files (`*.ulf`), secrets; `Tasks/` on main (below).

**Every asset with its `.meta`.** Every tracked file and folder under `Assets/` and under an embedded package
`Packages/<name>/` has its `.meta` tracked, and every tracked `.meta` has its file or folder (a folder counts as tracked
when a file under it is). An asset without its `.meta` gets a new GUID on the next import and every scene, prefab and
material that refers to it breaks; a `.meta` without its asset, or the `.meta` of an empty folder (git cannot hold the
folder), is an orphan Unity deletes. Each `.meta` names a GUID of its own: one without a GUID, or two with the same
GUID (a folder copied with its `.meta` files), is an error. Names Unity skips on import need none: hidden (`.name`),
`name~` (`Samples~`, `Documentation~`), `cvs`, `*.tmp`, and everything under them. `Packages/manifest.json`,
`ProjectSettings/` and the repo's own files have no `.meta`.

**Tasks live on the orphan `tasks` branch, never on main.** The same repo has a branch `tasks` that shares no history
with main: `Tasks/<game>-<kind>-<slug>.json` (one task each in the task format `GameTask`,
[schemas/game-task.schema.json](schemas/game-task.schema.json), `"engine": "unity-6000.3"`; at least one, up to about
10, every one a long thread of multiple edits; written with the `unity-write-tasks` skill), a short `README.md`,
optionally `tasks-workflow.jsonl`. It is checked out as a git worktree outside the game folder (e.g.
`<root>/tasks/<slug>`), committed and pushed there. Task work never enters the game's history: main never tracks
`Tasks/` and never references the tasks branch, the recording hooks ignore commits on it, and the delivered history
leaves it out. Seeds (`seed.commit`, `seed.reference`) point at commits of main's history, or of the task's own start
branch `starts/<task name>`.

No tool, vendor or owner names anywhere in the repo's text: Superposition, unity-game-factory and "game factory" in
any other spelling (`gamefactory`, `game_factory`), Claude, Anthropic, OpenAI (the validator scans tracked text files;
the packager, not available yet, will scan binaries too, so keep the names out of binary files yourself). The build
machine's account name (machine paths carry it) counts too: the validator reads it at run time and enforces it
everywhere except in scripts that already ran (`Scripts/`, `Assets/Editor/Steps/`, and
`.ps1`/`.psm1`/`.py`/`.sh`/`.bat`/`.cmd` files anywhere), which stay unchanged: the packager (not available yet) will
scrub them in every delivery. That includes
`workflow.jsonl`: it is append-only except that a row naming a banned term is edited in place to a neutral word or
placeholder, nothing else changed, with one `log.correct` row appended (`params {rows, what}`) and the edited rows
named in the commit message: `python tools/scrub-workflow-rows.py <repo>` (dry run), then `--apply`.

**Store content.** Store packs may sit in any folder under `Assets/` (or `RawAssets/` for import sources, or an
embedded package under `Packages/`): what matters is that every file the game uses is committed, so a clone opens and
builds the game. The repo stays private. `assets.manifest.json` lists each external asset once:

```json
{ "schema": "assets-manifest/v1", "project": "MyGame", "assets": [
  { "name": "Modular Warehouse", "source": "Unity Asset Store", "url": "https://assetstore.unity.com/packages/...",
    "licence": "Standard Unity Asset Store EULA", "version": "2.1", "store": true,
    "files": ["Assets/ThirdParty/Warehouse/"], "used_for": "level kit", "changes": "materials re-tinted" } ] }
```

Every asset needs an https `url` (its listing or source page), except one made in-house by the studio (e.g. the
studio's own earlier project): that one has `"origin": "studio"` and a short `description` (what it is, where it comes
from inside the studio) instead of a url.

`files` are repo paths under `Assets/`, `Packages/` or `RawAssets/`; one ending in `/` stands for every file under it.
Each must be committed (repo check) and be inside `UnityProject/` of `Dataset.zip` (dataset check). Registry packages
(`com.unity.*` in `Packages/manifest.json`) and content made by the game's own code or editor steps are not listed.

## The dataset (`unity-dataset-layout/v1`)

`<repo>\Dataset.zip`, one top folder `<game>/`, made by the packager (not available yet:
[unity-pipeline.md, Dataset packager](unity-pipeline.md#dataset-packager) holds the plan; until it is here a repo's
`Dataset/` stays as the template made it):

| Entry | In the repo's `Dataset/` | What |
|---|---|---|
| `README.md` | yes | the game, how to play, open, replay and restore it; sections in the order of the layout file |
| `git.log` | yes | every commit up to the release, oldest first: message, `dev_NN` authors, dates, full text diff; binaries as path + sha256 |
| `workflow.jsonl` | yes | the creation record; **the person's directions are `user.direction` rows** (they replace conversation transcripts) |
| `Brief/` | yes | `brief.md`, the brief as given; `design.md`, the design doc with story bible and status |
| `History/` | no | `<game>.bundle` (every commit of every ref except the tasks branch) and `lfs/objects/<aa>/<bb>/<sha256>` (every Git LFS object of every commit) |
| `Tasks/` | no | the game's tasks, each split: `Tasks/<name>/task.json` (the agent's part) and `Tasks/<name>/grader.json` (milestones, `seed.reference`), plus a generated `README.md` (`tools/split-tasks.py`) |
| `UnityProject/` | no | the project at the release commit (`Assets/` with every `.meta`, `Packages/`, `ProjectSettings/` on 6000.3; no `Library/`), store content included |
| `ReplayScripts/` | yes | the creation replayed headless, with `Verification/report.json` (required for complete; its verdict PASS or FAIL is metadata) |
| `Gameplay/<game>_S<n>.mp4` | yes | at least one scenario video of the release version (one recorded scenario is enough; videos of other scenarios already recorded may be included), 1920x1080 h264 + aac |
| `Screenshots/` | yes | the README's images |
| `Build/` | no | the Windows release player (x64, non-development), no `.pdb` |
| `manifest.json` | yes | metadata, `history`, `brief`, `tasks`, `build`, and path / bytes / sha256 of every file except the content-addressed `History/lfs/objects/` |

**The history is rewritten for delivery** (the game repos are not changed): authors and committers become `dev_NN`,
agent trailer lines go, the scrub rules apply to every message and text blob. Commit ids therefore differ from the
private repo; the dataset uses the delivered ids everywhere (`manifest.json` `commit`, `git.log`, `ReplayScripts/`,
the tasks' seeds), and the packager keeps the old -> new map next to the package. Restore a commit:

```bash
git clone History/<game>.bundle <game>
```

then copy `History/lfs` into `<game>/.git/lfs`, `git lfs install --local`, `git checkout <commit>`, `git lfs checkout`.

**Tasks.** A game is complete when its repo's orphan `tasks` branch has `Tasks/`: tasks an agent can be given on
this game (a bug fix from its history, a correction from a person's direction, a feature, a look or content change),
in the task format (`GameTask`, game-task/1), one file per task named `<game>-<kind>-<slug>.json` with `name` equal to
the file name. About 10 are recommended; the count is reported, and only a game with none fails. The tasks branch is
the single source: tasks are loaded as `Tasks/*.json` from the repos' tasks branches. How to write them: the
`unity-write-tasks` skill. The validator reads the tasks from `tasks` (else `origin/tasks`) and checks each against
[schemas/game-task.schema.json](schemas/game-task.schema.json) (the task format; probe checks:
[task-probes.md](task-probes.md)) and the rules the schema cannot express (probe rules, play arguments, thresholds
that are never literal, the no-op rule), that its seed is on this game and its seed commits are ancestors of main's
head or of the task's own start branch `starts/<task name>` and Unity `6000.3.x` projects as committed
(`ProjectSettings/ProjectVersion.txt`), that the branch shares no history with main, and that main tracks nothing
under `Tasks/`. It also holds each task to the bar of a long thread: `medium` or `hard`, tagged `long-thread`, with
`seed.reference`, at least 3 required outcome probes outside `still_works`, and from start to reference at least 5
game files (`Assets/`, `Packages/`, `ProjectSettings/`; an editor step or a `.meta` is not one), 100 code lines and 2
systems, and for a seed on main 4 commits that change the game (`tools/validate-game.py` holds the numbers).

In a dataset (`unity-dataset-layout/v1`) the packager copies the tasks from the tip of the tasks branch, maps each
seed's commits through the history rewrite, scrubs them, and splits each into `Tasks/<name>/task.json` (what the agent
may see: name, title, instruction, engine, seed without its reference, `play_scene`, `play_args`, `player`, asset
packs, difficulty, tags, limits) and `Tasks/<name>/grader.json` (the grader's half: `milestones` with their probes,
rubrics, judge and code-judge questions and log patterns, and `seed.reference`); merging the two gives the task.
`Tasks/README.md` explains it. The validator checks the split, that each merged task is valid on this game, and that
its seeds are commits of `History/`.

**The harness rule.** An agent given a task starts from a history-less snapshot of the game at `seed.commit`, with
`Tasks/`, `History/` and `Dataset/` removed (every task's answers are in them, and the reference fixes are in the
history); it sees only the brief and that snapshot. The grader's half never reaches the agent.

**Complete vs pending.** `status` is `complete` when every entry is there, `ReplayScripts/` with its
`Verification/report.json` included; `pending` while `ReplayScripts/` or `Gameplay/` is missing (listed in `pending`;
the zip is then `Dataset.pending.zip`). The replay is required but need not pass (user rule): a FAIL verdict is
metadata, like a gameplay run's result: manifest `replay_verification.pass` false (equal to the report's
`verdict.pass`) and the README says FAIL.

## For a contractor

Deliver the repo (private, with Git LFS) with the content below. The packager is not available yet: it will build the
dataset from the repo, so don't assemble a `Dataset.zip` by hand.

1. The repo rules above, every asset with its `.meta`; `assets.manifest.json` in `assets-manifest/v1`.
2. `workflow.jsonl` from the first operation, with every direction you were given as a `user.direction` row
   (neutral wording, what and why) before the work it caused, and `"direction": "<id>"` on the rows that act on it.
3. `Brief/brief.md` (the brief you were given) and `Brief/design.md` (your design doc).
4. Your game's tasks in `Tasks/` on an orphan `tasks` branch of the repo, never on main (about 10; the
   `unity-write-tasks` skill), each seeded on commits of main's history (or its own `starts/<task>` branch).
5. `python tools/validate-game.py <repo>` VALID. Its warning "Dataset/ has no manifest.json: not packaged yet" is
   expected until the packager is here; once a `Dataset.zip` exists, the same for the `Dataset.zip`.

Your agent sessions use only the unity-game-factory skills (`unity-commit-always`, `unity-game-session`,
`unity-sound`, `unity-write-tasks`, installed by `machine/setup.ps1`): never install, enable or invoke any other
skill, whether your own personal or project skills, a plugin's or marketplace's, or one bundled with the agent
(AGENTS.md, "Only these skills"). The recorded sessions are the dataset, so the game is made under these rules alone.
