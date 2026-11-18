---
name: unity-check-tasks
description: 'How to validate a Unity game''s tasks on your own machine before they ship: the no-op case (the game at seed.commit, unchanged, must FAIL the task for the reason its checks give) and the oracle case (the game at seed.reference, the game''s own fix, must PASS every required check), both run by tools/task-check.py in one background run; the exact commands, what each run writes and which files to read (progress, the verdict, the probe values, each play''s probe.json, shots, judge-shots and seen-shots with their blind answers), what VALID, INVALID and ERROR mean, a table of failure patterns with what to do for each, and the rule that a task is not finished until both cases are right on its final file. Use after writing or editing any task, before calling a task or a game done, and whenever you read a task check''s result.'
---

# Checking a game's tasks (Unity): the no-op case and the oracle case

The Lab's grader checks every task before any agent is given it, in two cases:

- **the no-op case**: the game at the task's start, `seed.commit`, exactly as an agent that changed nothing would leave
  it. It must **fail** the task, and fail it for the reason the checks give;
- **the oracle case**: the game at the task's reference, `seed.reference`, the game's own accepted fix of the thread.
  It must **pass every required check**.

A task whose no-op passes rewards no work, and a task whose oracle fails can't be passed by a correct solution: either
way the task is void, and the Lab runs no agent on it. The task checker
(`tools/task-check.py`) runs both cases on your machine as the Lab's grader runs them, so you find out first. Write
the tasks with the unity-write-tasks skill; this skill is how you check them and read the result. `<UGF_ROOT>` is the
machine root (`%UGF_ROOT%`, `C:\Users\<you>\UnityWork` by default); every `tools\...` and `docs\...` path here is in
`<UGF_ROOT>\unity-game-factory`. The full reference is [docs/task-check.md](../../docs/task-check.md).

**A task is not finished until both cases are right, on its final task file.** Check it after every edit to the file,
however small, and read what it measured, not only the verdict (section 5). _(why: a verdict is only about the file
it read; an edit after the last check is unchecked, and a VALID line can still hide a check that measured nothing it
meant to)_

**VALID is necessary, not sufficient.** Passing both cases does not make a task valid by itself: the Lab's review reads
the game's code and every check's whole definition (its plays, selectors, thresholds and rubric) against the
instruction, and marks a task that passes both cases but whose checks do not decide what the instruction asks. So
read each check's definition against the instruction and the game's code, never only its name or its `describe`
(unity-write-tasks skill, section 5, "Every ask has a check"). _(why: the two cases show only that a check tells the
start from the reference, never that it reads what the instruction asks)_

## 1. Before you run it

- Commit the task on the tasks branch and run the validator first: `python
  <UGF_ROOT>\unity-game-factory\tools\validate-game.py <UGF_ROOT>\games\<slug>`. Its `repo: Tasks` lines are about
  your tasks; fix every `x` line there before the task check. _(why: the task check refuses a task that doesn't
  validate, and the validator is seconds while a check is many minutes)_
- **Unity Hub is signed in with an active licence.** Without one every build and the editor pass exit 198 and the
  check is an ERROR, never a verdict. _(why: a machine that can't run Unity says nothing about the task)_
- The project's Unity 6000.3 editor is installed, both commits' Git LFS objects are in the local store
  (`git -C <UGF_ROOT>\games\<slug> lfs fetch origin <commit>`), the repo's drive has room above the machine's floor
  (50 GB unless the machine config says otherwise), and the session is an interactive Windows session (the plays run
  on a desktop of their own).
- One run per game at a time, from an interactive shell. _(why: two runs on one game share its results folder and
  overwrite each other's progress and evidence)_

## 2. Run both cases: the commands

One task check runs both cases of a task: it builds the start and the reference, plays both, and grades each.
Check every task of the game **together, in one background run** (a commit several tasks share is built once), started
as its own process so it outlives your turn and no tool timeout cuts it short (PowerShell, under either agent):

```powershell
New-Item -ItemType Directory -Force <UGF_ROOT>\games\<slug>\.task-checks | Out-Null
Start-Process python -WindowStyle Hidden -WorkingDirectory <UGF_ROOT>\unity-game-factory `
  -ArgumentList 'tools\task-check.py', '<UGF_ROOT>\games\<slug>', '--all' `
  -RedirectStandardOutput <UGF_ROOT>\games\<slug>\.task-checks\run.out `
  -RedirectStandardError <UGF_ROOT>\games\<slug>\.task-checks\run.log
```

- Recheck the tasks you changed by name, one `--task` each, in place of `--all`:
  `python tools\task-check.py <UGF_ROOT>\games\<slug> --task <task-name> --task <other-task-name>`.
- Check a task file you haven't committed yet by its path:
  `python tools\task-check.py <UGF_ROOT>\games\<slug> --task <UGF_ROOT>\tasks\<slug>\Tasks\<task-name>.json`.
  Commit it and check it once more from the branch before it ships (the result names the file it read).
- A scratch folder Unity can't build in (the checker refuses a project path over 90 characters) stops the run at once
  with a usage error in `run.log`: add `'--scratch', 'C:\tc'` (a short folder on the repo's drive).
- Tell the person it is running, roughly how long (several minutes to over half an hour a task, most of it builds;
  longer for a large game or a busy machine), and that they can leave it.

The other options (`--keep` to keep the built copies, `--out`, `--direct`, `--timeout`, `--build-timeout`,
`--no-judge-shots`) are in [docs/task-check.md](../../docs/task-check.md). `--no-judge-shots` leaves every required
judge unscored, so a task with one can't be VALID in that run.

The try (`tools/task-try.py`, an agent run on the task) is the Lab's own tool: never run it, nor another agent on a
task. Judge difficulty in the session instead (unity-write-tasks skill, section 6). _(why: the try is long and tells you
nothing the session can't judge; the Lab tries every submitted task itself)_

## 3. What a run does on each side

| | the no-op case (start, `seed.commit`) | the oracle case (reference, `seed.reference`) |
|---|---|---|
| build | built first; a start that doesn't build makes the task INVALID, unless its build check says `fails_at_start` (then not building is the start failing the task, and it is never played) | built as committed |
| checks run | its probes, and a `fails_at_start` build check | every check in the task's order: build, boot, `log_absent`, `file_exists`, `package` (always fails: the Lab's grader can't package a Unity game), every probe; a check whose `needs` failed reads `not run: needs X` |
| thresholds | a calibrated or start-relative threshold is made from what the start and the reference measure, the same threshold on both sides | |
| judges, `seen` | screenshots and crops saved for you to score and read blind | the same |

Plays are made once per side and shared by every check that names them. Each one runs on a Windows desktop of its own
at a fixed 30 frames a second of game time, faster than a clock, with clean saved data unless its `after` names the
plays that write it ([docs/task-probes.md](../../docs/task-probes.md), section 1.1).

## 4. What it writes, and what to read

Everything goes under `<UGF_ROOT>\games\<slug>\.task-checks\` (git-ignored; never commit it). Read it in this order:

1. **`progress.txt`** (and `progress.json`): how many tasks are done, each one's line, the judges and `seen` probes
   still waiting for you, the task being checked; `finished` at the end. Read it to see where a run stands.
2. **`run.out`**: one line per task, `VALID`, `INVALID` or `ERROR`, the task's name and its reasons joined by `; `.
   `run.log` holds the progress lines with their times, and any error that stopped the run.
3. **`<task>.json`**, the task's result: `verdict`, `reasons` (why INVALID or ERROR), `notes` (failures that don't
   decide, and scenes that name assets the commit lacks), and:
   - `probes`: the probe values table, one entry per probe: `start` and `reference` (what each side measured; null is
     "measured nothing", never 0), `threshold` (null when uncalibrated), `start_passed` and `reference_passed`;
   - `start_checks` and `reference_checks`: every check's row on each side, with its `detail`: a probe's is its
     `describe`, then `| measured V, threshold OP T (start S, fix R)` and why it has no value when it has none;
   - `judges` and `seen`: each judge check and `seen` probe, `answer needed` or answered.
4. **`<task>\start\<play>\` and `<task>\reference\<play>\`**, one folder per play (`look`, `drive`, `play_<name>`,
   `boot_<seconds>s`): `probe.json` (the player's `track`, the `measures` samples by query id, `inputs_missed`,
   `query_errors`), `play_spec.json` (which query id is which select), `probe.log` (where each teleport put the player,
   what each click hit), the screenshots `shot_NN.png` and the named ones `shot_<name>.png`, `play.log` (the game's
   own log) and `output.txt`. `<side>\build\build.log` is a failed build's log, `<side>\editor\output.txt` the editor
   pass's.
5. **`<task>\judge-shots\<check>\`**, for each `judge` check: `ask.md` (the brief, the question, the rubric, what each
   picture is, how to answer), `start\` and `reference\`, the blind copy `blind\A\` and `blind\B\` with
   `blind\key.json` (which is which) and `sides.md` (each side's own pictures and notes), and `pictures.json`.
6. **`<task>\seen-shots\<check>\`**, for each `seen` probe: `ask.md`, the crops of both sides, `crops.json` and the
   same blind copy.

### Answer the judges and the `seen` probes, blind

The checker asks no model; you are the model. **A required judge holds the task until you score it**, as the Lab's
grader holds the task's own fix to its judge, and a required `seen` probe measures nothing until you read it.

- **Judge:** open `ask.md`, look at `blind\A\` and `blind\B\`, and score every rubric item of each from 0 to 1, as if
  each were the developer's game, into `blind\answers.json`, before you open `blind\key.json` or `sides.md`:
  `{"A": {"door_open": 1, "lit": 0.5}, "B": {"door_open": 0, "lit": 0}}` (the keys are the rubric's).
- **`seen` probe:** copy every line of text each crop shows, top to bottom, exactly as shown (`?` for a character you
  can't read for sure, `[]` for no text), into `blind\answers.json`, before you open the key:
  `{"A": ["COMBO x3"], "B": ["COMBO"]}`.
- **"Cannot be seen" scores as fail, never as pass.** An item the pictures do not show scores 0, on either side,
  however sure you are of what the game does; then fix the judge's plays (named `shot` inputs timed at the event) so
  the pictures show it, and score again. _(why: the Lab's model scores only what its pictures show)_
- Then check the task again. Scores and readings stand while their pictures stay the same (`pictures.json`,
  `crops.json`); pictures that changed need new ones. Write the judges' scores of both sides in the task's
  `tasks-workflow.jsonl` row too.

_(why: blind scoring keeps you from scoring the side you know is the fix higher; the Lab's model sees no labels
either)_

## 5. Is each case right?

The verdict is the checker's; whether the task tests what it asks is yours. Read the rows and the play folders and
hold each case to this:

**The no-op case is right when**

- the start builds (or, with `fails_at_start`, doesn't);
- every required probe outside `still_works` fails, **for the reason its `describe` gives**: its row reads a measured
  value on the wrong side of the threshold, not `measured nothing`, `the play's input did not land`, `not run: needs
  X` or an empty selection;
- every required `still_works` probe passes, and every check the start passes carries `"weight": 0`;
- every required judge fails on your blind scores of the start (each required item below 0.5), and passes, for a
  judge in `still_works`.

**The oracle case is right when**

- the reference builds, boots and passes every required check, `log_absent` and `file_exists` included;
- every probe has a threshold (none reads `uncalibrated`), and the start and the reference measure different values
  for each calibrated one (a reading the same on both sides measures nothing: uncalibrated, never a pass);
- every task play's inputs landed (`inputs_missed` empty in the reference's `probe.json`, but for a click marked
  `"optional": true` that found nothing; `probe.log` shows each click hit its button and each teleport its object);
- every selection matched rows on both sides, or at least on the side where the thing exists (`probe.json`'s
  `measures` hold rows, not an empty selection that happens to compare right: a `count`, `any`, `all` or `sum` over no
  rows reads 0, which looks like a real value and passes a literal `== 0` or `<= 0` on both sides);
- the moment each probe reads falls inside its window on both sides, with room to spare (sample times in
  `probe.json`), and a judge's screenshots show the moment it asks about;
- every required judge passes on your blind scores of the reference, and every required `seen` probe is read.

A threshold comes from the instruction or from the start (`start_plus`, `start_times`, a number the ticket states, a
literal for a fact), never from what makes the reference pass. _(why: a threshold fitted to the reference fails
every other correct solution)_

## 6. What each verdict means

| verdict | means | do |
|---|---|---|
| `VALID` | both cases are right as far as the checker can tell: necessary, not sufficient (the Lab's review still marks a task whose checks don't decide what the instruction asks) | still read section 5 and each check's definition against the instruction; the task ships only with this verdict on its final file |
| `INVALID` | a case is wrong: the reasons say which | fix the task (section 7) and check it again |
| `ERROR` | the checker couldn't check the task: the machine, the licence, a build that stopped with no word about the game, a check the checker couldn't run | fix the machine and run again; never edit the task for an ERROR |

What a row's `detail` says:

| detail | means |
|---|---|
| `not asked: ...` | a check that side doesn't run (a judge, a retired kind; on the start, everything but its probes): shows as passed, counts for nothing |
| `not run: needs X` | an earlier check it `needs` failed: fix X first |
| `uncalibrated: ...` | the probe has no threshold: no solution could pass it |
| `the play's input did not land: ...` | an input of the task play missed; what it measured doesn't count |
| `task error: ...` | no version of the game can pass the check: the reference's own play can't be driven |
| `not packaged: ...` | a `package` check, which always fails: the Lab's grader can't package a Unity game |
| `the checker failed (...)` | the checker couldn't run the check: the task is an ERROR |

## 7. Failure patterns and what to do

Never make a check easier to get a case right (unity-write-tasks skill, section 1). Fix what the pattern names:

| what you see | what it means | what to do |
|---|---|---|
| **no-op passes**: `start already passes every required probe` / `start already passes required probe X` | the check doesn't test the ask (wrong field, window or play), or the start already does what it asks | measure what the fix changes: compare the start's and the reference's `probe.json` samples and pick a field that differs; make the play reach the moment the issue shows (a task play with the inputs or a teleport); if the start really does it already, that is no issue of the thread: drop the check and its ask, or pick another start |
| the no-op fails, but **for the wrong reason** (its row: `measured nothing`, `no samples in the window`, `the play's input did not land`, `not run: needs X`, an empty selection) | the start never showed the bug; the check only failed to read | fix the play or the selection so it measures the start; a failure that isn't the reported one proves nothing |
| `start fails still-works X` | the still-works probe is broken: it doesn't find what it looks for in a game that works | fix the probe (its selection, play or window), never its threshold |
| `a no-op scores N, not 0: give X "weight": 0` | checks the start passes carry weight | give each `"weight": 0` (it still gates) or drop it |
| `no required probe outside still_works to check the start with` | nothing can show the start failing | add a required probe outside `still_works` for each issue of the thread |
| **oracle fails**: `reference fails X: ... measured V, threshold OP T` | the check is wrong (`op` on the wrong side, the wrong field, a threshold not from the instruction or the start), or the reference's play doesn't reach the state | read the reference's play folder: the screenshots, the `track`, `probe.log`; fix the check or the play so the fix passes what the instruction asks |
| `reference fails X: ... no samples in the window` | the window misses the moment, or the reference's play ended early (see its `play.log`) | move the window to when the moment happens on both sides, with room to spare, or lengthen the play |
| `reference fails X: ... no value in the window (nothing it selects was measured)` | the selection names something the reference doesn't have under that name (renamed, re-parented, made at run time as `<Prefab>(Clone)`) | select by what the thing is or does (a component or tag the start has, `has`, `near`, `ui` text), never by a name only one build has |
| `the play's input did not land: ...`, or `task error: ... in the reference's play X, an input did not land` | an input missed: a click before its button showed, a second click on a button already gone, a click on a control scrolled past the screen's edge, a confirmation that shows only in some states, a teleport next to nothing, a key the probe has no control for, a stage nothing took | wait for the button, click by the caption the start has, drop a repeated click, scroll first as a player would (a `cursor` over the list, then `<Mouse>/scroll/y`; a `drag` on a mobile game), mark a click that may rightly find nothing `"optional": true` (never one the play needs), teleport next to something that is there; read `inputs_missed` and `probe.log` |
| `judge X: shots saved ..., answer needed` | a required judge isn't scored yet | score it blind (section 4) and check again |
| `reference fails judge X on your scores` / `start already passes judge X on your scores` | the rubric or the plays don't separate the fix from the start | reword the item so it is decidable from the screenshots, or give the judge plays that reach the state; never ask less of the solution |
| `seen X: crops saved ..., answer needed`, or `nothing the check reads was read on the reference` | a required `seen` probe isn't read, or its crop shows nothing it reads | read it blind; if the reference's crop holds no such text, take the shot at a stiller moment, loosen the rect, or read the text from the UI (`ui`, `widgets`) |
| `uncalibrated: X: the start and the reference both measure N` | the probe doesn't see the change | measure something the fix changes, or use a literal for a count or a fact |
| `uncalibrated: X: the reference measured nothing (...)` | the reference's play didn't reach what the probe reads | read the reason in brackets and fix the play or the selection |
| `uncalibrated: X: the start measured nothing (...) and the reference measured 0` | a reference of 0 leaves no margin to put a threshold in | measure what the fix makes non-zero, or a literal |
| `X has no threshold: uncalibrated: ...` (a `"required": false` probe) | an optional probe without a threshold fails the Lab's grade of the task whole | fix it or drop it |
| `reference fails X: not packaged: ...` | a required `package` check, which can't pass | drop it |
| `reference fails X: N matching log line(s)` (`log_absent`) or `0 file(s) match` (`file_exists`) | a required check the reference itself fails | fix the pattern or the glob so the fix passes, or drop the check |
| `start doesn't build: ...` | the start doesn't compile or build as committed | pick a start that builds, or set `"fails_at_start": true` when making it build is the task (then nothing may be relative to the start) |
| `start builds, though X says it doesn't` | `fails_at_start` on a start that builds | drop `fails_at_start`, or pick the commit where the build broke |
| a note: `<side>: <scene> names N of its M assets that the commit doesn't have` | the scene loads assets as missing at that commit | pick a commit that has them, or commit them with their `.meta` |
| `ERROR`: no licence (exit 198), `Unity stopped twice ...`, `the checker couldn't run a check ...`, `desk.py ...`, a missing LFS object, a Unity version not installed, the disk floor | the machine, never the task | sign in to Unity Hub, fetch the LFS objects, install the editor, free space, run from an interactive session; then run again |

More causes, line by line: [docs/task-check.md](../../docs/task-check.md), "Common reasons and fixes".

## 8. After every fix

1. Edit the task file on the tasks branch and commit it.
2. Run the validator again.
3. Check that task again, by name (`--task <task-name>`), and read both cases again (section 5): a fix that rights one
   case can break the other. A check you added or changed after the last run is unchecked until it has run.
4. Score again any judge or `seen` probe whose pictures changed.
5. Repeat until the verdict is VALID and both cases are right on the final file; then the task can ship. A task you
   can't get right without asking less of the solution is dropped, never eased.
