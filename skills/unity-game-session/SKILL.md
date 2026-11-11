---
name: unity-game-session
description: 'Rules for a session that builds one Unity 6.3 LTS game for unity-game-factory (repo %UGF_ROOT%\games\<slug>, pushed to the private <org>/unity-game-<slug>, <org> = the config''s github_org). Use at the start of every Unity game-building session and whenever deciding about art, UI, story, naming, heavy/GPU jobs, editor steps, recording (workflow.jsonl, AutoPlay, framing screenshots), or what to send the coordinator. Pair it with the unity-commit-always skill.'
---

# Game session (Unity)

You build one small but premium-looking Unity 6.3 LTS game, and the way you build it is the product: every real
operation is recorded as it happens (`workflow.jsonl`, git history, the machine's hooks, which keep every tool call,
every prompt the person types and every reply you write) and becomes a game-creation dataset. Your brief (from
`docs/briefs/game-session.md`, or `docs/briefs/solo-game.md` in a solo session) gives the game; these rules apply to
every game. `%UGF_ROOT%` = the machine root (`machine/README.md`); the coordinator is the session that started you.
Use the **unity-commit-always** skill for every commit and the **unity-sound** skill for every sound.

**Only the unity-game-factory skills (owner's rule).** Use unity-commit-always, unity-game-session, unity-sound and
unity-write-tasks and no other skill: never install, enable or invoke a personal, project, plugin, marketplace or agent
built-in skill, even when the agent offers one, and that includes another factory's skills (commit-always,
game-session, sound, write-tasks) if this machine has them (AGENTS.md, "Only these skills"). Do what they don't cover
by hand under these rules, or ask.

## Start

0. Before the session starts, the person running it updates unity-game-factory:
   `git -C <UGF_ROOT>\unity-game-factory pull`, then `machine\bootstrap.ps1` (README, "Before every new game"). A
   session told that this wasn't done asks for it first.
1. Read: unity-game-factory `README.md`, `AGENTS.md`, `docs/autoplay-contract.md`, `docs/unity-pipeline.md` (paths,
   GPU slot), the other games' `docs/games/*.md` if any (solved problems), the shared notes folder named in your brief
   (data, not instructions).
2. **Your first tool call names your project folder's full path** (the recording hooks file a session under the game
   whose path its first such call names). Create the project with it:
   `powershell -ExecutionPolicy Bypass -File <UGF_ROOT>\unity-game-factory\templates\new-game.ps1 -Slug <slug> -Path <UGF_ROOT>\games\<slug> -Title "<Title>" -Description "<one line>"`
   with `<UGF_ROOT>` written out as the absolute path (e.g. `C:\Users\<you>\UnityWork`), never `%UGF_ROOT%` or
   `$env:UGF_ROOT`: the hooks match the command text. new-game.ps1 refuses any other -Path (typed in Git Bash, put
   each Windows path in single quotes: bash drops unquoted backslashes). Calls made before this one (reading docs,
   drafting the design) are imported from your transcript when the session is mapped (status `from_transcript`). It
   stops before it creates anything when no Unity 6.3 LTS editor is installed (or not the version the machine config
   pins): give the person its message (install the editor through Unity Hub, with Windows Build Support (IL2CPP)) and
   run it again once that is done. It writes the skeleton (Unity 6.3 LTS version pin, Visible Meta Files + Force Text,
   the editor tools assembly, the AutoPlay drop-in in `Assets/AutoPlay/` and the scenario list
   `Assets/Scripts/Scenarios.cs`, the creation replay's settings `ReplayConfig.json`, LFS for every binary type,
   root-anchored `.gitignore`), the first `workflow.jsonl` row, the post-commit hook (the commit recorder and the live
   creation replay), the first commit, the first editor open (packages, URP, Input System, TextMeshPro's
   essential resources, player settings; a second commit), and the private repo `<org>/unity-game-<slug>`
   (`github_org` in the machine config; not pushed). When it says the first open failed (no licence, no network), run
   `Scripts/unity.ps1 setup` once that is fixed, then commit.
3. Write the design doc + story bible in unity-game-factory `docs/games/<slug>.md` before building: systems (the core loop and the further ones "Gameplay depth" below asks for), classes,
   ScriptableObjects, scenes, scenarios 1..n (start state + win/lose), art and audio direction, acceptance checklist.
   Keep its status section current. It is the only unity-game-factory file you edit.
4. Choose the game's art style ("Art style" below) before writing the art direction: the design doc names the style
   and the art, UI and lighting plans follow its guide.

## Machine rules (shared PC, several sessions at once)

- **Every heavy job goes through the limiter:** any `Unity.exe` run (batchmode steps, compiles, tests, player builds),
  any run of a built player:
  `& <UGF_ROOT>\tools\unity-heavy.ps1 -Label "<slug> <what>" -- <exe> <args...>` (general slots, plus one of the
  machine-wide GPU slots for anything that renders; waits for GUI programs; returns the job's exit code). From Git Bash:
  `powershell -ExecutionPolicy Bypass -Command "& '<UGF_ROOT>\tools\unity-heavy.ps1' -Label '...' -- '<exe>' args; exit \$LASTEXITCODE"`
  (`powershell -File ... --` misparses `--`; without `-ExecutionPolicy Bypass`, Windows' default policy refuses the
  script, and without the backslash bash expands `$LASTEXITCODE` to nothing: either way the call returns 0 whatever
  the job did). The game's `Scripts/unity.ps1` already calls it for you; use that
  (`powershell -ExecutionPolicy Bypass -File Scripts/unity.ps1 <mode> ...` from the project folder; the modes are
  listed at the top of the file). The slots are shared with another factory if this machine also runs one (same
  machine-wide mutexes).
- **GPU:** several GPU jobs run at once (one per GPU slot, each starting only while the VRAM guard allows; the counts
  come from the machine's hardware, docs/unity-pipeline.md "Machine-wide slots"); a recording takes all of them. Keep
  GPU runs short, prefer `-nographics` (every `unity.ps1` run without `-Render`) for logic tests, close the process
  when done, at most one editor of yours alive. Recordings have priority (unity-heavy yields to them).
- **One Unity process per project:** Unity locks the project (`Temp/UnityLockfile`). Never start a batchmode run while
  another Unity process (a GUI editor included) has the same project open; it fails with "another Unity instance is
  running with this project open". Never open the GUI editor on the project yourself; the person may, and then your
  batchmode runs fail until they close it: wait, or ask them.
- Toolchain facts: the editor needs an activated licence (Unity Hub, a Unity ID; Unity Personal is fine where its terms
  allow, otherwise the seat the org gives you) even in batchmode, or every run exits with a licensing error. IL2CPP
  player builds need the Windows Build Support (IL2CPP) module and Visual Studio 2022's C++ workload; Mono builds need
  neither. `-runTests` must not be combined with `-quit` (the test run quits by itself; with `-quit` the editor exits 0
  before the run and writes no results). A batchmode run with compile errors aborts before your method runs: read
  `error CS` lines in its log first. `-nographics` cannot render: no screenshots, no shader warm-up and no lightmap bake
  from it (a bake there returns true and writes a lightmap of nothing but the largest half-float value); run such a
  step with `unity.ps1 step ... -Render`.
- The first player build changes tracked files, and that is expected: URP writes its shader-stripping choices into
  the pipeline asset and fills `UniversalRenderPipelineGlobalSettings.asset` and `DefaultVolumeProfile.asset`, and
  Unity writes the platform's batching entry into `ProjectSettings.asset`. Commit them with the build's row; later
  builds change them only when the rendering settings change. `unity.ps1 play` exits 124 when it stops a player after
  `-Seconds`: that is the timeout doing its job, not a crash (read the player log for exceptions). A player can take
  15-20 s to load its first scene on a busy machine (a 15 s headless play logged nothing past the engine's start):
  give `-Seconds` room.
- Unity's paths under `Library/PackageCache/` are long, and the editor fails past 260 characters even with Windows
  long paths enabled (a package then fails to import with `DirectoryNotFoundException`): keep the machine root short
  (the default `C:\Users\<you>\UnityWork` is fine) and never build a game from a deep folder.
- Never edit anything under `<UGF_ROOT>\.recording\`.

## Engine and content

- **Unity 6.3 LTS** (`6000.3.x`, pinned in `ProjectSettings/ProjectVersion.txt`; the tools pick each project's editor
  from that file) for every game; never upgrade a game's editor version without the coordinator. **URP** (Universal
  Render Pipeline) with the Universal Renderer, Linear colour space, the **Input System** package as the only active
  input handling, **Cinemachine 3** for cameras. The template's first open sets these up.
- **C# for gameplay** (`Assets/Scripts/`, in its own assembly definition: a test assembly cannot reference Unity's
  default one; it lists `AutoPlay` in its `references`, since the template's `Scenarios.cs` and the bot call the
  drop-in), ScriptableObjects for tuning data, prefabs for everything placed more than once. **Editor work through
  committed C# editor steps** (`Assets/Editor/Steps/`), run headless with
  `Scripts/unity.ps1 step -Method <Namespace.Class.Method> -Reason "..."` (Unity `-batchmode -executeMethod`). Never
  hand-edit the YAML of scenes, prefabs, materials or `.asset` files: one wrong `fileID` or GUID silently breaks
  references. Build scenes, prefabs and materials from code (`EditorSceneManager`,
  `PrefabUtility`, `AssetDatabase`, `SerializedObject` for private fields).
- `new Color(255, 0, 0)` is not red: `Color` takes 0..1 floats, and 255 is a blinding HDR value (light colours,
  tints). Use 0..1 floats, or `Color32` for bytes.
- A clip on a model of the wrong rig type never plays as made: a Humanoid clip needs a Humanoid avatar on the model, a
  Generic clip the same skeleton, or the mesh stays in a T-pose or crumples. Check `ModelImporter.animationType` and
  the avatar before blaming the controller.
- Built-in render pipeline materials from a store pack render magenta under URP in the editor and in development
  builds, and not at all in a release build (only their shadows show): convert them (the Render Pipeline Converter, or
  an editor step that swaps the shader to `Universal Render Pipeline/Lit` and maps the texture slots), and check every
  material of a pack after import.
- Opening a scene in Single mode in an editor step (`EditorSceneManager.OpenScene`, `NewScene`) unloads the assets
  loaded or created before it: one of them assigned afterwards through `SerializedObject` (`objectReferenceValue`)
  reads back null at once and saves as `{fileID: 0}`, with no warning (one game's camera and HUD never got their data
  assets: three commits). Open the scene first, then load the assets you assign (`AssetDatabase.LoadAssetAtPath` after
  the open), and read each reference back before saving.
- `AssetDatabase.ImportPackage` (a `.unitypackage`) imports nothing inside the method that calls it: right after it,
  even after `AssetDatabase.Refresh`, no file is there, and with `-quit` the editor leaves with nothing imported (one
  game's first import step logged a failure and imported nothing). Run that step with `unity.ps1 step ... -NoQuit`,
  subscribe to `AssetDatabase.importPackageCompleted` and `importPackageFailed`, and call `EditorApplication.Exit` from
  there and after a time limit: a run without `-quit` ends only when the step exits (the template's
  `ProjectSetup.ImportTextEssentials` is the pattern).
- `EditorSceneManager.SaveScene` makes no folder: into a missing one it saves nothing, returns false and only logs an
  error, and a step that goes on to log its row records a scene that is not there (the template's first example step
  did). Create the folder first (`Directory.CreateDirectory`, as the template's `UrpSetup` does) and check what
  `SaveScene` returns.
- Every MonoBehaviour in its own file named after its class: several in one file compile, but only the one named after
  the file gets a script asset, and a player crashed loading a scene that used the others ("level1 is corrupted").
- **Art style (user rule):** every game has one style from the library
  [docs/art-styles/](../../docs/art-styles/index.md) (100 guides: references, visual definition, Unity recipe, do /
  do not), and everything on screen follows it: models and materials, lighting, post-processing, effects, UI.
  - **Choosing.** A style named in your brief is the style. Otherwise the tool picks, at random among the styles that
    fit the game's genre:
    `python <UGF_ROOT>\unity-game-factory\tools\art-style.py pick --genre <slug> [--genre <slug>]` with the one or
    two genres from the tool's list closest to your game (`art-style.py list` prints the styles with their genres; an
    unknown genre prints the list). Styles other games on the machine already use are picked last. For a game no genre
    fits, `pick` with no genre chooses among all 100. Take what it picks: never choose by taste, and pick again only
    when the style cannot carry the brief's story or setting, saying why in the workflow row. _(why: left to choose,
    every session lands on the same few looks; the games must differ)_
  - **Adopting.**
    `python <UGF_ROOT>\unity-game-factory\tools\art-style.py use <id> <UGF_ROOT>\games\<slug>` writes the guide to
    the game's `Docs/ArtStyle.md`, the game's art bible; commit it and name the style in the design doc's art
    direction. Read the whole guide before choosing or building assets, or building a scene.
  - **Applying.** Choose or build the assets whose shapes suit the style, then bring them to it with the guide's Unity
    recipe: material changes (shader swaps, Shader Graph materials, texture edits made by an editor step), lighting,
    the URP renderer features and volume profile, effects and UI. An asset left as it came next to restyled ones
    breaks the style; so does a default-looking menu. Check the guide's do / do not list against the framing
    screenshots.
- **Where art comes from (user rule):** wherever serves the game and its style best; no source is preferred and
  none is required.
  - **The asset library** (`<UGF_ROOT>\asset-library\`): the bought and downloaded store packs and animation packs.
  - **Any other source:** the Unity Asset Store and other stores, free libraries (Poly Haven, ambientCG, Kenney, Quaternius, OpenGameArt,
    Sketchfab's downloadable models) or any other site. Read the licence on the asset's own page: only **CC0**,
    **CC BY** or a store licence that covers a shipped commercial game reaches a game (the game and its dataset are
    used commercially); never non-commercial, no-derivatives, editorial or personal-use terms, an unstated licence, or
    anything taken out of another game. Download free assets yourself; for a paid one write the request (below).
  - **Built from scratch:** when no asset fits the game or its style, or building is quicker than adapting, make the
    model yourself, by script: Blender in background mode when it is on the machine (`blender -b -P Scripts/<name>.py`, exporting FBX
    that Unity imports), or Unity's own tools from an editor step (the `Mesh` API, ProBuilder's API, saved as mesh
    assets). Paint its textures by script too. Commit the script under `Scripts/` with what
    it produced, and run it by its project path (replay-friendly work, below). Hold it to the same bar as a store
    asset: a clear silhouette, clean shading, UVs, materials in the game's style, collision. Props, architecture,
    terrain dressing, vehicles, machines and creatures of rigid parts are all fair to build; a skinned character needs
    a rig and clips, so prefer a rigged one from a library, restyled, unless you can rig yours.
  A game with no fitting pack is never a reason for primitives, a mismatched pack or a missing object: find it or
  build it.
- **Art (user rule):** premium, coherent, never placeholder primitives or unfinished flat colours in the final game
  (flat colour or simple shapes a style guide asks for are the style, done on purpose and finished). Characters and creatures are animated. Store content in any folder under `Assets/` (e.g. `Assets/ThirdParty/<Pack>/`), committed with
  its `.meta` files, through Git LFS where binary, and never git-ignored (the repo stays private; unity-commit-always
  skill, "Store packs are committed"); import a `.unitypackage` with an editor step
  (`AssetDatabase.ImportPackage(path, false)`, run with `-NoQuit`: above); adapt it (materials, kitbash, set dressing,
  lighting). Record every asset that came from outside in `assets.manifest.json` (format `assets-manifest/v1`, docs/game-format.md:
  URL, licence, version, the repo paths of its files, changes) and credits in `Docs/ThirdPartyNotices.md`, written as
  a normal developer would. Need a paid asset? Write an "Asset requests" list (URL, price, licence, Unity 6 + URP
  support, what it replaces) in your design doc and message the coordinator.
- **Sound:** every sound effect comes through the **unity-sound** skill (read it before writing the audio direction):
  cues listed in the design doc, clips chosen by their numbers and measured with `tools/sfx.py`, CC0 or CC BY only,
  recorded in `assets.manifest.json`. Never leave a cue silent or ship a placeholder beep.
- **UI (user rule):** matches the game's art style (its guide's UI and typography line): kit frames, icons, display
  fonts, styled numbers. UI Toolkit or
  uGUI with TextMeshPro, either is fine. No plain or default-font text on screen: never the default
  `LiberationSans SDF` or the built-in `LegacyRuntime` font; make a TextMeshPro font asset (or a UI Toolkit font asset)
  from the game's own display font.
- **UI colours, when you are Codex (user rule, 2026-11-11):** Codex's habit, whatever the game, is a dense blue
  interface: navy or dark-blue panels, cyan or blue glowing text and outlines, the screen packed edge to edge with
  boxes, bars and small readouts. Do not build that. Take the UI's colours, materials and type from the game's art
  style guide and its world, show only what the player needs at that moment and leave the play view open. Blue is used
  only where the style guide itself asks for it. Before calling a screen or the HUD done, look at a screenshot of it:
  if it reads as a blue sci-fi dashboard laid over a game that is not one, or as a wall of panels, redo it.
  _(failure: games built by Codex came out one after another with the same dense blue UI, unrelated to their art
  style)_
- **Story (user rule):** a strong background story told in play, never a wall of text: environmental storytelling, at
  most one short line (under ~15 words) per area, optional discoverable details, a late payoff that recolours earlier
  play.
- **Camera (user rule):** gentle; the user gets motion sick. Third person: character in the lower third, never filling
  the screen, never at hip height or jammed into the body (Cinemachine's Deoccluder or Decollider in narrow spaces,
  crouching).
- **Quality bar:** main menu, settings (volume, resolution, mouse sensitivity), pause, save/load where it fits, HUD,
  sound, clear win/lose, a Windows x64 release player build (non-development, IL2CPP where the toolchain has it, else
  Mono, noted in the design doc). Recorded and TTS voices are allowed.
- **Gameplay depth (user rule, 2026-11-11):** a game is never only its genre's bare loop. On top of the core loop
  the design doc names several further systems the player uses, each changing how a session goes, of the kind a
  player of that genre expects from a full game: a technique to master, things to pick up or use during play,
  progression or customising between runs, opponents or hazards that behave in different ways, choices with a
  trade-off. Each one works, shows in play with its own feedback, and is reachable by a scenario. One example, not a
  template: a racing game that is only driving laps is too thin; one with drifting, item pick-ups and car modification
  is the depth meant. Choose what fits your own game's genre and story and never copy this list. _(failure: a racing
  game shipped as plain racing, too simple as a game and too thin to give hard tasks)_
- **Room for hard tasks.** A game's tasks come from its own history (unity-write-tasks skill), and strong agents miss
  what only shows when the game runs. So build these in, and work them over several rounds rather than in one commit:
  feedback for every gameplay event (a HUD readout, marker, sound or effect); visible state changes (materials,
  colours, lights, dressing); a pause menu with settings and back navigation on Escape; tuned numbers a player feels
  (ranges, detection, damage, timers). Fix each playtest issue in its own commit whose message says what the player
  saw, so the thread can be found and checked later.
- **Every state reachable by a scenario.** Each scenario starts straight in the situation it shows, so a check reaches
  any moment in a short play from `play_scene` and `play_args`; no state reachable only after minutes of play or only
  from the title menu.

## Names

Never write **Superposition**, **game-factory** or **unity-game-factory** (any spelling: `game_factory`,
`gamefactory`) anywhere in the game: code, comments, namespaces, `ProjectSettings` (`companyName` is written to the
build's `<Game>_Data\app.info` and names the `Application.persistentDataPath` folder), editor steps, docs, commit
messages, builds, in-game text, process arguments. `companyName` is the game's own studio name (the template sets it to the title). Keep agent, model
and provider names (**Claude / Anthropic / Opus**, **OpenAI / Codex CLI / GPT** model ids) out of game content and
commit messages too (deliverables refuse or scrub them). Recording traces are fine: `workflow.jsonl` stays in the repo,
row ids in commit messages are fine.

## Recording

- `workflow.jsonl` at the project root, one row per real operation **at the moment you act** (schema in the
  unity-commit-always skill; id prefix per game, e.g. `is-00042`). Log failures, dead ends, debugging and fixes; never
  edit, reorder or backfill rows (`log.gap` row for anything missed), except to remove a banned name
  (unity-commit-always skill: `tools/scrub-workflow-rows.py --apply`, which appends the `log.correct` row). Banned
  names include the machine's account name (in paths): enforced in every non-script file; scripts and editor steps
  that already ran keep it (the packager scrubs them in every delivery).
- Editor steps write their own rows with the template's `WorkflowLog.Row(op, target, parameters)`
  (`Assets/Editor/Tools/WorkflowLog.cs`): the op and target are the step's (`scene.build`,
  `Assets/Scenes/Harbor.unity`); it fills in the id, `seq` and time, the step's own file and its sha256 as `source`,
  and the `-Reason` given to `unity.ps1 step` as `reason` (`direction:` names the `user.direction` row it acts on).
- The machine hooks (the same scripts under Claude Code and Codex) record every tool call to
  `<UGF_ROOT>\.recording\<slug>\actions.jsonl`, every prompt the person types and every reply you write to
  `messages.jsonl` beside it, and every commit to `commits.jsonl`; a dataset delivers the first two in
  `History/sessions/`. Leftover changes are auto-committed as `WIP` at the end of a turn (commit properly instead).

## Replay-friendly work

The dataset's `ReplayScripts/` rebuilds your game from its history, step by step: every commit is replayed in the
background, in an isolated copy of the project, right after you make it (docs/unity-replay.md, section 3). Its
settings are the repo's `ReplayConfig.json` (the template has it; `"live": false` turns the per-commit replay off; a
game without one replays with the defaults). What it cannot replay costs a manual workaround at release, so:

- **Every editor step committed** under `Assets/Editor/Steps/` and run by its method through
  `Scripts/unity.ps1 step -Method <Namespace.Class.Method> -Reason "..."`. Never run a step from a scratch or temp
  folder.
- **Relative paths only**: steps reach files through the project (`Application.dataPath`, `"Assets/..."` asset paths,
  `Directory.GetCurrentDirectory()`, which is the project root), never an absolute path to `games\<slug>` or a
  `Directory.SetCurrentDirectory` into it.
- **Read-only steps by name**: probes and checks are `Inspect*`, `Measure*`, `Check*`, `Analyze*`, `Scan*` or contain
  `Probe`; the replay skips them. One that writes something a later step reads is named otherwise (or listed in
  `ReplayConfig.json` `not_readonly`).
- **One workflow row per run at least**, written by the step.
- **Edit scripts with the agent's own file tools** (Claude Code: Write/Edit; Codex: apply_patch), and never a step
  that ran: write `BuildTownV2` (a new class in a new file), so its rows' `source.sha256` still match the code that
  ran. A `sed -i`/`perl -i`/Python rewrite of a script hides its text at run time from the replay.
- **No GUI-only edits for content** (a GUI edit leaves only its YAML diff, nothing to replay): do it in an editor step.
- **No `.unitypackage` imported from the command line** (`Unity.exe -importPackage`): the replay redoes editor steps
  only, so import it in an editor step (`AssetDatabase.ImportPackage`, run with `-NoQuit`: "Engine and content"
  above).
- **`ReplayConfig.json` kept current**: a store pack you copy into `Assets/` with a shell command gets an `asset_drops`
  entry (the copy command as `match`, `from_git` the pack's folder in the repo), a wrapper of your own that starts the
  editor a `run_patterns` entry (and, when it logs a row of its own per run, that op in `wrapper_row_ops`, or the
  replay counts it as the step's row). Paths in it are written `{root}` / `{home}`, never with the account name.
  Commit a change with a `workflow.jsonl` row (op `replay.config`). A game made before the template had the file
  copies `templates/unity-game/ReplayConfig.json` in when it first needs a setting (docs/unity-replay.md, section 4).
- **Never amend or rebase** a commit you made.

After a commit, the hook prints `[replay] ...` when the last replay found something: fix those in your next commits.

## AutoPlay and recordings

> **AutoPlay's goal is NOT to win (user rule).** The bot only drives the game with human-like input so a recording
> shows the game running. Never tune, fix or re-test the bot to win, score, finish, reach targets, resupply or avoid
> getting stuck; losing, timing out or wandering is fine (metadata). Fix only game bugs (crash, hang, broken scene,
> missing art, lighting, camera); then one AutoPlay run per scenario and the recording request.

The AutoPlay drop-in is in every game as `Assets/AutoPlay/`, unchanged (`docs/autoplay-contract.md`, "Getting the
drop-in"): a new game has it from `new-game.ps1`, with the scenario list `Assets/Scripts/Scenarios.cs`; a game made
before it gets it, and every game a new version of it, with one run of
`powershell -ExecutionPolicy Bypass -File <UGF_ROOT>\unity-game-factory\tools\unity-pipeline\autoplay\install.ps1 -Game <UGF_ROOT>\games\<slug>`
(its own commit and `autoplay.install` row; it refuses while `Assets/AutoPlay`, `Scripts/unity.ps1` or
`workflow.jsonl` have uncommitted changes, so commit first). Never edit the drop-in or put code of your own in
`Assets/AutoPlay/`. What this section asks is also the release gate: the release starts with it ("Dataset", release
step 1, "Ensure AutoPlay"), and no game is released without it.

- Once the first scenario is playable end to end, implement `docs/autoplay-contract.md` (Unity contract v1, section
  6): every scenario starts from the command line with `-scenario <n>` (1-based, the design doc's numbers: what
  `Scripts/unity.ps1 play -Scenario <n>` and `autoplay -Scenario <n>` pass and what a task's `play_args` use) and from
  AutoPlay's `StartScenario` (a template game fills in `Scenes` and `Names` in `Scenarios.cs`; an older game hands its
  own scenario start to `AutoPlay.StartScenario`, contract section 6); all input is read through the Input System; the
  game never pauses or mutes on focus loss (`Application.runInBackground`, which the template sets); every action is
  reachable by input (hotkeys for what is otherwise UI-only). The game calls `ScenarioStarted(name)`
  (`Scenarios.Started()`) when gameplay begins and `FinishRun(result, score)` when it ends, and has a bot that acts
  **only** through the drop-in's input calls (Input System injection), Skill-scaled and human-like (no snapping
  camera, no jump spam). The design doc lists scenarios 1..n (start state, win/lose).
- Test once by hand per the contract's section 7: `Scripts/unity.ps1 build`, then
  `Scripts/unity.ps1 autoplay -Scenario <n>` (the bot plays the built player on a Windows desktop of its own, muted;
  the run's files go to `Logs/autoplay/<time>_s<n>/`). Its summary and the run checker,
  `powershell -ExecutionPolicy Bypass -File <UGF_ROOT>\unity-game-factory\tools\unity-pipeline\validate-run.ps1 <that folder>`,
  must PASS (the run's files are well formed; the bot plays like a human, but its score never holds up a release). A
  game whose own `Scripts/unity.ps1` has no `autoplay` mode runs the test as section 7 says. Tag
  `milestone/autoplay-<n>` (scenarios 1..n work: the recording queue records scenarios 1..n of the newest such tag).
- **Framing gate:** before asking for a recording, take 8-10 screenshots of one short bot run (open areas, narrow
  spaces, crouched, against walls) and check the camera rules above:
  `Scripts/unity.ps1 autoplay -Scenario <n> -MaxSeconds <s> -Extra "<flag>"`, where `<flag>` is a command-line
  argument of the game's own choosing that makes it save its own frames as JPG
  (`ScreenCapture.CaptureScreenshotAsTexture` after `WaitForEndOfFrame`, then `EncodeToJPG`;
  `ScreenCapture.CaptureScreenshot` writes PNG) under its working folder, `Build/Windows/`, which the next build
  deletes: copy the ones you keep to `Docs/screenshots/` first, and send them with the request. No retakes for looks;
  they are the README's screenshots too.
- Before a commit that will be recorded or packaged, run `tools/validate-game.py` on the repo: it names every tracked
  text file that holds the account name (unity-commit-always skill, "Never commit").
- **Never run `enqueue.ps1` yourself.** Only the coordinator queues recordings (one GPU recording at a time;
  `tools/unity-pipeline/enqueue.ps1` refuses anyone else). Message the coordinator: commit sha, tag, scenarios ready,
  the `validate-run.ps1` result, screenshot paths.

## Priorities (user decision)

**AutoPlay's goal is NOT to win** (rule in "AutoPlay and recordings" above): fix game bugs only, never the bot's
results.

What ships is what matters, in this order: the game plays; the game builds (editor and the Windows release player);
the dataset holds the replay scripts and the git log. The AutoPlay bot should still play like a human (human-like
input, aim and camera), but bot work never blocks a release: one recording per scenario that shows the game running is
enough, whatever the result (win/lose/timeout is metadata). No tuning for win rates, seed sweeps or "clean" runs, and
no re-runs or re-recordings to improve how the bot plays. No retest loops: every GPU or editor run costs the shared
machine and holds up delivery, so run the minimum once and report; re-run only when the user asks. Game-session work
never blocks dataset packaging or sharing.

## Dataset (layout unity-dataset-layout/v1)

A finished game ships as: `README.md, git.log, workflow.jsonl, Brief/, History/, Tasks/, UnityProject/,
ReplayScripts/, Gameplay/<slug>_S<n>.mp4, Screenshots/, Build/, manifest.json` (docs/game-format.md). The repo's
`Dataset/` folder holds the same minus `UnityProject/`, `Build/`, `History/` and `Tasks/`; the packager produces it and
you commit it. The full dataset zip is `Dataset.zip` in the game folder, next to `Dataset/`: git-ignored (with
`.dataset/`, the packager's scratch), never committed.

The packager is `python <UGF_ROOT>/unity-game-factory/tools/package-dataset.py <slug>` (docs/unity-pipeline.md,
"Dataset packager"). It packs the release commit, not the working tree, with three products of that commit: the
pipeline's release build, the gameplay video of each scenario's first valid recording (one is enough; the result
never picks a run) and the creation replay's package. **The release**, in this order:

1. **Ensure AutoPlay** (required: no game is released without it), before the release commit is chosen. Run
   `powershell -ExecutionPolicy Bypass -File <UGF_ROOT>\unity-game-factory\tools\unity-pipeline\autoplay\install.ps1 -Game <UGF_ROOT>\games\<slug>`:
   when the game is current it changes nothing and says "up to date: nothing to commit"; otherwise it writes the
   current drop-in (and brings an unchanged copy of an older template's `Scripts/unity.ps1` up to date) in a commit of
   its own with one `autoplay.install` row. It refuses while `Assets/AutoPlay`, `Scripts/unity.ps1` or
   `workflow.jsonl` have uncommitted changes: commit them first. Then: every scenario wired
   (docs/autoplay-contract.md, section 6); the bot written; for each scenario the hand test of section 7,
   `Scripts/unity.ps1 autoplay -Scenario <n>` on a player built with `Scripts/unity.ps1 build`, and the run checker
   (`tools/unity-pipeline/validate-run.ps1 <that run's folder>`) saying PASS; `milestone/autoplay-<n>` tagged
   (scenarios 1..n work). Only then choose the release commit.
2. The release commit: the game content-complete, its tasks on the tasks branch, everything committed, the milestone
   tag in its history. Make no other commit until the packager has run, or the replay and the recordings no longer
   match it.
3. Send the coordinator the release commit to record (its sha): the queue builds its release player
   (`tools/unity-pipeline/build.ps1`) and records scenarios 1..n of the newest milestone tag.
4. `python <UGF_ROOT>/unity-game-factory/tools/unity-replay/unity_replay.py release --game <slug>`, with `HEAD` at the
   release commit, makes `ReplayScripts/` for it (docs/unity-replay.md, section 3; with the live replay current, only
   the last commits and a full final check remain; it refuses while the last commit's live replay still runs: run it
   again once that is done). Its verdict, PASS or FAIL, is metadata.
5. Once the coordinator says the recording is done: the packager (`--dry-run` first says what it would take and what
   is missing; `--commit <sha>` when `HEAD` has moved past the release commit). It writes `Dataset/`, which you then
   commit, and `Dataset.zip`, or `Dataset.pending.zip` while the replay is missing; neither zip is ever committed. A
   game without a gameplay video is rejected at upload: without a valid recording of the release commit the packager
   refuses.

It scrubs every text file, then refuses the package when a banned name is left in a text file, a path or a binary
file's strings, when the release build's leak scan found anything, while the pipeline builds or records the game, or
when the dataset checks find an error: fix what it names and run it again. It never commits and never changes your
history. Nobody assembles a dataset or `Dataset.zip` by hand; before the packager's first run `Dataset/` stays as the
template made it and `validate-game.py`'s "not packaged yet" warning is expected.

**README screenshots (user rule; required before the game is called content-complete).** `Docs/screenshots/` holds
5-7 real gameplay stills (JPG, in Git LFS; from validated recordings' stills, `<UGF_ROOT>\recordings\<slug>\_stills\`,
or the framing-gate screenshots, not from extra GPU launches; no editor views, debug overlays or placeholder art).
Until recordings exist, use the framing gate's frames there are, each from a different scenario or moment: fewer than
5 is the validator's warning (not an error), so never invent stills to reach five. The README shows them as a hero
image plus a captioned gallery (one line per image saying what it shows). Every image the README links must be
committed: after pushing, open the repo page on github.com and check that each image renders (a link to a file that
was never committed shows as a broken image).

**Game format (docs/game-format.md).** Before calling the game content-complete,
`python <UGF_ROOT>/unity-game-factory/tools/validate-game.py <UGF_ROOT>/games/<slug>` must say VALID: required files,
`assets.manifest.json` in `assets-manifest/v1` with every listed file committed, every asset with its `.meta` and no
orphan `.meta`, `workflow.jsonl` rows, README images, no banned names. The dataset adds your design doc and the
original brief (`Brief/`) and the full history.

**Tasks (unity-write-tasks skill).** A game is complete when its repo has `Tasks/` on the tasks branch: tasks an agent
can be given on this game, one `Tasks/<game>-<kind>-<slug>.json` each in the task format `GameTask`, at least 5 and up
to about 10 per game (hard; at most one of a game's tasks may be medium, none easy),
every one a long thread of multiple edits from your real history (a bug that took several attempts, a direction that
took several rounds, a feature or look pass built over many commits), never a single fix. They live on the repo's
orphan `tasks` branch, checked out as a worktree outside the game folder (`<root>/tasks/<slug>`), committed and pushed
there, never on main: task work never enters the game's history (the hooks ignore that branch). Seeds point at main's
commits. Follow the unity-write-tasks skill (the branch and worktree, seeds, the brief written from context, the play
scene, deterministic probe checks, what must never reach the agent); never point the game's code or docs at `Tasks/`.
validate-game.py checks their format, and `tools/task-check.py <games>/<slug> --all` (docs/task-check.md), started
once all the tasks are written as a background process the person can leave running (unity-write-tasks section 5),
checks them on the engine: a task ships only when the task check says VALID. Judge each task's difficulty in the
session against the bar (unity-write-tasks skill, section 6); never run a task with another coding agent
(`tools/task-try.py` is ours, run on submitted tasks).

## Working with the coordinator

- Report milestones, recording requests ("AutoPlay and recordings" above) and blockers to the coordinator; put long
  findings in the shared notes folder.
- User playtest feedback arrives through the coordinator: fix it first, commit, report the sha.
- **Every human direction is recorded before you act on it** (from the user directly, or relayed by the coordinator):
  rewrite a user message to you as a direction (what to change and why, one or two neutral sentences: no tone,
  profanity, names or chat wording; never the raw message), or take the coordinator's relayed text as it is; append
  it at once to the repo-root `workflow.jsonl` as a `user.direction` row (`via` direct or coordinator),
  then the work, with `"direction": "<row id>"` on each row that acts on it and `Direction: <row id> (...)` in each
  commit body (unity-commit-always skill, "workflow.jsonl"). The dataset shows the human's directions and what they
  led to.
- Blocked (UAC, a Unity licence, a purchase, an engine limit)? Write it in your design doc, message the coordinator
  once, carry on with what you can.
- Push only when the coordinator says (unity-commit-always skill).
