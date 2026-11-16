# __TITLE__

__DESCRIPTION__

<!-- PLACEHOLDER, replace before the game is content-complete: 5-7 real gameplay stills in Docs/screenshots/ (jpg,
     in Git LFS, from the stills of the game's validated recordings or the framing-gate screenshots), shown here as a
     hero image plus a captioned gallery, e.g.
       ![<title>](Docs/screenshots/hero.jpg)
       | ![](Docs/screenshots/<name>.jpg) | ![](Docs/screenshots/<name>.jpg) |
       |---|---|
       | <what it shows> | <what it shows> |
     Link only files that are committed, and check on github.com that every image renders. -->

## Play

- Engine: Unity __UNITY_VERSION__ (Unity 6.3 LTS), Universal Render Pipeline. An Android phone game (arm64), held in
  __ORIENTATION__ and played by touch.
- Install the built `__PROJECT__.apk` on an Android phone (Android 8.0 or later), or, on a Windows PC, open the folder in
  Unity Hub with that editor version or run the built `__PROJECT__.exe`: the same game in a window of the phone's size
  (__PHONE_WIDTH__x__PHONE_HEIGHT__), where the mouse is the finger.
- Controls (touch): _fill in_.

## Scenarios

| # | Name | Start state | Win / lose |
|---|---|---|---|
| 1 | _fill in_ | | |

## Project layout

| Path | What |
|---|---|
| `Assets/Scripts/` | gameplay C#, with `Scenarios.cs`: the scenario list (scenario n's scene and name), and `Phone.cs`: the phone's size and orientation |
| `Assets/AutoPlay/` | the AutoPlay drop-in, unchanged: scripted play by an in-game bot for the gameplay recordings |
| `Assets/Editor/Steps/` | every editor step that was run to build the content, kept unchanged |
| `Assets/Editor/Tools/` | the project's editor tools: workflow log, first-open setup (with the mobile setup), the Windows player build and the Android APK build |
| `Assets/` (other folders) | scenes, prefabs, materials, data assets, audio, imported packs (`Assets/ThirdParty/<Pack>/`) |
| `Packages/`, `ProjectSettings/` | package manifest and lock file, project settings |
| `Platform.json` | what the game is made for: an Android phone, held in __ORIENTATION__ |
| `Scripts/unity.ps1` | headless editor runs: setup, compile, editor steps, tests, player build, player runs, AutoPlay runs |
| `workflow.jsonl` | one row per editor/code operation, written as it happened |
| `ReplayConfig.json` | the settings of the creation replay, which rebuilds the project from its history |
| `assets.manifest.json`, `Docs/ThirdPartyNotices.md` | third-party assets: source, licence, files used, changes |
| `Dataset/` | the built dataset (git log, creation record, brief, gameplay videos, replay scripts, screenshots), written by the dataset packager |
