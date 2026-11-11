---
name: unity-write-tasks
description: 'How to write the tasks a Unity game ships with (Tasks/ on the repo''s orphan tasks branch, never on main, one GameTask JSON per task, at least 5, up to about 10 per game) so an agent can be given them in the game-creation environment: the tasks branch and its worktree, the one bar every task meets (a long thread of multiple edits from the game''s real history: many commits, many files, several systems, every task hard, at most one medium, never easy or a single fix), the four kinds as where a thread comes from, picking seed.commit (the parent of the thread''s first attempt) and seed.reference (its final accepted fix), observation-only briefs, play_scene and play_args, milestones and deterministic probe checks (pass/fail never by a model judge or pixels; one required probe per issue), validating and the background task check, limits, and what keeps a task gradable and unleaked. Use when a Unity game session writes, moves, checks or reviews tasks, or reads a task check''s result, and before calling a game complete.'
---

# Writing a game's tasks (Unity)

A game is complete when its repo's orphan `tasks` branch has `Tasks/`: tasks an LLM agent can be given on this game,
fair, checkable and not leaked. One file per task, `Tasks/<game>-<kind>-<slug>.json` (`kind`: `fix`, `corr`, `feat`,
`change`; the whole name in lower-case letters, digits and `-`, at most 63 characters), in the task format `GameTask`
([docs/schemas/game-task.schema.json](../../docs/schemas/game-task.schema.json), `game-task/1`; its `"engine"` is
`"unity-6000.3"`), with `"name"` equal to the file stem (run and grade ids depend on it; never rename a
shipped task). At least 5 and up to about 10 per game, every one a long thread of multiple edits (section 1): a game
with fewer than 5 tasks is rejected, and a short task never fills the count: a game whose history does not hold 5 long
threads is not ready. The tasks branch is the single source: tasks are loaded as `Tasks/*.json` from the
repos' tasks branches, and the packager ships them in the dataset split into the agent's and the grader's halves
(docs/game-format.md). Write tasks with this skill and the unity-game-factory tools only, never
with another skill (AGENTS.md, "Only these skills"). `<root>` and `<UGF_ROOT>` below are the machine root
(`%UGF_ROOT%`); every `docs/...` and `tools/...` path named here is in the unity-game-factory folder under it,
`<UGF_ROOT>/unity-game-factory` (the links lead there too: they work in that folder, not in an installed copy of this
skill).

## 0. Where tasks live: the orphan `tasks` branch

**Task work never goes into the game's history.** Tasks live on a branch `tasks` of the game repo that shares no
history with main, checked out as a git worktree **outside** the game folder (`<root>/tasks/<slug>`). The branch holds
`Tasks/<game>-<kind>-<slug>.json`, a short `README.md` (what the branch is), and optionally `tasks-workflow.jsonl`
(one row per task written, `op:"task.write"`, `target:"Tasks/<name>.json"`; never in main's `workflow.jsonl`). Its
rows have the form of main's rows (docs/schemas/workflow-row.schema.json), with what is the task's own in `params`;
no tool reads the file.

Create the worktree once. When the branch does not exist yet (on origin either):

```bash
git -C <root>/games/<slug> worktree add --orphan -b tasks <root>/tasks/<slug>
```

With an older git that lacks `worktree add --orphan`:

```bash
git -C <root>/games/<slug> worktree add --detach <root>/tasks/<slug>
git -C <root>/tasks/<slug> checkout --orphan tasks
git -C <root>/tasks/<slug> rm -rf .
```

When the branch already exists on origin (another machine or session made it):

```bash
git -C <root>/games/<slug> fetch origin tasks
git -C <root>/games/<slug> worktree add <root>/tasks/<slug> tasks    # creates local tasks tracking origin/tasks
```

Then write the tasks in `<root>/tasks/<slug>/Tasks/`, commit there (`git -C <root>/tasks/<slug> commit`) and push
when told: `git -C <root>/tasks/<slug> push -u origin tasks` the first time, `git push` after. In that worktree on
Windows the word `tasks` also names the folder `Tasks/` (the disk ignores case), and git calls it ambiguous: write
`git log tasks --`.

- Never add `Tasks/` (or any task file) to main, never merge or cherry-pick between `tasks` and main, never point
  main's code, docs, README or `workflow.jsonl` at the tasks branch. The validator fails a repo whose main tracks
  anything under `Tasks/` or whose `tasks` branch shares history with main.
- The recording hooks and the live creation replay ignore commits on the `tasks` branch, and the delivered history
  leaves it out, so committing tasks costs the game's record nothing.
- Seeds (`seed.commit`, `seed.reference`) are commits of main's history (ancestors of main's head) or of the task's
  own start branch `starts/<task name>` (section 2, "Starts on the engine"); pick them in the game checkout
  (`git -C <root>/games/<slug> log`), never on the tasks branch.

Check every task after committing it on the tasks branch:
`python <UGF_ROOT>/unity-game-factory/tools/validate-game.py <UGF_ROOT>/games/<slug>` (it reads the committed `tasks`
branch, else `origin/tasks`, through git: schema, the format's extra rules, name = file name, seed commits on main or
the task's `starts/<name>` branch and on Unity 6000.3, the branch an orphan, nothing under `Tasks/` on main). It
prints one line per finding (`x` an error, `!` a warning, `-` a note): its `repo: Tasks` lines are about your tasks
(a task with nothing wrong has no line of its own: the note `N task(s) on tasks` counts those it read and checked);
its other `repo:` lines (the README, `.meta` files, LFS, the manifest) and its `dataset:` lines are about the game
repo, not a task: they never change a task check's verdict, but a game is delivered only when the validator says
VALID. Commit tasks as you go, like any work (unity-commit-always skill), but on the tasks branch only. Then run the
task check on all of them in one background run (section 5, `tools/task-check.py`): only VALID tasks ship, so fix or
remove every INVALID one before the game is packaged.

## 1. The bar: long threads of multiple edits, nothing else

**The only tasks that meet our requirements are long threads of multiple edits.** A long task keeps one clean run of
a strong agent working about 25 minutes or more. That length is a guide, not a requirement: what counts is that a
strong agent can't solve it easily. You judge this in the session from the thread itself (section 6); we measure it
on every submitted task. A task is a stretch of the game's real history where its own sessions needed many commits,
several attempts or several rounds of directions, touching many files across several systems, before the outcome
held. Strong agents finish a single fix, one cause in one place, in minutes, however long it took in the game; such a
task is worthless to us and never ships, not even as an "easy" one. A task is `"difficulty": "hard"`, with
the tag `long-thread`; at most one of a game's tasks may be medium, none easy.

A thread qualifies only when all of these hold (the validator enforces the numbers, section 6):

1. **Many edits.** From `seed.commit` to `seed.reference`, at least 4 commits change the game itself (`Assets/`,
   `Packages/`, `ProjectSettings/`), and the reference changes at least 5 game files against the start (an editor
   step under `Assets/Editor/Steps/` is the creation's record and a `.meta` follows its asset: neither is a game
   file), with at least 100 code lines added plus removed (any code file of the repo: C#, `.asmdef`/`.asmref`,
   shaders, `.uss`/`.uxml`/`.tss`, scripts such as `.ps1` or `.py`, editor steps included; not under `Dataset/`,
   `Docs/`, `RawAssets/` or a `ThirdParty/` folder, so store packs' own code doesn't count). Status, docs and
   `workflow.jsonl` commits don't count. Assets and binary files don't count as code lines (scenes, prefabs and
   materials neither, even though they are YAML text).
2. **Several systems.** The change spans at least two of: C# code (`.cs`, `.asmdef`, `.asmref`; game and editor code
   alike), config (`ProjectSettings/`, `Packages/manifest.json` and its lock file), embedded packages
   (`Packages/<name>/`), scenes (`.unity`), materials, shaders and textures, prefabs, UI documents and animator
   controllers (`.prefab`, `.uxml`, `.uss`, `.controller`), data (`.asset` ScriptableObjects, `.json`, `.csv`, `.txt`),
   other assets (models, clips, sounds, fonts). The validator counts them over the game files of item 1 (so an editor
   step is no system), by path and extension. A long thread confined to one method is a short task in disguise.
3. **Several outcomes.** At least 3 required outcome probes, one per issue the thread settled, so partial work earns
   partial credit (a compound ticket). A thread that settled only one observable thing is rarely long enough.
4. **The first attempt didn't hold, or the cause is far from the symptom.** The thread had a fix that was undone,
   complained about again ("still too low") or broke something else; or the symptom shows in one system and the cause
   sits in another (a HUD symptom from a ScriptableObject, a camera symptom from physics layers, a crash only in the
   player build, an intermittent or timing bug, a regression from an earlier change).
5. **Checkable by the grader.** Every required outcome is measurable in the grader's own plays: a scenario
   (`play_scene` and `play_args` at the seed) that triggers the moment, or a task play whose scripted inputs reach it
   (Input System control paths, mouse buttons, mouse axes and the cursor included, widget clicks and teleports). The
   plays drive the Input System only: a game that reads the old Input Manager (`Input.GetKey`) takes no keys in them.
   A thread no probe can measure is not a task. One issue of a compound thread that no probe can measure fairly
   stays in the brief and gets a `judge` in `quality` (section 5), never a required check.

**Never make a task easier (permanent).** After a task is first written (committed on the tasks branch), these are
banned if they lower the bar:
widening a threshold or window, making a required probe optional, removing a probe, removing a requirement from the
brief or narrowing what it asks. A plainly broken probe may be fixed only so that it asks at least as much as the
brief. Otherwise drop the whole task and say so; fewer tasks is an acceptable result.

The four kinds say where the thread comes from; each is a long thread, never one commit. The kind is `seed.kind`,
and the file's name carries its short form: `fix` for `bug_fix`, `corr` for `correction`, `feat` for `feature`,
`change` for `change`:

| kind | the thread | `seed.commit` | `seed.reference` |
|---|---|---|---|
| `bug_fix` | a bug the game's sessions fixed over several attempts or commits | the parent of the first attempt | the final fix that held |
| `correction` | a person's direction (`user.direction` rows) that took several rounds or follow-ups to satisfy | the last commit before the first direction | the commit that answered the last round |
| `feature` | a mechanic the game itself built over a span of commits (code, prefabs, input, HUD) | the parent of the span's first commit | the span's last commit, once it played |
| `change` | a look or content pass built over a span (lighting plus post-processing volumes plus materials, a camera rework, a HUD restyle) | the parent of the span's first commit | the span's last commit |

`seed.reference` is always set: a task without the game's own accepted end of the thread is not a task. Merge, don't
split: a chain whose first fix didn't hold is one task, not two; a direction with several issues fixed in several
commits is one compound task with a probe per issue; neighbouring fixes of the same system in the same stretch belong
together. A separate thread in the same stretch (another system, other issues) is its own task, even over the same
commits (section 2), when its own commits meet the floors; threads that are each too short on their own are merged
into one compound task or dropped (section 2, "Measure the thread on its own commits").

Not a task: a single fix or a single commit, a one-setting change, a bug with one cause in one file, status chatter,
process rules, questions, praise, a fix that is only a re-import of assets the start does not have, a sweeping pass
resting on a pack imported later, anything whose outcome neither play nor code can show. If a game's history has fewer
than 10 qualifying threads, ship fewer tasks.

**Where strong agents fail (measured on our tries, 2026-11).** Most tasks a strong agent missed had the code
written and the outcome never checked in the running game. Prefer threads that settled these, and give each one its
own probe in a play that reaches the moment:

- **Feedback that must show in play**: a HUD readout, a marker, a sound or an effect when the event happens (a play
  that triggers the event, then `ui`, `drawn`, `audio`, `lit`);
- **A look change**: colours, materials, dressing, HUD art (`drawn`, `lit`, `screen`, `pieces`, relative to the
  start);
- **Menu, pause and back flows**: Escape or Back closes what it opened and returns where it came from (a task play
  with the keys, then `ui`);
- **A tuned outcome judged in play**: seen or not seen at a distance, holds or breaks under load, passable, winnable
  (a teleport to the spot, then the outcome);
- **Many small requirements in one span**: one probe each, so a single dropped item shows.

Threads that strong agents solve in minutes: one system's logic, a feature whose outcome the code alone shows, a brief
that points at the system. Hiding the list of problems (a brief that reports the symptoms a player meets, not a
checklist) lengthens a run without changing what it misses.

**Finding threads.** Walk the history for clusters: `git log --stat` around a feature, runs of commits on the same
files (`git log --format=%h -- <path>` piled up in a short window), several `user.direction` rows on one topic
(the workflow rows' `"direction"` links), fixes followed by "still", "again", "regressed" or a revert, a render
pipeline or package upgrade that broke a system and the commits that mended it. Read the whole span before picking
its ends.

## 2. Picking the commits

### Starts on the engine

The checker opens a start exactly as committed, with the Unity version its `ProjectSettings/ProjectVersion.txt` names
(6000.3.x): it never upgrades, patches or rewrites a game, and it refuses a start that isn't a 6000.3 project. So
`seed.commit` and `seed.reference` must both be 6000.3 commits that compile and build as they are (the validator
checks the version). When a thread's real start can't be used as it is (it predates a package upgrade the reference
depends on, or an unrelated later fix is needed for it to compile), give it a made start:

- **B** = main's head. **S** (`seed.commit`) = B with the thread's change taken back out of the game itself
  (`Assets/`, `Packages/`, `ProjectSettings/`), re-created by hand where later work moved the code: the issue must
  really be back, and S must still compile. Every other path of S (`workflow.jsonl`, `Scripts/`, `Docs/`,
  `README.md`, manifests) is exactly as at the old pre-fix commit, so nothing in the start records or regenerates the
  fix. **R** (`seed.reference`) = a child of S whose tree is B's (`git commit-tree <B^{tree}> -p S -m "<message>"`;
  without `-m` it waits for a message on its input, or makes R with none).
- Both live on the branch `starts/<task name>` (pointing at R), pushed with the game; the dataset ships every branch
  but `tasks`, so the delivered history holds them.
- Scenes and prefabs are YAML: a scene or prefab may go back to its pre-fix version only if no later commit changed
  it, or by re-creating the issue with an editor step; a binary asset only if no later commit changed it; otherwise
  re-create the issue in code or config, or pick another task. Keep every `.meta` with its asset (a reverted asset
  with a newer `.meta`, or the reverse, breaks GUID references).
- For a thread, "the change" is the whole thread: S takes every commit of it back out, not only the last one, and the
  thread's commits on main (its count and files) are what qualify it; note them in the task's `tasks-workflow.jsonl`
  row (in its `params`, `"thread"`: first and last commit of main).

- **Read the code at `seed.commit`** and confirm the issue is there (the reference diff's removed lines, or a search).
- **The thread's real ends are often not the commits that say so**: a descriptive commit may touch only
  `workflow.jsonl` while the code is in the WIP commit before it. Use `git show --stat` around that time and the
  workflow rows that link the direction (`"direction"`). Start before the first attempt (the earliest, when the
  thread settled several issues), so the agent faces every issue the thread settled, and end at the commit after
  which no more work on it followed.
- **The reference must compile and run**: the grader plays it beside the agent's result. If the last fix crashed until
  a later commit, extend the thread to the later one.
- **Chains and splits merge**: a person complained again after a fix ("still too low"): one task from before the first
  fix to the last. A direction with several issues fixed in separate commits: one compound task, one required probe
  per issue.
- **Spans may overlap; issues may not.** Two tasks may share commits, overlap or nest: one task's start or reference
  may be another's, and a long feature span may contain a shorter thread that settled different issues. Different
  threads that ran at the same time (a camera rework during a HUD pass) are separate tasks over the same commits. What
  never repeats is an issue: two tasks never test the same outcome, so dedupe against the game's existing tasks by
  issue (their briefs and required probes), not by commits. Merging still wins over splitting one thread into short
  tasks (section 1).
- **Measure the thread on its own commits.** The validator measures everything from `seed.commit` to `seed.reference`,
  so a short thread inside another thread's stretch can pass the floors on the other thread's work. Which commits are
  the thread's own is your call (the commits that answer its directions or work on its issues); list them and count
  them: `python <UGF_ROOT>/unity-game-factory/tools/thread-stats.py <UGF_ROOT>/games/<slug> <commit> <commit> ...
  --span <seed.commit>..<seed.reference>` (git only, seconds). Its `thread` line adds up each listed commit's own
  changes (a line two of them touch counts twice), its `span` line is the reference against the start, which is what
  the validator holds to the floors; so the thread's code lines can be more than the span's. A thread whose own
  commits are below the floors (section 6) is too short, whatever the span says: extend it, merge it with its
  neighbouring issues, or drop it. When you tell the person a task is ready, give its own line from the tool
  (commits, files, code lines, systems).
- Asset-only fixes are fine (the agent can make the same change through editor steps or code); drop one only when its
  outcome cannot be seen.

## 3. The instruction (the brief)

Write it from the context, never by quoting a person: no quotes, typos, capitals, profanity, "the owner said" or chat
wording. The reader is a capable developer who has never seen the game.

**Every brief is only an observation**: what a player or QA sees, in plain words, for every issue the thread settled.
It names no cause, no place to look, no file, system, script, component, prefab or asset, and no mechanism ("the
camera feels jammed against the ship", not "the deoccluder counts the water layer"). It never says how many changes
are needed or that the issues are related. Leave out the play_scene line, which the harness adds after the brief
("QA plays the game from the scene ..., with the arguments ..."; with `play_scene` null, the arguments alone). An
issue that shows only once another is fixed (a first fix that didn't hold: the lamp that never lights hides how dim
it is lit) can't be reported as seen at the start: say what is expected there in the item that hides it (how a lit
lamp looks), and give it its own probe.

- **bug_fix**: a QA bug report listing each symptom: what happens, how to reproduce it, what is expected. Code
  identifiers only inside a quoted compiler error or exception line from the player log, which is what a log shows.
- **correction**: what is wrong and how a player sees it, item by item, then the wanted outcome.
- **feature / change**: a producer's ticket: what and why, how the player uses it (which key), the behaviours and
  looks wanted, what must still work. Close with the art bar: the project's own assets and engine features, no
  primitive placeholder shapes, no debug text.
- Describe the controls the player needs; the harness tells the agent which scene QA plays (`play_scene`).
- Never name the studio, its pipeline or its tools. Never describe the fix or any step of the thread.

## 4. `play_scene` and `play_args`

The game's first build scene is usually a title menu that simulated keys cannot leave, so a task almost always needs
`play_scene` and `play_args`: the scene that starts straight in the gameplay where the issue shows, and the player's
command-line arguments that pick its scenario (e.g. `"play_scene": "Assets/Scenes/Harbor.unity"`, `"play_args":
["-scenario", "2"]`). Read the game's command-line and scenario handling at `seed.commit` and check the scene exists
there and at `seed.reference`; it needn't be in the game's build settings (the checker adds every scene the plays open
to its build). Every grader play opens it with `play_args` (boots, idle and drive, and a judge's own plays: its
route, its before and reference plays). The game's first build scene doesn't run when a play opens another scene: a
game that sets itself up in its boot scene's `Start` is started through its own `play_args` with `play_scene` null.
So is a game whose gameplay scene is its first build scene: named in `play_scene`, that scene would load a second
time. What a play does to the game, and the rules for the arguments (their form, the flags a task can't set), are in
docs/task-probes.md, section 1.1. Check in the task check's screenshots and `track` that the reference's plays
really start where the issue shows.

The plays also need to know which object is the player (for `player` measures, teleports, a `near` around the
player). The probe takes an active object tagged `Player`, else one with a `PlayerInput`, else one with a
`CharacterController`, else the camera's root object. Where that finds the wrong object, or none worth the name, set
the task's top-level `player`, an object select that names it for every play (`"player": {"name": "Boat"}`):
docs/task-probes.md, "Words used here".

## 5. Milestones and checks: deterministic probes decide

**Pass/fail is decided only by checks the grader computes itself:** `build`, `boot`, `log_absent` and **`probe`**
checks. A model judge (`judge`, `code_judge`, `actions_judge`) never decides pass/fail and nothing is graded from pixel
statistics of the game's frames except the frame's mean luminance (`screen`), whose threshold is always calibrated or
relative to the start. Judges may stay as `"required": false` quality checks (taste, readability, how the agent
worked). The probe language, every play, measure and threshold with the rules that gate a task, is the task author's
contract [docs/task-probes.md](../../docs/task-probes.md), checked by the schema
[docs/schemas/game-task.schema.json](../../docs/schemas/game-task.schema.json) and `tools/validate-game.py`.

Each milestone is a reward group; a run that gets part of the way earns part of the reward. A task holds 1 to 8
milestones and a milestone 1 to 32 checks; their names are lower-case letters, digits and `_` (a milestone's at most
32 characters, a check's 48). **A no-op scores zero (permanent):** the score is the weighted share of checks passed,
so every check the start already passes takes `"weight": 0`: `builds`, `boots`, all of `still_works`, any
`log_absent` or `file_exists` true of the start, and any probe the start already passes, required or not. They still
gate: a run must pass the required ones to be solved.
`validate-game.py` refuses a weighted `build`, `boot` or `still_works` check, and the task check a weighted probe the
start passes; nothing checks a `log_absent` or `file_exists` outside `still_works`, so their `"weight": 0` is yours to
set. The usual order:

1. `builds`: `build` (`player_builds`: the scripts compile and a Windows player builds).
2. `boots`: `boot` 60 s (`boots_clean`: the player runs 60 s without a crash), `needs` the build. A managed exception
   the game survives is not a crash; a `log_absent` check catches those. It is required like any check that doesn't
   say `"required": false`, and the task check only notes a `log_absent` the reference fails: read its notes, since
   no solution like the reference could pass one (docs/task-check.md, "VALID and INVALID").
3. `fixed` (bug_fix, correction) / `done` (feature, change): `probe` checks of the reported outcomes, `required`,
   `needs` `boots_clean`: at least 3, one per issue the thread settled (split them over several milestones, e.g.
   `fixed_hud`, `fixed_camera`, when the issues are separable). Each one fails at the start for the reported reason
   and passes on the reference.
4. `still_works`: probes that what must keep working still does (the player still moves, the HUD still shows, the
   scene still loads its scenario).
5. `quality` (optional, never required): a `judge` for taste items no probe can capture ("reads as a castle",
   readability of text over the scene), a `code_judge` for code quality, and the standard `actions_judge`
   `worked_well` (or `trace` probes, `"required": false`). A judge is written
   `{"name": ..., "kind": "actions_judge", "question": ..., "rubric": [{"key": ..., "criterion": ...}]}` with
   `"required": false`; a `judge` (of the game, from screenshots and frames of the grader's own play) may also set
   `"before": true` to be shown the start beside the result, and `route` and `reference` (the task schema's `Judge`
   says what each does). The standard `worked_well` question and rubric are not in this repo yet: leave that check
   out unless the coordinator gives you its text (one with words of your own is not the standard one).

A probe names one measurement and its threshold:

```json
{"name": "hero_on_ground", "kind": "probe", "required": true, "weight": 3, "needs": ["boots_clean"],
 "describe": "After the scenario starts, the hero stays on the ground near the west kiln tower instead of falling through the town.",
 "play": "look",
 "measure": {"probe": "player", "field": "y", "window": [3, 18], "agg": "min"},
 "expect": {"op": ">=", "calibrate": 0.5}}
```

Unity is Y-up and in metres: height is `y`, distances are m, speeds m/s.

- `play`: `look` (20 s idle), `drive` (22 s: `<Keyboard>/w` 1-6 s, `<Keyboard>/d` 6-8 s, `<Keyboard>/w` 8-13 s with
  `<Keyboard>/space` at 9 s, `<Keyboard>/a` 13-15 s, `<Keyboard>/w` 15-21 s), a task play `{"name": ..., "seconds":
  ..., "inputs": [{"t", "key", "press"}]}` with Input System control paths (`<Keyboard>/f2`, `<Mouse>/leftButton`,
  `<Gamepad>/buttonSouth`) when the outcome needs other keys (F2, a fire button, a menu key), or `editor` for asset
  facts.
- `measure.probe`: `player` (track: x/y/z/speed/moved/dist), `camera` (distance/height/pitch/yaw/fov/occluded/
  player_on_screen), `objects` (select by component type, tag, layer, name, near, `has`; count, transform, extent,
  active, hidden, collision, speed, lit, `prop:<Component>.<member>` by reflection, `anim:<Parameter>`), `components`
  (lights, particle systems, renderers, audio sources: count, active, visible, position, spin, lit, on, intensity),
  `widgets` (a uGUI or UI Toolkit element's own state: visible, text, percent, value, has_brush), `ui` (what the UI
  shows, whatever draws it: text, count, place of uGUI, TextMeshPro and UI Toolkit elements alike, and text read from
  the frame in a rect; signature with agg changes for a readout that updates; number and clock for which way a readout
  or a timer moved, with agg rises/falls), `drawn` (what is drawn near a point or along a line, rendered: drawn,
  motion, base colour, a beam's reach), `pieces` (placed mesh pieces and their triangles), `light` (illuminance,
  exposure, brightness at a point), `grading` (the URP volume result: cast, warmth, tint, saturation, contrast, grey,
  `post:<Component>.<parameter>`), `screen` (the frame's luminance, never a literal threshold), `audio` (what plays
  and how loud the listener hears it), `ground` (height and relief), `spawns`, `log`, `asset` (editor: a material's
  `shader:` and `keyword:` values, `import:` settings, a ScriptableObject's `prop:`, and in a scene or prefab
  `material_default`, `material:<property>`, `mesh_collision`).
- `expect`: a literal (`{"op": ">=", "value": 1}`) for facts (counts, booleans, "not the default material"), or
  `{"op": ">=", "calibrate": 0.5}` for continuous quantities: the grader measures the start and the reference in the
  grading environment and puts the threshold that fraction of the way from start to fix; `op` points to the fix's side.
  Where the reference is only one fair way of reaching the outcome (most features and changes: how fast a new thing
  spins, how bright it glows), a calibrated threshold would hold every solution to the reference's own tuning: set it
  relative to the start instead, `{"op": ">=", "start_plus": 30}` or `"start_times"` (docs/task-probes.md, section
  1.2). Such a threshold needs a value at the start, and what the task adds isn't there yet: measure over what the
  start has too (the fastest spin of any drawn object, 0 at the start), not over the new things alone, which leave a
  required probe without a threshold and the task INVALID.

Write probes from the game's own code at `seed.commit`: the real component types, tags, layers, scene paths and UI
element names. **Never a name only the reference has** (a component type, tag, layer, object, scene or asset the
thread itself created): another fair build names it otherwise and reads as absent. Select what the thread creates by
what it does or where it is (`has`, `near`, `ui` with a `rect` or text, `drawn`, `lit`, `changed`); `validate-game.py`
refuses a required probe that names something the start lacks and the reference has. **Test the outcome a player
sees, never the implementation**: another valid fix must
pass ("the hero stands on ground", "the stone breaks the wall piece it hits", "the light reaching the tunnel floor
times the camera's exposure is brighter", not "spawnHeight is 0.92" or "the method was changed"). Lighting and colour
are measured from the engine (`light`, `grading`), never from screenshots. `describe` says the assertion in plain
words; it is shown in the grade, never to the agent. Check names are unique and `needs` only names earlier checks;
calibrated probes, `code_judge` and `"reference": true` judges need `seed.reference`.

A task is valid only when it passes the task check: its start fails the task and its reference fix builds, boots and
passes every required probe, and every required `still_works` probe already passes at the start. Write the probes per
[docs/task-probes.md](../../docs/task-probes.md), then check the game's tasks **together, in one background run** (one
run builds a commit several tasks share once, and the person can leave it running and come back). Write and commit
every task first, check that Unity Hub is signed in with an active licence (a batchmode run without one exits 198),
then start the check as its own process so it outlives your turn and no tool timeout cuts it short (PowerShell, under
either agent):

```powershell
Start-Process python -WindowStyle Hidden -WorkingDirectory <UGF_ROOT>\unity-game-factory `
  -ArgumentList 'tools\task-check.py', '<UGF_ROOT>\games\<slug>', '--all' `
  -RedirectStandardOutput <UGF_ROOT>\games\<slug>\.task-checks\run.out `
  -RedirectStandardError <UGF_ROOT>\games\<slug>\.task-checks\run.log
```

Create `.task-checks` first if it doesn't exist. Unity fails on paths past 260 characters, so the checker refuses a
scratch project folder longer than 90 characters: it then stops at once and `run.log` says so; add `'--scratch',
'C:\tc'` (a short folder on the repo's drive) to the arguments. Tell the person it is running, roughly how long (7 to
31 minutes a task for small projects on the machine it was measured on, longer for a game with many or large assets
and several times longer while the machine runs other Unity jobs; most of it is the builds, and a commit several
tasks share is built once: docs/task-check.md, "Requirements"), and that they can leave it. Read
`<UGF_ROOT>\games\<slug>\.task-checks\progress.txt` to see where it stands (rewritten after every task; it says
`finished` at the end); never start a second run of the same game while one is going. A recheck of the tasks you
fixed takes `--task <name>` once per task instead of `--all`. `--task <path>/Tasks/<name>.json` checks a file not
committed yet ([docs/task-check.md](../../docs/task-check.md)). The check builds each start and reference as a
Windows player with the probe package, plays them on a Windows desktop of their own (nothing on the person's screen,
the game counting itself focused) and writes VALID or INVALID per task with the reasons and the measured values. **A
task ships only when the task check says VALID**; for INVALID, fix the task (the docs' "Common reasons and fixes"),
never the threshold toward what the start happens to measure.

## 6. Difficulty, limits and what the validator enforces

- `difficulty` is `hard`; at most one of a game's tasks may be `medium`, none easy (a task that names no difficulty
  counts as medium), and `tags` hold `long-thread`. It is your own estimate of the thread; our runs of the task decide
  its difficulty (last item below).
- `limits`: 400 turns, 480 min, 150 USD, 1800 s tool timeout unless the task needs more; a long thread needs room.
- `tools/validate-game.py` fails a game with fewer than 5 tasks or more than one `medium` task, and a task that is
  `easy`, has no `seed.reference`, has fewer than 3 required probes
  outside `still_works`, or whose reference changes fewer than 5 game files, fewer than 100 code lines or fewer than 2
  systems against its start; for a seed on main it also fails fewer than 4 game-changing commits from `seed.commit` to
  `seed.reference`, and any required probe that names a component type, tag, layer, scene or asset the reference has
  and the start doesn't (section 5). These are floors, not targets: pick the longest threads the history has. It also refuses a task
  without the `long-thread` tag, a weighted check a no-op passes (section 5) and anything against the format rules of
  section 0.
- **Judge difficulty in the session; never run the task with another agent** (the try took up to 25 minutes a task
  and slowed contractors down). Don't run `tools/task-try.py` or start a fresh Claude Code or Codex session on a
  task. Before committing, review each task against section 1 here, with the person: would a strong agent given only
  the brief and the start solve it easily (25 minutes is a guide, not a cut-off)? It would when the brief points at
  one place, the issues share one obvious cause, or the reference diff is mostly one file or one system. If so, extend
  the thread back to an earlier attempt, merge it with its neighbouring issues, or drop it. Tell the person which
  tasks you judged long enough and why, in a line each. We try every submitted task with a strong agent and measure
  its time; that grade decides.

Probes may measure the cause's effect directly, since the agent never sees them.

Wording: neutral and technical, for the game's people and creatures as for the rest. Describe meshes, bones, poses,
hits and reactions. Never use gore, injury or body-horror words ("crumpled body", "cut neck"); a cloud content
filter rejects such briefs and rubrics.

## 7. What must never reach the agent

The agent sees only the brief and the game at `seed.commit` (a commit of main, so without the tasks branch) as a fresh
repository without history, `Tasks/`, `History/` or `Dataset/` (the harness rule: those hold every task's checks and
the reference fixes). The grader's half (`milestones`: probes, rubrics, questions, `log_absent` patterns; and
`seed.reference`) never reaches it. So:

- the instruction holds nothing of the grader's half and does not describe the fix;
- nothing else at `seed.commit` should spell out the answer (a design-doc "known issues" line naming the cause, a
  comment saying how to fix it): if it does, pick another seed or another task;
- never point the game's code, docs or README at `Tasks/` or the tasks branch.

## 8. Pitfalls already hit

| pitfall | rule |
|---|---|
| checks or log patterns shown in the brief | the agent gets the brief only |
| a model judge misread screenshots and failed a correct fix (or passed a wrong one) | pass/fail by probes only; judges are `"required": false` |
| a fix made only in assets (a prefab, a material) failed a code review | the cause is checked by its measured effect (a probe), never by reading the diff |
| a pixel threshold moved between GPUs | light and colour from the engine (`light`, `grading`); the frame's luminance (`screen`) only calibrated or relative to the start, never a literal |
| trees painted on a Terrain counted as one object | count placed pieces (`pieces`), not objects or components |
| a dense forest combined into 3 meshes read 3 pieces against a threshold set on hundreds | count the drawn geometry (`pieces` `visible_triangles`), calibrated or relative to the start, never a literal |
| a count stopped at 200 rows and a threshold was set on it | counts and `of` read every match (`total` and `full`) |
| a light's turn read relative to its own object | `world_yaw:`/`world_pitch:`/`forward:` read the Light's part in the world |
| a lamp switched off (Light disabled, its object inactive, intensity 0) read as lit | the `light` probe counts only Lights that are on; a lamp's `on` and `intensity` are `components` fields |
| a hidden panel (CanvasGroup alpha 0, `display: none`, an inactive object) still counted as shown | `"visible": true` in a widget select counts only what the game shows (its state: a fully transparent widget still counts), `ui` only what is drawn on screen |
| a sound judged by its AudioSource being enabled, not by what the player hears | `audio`: sources playing at their volume at the listener, and the mix's `level`; volumes and level calibrated or relative to the start |
| relief judged by the height of one spot | `ground` over a box: `range`, calibrated or relative to the start |
| a teleport to fixed coordinates missed what each build placed itself | `teleport_to` an object select (nearest match), facing it or a point |
| a `teleport_to` by a `name` wildcard (`Coin*`) went to the `CoinSpawner` beside the player, not to a coin | a select takes every object that fits, and `teleport_to` the nearest: select the instances by their own component or whole name (`Coin(Clone)`) when the start has them too, by what they carry (`has`, next row) when the task adds them, and read `probe.log` in the reference's play |
| a select by component type or tag also matched the scene's own objects, or named the type the reference happened to use | select by what the object carries: `has` (a part that is `lit`, `visible`, of a `component`, `near` a point); a parent that holds such objects (a spawner) matches too, so add a `component` the object itself has and the parent lacks |
| cars that are parts of one object had no position or speed | `components` fields `x`, `y`, `z`, `speed` |
| a broken crate kept its pieces drawn and tagged, so counts couldn't see it break | object `simulating` and `spread`, component `extent_*` and `simulating` |
| an object that breaks by hiding a part or by animating its pieces read whole to `spread`, `extent_*` and `simulating` | object or component `changed` (since the start; `bounds_change` and `pose_change` calibrated or relative to the start) |
| a lamp drawn by an emissive material rather than a Light read dark to `on`, `intensity` and `light` | object or component `lit` (any Light that is on or glowing renderer; `glow` calibrated or relative to the start) |
| a HUD made with UI Toolkit read as absent to a uGUI widget select (or the reverse) | `ui`: what the UI shows on screen, whatever draws it (text with `match`, counts by `kind` and `rect`) |
| a lamp whose glow comes from a Shader Graph's own nodes had no reading from its material | `lit` and `glow` as they are: a renderer whose shader lacks the standard emission interface, or whose colour has a texture, is read as rendered |
| a readout drawn with `OnGUI`, `GL` lines or a custom mesh read as absent to `ui` | `ui` `text` with `match` on a `select` of `"kind": "text"` with a `rect` around the readout (read from the frame as drawn); there are no line elements, so if it still doesn't read, grade another outcome |
| a task needs a readout to keep updating, and it may be drawn by any UI system | `ui` `signature` with `"agg": "changes"` on a `select` with a `rect` around the readout (calibrated or relative to the start) |
| an effect (particles, a panned material, a spinning mesh) had no reading that it shows and moves | `drawn` `near` a point: `drawn`, and `motion` calibrated or relative to the start |
| a spinning part had no speed, or needed its object's name | `spin` of `components` near a point or by `owner`, or an object's `spin`; calibrated or relative to the start |
| duplicate effects after a restart went unseen | `components` with `"effect": true` and `near`: `count` of live effects, read after the restart |
| a score or a timer had to be read as a number, not a string | `ui` `number` or `clock` on a `select` of `"kind": "text"` with a `rect`; `rises`, `falls`, `range` over the window |
| a lamp lit only by particles read dark | `lit` and `glow` as they are: particle systems, trails and visual effects are sources |
| a beam's length had no reading | `drawn` along a `line` from its source: `reach` or `length`, calibrated or relative to the start |
| a surface's tint change (not emissive) had no reading | `drawn` `near` it: `base_r`/`base_g`/`base_b` or `base_change`, calibrated or relative to the start |
| the nearest object a player can push had to be named by type | `has` with `"simulating": true`, in a select or `teleport_to` |
| the game reset the player's position every frame, undoing a teleport | `teleport` or `teleport_to` with `hold` (seconds) |
| a lamp above matched together with one below it | `near` with `y_min`/`y_max` (world, or `y_relative` to the point) |
| a menu that pages on real time (`Time.unscaledTime`, `Time.realtimeSinceStartup`) never reached its later pages in a play | a task-play input `{"t": ..., "wait": seconds}`: the play's clock holds while the game runs on in real time |
| a boot scene's `Start` set up what the play needed, and the play opened `play_scene` before it ran | a boot scene only gets `Awake` and `OnEnable` before `play_scene` replaces it: start such a game through its own `play_args` with `play_scene` null |
| `"of": "first"` over a broad select read another object on the reference (the scene was edited) | matches come in hierarchy order, which a scene edit can change: select by name, tag or `near` |
| `spawns` of `MeshRenderer` counted every child of each coin | name a component that sits once per thing (the coin's own script, when the start has it too); in a task that adds the thing no such component is sure, so count how often an `objects` `count` over a `has` select rises (docs/task-probes.md, section 2.9) |
| `teleport_to` a hovering target left the player in the air | the player's pivot goes to the target's own height plus `offset`'s y, with no ground snap: give a negative y `offset` |
| a sound played with `PlayOneShot` matched no `sound` select | the probe sees only a source's own clip, never a one-shot's: read `level` in an audio play, or select the source by `owner` |
| a widget click didn't fire a UI Toolkit button that handles `ClickEvent` | a widget click sends a submit (`Button.clicked`); for a raw `ClickEvent` use a `cursor` input, then press and release `<Mouse>/leftButton` |
| an editor `shader:` value compared with `==` 0.2 read 0.19999995827674866 | floats come back as stored: `>=`/`<=` a little either side |
| a readout read through the frame touched its rect's edge and read nothing | give the `ui` rect a margin of background around the text |
| a probe that isn't required but passes at the start carried weight | every check the start passes takes `"weight": 0`, a `"required": false` probe too |
| a probe that tests the reference's implementation ("spawnHeight = 0.92") | measure the outcome; another valid fix must pass |
| the brief said "scenario 1" but not `-scenario 1` | `play_scene` and `play_args` always set and checked at the seed |
| a UI element or component name guessed | read the names from the code and assets at `seed.commit` |
| a probe named a component, tag or scene only the reference had, so a fair build that named it otherwise read as absent | select what the thread creates by what it does or where it is; the validator refuses a reference-only name |
| a run wrote the feature but never ran the game to see it, and the task had no probe of the moment | a play that triggers each piece of feedback, and a probe of what the player sees then |
| quoting the person | write from context |
| a reference that crashed | the reference must compile and run |
| tasks solved in minutes: one cause, one place, the brief named the system | only long threads of multiple edits, compound probes, observation-only briefs (section 1) |
| a chain split into two short tasks | one task from before the first attempt to the fix that held |
| a bug that never shows in the grader's plays | a scenario or a task play that triggers the moment |
| a brief rejected by a content filter (injury wording) | neutral technical words: mesh, bones, pose, hit, reaction |
| a reverted asset kept its newer `.meta` and lost its references | an asset and its `.meta` always move together |

## 9. Examples

One whole task, to show the file format and the probe style only. Its game and its commits are made up, so it has
passed the schema and the validator's rules for a task, never the task check: copy its shape, never its names or
thresholds.

```json
{
  "name": "harbor-run-corr-chase-camera-and-lap-count",
  "title": "The chase camera crowds the boat and the lap count never changes",
  "instruction": "QA played scenario 2 (the harbor circuit; W and S throttle, A and D steer) and reports three things.\n1. The camera rides so close behind the boat that the course ahead can hardly be seen. It should sit well back and above the boat.\n2. In turns the quay and the moored boats cut off the view of the boat. The boat should stay in clear view all the way round.\n3. The lap count at the top of the screen stays at LAP 1/3 after the boat rounds the last buoy. It should show the lap the boat is on.\nSteering, throttle and the rest of the HUD must keep working as they do now.",
  "engine": "unity-6000.3",
  "seed": {"game": "harbor-run", "kind": "correction",
           "commit": "1111111111111111111111111111111111111111",
           "reference": "2222222222222222222222222222222222222222"},
  "play_scene": "Assets/Scenes/Harbor.unity",
  "play_args": ["-scenario", "2"],
  "difficulty": "hard",
  "tags": ["long-thread"],
  "limits": {"max_turns": 400, "max_minutes": 480, "max_usd": 150, "tool_timeout_seconds": 1800},
  "milestones": [
    {"name": "builds", "checks": [
      {"name": "player_builds", "kind": "build", "weight": 0}]},
    {"name": "boots", "checks": [
      {"name": "boots_clean", "kind": "boot", "seconds": 60, "weight": 0, "needs": ["player_builds"]},
      {"name": "no_exceptions", "kind": "log_absent", "pattern": "Exception", "weight": 0, "needs": ["boots_clean"]}]},
    {"name": "fixed", "checks": [
      {"name": "camera_back_from_boat", "kind": "probe", "weight": 3, "needs": ["boots_clean"],
       "describe": "While the boat is driven, the camera stays well back from it instead of riding just behind it.",
       "play": "drive",
       "measure": {"probe": "camera", "field": "distance", "window": [8, 21], "agg": "mean"},
       "expect": {"op": ">=", "calibrate": 0.5}},
      {"name": "boat_stays_in_view", "kind": "probe", "weight": 2, "needs": ["boots_clean"],
       "describe": "Through the whole drive nothing stands between the camera and the boat.",
       "play": "drive",
       "measure": {"probe": "camera", "field": "occluded", "window": [2, 21], "agg": "max"},
       "expect": {"op": "<=", "value": 0}},
      {"name": "lap_count_updates", "kind": "probe", "weight": 3, "needs": ["boots_clean"],
       "describe": "After the boat is put beside the last buoy and driven on past it, the HUD shows lap 2 of 3.",
       "play": {"name": "round_last_buoy", "seconds": 12,
                "inputs": [{"t": 2, "teleport_to": {"name": "Buoy_3"}, "distance": 4, "hold": 1},
                           {"t": 4, "key": "<Keyboard>/w", "press": true},
                           {"t": 9, "key": "<Keyboard>/w", "press": false}]},
       "measure": {"probe": "ui", "select": {"kind": "text"}, "field": "text", "match": "LAP\\s*2/3", "of": "any",
                   "at": "end"},
       "expect": {"op": ">=", "value": 1}}]},
    {"name": "still_works", "checks": [
      {"name": "boat_still_moves", "kind": "probe", "weight": 0, "needs": ["boots_clean"],
       "describe": "The boat still travels under the drive's keys.",
       "play": "drive",
       "measure": {"probe": "player", "field": "moved", "agg": "max"},
       "expect": {"op": ">=", "value": 5}}]}
  ]
}
```

`builds`, `boots` and `still_works` carry `"weight": 0` because the start already passes them; the three probes of
`fixed`, one per issue of the brief, carry the weight. The task play reaches its spot with `teleport_to` an object
by its whole name, then drives on. `limits` are written out: left out, the schema's lower defaults apply. The
optional `quality` milestone is left out.
