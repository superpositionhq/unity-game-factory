# Dataset

The built data for __TITLE__ (dataset layout v1), written by the dataset packager and committed with each release.
Until the packager's first run, leave this folder as the template made it (nobody assembles a dataset or
`Dataset.zip` by hand); the packager then replaces what is here, this file included. What it puts here:

| Path | What |
|---|---|
| `README.md` | what the game is, how it was made, how to open and play it, what each file is |
| `git.log` | every commit: message, author, date, full diff (binary files as path + sha256) |
| `workflow.jsonl` | every editor/code operation, recorded as it happened |
| `Brief/` | the original brief (`brief.md`) and the design doc with story bible and status (`design.md`) |
| `Screenshots/` | the README images |
| `manifest.json` | path, bytes and sha256 of every file |

Not packed yet, and listed as pending in `manifest.json` until they can be made:

| Path | What |
|---|---|
| `ReplayScripts/` | scripts that rebuild the project step by step, plus their verification report |
| `Gameplay/__SLUG___S<n>.mp4` | one gameplay video per scenario, release version |

The full delivery (a zip next to this folder, `Dataset.pending.zip` while those two are missing, never committed) also
has `UnityProject/` (the project at the release commit), `Build/` (the Windows release player), `History/` (the full
git history, and the creation sessions as recorded: every prompt, every reply and every tool call) and `Tasks/` (the
game's tasks, split into the agent's and the grader's halves); they are not duplicated here because the repo is the
project and its history, builds are not committed, and tasks live on the tasks branch.
