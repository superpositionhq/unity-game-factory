# The probe's tests on the real engine

`tools/task_check/TaskProbe/` runs inside a built Unity player, so only the engine can tell whether a measure reads
what it says. These tests build a real player with the package, play it the way the task checker does, and check every
value. A field that no play here checks is not tested.

## Running them

```
python tools/task_check/probe_tests/run.py <project> [--only FAMILY ...] [--play FAMILY.PLAY ...] [--skip-build] [--once] [--package DIR] [--direct] [-v]
```

`<project>` is a scratch Unity 6000.3 project the run may change: a copy of a URP project with the Input System and
uGUI with TextMeshPro (a new game from `templates/unity-game` will do). Never a game's own folder: the run adds
folders, tags and layers to it. Keep its path short (Unity fails past 260 characters).

The run:

1. adds the package (`Packages/com.taskprobe/`, as the checker adds it) and every family's material
   (`Assets/ProbeTests/<family>/`);
2. starts the editor once to make every family's scenes;
3. builds the player once, as the checker builds its scratch copy;
4. runs each family's editor pass and plays as the checker runs them (a windowed player on a Windows desktop of its
   own: nothing shows on your screen), each play twice: the second must write the same probe.json as the first;
5. prints one line per play and exits with 0 when everything passed.

```
probe tests in C:\t\proj (package: ...\tools\task_check\TaskProbe)
ok    setup: 7 method(s)  95 s
ok    build: 19 scene(s)  212 s
PASS  core.clock                           21 checks  same twice  14 s
FAIL  light.lamps                          64 checks, 1 failed  same twice  11 s
      FAIL illuminance under the lamp at 2 s: got 3.11, want 3.25 +- 0.01
...
```

`--only` runs some families (the others' material is taken out of the project), `--play` some plays, `--skip-build`
leaves out steps 1 to 3 (the project as an earlier run built it), `--once` the second play, `-v` prints every check.
`--package` tests a package folder other than the repo's. What each play wrote is kept in
`<project>/Logs/ProbeTests/<family>.<play>/` (probe.json, probe.log, the screenshots, the player's log); the build's
log is `<project>/Logs/TaskProbe/build.log`, the scene builders' `<project>/Logs/TaskProbe/probe_tests_setup.log`.
The editor runs through the machine's `unity-heavy.ps1` when the machine has one (`--direct`: never).

## A family

One folder per family of measures, each with the same layout:

```
<family>/
  README.md      what each scene holds and what each play proves
  tests.py       the manifest and the checks
  Editor/*.cs    editor scripts that build its scenes and assets   -> <project>/Assets/ProbeTests/<family>/Editor/
  Scripts/*.cs   game scripts, one MonoBehaviour per file named after it -> .../<family>/Scripts/
  Assets/**      other source files its scenes need (shaders)       -> .../<family>/Assets/
  plays/<play>.json   one play spec each
```

- C# is in a namespace of the family's own under `ProbeTests` (`ProbeTests.Core`), and a type name is unique across
  all families: a select by `component` and a `prop:` path find a type by its name alone (the runner refuses two
  scripts of one file name). The namespace's last part must not be the name of a type another family's code uses:
  inside `ProbeTests.*` it would be found before the type (`ProbeTests.Light` hides `UnityEngine.Light` from every
  family, so the light family is `ProbeTests.Lighting`). Test scripts compile into the game's assembly and cannot
  reference the `TaskProbe` assembly: the tests are black-box.
- In a test project each MonoBehaviour is in its own file named after it (several in one file made the player fail
  to load the scene).
- The scene builders (`SETUP`) are static methods without arguments. They make the scenes from code, write everything
  they make under `Assets/ProbeTests/<family>/Made/` (emptied before every setup), return normally and are
  deterministic.
- A play spec is the checker's play spec (`tools/task_check/CONTRACT.md` section 5) without `format` and `out`; its
  `queries` is a list of queries, each with an `id` of your choosing.
- Plays are deterministic: test objects move by game time (`Time.deltaTime`, physics), never by real time or
  unseeded random numbers. A measure that depends on real time by its nature (the audio mix's `level`, anything after
  a `wait`) is named in the play's `varies`, with the reason beside it.

`tests.py`:

```python
"""<what the family tests>"""
SETUP = ["ProbeTests.Lighting.LightScenes.Build"]         # the scene builders, run in one start of the editor
SCENES = ["Assets/ProbeTests/light/Made/LightLab.unity"]  # the scenes the plays open (added to the build)

def lamps(t, play):
    """<what this play proves>"""
    t.near("illuminance under the lamp at 2 s", play.value("under_lamp", 2.0)["illuminance"], 3.25, 0.01)
    t.eq("one light reaches the point", play.value("under_lamp", 2.0)["lights"], 1)

PLAYS = {                    # in the order they run; a play's spec is plays/<name>.json
    "lamps": {"check": lamps},
    "walls": {"check": walls, "args": ["-scenario", "2"], "errors": [r"^light under_wall: "], "varies": ["mix"]},
}

ASSETS = {"measures": "measures.json", "check": saved}    # one editor pass: {"<id>": {<asset measure>}}; saved(t, results)
```

- `t.eq(what, got, want)`: exactly equal. `t.near(what, got, want, tol)`: a number within `tol`. `t.ok(what,
  condition, got=None)`: anything else. Each call is one line of the report. A tolerance follows from the measure (a
  float widened to a double: 1e-5), never from the value that happened to come out.
- `play`: `.probe` (probe.json), `.log` (the player's log), `.probe_log`, `.files`, `.spec`, `.errors`
  (`query_errors`), `.samples(id)`, `.sample(id, t)`, `.value(id, t)`, `.rows(id, t)`, `.row(id, t, name)`,
  `.series(id, field, name=None)`, `.track(t)`, `.camera(t)`, `.image("shot_00.png")` (`width`, `height`,
  `at(x, y)`), `.earlier("<play>")` (an earlier play of the family).
- A play's entry: `check`; `args` (player arguments after the spec); `ended` (what probe.json's `ended` must say,
  default `"time"`); `errors` (regular expressions: every `query_errors` line must match one and each must match a
  line; none by default, so an unexpected error fails the play); `varies` (measure ids left out of the comparison of
  the two plays, or `True` to play it once); `timeout` (seconds).
- `t.project` is the test project's folder (a `Path`): a check may read the project's files, or start its built
  player itself (`<project>/Build/TaskProbe/Game.exe`, through `tools/task_check/desk.py`) for what a probe play
  cannot show.
- For every play the runner itself checks: the player's exit code is 0, probe.json was written, `ended`,
  `query_errors`, no exception of the probe's in the player's log, and the second play's probe.json is the first's.
  For an editor pass it checks the editor's exit code, that the result is the pass's own, and that the pass changed
  no file under `Assets/`, `Packages/` and `ProjectSettings/`. For the build it checks that no file under `Packages/`
  and `ProjectSettings/` changed: the checker's build changes player settings and must put them back (`Assets/` is
  left out: in any player build URP writes into its own assets there).

## The families

| Family | What it tests |
|---|---|
| `core` | the play itself: the clock, samples, inputs, teleports and holds, waits, scene loads, the player and the camera, screenshots, saved data, how a play ends, the queries list's errors |
| `select` | object selects (every key), `prop:` paths, rows, the 200-row cap |
| `world` | `camera`, `spawns`, `pieces`, `ground` |
| `objects` | `objects` and `components`: every field, `lit` and `glow`, change over time |
| `ui` | `widgets`, `ui`, `screen`, clicks on widgets |
| `ocr` | the frame text reader behind `ui` |
| `light` | `light`, `grading`, `audio` |
| `drawn` | `drawn`, and what its renders leave behind |
| `asset` | the editor pass over the project as saved (asset measures), and the build |

Each family's README says what its scenes hold, what each play proves and what it leaves untested.

## A project that lacks a part

```
python tools/task_check/probe_tests/variants.py <template project> [--package DIR]
```

The package must compile in a game without the Input System, uGUI, TextMeshPro or URP, and in one that took a
built-in module out (physics, 2D physics, audio, animation, particles, terrain, AI, UI Toolkit, video, cloth, vehicles,
image conversion). `variants.py` compiles the runtime assembly with the editor's own C# compiler, without starting the
editor, once per missing part: each of the asmdef's defines off with the assemblies it stands for taken away (and those
of every module that needs that module), every package off, every module off, both, and each removable module gone
with every define still on (a use of a type outside its guard). `<template project>` is any project that has opened
once in the editor with the template's packages (its `Library/ScriptAssemblies` gives the packages' assemblies). It
prints one line per variant and exits with 0 when all compile. It starts no editor and no player: it proves the
package compiles there, not what a play measures there (a measure that needs the missing part gives no value and one
`query_errors` line saying which part the project lacks).
