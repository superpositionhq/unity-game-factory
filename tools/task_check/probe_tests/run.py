"""The probe's regression run on the real engine: every family's plays against the TaskProbe package as it is in the
repo, every value checked, a pass/fail table printed (README.md beside this file).

    python tools/task_check/probe_tests/run.py <project> [--only FAMILY ...] [--play FAMILY.PLAY ...] [--skip-build]
                                               [--once] [--package DIR] [--direct] [-v]

<project>: a scratch Unity 6000.3 project the run may change (a copy of a URP project with the Input System and uGUI;
never a game's own folder). The run
1. adds the package to it as the checker does (Packages/com.taskprobe) and every family's material
   (Assets/ProbeTests/<family>/);
2. starts the editor once to make every family's scenes (each family's SETUP methods, through Setup.cs);
3. builds the player once, as the checker builds a scratch copy, with every family's SCENES;
4. runs each family's editor pass (ASSETS) and plays (PLAYS) as the checker runs them, each play twice: the second
   must give the same probe.json as the first (two plays of one build measure the same);
5. checks every value and prints one line per play; exit code 0 when everything passed.

--only: just these families (the others' material is taken out of the project). --play: just these plays.
--skip-build: steps 1 to 3 left out (the project as an earlier run built it; needs no editor unless a family has an
editor pass). --once: no second play. --package: a package folder other than the repo's. --direct: never through the
machine's unity-heavy.ps1. -v: every check, not only the failed ones. What each play wrote is kept in
<project>/Logs/ProbeTests/<family>.<play>/.

Standard library only (Python 3.12)."""

import argparse
import hashlib
import importlib.util
import json
import re
import secrets
import shutil
import struct
import sys
import time
import zlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent))
from task_check import probes, seeds, unity  # noqa: E402

TESTS = "Assets/ProbeTests"  # in the project: <family>/Editor, Scripts, Assets (from the repo) and Made (what SETUP makes)
PARTS = ("Editor", "Scripts", "Assets")
MADE = "Made"
SETUP_METHOD = "ProbeTests.Setup.Run"
KEPT = "Logs/ProbeTests"
PROBE_STACK = re.compile(r"^\s*at TaskProbe\.", re.M)  # an exception of the probe's own in the player log


# -- what a family's checks get ---------------------------------------------------------------------------------------


class Checks:
    """The checks of one play (or editor pass): each call is one line of the report. `project`: the test project's
    folder (a check may look at its files, or start its built player itself)."""

    def __init__(self, project):
        self.project = Path(project)
        self.lines = []  # (passed, what, detail)

    def eq(self, what, got, want):
        """`got` is exactly `want`."""
        self.lines.append((got == want, what, f"got {got!r}, want {want!r}"))

    def near(self, what, got, want, tol):
        """`got` is a number within `tol` of `want`."""
        ok = isinstance(got, (int, float)) and not isinstance(got, bool) and abs(got - want) <= tol
        self.lines.append((ok, what, f"got {got!r}, want {want!r} +- {tol!r}"))

    def ok(self, what, condition, got=None):
        """`condition` holds; `got` is shown when it doesn't."""
        self.lines.append((bool(condition), what, "" if got is None else f"got {got!r}"))

    @property
    def failed(self):
        return [line for line in self.lines if not line[0]]


class Image:
    """A screenshot: `width`, `height`, and `at(x, y)` -> (r, g, b) of the pixel at column x, row y from the top."""

    def __init__(self, data):
        if data[:8] != b"\x89PNG\r\n\x1a\n":
            raise ValueError("not a PNG")
        at, packed = 8, b""
        while at < len(data):
            size, kind = struct.unpack(">I4s", data[at:at + 8])
            body = data[at + 8:at + 8 + size]
            if kind == b"IHDR":
                self.width, self.height, depth, colour, _, _, interlace = struct.unpack(">IIBBBBB", body)
                if depth != 8 or colour not in (2, 6) or interlace:
                    raise ValueError("only 8-bit RGB and RGBA PNGs without interlace are read")
                self.channels = 3 if colour == 2 else 4
            elif kind == b"IDAT":
                packed += body
            at += 12 + size
        raw, n, stride = zlib.decompress(packed), self.channels, self.width * self.channels
        self.rows, before = [], bytearray(stride)
        for y in range(self.height):
            kind, row = raw[y * (stride + 1)], bytearray(raw[y * (stride + 1) + 1:(y + 1) * (stride + 1)])
            for i in range(stride):
                a = row[i - n] if i >= n else 0
                b, c = before[i], before[i - n] if i >= n else 0
                if kind == 1:
                    row[i] = (row[i] + a) & 255
                elif kind == 2:
                    row[i] = (row[i] + b) & 255
                elif kind == 3:
                    row[i] = (row[i] + (a + b) // 2) & 255
                elif kind == 4:
                    p = a + b - c
                    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                    row[i] = (row[i] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
            self.rows.append(bytes(row))
            before = row

    def at(self, x, y):
        i = x * self.channels
        return tuple(self.rows[y][i:i + 3])


class Play:
    """One play as it ran: `name`, `spec` (the family's plays/<name>.json), `probe` (probe.json), `log` (the player's
    log), `probe_log` (probe.log), `files` ({name: bytes} of what the play wrote), `exit_code`, `seconds` (real)."""

    def __init__(self, name, spec, played, earlier):
        self.name, self.spec, self._earlier = name, spec, earlier
        self.probe, self.log, self.files = played.probe, played.log, played.files
        self.exit_code, self.seconds, self.output = played.exit_code, played.seconds, played.output
        self.probe_log = played.files.get("probe.log", b"").decode("utf-8", errors="replace")
        self.every = float(spec.get("every") or probes.EVERY)

    @property
    def errors(self):
        """probe.json's query_errors."""
        return list((self.probe or {}).get("query_errors") or [])

    def samples(self, qid):
        """Every sample of the query `qid`."""
        return list(((self.probe or {}).get("measures") or {}).get(qid) or [])

    def sample(self, qid, t):
        """The sample of `qid` at play time `t` (the nearest, within half the sampling interval), or None."""
        found = min(self.samples(qid), key=lambda s: abs(s["t"] - t), default=None)
        return found if found is not None and abs(found["t"] - t) <= self.every / 2 + 1e-6 else None

    def value(self, qid, t):
        """The `value` of a value sample at `t`, or None."""
        return (self.sample(qid, t) or {}).get("value")

    def rows(self, qid, t):
        """The rows of a selection sample at `t` ([] when it has none)."""
        return list((self.sample(qid, t) or {}).get("rows") or [])

    def row(self, qid, t, name):
        """The first row named `name` of the sample at `t`, or None."""
        return next((r for r in self.rows(qid, t) if r.get("name") == name), None)

    def series(self, qid, field, name=None):
        """[(t, value)] of `field` over the play: of each sample's value, or of its row named `name`."""
        out = []
        for s in self.samples(qid):
            if name is None:
                found = s.get("value")
            else:
                found = next((r for r in s.get("rows") or [] if r.get("name") == name), None)
            out.append((s["t"], (found or {}).get(field)))
        return out

    def track(self, t):
        """The track row [t, x, y, z] nearest play time `t` ([t] without a player)."""
        return min((self.probe or {}).get("track") or [], key=lambda r: abs(r[0] - t), default=None)

    def camera(self, t):
        """The camera row [t, x, y, z, pitch, yaw, fov] nearest play time `t`."""
        return min((self.probe or {}).get("camera") or [], key=lambda r: abs(r[0] - t), default=None)

    def image(self, file):
        """A screenshot of the play (shot_00.png, ...) as an Image."""
        return Image(self.files[file])

    def earlier(self, name):
        """An earlier play of the same family (plays run in the order PLAYS lists them)."""
        return self._earlier[name]


# -- families ---------------------------------------------------------------------------------------------------------


class Family:
    def __init__(self, folder):
        self.folder, self.name = folder, folder.name
        spec = importlib.util.spec_from_file_location("probe_tests_" + self.name, folder / "tests.py")
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)
        self.setup = list(getattr(self.module, "SETUP", []))
        self.scenes = list(getattr(self.module, "SCENES", []))
        self.plays = dict(getattr(self.module, "PLAYS", {}))
        self.assets = getattr(self.module, "ASSETS", None)


def families(only):
    found = [Family(f) for f in sorted(HERE.iterdir()) if (f / "tests.py").is_file()]
    unknown = set(only or []) - {f.name for f in found}
    if unknown:
        sys.exit(f"no family {', '.join(sorted(unknown))} (there are: {', '.join(f.name for f in found)})")
    return [f for f in found if not only or f.name in only]


def same_names(chosen):
    """A script name two families share: in one project a type name must be one type (`prop:Spinner.speed` reads the
    first Spinner it finds)."""
    seen, twice = {}, []
    for family in chosen:
        for part in ("Editor", "Scripts"):
            for script in sorted((family.folder / part).rglob("*.cs")) if (family.folder / part).is_dir() else []:
                if script.stem in seen and seen[script.stem] != family.name:
                    twice.append(f"{script.stem}.cs is in {seen[script.stem]} and {family.name}")
                seen.setdefault(script.stem, family.name)
    return twice


# -- the project ------------------------------------------------------------------------------------------------------


def _sync(source, target):
    """`target` holds exactly `source`'s files (Unity's .meta files beside them kept, so their ids stay)."""
    if not source.is_dir():
        shutil.rmtree(target, ignore_errors=True)
        return
    for file in source.rglob("*"):
        if file.is_file() and "__pycache__" not in file.parts:
            to = target / file.relative_to(source)
            to.parent.mkdir(parents=True, exist_ok=True)
            if not to.is_file() or to.read_bytes() != file.read_bytes():
                shutil.copyfile(file, to)
    for file in sorted(target.rglob("*"), reverse=True):
        twin = source / file.relative_to(target)
        if file.suffix == ".meta":
            twin = twin.with_suffix("")
        if not twin.exists():
            shutil.rmtree(file) if file.is_dir() else file.unlink()


def install(project, chosen, package):
    """The package and the chosen families' material in the project; every other family's taken out."""
    if package is not None:
        seeds.PROBE_SOURCE = package
    seeds.add_probe(project)
    tests = project / TESTS
    tests.mkdir(parents=True, exist_ok=True)
    names = {f.name for f in chosen}
    for there in tests.iterdir():
        if there.is_dir() and there.name not in names and there.name != "Editor":
            shutil.rmtree(there)
            Path(str(there) + ".meta").unlink(missing_ok=True)
    (tests / "Editor").mkdir(exist_ok=True)
    shutil.copyfile(HERE / "Setup.cs", tests / "Editor" / "Setup.cs")
    for family in chosen:
        for part in PARTS:
            _sync(family.folder / part, tests / family.name / part)
        shutil.rmtree(tests / family.name / MADE, ignore_errors=True)  # what SETUP makes is made anew


def setup(project, chosen, timeout=1800):
    """Every family's SETUP methods in one start of the editor (with graphics: a scene may bake its lighting)."""
    methods = [m for f in chosen for m in f.setup]
    if not methods:
        return None
    log = project.logs() / "probe_tests_setup.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    argv = [project.machine.editor, "-batchmode", "-quit", "-projectPath", project.folder, "-logFile", log,
            "-executeMethod", SETUP_METHOD, "-probeTestsSetup", ",".join(methods)]
    found = project.machine.job("probe-tests setup", argv, project.folder, timeout)
    text = log.read_text(encoding="utf-8", errors="replace") if log.is_file() else ""
    missing = [s for f in chosen for s in f.scenes if not (project.folder / s).is_file()]
    if found.exit_code == 0 and not missing:
        return None
    said = [line.strip() for line in text.splitlines() if "error CS" in line or "ProbeTests:" in line][:30]
    return (f"the editor exited {found.exit_code}" + (f"; not made: {', '.join(missing)}" if missing else "")
            + "".join("\n    " + line for line in said) + f"\n    (log: {log})")


# -- running and checking ---------------------------------------------------------------------------------------------


def _differs(a, b, path="probe.json"):
    """Where two JSON values first differ, or None."""
    if type(a) is not type(b):
        return f"{path}: {a!r} and {b!r}"
    if isinstance(a, dict):
        for key in sorted(set(a) | set(b)):
            if key not in a or key not in b:
                return f"{path}.{key}: only in the {'first' if key in a else 'second'} play"
            found = _differs(a[key], b[key], f"{path}.{key}")
            if found:
                return found
        return None
    if isinstance(a, list):
        if len(a) != len(b):
            return f"{path}: {len(a)} and {len(b)} items"
        return next((d for d in (_differs(x, y, f"{path}[{i}]") for i, (x, y) in enumerate(zip(a, b))) if d), None)
    return None if a == b else f"{path}: {a!r} and {b!r}"


def _steady(probe, varies):
    """probe.json without the measures a play says vary with real time."""
    found = json.loads(json.dumps(probe))
    for qid in varies:
        (found.get("measures") or {}).pop(qid, None)
    return found


def _spec(family, name):
    spec = json.loads((family.folder / "plays" / f"{name}.json").read_text(encoding="utf-8"))
    queries = spec.get("queries")
    if isinstance(queries, dict):
        queries = queries.get("queries")
    return spec, probes.query_file(queries or [], spec.get("every"))


def _play(project, spec, queries, args, timeout):
    waits = sum(float(i.get("wait") or 0) for i in spec.get("inputs") or [] if isinstance(i, dict))
    return project.play(spec.get("seconds", 20), spec.get("shots", 0), timeout + int(waits) + int(spec.get("seconds", 20)),
                        scene=spec.get("scene"), inputs=spec.get("inputs"), queries=queries, args=args,
                        every=spec.get("every"), player=spec.get("player"))


def run_play(project, family, name, entry, earlier, once):
    """One play of a family, checked: (Checks, note, seconds)."""
    t = Checks(project.folder)
    spec, queries = _spec(family, name)
    args, timeout = list(entry.get("args") or []), entry.get("timeout", 240)
    started = time.monotonic()
    played = _play(project, spec, queries, args, timeout)
    play = Play(name, spec, played, earlier)
    kept = project.folder / KEPT / f"{family.name}.{name}"
    shutil.rmtree(kept, ignore_errors=True)
    kept.mkdir(parents=True)
    for file, data in played.files.items():
        (kept / file).write_bytes(data)
    (kept / "play.log").write_text(played.log, encoding="utf-8")
    t.eq("the player's exit code", played.exit_code, 0)
    if play.probe is None:
        t.ok("the play wrote probe.json", False, played.output[-300:] or "no output")
        return t, "", time.monotonic() - started
    t.eq("probe.json ended", play.probe.get("ended"), entry.get("ended", "time"))
    wanted = [re.compile(p) for p in entry.get("errors") or []]
    for error in play.errors:
        t.ok(f"query_errors: {error!r} is expected", any(p.search(error) for p in wanted))
    for pattern in wanted:
        t.ok(f"query_errors has one matching {pattern.pattern!r}", any(pattern.search(e) for e in play.errors), play.errors)
    t.ok("no exception of the probe's in the player log", not PROBE_STACK.search(play.log))
    earlier[name] = play
    try:
        entry["check"](t, play)
    except Exception as exc:  # a check that reads a row or a value that isn't there
        t.ok(f"the check ran ({type(exc).__name__}: {exc})", False)
    note = ""
    varies = entry.get("varies") or []
    if not once and varies is not True:
        again = _play(project, spec, queries, args, timeout)
        where = "no probe.json" if again.probe is None else _differs(_steady(play.probe, varies), _steady(again.probe, varies))
        t.ok("a second play gives the same probe.json", where is None, where)
        note = "same twice" if where is None else "differs twice"
    return t, note, time.monotonic() - started


def _saved(folder):
    """{file: sha256} of the project as saved: everything under Assets, Packages and ProjectSettings."""
    found = {}
    for part in ("Assets", "Packages", "ProjectSettings"):
        for file in (folder / part).rglob("*"):
            if file.is_file():
                found[file.relative_to(folder).as_posix()] = hashlib.sha256(file.read_bytes()).hexdigest()
    return found


def run_assets(project, family, timeout=1800):
    """A family's editor pass, checked. The pass reads the project as saved: no file of it may change."""
    t = Checks(project.folder)
    started = time.monotonic()
    measures = json.loads((family.folder / family.assets["measures"]).read_text(encoding="utf-8"))
    nonce = secrets.token_hex(8)
    before = _saved(project.folder)
    found = project.editor_assets({"nonce": nonce, "measures": measures}, timeout)
    results = probes.editor_results(project.read(probes.EDITOR_FILE), nonce)
    after = _saved(project.folder)
    changed = sorted(f for f in set(before) | set(after) if before.get(f) != after.get(f))
    t.eq("the editor's exit code", found.exit_code, 0)
    t.ok("the pass changed no file under Assets, Packages and ProjectSettings", not changed, changed[:10])
    if results is None:
        t.ok("the editor pass wrote its result", False, found.output[-300:])
        return t, "", time.monotonic() - started
    try:
        family.assets["check"](t, results)
    except Exception as exc:
        t.ok(f"the check ran ({type(exc).__name__}: {exc})", False)
    return t, "", time.monotonic() - started


def report(label, t, note, seconds, verbose):
    failed = t.failed
    print(f"{'FAIL' if failed else 'PASS'}  {label:<34} {len(t.lines):>4} checks"
          + (f", {len(failed)} failed" if failed else "") + (f"  {note}" if note else "") + f"  {seconds:.0f} s", flush=True)
    for passed, what, detail in t.lines:
        if verbose or not passed:
            print(f"      {'ok  ' if passed else 'FAIL'} {what}" + (f": {detail}" if detail else ""))
    return not failed


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("project")
    parser.add_argument("--only", nargs="+", metavar="FAMILY")
    parser.add_argument("--play", nargs="+", metavar="FAMILY.PLAY")
    parser.add_argument("--skip-build", action="store_true")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--package")
    parser.add_argument("--direct", action="store_true")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    folder = Path(args.project).resolve()
    if not (folder / seeds.VERSION_FILE).is_file():
        sys.exit(f"{folder} is no Unity project")
    chosen = families(args.only)
    twice = same_names(chosen)
    if twice:
        sys.exit("two families have a script of one name:\n  " + "\n  ".join(twice))
    package = Path(args.package).resolve() if args.package else None
    project = unity.Project(folder, unity.Machine.for_project(folder, direct=args.direct), "probe-tests")
    print(f"probe tests in {folder} (package: {package or seeds.PROBE_SOURCE})", flush=True)

    passed = True
    try:
        if not args.skip_build:
            install(folder, chosen, package)
            started = time.monotonic()
            why = setup(project, chosen)
            print(f"{'FAIL' if why else 'ok  '}  setup: {sum(len(f.setup) for f in chosen)} method(s)  "
                  f"{time.monotonic() - started:.0f} s" + (f"\n    {why}" if why else ""), flush=True)
            if why:
                return 1
            built = project.build(3600, [s for f in chosen for s in f.scenes])
            ok = built.exit_code == 0
            print(f"{'ok  ' if ok else 'FAIL'}  build: {len((built.report or {}).get('scenes') or [])} scene(s)  "
                  f"{built.seconds:.0f} s", flush=True)
            if not ok:
                errors = [line.strip() for line in built.output.splitlines() if "error CS" in line or "rror:" in line]
                print("    " + "\n    ".join(errors[:30] or [built.output[-600:]]))
                return 1
        wanted = set(args.play or [])
        for family in chosen:
            if family.assets and (not wanted or f"{family.name}.assets" in wanted):
                passed &= report(f"{family.name}.assets (editor pass)", *run_assets(project, family), args.verbose)
            earlier = {}
            for name, entry in family.plays.items():
                if wanted and f"{family.name}.{name}" not in wanted:
                    continue
                passed &= report(f"{family.name}.{name}", *run_play(project, family, name, entry, earlier, args.once),
                                 args.verbose)
    finally:
        seeds.forget_saves(folder)  # the plays' saved data, outside the project
    print("every play passed" if passed else "FAILED", flush=True)
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
