# Task check: check your own tasks

A task (a GameTask JSON in `Tasks/` on the game repo's orphan `tasks` branch, schema
[schemas/game-task.schema.json](schemas/game-task.schema.json)) is only useful when its checks tell a broken game from a
fixed one. The task checker proves that on your machine before you hand the task in: it builds the game at the task's
start (`seed.commit`) and at its reference (`seed.reference`, the change that solves it), plays both with the TaskProbe
package, measures every probe, and says **VALID** or **INVALID** with the reasons.

```powershell
python tools\task-check.py C:\Users\<you>\UnityWork\games\<slug> --task <task-name>
python tools\task-check.py C:\Users\<you>\UnityWork\games\<slug> --task <one> --task <two>
python tools\task-check.py C:\Users\<you>\UnityWork\games\<slug> --all
python tools\task-check.py C:\Users\<you>\UnityWork\games\<slug> --task C:\Users\<you>\UnityWork\tasks\<slug>\Tasks\<task-name>.json
```

Run it from the unity-game-factory folder (`%UGF_ROOT%\unity-game-factory`, where `%UGF_ROOT%` is the machine root,
`C:\Users\<you>\UnityWork` by default). A task is read from the repo's `tasks` branch by name (its file name in
`Tasks/` without `.json`); give the path of a `.json` file instead to check a task you haven't committed yet.

**Check a game's tasks in one run** (`--all`, or several `--task`). The run makes one scratch copy per commit and
builds it once (again only when a later task plays a scene the build lacks: a player holds only the scenes it was
built with), so a commit that is one task's start and another's reference, or two tasks' start, costs one build; each
copy is deleted after the last task that needs it (or when the disk runs below the floor, then rebuilt if a later task
needs it). A shared copy is the commit exactly as committed, so sharing changes no result. A run of 10 tasks takes
hours, so start it where it can run on its own and come back; a game session starts it as its own process
(unity-write-tasks skill, section 5). Two runs at once on one game each get their own scratch folder, but share
`<out>` unless each is given its own `--out`: they rewrite each other's progress files, and a task checked by both
loses its evidence to the other. `<out>\progress.txt` (and `progress.json`) is rewritten after every task: how many
are done, each one's verdict and minutes, and which is running; it says `finished` at the end. Progress lines carry
the time of day, and each build and play logs how long it took.

Without `--task` or `--all` it lists the tasks on the branch. Each task prints one line, and the exit code is 0 only
when every task is VALID (1 otherwise; 2 for a usage error, when nothing ran):

```
VALID   metro-runner-corr-cell-and-dead-meter
INVALID island-survival-fix-hut-door: start already passes every required probe
```

Options: `--keep` keeps the built copies (to look at a build or rerun a play by hand), not what their plays left
outside them (a play starts from clean saved data anyway), `--out DIR` puts the results elsewhere, `--scratch DIR`
puts the copies elsewhere (a short path: see "Requirements"), `--direct` runs Unity without the machine's job slots,
`--timeout S` (a play or the editor pass, default 1800) and `--build-timeout S` (default 3600).

## Requirements

- Windows with the Unity editor the project names: each commit's `ProjectSettings/ProjectVersion.txt`
  (`m_EditorVersion: 6000.3.x`) picks the install through the machine config (`unity_editors` in
  `%USERPROFILE%\.unity-game-factory\config.json`, or in the file the environment variable `UGF_CONFIG` names, else
  `<unity_hub_editors>\<version>\Editor\Unity.exe`; [machine/README.md](../machine/README.md)). A version that isn't
  installed is an ERROR naming it: install it through Unity Hub. Every start and reference must be a Unity 6.3 LTS
  (`6000.3.*`) project as committed: the checker never upgrades, ports or patches a game, and refuses any other
  version. The build is a Mono player, so the IL2CPP module and Visual Studio's C++ workload are not needed.
- **An active Unity licence** (Unity Hub, signed in). A batchmode Unity run without one exits with code 198 (its log
  says `No valid Unity Editor license`) and the check of that task stops with an ERROR: sign in to Unity Hub again and
  rerun. It is never a game bug.
- Python 3.12 (standard library only), git and Git LFS. The checker reads the game's files straight from its git objects
  and its local LFS store, so the LFS objects of both commits must be there: `git -C <repo> lfs fetch origin <commit>`
  when it says one is missing.
- **Short paths.** Unity fails on paths past 260 characters, and a project's `Library/` nests deep, so the checker
  refuses a scratch project folder longer than 90 characters. A copy's folder is `<scratch>\<run>\<commit>` (8 and 12
  characters), so `--scratch` may be at most 68 characters long: when it says so, pass a short folder on the repo's
  drive (`--scratch C:\tc`).
- Disk: each task needs up to two copies of the game plus their `Library/` folders (the imported assets, often larger
  than the project) and their builds, deleted after the last task of the run that needs them. The copies go on the
  repo's own drive (its resolved path, junctions followed), so LFS files are hardlinks of the repo's own objects and
  cost no disk; `--scratch` on another drive makes them copies. It refuses to start below the machine's free-space
  floor (`min_free_gb` in the machine config, else 50 GB; the environment variable `UGF_MIN_FREE_GB` overrides both),
  and a run that falls below it stops once it has deleted every copy the current task doesn't need.
- **One Unity process per project.** Unity locks a project folder while it has it open (`Temp/UnityLockfile`). The
  checker opens only its own scratch copies, one job at a time, never your checkout, so an editor open on the game
  doesn't stop it.
- Time: two builds and a few plays per task: 7 minutes for a near-empty URP project, 12 to 31 for the two tasks of a
  small game (the factory's sample) on the machine this was measured on, longer for a real game with many or large
  assets, and several times longer while the machine runs other Unity jobs (the same two tasks then took 45 and 74
  minutes). Half of it or more is the builds (2 to 5 minutes each in the short runs, 24 and 28 in the longest): a
  scratch copy's first build imports every asset into the copy's own `Library/`. A commit shared by several tasks of
  one run is built once. A task with `asset` measures adds one editor pass per side, an editor start of its own (6
  to 40 s in the short runs, 5 and 11 minutes in the longest).
  A 20 s play takes a few seconds of real time (one that measures audio takes its own seconds); the first play after a
  build starts about 20 s slower (the antivirus scans the new player). Every build, play and editor pass goes through
  `<root>\tools\unity-heavy.ps1` when the machine has it (plays with `-Gpu`), so checks share the machine's job slots
  with everything else; its timeouts count from when a job starts, not the wait for a slot. A job waits for its slot
  as long as the machine's slots are taken (an editor opened through the limiter holds one while it is open); the
  job's progress line then says how long it waited. The checker starts that script itself, from any shell; if
  PowerShell still refuses to run it (an execution policy your organisation set), each task's line is an ERROR that
  says so: pass `--direct`.

## What it does

1. Reads the task from the `tasks` branch (else `origin/tasks`) and validates it like
   [tools/validate-game.py](../tools/validate-game.py) does (the schema and the task format's own rules; the
   validator's long-thread bar is the validator's alone); a task that doesn't validate is INVALID.
2. Materializes the start and the reference into a scratch folder outside the repo, on its drive (default
   `<root>\.task-check\` when the machine root is on the repo's drive, else a `.task-check` folder beside the folder
   that holds the repo; each copy in a `<run>\<commit>` folder under it): every file of that commit exactly as
   committed, LFS files hardlinked from the repo's store (copied across drives), without `Tasks/`, `History/`,
   `Dataset/` or `Dataset.zip`. The TaskProbe package is added as `Packages/com.taskprobe/` (an embedded package, so
   `Packages/manifest.json` stays untouched); nothing else is added or changed, and nothing comes from another commit
   (no port, no patch). Your checkout is never touched. When a scene the task plays names assets (by GUID) the commit
   doesn't hold (a store pack committed only later, say), the result says so in a note: that is the task's commit to
   fix.
3. Builds the start: `Unity.exe -batchmode -nographics -quit -projectPath <copy> -executeMethod
   TaskProbe.EditorTools.Build.Player`, a Windows x64 Mono non-development player in `<copy>\Build\TaskProbe\`, with
   every scene the task's plays open added after the project's own enabled build scenes. For the plays only, the
   copy's build gets its own company name (`TaskProbe.<hash>`, so a play's saved data is never the real game's), no
   splash screen, no static batching (so each renderer keeps its own mesh name and triangle count), no code stripping
   (the probe reads members by name that the game may never call) and several instances allowed; the build puts each
   of these settings back when it is done, and the game's assets and code are untouched. The window (960x540, not
   full screen) comes from each play's command line. The build passes when Unity exits 0 and the probe's build result
   says ok. A start that doesn't build makes the task INVALID, unless
   its build check says so (`"fails_at_start": true`: making it build is the task); then the start failing to build is
   the start failing the task, and it is never played.
4. Checks the reference as if it were a solution: the task's checks in order (a check whose `needs` failed doesn't run
   and fails: `not run: needs X`): build, boot (a play of `seconds` that must run to its end without a crash: a player
   log line matching `Crash!!!`, `OUTPUTTING STACK TRACE`, `Fatal error` or `Out of memory`), `log_absent`,
   `file_exists`, and every probe against its threshold.
5. Checks the start on its probes.
6. Writes the result and deletes the scratch copies (unless `--keep`) and, kept or not, what their plays left outside
   them, all under each copy's own company name (step 3) and nothing else: the registry key
   `HKEY_CURRENT_USER\Software\TaskProbe.<hash>` (PlayerPrefs), the folders `TaskProbe_<hash>` in
   `%USERPROFILE%\AppData\LocalLow` and in the temp folder (persistent data, cache) and `TaskProbe.<hash>` in the temp
   folder (crash reports).

### The plays

Each play is the built player started windowed at 960x540 **on a Windows desktop of its own**
(`tools/task_check/desk.py`: nothing shows on your screen, and the play can't take your keyboard or mouse) on a fixed
30 fps clock, on the task's `play_scene` with its `play_args` (or the task play's own `scene` and `args`), with the
TaskProbe package sampling every 0.5 s (a task play's `every`). Each play is played once per side, with the measures of
every probe that names it. A play with an `audio` measure is paced to real time and every other play runs as fast as
the machine renders; the probe silences every play once it has measured the sound, so no play is ever heard
(task-probes.md, section 2.16). What a play does to the game (its focus, its clock, the first build scene, saved data,
inputs) is in task-probes.md, section 1.1. Only a player you start by hand on your own desktop, to rerun a play of a
kept copy, has its window moved off-screen and deactivated by the probe instead; that one does see itself lose focus.

| `play` | What |
|---|---|
| `"look"` | 20 s, no input, 6 screenshots |
| `"drive"` | 22 s, 8 screenshots: `<Keyboard>/w` 1-6 s, `<Keyboard>/d` 6-8 s, `<Keyboard>/w` 8-13 s with `<Keyboard>/space` at 9-9.3 s, `<Keyboard>/a` 13-15 s, `<Keyboard>/w` 15-21 s |
| `{"name": ..., "seconds": ..., "inputs": [...]}` | a task play: keys, axes, widget clicks, cursor moves, teleports, teleports next to an object and waits at their times, its own `scene`, `args` and `every`; 2 screenshots |
| `"editor"` | one batchmode editor pass per side over every `asset` measure (the project as saved) |
| a boot check | `seconds` of play, no input, 2 screenshots; `log_absent` reads a 60 s boot's log |

A boot is the same idle game as `"look"`, only longer, so on the side that boots (the reference; a start is never
booted) one 60 s idle play with look's queries and screenshots serves both: the boot check reads all of it and
`"look"` reads only what a 20 s play samples (its first 20.5 s: a play samples on to half a second past its length),
exactly what a 20 s play would have measured. That saves a game launch per task. A
look probe that reads the log (`"probe": "log"`) keeps its own 20 s play, because a log covers the whole play. The kept
files are then under `boot_60s\`, not `look\`. Each play's progress line says how long it took, and how much of that
it waited for a machine slot (`unity-heavy.ps1`).

### Thresholds

- `{"op": ">=", "value": 1}`: a literal.
- `{"op": ">=", "calibrate": 0.5}`: `s + 0.5 * (r - s)` between the start's measure `s` and the reference's `r`.
  If the start measured nothing (its play crashed, often the bug itself; or nothing the measure selects is there yet,
  the usual case in a task that adds it), the threshold is `r` moved a quarter of `|r|` off the passing side
  (`r - 0.25 * |r|` for `>`/`>=`, `r + 0.25 * |r|` for `<`/`<=`; an `r` of 0 gives no margin: uncalibrated). If the
  reference measured nothing, or both sides measure the same, the probe fails as **uncalibrated**.
- `{"op": ">=", "start_times": 1.3}` / `{"op": ">=", "start_plus": 5}`: `s * 1.3` / `s + 5` from the start (for an
  outcome the reference is only one fair way of reaching, or a task with no reference: task-probes.md, section 1.2).
  A start that measured nothing leaves no threshold (uncalibrated).

## VALID and INVALID

A task is **VALID** when all of this holds:

- the start builds, or doesn't build exactly when a build check says `fails_at_start`;
- with a reference: the reference builds, boots (every `boot` check) and passes every **required** probe;
- the start fails every required probe outside `still_works` (or doesn't build by design): each is one issue of the
  thread, and one the start already passes rewards no work;
- every required probe in the `still_works` milestone already passes at the start. What must keep working has to work
  before the change, or the probe is broken and would fail every correct solution. A still-works probe the start has
  no samples for (its play crashed or ended early, which is often the task's own bug) doesn't count against it; one
  that finds nothing to measure in a start that ran does;
- a no-op scores zero: no check the start passes carries weight, so build, boot and `still_works` checks take
  `"weight": 0` (`tools/validate-game.py` refuses a task where one doesn't), and so does any other check true of the
  start: a `log_absent` or `file_exists` check (nothing measures those at the start, so their weight is yours to set)
  or a probe, a `"required": false` one too (the task check measures that). Judges and trace probes aren't measured
  here, so their weights aren't covered by this rule.

Never part of the check: judges (`judge`, `code_judge`, `actions_judge`: quality scores, never pass/fail), trace probes
(they read an agent's own tool calls), and `package` checks. The reference's other failures (`log_absent`,
`file_exists`, probes with `"required": false`) are reported as notes and never make a task INVALID. Read the notes
all the same: every check is required unless it says `"required": false`, a `log_absent` or `file_exists` too, and
a run counts as solved only when every required check passes, so a required one the reference itself fails is one no
solution like the reference can pass. Fix its pattern, or make it `"required": false`.

A task with no reference is checked on its start alone: it must build, fail every required probe outside
`still_works` and pass its still-works probes, and every required probe, a still-works one too, needs a threshold
(relative to the start, or a literal; a relative one the start measured nothing for has none, and no solution could
pass it). Every shipped task has a reference (unity-write-tasks section 1; `tools/validate-game.py` rejects one
without), so this is for drafts only.

## Results

- One line per task on the console: the verdict (`VALID`, `INVALID`, or `ERROR` when the checker couldn't check it),
  the task, and its reasons joined by `; `. Progress goes to stderr.
- `<repo>\.task-checks\<task>.json` (format `task-check/1`; `--out` moves the folder; a task file that isn't JSON gets
  none, only its console line and its row in `progress.json`):
  - `verdict`, `reasons` (why INVALID or ERROR), `notes` (the reference's failures that don't decide, written
    `reference fails X (<kind>): <detail>`, and scenes that name assets the commit lacks); a reason or note carries at
    most 160 characters of a check's detail, the whole of it is in that check's row;
  - `start` and `reference`: the side's `commit`, whether it `built`, its `missing_assets` (`{}` when nothing is
    missing; else, per scene the task plays, the asset GUIDs it names that the commit has no asset for, and how many
    assets it names), and how its copy was made (`files`, `lfs_linked`, `lfs_copied`, `engine`: the Unity.exe used,
    `slots`: `unity-heavy` or `direct`);
  - `probes`: an object keyed by each probe check's name: its milestone (`group`), `required`, `op`, `expect`, the
    `start` and `reference` measures (null where that side measured nothing, which is not a measured 0), the
    `threshold` (null when uncalibrated), and whether each side passed (`start_passed`, `reference_passed`);
  - `start_checks`, `reference_checks`: a list with every check's row on each side, in the task's order (`name`,
    `kind`, `group`, `required`, `weight`, `passed` and a `detail`). A probe's detail is its `describe`, then
    `| measured V, threshold OP T`, with what the start and the reference measured when the threshold came from them,
    and why it has no value: `... | measured 0, threshold >= 89.9957 (start 0, fix 179.991)`, `... | measured nothing,
    threshold >= 1: no value in the window (...)`; a probe left without a threshold reads `uncalibrated: X: ...`
    instead. A detail starting `not asked` is a check that side doesn't run (judges, trace probes and packaging on
    either side; on the start, everything but its probes and a `fails_at_start` build check): it shows as passed and
    counts for nothing;
  - `task_sha256` (the SHA-256 of the task file as the run read it: the file as committed on the `tasks` branch, or
    the `.json` given by path; a checkout with other line endings hashes differently), `task`, `game`, `at` (when,
    UTC), `seconds` (how long the check took) and `evidence` (the task's folder of play files, below).
- `<repo>\.task-checks\<task>\<side>\<play>\` (`<side>` is `start` or `reference`): a folder per play, named `look`,
  `drive`, `play_<name>` for a task play, or `boot_<seconds>s` for a boot (on the reference it also serves `look`).
  The result doesn't name a check's play: it is the check's `play` in the task file. Each holds `probe.json`
  (below), `play_spec.json` (what the play was given: its seconds, scene and inputs, and its queries with their ids,
  kinds and selects or places; a `look` that a boot served has its queries in the boot's), `probe.log` (the probe's
  own lines: where each teleport put the player, each click, wait and error, and every 10 samples what a `drawn`
  measure cost, `drawn <id>: N ms this sample ...`; each line `<play time> [<real time> s] ...`), the screenshots
  `shot_00.png`, `shot_01.png`, ... (960x540 PNGs, UI included, evenly over the play), `play.log` (the game's own
  player log) and `output.txt` (what the play's job printed, the machine slot's waits among it; empty when it
  printed nothing, as under `--direct`). `editor\output.txt` is the editor pass's log, and `build\build.log` Unity's
  log of a build that failed. Read these when a value surprises you. Checking a task again replaces its folder.
- A play's `probe.json` holds, per sample time: in `track` a row `[t, x, y, z]`, the player's position (`[t]` alone
  while the play has no player); in `camera` a row `[t, x, y, z, pitch, yaw, fov]`; in `measures` the samples of
  every query the play's probes asked; and `query_errors`, the lines of what the probe couldn't read (only when
  there are some). A key of `measures` is a query's id, `q` and ten hex digits made from what the query selects (its
  kind with its select, point or rect), so a query has the same id in every play and on both sides, and probes that
  read other fields of one selection share one query. The file doesn't name the checks: `play_spec.json` beside it
  gives each id's kind and select, which you match with the check's measure in the task file. A sample holds either
  `rows` (one per object, component, widget or element matched, with its `name` and the fields asked for) or a
  `value` with the kind's own keys (task-probes.md, section 2, under each kind). A
  `spawns` sample holds running totals since the play started; the checker reads each sample's rise over the one
  before.
- `<out>\progress.txt`: `task check: D of T task(s) done, started HH:MM, M min so far` (`, finished` at the end), each
  finished task's console line with its minutes (`(18 min)`), and `checking <task>, then N more`. `progress.json`
  (format `task-check-progress/1`) holds the same: `started` and `updated` (seconds since 1970), `tasks` (in order),
  `done` (each finished task's `task`, `verdict`, `reasons` and `seconds`) and `finished`.
- `.task-checks\` is git-ignored: new games have it in `.gitignore` (templates/unity-game); for an older game the
  checker adds it to the repo's own `.git\info\exclude`. Never commit results.

## Common reasons and fixes

An entry in code font is the line as the checker prints it (`X` a check's name, `N` a number, `...` the rest). A line
that says its own fix (`fetch it, or fix the task`, `install it through Unity Hub`, `pass --direct`, `name one with
--task NAME`) has no entry: do what it says.

**`start already passes every required probe`** (or **`start already passes required probe X`**, for some of them).
The bug doesn't show in what the probes measure.
- The play never reaches the situation: the idle `look` stands at the spawn, the `drive` walks a fixed pattern. Write a
  task play that gets there: a `teleport` input (`{"t": 0.2, "teleport": [x, y, z], "yaw": 90}` places the player,
  in metres, y up; take the coordinates from the editor, or from the `track` in a play's `probe.json`), its own
  `scene` (`Assets/Scenes/Arena.unity`) and `args` (`["-scenario", "2"]`), and the inputs that trigger the bug.
- The measure is the wrong one: compare the start's and the reference's `probe.json` samples for the field you read
  and pick one that differs.
- The play opens a later scene, but the game sets itself up in its boot scene's `Start`: the probe opens `play_scene`
  before that scene's `Start` runs (only its `Awake` and `OnEnable` do), so what it sets up there is missing. Start
  such a game through its own `play_args` with `play_scene` null (task-probes.md, section 1.1).

**`uncalibrated: ... the start and the reference both measure N`.** The measures are equal on both sides, so there is
nothing to put a threshold between: the probe doesn't see the change. Measure something the fix changes (a
different field, window or play), or use a literal value when the fact is a count or a boolean. A probe that isn't
required and can't be calibrated fails as a note, never as a reason for INVALID. `uncalibrated: X: the reference
measured nothing (...)` (or `the start measured nothing (...)`, for a threshold relative to the start or with a
reference that measured 0): read the reason in brackets as below. In a task with no reference, a required probe the
start leaves uncalibrated reads **`X has no threshold: uncalibrated: ...`**: no solution could pass it.

**`no samples in the window (the play ended at N s)`.** The play ended before the window: the window or `at` lies past
the play's `seconds`, or the game crashed or quit (see the play's log). **`the play wrote no probe file`**: the game
never got to play (a crash at load: see the play's `play.log` and `output.txt`), or the play was stopped at
`--timeout` before its end (its progress line then shows it took that long). A scene the commit doesn't have
doesn't stop a play: the probe plays the game's own first scene instead, and its `query_errors` says so.

**`no value in the window (nothing it selects was measured)`.** The selection matched nothing, or nothing it matched
has that field, or a `player` or `camera` measure's play never found the player or the camera (name the player with
the task's `player` select: task-probes.md, "Words used here"). `component` is the C# type name (`Projectile`) or its
full name (`MyGame.Projectile`); an object instantiated at run time is named `<Prefab>(Clone)` (`Projectile(Clone)`),
and a `name` wildcard takes every whole name it fits (`Projectile*` takes a `ProjectileSpawner` too), so select the
things themselves by their own component or their full name (task-probes.md, section 2.4); only objects active in the
hierarchy match unless the select says `"inactive": true`; a component's member is `prop:<Component>.<member>`.
`; the probe said: ...` quotes the line of the play's `query_errors` about this measure's own query (what the probe
couldn't read; it starts with the query's kind, and its id when it is about that query alone: `spawns q4f2a91c07e:
no component type Coin`); a line with the kind alone can be another query's of that kind in the same play. The `rows`
in the play's `probe.json` show what was found, and `probe.log` beside it what the probe did (a `teleport_to` that
found nothing, a widget click that matched no button). A `drawn` measure has no value in a player that can't render
the place alone (no graphics device, or a render pipeline other than URP with its Universal Renderer, URP's 2D
Renderer among them), and `lit` or `glow` of a source the probe reads as rendered then reads its bound or nothing:
the play's `query_errors` (in `probe.json`) holds one `rendering: ...` line saying why (task-probes.md, section
2.19), and such a measure's reason quotes it after `; the probe said:`. Some fields have no value at first by
design: `spin` on the first sample an object is seen in, `speed` of an object with no velocity of its own then too,
audio `level` in the play's first frames, the grading fields and a light's `exposure` and `brightness` at a play's
first sample.

**`the editor couldn't measure it: ...`.** An `asset` measure the editor pass refused: a path it has no asset, scene or
prefab for (`no asset`, `no scene`, `no prefab`), a colour without a channel, an unknown shader property or member,
or a select using `player`, `has` or a `near` around the player or the camera (task-probes.md, section 2.11). `the
property has no number`: the value isn't a number, a boolean or an enum (a string needs `match`), or its path stops
at an unset reference or past the end of a list; `no selected object has a value`: none of the selected objects has
it. `the editor pass gave no result (exit N)`: the pass itself failed (its log is `editor\output.txt`); `the editor
pass gave nothing for it`: the pass ran but its result has nothing for this measure (see the same log); `the project
didn't build, so the editor couldn't open it`: see `start doesn't build`.

**`of` defaults to `count`.** For `objects`, `components`, `widgets`, `ui` and scene `asset` measures, `of` combines
the selected rows of one sample, and without it a field like `y` counts the rows whose value isn't 0 instead of
reading the value. Set `"of": "first"`, `"max"`, `"min"` or `"mean"` when you mean the value. "First" is the first
in hierarchy order, which an edit to the scene between the start and the reference can change: narrow the select
(name, tag, `near`) so it picks the object you mean on both sides.

**More than 200 matches.** The probe keeps at most 200 rows a sample in `probe.json`, but reads every match: the
sample's `total` is how many matched and `full` sums up every match's numeric value of each field (`n`, `nonzero`,
`sum`, `min`, `max`). `count` reads `total`, and `of` (`count`, `any`, `all`, `sum`, `min`, `max`, `mean`) reads
`full`, so neither stops at 200. Only `"of": "first"` and values read through `match`, `to_angle` or `to_axis` read the
200 rows alone.

**Angles.** `yaw`, `pitch`, `roll`, `rel_yaw:` and `world_yaw:`/`world_pitch:`/`world_roll:` are normalised to
(-180, 180], so a raw yaw jumps from 180 to -180 and `mean` or `delta` across the wrap mean nothing. Use
`"to_angle": 90` (the shortest distance to 90 degrees, 0-180) or `"to_axis": 90` (the distance to that axis, 0-90: a
direction and its opposite are one axis), with the threshold on that distance. A `prop:` that holds an angle takes
`to_angle`/`to_axis` too.

**Mouse look moves too little or too much.** An axis input (`{"t": 1, "key": "<Mouse>/delta/x", "axis": 40.0}`) is a
raw mouse delta in pixels for one frame: the turn it gives is the axis value times the game's own look scale (its
input actions' processors, its sensitivity setting, whatever its code multiplies by), so the same 40 turns one game a
few degrees and another a whole turn. Check the camera's `yaw` in the start play's `probe.json` and scale the axis
values to the turn you need.

**Keys do nothing.** The probe drives the Input System only. A game that reads the old Input Manager
(`Input.GetKey`, `Input.GetAxis`) takes no input in a play; the `track` in `probe.json` stays put through the
`drive`. Such a game's tasks can only use what goes around the Input System (teleports, widget clicks, waits and idle
plays), or a start that reads the Input System.

**`start fails still-works X`.** The game works at the start, so a still-works probe that fails there is broken: it
doesn't find the HUD, the object or the value it looks for. Fix the probe (see the play's `probe.json`), never the
threshold.

**`reference fails X`.** The reference doesn't do what the probe asks (a threshold on the wrong side: check `op`), or
the reference's play doesn't reach the situation either. The play's folder (`.task-checks\<task>\reference\<play>\`,
see "Results") tells which: its screenshots, the `track` in `probe.json`, and `probe.log`, which says where each
teleport put the player and what each click hit. A `teleport_to` goes next to the match nearest the player, so a
select that also matches another object can take the player there instead:
`6.00 [6.5 s] teleported next to CoinSpawner: asked (0.00, 0.00, 0.30) yaw 180.0, now at (0.00, 0.00, 0.30)` is a
`{"name": "Coin*"}` that found the spawner, not a coin. Select the things themselves: by their own component
(`"component": "Coin"`) or their full name (`Coin(Clone)`) when the start has them too; when the task adds them (a
feature, a change), another solution would name them otherwise, so select by what they carry (`has`: a part the
brief itself asks for, as coins that shine are `lit`), and keep out a parent that holds them with a `component` on
the object itself (task-probes.md, section 2.4). `teleport_to skipped
(no object matches)` found nothing. `reference fails boots_clean: crashed` means the reference crashes in a plain
boot (`didn't finish its run`: it stopped before its `seconds`; `timed out`: it ran past `--timeout`).
`reference fails X: build failed (exit N: ...)` means the reference doesn't build as committed; every check that
`needs` it then fails `not run: needs X`, and so on down the chain. The reason names the first cause and
`reference\build\build.log` holds the rest, as for `start doesn't build` below.

**`start: Assets/Scenes/X.unity names N of its M assets that the commit doesn't have`** (a note). The scene refers to
asset GUIDs the commit lacks, typically a store pack committed only later, or an asset committed without its `.meta`;
in the plays they load as missing (pink materials, empty mesh slots, missing scripts), which can make probes measure
the wrong thing. Pick a commit that has the assets, or commit them (each with its `.meta`) so the task's commits hold
them; the checker never adds files from other commits.

**`start doesn't build`.** The start's scripts don't compile on its 6000.3 editor as committed, or the player build
fails. The reason itself names the first cause after the exit code (`didn't build (exit 1: ...)`), in one line of at
most 200 characters: the build's own error, else the log's first compiler error (`<file>(<line>,<column>): error
CS<n>: ...`), else its first `## Script Compilation Error for:` line (an assembly a post-processor failed on).
`start\build\build.log` starts with the build's own reason when it gave one (`[task-check] the build's result says it
failed: ...`), then Unity's log: read its `error CS` lines first. Pick a start that builds, or, when making it build
is the task, set `"fails_at_start": true` on the build check (then no threshold may be relative to the start).
`didn't build (timed out)` is a build that said why it failed (a compiler error, or its result) and then ran past
`--build-timeout`. A build that stops with no word about the game is no verdict: see the ERROR entry `... didn't
build: Unity stopped twice ...` below.

**`start: ProjectSettings/ProjectVersion.txt names Unity ...: a task's commits must be Unity 6000.3 projects as
committed`** (or `reference: ...`). That commit was made on another Unity, and the checker never upgrades a project.
Pick a start and a reference from the part of the game's history made on 6000.3.

**`... LFS object(s) ... aren't in ...'s local store`** (an ERROR line, not a verdict): fetch them,
`git -C <repo> lfs fetch origin <commit>`, and run again.

**`ERROR   <task>: the checker couldn't check it: ...`.** The checker itself failed on that task, so the line says
nothing about the task; the run goes on with the next one, and the exit code is 1. The rest of the line says why: a
missing LFS object (above), a Unity version that isn't installed, PowerShell refusing `unity-heavy.ps1`, a build that
stopped (next entry), a player that couldn't be started on a desktop of its own, a disk error. Fix that and run
again. One check's row reading `the checker failed (...)` is the same for that check alone.

**`... didn't build: Unity stopped twice (exit N) with no compiler error and no result saying why: ...`** (or **`Unity
was stopped at the build's time limit (N s) ...`**; an ERROR line). The build failed without a word about the game:
neither a compiler error in its log nor a build result saying it failed, so Unity or one of its tools stopped, or the
build ran into `--build-timeout`. The checker tries a build that stops this way once more (the progress line `build
stopped (exit N) with no compiler error and no result saying why, retry 1`); stopped again, or stopped at the time
limit (never tried again), it is the machine's failure, not the game's, and the task has no verdict. The line names
the kept log (`<side>\build\build.log`). Run the check again; when it stops the same way every time, read that log
for what stopped (its first `## Script Compilation Error for:` line names the assembly a post-processor failed on).

**A Python traceback that ends the run.** The checker met a fault of its own that it doesn't turn into an ERROR line.
The tasks it finished keep their results, `progress.txt` names the one it was checking, and the scratch copies are
deleted (unless `--keep`). Report it with the traceback, and check the remaining tasks with `--task`.

**`couldn't delete <folder> (...): delete it by hand`** (a progress line). A file of a scratch copy is held by a
process outside the checker (a player that outlived an interrupt, a viewer); the run goes on. Close what holds it and
delete the folder.

**`a no-op scores N, not 0: give X "weight": 0, or drop them`.** Those checks already pass at the start (`still_works`
probes, probes that aren't required), so a run that changes nothing would score `N` (the weighted share of checks
passed). Give each `"weight": 0` (a required one still gates), or drop it.

**`no required probe outside still_works to check the start with`.** Nothing is left to show the start failing: every
required probe is in `still_works`, or none is required. Add a required probe outside `still_works` for each issue of
the thread (unity-write-tasks skill, section 5).

**`start builds, though X says it doesn't (fails_at_start)`.** The start built, though its build check says making it
build is the task. Drop `fails_at_start`, or pick the commit where the build broke.

**`the task doesn't validate: ...`.** The task breaks its schema or a rule of the task format (up to five problems,
worded as `tools/validate-game.py` words them for the task; `... is not JSON (...)`: the file doesn't even parse). Fix
the task file and check it again. The validator checks more than this: the long-thread bar and the no-op weights of
each task, and on its `repo:` lines the game repo itself (`repo: README: shows no gameplay image`). Those never change
a task check's verdict, but a game is delivered only with the validator's VALID too ([game-format.md](game-format.md)).

**`Unity has no active licence (exit N, "No valid Unity Editor license"): ...`** (an ERROR line; `exit 198` as a
rule): Unity has no active licence, and the check of that task says nothing about it. Sign in to Unity Hub, check the
licence there, and run again. Every Unity log also holds `[Licensing::...]` lines with `Error` in them when the licence
works: those mean nothing.

**`... the player couldn't be started on a desktop of its own (desk.py: ...)`** (an ERROR line). `desk.py` itself
failed before the player ran: it makes a Windows desktop for the play, and a session with no interactive window
station (a service, some remote shells) can't. The machine's fault, never a verdict on the game: run the check from an
interactive session.

**`task-check.py: error: the scratch project folder ... is longer than 90 characters (N): ...`** (a usage error, exit
code 2: nothing ran). Pass a `--scratch` of at most 68 characters on the repo's drive (`--scratch C:\tc`).

**`task check: only N GB free on C: (floor 50 GB; UGF_MIN_FREE_GB / min_free_gb). ...`** (exit code 1). The scratch
copies' drive is below the machine's floor ("Requirements"): the run didn't start, or stopped after the tasks it had
finished. Free space on that drive, or pass `--scratch` on a drive with room (its LFS files are then copies).
