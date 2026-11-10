# Game format (Unity)

What a finished Unity game is: its repo, and the dataset made from it. The validator that checks this
(`tools/validate-game.py`) comes with the task verifier; until then this page is the checklist.

## The game repo (`<org>/unity-game-<slug>`, private)

| Path | Required | What |
|---|---|---|
| `Assets/` | yes | everything the game is made of, **every file with its `.meta`**; store packs in any folder (e.g. `Assets/ThirdParty/<Pack>/`), never git-ignored |
| `Assets/Editor/Steps/` | yes | every editor step that ran, unchanged after it ran |
| `Packages/manifest.json`, `Packages/packages-lock.json` | yes | the packages, versions locked |
| `ProjectSettings/` | yes | `ProjectVersion.txt` on `6000.3.x`; Force Text serialization and Visible Meta Files in `EditorSettings.asset`; `companyName` the game's own name |
| `Scripts/unity.ps1` | yes | from the template |
| `workflow.jsonl` | yes | `unity-workflow/v0` rows ([schemas/workflow-row.schema.json](schemas/workflow-row.schema.json)): ids `<prefix>-<n>` unique, `seq` strictly increasing, every `"direction"` naming an earlier `user.direction` row |
| `assets.manifest.json` | yes | `assets-manifest/v1` ([schemas/assets-manifest.schema.json](schemas/assets-manifest.schema.json)): every external asset, every listed file committed |
| `Docs/ThirdPartyNotices.md` | yes | credits, in step with the manifest |
| `Docs/screenshots/` | yes | 5-7 real gameplay stills (JPG, LFS) |
| `README.md` | yes | title, hero image and captioned gallery (every linked image committed), how to play, scenarios, layout |
| `Dataset/` | at release | the dataset minus `UnityProject/`, `Build/` and `History/` |
| `.gitattributes`, `.gitignore` | yes | the template's: every binary in LFS; only Unity's generated folders, build output and local dataset files ignored |

Never on main: `Tasks/` (the orphan `tasks` branch holds it, unity-write-tasks skill). Never anywhere in the repo: the
banned names (unity-game-session skill, "Names"), secrets, `Library/`, `Temp/`, `Logs/`, `UserSettings/`, `Build/`.

## The dataset (`games\<slug>\Dataset.zip`, git-ignored)

```
<game>/
  README.md
  git.log                        every commit: message, author (dev_NN), date, diff (binary files as path + sha256)
  workflow.jsonl                 editor operations + user.direction rows, scrubbed
  Brief/                         brief.md (the original brief), design.md (design doc, story bible, status)
  History/                       <game>.bundle (every branch but tasks) + lfs/objects/
  Tasks/                         the game's tasks, each <name>/task.json (agent) + grader.json; from the tasks branch
  UnityProject/                  the project at the release commit (no Library/)
  ReplayScripts/                 the creation replay and its verification report
  Gameplay/<game>_S<n>.mp4       one video per scenario of the release version, game audio muxed
  Screenshots/                   the README's hero and gallery
  Build/                         the Windows release player, no .pdb
  manifest.json                  path, bytes and sha256 of every file
```

The packager, the replay and the gameplay recording that fill it come with the pipeline
([unity-pipeline.md](unity-pipeline.md)).
