# Unity creation replay

Rebuilds one of our Unity games from its first commit by re-running, in order, what its builder actually ran: each
commit's inputs, the editor steps that created its scenes and placed every object, and the shell commands that copied,
moved or deleted content. The replay then checks the result against the game's final commit. It produces the dataset's
`ReplayScripts/` with `Verification/report.json` ([game-format.md](game-format.md), "Complete vs pending";
[schemas/replay-report.schema.json](schemas/replay-report.schema.json)). The replay is required for a complete dataset;
its verdict, PASS or FAIL, is metadata.

Tool: `tools/unity-replay/` (`unity_replay.py`, Python 3.10+, standard library only; editor-side C# in
`tools/unity-replay/editor/`). Per-game settings live in the game's own repo as `<root>/games/<slug>/ReplayConfig.json`
(the template has it); a game without one replays with the defaults (section 5), so games started before the replay
existed need nothing in their repo. `unity_replay.py <command> --game <slug>` loads them; `--game` also takes a game
repo folder, or a settings file (for example a delivered `ReplayScripts/game.json`). Per-game results belong in the
game's own docs, not here.

## 1. How our Unity games are built

Agent sessions build them almost entirely through committed code, and three records cover what they did:

- **C#** under `Assets/` (gameplay code, the editor tools of `Assets/Editor/Tools/`), compiled by the editor itself.
- **Editor steps**: static methods under `Assets/Editor/Steps/`, run headless with
  `Scripts/unity.ps1 step -Method <Namespace.Class.Method> -Reason "..."` (Unity `-batchmode -nographics
  -executeMethod` through the machine's limiter). They create the scenes and place every object, make prefabs,
  materials and data assets, and set import settings. Each run logs `workflow.jsonl` rows through `WorkflowLog.Row`,
  with the step's own file (`source.script`) and the sha256 of its text as it ran (`source.sha256`). The first editor
  open (`Scripts/unity.ps1 setup`, which `templates/new-game.ps1` runs) is four such runs.
- **Shell steps**: generated source files (images, sounds), store packs copied in, copies and moves of content.

| Record | What it gives the replay |
|---|---|
| git history (`games\<slug>`) | the exact inputs (code, editor steps, settings, source art) at every commit, and the committed content to compare against |
| `workflow.jsonl` | what each editor step run did (rows with `source.script`, `source.sha256`, time, `status`, params such as piece counts) |
| `.recording\<slug>\actions.jsonl` | the agent's tool calls in order: every editor step run (with the command line and its output), every `Write`/`Edit` (`apply_patch`) of a file, every shell copy |

The replay also reads `.recording\<slug>\commits.jsonl` (the post-commit recorder's rows) for the moment each commit
was made: a commit's own time has whole seconds only.

## 2. Replay design

### 2.1 The replay unit

The unit is the **window**: the work between two consecutive commits on the first-parent chain, closed by the commit.
A window's steps come from the ledger (`unity_replay.py ledger`), in the order they happened.

What the replay writes from the commits and what it makes itself:

- **Inputs** are the files the builder writes: code and text (`.cs`, `.asmdef`, shaders, `.json`, docs), source art
  (images, sounds, models), `Packages/` (the manifest and the lock file, so every window runs on exactly the package
  versions its commit names), `ProjectSettings/ProjectVersion.txt` and everything else outside `Assets/` and
  `ProjectSettings/`.
- **Content** is what the editor writes: Unity's serialized assets under `Assets/` (`.unity`, `.prefab`, `.mat`,
  `.asset`, `.controller`, `.anim`, ...; settings `content_ext` adds extensions), every `.meta` under `Assets/`, and
  `ProjectSettings/`. Content is never copied from a commit when the replay produced it, so errors accumulate visibly
  instead of being reset.

| Step | Source | What the replay does |
|---|---|---|
| `inputs.apply` | commit tree | writes every input the commit adds or changes; deletes what it deletes; `workflow.jsonl` as the commit has it |
| `meta identity` | commit tree | each new input file and folder gets its `.meta` from the commit before the window's first editor run, so Unity imports it under the GUID the builder's editor gave it (other files refer to it by that GUID); a later change of its import settings is the replay's own (`input_meta`, section 5) |
| `code at run time` | `actions.jsonl` `Write`/`Edit`/`apply_patch` and shell edits | every code file (`.cs`, `.asmdef`, `.asmref`, `.rsp`, `Packages/manifest.json`) the builder wrote in the window, as it stood when the step started, rebuilt by re-applying the writes and edits from the previous commit's text |
| `assets.drop` | settings + `actions.jsonl` | copies a store pack into the project at the point where the builder copied it (`asset_drops`) |
| `shell content step` | `actions.jsonl` | a `cp`, `mv` or `rm` (`Copy-Item`, `Move-Item`, `Remove-Item`) of content files in a recorded command, done to the replay's own files at the same point: a copy of a material is a copy of the material the replay made |
| `shell.replay` | settings | shell commands that changed content and that the replay cannot read, matched to the recorded command (`match`) and replayed as `argv`: `delete <paths>`, `copy <src> <dst>`, `move-merge <src> <dst>`, `host-python <script> <args>`, `keep-committed <dirs>` |
| `editor.step` | `actions.jsonl` command lines | re-runs the step headless in the replay project: `Unity.exe -batchmode -nographics [-quit] -projectPath <project> -logFile <log> -executeMethod <method>` with the recorded `-Reason` as `UNITY_RUN_REASON`; `-quit` unless the builder ran it with `-NoQuit` |
| `boundary` | commit | checks the window (section 2.4): identity, content, fallbacks; then makes the replay project's inputs equal to the commit |

The editor runs it recognises in a recorded command: `Scripts/unity.ps1 step -Method <m>` (also inside a `for` or
`foreach` loop, with the method written out or built from the loop variable), `Scripts/unity.ps1 setup` and
`templates/new-game.ps1` without `-NoSetup` (the first open: the four runs of the game's own `Scripts/unity.ps1`
setup table, from the copy of that file the run used), and `Unity.exe ... -executeMethod <m>` with `-projectPath`
naming the game repo. A wrapper of the game's own is added with `run_patterns` (a regex with the named groups
`method`, `reason`, `args`, or `{"pattern", "method", "reason", "quit"}`). `unity.ps1 compile`, `test`, `build` and
`play` do not change the project's content and are not replayed. The exit code of each run and the workflow row ids it
printed (`[workflow] <id> ...`) come from the recorded output.

Read-only runs (probes, checks: settings `readonly_patterns` on the step's class name, by default `Inspect*`,
`Measure*`, `Check*`, `Analyze*`, `Scan*`, `*Probe*`) are listed but skipped, except a class in `not_readonly` (every
run of it) or one run in `not_readonly_runs` (`{tool_use_id, method, reason}`) whose output a later run reads. A run
the recorded actions miss is rebuilt from the workflow row its step wrote (`runs_from_rows`:
`[{"row": "<id>", "method": "<Ns.Class.Method>"}]`; listed as a deviation): the usual cause is a tool call interrupted
while its editor kept running, which records no PostToolUse event. Runs the records show never happened go in
`not_run` (`{tool_use_id, method, reason}`). A run whose editor finished before a commit that its tool call outlived
(its last workflow row is before the commit) is put before that commit. The replay never commits.

### 2.2 Preparing the isolated project

`unity_replay.py prepare` creates `%UGF_ROOT%\unity-replay\<game>\` (settings `work_root`) with:

- `<slug>/`: the replay project, a `git clone --shared --no-checkout` of the game repo, Git LFS reading the game's own
  object store (`lfs.storage`; nothing downloaded), checked out at the **first commit** (the template's skeleton). It
  carries the game folder's name because Unity names a new project's settings after its folder (`metroPackageName`).
  The game repo itself is only read.
- `work/`: ledger, state, blobs (step and code texts), logs, rows, dumps, results.
- `truth/<slug>/`: the same clone at the final commit, used to dump the reference state (`unity_replay.py dump
  --which truth` checks it out there and imports it; `unity_replay.py truth` imports it on its own).

Unity fails on paths longer than 260 characters: keep `work_root` short (the default is under the machine root).
`initial-assets.manifest.json` lists what the replay takes from outside the game's history (store packs dropped in,
external sources), with sha256 per file.

An external source a step reads (a folder named by an environment variable of the recorded command, or by an absolute
path in the step's text) goes in `external_sources`: `{"id", "role", "recorded": "{home}/Downloads/pack", "path":
"{root}/asset-library/pack", "remap_scripts": true}`, or with a `rebuild` recipe (`{"unzip": [{"zip": "<glob>",
"to": "<subdir>", "exclude": [...]}]}`) when the builder unpacked it into a scratch folder that no longer exists.
Settings never hold a machine's user name or tool folders: what the recording says (`match`, `recorded`) is written as
a template and matched on any machine (`{home}` = any user profile, `{root}` = any path prefix, `*` = one path
component, `/` = any slash).

### 2.3 Running

`unity_replay.py run` executes the plan, resumable (`work/state.json`; a `work/STOP` file pauses it between steps).
Every editor process goes through `<root>\tools\unity-heavy.ps1` (a machine without it runs the editor directly), and
every one is headless: a general slot, never a GPU slot. A step the builder ran with `-Render` (screenshots, baked
lighting) runs headless too and is listed (`render_runs_headless`). Each run's new `workflow.jsonl` rows are cut out
and saved (`work/rows/<run>.jsonl`) and the project's `workflow.jsonl` is restored, so the file stays an input. A run
that lasts longer than `run_timeout_s` (default 3600) is stopped and counted as failed (a step started with `-NoQuit`
that never exits). A run in which the editor crashed before the step logged what the original did is run once more.
Each editor run is logged under `work/logs/runs/`.

### 2.4 What is checked

Per window (`work/windows.jsonl`):

1. **Reconstruction**: every code file rebuilt from the recorded edits matches the commit's text at the boundary (one
   that does not is listed in the report, `reconstruction_mismatch`).
2. **Identity**: the GUIDs of the assets the replay created (Unity makes a random one in every editor) become the ones
   the commit has at the same paths, in the `.meta` files and in every file of the window that refers to them; so does
   the project's `productGUID`. Identity, never content: what refers to what stays the replay's (`guids_adopted`).
3. **Content**: every content file the commit adds or changes is identical, differs (kept as the replay made it) or,
   when no replayed step produced it, is taken from the commit (`fallback`, with the reason; listed as a deviation);
   files the commit deletes are deleted; the set of files under `Assets/` and `ProjectSettings/` against the commit
   (`missing`, `extra`).
4. **Behaviour** (in the report): each replayed run's workflow rows against the original run's (same `op`, `target`,
   `status`, the same `params` once times and absolute paths are masked), and the sha256 of the step's text the rows
   carry, as the builder ran it and as the replay ran it.

At the end (`unity_replay.py verify`, against the final commit):

1. **Files**: every tracked file outside `Assets/` is byte-identical to the final commit.
2. **Structure**: `editor/ReplayDump.cs` runs headless on the replayed project and on `truth/`
   (`unity_replay.py dump --which replay|truth`), and the dumps are compared:
   - every asset by path: main type, importer and its settings, the sha256 of a source file (code, images, sounds,
     models), every serialized object of the file (all visible fields), a mesh's vertex and index counts and bounds, a
     texture's size and format, a sound's length and channels, a prefab's hierarchy;
   - every scene: each GameObject by hierarchy path (siblings that share a name as `Name[k]`), matched by path and then
     by nearest position: active, tag, layer, static flags, prefab source, every component with all its visible
     serialized fields (floats to 1e-4, tolerance 0.0011); the scene's render and lighting settings.
   References are compared as paths (`asset:Assets/X.mat`, `scene:Root/Child|UnityEngine.Light`,
   `builtin:Mesh:Cube`), never as GUIDs or file ids.
3. **Verdict** (`report.json` `verdict`, top of `report.md`): PASS only when (a) every tracked file outside `Assets/`
   is byte-identical, none missing, and no extra files except git-ignored ones; (b) every asset has the same type,
   import settings and structure; (c) every scene (`scene_roots`) has the same GameObjects with the same components,
   values and scene settings. Known non-content differences are normalised first and counted in `verdict.exclusions`
   (a list of `{id, what, count}`): the bytes of Unity's serialized files under `Assets/` (every new object gets a
   random file id), GUID strings inside values, absolute paths into the folder the editor ran in, the adopted GUIDs,
   git-ignored extra files, scenes outside `scene_roots` (store packs' demo scenes), folders in `dump_exclusions`
   (assets that fail to load, in the final commit too). Workflow-row comparison is informational.

`report.json` follows [schemas/replay-report.schema.json](schemas/replay-report.schema.json) (the tool checks it when
it writes it); `deviations` lists every place the replay departs from the raw recording, with the reason, and
`report.md` says the same for people. `unity_replay.py report` re-renders the deviations from the current settings
without verifying again.

### 2.5 World ops

The headless replay is the reference. A step places many objects inside one call; to show scene building object by
object, every scene can also be described as **world ops**:

- With `"scene_exports": true`, after every replayed run that changed a scene, `ReplayDump.cs` exports that scene (an
  extra headless editor run per such run).
- `unity_replay.py derive` turns consecutive exports into ops tied to the run that produced them: `scene.create`,
  `object.spawn` (the object with every component and value), `object.update`, `object.remove`, `scene.save`, in the
  workflow field set (`id`, `chapter`, `op`, `target`, `params`, `reason`, `source`, `expected`, `presentation`) with
  `status: derived_from_replayed_step_run`. Without exports, each scene of the final replay dump becomes one
  `scene.create` with all its objects.
- `unity_replay.py world` plays the ops headless (`editor/ReplayWorld.cs`): each scene rebuilt under
  `Assets/CreationReplayWorld/`, dumped in the same run and removed again, and compared with the scene the steps built
  (`work/world/report.json`). The ops are not part of `ReplayScripts/`.

### 2.6 ReplayScripts

`unity_replay.py package --game <game>` assembles it in `<out>\_replay\<game>\<final sha8>\` (`<out>`: env `UGF_OUT`,
config `out`, else `%UGF_ROOT%\deliverables`), unscrubbed:

```
ReplayScripts/
  README.md                       how to replay, what is observed vs verified, results, deviations
  unity_replay.py, runner.py, ledger.py, derive.py, verify.py, shellfx.py, patchfx.py, package.py, live.py
                                  the tooling as it ran (it works outside the tool checkout: UGF_ROOT or ~/UnityWork)
  editor/CreationReplay.Editor.asmdef, ReplayDump.cs, ReplayWorld.cs
  game.json                       the game's replay settings ({root} placeholders, no machine paths)
  ledger.json                     windows, step runs, texts (from history + actions)
  initial-assets.manifest.json    store packs and external sources, sha256 per file
  Blobs/                          step and code texts by sha256
  Verification/
    report.md, report.json        files, assets, scenes, rows, verdict, deviations
    windows.jsonl                 per-window checks
    dump-replay/, dump-truth/     the JSON structure dumps of both projects
verification.json                 summary for the packager: parts present, windows, verdict
READY                             written last, when every window was replayed and verified (PASS or FAIL)
```

`--force` assembles an incomplete copy without `READY` (for checks only). The build machine's session folders and
session ids in the copied records become neutral names.

Disk: `prepare`, `run`, `dump`, `live`, `truth` and `release` refuse to start when the work drive has less than
`min_free_gb` (env `UGF_MIN_FREE_GB`, default 50 GB) free, `package` likewise for `<out>`. Once `READY` exists,
`unity_replay.py clean --game <game>` lists the replay project, the truth project and the bulky work files and removes
them with `--yes`; the ledger, state and report stay.

### 2.7 Code as it stood when each step ran

The window's inputs are the commit's, but a step that ran before a mid-window code change ran with the earlier code.
The ledger records, per run, every code file the builder wrote in the window as it stood at the run's start (`texts`,
`absent` for one not written yet, `unknown` for one the recording cannot rebuild, which keeps the commit's text). The
runner writes those texts before the run and puts the commit's code back at the boundary. A code file the window
changes without a recorded write was changed by the editor (`Packages/manifest.json` through the Package Manager) or
outside the recording: it keeps the commit's text for every run. When the run-time code does not compile here although
the builder's run did, the run gets the commit's code (`code_at_run_time_not_buildable`); when the commit's own code
does not compile on its editor (a mid-upgrade commit), the run takes the code of the nearest later commit under which
it compiles (`code_from_commit`; settings `"code_from_later_commit": false` turns it off). Both are deviations, never
verdict rules.

### 2.8 Editor per commit

With `"editor": "{editor}"` (the default), every window uses the editor its commit's
`ProjectSettings/ProjectVersion.txt` names (machine/lib/ugfroot.py `unity_for_version`: the config's `unity_editors`,
else Unity Hub's folder), so a game upgraded to a newer editor replays its early commits on the old one. At the commit
that switches, the replay project's `Library/` is cleared and the project is imported again with the new editor
(`editor_switch`, a deviation). The truth project uses the editor its own commit names. A literal `"editor"` path stays
fixed for every window.

## 3. Live replay (per commit, during development)

A game is replayed while it is being built, so its `ReplayScripts/` is verified commit by commit and release only adds
the last windows. `"live": false` in its `ReplayConfig.json` turns it off.

**Trigger.** The game repo's post-commit hook (`machine/install-git-hook.ps1`; `templates/new-game.ps1` installs it in
a new game and `machine/bootstrap.ps1` in every game under `<root>\games`) runs `tools/unity-replay/live-hook.ps1` of
the tool checkout. It returns at once: it prints the last job's findings once (`[replay] ...`), then starts
`unity_replay.py live --game <repo>` detached at below-normal priority unless a job for the game runs (one per game,
`work/live/lock`; the running job picks up new commits before it exits). It acts only for a game of the machine's
root: the repo must be exactly `<root>\games\<slug>` for the root the committing shell resolves (`UGF_ROOT`, else the
machine config). A commit anywhere else that carries the line (a scratch or test copy of a game, a task check's copy,
a clone in `builds\`, a game of another root) starts nothing and writes nothing, and `unity_replay.py live` refuses such
a repo too. A commit on the orphan `tasks` branch is not replayed.

**The job** (`live.py`):

1. Builds the ledger up to `HEAD` and compares it window by window with the ledger already replayed (commit, runs,
   step and code texts, drops, shell steps). If history was rewritten (an amend, a rebase) or the settings changed what
   a replayed window does, the replay project goes back to the last unchanged commit's tree and replays from there
   (`work/live/events.jsonl`, `replay_restarted_from_commit`).
2. Replays the new windows into the persistent replay project (section 2.3). Every editor process goes through
   `unity-heavy.ps1 -Low`: one low-priority job machine-wide, which takes a general slot only while no other job waits
   for one, at below-normal process priority. `work/STOP` pauses it as usual.
3. Checks the new windows: each run against its original (exit code, compile errors, workflow rows), each window's
   content against its commit (fallbacks, extras), and the assets and scenes the new commits touched against the truth
   project at `HEAD` (structure dumps of just those).
4. Reads the recording for work the replay cannot redo: a step call whose method it cannot read, an editor started
   through a wrapper it does not know, a `.unitypackage` imported from the command line (`-importPackage`), a shell
   copy of content it cannot follow (a wildcard, a variable), steps outside the repo or naming the live project folder,
   runs that logged no workflow row, step texts the recording cannot rebuild or rebuilds to another text than the
   commit's, and touched assets that differ from the commit after the replay (a hand edit of a serialized file, a GUI
   change).
5. Writes `work/live/reports/<sha8>.md/.json`, `work/live/status.json` and, when something needs the builder,
   `work/live/feedback.md`; the hook prints it at the session's next commit.

`unity_replay.py live-status` lists every live game (HEAD, replayed window, last result, findings, job running).

**Rules for game sessions** (unity-game-session skill, "Replay-friendly work"): every editor step committed under
`Assets/Editor/Steps/` and run by its method through `Scripts/unity.ps1 step -Method <Namespace.Class.Method>`;
relative paths only, never an absolute path to or `Directory.SetCurrentDirectory` into `games\<slug>`; probes named
by `readonly_patterns` (`not_readonly` for one that writes something later work reads); one workflow row per run at
least; steps edited with the agent's own file tools, or written as a new step; no `.unitypackage` imported from the
command line and no GUI-only edits for content; a store pack copied in gets an `asset_drops` entry; no amend or
rebase.

**Release** (`unity_replay.py release --game <slug>`, normal priority): catches the replay up to the settings' `final`
(`HEAD` by default), checks out `truth/` there, dumps both projects in full, runs `verify` and `package`. With the live
replay current, that is the last windows plus a full final verify. A FAIL is packaged like a PASS: the verdict is
metadata.

## 4. Games started before the replay existed

A game made from an earlier template has no `ReplayConfig.json`, its own copies of `Scripts/unity.ps1` and
`Assets/Editor/Tools/`, and a post-commit hook with the commit recorder only. Nothing has to change in its repo:

1. Pull this repo and run `machine\bootstrap.ps1` (as before every new game). Bootstrap runs
   `machine\install-git-hook.ps1` for every game under `<root>\games`, which adds the live replay's line to each
   post-commit hook. A game repo outside `<root>\games` is not replayed after its commits: replay it by hand
   (`unity_replay.py release --game <repo folder>`; a repo that is not the root's game of its name gets a work folder
   of its own, `<root>\unity-replay\_other\<name>-<id>`).
2. The game's next commit starts its first live job, which replays its whole history from the first commit: one
   headless editor run per recorded step, at low priority.
3. The game replays with the defaults of section 5 (`unity_replay.py` derives the slug, the recording folder and the
   work folder from the repo; each commit's editor from its `ProjectVersion.txt`). When it needs a setting (a store
   pack's `asset_drops` entry, a wrapper in `run_patterns`), copy `templates/unity-game/ReplayConfig.json` into the repo
   root, replace `__SLUG__` with the game's slug, add the setting, and commit it with a `workflow.jsonl` row (op
   `replay.config`); the live job reads the new settings at its next pass and replays the windows they change.

The editor steps such a game ran, its `Scripts/unity.ps1` call shape and its `WorkflowLog.cs` rows are the ones the
replay reads, so its history replays like a new game's.

## 5. Settings (ReplayConfig.json)

| Key | Default | What |
|---|---|---|
| `game`, `repo`, `recording`, `work_root` | from the repo | slug, game repo, its recording, the replay's folders (`{root}` = machine root) |
| `live` | `true` | the per-commit replay after every commit |
| `final` | `HEAD` | the commit `verify`, `package` and `release` take |
| `editor` | `{editor}` | the editor per commit (section 2.8), or a literal `Unity.exe` path |
| `editor_args` | `["-batchmode", "-nographics"]` | the editor's arguments before `-quit`, `-projectPath`, `-logFile`, `-executeMethod` |
| `reason_env` | `UNITY_RUN_REASON` | the variable a run's recorded `-Reason` goes in |
| `readonly_patterns`, `not_readonly`, `not_readonly_runs` | probes by class name | section 2.1 |
| `asset_roots`, `scene_roots` | `["Assets"]` | what the structure dump covers and which scenes the verdict compares |
| `run_patterns` | `[]` | the game's own editor wrappers (section 2.1) |
| `asset_drops` | `[]` | store packs: `{"id", "match", "items": [{"from_git": "Assets/ThirdParty/Pack", "ref"?} or {"from": "{root}/asset-library/...", "to": "Assets/..."}], "reason"}` |
| `shell_replay` | `[]` | shell commands replayed from settings (section 2.1) |
| `input_meta` | `commit` | the `.meta` of a new input file: the commit's whole `.meta`; `guid` writes only its GUID, so Unity imports it with its default settings and a step of the window sets the rest (Unity keeps a `.meta` without an importer section as it is, so every such `.meta` that holds settings is then taken from the commit at the window's end, and listed) |
| `run_timeout_s` | `3600` | the longest an editor run may last |
| `scene_exports` | `false` | section 2.5 |
| `content_ext` | `[]` | more file extensions that count as content |
| `runs_from_rows`, `not_run`, `use_commit_text`, `fold_commits`, `wrapper_row_ops`, `external_sources`, `dump_exclusions`, `step_env`, `code_from_later_commit`, `live_structure`, `scene_list` | | sections 2.1 to 3 |

## 6. Packager integration

A dataset's `ReplayScripts/` is `<out>\_replay\<game>\<release sha8>\ReplayScripts\` (the release commit's id before
the history is rewritten for delivery), complete once `READY` is beside it; `unity_replay.py release --game <slug>`
makes it. What the dataset takes from it: the folder itself, copied, scrubbed like every other text file of the
delivery and with its commit ids mapped to the delivered history (so `report.json` `final_commit` equals the manifest's
`commit`), and the manifest's `replay_verification` from `ReplayScripts/Verification/report.json` (`verdict.pass`,
`verdict.criteria` with their `result`, `verdict.exclusions` as `{id, what, count}`; `report`:
`ReplayScripts/Verification/report.md`). The packager (`tools/package-dataset.py`) takes it from there
([unity-pipeline.md, Dataset packager](unity-pipeline.md#dataset-packager)); without `READY` a dataset lists
`ReplayScripts/` as pending. The replay is required but need not pass: a FAIL is packaged as metadata (manifest
`replay_verification.pass` false, the README says FAIL), and the dataset is complete with it as with a PASS
([game-format.md](game-format.md), "Complete vs pending").
