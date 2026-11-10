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
   recorder hook, the first commit, the first editor open (packages, URP, Input System, player settings; a second
   commit) when the editor is installed, and the private repo `<org>/unity-game-<slug>` (`github_org` in the machine
   config; not pushed).
3. Write the design doc + story bible in unity-game-factory `docs/games/<slug>.md` before building: systems, classes,
   ScriptableObjects, scenes, prefabs, scenarios 1..n (start state + win/lose), art and audio direction, acceptance
   checklist. Keep its status section current. It is the only unity-game-factory file you edit.

## Machine rules (shared PC, several sessions at once)

- **Every heavy job goes through the limiter:** any `Unity.exe` run (batchmode steps, compiles, tests, player builds),
  any run of a built player, any long `dotnet`/MSBuild job:
  `& <UGF_ROOT>\tools\unity-heavy.ps1 -Label "<slug> <what>" -- <exe> <args...>` (general slots, plus one of the
  machine-wide GPU slots for anything that renders; waits for GUI programs; returns the job's exit code). From Git Bash:
  `powershell -Command "& '<UGF_ROOT>\tools\unity-heavy.ps1' -Label '...' -- '<exe>' args; exit $LASTEXITCODE"`
  (`powershell -File ... --` misparses `--`). The game's `Scripts/unity.ps1` already calls it for you; use that.
  The slots are shared with the Unreal game-factory if this machine runs both (same machine-wide mutexes).
- **GPU:** several GPU jobs run at once (one per GPU slot, each starting only while the VRAM guard allows; the counts
  come from the machine's hardware, docs/unity-pipeline.md "Machine-wide slots"); a recording takes all of them. Keep
  GPU runs short, prefer `-batchmode -nographics` for logic (editor steps, EditMode tests, a headless player run),
  close the process when done, at most one Unity process of yours alive.
- **One Unity process per project:** Unity locks the project (`Temp/UnityLockfile`). Never start a batchmode run while
  another Unity process (a GUI editor included) has the same project open; it fails with "another Unity instance is
  running with this project open". Never open the GUI editor on the project yourself; the person may, and then your
  batchmode runs wait until they close it.
- Toolchain facts: the editor needs an activated licence (Unity Hub, a Unity ID; Personal is fine) even in batchmode,
  or every run exits with a licensing error. IL2CPP player builds need the Windows Build Support (IL2CPP) module and
  Visual Studio 2022's C++ workload; Mono builds need neither. `-runTests` must not be combined with `-quit` (the test
  run quits by itself). A batchmode run with compile errors aborts before your method runs: read `error CS` lines in its
  log first. `-nographics` cannot render: no screenshots, no lightmap bake, no shader warm-up from it.
- Never edit anything under `<UGF_ROOT>\.recording\`.

## Engine and content

- **Unity 6.3 LTS** (`6000.3.x`, pinned in `ProjectSettings/ProjectVersion.txt`) for every game; never upgrade a
  game's editor version without the coordinator. **URP** (Universal Render Pipeline) with the Universal Renderer,
  Linear colour space, the **Input System** package as the only active input handling, **Cinemachine 3** for cameras.
  The template's first open sets these up.
- **C# for gameplay** (`Assets/Scripts/`, its own assembly definition), ScriptableObjects for tuning data, prefabs for
  everything placed more than once. **Editor work through committed C# editor steps** (`Assets/Editor/Steps/`), run
  headless with `Scripts/unity.ps1 step -Method <Namespace.Class.Method> -Reason "..."` (Unity `-batchmode
  -executeMethod`). Never hand-edit the YAML of scenes, prefabs, materials or `.asset` files: one wrong `fileID` or
  GUID silently breaks references. Build scenes, prefabs and materials from code (`EditorSceneManager`,
  `PrefabUtility`, `AssetDatabase`, `SerializedObject` for private fields).
- Unity gotchas already hit elsewhere:
  - `new Color(255, 0, 0)` is not red: `Color` takes 0..1 floats (255 is a blinding HDR value); use `Color32` for bytes.
  - A model imported with the wrong rig type plays its clips as a T-pose or a crumpled mesh: a Humanoid clip needs a
    Humanoid avatar on the model, a Generic clip the same skeleton. Check `ModelImporter.animationType` and the avatar
    before blaming the controller; root motion only with `Animator.applyRootMotion` and a matching clip setting.
  - Built-in render pipeline materials from a store pack render magenta under URP: convert them (the Render Pipeline
    Converter, or an editor step that swaps the shader to `Universal Render Pipeline/Lit` and maps the texture slots),
    and check every material of a pack after import.
  - An asset loaded by path at runtime must be in `Resources/` or an Addressables group; `AssetDatabase` does not
    exist in a player build (it compiles in the editor and fails the player build).
  - Everything a player build needs must be referenced from a scene in the build list (`EditorBuildSettings.scenes`)
    or loaded through Resources/Addressables, or it is stripped.
  - `Time.timeScale = 0` pauses `Update` motion but not `Time.unscaledDeltaTime`, UI or audio; pause menus and
    AutoPlay timers must use the right clock.
- **Art (user rule):** premium, coherent, never primitives or flat colours in the final game. Use the bought and
  downloaded Unity Asset Store packs and the animation packs (library `<UGF_ROOT>\asset-library\`); characters and
  creatures animated. Store content goes in any folder under `Assets/` (e.g. `Assets/ThirdParty/<Pack>/`), committed
  with its `.meta` files through Git LFS where binary and never git-ignored (the repo stays private;
  unity-commit-always skill, "Store packs are committed"). Import a `.unitypackage` with an editor step
  (`AssetDatabase.ImportPackage(path, false)`), then adapt it (URP materials, prefab variants, set dressing,
  lighting). Record every external asset in `assets.manifest.json` (format `assets-manifest/v1`: URL, licence,
  version, the repo paths of its files, changes) and credits in `Docs/ThirdPartyNotices.md`, written as a normal
  developer would. Need more? Write an "Asset Store requests" list (URL, price, licence, Unity 6 + URP support, what it
  replaces) in your design doc and message the coordinator.
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
  crouching; damping instead of snapping).
- **Quality bar:** main menu, settings (volume through AudioMixer groups, resolution, mouse sensitivity), pause,
  save/load where it fits, HUD, sound, clear win/lose, a Windows x64 release player build (non-development, IL2CPP
  where the toolchain has it, else Mono, noted in the design doc). Recorded and TTS voices are allowed.

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
  names include the machine's account name (in paths): enforced in every non-script file; editor steps that already
  ran keep it (packaging scrubs them).
- Editor steps log their own row through the template's `WorkflowLog.Row(...)` (`Assets/Editor/Tools/WorkflowLog.cs`):
  `op:"editor.step"`, the method, the step's source file and its sha256, the `-Reason` you passed.
- The machine hooks (the same scripts under Claude Code and Codex) record every tool call to
  `<UGF_ROOT>\.recording\<slug>\actions.jsonl` and every commit to `commits.jsonl`; leftover changes are
  auto-committed as `WIP` at the end of a turn (commit properly instead).

## Replay-friendly work

The dataset's replay scripts rebuild your game from its history, step by step, so what it cannot replay costs a
manual workaround at release:

- **Every editor step committed** under `Assets/Editor/Steps/` and run through
  `Scripts/unity.ps1 step -Method <Namespace.Class.Method> -Reason "..."`. Never run one from a scratch or temp
  folder, never run an editor step by clicking a menu item, and never leave a step uncommitted after it ran.
- **A step that ran is never edited:** write `BuildTownV2` (a new class or method, in a new file) instead, so the row's
  `source.sha256` still matches the code that ran. Gameplay code under `Assets/Scripts/` is edited normally.
- **Relative paths only**: steps reach files through the project (`Application.dataPath`, `"Assets/..."` asset paths,
  `Directory.GetCurrentDirectory()` which is the project root in batchmode), never an absolute path to
  `games\<slug>`.
- **Read-only steps by name**: probes and checks are `Inspect*`, `Measure*`, `Check*`, `Analyze*`, `Scan*` or contain
  `Probe`; the replay skips them. One that writes something a later step reads is named otherwise.
- **One workflow row per run at least**, written by the step.
- **Edit files with the agent's own file tools** (Claude Code: Write/Edit; Codex: apply_patch), not `sed -i`,
  `perl -i` or a Python rewrite: those hide the text at run time from the replay.
- **No GUI-only edits for content:** anything the person does in the editor GUI is recorded only as the YAML diff; do
  content work in an editor step.
- **Never amend or rebase** a commit you made.

## AutoPlay and recordings

> **AutoPlay's goal is NOT to win (user rule).** The bot only drives the game with human-like input so a recording
> shows the game running. Never tune, fix or re-test the bot to win, score, finish, reach targets, resupply or avoid
> getting stuck; losing, timing out or wandering is fine (metadata). Fix only game bugs (crash, hang, broken scene,
> missing art, lighting, camera); then one AutoPlay run per scenario and the recording request.

- Once the first scenario is playable end to end, implement `docs/autoplay-contract.md` (Unity contract v1): the
  player reads `-autoplay -scenario <n>`, the game supplies `StartScenario(n)` (load scenario n's scene), calls
  `ScenarioStarted(name)` and `FinishRun(result)`, and a bot that acts **only** through Input System injection
  (`InputSystem.QueueStateEvent` / `QueueDeltaStateEvent` on the bot's virtual devices, never `SendInput` and never by
  calling gameplay code directly), Skill-scaled and human-like (no snapping camera, no jump spam).
- Test once by hand per the contract's testing section with a player build through `Scripts/unity.ps1 play`, check
  the run's files are well formed (the bot plays like a human, but its score never holds up a release). Tag
  `milestone/autoplay-<n>` (scenarios 1..n work).
- **Framing gate:** before asking for a recording, take 8-10 screenshots from one short bot run (open areas, narrow
  spaces, crouched, against walls; `ScreenCapture.CaptureScreenshot` from the bot, so it needs a rendered run) and check
  the camera rules above; send them with the request.
- **Never queue a recording yourself.** Only the coordinator queues recordings (one GPU recording at a time). Message
  the coordinator: commit sha, tag, scenarios ready, the run check result, screenshot paths.

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

## Dataset

A finished game ships as: `README.md, git.log, workflow.jsonl, Brief/, History/, UnityProject/, ReplayScripts/,
Gameplay/<slug>_S<n>.mp4, Screenshots/, Build/, manifest.json` (docs/game-format.md). The repo's `Dataset/` folder holds
the same minus `UnityProject/`, `Build/` and `History/`; the packager produces it and you commit it. The full dataset
zip is `Dataset.zip` in the game folder, next to `Dataset/`: git-ignored (with `.dataset/`, the packager's scratch),
never committed.

**README screenshots (user rule; required before the game is called content-complete).** `Docs/screenshots/` holds
5-7 real gameplay stills (JPG, in Git LFS; from validated recordings' stills or the framing-gate screenshots, not from
extra GPU launches; no editor views, debug overlays or placeholder art). The README shows them as a hero image plus a
captioned gallery (one line per image saying what it shows). Every image the README links must be committed: after
pushing, open the repo page on github.com and check that each image renders (a link to a file that was never committed
shows as a broken image).

**Game format (docs/game-format.md).** Before calling the game content-complete, the game repo must hold the required
files: `assets.manifest.json` in `assets-manifest/v1` with every listed file committed, every asset with its `.meta`,
`workflow.jsonl` rows, README images, no banned names. The dataset adds your design doc and the original brief
(`Brief/`) and the full history.

**Tasks (unity-write-tasks skill).** A game is complete when its repo has `Tasks/` on the tasks branch: tasks an agent
can be given on this game, one `Tasks/<game>-<kind>-<slug>.json` each in the task format `GameTask`, up to about 10,
every one a long thread of multiple edits from your real history (a bug that took several attempts, a direction that
took several rounds, a feature or look pass built over many commits), never a single fix. They live on the repo's
orphan `tasks` branch, checked out as a worktree outside the game folder (`<root>/tasks/<slug>`), committed and pushed
there, never on main: task work never enters the game's history (the hooks ignore that branch). Seeds point at main's
commits. Follow the unity-write-tasks skill; never point the game's code or docs at `Tasks/`. Judge each task's
difficulty in the session against the bar (unity-write-tasks skill); never run a task with another coding agent.

## Working with the coordinator

- Report milestones, recording requests and blockers to the coordinator; put long findings in the shared notes folder.
- User playtest feedback arrives through the coordinator: fix it first, commit, report the sha.
- **Every human direction is recorded before you act on it** (from the user directly, or relayed by the coordinator):
  rewrite a user message to you as a direction (what to change and why, one or two neutral sentences: no tone,
  profanity, names or chat wording; never the raw message), or take the coordinator's relayed text as it is; append
  it at once to the repo-root `workflow.jsonl` as a `user.direction` row (`via` direct or coordinator),
  then the work, with `"direction": "<row id>"` on each row that acts on it and `Direction: <row id> (...)` in each
  commit body (unity-commit-always skill, "workflow.jsonl"). The dataset shows the human's directions and what they
  led to.
- Blocked (a licence, a purchase, an editor limit)? Write it in your design doc, message the coordinator once, carry
  on with what you can.
- Push only when the coordinator says (unity-commit-always skill).
