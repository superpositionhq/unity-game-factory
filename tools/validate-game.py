#!/usr/bin/env python3
"""Validate a Unity game against the final game format (docs/game-format-v1.json, prose docs/game-format.md).

    python tools/validate-game.py <games>/<slug>                 # the repo, its Dataset/ and Dataset.zip if present
    python tools/validate-game.py --dataset <Dataset.zip|folder>  # a dataset alone (what a consumer receives)
    options: --no-layout (skip tools/validate-dataset.ps1), --no-zip, --json <file>, --quiet

Checks the repo (required files, Unity 6000.3, Force Text and Visible Meta Files, .gitignore, Git LFS for binaries and
Unity YAML out of it, every asset with its .meta and no orphan .meta, README images, banned names,
assets.manifest.json in the one unified format with every listed file committed under Assets/, Packages/ or
RawAssets/, workflow.jsonl rows, the tasks on the orphan tasks branch, and a mobile game's project settings against its
Platform.json) and the dataset contents (manifest.json,
workflow.jsonl, git.log, ReplayScripts/Verification/report.json against docs/schemas/, cross-file rules, and in
Dataset.zip every asset file inside UnityProject/). The dataset layout (entries, video format, hashes, README sections)
is tools/validate-dataset.ps1, which this script runs too on Windows unless --no-layout.

Verdict: VALID (no errors), INVALID (errors). Exit code 0 / 2. Warnings never change the verdict.
Standard library only (Python 3.10+).
"""
import argparse, io, json, os, re, shutil, subprocess, sys, zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)


def load_json(path):
    """A JSON file's content, the file closed once read (json.load(open(...)) leaves it open for the garbage collector:
    a ResourceWarning in the tests of every tool that imports this file)."""
    with open(path, encoding='utf-8-sig') as f:
        return json.load(f)


SPEC = load_json(os.path.join(REPO, 'docs', 'game-format-v1.json'))
SCHEMAS = {n: load_json(os.path.join(REPO, 'docs', 'schemas', n + '.schema.json'))
           for n in ('workflow-row', 'dataset-manifest', 'replay-report', 'assets-manifest', 'game-task')}


def read_text(path):
    """A text file's content ('' when it isn't there): the Unity settings files, .gitignore, README.md."""
    if not os.path.isfile(path):
        return ''
    with open(path, encoding='utf-8-sig', errors='replace') as f:
        return f.read()


class Report:
    def __init__(self):
        self.items = []  # (severity, area, message)

    def error(self, area, msg): self.items.append(('error', area, msg))
    def warn(self, area, msg): self.items.append(('warning', area, msg))
    def note(self, area, msg): self.items.append(('note', area, msg))

    def count(self, sev): return sum(1 for s, _, _ in self.items if s == sev)


# ---- a small JSON Schema subset validator (type, required, properties, additionalProperties: false, minProperties,
# ---- enum, const, pattern, minLength, minimum, items, minItems, $ref "#/$defs/...") --------------------------------
TYPES = {'object': dict, 'array': list, 'string': str, 'boolean': bool, 'null': type(None)}


def _is(v, t):
    if t == 'integer': return isinstance(v, int) and not isinstance(v, bool)
    if t == 'number': return isinstance(v, (int, float)) and not isinstance(v, bool)
    return isinstance(v, TYPES[t])


def _same(a, b):
    """JSON equality: true is not 1 (to Python's == it is)."""
    return a == b and isinstance(a, bool) == isinstance(b, bool)


def _ecma(pattern):
    """A schema's pattern as JSON Schema (ECMA-262) reads it: its final `$` ends the string (Python's `$` also matches
    before a final newline), and with re.ASCII `\\d` is 0-9 only. The schemas' patterns have `$` at their end only."""
    return pattern[:-1] + r'\Z' if pattern.endswith('$') else pattern


def check_schema(value, schema, root=None, path='$'):
    """Yield 'path: problem' strings for value against schema."""
    root = root or schema
    if '$ref' in schema:
        ref = schema['$ref']
        node = root
        for part in ref.lstrip('#/').split('/'):
            node = node[part]
        yield from check_schema(value, node, root, path)
        return
    if 'type' in schema:
        ts = schema['type'] if isinstance(schema['type'], list) else [schema['type']]
        if not any(_is(value, t) for t in ts):
            yield f'{path}: expected {"/".join(ts)}, got {type(value).__name__}'
            return
    # combinators (the task schema uses them: optional fields, check kinds)
    if 'allOf' in schema:
        for sub in schema['allOf']:
            yield from check_schema(value, sub, root, path)
    for key in ('anyOf', 'oneOf'):
        if key in schema:
            tag = (schema.get('discriminator') or {}).get('propertyName')
            if tag and isinstance(value, dict):
                # the shape its tag names, and that shape's own problems: against every shape, a wrong kind read as
                # the nearest shape's ("packages": must be "build") and a wrong field as "matches none"
                shapes = schema['discriminator'].get('mapping') or {}
                if tag not in value:
                    yield f'{path}: missing "{tag}"'
                elif not isinstance(value[tag], str) or value[tag] not in shapes:
                    yield f'{path}.{tag}: {json.dumps(value[tag])[:80]} not one of {sorted(shapes)}'
                else:
                    yield from check_schema(value, {'$ref': shapes[value[tag]]}, root, path)
                continue
            fits = [list(check_schema(value, sub, root, path)) for sub in schema[key]]
            ok = sum(1 for f in fits if not f)
            if ok == 0:
                best = min(fits, key=len)
                yield f'{path}: matches none of the allowed shapes ({best[0] if best else "?"})'
            elif key == 'oneOf' and ok > 1 and 'discriminator' not in schema:
                yield f'{path}: matches more than one of the allowed shapes'
    if 'const' in schema and not _same(value, schema['const']):
        yield f'{path}: must be {json.dumps(schema["const"])}, got {json.dumps(value)[:80]}'
    if 'enum' in schema and not any(_same(value, e) for e in schema['enum']):
        yield f'{path}: {json.dumps(value)[:80]} not one of {schema["enum"]}'
    if isinstance(value, str):
        if 'minLength' in schema and len(value) < schema['minLength']:
            yield f'{path}: empty'
        if 'maxLength' in schema and len(value) > schema['maxLength']:
            yield f'{path}: longer than {schema["maxLength"]}'
        if 'pattern' in schema and not re.search(_ecma(schema['pattern']), value, re.ASCII):
            yield f'{path}: {value[:80]!r} does not match {schema["pattern"]}'
    if _is(value, 'number'):
        if 'minimum' in schema and value < schema['minimum']:
            yield f'{path}: {value} < {schema["minimum"]}'
        if 'maximum' in schema and value > schema['maximum']:
            yield f'{path}: {value} > {schema["maximum"]}'
        if 'exclusiveMinimum' in schema and value <= schema['exclusiveMinimum']:
            yield f'{path}: {value} <= {schema["exclusiveMinimum"]}'
        if 'exclusiveMaximum' in schema and value >= schema['exclusiveMaximum']:
            yield f'{path}: {value} >= {schema["exclusiveMaximum"]}'
    if isinstance(value, dict):
        if 'minProperties' in schema and len(value) < schema['minProperties']:
            yield f'{path}: needs at least {schema["minProperties"]} key(s)'
        for k in schema.get('required', []):
            if k not in value:
                yield f'{path}: missing "{k}"'
        props = schema.get('properties', {})
        for k, v in value.items():
            if k in props:
                yield from check_schema(v, props[k], root, f'{path}.{k}')
            elif schema.get('additionalProperties') is False:
                yield f'{path}: unexpected key "{k}"'
    if isinstance(value, list):
        if 'minItems' in schema and len(value) < schema['minItems']:
            yield f'{path}: needs at least {schema["minItems"]} item(s)'
        if 'maxItems' in schema and len(value) > schema['maxItems']:
            yield f'{path}: more than {schema["maxItems"]} item(s)'
        if 'items' in schema:
            for i, v in enumerate(value):
                yield from check_schema(v, schema['items'], root, f'{path}[{i}]')


def schema_errors(rep, area, value, name, limit=20):
    problems = list(check_schema(value, SCHEMAS[name]))
    for p in problems[:limit]:
        rep.error(area, p)
    if len(problems) > limit:
        rep.error(area, f'... and {len(problems) - limit} more schema problems')
    return not problems


# ---- shared content checks ---------------------------------------------------------------------------------------------
def check_workflow(rep, area, lines):
    """lines: iterable of text lines of a workflow.jsonl. Returns ids of user.direction rows."""
    seen, directions, prev_seq, bad_rows, n, empty_reason = set(), set(), None, 0, 0, 0
    problems = []
    grouped = {}  # schema problem (row-independent text) -> [count, first line]
    for i, line in enumerate(lines, 1):
        line = line.strip()
        if not line:
            continue
        n += 1
        try:
            row = json.loads(line)
        except ValueError as e:
            problems.append(f'line {i}: not JSON ({e})')
            continue
        errs = list(check_schema(row, SCHEMAS['workflow-row']))
        if errs:
            bad_rows += 1
            for e in errs:
                g = grouped.setdefault(e, [0, i])
                g[0] += 1
            continue
        if not row['reason'].strip():
            empty_reason += 1
        if row['id'] in seen:
            problems.append(f'line {i}: duplicate id {row["id"]}')
        seen.add(row['id'])
        if prev_seq is not None and row['seq'] <= prev_seq:
            problems.append(f'line {i}: seq {row["seq"]} not after {prev_seq}')
        prev_seq = row['seq']
        if row['op'] == 'user.direction':
            if row['actor'] != 'user' or row['reason_source'] != 'user_direction' or not str(row['params'].get('direction', '')).strip():
                problems.append(f'line {i}: user.direction row needs actor user, reason_source user_direction, params.direction')
            directions.add(row['id'])
        if 'direction' in row and row['direction'] not in directions:
            problems.append(f'line {i}: direction {row["direction"]} is not an earlier user.direction row')
    for e, (count, first) in sorted(grouped.items(), key=lambda kv: -kv[1][0])[:15]:
        rep.error(area, f'{count} row(s), first at line {first}: {e}')
    for p in problems[:25]:
        rep.error(area, p)
    if len(problems) > 25:
        rep.error(area, f'... {len(problems) - 25} more')
    if empty_reason:
        rep.warn(area, f'{empty_reason} row(s) with an empty reason')
    if n == 0:
        rep.error(area, 'no rows')
    else:
        rep.note(area, f'{n} rows, {bad_rows} not matching the row schema, {len(directions)} user.direction rows')
    return directions


def check_git_log(rep, area, stream):
    g = SPEC['dataset']['git_log']
    first = stream.readline().rstrip('\r\n')
    if first != g['first_line']:
        rep.error(area, f'first line must be "{g["first_line"]}", got {first[:40]!r}')
    shas, expect, problems = [], None, []
    commit_rx, author_rx, date_rx = re.compile(g['commit_line']), re.compile(g['author_pattern']), re.compile(g['date_pattern'])
    for i, line in enumerate(stream, 2):
        line = line.rstrip('\r\n')
        if expect is None:
            if line.startswith('commit ') and not line.startswith(' '):
                if not commit_rx.match(line):
                    problems.append(f'line {i}: bad commit line {line[:60]!r}')
                    continue
                shas.append(line[7:])
                expect = list(g['fields_in_order'])
            continue
        field = expect.pop(0)
        if not line.startswith(field + ':'):
            problems.append(f'line {i}: expected "{field}:" after commit {shas[-1][:8]}, got {line[:40]!r}')
            expect = None
            continue
        value = line[len(field) + 1:].strip()
        if field in ('Author', 'Committer') and not author_rx.match(value):
            problems.append(f'line {i}: {field} "{value[:40]}" is not anonymised (dev_NN)')
        if field in ('AuthorDate', 'CommitDate') and not date_rx.match(value):
            problems.append(f'line {i}: {field} "{value}" is not ISO 8601')
        if not expect:
            expect = None
    if len(set(shas)) != len(shas):
        problems.append('a commit appears twice')
    for p in problems[:20]:
        rep.error(area, p)
    if not shas:
        rep.error(area, 'no commits')
    else:
        rep.note(area, f'{len(shas)} commits')
    return shas[-1] if shas else None


def git_ls(repo):
    out = subprocess.run(['git', '-C', repo, '-c', 'core.quotepath=off', 'ls-files', '-z'], capture_output=True)
    return [p for p in out.stdout.decode('utf-8', 'replace').split('\0') if p]


def check_assets_manifest(rep, area, data, present):
    """data: parsed assets.manifest.json; present(path) -> True when the file (or, for a path ending in /, any file
    under the folder) is there."""
    if not isinstance(data, dict) or data.get('schema') != 'assets-manifest/v1':
        rep.error(area, 'not in the unified format (schema "assets-manifest/v1", docs/schemas/assets-manifest.schema.json)')
        return
    schema_ok = schema_errors(rep, area, data, 'assets-manifest')
    # the schema's if/then/else (the small validator above does not evaluate it): in-house assets (origin "studio")
    # carry a description instead of a url; every other asset needs an https url
    for i, a in enumerate(data.get('assets') if isinstance(data.get('assets'), list) else []):
        if not isinstance(a, dict):
            continue
        if a.get('origin') == 'studio':
            if not str(a.get('description', '')).strip():
                rep.error(area, f'$.assets[{i}] ({a.get("name")}): origin studio needs a "description"')
        elif not str(a.get('url', '')).startswith('https://'):
            rep.error(area, f'$.assets[{i}] ({a.get("name")}): needs an https "url" (or origin "studio" with a description, for in-house assets)')
    if not schema_ok:
        return
    missing, outside, n = [], [], 0
    for a in data['assets']:
        for f in a['files']:
            n += 1
            if not re.match(r'^(Assets|Packages|RawAssets)/', f):
                outside.append(f'{a["name"]}: {f}')
            if not present(f):
                missing.append(f'{a["name"]}: {f}')
    for m in outside[:10]:
        rep.error(area, f'asset path outside Assets/, Packages/ or RawAssets/: {m}')
    for m in missing[:15]:
        rep.error(area, f'listed asset file not present: {m}')
    if len(missing) > 15:
        rep.error(area, f'... {len(missing) - 15} more listed files not present')
    rep.note(area, f'{len(data["assets"])} assets, {n} listed paths, {len(missing)} missing')


# ---- dataset (folder or zip) -------------------------------------------------------------------------------------------
class DatasetView:
    def __init__(self, path):
        self.path = path
        self.zip = None
        if path.lower().endswith('.zip'):
            self.zip = zipfile.ZipFile(path)
            names = [n for n in self.zip.namelist() if not n.endswith('/')]
            tops = sorted({n.split('/')[0] for n in names})
            self.top = tops[0] if len(tops) == 1 else None
            self.names = {n[len(self.top) + 1:]: n for n in names} if self.top else {}
            self.sizes = {n[len(self.top) + 1:]: self.zip.getinfo(n).file_size for n in names} if self.top else {}
        else:
            self.top = os.path.basename(os.path.normpath(path))
            self.names, self.sizes = {}, {}
            for d, _, fs in os.walk(path):
                for f in fs:
                    full = os.path.join(d, f)
                    rel = os.path.relpath(full, path).replace('\\', '/')
                    self.names[rel] = full
                    self.sizes[rel] = os.path.getsize(full)

    def has(self, rel): return rel in self.names
    def has_dir(self, rel): return any(n.startswith(rel.rstrip('/') + '/') for n in self.names)

    def open_text(self, rel):
        if self.zip:
            return io.TextIOWrapper(self.zip.open(self.names[rel]), encoding='utf-8-sig', errors='replace')
        return open(self.names[rel], encoding='utf-8-sig', errors='replace')

    def json(self, rel):
        with self.open_text(rel) as f:
            return json.load(f)


def check_dataset(rep, path, area='dataset'):
    v = DatasetView(path)
    try:
        _check_dataset(rep, v, area)
    finally:
        if v.zip:
            v.zip.close()   # Windows keeps an open zip locked


def _check_dataset(rep, v, area):
    if v.zip and not v.top:
        rep.error(area, 'the zip must hold exactly one top folder (<game>/)')
        return
    if not v.has('manifest.json'):
        rep.error(area, 'no manifest.json')
        return
    try:
        m = v.json('manifest.json')
    except ValueError as e:
        rep.error(area, f'manifest.json is not JSON: {e}')
        return
    ok = schema_errors(rep, f'{area}: manifest.json', m, 'dataset-manifest')
    if not ok:
        return
    a = f'{area}: manifest.json'
    if v.zip and m['game'] != v.top:
        rep.error(a, f'game "{m["game"]}" differs from the zip top folder "{v.top}"')
    listed = {f['path']: f for f in m['files']}
    for p, f in listed.items():
        if p not in v.sizes:
            rep.error(a, f'files[] lists {p}, not in the dataset')
        elif v.sizes[p] != f['bytes']:
            rep.error(a, f'{p}: {v.sizes[p]} bytes, manifest says {f["bytes"]}')
    if m['totals']['files'] != len(m['files']) or m['totals']['bytes'] != sum(f['bytes'] for f in m['files']):
        rep.error(a, 'totals do not match files[]')
    for s in m['scenarios']:
        if s['file'] not in listed:
            rep.error(a, f'scenario file {s["file"]} not in files[]')
    if m['variant'] == 'full' and not isinstance(m.get('build'), dict):
        rep.error(a, 'variant full needs a build object')
    if m['variant'] == 'repo-dataset' and m.get('build') is not None:
        rep.error(a, 'variant repo-dataset has build null')
    check_dataset_platform(rep, area, v, m, listed)
    # workflow.jsonl
    directions = set()
    if v.has('workflow.jsonl'):
        with v.open_text('workflow.jsonl') as f:
            text = f.read()
        directions = check_workflow(rep, f'{area}: workflow.jsonl', io.StringIO(text))   # lines end at \n only
        for p in SPEC['repo']['banned_names']['patterns']:   # a banned name left in a row is an error here too
            n = len(re.findall(p, text))
            if n:
                rep.error(f'{area}: workflow.jsonl', f'banned name {p} x{n}')
    else:
        rep.error(area, 'no workflow.jsonl')
    # git.log
    last = None
    if v.has('git.log'):
        with v.open_text('git.log') as f:
            last = check_git_log(rep, f'{area}: git.log', f)
        if last and last != m['commit']:
            rep.error(f'{area}: git.log', f'last commit {last[:12]} differs from manifest commit {m["commit"][:12]}')
    else:
        rep.error(area, 'no git.log')
    # replay report
    rp = 'ReplayScripts/Verification/report.json'
    if v.has(rp):
        try:
            r = v.json(rp)
        except ValueError as e:
            rep.error(f'{area}: report.json', f'not JSON: {e}')
        else:
            if schema_errors(rep, f'{area}: report.json', r, 'replay-report'):
                if r['final_commit'] != m['commit']:
                    rep.error(f'{area}: report.json', f'final_commit {r["final_commit"][:12]} differs from manifest commit {m["commit"][:12]}')
                # the verdict is metadata (user rule: the replay is required but need not pass); manifest and report agree
                rv = m.get('replay_verification')
                if isinstance(rv, dict) and 'pass' in rv and bool(rv['pass']) != bool(r['verdict']['pass']):
                    rep.error(f'{area}: report.json', f'verdict pass {r["verdict"]["pass"]} differs from manifest replay_verification.pass {rv["pass"]}')
                if not r['verdict']['pass']:
                    rep.note(f'{area}: report.json', 'creation replay verification FAIL (metadata)')
    elif m['status'] == 'complete':
        rep.error(area, f'status complete but no {rp}')
    if m['status'] == 'complete':
        if m['pending']:
            rep.error(a, 'status complete with pending entries')
        if not isinstance(m.get('replay_verification'), dict) or not isinstance(m['replay_verification'].get('pass'), bool):
            rep.error(a, 'status complete needs replay_verification with pass true or false')
    else:
        rep.warn(a, f'status pending: {", ".join(m["pending"]) or "(nothing listed)"}')
    # replay_verification is null only while ReplayScripts/ is pending (listed in pending)
    if m.get('replay_verification') is None and not any(str(p).rstrip('/') == 'ReplayScripts' for p in m['pending']):
        rep.error(a, 'replay_verification is null but ReplayScripts/ is not listed as pending')
    # videos: at least one (user rule 2026-10-19: one recorded scenario is enough), unless Gameplay/ is listed as pending
    if not m['scenarios'] and not any(str(p).rstrip('/') == 'Gameplay' for p in m['pending']):
        rep.error(a, 'no scenario videos: a delivery has at least one, or lists Gameplay/ as pending')
    # a game without a gameplay video is rejected at upload (owner, 2026-11-10): the delivered zip never has Gameplay/ pending
    if m.get('variant') == 'full' and any(str(p).rstrip('/') == 'Gameplay' for p in m['pending']):
        rep.error(a, 'Gameplay/ is pending: a game is rejected without a gameplay video; record a scenario of the release '
                     'commit and package again')
    # Brief/, the person's directions, History/, Tasks/ (all part of the first Unity layout)
    b = m.get('brief')
    if not isinstance(b, dict):
        rep.error(a, 'the layout needs brief {"brief": "Brief/brief.md", "design": "Brief/design.md"}')
    for rel in ('Brief/brief.md', 'Brief/design.md'):
        if not v.has(rel):
            rep.error(area, f'no {rel}')
        elif v.sizes[rel] < 200:
            rep.error(area, f'{rel} is nearly empty ({v.sizes[rel]} bytes)')
    if not directions:
        rep.warn(f'{area}: workflow.jsonl', "no user.direction rows: the person's directions are recorded nowhere else")
    if m['variant'] == 'full':
        check_history(rep, area, v, m)
        check_sessions(rep, area, v, m)
        check_tasks(rep, area, v, m)
    else:
        if m.get('history') is not None or v.has_dir('History'):
            rep.error(area, 'a repo Dataset/ has no History/ and history null (the repo is its own history)')
        if v.has_dir('Tasks'):
            rep.error(area, 'a repo Dataset/ has no Tasks/ (tasks live on the game repo\'s tasks branch)')
    # full variant: every asset file listed by the project's assets.manifest.json is inside UnityProject/
    if m['variant'] == 'full':
        am = 'UnityProject/assets.manifest.json'
        if v.has(am):
            try:
                data = v.json(am)
            except ValueError as e:
                rep.error(f'{area}: {am}', f'not JSON: {e}')
            else:
                check_assets_manifest(rep, f'{area}: {am}', data,
                                      lambda f: v.has_dir('UnityProject/' + f) if f.endswith('/') else (v.has('UnityProject/' + f) or v.has_dir('UnityProject/' + f)))
        else:
            rep.error(area, f'no {am}')
    rep.note(area, f'{m["game"]} {m["variant"]} {m["status"]}: {len(m["files"])} files, {len(m["scenarios"])} scenario video(s)')


def check_dataset_platform(rep, area, v, m, listed):
    """A dataset's platform (docs/game-format.md, "Platform"): the manifest's `platform` (absent or kind desktop: a
    desktop game; kind mobile with its orientation: an Android phone game) says what UnityProject/Platform.json says
    (full variant); a mobile game's build names its APK with what the APK says of itself, at the SDK levels and
    package name of a mobile game, the file in Build/; a desktop game's names none. A mobile game delivered without
    its APK (full variant) is an error: the APK is part of a mobile game's delivery."""
    a = f'{area}: manifest.json'
    p = m.get('platform') if isinstance(m.get('platform'), dict) else {}
    mobile = p.get('kind') == 'mobile'
    if mobile != (p.get('orientation') in ORIENTATIONS):
        rep.error(a, 'platform: a mobile game says its orientation (landscape or portrait), a desktop game has none')
        return
    if m['variant'] == 'full':
        rel = 'UnityProject/' + PLATFORM_FILE
        try:
            with v.open_text(rel) as f:
                held = platform_said(f.read())
        except KeyError:
            held = None
        except ValueError as e:
            rep.error(area, f'UnityProject/{e}')
            return
        if held != (p.get('orientation') if mobile else None):
            rep.error(a, f'platform says {"mobile, " + str(p.get("orientation")) if mobile else "a desktop game"}, but '
                         + (f'{rel} says mobile, {held}' if held else f'there is no {rel} (a desktop game)'))
    b = m.get('build') if isinstance(m.get('build'), dict) else {}
    keys = ('apk', 'package', 'version_code', 'version_name', 'min_sdk', 'target_sdk')
    if not mobile:
        named = [k for k in keys if k in b]
        if named:
            rep.error(a, f'build names {", ".join(named)}, but the game is a desktop game (no platform of kind mobile)')
        return
    if 'apk' not in b:
        if m['variant'] == 'full':
            rep.error(a, 'a mobile game without its APK in Build/: a mobile game is delivered with its Android APK. Build '
                         'the release commit on a machine with the Android toolchain (docs/new-machine.md, "Mobile '
                         'games") and package again')
        return
    missing = [k for k in keys if k not in b]
    if missing:
        rep.error(a, f'build names its apk without {", ".join(missing)} (what the APK says of itself)')
        return
    if 'Build/' + b['apk'] not in listed:
        rep.error(a, f'build.apk Build/{b["apk"]} is not in files[]')
    if b['min_sdk'] < MOBILE_MIN_SDK or b['target_sdk'] < MOBILE_TARGET_SDK:
        rep.error(a, f'the APK is for minSdk {b["min_sdk"]} and targetSdk {b["target_sdk"]}: at least {MOBILE_MIN_SDK} and '
                     f'{MOBILE_TARGET_SDK}')
    if not re.fullmatch(r'com\.[a-z][a-z0-9]*\.game', b['package']):
        rep.error(a, f'the APK\'s package name is {b["package"]!r}: com.<project in lower case>.game')


LFS_PTR = re.compile(rb'^version https://git-lfs\.github\.com/spec/v1\r?\noid sha256:([0-9a-f]{64})\r?\nsize ([0-9]+)')
OPTS = {'hash': True, 'quick': False}


def git_out(*args, input=None):
    r = subprocess.run(['git', *args], capture_output=True, input=input)
    if r.returncode != 0:
        raise RuntimeError(f'git {" ".join(args[:3])}: {r.stderr.decode("utf-8", "replace").strip()[:200]}')
    return r.stdout


def check_sessions(rep, area, v, m):
    """Full variant: History/sessions/, the creation sessions as recorded: messages.jsonl (every prompt the person
    typed and every reply the model wrote) and actions.jsonl (every tool call), one JSON row per line. Games recorded
    before prompts and replies were have no messages.jsonl; nothing here is an error."""
    a = f'{area}: History/sessions'
    files = {'messages.jsonl': ('role', 'text'), 'actions.jsonl': ('event',)}
    stray = sorted(r for r in v.names if r.startswith('History/sessions/') and r[len('History/sessions/'):] not in files)
    if stray:
        rep.warn(a, f'{len(stray)} file(s) that are not messages.jsonl or actions.jsonl, e.g. {stray[0]}')
    listed = (m.get('history') or {}).get('sessions') or {}
    for name, keys in files.items():
        rel = f'History/sessions/{name}'
        if not v.has(rel):
            rep.note(a, f'no {name}' + (': the prompts and replies of the creation sessions are not in this dataset'
                                        if name == 'messages.jsonl' else ''))
            continue
        rows, bad, raw_ids, sessions, roles = 0, 0, 0, set(), {}
        with v.open_text(rel) as f:
            for line in f:
                if not line.strip():
                    continue
                rows += 1
                try:
                    r = json.loads(line)
                except ValueError:
                    r = None
                if not isinstance(r, dict) or not all(isinstance(r.get(k), str) for k in ('time', 'session_id') + keys):
                    bad += 1
                    continue
                sessions.add(r['session_id'])
                if re.fullmatch(r'[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}', r['session_id']):
                    raw_ids += 1
                if name == 'messages.jsonl':
                    roles[r['role']] = roles.get(r['role'], 0) + 1
        if bad:
            rep.warn(a, f'{name}: {bad} of {rows} row(s) are not a JSON object with {", ".join(("time", "session_id") + keys)}')
        if raw_ids:
            rep.warn(a, f"{name}: {raw_ids} row(s) carry the build machine's session id, not session_NN")
        if name == 'messages.jsonl' and set(roles) - {'user', 'assistant', 'thinking'}:
            rep.warn(a, f'{name}: roles other than user, assistant and thinking: {", ".join(sorted(set(roles) - {"user", "assistant", "thinking"}))}')
        want = (listed.get(name[:-len('.jsonl')]) or {}).get('rows') if isinstance(listed, dict) else None
        if want is not None and want != rows:
            rep.warn(a, f'{name}: {rows} row(s), manifest.json history.sessions says {want}')
        detail = f'{roles.get("user", 0)} prompt(s), {roles.get("assistant", 0)} repl(ies), {roles.get("thinking", 0)} reasoning summar(ies)' if name == 'messages.jsonl' else f'{rows} row(s)'
        rep.note(a, f'{name}: {detail} in {len(sessions)} session(s)')


def check_history(rep, area, v, m):
    """Full variant: History/<game>.bundle + History/lfs/objects (every LFS object of every commit)."""
    import hashlib, tempfile
    a = f'{area}: History'
    h = m.get('history')
    if not isinstance(h, dict):
        rep.error(a, 'manifest.json history must be an object in a Dataset.zip')
        return
    if h['head'] != m['commit']:
        rep.error(a, f'history.head {h["head"][:12]} differs from manifest commit {m["commit"][:12]}')
    if not v.has(h['bundle']):
        rep.error(a, f'no {h["bundle"]}')
        return
    objs = {rel[len('History/lfs/objects/'):].split('/')[-1]: rel for rel in v.names if rel.startswith('History/lfs/objects/')}
    for oid, rel in objs.items():
        if not re.fullmatch(r'[0-9a-f]{64}', oid) or rel != f'History/lfs/objects/{oid[:2]}/{oid[2:4]}/{oid}':
            rep.error(a, f'{rel}: not at lfs/objects/<aa>/<bb>/<sha256>')
    if len(objs) != h['lfs_objects'] or sum(v.sizes[r] for r in objs.values()) != h['lfs_bytes']:
        rep.error(a, f'{len(objs)} LFS objects / {sum(v.sizes[r] for r in objs.values())} bytes, manifest history says {h["lfs_objects"]} / {h["lfs_bytes"]}')
    if OPTS['quick']:
        rep.note(a, 'quick: bundle contents and LFS hashes not checked')
        return
    with tempfile.TemporaryDirectory(prefix='validate-game-') as tmp:
        bundle = v.names[h['bundle']]
        if v.zip:
            bundle = os.path.join(tmp, 'h.bundle')
            with v.zip.open(v.names[h['bundle']]) as src, open(bundle, 'wb') as dst:
                shutil.copyfileobj(src, dst, 1 << 20)
        try:
            heads = git_out('bundle', 'list-heads', bundle).decode().split()
            if h['head'] not in heads:
                rep.error(a, f'the bundle has no ref at history.head {h["head"][:12]}')
            bare = os.path.join(tmp, 'repo.git')
            git_out('clone', '--quiet', '--bare', '--mirror', bundle, bare)
            commits = git_out('-C', bare, 'rev-list', '--all').decode().split()
            v.commits = set(commits)   # for the tasks' seed commits
            if len(commits) != h['commits']:
                rep.error(a, f'the bundle holds {len(commits)} commits, manifest history says {h["commits"]}')
            idents = set(git_out('-C', bare, 'log', '--all', '--format=%an%n%cn%n%ae%n%ce').decode('utf-8', 'replace').split('\n')) - {''}
            bad = sorted(i for i in idents if not re.fullmatch(r'dev_[0-9]+(@[a-z0-9.-]+)?', i))
            if bad:
                rep.error(a, f'{len(bad)} author/committer identities are not anonymised (dev_NN), e.g. {bad[0][:3]}...')
            msgs = git_out('-C', bare, 'log', '--all', '--format=%B').decode('utf-8', 'replace')
            for p in SPEC['repo']['banned_names']['patterns']:
                n = len(re.findall(p, msgs))
                if n:
                    rep.error(a, f'commit messages: {p} x{n}')
            # every LFS pointer of every commit has its object
            objlist = git_out('-C', bare, 'rev-list', '--objects', '--all').decode('utf-8', 'replace').splitlines()
            shas = '\n'.join(l.split(' ')[0] for l in objlist) + '\n'
            small = [l.split(' ') for l in git_out('-C', bare, 'cat-file', '--batch-check=%(objectname) %(objecttype) %(objectsize)',
                                                   input=shas.encode()).decode().splitlines()]
            cand = [s[0] for s in small if len(s) == 3 and s[1] == 'blob' and int(s[2]) < 300]
            need, missing = set(), []
            if cand:
                data = git_out('-C', bare, 'cat-file', '--batch', input=('\n'.join(cand) + '\n').encode())
                pos = 0
                while pos < len(data):
                    nl = data.index(b'\n', pos)
                    size = int(data[pos:nl].split()[2])
                    body = data[nl + 1:nl + 1 + size]
                    pos = nl + 1 + size + 1
                    mm = LFS_PTR.match(body)
                    if mm:
                        need.add((mm.group(1).decode(), int(mm.group(2))))
            for oid, size in sorted(need):
                rel = objs.get(oid)
                if not rel:
                    missing.append(oid)
                elif v.sizes[rel] != size:
                    rep.error(a, f'LFS object {oid[:12]}: {v.sizes[rel]} bytes, its pointer says {size}')
            for oid in missing[:10]:
                rep.error(a, f'LFS object {oid[:12]}... is referenced by a commit but not in History/lfs/objects')
            if len(missing) > 10:
                rep.error(a, f'... {len(missing) - 10} more LFS objects missing')
            if OPTS['hash']:
                badhash = 0
                for oid, rel in objs.items():
                    hs = hashlib.sha256()
                    with (v.zip.open(v.names[rel]) if v.zip else open(v.names[rel], 'rb')) as f:
                        for chunk in iter(lambda: f.read(1 << 20), b''):
                            hs.update(chunk)
                    if hs.hexdigest() != oid:
                        badhash += 1
                        if badhash <= 5:
                            rep.error(a, f'{rel}: content does not hash to its name')
            rep.note(a, f'{len(commits)} commits, {len(heads) // 2} ref(s), {len(need)} LFS objects referenced, {len(objs)} present')
        except (RuntimeError, ValueError, IndexError) as e:
            rep.error(a, f'cannot read the bundle: {e}')


# A game's platform (docs/game-format.md, "Platform"): a mobile (Android phone) game has Platform.json at its root,
# written by templates/new-game.ps1 -Platform mobile when the project is created; a game without the file is a desktop
# game. read_platform is the one reader of it: the validator, the task check, the pipeline and the packager all ask
# here (the PowerShell tools through `validate-game.py --platform <folder>`).
PLATFORM_FILE = 'Platform.json'
ORIENTATIONS = ('landscape', 'portrait')
PHONE_SIZE = {'landscape': (1920, 1080), 'portrait': (1080, 1920)}   # every play, still and recording of a mobile game


def platform_said(text):
    """What a Platform.json's text says: how the game is held ('landscape' or 'portrait'). ValueError, saying why, for
    one that says anything else: never read as desktop. For a game read out of git or a zip; a folder is read with
    read_platform."""
    try:
        said = json.loads(text.decode('utf-8-sig') if isinstance(text, bytes) else text.lstrip('\ufeff'))
    except ValueError as e:
        raise ValueError(f'{PLATFORM_FILE} cannot be read ({type(e).__name__})') from e
    if (not isinstance(said, dict) or set(said) != {'platform', 'orientation'} or said['platform'] != 'mobile'
            or said['orientation'] not in ORIENTATIONS):
        raise ValueError(f'{PLATFORM_FILE} must be {{"platform": "mobile", "orientation": "landscape" or "portrait"}}')
    return said['orientation']


def read_platform(folder):
    """How the game in `folder` (a game repo, a copy of one at a commit, a dataset's UnityProject/) is held when it is
    a mobile game ('landscape' or 'portrait'), or None: a desktop game, which has no Platform.json. ValueError, saying
    why, for a file that is there and says neither: never read as desktop."""
    path = os.path.join(str(folder), PLATFORM_FILE)
    if not os.path.isfile(path):
        return None
    try:
        with open(path, 'rb') as f:
            return platform_said(f.read())
    except OSError as e:
        raise ValueError(f'{PLATFORM_FILE} cannot be read ({type(e).__name__})') from e


def platform_of(folder):
    """read_platform's answer as the tools pass it on: {"platform": "desktop"}, or {"platform": "mobile",
    "orientation", "width", "height"} with the phone's size for that orientation."""
    orientation = read_platform(folder)
    if orientation is None:
        return {'platform': 'desktop'}
    width, height = PHONE_SIZE[orientation]
    return {'platform': 'mobile', 'orientation': orientation, 'width': width, 'height': height}


# ---- a mobile game's own rules (rule `mobile`; unity-mobile-game skill) ----------------------------------------------
# The values ProjectSettings/ProjectSettings.asset holds for them (Unity 6.3 writes every one of these keys).
MOBILE_MIN_SDK, MOBILE_TARGET_SDK = 26, 34
ANDROID_ARM64 = 2            # AndroidTargetArchitectures: a bit mask, ARMv7 1, ARM64 2, x86 4, x86-64 8
SCRIPTING_IL2CPP = 1         # scriptingBackend: Mono 0, IL2CPP 1
GRAPHICS_VULKAN = '15000000'   # m_APIs of a build target: one little-endian int per API, Vulkan is 21
# defaultScreenOrientation: Portrait 0, PortraitUpsideDown 1, LandscapeRight 2, LandscapeLeft 3, AutoRotation 4
ORIENTATION_FIXED = {'portrait': ('0',), 'landscape': ('2', '3')}
ORIENTATION_AUTO = '4'
AUTOROTATE = {'portrait': ('allowedAutorotateToPortrait', 'allowedAutorotateToPortraitUpsideDown'),
              'landscape': ('allowedAutorotateToLandscapeRight', 'allowedAutorotateToLandscapeLeft')}
MOBILE_QUALITY = 'Mobile'    # the one quality level of a mobile game, on every platform
PROJECT_SETTINGS = 'ProjectSettings/ProjectSettings.asset'
QUALITY_SETTINGS = 'ProjectSettings/QualitySettings.asset'
GRAPHICS_SETTINGS = 'ProjectSettings/GraphicsSettings.asset'


def yaml_map(text, key):
    """The entries of a one-level map under `key:` in a Unity YAML settings file ({name: value}; {} when absent or
    written `key: {}`)."""
    found = re.search(r'^([ \t]*)' + re.escape(key) + r':[ \t]*\r?\n((?:\1[ \t]+\S.*\r?\n?)*)', text or '', re.M)
    return dict(re.findall(r'^[ \t]+([^:\s][^:]*):[ \t]*(.*?)\s*$', found.group(2), re.M)) if found else {}


def mobile_project_errors(orientation, project, quality, graphics):
    """What a mobile game's project settings break (the texts of ProjectSettings.asset, QualitySettings.asset and
    GraphicsSettings.asset): the Android settings as Platform.json says (`orientation`), the package name, the SDK
    levels, arm64 alone, IL2CPP, Vulkan alone; the Windows player's window at the phone's size; and nothing of a
    desktop game's left: one quality level, Mobile, on every platform, drawn with the project's one render pipeline."""
    errs = []
    held = setting(project, 'defaultScreenOrientation')
    other = 'landscape' if orientation == 'portrait' else 'portrait'
    turns = [k for k in AUTOROTATE[other] if setting(project, k) == '1']
    stays = [k for k in AUTOROTATE[orientation] if setting(project, k) == '1']
    if not (held in ORIENTATION_FIXED[orientation] or (held == ORIENTATION_AUTO and stays and not turns)):
        errs.append(f'defaultScreenOrientation is {held}' + (f' with {turns[0]} on' if held == ORIENTATION_AUTO and turns else '')
                    + f', but {PLATFORM_FILE} says {orientation}')
    package = yaml_map(project, 'applicationIdentifier').get('Android', '')
    if not re.fullmatch(r'com\.[a-z][a-z0-9]*\.game', package):
        errs.append(f'the Android package name is {package or "(none)"!r}: com.<project in lower case>.game')
    for key, least in (('AndroidMinSdkVersion', MOBILE_MIN_SDK), ('AndroidTargetSdkVersion', MOBILE_TARGET_SDK)):
        got = setting(project, key) or ''
        if not got.isdigit() or int(got) < least:
            errs.append(f'{key} is {got or "(none)"}: at least {least}')
    if setting(project, 'AndroidTargetArchitectures') != str(ANDROID_ARM64):
        errs.append(f'AndroidTargetArchitectures is {setting(project, "AndroidTargetArchitectures")}: a mobile game is '
                    f'built for arm64 alone ({ANDROID_ARM64})')
    if yaml_map(project, 'scriptingBackend').get('Android') != str(SCRIPTING_IL2CPP):
        errs.append('the Android scripting backend is not IL2CPP (arm64 needs it)')
    apis = re.search(r'-[ \t]*m_BuildTarget:[ \t]*AndroidPlayer[ \t]*\r?\n[ \t]*m_APIs:[ \t]*(\S*)[ \t]*\r?\n[ \t]*m_Automatic:[ \t]*(\d)',
                     project or '')
    if not apis or apis.group(1) != GRAPHICS_VULKAN or apis.group(2) != '0':
        errs.append('the Android graphics API is not Vulkan alone (Auto Graphics API off, Vulkan the only one listed)')
    width, height = PHONE_SIZE[orientation]
    size = (setting(project, 'defaultScreenWidth'), setting(project, 'defaultScreenHeight'))
    if size != (str(width), str(height)):
        errs.append(f'the Windows player opens at {size[0]}x{size[1]}: a mobile game held in {orientation} is played at '
                    f'the phone\'s size, {width}x{height}')
    levels = re.findall(r'^[ \t]*-[ \t]*serializedVersion:.*\r?\n[ \t]*name:[ \t]*(.*?)\s*$', quality or '', re.M)
    if levels != [MOBILE_QUALITY]:
        errs.append(f'the quality levels are {", ".join(levels) or "(none)"}: a mobile game has one, {MOBILE_QUALITY}, so '
                    'the Windows player draws what the phone draws')
    pipeline = re.search(r'customRenderPipeline:[ \t]*\{[^}]*guid:[ \t]*([0-9a-f]{32})', quality or '')
    default = re.search(r'm_CustomRenderPipeline:[ \t]*\{[^}]*guid:[ \t]*([0-9a-f]{32})', graphics or '')
    if not pipeline or not default or pipeline.group(1) != default.group(1):
        errs.append(f"the {MOBILE_QUALITY} quality level's render pipeline is not the project's default one: a mobile "
                    'game is drawn with one pipeline asset everywhere')
    return errs


def check_mobile(rep, repo, files):
    """Rule `mobile`: nothing for a desktop game (no Platform.json); a mobile game's project settings
    (mobile_project_errors). A Platform.json that says neither is an error, never read as desktop."""
    try:
        orientation = read_platform(repo)
    except ValueError as e:
        rep.error('mobile', str(e))
        return
    if orientation is None:
        return
    if PLATFORM_FILE not in files:
        rep.error('mobile', f'{PLATFORM_FILE} is not committed')
    texts = {}
    for path in (PROJECT_SETTINGS, QUALITY_SETTINGS, GRAPHICS_SETTINGS):
        try:
            with open(os.path.join(repo, path), encoding='utf-8-sig', errors='replace') as f:
                texts[path] = f.read()
        except OSError:
            rep.error('mobile', f'no {path} (the first editor open and the mobile setup write it: Scripts/unity.ps1 setup, '
                                'then the step the unity-mobile-game skill names)')
            return
    found = mobile_project_errors(orientation, texts[PROJECT_SETTINGS], texts[QUALITY_SETTINGS], texts[GRAPHICS_SETTINGS])
    for e in found:
        rep.error('mobile', e + ' (unity-mobile-game skill, "Start": the project settings stay as the mobile setup made them)')
    if not found:
        rep.note('mobile', f'an Android phone game held in {orientation}: the project settings agree with {PLATFORM_FILE}')


TASK_NAME = re.compile(r'^[a-z0-9][a-z0-9-]{1,62}\Z')
GRADER_KEYS = ('milestones',)          # the grader's half of a task, with seed.reference


# A play's command line (play_args, a task play's args): the player's own arguments, never the checker's
# (docs/task-probes.md, section 1.1). An element starting with "-" and a letter is a flag, anything else a value.
PLAY_FLAG = re.compile(r'^-+([A-Za-z][^=]*)')   # "--x" too: Unity's own parsing is not ours to second-guess
DENIED_PLAY_ARGS = {'batchmode', 'nographics', 'quit', 'logfile', 'nolog', 'projectpath', 'executemethod', 'popupwindow',
                    'monitor', 'parenthwnd', 'single-instance', 'window-mode'}
DENIED_PLAY_PREFIXES = ('screen-', 'force-', 'taskprobe')
# a task play's `scene` and `args` take the task's place only when present, so they have no default here
TASK_PLAY_DEFAULTS = {'inputs': [], 'every': None, 'after': None}


def denied_play_args(args):
    """The flags among `args` the checker sets itself (window, log, the probe's own) or that would undo them (-nolog,
    -window-mode), as written."""
    for arg in args or []:
        mm = PLAY_FLAG.match(arg) if isinstance(arg, str) else None
        if mm and (mm.group(1).lower() in DENIED_PLAY_ARGS or mm.group(1).lower().startswith(DENIED_PLAY_PREFIXES)):
            yield mm.group(1)


PIECE_TRIANGLES = ('triangles', 'visible_triangles')  # pieces fields whose threshold is never a literal
# fields whose threshold is never a literal: how bright a light, how big a component's bounds, how far apart an object's
# parts, how far an object's bounds or pose moved, how much light it gives off, how loud a sound, how much the ground
# rises and falls, how fast a part spins, and what is drawn in a place (how much of it changes, its colour, how far
# along a line) depend on what a build chose (docs/task-probes.md)
NEVER_LITERAL = {'components': ('intensity', 'extent_x', 'extent_y', 'extent_z', 'bounds_change', 'pose_change', 'glow',
                                'spin'),
                 'objects': ('spread', 'bounds_change', 'pose_change', 'glow', 'spin'),
                 'audio': ('volume', 'max_volume', 'level'), 'ground': ('range',),
                 'drawn': ('motion', 'base_r', 'base_g', 'base_b', 'base_change', 'reach', 'length')}
GROUND_POINT = ('height', 'hit')        # a ground measure at a point `xz`
GROUND_BOX = ('min', 'max', 'mean', 'range', 'hits')   # a ground measure over a `box`
UI_SIGNATURE_AGGS = ('changes', 'any', 'all', 'count')  # a ui signature's value means nothing; whether it changes does
DRAWN_NEAR = ('drawn', 'motion', 'base_r', 'base_g', 'base_b', 'base_change')  # a drawn measure near a point
DRAWN_LINE = ('drawn', 'reach', 'length')    # a drawn measure along a line
ASSET_ONLY = ('import:', 'shader:', 'keyword:')    # fields of one asset (with prop:)
SCENE_ONLY = ('count', 'material_default', 'mesh_collision', 'material:')   # fields of a scene's or prefab's objects
WAITS = 300   # seconds of real time a task play's waits add at most
# seconds a finger stays up before it goes down again (docs/task-probes.md, section 1.3): the probe lifts a finger a
# frame after its touch is over, so a touch that began sooner would find its finger still down and miss on every run
TOUCH_GAP = 0.1
JUDGE_PLAY_SHOTS = 5   # the screenshots a judge check is shown of each of its own plays, unless its `shots` says
JUDGE_SHOTS = 20       # the screenshots a judge check is shown at most: its plays times its shots


def dotted(path):
    """Why a project path (an asset, a scene, a prefab) can't be used, as a list: a `.` or `..` part names a file by a
    way round, outside Assets/ or Packages/ even, and an empty part (`//`, a `/` at the end) is no name at all (the
    editor pass refuses both, the build leaves such a scene out: TaskProbe AssetPass.InProject)."""
    parts = path.split('/') if isinstance(path, str) else []
    if any(part in ('.', '..') for part in parts):
        return [f'{path} has a "." or ".." part: name the file by its own path under Assets/ or Packages/']
    if '' in parts:
        return [f'{path} has an empty part ("//", or a "/" at its end): name the file by its own path under Assets/ '
                'or Packages/']
    return []


def nears(o):
    """Every `near` inside `o` (a measure, a play's inputs, a select), wherever it is nested."""
    if isinstance(o, dict):
        for k, v in o.items():
            if k == 'near' and isinstance(v, dict):
                yield v
            yield from nears(v)
    elif isinstance(o, list):
        for v in o:
            yield from nears(v)


def near_errors(label, o):
    """A near's height band has y_min < y_max, and `y_relative` only with one of them."""
    errs = []
    for near in nears(o):
        lo, hi = near.get('y_min'), near.get('y_max')
        if isinstance(lo, (int, float)) and isinstance(hi, (int, float)) and not lo < hi:
            errs.append(f'{label}: a near band has y_min < y_max')
        if near.get('y_relative') and lo is None and hi is None:
            errs.append(f'{label}: `y_relative` goes with y_min or y_max')
    return errs


def live(o, keys=('player', 'camera')):
    """Whether a select names the player or the camera anywhere in it (a `player` select, a point on either), which
    only a running game has."""
    if isinstance(o, dict):
        return any(o.get(k) is not None for k in keys) or any(live(v, keys) for v in o.values())
    if isinstance(o, list):
        return any(live(v, keys) for v in o)
    return False


def component_selects(measure):
    """The components selects of a measure (its own when it reads components)."""
    if measure.get('probe') == 'components' and isinstance(measure.get('select'), dict):
        yield measure['select']


def named_shots(play):
    """The names of the screenshots a task play's `shot` inputs take."""
    return [i['shot'] for i in play.get('inputs') or [] if isinstance(i, dict) and isinstance(i.get('shot'), str)]


def task_play_errors(n, play, plays):
    """A task play's rules beyond the schema, for check `n` (a probe's `play`, a judge's `plays`): not named
    look/drive/editor/trace, no input at or after its end, no touch that ends after it or begins less than TOUCH_GAP
    after its finger lifts, no flag of the checker's own, a scene path without dotted segments, waits of at most 300 s
    in all, its named shots each named once (20 at most), a view's pitch within -89 to
    89, scene loads without dotted segments, no pin on the player and none both `front` and `at`, a shot's `when` an
    event's rules (event_errors), and identical to every other task play of its name in the task (`plays`:
    those seen so far, by name)."""
    errs, pname = [], play.get('name')
    if pname in ('look', 'drive', 'editor', 'trace'):
        errs.append(f"check {n}: a task play can't be named {pname}")
    secs = play.get('seconds')
    if isinstance(secs, (int, float)) and any(isinstance(i, dict) and isinstance(i.get('t'), (int, float))
                                              and i['t'] >= secs for i in play.get('inputs') or []):
        errs.append(f'check {n}: play {pname} has an input at or after its end ({secs} s)')
    for name in denied_play_args(play.get('args') if isinstance(play.get('args'), list) else []):
        errs.append(f"check {n}: a task play can't set -{name}")
    errs += [f'check {n}: play {pname}: {e}' for e in dotted(play.get('scene'))]
    waits = sum(i['wait'] for i in play.get('inputs') or []
                if isinstance(i, dict) and isinstance(i.get('wait'), (int, float)))
    if waits > WAITS:
        errs.append(f'check {n}: play {pname} waits {waits:g} s in all, more than {WAITS} s')
    shots = named_shots(play)
    if len(shots) != len(set(shots)):
        errs.append(f'check {n}: play {pname} names a shot twice')
    if len(shots) > JUDGE_SHOTS:
        errs.append(f'check {n}: play {pname} takes {len(shots)} named shots, more than {JUDGE_SHOTS}')
    for i in play.get('inputs') or []:
        if not isinstance(i, dict):
            continue
        view = i.get('view')
        if isinstance(view, list) and len(view) == 2 and all(isinstance(v, (int, float)) for v in view) and not (
                -89 <= view[0] <= 89 and -360 <= view[1] <= 360):
            errs.append(f'check {n}: play {pname} has a view {view}: [pitch, yaw], pitch -89 to 89, yaw -360 to 360')
        errs += [f'check {n}: play {pname}: {e}' for e in dotted(i.get('scene'))]
        if isinstance(i.get('pin'), dict) and i['pin'].get('player') is True:
            errs.append(f'check {n}: play {pname} pins the player: a pin holds another object (a teleport holds the player)')
        if 'pin' in i and i.get('front') is not None and i.get('at') is not None:
            errs.append(f'check {n}: play {pname} pins an object `front` of the player or `at` a point, not both')
        if isinstance(i.get('when'), dict):
            errs += event_errors(n, i['when'], f"play {pname}: shot {i.get('shot')}'s when", True)
    down = {}   # finger -> when its last touch lifts
    touches = [i for i in play.get('inputs') or [] if isinstance(i, dict) and ('tap' in i or 'drag' in i)
               and isinstance(i.get('t'), (int, float))]
    for i in sorted(touches, key=lambda i: i['t']):
        lasts = sum(i[k] for k in (('over', 'hold') if 'drag' in i else ('hold',))
                    if isinstance(i.get(k), (int, float)) and not isinstance(i.get(k), bool))
        finger = i.get('finger') if isinstance(i.get('finger'), int) else 0
        if isinstance(secs, (int, float)) and i['t'] + lasts > secs:
            errs.append(f'check {n}: play {pname} has a touch that ends after the play ({secs} s)')
        if finger in down and i['t'] < down[finger] + TOUCH_GAP - 1e-9:
            errs.append(f"check {n}: play {pname} puts finger {finger} down at {i['t']:g} s, less than {TOUCH_GAP:g} s "
                        f"after it lifts ({down[finger]:g} s): give the second touch another finger, or start it later")
        down[finger] = i['t'] + lasts
    whole = dict(TASK_PLAY_DEFAULTS, **play)
    if plays.setdefault(pname, whole) != whole:
        errs.append(f'check {n}: task play {pname} differs from another play of that name')
    return errs


def captures(value):
    """Whether a measure or a play's inputs make the probe render a view of its own: a `drawn` measure, an objects or
    components measure of `lit` or `glow` (read as rendered), or a select anywhere in it with `has.lit`."""
    if isinstance(value, dict):
        if value.get('probe') == 'drawn' or (value.get('probe') in ('objects', 'components')
                                             and value.get('field') in ('lit', 'glow')):
            return True
        if isinstance(value.get('has'), dict) and value['has'].get('lit') is True:
            return True
        return any(captures(v) for v in value.values())
    return isinstance(value, list) and any(captures(v) for v in value)


def render_errors(checks):
    """A play that takes a render measure (draw calls, triangles) takes no reading that makes the probe render
    (`captures`): the counts would hold the probe's own renders, and a budget a correct game keeps could read as
    broken. A budget check gets a play of its own (docs/task-probes.md, section 2.20)."""
    reads, capturing = set(), {}
    for c in checks:
        if c.get('kind') != 'probe' or not isinstance(c.get('measure'), dict):
            continue
        play = c.get('play')
        name = play if isinstance(play, str) else (play.get('name') if isinstance(play, dict) else None)
        if c['measure'].get('probe') == 'render':
            reads.add(name)
        if captures(c['measure']) or (isinstance(play, dict) and captures(play.get('inputs'))):
            capturing.setdefault(name, c.get('name'))
    return [f'play {name} takes a render measure and also makes the probe render (check {capturing[name]}: a drawn, '
            'lit or glow reading, or a select with has.lit): give the render measure a play with none of them'
            for name in sorted(x for x in reads & set(capturing) if x)]


def probe_errors(c, seed, ref, plays):
    """A probe check's rules beyond the schema (docs/task-probes.md):
    asset measures only with play "editor" and trace measures only with play "trace"; an asset measure reads one
    `asset`, or the objects of one `scene` or `prefab` (with `select`, which takes no `has`, no `player` and no `near`
    around the player or the camera), and the fields of that one; a trace probe never gates and takes a literal value;
    a task play is not named look/drive/editor/trace, has no input at or after its end, sets no flag of the checker's
    own, and same-named task plays are identical; == and != take a literal value; a screen measure's threshold is
    calibrated or relative to the start (the frame's luminance moves between machines), and so is a pieces measure's
    triangles (they depend on the meshes a build chose) and every NEVER_LITERAL field; a screen rect [x0, y0, x1, y1]
    has x0 < x1 and y0 < y1; a player measure's dist has its `to`; `to_angle` or `to_axis`, not both; `window` or `at`,
    not both; a ground measure takes a point `xz` or a `box` and the fields of that one; a drawn measure takes `near`
    or a `line` and the fields of that one; a components select names its component or `effect`; a near's height band
    has y_min < y_max and `y_relative` only with one of them; a task play's waits add at most 300 s; regular
    expressions that compile; a ui measure takes `match` exactly when it reads text, `agg` changes, any, all or count
    when it reads its signature, and a select rect [x0, y0, x1, y1] with x0 < x1 and y0 < y1; a seen measure's rules
    (seen_errors); a measure's `since` an event's rules (event_errors); a calibrated threshold needs seed.reference and
    a start-relative one a seed."""
    errs, n = [], c.get('name')
    play = c.get('play')
    measure = c.get('measure') if isinstance(c.get('measure'), dict) else {}
    expect = c.get('expect') if isinstance(c.get('expect'), dict) else {}
    probe = measure.get('probe')
    field = measure.get('field')
    pname = play if isinstance(play, str) else (play.get('name') if isinstance(play, dict) else None)
    if (probe == 'asset') != (pname == 'editor'):
        errs.append(f'check {n}: asset measures are taken by the editor pass (play "editor"), and it takes nothing else')
    if (probe == 'trace') != (pname == 'trace'):
        errs.append(f'check {n}: trace measures are read from the trace (play "trace"), and it gives nothing else')
    if probe == 'asset':
        anchors = [k for k in ('asset', 'scene', 'prefab') if measure.get(k) is not None]
        errs += [f'check {n}: {e}' for k in anchors for e in dotted(measure[k])]
        fname = field if isinstance(field, str) else ''
        if len(anchors) != 1:
            errs.append(f'check {n}: an asset measure reads one `asset`, or the objects of one `scene` or `prefab`')
        elif anchors == ['asset'] and (measure.get('select') is not None or fname.startswith(SCENE_ONLY)):
            errs.append(f'check {n}: an asset measure of one asset takes no select and reads prop:, import:, shader: '
                        'or keyword:')
        elif anchors != ['asset'] and fname.startswith(ASSET_ONLY):
            errs.append(f"check {n}: a {anchors[0]}'s objects are read with count, material_default, material:, "
                        'mesh_collision or prop:')
        if isinstance(measure.get('select'), dict) and measure['select'].get('has') is not None:
            errs.append(f'check {n}: a scene as saved is read without its components drawn, so its select takes no `has`')
        if live(measure.get('select')):
            errs.append(f'check {n}: a scene as saved has no player or camera, so its select takes no `player` and no '
                        '`near` around the player or the camera')
    rel = 'calibrate' if 'calibrate' in expect else ('start' if 'start_times' in expect or 'start_plus' in expect else None)
    if probe == 'trace' and (c.get('required', True) or rel):
        errs.append(f'check {n}: a trace probe never gates (required: false) and takes a literal value')
    if isinstance(play, dict):
        errs.extend(task_play_errors(n, play, plays))
    if probe == 'screen' and not rel:
        errs.append(f"check {n}: the frame's luminance moves between machines, so a screen measure's threshold is "
                    'calibrated or relative to the start, never a literal value')
    rect = measure.get('rect')
    if probe == 'screen' and isinstance(rect, list) and len(rect) == 4 and not (rect[0] < rect[2] and rect[1] < rect[3]):
        errs.append(f'check {n}: a screen rect is [x0, y0, x1, y1] with x0 < x1 and y0 < y1')
    if probe == 'pieces' and field in PIECE_TRIANGLES and not rel:
        errs.append(f'check {n}: how many triangles a fair build draws depends on the meshes it chose, so a pieces '
                    "measure's triangles threshold is calibrated or relative to the start, never a literal value")
    if field in NEVER_LITERAL.get(probe, ()) and not rel:
        errs.append(f"check {n}: a {probe} measure's {field} depends on what a build chose, so its "
                    'threshold is calibrated or relative to the start, never a literal value')
    if probe == 'player' and field == 'dist' and measure.get('to') is None:
        errs.append(f"check {n}: a player measure's dist is the distance to its `to` point, which it lacks")
    if measure.get('to_angle') is not None and measure.get('to_axis') is not None:
        errs.append(f'check {n}: `to_angle` or `to_axis`, not both')
    if measure.get('window') is not None and measure.get('at') is not None:   # pick() would take the window alone
        errs.append(f'check {n}: `window` or `at`, not both')
    if probe == 'ground':
        xz, box = measure.get('xz'), measure.get('box')
        if (xz is None) == (box is None):
            errs.append(f'check {n}: a ground measure takes a point `xz` or a `box`, one of them')
        elif xz is not None and field not in GROUND_POINT:
            errs.append(f"check {n}: a ground measure at a point reads {', '.join(GROUND_POINT)}")
        elif box is not None and field not in GROUND_BOX:
            errs.append(f"check {n}: a ground measure over a box reads {', '.join(GROUND_BOX)}")
        elif box is not None and isinstance(box, list) and len(box) == 4 and not (box[0] < box[2] and box[1] < box[3]):
            errs.append(f'check {n}: a ground box is [x0, z0, x1, z1] with x0 < x1 and z0 < z1')
    if probe == 'drawn':
        near, line = measure.get('near'), measure.get('line')
        if (near is None) == (line is None):
            errs.append(f'check {n}: a drawn measure takes `near` (a point) or a `line`, one of them')
        elif near is not None and field not in DRAWN_NEAR:
            errs.append(f"check {n}: a drawn measure near a point reads {', '.join(DRAWN_NEAR)}")
        elif line is not None and field not in DRAWN_LINE:
            errs.append(f"check {n}: a drawn measure along a line reads {', '.join(DRAWN_LINE)}")
    for sel in component_selects(measure):
        if sel.get('component') is None and sel.get('effect') is None:
            errs.append(f'check {n}: a components select names its component, or `effect`')
    errs += near_errors(f'check {n}', [measure, play.get('inputs') if isinstance(play, dict) else None])
    # every regular expression of the measure: the checker reads `match` and a log's `pattern` with Python's re (one
    # that doesn't compile would stop the task check), the probe a select's `text` with .NET's (checked as Python reads it)
    sel = measure.get('select') if isinstance(measure.get('select'), dict) else {}
    for pattern in (measure.get('match'), measure.get('pattern'), sel.get('text')):
        try:
            re.compile(pattern) if isinstance(pattern, str) else None
        except re.error as e:
            errs.append(f"check {n}: {pattern!r} isn't a regular expression ({e})")
    if probe == 'audio' and field in ('sounds', 'repeats') and measure.get('agg') is not None:
        errs.append(f'check {n}: audio {field} is read from the names of the sounds that started over the window: it '
                    'takes no `agg`')
    if probe == 'ui':
        if (field == 'text') != (measure.get('match') is not None):
            errs.append(f'check {n}: a ui measure takes `match` exactly when its field is text')
        if field == 'signature' and measure.get('agg') not in UI_SIGNATURE_AGGS:
            errs.append(f'check {n}: a ui signature is read with `agg` changes, any, all or count')
        rect = sel.get('rect')
        if isinstance(rect, list) and len(rect) == 4 and not (rect[0] < rect[2] and rect[1] < rect[3]):
            errs.append(f'check {n}: a ui select rect is [x0, y0, x1, y1] with x0 < x1 and y0 < y1')
        if sel.get('text') is not None and sel.get('kind') not in (None, 'text'):
            errs.append(f"check {n}: a ui select's `text` picks text elements: its kind is text or unset")
    if probe == 'seen':
        errs.extend(seen_errors(n, play, measure))
    if isinstance(measure.get('since'), dict):
        errs.extend(event_errors(n, measure['since'], 'its since', False))
    if rel and expect.get('op') in ('==', '!='):
        errs.append(f'check {n}: == and != take a literal value, never a calibrated threshold')
    if rel == 'calibrate' and not ref:
        errs.append(f"check {n} calibrates against a reference the task's seed doesn't name")
    if rel == 'start' and not seed:
        errs.append(f'check {n} sets its threshold from the start, which only a seeded task has')
    return errs


SEEN_RECT = 0.02   # a seen rect's least width and height, in frame fractions (the Lab's grader)
# the measures read from samples of a play: what an event (a measure's `since`, a shot's `when`) may read
SAMPLED_PROBES = ('player', 'camera', 'objects', 'widgets', 'components', 'pieces', 'screen', 'light', 'grading',
                  'spawns', 'audio', 'ground', 'ui', 'drawn', 'render', 'world')
# what the probe reads itself, every frame, for a shot's `when` (and an objects measure's prop: fields)
WHEN_FIELDS = {'ui': ('count', 'text'), 'widgets': ('count', 'visible'),
               'objects': ('count', 'x', 'y', 'z', 'active', 'hidden')}


def event_errors(n, event, label, shot):
    """An event's rules beyond the schema (docs/task-probes.md, section 2.23), for check `n`; `label` names it in the
    words ("its since", "shot NAME's when"): its measure is one the probe samples (never log, asset, trace or seen,
    nor audio sounds or repeats, which are read over a window), takes no window, at, agg or since of its own (the event
    is the first sample, or frame, whose reading meets its expect), and keeps every rule of a measure (probe_errors,
    its expect a literal value). A shot's `when` is read by the probe itself every frame, so its measure is one of
    WHEN_FIELDS (or an objects prop: field), its ui select has no rect (the frame isn't read for it) and it takes no
    to_angle or to_axis."""
    at = f'check {n}: {label}'
    measure = event.get('measure') if isinstance(event.get('measure'), dict) else {}
    probe, field = measure.get('probe'), measure.get('field')
    if probe not in SAMPLED_PROBES or (probe == 'audio' and field in ('sounds', 'repeats')):
        return [f'{at}: its measure is read from samples of the play, so it is one the probe samples (never log, '
                'asset, trace or seen, nor audio sounds or repeats)']
    errs = []
    own = [k for k in ('window', 'at', 'agg', 'since') if measure.get(k) is not None]
    if own:
        errs.append(f"{at}: its measure takes no {', '.join(own)} of its own: the event is the first moment its "
                    'reading meets its expect')
    if shot:
        if not (field in WHEN_FIELDS.get(probe, ()) or (probe == 'objects' and str(field).startswith('prop:'))):
            errs.append(f'{at}: the probe reads a shot\'s event itself every frame, so it reads ui count or text, '
                        'widgets count or visible, or objects count, x, y, z, active, hidden or a prop: member')
        sel = measure.get('select') if isinstance(measure.get('select'), dict) else {}
        if probe == 'ui' and sel.get('rect') is not None:
            errs.append(f"{at}: the probe reads a shot's event from the UI's elements, never the frame, so its ui "
                        'select takes no rect')
        if measure.get('to_angle') is not None or measure.get('to_axis') is not None:
            errs.append(f"{at}: a shot's event takes no to_angle or to_axis")
    expect = event.get('expect') if isinstance(event.get('expect'), dict) else {}
    return errs + probe_errors({'name': f'{n} ({label})', 'play': None, 'measure': measure, 'expect': expect},
                               None, None, {})



def seen_errors(n, play, measure):
    """A `seen` measure's rules beyond the schema, as the Lab's grader and dataset format say them (docs/task-probes.md,
    section 2.22): it reads named shots (`shot` inputs) of its check's own task play, never look, drive, editor or
    trace; a rect is at least SEEN_RECT of the frame each way; `match` exactly when it reads text; a list of shots
    only as a number or a clock, with an `agg`, each shot named once; one shot with no `agg`. A null `match` or `agg`
    counts as given where the format reads the key and as missing where the grader reads its value, so either way
    refuses it."""
    errs = []
    if not isinstance(play, dict):
        errs.append(f'check {n}: a seen measure reads a named shot of a task play of its own, never of {play}')
    else:
        named = set(named_shots(play))
        shots = measure.get('shot') if isinstance(measure.get('shot'), list) else [measure.get('shot')]
        for shot in (s for s in shots if s not in named):
            errs.append(f"check {n}: its play {play.get('name')} takes no shot named {shot} (a `shot` input)")
    rect = measure.get('rect')
    if isinstance(rect, list) and len(rect) == 4 and all(_is(v, 'number') for v in rect) and not (
            rect[2] - rect[0] >= SEEN_RECT - 1e-9 and rect[3] - rect[1] >= SEEN_RECT - 1e-9):
        errs.append(f'check {n}: a seen rect is [x0, y0, x1, y1], at least {SEEN_RECT} of the frame each way')
    text = measure.get('read') == 'text'
    if (text and measure.get('match') is None) or (not text and 'match' in measure):
        errs.append(f'check {n}: a seen measure takes `match` exactly when it reads text')
    listed = isinstance(measure.get('shot'), list)
    if listed and (text or measure.get('agg') is None):
        errs.append(f'check {n}: a seen measure reads a list of shots as a number or a clock, with an `agg`')
    if listed and len(set(map(str, measure['shot']))) != len(measure['shot']):
        errs.append(f'check {n}: a seen measure names a shot twice')
    if not listed and 'agg' in measure:
        errs.append(f'check {n}: a seen measure of one shot takes no `agg`')
    return errs


def visual(c):
    """Whether check `c` is a visual one, a model's reading of the grader's screenshots: a `judge`, or a probe whose
    measure is `seen` (the Lab's grader counts it with the judges wherever checks are switched or counted). A seen
    probe is no deterministic probe: it counts toward no task's required or outcome probes."""
    measure = c.get('measure') if isinstance(c.get('measure'), dict) else {}
    return c.get('kind') == 'judge' or (c.get('kind') == 'probe' and measure.get('probe') == 'seen')


def task_semantic_errors(t):
    """What the schema cannot say (the task format's own rules): check names unique, `needs` naming earlier
    checks, a code judge or a reference judge only with seed.reference, a before/after judge only with a seed, a
    judge's own `plays` each named once in the check and under a task play's rules (task_play_errors), its `shots` only
    with plays of its own and its plays times its shots 20 at most, a log_absent pattern that compiles, the task's play_args and player select (no flag of the checker's own; near
    bands; no `player` in the select that says which object the player is) and the probe rules (probe_errors);
    and a task whose start doesn't build (a build check's `fails_at_start`) has nothing that needs the start played:
    no start-relative threshold, no before/after judge (docs/task-probes.md, 3.1); and a play that takes a render
    measure makes no render of the probe's own (render_errors); and a task play's `after` names task plays of the task,
    never itself, in no cycle, each on the saved data of the one before (play_after_errors)."""
    errs, seen, plays = [], set(), {}
    seed = t.get('seed') if isinstance(t.get('seed'), dict) else None
    ref = seed.get('reference') if seed else None
    for name in denied_play_args(t.get('play_args') if isinstance(t.get('play_args'), list) else []):
        errs.append(f"play_args can't set -{name}")
    errs += [f'play_scene: {e}' for e in dotted(t.get('play_scene'))]
    errs += near_errors('player', t.get('player'))
    if live(t.get('player'), ('player',)):
        errs.append('player: this select says which object the player is, so it names no `player` and no point on the '
                    "player (the probe drops a `player` key here and would take the scene's first object)")
    checks = [c for m in t.get('milestones') or [] if isinstance(m, dict) for c in m.get('checks') or []
              if isinstance(c, dict)]
    broken = next((c.get('name') for c in checks if c.get('kind') == 'build' and c.get('fails_at_start') is True), None)
    for m in t.get('milestones') or []:
        for c in (m.get('checks') or []) if isinstance(m, dict) else []:
            if not isinstance(c, dict):
                continue
            n, k = c.get('name'), c.get('kind')
            if k == 'probe':
                errs.extend(probe_errors(c, seed, ref, plays))
                expect = c.get('expect') if isinstance(c.get('expect'), dict) else {}
                relative = [x for x in ('calibrate', 'start_times', 'start_plus') if x in expect]
                if broken and relative:
                    errs.append(f"check {n}: its threshold is relative to the start ({relative[0]}), but the start "
                                f"doesn't build ({broken}: fails_at_start), so it is never played; use a literal value")
            if k == 'judge' and c.get('before') and broken:
                errs.append(f"check {n} compares with the start (before: true), but the start doesn't build "
                            f"({broken}: fails_at_start), so it is never played")
            if k == 'judge':
                own = [p for p in c.get('plays') or [] if isinstance(p, dict)]
                if len({p.get('name') for p in own}) != len(own):
                    errs.append(f'judge check {n} names a play twice')
                for p in own:
                    errs.extend(task_play_errors(n, p, plays))
                    errs.extend(near_errors(f'check {n}', p.get('inputs')))
                shots = c.get('shots', JUDGE_PLAY_SHOTS)
                if shots != JUDGE_PLAY_SHOTS and not own:
                    errs.append(f'judge check {n} sets shots but names no play of its own to take them in')
                named = sum(len(named_shots(p)) for p in own)
                if isinstance(shots, int) and len(own) * shots + named > JUDGE_SHOTS:
                    errs.append(f"judge check {n} asks {len(own)} plays of {shots} screenshots"
                                + (f' and {named} named ones' if named else '') + f": more than a judge's {JUDGE_SHOTS}")
            if k == 'code_judge' and not ref:
                errs.append(f'check {n}: a code judge needs seed.reference')
            if k == 'judge' and c.get('before') and not seed:
                errs.append(f'check {n}: a before/after judge needs a seed')
            if k == 'judge' and c.get('reference') and not ref:
                errs.append(f'check {n}: a reference judge needs seed.reference')
            if k == 'log_absent':
                try:
                    re.compile(c.get('pattern') or '')
                except re.error as e:
                    errs.append(f"check {n}: {c.get('pattern')!r} isn't a regular expression ({e})")
            if n in seen:
                errs.append(f'check {n} is named twice')
            missing = [x for x in (c.get('needs') or []) if x not in seen]
            if missing:
                errs.append(f'check {n} needs {missing}, which come later or do not exist')
            seen.add(n)
    return errs + render_errors(checks) + play_after_errors(checks)


def fresh_after_error(name):
    """Why task play `name` can't be both `fresh` and run `after` other plays."""
    return f'task play {name} is fresh (it starts with the saved data cleared), so it runs after no play: drop its after'


def play_after_errors(checks):
    """A task play's `after` (docs/task-probes.md 1.1): every name it lists is a task play of the task (a probe's play
    or a judge's own plays; never look, drive, editor or trace), named once, never the play itself, and the plays
    never wait on each other in a cycle. A play that names none starts on no saved data and clears what was there, so
    of any two plays one `after` lists, one runs after the other (itself or through the plays it names), in whichever
    order they are listed: the checker plays them in the order their own `after` gives. A play marked `fresh` names
    none."""
    after = {}
    errs = []
    for c in checks:
        named = [c.get('play')] if c.get('kind') == 'probe' else (c.get('plays') or [] if c.get('kind') == 'judge' else [])
        for p in named:
            if isinstance(p, dict) and isinstance(p.get('name'), str):
                found = p.get('after')
                if p.get('fresh') is True and found and p['name'] not in after:
                    errs.append(fresh_after_error(p['name']))
                after.setdefault(p['name'], [x for x in found if isinstance(x, str)] if isinstance(found, list) else [])
    for name, before in after.items():
        if name in before:
            errs.append(f'task play {name} names itself in its after')
        errs += [f'task play {name} names {other} twice in its after' for other in dict.fromkeys(before)
                 if before.count(other) > 1]
        errs += [f'task play {name} runs after {other}, which is no task play of the task' for other in before
                 if other not in after]
    if errs:
        return errs
    done = set()
    while len(done) < len(after):
        free = next((x for x in after if x not in done and all(b in done for b in after[x])), None)
        if free is None:
            return [f"task plays {', '.join(x for x in after if x not in done)} can never start: their after names a "
                    'cycle']
        done.add(free)

    def all_before(name):
        found = set()
        for b in after[name]:
            found |= {b} | all_before(b)
        return found
    for name, before in after.items():
        for i, first in enumerate(before):
            for then in before[i + 1:]:
                if first not in all_before(then) and then not in all_before(first):
                    errs.append(f'task play {name} runs after {first} and {then}, but neither runs after the other: '
                                f'the later one starts on no saved data and clears what the earlier saved (give '
                                f'{then} "after": ["{first}"], or {first} "after": ["{then}"])')
    return errs


def wild(sel):
    """A select that takes its objects by a wildcard on their name and nothing else that narrows them (a components
    select's effect, owner and mesh, a widgets select's text narrow it too)."""
    return isinstance(sel, dict) and isinstance(sel.get('name'), str) and bool(re.search(r'[*?]', sel['name'])) and \
        all(sel.get(k) is None for k in ('component', 'tag', 'layer', 'near', 'has', 'player', 'effect', 'owner', 'mesh',
                                         'text'))


def object_points(o):
    """Every object point ({"object": <select>, ...}) inside `o`, wherever it is nested."""
    if isinstance(o, dict):
        if isinstance(o.get('object'), dict):
            yield o
        for v in o.values():
            yield from object_points(v)
    elif isinstance(o, list):
        for v in o:
            yield from object_points(v)


AUDIO_STARTS = ('started', 'started_audible', 'sounds', 'repeats')   # the sounds that start (docs/task-probes.md 2.16)


def task_warnings(t):
    """Selects that take one object by a wildcard name alone (a warning, never an error): a teleport_to goes to the
    nearest match (Inputs.TeleportTo), an object point stands at the first match in hierarchy order (Find.Point), and
    "of": "first" reads the first row, in the same order. A spawner, a pool or a parent whose name fits is matched
    too: the sample game's teleport_to {"name": "Coin*"} took CoinSpawner. And an upper bound or an exact count of
    the sounds that started, which misses a one-shot on a source that is already playing."""
    out = []
    for m in t.get('milestones') or []:
        for c in (m.get('checks') or []) if isinstance(m, dict) else []:
            if not isinstance(c, dict) or c.get('kind') not in ('probe', 'judge'):
                continue
            measure = c.get('measure') if isinstance(c.get('measure'), dict) else {}
            own = [c.get('play')] if c['kind'] == 'probe' else c.get('plays') or []   # a judge's own plays too
            check, first, found = f'check {c.get("name")}', 'the first (in hierarchy order)', []
            for play in (p for p in own if isinstance(p, dict)):
                inputs = play.get('inputs') or []
                found += [(f'play {play.get("name")}', 'teleport_to', i['teleport_to'], 'goes to the nearest')
                          for i in inputs if isinstance(i, dict) and wild(i.get('teleport_to'))]
                found += [(f'play {play.get("name")}', 'the point', {'object': p['object']}, 'stands at ' + first)
                          for p in object_points(inputs) if wild(p['object'])]
            found += [(check, 'the point', {'object': p['object']}, 'stands at ' + first)
                      for p in object_points(measure) if wild(p['object'])]
            if measure.get('of') == 'first' and wild(measure.get('select')):
                found.append((check, 'the select', measure['select'], 'reads ' + first))
            for where, what, sel, how in found:
                said = (f'{where}: {what} {json.dumps(sel)} {how} object whose name fits, and a spawner, a pool or a '
                        'parent named like it fits too (Coin* takes CoinSpawner): select it by its component (or tag, '
                        'layer, near), or by its full name')
                if said not in out:   # a play's inputs once, whichever checks use the play
                    out.append(said)
            op = (c.get('expect') or {}).get('op') if isinstance(c.get('expect'), dict) else None
            if measure.get('probe') == 'audio' and measure.get('field') in AUDIO_STARTS and op in ('<', '<=', '=='):
                out.append(f"{check}: `{op}` against audio {measure['field']} counts no PlayOneShot on a source that is "
                           'already playing (the engine shows none), so the game may play more sounds than the check '
                           'reads: an upper bound or an exact count holds only where the start plays its sounds '
                           'otherwise (docs/task-probes.md, section 2.16)')
    return out


# The bar every task meets (owner, 2026-11-02): only long threads of multiple edits qualify (unity-write-tasks sections
# 1, 6). The span's size (files, commits, code lines, systems) is a soft bar that warns (owner, 2026-11-19); the
# outcome probes still reject.
MIN_OUTCOME_PROBES = 3     # required probes of weight above 0 outside still_works: one per issue the thread settled
MIN_THREAD_FILES = 5       # game files the reference changes against the start
MIN_THREAD_COMMITS = 4     # commits from seed.commit to seed.reference that change the game (a seed on main)
MIN_THREAD_CODE_LINES = 100   # code lines added plus removed from start to reference (owner, 2026-11-09; was 300)
MIN_THREAD_SYSTEMS = 2        # systems the change crosses, as thread_size counts them (owner, 2026-11-04)
CODE_FILE = re.compile(r'\.(cs|asmdef|asmref|shader|hlsl|cginc|compute|uss|uxml|tss|cpp|h|hpp|c|cc|inl|py|ps1|bat|cmd|sh|'
                       r'js)$', re.I)
NOT_CODE_DIR = re.compile(r'^(Dataset|Docs|RawAssets)/|/ThirdParty/')   # store packs' own code is not the thread's
# the game itself, not its records or docs: the editor steps are the creation's record, and a .meta follows its asset
# (its GUID and import settings)
GAME_FILE = re.compile(r'^(?!Assets/Editor/Steps/)(Assets|Packages|ProjectSettings)/(?!.*\.meta$)')
GAME_PATHS = ('Assets', 'Packages', 'ProjectSettings', ':(exclude)Assets/Editor/Steps', ':(exclude)*.meta')


def outcome_probes(t):
    """The task's outcome probes: its required probes outside still_works whose weight is above 0. A required probe of
    weight 0 is a guard, not an outcome: it must pass, and settles nothing a run earns. A `seen` probe is a visual
    check (`visual`), never an outcome probe."""
    return [c for m in t.get('milestones') or [] if isinstance(m, dict) and m.get('name') != 'still_works'
            for c in m.get('checks') or [] if isinstance(c, dict) and c.get('kind') == 'probe'
            and c.get('required', True) and c.get('weight', 1) > 0 and not visual(c)]


def thread_errors(t, outcomes):
    """Why task `t` (with `outcomes` outcome probes, `outcome_probes`) is not a long thread, from the task alone."""
    errs = []
    if t.get('difficulty') == 'easy':
        errs.append('difficulty \'easy\': a task is "hard" or "medium" (a game needs at least 4 "hard")')
    if 'long-thread' not in (t.get('tags') or []):
        errs.append('no long-thread tag')
    if not (isinstance(t.get('seed'), dict) and t['seed'].get('reference')):
        errs.append("no seed.reference: every task ends at the game's own accepted fix of the thread")
    if outcomes < MIN_OUTCOME_PROBES:
        errs.append(f'{outcomes} required outcome probe(s) of weight above 0 outside still_works, fewer than '
                    f'{MIN_OUTCOME_PROBES} (a required probe of weight 0 is a guard, not an outcome)')
    return errs + noop_errors(t)


def noop_errors(t):
    """Why a no-op would earn something, from the task alone: a no-op scores zero (owner, 2026-11-04). The score is the
    weighted share of checks passed, so what is true of the start takes `"weight": 0`. The task check measures the rest.
    A `seen` probe is a visual check (`visual`), never the outcome check that earns."""
    errs, earning = [], 0
    for m in t.get('milestones') or []:
        for c in (m.get('checks') or []) if isinstance(m, dict) else []:
            if not isinstance(c, dict):
                continue
            kind, weight = c.get('kind'), c.get('weight', 1)
            passes_at_start = (kind == 'build' and not c.get('fails_at_start')) or kind == 'boot' \
                or m.get('name') == 'still_works'
            if passes_at_start and weight != 0:
                errs.append(f'check {c.get("name")}: a no-op passes it, so a no-op would score; give it "weight": 0')
            elif not passes_at_start and c.get('required', True) and kind in ('probe', 'build') and weight > 0 \
                    and not visual(c):
                earning += 1
    if not earning:
        errs.append('no required outcome check carries weight, so no run can score')
    return errs


def thread_system(path):
    """Which system a changed game file belongs to, by its path and extension: config, an embedded package, code (C#
    and assembly definitions), a scene, materials (shaders and textures among them), prefabs (UI documents and
    animator controllers among them), data or another asset."""
    low = path.lower()
    if low.startswith('projectsettings/') or low in ('packages/manifest.json', 'packages/packages-lock.json'):
        return 'config'
    if low.startswith('packages/'):
        return 'package'
    if low.endswith(('.cs', '.asmdef', '.asmref')):
        return 'code'
    if low.endswith('.unity'):
        return 'scene'
    if low.endswith(('.mat', '.shader', '.hlsl', '.cginc', '.compute', '.shadergraph', '.shadersubgraph', '.png', '.jpg',
                     '.jpeg', '.tga', '.psd', '.exr', '.hdr', '.tif', '.tiff')):
        return 'material'
    if low.endswith(('.prefab', '.controller', '.overridecontroller', '.uxml', '.uss', '.tss')):
        return 'prefab'
    if low.endswith(('.asset', '.json', '.csv', '.txt')):
        return 'data'
    return 'asset'


def thread_size(numstat):
    """(code lines, systems) from `git diff --numstat --no-renames`. Binary files and assets never count as code lines;
    assets do count as systems."""
    lines, systems = 0, set()
    for row in numstat.splitlines():
        parts = row.split('\t')
        if len(parts) != 3:
            continue
        added, removed, path = parts
        if GAME_FILE.search(path):
            systems.add(thread_system(path))
        if added.isdigit() and removed.isdigit() and CODE_FILE.search(path) and not NOT_CODE_DIR.search(path):
            lines += int(added) + int(removed)
    return lines, len(systems)


MIN_TASKS = 5          # a game with fewer tasks is rejected (owner, 2026-11-10)
MIN_HARD_TASKS = 4     # at least this many are hard; the others may be medium, none easier (owner, 2026-11-12,
                       # replacing the 2026-11-10 "max 1 medium")


def task_bar_errors(levels):
    """Why a game's tasks ({name: its difficulty or None}) miss the bar a game is accepted at: at least MIN_TASKS tasks,
    at least MIN_HARD_TASKS of them hard; the others may be medium. A task that names no difficulty is medium, the
    format's default; an easy one is thread_errors' finding."""
    errs = []
    if len(levels) < MIN_TASKS:
        errs.append(f'{len(levels)} task(s): a game ships at least {MIN_TASKS}')
    level = {n: d or 'medium' for n, d in levels.items()}
    errs += [f'{n}: difficulty {d!r}: a task is "hard"' for n, d in sorted(level.items()) if d not in ('easy', 'medium', 'hard')]
    hard = sum(d == 'hard' for d in level.values())
    if hard < MIN_HARD_TASKS:
        medium = sorted(n for n, d in level.items() if d == 'medium')
        errs.append(f'{hard} hard task(s): a game needs at least {MIN_HARD_TASKS} hard tasks'
                    + (f' (medium: {", ".join(medium)})' if medium else '') + '; the others may be medium')
    return errs


def report_thread_span(rep, area, label, repo, seed, on_main):
    """The size of a task's span is a soft bar (owner, 2026-11-18 in the Unreal factory, 2026-11-19 here): each
    shortfall is a warning and never rejects the task. A returned task whose start and reference were rebuilt around a
    fix of the game is often smaller than the thread it was written from."""
    for e in thread_span_errors(repo, seed, on_main):
        rep.warn(area, f'{label}: {e} (unity-write-tasks section 1: a long thread is the aim; the size is a soft bar, '
                       'so this does not reject the task)')


def thread_span_errors(repo, seed, on_main):
    """Why the span from seed.commit to seed.reference is short: game files changed, and on main the commits. The
    caller reports these as warnings: the size of a span is a soft bar, not a rejection."""
    start, ref = seed.get('commit'), seed.get('reference')
    if not (start and ref):
        return []
    errs = []
    files = [p for p in _git(repo, '-c', 'core.quotepath=off', 'diff', '--name-only', start, ref, '--', *GAME_PATHS)
             .stdout.decode('utf-8', 'replace').splitlines() if p.strip()]
    if len(files) < MIN_THREAD_FILES:
        errs.append(f'the reference changes {len(files)} game file(s) against the start, fewer than {MIN_THREAD_FILES}')
    lines, systems = thread_size(_git(repo, '-c', 'core.quotepath=off', 'diff', '--numstat', '--no-renames', start, ref)
                                 .stdout.decode('utf-8', 'replace'))
    if lines < MIN_THREAD_CODE_LINES:
        errs.append(f'the reference changes {lines} code line(s) against the start, fewer than {MIN_THREAD_CODE_LINES}')
    if systems < MIN_THREAD_SYSTEMS:
        errs.append(f'the reference crosses {systems} system(s), fewer than {MIN_THREAD_SYSTEMS}')
    if on_main:
        n = _git(repo, 'rev-list', '--count', f'{start}..{ref}', '--', *GAME_PATHS).stdout.decode().strip()
        if int(n or 0) < MIN_THREAD_COMMITS:
            errs.append(f'{n or 0} commit(s) change the game from seed.commit to seed.reference, '
                        f'fewer than {MIN_THREAD_COMMITS}')
    return errs


RETIRED_KINDS = ('actions_judge',)   # check kinds no new task carries, and with them the `trace` probe


def required_quality_judges(t):
    """The required judge checks that should be optional quality checks: every required judge but the ones covering
    the brief's looks, a `judge` named `looks_as_asked` and a `judge` in the `still_works` milestone."""
    return [c.get('name') for m in t.get('milestones') or [] if isinstance(m, dict) for c in m.get('checks') or []
            if isinstance(c, dict) and c.get('kind') in ('judge', 'code_judge')
            and c.get('required', True) and not (c.get('kind') == 'judge' and (
                c.get('name') == 'looks_as_asked' or m.get('name') == 'still_works'))]


def retired_checks(t):
    """The task's retired checks, `actions_judge` checks and `trace` probes (the owner, 2026-11-13: nothing in a task
    reads the agent's tool calls). Refused (owner, 2026-11-19): the Lab's Unity grader has no `trace` play, so a task
    with a trace probe gives every run reward 0, and it has no `actions_judge` kind, so such a check fails every run."""
    return [c.get('name') for m in t.get('milestones') or [] if isinstance(m, dict) for c in m.get('checks') or []
            if isinstance(c, dict) and (c.get('kind') in RETIRED_KINDS or c.get('kind') == 'probe'
                                        and isinstance(c.get('measure'), dict) and c['measure'].get('probe') == 'trace')]


def check_task(rep, a, label, t, game, has_commit):
    """One whole task (GameTask): schema, the format's extra rules, seed on `game` and on known commits. False when the
    schema refuses it: the rest reads the values as the schema types them, so it waits until the task matches."""
    problems = list(check_schema(t, SCHEMAS['game-task']))
    for e in problems[:5]:
        rep.error(a, f'{label}: {e}')
    if problems:
        return False
    for e in task_semantic_errors(t)[:5]:
        rep.error(a, f'{label}: {e}')
    for w in task_warnings(t)[:5]:
        rep.warn(a, f'{label}: {w}')
    gated = [c for m in t.get('milestones') or [] if isinstance(m, dict) for c in m.get('checks') or []
             if isinstance(c, dict) and c.get('kind') == 'probe' and c.get('required', True) and not visual(c)]
    judged = required_quality_judges(t)
    retired = retired_checks(t)
    if retired:
        rep.error(a, f'{label}: check(s) {retired}: `actions_judge` checks and `trace` probes are retired: remove it '
                     f'(the Lab\'s grader gives a task with a trace probe reward 0 on every run and fails an '
                     f'actions_judge check on every run) (unity-write-tasks section 5)')
    seen_probes = [c.get('name') for m in t.get('milestones') or [] if isinstance(m, dict)
                   for c in m.get('checks') or [] if isinstance(c, dict) and c.get('kind') == 'probe' and visual(c)]
    if not gated:
        rep.error(a, f'{label}: no required probe check: pass/fail must be deterministic (unity-write-tasks section 5)'
                     + (f'; seen probe(s) {seen_probes} are visual checks, counted with the judges'
                        if seen_probes else ''))
    for e in thread_errors(t, len(outcome_probes(t))):
        rep.error(a, f'{label}: {e} (unity-write-tasks section 1: only long threads of multiple edits)'
                     + (f'; seen probe(s) {seen_probes} are visual checks, never outcome probes'
                        if seen_probes and 'outcome probe' in e else ''))
    if judged:
        rep.note(a, f'{label}: required judge check(s) {judged}: only a judge of the brief\'s looks is required '
                    '(`looks_as_asked`, or a judge in `still_works`); other judges should be "required": false '
                    'quality checks')
    s = t.get('seed')
    if isinstance(s, dict):
        if s.get('game') != game:
            rep.error(a, f'{label}: seed.game {s.get("game")!r} is not this game ({game})')
        for k in ('commit', 'reference'):
            c = s.get(k)
            if c and has_commit is not None and not has_commit(c):
                rep.error(a, f'{label}: seed.{k} {str(c)[:12]} is not a commit of this game\'s history'
                             + (' (an ancestor of main\'s head)' if a.startswith('repo') else ''))
    return True


TASKS_REFS = ('tasks', 'origin/tasks')   # where a game's tasks live: its orphan tasks branch, never main


def _git(repo, *args):
    return subprocess.run(['git', '-C', repo, *args], capture_output=True)


def check_repo_tasks(rep, repo, files=None):
    """The game's tasks on its orphan `tasks` branch (`tasks`, else `origin/tasks`): Tasks/<name>.json, one GameTask
    each, name = file stem, seeds on commits of main's history (ancestors of HEAD, the main branch in a game checkout)
    or of the task's own start branch `starts/<name>` (unity-write-tasks section 2), each a Unity ENGINE project as
    committed. The branch shares no history with main, and main's HEAD tracks nothing under Tasks/. Read from git, not
    the working tree (`files` is unused)."""
    a = 'repo: Tasks'
    game = os.path.basename(os.path.normpath(repo))
    on_main = [p for p in _git(repo, '-c', 'core.quotepath=off', 'ls-tree', '-r', '--name-only', 'HEAD', '--', 'Tasks')
               .stdout.decode('utf-8', 'replace').splitlines() if p.strip()]
    if on_main:
        rep.error(a, f'main tracks {len(on_main)} path(s) under Tasks/ (e.g. {on_main[0]}): '
                     'tasks live on the tasks branch, never on main')
    ref = next((r for r in TASKS_REFS if _git(repo, 'rev-parse', '--verify', '-q', r + '^{commit}').returncode == 0), None)
    if not ref:
        rep.error(a, 'no tasks branch (neither tasks nor origin/tasks): a game ships at least 5 tasks, '
                     'on its orphan tasks branch')
        return
    if _git(repo, 'merge-base', ref, 'HEAD').returncode == 0:
        rep.error(a, f'{ref} shares history with main: tasks must be an orphan branch')
    names = [n for n in _git(repo, '-c', 'core.quotepath=off', 'ls-tree', '--name-only', ref + ':Tasks')
             .stdout.decode('utf-8', 'replace').splitlines() if n.strip()]
    paths = ['Tasks/' + n for n in names if n.endswith('.json')]
    if not paths:
        rep.error(a, f'no task files in Tasks/ on {ref} (a game ships at least {MIN_TASKS}; about 10 recommended)')
        return
    known, current, levels = {}, {'stem': ''}, {}

    def has_commit(c):   # an ancestor of main's head, or of the task's own start branch
        key = (c, current['stem'])
        if key not in known:
            tips = ['HEAD'] + [r for r in (f'refs/heads/starts/{current["stem"]}', f'refs/remotes/origin/starts/{current["stem"]}')
                               if _git(repo, 'rev-parse', '--verify', '-q', r).returncode == 0]
            known[key] = any(_git(repo, 'merge-base', '--is-ancestor', c, tip).returncode == 0 for tip in tips)
        return known[key]
    for f in paths:
        stem = f[len('Tasks/'):-len('.json')]
        label = f'{ref}:{f}'
        r = _git(repo, 'show', label)
        if r.returncode != 0:
            rep.error(a, f'{label}: cannot read ({r.stderr.decode("utf-8", "replace").strip()[:120]})')
            continue
        try:
            t = json.loads(r.stdout.decode('utf-8-sig'))
        except ValueError as e:
            rep.error(a, f'{label}: not JSON ({e})')
            continue
        if not isinstance(t, dict):
            rep.error(a, f'{label}: not a task object')
            continue
        levels[stem] = t.get('difficulty') if isinstance(t.get('difficulty'), str) else None
        if t.get('name') != stem:
            rep.error(a, f'{label}: name {t.get("name")!r} differs from the file name')
        current['stem'] = stem
        if not check_task(rep, a, label, t, game, has_commit):
            continue
        seed = t.get('seed') if isinstance(t.get('seed'), dict) else {}
        for k in ('commit', 'reference'):
            if seed.get(k) and has_commit(seed[k]):
                version = start_engine(repo, seed[k])
                if not version.startswith(ENGINE + '.'):
                    rep.error(a, f'{label}: seed.{k} {seed[k][:12]} is a Unity {version or "?"} project: a task starts '
                                 f'from a commit that opens on Unity {ENGINE} as committed (never upgraded; '
                                 'unity-write-tasks section 2)')
        if all(seed.get(k) and has_commit(seed[k]) for k in ('commit', 'reference')):
            on_main = all(_git(repo, 'merge-base', '--is-ancestor', seed[k], 'HEAD').returncode == 0
                          for k in ('commit', 'reference'))
            report_thread_span(rep, a, label, repo, seed, on_main)
            for check, name in reference_only_names(repo, t):
                if check == 'play_args':
                    rep.error(a, f'{label}: play_args set -{name}, a flag only the reference has: a play starts with '
                                 'a scene or flag the start commit has (unity-write-tasks section 4)')
                else:
                    rep.error(a, f'{label}: check {check} names {name}, which only the reference has: another fair '
                                 'build names it otherwise; select by what it does or where it is, press a control by '
                                 'words the start shows or the instruction states (unity-write-tasks section 5)')
    for e in task_bar_errors(levels):
        rep.error(a, f'{ref}: {e} (unity-write-tasks section 1)')
    rep.note(a, f'{len(paths)} task(s) on {ref} (at least {MIN_TASKS}, up to about 10, every one a long thread)')


# What a check names: the component, tag, layer, name and mesh keys of its selects (owner selects and `has` included),
# the members a `where` compares and a `set` stage writes, and the scene, asset and prefab paths of its measure, its
# plays and the task's play_scene; and what a play's inputs name a player sees or a ticket can say: a click's, tap's
# or drag's widget (its caption or name), a scene a play opens or loads, a flag on its command line. A name that
# exists in the reference and not at the start can only be matched by a build that chose the reference's names;
# another fair build reads as absent (unity-write-tasks section 5). A shown name the instruction or title states is
# the ticket's own word, so any fair build has it.
NAMED_KEYS = ('component', 'tag', 'layer', 'name', 'mesh', 'prop')
PATH_KEYS = ('scene', 'asset', 'prefab')
NAME = re.compile(r'[A-Za-z_][A-Za-z0-9_ ]{2,120}')
# a field that names a part: world_yaw:<Part>, forward:<Part>.x, bone:<Component>.<Bone>.y
FIELD_PART = re.compile(r'(?:rel_yaw|world_yaw|world_pitch|world_roll):(.+)$|forward:(.+)\.[xyz]$'
                        r'|bone:([^.]+)\..+\.[xyz]$')


def _walk_names(v, names, paths, key=None):
    if isinstance(v, dict):
        for k, x in v.items():
            _walk_names(x, names, paths, k)
    elif isinstance(v, list):
        for x in v:
            _walk_names(x, names, paths, key)
    elif isinstance(v, str) and not any(ch in v for ch in '*?'):
        if key in PATH_KEYS and v.startswith(('Assets/', 'Packages/')):
            paths.add(v)
        elif key == 'prop':   # a where's member path: each of its members
            names.update(x for x in re.split(r'[.\[\]0-9]+', v) if NAME.fullmatch(x))
        elif key in NAMED_KEYS and NAME.fullmatch(v):
            names.add(v)


def arg_flags(args):
    """The flags of a command line (-scenario 2 -skipIntro: scenario, skipIntro), without their dashes or values."""
    out = set()
    for a in args or []:
        if isinstance(a, str) and a.startswith('-'):
            f = a.lstrip('-').split('=', 1)[0]
            if re.fullmatch(r'[A-Za-z_][A-Za-z0-9_.-]{2,60}', f):
                out.add(f)
    return out


def play_names(play):
    """(names, paths, shown) a task play depends on: the selects of its teleports and stages, the members its `set`
    stages write, the scenes it opens and loads, and the widgets its clicks, taps and drags press and the flags of its
    command line (shown: a player sees them or a ticket can say them)."""
    names, paths, shown = set(), set(), set()
    if not isinstance(play, dict):
        return names, paths, shown
    _walk_names({'scene': play.get('scene')}, names, paths)
    shown |= arg_flags(play.get('args'))
    for i in play.get('inputs') or []:
        if not isinstance(i, dict):
            continue
        for k in ('teleport_to', 'pin', 'to', 'from', 'on'):  # the selects of a teleport and of a stage
            _walk_names(i.get(k), names, paths)
        _walk_names({'scene': i.get('scene')}, names, paths)  # a scene the play loads
        if isinstance(i.get('set'), str):
            names.update(x for x in i['set'].split('.') if NAME.fullmatch(x))
        spots = [i.get('widget')] if i.get('click') else []
        spots += [i.get('tap')] + list(i.get('drag') or []) if ('tap' in i or 'drag' in i) else []
        for w in spots:
            w = w.get('widget') if isinstance(w, dict) else w
            if isinstance(w, str) and len(w.strip()) >= 3 and not any(ch in w for ch in '*?'):
                shown.add(w.strip())
    return names, paths, shown


def probe_names(c):
    """The literal names and project paths a probe check depends on (wildcards skipped: they match by pattern)."""
    names, paths = set(), set()
    _walk_names(c.get('measure'), names, paths)
    field = c['measure'].get('field') if isinstance(c.get('measure'), dict) else None
    found = FIELD_PART.match(field) if isinstance(field, str) else None
    part = next((g for g in found.groups() if g), None) if found else None
    if part and NAME.fullmatch(part):
        names.add(part)
    n, p, _ = play_names(c.get('play'))
    return names | n, paths | p


def _has_name(repo, commit, name, tree):
    """Whether `name` shows at `commit`: as a file name in its tree, or in a text file under Assets/ or ProjectSettings/
    (scripts, scenes and prefabs serialized as text, the tag and layer list)."""
    if any(re.search(rf'(^|/){re.escape(name)}(\.|$)', p) for p in tree):
        return True
    return _git(repo, 'grep', '-q', '-I', '-w', '-F', name, commit, '--', 'Assets', 'ProjectSettings').returncode == 0


def _stated(text, name):
    """Whether the instruction or title says `name` (a caption, a scene by its file name, a flag) in so many words, as
    written (case included)."""
    word = name.rsplit('/', 1)[-1].rsplit('.unity', 1)[0] if name.endswith('.unity') else name
    return bool(re.search(rf'(?<![A-Za-z0-9]){re.escape(word)}(?![A-Za-z0-9])', text))


def reference_only_names(repo, t):
    """[(check, name)] of required probes and judges whose measure or plays name something the reference has and the
    start doesn't (a component type, tag, layer, object, member, scene or asset the thread itself created; a widget a
    play clicks or taps, or a flag on its command line, unless the instruction states it). Engine names are in neither
    tree and pass."""
    seed = t.get('seed') if isinstance(t.get('seed'), dict) else {}
    start, ref = seed.get('commit'), seed.get('reference')
    if not (start and ref):
        return []
    trees = {k: set(_git(repo, '-c', 'core.quotepath=off', 'ls-tree', '-r', '--name-only', k).stdout
                    .decode('utf-8', 'replace').splitlines()) for k in (start, ref)}
    scene = t.get('play_scene') if isinstance(t.get('play_scene'), str) else None
    said = ' '.join(x for x in (t.get('title'), t.get('instruction')) if isinstance(x, str))
    found, cache = [], {}

    def ref_only(n):
        if n not in cache:
            cache[n] = _has_name(repo, ref, n, trees[ref]) and not _has_name(repo, start, n, trees[start])
        return cache[n]

    checks = []
    for m in t.get('milestones') or []:
        for c in (m.get('checks') or []) if isinstance(m, dict) else []:
            if isinstance(c, dict) and c.get('required', True) and c.get('kind') in ('probe', 'judge'):
                checks.append(c)
    if checks and isinstance(t.get('play_args'), list):   # every play starts with them unless it sets its own
        for f in sorted(arg_flags(t['play_args'])):
            if not _stated(said, f) and ref_only(f):
                found.append(('play_args', f))
    for c in checks:
        if c['kind'] == 'probe':
            names, paths = probe_names(c)
            shown = play_names(c.get('play'))[2]
            plays = [c.get('play')]
        else:
            names, paths, shown, plays = set(), set(), set(), c.get('plays') or []
            for pl in plays:
                n, p, s = play_names(pl)
                names, paths, shown = names | n, paths | p, shown | s
        if scene and not any(isinstance(pl, dict) for pl in plays):
            paths.add(scene)
        for p in sorted(paths):
            if p in trees[ref] and p not in trees[start] and not _stated(said, p):
                found.append((c.get('name'), p))
        for n in sorted(names):
            if ref_only(n):
                found.append((c.get('name'), n))
        for n in sorted(shown - names):
            if not _stated(said, n) and ref_only(n):
                found.append((c.get('name'), n))
    return found


ENGINE = '6000.3'   # the checker's Unity (6.3 LTS): it opens a start exactly as committed
EDITOR_VERSION = re.compile(r'^\s*m_EditorVersion:\s*(\S+)', re.M)


def editor_version(text):
    """m_EditorVersion of a ProjectVersion.txt ('' when it names none)."""
    mm = EDITOR_VERSION.search(text or '')
    return mm.group(1) if mm else ''


def start_engine(repo, commit):
    """The Unity version ProjectSettings/ProjectVersion.txt names at `commit` ('' when there is none)."""
    r = _git(repo, 'show', f'{commit}:ProjectSettings/ProjectVersion.txt')
    return editor_version(r.stdout.decode('utf-8-sig', 'replace')) if r.returncode == 0 else ''


def check_tasks(rep, area, v, m):
    """Tasks/ in a Dataset.zip: README.md and Tasks/<name>/task.json + grader.json per task; the agent's part holds none
    of the grader's half; merged, each is a valid task on this game and on commits of History/."""
    a = f'{area}: Tasks'
    if not v.has('Tasks/README.md'):
        rep.error(a, 'no Tasks/README.md')
    folders = sorted({r.split('/')[1] for r in v.names if r.startswith('Tasks/') and r.count('/') >= 2})
    stray = sorted(r for r in v.names if r.startswith('Tasks/') and r != 'Tasks/README.md'
                   and not re.fullmatch(r'Tasks/[^/]+/(task|grader)\.json', r))
    for r in stray[:5]:
        rep.error(a, f'{r}: not part of the layout (Tasks/<name>/task.json, Tasks/<name>/grader.json, Tasks/README.md)')
    if not folders:
        rep.error(a, f'no tasks (a game ships at least {MIN_TASKS})')
    commits = getattr(v, 'commits', None)
    names, levels = [], {}
    for name in folders:
        tp, gp = f'Tasks/{name}/task.json', f'Tasks/{name}/grader.json'
        if not (v.has(tp) and v.has(gp)):
            rep.error(a, f'Tasks/{name}/: needs task.json and grader.json')
            continue
        try:
            task, grader = v.json(tp), v.json(gp)
        except ValueError as e:
            rep.error(a, f'Tasks/{name}/: not JSON ({e})')
            continue
        if not isinstance(task, dict) or not isinstance(grader, dict):
            rep.error(a, f'Tasks/{name}/: task.json and grader.json must be objects')
            continue
        leaked = [k for k in GRADER_KEYS if k in task] + (['seed.reference'] if isinstance(task.get('seed'), dict) and 'reference' in task['seed'] else [])
        if leaked:
            rep.error(a, f'{tp}: holds the grader\'s half ({", ".join(leaked)}): it belongs in grader.json')
        extra = [k for k in grader if k not in ('name', 'seed') + GRADER_KEYS] + \
                ([k for k in grader['seed'] if k != 'reference'] if isinstance(grader.get('seed'), dict) else [])
        if extra:
            rep.error(a, f'{gp}: only name, milestones and seed.reference belong here, not {extra}')
        if task.get('name') != name or grader.get('name') != name:
            rep.error(a, f'Tasks/{name}/: name fields must equal the folder name')
        whole = dict(task)
        for k in GRADER_KEYS:
            if k in grader:
                whole[k] = grader[k]
        if isinstance(grader.get('seed'), dict) and isinstance(whole.get('seed'), dict):
            whole['seed'] = dict(whole['seed'], **grader['seed'])
        check_task(rep, a, f'Tasks/{name}', whole, m['game'], (lambda c: c in commits) if commits is not None else None)
        names.append(name)
        levels[name] = whole.get('difficulty') if isinstance(whole.get('difficulty'), str) else None
    if folders:
        for e in task_bar_errors(levels):
            rep.error(a, f'Tasks/: {e}')
    if commits is None and folders:
        rep.note(a, 'seed commits not checked against History/ (bundle not unpacked: --quick)')
    mt = m.get('tasks')
    if not isinstance(mt, dict):
        rep.error(a, 'the layout needs manifest tasks {"count": n, "names": [...]}')
    elif sorted(mt.get('names') or []) != names or mt.get('count') != len(names):
        rep.error(a, 'manifest tasks (count, names) differ from Tasks/')
    rep.note(a, f'{len(names)} task(s) (at least {MIN_TASKS}; about 10 recommended)')


def run_layout_validator(rep, path, repo_dataset):
    ps = shutil.which('powershell') or shutil.which('pwsh')
    if not ps:
        rep.note('layout', 'PowerShell not found: tools/validate-dataset.ps1 not run')
        return
    args = [ps, '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', os.path.join(HERE, 'validate-dataset.ps1'), path]
    if repo_dataset:
        args.append('-RepoDataset')
    r = subprocess.run(args, capture_output=True, text=True, encoding='utf-8', errors='replace',
                       env=dict(os.environ, UGF_SKIP_CONTENT='1', GF_SKIP_CONTENT='1'))
    out = r.stdout.strip().splitlines()
    vl = [l for l in out if re.match(r'^(VALID|PENDING|INVALID) ', l)]
    verdict = vl[0].strip() if vl else f'no verdict (exit {r.returncode}): {r.stderr.strip()[:200]}'
    area = f'layout ({os.path.basename(path)})'
    for line in out:
        s = line.strip()
        if s.startswith('x '):
            rep.error(area, s[2:])
        elif s.startswith('! '):
            rep.note(area, s[2:])   # validate-dataset.ps1: "!" = note
    if r.returncode == 1:
        m = re.search(r'pending: ([^)]+)\)', verdict)
        rep.warn(area, f'PENDING: {m.group(1).strip() if m else "parts"} not there yet')
    rep.note(area, f'validate-dataset.ps1: {verdict}')


# ---- repo ---------------------------------------------------------------------------------------------------------------
def unity_hidden(name):
    """A file or folder name Unity skips on import, so it has no .meta: .name, name~, cvs, *.tmp."""
    low = name.lower()
    return name.startswith('.') or name.endswith('~') or low == 'cvs' or low.endswith('.tmp')


def meta_depth(parts):
    """How many leading parts of a path are outside what Unity imports: 1 under Assets/, 2 under an embedded package
    Packages/<name>/; None for anything else (Packages/manifest.json, ProjectSettings/, the repo's own files)."""
    if parts[0] == 'Assets' and len(parts) >= 2:
        return 1
    if parts[0] == 'Packages' and len(parts) >= 3:
        return 2
    return None


def meta_problems(files):
    """(missing, orphan, metas): tracked files and folders under Assets/ and embedded packages without a tracked .meta,
    tracked .meta files whose file or folder is not tracked, and the tracked .meta files Unity reads. A folder is
    tracked when a file under it is, even one Unity skips (a folder holding only a .gitkeep gets its .meta)."""
    tracked = set(files)
    need, metas = set(), []
    for f in files:
        base = f[:-len('.meta')] if f.endswith('.meta') else f
        parts = base.split('/')
        k = meta_depth(parts)
        if k is None:
            continue
        shown = next((i for i in range(k, len(parts)) if unity_hidden(parts[i])), len(parts))   # what Unity imports
        if f.endswith('.meta'):
            if shown == len(parts):
                metas.append(f)
            continue
        need.update('/'.join(parts[:i]) for i in range(k + 1, shown + 1))
    missing = sorted(p for p in need if p + '.meta' not in tracked)
    orphan = sorted(m for m in metas if m[:-len('.meta')] not in need)
    return missing, orphan, metas


META_GUID = re.compile(r'^guid:\s*([0-9a-fA-F]{32})\s*$', re.M)


def check_meta(rep, repo, files):
    """Every asset with its .meta (unity-commit-always skill): the .meta holds the GUID every scene, prefab and material
    refers to it by, so it is there, it has its asset, and its GUID is the asset's own."""
    a = 'repo: .meta'
    missing, orphan, metas = meta_problems(files)
    for p in missing[:15]:
        rep.error(a, f'{p}: no .meta tracked (Unity gives it a new GUID on import and every reference to it breaks)')
    if len(missing) > 15:
        rep.error(a, f'... {len(missing) - 15} more files or folders without a .meta')
    for p in orphan[:15]:
        rep.error(a, f'{p}: its file or folder is not tracked (an orphan Unity deletes; an empty folder cannot be '
                     'committed, so neither can its .meta)')
    if len(orphan) > 15:
        rep.error(a, f'... {len(orphan) - 15} more orphan .meta files')
    owners, bad = {}, []
    for m in metas:
        text = read_text(os.path.join(repo, m))
        g = META_GUID.search(text)
        if g and g.group(1).strip('0'):
            owners.setdefault(g.group(1).lower(), []).append(m)
        elif not text.startswith('version https://git-lfs'):   # an LFS pointer: the .meta in LFS is reported above
            bad.append(m)
    for m in bad[:10]:
        rep.error(a, f'{m}: no guid (Unity writes a new one on import and every reference to its asset breaks)')
    shared = [(g, ms) for g, ms in owners.items() if len(ms) > 1]
    for g, ms in shared[:10]:
        rep.error(a, f'{" and ".join(ms[:3])}{" and more" if len(ms) > 3 else ""} share the guid {g}: Unity gives all '
                     'but one a new GUID on import and every reference to those breaks (a folder copied with its .meta '
                     'files: delete the copies\' .meta files so Unity makes new ones)')
    if not missing and not orphan and not bad and not shared:
        rep.note(a, f'{len(metas)} .meta files, each with its file or folder and a guid of its own')


def setting(text, key):
    """The value of a top-level `key:` in a Unity YAML settings file (None when absent)."""
    mm = re.search(r'^\s*' + re.escape(key) + r':[ \t]*(.*?)\s*$', text or '', re.M)
    return mm.group(1) if mm else None


def check_repo(rep, repo):
    R = SPEC['repo']
    files = git_ls(repo)
    if not files:
        rep.error('repo', 'not a git repo, or nothing tracked')
        return
    tracked = set(files)
    gone = [f for f in files if not os.path.lexists(os.path.join(repo, f))]
    if gone:   # the rules below read the checkout
        rep.error('repo', f'{len(gone)} tracked file(s) not in the working tree (e.g. {gone[0]}): check out the release '
                          'commit as it is')
    for req in R['required_files']:
        hits = [f for f in files if re.match(req['pattern'], f)]
        if not hits:
            rep.error('repo', f'missing {req["pattern"]} ({req["what"]})')
        elif req.get('count') and len(hits) != req['count']:
            rep.error('repo', f'{len(hits)} files match {req["pattern"]}, expected {req["count"]}')
    for rule in R['never_tracked']:
        hits = [f for f in files if re.search(rule['pattern'], f)]
        if hits:
            rep.error('repo', f'{len(hits)} tracked file(s) match {rule["pattern"]} (e.g. {hits[0]}): {rule["what"]}')
    # engine: Unity 6.3 LTS, as committed
    pv = 'ProjectSettings/ProjectVersion.txt'
    if pv in tracked:
        version = editor_version(read_text(os.path.join(repo, pv)))
        if not any(version.startswith(e + '.') for e in R['editor_versions']):
            rep.error('repo', f'{pv}: m_EditorVersion {version or "(none)"!r} is not Unity {" or ".join(R["editor_versions"])}')
        else:
            rep.note('repo', f'{pv}: Unity {version}')
    # Force Text serialization and Visible Meta Files: scenes and prefabs diff as YAML, every asset keeps its GUID
    for path, keys in R['project_settings'].items():
        if path in tracked:
            text = read_text(os.path.join(repo, path))
            for key, want in keys.items():
                got = setting(text, key)
                if got != want['value']:
                    rep.error('repo', f'{path}: {key} is {got!r}, must be {want["value"]!r} ({want["what"]})')
    # .gitignore: Unity's generated folders and the local dataset ignored, nothing the game is made of
    text = read_text(os.path.join(repo, '.gitignore'))
    for line in R['gitignore_must_contain']:
        if line not in text.split():
            rep.error('repo: .gitignore', f'missing {line}')
    probes = R['gitignore_must_ignore'] + R['gitignore_must_not_ignore']
    out = subprocess.run(['git', '-C', repo, '-c', 'core.quotepath=off', 'check-ignore', '--no-index', '--stdin'],
                         input=('\n'.join(probes) + '\n').encode(), capture_output=True)   # bytes: no \r on Windows
    ignored = set(out.stdout.decode('utf-8', 'replace').splitlines())
    for p in R['gitignore_must_ignore']:
        if p not in ignored:
            rep.error('repo: .gitignore', f'{p.split("/")[0]}/ is not ignored (Unity regenerates it; it holds machine '
                                          'state and never belongs in the repo)')
    for p in R['gitignore_must_not_ignore']:
        if p in ignored:
            rep.error('repo: .gitignore', f'{p} would be git-ignored: everything the game is made of is committed '
                                          '(store packs included), only Unity\'s generated folders and build output '
                                          'are ignored')
    # Git LFS for binaries; Unity's YAML stays plain git text
    r = subprocess.run(['git', '-C', repo, '-c', 'core.quotepath=off', 'lfs', 'ls-files', '--name-only'],
                       capture_output=True, text=True, encoding='utf-8', errors='replace')
    lfs = set(r.stdout.splitlines())
    ext_rx = re.compile(r'(?i)\.(' + '|'.join(R['lfs_required_extensions']) + r')$')
    path_rx = [re.compile(p) for p in R['lfs_required_paths']]
    yaml_rx = re.compile(r'(?i)\.(' + '|'.join(R['yaml_extensions']) + r')$')
    binary = lambda f: ext_rx.search(f) or any(r.search(f) for r in path_rx)

    def yaml_asset(f):   # an .asset Unity wrote as YAML (a binary one may go to LFS through a pattern of its own)
        try:
            with open(os.path.join(repo, f), 'rb') as fh:
                return fh.read(5) == b'%YAML'
        except OSError:
            return False
    if r.returncode:   # without Git LFS every binary would read as plain git
        rep.error('repo: LFS', f'git lfs ls-files failed, so LFS is not checked (is Git LFS installed?): '
                               f'{r.stderr.strip()[:200]}')
    else:
        plain = [f for f in files if binary(f) and f not in lfs]
        for f in plain[:10]:
            rep.error('repo: LFS', f'binary tracked in plain git: {f}')
        if len(plain) > 10:
            rep.error('repo: LFS', f'... {len(plain) - 10} more binaries in plain git')
        yaml_lfs = [f for f in files if f in lfs and (yaml_rx.search(f) or (f.lower().endswith('.asset') and not binary(f)
                                                                            and yaml_asset(f)))]
        for f in yaml_lfs[:10]:
            rep.error('repo: LFS', f'Unity YAML or C# in LFS: {f} (it loses its diffs and merges; .gitattributes must '
                                   'keep it plain git text, as the template\'s does)')
        if len(yaml_lfs) > 10:
            rep.error('repo: LFS', f'... {len(yaml_lfs) - 10} more YAML files in LFS')
    # README images
    if 'README.md' in tracked:
        md = re.sub(r'(?s)<!--.*?-->', '', read_text(os.path.join(repo, 'README.md')))
        links = re.findall(r'!\[[^\]]*\]\(\s*<?([^)\s>]+)>?(?:\s+"[^"]*")?\s*\)', md) + re.findall(r'(?i)<img\b[^>]*\bsrc\s*=\s*["\']([^"\']+)["\']', md)
        local = []
        for l in links:
            if re.match(r'(?i)^(https?:|data:)', l):
                continue
            p = re.sub(r'^\./|^/', '', l.split('#')[0].split('?')[0]).replace('%20', ' ')
            if p not in local:
                local.append(p)
        for p in local:
            if p not in tracked:
                rep.error('repo: README', f'links {p}, which is not committed')
        imgs = R['readme']['gameplay_images']
        if len(local) < imgs['min']:
            rep.error('repo: README', 'shows no gameplay image')
        elif not imgs['recommended_min'] <= len(local) <= imgs['recommended_max']:
            rep.warn('repo: README', f'{len(local)} images; the rule is a hero + gallery of {imgs["recommended_min"]}-{imgs["recommended_max"]} gameplay stills')
        else:
            rep.note('repo: README', f'{len(local)} images, all committed' if all(p in tracked for p in local) else f'{len(local)} images')
    # banned names in tracked text files (LFS and binaries are scanned by the packager)
    bn = R['banned_names']
    rxs = [re.compile(p) for p in bn['patterns']]
    labels = list(bn['patterns'])
    exempt = [None] * len(rxs)
    # the account name of this machine (machine paths with it included), read at run time, never written in the repo;
    # not enforced in scripts (account_name.exempt_paths: Scripts/, the editor steps that ran and script files
    # anywhere), which stay unchanged once they ran and are scrubbed at packaging (user decision b)
    acct = os.environ.get('USERNAME') or os.path.basename(os.path.expanduser('~'))
    if acct and len(acct) >= 4:
        rxs.append(re.compile(r'(?i)(?<![A-Za-z0-9_])' + re.escape(acct) + r'(?![A-Za-z0-9_])'))
        labels.append('the account name')
        exempt.append(re.compile(bn.get('account_name', {}).get('exempt_paths', r'^Scripts/')))
    skip = [re.compile(p) for p in bn['skip_paths']]
    hits, nul = {}, []
    for f in files:
        if f in lfs or binary(f) or any(s.search(f) for s in skip):
            continue
        full = os.path.join(repo, f)
        try:
            if os.path.getsize(full) > 20 * 1024 * 1024:
                continue
            with open(full, 'rb') as fh:
                data = fh.read()
        except OSError:
            continue
        if b'\0' in data[:8192]:
            nul.append(f)   # binary content under a text name (an .asset Unity wrote in binary)
            continue
        text = data.decode('utf-8', 'replace')
        for rx, label, ex in zip(rxs, labels, exempt):
            if ex is not None and ex.search(f):
                continue
            n = len(rx.findall(text))
            if n:
                hits.setdefault(f, []).append(f'{label} x{n}')
    for f, h in list(hits.items())[:15]:
        rep.error('repo: banned names', f'{f}: {", ".join(h)}')
    if len(hits) > 15:
        rep.error('repo: banned names', f'... {len(hits) - 15} more files')
    for f in nul[:10]:
        rep.warn('repo: LFS', f'binary content in plain git: {f} (give its type an LFS pattern in .gitattributes)')
    # every asset with its .meta, no orphan .meta
    check_meta(rep, repo, files)
    # assets.manifest.json: unified format, every listed file committed under Assets/, Packages/ or RawAssets/
    if 'assets.manifest.json' in tracked and os.path.isfile(os.path.join(repo, 'assets.manifest.json')):
        try:
            data = load_json(os.path.join(repo, 'assets.manifest.json'))
        except ValueError as e:
            rep.error('repo: assets.manifest.json', f'not JSON: {e}')
            data = None
        if data is not None:
            check_assets_manifest(rep, 'repo: assets.manifest.json', data,
                                  lambda p: any(t.startswith(p) for t in files) if p.endswith('/') else (p in tracked or any(t.startswith(p + '/') for t in files)))
    # workflow.jsonl: same row schema as the dataset copy (the packager rewrites nothing else)
    if 'workflow.jsonl' in tracked and os.path.isfile(os.path.join(repo, 'workflow.jsonl')):
        with open(os.path.join(repo, 'workflow.jsonl'), encoding='utf-8-sig', errors='replace') as f:
            check_workflow(rep, 'repo: workflow.jsonl', f)
    check_repo_tasks(rep, repo, files)
    check_rules(rep, repo, files)


def check_rules(rep, repo, files):
    """The game contract and the sound rule (the owner's decisions of 2026-11-11): every game not yet submitted, a
    game in progress too, meets them before it is packaged; games already approved in the Lab are not re-validated.
    And a mobile game's own rule (its project settings as its Platform.json says), which says nothing of a desktop
    game."""
    check_contract(rep, repo, files)
    check_sound(rep, repo, files)
    check_mobile(rep, repo, files)


# ---- the contract on a game with combat (unity-game-session skill, "Combat through one interface, state readable"):
# ---- damage through one IDamageable interface the probe can find, key gameplay state never in mutable statics -------
HEALTH_WORDS = {'health', 'hp', 'hitpoints', 'hull', 'poise', 'armor', 'armour'}
STATE_WORDS = {'shield', 'stamina', 'mana', 'lives', 'dead', 'alive', 'dying', 'stun', 'stunned', 'stagger', 'staggered',
               'invulnerable', 'invincible', 'guard', 'guarding', 'blocking', 'parry', 'parrying', 'alert', 'aggro',
               'awake', 'asleep', 'dormant', 'roused'}
WHOLE_WORDS = {'phase', 'state'}
SHOWN_WORDS = {'sound', 'sfx', 'audio', 'fx', 'vfx', 'shown', 'display', 'shake'}
CS_NUMBERS = {'float', 'double', 'decimal', 'bool', 'int', 'uint', 'long', 'ulong', 'short', 'ushort', 'byte', 'sbyte'}
CS_HIT_FUNCTION = re.compile(r'\b(?:void|bool|float|int)\s+(?!TakeDamage\b)((?:Take|Receive|Apply|Deal)(?:Hit|Hurt|Damage)\w*)\s*\(')
CS_MEMBER = re.compile(r'^\s*(?:\[[^\]]*\]\s*)*(?P<mods>(?:(?:public|private|protected|internal|static|readonly|volatile|'
                       r'new|const)\s+)*)(?!(?:return|else|throw|case|goto|await|yield|in|out|ref)\b)(?P<type>[A-Za-z_][\w.]*\??)\s+(?P<name>[A-Za-z_]\w*)\s*(?:=[^;]*;|;|\{\s*get)',
                       re.M)
# a sound made at run time (the owner's decision of 2026-11-11): every game sound is an imported AudioClip asset
RUNTIME_SOUND = re.compile(r'\bAudioClip\s*\.\s*Create\s*\(|\bvoid\s+OnAudioFilterRead\s*\(')


def check_sound(rep, repo, files):
    """Every sound the game plays is an imported asset: no code in Assets/ makes one at run time (AudioClip.Create,
    OnAudioFilterRead), each named with its file and line."""
    found = []
    for f in (f for f in files if f.startswith('Assets/') and f.endswith('.cs') and '/AutoPlay/' not in f
              and '/Editor/' not in f):
        try:
            text = _strip_cs(open(os.path.join(repo, f), encoding='utf-8-sig', errors='replace').read())
        except OSError:
            continue
        for m in RUNTIME_SOUND.finditer(text):
            what = 'OnAudioFilterRead' if 'OnAudioFilterRead' in m.group(0) else 'AudioClip.Create'
            found.append((f, text.count('\n', 0, m.start()) + 1, what))
    for f, ln, what in found[:20]:
        rep.error('sound', f'{f}:{ln}: {what} makes a sound at run time: import every sound as an AudioClip asset (a '
                  'clip, or a WAV a committed script made and imported), so it has a name' + REQUIRED)
    if len(found) > 20:
        rep.error('sound', f'... {len(found) - 20} more places that make a sound at run time' + REQUIRED)


# every finding of the contract and the sound rule ends with this: a game in progress is brought up to them first
REQUIRED = (' (required before this game can be packaged: unity-game-session skill, "Combat through one interface" and'
            ' "Sound")')


def _cs_words(name):
    name = re.sub(r'^(?:m_|_+|k_|s_)', '', name)
    return [w.lower() for w in re.findall(r'[A-Z]+(?=[A-Z][a-z]|\d|$)|[A-Z]?[a-z]+|\d+', name)]


def _cs_key(type_, name):
    """Why a C# member is key state (spec 11.2 K, the name rule of 11.1 K), or None."""
    words, low, t = set(_cs_words(name)), name.lower(), type_.rstrip('?')
    if SHOWN_WORDS & words:
        return None
    number = t in CS_NUMBERS
    if number and (HEALTH_WORDS & words or 'hitpoint' in low):
        return 'health'
    if number and (STATE_WORDS & words or 'cooldown' in low):
        return 'combat state'
    if WHOLE_WORDS & words and (t in CS_NUMBERS - {'float', 'double', 'decimal', 'bool'} or re.match(r'^[A-Z]\w*$', t)):
        return 'phase or state'
    return None


def _strip_cs(text):
    """C# text without comments and string literals (newlines kept, so line numbers hold)."""
    text = re.sub(r'/\*.*?\*/', lambda m: re.sub(r'[^\n]', ' ', m.group(0)), text, flags=re.S)
    text = re.sub(r'//[^\n]*', '', text)
    return re.sub(r'@?"(?:[^"\\\n]|\\.)*"', '""', text)


def check_contract(rep, repo, files):
    """Spec 11.2 D and K on the game's Assets/**/*.cs (the template's AutoPlay and editor code aside): a game with
    combat declares an IDamageable interface with TakeDamage(float, GameObject), implements it and calls it; no key
    state member is a mutable static (no prop: reads one). For new games (the owner's decision of 2026-11-11)."""
    sources = [f for f in files if f.startswith('Assets/') and f.endswith('.cs') and '/AutoPlay/' not in f
               and '/Editor/' not in f]
    health, statics, hit_functions = [], [], []
    declares = implements = calls = False
    for f in sources:
        try:
            text = _strip_cs(open(os.path.join(repo, f), encoding='utf-8-sig', errors='replace').read())
        except OSError:
            continue
        for m in CS_MEMBER.finditer(text):
            why = _cs_key(m.group('type'), m.group('name'))
            if not why:
                continue
            mods = m.group('mods').split()
            if why == 'health':
                health.append(f)
            if 'static' in mods and 'readonly' not in mods and 'const' not in mods:
                statics.append((f, text.count('\n', 0, m.start()) + 1, m.group('name'), why))
        for m in CS_HIT_FUNCTION.finditer(text):
            hit_functions.append((f, text.count('\n', 0, m.start()) + 1, m.group(1)))
        if re.search(r'\binterface\s+IDamageable\b[^{]*\{[^}]*\bfloat\s+TakeDamage\s*\(\s*float\s+\w+\s*,\s*GameObject\b', text,
                     re.S):
            declares = True
        if re.search(r'\bclass\s+\w+\s*:[^{]*\bIDamageable\b', text):
            implements = True
        if re.search(r'(?:\.|\?\.)\s*TakeDamage\s*\(', text):
            calls = True
    if not (health or hit_functions):
        rep.note('contract', 'no combat (no health member, no hit function): the damage rule does not apply')
    else:
        if not declares:
            rep.error('contract', 'combat without the IDamageable interface: declare `interface IDamageable { float '
                      'TakeDamage(float amount, GameObject source); }`, returning the damage actually applied' + (
                          f" (the game's own hit function {hit_functions[0][2]} at {hit_functions[0][0]}:"
                          f'{hit_functions[0][1]} must be a step called from TakeDamage)' if hit_functions else '')
                      + REQUIRED)
        if not implements:
            rep.error('contract', 'combat without a component implementing IDamageable: what can be hurt implements it'
                      + REQUIRED)
        if not calls:
            rep.error('contract', 'combat without a call of TakeDamage: everything that hurts calls IDamageable.TakeDamage'
                      + REQUIRED)
    for f, ln, name, why in statics[:20]:
        rep.error('contract', f'{f}:{ln}: {name} ({why}) is a static field: keep it on a component instance, '
                  'where prop: reads it' + REQUIRED)
    if len(statics) > 20:
        rep.error('contract', f'... {len(statics) - 20} more static key state members' + REQUIRED)


def main():
    for stream in (sys.stdout, sys.stderr):  # paths and names in any script, on any Windows console code page
        stream.reconfigure(encoding='utf-8', errors='replace')
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('repo', nargs='?', help='a game repo (games/<slug>)')
    ap.add_argument('--dataset', help='validate only this dataset (Dataset.zip or a Dataset folder)')
    ap.add_argument('--no-layout', action='store_true', help='skip tools/validate-dataset.ps1')
    ap.add_argument('--content-only', action='store_true', help=argparse.SUPPRESS)  # used by validate-dataset.ps1
    ap.add_argument('--no-zip', action='store_true', help="skip the repo's Dataset.zip")
    ap.add_argument('--json', help='write the findings as JSON')
    ap.add_argument('--quiet', action='store_true', help='print only errors and warnings')
    ap.add_argument('--no-hash', action='store_true', help='skip hashing History/ LFS objects')
    ap.add_argument('--quick', action='store_true', help='skip unpacking the History/ bundle')
    ap.add_argument('--rules-only', action='store_true',
                    help="only the game contract and the sound rule on the repo's Assets/ and a mobile game's project settings "
                         '(what the packager checks first)')
    ap.add_argument('--platform', metavar='FOLDER',
                    help="print what a game folder's Platform.json says, as one JSON line, and exit: "
                         '{"platform": "desktop"}, or {"platform": "mobile", "orientation", "width", "height"}')
    a = ap.parse_args()
    if a.platform:   # the one reader of Platform.json, for the PowerShell tools (tools/unity-pipeline/common.ps1)
        try:
            print(json.dumps(platform_of(a.platform)))
        except ValueError as e:
            print(f'{a.platform}: {e}', file=sys.stderr)
            sys.exit(2)
        sys.exit(0)
    if a.rules_only:
        if not a.repo:
            ap.error('--rules-only takes a game repo')
        rep = Report()
        check_rules(rep, os.path.abspath(a.repo), git_ls(os.path.abspath(a.repo)))
        print(f'{"INVALID" if rep.count("error") else "VALID"}  {rep.count("error")} error(s)  [{a.repo}: contract, sound, mobile]')
        for sev, area, msg in rep.items:
            print(f'  {"x" if sev == "error" else "-"} {area}: {msg}')
        sys.exit(2 if rep.count('error') else 0)
    OPTS['hash'] = not a.no_hash
    OPTS['quick'] = a.quick
    if not a.repo and not a.dataset:
        ap.error('give a game repo or --dataset')
    rep = Report()
    targets = []
    if a.dataset:
        targets.append((os.path.abspath(a.dataset), os.path.basename(os.path.normpath(a.dataset)) == 'Dataset'))
    else:
        repo = os.path.abspath(a.repo)
        check_repo(rep, repo)
        ds = os.path.join(repo, 'Dataset')
        if os.path.isfile(os.path.join(ds, 'manifest.json')):
            targets.append((ds, True))
        else:
            rep.warn('dataset', 'Dataset/ has no manifest.json: not packaged yet (run python tools/package-dataset.py '
                                '<slug>, docs/unity-pipeline.md: it writes Dataset/ for the game session to commit)')
        for z in ('Dataset.zip', 'Dataset.pending.zip'):
            if not a.no_zip and os.path.isfile(os.path.join(repo, z)):
                targets.append((os.path.join(repo, z), False))
    for path, repo_ds in targets:
        name = os.path.basename(path) if not repo_ds else 'Dataset/'
        check_dataset(rep, path, f'dataset {name}')
        if not a.no_layout and not a.content_only:
            run_layout_validator(rep, path, repo_ds)
    verdict = 'INVALID' if rep.count('error') else 'VALID'
    print(f'{verdict}  {rep.count("error")} error(s), {rep.count("warning")} warning(s)  [{a.dataset or a.repo}]')
    for sev, area, msg in rep.items:
        if a.quiet and sev == 'note':
            continue
        mark = {'error': 'x', 'warning': '!', 'note': '-'}[sev]
        print(f'  {mark} {area}: {msg}')
    if a.json:
        with open(a.json, 'w', encoding='utf-8') as f:
            json.dump({'verdict': verdict, 'target': a.dataset or a.repo, 'findings': [dict(severity=s, area=ar, message=m) for s, ar, m in rep.items]}, f, indent=1)
    sys.exit(2 if rep.count('error') else 0)


if __name__ == '__main__':
    main()
