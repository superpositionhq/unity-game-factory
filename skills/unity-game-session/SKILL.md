---
name: unity-game-session
description: 'Rules for a session that builds one Unity 6.3 LTS game for unity-game-factory (repo %UGF_ROOT%\games\<slug>, pushed to the private <org>/unity-game-<slug>, <org> = the config''s github_org). Use at the start of every Unity game-building session and whenever deciding about art, UI, story, naming, heavy/GPU jobs, editor steps, recording (workflow.jsonl, AutoPlay, framing screenshots), or what to send the coordinator. Pair it with the unity-commit-always skill.'
---

# Game session (Unity)

You build one small but premium-looking Unity 6.3 LTS game, and the way you build it is the product: every real
operation is recorded as it happens (`workflow.jsonl`, git history, the machine's action hooks) and becomes a
game-creation dataset. Your brief (from `docs/briefs/game-session.md`, or `docs/briefs/solo-game.md` in a solo
session) gives the game; these rules apply to every game. `%UGF_ROOT%` = the machine root (`machine/README.md`); the
coordinator is the session that started you. Use the **unity-commit-always** skill for every commit and the
**unity-sound** skill for every sound.

**Only the unity-game-factory skills (owner's rule).** Use unity-commit-always, unity-game-session, unity-sound and
unity-write-tasks and no other skill: never install, enable or invoke a personal, project, plugin, marketplace or agent
built-in skill, even when the agent offers one, and that includes the Unreal game-factory's skills (commit-always,
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
   `$env:UGF_ROOT`: the hooks match the command text. new-game.ps1 refuses any other -Path. Calls made before this one
   (reading docs, drafting the design) are imported from your transcript when the session is mapped (status
   `from_transcript`). It writes the skeleton (Unity 6.3 LTS version pin, Visible Meta Files + Force Text, the editor
   tools assembly, LFS for every binary type, root-anchored `.gitignore`), the first `workflow.jsonl` row, the commit
   recorder hook, the first commit, the first editor open (packages, URP, Input System, TextMeshPro's essential
   resources, player settings; a second commit) when the editor is installed, and the private repo
   `<org>/unity-game-<slug>` (`github_org` in the machine config; not pushed). When it says the first open did not run
   or failed (no editor, no licence), run `Scripts/unity.ps1 setup` once that is fixed, then commit.
3. Write the design doc + story bible in unity-game-factory `docs/games/<slug>.md` before building: systems, classes,
   ScriptableObjects, scenes, scenarios 1..n (start state + win/lose), art and audio direction, acceptance checklist.
   Keep its status section current. It is the only unity-game-factory file you edit.

## Machine rules (shared PC, several sessions at once)

- **Every heavy job goes through the limiter:** any `Unity.exe` run (batchmode steps, compiles, tests, player builds),
  any run of a built player:
  `& <UGF_ROOT>\tools\unity-heavy.ps1 -Label "<slug> <what>" -- <exe> <args...>` (general slots, plus one of the
  machine-wide GPU slots for anything that renders; waits for GUI programs; returns the job's exit code). From Git Bash:
  `powershell -Command "& '<UGF_ROOT>\tools\unity-heavy.ps1' -Label '...' -- '<exe>' args; exit $LASTEXITCODE"`
  (`powershell -File ... --` misparses `--`). The game's `Scripts/unity.ps1` already calls it for you; use that.
  The slots are shared with the Unreal game-factory if this machine runs both (same machine-wide mutexes).
- **GPU:** several GPU jobs run at once (one per GPU slot, each starting only while the VRAM guard allows; the counts
  come from the machine's hardware, docs/unity-pipeline.md "Machine-wide slots"); a recording takes all of them. Keep
  GPU runs short, prefer `-nographics` (every `unity.ps1` run without `-Render`) for logic tests, close the process
  when done, at most one editor of yours alive. Recordings have priority (unity-heavy yields to them).
- **One Unity process per project:** Unity locks the project (`Temp/UnityLockfile`). Never start a batchmode run while
  another Unity process (a GUI editor included) has the same project open; it fails with "another Unity instance is
  running with this project open". Never open the GUI editor on the project yourself; the person may, and then your
  batchmode runs fail until they close it: wait, or ask them.
- Toolchain facts: the editor needs an activated licence (Unity Hub, a Unity ID; Personal is fine) even in batchmode,
  or every run exits with a licensing error. IL2CPP player builds need the Windows Build Support (IL2CPP) module and
  Visual Studio 2022's C++ workload; Mono builds need neither. `-runTests` must not be combined with `-quit` (the test
  run quits by itself). A batchmode run with compile errors aborts before your method runs: read `error CS` lines in its
  log first. `-nographics` cannot render: no screenshots, no lightmap bake, no shader warm-up from it.
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
  default one), ScriptableObjects for tuning data, prefabs for everything placed more than once. **Editor work through
  committed C# editor steps** (`Assets/Editor/Steps/`), run
  headless with `Scripts/unity.ps1 step -Method <Namespace.Class.Method> -Reason "..."` (Unity `-batchmode
  -executeMethod`). Never hand-edit the YAML of scenes, prefabs, materials or `.asset` files: one wrong `fileID` or
  GUID silently breaks references. Build scenes, prefabs and materials from code (`EditorSceneManager`,
  `PrefabUtility`, `AssetDatabase`, `SerializedObject` for private fields).
- `new Color(255, 0, 0)` is not red: `Color` takes 0..1 floats, and 255 is a blinding HDR value (light colours,
  tints). Use 0..1 floats, or `Color32` for bytes.
- A clip on a model of the wrong rig type never plays as made: a Humanoid clip needs a Humanoid avatar on the model, a
  Generic clip the same skeleton, or the mesh stays in a T-pose or crumples. Check `ModelImporter.animationType` and
  the avatar before blaming the controller.
- Built-in render pipeline materials from a store pack render magenta under URP: convert them (the Render Pipeline
  Converter, or an editor step that swaps the shader to `Universal Render Pipeline/Lit` and maps the texture slots),
  and check every material of a pack after import.
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
- Every MonoBehaviour in its own file named after its class: several in one file compile, but only the one named after
  the file gets a script asset, and a player crashed loading a scene that used the others ("level1 is corrupted").
- **Art (user rule):** premium, coherent, never primitives or flat colours in the final game. Use the bought and
  downloaded Unity Asset Store packs and the animation packs (library `<UGF_ROOT>\asset-library\`); characters and
  creatures animated. Store content in any folder under `Assets/` (e.g. `Assets/ThirdParty/<Pack>/`), committed with
  its `.meta` files, through Git LFS where binary, and never git-ignored (the repo stays private; unity-commit-always
  skill, "Store packs are committed"); import a `.unitypackage` with an editor step (`AssetDatabase.ImportPackage(path,
  false)`, run with `-NoQuit`: above); adapt it (materials, kitbash, set dressing, lighting). Record every external
  asset in `assets.manifest.json` (format `assets-manifest/v1`, docs/game-format.md: URL, licence, version, the repo
  paths of its files, changes) and credits in `Docs/ThirdPartyNotices.md`, written as a normal developer would. Need
  more? Write an "Asset Store requests" list (URL, price, licence, Unity 6 + URP support, what it replaces) in your
  design doc and message the coordinator.
- **Sound:** every sound effect comes through the **unity-sound** skill (read it before writing the audio direction):
  cues listed in the design doc, clips chosen by their numbers and measured with `tools/sfx.py`, CC0 or CC BY only,
  recorded in `assets.manifest.json`. Never leave a cue silent or ship a placeholder beep.
- **UI (user rule):** matches the game's art style: kit frames, icons, display fonts, styled numbers. UI Toolkit or
  uGUI with TextMeshPro, either is fine. No plain or default-font text on screen: never the default
  `LiberationSans SDF` or the legacy Arial font; make a TextMeshPro font asset (or a UI Toolkit font asset) from the
  game's own display font.
- **Story (user rule):** a strong background story told in play, never a wall of text: environmental storytelling, at
  most one short line (under ~15 words) per area, optional discoverable details, a late payoff that recolours earlier
  play.
- **Camera (user rule):** gentle; the user gets motion sick. Third person: character in the lower third, never filling
  the screen, never at hip height or jammed into the body (Cinemachine's Deoccluder or Decollider in narrow spaces,
  crouching).
- **Quality bar:** main menu, settings (volume, resolution, mouse sensitivity), pause, save/load where it fits, HUD,
  sound, clear win/lose, a Windows x64 release player build (non-development, IL2CPP where the toolchain has it, else
  Mono, noted in the design doc). Recorded and TTS voices are allowed.

## Names

Never write **Superposition**, **game-factory** or **unity-game-factory** (any spelling: `game_factory`,
`gamefactory`) anywhere in the game: code, comments, namespaces, `ProjectSettings` (`companyName` becomes the exe's
company and the `Application.persistentDataPath` folder), editor steps, docs, commit messages, builds, in-game text,
process arguments. `companyName` is the game's own studio name (the template sets it to the title). Keep agent, model
and provider names (**Claude / Anthropic / Opus**, **OpenAI / Codex CLI / GPT** model ids) out of game content and
commit messages too (deliverables refuse or scrub them). Recording traces are fine: `workflow.jsonl` stays in the repo,
row ids in commit messages are fine.

## Recording

- `workflow.jsonl` at the project root, one row per real operation **at the moment you act** (schema in the
  unity-commit-always skill; id prefix per game, e.g. `is-00042`). Log failures, dead ends, debugging and fixes; never
  edit, reorder or backfill rows (`log.gap` row for anything missed), except to remove a banned name
  (unity-commit-always skill: `tools/scrub-workflow-rows.py --apply`, which appends the `log.correct` row). Banned
  names include the machine's account name (in paths): enforced in every non-script file; scripts and editor steps
  that already ran keep it (packaging scrubs them).
- Editor steps write their own rows with the template's `WorkflowLog.Row(op, target, parameters)`
  (`Assets/Editor/Tools/WorkflowLog.cs`): the op and target are the step's (`scene.build`,
  `Assets/Scenes/Harbor.unity`); it fills in the id, `seq` and time, the step's own file and its sha256 as `source`,
  and the `-Reason` given to `unity.ps1 step` as `reason` (`direction:` names the `user.direction` row it acts on).
- The machine hooks (the same scripts under Claude Code and Codex) record every tool call to
  `<UGF_ROOT>\.recording\<slug>\actions.jsonl` and every commit to `commits.jsonl`; leftover changes are
  auto-committed as `WIP` at the end of a turn (commit properly instead).

## Replay-friendly work

The dataset's `ReplayScripts/` rebuilds your game from its history, step by step. Not available yet: the creation
replay comes with the recording pipeline, so nothing replays your commits today; these rules are what makes your
history replayable when it arrives, and `workflow.jsonl` already depends on them. What it cannot replay costs a manual
workaround at release, so:

- **Every editor step committed** under `Assets/Editor/Steps/` and run by its method through
  `Scripts/unity.ps1 step -Method <Namespace.Class.Method> -Reason "..."`. Never run a step from a scratch or temp
  folder.
- **Relative paths only**: steps reach files through the project (`Application.dataPath`, `"Assets/..."` asset paths,
  `Directory.GetCurrentDirectory()`, which is the project root), never an absolute path to `games\<slug>` or a
  `Directory.SetCurrentDirectory` into it.
- **Read-only steps by name**: probes and checks are `Inspect*`, `Measure*`, `Check*`, `Analyze*`, `Scan*` or contain
  `Probe`; the replay skips them. One that writes something a later step reads is named otherwise.
- **One workflow row per run at least**, written by the step.
- **Edit scripts with the agent's own file tools** (Claude Code: Write/Edit; Codex: apply_patch), and never a step
  that ran: write `BuildTownV2` (a new class in a new file), so its rows' `source.sha256` still match the code that
  ran. A `sed -i`/`perl -i`/Python rewrite of a script hides its text at run time from the replay.
- **No GUI-only edits for content** (a GUI edit leaves only its YAML diff, nothing to replay): do it in an editor step.
- **Never amend or rebase** a commit you made.

## AutoPlay and recordings

> **AutoPlay's goal is NOT to win (user rule).** The bot only drives the game with human-like input so a recording
> shows the game running. Never tune, fix or re-test the bot to win, score, finish, reach targets, resupply or avoid
> getting stuck; losing, timing out or wandering is fine (metadata). Fix only game bugs (crash, hang, broken scene,
> missing art, lighting, camera); then one AutoPlay run per scenario and the recording request.

Not available yet: the AutoPlay drop-in (the `AutoPlay` class a game's code calls), the run checker, the recorder and
the recording queue; they come with the recording pipeline (`docs/autoplay-contract.md` and `docs/unity-pipeline.md`
hold the plan). Until the drop-in is in the repo, write no AutoPlay code, no bot and no `AutoPlay` class of your own:
code against the drop-in does not compile without it, and a stand-in would not match it. The rules of this section
bind the day it arrives; until then, do what each bullet says to do today.

- Once the first scenario is playable end to end, make the game ready for AutoPlay (`docs/autoplay-contract.md`,
  "Until the drop-in is here"): every scenario starts from the command line with `-scenario <n>` (1-based, the design
  doc's numbers: what `Scripts/unity.ps1 play -Scenario <n>` passes and what a task's `play_args` use); all input is
  read through the Input System; the game never pauses or mutes on focus loss (`Application.runInBackground`, which
  the template sets); every action is reachable by input (hotkeys for what is otherwise UI-only). The design doc lists
  scenarios 1..n (start state, win/lose) and its status section says AutoPlay is open. Once the drop-in is here,
  implement `docs/autoplay-contract.md` (Unity contract v1): the drop-in stays unchanged; the game supplies
  `StartScenario(n)` (load scenario n's scene), calls `ScenarioStarted(name)` and `FinishRun(result)`, and has a bot
  that acts **only** through the drop-in's input calls (Input System injection), Skill-scaled and human-like (no
  snapping camera, no jump spam).
- With the drop-in, test once by hand per the contract's section 7 with a rendered run through `Scripts/unity.ps1
  play`; then the run checker (not available yet) must pass (the run's files are well formed; the bot plays like a
  human, but its score never holds up a release). Tag `milestone/autoplay-<n>` (scenarios 1..n work).
- **Framing gate:** take 8-10 screenshots of one short rendered run (open areas, narrow spaces, crouched, against
  walls) and check the camera rules above. Until the drop-in is here the run is not a bot run (not available yet): run
  the built player once per scenario at most with `Scripts/unity.ps1 play -Render -Scenario <n> -Seconds <s> -Extra
  "<flag>"`, where `<flag>` is a command-line argument of the game's own choosing that makes it save its own frames as
  JPG (`ScreenCapture.CaptureScreenshotAsTexture` after `WaitForEndOfFrame`, then `EncodeToJPG`;
  `ScreenCapture.CaptureScreenshot` writes PNG); no retakes for looks. They are the README's screenshots too.
- **Never queue a recording yourself.** Only the coordinator queues recordings (one GPU recording at a time); the
  queue is not available yet, so never request or wait for one. Message the coordinator what is ready: commit sha,
  the scenarios that start with `-scenario <n>`, the release build's result, screenshot paths.

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
`.dataset/`, the packager's scratch), never committed. The packager is not available yet: until it is, `Dataset/`
stays as the template made it, nobody assembles a dataset or `Dataset.zip` by hand, and `validate-game.py`'s "not
packaged yet" warning is expected.

**README screenshots (user rule; required before the game is called content-complete).** `Docs/screenshots/` holds
5-7 real gameplay stills (JPG, in Git LFS; from validated recordings' stills or the framing-gate screenshots, not from
extra GPU launches; until recordings exist, the framing gate's frames; no editor views, debug overlays or placeholder
art). The README shows them as a hero image plus a captioned gallery (one line per image saying what it shows). Every
image the README links must be committed: after pushing, open the repo page on github.com and check that each image
renders (a link to a file that was never committed shows as a broken image).

**Game format (docs/game-format.md).** Before calling the game content-complete,
`python <UGF_ROOT>/unity-game-factory/tools/validate-game.py <UGF_ROOT>/games/<slug>` must say VALID: required files,
`assets.manifest.json` in `assets-manifest/v1` with every listed file committed, every asset with its `.meta` and no
orphan `.meta`, `workflow.jsonl` rows, README images, no banned names. The dataset adds your design doc and the
original brief (`Brief/`) and the full history.

**Tasks (unity-write-tasks skill).** A game is complete when its repo has `Tasks/` on the tasks branch: tasks an agent
can be given on this game, one `Tasks/<game>-<kind>-<slug>.json` each in the task format `GameTask`, up to about 10,
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

- Report milestones, what is ready for a recording ("AutoPlay and recordings" above) and blockers to the coordinator;
  put long findings in the shared notes folder.
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
