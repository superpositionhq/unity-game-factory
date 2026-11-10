# __TITLE__

__DESCRIPTION__

<!-- PLACEHOLDER, replace before the game is content-complete: 5-7 real gameplay stills in Docs/screenshots/ (jpg,
     in Git LFS, from validated recordings or the framing-gate screenshots), shown here as a hero image plus a
     captioned gallery, e.g.
       ![<title>](Docs/screenshots/hero.jpg)
       | ![](Docs/screenshots/<name>.jpg) | ![](Docs/screenshots/<name>.jpg) |
       |---|---|
       | <what it shows> | <what it shows> |
     Link only files that are committed, and check on github.com that every image renders. -->

## Play

- Engine: Unity __UNITY_VERSION__ (Unity 6.3 LTS), Universal Render Pipeline, Windows x64.
- Open the folder in Unity Hub with that editor version, or run the built `__PROJECT__.exe` from a release build.
- Controls: _fill in_.

## Scenarios

| # | Name | Start state | Win / lose |
|---|---|---|---|
| 1 | _fill in_ | | |

## Project layout

| Path | What |
|---|---|
| `Assets/Scripts/` | gameplay C# |
| `Assets/Editor/Steps/` | every editor step that was run to build the content, kept unchanged |
| `Assets/Editor/Tools/` | the project's editor tools: workflow log, first-open setup, player build |
| `Assets/` (other folders) | scenes, prefabs, materials, data assets, audio, imported packs (`Assets/ThirdParty/<Pack>/`) |
| `Packages/`, `ProjectSettings/` | package manifest and lock file, project settings |
| `Scripts/unity.ps1` | headless editor runs: setup, compile, editor steps, tests, player build, player runs |
| `workflow.jsonl` | one row per editor/code operation, written as it happened |
| `assets.manifest.json`, `Docs/ThirdPartyNotices.md` | third-party assets: source, licence, files used, changes |
| `Dataset/` | the built dataset (gameplay videos, screenshots, replay scripts) |
