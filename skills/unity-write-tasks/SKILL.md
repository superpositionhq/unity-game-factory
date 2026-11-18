---
name: unity-write-tasks
description: 'How to write the tasks a Unity game ships with (Tasks/ on the repo''s orphan tasks branch, never on main, one GameTask JSON per task, 5 to about 10 per game) so an agent can be given them in the game-creation environment: the tasks branch and its worktree, the one bar every task meets (a long thread of multiple edits from the game''s real history: many commits, many files, several systems, at least 4 hard, the rest medium, never easy or a single fix), the four kinds as where a thread comes from, picking seed.commit (the parent of the thread''s first attempt) and seed.reference (its final accepted fix), observation-only briefs, play_scene and play_args, deterministic probe checks (never by pixels; judges only for asked looks; one required probe per issue), every ask with a check, limits, and what keeps a task gradable and unleaked (checking it: unity-check-tasks). Use when a Unity game session writes, moves, checks or reviews tasks, or reads a task check''s result, and before calling a game complete.'
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
VALID. Commit tasks as you go, like any work (unity-commit-always skill), but on the tasks branch only. Then check
all of them, the no-op case and the oracle case, in one background run of `tools/task-check.py` (the unity-check-tasks
skill): only VALID tasks ship, so fix or remove every INVALID one before the game is packaged.

**VALID is needed, never enough.** Passing the no-op case and the oracle case does not make a task valid by itself.
The Lab's review reads the game's code and every check's whole definition (its plays, selectors, thresholds and
rubric) against the instruction, and marks a task that passes both cases but whose checks do not decide what the
instruction asks. So read each check's definition against the instruction and the game's code, never only its name
or its `describe` (section 5, "Every ask has a check"). _(why: the two cases show only that a check tells the start
from the reference, never that it reads what the instruction asks)_

## 1. The bar: long threads of multiple edits, nothing else

**The only tasks that meet our requirements are long threads of multiple edits.** A long task keeps one clean run of
a strong agent working about 25 minutes or more. That length is a guide, not a requirement: what counts is that a
strong agent can't solve it easily. You judge this in the session from the thread itself (section 6); we measure it
on every submitted task. A task is a stretch of the game's real history where its own sessions needed many commits,
several attempts or several rounds of directions, touching many files across several systems, before the outcome
held. Strong agents finish a single fix, one cause in one place, in minutes, however long it took in the game; such a
task is worthless to us and never ships, not even as an "easy" one. A task is `"difficulty": "hard"`, with
the tag `long-thread`. A game needs at least 4 hard tasks; the others may be medium (what a task that names no
difficulty is), none easier. Four is the floor, not a target: pick threads that make every task hard, and call a task
medium only when its thread is.

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
3. **Several outcomes.** At least 3 required outcome probes of weight above 0, one per issue the thread settled, so
   partial work earns partial credit (a compound ticket). A required probe of weight 0 is a guard, not an outcome, and a
   `seen` probe is a visual check, counted with the judges, never an outcome probe (a model's reading is no
   deterministic measure). A thread that settled only one observable thing is rarely long enough.
4. **The first attempt didn't hold, or the cause is far from the symptom.** The thread had a fix that was undone,
   complained about again ("still too low") or broke something else; or the symptom shows in one system and the cause
   sits in another (a HUD symptom from a ScriptableObject, a camera symptom from physics layers, a crash only in the
   player build, an intermittent or timing bug, a regression from an earlier change).
5. **Checkable by the grader.** Every required outcome is measurable in the grader's own plays: a scenario
   (`play_scene` and `play_args` at the seed) that triggers the moment, or a task play whose scripted inputs reach it
   (Input System control paths, mouse buttons, mouse axes and the cursor included, widget clicks, teleports, and
   touches: `tap` and `drag`, docs/task-probes.md section 1.3). The plays drive the Input System only: a game that
   reads the old Input Manager (`Input.GetKey`) takes no keys in them, and a menu drawn with `OnGUI` (`GUI.Button`,
   `GUI.TextField`) takes no click or key. A key does type into a uGUI or UI Toolkit text field the play has focused
   (a click on it first). A mobile game (its root has a `Platform.json`)
   is played at the phone's size and driven by touch: the unity-mobile-game skill, "Tasks on a mobile game".
   A thread no probe can measure is not a task. One issue of a compound thread that no probe can measure fairly
   stays in the brief and gets a required `looks_as_asked` rubric item (section 5), never one of the required probes.

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

**Where strong agents fail.** A strong agent tends to write the code and never check the outcome in the running
game. Prefer threads that settled such outcomes, and give each one its own probe in a play that reaches the moment:

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

Any Unity 6000.3 project can be a task's start or reference, whatever its patch. The checker works on a scratch copy
of each commit and opens the start and the reference with one editor: the 6000.3 patch the higher of their two
`ProjectSettings/ProjectVersion.txt` versions names when it is installed, else the newest installed 6000.3 patch above
it, never an older one. It never patches or rewrites the game: a newer editor may re-import its copy and rewrite the
copy's version files (`ProjectVersion.txt`, the package lock), never the game's. It refuses a start that isn't a 6000.3
project. So `seed.commit` and `seed.reference` must both be 6000.3 commits that compile and build as they are (the
validator checks the version). _(why: one editor for both sides gives the start and the reference the same readings,
and what is drawn can read a little differently from one patch to the next)_ When a thread's real start can't be used as it is (it predates a package upgrade the reference
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
- Describe the controls the player needs, and how a player gets from a title screen into play when the plays go
  through it (the button's caption), or say which scene QA plays; the harness tells the agent the scene and its
  arguments (`play_scene`, `play_args`). _(why: a play may only do what a player can, and a solver can't keep working
  what nobody told it is there)_
- **Say what QA's plays do to the game, where it matters.** The checker steps the game at a fixed 30 frames a second
  of game time and runs it as fast as the machine renders, so far faster than a clock (a play that reads sound or a
  hit stop runs at the pace of a clock); it may put the player somewhere at once and hold it there. Logic timed on
  the real clock (`Time.unscaledTime`, `Time.realtimeSinceStartup`) barely advances in such a play, and state that
  doesn't follow a moved player is left behind. QA may also set a fight up (put a foe in reach, deal a hit at a
  known moment), ends each play by closing the game (the game's quit code doesn't run, so anything saved is saved
  during play), and starts every play with clean saved data unless it follows the plays that write it. When the ask
  touches any of these, the ticket's QA note says so in a player's words ("QA fast-forwards the game", "QA may place
  the player at the gate", "QA closes the game without quitting from the menu"), and the checks' windows leave room
  for it. _(why: a correct solution that relies on the real clock, a quit handler or a leftover save fails every play,
  and its author couldn't know)_
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

**Pass/fail is decided by checks the grader computes itself:** `build`, `boot`, `log_absent` and **`probe`** checks, and
nothing is graded from pixel statistics of the game's frames except the frame's mean luminance (`screen`), whose
threshold is always calibrated or relative to the start. Two judges are required:
`looks_as_asked`, whose rubric items are the brief's own look-and-feel asks, and one in `still_works` of what must still
look as it did (below). Every other judge (`judge`, `code_judge`: taste, readability, code review) stays a `"required":
false` quality check. Nothing in a task reads the agent's tool calls: a task is graded on the game's outcome alone.
Retired: `actions_judge` checks and `trace` probes; never add one, take them out of a task you
edit. A task still needs required probes the grader decides without a judge (section 6). The probe language, every play,
measure and threshold with the rules that gate a task, is the task author's contract
[docs/task-probes.md](../../docs/task-probes.md), checked by the schema
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
   say `"required": false`, so the reference must pass it: a required `log_absent` the reference fails makes the task
   INVALID, since no solution like the reference could pass it (docs/task-check.md, "VALID and INVALID").
3. `fixed` (bug_fix, correction) / `done` (feature, change): `probe` checks of the reported outcomes, `required`,
   `needs` `boots_clean`: at least 3, one per issue the thread settled (split them over several milestones, e.g.
   `fixed_hud`, `fixed_camera`, when the issues are separable). Each one fails at the start for the reported reason
   and passes on the reference. The required `looks_as_asked` judge goes here when the brief asks for a look.
4. `still_works`: probes that what must keep working still does (the player still moves, the HUD still shows, the
   scene still loads its scenario), and a required judge with `"before": true` for what must still look as it did.
5. `quality` (optional, never required): a `judge` for taste items no probe can capture ("reads as a castle",
   readability of text over the scene), and a `code_judge` for code quality. A
   judge is written
   `{"name": ..., "kind": "code_judge", "question": ..., "rubric": [{"key": ..., "criterion": ...}]}` with
   `"required": false`; a `judge` (of the game, from screenshots and frames of the grader's own play) may also set
   `"before": true` to be shown the start beside the result, and `route`, `reference`, `plays` and `shots` (the task
   schema's `Judge` says what each does). **Every judge has plays of its own that show each rubric item at the
   moment it can be seen** (named `shot` inputs timed at the event the item asks about): a judge without plays sees
   only the idle look and the drive. An item the pictures cannot show scores 0 on either side, never a pass: fix
   the plays so the pictures show it. One subject per judge; no item about "every screen" unless its plays open
   every screen; no empty criterion such as "shows what the ticket asks". A `code_judge` may name the files its
   question is about in `focus` (up to 8 globs of project files, `["Assets/Scripts/Combat/*"]`): their diffs are
   shown first on both sides, so a long change still shows them.

**Every look-and-feel ask in the brief gets a required `looks_as_asked` rubric item** (such an ask gates the task
like any other: without an item of its own it ships unchecked). Go through the brief ask by ask: what a probe can measure gets a probe; what only an eye can tell (reads
clearly, fits the style, looks like the thing it is meant to be) gets its own rubric item, `"required": true`, in one
required `judge` named `looks_as_asked`, with `"before": true` and `"reference": true` when the seed has a reference.
A judge can misread screenshots, so word each item concretely, decidable from the screenshots alone, so the unchanged
game scores 0 on it and any solution that meets the brief scores 1. A rubric item asks exactly what its sentence
asks, in the sentence's words, never more: no stricter look, no added detail, no other quality. _(why: a solution
that does all the instruction says must score 1)_ What must still look as it did goes in a required
judge in `still_works` the same way. A judge is shown screenshots of the idle `look` and the `drive` on `play_scene`
and nothing else, unless the check names its own plays. When what must be seen appears only after a task-specific
key, in another scenario or scene, or past a title screen, give the check `plays`: up to 4 task plays that reach that
state (when a probe's play already does, reuse it under its name, written identically):

```json
{"name": "looks_as_asked", "kind": "judge", "required": true, "needs": ["boots_clean"], "before": true,
 "reference": true,
 "question": "With the upgrade menu open, does it read the way the request asks?",
 "rubric": [{"key": "costs_legible", "criterion": "Each upgrade's cost is legible against the panel behind it.",
             "required": true}],
 "plays": [{"name": "open_upgrades", "seconds": 10,
            "inputs": [{"t": 0.5, "key": "<Keyboard>/u", "press": true},
                       {"t": 0.7, "key": "<Keyboard>/u", "press": false}]}]}
```

The judge is shown 5 screenshots of each play, at 10, 30, 50, 70 and 90% of its `seconds`: time the inputs so the
state is on screen at those moments. Those moments, like every probe's window, are in play time, the game's own clock
at a fixed 30 frames a second: time them from what the recorded plays show (`probe.json`'s sample times, the
screenshots), never from real seconds. _(why: a play runs faster than a clock, so a moment timed on the wall clock
falls elsewhere in the play)_ A play also runs on the task's start (`"before": true`) and on the reference
(`"reference": true`), so it must run there too; a key that does nothing at the start is fine
([docs/task-probes.md](../../docs/task-probes.md), section 3.2).

**Motion is asked two ways.** Motion that is a number (eases instead of snapping, gentle, no sudden moves) is a probe:
a task play with `"every": 0.1` and a field over the window of the move, with `"agg": "step"` for the largest jump
between two samples ([docs/task-probes.md](../../docs/task-probes.md), section 2.1). Motion that can only be seen
(feet that slide, a trail) is a `looks_as_asked` item with a short play and many `shots` (2-20 of each play, plays
times shots 20 at most): a 5 s play with `"shots": 20` is a frame every 0.25 s, screenshot i of N at `seconds` x (i +
0.5) / N.

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
  facts. A task play lasts 5 to 300 s, and every time in it (an input's `t`, a hold, an `at`, an event's `within`)
  stays within 300 s. Make it as long as the asked moment needs and no longer. _(why: a moment that comes only after
  minutes of play can be reached; every second of a play is paid on both sides of every check run)_
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
  and how loud the listener hears it), `ground` (height and relief), `render` (what the renderer drew, against a
  budget: draw calls, triangles, texture memory; a literal threshold, in a play of its own), `spawns`, `log`, `asset` (editor: a material's
  `shader:` and `keyword:` values, `import:` settings, a ScriptableObject's `prop:`, and in a scene or prefab
  `material_default`, `material:<property>`, `mesh_collision`).
- On-screen text: `ui` (or `widgets`) first, and `ui`'s frame reader (a text select with a `rect`) for what `OnGUI`,
  `GL` or a mesh draws. Only text neither can read (drawn by a script, a shader or a texture, in a font the frame
  reader refuses) is a `seen` probe's: the model the visual checks use reads it from a `shot` input of the check's own
  task play, taken when the text holds still, with a loose `rect` or none (docs/task-probes.md, section 2.22). It is a
  visual check, counted with the judges: the task still needs a required probe besides it, and the task check saves
  its crops for you to read blind: type what each crop shows into `blind/answers.json` before opening the key
  (docs/task-check.md).
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
element names. **Everything a required probe or its play relies on exists at the start commit, or is something the
instruction says in a ticket's own words.** That covers object, component, member, tag, layer and widget names, the
scenes a play opens or loads, play arguments, exact strings and regular expressions, coordinates, and input sequences
that only work on the reference's own layout. A code name comes from the start, never from the instruction (below,
"Hints, never answers"); what a player sees or a ticket can say (a line of on-screen text the instruction or its title
quotes, the scene QA is told to play) may come from the instruction. Engine types (`Light`, `Camera`, `Canvas`) are
in every build, and a threshold relative to the start, calibrated, or a number the instruction states is fair. Anything else, a name only the reference has first of all (a component
type, tag, layer, object, scene or asset the thread itself created), moves the probe to what the player sees:
another fair build names it otherwise and reads as absent. Select what the thread creates by
what it does or where it is (`has`, `near`, `ui` with a `rect` or text, `drawn`, `lit`, `changed`; a part's direction
by `components` `world_yaw`/`world_pitch` with `near`, not `world_yaw:<Part>`); `validate-game.py` refuses a required
probe that names something the start lacks and the reference has, a part in a field such as `world_yaw:<Part>`
included. **Test the outcome a player
sees, never the implementation**: another valid fix must
pass ("the hero stands on ground", "the stone breaks the wall piece it hits", "the light reaching the tunnel floor
times the camera's exposure is brighter", not "spawnHeight is 0.92" or "the method was changed"). So prefer what the
player sees: on-screen text read with a loose match (`ui`, a regular expression for the words the ticket asks to
see, never an exact string it doesn't quote), objects by a tag or a type the start already has, a place reached by
`teleport_to` or by pinning an object, never by raw coordinates. **"Shown" means on screen**: a `widgets` select reads
the widgets on screen, so one hidden instead of removed is not shown when it is inactive, under a disabled Canvas or
a CanvasGroup at alpha 0, has its own graphic disabled, lies outside the frame, or lies wholly outside a scroll area's
view (a `RectMask2D`, a `Mask` or a UI Toolkit `overflow: hidden` above it). A widget hidden another way (its colour's
alpha at 0, scale 0, an empty text) still reads on screen: what is really drawn is `ui`'s to read.
Write `"visible": false` only when the check really means "exists while hidden". **Measure the effect the player sees, never one way of building it**: not a global such as the game's time scale
for "twice as fast" (read how far the thing gets in a time), not a part's offset from its parent (a correct fix
that re-parents it reads otherwise: read where it is in the world), not the root object's rotation when a child does
the moving, not a count of samples standing in for a count of events. **Select by what the thing is, not where the
old one was**: no `near` around the start's position for something the task asks to move (a camera that must stand
further back falls outside its own sphere). **Ask the second-solution question of every check:** would a correct solution
that names things differently, lays the level or its screens out differently, is made of more or fewer parts, or
hides a thing instead of removing it still pass? If not, the check reads the reference, not the ask: rewrite it. So
never a click or a tap at fixed screen coordinates, a teleport to where the reference put a thing, the reference's
object or widget names, or a count of the parts one build is made of (its child objects, components or widgets,
where the instruction states no number). _(why: each of these reads how the reference was built, so another correct
build fails it)_ Lighting and colour
are measured from the engine (`light`, `grading`), never from screenshots. `describe` says the assertion in plain
words; it is shown in the grade, never to the agent. Check names are unique and `needs` only names earlier checks;
calibrated probes, `code_judge` and `"reference": true` judges need `seed.reference`.

A task is valid only when it passes the task check in both of its cases: **the no-op case**, the game at
`seed.commit` unchanged, fails it for the reason its checks give, and **the oracle case**, the game at
`seed.reference`, passes every required check (build, boot, `log_absent`, `file_exists`, every required probe and
every required judge), with every required `still_works` probe already passing at the start and every probe a
threshold. Write the probes per [docs/task-probes.md](../../docs/task-probes.md), commit every task, then check them
with the **unity-check-tasks** skill: one background run of `tools/task-check.py` over all of the game's tasks, how to
read what it writes, how to score the judges and read the `seen` probes blind, and what to do for each failure.
**A task ships only when the task check says VALID on its final file, checked again after every edit**; for INVALID,
fix the task, never the threshold toward what the start happens to measure. _(why: the Lab's grader runs the same two
cases before any agent gets the task, and a task that fails either is void)_

**Every check is run before the task is handed in, on both builds, and you read what it measured**, not only the
verdict (`.task-checks\<task>\`: the result's `probes` values, each play's `probe.json` and `probe.log`): it fails at
the start and passes on the reference for the reason its `describe` gives; the play's inputs landed (no row in
`inputs_missed`, the click found its button, the teleport its object: a probe of a play whose input missed fails
whatever it measured; only an `optional` click may find nothing); the probe matched something (rows, on both sides
or at least on the side where the thing exists, not an empty selection that happens to compare right: below, "A
probe reads something"); the moment it reads falls inside its window on both sides with room to spare; a judge's
frames show the moment asked about. A check added or changed after the last run is unchecked until it runs again. A
threshold comes from the instruction or from the start (`start_plus`, `start_times`, a number the ticket states),
never from whatever makes the reference pass. **The reference does everything the instruction asks, in a place a play
can reach**: an ask the reference doesn't meet, or meets only where no play gets to, comes out of the instruction or
the reference is the wrong commit. A reference that fails its own check with a real reading means the check or the
reference is wrong, never the solver's problem: fix it before the task is handed in. A task with no reference cannot
be validated. _(why: the Lab's grader holds the reference to every required check, and the oracle case is the only
proof that a correct solution can pass)_

**The check asks no model, so you score the judges.** A required judge holds the task until you have scored its saved
screenshots blind, every rubric item of the start and the reference from 0 to 1 (unity-check-tasks skill, "Answer the
judges and the `seen` probes, blind"): the reference must pass it and the start must fail every required item (pass
it, for a judge in `still_works`). If either doesn't, reword the item or fix the plays so the pictures show the state,
never by asking less of the solution. Write both sides' scores in the task's notes (its `tasks-workflow.jsonl` row).

### Every ask has a check

Before the game is packaged, read each task you wrote, its instruction against its checks, yourself; no tool or
reviewer does this for you. The Lab's review reads every task the same way at submission and sends the game back when
an ask has no check at all, naming the task and the sentence. Some faults of a check the Lab may repair itself,
without sending the game back, and only these: restage a play with the steps the instruction gives a player; move a window, or a
judge's frames, to the moment the recorded play shows; retarget a selector to what the instruction names; click by
on-screen text, or wait; read from the screen a value whose property reads nothing; remove a click repeated after
its action already happened. The measure and its threshold stay as written. Everything else comes back to you.
Fix what you find in the task before it is packed:

- **Go through the instruction sentence by sentence.** The game's description, the controls line and the art line are
  context, and so are a bug report's cause and steps to reproduce, and a statement of what the task does not add or
  change; they ask nothing. How the work is to be built or documented ("fix it at its cause", "keep it in data, not
  code", "note it in the README") is implementation and needs no check, but an ask about what the player sees, hears
  or can do is never implementation. What should now be different is an ask; what must stay as it is is a keep.
  _(why: the Lab's review reads every sentence this way, and a sentence read as context that is really an ask ships
  unchecked)_
- **A sentence with several requests is several asks**, each with its own check: never join them because one check
  covers one of them. A list that describes one look or one scene is one ask, unless its items are asked for one by
  one. _(why: a run that does half of a joined ask passes the one check and is graded as having done all of it)_
- **In a bug report, the expected behaviour is the ask** when it is as broad as the symptom; when it is narrower, the
  symptom's own sentence is the ask too, and that it no longer happens needs a check. _(why: a fix that meets a narrow
  "expected" can leave the reported symptom in place)_
- **Words of time and number mean what they say.** "Never", "always", "each time", "until": in a bug report, the
  symptom no longer happens under the conditions the report names, so the play runs past the point where it was
  reported; reading one instant for an ask about a span covers it only in part. "Every" and "each" mean every case the
  instruction lists, one check per case. A number the instruction states is held on the side or sides it states, at
  that number: a looser bound, or one side of a two-sided number, covers it only in part. _(why: a check narrower
  than its sentence passes a solution that does only the part it reads)_
- **Read the check itself, never only its `describe`**: what the measure, its play and its threshold read is what is
  checked, and a `describe` that says more than they read is no coverage. A look or a motion reduced to one reading
  covers it only in part, and a listed look judged as a whole by a judge that doesn't name each item covers each only
  in part: give each its own rubric item. _(why: the grade decides on the measure, not the words beside it)_
- **Every ask has a check that would fail if that ask alone were not done**: a required probe for each key, direction,
  scenario or case it lists; a number it states held on both sides; a look-and-feel ask as a required
  `looks_as_asked` rubric item in the ask's own words, with the check's own `plays` when the state must be reached
  first; motion as a probe sampled every 0.1 s with `agg` `step`, or a required judge with a run of `shots`.
- **A keep that names a thing** ("the boss bar still starts full") has a required `still_works` check reading that
  thing; a bare "everything else keeps working" is covered by any required `still_works` check.
- **Never cover an ask with an optional probe, a `build`, `boot` or `package` check, or a `"required": false` quality
  check alone.** _(why: those decide nothing about the ask: a run that skips it still passes them)_
- **Every required check traces back to an ask or a keep of the instruction.** A required check of something the
  instruction never asks fails a solution that did everything asked: drop it, or make the ask part of the
  instruction. _(why: a solver can only be held to what it was told)_
- **A probe reads something.** A property that is null, a widget that is hidden, a selector that matches no rows, or
  one so broad it reads another thing measures nothing the ask is about. A `count`, `any`, `all` or `sum` over a
  selector that matches no rows reads 0, which looks like a real value, so a literal threshold such as `== 0` or
  `<= 0` can compare right on both sides while it reads nothing: confirm in `probe.json` that the selector matched
  rows on at least the side where the thing exists, and prefer a check that reads something the reference has. An
  outcome probe whose reading is the same on the start and the reference measures nothing: it is uncalibrated, never
  a pass. _(why: a check that reads nothing decides nothing about the ask, whatever its verdict)_
- **A play does what a player must do to reach the state it probes.** When the game starts on a title screen or a
  menu, every play that checks something in the level first clicks the start control the instruction names, by its
  on-screen text (`{"widget": "begin_run", "click": true}` clicks a button reading "Begin Run"), and waits for the
  level; or the instruction states the scene QA plays (`play_scene`). Never a
  shortcut only the reference has.
- **A play keeps its own preconditions true.** No input on the frame a state resets (press the key a few seconds
  into the round, not at its start). No teleport that breaks what the game holds together: carried objects, tethers,
  a range the instruction gives a limit to. Where a teleport is needed, move what the game moves together, or walk
  there.
- **A play never repeats an action that already happened.** No second click on Continue or Retry after it worked:
  the button is gone, and the click is a missed input.
- **A play needs no state the instruction never gives.** An existing save, a timer already run out, a filled-in
  profile: each play starts from clean saved data, so it reaches such a state only by the steps the instruction gives
  a player, by player steps of its own (it plays until the timer runs out), or by reading the plays that make it
  (`after`, below). _(why: a state no player is told how to reach is there on one build and not
  on another)_
- **Inputs a player would make, placed from the event.** A play's inputs are as fragile as they are guessed:
  - Click by the caption a player reads, never by screen coordinates (`cursor` and `tap` points are for what has no
    widget, at a place the start's own layout fixes). Write `widget` as the text is shown, spaces, punctuation, case
    and any script included (`"Save & quit"`, `"开始游戏"`): a caption equal to it is clicked first. _(why: the shown
    text is what the instruction and the player name, and an exact match never takes a button that only reads
    alike)_ Click by caption has limits (docs/task-probes.md, section 1.1): a widget whose name or type matches
    `widget` wins over a caption match, and `*` and `?` are wildcards on that name; a caption is compared whole
    (`"start"` does not click a button reading "Start Game"), and when no caption is equal, one that reads the same in
    lower case with every run of other characters as `_` is taken; a caption on two lines is written with a space at
    the break; only a uGUI Selectable or a UI Toolkit `Button` is clicked, and a UI Toolkit one by a submit, so a raw
    `ClickEvent` handler does not fire (section 8).
  - A click (and a tap on a widget) scrolls its control's own scroll area into view first, as a player would, and
    clicks it the next frame; it does not open a menu, change a tab or bring up a screen, and a control hidden any
    other way (inactive, outside the screen, outside a mask that is no scroll area) is still a missed input. So the
    play opens the menu, tab or screen first, then clicks. _(why: scrolling a list to an item is part of a player's
    click on it; opening a screen is a step of the play the task must write)_ The manual scroll inputs stay for what
    tests scrolling itself (a list that pages, a wheel the game reads): a `cursor` input over the list, then the mouse
    wheel (`{"t": 3.0, "key": "<Mouse>/scroll/y", "axis": -120}`, one frame each), or on a mobile game a `drag` across
    the list.
  - A click lands only where a player's pointer would: a control under a dialog, a dimming overlay or any image that
    takes the pointer is not clicked, and the row says `covered by another control`; `optional` and `disabled` never
    allow it. Close what covers it first, as a player would. _(why: a player's click lands on what is drawn over the
    button)_ To check that a control is not hidden under another, read the widgets field `covered`.
  - A control that shows only in some states (a confirmation shown only when a save exists) is clicked with
    `"optional": true`: when nothing matches at that moment the click is skipped and is no missed input. Never mark a
    click the play needs optional. _(why: a needed click that may find nothing hides a play that never got where it
    should)_
  - A click on a button the game shows disabled by design (a locked choice the instruction says stays locked) says
    `"disabled": true`: it has landed when the button is shown but disabled, and does nothing, as a player's click on
    it. Without the mark a click on a disabled button is a missed input. Never mark a click the play needs to press.
    _(why: a play may show that a locked choice stays locked, and a mark on a needed click hides a press that never
    happened)_
  - Windows and shots count fixed seconds of play time unless they are tied to the event itself. When the play makes
    the moment (the input at 2 s), put the input at a known time and place the window or the shot right after it,
    from the recorded play of both sides, with room. When the build decides when it comes (an animation's length, a
    load, an enemy's arrival, a dialog after the game's own delay), tie them to it: a measure's `since` counts its
    `window` and `at` from the first sample whose reading meets the event's `expect`, and a shot's `when` takes the
    picture in the first frame it does (docs/task-probes.md, section 2.23); give a play of a fast event `"every":
    0.1`, and an event a `within` that the reference meets with room. Never seconds guessed before the game ran.
    _(why: the event falls at another time on each build, and a window guessed in advance reads before or after it)_
- **A play that reads what another play writes names it in `after`. Never rely on the checker's order.** A task play
  that reads a save (a level reached, a profile filled in) lists the plays that write it:
  `"after": ["writes_save"]`, by their names. On each side they run, and end, first, and the reader starts on the saved data they
  left; every other play starts with none. A writer that failed still counts as run, so the failure shows in the
  reader's checks. Of two writers, one names the other in its own `after`. A writer saves during its play, before
  its time is up: `OnApplicationQuit` is not run (docs/task-probes.md, 1.1). A play whose check needs a first run (no
  save, default settings) may say `"fresh": true`, never together with `after`. _(why: every play without `after`
  already starts with the saved data cleared; the mark states it for the reader)_
- **An ask that shows only after a contact** (a blow landing, getting hit, a stun, the last foe of a group falling) is
  staged, never left out because "no fixed play guarantees the contact": `pin` the foe or target ahead of the player
  (a target the build invents: the nearest thing a player can shove near the player) and press the task's own attack
  key; `set` a start-named health only to set the fight up; `damage` for a hit taken at a known moment (the game's
  own `IDamageable.TakeDamage`); `where` to pick the live ones (docs/task-probes.md, section 1.4). Read the result
  deterministically: a state change in a probe one sentence explains (a `prop:` of the component holding health,
  state or phase, `damage_taken`); a hit stop by objects `frozen` (the one struck holds still for a moment), never a judge (no
  screenshot shows it), and by `world` `time_scale` only when the ticket itself says the game's time slows or stops:
  a build may stop the object alone; a stagger, knock-back or interrupted action by a start-named state or Animator parameter, the object unable to
  move, or its distance from the attacker, never a judge. What it looks like (sparks, colours, glow) goes to the
  required visual judge on named frames across the contact. Names come from the start commit; `set` and `where` only
  on members the task does not ask to change. Where the nearest thing a player can shove is not surely the target,
  the ask is listed as not testable. A stage nothing took (a pin no object matches, a damage with no target) is a
  missed input: every probe of that play fails, so read the reference's `inputs_missed` and `probe.log` until the
  stages land. Never use an input or measure that docs/task-probes.md doesn't list.
- **Hints, never answers.** An instruction may hint, in the ticket's own words, at what a player
  must see, hear or meet, or what must exist in the world, and may say that hits go through the game's damage
  interface. It never says how the build names or stores it: no class, field, method, tag, asset or file name, nothing
  that is really the check's read target dictated to the solver. Names a check uses come from the start commit.
  - Good: "Every blow that lands throws sparks and a short pause." "A training post stands in the yard to practise
    on." "Hits reach her through the game's damage interface."
  - Refused: "Add a component called TrainingPost to the yard." "Keep the enemy's health in a field called health."
    "Tag each generator Generator so QA can find it."
  _(why: a ticket that names the check's read target hands the solver the answer)_
- **A sound ask** is checked by a sound starting when the event happens: `audio` `started_audible` by its `owner`, or
  near the source (`select.near`) only when the ticket places the sound in the world (a 2D sound is near nothing), in
  a window right after the event (give it 0.2 s of room); a sound that fades in, and music, by `audible`, `volume` or
  `level`; `sounds` and `repeats`
  when the ticket asks for distinct sounds ("each gun has its own sound", "never the same take twice"). What the
  sound is, how it sounds, is never checked. A `PlayOneShot` clip has no name the probe can tell, and one played on a
  source that is already playing is not seen at all (docs/task-probes.md, section 2.16): where the start plays its
  sounds that way, read the mix's `level` rising in the window instead, and never write `sounds` or `repeats`. The
  count of starts is a lower bound for the same reason: write "a sound starts" (`>=`), never "plays once" or "never
  twice" (`<`, `<=`, `==`; the validator warns), unless the start plays that sound as a source's own clip.
- **An ask that cannot be checked fairly** comes out: rewrite the instruction so it no longer asks for it, rather than
  ship an ask nothing checks. The instruction stays plain prose, never fields.
- **Nothing is asked that the checker cannot run.** Saving across plays can be checked (a play that names its
  writer in `after`, above). What a sound is like (a sound the game's characters hear and react to, or one that must
  start at a moment the game decides, is an ask like any other), how the packaged build behaves outside a play, a
  frame rate or performance on given hardware, and a given screen size or resolution (what must be seen on screen,
  at any size, stays an ask) cannot: never write them as asks. _(why: the Lab's review leaves such asks out and no
  play can show them, so they would ship unchecked)_

## 6. Difficulty, limits and what the validator enforces

- `difficulty` is `hard`; a game needs at least 4 `hard` tasks, the others may be `medium`, none easier (a task that
  names no difficulty counts as medium; four is the floor, so aim every task at hard), and `tags` hold `long-thread`. It is your own estimate of the thread; our runs of the task decide
  its difficulty (last item below).
- `limits`: 400 turns, 480 min, 150 USD, 1800 s tool timeout unless the task needs more; a long thread needs room.
- `tools/validate-game.py` fails a game with fewer than 5 tasks or fewer than 4 `hard` ones, and a task that is
  `easy`, has no `seed.reference`, has fewer than 3 required probes of weight above 0 outside `still_works`, or whose reference changes fewer than 5 game files, fewer than 100 code lines or fewer than 2
  systems against its start; for a seed on main it also fails fewer than 4 game-changing commits from `seed.commit` to
  `seed.reference`, and any required probe that names a component type, tag, layer, scene or asset the reference has
  and the start doesn't (section 5). These are floors, not targets: pick the longest threads the history has. It also refuses a task
  without the `long-thread` tag, a weighted check a no-op passes (section 5) and anything against the format rules of
  section 0.
- **Judge difficulty in the session; never run the task with another agent** (a try is long and tells you nothing
  the session can't judge; the Lab tries every submitted task itself). Don't run `tools/task-try.py` or start a fresh
  Claude Code or Codex session on a task. Before committing, review each task against section 1 here, with the
  person: would a strong agent given only the brief and the start solve it easily (25 minutes is a guide, not a
  cut-off)? It would when the brief points at one place, the issues share one obvious cause, or the reference diff is
  mostly one file or one system. If so, extend the thread back to an earlier attempt, merge it with its neighbouring
  issues, or drop it. Tell the person which tasks you judged long enough and why, in a line each. The Lab tries every submitted task with a strong agent and
  measures its time; that grade decides.

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
- never point the game's code, docs or README at `Tasks/` or the tasks branch;
- nothing in the game, the instruction or the task's files speaks to the grader or a reviewer (text telling a judge
  what to see or answer). _(why: the grader reads such text as an attempt to sway it, and the run that carries it
  scores nothing)_

## 8. Pitfalls

| pitfall | rule |
|---|---|
| checks or log patterns shown in the brief | the agent gets the brief only |
| an ask in the brief that no check reads (the Lab's review sends the game back for it) | read each task against its checks before packing (section 5, "Every ask has a check") |
| a probe or its play relies on something only the reference has and the instruction never says (a widget or member name, a scene, an exact on-screen string, a teleport coordinate, a click or tap at a fixed screen point, a count of key presses that solves the reference's layout, a count of the parts the reference is made of): a correct solution built another way reads "nothing it selects was measured" or another number | everything a required probe or its play relies on is at the start commit or in the instruction's own words; else read what the player sees (section 5) |
| a "must not be shown" check fails a solution that hides the widget instead of removing it, and a hidden widget passes a "must be shown" check | "shown" means on screen: `widgets` reads the widgets on screen (not inactive, not under a disabled Canvas or a CanvasGroup at alpha 0, inside the frame, not scrolled out of a scroll area's view); what is drawn is `ui`'s; `"visible": false` only for "exists while hidden" |
| a check written without running the game fails on the reference: an invented threshold, a window that misses the event, a click when no button is shown, a judge asking for what the frames don't show | run every check on both builds and read what it measured before handing the task in (section 5) |
| an instruction asks for what no play can show (how a sound sounds, the packaged build, a frame rate on given hardware, a given screen size) | never an ask; saving across plays is checked with `after` |
| a model judge misreads screenshots and fails a correct fix (or passes a wrong one) | required probes for what can be measured; only the brief's own looks in a required judge (`looks_as_asked`, still-looks in `still_works`), each item concrete and decidable from the screenshots; every other judge `"required": false` |
| every play probes the level while the game still sits on a title screen the task itself adds | a play clicks the start control the instruction names, by its text, and waits; or the instruction states the scene QA plays |
| "twice as fast" read from the game's time scale, a part read by its offset from its parent, a moving child read by its root's rotation, samples counted as events: a correct build made another way fails | measure the effect the player sees, in the world |
| a `near` sphere around where the start had the thing, for a task that asks to move it | select by what the thing is (a component or tag the start has, `has`), not where the old one was |
| an input sent on the frame the round resets is lost; a teleport leaves the carried object or the tether behind | a play keeps its own preconditions: input a few seconds in; move what the game moves together |
| a second click on a button the first click already took (and closed) is a missed input | a play never repeats an action that already happened |
| a judge is shown only the title screen, or never the state a task's own key opens; an item its pictures cannot show is scored as a pass | the `judge` check names its own `plays` that reach it, with named `shot` inputs timed at the event (section 5); an item the pictures cannot show scores 0 on either side, then the plays are fixed |
| a few stills can't show whether a move eases or feet slide | a number: a probe sampled every 0.1 s with `agg` `step`; only seen: a `looks_as_asked` item with a short play and `shots` (section 5) |
| a fix made only in assets (a prefab, a material) fails a code review | the cause is checked by its measured effect (a probe), never by reading the diff |
| a pixel threshold moves between GPUs | light and colour from the engine (`light`, `grading`); the frame's luminance (`screen`) only calibrated or relative to the start, never a literal |
| trees painted on a Terrain count as one object | count placed pieces (`pieces`), not objects or components |
| placed pieces combined into a few meshes read as a few pieces against a threshold set on many | count the drawn geometry (`pieces` `visible_triangles`), calibrated or relative to the start, never a literal |
| a threshold set on the rows a sample keeps (at most 200), not on every match | counts and `of` read every match (`total` and `full`) |
| a light's turn read relative to its own object | `world_yaw:`/`world_pitch:`/`forward:` read the Light's part in the world |
| a part's direction read by a name only the reference has | `components` `world_yaw`/`world_pitch` of the part picked by `near`, `component` or `owner`, with `to_angle` |
| a lamp switched off (Light disabled, its object inactive, intensity 0) reads as lit | the `light` probe counts only Lights that are on; a lamp's `on` and `intensity` are `components` fields |
| a hidden panel (CanvasGroup alpha 0, `display: none`, an inactive object, an item scrolled out of its list's view) still counts as shown | `"visible": true` in a widget select counts only what the game shows (its state: a fully transparent widget still counts), `ui` only what is drawn on screen |
| a sound judged by its AudioSource being enabled, not by what the player hears | `audio`: sources playing at their volume at the listener, and the mix's `level`; volumes and level calibrated or relative to the start |
| relief judged by the height of one spot | `ground` over a box: `range`, calibrated or relative to the start |
| a teleport to fixed coordinates misses what each build places itself | `teleport_to` an object select (nearest match), facing it or a point |
| a `teleport_to` by a `name` wildcard (`Coin*`) goes to the `CoinSpawner` beside the player, not to a coin | a select takes every object that fits, and `teleport_to` the nearest: select the instances by their own component or whole name (`Coin(Clone)`) when the start has them too, by what they carry (`has`, next row) when the task adds them, and read `probe.log` in the reference's play |
| a select by component type or tag also matches the scene's own objects, or names the type the reference happens to use | select by what the object carries: `has` (a part that is `lit`, `visible`, of a `component`, `near` a point); a parent that holds such objects (a spawner) matches too, so add a `component` the object itself has and the parent lacks |
| cars that are parts of one object have no position or speed of their own | `components` fields `x`, `y`, `z`, `speed` |
| a broken object keeps its pieces drawn and tagged, so counts can't see it break | object `simulating` and `spread`, component `extent_*` and `simulating` |
| an object that breaks by hiding a part or by animating its pieces reads whole to `spread`, `extent_*` and `simulating` | object or component `changed` (since the start; `bounds_change` and `pose_change` calibrated or relative to the start) |
| a lamp drawn by an emissive material rather than a Light reads dark to `on`, `intensity` and `light` | object or component `lit` (any Light that is on or glowing renderer; `glow` calibrated or relative to the start) |
| a HUD made with UI Toolkit reads as absent to a uGUI widget select (or the reverse) | `ui`: what the UI shows on screen, whatever draws it (text with `match`, counts by `kind` and `rect`) |
| a lamp whose glow comes from a Shader Graph's own nodes has no reading from its material | `lit` and `glow` as they are: a renderer whose shader lacks the standard emission interface, or whose colour has a texture, is read as rendered |
| a menu drawn with `OnGUI` (`GUI.Button`, `GUI.TextField`, a click read from `Event.current`) takes no click or key in a play | reach the state another way (a key bound in the game's Input System actions, a scenario, a teleport, a `set`) or grade an outcome that needs no click; a hit box the game tests against `Mouse.current` is clicked by `cursor` and `<Mouse>/leftButton` |
| a task needs a name or a code typed into a text field | a widget click on the uGUI `InputField` or `TMP_InputField` (a cursor click on a UI Toolkit `TextField`), then one key at a time (`<Keyboard>/a` press and release; `leftShift` held for capitals), `<Keyboard>/enter` to submit; read the field's `widgets` `text` |
| a readout drawn with `OnGUI`, `GL` lines or a custom mesh reads as absent to `ui`'s element rows | `ui` `text` with `match` on a `select` of `"kind": "text"` with a `rect` around the readout (read from the frame as drawn); there are no line elements, so if it still doesn't read, grade another outcome |
| text drawn by a script, a shader or a texture that `ui` and its frame reader can't read has no reading | a `seen` probe on a `shot` input of its own play, with a loose `rect` (a tight one fails a build that draws it elsewhere); a visual check besides the task's required probes, never in their place |
| a task needs a readout to keep updating, and it may be drawn by any UI system | `ui` `signature` with `"agg": "changes"` on a `select` with a `rect` around the readout (calibrated or relative to the start) |
| an effect (particles, a panned material, a spinning mesh) needs a reading that it shows and moves | `drawn` `near` a point: `drawn`, and `motion` calibrated or relative to the start |
| a spinning part has no speed of its own, or would need its object's name | `spin` of `components` near a point or by `owner`, or an object's `spin`; calibrated or relative to the start |
| duplicate effects after a restart go unseen | `components` with `"effect": true` and `near`: `count` of live effects, read after the restart |
| a score or a timer has to be read as a number, not a string | `ui` `number` or `clock` on a `select` of `"kind": "text"` with a `rect`; `rises`, `falls`, `range` over the window |
| a lamp lit only by particles reads dark | `lit` and `glow` as they are: particle systems, trails and visual effects are sources |
| a beam's length needs a reading | `drawn` along a `line` from its source: `reach` or `length`, calibrated or relative to the start |
| a surface's tint change (not emissive) needs a reading | `drawn` `near` it: `base_r`/`base_g`/`base_b` or `base_change`, calibrated or relative to the start |
| the nearest object a player can push would have to be named by type | `has` with `"simulating": true`, in a select or `teleport_to` |
| the game resets the player's position every frame, undoing a teleport | `teleport` or `teleport_to` with `hold` (seconds) |
| a lamp above matches together with one below it | `near` with `y_min`/`y_max` (world, or `y_relative` to the point) |
| a menu that pages on real time (`Time.unscaledTime`, `Time.realtimeSinceStartup`) never reaches its later pages in a play | a task-play input `{"t": ..., "wait": seconds}`: the play's clock holds while the game runs on in real time |
| a boot scene's `Start` sets up what the play needs, and the play opens `play_scene` before it runs | a boot scene only gets `Awake` and `OnEnable` before `play_scene` replaces it: start such a game through its own `play_args` with `play_scene` null |
| `"of": "first"` over a broad select reads another object on the reference (a scene edit changes the order) | matches come in hierarchy order, which a scene edit can change: select by name, tag or `near` |
| `spawns` of `MeshRenderer` counts every child of each spawned thing | name a component that sits once per thing (the coin's own script, when the start has it too); in a task that adds the thing no such component is sure, so count how often an `objects` `count` over a `has` select rises (docs/task-probes.md, section 2.9) |
| `teleport_to` a hovering target leaves the player in the air | the player's pivot goes to the target's own height plus `offset`'s y, with no ground snap: give a negative y `offset` |
| a play that reads a save, or needs a state the instruction never gives, runs on clean saved data and reads nothing (a later level not yet unlocked, an empty profile, a timer not yet run out) | the reading play names its writers in `after`; every other play starts clean (docs/task-probes.md, 1.1) |
| a sound played with `PlayOneShot` matches no `sound` select | the probe sees only a source's own clip, never a one-shot's: read `started_audible` by `owner` or `near`, or `level` in an audio play |
| a widget click doesn't fire a UI Toolkit button that handles `ClickEvent` | a widget click sends a submit (`Button.clicked`); for a raw `ClickEvent` use a `cursor` input, then press and release `<Mouse>/leftButton` |
| an editor `shader:` value compared with `==` reads back as stored (0.2 as 0.19999995827674866) | floats come back as stored: `>=`/`<=` a little either side |
| a readout read through the frame touches its rect's edge and reads nothing | give the `ui` rect a margin of background around the text |
| a probe that isn't required but passes at the start carries weight | every check the start passes takes `"weight": 0`, a `"required": false` probe too |
| a probe that tests the reference's implementation ("spawnHeight = 0.92") | measure the outcome; another valid fix must pass |
| the brief says "scenario 1" but the task doesn't set `-scenario 1` | `play_scene` and `play_args` always set and checked at the seed |
| a UI element or component name guessed | read the names from the code and assets at `seed.commit` |
| a probe names a component, tag or scene only the reference has, so a fair build that names it otherwise reads as absent | select what the thread creates by what it does or where it is; the validator refuses a reference-only name |
| a run writes the feature but never runs the game to see it, and the task has no probe of the moment | a play that triggers each piece of feedback, and a probe of what the player sees then |
| a judge's pictures come from views the game itself lists, so a build could dress only those spots | the task's own tour: `scene`, `teleport_to` what the build made, `view`, named `shot` inputs (docs/task-probes.md, section 1.1); never a view list from the game's files |
| quoting the person | write from context |
| a reference that crashes | the reference must compile and run |
| a task solved in minutes: one cause, one place, a brief that names the system | only long threads of multiple edits, compound probes, observation-only briefs (section 1) |
| a chain split into two short tasks | one task from before the first attempt to the fix that held |
| a bug that never shows in the grader's plays | a scenario or a task play that triggers the moment |
| a brief rejected by a content filter (injury wording) | neutral technical words: mesh, bones, pose, hit, reaction |
| a reverted asset keeps its newer `.meta` and loses its references | an asset and its `.meta` always move together |
| an ask that shows only after a contact is left without a check | stage the contact (`pin`, `damage`, `set`) and read it deterministically (section 5) |
| an ask the reference never does, or does only where no play reaches | the reference does every ask in a place a play reaches, or the ask comes out of the instruction (section 5) |
| a threshold picked so the reference passes | a threshold comes from the instruction, the start, or calibration between the two |
| a check passes the task check but measures nothing it meant to (an empty selection, a value read before the moment) | read each probe's rows and sample times on both sides, not only the verdict (unity-check-tasks skill, section 5) |
| a render budget read in a play that also tours the level or captures for other measures | a `render` reading goes in a play of its own, where the game is heaviest (docs/task-probes.md, section 2.20) |
| a required check of something the instruction never asks | every required check traces back to an ask or a keep; drop it or put the ask in the instruction |
| a task VALID in both cases whose checks don't decide what the instruction asks (the Lab's review marks it) | VALID is needed, never enough: read each check's whole definition (plays, selectors, thresholds, rubric) against the instruction and the game's code (section 0) |
| a `count`, `any`, `all` or `sum` over a selector that matches no rows reads 0, so a literal `== 0` or `<= 0` compares right on both sides while it reads nothing | confirm in `probe.json` that the selector matched rows on the side where the thing exists; prefer a check that reads something the reference has (section 5, "A probe reads something") |
| a click on a control in a menu, tab or screen the play never opened is a missed input (`no visible button matches it`): a click scrolls its own scroll area, nothing else | the play opens the menu, tab or screen first, then clicks (section 5) |
| a click on a control under a dialog or an overlay that takes the pointer is a missed input (`covered by another control`), whatever its marks | the play closes what covers it first, as a player would; to check a control isn't hidden, read `covered` (section 5) |
| a window or a shot at fixed seconds reads before or after an event whose time the build decides | tie it to the event: `since` on the measure, `when` on the shot, a play with `"every": 0.1` (section 5) |
| a shot's event never comes (`its event never happened`, kind `shot_when`): no picture, a missed input | the event's measure reads what the reference shows at that moment, and its `within` leaves room |
| a confirmation that shows only in some states (only when a save exists) is a missed input on the side where it doesn't show | click it with `"optional": true`; never mark a click the play needs optional (section 5) |
| a click by caption takes another button whose name matches `widget` first, or never matches a button whose caption it gives only in part | a name or type match wins over a caption, and a caption is compared whole: pick a `widget` no other button's name or type matches, and write the whole caption exactly as shown (docs/task-probes.md, section 1.1) |
| a click on a button the game disables by design is a missed input (`shown but disabled`) | when the instruction says the choice stays locked, mark the click `"disabled": true`; else wait until the game enables it (section 5) |
| a window or a shot set at seconds guessed before the game ran reads before or after the event | put the input that triggers the event at a known time and place the window or shot right after it, from both sides' recorded plays, with room (section 5) |
| a rubric item asks more than its sentence (a stricter look, an added detail), so a solution that does all the instruction says scores below 1 | a rubric item asks exactly what its sentence asks, in the sentence's words (section 5) |

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
