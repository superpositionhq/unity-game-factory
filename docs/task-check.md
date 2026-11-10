# Task check: check your own tasks

A task (a GameTask JSON in `Tasks/` on the game repo's orphan `tasks` branch, schema
[schemas/game-task.schema.json](schemas/game-task.schema.json)) is only useful when its checks tell a broken game from a
fixed one. The task checker proves that on your machine before you hand the task in: it builds the game at the task's
start (`seed.commit`) and at its reference (`seed.reference`, the change that solves it) as Windows players with the
TaskProbe package in them, plays both, measures every probe ([task-probes.md](task-probes.md)), and says **VALID** or
**INVALID** with the reasons.

```powershell
python tools\task-check.py C:\Users\<you>\UnityWork\games\<slug> --task <task-name>
python tools\task-check.py C:\Users\<you>\UnityWork\games\<slug> --task <one> --task <two>
python tools\task-check.py C:\Users\<you>\UnityWork\games\<slug> --all
python tools\task-check.py C:\Users\<you>\UnityWork\games\<slug> --task C:\Users\<you>\UnityWork\tasks\<slug>\Tasks\<task-name>.json
```

Run it from the unity-game-factory folder (`%UGF_ROOT%\unity-game-factory`). A task is read from the repo's `tasks`
branch by name; give the path of a `.json` file instead to check a task you haven't committed yet.

**Check a game's tasks in one run** (`--all`, or several `--task`). The run makes one scratch copy per commit and
builds it once, so a commit that is one task's start and another's reference, or two tasks' start, costs one build
(and one import of every asset, the long part), and a later copy starts from the import cache of a copy already built
(see "Time" below); each copy is deleted after the last task that needs it (or when the
disk runs below the floor, then rebuilt if a later task needs it). A shared copy is the commit exactly as committed,
so sharing changes no result. A run of 10 tasks takes hours, so start it where it can run on its own and come back; a
game session starts it as its own process (unity-write-tasks skill, section 5). `<out>\progress.txt` (and
`progress.json`) is rewritten after every task: how many are done, each one's verdict and minutes, and which is
running; it says `finished` at the end. Progress lines carry the time of day, and each build and play logs how long
it took.

Run it from PowerShell (the machine's `unity-heavy.ps1` is a PowerShell script; see "Requirements"). Without `--task`
or `--all` it lists the tasks on the branch. Each task prints one line, and the exit code is 0 only when every task is
VALID:

```
VALID   harbor-run-corr-chase-camera-and-fog
INVALID island-survival-fix-hut-door: start already passes every required probe
```

Options: `--keep` keeps the built copies (to look at a build or rerun a play by hand), `--out DIR` puts the results
elsewhere, `--scratch DIR` puts the copies elsewhere (a short path: see "Requirements"), `--direct` runs Unity without
the machine's job slots, `--timeout S` (a play or the editor pass, default 1800) and `--build-timeout S` (default
3600).

## Requirements

- Windows with the Unity editor the project names: each commit's `ProjectSettings/ProjectVersion.txt`
  (`m_EditorVersion: 6000.3.x`) picks the install through the machine config (`unity_editors`, else
  `<unity_hub_editors>\<version>\Editor\Unity.exe`; [machine/README.md](../machine/README.md)). A version that isn't
  installed is an error naming it: install it through Unity Hub. Every start and reference must be a Unity 6.3 LTS
  (`6000.3.*`) project as committed: the checker never upgrades, ports or patches a game, and refuses any other
  version. The build is a Mono player, so the IL2CPP module and Visual Studio's C++ workload are not needed.
- **An active Unity licence** (Unity Hub, signed in). A batchmode run without one exits with code 198 and the check
  stops: sign in to Unity Hub again and rerun. It is not a game bug.
- Python 3.12 (standard library only), git and Git LFS. The checker reads the game's files straight from its git objects
  and its local LFS store, so the LFS objects of both commits must be there: `git -C <repo> lfs fetch origin <commit>`
  when it says one is missing.
- **Short paths.** Unity fails on paths past 260 characters, and a project's `Library/` nests deep, so the checker
  refuses a scratch project folder longer than 90 characters and says so. Pass `--scratch` with a short folder on the
  repo's drive (`--scratch C:\tc`).
- Disk: each task needs up to two copies of the game plus their `Library/` folders (the imported assets, often larger
  than the project; a copy seeded from another's import cache holds its own copy of it) and their builds, deleted
  after the last task of the run that needs them. The copies go on the repo's own drive (its
  resolved path, junctions followed), so LFS files are hardlinks of the repo's own objects and cost no disk; `--scratch`
  on another drive makes them copies. It refuses to start below the machine's free-space floor (`min_free_gb`).
- **One Unity process per project.** Unity locks a project folder while it has it open (`Temp/UnityLockfile`). The
  checker opens only its own scratch copies, never your checkout, so an editor open on the game doesn't stop it; but
  close any editor you opened on a scratch copy (after `--keep`) before the next run uses it.
- Time: two builds and a few plays, typically 20-60 minutes per task. Most of a build is a scratch copy's first build
  importing every asset into the copy's own `Library/`: about 5 minutes for a near-empty URP project on the machine
  this was measured on, much longer for a real game with many or large assets. Within one run, a later copy starts
  from the import cache of a copy that was already built (Unity's cache is keyed by each asset's content and import
  settings, and is never part of the game: both copies stay exactly as committed), so it imports only what differs. A
  commit shared by several tasks of one run is built once. A 20 s play takes a few seconds of real time; the first
  play after a build starts about 20 s slower (the antivirus scans the new player). Every build, play and editor pass
  goes through `<root>\tools\unity-heavy.ps1` when the machine has it (plays with `-Gpu`), so checks share the
  machine's job slots with everything else; its timeouts count from when a job starts, not the wait for a slot. If
  PowerShell refuses to load `unity-heavy.ps1` (an `AllSigned` execution policy), run the checker from a PowerShell
  session that may run the machine's scripts, or pass `--direct`.

## What it does

1. Reads the task from the `tasks` branch (else `origin/tasks`) and validates it like
   [tools/validate-game.py](../tools/validate-game.py) does; a task that doesn't validate is INVALID.
2. Materializes the start and the reference into a scratch folder outside the repo, on its drive (default
   `<root>\.task-check\` when the machine root is on the repo's drive, else a `.task-check` folder beside the folder
   that holds the repo): every file of that commit exactly as committed, LFS files hardlinked from the repo's store
   (copied across drives), without `Tasks/`, `History/`, `Dataset/` or `Dataset.zip`. The TaskProbe package is added
   as `Packages/com.taskprobe/` (an embedded package, so `Packages/manifest.json` stays untouched); nothing else is
   added or changed, and nothing comes from another commit (no port, no patch). Your checkout is never touched. When a
   scene the task plays names assets (by GUID) the commit doesn't hold (a store pack committed only later, say), the
   result says so in a note: that is the task's commit to fix.
3. Builds the start: `Unity.exe -batchmode -nographics -quit -projectPath <copy> -executeMethod
   TaskProbe.EditorTools.Build.Player`, a Windows x64 Mono non-development player in `<copy>\Build\TaskProbe\`, with
   every scene the task's plays open added after the project's own enabled build scenes. For the plays only, the
   copy's build gets its own company name (`TaskProbe.<hash>`, so a play's saved data is never the real game's), no
   splash screen, no static batching (so each renderer keeps its own mesh name and triangle count), windowed 960x540,
   running in the background, several instances allowed; the game's assets and code are untouched. The build passes
   when Unity exits 0 and the probe's build result says ok. A start that doesn't build makes the task INVALID, unless
   its build check says so (`"fails_at_start": true`: making it build is the task); then the start failing to build is
   the start failing the task, and it is never played.
4. Checks the reference as if it were a solution: the task's checks in order (a check whose `needs` failed doesn't run
   and fails): build, boot (a play of `seconds` that must end without a crash: a player log line matching `Crash!!!`,
   `OUTPUTTING STACK TRACE`, `Fatal error` or `Out of memory`), `log_absent`, `file_exists`, and every probe against
   its threshold.
5. Checks the start on its probes.
6. Writes the result and deletes the scratch copies (unless `--keep`).

### The plays

Each play is the built player started windowed at 960x540 (`-screen-fullscreen 0 -screen-width 960 -screen-height
540`) **on a Windows desktop of its own** (`tools/task_check/desk.py`): nothing shows on your screen, the play can't
take your keyboard, and a game that locks the mouse cursor can't grab yours. The game counts itself focused for the
whole play (`Application.isFocused` is true, no `OnApplicationFocus(false)`), so a game that pauses on focus loss plays
on, and the frame read back is the same as a normal window's. (Only a player you start by hand on your own desktop,
to try a play, has its window moved off-screen and deactivated by the probe instead; that one does see itself lose
focus.) The probe opens the task's `play_scene` with the task's `play_args` (or the task play's own `scene` and
`args`; `play_args` apply to every play, look, drive and boot included) and runs it on a fixed 30 fps clock (play time
is frames / 30) from the moment the scene has loaded; the clock holds while any scene is still loading and during a
`wait`, and keeps counting when the game pauses itself (`timeScale` 0). It samples every 0.5 s (a task play's
`every`). The game's first build scene gets `Awake` and `OnEnable` but is replaced before its `Start`
(task-probes.md, section 1.1). Every play starts from clean saved data: the probe clears the copy's own PlayerPrefs and
persistent data folder when a play starts, and the checker deletes them with the copy. Each play is played once per
side, with the measures of every probe that names it. Keys, buttons and axes go through the probe's own virtual Input
System devices; your keyboard and mouse are never read. A play with an `audio` measure is paced to real time; in every
play the probe's tap on the AudioListener measures the mix and silences it, so no play is ever heard
(task-probes.md, section 2.16).

| `play` | What |
|---|---|
| `"look"` | 20 s, no input, 6 screenshots |
| `"drive"` | 22 s, 8 screenshots: `<Keyboard>/w` 1-6 s, `<Keyboard>/d` 6-8 s, `<Keyboard>/w` 8-13 s with `<Keyboard>/space` at 9-9.3 s, `<Keyboard>/a` 13-15 s, `<Keyboard>/w` 15-21 s |
| `{"name": ..., "seconds": ..., "inputs": [...]}` | a task play: keys, axes, widget clicks, cursor moves, teleports, teleports next to an object and waits at their times, its own `scene`, `args` and `every`; 2 screenshots |
| `"editor"` | one batchmode editor pass per side over every `asset` measure (the project as saved) |
| a boot check | `seconds` of play, no input; `log_absent` reads a 60 s boot's log |

A boot is the same idle game as `"look"`, only longer, so on the side that boots (the reference; a start is never
booted) one 60 s idle play with look's queries serves both: the boot check reads all of it and `"look"` reads only its
first 20 s, exactly what a 20 s play would have measured. That saves a game launch per task. A look probe that reads
the log (`"probe": "log"`) keeps its own 20 s play, because a log covers the whole play. The kept files are then under
`boot_60s\`, not `look\`. Each play's progress line says how long it took, and how much of that it waited for a
machine slot (`unity-heavy.ps1`).

### Thresholds

- `{"op": ">=", "value": 1}`: a literal.
- `{"op": ">=", "calibrate": 0.5}`: `s + 0.5 * (r - s)` between the start's measure `s` and the reference's `r`.
  If the start measured nothing (its play crashed: often the bug itself), the threshold is `r` moved a quarter of
  `|r|` toward the start's side. If the reference measured nothing, or both sides measure the same, the probe fails as
  **uncalibrated**.
- `{"op": ">=", "start_times": 1.3}` / `{"op": ">=", "start_plus": 5}`: `s * 1.3` / `s + 5` from the start (for a
  task with no reference). A start that measured nothing leaves no threshold (uncalibrated).

## VALID and INVALID

A task is **VALID** when all of this holds:

- the start builds, or doesn't build exactly when a build check says `fails_at_start`;
- with a reference: the reference builds, boots (every `boot` check) and passes every **required** probe;
- the start fails every required probe outside `still_works` (or doesn't build by design): each is one issue of the
  thread, and one the start already passes rewards no work;
- every required probe in the `still_works` milestone already passes at the start. What must keep working has to work
  before the change, or the probe is broken and would fail every correct solution. A still-works probe the start
  measured nothing for (its play crashed, which is often the task's own bug) doesn't count against it;
- a no-op scores zero: no deterministic check the start passes carries weight, required or not, so build, boot and
  `still_works` checks, and any probe the start already passes (a `"required": false` one too), take `"weight": 0`.
  Judges and trace probes aren't measured here, so their weights aren't covered by this rule.

Never part of the check: judges (`judge`, `code_judge`, `actions_judge`: quality scores, never pass/fail), trace probes
(they read an agent's own tool calls), and `package` checks. The reference's other failures (`log_absent`,
`file_exists`, probes with `"required": false`) are reported as notes and never make a task INVALID.

A task with no reference is checked on its start alone: it must build, fail every required probe outside
`still_works` (thresholds relative to the start, or literals), and pass its still-works probes. Every shipped task has
a reference (unity-write-tasks section 1; `tools/validate-game.py` rejects one without), so this is for drafts only.

## Results

- One line per task on the console; progress goes to stderr.
- `<repo>\.task-checks\<task>.json` (format `task-check/1`): `verdict`, `reasons` (why INVALID), `notes`, the `start`
  and `reference` commits and whether they built, `probes` (per probe: its milestone, `required`, `op`, `expect`, the
  `start` and `reference` measures, the `threshold`, and whether each side passed), every check's row on each side
  (`start_checks`, `reference_checks`: `passed` and a `detail` such as `... | measured 1.18, threshold >= 1.193 (start
  1.18, fix 1.205)`), `missing_assets` (per side, the played scenes' asset GUIDs the commit has no asset for), and the
  task file's `task_sha256`.
- `<repo>\.task-checks\<task>\<side>\<play>\`: each play's `probe.json` (the track, the camera rows, every measure's
  samples, `query_errors`), `probe.log` (the probe's own lines: teleports, clicks, waits and errors, each with play
  time and real time), its screenshots (960x540 PNGs, UI included) and `play.log`, the game's own player log;
  `build\build.log` (Unity's
  editor log of the build) when a build failed. Read these when a value surprises you.
- `.task-checks\` is git-ignored: new games have it in `.gitignore` (templates/unity-game); for an older game the
  checker adds it to the repo's own `.git\info\exclude`. Never commit results.

## Common reasons and fixes

**`start already passes every required probe`.** The bug doesn't show in what the probes measure.
- The play never reaches the situation: the idle `look` stands at the spawn, the `drive` walks a fixed pattern. Write a
  task play that gets there: a `teleport` input (`{"t": 0.2, "teleport": [x, y, z], "yaw": 90}` places the player,
  in metres, y up; take the coordinates from the editor, or from the `track` in a play's `probe.json`), its own
  `scene` (`Assets/Scenes/Arena.unity`) and `args` (`["-scenario", "2"]`), and the inputs that trigger the bug.
- The measure is the wrong one: compare the start's and the reference's `probe.json` samples for the field you read
  and pick one that differs.
- The play opens a later scene, but the game sets itself up in its boot scene's `Start`: the probe opens `play_scene`
  before that scene's `Start` runs (only its `Awake` and `OnEnable` do), so what it sets up there is missing. Start
  such a game through its own `play_args` with `play_scene` null (task-probes.md, section 1.1).

**`uncalibrated: ... the start and the reference both measure X`.** The measures are equal on both sides, so there is
nothing to put a threshold between: the probe doesn't see the change. Measure something the fix changes (a
different field, window or play), or use a literal value when the fact is a count or a boolean. A probe that isn't
required and can't be calibrated fails as a note, never as a reason for INVALID.

**`no samples in the window (the play ended at X s)`.** The play ended before the window: the window or `at` lies past
the play's `seconds`, or the game crashed or quit (see the play's log). **`the play wrote no probe file`**: the game
never got to play (a crash at load, a scene that doesn't exist at that commit).

**`no value in the window (nothing it selects was measured)`.** The selection matched nothing, or nothing it matched
has that field. `component` is the C# type name (`Projectile`) or its full name (`MyGame.Projectile`); an instantiated
prefab's object is named `<Prefab>(Clone)`, so select it by `name` with a wildcard (`Projectile*`); only objects active
in the hierarchy match unless the select says `"inactive": true`; a component's member is
`prop:<Component>.<member>`; `; the probe said: ...` quotes what the probe couldn't read (`query_errors`). The `rows`
in the play's `probe.json` show what was found, and `probe.log` beside it what the probe did (a `teleport_to` that
found nothing, a widget click that matched no button). Some fields have no value at first by design: `spin` on the
first sample an object is seen in, `speed` of an object with no velocity of its own then too, audio `level` in the
play's first frames.

**`the editor couldn't measure it: ...`.** An `asset` measure the editor pass refused: a path it has no asset, scene or
prefab for (`no asset`, `no scene`, `no prefab`), a colour without a channel, an unknown shader property or member,
or a select using `player`, `has` or a `near` around the player or the camera (task-probes.md, section 2.11).

**Keys do nothing.** The probe drives the Input System only. A game that reads the old Input Manager
(`Input.GetKey`, `Input.GetAxis`) takes no input in a play; the `track` in `probe.json` stays put through the
`drive`. Such a game's tasks can only use outcomes that need no input (teleports and idle plays), or a start that
reads the Input System.

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

**`start fails still-works X`.** The game works at the start, so a still-works probe that fails there is broken: it
doesn't find the HUD, the object or the value it looks for. Fix the probe (see the play's `probe.json`), never the
threshold.

**`reference fails X`.** The reference doesn't do what the probe asks (a threshold on the wrong side: check `op`), or
the reference's play doesn't reach the situation either. `reference fails boots_clean: crashed` means the reference
crashes in a plain boot.

**`start: Assets/Scenes/X.unity names N assets that the commit doesn't have`** (a note). The scene refers to asset
GUIDs the commit lacks, typically a store pack committed only later, or an asset committed without its `.meta`; in the
plays they load as missing (pink materials, empty mesh slots, missing scripts), which can make probes measure the
wrong thing. Pick a commit that has the assets, or commit them (each with its `.meta`) so the task's commits hold them;
the checker never adds files from other commits.

**`start doesn't build`.** The start's scripts don't compile on its 6000.3 editor as committed, or the player build
fails (`build\build.log`: the `error CS` lines first). Pick a start that builds, or, when making it build is the task,
set `"fails_at_start": true` on the build check (then no threshold may be relative to the start).

**`repo: README: shows no gameplay image`, or another `repo:` error from the validator.** That is
`tools/validate-game.py` checking the game repo itself, not a task. The task check needs only the task to validate
(the schema and the task rules beyond it); fix the repo for packaging, but it doesn't change a task's verdict.

**Exit code 198, or a licence error in `build.log`** (an ERROR line, not a verdict): Unity has no active licence.
Sign in to Unity Hub, check the licence there, and run again.

**`... scratch project folder ... longer than 90 characters`** (an ERROR line): pass a short `--scratch` on the
repo's drive (`--scratch C:\tc`).

**`... LFS object(s) ... aren't in ...'s local store`** (an ERROR line, not a verdict): fetch them,
`git -C <repo> lfs fetch origin <commit>`, and run again.
