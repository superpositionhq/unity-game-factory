"""Probe checks: what the checker asks the TaskProbe package to measure during a play, how it reduces what came back to
one number, and the editor pass's request and results. Nothing here runs Unity: check.py plays the game and runs the
editor pass (unity.py) and hands the results here. Measures are dicts with their defaults filled in (tasks.measure).
Units are metres, Y is up.

- `plan(task)`: each play's probe queries (game-probe-queries/1), every runtime measure of the task's probes merged
  per play under stable ids (a query's id is the hash of what it selects, its fields the union of what the probes read).
- `measured(measure, probe, log)`: one number from a play's probe.json (`measures`, and the `track` and `camera` rows
  for the player's and the camera's own fields) or its log, following window/at/of/agg/match, and why there is none.
  The grading probe's grey, cast, warmth, tint, saturation and contrast come from colour.py.
- `editor_request(items, nonce)` / `editor_results(file, nonce, output)` / `reduce_asset(measure, result)`: the editor
  pass, one batchmode Unity run (TaskProbe.EditorTools.AssetPass) evaluating every `asset` measure of a side."""

import hashlib
import json
import math
import re

from . import colour as grading
from . import tasks

QUERIES_FORMAT = "game-probe-queries/1"
EVERY = 0.5  # seconds between samples
NEAR = 0.26  # a sample within this many seconds of a time is the sample at that time
EDITOR_FILE = "Logs/TaskProbe/probes_editor.json"  # the editor pass's result, beside its printed line
MARKER = "TASK_PROBES"


def _hash(data, n=10):
    return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()[:n]


def probes(task):
    """The task's probe checks, in order (tasks.check form)."""
    return [c for _, c in tasks.checks(task) if c["kind"] == "probe"]


# -- (a) the probe's queries --------------------------------------------------------------------------------------------


def needs(measure):
    """The probe queries a runtime measure needs, without ids: [{kind, ..., fields}] (none for the player's and the
    camera's own fields, read from the track and camera rows, nor for the log)."""
    probe, field = measure["probe"], measure.get("field")
    if probe == "player":
        to = measure.get("to")
        if field == "dist" and to is not None and "object" in to:
            return [{"kind": "objects", "select": to["object"], "fields": ["x", "y", "z"]}]
        return []
    if probe == "camera":
        return [{"kind": "camera", "fields": [field]}] if field in ("occluded", "player_on_screen") else []
    if probe in ("objects", "widgets", "components"):
        return [{"kind": probe, "select": measure["select"], "fields": [] if field == "count" else [field]}]
    if probe == "light":
        return [{"kind": "light", "point": measure["point"]}]
    if probe == "pieces":
        return [{"kind": "pieces", "select": measure["select"]}]
    if probe == "screen":
        return [{"kind": "screen", "rect": measure["rect"]}]
    if probe == "audio":
        return [{"kind": "audio", "select": measure["select"]}]
    if probe == "ui":
        fields = UI_SIGNED if field in UI_WHOLE else [] if field == "count" else [field]
        return [{"kind": "ui", "select": measure["select"], "fields": list(fields)}]
    if probe == "ground":
        place = {"xz": measure["xz"]} if measure["xz"] is not None else {"box": measure["box"], "grid": measure["grid"]}
        return [{"kind": "ground", **place, **({"select": measure["select"]} if measure["select"] is not None else {})}]
    if probe == "drawn":  # the probe renders only what the fields ask for
        place = {"near": measure["near"]} if measure["near"] is not None else {"line": measure["line"]}
        return [{"kind": "drawn", **place, "fields": [field]}]
    if probe == "grading":  # a post: field is asked for by name; the colour pipeline's settings always come
        return [{"kind": "grading", "fields": [field] if field.startswith("post:") else []}]
    if probe == "spawns":
        return [{"kind": "spawns", "component": measure["component"]}]
    return []  # log


def hears(queries):
    """Whether a play's queries (a list, or a query file) measure audio: the play spec's `sound`, which paces the play
    to real time (sound plays in real time); every other play runs as fast as the machine renders. In every play the
    probe's tap on the AudioListener measures the mix and then silences it."""
    found = queries.get("queries") if isinstance(queries, dict) else queries
    return any(isinstance(q, dict) and q.get("kind") == "audio" for q in found or [])


def query_id(query):
    """A query's stable id: the hash of what it measures (its fields left out, so probes reading other fields of one
    selection share it)."""
    return "q" + _hash({k: v for k, v in query.items() if k != "fields"})


def plan(task):
    """{play name: [query, ...]} for every play a runtime probe of `task` names ("look", "drive", a task play), each
    query with its id, sorted by id; a play whose probes need no query (the track, the log) maps to []."""
    out = {}
    for check in probes(task):
        if check["measure"]["probe"] not in tasks.RUNTIME:
            continue
        merged = out.setdefault(tasks.play_name(check), {})
        for query in needs(check["measure"]):
            qid = query_id(query)
            found = merged.setdefault(qid, {"id": qid, **{k: v for k, v in query.items() if k != "fields"}})
            if "fields" in query:
                found["fields"] = sorted(set(found.get("fields", [])) | set(query["fields"]))
    return {name: [merged[q] for q in sorted(merged)] for name, merged in out.items()}


def query_file(queries, every=None):
    """The probe's queries for one play (the play spec's `queries`; sampled every `every` s, default 0.5), or None when
    it has none."""
    return {"format": QUERIES_FORMAT, "every": every or EVERY, "queries": queries} if queries else None


def task_plays(task):
    """{name: task play} of the task-defined plays its probes name."""
    return {c["play"]["name"]: c["play"] for c in probes(task) if isinstance(c["play"], dict)}


# -- (b) reducing samples to one number ---------------------------------------------------------------------------------


def number(value, match=None):
    """A measured value as a number: booleans 0/1, numbers as they are, a string 1/0 by `match` (None without one)."""
    if value is None:
        return None
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    if isinstance(value, int | float):
        return float(value) if math.isfinite(value) else None
    if isinstance(value, str):
        return None if match is None else (1.0 if re.search(match, value) else 0.0)
    return None


def combine(values, of):
    """One sample's rows (objects, widgets) combined by `of`; None values left out."""
    found = [v for v in values if v is not None]
    if of == "count":
        return float(sum(1 for v in found if v != 0))
    if of == "any":
        return 1.0 if any(v != 0 for v in found) else 0.0
    if of == "all":
        return 1.0 if found and all(v != 0 for v in found) else 0.0
    if of == "sum":
        return float(sum(found))
    if not found:
        return None
    if of == "min":
        return min(found)
    if of == "max":
        return max(found)
    if of == "mean":
        return sum(found) / len(found)
    if of == "first":
        return found[0]
    raise ValueError(f"no `of` {of}")


ROWS = object()  # every_match: the rows alone read the measure
UI_SIGNED = ("h", "text", "w", "x", "y")  # what a ui signature is made of, besides each row's kind
UI_GRID = 0.002  # a ui signature's geometry, rounded to this fraction of the viewport
UI_WHOLE = ("signature", "number", "clock")  # ui fields read over everything a select picks in a sample (`of` ignored)
UI_LINE = 0.01  # ui text rows whose centres are this close in height read as one line (reading order)
NUMBER = re.compile(r"(?<![\d.])(-?)(\d{1,3}(?:,\d{3})+(?!\d)|\d+)(?:\.(\d+))?")
CLOCK = re.compile(r"(?<!\d)(\d{1,3}):([0-5]\d)(?::([0-5]\d))?(?:[.,](\d{1,3}))?(?!\d)")


def ui_text(rows):
    """What a ui select's text elements show in one sample, in reading order (top to bottom by their centres, a line
    within UI_LINE of the viewport's height; left to right), joined with spaces; "" when none shows text."""
    def at(r, key):
        v = r.get(key)
        return float(v) if _count(v) else 0.0

    texts = [r for r in rows if r.get("kind") == "text" and isinstance(r.get("text"), str)]
    texts.sort(key=lambda r: (round((at(r, "y") + at(r, "h") / 2) / UI_LINE), at(r, "x")))
    return " ".join(r["text"] for r in texts)


def ui_number(text):
    """The first number in `text`: digits with a decimal point and comma thousands (1,234 is 1234), negative when a
    minus sign stands before it after no letter or digit (a dash between two numbers is not a sign); None if none."""
    found = NUMBER.search(text)
    if found is None:
        return None
    sign, whole, frac = found.groups()
    before = text[found.start() - 1] if found.start() > 0 else " "
    value = float(whole.replace(",", "") + (f".{frac}" if frac else ""))
    return -value if sign and not before.isalnum() else value


def ui_clock(text):
    """The first time `text` shows, in seconds: h:mm:ss or m:ss (a fraction after . or , added), else its first number
    as seconds; None if neither."""
    found = CLOCK.search(text)
    if found is None:
        return ui_number(text)
    a, b, c, frac = found.groups()
    seconds = int(a) * 3600 + int(b) * 60 + int(c) if c is not None else int(a) * 60 + int(b)
    return seconds + (float(f"0.{frac}") if frac else 0.0)


def _count(value):
    return isinstance(value, int | float) and not isinstance(value, bool) and math.isfinite(value)


def selected_count(sample, rows):
    """How many a selection's sample matched: the probe's `total` when more matched than its rows hold (it keeps at
    most 200 rows), else the rows."""
    total = sample.get("total")
    return float(total) if _count(total) and total > rows else float(rows)


def ui_signature(sample, rows):
    """One number for what a ui select shows in one sample: 0 when it picks nothing, else a hash (1 to 2^31 - 1) of its
    elements' kinds, texts and rectangles (rounded to UI_GRID) as a set, and how many matched. Two samples showing the
    same thing read the same, so `agg: changes` counts how often what the select shows changed, however it was drawn
    (a uGUI or UI Toolkit text, a readout read off the frame, a box or an image); its value is otherwise meaningless."""
    total = selected_count(sample, len(rows))
    if not total:
        return 0.0

    def cell(v):
        return round(v / UI_GRID) if _count(v) else None

    items = sorted(json.dumps([r.get("kind") if isinstance(r.get("kind"), str) else "",
                               r.get("text") if isinstance(r.get("text"), str) else "",
                               *(cell(r.get(k)) for k in ("x", "y", "w", "h"))]) for r in rows)
    return float(int(_hash([total, items], 8), 16) % (2 ** 31 - 1) + 1)


def every_match(sample, rows, field, of):
    """`of` over every match of a sample whose matches outnumber its rows, from the probe's summary of their values
    of `field` (`full`: n with a number, nonzero, sum, min, max); ROWS when the rows are the whole selection, for
    `first` (the first row is the first match), or without a summary."""
    full = sample.get("full") if isinstance(sample.get("full"), dict) else {}
    found = full.get(field)
    if not (_count(sample.get("total")) and sample["total"] > rows) or of == "first" or not isinstance(found, dict):
        return ROWS
    n, nonzero, total = found.get("n"), found.get("nonzero"), found.get("sum")
    if not (_count(n) and _count(nonzero) and _count(total)):
        return ROWS
    if of == "count":
        return float(nonzero)
    if of == "any":
        return 1.0 if nonzero > 0 else 0.0
    if of == "all":
        return 1.0 if n > 0 and nonzero == n else 0.0
    if of == "sum":
        return float(total)
    if n == 0:
        return None
    if of == "mean":
        return total / n
    value = found.get(of)  # min, max
    return float(value) if _count(value) else None


def aggregate(values, agg):
    """The picked samples' values reduced by `agg`; None when no sample has a value."""
    found = [v for v in values if v is not None]
    if not found:
        return None
    if agg == "min":
        return min(found)
    if agg == "max":
        return max(found)
    if agg == "mean":
        return sum(found) / len(found)
    if agg == "first":
        return found[0]
    if agg == "last":
        return found[-1]
    if agg == "delta":
        return found[-1] - found[0]
    if agg == "any":
        return 1.0 if any(v != 0 for v in found) else 0.0
    if agg == "all":
        return 1.0 if all(v != 0 for v in found) else 0.0
    if agg == "count":
        return float(sum(1 for v in found if v != 0))
    if agg == "sum":
        return float(sum(found))
    if agg == "range":
        return max(found) - min(found)
    if agg == "std":
        mean = sum(found) / len(found)
        return math.sqrt(sum((v - mean) ** 2 for v in found) / len(found))
    if agg == "changes":
        return float(sum(1 for a, b in zip(found, found[1:]) if not math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-9)))
    if agg == "rises":
        return float(sum(1 for a, b in zip(found, found[1:]) if b > a + 1e-9))
    if agg == "falls":
        return float(sum(1 for a, b in zip(found, found[1:]) if b < a - 1e-9))
    raise ValueError(f"no agg {agg}")


def normal(degrees):
    """An angle in (-180, 180]."""
    out = math.fmod(degrees, 360.0)
    out = out - 360.0 if out > 180.0 else out
    return out + 360.0 if out <= -180.0 else out


def angled(measure, value):
    """An angle field's value normalised; with `to_angle`, its shortest absolute distance to that angle (0-180); with
    `to_axis`, its shortest distance to that axis (0-90: a direction and its opposite are one axis). Other fields as
    they are."""
    to_angle, to_axis = measure.get("to_angle"), measure.get("to_axis")
    turn = to_angle if to_angle is not None else to_axis
    if value is None or not tasks.is_angle(measure["field"], turn):
        return value
    if to_axis is not None:
        apart = abs(normal(value - to_axis))
        return min(apart, 180.0 - apart)
    return abs(normal(value - to_angle)) if to_angle is not None else normal(value)


def pick(series, measure):
    """The samples [(t, value)] (in time order) that `window` or `at` picks; all of them by default."""
    series = sorted(series, key=lambda s: s[0])
    if measure.get("window") is not None:
        t0, t1 = measure["window"]
        return [s for s in series if t0 - 1e-6 <= s[0] <= t1 + 1e-6]
    at = measure.get("at")
    if at == "end":
        return series[-1:]
    if at is not None:
        picked = []
        for t in at:
            found = _nearest(series, t)
            if found is not None:
                picked.append(found)
        return picked
    return series


def _nearest(rows, t, key=lambda r: r[0]):
    best = min(rows, key=lambda r: abs(key(r) - t), default=None)
    return best if best is not None and abs(key(best) - t) <= NEAR else None


def _rows(probe, name, *widths):
    return [[float(v) for v in row] for row in (probe or {}).get(name) or []
            if isinstance(row, list) and len(row) in widths and all(isinstance(v, int | float) for v in row)]


def _samples(probe, qid):
    found = ((probe or {}).get("measures") or {}).get(qid) or []
    return sorted((s for s in found if isinstance(s, dict) and isinstance(s.get("t"), int | float)),
                  key=lambda s: s["t"])


def _distance(a, b):
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b, strict=True)))


def _forward(pitch, yaw):
    """The way a camera of `pitch` (positive looks down) and `yaw` (about Y) looks, Unity's axes (Y up, Z forward)."""
    p, y = math.radians(pitch), math.radians(yaw)
    return [math.cos(p) * math.sin(y), -math.sin(p), math.cos(p) * math.cos(y)]


def point_at(point, t, probe):
    """Where `point` (tasks.point form) is at play time `t` (m), or None when the play didn't measure it then."""
    if "xyz" in point:
        return list(point["xyz"])
    if "player" in point:
        row = _nearest(_rows(probe, "track", 4), t)
        return None if row is None else [a + b for a, b in zip(row[1:4], point["offset"], strict=True)]
    if "camera" in point:
        row = _nearest(_rows(probe, "camera", 7), t)
        if row is None:
            return None
        ahead = _forward(row[4], row[5])
        return [c + point["forward"] * f for c, f in zip(row[1:4], ahead, strict=True)]
    query = {"kind": "objects", "select": point["object"]}
    sample = _nearest(_samples(probe, query_id(query)), t, key=lambda s: s["t"])
    rows = (sample or {}).get("rows") or []
    first = rows[0] if rows and isinstance(rows[0], dict) else None
    xyz = [number(first.get(k)) for k in ("x", "y", "z")] if first else None
    if xyz is None or None in xyz:
        return None
    return [a + b for a, b in zip(xyz, point["offset"], strict=True)]


def series(measure, probe):
    """[(t, value or None)] of a runtime measure, one per sample of its play."""
    probe_kind, field = measure["probe"], measure["field"]
    if probe_kind == "player":  # a sample that found no player is a track row [t]: no value there
        out, first, last = [], None, None
        for row in _rows(probe, "track", 1, 4):
            t, here = row[0], row[1:4]
            if not here:
                value = None
            elif field in ("x", "y", "z"):
                value = here["xyz".index(field)]
            elif field == "speed":
                dt = t - last[0] if last else 0.0
                value = _distance(here, last[1:4]) / dt if last and dt > 0 else None
            elif field == "moved":
                value = _distance(here, (first or row)[1:4])
            else:  # dist
                there = point_at(measure["to"], t, probe)
                value = None if there is None else _distance(here, there)
            if here:
                first, last = first or row, row
            out.append((t, value))
        return out
    if probe_kind == "camera" and field not in ("occluded", "player_on_screen"):
        # every sample has a track row; one with no camera row found no camera: no value there
        track, out = _rows(probe, "track", 4), []
        cameras = {row[0]: row for row in _rows(probe, "camera", 7)}
        for t in sorted({row[0] for row in _rows(probe, "track", 1, 4)} | set(cameras)):
            row = cameras.get(t)
            if row is None:
                out.append((t, None))
                continue
            if field in ("pitch", "yaw", "fov"):
                out.append((t, angled(measure, row[{"pitch": 4, "yaw": 5, "fov": 6}[field]])))
                continue
            player = _nearest(track, t)
            if player is None:
                out.append((t, None))
            elif field == "distance":
                out.append((t, _distance(row[1:4], player[1:4])))
            else:  # height: y is up
                out.append((t, row[2] - player[2]))
        return out
    (query,) = needs(measure)
    samples = _samples(probe, query_id(query))
    if probe_kind in ("objects", "widgets", "components", "ui"):
        out, turned = [], measure.get("to_angle") is not None or measure.get("to_axis") is not None
        for s in samples:
            if probe_kind == "ui" and not isinstance(s.get("rows"), list):  # no frame was drawn after the sample
                out.append((s["t"], None))
                continue
            rows = [r for r in s.get("rows") or [] if isinstance(r, dict)]
            if field == "signature":
                out.append((s["t"], ui_signature(s, rows)))
                continue
            if field in ("number", "clock"):
                out.append((s["t"], (ui_number if field == "number" else ui_clock)(ui_text(rows))))
                continue
            whole = every_match(s, len(rows), field, measure["of"]) if measure.get("match") is None and not turned else ROWS
            if field == "count":
                out.append((s["t"], selected_count(s, len(rows))))
            elif whole is not ROWS:
                out.append((s["t"], whole))
            else:
                out.append((s["t"], combine([angled(measure, number(r.get(field), measure.get("match")))
                                             for r in rows], measure["of"])))
        return out
    values = [(s["t"], s.get("value") if isinstance(s.get("value"), dict) else {}) for s in samples]
    if probe_kind in ("camera", "light", "pieces", "screen", "audio", "ground", "drawn"):
        return [(t, number(v.get(field))) for t, v in values]
    if probe_kind == "grading":
        if field.startswith("post:"):
            return [(t, number(v.get(field))) for t, v in values]
        # a sample the probe couldn't read has no value: no grade, never a neutral one
        return [(s["t"], grading.colour(s["value"])[field] if isinstance(s.get("value"), dict) else None)
                for s in samples]
    if probe_kind == "spawns":  # cumulative counts since the play started -> the count in each sample's interval
        out, before = [], 0.0
        for t, v in values:
            now = number(v.get(field))
            out.append((t, None if now is None else now - before))
            before = now if now is not None else before
        return out
    raise ValueError(f"no runtime probe {probe_kind}")


def default_agg(measure):
    return measure.get("agg") or ("sum" if measure["probe"] == "spawns" else "last")


def reduce(measure, probe, log=""):
    """A runtime measure of one play as one number, or None when the play measured nothing for it."""
    return measured(measure, probe, log)[0]


def ended(probe):
    """When a play's samples end (s): the probe's own seconds, else its last track or camera row."""
    found = [r[0] for r in _rows(probe, "track", 1, 4) + _rows(probe, "camera", 7)]
    seconds = (probe or {}).get("seconds")
    if isinstance(seconds, int | float) and not isinstance(seconds, bool):
        return float(seconds)
    return max(found, default=0.0)


def measured(measure, probe, log=""):
    """(a runtime measure of one play as one number, or None; why none). A play that ended early (quit, crashed,
    never reached the window) has no samples there: "no samples in the window (the play ended at X s)"."""
    if measure["probe"] == "log":
        return float(sum(1 for line in (log or "").splitlines() if re.search(measure["pattern"], line))), None
    if probe is None:
        return None, "no samples in the window (the play wrote no probe file)"
    picked = pick(series(measure, probe), measure)
    if not picked:
        return None, f"no samples in the window (the play ended at {fmt(ended(probe))} s)"
    value = aggregate([v for _, v in picked], default_agg(measure))
    if value is not None:
        return value, None
    errors = _own_errors(measure, probe)
    said = f"; the probe said: {errors[0][:300]}" if errors else ""
    return None, f"no value in the window (nothing it selects was measured){said}"


def _own_errors(measure, probe):
    """The play's `query_errors` lines about `measure`'s own query: those naming its kind and id ("components
    q1a2b3c4d5e: ..."), then those naming its kind alone ("components: no component type X": the probe writes a
    select's own errors so); another query's or the play's are left out. A measure read off a render (drawn; an
    object's or a component's lit and glow) also takes the lines of the renderer they share, which name no query
    ("rendering: the render pipeline isn't URP: drawn and glow as rendered have no value")."""
    query = next(iter(needs(measure)), None)
    if query is None:
        return []
    kind, qid = query["kind"], query_id(query)
    lines = [str(e) for e in (probe.get("query_errors") or []) if isinstance(e, str)]
    rendered = kind == "drawn" or measure.get("field") in ("lit", "glow")
    return [e for e in lines if e.startswith((f"{kind} {qid}:", f"{kind} {qid} ("))] + \
        [e for e in lines if e.startswith(f"{kind}: ")] + \
        [e for e in lines if rendered and e.startswith("rendering: ")]


# -- (c) the editor pass --------------------------------------------------------------------------------------------------


def _asset_json(measure):
    """An asset measure as the editor pass reads it: its set fields only."""
    return {k: v for k, v in measure.items() if v is not None}


def editor_id(measure):
    return "a" + _hash(_asset_json(measure))


def editor_items(task):
    """[(id, measure as JSON)] of the task's asset measures, each once, by a stable id."""
    seen = {}
    for check in probes(task):
        if check["measure"]["probe"] == "asset":
            seen.setdefault(editor_id(check["measure"]), _asset_json(check["measure"]))
    return sorted(seen.items())


def editor_request(items, nonce):
    """The editor pass's request (-taskProbeAssets) for `items` ([(id, measure JSON)]): {"nonce", "measures": {id:
    measure}}; unity.Project adds where the result goes (EDITOR_FILE). TaskProbe.EditorTools.AssetPass evaluates each
    measure on the project as saved and writes {"nonce", "measures": {id: {"value"} | {"rows": [{name, value}]} |
    {"error"}}} there and as one line, after MARKER, to its log. `nonce` (the checker's, unknown to the project) marks
    the real one."""
    return {"nonce": nonce, "measures": dict(items)}


def editor_results(file, nonce, output=""):
    """{id: result} from the editor pass: its file's contents (bytes) when it wrote one, else the last MARKER line of
    its output, whichever carries `nonce`; None when neither does."""
    candidates = []
    if file is not None:
        candidates.append(file.decode("utf-8", errors="replace") if isinstance(file, bytes) else file)
    for line in reversed((output or "").splitlines()):
        at = line.find(MARKER + " ")
        if at >= 0:
            candidates.append(line[at + len(MARKER) + 1:])
    for text in candidates:
        try:
            found = json.loads(text)
        except ValueError:
            continue
        if isinstance(found, dict) and found.get("nonce") == nonce and isinstance(found.get("measures"), dict):
            return found["measures"]
    return None


def reduce_asset(measure, result):
    """(number or None, why none) of an asset measure from its editor result."""
    if not isinstance(result, dict):
        return None, "the editor pass gave nothing for it"
    if "error" in result:
        return None, f"the editor couldn't measure it: {str(result['error'])[:200]}"
    if measure.get("asset") is not None:
        value = angled(measure, number(result.get("value"), measure.get("match")))
        return value, None if value is not None else "the property has no number"
    rows = [r for r in result.get("rows") or [] if isinstance(r, dict)]
    if measure["field"] == "count":
        return float(len(rows)), None
    value = combine([angled(measure, number(r.get("value"), measure.get("match"))) for r in rows], measure["of"])
    return value, None if value is not None else "no selected object has a value"


def fmt(value):
    return "nothing" if value is None else f"{value:.6g}"
