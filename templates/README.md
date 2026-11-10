# templates/

## unity-game/ + new-game.ps1

Skeleton of a game repo for Unity 6.3 LTS. `new-game.ps1` instantiates it:

```powershell
powershell -ExecutionPolicy Bypass -File templates/new-game.ps1 -Slug island-survival -Path C:\Users\<you>\UnityWork\games\island-survival -Title "Island Survival" -Description "Stranded on a tropical island..."
```

It copies `unity-game/`, replacing `__PROJECT__` (PascalCase C# namespace and assembly prefix, also the exe name;
default from the slug), `__SLUG__`, `__TITLE__`, `__DESCRIPTION__` and `__UNITY_VERSION__` in names and contents;
writes the first `workflow.jsonl` row (`project.create`); runs `git init -b main` + `git lfs install --local`; adds the
commit recorder to `post-commit` (`machine/install-git-hook.ps1`); makes the first commit; runs the first editor open
(`Scripts/unity.ps1 setup`) and commits what it made, when the editor is installed (`-NoSetup` skips it); and creates
the private GitHub repo `<org>/unity-game-<slug>` (`github_org` in the machine config, or `-Org`) as `origin` without
pushing (`-NoGitHub` skips that; an existing repo of that name is never linked). It refuses names containing
Superposition, game-factory, Claude, Anthropic or OpenAI, and titles with quotes or backslashes (they land in C#
string literals).

The editor version: `-UnityVersion`, else the newest installed `6000.3.*` editor (Unity Hub), else the config's
`unity_version` (default `6000.3.26f1`).

What the skeleton carries, and why:

| File | Why |
|---|---|
| `ProjectSettings/ProjectVersion.txt` | pins the editor (6.3 LTS); every tool opens the project with exactly this version |
| `ProjectSettings/EditorSettings.asset` | Force Text serialization and Visible Meta Files, so scenes, prefabs and materials diff as YAML and every GUID is in git; Unity fills the other fields on the first open |
| `Packages/manifest.json` | the built-in modules only; the first open adds URP, Input System, Cinemachine, uGUI, NavMesh, Timeline and Test Framework **by name**, so the Package Manager picks the versions that ship with the editor (no hand-written version that may not exist) |
| `Assets/Editor/Tools/` (`<P>.EditorTools` assembly) | `WorkflowLog.cs` (a step's `workflow.jsonl` row, with the step's own file and sha256), `ProjectSetup.cs` (packages; player and editor settings), `BuildPlayer.cs` (Windows x64 player, IL2CPP release / Mono development, the backend setting put back afterwards) |
| `Assets/Editor/Tools/Urp/` (`<P>.EditorTools.Urp`) | `UrpSetup.cs`: the URP renderer and pipeline asset, made the default and assigned to every quality level; compiled only once URP is installed (`defineConstraints` `HAS_URP`), so the project compiles before the packages are added |
| `Assets/Editor/Steps/README.md` | where editor steps go and the rules that keep them replayable |
| `Scripts/unity.ps1` | `setup`, `compile`, `step`, `test`, `build`, `play`: headless Unity and player runs through the machine's job limiter, logs in `Logs/unity-ps1/` |
| `.gitignore` | root-anchored Unity output only (`/Library/`, `/Temp/`, `/Logs/`, `/UserSettings/`, `/Build/`, generated `*.csproj`/`*.sln`, ...) and local results: everything else is committed |
| `.gitattributes` | `* text=auto`, Unity YAML as LF text, every binary type in LFS case-insensitively, and the Unity `.asset` files that stay binary (lighting, NavMesh, terrain data) |
| `Docs/ThirdPartyNotices.md`, `assets.manifest.json`, `Docs/screenshots/` | third-party credits; the asset manifest (`assets-manifest/v1`); README images |
| `Dataset/` | the dataset placeholder (`Gameplay/`, `Screenshots/`, `ReplayScripts/`, README) |

Not in the skeleton yet: the AutoPlay drop-in (docs/autoplay-contract.md describes the contract; the shared
implementation comes with the recording pipeline) and the replay configuration (comes with the creation replay).

`workflow.jsonl` conventions (schema `unity-workflow/v0`, one row per operation at the moment it happens, id prefix
per game, row ids in commit messages) are in the unity-commit-always and unity-game-session skills (`skills/`).
