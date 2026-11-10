#!/usr/bin/env python3
"""Build a Unity game's dataset (unity-dataset-layout/v1, docs/game-format.md): <repo>/Dataset.pending.zip.

    python tools/package-dataset.py <slug>                      # the game at <root>/games/<slug>, its HEAD
    python tools/package-dataset.py <slug> --commit <rev> --version 1.0 --brief <brief.md> --design <design.md>
    python tools/package-dataset.py <slug> --dry-run            # what would go in; writes nothing

What it packs, from the game repo at the release commit, its recording (<root>/.recording/<slug>/) and its player
build (<repo>/Build/Windows, made with Scripts/unity.ps1 build; --build names another folder):

    History/<slug>.bundle     the history rewritten for delivery: authors and committers dev_NN, agent trailer lines
                              gone, the scrub rules on every message and text blob. The release commit as
                              refs/heads/main and each task's start branch (refs/heads/starts/<task>), nothing else:
                              a side branch, a tag off main or a stash can hold work the tasks ask for.
    History/lfs/objects/      every Git LFS object of every commit of the bundle, from the repo's own store
    History/sessions/         the creation sessions as recorded: messages.jsonl (every prompt the person typed and
                              every reply the model wrote) and actions.jsonl (every tool call), rows up to the release
                              commit, each session named session_NN in both
    git.log                   every commit of the delivered history up to the release, oldest first, with full diffs
    workflow.jsonl            the creation record at the release commit
    UnityProject/             the delivered tree at the release commit, LFS files as their real content (no Dataset/)
    Tasks/                    the tasks of the repo's tasks branch, seeds mapped to the delivered history, each split
                              into task.json and grader.json (tools/split-tasks.py), and a README.md
    Brief/                    brief.md and design.md (--brief / --design, else the places listed at find_brief)
    Screenshots/              the images the game's README.md shows
    Build/                    the Windows player, without .pdb files and Unity's "do not ship" folders
    README.md, manifest.json

Not packed yet: Gameplay/ and ReplayScripts/ (the recorder and the creation replay are not available yet). The manifest
lists both as pending, its status is "pending" and the zip is Dataset.pending.zip.

Every text file of the delivery is scrubbed (studio and tool names, agent, model and provider names, the account and
machine name, e-mail addresses, git identities, the build machine's session folders and ids) and then scanned: a name
left in a text file or a path refuses the package (exit 2, nothing zipped; the hits in <scratch>/<slug>.refused-hits.tsv).
Binary files are never changed: names found in them are listed in <scratch>/<slug>.binary-hits.tsv and reported, and
refuse the package only with --strict-binaries. Commit ids change with the rewrite: the delivery uses the new ids
everywhere, and <scratch>/<slug>.commit-map.tsv keeps original -> delivered.

It ends with the checks a consumer runs: tools/validate-game.py --dataset on the delivery (an error refuses the
package). Then it writes the zip and, unless --no-repo-dataset, the repo's Dataset/ folder (the delivery minus
UnityProject/, Build/, History/ and Tasks/) for the game session to commit. Nothing is committed here, and the game
repo's history is not changed. Scratch: <repo>/.dataset/ (git-ignored). Standard library, Python 3.10+, git, git-lfs.
"""
import argparse, base64, getpass, hashlib, importlib.util, json, os, re, shutil, socket, stat, subprocess, sys, time, zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, 'machine', 'lib'))
import ugfroot  # noqa: E402

LAYOUT = 'unity-dataset-layout/v1'
SECTIONS = ('Requirements', 'Package contents', 'Play the game', 'Replay the creation process',
            'Restore the git history', 'Tasks', 'Scenarios', 'Screenshots', 'Assets and licences', 'Integrity')
PENDING = ['ReplayScripts', 'Gameplay']   # entries no tool makes yet
UUID = r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}'
LFS_MAGIC = b'version https://git-lfs.github.com/spec/'
LFS_PTR = re.compile(rb'^version https://git-lfs\.github\.com/spec/v1\r?\noid sha256:([0-9a-f]{64})\r?\nsize ([0-9]+)')
IMAGE_EXT = ('.png', '.jpg', '.jpeg', '.webp')
# Formats that are binary whatever their first bytes say; everything else is text unless its first 8000 bytes hold a NUL.
BINARY_EXT = frozenset('''.png .jpg .jpeg .tga .psd .exr .hdr .bmp .tif .tiff .dds .ktx .ktx2 .gif .webp .ico .raw .r16 .r8
.fbx .obj .glb .gltf .abc .blend .max .ma .mb .3ds .dae .usd .usdc .usdz .ply .stl .spp .sbsar
.wav .ogg .mp3 .flac .aif .aiff .m4a .opus .wem .bank .bnk .mp4 .mov .mkv .webm .avi .bk2
.ttf .otf .ttc .woff .woff2 .zip .7z .rar .gz .tgz .tar .unitypackage .upack .pdf .xlsx .docx .pptx
.exe .dll .pdb .lib .so .dylib .a .bin .dat .ies .bytes .bundle .speedtree .assets .resource .ress'''.split())
STORED_EXT = frozenset('.png .jpg .jpeg .webp .mp4 .mov .mkv .webm .ogg .mp3 .flac .zip .7z .gz .unitypackage .bundle'.split())
NOT_SHIPPED_BUILD = re.compile(r'(?i)(_DoNotShip|_BackUpThisFolder_ButDontShipItWithYourGame)$')


class Refused(Exception):
    """The package cannot be made as things are; the message says what to fix."""


def step(msg):
    print(f'[{time.strftime("%H:%M:%S")}] {msg}', flush=True)


def lp(path):
    """A path Windows opens whatever its length (a Unity project's paths pass 260 characters once under a scratch folder)."""
    if os.name == 'nt':
        path = os.path.abspath(path)
        if not path.startswith('\\\\'):
            return '\\\\?\\' + path
    return path


def read_bytes(path):
    with open(lp(path), 'rb') as f:
        return f.read()


def write_bytes(path, data):
    os.makedirs(lp(os.path.dirname(path)), exist_ok=True)
    with open(lp(path), 'wb') as f:
        f.write(data)


def write_text(path, text):
    write_bytes(path, text.encode('utf-8'))


def copy_file(src, dst):
    os.makedirs(lp(os.path.dirname(dst)), exist_ok=True)
    shutil.copyfile(lp(src), lp(dst))


def remove_tree(path):
    """shutil.rmtree that also deletes read-only files: git writes its pack files read-only, and on Windows rmtree
    cannot delete those (the scratch's <slug>.history.git stayed behind and stopped the next run)."""
    def writable_then_again(func, p, _exc):
        os.chmod(p, stat.S_IWRITE)
        func(p)
    if os.path.isdir(lp(path)):
        shutil.rmtree(lp(path), onerror=writable_then_again)


def files_under(root):
    """Relative paths (forward slashes) of every file under root, sorted."""
    out = []
    base = lp(root)
    for d, _, fs in os.walk(base):
        for f in fs:
            out.append(os.path.relpath(os.path.join(d, f), base).replace('\\', '/'))
    return sorted(out)


def sha256_file(path):
    h = hashlib.sha256()
    with open(lp(path), 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def git(repo, *args, input=None, check=True):
    r = subprocess.run(['git', '-C', repo, '-c', 'core.quotepath=off', *args], capture_output=True, input=input)
    if check and r.returncode != 0:
        raise Refused(f'git {" ".join(args[:3])} failed in {repo}: {r.stderr.decode("utf-8", "replace").strip()[:400]}')
    return r.stdout


def git_text(repo, *args, check=True):
    return git(repo, *args, check=check).decode('utf-8', 'replace').strip()


class CatFile:
    """git cat-file --batch on one repo: blobs by id or <rev>:<path>."""
    def __init__(self, repo):
        self.p = subprocess.Popen(['git', '-C', repo, 'cat-file', '--batch'], stdin=subprocess.PIPE, stdout=subprocess.PIPE)

    def read(self, spec):
        """(type, bytes), or (None, None) when the object is missing."""
        self.p.stdin.write(spec.encode('utf-8') + b'\n')
        self.p.stdin.flush()
        head = self.p.stdout.readline().split()
        if len(head) < 3:
            return None, None
        size = int(head[2])
        data = self.p.stdout.read(size)
        self.p.stdout.read(1)
        return head[1].decode(), data

    def close(self):
        try:
            self.p.stdin.close()
            self.p.wait(15)
        except (OSError, subprocess.TimeoutExpired):
            self.p.kill()


def is_text(name, head):
    """A file is text by its name's extension, then by its first bytes (UTF-16 with a BOM counts as text)."""
    if os.path.splitext(name)[1].lower() in BINARY_EXT:
        return False
    if head[:2] in (b'\xff\xfe', b'\xfe\xff'):
        return True
    return b'\0' not in head[:8000]


def decode(data):
    """Text for the scrub and the scan: Latin-1 keeps every byte of UTF-8 as it is; UTF-16 by its BOM."""
    if data[:2] == b'\xff\xfe':
        return data.decode('utf-16-le', 'replace'), 'utf-16-le'
    if data[:2] == b'\xfe\xff':
        return data.decode('utf-16-be', 'replace'), 'utf-16-be'
    return data.decode('latin-1'), 'latin-1'


# ---- the scrub rules -----------------------------------------------------------------------------------------------------
# (id, scope, pattern, replacement, hint). Scopes: all | json (.json/.jsonl) | lines (other text) | logs (.json/.jsonl,
# git.log, History/sessions/). hint: lower-case text a file must hold for the rule to be tried. Applied in this order.
RULE_TEXT = {
    'base64-payload': 'base64 runs of 256+ characters in logs (screenshots and binary payloads in tool results) replaced by <base64 omitted, N bytes, sha256 ...>',
    'agent-trailer': 'agent co-author and generated-with trailer lines removed',
    'agent-identity': 'agent identity (name + no-reply address) replaced by a neutral dev identity',
    'banned-name': 'studio and tooling names replaced (studio, studio-tools)',
    'git-identity': 'git author and committer names and handles replaced by dev_NN',
    'session-path': "the build machine's per-session folders and session ids replaced by neutral names",
    'username': 'the account and machine name, including inside user paths, replaced by dev / dev-pc',
    'email': 'e-mail addresses (other than example ones) replaced by <redacted-email>',
    'agent-mention': 'remaining agent, model and provider mentions neutralised (agent, agent-tool, agent-model, provider)',
}
# the start of a word, also right after a JSON escape such as \n (whose letter would otherwise hide the boundary)
WORD_START = r'(?:(?<=\\[nrtfb])|(?<=\\u[0-9a-fA-F]{4})|(?<![A-Za-z0-9_]))'
EMAIL = (r'(?:(?<=\\u[0-9a-fA-F]{4})|(?<=\\[nrtfb"/])|(?<![A-Za-z0-9._%+\\-]))'
         r'(?!(?:git@(?:github|gitlab|bitbucket)\.(?:com|org)|noreply@github\.com)\b)'
         r'[A-Za-z0-9._%+-]+@(?!(?:[A-Za-z0-9-]+\.)*(?:example\.(?:com|org|net)|invalid|test|localhost)\b)(?:[A-Za-z0-9-]+\.)+'
         r'(?!(?:png|jpe?g|tga|gif|svg|webp|exr|hdr|bmp|dds|unity|prefab|mat|asset|meta|wav|ogg|mp3|flac|fbx|glb|gltf|obj|json|jsonl|txt|md|ini|py|ps1|sh|cs|bin|zip)\b)'
         r'[A-Za-z]{2,}\b')
TRAILER = re.compile(r'(?i)^\s*(Co-Authored-By:\s*(?:Claude|Codex|OpenAI|ChatGPT)\b|.*Generated with \[?(?:Claude Code|Codex)\b)')
# the word opus on its own, any case: the model's name in prose. Codec identifiers (libopus, opus_decode, audio/opus,
# AudioCodec.Opus, a .opus file) keep theirs.
OPUS_WORD = r'(?:(?<=\\u00[0-9a-fA-F]{2})|(?<=\\[nrtfb])|(?<![A-Za-z0-9_.-]))(?<!audio/)%s(?![A-Za-z0-9_.-]|/\d)'


def cased(lower, title, upper):
    def f(m):
        s = m.group(0)
        return upper if s.isupper() else title if s[:1].isupper() else lower
    return f


def tools_name(m):
    """game-factory / unity-game-factory in any spelling -> studio-tools in the same one (separator and case)."""
    sep = m.group('sep')
    s = m.group(0)
    a, b = ('STUDIO', 'TOOLS') if s.isupper() else ('Studio', 'Tools') if s[:1].isupper() else ('studio', 'tools')
    return a + sep + b


def base64_placeholder(m):
    b64 = m.group(0)
    try:
        data = base64.b64decode(b64[:len(b64) - len(b64) % 4], validate=True)
    except ValueError:
        data = b64.encode('ascii')
    return f'<base64 omitted, {len(data)} bytes, sha256 {hashlib.sha256(data).hexdigest()[:16]}>'


def session_folder(m):
    return m.group(1) + 'session' + (m.group(3) + 'scratch' if m.group(3) else '')


def build_rules(user, machine, session_ids, identities):
    """identities: [(term, dev_NN)], longest first."""
    R = []

    def add(rid, scope, pattern, rep, hint=''):
        R.append((rid, scope, re.compile(pattern), rep, hint))
    add('base64-payload', 'logs', r'(?<![A-Za-z0-9+/])[A-Za-z0-9+/]{256,}={0,2}(?![A-Za-z0-9+/=])', base64_placeholder)
    add('agent-trailer', 'lines', r'(?im)^[ \t]*Co-Authored-By:[ \t]*(?:Claude|Codex|OpenAI|ChatGPT)[^\r\n]*\r?\n?', '', 'co-authored-by')
    add('agent-trailer', 'lines', r'(?im)^[^\r\n]*Generated with \[?(?:Claude Code|Codex)\b[^\r\n]*\r?\n?', '', 'generated with')
    add('agent-trailer', 'json', r'(?i)(?:\\r)?(?:\\n)*Co-Authored-By:[ \t]*(?:Claude|Codex|OpenAI|ChatGPT)(?:[^"\\]|\\u003[cCeE])*', '', 'co-authored-by')
    add('agent-trailer', 'json', r'(?i)(?:(?:\\r)?(?:\\n)+|(?<="))(?:[^"\\]|\\u[0-9a-fA-F]{4})*?Generated with \[?(?:Claude Code|Codex)\b(?:[^"\\]|\\u003[cCeE])*', '', 'generated with')
    add('agent-identity', 'all', r'Claude \(agent\)', 'dev', 'claude')
    add('agent-identity', 'all', r'(?i)\bClaude(?: (?:Opus|Sonnet|Haiku|Fable)(?: [0-9.]+)?)?(?=[ ]*(?:<|\\u003[cC])noreply@anthropic\.com)', 'dev', 'anthropic')
    add('agent-identity', 'all', r'(?i)noreply@anthropic\.com', 'dev@example.invalid', 'anthropic')
    add('banned-name', 'all', r'(?i)superposition\.(?=[a-z0-9_-]+/v?\d)', '', 'superposition')
    add('banned-name', 'all', r'(?i)superposition', cased('studio', 'Studio', 'STUDIO'), 'superposition')
    add('banned-name', 'all', r'(?i)(?:unity[-_ ]?)?game(?P<sep>[-_ ]?)factory', tools_name, 'factory')
    for term, dev in identities:
        e = re.escape(term)
        # a term with a digit is a handle: it also takes the letters and digits glued to it (account names built on it)
        tail = '[A-Za-z0-9]*' if re.search(r'\d', term) and len(term) >= 5 else '(?![A-Za-z0-9])'
        add('git-identity', 'all', f'(?i){WORD_START}{e}{tail}', dev, term.lower())
    # the build machine's per-session folders, before the account-name rules (which only rename their profile part)
    add('session-path', 'all', r'(?i)(AppData[\\/]+Local[\\/]+Temp([\\/]+))[^\\/\s\'"]+[\\/]+[^\\/\s\'"]+[\\/]+' + UUID +
        r'(?:([\\/]+)scratchpad(?![\w-]))?', session_folder, 'temp')
    add('session-path', 'all', r'(?i)\blocal_' + UUID + r'\b', 'session', 'local_')
    if session_ids:
        add('session-path', 'all', r'(?i)\b(?:' + '|'.join(re.escape(s) for s in sorted(session_ids)) + r')\b', 'session')
    if machine and len(machine) >= 4:
        add('username', 'all', '(?i)' + re.escape(machine), 'dev-pc', machine.lower())
    if user:
        u = re.escape(user)
        # paths, also ones that lost their separators (C:UsersNameWork) or took a regex backreference (Users\1Name)
        add('username', 'all', f'(?i)((?:users[\\\\/:0-9]{{0,6}}|home[\\\\/:0-9]{{1,6}})){u}', lambda m: m.group(1) + 'dev', user.lower())
        if len(user) >= 3:   # a shorter name is too common a word to replace outside a path
            add('username', 'all', f'(?i){WORD_START}{u}(?![A-Za-z0-9_])', 'dev', user.lower())
    add('email', 'all', EMAIL, '<redacted-email>', '@')
    add('agent-mention', 'all', r'(?i)\bclaude[-_ ]code\b', 'agent-tool', 'claude')
    # Codex: the tool's names, its model ids and the provider; a bare "codex" stays (games have lore codices)
    add('agent-mention', 'all', r'(?i)\b(?:openai[-_ ])?codex[-_ ](?:cli|exec)\b|\bopenai[-_ ]codex\b', 'agent-tool', 'codex')
    add('agent-mention', 'all', r'(?i)\bgpt-\d+(?:\.\d+)?(?:-[a-z0-9]+)*\b', 'agent-model', 'gpt-')
    add('agent-mention', 'all', r'(?i)chatgpt', cased('agent', 'Agent', 'AGENT'), 'chatgpt')
    add('agent-mention', 'all', r'(?i)openai', cased('provider', 'Provider', 'PROVIDER'), 'openai')
    add('agent-mention', 'all', r'(?i)\bclaude[-_ ]?(?:opus|sonnet|haiku|fable|instant)(?:[-_ ]?[0-9]+(?:[._-][0-9]+)*)?[\w.-]*', 'agent-model', 'claude')
    add('agent-mention', 'all', r'(?i)\b(?:opus|sonnet|haiku)[-_ ]?[0-9]+(?:\.[0-9]+)*\b', 'agent-model')
    add('agent-mention', 'all', OPUS_WORD % 'OPUS', 'MODEL', 'opus')
    add('agent-mention', 'all', OPUS_WORD % 'Opus', 'Model', 'opus')
    add('agent-mention', 'all', '(?i)' + OPUS_WORD % 'opus', 'model', 'opus')
    add('agent-mention', 'all', r'(?i)claude', cased('agent', 'Agent', 'AGENT'), 'claude')
    add('agent-mention', 'all', r'(?i)anthropic', cased('provider', 'Provider', 'PROVIDER'), 'anthropic')
    return R


def apply_rules(text, rules, json_file, log_file, counts=None):
    low = None
    for rid, scope, rx, rep, hint in rules:
        if (scope == 'json' and not json_file) or (scope == 'lines' and json_file) or (scope == 'logs' and not log_file):
            continue
        if hint:
            if low is None:
                low = text.lower()
            if hint not in low:
                continue
        text, n = rx.subn(rep, text)
        if n:
            low = None
            if counts is not None:
                counts[rid] = counts.get(rid, 0) + n
    return text


def enforced_pattern(user, identities):
    """What must not be left in a delivered text file or path: the names of the layout's scan list."""
    parts = [r'superposition', r'game[-_ ]?factory', r'claude', r'anthropic', r'openai', OPUS_WORD % 'opus', EMAIL]
    if user and len(user) >= 3:
        # the account name as a word or path segment of its own, not inside a longer word (a place name); a lower ->
        # upper boundary counts as a word's edge (OwnerNameDesktop, and C:UsersNameWork: a path whose separators a
        # shell dropped)
        parts.append(r'(?:(?<=\\[nrtfb])|(?<=\\u[0-9a-fA-F]{4})|(?<![A-Za-z])|(?-i:(?<=[a-z])(?=[A-Z])))' + re.escape(user) +
                     r'(?:(?![A-Za-z])|(?-i:(?<=[a-z])(?=[A-Z])))')
    elif user:
        parts.append(r'(?:users|home)[\\/]{1,2}' + re.escape(user) + r'(?![A-Za-z0-9_])')
    for term, _ in identities:
        tail = '[A-Za-z0-9]*' if re.search(r'\d', term) and len(term) >= 5 else '(?![A-Za-z0-9])'
        parts.append(WORD_START + re.escape(term) + tail)
    return re.compile('|'.join(f'(?:{p})' for p in parts), re.I)


# ---- the delivered history ---------------------------------------------------------------------------------------------
HISTORY_REFS = ['--single-worktree', '--exclude=refs/heads/tasks', '--exclude=refs/heads/tasks-*', '--exclude=refs/remotes/*/tasks',
                '--exclude=refs/remotes/*/tasks-*', '--exclude=refs/stash', '--all']
SKIP_WORDS = {'claude', 'anthropic', 'codex', 'openai', 'agent', 'user', 'users', 'admin', 'root', 'dev', 'noreply', 'github', 'unknown'}


def identity_terms(repo, authors):
    """[(term, dev_NN)] for every author and committer of the history: the full name, its words of 4+ letters and the
    e-mail handle, longest first. Numbers them dev_01.. in `authors` (name -> dev_NN) in the order git lists them."""
    terms = {}
    seen = []
    for line in git_text(repo, 'log', '--reverse', '--format=%an%x09%ae%n%cn%x09%ce', *HISTORY_REFS).splitlines():
        if line not in seen:
            seen.append(line)
    for line in seen:
        name, _, mail = line.partition('\t')
        name, mail = name.strip(), mail.strip()
        if not name:
            continue
        dev = name if re.fullmatch(r'dev_\d+', name) else authors.setdefault(name, 'dev_%02d' % (len(authors) + 1))
        if not re.fullmatch(r'(?i)(claude|codex|agent|dev|dev_\d+)', name):
            terms.setdefault(name, dev)
        for w in re.split(r'[^A-Za-z0-9]+', name):
            if len(w) >= 4 and w.lower() not in SKIP_WORDS and not re.fullmatch(r'dev_?\d*', w):
                terms.setdefault(w, dev)
        local = mail.split('@')[0].split('+')[-1]
        if len(local) >= 4 and local.lower() not in SKIP_WORDS and not re.fullmatch(r'dev_?\d*', local):
            terms.setdefault(local, dev)
    return sorted(terms.items(), key=lambda kv: -len(kv[0]))


def rewrite_history(repo, bare, rules, authors, stats):
    """Stream `git fast-export` of every ref but the tasks branch and the stash into `git fast-import` of the new bare
    repo: author / committer / tagger -> dev_NN, agent trailer lines of messages dropped, the scrub rules on messages
    and on text blobs (text by the path that first holds the blob); Git LFS pointers stay as they are. Returns the
    original -> delivered commit id map."""
    blob_path = {}
    for line in git(repo, 'rev-list', '--objects', *HISTORY_REFS).decode('utf-8', 'replace').splitlines():
        if len(line) > 41 and line[40] == ' ':
            blob_path.setdefault(line[:40], line[41:])
    marks = os.path.join(bare, 'import.marks')
    ex = subprocess.Popen(['git', '-C', repo, 'fast-export', *HISTORY_REFS, '--show-original-ids', '--signed-tags=strip',
                           '--tag-of-filtered-object=rewrite', '--reencode=yes'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    im = subprocess.Popen(['git', '-C', bare, 'fast-import', '--quiet', '--force', f'--export-marks={marks}'],
                          stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    out, inp = im.stdin, ex.stdout
    ctx, mark, orig, after_data, orig_to_mark = '', None, None, False, {}
    try:
        while True:
            raw = inp.readline()
            if not raw:
                break
            line = raw[:-1] if raw.endswith(b'\n') else raw
            if after_data:   # the export's optional LF after a data block: ours is already written
                after_data = False
                if not line:
                    continue
            if line == b'blob':
                ctx, mark, orig = 'blob', None, None
            elif line.startswith(b'commit '):
                ctx, mark, orig = 'commit', None, None
            elif line.startswith(b'tag '):
                ctx, mark, orig = 'tag', None, None
            elif line.startswith(b'reset '):
                ctx = 'reset'
            elif line.startswith(b'mark :'):
                mark = line[5:]
            elif line.startswith(b'original-oid '):
                orig = line[13:].strip().decode()
                if ctx == 'commit' and mark:
                    orig_to_mark[orig] = mark
            elif ctx in ('commit', 'tag') and line.split(b' ', 1)[0] in (b'author', b'committer', b'tagger'):
                s = line.decode('utf-8', 'replace')
                sp, lt = s.index(' '), s.rfind(' <')
                gt = s.find('> ', lt) if lt > 0 else -1
                if lt > 0 and gt > 0:
                    who = s[sp + 1:lt]
                    anon = who if re.fullmatch(r'dev_\d+', who) else authors.setdefault(who, 'dev_%02d' % (len(authors) + 1))
                    line = (s[:sp + 1] + anon + ' <' + anon + '@example.invalid' + s[gt:]).encode('utf-8')
            elif line.startswith(b'data '):
                n = int(line[5:])
                if n >= (256 << 20):   # never an LFS pointer nor text the rules rewrite: copied through in chunks
                    out.write(b'data %d\n' % n)
                    left = n
                    while left:
                        chunk = inp.read(min(left, 1 << 20))
                        if not chunk:
                            raise Refused('the fast-export stream ended inside a data block')
                        out.write(chunk)
                        left -= len(chunk)
                    out.write(b'\n')
                    after_data = True
                    continue
                d = inp.read(n)
                if len(d) != n:
                    raise Refused('the fast-export stream ended inside a data block')
                if ctx == 'blob':
                    path = blob_path.get(orig or '', '')
                    if d and not (n < 300 and d.startswith(LFS_MAGIC)) and is_text(path, d):
                        text, enc = decode(d)
                        new = apply_rules(text, rules, path.lower().endswith(('.json', '.jsonl')), False)
                        if new != text:
                            d = new.encode(enc)
                            stats['blobs_scrubbed'] += 1
                elif ctx in ('commit', 'tag'):
                    msg = d.decode('latin-1')
                    kept = [ml for ml in msg.split('\n') if not TRAILER.match(ml)]
                    new = apply_rules('\n'.join(kept), rules, False, False)
                    if new != msg:
                        d = new.encode('latin-1')
                        stats['messages_scrubbed'] += 1
                out.write(b'data %d\n' % len(d))
                out.write(d)
                out.write(b'\n')
                after_data = True
                continue
            out.write(line + b'\n')
        out.close()
    except BaseException:
        ex.kill()
        im.kill()
        raise
    err_ex, err_im = ex.stderr.read(), im.stderr.read()
    if ex.wait() != 0:
        raise Refused(f'git fast-export failed: {err_ex.decode("utf-8", "replace")[:400]}')
    if im.wait() != 0:
        raise Refused(f'git fast-import failed: {err_im.decode("utf-8", "replace")[:400]}')
    mark_to_new = {}
    with open(marks, 'rb') as f:
        for ml in f:
            m, _, sha = ml.strip().partition(b' ')
            mark_to_new[m] = sha.decode()
    os.remove(marks)
    lost = [o for o, m in orig_to_mark.items() if m not in mark_to_new]
    if lost:
        raise Refused(f'the history rewrite lost {len(lost)} commit(s), e.g. {lost[0]}')
    return {o: mark_to_new[m] for o, m in orig_to_mark.items()}


def write_git_log(bare, head, out_file, header):
    """Every commit up to head, oldest first: message, dev_NN author and committer, dates, the full text diff; a binary
    file as path + sha256 + bytes (old -> new), a Git LFS file as its pointers' sha256 and size. Returns the commit count."""
    fmt = 'commit %H%nParents: %P%nAuthor: %an <%ae>%nAuthorDate: %aI%nCommitter: %cn <%ce>%nCommitDate: %cI%n%n%w(0,4,4)%B'
    p = subprocess.Popen(['git', '-C', bare, '-c', 'core.quotepath=off', '-c', 'diff.renameLimit=20000', 'log', '--reverse',
                          '--topo-order', '--no-color', '--no-textconv', '--no-ext-diff', '--full-index', '-M',
                          '--diff-merges=first-parent', '-p', f'--format={fmt}', head], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    cat = CatFile(bare)
    commits = 0

    def desc(sha, size):
        return '(none)' if sha is None else f'sha256 {sha} ({size} bytes)'

    def blob_desc(oid):
        if not oid or not oid.strip('0'):
            return '(none)'
        t, d = cat.read(oid)
        return f'(blob {oid} missing)' if d is None else desc(hashlib.sha256(d).hexdigest(), len(d))

    def section_path(sec):
        for pre, cut in (('rename to ', 10), ('+++ b/', 6), ('--- a/', 6)):
            for l in sec:
                if l.startswith(pre):
                    return l[cut:].rstrip('\r\t')
        s = sec[0][11:]
        if (len(s) - 1) % 2 == 0:
            h = (len(s) - 1) // 2
            a, b = s[:h], s[h + 1:]
            if len(a) > 2 and a[2:] == b[2:]:
                return b[2:]
        return s

    def flush(sec, w):
        if not sec:
            return
        path = section_path(sec)
        lfs, all_ptr, in_hunk, hunks = False, True, False, 0
        old_oid = new_oid = None
        old_size = new_size = -1
        for l in sec:
            if l.startswith('@@'):
                in_hunk, hunks = True, hunks + 1
                continue
            if not in_hunk or not l:
                continue
            c, body = l[0], l[1:].rstrip('\r')
            if c == '\\':
                continue
            if c not in ' +-':
                all_ptr = False
            elif body.startswith('version https://git-lfs.github.com/spec/'):
                lfs = True
            elif body.startswith('oid sha256:'):
                if c != '+':
                    old_oid = body[11:]
                if c != '-':
                    new_oid = body[11:]
            elif body.startswith('size '):
                z = int(body[5:]) if body[5:].isdigit() else 0
                if c != '+':
                    old_size = z
                if c != '-':
                    new_size = z
            else:
                all_ptr = False
        if lfs and all_ptr and hunks:
            for l in sec:
                if l.startswith(('index ', '--- ', '+++ ', '@@')):
                    break
                w.write(l + '\n')
            w.write(f'Git LFS file {path}: {desc(old_oid, old_size)} -> {desc(new_oid, new_size)}\n')
            for l in reversed(sec):
                if l:
                    break
                w.write('\n')
        else:
            a = b = None
            for l in sec:
                m = re.match(r'^index ([0-9a-f]+)\.\.([0-9a-f]+)', l)
                if m:
                    a, b = m.group(1), m.group(2)
                    break
            for l in sec:
                if l.startswith('Binary files ') and l.rstrip('\r').endswith(' differ'):
                    w.write(f'Binary file {path}: {blob_desc(a)} -> {blob_desc(b)}\n')
                else:
                    w.write(l + '\n')
        sec.clear()

    os.makedirs(lp(os.path.dirname(out_file)), exist_ok=True)
    with open(lp(out_file), 'w', encoding='latin-1', newline='') as w:
        w.write(header)
        section, in_header, in_message = [], False, False
        for raw in p.stdout:
            line = raw.decode('latin-1')
            line = line[:-1] if line.endswith('\n') else line
            if len(line) == 47 and line.startswith('commit '):
                flush(section, w)
                commits += 1
                in_header, in_message = True, False
                w.write(line + '\n')
                continue
            if in_header:
                if not line:
                    in_header, in_message = False, True
                elif line.startswith(('Author: ', 'Committer: ')):
                    sp = line.index(': ')
                    who = line[sp + 2:]
                    lt = who.rfind(' <')
                    line = line[:sp + 2] + (who[:lt] if lt > 0 else who)   # identities by name
                w.write(line + '\n')
                continue
            if in_message and TRAILER.match(line):
                continue
            if line.startswith('diff --git '):
                in_message = False
                flush(section, w)
                section.append(line)
                continue
            if section:
                section.append(line)
            else:
                w.write(line + '\n')
        flush(section, w)
    err = p.stderr.read()
    cat.close()
    if p.wait() != 0:
        raise Refused(f'git log failed: {err.decode("utf-8", "replace")[:400]}')
    return commits


def lfs_pointers(bare, refs):
    """{oid: size} of every Git LFS pointer in every commit reachable from refs."""
    objs = git(bare, 'rev-list', '--objects', *refs).decode('utf-8', 'replace').splitlines()
    ids = '\n'.join(l.split(' ')[0] for l in objs) + '\n'
    small = [l.split(' ') for l in git(bare, 'cat-file', '--batch-check=%(objectname) %(objecttype) %(objectsize)',
                                       input=ids.encode()).decode().splitlines()]
    cand = [s[0] for s in small if len(s) == 3 and s[1] == 'blob' and int(s[2]) < 300]
    need = {}
    if cand:
        data = git(bare, 'cat-file', '--batch', input=('\n'.join(cand) + '\n').encode())
        pos = 0
        while pos < len(data):
            nl = data.index(b'\n', pos)
            size = int(data[pos:nl].split()[2])
            m = LFS_PTR.match(data[nl + 1:nl + 1 + size])
            pos = nl + 1 + size + 1
            if m:
                need[m.group(1).decode()] = int(m.group(2))
    return need


def export_tree(bare, commit, lfs_store, dest, problems):
    """The tree of commit under dest, Git LFS pointers replaced by their objects from lfs_store. Dataset/ and Tasks/ at
    the top are left out (a dataset holds neither inside its project)."""
    cat = CatFile(bare)
    n = 0
    try:
        for entry in git(bare, 'ls-tree', '-r', '-z', '--full-tree', commit).split(b'\0'):
            if not entry:
                continue
            meta, _, path = entry.partition(b'\t')
            mode, kind, oid = meta.decode().split(' ')
            path = path.decode('utf-8', 'replace')
            if path.split('/')[0] in ('Dataset', 'Tasks'):
                continue
            if kind != 'blob':
                problems.append(f'note: submodule left out: {path}')
                continue
            t, data = cat.read(oid)
            if data is None:
                problems.append(f'error: missing git object {oid} for {path}')
                continue
            m = LFS_PTR.match(data) if len(data) < 1024 else None
            dst = os.path.join(dest, *path.split('/'))
            if m:
                o, size = m.group(1).decode(), int(m.group(2))
                src = os.path.join(lfs_store, o[:2], o[2:4], o)
                if not os.path.isfile(lp(src)):
                    problems.append(f'error: Git LFS object {o[:12]}... ({path}) is not in the local store: git lfs fetch --all first')
                    continue
                if os.path.getsize(lp(src)) != size:
                    problems.append(f'error: Git LFS object {o[:12]}... ({path}) has the wrong size in the local store')
                    continue
                copy_file(src, dst)
            else:
                write_bytes(dst, data)
            n += 1
    finally:
        cat.close()
    return n


# ---- the sessions' record --------------------------------------------------------------------------------------------------
SESSION_RX = re.compile(r'"session_id"\s*:\s*"([^"]+)"')
TIME_RX = re.compile(r'"time"\s*:\s*"([^"]+)"')


def parse_time(s):
    from datetime import datetime
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        return None


def session_logs(recording, until, exclude, dest, stats):
    """History/sessions/messages.jsonl and actions.jsonl from the recording: rows up to the release commit's time (work
    after it is not part of the release), without the sessions that packaged (over a quarter of their tool calls name
    this packager) and the ones given with --exclude-sessions. Each session's id becomes session_NN in both files,
    numbered by its first row in actions.jsonl, then in messages.jsonl: the scrub turns every session id it meets into
    the one word "session", which would leave no way to tell which reply belongs to which tool calls.
    Returns the session ids met (for the scrub)."""
    skip = {s: 'given' for s in exclude}
    ids = set()
    act = os.path.join(recording, 'actions.jsonl')
    if os.path.isfile(act):
        rows, pkg = {}, {}
        with open(act, encoding='utf-8', errors='replace') as f:
            for line in f:
                m = SESSION_RX.search(line)
                if not m:
                    continue
                rows[m.group(1)] = rows.get(m.group(1), 0) + 1
                if 'package-dataset.py' in line:
                    pkg[m.group(1)] = pkg.get(m.group(1), 0) + 1
        for sid, n in pkg.items():
            if sid not in skip and n / rows[sid] > 0.25:
                skip[sid] = 'packaging session'
    numbers = {}
    for name in ('actions.jsonl', 'messages.jsonl'):
        src = os.path.join(recording, name)
        if not os.path.isfile(src):
            stats[name] = None
            continue
        kept, total = [], 0
        with open(src, encoding='utf-8', errors='replace', newline='') as f:
            for line in f:
                line = line.rstrip('\r\n')
                if not line.strip():
                    continue
                total += 1
                sm, tm = SESSION_RX.search(line), TIME_RX.search(line)
                if not sm or not tm:
                    continue
                sid = sm.group(1)
                ids.add(sid.lower())
                when = parse_time(tm.group(1))
                if when is not None and when.tzinfo is None:
                    when = when.astimezone()   # a row without an offset: this machine's time
                if sid in skip or when is None or when > until:
                    continue
                label = numbers.setdefault(sid, 'session_%02d' % (len(numbers) + 1))
                kept.append(line[:sm.start(1)] + label + line[sm.end(1):])   # the row's own session_id (its first)
        stats[name] = {'rows': len(kept), 'source_rows': total, 'sessions_left_out': len(skip)}
        if kept:
            write_text(os.path.join(dest, name), '\n'.join(kept) + '\n')
    stats['sessions'] = len(numbers)
    return ids


# ---- brief, screenshots, build ---------------------------------------------------------------------------------------------
def find_brief(repo, slug, given, kind):
    """The brief as given (kind 'brief') or the design doc ('design'): the file named on the command line, else the
    game repo's Brief/<kind>.md or Docs/<Kind>.md, else this repo's docs (briefs/original/game-<slug>.md, then
    briefs/games/<slug>.md, for the brief; games/<slug>.md for the design doc)."""
    if given:
        if not os.path.isfile(given):
            raise Refused(f'--{kind} {given}: no such file')
        return given
    cands = [os.path.join(repo, 'Brief', f'{kind}.md'), os.path.join(repo, 'Docs', f'{kind.capitalize()}.md'),
              os.path.join(repo, 'Docs', f'{kind}.md')]
    docs = os.path.join(REPO, 'docs')
    if kind == 'brief':
        cands += [os.path.join(docs, 'briefs', 'original', f'game-{slug}.md'), os.path.join(docs, 'briefs', 'games', f'{slug}.md')]
    else:
        cands += [os.path.join(docs, 'games', f'{slug}.md')]
    for c in cands:
        if os.path.isfile(c):
            return c
    return None


def readme_images(text):
    """(alt, path) of the local images a README shows, in its order: markdown images and <img src>."""
    text = re.sub(r'(?s)<!--.*?-->', '', text)
    found = [(m.group(1).strip(), m.group(2)) for m in re.finditer(r'!\[([^\]]*)\]\(\s*<?([^)\s>]+)>?[^)]*\)', text)]
    found += [('', m.group(1)) for m in re.finditer(r'(?i)<img[^>]+src=["\']([^"\']+)["\']', text)]
    out, seen = [], set()
    for alt, p in found:
        p = p.split('#')[0].split('?')[0]
        if re.match(r'(?i)^[a-z][a-z0-9+.-]*:', p) or not p.lower().endswith(IMAGE_EXT) or p in seen:
            continue
        seen.add(p)
        out.append((alt, p.lstrip('./')))
    return out


def md_section(text, heading_rx):
    """The body of the first '## <heading>' section whose heading matches, without the heading line."""
    out, inside = [], False
    for line in text.splitlines():
        m = re.match(r'^##\s+(.*?)\s*$', line)
        if m:
            if inside:
                break
            inside = bool(re.search(heading_rx, m.group(1), re.I))
            continue
        if inside:
            out.append(line)
    return '\n'.join(out).strip()


def find_exe(build):
    """The player's exe in a build folder: the one with its <name>_Data folder next to it."""
    exes = sorted(f for f in os.listdir(build) if f.lower().endswith('.exe'))
    for e in exes:
        if os.path.isdir(os.path.join(build, e[:-4] + '_Data')):
            return e
    exes = [e for e in exes if not e.lower().startswith('unitycrashhandler')]
    return exes[0] if exes else None


# ---- scan ------------------------------------------------------------------------------------------------------------------
def short_token(buf, at, n, w):
    """Whether a short needle (an account name of four or five letters) found at buf[at] with stride w (1 ASCII, 2
    UTF-16LE) stands as a word of its own: spelled as a word is (name, Name, NAME), after a non-letter or at a lower ->
    upper boundary, and not followed by a lower-case letter. The engine's own files spell short names inside longer
    words and identifiers, in any case (System.Core.dll's method names, a word list in mono-2.0-bdwgc.dll)."""
    if w == 2 and any(buf[at + 2 * k + 1] for k in range(n)):
        return False
    s = bytes(buf[at + w * k] for k in range(n)).decode('latin-1')
    if not (s.islower() or s.isupper() or (s[0].isupper() and s[1:].islower())):
        return False
    def char(i):
        return buf[i] if 0 <= i < len(buf) and (w == 1 or (i + 1 < len(buf) and buf[i + 1] == 0)) else 0
    prev, nxt = char(at - w), char(at + n * w)
    letter = lambda c: 65 <= c <= 90 or 97 <= c <= 122   # noqa: E731
    return (not letter(prev) or (97 <= prev <= 122 and s[0].isupper())) and not 97 <= nxt <= 122


def scan_binary(path, needles):
    """[(offset, needle, run)] of needles (lower-case ASCII) found in a binary file as ASCII or UTF-16LE, any case. run =
    the printable characters in a row around the hit: compiled-in strings run long, compressed data seldom past 8."""
    hits = []
    wide = [n.encode('utf-16-le') for n in needles]
    plain = [n.encode('ascii') for n in needles]
    chunk, overlap, base, carry = 4 << 20, 128, 0, b''
    with open(lp(path), 'rb') as f:
        while True:
            data = f.read(chunk)
            if not data:
                break
            buf = carry + data
            low = buf.lower()
            for k, n in enumerate(needles):
                for pat, w in ((plain[k], False), (wide[k], True)):
                    at = low.find(pat)
                    while at >= 0 and len(hits) < 200:
                        off = base - len(carry) + at
                        if len(n) < 6 and not short_token(buf, at, len(n), 2 if w else 1):
                            pass   # a short name inside a longer word or identifier, or in random bytes
                        elif not any(h[0] == off for h in hits):
                            st = 2 if w else 1
                            run, a, z = len(n), at - st, at + len(pat)
                            while a >= 0 and run < 64 and 0x20 <= buf[a] <= 0x7e and (not w or buf[a + 1] == 0):
                                run, a = run + 1, a - st
                            while z + st - 1 < len(buf) and run < 64 and 0x20 <= buf[z] <= 0x7e and (not w or buf[z + 1] == 0):
                                run, z = run + 1, z + st
                            hits.append((off, n, run))
                        at = low.find(pat, at + 1)
            carry = buf[-overlap:]
            base += len(data)
    return hits


# ---- the package ---------------------------------------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0], formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('game', help='the game\'s slug (the repo is <root>/games/<slug>)')
    ap.add_argument('--repo', help='the game repo, when it is not <root>/games/<slug>')
    ap.add_argument('--commit', default='HEAD', help='the release commit (default HEAD)')
    ap.add_argument('--version', default='', help='the release version for the README and manifest.json, e.g. 1.0')
    ap.add_argument('--build', help='the player build folder (default <repo>/Build/Windows)')
    ap.add_argument('--brief', help='the brief as given (Brief/brief.md)')
    ap.add_argument('--design', help='the design doc (Brief/design.md)')
    ap.add_argument('--tasks-ref', default='', help='where Tasks/ comes from (default the branch tasks, else origin/tasks)')
    ap.add_argument('--exclude-sessions', default='', help='session ids, comma-separated, whose rows are not creation work')
    ap.add_argument('--recording', help='the recording folder (default <root>/.recording/<slug>)')
    ap.add_argument('--out', help='where the zip and the scratch folder go (default the game repo)')
    ap.add_argument('--lenient-binaries', action='store_true',
                    help='list the names found in binary files without refusing the package (to review a refusal)')
    ap.add_argument('--strict-binaries', action='store_true', help=argparse.SUPPRESS)   # the default now
    ap.add_argument('--no-repo-dataset', action='store_true', help='do not write the repo\'s Dataset/ folder')
    ap.add_argument('--no-zip', action='store_true', help='stop after the checks; the delivery stays in the scratch folder')
    ap.add_argument('--dry-run', action='store_true', help='print what would go in; write nothing')
    args = ap.parse_args()
    try:
        return package(args)
    except Refused as e:
        print(f'REFUSED: {e}', file=sys.stderr)
        return 2


def package(args):
    t0 = time.time()
    game = args.game
    if not re.fullmatch(r'[a-z0-9][a-z0-9-]*[a-z0-9]', game):
        raise Refused(f'{game!r} is not a game slug (lower-case letters, digits and dashes)')
    repo = os.path.abspath(args.repo or os.path.join(ugfroot.root(), 'games', game))
    if not os.path.isdir(os.path.join(repo, '.git')):
        raise Refused(f'no game repo at {repo}')
    recording = os.path.abspath(args.recording or os.path.join(ugfroot.root(), '.recording', game))
    out_root = os.path.abspath(args.out or repo)
    scratch = os.path.join(out_root, '.dataset')
    stage = os.path.join(scratch, game)
    sha = git_text(repo, 'rev-parse', '--verify', '-q', args.commit + '^{commit}', check=False)
    if not re.fullmatch(r'[0-9a-f]{40}', sha):
        raise Refused(f'--commit {args.commit}: no such commit in {repo}')
    from datetime import datetime
    commit_time = datetime.fromisoformat(git_text(repo, 'log', '-1', '--format=%cI', sha))
    user = os.environ.get('USERNAME') or getpass.getuser()
    machine = os.environ.get('COMPUTERNAME') or socket.gethostname().split('.')[0]
    problems, warnings = [], []

    # inputs that can refuse the package before anything is written
    build = os.path.abspath(args.build or os.path.join(repo, 'Build', 'Windows'))
    exe = find_exe(build) if os.path.isdir(build) else None
    if not exe:
        problems.append(f'error: no player build at {build} (no .exe): build it with Scripts\\unity.ps1 build, or name the folder with --build')
    brief, design = find_brief(repo, game, args.brief, 'brief'), find_brief(repo, game, args.design, 'design')
    for kind, f in (('brief', brief), ('design', design)):
        if not f:
            problems.append(f'error: no {kind} found: name it with --{kind} <file> (it becomes Brief/{kind}.md)')
        elif os.path.getsize(f) < 200:
            problems.append(f'error: {f} is nearly empty ({os.path.getsize(f)} bytes): Brief/{kind}.md must say something')
    tasks_at = None
    for r in ([args.tasks_ref] if args.tasks_ref else ['tasks', 'origin/tasks']):
        c = git_text(repo, 'rev-parse', '--verify', '-q', r + '^{commit}', check=False)
        if re.fullmatch(r'[0-9a-f]{40}', c):
            tasks_at = (r, c)
            break
    task_files = []
    if tasks_at:
        task_files = [n for n in git_text(repo, 'ls-tree', '--name-only', tasks_at[1] + ':Tasks', check=False).splitlines() if n.endswith('.json')]
    if not task_files:
        problems.append('error: no tasks: the repo needs Tasks/<name>.json on its tasks branch (a game ships at least one; the unity-write-tasks skill)')
    if not os.path.isfile(os.path.join(recording, 'actions.jsonl')):
        warnings.append(f'no {os.path.join(recording, "actions.jsonl")}: History/sessions/ will hold no tool calls')
    if not os.path.isfile(os.path.join(recording, 'messages.jsonl')):
        warnings.append(f'no {os.path.join(recording, "messages.jsonl")}: History/sessions/ will hold no prompts or replies '
                        '(sessions recorded before they were: record-unity-action.ps1 -Backfill all imports them while their transcripts are on this machine)')
    step(f'{game}: commit {sha[:12]} ({commit_time.isoformat()}), build {build if exe else "MISSING"}, '
         f'{len(task_files)} task(s) on {tasks_at[0] if tasks_at else "no tasks branch"}')
    errors = [p for p in problems if p.startswith('error:')]
    if args.dry_run or errors:
        for p in problems:
            print('  ' + p)
        for w in warnings:
            print('  warning: ' + w)
        if errors:
            raise Refused(f'{len(errors)} thing(s) missing; nothing was written')
        print(f'  would write {os.path.join(out_root, "Dataset.pending.zip")} (pending: {", ".join(PENDING)})')
        return 0
    ugfroot.check_free(out_root, 'package-dataset')
    remove_tree(scratch)
    os.makedirs(lp(stage))

    # ---- the delivered history: rewrite, bundle, LFS objects, git.log ----
    step('reading the recording and the git identities')
    ses_stats = {}
    exclude = [s.strip() for s in args.exclude_sessions.split(',') if s.strip()]
    session_ids = session_logs(recording, commit_time, exclude, os.path.join(stage, 'History', 'sessions'), ses_stats)
    authors = {}
    identities = identity_terms(repo, authors)
    rules = build_rules(user, machine, session_ids, identities)
    step(f'rewriting the history ({len(authors)} identities -> dev_NN, {len(rules)} scrub rules)')
    bare = os.path.join(scratch, f'{game}.history.git')
    subprocess.run(['git', 'init', '--quiet', '--bare', bare], check=True, capture_output=True)
    hstats = {'blobs_scrubbed': 0, 'messages_scrubbed': 0}
    cmap = rewrite_history(repo, bare, rules, authors, hstats)
    if sha not in cmap:
        raise Refused(f'the rewritten history has no commit for {sha}: is it on a branch (not only on the tasks branch or in the stash)?')
    head = cmap[sha]
    # the delivered refs: the release commit as main, and each task's start branch; nothing else reaches the bundle
    # (a start branch made on another machine is here only as origin's: it is delivered under its own name too)
    for line in git_text(bare, 'for-each-ref', '--format=%(refname) %(objectname)', 'refs/remotes/origin/starts/').splitlines():
        r, _, oid = line.partition(' ')
        local = 'refs/heads/starts/' + r[len('refs/remotes/origin/starts/'):]
        if oid and not git_text(bare, 'rev-parse', '--verify', '-q', local, check=False):
            git(bare, 'update-ref', local, oid)
    starts = [r for r in git_text(bare, 'for-each-ref', '--format=%(refname)', 'refs/heads/starts/').splitlines() if r]
    git(bare, 'update-ref', 'refs/heads/main', head)
    refs = ['refs/heads/main'] + starts
    for r in git_text(bare, 'for-each-ref', '--format=%(refname)').splitlines():
        if r and r not in refs:
            git(bare, 'update-ref', '-d', r)
    if any(re.search(r'/tasks(-[^/]*)?$', r) for r in refs):
        raise Refused('the delivered history carries the tasks branch: task work must never enter it')
    n_commits = int(git_text(bare, 'rev-list', '--count', *refs))
    hist = os.path.join(stage, 'History')
    os.makedirs(lp(hist), exist_ok=True)
    git(bare, 'symbolic-ref', 'HEAD', 'refs/heads/main')   # so a clone of the bundle checks main out
    git(bare, 'bundle', 'create', os.path.join(hist, f'{game}.bundle'), 'HEAD', *refs)
    lfs_store = os.path.join(git_text(repo, 'rev-parse', '--absolute-git-dir'), 'lfs', 'objects')
    need = lfs_pointers(bare, refs)
    lfs_bytes = 0
    for oid, size in sorted(need.items()):
        src = os.path.join(lfs_store, oid[:2], oid[2:4], oid)
        if not os.path.isfile(lp(src)):
            problems.append(f'error: Git LFS object {oid[:12]}... of the history is not in the local store: git lfs fetch --all first')
        elif os.path.getsize(lp(src)) != size:
            problems.append(f'error: Git LFS object {oid[:12]}... has the wrong size in the local store')
        else:
            copy_file(src, os.path.join(hist, 'lfs', 'objects', oid[:2], oid[2:4], oid))
            lfs_bytes += size
    step(f'history: {n_commits} commits, {len(refs)} ref(s), head {head[:12]}; {hstats["blobs_scrubbed"]} blobs and '
         f'{hstats["messages_scrubbed"]} messages scrubbed; {len(need)} LFS objects')
    write_text(os.path.join(scratch, f'{game}.commit-map.tsv'), 'original\tdelivered\n' + ''.join(f'{o}\t{n}\n' for o, n in cmap.items()))

    # ---- UnityProject, workflow.jsonl, git.log ----
    step('writing UnityProject/ and git.log')
    project = os.path.join(stage, 'UnityProject')
    n_project = export_tree(bare, head, lfs_store, project, problems)
    if not os.path.isfile(lp(os.path.join(project, 'workflow.jsonl'))):
        problems.append('error: no workflow.jsonl at the commit')
    else:
        copy_file(os.path.join(project, 'workflow.jsonl'), os.path.join(stage, 'workflow.jsonl'))
    readme_src = ''
    if os.path.isfile(lp(os.path.join(project, 'README.md'))):
        readme_src = read_bytes(os.path.join(project, 'README.md')).decode('utf-8', 'replace')
    m = re.search(r'(?m)^#\s+(.+?)\s*$', readme_src)
    title = m.group(1) if m else game
    header = (f'GIT-LOG 1\n# {title} ({game}): the git history up to commit {head}, oldest first (History/ holds every commit).\n'
              '# Recorded as it happened (not reconstructed). Authors and committers are anonymised as dev_NN.\n'
              '# Text changes are full unified diffs; binary files and Git LFS files are given as path + sha256 + bytes (old -> new).\n\n')
    log_commits = write_git_log(bare, head, os.path.join(stage, 'git.log'), header)

    # ---- Brief, Screenshots, Build ----
    copy_file(brief, os.path.join(stage, 'Brief', 'brief.md'))
    copy_file(design, os.path.join(stage, 'Brief', 'design.md'))
    shots = []
    for alt, rel in readme_images(readme_src):
        src = os.path.join(project, *rel.split('/'))
        if not os.path.isfile(lp(src)):
            warnings.append(f'the README shows {rel}, which is not in the project at the commit')
            continue
        name = re.sub(r'[^A-Za-z0-9._-]', '_', os.path.basename(rel))   # the README links it without escapes
        while any(s[0].lower() == name.lower() for s in shots):
            name = '_' + name
        copy_file(src, os.path.join(stage, 'Screenshots', name))
        shots.append((name, alt or os.path.splitext(name)[0]))
    if not shots:
        problems.append('error: the game\'s README.md shows no committed image: Screenshots/ needs at least one (hero + gallery in Docs/screenshots/)')
    n_build = 0
    for d, dirs, fs in os.walk(lp(build)):
        dirs[:] = [x for x in dirs if not NOT_SHIPPED_BUILD.search(x)]
        for f in fs:
            if f.lower().endswith('.pdb'):
                continue
            full = os.path.join(d, f)
            copy_file(full, os.path.join(stage, 'Build', os.path.relpath(full, lp(build))))
            n_build += 1
    if os.path.getmtime(os.path.join(build, exe)) < commit_time.timestamp():
        warnings.append(f'Build/{exe} is older than the release commit: build the release commit before packaging')

    # ---- Tasks ----
    step(f'tasks: {len(task_files)} from Tasks/ on {tasks_at[0]} ({tasks_at[1][:12]})')
    tasks_tmp = os.path.join(scratch, '_tasks')
    cat = CatFile(repo)
    for tf in task_files:
        t, data = cat.read(f'{tasks_at[1]}:Tasks/{tf}')
        write_bytes(os.path.join(tasks_tmp, tf), data or b'')
    cat.close()
    scrub_tree(tasks_tmp, rules, {}, None)
    remap_tree(tasks_tmp, cmap)
    spec = importlib.util.spec_from_file_location('split_tasks', os.path.join(HERE, 'split-tasks.py'))
    split_tasks = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(split_tasks)
    task_rows = []
    for tf in sorted(task_files):
        stem = tf[:-5]
        try:
            task = json.loads(read_bytes(os.path.join(tasks_tmp, tf)).decode('utf-8-sig'))
        except ValueError as e:
            problems.append(f'error: Tasks/{tf} is not JSON ({e})')
            continue
        if not isinstance(task, dict) or task.get('name') != stem:
            problems.append(f'error: Tasks/{tf}: its name must equal the file name')
            continue
        agent, grader = split_tasks.split(task)
        for name, obj in (('task.json', agent), ('grader.json', grader)):
            write_text(os.path.join(stage, 'Tasks', stem, name), json.dumps(obj, indent=2, ensure_ascii=False) + '\n')
        seed = task.get('seed') if isinstance(task.get('seed'), dict) else {}
        task_rows.append({'name': stem, 'title': task.get('title', ''), 'kind': seed.get('kind', 'new game'),
                          'difficulty': task.get('difficulty', 'medium')})
    write_text(os.path.join(stage, 'Tasks', 'README.md'), tasks_readme(game, task_rows))
    remove_tree(tasks_tmp)

    # ---- README, then the scrub and the scan of everything ----
    ses_files = [n for n in ('messages.jsonl', 'actions.jsonl') if os.path.isfile(lp(os.path.join(hist, 'sessions', n)))]
    ctx = dict(game=game, title=title, version=args.version, head=head, exe=exe, shots=shots, task_rows=task_rows,
               readme_src=readme_src, sessions=ses_files, engine=ugfroot.project_unity_version(project) or '6000.3')
    write_text(os.path.join(stage, 'README.md'), dataset_readme(ctx, False))
    step('scrubbing every text file of the delivery')
    counts, touched = {}, []
    scrub_tree(stage, rules, counts, touched)
    remapped = remap_tree(stage, cmap)
    step(f'scrubbed {len(touched)} file(s): ' + (', '.join(f'{k} {v}' for k, v in counts.items()) or 'nothing to replace') +
         f'; commit ids mapped in {remapped} file(s)')
    step('scanning every file (paths and text; binaries as ASCII and UTF-16)')
    enforced = enforced_pattern(user, identities)
    needles = ['superposition', 'game-factory', 'game_factory', 'gamefactory', 'anthropic', 'claude', 'openai']
    if user and len(user) >= 4:
        needles.append(user.lower())
    hits, bin_hits = [], []
    for rel in files_under(stage):
        if enforced.search(rel):
            hits.append((rel, 'path', 0, rel))
        full = os.path.join(stage, *rel.split('/'))
        size = os.path.getsize(lp(full))
        if size == 0 or rel.endswith('.bundle'):   # the bundle's messages and text blobs were scrubbed in the rewrite
            continue
        with open(lp(full), 'rb') as f:
            head_bytes = f.read(8000)
        if not rel.startswith('History/lfs/objects/') and size < (256 << 20) and is_text(rel, head_bytes):
            text = decode(read_bytes(full))[0]
            found = 0
            for i, line in enumerate(text.split('\n'), 1):
                for mm in enforced.finditer(line):
                    found += 1
                    if found <= 20:
                        hits.append((rel, 'text', i, line[max(0, mm.start() - 60):mm.end() + 60].replace('\t', ' ').replace('\r', '')))
        else:
            for off, needle, run in scan_binary(full, needles):
                bin_hits.append((rel, off, needle, run))
    tsv = lambda rows: ''.join('\t'.join(str(x) for x in r) + '\n' for r in rows)   # noqa: E731
    write_text(os.path.join(scratch, f'{game}.binary-hits.tsv'), 'path\toffset\tname\tprintable_run\n' + tsv(bin_hits))
    strings = [h for h in bin_hits if h[3] >= 8]
    if bin_hits:
        warnings.append(f'{len(bin_hits)} name(s) in {len({h[0] for h in bin_hits})} binary file(s), {len(strings)} of them inside a string of 8+ '
                        f'characters: review {os.path.join(scratch, game + ".binary-hits.tsv")} (binaries are never changed)')
    if not args.lenient_binaries:   # a name in a binary file's strings refuses the package, as one in a text file does
        hits += [(h[0], 'binary', h[1], h[2]) for h in strings]
    errors = [p for p in problems if p.startswith('error:')]
    if hits or errors:
        write_text(os.path.join(scratch, f'{game}.refused-hits.tsv'), 'path\tkind\tline_or_offset\ttext\n' + tsv(hits) +
                   ''.join(f'-\terror\t-\t{e}\n' for e in errors))
        for e in errors[:15]:
            print('  ' + e)
        by_file = {}
        for h in hits:
            by_file.setdefault(h[0], []).append(h)
        for rel, hs in sorted(by_file.items(), key=lambda kv: -len(kv[1]))[:25]:
            print(f'  {len(hs):5d}  {hs[0][1]:<7} {rel}  e.g. {hs[0][3][:100]}')
        raise Refused(f'{len(hits)} name(s) left in {len(by_file)} file(s), {len(errors)} error(s); nothing was zipped. '
                      f'All of them: {os.path.join(scratch, game + ".refused-hits.tsv")}; the staged delivery: {stage}')

    # ---- manifest.json ----
    step('hashing every file for manifest.json')
    ses_manifest = {}
    for n in ses_files:
        with open(lp(os.path.join(hist, 'sessions', n)), 'rb') as f:
            ses_manifest[n[:-6]] = {'file': f'History/sessions/{n}', 'rows': sum(1 for l in f if l.strip())}
    history = {'bundle': f'History/{game}.bundle', 'head': head, 'commits': n_commits, 'refs': refs,
               'lfs_objects': len(need), 'lfs_bytes': lfs_bytes, 'authors_anonymised': True}
    if ses_manifest:
        history['sessions'] = ses_manifest
    base = {'layout': LAYOUT, 'game': game, 'title': title, 'version': args.version, 'commit': head, 'status': 'pending',
            'pending': list(PENDING), 'created': datetime.now().astimezone().isoformat(timespec='seconds'), 'replay_verification': None,
            'scenarios': [],
            'brief': {'brief': 'Brief/brief.md', 'design': 'Brief/design.md'}}
    write_manifest(stage, dict(base, variant='full', history=history,
                               build={'config': 'Release', 'commit': head, 'exe': f'Build/{exe}',
                                      'source': 'the game session\'s own player build (Scripts/unity.ps1 build); its commit is stated, not verified'},
                               tasks={'count': len(task_rows), 'names': [r['name'] for r in task_rows], 'schema': 'game-task/1'}))
    mhits = [mm.group(0) for mm in enforced.finditer(read_bytes(os.path.join(stage, 'manifest.json')).decode('latin-1'))]
    if mhits:
        raise Refused(f'manifest.json holds a name that must not be delivered ({len(mhits)} place(s)): a file path or the title carries it')

    # ---- the checks a consumer runs ----
    step('checking the delivery (tools/validate-game.py --dataset)')
    verdict = validate(stage)
    if verdict['errors']:
        for e in verdict['errors'][:30]:
            print('  x ' + e)
        raise Refused(f'the delivery is not valid ({len(verdict["errors"])} error(s)); nothing was zipped. The staged delivery: {stage}')
    zip_path = None
    if not args.no_zip:
        zip_path = os.path.join(out_root, 'Dataset.pending.zip')
        step(f'zipping {zip_path}')
        tmp = zip_path + '.tmp'
        n_zip = zip_tree(stage, tmp, game)
        for old in (zip_path, os.path.join(out_root, 'Dataset.zip')):   # a pending delivery never sits next to a complete one
            if os.path.isfile(old):
                os.remove(old)
        os.replace(tmp, zip_path)
    if not args.no_repo_dataset:
        ds = os.path.join(repo, 'Dataset')
        step(f'writing {ds}')
        if os.path.isdir(ds):
            for n in os.listdir(ds):
                if n != '.gitattributes':
                    p = os.path.join(ds, n)
                    remove_tree(p) if os.path.isdir(p) else os.remove(p)
        for rel in files_under(stage):
            if rel.split('/')[0] in ('git.log', 'workflow.jsonl', 'Brief', 'Screenshots'):
                copy_file(os.path.join(stage, *rel.split('/')), os.path.join(ds, *rel.split('/')))
        write_text(os.path.join(ds, 'README.md'), apply_rules(dataset_readme(ctx, True), rules, False, False))
        # the files are committed byte for byte as manifest.json lists them: no line-ending conversion (Git for Windows'
        # core.autocrlf with the template's "* text=auto" checks them out with CRLF, and every size and sha256 differs)
        write_text(os.path.join(ds, '.gitattributes'), '* -text\n' + ''.join(
            f'*.{e} filter=lfs diff=lfs merge=lfs -text\n' for e in ('mp4', 'png', 'jpg', 'jpeg', 'webp')))
        write_manifest(ds, dict(base, variant='repo-dataset', history=None, build=None, tasks=None))
        rv = validate(ds, True)
        if rv['errors']:
            for e in rv['errors'][:30]:
                print('  x ' + e)
            raise Refused(f'{ds} is not valid ({len(rv["errors"])} error(s))')
    remove_tree(bare)

    sizes = {}
    for rel in files_under(stage):
        top = rel.split('/')[0] if '/' in rel else '(top level)'
        sizes[top] = sizes.get(top, 0) + os.path.getsize(lp(os.path.join(stage, *rel.split('/'))))
    print(f'\nOK  {zip_path or stage}  (pending: {", ".join(PENDING)})')
    for k in sorted(sizes):
        print(f'  {k:<16} {sizes[k] / 1e6:12.1f} MB')
    if zip_path:
        print(f'  {"zip":<16} {os.path.getsize(zip_path) / 1e6:12.1f} MB  ({n_zip} files)')
    print(f'  history: {n_commits} commits ({log_commits} in git.log), {len(need)} LFS objects; project: {n_project} files; '
          f'build: {n_build} files; tasks: {len(task_rows)}')
    for n in ('messages.jsonl', 'actions.jsonl'):
        s = ses_stats.get(n)
        print(f'  History/sessions/{n}: ' + (f'{s["rows"]} of {s["source_rows"]} rows' if s else 'not recorded'))
    for w in warnings + verdict['warnings']:
        print('  warning: ' + w)
    for p in problems:
        print('  ' + p)
    print(f'  {(time.time() - t0) / 60:.1f} min')
    return 0


def scrub_tree(root, rules, counts, touched):
    """Apply the scrub rules to every text file under root, in place (History/lfs/objects and the bundle are not text)."""
    for rel in files_under(root):
        if rel.startswith('History/lfs/objects/') or rel.endswith('.bundle'):
            continue
        full = os.path.join(root, *rel.split('/'))
        size = os.path.getsize(lp(full))
        if size == 0 or size >= (256 << 20):
            continue
        data = read_bytes(full)
        if not is_text(rel, data[:8000]):
            continue
        text, enc = decode(data)
        is_json = rel.lower().endswith(('.json', '.jsonl'))
        new = apply_rules(text, rules, is_json, is_json or rel == 'git.log' or rel.startswith('History/sessions/'), counts)
        if new != text:
            write_bytes(full, new.encode(enc, 'replace'))
            if touched is not None:
                touched.append(rel)


def remap_tree(root, cmap):
    """Every full commit id of the map in the text files under root -> its delivered id. Returns the files changed."""
    if not cmap:
        return 0
    rx, n = re.compile(r'(?<![0-9a-f])[0-9a-f]{40}(?![0-9a-f])'), 0
    for rel in files_under(root):
        if rel.startswith('History/lfs/objects/') or rel.endswith('.bundle') or rel == 'git.log':
            continue
        full = os.path.join(root, *rel.split('/'))
        size = os.path.getsize(lp(full))
        if size == 0 or size >= (256 << 20):
            continue
        data = read_bytes(full)
        if not is_text(rel, data[:8000]):
            continue
        text, enc = decode(data)
        new = rx.sub(lambda m: cmap.get(m.group(0), m.group(0)), text)
        if new != text:
            write_bytes(full, new.encode(enc, 'replace'))
            n += 1
    return n


def write_manifest(root, meta):
    """manifest.json: meta, then path, bytes and sha256 of every other file (History/lfs/objects is content-addressed:
    counted in history, not listed)."""
    files = []
    for rel in files_under(root):
        if rel in ('manifest.json', '.gitattributes') or rel.startswith('History/lfs/objects/'):
            continue
        full = os.path.join(root, *rel.split('/'))
        files.append({'path': rel, 'bytes': os.path.getsize(lp(full)), 'sha256': sha256_file(full)})
    m = dict(meta)
    m['totals'] = {'files': len(files), 'bytes': sum(f['bytes'] for f in files)}
    m['files'] = files
    write_text(os.path.join(root, 'manifest.json'), json.dumps(m, indent=1, ensure_ascii=False) + '\n')


def validate(path, repo_dataset=False):
    """tools/validate-game.py's dataset checks on a delivery folder, and with them tools/validate-dataset.ps1 where
    PowerShell is installed: {'errors': [...], 'warnings': [...]}."""
    spec = importlib.util.spec_from_file_location('validate_game', os.path.join(HERE, 'validate-game.py'))
    vg = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(vg)
    rep = vg.Report()
    vg.check_dataset(rep, path, 'dataset')
    vg.run_layout_validator(rep, path, repo_dataset)
    return {'errors': [f'{a}: {m}' for s, a, m in rep.items if s == 'error'],
            'warnings': [f'{a}: {m}' for s, a, m in rep.items if s == 'warning']}


def zip_tree(root, zip_path, top):
    """root as <top>/ in a zip (ZIP64): compressed formats stored, the rest deflated lightly. Returns the entry count."""
    n = 0
    with zipfile.ZipFile(zip_path, 'w', allowZip64=True) as z:
        for rel in files_under(root):
            full = lp(os.path.join(root, *rel.split('/')))
            stored = os.path.splitext(rel)[1].lower() in STORED_EXT
            z.write(full, f'{top}/{rel}', zipfile.ZIP_STORED if stored else zipfile.ZIP_DEFLATED, None if stored else 1)
            n += 1
    with zipfile.ZipFile(zip_path) as z:
        if len(z.namelist()) != n:
            raise Refused(f'{zip_path} holds {len(z.namelist())} entries, expected {n}')
    return n


def tasks_readme(game, rows):
    a = ['# Tasks', '',
         "Tasks an agent can be given on this game, in a game-creation environment's task format (GameTask, game-task/1).",
         "Each task is split in two, so the grader's half is never handed to an agent by mistake:", '',
         '| File | Holds |', '|---|---|',
         '| `<name>/task.json` | what the agent may see: `name`, `title`, `instruction` (the brief), `engine`, `seed` (`game`, `commit`: where it starts, `kind`: bug_fix, feature, change or correction), `play_scene` (the scene graders open), `play_args`, `player`, `asset_packs`, `difficulty`, `tags`, `limits` (turns, minutes, cost, tool timeout) |',
         "| `<name>/grader.json` | the grader's half: `milestones` (ordered groups of checks: build, boot, probes, logs, files, and judged questions with rubrics) and `seed.reference` (a later commit whose change solves the task) |",
         '', "Merging `grader.json` into `task.json` (its `seed` into the task's `seed`) gives the whole task.", '',
         '**The harness rule.** An agent given a task starts from a snapshot of the game at `seed.commit` with no git history and',
         "without `Tasks/`, `History/` and `Dataset/` (they hold every task's rubrics and the reference fixes). It sees the brief",
         'and that snapshot only; `grader.json` and `seed.reference` are for grading.', '',
         f"The seed commits are commits of `History/{game}.bundle`. Make a task's start:", '', '```',
         f'git clone History/{game}.bundle work', 'robocopy History\\lfs work\\.git\\lfs /E          # or: cp -r History/lfs work/.git/',
         'cd work', 'git lfs install --local', 'git checkout <seed.commit>', 'git lfs checkout', '```', '',
         'then copy the working tree, without `.git`, `Tasks/`, `History/` and `Dataset/`, to where the agent works.', '',
         '| Task | Kind | Difficulty | Title |', '|---|---|---|---|']
    a += [f'| `{r["name"]}` | {r["kind"]} | {r["difficulty"]} | {r["title"]} |' for r in rows]
    return '\n'.join(a) + '\n'


def dataset_readme(c, repo):
    """README.md of the delivery (repo: of the game repo's Dataset/ folder), sections in the layout's order."""
    game, title, shots = c['game'], c['title'], c['shots']
    a = [f'# {title}', '']
    if shots:
        a += [f'![{title}](Screenshots/{shots[0][0]})', '']
    a += ['> **Pending:** `ReplayScripts/` (the replay of the creation process) and `Gameplay/` (the scenario videos) are not in',
          '> this delivery yet; everything else is complete.', '']
    intro = c['readme_src'].split('\n## ')[0]
    intro = '\n'.join(l for l in intro.splitlines()[1:] if not re.match(r'\s*(!\[|<img)', l)).strip()
    if intro:
        a += [intro, '']
    a += [f'Version {c["version"] or "(not numbered)"}, release commit `{c["head"]}`.', '',
          '## Requirements', '',
          f'- Unity {c["engine"]} (Unity 6.3 LTS, with Windows Build Support) to open the project' + ('.' if repo else '; nothing to run the built player.'),
          '- 64-bit Windows 10/11 for the built player.', '- `git` and `git-lfs` to restore the history.', '',
          '## Package contents', '']
    if not repo:
        a.append('- `UnityProject/` — the completed game project at the release commit (`Assets/` with every `.meta`, `Packages/`, `ProjectSettings/`).')
    a += ['- `ReplayScripts/` — replay of the creation process from the recorded editor operations. *(pending)*',
          '- `workflow.jsonl` — editor, code and build operations, one row per operation, written when it happened. Rows with `actor` "user" and '
          '`op` "user.direction" summarise what the person directing the work asked for; later rows name the direction they act on.',
          '- `git.log` — every commit with its message and full diff (binary files as path and sha256).']
    if not repo:
        a.append(f'- `History/` — the full git history: `History/{game}.bundle` (every commit up to the release, and each task\'s start branch) and '
                 '`History/lfs/objects/` (every Git LFS file of every commit). Authors are anonymised as dev_NN.')
        if c['sessions']:
            a.append('  `History/sessions/` — the creation sessions as recorded, one JSON row per line, oldest first within a session: ' +
                     ('`messages.jsonl` holds every prompt the person typed (`role` "user") and every reply the model wrote (`role` "assistant"); '
                      if 'messages.jsonl' in c['sessions'] else '') +
                     ('`actions.jsonl` holds every tool call with its input and the start of its result. ' if 'actions.jsonl' in c['sessions'] else '') +
                     '`session_id` (session_NN) and `time` tie the rows of one session together.')
    a.append('- `Brief/` — the original brief the game was built from (`Brief/brief.md`) and its design doc with story bible and status (`Brief/design.md`).')
    if not repo:
        a.append(f'- `Tasks/` — {len(c["task_rows"])} task(s) on this game for a game-creation environment (`Tasks/README.md`).')
    a.append('- `Gameplay/` — videos of the recorded scenarios, played through with the game audio. *(pending)*')
    if not repo:
        a.append(f'- `Build/` — the Windows player (`Build/{c["exe"]}`).')
    a += ['- `Screenshots/` — the images in this README.', '- `manifest.json` — path, size and sha256 of every file, and the release metadata.', '',
          'Keep these files and folders together.', '', '## Play the game', '']
    if repo:
        a.append(f'Open the repository root as a project in Unity {c["engine"]} and press **Play**.')
    else:
        a.append(f'Run `Build/{c["exe"]}` (no installation), or open `UnityProject/` in Unity {c["engine"]} and press **Play**.')
    play = md_section(c['readme_src'], r'^(how to )?play|^controls')
    if play:
        a += ['', '\n'.join(l for l in play.splitlines() if not re.search(r'Build[/\\]', l)).strip()]
    a += ['', '## Replay the creation process', '', '`ReplayScripts/` is pending.', '', '## Restore the git history', '']
    if repo:
        a.append('This repository is the history itself: every commit, with Git LFS for the binary files.')
    else:
        a += ["`History/` restores the project's repository at any commit (`git` and `git-lfs` needed):", '', '```',
              f'git clone History/{game}.bundle {game}', f'robocopy History\\lfs {game}\\.git\\lfs /E          # or: cp -r History/lfs {game}/.git/',
              f'cd {game}', 'git lfs install --local', 'git checkout <commit>      # any commit of git.log; main is the release commit',
              'git lfs checkout', '```', '', f'The release commit is `{c["head"]}`; `git.log` and the tasks use the same commit ids.']
    a += ['', '## Tasks', '']
    if repo:
        a.append("The game's tasks are kept out of this history, on a separate orphan branch of the repository (`Tasks/`, one task per file); "
                 "the dataset zip ships them split into the agent's and the grader's parts.")
    else:
        a += [f"`Tasks/` holds {len(c['task_rows'])} task(s) on this game in a game-creation environment's format, each split into `<name>/task.json`",
              '(what the agent sees) and `<name>/grader.json` (milestones with rubrics, and `seed.reference`). A task starts the project at a',
              'commit of `History/` (its `seed`); `Tasks/README.md` explains the fields. **An agent starts from a snapshot at `seed.commit`',
              'with no history and without `Tasks/`, `History/` and `Dataset/`, and never sees `grader.json`.**', '',
              '| Task | Kind | Difficulty | Title |', '|---|---|---|---|']
        a += [f'| `{r["name"]}` | {r["kind"]} | {r["difficulty"]} | {r["title"]} |' for r in c['task_rows']]
    a += ['', '## Scenarios', '']
    scen = md_section(c['readme_src'], r'^scenarios')
    a += [scen if scen else 'The scenario videos are pending.', '', '## Screenshots', '']
    for name, alt in shots:
        a += [f'![{alt}](Screenshots/{name})', '']
    a += ['## Assets and licences', '']
    lic = md_section(c['readme_src'], r'^(assets|credits|licen[cs]es?|third[- ]party)')
    where = '`assets.manifest.json` (repository root) and `Docs/ThirdPartyNotices.md`' if repo else '`UnityProject/assets.manifest.json` and `UnityProject/Docs/ThirdPartyNotices.md`'
    a += [f'Every external asset, with its source and licence, is listed in {where}.']
    if lic:
        a += ['', lic]
    a += ['', '## Integrity', '', '`manifest.json` lists every file with its size and sha256. Check with PowerShell (read it as UTF-8):', '', '```',
          '$m = Get-Content manifest.json -Raw -Encoding UTF8 | ConvertFrom-Json',
          '$m.files | ? { (Get-FileHash -Algorithm SHA256 -LiteralPath $_.path).Hash -ne $_.sha256 } | % path   # prints nothing when all match', '```']
    return '\n'.join(a) + '\n'


if __name__ == '__main__':
    sys.exit(main())
