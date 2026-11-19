"""Settle a kept task-check run on the writer's answers to that run's own pictures, without playing anything
(docs/task-check.md, "Settling a run").

A task check saves each judge's pictures and each `seen` probe's crops with a blind copy, and says "answer needed"
until the writer has answered them; the next check reads the answers only while its own pictures are byte for byte
the same. A game whose frames depend on the wall clock or on unseeded randomness never draws the same picture twice,
so those answers would be dropped by every check. A settle takes the run that saved the pictures instead:

- it reads that run's result (<out>/<task>.json, or the run's own kept inside an earlier settle) and refuses unless it
  is a VALID or INVALID verdict (an ERROR is no verdict) of the same task file (`task_sha256`);
- for every judge check and `seen` probe the run saved, it binds the answers to exactly that run's pictures: every
  saved picture still has the sha256 its folder's pictures.json (crops.json) recorded, the blind copy holds exactly
  the pictures both sides share, each one the picture of the side the key names, the hashes of the list and the key
  match what the run recorded in its result (runs saved before that record are bound by the rest), no picture, list
  or key was written after the run wrote its result, and the answers file is no older than the pictures and the key;
- a required check whose answers are missing, unreadable or not bound is refused, and nothing is written;
- otherwise it applies the run's own rules to them, unchanged (check.answered: judges.decide, the no-op score, the
  seen gate; a seen probe's threshold and pass from the Lab's reduction of the answered lines, verdict.verdict), and
  writes the final result over <out>/<task>.json, with the run's own result and the file times it saw under
  `settled`.

Everything else in the result is the run's own: every other check's row, measure and threshold."""

import hashlib
import json
import os
import time
from pathlib import Path
from types import SimpleNamespace

from . import FORMAT, check, judges, seen, tasks, verdict

NOTHING = "has no judge check or seen probe to settle"


class Refused(Exception):
    """A run a settle can't decide on: why."""


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _json(path, what):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except FileNotFoundError:
        raise Refused(f"{what} is missing ({path})") from None
    except (OSError, ValueError) as exc:
        raise Refused(f"{what} can't be read ({type(exc).__name__}: {str(exc)[:120]})") from None


def _when(path):
    """(mtime in ns, atime in ns) of a file."""
    st = os.stat(path)
    return st.st_mtime_ns, st.st_atime_ns


def _stamp(ns):
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(ns / 1e9)) + f".{ns // 1_000_000 % 1000:03d}Z"


def run_of(out, name):
    """(the run's own result, its file's mtime in ns, the file's sha256) for task `name` under `out`: the result file,
    or, when an earlier settle wrote it, the run kept inside it."""
    path = Path(out) / f"{name}.json"
    try:
        raw = path.read_bytes()
    except FileNotFoundError:
        raise Refused(f"no kept run: {path} is missing (check the task first)") from None
    result = _json(path, f"the run's result {path.name}")
    if not isinstance(result, dict):
        raise Refused(f"{path.name} is no task check result")
    if isinstance(result.get("settled"), dict):
        found = result["settled"]
        if not isinstance(found.get("run"), dict) or not isinstance(found.get("run_mtime_ns"), int):
            raise Refused(f"{path.name} was settled, but the run it settled isn't kept in it")
        return found["run"], found["run_mtime_ns"], found.get("run_sha256")
    return result, _when(path)[0], _sha(raw)


def _files(folder):
    folder = Path(folder)
    return sorted(p.name for p in folder.iterdir() if p.is_file()) if folder.is_dir() else None


def bind(base, record, made_name, run_mtime, what, file_of=lambda name: name):
    """Check that the folder `base` of one judge or seen check is exactly what the run saved, and return (the blind
    key {letter: side}, the answers {letter: answer}, the file times seen). `record`: the run's record of the check;
    `made_name`: its list of hashes (pictures.json, crops.json), whose names are files by `file_of`."""
    base = Path(base)
    if not record.get("blind"):
        raise Refused(f"{what}: the run made no blind copy of it (a side had no picture), so it can't be answered")
    made = _json(base / made_name, f"{what}: {made_name}")
    key = _json(base / "blind" / "key.json", f"{what}: blind/key.json")
    sides = sorted(record.get("sides") or {})
    if not isinstance(made, dict) or sorted(made) != sides:
        raise Refused(f"{what}: {made_name} doesn't list the sides the run saved ({', '.join(sides)})")
    if not (isinstance(key, dict) and set(key) <= {"A", "B"} and sorted(key.values()) == sides
            and len(key) == len(sides)):
        raise Refused(f"{what}: blind/key.json doesn't name the run's sides ({', '.join(sides)})")
    said = record.get("bound")
    if said is not None:  # what the run recorded of the list and the key when it saved them
        for name, path in ((made_name, base / made_name), ("key.json", base / "blind" / "key.json")):
            if said.get(name) != _sha(path.read_bytes()):
                raise Refused(f"{what}: {name} isn't the one the run saved (its sha256 differs from the run's result)")
    newest, paths = 0, [base / made_name, base / "blind" / "key.json"]
    names = {}
    for side in sides:
        listed = {file_of(n): h for n, h in made[side].items()} if isinstance(made[side], dict) else None
        if listed is None:
            raise Refused(f"{what}: {made_name} has no hashes for {side}")
        made[side] = listed
        names[side] = set(listed)
        on_disk = _files(base / side)
        if on_disk is None or sorted(on_disk) != sorted(listed):
            raise Refused(f"{what}: {side}/ doesn't hold exactly the pictures {made_name} lists")
        for name in on_disk:
            if _sha((base / side / name).read_bytes()) != listed[name]:
                raise Refused(f"{what}: {side}/{name} changed since the run saved it")
            paths.append(base / side / name)
    both = set.intersection(*names.values())
    for letter, side in key.items():
        on_disk = _files(base / "blind" / letter)
        if on_disk is None or set(on_disk) != both:
            raise Refused(f"{what}: blind/{letter}/ doesn't hold exactly the pictures both sides have")
        for name in on_disk:
            if _sha((base / "blind" / letter / name).read_bytes()) != made[side][name]:
                raise Refused(f"{what}: blind/{letter}/{name} isn't the {side}'s picture the key names")
            paths.append(base / "blind" / letter / name)
    for path in paths:
        mtime = _when(path)[0]
        if mtime > run_mtime:
            raise Refused(f"{what}: {path.relative_to(base).as_posix()} was written after the run wrote its result")
        newest = max(newest, mtime)
    answers_path = base / "blind" / judges.ANSWERS
    answers = _json(answers_path, f"{what}: blind/{judges.ANSWERS} (the writer's answers)")
    if not isinstance(answers, dict):
        raise Refused(f"{what}: blind/{judges.ANSWERS} is {{\"A\": ..., \"B\": ...}}")
    missing = [letter for letter in sorted(key) if letter not in answers]
    if missing or set(answers) - set(key):
        raise Refused(f"{what}: blind/{judges.ANSWERS} answers " + (f"no {', '.join(missing)}" if missing else
                                                                     f"letters the key hasn't ({', '.join(sorted(set(answers) - set(key)))})"))
    written, _ = _when(answers_path)
    key_mtime, key_atime = _when(base / "blind" / "key.json")
    if written < newest:
        raise Refused(f"{what}: blind/{judges.ANSWERS} is older than the pictures it answers")
    times = {"answers_sha256": _sha(answers_path.read_bytes()), "answers_written": _stamp(written),
             "pictures_newest_written": _stamp(newest), "key_written": _stamp(key_mtime),
             "key_last_read": _stamp(key_atime)}
    return key, answers, times


def judge_record(task_check, record, base, run_mtime):
    """(the judge's record with the writer's scores of this run's pictures, the file times seen)."""
    what = f"judge {task_check['name']}"
    key, answers, times = bind(base, record, judges.PICTURES, run_mtime, what)
    for letter in sorted(key):
        wrong = judges.score_problem(task_check, answers[letter])
        if wrong:
            raise Refused(f"{what}: blind/{judges.ANSWERS}: {letter}: {wrong}")
    scores = {side: answers[letter] for letter, side in key.items()}
    return {**record, "answered": sorted(scores), "scores": scores, "status": judges.ANSWERED}, times


def seen_values(task_check, record, base, run_mtime):
    """(the seen check's record answered, {side: (value or None, why none)}, the file times seen)."""
    what = f"seen {task_check['name']}"
    key, answers, times = bind(base, record, seen.CROPS, run_mtime, what, lambda shot: f"{shot}.png")
    made = _json(Path(base) / seen.CROPS, f"{what}: {seen.CROPS}")
    values = {}
    for letter, side in key.items():
        try:
            seen.lines_of(answers[letter], task_check["measure"])
        except ValueError as exc:
            raise Refused(f"{what}: blind/{seen.ANSWERS}: {letter}: {exc}") from None
        found = {shot: ({"sha256": made[side].get(shot)}, None) for shot in seen.shots(task_check["measure"])}
        held = {"sides": {side: {"lines": answers[letter], "crops": {s: c["sha256"] for s, (c, _) in found.items()}}}}
        values[side] = seen.read(task_check, side, found, held)
    return {**record, "answered": sorted(values), "status": seen.ANSWERED}, values, times


class Kept:
    """A side as the run left it: its seen values from the writer's answers, and its task plays' probe files (for
    whether a play's inputs landed). Nothing is played."""

    def __init__(self, name, values, evidence):
        self.name, self.values, self.evidence = name, values, Path(evidence)
        self.answers = {}
        self.played = {}
        folder = self.evidence / name
        for play in sorted(folder.iterdir()) if folder.is_dir() else ():
            probe = play / "probe.json"
            if play.is_dir() and play.name.startswith("play_") and not play.name.endswith("_again"):
                try:
                    found = json.loads(probe.read_text(encoding="utf-8-sig")) if probe.is_file() else None
                except (OSError, ValueError):
                    found = None
                self.played[play.name] = SimpleNamespace(probe=found)

    def value(self, task_check):
        return self.values.get(task_check["name"], (None, "not answered"))

    @staticmethod
    def replayed(play):
        return ""


def _needs(task, name):
    """The checks that need check `name`, directly or through another."""
    found, more = set(), {name}
    while more:
        more = {c["name"] for _, c in tasks.checks(task) if set(c["needs"]) & more} - found
        found |= more
    return found


def regrade_seen(task, run, answered_values, evidence):
    """The run's check rows and probe values with each answered seen probe graded again on its answers, as
    check.Grade grades it; every other row as the run had it."""
    start_rows = [dict(r) for r in run.get("start_checks") or []]
    ref_rows = [dict(r) for r in run.get("reference_checks") or []]
    probes_out = {k: dict(v) for k, v in (run.get("probes") or {}).items()}
    if not answered_values:
        return start_rows, ref_rows, probes_out
    sides = {s: Kept(s, {n: v[s] for n, v in answered_values.items() if s in v}, evidence)
             for s in ("start", "reference")}
    has_ref = bool(run.get("reference"))
    thresholds = {}
    graders = {"start": check.Grade(task, "start", sides["start"], sides["reference"] if has_ref else None,
                                    thresholds),
               "reference": check.Grade(task, "reference", sides["start"], sides["reference"], thresholds)}
    for name in answered_values:
        task_check = next(c for _, c in tasks.checks(task) if c["name"] == name)
        for side, rows in (("reference", ref_rows), ("start", start_rows)):
            row = next((r for r in rows if r["name"] == name), None)
            if row is None or str(row["detail"]).startswith(("not run: needs", "not asked")):
                continue  # not graded on that side in the run (a check it needs failed), so not here either
            passed, detail = graders[side].check(task_check)
            note = str(row["detail"]).find("; note: ")
            detail = str(detail) + (str(row["detail"])[note:] if note >= 0 else "")
            if bool(passed) != bool(row["passed"]):
                waiting = sorted(n for n in _needs(task, name) if any(r["name"] == n for r in rows))
                if waiting:
                    raise Refused(f"{', '.join(waiting)} need(s) seen {name}, whose answer changes it on the {side}: "
                                  "the run never graded them that way, so check the task again")
            row.update(passed=bool(passed), detail=detail[:700])
        measured = {s: g.measured.get(name) for s, g in graders.items()}
        entry = probes_out.get(name)
        if entry is not None:
            ref, own = measured["reference"] or {}, measured["start"] or {}
            entry.update(start=own.get("value", ref.get("start")), reference=ref.get("value") if has_ref else None,
                         threshold=ref.get("threshold", own.get("threshold")),
                         start_passed=next((r["passed"] for r in start_rows if r["name"] == name), None),
                         reference_passed=next((r["passed"] for r in ref_rows if r["name"] == name), None)
                         if has_ref else None)
    return start_rows, ref_rows, probes_out


def settle(task, raw, out, clock=time.time):
    """Settle the kept run of `task` (its file's bytes `raw`) under `out` on the writer's answers to that run's own
    pictures: the final result, written to <out>/<task>.json. Raises Refused, writing nothing."""
    name = task.get("name", "?")
    found = tasks.problems(task)
    if found:
        raise Refused(f"the task doesn't validate: {found[0]}")
    if not judges.judges(task) and not seen.checks(task):
        raise Refused(NOTHING)
    run, run_mtime, run_sha = run_of(out, name)
    if run.get("format") != FORMAT or run.get("task") != name:
        raise Refused(f"{name}.json is no {FORMAT} result of this task")
    if run.get("task_sha256") != tasks.digest(raw):
        raise Refused("the task file isn't the one the run checked (its sha256 differs from the run's task_sha256)")
    if run.get("verdict") not in ("VALID", "INVALID"):
        raise Refused(f"the run's verdict is {run.get('verdict')}, no verdict to settle: check the task again")
    if any(str(r).startswith("the task doesn't validate") for r in run.get("reasons") or []):
        raise Refused("the run didn't check the task (it didn't validate)")
    evidence = Path(out) / name
    times = {}
    records = dict(run.get("judges") or {})
    for task_check in judges.judges(task):
        record = records.get(task_check["name"])
        if record is None:
            if task_check.get("required", True):
                raise Refused(f"judge {task_check['name']}: the run saved no pictures of it (--no-judge-shots?)")
            continue
        try:
            records[task_check["name"]], times[f"judge {task_check['name']}"] = judge_record(
                task_check, record, evidence / "judge-shots" / task_check["name"], run_mtime)
        except Refused:
            if task_check.get("required", True) or (evidence / "judge-shots" / task_check["name"] / "blind" /
                                                    judges.ANSWERS).exists():
                raise
    seen_records, values = dict(run.get("seen") or {}), {}
    for task_check in seen.checks(task):
        record = seen_records.get(task_check["name"])
        if record is None:
            raise Refused(f"seen {task_check['name']}: the run saved no crops of it")
        try:
            seen_records[task_check["name"]], values[task_check["name"]], times[f"seen {task_check['name']}"] = \
                seen_values(task_check, record, evidence / "seen-shots" / task_check["name"], run_mtime)
        except Refused:
            if task_check["required"] or (evidence / "seen-shots" / task_check["name"] / "blind" /
                                          seen.ANSWERS).exists():
                raise
    start_rows, ref_rows, probe_rows = regrade_seen(task, run, values, evidence)
    reference = {"checks": ref_rows} if run.get("reference") else None
    start = {"checks": start_rows}
    if verdict.failures(reference, start):
        raise Refused("the run has a row the checker couldn't run: check the task again")
    result = {k: v for k, v in run.items() if k != "settled"}
    result.update(judges=records, seen=seen_records, probes=probe_rows, start_checks=start_rows,
                  reference_checks=ref_rows)
    valid, why, notes = verdict.verdict(task, reference, start)
    notes += check.gap_notes(result)
    valid, why, notes = check.answered(task, result, start, valid, why, notes)
    result.update(verdict="VALID" if valid else "INVALID", reasons=why, notes=notes,
                  settled={"at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(clock())),
                           "run_verdict": run.get("verdict"), "run_reasons": run.get("reasons"),
                           "run_written": _stamp(run_mtime), "run_mtime_ns": run_mtime, "run_sha256": run_sha,
                           "answers": times, "run": run})
    (Path(out) / f"{name}.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result
