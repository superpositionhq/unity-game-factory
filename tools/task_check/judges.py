"""A `judge` check's screenshots, saved for a person or a local session to look at (docs/task-probes.md, 3.2).

Nothing here asks a model. The task check and the task try play each judge check's plays on their sides (check.Side,
the same plays the probes use) and save the screenshots the cloud's judge would be shown, so whoever runs the check
looks at them and answers the rubric:

- a judge with its own `plays` is shown each play's `shots` evenly spaced screenshots (taken at seconds x (i + 0.5) / N
  by the plugin; a play another judge asks more of is played with the most asked, and `shots` of them are picked
  evenly through), and every screenshot its `shot` inputs take by name, in the order taken;
- a judge with no plays is shown the shared idle play ("look", 20 s, 6 screenshots) and the drive (22 s, 8) on the
  task's play_scene;
- a judge is shown 20 screenshots of a side at most, unless it compares (`before`, `reference`): the cloud then shows
  every screenshot as a panel of the sides side by side (grade.side_by_side), with no limit.

ask.md also gives what the cloud's prompt says of each play beside its pictures (its `readings`: the player's position
track and the camera's measures, as judging.prompt words them), and for a judge that compares, the panels the cloud
shows it: BEFORE (the start), AFTER (the side being scored) and REFERENCE at the same moment, as a table of the saved
pictures. A developer's `route` isn't played here (a game has none until a developer writes one); ask.md says what the
cloud adds with it.

`save` writes them under <folder>/<check>/<side>/<play>_<nn>.png with <folder>/<check>/ask.md (the brief, the question,
the rubric, what each picture is) and pictures.json (each picture's sha256); with `blind`, a copy of the sides under
blind/A and blind/B whose mapping is blind/key.json, so the looker can answer before knowing which side is which.

The Lab's grader asks its judge model a required judge check on the task's own fix, which must pass it. The checker asks
no model, so the writer scores the blind copy instead, item by item from 0 to 1, into blind/answers.json:

    {"A": {"door_open": 1, "lit": 0.5}, "B": {"door_open": 0, "lit": 0}}

A later task check reads them (`kept`), keeps each side's scores while its pictures are the same (pictures.json), and
`decide` holds a required judge to them as the Lab holds the fix to its judge: the reference passes it (weighted score
at least PASS, no required item below REQUIRED); the start, beside it, fails every required item (passes it, for a
judge of what still works). Until both sides are scored the task isn't VALID."""

import hashlib
import json
import random
import re
import shutil
from pathlib import Path

from . import tasks

JUDGE_IMAGES = 20  # a judge check's screenshots of one side at most (the grader's own limit)
PLAY_SHOTS = 5  # a judge's screenshots of each of its own plays unless its `shots` says
SHARED = {"look": ("idle play, 20 s, no input", 20, 6), "drive": ("scripted drive, 22 s", 22, 8)}
ROUTE_SHOTS = 8  # a developer's route's screenshots in the cloud (unity/grade.py ROUTE_SHOTS)
EVEN_SHOT = re.compile(r"^shot_\d{2,3}\.png$")  # an evenly spaced screenshot; any other is one a `shot` input took
PICTURES = "pictures.json"  # each saved picture's sha256, by side: a side's scores stand while they are the same
PASS, REQUIRED = 0.6, 0.5  # the judge's pass mark: weighted score at least PASS, no required item below REQUIRED
PENDING = "shots saved for {sides}, answer needed"
ANSWERS = "answers.json"  # under blind/: the writer's scores
ANSWERED = "scored in blind/answers.json"
STILL_WORKS = "still_works"  # a judge of what still works passes on the start too


def judge(c):
    """A `judge` check with its defaults: `plays` (task plays with theirs), `shots`, `before`, `reference`, `route`."""
    out = dict(c)
    out["plays"] = [tasks.play(p) for p in c.get("plays") or []]
    out.setdefault("shots", PLAY_SHOTS)
    out.setdefault("before", False)
    out.setdefault("reference", False)
    out.setdefault("route", None)
    out["rubric"] = [{"key": i["key"], "criterion": i["criterion"], "required": bool(i.get("required", False)),
                      "weight": int(i.get("weight", 1))} for i in c.get("rubric") or []]
    return out


def judges(task):
    """The task's `judge` checks (not code or actions judges), in order, with their defaults and their milestone's name
    (`group`)."""
    return [{**judge(c), "group": group} for group, c in tasks.checks(task) if c["kind"] == "judge"]


def play_shots(task):
    """{task play name: the evenly spaced screenshots taken of it}: the most any judge check naming it asks, so one
    play serves each (and the probes that name it)."""
    found = {}
    for c in judges(task):
        for p in c["plays"]:
            found[p["name"]] = max(found.get(p["name"], 0), c["shots"])
    return found


def plays(check):
    """What a judge check is shown of a side, in order: [(play, label, shots)], `play` "look", "drive" or a task play,
    `shots` how many of its evenly spaced screenshots (None: every one taken)."""
    if check["plays"]:
        return [(p, f"task play {p['name']}, {p['seconds']} s", check["shots"]) for p in check["plays"]]
    return [(name, label, None) for name, (label, _, _) in SHARED.items()]


def spread(items, count):
    """`count` of `items`, evenly through them and in their order (all of them when there are no more)."""
    items = list(items)
    if count is None or len(items) <= count:
        return items
    return [items[min(len(items) - 1, int((i + 0.5) * len(items) / count))] for i in range(count)]


def even_times(seconds, count):
    """When the plugin takes a play's `count` evenly spaced screenshots: at seconds x (i + 0.5) / count."""
    return [round(seconds * (i + 0.5) / count, 2) for i in range(count)]


def taken(probe, files):
    """A play's screenshots by name, in the order taken, each once and only those it wrote: the probe's list, else the
    PNG files it left (sorted)."""
    names = (probe or {}).get("screenshots") if isinstance(probe, dict) else None
    if not isinstance(names, list):
        names = sorted(n for n in files if n.lower().endswith(".png"))
    return [n for n in dict.fromkeys(n for n in names if isinstance(n, str)) if n in files]


def chosen(names, shots):
    """The screenshots of one play a judge is shown: `shots` of the evenly spaced ones (shot_NN.png), evenly through
    them, and every named one, in the order taken."""
    even = [n for n in names if EVEN_SHOT.fullmatch(n)]
    keep = set(spread(even, shots)) | {n for n in names if n not in even}
    return [n for n in names if n in keep]


def compares(check):
    """Whether the cloud shows judge `check` its sides as panels: BEFORE and REFERENCE beside the developer's game."""
    return bool(check.get("before") or check.get("reference"))


def selection(check, played):
    """[(play name, label, [(file name in the play, saved name)])] of one side, 20 screenshots at most in all unless
    the judge compares (the cloud's panels have no limit). `played`: {play name: (probe dict or None, {file: bytes})}
    of the plays made (a missing play shows nothing)."""
    out, left = [], None if compares(check) else JUDGE_IMAGES
    for play, label, shots in plays(check):
        name = play if isinstance(play, str) else play["name"]
        probe, files = played.get(name, (None, {}))
        picked = chosen(taken(probe, files), shots)[:left]
        left = None if left is None else left - len(picked)
        out.append((name, label, [(n, f"{name}_{i + 1:02d}.png") for i, n in enumerate(picked)]))
    return out


def named(file):
    """A named screenshot's name (shot_<name>.png), or None for an evenly spaced one."""
    return None if EVEN_SHOT.fullmatch(file) else file[len("shot_"):-len(".png")] if file.startswith("shot_") else file


def blind_key(sides, rng=None):
    """{"A": side, "B": side} for two sides, in an order the looker can't guess."""
    order = list(sides)
    (rng or random.SystemRandom()).shuffle(order)
    return dict(zip("AB", order))


def blind_copy(base, sides, rng=None, key=None):
    """The blind copy of side folders under `base` (<base>/<side>/), for judges and `seen` probes alike: blind/A and
    blind/B, whose sides are in blind/key.json; `key` ({"A": side, "B": side}) keeps an earlier copy's letters, else
    they are drawn (blind_key). (key, notes)."""
    key, notes = key or blind_key(sides, rng), []
    # Only pictures both sides have go in: a side with fewer (a play cut short) would be told apart by its count.
    both = set.intersection(*({p.name for p in (base / side).iterdir()} for side in sides))
    for side in sides:
        only = sorted({p.name for p in (base / side).iterdir()} - both)
        if only:
            notes.append(f"{side}: {len(only)} picture(s) the other side lacks, left out of the blind copy "
                         f"({', '.join(only)})")
    for letter, side in key.items():
        (base / "blind" / letter).mkdir(parents=True)
        for name in sorted(both):
            shutil.copy2(base / side / name, base / "blind" / letter / name)
    (base / "blind" / "key.json").write_text(json.dumps(key, indent=2) + "\n", encoding="utf-8")
    return key, notes


def track_text(probe):
    """The player's position track as the cloud's judge prompt gives it (judging.prompt): about ten of the probe's
    track rows, as JSON cut at 1200 characters."""
    track = (probe or {}).get("track") or [] if isinstance(probe, dict) else []
    sampled = track[:: max(1, len(track) // 10)]
    return json.dumps(sampled)[:1200] if sampled else "none (no player pawn)"


def _median(values):
    ordered = sorted(values)
    return ordered[len(ordered) // 2] if ordered else None


def camera_text(probe):
    """The camera's measures as the cloud's judge prompt gives them (judging.camera_text, word for word), or None. Its
    formula is the Unreal grader's: it takes z as height and centimetres, so for a Unity game (y up, metres) its "m
    above the player" is the z difference over 100, and its pitch is Unity's (positive looks down)."""
    try:
        camera = [row for row in (probe or {}).get("camera") or [] if len(row) == 7]
        if not camera:
            return None
        pawn = {round(row[0], 2): row[1:] for row in (probe or {}).get("track") or [] if len(row) == 4}
        pitch, fov = _median([row[4] for row in camera]), _median([row[6] for row in camera])
        pairs = [(row[1:4], pawn[round(row[0], 2)]) for row in camera if round(row[0], 2) in pawn]
        if not pairs:
            return f"camera (median of {len(camera)} samples, no player pawn to measure from): pitch {pitch:.0f}°, " \
                   f"field of view {fov:.0f}°"
        above = _median([(c[2] - p[2]) / 100 for c, p in pairs])
        away = _median([((c[0] - p[0]) ** 2 + (c[1] - p[1]) ** 2) ** 0.5 / 100 for c, p in pairs])
        return (f"camera (median of {len(pairs)} samples): {above:.2f} m above the player, {away:.2f} m from it "
                f"horizontally, pitch {pitch:.1f}°, field of view {fov:.0f}°")
    except (ArithmeticError, TypeError, ValueError, AttributeError):
        return None


def readings(check, made):
    """[(play label, its readings line)] of one side's plays as the cloud's judge prompt gives them beside its pictures:
    the player's position track (seconds, x, y, z) and the camera's measures."""
    out = []
    for name, label, _ in selection(check, made):
        probe = made.get(name, (None, {}))[0]
        seen = camera_text(probe)
        out.append((label, f"player position track (seconds, x, y, z in cm): {track_text(probe)}"
                           + (f"; {seen}" if seen else "")))
    return out


def route_lines(check, saved):
    """What the cloud adds to judge `check` with its developer's `route`, which isn't played here."""
    if not check["route"]:
        return []
    said = (f"In the cloud the judge also plays the developer's route file `{check['route']}` ({ROUTE_SHOTS} "
            "screenshots, after the plays above) on the developer's game")
    if check["before"]:
        said += " and on the start (BEFORE), never on the reference"
    if compares(check):
        said += ", and shows them as panels too"
    else:
        counts = [sum(len(p) for _, _, p in rows) for rows in (saved or {}).values()]
        room = max(0, JUDGE_IMAGES - max(counts, default=0))
        said += (f": with the {max(counts, default=0)} pictures above, {min(ROUTE_SHOTS, room)} of its "
                 f"{ROUTE_SHOTS} fit in the {JUDGE_IMAGES} the judge is shown")
    return ["", said + ". A game has no route until a developer writes one, so it isn't played here."]


def panel_lines(check, saved, key):
    """For a judge that compares: the panels the cloud shows it, one table per side scored, BEFORE (the start), AFTER
    (that side, standing in for a developer's game) and REFERENCE (the reference) at each moment, as links to the
    saved pictures; [] when the start or the reference wasn't saved. As the cloud's panels, a play's moments run to the
    most any side has, and a side with fewer shows "no screenshot"."""
    if not compares(check) or not {"start", "reference"} <= set(saved or {}):
        return []
    cols = [c for c, on in (("BEFORE", check["before"]), ("AFTER", True), ("REFERENCE", check["reference"])) if on]
    lines = ["", "## The panels the cloud's judge is shown", "",
             f"The cloud shows this judge each moment as one panel, {', '.join(cols)} left to right, every side named "
             "above its picture. Score each side as the AFTER of its own panels."]
    files = {side: {label: [s for _, s in picked] for _, label, picked in rows} for side, rows in saved.items()}
    scored = [(letter, key[letter], f"blind/{letter}") for letter in sorted(key)] if key else \
        [(side, side, side) for side in ("reference", "start")]
    for title, side, after in scored:
        where = {"BEFORE": ("start", "start"), "AFTER": (side, after), "REFERENCE": ("reference", "reference")}
        lines += ["", f"### {title} as AFTER", "", "| play, moment | " + " | ".join(cols) + " |",
                  "| --- |" + " --- |" * len(cols)]
        for _, label, _ in saved[side]:
            count = max(len(files[where[c][0]].get(label, [])) for c in cols)
            for n in range(count):
                cells = []
                for c in cols:
                    own, folder = where[c]
                    shots = files[own].get(label, [])
                    if n >= len(shots):
                        cells.append("no screenshot")
                    elif key and c == "AFTER" and any(shots[n] not in files[o].get(label, []) for o in key.values()):
                        cells.append("not in the blind copy (the other side has no such picture)")
                    else:
                        cells.append(f"![]({folder}/{shots[n]})")
                lines.append(f"| {label}, {n + 1}/{count} | " + " | ".join(cells) + " |")
    return lines


def ask_text(task, check, sides, notes=(), blind=False, saved=None, said=None, key=None):
    """ask.md: the brief, the question, the rubric, the plays and their pictures, what the cloud's prompt says of each
    play (`said`: {side: readings()}), the panels a comparing judge is shown, how to answer."""
    rubric = "\n".join(f"| {i['key']} | {'yes' if i['required'] else 'no'} | {i['weight']} | "
                       f"{i['criterion'].replace('|', '/')} |" for i in check["rubric"])
    lines = [f"# Judge check {check['name']}", "",
             f"{'Required' if check.get('required', True) else 'Optional'} check, weight {check.get('weight', 1)}.",
             "", "## The brief", "", task.get("instruction", "").strip(), "", "## The question", "",
             check["question"].strip(), "", "## The rubric", "",
             f"Score each item from 0 (not at all) to 1 (fully) from what the pictures show; an item they can't show "
             f"scores 0. A side passes when its weighted score is at least {PASS} and no required item is below "
             f"{REQUIRED}.", "", "| key | required | weight | criterion |", "| --- | --- | --- | --- |", rubric, "",
             "## The pictures", ""]
    for play, label, shots in plays(check):
        name = play if isinstance(play, str) else play["name"]
        if isinstance(play, str):
            _, seconds, count = SHARED[play]
            what = f"every one of its {count} screenshots, at {', '.join(f'{t:g}' for t in even_times(seconds, count))} s"
        else:
            inputs = play["inputs"]
            names = [i["shot"] for i in inputs if "shot" in i]
            what = (f"{len(inputs)} scripted input(s)" if inputs else "no input") \
                + (f", scene {play['scene']}" if play.get("scene") else "") \
                + (f", args {' '.join(play['args'])}" if play.get("args") else "") \
                + f"; {shots} evenly spaced screenshots, about one every {play['seconds'] / shots:.2g} s" \
                + (f", and the named ones: {', '.join(names)}" if names else "")
        lines.append(f"- `{name}_NN.png`: {label}: {what}.")
    lines += ["", "Each side's folder holds the pictures in time order, play by play."]
    if blind:  # a side's picture count or its notes would tell a blind scorer which side is which
        lines.append("Which pictures each side has, and any side's notes, are in `sides.md`: open it with the key.")
    else:
        lines += side_lines(saved)
    if compares(check):
        shown = [x for x, on in (("the start as BEFORE", check["before"]), ("the reference as REFERENCE",
                                                                             check["reference"])) if on]
        lines += ["", f"In the cloud the judge is also shown {' and '.join(shown)}, beside the developer's game, the "
                      "same plays at the same moments, as panels (below)."]
    lines += route_lines(check, saved)
    if said:
        lines += ["", "## What the cloud's prompt says of each play", "",
                  "Beside the pictures the cloud's judge reads these lines for each play, from the probe's own "
                  "samples of it:"]
        order = [(letter, key[letter]) for letter in sorted(key)] if key else [(s, s) for s in said]
        named = [("BEFORE (the start)", "start")] if check["before"] else []
        named += [("REFERENCE (the reference)", "reference")] if check["reference"] else []
        for title, side in order + [(t, s) for t, s in named if key]:
            for label, text in said.get(side, []):
                lines.append(f"- {title}, {label}: {text}")
    lines += panel_lines(check, saved, key)
    lines += ["", "## How to answer", ""]
    if blind:
        lines += ["`blind/A/` and `blind/B/` hold the pictures both sides have, under the same names; which is which "
                  "is in `blind/key.json`. Score every rubric item for A and for B first, each as if it were the "
                  "developer's game, then open the key.", ""]
    if "reference" in sides:
        example = "{" + ", ".join(f'"{i["key"]}": 0' for i in check["rubric"]) + "}"
        start = ("the start passes it too (a judge of what still works)" if check.get("group") == STILL_WORKS else
                 "the start fails every required rubric item (below " + f"{REQUIRED})") if "start" in sides else None
        lines += [f"Write each side's scores, 0 to 1 per item, into `blind/{ANSWERS}`"
                  + (" before opening the key" if blind else "") + ":", "", "```json",
                  "{" + ", ".join(f'"{letter}": {example}' for letter in "AB"[:len(sides)]) + "}", "```", "",
                  "Then check the task again: it reads the scores and holds the check to them. The task is VALID on "
                  "this check only when the reference passes it (weighted score at least "
                  f"{PASS}, no required item below {REQUIRED})" + (f" and {start}" if start else "") + ". Scores "
                  "stand while a side's pictures stay the same (`pictures.json`); pictures that changed need new ones. "
                  "Write the scores of both sides in the task's notes too."]
    elif "agent" in sides:
        lines += ["Score the agent's game the same way, before calling the task too easy or held: the try's own "
                  "number leaves judges out."]
    if notes and not blind:
        lines += ["", "## Notes", ""] + [f"- {n}" for n in notes]
    return "\n".join(lines).rstrip() + "\n"


def _json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8-sig")), None
    except FileNotFoundError:
        return None, None
    except (OSError, ValueError) as exc:
        return None, f"{Path(path).name} can't be read ({type(exc).__name__}: {str(exc)[:120]})"


def score_problem(check, scores):
    """Why one side's scores aren't {item key: a number from 0 to 1} for every item of the rubric, or None."""
    keys = [i["key"] for i in check["rubric"]]
    if not isinstance(scores, dict) or sorted(scores) != sorted(keys):
        return f"a side's scores are {{item: 0 to 1}} for the items {', '.join(keys)}"
    if not all(isinstance(v, int | float) and not isinstance(v, bool) and 0 <= v <= 1 for v in scores.values()):
        return "a score is a number from 0 to 1"
    return None


def kept(folder, task):
    """What an earlier task check's judge-shots folder holds, read before the folder is made again: {check: {"key":
    {letter: side}, "sides": {side: {"scores": its scores or None, "pictures": {name: sha256}}}, "problem": why the
    scores can't be read, or None, "raw": that file's bytes, kept as written}}."""
    out, folder = {}, Path(folder)
    if not folder.is_dir():
        return out
    rubric = {c["name"]: c for c in judges(task)}
    for base in sorted(p for p in folder.iterdir() if p.is_dir() and p.name in rubric):
        key, _ = _json(base / "blind" / "key.json")
        if not (isinstance(key, dict) and key and set(key) <= {"A", "B"}):
            continue
        answers, problem = _json(base / "blind" / ANSWERS)
        if answers is not None and not isinstance(answers, dict):
            answers, problem = None, 'it is {"A": {item: score}, "B": ...}'
        for letter in sorted(answers or {}):
            wrong = score_problem(rubric[base.name], answers[letter]) if letter in key else None
            problem = problem or (f"{letter}: {wrong}" if wrong else None)
        if problem:
            answers = None
        try:
            raw = (base / "blind" / ANSWERS).read_bytes() if problem else None
        except OSError:
            raw = None
        made, _ = _json(base / PICTURES)
        out[base.name] = {"key": key, "problem": problem, "raw": raw,
                          "sides": {side: {"scores": (answers or {}).get(letter),
                                           "pictures": (made or {}).get(side) if isinstance(made, dict) else None}
                                    for letter, side in key.items()}}
    return out


def weighted(check, scores):
    """A side's weighted score over the rubric, each score held to 0..1, in the rubric's order: the Lab's judging.score
    to the last bit, so a score at the pass mark falls on the same side of it there and here."""
    total = sum(i["weight"] for i in check["rubric"])
    return sum(i["weight"] * max(0.0, min(1.0, float(scores[i["key"]]))) for i in check["rubric"]) / total \
        if total else 0.0


def passes(check, scores):
    """Whether scores pass a judge, as its model's sample would (the Lab's judging.sampled): weighted score at least
    PASS exactly, with no tolerance, and no required item below REQUIRED."""
    return weighted(check, scores) >= PASS and all(float(scores[i["key"]]) >= REQUIRED for i in check["rubric"]
                                                    if i["required"])


def decide(check, record):
    """[reason] a required judge check `check` (judges() form) keeps its task from VALID by, from its record (save):
    unscored ("answer needed"), the reference failing it, or the start passing what it should fail (every required
    item below REQUIRED; a judge with no required item, below PASS), or failing a judge of what still works."""
    if not check.get("required", True):
        return []
    if record.get("status") != ANSWERED:
        return [line(check["name"], record)]
    why, scores = [], record.get("scores") or {}
    if "reference" in scores and not passes(check, scores["reference"]):
        low = [i["key"] for i in check["rubric"] if i["required"] and scores["reference"][i["key"]] < REQUIRED]
        why.append(f"reference fails judge {check['name']} on your scores (weighted "
                   f"{weighted(check, scores['reference']):.2f}" + (f"; below {REQUIRED}: {', '.join(low)}" if low
                                                                   else f", under {PASS}") + ")")
    if "start" in scores:
        start = scores["start"]
        if check.get("group") == STILL_WORKS:
            if not passes(check, start):
                why.append(f"start fails still-works judge {check['name']} on your scores (weighted "
                           f"{weighted(check, start):.2f})")
        else:
            items = [i["key"] for i in check["rubric"] if i["required"]]
            held = [k for k in items if start[k] >= REQUIRED] if items else \
                ([] if weighted(check, start) < PASS else ["its weighted score"])
            if held:
                why.append(f"start already passes judge {check['name']} on your scores ({', '.join(held)})")
    return why


def side_lines(saved):
    """One line per side: its pictures, by file name and what each is."""
    lines = []
    for side, rows in (saved or {}).items():
        files = [f"{s} ({'named ' + named(f) if named(f) else f})" for _, _, picked in rows for f, s in picked]
        lines.append(f"- `{side}/`: {len(files)} picture(s)" + (": " + ", ".join(files) if files else ""))
    return lines


def save(task, check, played, folder, blind=False, notes=(), rng=None, held=None):
    """Save judge check `check`'s screenshots of each side under <folder>/<check>/: `played` {side: {play name: (probe,
    files)}}. With `blind`, the blind copy (of one side or two): only the pictures both sides have, and sides.md
    beside it with each side's own pictures and notes, which the blind ask.md leaves out; the letters of `held` (kept()
    [check]) are kept, and each side's scores whose pictures are unchanged are carried over into blind/answers.json.
    Its record: {"sides": {side: [saved names]}, "blind": whether there is a blind copy (its key stays in its folder),
    "answered": [sides scored], "scores": {side: {item: score}}, "notes", "status"}."""
    base = Path(folder) / check["name"]
    if base.exists():
        shutil.rmtree(base)
    base.mkdir(parents=True)
    saved, notes, made_ = {}, list(notes), {}
    for side, made in played.items():
        rows = selection(check, made)
        saved[side], made_[side] = rows, {}
        (base / side).mkdir()
        for name, _, picked in rows:
            files = made.get(name, (None, {}))[1]
            for f, s in picked:
                (base / side / s).write_bytes(files[f])
                made_[side][s] = hashlib.sha256(files[f]).hexdigest()
            if name not in made:
                notes.append(f"{side}: {name} wasn't played")
            elif not picked:
                notes.append(f"{side}: {name} took no screenshots")
    (base / PICTURES).write_text(json.dumps(made_, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    key, answered, scores = None, [], {}
    if blind and saved:
        old = (held or {}).get("key")
        key, more = blind_copy(base, list(saved), rng, old if old and sorted(old.values()) == sorted(saved) else None)
        notes += more
        sides = (held or {}).get("sides") or {}
        answers = {}
        for letter, side in key.items():
            found = (sides.get(side) or {}).get("scores")
            if found is None:
                continue
            if (sides.get(side) or {}).get("pictures") == made_[side]:
                answers[letter], scores[side] = found, found
                answered.append(side)
            else:
                notes.append(f"{side}: its pictures changed since they were scored, so its scores were dropped")
        if answers:
            (base / "blind" / ANSWERS).write_text(json.dumps(answers, indent=2) + "\n", encoding="utf-8")
        elif (held or {}).get("raw") and key == old:  # an answer file that can't be read stays as written, to fix
            (base / "blind" / ANSWERS).write_bytes(held["raw"])
            notes.append(f"blind/{ANSWERS}: {held['problem']}")
    said = {side: readings(check, made) for side, made in played.items()}
    (base / "ask.md").write_text(ask_text(task, check, list(saved), notes, key is not None, saved, said, key),
                                 encoding="utf-8")
    if key is not None:  # what would unblind the scorer, kept beside the key
        (base / "sides.md").write_text("\n".join(["# Each side's pictures", ""] + side_lines(saved)
                                                 + (["", "## Notes", ""] + [f"- {n}" for n in notes] if notes else []))
                                       + "\n", encoding="utf-8")
    done = key is not None and sorted(answered) == sorted(saved)
    return {"sides": {s: [n for _, _, p in rows for _, n in p] for s, rows in saved.items()},
            "blind": key is not None, "answered": sorted(answered), "scores": scores, "notes": notes,
            "status": ANSWERED if done else PENDING.format(sides="/".join(saved) or "no side")}


def line(name, record):
    """The line a run prints and keeps for one judge check."""
    return f"judge {name}: {record['status']}"
