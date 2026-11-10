---
name: unity-write-tasks
description: 'How to write the tasks a Unity game ships with (Tasks/ on the repo''s orphan tasks branch, never on main, one GameTask JSON per task, up to about 10 per game) so an agent can be given them in the game-creation environment: the tasks branch and its worktree, the one bar every task meets (a long thread of multiple edits from the game''s real history: many commits, many files, several systems, every task medium or hard, never easy or a single fix), the four kinds as where a thread comes from, picking seed.commit (the parent of the thread''s first attempt) and seed.reference (its final accepted fix), observation-only briefs, play_scene, milestones and deterministic probe checks (pass/fail never by a model judge or pixels; one required probe per issue), limits, and what keeps a task gradable and unleaked. Use when a Unity game session writes, moves or reviews tasks, and before calling a game complete.'
---

# Writing a game's tasks (Unity)

A game is complete when its repo's orphan `tasks` branch has `Tasks/`: tasks an LLM agent can be given on this game,
fair, checkable and not leaked. One file per task, `Tasks/<game>-<kind>-<slug>.json` (`kind`: `fix`, `corr`, `feat`,
`change`), in the task format `GameTask` (`game-task/1`, Unity flavour: `"engine": "unity"`), with `"name"` equal to
the file stem (run and grade ids depend on it; never rename a shipped task). Up to about 10 per game, every one a long
thread of multiple edits (section 1): fewer good tasks beat filling the count with short ones. The tasks branch is the
single source: tasks are loaded as `Tasks/*.json` from the repos' tasks branches, and the packager ships them in the
dataset split into the agent's and the grader's halves (docs/game-format.md). Write tasks with this skill and the
unity-game-factory tools only, never with another skill (AGENTS.md, "Only these skills").

> **The verifier is not in this repo yet.** The task schema (`docs/schemas/game-task.schema.json`), the validator
> (`tools/validate-game.py`), the probe plugin and the task check (`tools/task-check.py`, docs/task-check.md,
> docs/task-probes.md) come with it. Until they land: write and commit tasks by this skill, count each thread with
> `tools/thread-stats.py` (available now), and report the tasks as **written, not yet checked**. No task is VALID
> before the task check says so.

## 0. Where tasks live: the orphan `tasks` branch

**Task work never goes into the game's history.** Tasks live on a branch `tasks` of the game repo that shares no
history with main, checked out as a git worktree **outside** the game folder (`<root>/tasks/<slug>`). The branch holds
`Tasks/<game>-<kind>-<slug>.json`, a short `README.md` (what the branch is), and optionally `tasks-workflow.jsonl`
(one row per task written, `op:"task.write"`, `target:"Tasks/<name>.json"`; never in main's `workflow.jsonl`).

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
when told: `git -C <root>/tasks/<slug> push -u origin tasks` the first time, `git push` after.

- Never add `Tasks/` (or any task file) to main, never merge or cherry-pick between `tasks` and main, never point
  main's code, docs, README or `workflow.jsonl` at the tasks branch. The validator fails a repo whose main tracks
  anything under `Tasks/` or whose `tasks` branch shares history with main.
- The recording hooks ignore commits on the `tasks` branch, and the delivered history leaves it out, so committing
  tasks costs the game's record nothing.
- Seeds (`seed.commit`, `seed.reference`) are commits of main's history (ancestors of main's head) or of the task's
  own start branch `starts/<task name>` (section 2); pick them in the game checkout (`git -C <root>/games/<slug> log`),
  never on the tasks branch.

Commit tasks as you go, like any work (unity-commit-always skill), but on the tasks branch only.

## 1. The bar: long threads of multiple edits, nothing else

**The only tasks that meet our requirements are long threads of multiple edits.** A long task keeps one clean run of
a strong agent working about 25 minutes or more. That length is a guide, not a requirement: what counts is that a
strong agent can't solve it easily. You judge this in the session from the thread itself (section 6); we measure it
on every submitted task. A task is a stretch of the game's real history where its own sessions needed many commits,
several attempts or several rounds of directions, touching many files across several systems, before the outcome
held. Strong agents finish a single fix, one cause in one place, in minutes, however long the original took; such a
task is worthless to us and never ships, not even as an "easy" one. A task is `"difficulty": "medium"` or `"hard"`,
with the tag `long-thread`.

A thread qualifies only when all of these hold (`tools/unity_tasks.py` holds the numbers; thread-stats.py and the
validator count with it):

1. **Many edits.** From `seed.commit` to `seed.reference`, at least 4 commits change the game itself (`Assets/`,
   `Packages/`, `ProjectSettings/`), and the reference changes at least 5 game files against the start (a `.meta`
   file never counts on its own), with at least 100 code lines added plus removed (`.cs`, shaders, `.uss`/`.uxml`,
   `.asmdef`; store packs' own code under `ThirdParty/` doesn't count). Status, docs and `workflow.jsonl` commits don't
   count. Scenes, prefabs, materials and other assets don't count as code lines, even though they are YAML text.
2. **Several systems.** The change spans at least two of: gameplay code, editor code, shaders, config
   (`ProjectSettings/`, `Packages/`), scenes (`.unity`), prefabs, materials and textures, animation (`.anim`,
   `.controller`), UI (`.uxml`, `.uss`, UI folders), audio (`.mixer`, clips), data (`.asset` ScriptableObjects and
   other data files), other assets. The tools count them by extension and folder. A long thread confined to one
   method is a short task in disguise.
3. **Several outcomes.** At least 3 required outcome probes, one per issue the thread settled, so partial work earns
   partial credit (a compound ticket). A thread that settled only one observable thing is rarely long enough.
4. **The first attempt didn't hold, or the cause is far from the symptom.** The thread had a fix that was undone,
   complained about again ("still too low") or broke something else; or the symptom shows in one system and the cause
   sits in another (a HUD symptom from a ScriptableObject, a camera symptom from physics layers, a crash only in the
   player build, an intermittent or timing bug, a regression from an earlier change).
5. **Checkable by the grader.** Every required outcome is measurable in the grader's own plays: a scenario
   (`play_scene` arguments at the seed) that triggers the moment, or a task play whose scripted keys reach it (Input
   System key and button names, but no mouse movement). A thread no probe can measure is not a task.

**Never make a task easier (permanent).** After a task is first written, these are banned if they lower the bar:
widening a threshold or window, making a required probe optional, removing a probe, removing a requirement from the
brief or narrowing what it asks. A plainly broken probe may be fixed only so that it asks at least as much as the
brief. Otherwise drop the whole task and say so; fewer tasks is an acceptable result.

The four kinds say where the thread comes from; each is a long thread, never one commit:

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
commits (section 2).

Not a task: a single fix or a single commit, a one-setting change, a bug with one cause in one file, status chatter,
process rules, questions, praise, a fix that is only a re-import of assets the start does not have, a sweeping pass
resting on a pack imported later, anything whose outcome neither play nor code can show. If a game's history has fewer
than 10 qualifying threads, ship fewer tasks.

**Finding threads.** Walk the history for clusters: `git log --stat` around a feature, runs of commits on the same
files (`git log --format=%h -- <path>` piled up in a short window), several `user.direction` rows on one topic
(the workflow rows' `"direction"` links), fixes followed by "still", "again", "regressed" or a revert, a render
pipeline or package upgrade that broke a system and the commits that mended it. Read the whole span before picking
its ends.

## 2. Picking the commits

**Starts on the game's editor.** The checker opens a start exactly as committed, with the Unity version its
`ProjectSettings/ProjectVersion.txt` names (6000.3.x): it never upgrades, patches or rewrites a game. So `seed.commit`
and `seed.reference` must both be 6000.3 commits that compile and open as they are. When a thread's real start can't
be used as it is (it predates a package upgrade the reference depends on, or an unrelated later fix is needed for it to
compile), give it a made start:

- **B** = main's head. **S** (`seed.commit`) = B with the thread's change taken back out of the game itself
  (`Assets/`, `Packages/`, `ProjectSettings/`), re-created by hand where later work moved the code: the issue must
  really be back, and S must still compile. Every other path of S (`workflow.jsonl`, `Scripts/`, `Docs/`,
  `README.md`, manifests) is exactly as at the old pre-fix commit, so nothing in the start records or regenerates the
  fix. **R** (`seed.reference`) = a child of S whose tree is B's (`git commit-tree <B^{tree}> -p S`).
- Both live on the branch `starts/<task name>` (pointing at R), pushed with the game; the dataset ships every branch
  but `tasks`, so the delivered history holds them.
- Scenes and prefabs are YAML: a scene or prefab may go back to its pre-fix version only if no later commit changed
  it, or by re-creating the issue with an editor step; a binary asset only if no later commit changed it. Keep every
  `.meta` with its asset (a reverted asset with a newer `.meta`, or the reverse, breaks GUID references).
- For a thread, "the change" is the whole thread: S takes every commit of it back out, not only the last one, and the
  thread's commits on main (its count and files) are what qualify it; note them in the task's `tasks-workflow.jsonl`
  row (`"thread"`: first and last commit of main).

- **Read the code at `seed.commit`** and confirm the issue is there (the reference diff's removed lines, or a search).
- **The thread's real ends are often not the commits that say so**: a descriptive commit may touch only
  `workflow.jsonl` while the code is in the WIP commit before it. Use `git show --stat` around that time and the
  workflow rows that link the direction (`"direction"`). Start before the first attempt, so the agent faces every issue
  the thread settled, and end at the commit after which no more work on it followed.
- **The reference must compile and run**: the grader plays it beside the agent's result. If the last fix crashed until
  a later commit, extend the thread to the later one.
- **Chains and splits merge**: a person complained again after a fix ("still too low"): one task from before the first
  fix to the last. A direction with several issues fixed in separate commits: one compound task, one required probe
  per issue.
- **Spans may overlap; issues may not.** Two tasks may share commits, overlap or nest. Different threads that ran at
  the same time (a camera rework during a HUD pass) are separate tasks over the same commits. What never repeats is an
  issue: two tasks never test the same outcome, so dedupe against the game's existing tasks by issue (their briefs and
  required probes), not by commits. Merging still wins over splitting one thread into short tasks (section 1).
- **Measure the thread on its own commits.** The validator measures everything from `seed.commit` to
  `seed.reference`, so a short thread inside another thread's stretch can pass the floors on the other thread's work.
  Which commits are the thread's own is your call; list them and count them:
  `python <UGF_ROOT>/unity-game-factory/tools/thread-stats.py <UGF_ROOT>/games/<slug> <commit> <commit> ... --span <seed.commit>..<seed.reference>`
  (git only, seconds). A thread whose own commits are below the floors (section 6) is too short, whatever the span
  says: extend it, merge it with its neighbouring issues, or drop it. When you tell the person a task is ready, give
  its own line from the tool (commits, files, code lines, systems).
- Asset-only fixes are fine (the agent can make the same change through editor steps or code); drop one only when its
  outcome cannot be seen.

## 3. The instruction (the brief)

Write it from the context, never by quoting a person: no quotes, typos, capitals, profanity, "the owner said" or chat
wording. The reader is a capable developer who has never seen the game.

**Every brief is only an observation**: what a player or QA sees, in plain words, for every issue the thread settled.
It names no cause, no place to look, no file, script, component, prefab or asset, and no mechanism ("the camera feels
jammed against the ship", not "the deoccluder counts the water layer"). It never says how many changes are needed or
that the issues are related. Leave out the play_scene line, which the harness adds.

- **bug_fix**: a QA bug report listing each symptom: what happens, how to reproduce it, what is expected. Code
  identifiers only inside a quoted compiler error or exception line from the player log, which is what a log shows.
- **correction**: what is wrong and how a player sees it, item by item, then the wanted outcome.
- **feature / change**: a producer's ticket: what and why, how the player uses it (which key), the behaviours and
  looks wanted, what must still work. Close with the art bar: the project's own assets and engine features, no
  primitive placeholder shapes, no debug text.
- Describe the controls the player needs; the harness tells the agent which scene QA plays (`play_scene`).
- Never name the studio, its pipeline or its tools. Never describe the fix or any step of the thread.

## 4. `play_scene`

The game's first build scene is usually a title menu that simulated keys cannot leave, so a task almost always needs
`play_scene`: the scene path and the player's command-line arguments that start straight in the gameplay where the
issue shows (e.g. `{"scene": "Assets/Scenes/Harbor.unity", "args": ["-scenario", "2"]}`). Read the game's
command-line and scenario handling at `seed.commit` and check the scene exists there and is in the build list
(`ProjectSettings/EditorBuildSettings.asset`). Every grader play opens it (boots, idle and drive, the route, the before
and reference plays).

## 5. Milestones and checks: deterministic probes decide

**Pass/fail is decided only by checks the grader computes itself:** `build`, `boot`, `log_absent` and **`probe`**
checks. A model judge (`judge`, `code_judge`, `actions_judge`) never decides pass/fail and nothing is graded from pixel
statistics of the game's frames except the frame's mean luminance (`screen`), whose threshold is always calibrated or
relative to the start. Judges may stay as `"required": false` quality checks (taste, readability, how the agent
worked).

Each milestone is a reward group; a run that gets part of the way earns part of the reward. **A no-op scores zero
(permanent):** the score is the weighted share of checks passed, so every check the start already passes takes
`"weight": 0`: `builds`, `boots`, all of `still_works`, and any `log_absent` or `file_exists` true of the start. They
still gate: a run must pass the required ones to be solved. The usual order:

1. `builds`: `build` (`player_builds`: the scripts compile and a Windows player builds).
2. `boots`: `boot` 60 s (`boots_clean`: no exception in the player log), `needs` the build.
3. `fixed` (bug_fix, correction) / `done` (feature, change): `probe` checks of the reported outcomes, `required`,
   `needs` `boots_clean`: at least 3, one per issue the thread settled (split them over several milestones, e.g.
   `fixed_hud`, `fixed_camera`, when the issues are separable). Each one fails at the start for the reported reason
   and passes on the reference.
4. `still_works`: probes that what must keep working still does (the player still moves, the HUD still shows, the
   scene still loads its scenario).
5. `quality` (optional, never required): a `judge` for taste items no probe can capture, a `code_judge` for code
   quality, and the standard `actions_judge` `worked_well`.

A probe names one measurement and its threshold:

```json
{"name": "hero_on_ground", "kind": "probe", "required": true, "weight": 3, "needs": ["boots_clean"],
 "describe": "After the scenario starts, the hero stays on the ground near the west kiln tower instead of falling through the town.",
 "play": "look",
 "measure": {"probe": "player", "field": "y", "window": [3, 18], "agg": "min"},
 "expect": {"op": ">=", "calibrate": 0.5}}
```

Unity is Y-up: height is `y`.

- `play`: `look` (20 s idle), `drive` (22 s: W 1-6 s, D 6-8 s, W 8-13 s with Space at 9 s, A 13-15 s, W 15-21 s),
  a task play `{"name": ..., "seconds": ..., "inputs": [{"t", "key", "press"}]}` with Input System control names
  (`<Keyboard>/f2`, `<Mouse>/leftButton`, `<Gamepad>/buttonSouth`) when the outcome needs other input, or `editor`
  for asset facts.
- `measure.probe` (the Unity probe set; its exact fields come with the verifier, docs/task-probes.md): `player`
  (x/y/z/speed/moved/dist of the object the game marks as the player), `camera` (distance/height/pitch/fov/occluded/
  player_on_screen of the main camera), `objects` (select by component type, tag, layer, name, near; count, transform,
  bounds, active, collider, speed, `field:<Component>.<field>` by reflection), `ui` (what the UI shows on screen,
  whatever draws it: uGUI, TextMeshPro, UI Toolkit: text, count, place; number and clock for readouts), `drawn` (what
  is rendered near a point), `light` (illuminance and exposure at a point), `grading` (the post-processing volume
  result: exposure, colour, contrast), `audio` (what plays and how loud the listener hears it), `spawns`, `log`,
  `asset` (editor: a material's shader and properties, import settings, a ScriptableObject's fields).
- `expect`: a literal (`{"op": ">=", "value": 1}`) for facts (counts, booleans, "not the default material"), or
  `{"op": ">=", "calibrate": 0.5}` for continuous quantities: the grader measures the start and the reference in the
  grading environment and puts the threshold that fraction of the way from start to fix; `op` points to the fix's side.

Write probes from the game's own code at `seed.commit` and `seed.reference`: the real component types, tags, layers,
scene paths and UI element names. **Test the outcome a player sees, never the implementation**: another valid fix must
pass ("the hero stands on ground", "the stone breaks the wall piece it hits", "the light reaching the tunnel floor is
brighter", not "spawnHeight is 0.92" or "the method was changed"). Lighting and colour are measured from the engine
(`light`, `grading`), never from screenshots. `describe` says the assertion in plain words; it is shown in the grade,
never to the agent. Check names are unique and `needs` only names earlier checks; calibrated probes, `code_judge` and
`"reference": true` judges need `seed.reference`.

A task is valid only when it passes the task check: its start fails the task and its reference fix passes every
required check, and every required `still_works` probe already passes at the start. Once the verifier lands, the
game's tasks are checked **together, in one background run** (one run builds a commit several tasks share once, and
the person can leave it running and come back); its command and how to read its progress come with it.
**A task ships only when the task check says VALID**; for INVALID, fix the task, never the threshold toward what the
start happens to measure.

## 6. Difficulty, limits and what the validator enforces

- `difficulty` is `medium` or `hard` (never `easy`), and `tags` hold `long-thread`.
- `limits`: 400 turns, 480 min, 150 USD, 1800 s tool timeout unless the task needs more; a long thread needs room.
- The validator fails a task that is `easy`, has no `seed.reference`, has fewer than 3 required probes outside
  `still_works`, or whose reference changes fewer than 5 game files, fewer than 100 code lines or fewer than 2 systems
  against its start; for a seed on main it also fails fewer than 4 game-changing commits from `seed.commit` to
  `seed.reference`. These are floors, not targets: pick the longest threads the history has.
- **Judge difficulty in the session; never run the task with another agent.** Don't start a fresh Claude Code or Codex
  session on a task. Before committing, review each task against section 1 here, with the person: would a strong
  agent given only the brief and the start solve it easily (25 minutes is a guide, not a cut-off)? It would when the
  brief points at one place, the issues share one obvious cause, or the reference diff is mostly one file or one
  system. If so, extend the thread back to an earlier attempt, merge it with its neighbouring issues, or drop it. Tell
  the person which tasks you judged long enough and why, in a line each. We try every submitted task with a strong
  agent and measure its time; that grade decides.

Probes may measure the cause's effect directly, since the agent never sees them.

Wording: neutral and technical, for the game's people and creatures as for the rest. Describe meshes, bones, poses,
hits and reactions. Never use gore, injury or body-horror words ("crumpled body", "cut neck"); a cloud content
filter rejects such briefs and rubrics.

## 7. What must never reach the agent

The agent sees only the brief and the game at `seed.commit` (a commit of main, so without the tasks branch) as a fresh
repository without history, `Tasks/`, `History/` or `Dataset/` (those hold every task's checks and the reference
fixes). The grader's half (`milestones`: probes, rubrics, questions, `log_absent` patterns; and `seed.reference`) never
reaches it. So:

- the instruction holds nothing of the grader's half and does not describe the fix;
- nothing else at `seed.commit` should spell out the answer (a design-doc "known issues" line naming the cause, a
  comment or a `// TODO` saying how to fix it): if it does, pick another seed or another task;
- never point the game's code, docs or README at `Tasks/` or the tasks branch.

## 8. Pitfalls already hit (from the Unreal factory, in Unity terms)

| pitfall | rule |
|---|---|
| checks or log patterns shown in the brief | the agent gets the brief only |
| a model judge misread screenshots and failed a correct fix (or passed a wrong one) | pass/fail by probes only; judges are `"required": false` |
| a fix made only in assets (a prefab, a material) failed a code review | the cause is checked by its measured effect (a probe), never by reading the diff |
| a pixel threshold moved between GPUs | light and colour from the engine (`light`, `grading`); the frame's luminance (`screen`) only calibrated or relative to the start, never a literal |
| a level dressed with GPU-instanced or combined meshes counted as one object | count what is drawn (rendered pieces or triangles), calibrated or relative to the start, never a literal |
| a lamp turned off by disabling its GameObject (or intensity 0) read as lit | only lights the renderer draws count; a light's `enabled` and `intensity` are component fields |
| a lamp drawn by an emissive material rather than a Light read dark | read glow as rendered, not only Light components |
| a HUD drawn with UI Toolkit read as absent to a uGUI-only probe (or the reverse) | `ui`: what the UI shows on screen, whatever draws it |
| a hidden panel (alpha 0, `display: none`, inactive) still counted as shown | count only what is visible on screen |
| a probe that tests the reference's implementation ("spawnHeight = 0.92") | measure the outcome; another valid fix must pass |
| every AudioSource read silent because the play ran with audio off | `audio` reads what the listener hears; volumes calibrated or relative to the start |
| a teleport to fixed coordinates missed what each build placed itself | teleport to an object select (nearest match) |
| the game reset the player's position every frame, undoing a teleport | teleport with `hold` (seconds) |
| a menu that pages on real time (`Time.unscaledTime`) never reached its later pages in a play | a task-play input `{"t": ..., "wait": seconds}` |
| the brief said "scenario 1" but not `-scenario 1` | `play_scene` always set and checked at the seed |
| a UI element or component name guessed | read the names from the code and assets at `seed.commit` and `seed.reference` |
| quoting the person | write from context |
| a reference that crashed | the reference must compile and run |
| tasks solved in minutes: one cause, one place, the brief named the system | only long threads of multiple edits, compound probes, observation-only briefs (section 1) |
| a chain split into two short tasks | one task from before the first attempt to the fix that held |
| a bug that never shows in the grader's plays | a scenario or a task play that triggers the moment |
| a brief rejected by a content filter (injury wording) | neutral technical words: mesh, bones, pose, hit, reaction |
| a reverted asset kept its newer `.meta` and lost its references | an asset and its `.meta` always move together |
