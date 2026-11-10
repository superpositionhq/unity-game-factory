"""The task verifier's documents against the schema, the validator and the repo: every JSON example valid, every link,
path, option and section reference there, and docs/task-probes.md and the task schema documenting the same things.
Plain text checks: no Unity, no network, no git history.

    python -m unittest discover -s tools/tests -p "test_docs.py" -v

What is not checked, so a green run does not claim it:
- a field named in the section of the wrong kind (a field of `objects` under `components`) passes the check of names,
  which holds each name to the schema as a whole; an example that uses it there is caught;
- the files the probe and the checker exchange have no schema. CONTRACT.md section 5's examples of them are held to
  what the checker's own functions write and read and to the keys, flags and log lines the probe's sources name
  (part E); anywhere else a snippet of one is only told apart from task JSON. Of the build's result only what the
  checker reads is held (`ok`, `error`, `missing`), and of a row in probe.json only that the checker reads a value
  from it: what the engine writes is the probe tests' to show (tools/task_check/probe_tests);
- a sketch (a snippet that leaves values out: {"name": ..., "seconds": ...}, {"t", "key", "press"}, an input shown
  without its time) is held to its keys only: each object in it must be a part of the task format with those keys.
  An example written out in full is held to the schema and the validator's rules.
"""
import ast, copy, importlib.util, json, os, re, subprocess, sys, unittest

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = os.path.dirname(TOOLS)
if TOOLS not in sys.path:
    sys.path.insert(0, TOOLS)

from task_check import probes, tasks, unity  # noqa: E402  the checker's writers and readers of the files of part E


def load(name, file):
    spec = importlib.util.spec_from_file_location(name, os.path.join(TOOLS, file))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


vg = load('validate_game', 'validate-game.py')
TASK = vg.SCHEMAS['game-task']
DEFS = TASK['$defs']

PROBES = 'docs/task-probes.md'
SKILL = 'skills/unity-write-tasks/SKILL.md'
CONTRACT = 'tools/task_check/CONTRACT.md'
DOCS = (PROBES, 'docs/task-check.md', 'docs/task-try.md', 'docs/game-format.md', SKILL, CONTRACT)


def read(rel):
    with open(os.path.join(REPO, rel), encoding='utf-8') as f:
        return f.read()


def tracked():
    """The repo's files: git's list, else the tree (an export has no .git)."""
    r = subprocess.run(['git', '-C', REPO, '-c', 'core.quotepath=off', 'ls-files'], capture_output=True)
    if r.returncode == 0 and r.stdout.strip():
        return [p for p in r.stdout.decode('utf-8', 'replace').split('\n') if p]
    out = []
    for base, dirs, files in os.walk(REPO):
        dirs[:] = [d for d in dirs if d not in ('.git', '__pycache__', 'Library', 'Temp', 'Logs')]
        out += [os.path.relpath(os.path.join(base, f), REPO).replace(os.sep, '/') for f in files]
    return out


# ---- text ---------------------------------------------------------------------------------------------------------
FENCE = re.compile(r'^[ \t]*```(\w*)[ \t]*\n(.*?)^[ \t]*```[ \t]*$', re.S | re.M)
SPAN = re.compile(r'`([^`\n]+(?:\n[^`\n]+){0,3})`')
HEADING = re.compile(r'^(#{1,6})[ \t]+(.*?)[ \t]*$', re.M)


def line_of(text, pos):
    return text.count('\n', 0, pos) + 1


def fences(text):
    """(language, line, body) of every fenced block."""
    return [(m.group(1), line_of(text, m.start()), m.group(2)) for m in FENCE.finditer(text)]


def prose(text):
    """The text with its fenced blocks blanked: every character keeps its place, so a position found here is the
    same position in the text."""
    return FENCE.sub(lambda m: re.sub(r'[^\n]', ' ', m.group(0)), text)


def spans(text):
    """(line, code) of every inline code span outside the fenced blocks, a wrapped one joined with single spaces."""
    body = prose(text)
    return [(line_of(body, m.start()), re.sub(r'\s+', ' ', m.group(1)).strip()) for m in SPAN.finditer(body)]


def sections(text):
    """{number: (title, line, body)} for the headings that start with a section number ("2.4", "5."), each with the
    text down to the next heading of its level or above."""
    heads = [(m.start(), len(m.group(1)), m.group(2)) for m in HEADING.finditer(prose(text))]
    out = {}
    for i, (pos, level, title) in enumerate(heads):
        num = re.match(r'(\d+(?:\.\d+)*)\.?(?=\s|$)', title)
        if not num:
            continue
        end = next((p for p, lv, _ in heads[i + 1:] if lv <= level), len(text))
        out[num.group(1)] = (title, line_of(text, pos), text[pos:end])
    return out


def anchors(text):
    """The anchors of a document's headings, as GitHub makes them."""
    out = set()
    for m in HEADING.finditer(prose(text)):
        title = re.sub(r'`|\*|\[([^\]]*)\]\([^)]*\)', lambda x: x.group(1) or '', m.group(2))
        out.add(re.sub(r'[^\w\- ]', '', title.lower()).replace(' ', '-'))
    return out


# ---- A. JSON examples ---------------------------------------------------------------------------------------------
class Unreadable(Exception):
    """A snippet that is neither JSON nor a pattern the table below can expand."""


# What a pattern's placeholder stands for. Bare ones take a JSON value, quoted ones a word. Only what the documents
# use: a new placeholder is added here or, better, the example is written out.
BARE = {'<Point>': '{"xyz": [0, 0, 0]}', '<object select>': '{"tag": "X"}', '<select>': '{"tag": "X"}',
        '<asset measure>': '{"probe": "asset", "asset": "Assets/X.mat", "field": "keyword:_X"}'}
QUOTED = {'<wildcard>': 'X*', '<regex>': 'X', '<type>': 'X', '<Component>': 'X', '<member>': 'x', '<sub>': 'x',
          '<parameter>': 'x', '<property>': '_X', '<Property>': '_X', '<NAME>': '_X', '<path>': 'x', '<Bone>': 'X',
          '<Part>': 'X', '<Parameter>': 'X', '<id>': 'x-1'}
EXPANDED = ('field', 'fact')     # keys whose "a|b|c" is a list of names; anywhere else "|" is a regular expression's


UNSTATED = '…'     # stands in for a value a sketch leaves out: {"name": ..., "seconds": ...}, {"t", "wait"}


def repaired(snippet):
    """A pattern as JSON text: its bare placeholders filled in, its elisions dropped, and what it leaves out ("name":
    ..., a key alone) made UNSTATED: such a snippet is a sketch of keys, not an example of values."""
    s = re.sub(r'\s+', ' ', snippet).strip()
    for k, v in BARE.items():
        s = s.replace(k, v)
    s = re.sub(r',\s*\.\.\.(?=\s*[}\]])', '', s)                    # {"a": 1, ...}: more members follow
    s = re.sub(r'(?<=[{\[])\s*\.\.\.\s*,', '', s)                   # {..., "a": 1}
    s = re.sub(r'(?<=[:\[])\s*\.\.\.(?=\s*[,}\]])', ' "%s"' % UNSTATED, s)          # "name": ...  and  [...]
    s = re.sub(r'(?<=[{,])(\s*"[A-Za-z_]+")(?=\s*[,}])', r'\1: "%s"' % UNSTATED, s)   # a key alone: {"t", "key"}
    # a unit or coordinate letter where a number goes ("radius": m, [x, y, z]): a bare word is never JSON
    s = re.sub(r'(?<=[:\[,])\s*(?!(?:true|false|null)\b)[a-z]+\b(?=\s*[,}\]])', ' 1', s)
    return re.sub(r'\btrue\|false\b', 'true', s)                    # either: the schema says boolean


def filled(v):
    """v with the placeholders inside its strings filled in."""
    if isinstance(v, str):
        for k, word in QUOTED.items():
            v = v.replace(k, word)
        return v
    if isinstance(v, list):
        return [filled(x) for x in v]
    return {k: filled(x) for k, x in v.items()} if isinstance(v, dict) else v


def alternatives(v):
    """v once for each alternative of each "a|b|c" under a key of EXPANDED: one varies, the others stay at their
    first, so every name is read once."""
    spots = []

    def walk(x, path):
        for k, y in (x.items() if isinstance(x, dict) else enumerate(x) if isinstance(x, list) else ()):
            if k in EXPANDED and isinstance(y, str) and '|' in y:
                spots.append((path + (k,), y.split('|')))
            else:
                walk(y, path + (k,))

    walk(v, ())
    out = []
    for i, (_, names) in enumerate(spots):
        for name in names:
            u = copy.deepcopy(v)
            for j, (path, others) in enumerate(spots):
                node = u
                for step in path[:-1]:
                    node = node[step]
                node[path[-1]] = name if j == i else others[0]
            out.append(u)
    return out or [v]


def expand(snippet):
    """The values a snippet stands for. An example written out is read as it is; a pattern is repaired into JSON
    first. Either way the placeholders in its strings are filled in and each alternative of a field's "a|b|c" is
    written out."""
    try:
        v = json.loads(snippet)
    except ValueError:
        try:
            v = json.loads(repaired(snippet))
        except ValueError as e:
            raise Unreadable(f'not JSON and not a pattern this test can expand ({e}): write the example out, or use '
                             f'a placeholder of the table in tools/tests/test_docs.py') from None
    return alternatives(filled(v))


CHECKS = {'probe': 'Probe', 'build': 'Build', 'boot': 'Boot', 'log_absent': 'LogAbsent', 'file_exists': 'FileExists',
          'package': 'Package', 'judge': 'Judge', 'code_judge': 'CodeJudge', 'actions_judge': 'ActionsJudge'}
INPUTS = (('key', 'Key'), ('widget', 'Click'), ('cursor', 'Cursor'), ('teleport_to', 'TeleportTo'),
          ('teleport', 'Teleport'), ('wait', 'Wait'))
EXPECTS = (('value', 'Value'), ('calibrate', 'Calibrate'), ('start_times', 'StartTimes'), ('start_plus', 'StartPlus'))
POINTS = (('xyz', 'AtXYZ'), ('player', 'AtPlayer'), ('camera', 'AtCamera'), ('object', 'AtObject'))
SELECTS = ('Select', 'ComponentSelect', 'WidgetSelect', 'UiSelect', 'AudioSelect', 'PieceSelect', 'Has')
EXCHANGED = ('unity-probe-play/1', 'unity-probe/1', 'game-probe-queries/1')   # CONTRACT.md section 5 formats
# how a snippet of one of those files is known before it is parsed (their examples hold prose and placeholders)
EXCHANGE_MARKS = ('"format": "unity-probe', '"format": "game-probe-queries', '"nonce":')


def classify(v):
    """What an example is: a definition of the task schema, 'task', 'assets-manifest', 'exchange' (a file the probe
    and the checker exchange), 'select' (any select), or None."""
    if not isinstance(v, dict):
        return None
    if 'seed' in v and 'milestones' in v:
        return 'task'
    if v.get('schema') == 'assets-manifest/v1':
        return 'assets-manifest'
    if v.get('format') in EXCHANGED or 'nonce' in v or {'out', 'result'} <= set(v) or {'ok', 'exe'} <= set(v):
        return 'exchange'       # a play spec, probe.json, the editor pass's files, the build's request and result
    if v.get('kind') in CHECKS and 'name' in v:
        return CHECKS[v['kind']]
    if 'probe' in v:
        return kinds().get(v['probe'])
    if 'name' in v and 'seconds' in v:
        return 'TaskPlay'
    if 't' in v:
        if 'axis' in v:
            return 'Axis'
        return next((d for k, d in INPUTS if k in v), None)
    for k, d in INPUTS:         # an input shown without its time: {"teleport_to": {...}}
        if k in v and set(v) <= set(DEFS[d]['properties']):
            return d
    if 'op' in v:
        return next((d for k, d in EXPECTS if k in v), None)
    if 'point' in v and 'radius' in v:
        return 'Near'
    if 'from' in v and 'to' in v:
        return 'Line'
    for k, d in POINTS:
        if k in v and set(v) <= set(DEFS[d]['properties']):
            return d
    if 'criterion' in v:
        return 'RubricItem'     # an item of a judge's rubric
    if any(set(v) <= set(DEFS[d]['properties']) for d in SELECTS):
        return 'select'
    return None


def schema_problems(v, name):
    return list(vg.check_schema(v, DEFS[name], TASK))


def measure_problems(m):
    """A measure's rules beyond the schema (probe_errors), read in a check whose play and threshold its kind takes."""
    probe = m.get('probe')
    c = {'name': 'x', 'kind': 'probe', 'describe': 'x', 'measure': m,
         'play': {'asset': 'editor', 'trace': 'trace'}.get(probe, 'look')}
    if probe == 'trace':
        c.update(required=False, expect={'op': '>=', 'value': 1})
    else:
        c['expect'] = {'op': '>=', 'calibrate': 0.5}    # every field takes a calibrated threshold; some only that
    return schema_problems(c, 'Probe') + vg.probe_errors(c, {'commit': 'a', 'reference': 'b'}, 'b', {})


def task_problems(t):
    rep = vg.Report()
    game = t['seed'].get('game') if isinstance(t.get('seed'), dict) else None
    vg.check_task(rep, 'docs', t.get('name'), t, game, None)
    return [msg for sev, _, msg in rep.items if sev == 'error']


def unstated(v):
    return v == UNSTATED or (isinstance(v, dict) and any(unstated(x) for x in v.values())) \
        or (isinstance(v, list) and any(unstated(x) for x in v))


def sketch_problems(v):
    """A sketch states keys, not values: each object in it must be something of the task format, with keys that
    thing has."""
    if isinstance(v, list):
        return [p for x in v for p in sketch_problems(x)]
    if not isinstance(v, dict):
        return []
    kind = classify(v)
    if kind is None:
        return [f'no part of the task format has the keys {sorted(v)} together']
    out = []
    if kind in DEFS:
        out = [f'{kind} has no key "{k}"' for k in v if k not in DEFS[kind]['properties']]
    return out + [p for x in v.values() for p in sketch_problems(x)]


def value_problems(v):
    """Why one example is not valid, as a list (empty: valid)."""
    kind = classify(v)
    if kind is None:
        return ['not recognised as a task, a check, a measure, a play, an input, a threshold, a point, a near, a line '
                'or a select: make it one, or teach classify() in tools/tests/test_docs.py what it is']
    if kind == 'exchange':
        return []
    if unstated(v) or (kind in dict(INPUTS).values() and 't' not in v):
        return sketch_problems(v)
    if kind == 'task':
        return task_problems(v)
    if kind == 'assets-manifest':
        return list(vg.check_schema(v, vg.SCHEMAS['assets-manifest']))
    if kind == 'select':
        fits = [schema_problems(v, d) for d in SELECTS]
        return [] if any(not f for f in fits) else [f'no select takes it ({min(fits, key=len)[0]})']
    if kind.endswith('Measure'):
        return measure_problems(v)
    problems = schema_problems(v, kind)
    if kind == 'Probe' and not problems:
        problems = vg.probe_errors(v, {'commit': 'a', 'reference': 'b'}, 'b', {})
    return problems


def members(code):
    """[(key, value)] when a span is one or more members of an object ("weight": 0), else None."""
    if not re.match(r'"[A-Za-z_]+"\s*:', code):
        return None
    try:
        return [kv for v in expand('{' + code + '}') for kv in v.items() if not unstated(kv[1])]
    except Unreadable:
        return None


def member_schemas(key):
    """[(schema of the member, its root)] for every place one of the repo's schemas gives a member of that name: the
    task format first, then the manifests and the workflow row."""
    found = []

    def walk(node, root):
        if isinstance(node, dict):
            props = node.get('properties')
            if isinstance(props, dict) and key in props:
                found.append((props[key], root))
            for v in node.values():
                walk(v, root)
        elif isinstance(node, list):
            for v in node:
                walk(v, root)

    for name in sorted(vg.SCHEMAS, key=lambda n: n != 'game-task'):
        walk(vg.SCHEMAS[name], vg.SCHEMAS[name])
    return found


def example_problems(text):
    """[(line, snippet, problem)] for every JSON example of a document: its `json` blocks and its inline spans that
    are an object or members of one. A brace span without a quoted key ({root}, {name, color}) is no JSON example."""
    out = []

    def check(line, snippet):
        if any(mark in snippet for mark in EXCHANGE_MARKS):     # no schema to hold these to: told apart, not checked
            return
        try:
            values = expand(snippet)
        except Unreadable as e:
            out.append((line, snippet, str(e)))
            return
        for v in values:
            out.extend((line, snippet if len(values) == 1 else json.dumps(v), p) for p in value_problems(v))

    for lang, line, body in fences(text):
        if lang != 'json':
            continue
        try:                                        # one value, or one value a line
            json.loads(body)
            parts = [(line + 1, body)]
        except ValueError:
            parts, buf, start = [], '', line + 1
            for i, row in enumerate(body.split('\n')):
                if not buf:
                    start = line + 1 + i
                buf += row + '\n'
                try:
                    expand(buf)
                    parts.append((start, buf))
                    buf = ''
                except Unreadable:
                    continue
            if buf.strip():
                parts.append((start, buf))
        for at, part in parts:
            check(at, part)
    for line, code in spans(text):
        if code.startswith('{'):
            if '"' in code:
                check(line, code)
        else:
            for key, v in members(code) or []:
                fits = member_schemas(key)
                if not fits:
                    out.append((line, code, f'no schema of the repo has a key "{key}"'))
                elif all(list(vg.check_schema(v, s, root)) for s, root in fits):
                    out.append((line, code, f'no "{key}" in a schema of the repo takes {json.dumps(v)}'))
    return out


# ---- B. links, paths, options, section references -------------------------------------------------------------------
LINK = re.compile(r'(?<!\!)\[[^\]\n]*\]\(([^)\s]+)\)')
ROOTS = ('tools', 'docs', 'skills', 'machine', 'templates')
PATH = re.compile(r'(?<![\w<>%\\/.-])((?:' + '|'.join(ROOTS) + r')[/\\][\w./\\-]*\w)')
UNDER_ROOT = re.compile(r'(?:<UGF_ROOT>|%UGF_ROOT%)[/\\]unity-game-factory[/\\]([\w./\\-]*\w)')
SCRIPT = re.compile(r'(?<![\w/\\.-])([A-Za-z][\w-]*\.(?:py|ps1))\b')


def link_problems(rel, text, files, anchor_of):
    """[(line, target, problem)] for the relative links of one markdown file."""
    out = []
    body = prose(text)
    for m in LINK.finditer(body):
        target = m.group(1)
        if re.match(r'[a-z][a-z0-9+.-]*:', target):
            continue
        path, _, frag = target.partition('#')
        dest = os.path.normpath(os.path.join(os.path.dirname(rel), path)).replace(os.sep, '/') if path else rel
        line = line_of(body, m.start())
        if dest not in files and not any(f.startswith(dest.rstrip('/') + '/') for f in files):
            out.append((line, target, f'{dest} is not in the repo'))
        elif frag and dest.endswith('.md') and frag not in anchor_of(dest):
            out.append((line, target, f'{dest} has no heading "#{frag}"'))
    return out


def path_problems(text, files, skip=lambda line, name: False):
    """[(line, path, problem)] for the repo paths and script names a document names."""
    out, names = [], {}
    for f in files:
        names.setdefault(f.rsplit('/', 1)[-1], []).append(f)
    body = prose(text)
    for rx in (PATH, UNDER_ROOT):
        for m in rx.finditer(text):
            p = m.group(1).replace('\\', '/').rstrip('.')
            if p not in files and not any(f.startswith(p.rstrip('/') + '/') for f in files):
                out.append((line_of(text, m.start()), m.group(1), f'{p} is not in the repo'))
    for m in SCRIPT.finditer(body):
        name, line = m.group(1), line_of(body, m.start())
        if text[max(0, m.start() - 1)] in '/\\' or skip(line, name):
            continue
        if name not in names:               # several is fine: each probe test family has its tests.py
            out.append((line, name, f'no file of the repo is named {name}'))
    return out


def options_of(source, prog=None):
    """The options an argparse parser in `source` declares (hidden ones left out); with `prog`, that parser's only."""
    if prog:
        at = source.find(f'prog="{prog}"')
        source = source[at:] if at >= 0 else ''
        nxt = source.find('ArgumentParser(', 1)
        source = source[:nxt] if nxt > 0 else source
    return {m.group(1) for m in re.finditer(r'add_argument\(\s*[\'"](--[a-z][a-z-]*)[\'"]([^\n]*)', source)
            if 'SUPPRESS' not in m.group(2)}


TOOLS_WITH_OPTIONS = {   # tool: (the document that owns it, where its parser is, the parser's prog)
    'task-check.py': ('docs/task-check.md', 'tools/task_check/cli.py', 'task-check.py'),
    'task-try.py': ('docs/task-try.md', 'tools/task_check/trial.py', 'task-try.py'),
    'validate-game.py': ('docs/game-format.md', 'tools/validate-game.py', None),
    'thread-stats.py': (SKILL, 'tools/thread-stats.py', None)}
OPTION = re.compile(r'(?<![\w-])(--[a-z][a-z-]*)')


def option_problems(text, tool, have):
    """[(line, option, problem)] for the options a document shows on the lines that name `tool`."""
    out = []
    for i, row in enumerate(text.split('\n'), 1):
        if tool in row:
            out += [(i, o, f'{tool} has no option {o}') for o in OPTION.findall(row) if o not in have]
    return out


SECTION_REF = re.compile(r'\bsections?\s+(\d+(?:\.\d+)*)(?:\s*(?:,|and|to|-)\s*(\d+(?:\.\d+)*))?')
NAMED = (('task-probes', PROBES), ('unity-write-tasks', SKILL), ('task-check.md', 'docs/task-check.md'))


def section_ref_problems(rel, text, numbers_of):
    """[(line, reference, problem)] for every "section N.M": a section of the document the sentence names just
    before it (task-probes.md, the unity-write-tasks skill), else of this document."""
    out = []
    body = prose(text)
    for m in SECTION_REF.finditer(body):
        before = body[max(0, m.start() - 60):m.start()]
        named = [(before.rfind(word), doc) for word, doc in NAMED if word in before]
        doc = max(named)[1] if named else rel
        for num in filter(None, m.groups()):
            if num not in numbers_of(doc):
                out.append((line_of(body, m.start()), m.group(0), f'{doc} has no section {num}'))
    return out


# ---- C. the schema and docs/task-probes.md ---------------------------------------------------------------------------
def field_words(schema):
    """The names a `field` (or `fact`) schema takes: enum values, and of a pattern "^(a|b|prefix:...)$" its plain
    alternatives and its prefixes ("prop:")."""
    out = set()
    for s in schema.get('anyOf', [schema]):
        if 'const' in s:
            out.add(s['const'])
        out.update(v for v in s.get('enum', []) if isinstance(v, str))
        pat = s.get('pattern')
        if pat:
            inner = re.fullmatch(r'\^\(?(.*?)\)?\$', pat)
            assert inner, f'a field pattern of another shape: {pat[:60]}'
            depth, part, parts = 0, '', []
            for ch in inner.group(1):
                depth += ch in '([' and 1 or ch in ')]' and -1 or 0
                if ch == '|' and depth == 0:
                    parts.append(part)
                    part = ''
                else:
                    part += ch
            for p in parts + [part]:
                word = re.match(r'[a-z_]+:?', p)
                assert word, f'a field alternative of another shape: {p[:40]}'
                out.add(word.group(0))
    return out


def kinds():
    """{probe kind: its measure's definition name}."""
    return {d['properties']['probe']['const']: n for n, d in DEFS.items() if n.endswith('Measure')}


def kind_sections(text):
    """{probe kind: (number, body)} for docs/task-probes.md's sections "### 2.N `kind`: ..."."""
    out = {}
    for num, (title, _, body) in sections(text).items():
        m = re.match(r'[\d.]+\s+`(\w+)`', title)
        if m:
            out[m.group(1)] = (num, body)
    return out


def words(text):
    """What a text names in code: every word (and comparison sign) of its inline spans and its fenced blocks."""
    out = set()
    for code in [c for _, c in spans(text)] + [b for _, _, b in fences(text)]:
        out.update(re.findall(r'[A-Za-z_][A-Za-z0-9_]*:?|[<>=!]=|[<>]', code))
    return out | {w[:-1] for w in out if w.endswith(':')}


def undocumented(text):
    """[(what, word, where it should be)] for everything of the task schema docs/task-probes.md doesn't name where a
    reader looks for it."""
    secs, ks, out = sections(text), kind_sections(text), []

    def need(what, names, num):
        have = words(secs[num][2]) if num in secs else set()
        out.extend((what, n, f'section {num}') for n in sorted(names) if n not in have)

    for kind, name in sorted(kinds().items()):
        if kind not in ks:
            out.append(('probe kind', kind, 'a section "### 2.N `%s`: ..."' % kind))
            continue
        num, props = ks[kind][0], DEFS[name]['properties']
        need(f'{kind} field', field_words(props.get('field') or props['fact']), num)
        need(f'{kind} key', set(props) - {'probe', 'field', 'window', 'at', 'agg', 'of', 'match', 'to_angle', 'to_axis'},
             num)
        sel = props.get('select', {}).get('$ref', '').rsplit('/', 1)[-1]
        if sel and sel != 'Select':
            need(f'{kind} select key', set(DEFS[sel]['properties']), num)
    obj = DEFS['ObjectsMeasure']['properties']
    if 'objects' in ks:     # the object select is documented with the kind that introduces it
        need('object select key', set(DEFS['Select']['properties']) | set(DEFS['Has']['properties']), ks['objects'][0])
    need('common key', {'window', 'at', 'agg', 'of', 'match', 'to_angle', 'to_axis'}, '2.1')
    need('agg', {v for s in obj['agg']['anyOf'] for v in s.get('enum', [])}, '2.1')
    need('of', set(obj['of']['enum']), '2.1')
    need('point key', {k for _, d in POINTS for k in DEFS[d]['properties']}, '2.13')
    need('near key', set(DEFS['Near']['properties']), '2.13')
    need('line key', set(DEFS['Line']['properties']), ks['drawn'][0] if 'drawn' in ks else '2.19')
    need('threshold', {k for _, d in EXPECTS for k in DEFS[d]['properties']}, '1.2')
    need('op', set(DEFS['Value']['properties']['op']['enum']), '1.2')
    need('task play key', set(DEFS['TaskPlay']['properties']), '1.1')
    need('input key', {k for d in ('Key', 'Axis', 'Click', 'Cursor', 'Teleport', 'TeleportTo', 'Wait')
                       for k in DEFS[d]['properties']}, '1.1')
    need('play', {v for s in DEFS['Probe']['properties']['play']['anyOf'] for v in s.get('enum', [])}, '1.1')
    need('check key', set(DEFS['Probe']['properties']), '1')
    return out


def unknown_kinds(text):
    """The kinds docs/task-probes.md gives a section the schema has no measure for."""
    return sorted(set(kind_sections(text)) - set(kinds()))


def schema_words():
    """Every name the task schema has: its keys, the values of its enums and constants, each measure's field names
    and prefixes ("prop:")."""
    out = set()

    def walk(node):
        if isinstance(node, dict):
            out.update(node['properties'] if isinstance(node.get('properties'), dict) else ())
            out.update(v for v in node.get('enum', ()) if isinstance(v, str))
            out.update([node['const']] if isinstance(node.get('const'), str) else ())
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(TASK)
    for name in kinds().values():
        props = DEFS[name]['properties']
        out |= field_words(props.get('field') or props['fact'])
    return out


# The words docs/task-probes.md writes in code that are no part of the task format, each for a reason. A word that is
# neither the schema's nor here is a field or key the page documents and the schema lacks.
LOGGED = (  # keys and values of probe.json's samples, which the page names "for the logs": no check reads them
    'query_errors', 'total', 'full', 'class', 'glow_sources', 'glow_read', 'props', 'render', 'bound', 'unread',
    'emissive', 'unlit', 'local', 'directional', 'sky', 'lights', 'pixels', 'size', 'primitives', 'points', 'loudest',
    'peak', 'listener', 'source', 'ugui', 'uitk', 'ocr', 'camera_stack', 'post_processing', 'grading_mode', 'ldr',
    'hdr', 'pipeline', 'hue_shift', 'sun', 'fog', 'mode')
NOT_OURS = ('true', 'false', 'null',        # JSON's own words
            'materials',                    # Unity's Renderer.materials, which a prop: reads as sharedMaterials
            'display', 'visibility',        # UI Toolkit style properties ("display: none")
            'h:mm:ss', 'm:ss')              # the forms of a clock on screen


def unknown_names(text):
    """[(section, word)] for the names docs/task-probes.md gives in code, in the sections that document measures
    (2.1 common fields, 2.13 points, and each kind's), that the task schema doesn't have: a single lower-case word, a
    `prefix:` form, or a `key: value`. Per kind this holds a field to the schema as a whole, not to that kind: a field
    of another kind named in a section passes here, and is caught where an example uses it."""
    known = schema_words() | set(LOGGED) | set(NOT_OURS)
    prefixes = {w for w in known if w.endswith(':')}
    known |= {w[:-1] for w in prefixes}             # `world_pitch` names the fields `world_pitch:<Part>`
    secs, out = sections(text), []
    for num in sorted({n for n, _ in kind_sections(text).values()} | ({'2.1', '2.13'} & set(secs)),
                      key=lambda n: [int(x) for x in n.split('.')]):
        for _, code in spans(secs[num][2]):
            word = re.match(r'[a-z][a-z0-9_]*', code)
            if not word or code in known:
                continue
            w, rest = word.group(0), code[word.end():]
            if rest == '':
                ok = w in known or (w.endswith('_') and any(k.startswith(w) for k in known))
            elif rest.startswith(': '):
                ok = w in known                     # `inactive: true`
            elif rest.startswith(':'):
                ok = w + ':' in prefixes            # `prop:Health.current`
            else:
                continue                            # not a name alone: a path, a sentence, JSON
            if not ok:
                out.append((num, code))
    return out


# ---- D. a skill's frontmatter -----------------------------------------------------------------------------------------
def frontmatter_problems(folder, text):
    m = re.match(r'---\n(.*?)\n---\n', text, re.S)
    if not m:
        return ['no frontmatter between two "---" lines at the top']
    rows = m.group(1).split('\n')
    keys = [r.split(':', 1)[0] for r in rows]
    out = [] if keys == ['name', 'description'] else [f'keys {keys}: a skill has name, then description, nothing else']
    name = rows[0].split(':', 1)[1].strip() if rows else ''
    if name != folder:
        out.append(f'name {name!r} is not its folder {folder!r}')
    d = rows[1].split(':', 1)[1].strip() if len(rows) > 1 else ''
    if not re.fullmatch(r"'(?:[^']|'')*'", d):
        out.append("description is not one single-quoted YAML scalar on one line (a quote inside it is written '')")
    elif len(d[1:-1].replace("''", "'")) > 1024:
        out.append(f'description is {len(d[1:-1].replace(chr(39) * 2, chr(39)))} characters, more than 1024')
    return out


# ---- E. the files the probe and the checker exchange (CONTRACT.md section 5) -----------------------------------------
UNITY_PY = 'tools/task_check/unity.py'
PROBE_CORE = 'tools/task_check/TaskProbe/Runtime/Core/'
PROBE_CS = PROBE_CORE + 'Probe.cs'
READS_FLAG = {'-taskProbe': PROBE_CS, '-taskProbeBuild': 'tools/task_check/TaskProbe/Editor/Build.cs',
              '-taskProbeAssets': 'tools/task_check/TaskProbe/Editor/AssetPass.cs'}
LOG_LINE = re.compile(r'\d+\.\d\d \[\d+\.\d s\] (.*)')      # Probe.Log: the play time, the real time, the message
EXCHANGED_FILES = ('play spec', 'probe.json', 'probe.log', 'player command line', 'build command line',
                   'build request', 'build result', 'editor-pass command line', 'editor-pass request',
                   'editor-pass result')


def written(function=None):
    """What a function of tools/task_check/unity.py spells out: ([the keys of each dict], its flags, its files); with
    no function, the whole module (a file's name may be a constant of the module)."""
    node = ast.parse(read(UNITY_PY))
    if function:
        node = next(n for n in ast.walk(node) if isinstance(n, ast.FunctionDef) and n.name == function)
    words = [n.value for n in ast.walk(node) if isinstance(n, ast.Constant) and isinstance(n.value, str)]
    dicts = [[k.value for k in d.keys if isinstance(k, ast.Constant)] for d in ast.walk(node) if isinstance(d, ast.Dict)]
    return dicts, {w for w in words if w.startswith('-')}, {w for w in words if w.endswith(('.json', '.log'))}


def measures_of(query):
    """Measures that read a query of a play spec: what the checker's plan turns back into that query. One that reads
    rows takes the first match's own value, a text as 1, so a row without the field reads as no value."""
    kind, fields = query.get('kind'), query.get('fields')
    if kind == 'ui' and fields == sorted(probes.UI_SIGNED):
        fields = probes.UI_WHOLE[:1]        # a field read over everything the select picks asks for all of these
    rest = {k: v for k, v in query.items() if k not in ('id', 'kind', 'fields')}
    if kind in ('objects', 'components', 'widgets', 'ui'):
        rest.update(of='first', match='')
    return [{'probe': kind, **rest, 'field': f} for f in fields or ['count']]


def task_of(measures, play):
    """A task whose probes read `measures` in `play`: as much of one as probes.plan and probes.editor_items read."""
    return {'milestones': [{'name': 'm', 'checks': [{'name': f'c{i}', 'kind': 'probe', 'play': play, 'measure': m}
                                                  for i, m in enumerate(measures)]}]}


def spec_problems(spec):
    """Why a play spec is not what unity.Project.play writes for queries probes.plan makes."""
    out = []
    keys = next(d for d in written('play')[0] if 'out' in d)
    if list(spec) != keys:
        out.append(f'its keys are {list(spec)}; unity.Project.play writes {keys}')
    if spec.get('format') != unity.SPEC_FORMAT:
        out.append(f'its format is not {unity.SPEC_FORMAT}')
    asked = spec.get('queries') if isinstance(spec.get('queries'), dict) else {}
    queries = asked.get('queries') if isinstance(asked.get('queries'), list) else []
    whole = probes.query_file(queries, spec.get('every')) or {**probes.query_file([None], spec.get('every')), 'queries': []}
    if json.dumps(asked) != json.dumps(whole):
        out.append(f'its `queries` are not as probes.query_file writes them: {json.dumps({**whole, "queries": "..."})}')
    if spec.get('sound') is not probes.hears(queries):
        out.append(f'`sound` is {json.dumps(spec.get("sound"))}; probes.hears says {json.dumps(probes.hears(queries))}')
    try:
        plan = probes.plan(task_of([m for q in queries for m in measures_of(q)], {'name': 'p', 'seconds': 1})).get('p', [])
        rows = tasks.inputs(spec.get('inputs'))
    except (KeyError, TypeError, AttributeError, ValueError) as e:
        return out + [f'the checker cannot make its queries or inputs ({type(e).__name__}: {e})']
    if json.dumps(queries) != json.dumps(plan):
        out.append(f'its queries are not as probes.plan makes them (ids, keys, sorted fields, order): {json.dumps(plan)}')
    if json.dumps(spec.get('inputs')) != json.dumps(rows):
        out.append(f'its inputs are not as tasks.inputs writes them: {json.dumps(rows)}')
    return out


def finish_writes():
    """(the keys Probe.Finish always writes, in order; those it writes when there is something; its format; the
    endings it is called with)."""
    source = read(PROBE_CS)
    body = source[source.index('void Finish('):]
    body = body[:body.index('WriteAllText')]
    fmt = re.search(r'\["format"\]\s*=\s*"([^"]+)"', body)
    return (re.findall(r'(?<!result)\["(\w+)"\]\s*=', body), re.findall(r'result\["(\w+)"\]\s*=', body),
            fmt and fmt.group(1), set(re.findall(r'\bFinish\("(\w+)"', source)))


def probe_json_problems(found, spec=None):
    """Why a probe.json is not what the probe writes and the checker reads; with the play's spec, also why it does
    not answer that spec's queries."""
    always, sometimes, fmt, endings = finish_writes()
    out = [f'Probe.Finish writes no key "{k}"' for k in found if k not in always + sometimes]
    if [k for k in found if k in always] != always:
        out.append(f'its keys are {list(found)}; Probe.Finish always writes {always}, in that order')
    if found.get('format') != fmt:
        out.append(f'its format is not {fmt}')
    if found.get('ended') not in endings:
        out.append(f'`ended` is {json.dumps(found.get("ended"))}, not one of {sorted(endings)}')

    def number(v):
        return isinstance(v, (int, float)) and not isinstance(v, bool)

    for name, widths in (('track', (1, 4)), ('camera', (7,))):
        rows = found.get(name)
        if not isinstance(rows, list) or not all(isinstance(r, list) and len(r) in widths and all(map(number, r))
                                                 for r in rows):
            out.append(f'`{name}` is not rows of {" or ".join(map(str, widths))} numbers')
    measures = found.get('measures') if isinstance(found.get('measures'), dict) else {}
    for qid, samples in measures.items():
        if not isinstance(samples, list) or not all(isinstance(s, dict) and number(s.get('t')) and
                                                    not ('rows' in s and 'value' in s) for s in samples):
            out.append(f'{qid}: not a list of samples, each with its `t` and `rows` or `value`')
    if spec is not None:
        queries = (spec.get('queries') or {}).get('queries') or []
        ids = sorted(q.get('id') for q in queries)
        if sorted(measures) != ids:
            out.append(f'its measures are of {sorted(measures)}; the play spec asks for {ids}')
        for m in [m for q in queries for m in measures_of(q)]:
            try:
                value, why = probes.measured(tasks.measure(m), found)
            except (KeyError, TypeError, AttributeError, ValueError) as e:
                value, why = None, f'{type(e).__name__}: {e}'
            if value is None:
                out.append(f'the checker reads no value for {json.dumps(m)} from it: {why}')
    return out


def build_request_problems(found):
    keys = next(d for d in written('build')[0] if 'out' in d)
    return [] if list(found) == keys else [f'its keys are {list(found)}; unity.Project.build writes {keys}']


def build_result_problems(found):
    """What the checker reads of a build's result (unity.Project.build, check.py): `ok`, `error`, `missing`."""
    out = [] if isinstance(found.get('ok'), bool) else ['`ok` is not true or false']
    if found.get('ok') is True and found.get('error') is not None:
        out.append('`ok` is true and it has an `error`')
    if not isinstance(found.get('missing'), dict):
        out.append('`missing` is not an object')
    return out


def editor_request_problems(found):
    """Why an editor-pass request is not what probes.editor_request and unity.Project.editor_assets write."""
    keys = list(probes.editor_request([], '')) + next(d for d in written('editor_assets')[0] if d)
    out = [] if list(found) == keys else [f'its keys are {list(found)}; the checker writes {keys}']
    if not re.fullmatch(r'[0-9a-f]{32}', str(found.get('nonce'))):
        out.append('its nonce is not 32 hex digits (secrets.token_hex(16))')
    measures = found.get('measures') if isinstance(found.get('measures'), dict) else {}
    for mid, m in measures.items():
        out += [f'{mid}: {p}' for p in measure_problems(m)]
    try:
        items = dict(probes.editor_items(task_of(list(measures.values()), 'editor')))
    except (KeyError, TypeError, AttributeError, ValueError) as e:
        return out + [f'the checker cannot make its measures ({type(e).__name__}: {e})']
    if json.dumps(measures) != json.dumps(items):
        out.append(f'its measures are not as probes.editor_items makes them (ids, set fields, order): {json.dumps(items)}')
    return out


def editor_result_problems(text, request):
    """Why the checker's reader (probes.editor_results, probes.reduce_asset) gets no number for each measure of
    `request` from an editor pass's result."""
    measures = request.get('measures') if isinstance(request.get('measures'), dict) else {}
    found = probes.editor_results(text, request.get('nonce'))
    if found is None:
        return ["probes.editor_results reads nothing from it with the request's nonce"]
    out = [] if sorted(found) == sorted(measures) else [f'it answers {sorted(found)}; the request asks {sorted(measures)}']
    for mid in sorted(set(found) & set(measures)):
        try:
            value, why = probes.reduce_asset(tasks.measure(measures[mid]), found[mid])
        except (KeyError, TypeError, AttributeError, ValueError) as e:
            value, why = None, f'{type(e).__name__}: {e}'
        if value is None:
            out.append(f'{mid}: the checker reads no number from it: {why}')
    return out


def log_problems(block, core):
    """Why a block is not probe.log: each line in Probe.Log's form, its message one a file of `core` (the text of the
    probe's Runtime/Core sources) writes, known by its words up to the first colon, number, name or bracket."""
    out = []
    for row in block.strip('\n').split('\n'):
        m = LOG_LINE.fullmatch(row)
        if not m:
            out.append(f'"{row[:70]}" is not a probe.log line: <play time> [<real time> s] <message>')
            continue
        lead = re.match(r'[^0-9(A-Z:]*:? ?', m.group(1)).group(0)
        if len(lead) < 5 or f'"{lead}' not in core:
            out.append(f'no source under {PROBE_CORE} writes a line that starts "{lead}"')
    return out


def command_problems(block):
    """(which job a command line starts, why it is not the one unity.py starts): its flags, its method, its window
    and the files it names against unity.py, and its own flag against the C# that reads it."""
    text = ' '.join(block.split())
    if unity.PLAYER in text:
        job, parts = 'player command line', ('play',)
    elif unity.BUILD_METHOD in text:
        job, parts = 'build command line', ('_batch', 'build')
    elif unity.ASSETS_METHOD in text:
        job, parts = 'editor-pass command line', ('_batch', 'editor_assets')
    else:
        return 'command line', [f'it starts neither the player ({unity.PLAYER}), the build ({unity.BUILD_METHOD}) nor '
                                f'the editor pass ({unity.ASSETS_METHOD})']
    flags, files = set(), written()[2]
    for part in parts:
        flags |= written(part)[1]
    shown = set(re.findall(r'(?<!\S)-[A-Za-z][\w-]*', text))
    out = [] if shown == flags else [f'its flags are {sorted(shown)}; unity.py passes {sorted(flags)}']
    out += [f'unity.py names no file {f}' for f in sorted(set(re.findall(r'\b[\w.]+\.(?:json|log)\b', text)) - files)]
    if job == 'player command line' and not all(f'-screen-{side} {n}' in text
                                                for side, n in zip(('width', 'height'), unity.SHOT_SIZE)):
        out.append(f'its window is not unity.SHOT_SIZE, {unity.SHOT_SIZE}')
    for flag in sorted(f for f in shown if f.lower().startswith('-taskprobe')):
        if f'"{flag}"' not in read(READS_FLAG.get(flag, PROBE_CS)):
            out.append(f'{READS_FLAG.get(flag, PROBE_CS)} looks for no {flag}')
    return job, out


def exchange_problems(text):
    """[(line, what, problem)] for section 5 of CONTRACT.md: every block one of the files the probe and the checker
    exchange or one of the three command lines, each of them shown once, as the code writes and reads it."""
    _, start, body = sections(text).get('5', ('', 1, ''))
    out, seen = [], {}

    def note(what, line, value):
        if what in seen:
            out.append((line, what, f'shown a second time (first at line {seen[what][0]})'))
        seen.setdefault(what, (line, value))

    for lang, line, block in fences(body):
        line += start - 1
        if lang == 'json':
            try:
                v = json.loads(block)
            except ValueError as e:
                out.append((line, block.strip()[:60], f'not JSON ({e}): section 5 shows these files as they are written'))
                continue
            what = None if not isinstance(v, dict) else \
                'play spec' if 'queries' in v else 'probe.json' if 'track' in v else 'build result' if 'ok' in v else \
                'editor-pass request' if 'nonce' in v and 'result' in v else 'editor-pass result' if 'nonce' in v else \
                'build request' if 'scenes' in v else None
            if what is None:
                out.append((line, block.strip()[:60], 'none of the files of section 5: ' + ', '.join(EXCHANGED_FILES)))
            else:
                note(what, line, (v, block))
        elif LOG_LINE.match(block.lstrip('\n')):
            note('probe.log', line, block)
        else:
            job, problems = command_problems(block)
            note(job, line, block)
            out += [(line, job, p) for p in problems]
    lacking = [w for w in EXCHANGED_FILES if w not in seen]
    if lacking:
        out.append((start, 'section 5', 'no example of ' + ', '.join(lacking)))

    def held(what, problems, *needs):
        if what in seen and all(n in seen for n in needs):
            out.extend((seen[what][0], what, p) for p in problems(*[seen[n][1] for n in (what,) + needs]))

    held('play spec', lambda spec: spec_problems(spec[0]))
    held('probe.json', lambda probe, spec: probe_json_problems(probe[0], spec[0]), 'play spec')
    held('probe.log', lambda log: log_problems(log, ''.join(read(f) for f in tracked()
                                                             if f.startswith(PROBE_CORE) and f.endswith('.cs'))))
    held('build request', lambda asked: build_request_problems(asked[0]))
    held('build result', lambda result: build_result_problems(result[0]))
    held('editor-pass request', lambda asked: editor_request_problems(asked[0]))
    held('editor-pass result', lambda result, asked: editor_result_problems(result[1], asked[0]), 'editor-pass request')
    return sorted(out, key=lambda p: p[0])


# ---- the documents ------------------------------------------------------------------------------------------------------
def show(rel, problems):
    return '\n' + '\n'.join(f'  {rel}:{line}: {str(what)[:160]}\n      {problem}' for line, what, problem in problems)


class Examples(unittest.TestCase):
    """A. Every JSON example of the six documents is valid: a task against the schema and the validator's rules, a
    fragment against its definition, a measure also against the rules for measures."""

    def test_examples(self):
        for rel in DOCS:
            with self.subTest(doc=rel):
                problems = example_problems(read(rel))
                self.assertFalse(problems, show(rel, problems))


class Paths(unittest.TestCase):
    """B. Every relative link, repo path, option and section reference leads somewhere."""

    @classmethod
    def setUpClass(cls):
        cls.files = set(tracked())
        cls.cache = {}

    def text(self, rel):
        if rel not in self.cache:
            self.cache[rel] = read(rel) if os.path.isfile(os.path.join(REPO, rel)) else ''
        return self.cache[rel]

    def test_links(self):
        """Every tracked markdown file: a broken link anywhere misleads a reader."""
        for rel in sorted(f for f in self.files if f.endswith('.md')):
            with self.subTest(doc=rel):
                problems = link_problems(rel, self.text(rel), self.files, lambda d: anchors(self.text(d)))
                self.assertFalse(problems, show(rel, problems))

    def test_paths(self):
        for rel in DOCS:
            with self.subTest(doc=rel):
                text = self.text(rel)
                # CONTRACT.md's first table maps the original's names to Unity's: its left column is the original's
                table = sections(text).get('1', ('', 0, ''))[2] if rel == CONTRACT else ''
                left = {row.split('|')[1] for row in table.split('\n') if row.startswith('|')}
                problems = path_problems(text, self.files, lambda line, name: any(name in cell for cell in left))
                self.assertFalse(problems, show(rel, problems))

    def test_options(self):
        """A document shows only options its tool has, and the tool's own document shows them all."""
        for tool, (owner, source, prog) in TOOLS_WITH_OPTIONS.items():
            have = options_of(self.text(source), prog)
            with self.subTest(tool=tool):
                self.assertTrue(have, f'no options found for {tool} in {source}')
                for rel in DOCS:
                    problems = option_problems(self.text(rel), tool, have)
                    self.assertFalse(problems, show(rel, problems))
                shown = set(OPTION.findall(self.text(owner)))
                self.assertFalse(have - shown, f'{owner} never shows {sorted(have - shown)} of {tool}')

    def test_section_references(self):
        for rel in DOCS:
            with self.subTest(doc=rel):
                problems = section_ref_problems(rel, self.text(rel), lambda d: sections(self.text(d)))
                self.assertFalse(problems, show(rel, problems))


class SchemaAndProbes(unittest.TestCase):
    """C. docs/task-probes.md and the task schema document the same things."""

    def test_schema_is_documented(self):
        missing = undocumented(read(PROBES))
        self.assertFalse(missing, '\n' + '\n'.join(f'  {PROBES}: {what} `{word}` of the schema is not named in {where}'
                                                   for what, word, where in missing))

    def test_documented_kinds_exist(self):
        self.assertEqual(unknown_kinds(read(PROBES)), [], 'sections of docs/task-probes.md for kinds the schema lacks')

    def test_documented_names_exist(self):
        """The reverse: a field or key the page names in code is the schema's, or a listed key of probe.json."""
        unknown = unknown_names(read(PROBES))
        self.assertFalse(unknown, '\n' + '\n'.join(
            f'  {PROBES} section {num}: `{word}` is no name of the task schema: correct it, or, when it is a key of '
            f'probe.json the page names for the logs, list it in LOGGED in tools/tests/test_docs.py'
            for num, word in unknown))

    def test_skill_names_every_kind(self):
        """The skill's section 5 is its index into task-probes.md."""
        body = sections(read(SKILL)).get('5', ('', 0, ''))[2]
        self.assertFalse(sorted(set(kinds()) - words(body)), f'{SKILL} section 5 names no measure of these kinds')


class Frontmatter(unittest.TestCase):
    """D. Each skill loads by its frontmatter."""

    def test_skills(self):
        for rel in sorted(f for f in tracked() if re.fullmatch(r'skills/[^/]+/SKILL\.md', f)):
            with self.subTest(skill=rel):
                self.assertEqual(frontmatter_problems(rel.split('/')[1], read(rel)), [])


class ExchangedFiles(unittest.TestCase):
    """E. CONTRACT.md section 5 shows the probe's and the checker's files and command lines as the code writes and
    reads them."""

    def test_exchanged_files(self):
        problems = exchange_problems(read(CONTRACT))
        self.assertFalse(problems, show(CONTRACT, problems))


class TheChecksCanFail(unittest.TestCase):
    """F. Each check, on a small document with one thing wrong."""

    def bad(self, text):
        return [p for _, _, p in example_problems(text)]

    def test_examples(self):
        good = ('```json\n{"probe": "player", "field": "y", "window": [3, 18], "agg": "min"}\n```\n'
                'a pattern `{"probe": "player", "field": "x|y|z|speed|moved", ...}` and `{"point": <Point>, "radius": m}`'
                ' and a key `<Keyboard>/w` in `{"t": 1.0, "key": "<Keyboard>/w", "press": true}`, `"weight": 0`')
        self.assertEqual(self.bad(good), [])
        self.assertTrue(self.bad('`{"probe": "player", "field": "x|y|height"}`'))            # one alternative wrong
        self.assertTrue(self.bad('`{"probe": "pawn", "field": "z"}`'))                       # no such kind
        self.assertTrue(self.bad('`{"probe": "objects", "select": {"class": "X"}, "field": "count"}`'))   # select key
        self.assertTrue(self.bad('`{"probe": "ground", "xz": [0, 0], "field": "range"}`'))   # a validator rule
        self.assertTrue(self.bad('`{"op": ">=", "calibrate": 2}`'))
        self.assertTrue(self.bad('`{"t": 1, "key": "W", "press": true}`'))                   # not a control path
        self.assertTrue(self.bad('`{"probe": "player", "field": "x" "y"}`'))                 # can't be expanded
        self.assertTrue(self.bad('`{"mystery": 1}`'))                                        # not recognised
        self.assertTrue(self.bad('`"weight": "heavy"`'))
        self.assertTrue(self.bad('`"wieght": 0`'))                                          # no schema has the key
        self.assertEqual(self.bad('`"origin": "studio"` in the assets manifest'), [])       # another schema's key
        # an example written out is read as it is: a string between two commas is no key left alone
        self.assertEqual(self.bad('`{"name": "aim", "seconds": 10, "args": ["-mode", "night", "fast"]}`'), [])
        self.assertEqual(self.bad('`{"probe": "log", "pattern": "first, then: second, third", "field": "count"}`'), [])
        self.assertTrue(self.bad('```json\n{"probe": "player", "field": "height"}\n```'))

    def test_sketches(self):
        """A snippet that leaves values out is held to its keys."""
        ok = ('`{"name": ..., "seconds": ..., "inputs": [{"t", "key", "press"}]}` `{"t": ..., "wait": seconds}` '
              '`{"point", "radius", "y_min", "y_max", "y_relative"}` `{"t", "key": "<Keyboard>/w", "press": true|false}`')
        self.assertEqual(self.bad(ok), [])
        self.assertTrue(self.bad('`{"name": ..., "seconds": ..., "map": ...}`'))             # the original's key
        self.assertTrue(self.bad('`{"name": ..., "seconds": ..., "inputs": [{"t", "button"}]}`'))
        self.assertTrue(self.bad('`{"point", "radius", "z_min"}`'))
        self.assertTrue(self.bad('`{"t", "wait": -1, "extra"}`'))
        self.assertEqual(self.bad('`{"teleport_to": {"has": {"simulating": true, "near": ...}}}`'), [])   # no time
        self.assertTrue(self.bad('`{"teleport_to": {"has": {"shovable": true}}}`'))
        self.assertTrue(self.bad('`{"scenes": ["Assets/X.unity"], "exe": "Game.exe"}`'))     # not one of their files
        self.assertEqual(self.bad('`"name": "<wildcard>"` and `"window": [t0, t1]`'), [])    # members, as patterns
        judge = '`{"name": ..., "kind": "actions_judge", "question": ..., "rubric": [{"key": ..., "criterion": ...}]}`'
        self.assertEqual(self.bad(judge), [])
        self.assertTrue(self.bad(judge.replace('criterion', 'criteria')))
        self.assertTrue(self.bad(judge.replace('"question"', '"ask"')))
        self.assertTrue(self.bad('`{"probe": "spawns", "component": "<type>", "field": "spawned|gone"}`'))

    def test_exchanged_files(self):
        """The probe's and the checker's own files are told apart from task JSON, not held to its schema."""
        self.assertEqual(self.bad('`{"format": "unity-probe/1", "track": [[t, x, y, z]], "anything": [ ... rows ... ]}`'), [])
        self.assertEqual(self.bad('`{"nonce": "...", "measures": {"a<id>": {"value": v} | {"error": "..."}}}`'), [])

    def test_section_5(self):
        """Part E: a play, a build and an editor pass as the checker's own functions write them pass; each with one
        thing changed does not."""
        play = {'name': 'p', 'seconds': 8, 'inputs': [{'t': 2, 'wait': 2}, {'t': 4, 'key': '<Keyboard>/e', 'press': 1}]}
        lamp = {'probe': 'objects', 'select': {'name': 'Lamp'}, 'field': 'lit'}
        queries = probes.plan(task_of([lamp, {**lamp, 'field': 'glow'}], play))['p']
        spec = {'format': unity.SPEC_FORMAT, 'out': 'C:/c/Logs/TaskProbe/play', 'seconds': 8, 'shots': 2, 'every': 0.5,
                'scene': None, 'sound': False, 'player': None, 'inputs': tasks.inputs(play['inputs']),
                'queries': probes.query_file(queries)}

        def but(value, *path, to):
            """`value` with what is at `path` changed to `to` (dropped when `to` is this function itself)."""
            out = copy.deepcopy(value)
            node = out
            for step in path[:-1]:
                node = node[step]
            if to is but:
                del node[path[-1]]
            else:
                node[path[-1]] = to
            return out

        first = ('queries', 'queries', 0)
        self.assertEqual(spec_problems(spec), [])
        self.assertTrue(spec_problems({('map' if k == 'scene' else k): v for k, v in spec.items()}))    # another key
        self.assertTrue(spec_problems(but(spec, 'format', to='unity-probe-play/2')))
        self.assertTrue(spec_problems(but(spec, 'queries', 'format', to='game-probe-queries/2')))
        self.assertTrue(spec_problems(but(spec, *first, 'id', to='q0000000000')))                      # not its hash
        self.assertTrue(spec_problems(but(spec, *first, 'fields', to=['lit', 'glow'])))                # not sorted
        self.assertTrue(spec_problems(but(spec, *first, 'select', to=but)))                            # a key missing
        self.assertTrue(spec_problems(but(spec, 'inputs', to=play['inputs'])))                         # the task's own
        self.assertTrue(spec_problems(but(spec, 'sound', to=True)))                                    # no audio query

        probe = {'format': 'unity-probe/1', 'ended': 'time', 'seconds': 8.5, 'scene': 'Assets/A.unity', 'player': 'Hero',
                 'inputs_sent': 2, 'screenshots': [], 'track': [[0.5, 0, 1, 0], [1.0]],
                 'camera': [[0.5, 0, 1, 0, 10, -90, 55]],
                 'measures': {queries[0]['id']: [{'t': 0.5, 'rows': [{'name': 'Lamp', 'lit': 1, 'glow': 2.5}]}]}}
        sample = ('measures', queries[0]['id'], 0)
        self.assertEqual(probe_json_problems(probe, spec), [])
        self.assertTrue(probe_json_problems({**probe, 'map': '/Game/A'}, spec))                        # the original's key
        self.assertTrue(probe_json_problems(but(probe, 'player', to=but), spec))                       # always written
        self.assertTrue(probe_json_problems(but(probe, 'format', to='game-probe/1'), spec))
        self.assertTrue(probe_json_problems(but(probe, 'ended', to='quit'), spec))
        self.assertTrue(probe_json_problems(but(probe, 'track', 0, to=[0.5, 0, 1]), spec))
        self.assertTrue(probe_json_problems(but(probe, 'camera', 0, to=[0.5, 0, 1, 0]), spec))
        self.assertTrue(probe_json_problems(but(probe, 'measures', to={'q0000000000': []}), spec))     # another play's
        self.assertTrue(probe_json_problems(but(probe, *sample, 'rows', 0, to={'name': 'Lamp', 'lit': 1, 'glw': 2}), spec))
        self.assertTrue(probe_json_problems(but(probe, *sample, 'value', to=None), spec))              # rows and value
        self.assertTrue(probe_json_problems(but(probe, *sample, 't', to=but), spec))

        bulb = {'probe': 'asset', 'asset': 'Assets/M.mat', 'field': 'keyword:_EMISSION'}
        asked = {**probes.editor_request(probes.editor_items(task_of([bulb], 'editor')), 'ab' * 16),
                 'result': 'C:/c/Logs/TaskProbe/probes_editor.json'}
        aid = next(iter(asked['measures']))
        self.assertEqual(editor_request_problems(asked), [])
        self.assertTrue(editor_request_problems(but(asked, 'nonce', to='a nonce')))
        self.assertTrue(editor_request_problems(but(asked, 'result', to=but)))
        self.assertTrue(editor_request_problems(but(asked, 'measures', to={'a0000000000': asked['measures'][aid]})))
        self.assertTrue(editor_request_problems(but(asked, 'measures', aid, to=bulb)))                 # the task's own
        self.assertTrue(editor_request_problems(but(asked, 'measures', aid, 'field', to='keyword')))   # no such field
        result = {'measures': {aid: {'value': 1}}, 'nonce': 'ab' * 16}
        self.assertEqual(editor_result_problems(json.dumps(result), asked), [])
        self.assertTrue(editor_result_problems(json.dumps(but(result, 'nonce', to='cd' * 16)), asked))
        self.assertTrue(editor_result_problems(json.dumps(but(result, 'measures', to={})), asked))
        self.assertTrue(editor_result_problems(json.dumps(but(result, 'measures', aid, to={'error': 'no asset'})), asked))
        self.assertTrue(editor_result_problems(json.dumps(but(result, 'measures', aid, to={'value': 'on'})), asked))

        build = {'out': 'C:/c/Build/TaskProbe', 'scenes': [], 'result': 'C:/c/Logs/TaskProbe/build.json'}
        built = {'ok': True, 'scenes': ['Assets/A.unity'], 'missing': {}}
        self.assertEqual(build_request_problems(build) + build_result_problems(built), [])
        self.assertTrue(build_request_problems({'out': 'C:/c/Build/TaskProbe', 'maps': [], 'result': 'C:/c/b.json'}))
        self.assertTrue(build_result_problems(but(built, 'ok', to='yes')))
        self.assertTrue(build_result_problems({**built, 'error': 'the player build failed'}))
        self.assertTrue(build_result_problems(but(built, 'missing', to=[])))

        core = 'Log("the play ended: " + reason); Probe.Log("teleported next to " + name);'
        log = '0.00 [0.2 s] teleported next to Lamp_1: asked (1.00, 0.00, 2.00)\n10.53 [12.9 s] the play ended: time'
        self.assertEqual(log_problems(log, core), [])
        self.assertTrue(log_problems('10.53 the play ended: time', core))                              # no real time
        self.assertTrue(log_problems('10.53 [12.9 s] the game ended: time', core))                     # no such line
        self.assertTrue(log_problems('1.00 [3.3 s] teleported beside Lamp_1', core))

        logs = '<copy>\\Logs\\TaskProbe\\'
        player = ('python desk.py <copy>\\Build\\TaskProbe\\Game.exe -screen-fullscreen 0 -screen-width 960\n'
                  f'    -screen-height 540 -logFile {logs}play.log -taskProbe {logs}play_spec.json <play args...>')
        batch = f'<Unity.exe> -batchmode -nographics -quit -projectPath <copy> -logFile {logs}'
        builds = f'{batch}build.log\n    -executeMethod {unity.BUILD_METHOD} -taskProbeBuild {logs}build_request.json'
        passes = f'{batch}editor.log -executeMethod {unity.ASSETS_METHOD} -taskProbeAssets {logs}probes_editor_request.json'
        self.assertEqual(command_problems(player), ('player command line', []))
        self.assertEqual(command_problems(builds), ('build command line', []))
        self.assertEqual(command_problems(passes), ('editor-pass command line', []))
        self.assertTrue(command_problems(player.replace('-taskProbe ', '-TaskProbeSpec '))[1])         # the original's
        self.assertTrue(command_problems(player.replace('960', '1280'))[1])
        self.assertTrue(command_problems(player.replace('play.log', 'game.log'))[1])
        self.assertTrue(command_problems(player + ' -popupwindow')[1])
        self.assertTrue(command_problems(builds.replace(' -quit', ''))[1])
        self.assertTrue(command_problems(builds.replace('-taskProbeBuild', '-taskProbeAssets'))[1])
        self.assertTrue(command_problems(passes.replace('AssetPass.Run', 'AssetPass.Start'))[1])       # no such job

        def page(*blocks):
            return '## 5. Files\n' + ''.join('```%s\n%s\n```\n' % (('', b) if isinstance(b, str) else ('json', json.dumps(b)))
                                             for b in blocks)

        whole = (spec, probe, '0.00 [0.2 s] the play ended: time', player, builds, build, built, passes, asked, result)
        self.assertEqual(exchange_problems(page(*whole)), [])
        self.assertTrue(exchange_problems(page(*whole[:2], *whole[3:])))                               # one not shown
        self.assertTrue(exchange_problems(page(*whole, build)))                                        # one shown twice
        self.assertTrue(exchange_problems(page(*whole, {'weather': 'fine'})))                          # none of them
        self.assertTrue(exchange_problems(page(*whole) + '```json\n{"nonce": ...}\n```\n'))            # not JSON
        self.assertTrue(exchange_problems(page(but(spec, 'shots', to=but), *whole[1:])))               # one of them wrong
        self.assertTrue(exchange_problems(page(*whole[:9], but(result, 'nonce', to='cd' * 16))))

    def test_whole_task(self):
        t = {'name': 'kiln-run-fix-x', 'title': 'x', 'instruction': 'x', 'difficulty': 'medium', 'tags': ['long-thread'],
             'seed': {'game': 'kiln-run', 'kind': 'bug_fix', 'commit': 'a' * 40, 'reference': 'b' * 40},
             'milestones': [{'name': 'fixed', 'checks': [
                 {'name': f'p{i}', 'kind': 'probe', 'describe': 'x', 'play': 'look',
                  'measure': {'probe': 'player', 'field': 'y'}, 'expect': {'op': '>=', 'value': 1}} for i in range(3)]}]}
        self.assertEqual(task_problems(t), [])
        t['milestones'][0]['checks'].pop()
        self.assertTrue(any('fewer than' in p for p in task_problems(t)))
        self.assertTrue(self.bad('```json\n%s\n```' % json.dumps(t)))

    def test_links(self):
        files = {'docs/a.md', 'docs/b.md', 'tools/x.py'}
        heads = lambda d: {'the-plays'}
        ok = '[b](b.md) [h](b.md#the-plays) [x](../tools/x.py) [web](https://example.com) [here](#the-plays)'
        self.assertEqual(link_problems('docs/a.md', ok, files, heads), [])
        self.assertTrue(link_problems('docs/a.md', '[c](c.md)', files, heads))
        self.assertTrue(link_problems('docs/a.md', '[b](b.md#nowhere)', files, heads))
        self.assertTrue(link_problems('docs/a.md', '[x](tools/x.py)', files, heads))          # relative to docs/

    def test_paths(self):
        files = {'tools/validate-game.py', 'docs/task-check.md', 'machine/tools/unity-heavy.ps1'}
        ok = ('run `tools\\validate-game.py`, read docs/task-check.md, `<UGF_ROOT>/unity-game-factory/tools/validate-game.py`,'
              ' the limiter unity-heavy.ps1; a game\'s `Scripts/unity.ps1` and `Assets/Scenes/X.unity` are not ours')
        self.assertEqual(path_problems(ok, files | {'templates/unity-game/Scripts/unity.ps1'}), [])
        self.assertTrue(path_problems('see `tools/validate-games.py`', files))
        self.assertTrue(path_problems('see %UGF_ROOT%\\unity-game-factory\\docs\\nothing.md', files))
        self.assertTrue(path_problems('run ue-heavy.ps1', files))

    def test_options(self):
        src = 'p = argparse.ArgumentParser(prog="a.py")\np.add_argument("--all")\np.add_argument("--x", help=argparse.SUPPRESS)\n'
        self.assertEqual(options_of(src), {'--all'})
        self.assertEqual(options_of(src + 'q = argparse.ArgumentParser(prog="b.py")\nq.add_argument("--runs")\n', 'b.py'),
                         {'--runs'})
        self.assertEqual(option_problems('python a.py --all', 'a.py', {'--all'}), [])
        self.assertTrue(option_problems('python a.py --every', 'a.py', {'--all'}))

    def test_section_references(self):
        nums = {'docs/a.md': {'1', '2.4'}, PROBES: {'1.1'}}
        refs = lambda text: section_ref_problems('docs/a.md', text, lambda d: nums.get(d, {}))
        self.assertEqual(refs('see section 2.4, and task-probes.md, section 1.1'), [])
        self.assertTrue(refs('see section 2.5'))
        self.assertTrue(refs('see task-probes.md, section 2.4'))

    def test_schema_is_documented(self):
        self.assertIn('prop:', field_words(DEFS['ObjectsMeasure']['properties']['field']))
        self.assertIn('extent_x', field_words(DEFS['ObjectsMeasure']['properties']['field']))
        self.assertEqual(field_words(DEFS['ScreenMeasure']['properties']['field']), {'luminance', 'luma'})
        page = '## 2. Measures\n### 2.15 `screen`: the frame\n`{"probe": "screen", "rect": [0, 0, 1, 1], "field": "luminance"}`\n'
        missing = undocumented(page)
        self.assertIn(('screen field', 'luma', 'section 2.15'), missing)
        self.assertNotIn(('screen field', 'luminance', 'section 2.15'), missing)
        self.assertIn(('probe kind', 'audio', 'a section "### 2.N `audio`: ..."'), missing)
        self.assertEqual(unknown_kinds('### 2.2 `pawn`: the player pawn\n'), ['pawn'])

    def test_documented_names_exist(self):
        page = ('### 2.4 `objects`: GameObjects\n`count`, `prop:Health.current`, `inactive: true`, `glow_read` (for '
                'the logs), `MeshRenderer`, `extent_`, `{"probe": "objects"}`, `bb:Speed`, `pawn_on_screen`, `visble`, '
                '`shown: true`\n### 3. Gates\n`anything`\n')
        self.assertEqual(unknown_names(page), [('2.4', 'bb:Speed'), ('2.4', 'pawn_on_screen'), ('2.4', 'visble'),
                                               ('2.4', 'shown: true')])

    def test_frontmatter(self):
        ok = "---\nname: a\ndescription: 'What it''s for. Use when writing.'\n---\n# A\n"
        self.assertEqual(frontmatter_problems('a', ok), [])
        self.assertTrue(frontmatter_problems('b', ok))
        self.assertTrue(frontmatter_problems('a', ok.replace("'What it''s", "What it's").replace("writing.'", 'writing.')))
        self.assertTrue(frontmatter_problems('a', ok.replace('---\n# A', 'model: x\n---\n# A')))
        self.assertTrue(frontmatter_problems('a', ok.replace('What', 'W' * 1100)))
        self.assertTrue(frontmatter_problems('a', '# A\n'))


if __name__ == '__main__':
    unittest.main()
