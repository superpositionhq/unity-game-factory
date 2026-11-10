# Dataset

The built data for __TITLE__ (dataset layout v1), regenerated and committed with each release by the dataset
packager, which is not available yet: until it is, leave this folder as the template made it (nobody assembles a
dataset or `Dataset.zip` by hand). What the packager will put here:

| Path | What |
|---|---|
| `README.md` | what the game is, how it was made, how to open and play it, what each file is |
| `git.log` | every commit: message, author, date, full diff (binary files as path + sha256) |
| `workflow.jsonl` | every editor/code operation, recorded as it happened |
| `Brief/` | the original brief (`brief.md`) and the design doc with story bible and status (`design.md`) |
| `ReplayScripts/` | scripts that rebuild the project step by step, plus their verification report |
| `Gameplay/__SLUG___S<n>.mp4` | one gameplay video per scenario, release version |
| `Screenshots/` | the README images |
| `manifest.json` | path, bytes and sha256 of every file |

The full delivery (zip) also has `UnityProject/` (the project at the release commit), `Build/` (the Windows release
player), `History/` (the full git history) and `Tasks/` (the game's tasks, split into the agent's and the grader's
halves); they are not duplicated here because the repo is the project and its history, builds are not committed, and
tasks live on the tasks branch.
