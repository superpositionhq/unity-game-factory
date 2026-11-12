#!/usr/bin/env python3
"""Build a Unity game's dataset (unity-dataset-layout/v1, docs/game-format.md): <repo>/Dataset.zip, or
<repo>/Dataset.pending.zip while the creation replay is missing.

    python tools/package-dataset.py <slug>                      # the game at <root>/games/<slug>, its HEAD
    python tools/package-dataset.py <slug> --commit <rev> --version 1.0 --brief <brief.md> --design <design.md>
    python tools/package-dataset.py <slug> --dry-run            # what would go in; writes nothing
    python tools/package-dataset.py <slug> --rescan <zip>       # scan a delivered dataset again
    python tools/package-dataset.py --self-check                # the scrub and scan rules on built-in samples

What it packs, from the game repo at the release commit (--commit milestone: the newest milestone/autoplay-<n> tag),
its recording (<root>/.recording/<slug>/) and the release's three products: the player (the pipeline's release build
<root>/builds/<slug>/<sha8>/ with build_info.json, else <repo>/Build/Windows from Scripts/unity.ps1 build; --build names
another), the recordings (<root>/recordings/<slug>/) and the creation replay (<out>/_replay/<slug>/<release sha8>/ with
READY; --replay names another):

    History/<slug>.bundle     the history rewritten for delivery: authors and committers dev_NN, agent trailer lines
                              gone, the scrub rules on every message and text blob, LFS pointers to patched objects.
                              The release commit as refs/heads/main and each task's start branch
                              (refs/heads/starts/<task>), nothing else: a side branch, a tag off main or a stash can
                              hold work the tasks ask for.
    History/lfs/objects/      every Git LFS object of every commit of the bundle, from the repo's own store; one that
                              names the account or an agent in a path, a whole string or an XML element as a copy
                              patched byte for byte (tools/unity-pipeline/export-lfs-history.py)
    History/sessions/         the creation sessions as recorded: messages.jsonl (every prompt the person typed and
                              every reply the model wrote) and actions.jsonl (every tool call), rows up to the release
                              commit, each session named session_NN in both
    git.log                   every commit of the delivered history up to the release, oldest first, with full diffs
    workflow.jsonl            the creation record at the release commit
    UnityProject/             the delivered tree at the release commit, LFS files as their real content (no Dataset/)
    Tasks/                    the tasks of the repo's tasks branch, seeds mapped to the delivered history, each split
                              into task.json and grader.json (tools/split-tasks.py), and a README.md
    Brief/                    brief.md and design.md (--brief / --design, else the release commit's, see find_brief)
    Gameplay/<slug>_S<n>.mp4  per scenario, the gameplay.mp4 of its first valid recording of the release commit
                              (gameplay_runs); the result is metadata, never a reason to pick a run
    ReplayScripts/            the creation replay's package, its commit ids mapped; its verdict, PASS or FAIL, becomes
                              manifest.json replay_verification
    Screenshots/              the images the game's README.md shows, else Docs/screenshots/, else the recordings' stills
    Build/                    the Windows release player, without .pdb files and Unity's "do not ship" folders
    README.md, manifest.json

Status "complete" and Dataset.zip when Gameplay/ holds a video and ReplayScripts/ is there (a FAIL verdict too);
while ReplayScripts/ is missing "pending", listed in the manifest's pending, and Dataset.pending.zip. A game without a
gameplay video is rejected by the Lab: with no valid recording of the release commit nothing is packaged. A pipeline build
whose leak scan found anything, a development player or another product's, and a running pipeline job of the game
(its lock in <root>/builds/) refuse the package.

Every text file of the delivery is scrubbed (studio and tool names, agent, model and provider names, the account and
machine name, e-mail addresses, git identities, the build machine's session folders and ids) and then scanned: a name
left in a text file or a path refuses the package (exit 2, nothing zipped; hits in <scratch>/<slug>.refused-hits.tsv).
Binary files are never changed: a name in one refuses the package too (--lenient-binaries lists them without refusing,
to review a refusal), except the allowed forms (scan_binary: the Opus codec's names, compressed bytes, a media file's
compressed payload, a locale id, a reviewed hit from --reviewed-hits); the history's people's names and addresses
refuse in binaries as well. Commit ids change with the rewrite: the delivery uses the new ids everywhere, and
<out>/<slug>/<slug>_<sha8>.commit-map.tsv keeps original -> delivered (<out>: env UGF_OUT, config "out", else
<root>/deliverables), beside the run's audit files (<slug>_<sha8>.scrub-report.json, .allowlisted.tsv,
.binary-emails.tsv, .leaks.tsv) and package-log.jsonl.

It ends with the checks a consumer runs: tools/validate-game.py --dataset on the delivery (an error refuses the
package). Then it writes the zip and, unless --no-repo-dataset, the repo's Dataset/ folder (the delivery minus
UnityProject/, Build/, History/ and Tasks/) for the game session to commit. Nothing is committed here, and the game
repo's history is not changed. One run per game at a time (<out>/<slug>/.package.lock). Scratch: <repo>/.dataset/
(git-ignored; .git/info/exclude when the repo's .gitignore lacks it). Standard library, Python 3.10+, git, git-lfs; the
pipeline's ffprobe checks the videos where it is found.
"""
import argparse, base64, getpass, glob, hashlib, importlib.util, json, os, re, shutil, socket, stat, subprocess, sys, time, zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, 'machine', 'lib'))
import ugfroot  # noqa: E402

LAYOUT = 'unity-dataset-layout/v1'
with open(os.path.join(REPO, 'docs', 'dataset-layout-v1.json'), encoding='utf-8') as _f:
    LAYOUT_SPEC = json.load(_f)
SECTIONS = ('Requirements', 'Package contents', 'Play the game', 'Replay the creation process',
            'Restore the git history', 'Tasks', 'Scenarios', 'Screenshots', 'Assets and licences', 'Integrity')
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


def hold_lock(path):
    """The open file of an exclusive lock on path, held until the process ends (the OS frees it when a run dies); Refused
    while another run holds it: two runs on one game empty each other's scratch and write the same Dataset/."""
    os.makedirs(lp(os.path.dirname(path)), exist_ok=True)
    f = open(lp(path), 'a+b')
    try:
        if os.name == 'nt':
            import msvcrt
            f.seek(0)
            msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        f.close()
        raise Refused(f'another package-dataset run of this game holds {path}: wait for it to finish')
    return f


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


def tool(name, *rel):
    """A tool of this repo, loaded as a module (its file name has dashes)."""
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, *rel))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


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
# (id, scope, pattern, replacement, hint). Scopes: all | json (.json/.jsonl) | lines (other text) | logs (git.log,
# History/sessions/). hint: lower-case text a file must hold for the rule to be tried. Applied in this order.
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
         # file names are not addresses: Unity names a model's clips <model>@<clip>.fbx and keeps the @ in the clips,
         # controllers and masks made from them (Keeper@Walk.anim), in either case; another .ext after the "domain" too
         r'(?!(?i:png|jpe?g|tga|gif|svg|webp|exr|hdr|bmp|dds|psd|tiff?|unity|prefab|mat|asset|meta|anim|controller|'
         r'overrideController|mask|playable|signal|wav|ogg|mp3|flac|aiff?|fbx|glb|gltf|obj|blend|dae|json|jsonl|txt|md|ini|'
         r'py|ps1|sh|cs|bin|zip)\b)'
         r'[A-Za-z]{2,}\b(?!\.[A-Za-z0-9])')
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
    # a session folder cut short (a recorded command is clipped): Temp/<tool>/<project>/<start of the uuid> at a string's end
    add('session-path', 'all', r'(?i)(AppData[\\/]+Local[\\/]+Temp[\\/]+)[^\\/\s\'"]+[\\/]+[^\\/\s\'"]+[\\/]+[0-9a-f]{8}'
        r'(?:-[0-9a-f]{0,12}){0,4}(?=\\?"|\'|$)', r'\g<1>session', 'temp')
    # the desktop app's side-session notes folder: AppData/Roaming/<app>/side-session-notes/local_<uuid>
    add('session-path', 'all', r'(?i)(AppData([\\/]+)Roaming\2)[^\\/\s\'"]+\2side-session-notes\2local_' + UUID,
        r'\g<1>session\g<2>notes', 'side-session')
    add('session-path', 'all', r'(?i)\blocal_' + UUID + r'\b', 'session', 'local_')
    add('session-path', 'all', r'(?i)side-session-notes', 'session-notes', 'side-session')
    add('session-path', 'all', r'(?i)scratchpad', 'scratch', 'scratchpad')
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
    # the model's name as a segment of a run or file name in the sessions' record (pilot-2c-opus-siege, run-opus-win.png)
    add('agent-mention', 'json', r'(?i)(?<=[A-Za-z0-9][-_.])opus(?=[-_}]|\.[A-Za-z]{2,4}\b)', 'model', 'opus')
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
        # shell dropped). Named: the scan allows it in a zh_ locale id and in escaped random bytes.
        parts.append(r'(?:(?<=\\[nrtfb])|(?<=\\u[0-9a-fA-F]{4})|(?<![A-Za-z])|(?-i:(?<=[a-z])(?=[A-Z])))(?P<user>' + re.escape(user) +
                     r')(?:(?![A-Za-z])|(?-i:(?<=[a-z])(?=[A-Z])))')
    elif user:
        parts.append(r'(?:users|home)[\\/]{1,2}(?P<user>' + re.escape(user) + r')(?![A-Za-z0-9_])')
    for term, _ in identities:
        tail = '[A-Za-z0-9]*' if re.search(r'\d', term) and len(term) >= 5 else '(?![A-Za-z0-9])'
        parts.append(WORD_START + re.escape(term) + tail)
    if not user:
        parts.append(r'(?P<user>(?!x)x)')   # the group the scan reads, never matching
    return re.compile('|'.join(f'(?:{p})' for p in parts), re.I)


def identity_emails(repo):
    """The e-mail addresses of the history's authors and committers (the people who made the game), example, no-reply
    and dev_NN addresses left out: a binary that carries one refuses the package."""
    out = set()
    for a in git_text(repo, 'log', '--format=%ae%n%ce', *HISTORY_REFS, check=False).splitlines():
        a = a.strip().lower()
        if '@' in a and 'noreply' not in a and not re.match(r'dev_\d+@', a) and \
                not re.search(r'@(?:[\w-]+\.)*(?:example\.(?:com|org|net)|invalid|test|localhost)$', a):
            out.add(a)
    return sorted(out)


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


def rewrite_history(repo, bare, rules, authors, stats, lfs_map=None):
    """Stream `git fast-export` of every ref but the tasks branch and the stash into `git fast-import` of the new bare
    repo: author / committer / tagger -> dev_NN, agent trailer lines of messages dropped, the scrub rules on messages
    and on text blobs (text by the path that first holds the blob); a Git LFS pointer to an object of lfs_map ({oid:
    [new oid, size]}: the objects patched for delivery) points at the patched object, every other pointer stays as it
    is. Returns the original -> delivered commit id map."""
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
                    pm = LFS_PTR.match(d) if n < 300 and d.startswith(LFS_MAGIC) else None
                    if pm and lfs_map and pm.group(1).decode() in lfs_map:
                        new_oid, new_size = lfs_map[pm.group(1).decode()]
                        d = d[:pm.start(1)] + new_oid.encode() + d[pm.end(1):pm.start(2)] + str(new_size).encode() + d[pm.end(2):]
                        stats['lfs_pointers_swapped'] = stats.get('lfs_pointers_swapped', 0) + 1
                    elif d and not (n < 300 and d.startswith(LFS_MAGIC)) and is_text(path, d):
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


def history_texts(bare, refs):
    """(where, text) of every commit message and every text blob reachable from refs but not from main (Git LFS
    pointers and blobs of 256 MB or more left out): what git.log, which the scan reads, does not show. git.log holds
    every message and every added line of main's history; a start branch's own commits are in the bundle alone."""
    for chunk in git(bare, 'log', '--format=%H%x00%B%x00', *refs, '--not', 'refs/heads/main').decode('utf-8', 'replace').split('\0\n'):
        sha, _, msg = chunk.partition('\0')
        if sha.strip():
            yield f'message {sha.strip()[:12]}', msg
    first = {}
    for line in git(bare, 'rev-list', '--objects', *refs, '--not', 'refs/heads/main').decode('utf-8', 'replace').splitlines():
        if len(line) > 41 and line[40] == ' ':
            first.setdefault(line[:40], line[41:])
    cat = CatFile(bare)
    try:
        for oid, path in first.items():
            kind, data = cat.read(oid)
            if kind != 'blob' or not data or len(data) >= (256 << 20) or (len(data) < 300 and data.startswith(LFS_MAGIC)):
                continue
            if is_text(path, data[:8000]):
                yield f'{path} {oid[:12]}', decode(data)[0]
    finally:
        cat.close()


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
def blob_at(repo, rev, path):
    """The bytes of path at rev, or None when it is not there."""
    r = subprocess.run(['git', '-C', repo, 'cat-file', 'blob', f'{rev}:{path}'], capture_output=True)
    return r.stdout if r.returncode == 0 else None


def find_brief(repo, sha, slug, given, kind, warnings):
    """(where, bytes) of the brief as given (kind 'brief') or the design doc ('design'), or None: the file named on the
    command line; else the game repo's Brief/<kind>.md, Docs/<Kind>.md or Docs/<kind>.md as the release commit has it,
    then as the working tree has it (a warning: it is not part of the release); else this repo's docs
    (briefs/original/game-<slug>.md, then briefs/games/<slug>.md, for the brief; games/<slug>.md for the design doc)."""
    if given:
        if not os.path.isfile(given):
            raise Refused(f'--{kind} {given}: no such file')
        return given, read_bytes(given)
    rels = [f'Brief/{kind}.md', f'Docs/{kind.capitalize()}.md', f'Docs/{kind}.md']
    for rel in rels:
        data = blob_at(repo, sha, rel)
        if data is not None:
            return f'{rel} at the release commit', data
    for rel in rels:
        if os.path.isfile(os.path.join(repo, *rel.split('/'))):
            warnings.append(f'{rel} is not in the release commit: Brief/{kind}.md is taken from the working tree (commit it)')
            return rel, read_bytes(os.path.join(repo, *rel.split('/')))
    docs = os.path.join(REPO, 'docs')
    if kind == 'brief':
        cands = [os.path.join(docs, 'briefs', 'original', f'game-{slug}.md'), os.path.join(docs, 'briefs', 'games', f'{slug}.md')]
    else:
        cands = [os.path.join(docs, 'games', f'{slug}.md')]
    for c in cands:
        if os.path.isfile(c):
            return c, read_bytes(c)
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


def screenshots(project, readme_src, runs, dest, warnings):
    """Screenshots/ and its [(file, caption)]: the images the game's README.md shows (alt text as caption), else every
    image in the project's Docs/screenshots/ at the commit, else up to four stills of the recordings taken (round robin
    over the runs: the middle frame first, then the quarter points; stills of other runs may show older art)."""
    shots = []

    def add(src, name, caption):
        name = re.sub(r'[^A-Za-z0-9._-]', '_', name)   # the README links it without escapes
        while any(s[0].lower() == name.lower() for s in shots):
            name = '_' + name
        copy_file(src, os.path.join(dest, name))
        shots.append((name, caption))

    def caption_of(name):
        return re.sub(r'[-_]+', ' ', re.sub(r'^\d+[-_ ]*', '', os.path.splitext(name)[0])).strip() or os.path.splitext(name)[0]

    for alt, rel in readme_images(readme_src):
        src = os.path.join(project, *rel.split('/'))
        if not os.path.isfile(lp(src)):
            warnings.append(f'the README shows {rel}, which is not in the project at the commit')
            continue
        add(src, os.path.basename(rel), alt or os.path.splitext(os.path.basename(rel))[0])
    if shots:
        return shots
    for docs in ('Docs', 'docs'):
        folder = os.path.join(project, docs, 'screenshots')
        if os.path.isdir(lp(folder)):
            for n in sorted(os.listdir(lp(folder))):
                if n.lower().endswith(IMAGE_EXT) and os.path.isfile(lp(os.path.join(folder, n))):
                    add(os.path.join(folder, n), n, caption_of(n))
            if shots:
                warnings.append(f'the README shows no image: Screenshots/ holds {docs}/screenshots/ (show them in the README)')
                return shots
    picked = []
    for pos in (0.5, 0.25, 0.75, 0.1):
        for r in runs:
            if len(picked) < 4 and r['stills']:
                f = r['stills'][min(len(r['stills']) - 1, int(pos * len(r['stills'])))]
                if f not in [p[0] for p in picked]:
                    picked.append((f, r))
    for f, r in picked:
        frame = re.sub(r'^' + re.escape(r['run']) + '_', '', os.path.splitext(os.path.basename(f))[0])
        add(f, f'{r["run"]}_{frame}.jpg', f'Scenario {r["scenario"]} {r["name"]}, frame {frame} of run {r["run"]}')
    if shots:
        warnings.append('the README shows no image and Docs/screenshots/ holds none: Screenshots/ holds stills of the recordings')
    return shots


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


def player_problem(repo, sha, build, exe):
    """Why the player in build is not this game's release player, or None: a development player (its UnityPlayer.dll
    names the development variant's debug symbols, UnityPlayer_Win64_player_development_<backend>_x64.pdb; its
    boot.config also carries the build machine's network address), or another product than the game's
    (<exe>_Data/app.info, company and product name, against ProjectSettings.asset productName at the commit)."""
    up = os.path.join(build, 'UnityPlayer.dll')
    if os.path.isfile(lp(up)) and re.search(rb'UnityPlayer_Win64_\w*_development_\w*\.pdb', read_bytes(up)):
        return f'{exe} is a development player: the dataset ships the release player (Scripts\\unity.ps1 build, without -Development)'
    m = re.search(r'(?m)^\s*productName:\s*(.+?)\s*$', git_text(repo, 'show', f'{sha}:ProjectSettings/ProjectSettings.asset', check=False))
    info = os.path.join(build, exe[:-4] + '_Data', 'app.info')
    lines = [l.strip() for l in read_bytes(info).decode('utf-8', 'replace').splitlines() if l.strip()] if os.path.isfile(lp(info)) else []
    if m and lines and lines[-1] != m.group(1):   # app.info: company name, then product name
        return f'{exe} is a player of "{lines[-1]}", not of this game ("{m.group(1)}" at the commit)'
    return None


# ---- the release's products: the pipeline's player, the recordings, the creation replay ----------------------------------
RESULTS = ('win', 'lose', 'timeout', 'abort')


def read_json(path):
    """The JSON object in a file (UTF-8 with or without the BOM PowerShell writes), or None."""
    try:
        with open(lp(path), encoding='utf-8-sig') as f:
            v = json.load(f)
    except (OSError, ValueError):
        return None
    return v if isinstance(v, dict) else None


def pipeline_job(root, game):
    """The pipeline job holding the game's lock right now, or None. build.ps1 and record.ps1 hold
    <root>/builds/_pipeline-<game>.lock open with no sharing while they write the game's player or a recording
    (tools/unity-pipeline/common.ps1 Enter-PipelineLock), and name themselves in <lock>.json; an open that fails with a
    sharing violation is the sign. The pipeline runs on Windows only."""
    path = os.path.join(root, 'builds', f'_pipeline-{game}.lock')
    if os.name != 'nt' or not os.path.isfile(lp(path)):
        return None
    try:
        with open(lp(path), 'rb'):
            return None
    except PermissionError:
        h = read_json(path + '.json') or {}
        return f'{h.get("job") or "a pipeline job"} (pid {h.get("pid", "?")}, since {h.get("since", "?")})'
    except OSError:
        return None


def pipeline_builds(root, game, lineage):
    """[(age, folder, build_info)] of the pipeline's release builds of the game in the release commit's history, nearest
    first (age: commits before the release commit, 0 = the release commit itself): <root>/builds/<game>/<sha8>/ with its
    player in Windows/ and build_info.json (unity-build/1) status "ok", config "release"."""
    base, out = os.path.join(root, 'builds', game), []
    if not os.path.isdir(lp(base)):
        return out
    for d in sorted(os.listdir(lp(base))):
        full = os.path.join(base, d)
        if d.startswith('_') or not os.path.isdir(lp(os.path.join(full, 'Windows'))):
            continue
        info = read_json(os.path.join(full, 'build_info.json'))
        if info and info.get('status') == 'ok' and str(info.get('config', '')).lower() == 'release' and info.get('commit') in lineage:
            out.append((lineage[info['commit']], full, info))
    return sorted(out, key=lambda t: t[0])


def find_ffprobe():
    """ffprobe where the pipeline finds ffmpeg (tools/unity-pipeline/common.ps1 Find-FFmpeg): beside env UGF_FFMPEG,
    the pinned copy under <root>/tools/ffmpeg-<version>/ (machine/get-ffmpeg.ps1), PATH, the winget package; else None."""
    name = 'ffprobe.exe' if os.name == 'nt' else 'ffprobe'
    cands = [os.path.join(os.path.dirname(os.environ['UGF_FFMPEG']), name)] if os.environ.get('UGF_FFMPEG') else []
    cands += sorted(glob.glob(os.path.join(ugfroot.root(), 'tools', 'ffmpeg-*', '*', 'bin', name)), reverse=True)
    cands.append(shutil.which('ffprobe') or '')
    if os.environ.get('LOCALAPPDATA'):
        cands += glob.glob(os.path.join(os.environ['LOCALAPPDATA'], 'Microsoft', 'WinGet', 'Packages', 'Gyan.FFmpeg*', '**', name), recursive=True)
    return next((c for c in cands if c and os.path.isfile(c)), None)


def probe_video(ffprobe, path):
    """(why it is not the layout's gameplay video or None, seconds): an mp4 with one h264 1920x1080 stream and aac audio
    (dataset-layout-v1.json gameplay_video)."""
    want = LAYOUT_SPEC['gameplay_video']
    try:
        r = subprocess.run([ffprobe, '-v', 'error', '-show_entries', 'stream=codec_type,codec_name,width,height:format=format_name,duration',
                            '-of', 'json', path], capture_output=True, timeout=300)
        j = json.loads(r.stdout.decode('utf-8', 'replace') or '{}')
    except (OSError, ValueError, subprocess.TimeoutExpired) as e:
        return f'ffprobe failed: {e}', 0.0
    fmt, streams = j.get('format') or {}, j.get('streams') or []
    v = [s for s in streams if s.get('codec_type') == 'video']
    a = [s for s in streams if s.get('codec_type') == 'audio']
    try:
        seconds = float(fmt.get('duration') or 0)
    except ValueError:
        seconds = 0.0
    if not fmt:
        return 'not readable as a video', seconds
    if want['container'] not in str(fmt.get('format_name', '')):
        return f'not an {want["container"]} ({fmt.get("format_name")})', seconds
    if len(v) != 1 or v[0].get('codec_name') != want['video_codec'] or (v[0].get('width'), v[0].get('height')) != (want['width'], want['height']):
        return 'video ' + (', '.join(f'{s.get("codec_name")} {s.get("width")}x{s.get("height")}' for s in v) or 'missing'), seconds
    if want.get('audio_required') and (not a or a[0].get('codec_name') != want['audio_codec']):
        return 'audio ' + (', '.join(str(s.get('codec_name')) for s in a) or 'missing'), seconds
    return None, seconds


def gameplay_runs(root, game, sha, exclude, ffprobe):
    """Per scenario, the first valid recording of the release commit, by run id (<game>_S<n>_<yyyyMMdd-HHmmss>_s<seed>:
    the earliest first): <root>/recordings/<game>/<run id>/ with metadata.json (unity-autoplay-bundle/v1) build.commit =
    the release commit, validation.json status ok or warn (written last, so a run still being written is not taken),
    neither FAILED nor INVALID, and its gameplay.mp4 (the layout's video, when ffprobe is here to check it). The result
    (win, lose, timeout, abort) is metadata, never a reason to pick a run. Returns ([run], [(run id, why it is not
    taken)]), runs in scenario order."""
    base = os.path.join(root, 'recordings', game)
    chosen, skipped = {}, []
    if not os.path.isdir(lp(base)):
        return [], []
    for name in sorted(os.listdir(lp(base))):
        d = os.path.join(base, name)
        if name.startswith('_') or not os.path.isdir(lp(d)):
            continue
        meta, val = read_json(os.path.join(d, 'metadata.json')), read_json(os.path.join(d, 'validation.json'))
        mp4 = os.path.join(d, 'gameplay.mp4')
        built = str(((meta or {}).get('build') or {}).get('commit') or '')
        n = (meta or {}).get('scenario')
        why = None
        if name in exclude:
            why = 'left out with --exclude-runs'
        elif os.path.exists(lp(os.path.join(d, 'INVALID'))):
            why = 'INVALID (mark-invalid.ps1)'
        elif os.path.exists(lp(os.path.join(d, 'FAILED'))):
            why = 'FAILED'
        elif not meta or not val:
            why = 'no metadata.json or validation.json (not finished)'
        elif val.get('status') not in ('ok', 'warn'):
            why = f'validation {val.get("status")}'
        elif built != sha:
            why = f'recorded from {built[:8] or "an unknown build"}, not from the release commit'
        elif not isinstance(n, int) or isinstance(n, bool) or n < 1:
            why = 'no scenario number'
        elif n in chosen:
            continue   # the scenario's earlier valid run is taken
        elif meta.get('result') not in RESULTS:
            why = f'result {meta.get("result")!r} is not one of {", ".join(RESULTS)}'
        elif not os.path.isfile(lp(mp4)):
            err = ((meta.get('gameplay_mp4') or {}).get('error') or 'never written')
            why = f'no gameplay.mp4 ({err}): tools/unity-pipeline/gameplay-mp4.ps1 {game} -RunId {name} writes it'
        if why:
            skipped.append((name, why))
            continue
        gm = meta.get('gameplay_mp4') or {}
        seconds = ((val.get('checks') or {}).get('video') or {}).get('duration_s') or gm.get('duration_s')
        if ffprobe:
            bad, probed = probe_video(ffprobe, lp(mp4))
            if bad:
                skipped.append((name, f'gameplay.mp4 is not the layout\'s video ({bad}): tools/unity-pipeline/gameplay-mp4.ps1 '
                                      f'{game} -RunId {name} -Force writes it again'))
                continue
            seconds = seconds or probed
        offset = gm.get('audio_offset_s')
        if offset is None:
            try:
                offset = (float((meta.get('system_audio') or {}).get('start_offset_ns')) - float(meta.get('video_start_offset_ns'))) / 1e9
            except (TypeError, ValueError):
                offset = None
        stills = sorted(glob.glob(os.path.join(glob.escape(os.path.join(base, '_stills')), glob.escape(name) + '_*.jpg')))
        if not stills:   # the bundle's own stills\NN.jpg, delivered under the run's name as _stills\ has them
            stills = sorted(glob.glob(os.path.join(glob.escape(d), 'stills', '*.jpg')))
        chosen[n] = {'run': name, 'dir': d, 'mp4': mp4, 'scenario': n, 'name': str(meta.get('scenario_name') or f'Scenario {n}'),
                     'result': meta['result'], 'seconds': round(float(seconds or 0), 3),
                     'audio_offset_s': None if offset is None else round(float(offset), 3),
                     'capture_notes': str(meta.get('capture_notes') or '').strip(), 'stills': stills}
    return [chosen[k] for k in sorted(chosen)], skipped


def ready_scenarios(repo, sha):
    """n of the newest milestone/autoplay-<n> tag in the release commit's history: scenarios 1..n are ready to record
    (tools/unity-pipeline/pipeline.ps1 reads the same tags); 0 without one."""
    tags = git_text(repo, 'tag', '--merged', sha, '--list', 'milestone/autoplay-*', check=False).split()
    return max((int(m.group(1)) for t in tags if (m := re.fullmatch(r'milestone/autoplay-(\d+)', t))), default=0)


def replay_verification(report):
    """manifest.json replay_verification from ReplayScripts/Verification/report.json: the verdict's pass, its criteria
    and its exclusions as {id, what, count} (the report lists them, or keys them by id)."""
    v = report['verdict']
    crit = [{'id': str(c.get('id', '')), 'text': str(c.get('text', '')), 'result': str(c.get('result', '')), 'pass': bool(c.get('pass'))}
            for c in v.get('criteria') or [] if isinstance(c, dict)]
    ex = v.get('exclusions') or []
    items = ex.items() if isinstance(ex, dict) else ((e.get('id'), e) for e in ex if isinstance(e, dict))
    exclusions = []
    for k, e in items:
        if isinstance(e, (list, str)):
            exclusions.append({'id': str(k), 'what': 'git-ignored extra files', 'count': len(e) if isinstance(e, list) else 1})
        elif isinstance(e, dict):
            cnt = e.get('count')
            exclusions.append({'id': str(k), 'what': str(e.get('what', '')),
                               'count': int(cnt) if isinstance(cnt, (int, float)) and cnt >= 0 else len(e.get('maps') or e.get('items') or [])})
    return {'pass': bool(v['pass']), 'report': 'ReplayScripts/Verification/report.md', 'criteria': crit, 'exclusions': exclusions}


# ---- scan ------------------------------------------------------------------------------------------------------------------
# A binary hit is checked against the word around it (letters, digits, _ . / : -): the Opus audio codec's own forms
# (engine, media and SDK code name it everywhere; the model's name is "opus" as a word of its own), Authenticode's
# SpcSpOpusInfo (Mono's security library in every Mono player) and the bare codec name. One segment of a scoped or path
# word is enough (third_party/opus/src/x.c, Media::OpusDecoder).
OPUS_CODEC = (r'(?:^|.*/)third_party/opus/.*', r'libopus(?:file|enc|dec)?(?:\.(?:dll|lib|so|a|h))?',
              r'opus(?:file|enc|dec)(?:\.(?:dll|lib|so|a|h))?', r'opus_(?:[a-z][a-z0-9_]*)?', r'OPUS_(?:[A-Z][A-Z0-9_]*)?',
              r'\w*WebRtcOpus_\w*', r'WebRTC-[\w-]*Opus[\w-]*', r'OpusCustom\w*', r'opus[-_]codecs?', r'ogg[/_-]opus',
              r'\.opus', r'[\w./-]*/[\w-]+\.opus', r'\w*Audio(?:En|De)coder\w*Opus\w*',
              r'\w*Opus(?:Impl|Config|Decoder|Encoder|AudioInfo|Format|Codec|Header|Head|Tags|File)\w*',
              r'[\w./-]*opus[\w.-]*\.(?:c|cc|cpp|h)', r'opus/\d+(?:/\d+)?', r'audio/opus', r'A_OPUS', r'Opus\w*(?:Decoder|Encoder)\w*',
              r'\w*SpOpusInfo\w*', r'SPC_SP_OPUS_INFO\w*')
ALLOW_BIN = re.compile(r'^(?:[\w./:-]*?[:/])?(?:' + '|'.join(OPUS_CODEC) + r')(?:[:/.][\w./:-]*)?$|^(?:[\w./:-]*?/)?opus$', re.I)
MODEL_FORM = re.compile(r'(?i)claude|anthropic|opus[-_ .]?v?\d')   # never allowed as random bytes
MIN_ENTROPY = 7.0          # bits per byte: compressed or encrypted data is near 8, text and tables well below
MAX_STREAM_HITS = 1000     # past this, a file's hits inside media payloads refuse again (not chance any more)
MEDIA_EXT = ('.mp4', '.mkv', '.mka', '.wav')
REVIEWED = os.path.join(HERE, 'package-reviewed-hits.tsv')


def short_token(buf, at, n, w):
    """Whether a short needle (an account name of four or five letters, "opus") found at buf[at] with stride w (1 ASCII,
    2 UTF-16LE) stands as a word of its own: spelled as a word is (name, Name, NAME), after a non-letter or at a lower ->
    upper boundary, and not followed by a lower-case letter. The engine's own files spell short names inside longer
    words and identifiers, in any case (System.Core.dll's method names, a word list in mono-2.0-bdwgc.dll)."""
    if w == 2 and any(buf[at + 2 * k + 1] for k in range(n) if at + 2 * k + 1 < len(buf)):
        return False
    s = bytes(buf[at + w * k] for k in range(n)).decode('latin-1')
    if not (s.islower() or s.isupper() or (s[0].isupper() and s[1:].islower())):
        return False

    def char(i):
        return buf[i] if 0 <= i < len(buf) and (w == 1 or (i + 1 < len(buf) and buf[i + 1] == 0)) else 0
    prev, nxt = char(at - w), char(at + n * w)
    letter = lambda c: 65 <= c <= 90 or 97 <= c <= 122   # noqa: E731
    return (not letter(prev) or (97 <= prev <= 122 and s[0].isupper())) and not 97 <= nxt <= 122


def bounded_word(buf, at, n, w):
    """Whether a name found at buf[at] is not part of a longer word: no letter right before or after it."""
    def char(i):
        return buf[i] if 0 <= i < len(buf) and (w == 1 or (i + 1 < len(buf) and buf[i + 1] == 0)) else 0
    letter = lambda c: 65 <= c <= 90 or 97 <= c <= 122   # noqa: E731
    return not letter(char(at - w)) and not letter(char(at + n * w))


def bin_word(buf, at, n, w):
    """The word around a hit (letters, digits, _ . / : -; up to 40 characters each side), decoded as it was found."""
    ok = lambda c: 48 <= c <= 57 or 65 <= c <= 90 or 97 <= c <= 122 or c in b'_./:-'   # noqa: E731
    a = at
    while a - w >= 0 and at - a < 40 * w and ok(buf[a - w]) and (w == 1 or buf[a - w + 1] == 0):
        a -= w
    z = at + n * w
    while z + w - 1 < len(buf) and z - at < 40 * w + n * w and ok(buf[z]) and (w == 1 or buf[z + 1] == 0):
        z += w
    return bytes(buf[a:z:w]).decode('latin-1')


def entropy(buf, at):
    """Shannon entropy (bits per byte) of the 512 bytes around at (0 with fewer than 256 bytes in the buffer)."""
    lo, hi = max(0, at - 256), min(len(buf), at + 256)
    if hi - lo < 256:
        return 0.0
    import math
    counts = {}
    for c in buf[lo:hi]:
        counts[c] = counts.get(c, 0) + 1
    n = hi - lo
    return -sum(k / n * math.log2(k / n) for k in counts.values())


def media_payload(path):
    """Sorted [(start, end)] byte ranges of the compressed audio and video data in a media file, or None when the file is
    no media file this reads (then nothing is relaxed): MP4, the mdat boxes when every track is video or audio (hdlr vide
    or soun); WAV, the data chunk; Matroska (.mkv, .mka), the frame data of the blocks of video and audio tracks."""
    ext = os.path.splitext(path)[1].lower()
    if ext not in MEDIA_EXT:
        return None
    try:
        with open(lp(path), 'rb') as f:
            r = _mp4_payload(f) if ext == '.mp4' else _wav_payload(f) if ext == '.wav' else _mkv_payload(f)
    except (OSError, ValueError, IndexError):
        return None
    return sorted(r) if r else None


def _read_at(f, off, n):
    f.seek(off)
    b = f.read(n)
    if len(b) != n:
        raise ValueError('short read')
    return b


def _mp4_payload(f):
    f.seek(0, 2)
    size_all, pos, mdat, moov = f.tell(), 0, [], None
    while pos + 8 <= size_all:
        h = _read_at(f, pos, 8)
        size, kind, hl = int.from_bytes(h[:4], 'big'), h[4:8], 8
        if size == 1:
            size, hl = int.from_bytes(_read_at(f, pos + 8, 8), 'big'), 16
        elif size == 0:
            size = size_all - pos
        if size < hl or pos + size > size_all:
            return None
        if kind == b'mdat':
            mdat.append((pos + hl, pos + size))
        elif kind == b'moov':
            if size > (256 << 20) or moov is not None:
                return None
            moov = _read_at(f, pos + hl, size - hl)
        pos += size
    if moov is None or not mdat:
        return None
    handlers = []

    def walk(b, start, end):
        p = start
        while p + 8 <= end:
            size, kind = int.from_bytes(b[p:p + 4], 'big'), b[p + 4:p + 8]
            if size < 8 or p + size > end:
                handlers.append(b'?')
                return
            if kind in (b'trak', b'mdia'):
                walk(b, p + 8, p + size)
            elif kind == b'hdlr' and size >= 20:
                handlers.append(b[p + 16:p + 20])
            p += size
    walk(moov, 0, len(moov))
    return mdat if handlers and all(t in (b'vide', b'soun') for t in handlers) else None


def _wav_payload(f):
    h = _read_at(f, 0, 12)
    if h[:4] != b'RIFF' or h[8:12] != b'WAVE':
        return None
    f.seek(0, 2)
    size_all, pos, out = f.tell(), 12, []
    while pos + 8 <= size_all:
        c = _read_at(f, pos, 8)
        size = int.from_bytes(c[4:8], 'little')
        end = min(size_all, pos + 8 + size)
        if c[:4] == b'data':
            out.append((pos + 8, end))
        pos = end + (size & 1)
    return out or None


def _vint(f, pos, keep_marker):
    """(value, length, unknown size) of an EBML variable-length integer: an id keeps its marker bit, a size drops it."""
    f.seek(pos)
    b0 = f.read(1)
    if not b0 or b0[0] == 0:
        raise ValueError('bad vint')
    b0, mask, n = b0[0], 0x80, 1
    while not b0 & mask:
        mask >>= 1
        n += 1
    if n > 8:
        raise ValueError('bad vint')
    v = b0 if keep_marker else b0 & (mask - 1)
    ones = (b0 & (mask - 1)) == mask - 1
    rest = f.read(n - 1)
    if len(rest) != n - 1:
        raise ValueError('short vint')
    for b in rest:
        v = v * 256 + b
        ones = ones and b == 0xFF
    return v, n, (not keep_marker) and ones


CLUSTER_CHILDREN = {0xE7, 0xA3, 0xA0, 0xA7, 0xAB, 0x5854, 0xBF, 0xEC}


def _mkv_payload(f):
    f.seek(0, 2)
    size_all = f.tell()
    eid, n, _ = _vint(f, 0, True)
    if eid != 0x1A45DFA3:
        return None
    sz, n2, unk = _vint(f, n, False)
    if unk:
        return None
    pos = n + n2 + sz
    eid, n, _ = _vint(f, pos, True)
    if eid != 0x18538067:
        return None
    sz, n2, unk = _vint(f, pos + n, False)
    seg_start = pos + n + n2
    seg_end = size_all if unk else min(size_all, seg_start + sz)
    types, blocks = {}, []
    _ebml(f, seg_start, seg_end, types, blocks)
    return [(b[0], b[1]) for b in blocks if types.get(b[2]) in (1, 2)] or None


def _ebml(f, pos, end, types, blocks, parent=0, entry=None):
    """Walk Segment > Tracks/Cluster > TrackEntry/BlockGroup: track types into types, block frame data into blocks."""
    while pos < end:
        try:
            eid, n, _ = _vint(f, pos, True)
        except ValueError:
            return pos
        if parent == 0x1F43B675 and eid not in CLUSTER_CHILDREN:
            return pos   # an unknown-size Cluster ends here
        try:
            sz, n2, unk = _vint(f, pos + n, False)
        except ValueError:
            return pos
        ds = pos + n + n2
        de = end if unk else min(end, ds + sz)
        if eid in (0x1654AE6B, 0x1F43B675, 0xA0):              # Tracks, Cluster, BlockGroup
            stop = _ebml(f, ds, de, types, blocks, eid)
            if unk:
                de = stop
        elif eid == 0xAE:                                       # TrackEntry
            e = [-1, -1]
            _ebml(f, ds, de, types, blocks, eid, e)
            if e[0] >= 0:
                types[e[0]] = e[1]
        elif entry is not None and eid in (0xD7, 0x83) and sz <= 8:   # TrackNumber, TrackType
            entry[0 if eid == 0xD7 else 1] = int.from_bytes(_read_at(f, ds, sz), 'big')
        elif eid in (0xA3, 0xA1):                               # SimpleBlock, Block
            try:
                track, tn, _ = _vint(f, ds, False)
            except ValueError:
                track, tn = -1, 0
            if track >= 0 and ds + tn + 3 <= de:
                blocks.append((ds + tn + 3, de, track))
        if unk and eid != 0x1F43B675:
            return de   # an unknown size elsewhere: the rest is not read
        pos = de
    return pos


def in_ranges(ranges, a, b):
    """Whether [a, b) lies inside one of the sorted ranges."""
    import bisect
    i = bisect.bisect_right([r[0] for r in ranges], a) - 1
    return i >= 0 and b <= ranges[i][1]


def binary_needles(user, identities, emails):
    """[(needle lower-case, category, mode)] of the binary scan. Modes: long (anywhere), short (a word of its own: an
    account name under 6 letters), opus (a word of its own inside a string, the codec's forms allowed), word (an identity
    name or handle, not inside a longer word), email (a developer's own address, anywhere)."""
    out = [(n, 'banned-name', 'long') for n in ('superposition', 'game-factory', 'game_factory', 'gamefactory')]
    out += [('anthropic', 'agent-name', 'long'), ('claude', 'agent-name', 'long'), ('openai', 'agent-name', 'long'),
            ('opus', 'agent-name', 'opus')]
    if user and len(user) >= 4:
        out.append((user.lower(), 'username', 'short' if len(user) < 6 else 'long'))
    seen = {n for n, _c, _m in out}
    for term, _dev in identities:   # full names and handles of the history's people; their single words are too common
        t = term.lower()
        if t not in seen and t.isascii() and (' ' in t or (len(t) >= 8 and re.fullmatch(r'[a-z0-9._-]+', t)) or
                                             (len(t) >= 5 and re.search(r'\d', t))):
            out.append((t, 'git-identity', 'word'))
            seen.add(t)
    for e in emails:
        if e.lower() not in seen and e.isascii():
            out.append((e.lower(), 'email', 'long'))
            seen.add(e.lower())
    return out


def scan_binary(path, needles, payload=None, stream_terms=()):
    """Every needle found in a binary file as ASCII or UTF-16LE, any case: [(offset, needle, category, run, word, kind)].
    run = the printable characters in a row around the hit (compiled-in strings run long, compressed data seldom past 8);
    word = the word around it. kind: binary (refuses), binary-info (listed only: a short name or an identity in a run
    under 8 that is not a whole C string) or allowed-<why> (locale, codec, stream: inside a media file's compressed
    payload, entropy: "opus" spelled by compressed bytes)."""
    hits = []
    plain = [n.encode('ascii') for n, _c, _m in needles]
    wide = [n.encode('utf-16-le') for n, _c, _m in needles]
    chunk, overlap, base, carry, stream_hits = 4 << 20, 160, 0, b'', 0
    with open(lp(path), 'rb') as f:
        while len(hits) < 400:
            data = f.read(chunk)
            if not data:
                break
            buf = carry + data
            low = buf.lower()
            for k, (n, cat, mode) in enumerate(needles):
                for pat, w in ((plain[k], 1), (wide[k], 2)):
                    at = low.find(pat)
                    while at >= 0 and len(hits) < 400:
                        off = base - len(carry) + at
                        nl = len(n)
                        if any(h[0] == off for h in hits):
                            pass
                        elif mode in ('short', 'opus') and not short_token(buf, at, nl, w):
                            pass   # inside a longer word or identifier, or random bytes
                        elif mode == 'word' and not bounded_word(buf, at, nl, w):
                            pass
                        else:
                            run, a, z = nl, at - w, at + len(pat)
                            while a >= 0 and run < 64 and 0x20 <= buf[a] <= 0x7e and (w == 1 or buf[a + 1] == 0):
                                run, a = run + 1, a - w
                            while z + w - 1 < len(buf) and run < 64 and 0x20 <= buf[z] <= 0x7e and (w == 1 or buf[z + 1] == 0):
                                run, z = run + 1, z + w
                            if mode == 'opus' and run < 8:
                                at = low.find(pat, at + 1)
                                continue   # the codec name and random bytes spell it outside strings all the time
                            word = bin_word(buf, at, nl, w)
                            kind = 'binary'
                            p3 = at - 3 * w
                            if cat == 'username' and p3 >= 0 and buf[p3] | 0x20 == ord('z') and buf[p3 + w] | 0x20 == ord('h') and buf[p3 + 2 * w] in b'_-':
                                kind = 'allowed-locale'   # a zh_<name> / zh-<name> locale id
                            elif ALLOW_BIN.match(word):
                                kind = 'allowed-codec'
                            elif payload and n in stream_terms and stream_hits < MAX_STREAM_HITS and in_ranges(payload, off, off + len(pat)):
                                kind, stream_hits = 'allowed-stream', stream_hits + 1
                            elif mode == 'opus' and run <= 16 and not MODEL_FORM.search(word) and entropy(buf, at) >= MIN_ENTROPY:
                                kind = 'allowed-entropy'
                            elif mode in ('short', 'word') and run < 8:
                                end = at + len(pat)
                                whole = (at < w or not any(buf[at - w:at])) and (end + w > len(buf) or not any(buf[end:end + w]))
                                kind = 'binary' if whole else 'binary-info'   # a whole C string, or a few random letters
                            hits.append((off, n, cat, run, word, kind + ('-utf16' if w == 2 and kind != 'binary' else '')))
                        at = low.find(pat, at + 1)
            carry = buf[-overlap:]
            base += len(data)
    return hits


def reviewed_hits(path=REVIEWED):
    """{(file sha256, offset): word} of a reviewed-hits TSV (tools/package-reviewed-hits.tsv: sha256, offset, word,
    why): single binary hits a person judged to be data, not text, keyed by the file's own bytes, so another file or
    another version of it still refuses."""
    out = {}
    if path and os.path.isfile(path):
        with open(path, encoding='utf-8') as f:
            for line in f:
                p = line.rstrip('\n').split('\t')
                if len(p) >= 3 and re.fullmatch(r'[0-9a-f]{64}', p[0]) and p[1].isdigit():
                    out[(p[0], int(p[1]))] = p[2]
    return out


# the account name written out as escaped bytes (a Python bytes repr \xHH, JSON \uHHHH): a short literal run between
# escapes is random bytes, not a path
ESC_TOKEN = re.compile(r'\\+(?:x[0-9a-fA-F]{2}|u[0-9a-fA-F]{4})')


def escaped_bytes(s, at, n):
    lo, hi = max(0, at - 64), min(len(s), at + n + 64)
    while lo < at and s[lo] != '\\':
        lo += 1
    while lo > 0 and s[lo - 1] == '\\':
        lo -= 1
    w = s[lo:hi]
    hs, he = at - lo, at - lo + n
    before = after = 0
    run_start = run_end = -1
    for e in ESC_TOKEN.finditer(w):
        if e.end() <= hs:
            before, run_start = before + 1, e.end()
        elif e.start() >= he:
            after += 1
            if run_end < 0:
                run_end = e.start()
        else:
            return False
    if before < 3 or after < 3 or run_end - run_start > 16:
        return False
    return not any(c == '\\' or c.isspace() for c in w[run_start:run_end])


# other people's profile folders in a delivery's text: reported, never changed (AGENTS.md's leak scan)
OTHER_PROFILE = re.compile(r'(?i)(?:\b[A-Z]:[\\/]{1,2}|[\\/]{2})Users[\\/]{1,2}([^\\/\s"\'<>|:*?`]{1,64})|(?<![\w.])/(?:Users|home)/([A-Za-z0-9._-]{1,64})')
PROFILE_OK = {'dev', 'public', 'default', 'all users', 'default user', 'runneradmin', 'user', 'name', 'you', 'username', '<you>',
              '<name>', '<user>', '<username>', '...', '…', '*', '%username%', '$env:username', '$username', '$user', '{user}',
              'first', 'firstname', 'first.last', 'yourname', 'your_name', 'example', 'someone', 'me'}   # placeholders in docs


def scan_tree(root, enforced, needles, user, reviewed=None, skip=()):
    """The scan of a delivery folder (paths, text files with the enforced pattern, binaries with the needles):
    {"hits": [(rel, kind, line, text)] of paths and text (each refuses), "binary": [(rel, offset, needle, category,
    printable run, word, kind)] (kind binary refuses unless --lenient-binaries; binary-info is listed only), "allowed":
    [(rel, kind, line or offset, word)], "emails": [(rel, offset, address)] (e-mail addresses in binaries, listed only),
    "leaks": [(rel, line, text)] (other people's profile folders in text, listed only)}."""
    out = {'hits': [], 'binary': [], 'allowed': [], 'emails': [], 'leaks': []}
    reviewed = reviewed or {}
    stream_terms = {n for n, cat, mode in needles if n in ('claude', 'openai', 'opus') or cat == 'username'}
    sums = {}
    for rel in files_under(root):
        if rel in skip:
            continue
        if enforced.search(rel):
            out['hits'].append((rel, 'path', 0, rel))
        full = os.path.join(root, *rel.split('/'))
        size = os.path.getsize(lp(full))
        if size == 0 or rel.endswith('.bundle'):   # the bundle's messages and text blobs: history_texts
            continue
        with open(lp(full), 'rb') as f:
            head_bytes = f.read(8000)
        if not rel.startswith('History/lfs/objects/') and size < (256 << 20) and is_text(rel, head_bytes):
            text = decode(read_bytes(full))[0]
            found = 0
            for i, line in enumerate(text.split('\n'), 1):
                for mm in enforced.finditer(line):
                    if mm.group('user') and user:
                        a = mm.start('user')
                        if a >= 3 and line[a - 3:a - 1].lower() == 'zh' and line[a - 1] in '_-':
                            out['allowed'].append((rel, 'allowed-locale', i, 'zh_' + mm.group('user')))
                            continue
                        if escaped_bytes(line, a, len(mm.group('user'))):
                            out['allowed'].append((rel, 'allowed-escaped-bytes', i, mm.group('user')))
                            continue
                    found += 1
                    if found <= 20:
                        out['hits'].append((rel, 'text', i, line[max(0, mm.start() - 60):mm.end() + 60].replace('\t', ' ').replace('\r', '')))
                for lm in OTHER_PROFILE.finditer(line):
                    who = (lm.group(1) or lm.group(2) or '').strip().rstrip('.')
                    if who and who.lower() not in PROFILE_OK and not re.fullmatch(r'dev_\d+|<[^>]*>|\{[^}]*\}|%\w+%|\$\w+', who, re.I):
                        out['leaks'].append((rel, i, lm.group(0)[:120]))
        else:
            for off, needle, cat, run, word, kind in scan_binary(full, needles, media_payload(full), stream_terms):
                if kind == 'binary' and reviewed:
                    if rel not in sums:
                        sums[rel] = sha256_file(full)
                    if reviewed.get((sums[rel], off)) == word:
                        kind = 'allowed-reviewed'
                if kind.startswith('allowed'):
                    out['allowed'].append((rel, kind, off, f'{cat}: {word}'))
                else:
                    out['binary'].append((rel, off, needle, cat, run, word, kind))
            if not rel.startswith('Gameplay/'):
                out['emails'] += [(rel, off, addr) for off, addr in bin_emails(full)]
    return out


BIN_EMAIL = re.compile(rb'(?<![A-Za-z0-9._%+-])[A-Za-z0-9._%+-]{1,64}@(?:[A-Za-z0-9-]{1,63}\.)+(?:com|org|net|edu|gov|io|dev|co|uk|de|fr|jp|cn|ru|info|biz|me|ai|app)(?![A-Za-z0-9-])')


def bin_emails(path):
    """[(offset, address)] of the e-mail addresses in a binary file's bytes (streamed), example domains left out."""
    out, chunk, overlap, base, carry = [], 8 << 20, 200, 0, b''
    with open(lp(path), 'rb') as f:
        while len(out) < 200:
            data = f.read(chunk)
            if not data:
                break
            buf = carry + data
            for m in BIN_EMAIL.finditer(buf):
                off = base - len(carry) + m.start()
                addr = m.group(0).decode('latin-1')
                if not re.search(r'(?i)@(?:[\w-]+\.)*(?:example\.(?:com|org|net)|invalid|test|localhost)$', addr) and not any(o == off for o, _a in out):
                    out.append((off, addr))
            carry = buf[-overlap:]
            base += len(data)
    return out


# ---- the package ---------------------------------------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0], formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('game', nargs='?', help='the game\'s slug (the repo is <root>/games/<slug>); --self-check needs none')
    ap.add_argument('--repo', help='the game repo, when it is not <root>/games/<slug>')
    ap.add_argument('--commit', default='HEAD', help='the release commit (default HEAD); "milestone": the newest '
                                                       'milestone/autoplay-<n> tag, the commit whose scenarios 1..n were recorded')
    ap.add_argument('--version', default='', help='the release version for the README and manifest.json, e.g. 1.0')
    ap.add_argument('--build', help='the player: a pipeline build folder (<root>/builds/<slug>/<sha8>, with build_info.json) or '
                                    'a player folder (default the newest pipeline release build of the release commit\'s '
                                    'history, else <repo>/Build/Windows)')
    ap.add_argument('--brief', help='the brief as given (Brief/brief.md)')
    ap.add_argument('--design', help='the design doc (Brief/design.md)')
    ap.add_argument('--tasks-ref', default='', help='where Tasks/ comes from (default the branch tasks, else origin/tasks)')
    ap.add_argument('--exclude-sessions', default='', help='session ids, comma-separated, whose rows are not creation work')
    ap.add_argument('--exclude-runs', default='', help='recording run ids, comma-separated, never to take for Gameplay/')
    ap.add_argument('--replay', help='the creation replay\'s package folder, with READY and ReplayScripts/ '
                                     '(default <out>/_replay/<slug>/<release sha8>)')
    ap.add_argument('--recording', help='the recording folder (default <root>/.recording/<slug>)')
    ap.add_argument('--out', help='where the zip and the scratch folder go (default the game repo)')
    ap.add_argument('--lfs-unpatchable-use-head', action='store_true',
                    help='a Git LFS object naming the account outside a path, a whole string or an XML element: deliver the '
                         'release commit\'s clean version of its path in every commit that held it')
    ap.add_argument('--reviewed-hits', default=REVIEWED, help='single binary hits a person judged to be data, not text: a TSV of '
                                                                'file sha256, offset, word (default tools/package-reviewed-hits.tsv)')
    ap.add_argument('--lenient-binaries', action='store_true',
                    help='list the names found in binary files without refusing the package (to review a refusal)')
    ap.add_argument('--strict-binaries', action='store_true', help=argparse.SUPPRESS)   # the default now
    ap.add_argument('--no-repo-dataset', action='store_true', help='do not write the repo\'s Dataset/ folder')
    ap.add_argument('--no-zip', action='store_true', help='stop after the checks; the delivery stays in the scratch folder')
    ap.add_argument('--dry-run', action='store_true', help='print what would go in; write nothing')
    tools = ap.add_mutually_exclusive_group()
    tools.add_argument('--rescan', metavar='ZIP_OR_FOLDER', help='scan a delivered dataset again with the current rules (paths, '
                       'text, binaries, its history); PASS exits 0, FAIL 2; the hits go to <out>/<slug>/<slug>.rescan-hits.tsv')
    tools.add_argument('--scrub-dir', metavar='FOLDER', help='apply the scrub rules to every text file of a folder, in place '
                       '(a report in <out>/<slug>/<slug>.scrub-dir.json); nothing is packaged')
    tools.add_argument('--self-check', action='store_true', help='check the scrub and scan rules on built-in samples (the '
                       'account name built at run time); the slug is not read')
    args = ap.parse_args()
    try:
        if args.self_check:
            return self_check()
        if not args.game:
            ap.error('the game\'s slug is needed')
        if args.rescan:
            return rescan(args)
        if args.scrub_dir:
            return scrub_dir(args)
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
    rules = check_rules(repo)
    if rules:
        raise Refused('the game fails the game contract or the sound rule: bring it up to them before packaging\n  '
                      + '\n  '.join(rules))
    recording = os.path.abspath(args.recording or os.path.join(ugfroot.root(), '.recording', game))
    out_root = os.path.abspath(args.out or repo)
    scratch = os.path.join(out_root, '.dataset')
    stage = os.path.join(scratch, game)
    if args.commit == 'milestone':   # the newest milestone/autoplay-<n> tag: the commit the pipeline recorded
        tags = [(int(m.group(1)), t) for t in git_text(repo, 'tag', '--list', 'milestone/autoplay-*', check=False).split()
                if (m := re.fullmatch(r'milestone/autoplay-(\d+)', t))]
        args.commit = max(tags)[1] if tags else 'HEAD'
        step(f'--commit milestone: {args.commit}')
    sha = git_text(repo, 'rev-parse', '--verify', '-q', args.commit + '^{commit}', check=False)
    if not re.fullmatch(r'[0-9a-f]{40}', sha):
        raise Refused(f'--commit {args.commit}: no such commit in {repo}')
    from datetime import datetime
    commit_time = datetime.fromisoformat(git_text(repo, 'log', '-1', '--format=%cI', sha))
    user = os.environ.get('USERNAME') or getpass.getuser()
    machine = os.environ.get('COMPUTERNAME') or socket.gethostname().split('.')[0]
    problems, warnings = [], []
    release_tag = None
    if args.version:   # a release/<version> tag must name the release commit
        tagged = git_text(repo, 'rev-parse', '--verify', '-q', f'release/{args.version}^{{commit}}', check=False)
        if re.fullmatch(r'[0-9a-f]{40}', tagged):
            if tagged == sha:
                release_tag = f'release/{args.version}'
            else:
                warnings.append(f'the tag release/{args.version} names {tagged[:8]}, not the release commit {sha[:8]}')

    # inputs that can refuse the package before anything is written
    root = ugfroot.root()
    job = pipeline_job(root, game)
    if job:   # build.ps1 or record.ps1 is writing this game's player or a recording
        problems.append(f'error: the pipeline is working on {game} right now: {job}; package after it finishes')
    lineage = {c: i for i, c in enumerate(git_text(repo, 'rev-list', sha).split())}
    build_info = None
    if args.build:   # a pipeline build folder (its player in Windows/, build_info.json beside it), or a player folder
        build = os.path.abspath(args.build)
        for d, player in ((build, os.path.join(build, 'Windows')), (os.path.dirname(build), build)):
            if os.path.isdir(lp(player)) and os.path.isfile(lp(os.path.join(d, 'build_info.json'))):
                build, build_info = player, read_json(os.path.join(d, 'build_info.json')) or {}
                break
    else:
        cands = pipeline_builds(root, game, lineage)
        build, build_info = (os.path.join(cands[0][1], 'Windows'), cands[0][2]) if cands else (os.path.join(repo, 'Build', 'Windows'), None)
    exe = find_exe(build) if os.path.isdir(build) else None
    build_commit, build_source = sha, "the game session's own player build (Scripts/unity.ps1 build); its commit is stated, not verified"
    if not exe:
        problems.append(f'error: no player build at {build} (no .exe): build the release commit (tools/unity-pipeline/build.ps1 '
                        f'{game} -Commit {sha[:8]}), or name a folder with --build')
    elif why := player_problem(repo, sha, build, exe):
        problems.append('error: ' + why)
    if build_info is not None:   # the pipeline's own record of the build (unity-build/1)
        bc = str(build_info.get('commit') or '')
        hits = (build_info.get('leak_scan') or {}).get('hits') or []
        if build_info.get('status') != 'ok' or str(build_info.get('config', '')).lower() != 'release':
            problems.append(f'error: {build} is not an ok release build (build_info.json: status {build_info.get("status")}, '
                            f'config {build_info.get("config")}): the dataset ships the release player')
        elif bc not in lineage:
            problems.append(f'error: {build} was built from {bc[:8] or "an unknown commit"}, which is not in the history of the release commit')
        elif hits:   # build.ps1's leak scan: a build with hits can be recorded but never handed out
            h = hits[0] if isinstance(hits[0], dict) else {}
            problems.append(f'error: {build} has {len(hits)} leak-scan hit(s) in build_info.json (e.g. {h.get("file")}: {h.get("pattern")}): '
                            'a build with hits must not be handed out; build it again from a clone outside the user profile (build.ps1 does)')
        else:
            build_commit = bc   # named in the manifest by its delivered id, once the history is rewritten
            build_source = 'the pipeline\'s release build of {} (tools/unity-pipeline/build.ps1, ' + str(build_info.get('backend') or 'il2cpp') + ')'
            if lineage[bc]:
                warnings.append(f'Build/ is the pipeline build of {bc[:8]}, {lineage[bc]} commit(s) before the release commit: build '
                                f'{sha[:8]} (tools/unity-pipeline/build.ps1 {game} -Commit {sha[:8]}) to ship its own player')
    elif exe:   # a session's build: a commit after it that changed the game's content or code means it is not the release's
        built = os.path.getmtime(os.path.join(build, exe))
        later = [l.split(' ', 2) for l in git_text(repo, 'log', '--format=%H %ct %s', sha, '--', 'Assets', 'Packages').splitlines()]
        later = [l for l in later if len(l) == 3 and int(l[1]) > built]
        if later:
            warnings.append(f'Build/{exe} was built before {len(later)} commit(s) that changed Assets/ or Packages/ (the latest: '
                            f'{later[0][0][:8]} "{later[0][2][:60]}"): build the release commit before packaging')
    ffprobe = find_ffprobe()
    exclude_runs = {s.strip() for s in args.exclude_runs.split(',') if s.strip()}
    runs, skipped_runs = gameplay_runs(root, game, sha, exclude_runs, ffprobe)
    for name, why in skipped_runs:
        warnings.append(f'recording {name} not taken: {why}')
    ready = ready_scenarios(repo, sha)
    missing = [n for n in range(1, ready + 1) if n not in {r['scenario'] for r in runs}]
    if runs and missing:
        warnings.append(f'scenario(s) {", ".join(map(str, missing))} of the {ready} ready (milestone/autoplay-{ready}) have no valid '
                        'recording of the release commit: Gameplay/ holds the others (one video is enough)')
    elif not runs:
        # a game without a gameplay video is rejected at upload (owner, 2026-11-10): Gameplay/ is never pending
        problems.append(f'error: no gameplay video: no valid recording of the release commit {sha[:8]} in '
                        f'{os.path.join(root, "recordings", game)}, and the Lab rejects a game without a gameplay video. Record a '
                        f'scenario of the release commit (tools/unity-pipeline/record.ps1 {game} -Build latest), then package again')
    replay = os.path.abspath(args.replay or os.path.join(ugfroot.out(), '_replay', game, sha[:8]))
    rs_src, report = os.path.join(replay, 'ReplayScripts'), None
    if os.path.isfile(lp(os.path.join(replay, 'READY'))) and os.path.isdir(lp(rs_src)):
        report = read_json(os.path.join(rs_src, 'Verification', 'report.json'))
        if not report or not isinstance(report.get('verdict'), dict) or not isinstance(report['verdict'].get('pass'), bool):
            problems.append(f'error: {os.path.join(rs_src, "Verification", "report.json")} has no verdict: make the replay again '
                            f'(python tools/unity-replay/unity_replay.py release --game {game})')
            report = None
        elif report.get('final_commit') != sha:
            problems.append(f'error: the replay in {replay} verified {str(report.get("final_commit"))[:12]}, not the release commit {sha[:12]}')
            report = None
    elif os.path.isdir(lp(rs_src)):
        warnings.append(f'the creation replay in {replay} is not finished (no READY): ReplayScripts/ stays pending')
    else:
        warnings.append(f'no creation replay of {sha[:8]} in {replay}: ReplayScripts/ stays pending '
                        f'(python tools/unity-replay/unity_replay.py release --game {game} makes it)')
    pending = ['ReplayScripts'] if report is None else []
    status = 'pending' if pending else 'complete'
    brief = find_brief(repo, sha, game, args.brief, 'brief', warnings)
    design = find_brief(repo, sha, game, args.design, 'design', warnings)
    for kind, f in (('brief', brief), ('design', design)):
        if not f:
            problems.append(f'error: no {kind} found: name it with --{kind} <file> (it becomes Brief/{kind}.md)')
        elif len(f[1]) < 200:
            problems.append(f'error: {f[0]} is nearly empty ({len(f[1])} bytes): Brief/{kind}.md must say something')
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
        problems.append('error: no tasks: the repo needs Tasks/<name>.json on its tasks branch (a game ships at least 5; the unity-write-tasks skill)')
    elif len(task_files) < 5:
        problems.append(f'error: {len(task_files)} task(s) on {tasks_at[0]}: a game with fewer than 5 tasks is rejected (the unity-write-tasks skill)')
    if not os.path.isfile(os.path.join(recording, 'actions.jsonl')):
        warnings.append(f'no {os.path.join(recording, "actions.jsonl")}: History/sessions/ will hold no tool calls')
    if not os.path.isfile(os.path.join(recording, 'messages.jsonl')):
        warnings.append(f'no {os.path.join(recording, "messages.jsonl")}: History/sessions/ will hold no prompts or replies '
                        '(sessions recorded before they were: record-unity-action.ps1 -Backfill all imports them while their transcripts are on this machine)')
    zip_name = 'Dataset.zip' if status == 'complete' else 'Dataset.pending.zip'
    step(f'{game}: commit {sha[:12]} ({commit_time.isoformat()}), build {build if exe else "MISSING"}, '
         f'{len(task_files)} task(s) on {tasks_at[0] if tasks_at else "no tasks branch"}, '
         f'{len(runs)} scenario video(s), replay {"PASS" if report and report["verdict"]["pass"] else "FAIL" if report else "pending"}')
    errors = [p for p in problems if p.startswith('error:')]
    if args.dry_run or errors:
        for p in problems:
            print('  ' + p)
        for w in warnings:
            print('  warning: ' + w)
        if errors:
            raise Refused(f'{len(errors)} thing(s) missing; nothing was written')
        for r in runs:
            print(f'  would take Gameplay/{game}_S{r["scenario"]}.mp4 from {r["run"]}')
        print(f'  would write {os.path.join(out_root, zip_name)} ({status}' + (f': {", ".join(pending)} pending)' if pending else ')'))
        return 0
    ugfroot.check_free(out_root, 'package-dataset')
    lock = hold_lock(os.path.join(ugfroot.out(), game, '.package.lock'))   # noqa: F841  held until the run ends
    if out_root == repo:   # the zips and the scratch sit in the repo: never committed (the template's .gitignore has them)
        exclude = os.path.join(git_text(repo, 'rev-parse', '--git-common-dir'), 'info', 'exclude')
        exclude = exclude if os.path.isabs(exclude) else os.path.join(repo, exclude)
        have = read_bytes(exclude).decode('utf-8', 'replace').splitlines() if os.path.isfile(exclude) else []
        for pat in ('/Dataset.zip', '/Dataset.pending.zip', '/.dataset/'):
            # a trailing slash tells check-ignore the path is a folder (the scratch is not there yet)
            if pat not in have and subprocess.run(['git', '-C', repo, 'check-ignore', '-q', '--no-index', pat.lstrip('/')],
                                                  capture_output=True).returncode:
                os.makedirs(os.path.dirname(exclude), exist_ok=True)
                with open(exclude, 'a', encoding='ascii', newline='\n') as f:
                    f.write(pat + '\n')
                warnings.append(f'{pat} added to {exclude}: the repo\'s .gitignore lacks it (add it there and commit it)')
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
    # the history's Git LFS objects: one that names the account or an agent in a path, a whole string or an XML element
    # is patched byte for byte (same length) into a new object, and the delivered history points at that one
    elh = tool('export_lfs_history', 'unity-pipeline', 'export-lfs-history.py')
    lfs_objects = elh.referenced(repo)
    step(f'scanning the history\'s {len(lfs_objects)} Git LFS object(s) for the account and agent names')
    lfs = elh.scan(repo, lfs_objects, os.path.join(scratch, '_lfs'), pats=elh.sip.byte_patterns(user or ''),
                   use_head=sha if args.lfs_unpatchable_use_head else None)
    step(f'rewriting the history ({len(authors)} identities -> dev_NN, {len(rules)} scrub rules, {lfs["patched"]} LFS object(s) patched)')
    bare = os.path.join(scratch, f'{game}.history.git')
    subprocess.run(['git', 'init', '--quiet', '--bare', bare], check=True, capture_output=True)
    hstats = {'blobs_scrubbed': 0, 'messages_scrubbed': 0, 'lfs_pointers_swapped': 0}
    cmap = rewrite_history(repo, bare, rules, authors, hstats, lfs['map'])
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
    lfs_store = elh.lfs_store(repo)
    need = lfs_pointers(bare, refs)
    lfs_bytes = 0
    unpatchable = {u['oid']: u for u in lfs['unpatchable']}
    for oid, size in sorted(need.items()):
        src = lfs['files'].get(oid) or os.path.join(lfs_store, oid[:2], oid[2:4], oid)
        if oid in unpatchable:   # delivered as it is: the binary scan below judges its bytes like every other file's
            warnings.append(f'Git LFS object {oid[:12]}... ({unpatchable[oid]["path"]}) names the account or an agent outside a path, '
                            'a whole string or an XML element, so it cannot be patched: re-export the asset, or pass '
                            '--lfs-unpatchable-use-head to deliver the release commit\'s version of that path in every commit')
        if not os.path.isfile(lp(src)):
            problems.append(f'error: Git LFS object {oid[:12]}... of the history is not in the local store: git lfs fetch --all first')
        elif os.path.getsize(lp(src)) != size:
            problems.append(f'error: Git LFS object {oid[:12]}... has the wrong size in the local store')
        else:
            copy_file(src, os.path.join(hist, 'lfs', 'objects', oid[:2], oid[2:4], oid))
            lfs_bytes += size
    step(f'history: {n_commits} commits, {len(refs)} ref(s), head {head[:12]}; {hstats["blobs_scrubbed"]} blobs and '
         f'{hstats["messages_scrubbed"]} messages scrubbed; {len(need)} LFS objects')
    map_text = 'original\tdelivered\n' + ''.join(f'{o}\t{n}\n' for o, n in cmap.items())
    write_text(os.path.join(scratch, f'{game}.commit-map.tsv'), map_text)

    # ---- UnityProject, workflow.jsonl, git.log ----
    step('writing UnityProject/ and git.log')
    project = os.path.join(stage, 'UnityProject')
    n_project = export_tree(bare, head, os.path.join(hist, 'lfs', 'objects'), project, problems)   # the delivered objects
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

    # ---- Brief, Screenshots, Gameplay, Build ----
    write_bytes(os.path.join(stage, 'Brief', 'brief.md'), brief[1])
    write_bytes(os.path.join(stage, 'Brief', 'design.md'), design[1])
    shots = screenshots(project, readme_src, runs, os.path.join(stage, 'Screenshots'), warnings)
    if not shots:
        problems.append('error: no screenshot: the game\'s README.md shows no committed image, Docs/screenshots/ holds none at the '
                        'commit and no recording taken has stills (Screenshots/ needs at least one: hero + gallery in Docs/screenshots/)')
    for r in runs:   # the recorder's gameplay.mp4 as it is: H.264 copied from the capture, the game audio as AAC
        copy_file(r['mp4'], os.path.join(stage, 'Gameplay', f'{game}_S{r["scenario"]}.mp4'))
    if runs:
        step('gameplay: ' + ', '.join(f'S{r["scenario"]} from {r["run"]} ({r["result"]}, {r["seconds"]:.0f} s)' for r in runs))
    n_build = 0
    for d, dirs, fs in os.walk(lp(build)):
        dirs[:] = [x for x in dirs if not NOT_SHIPPED_BUILD.search(x)]
        for f in fs:
            if f.lower().endswith('.pdb'):
                continue
            full = os.path.join(d, f)
            copy_file(full, os.path.join(stage, 'Build', os.path.relpath(full, lp(build))))
            n_build += 1

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
        if isinstance(task.get('seed'), dict):   # its commits are now the delivered history's (game-task/1 seed.history)
            task['seed']['history'] = 'dataset'
        agent, grader = split_tasks.split(task)
        for name, obj in (('task.json', agent), ('grader.json', grader)):
            write_text(os.path.join(stage, 'Tasks', stem, name), json.dumps(obj, indent=2, ensure_ascii=False) + '\n')
        seed = task.get('seed') if isinstance(task.get('seed'), dict) else {}
        task_rows.append({'name': stem, 'title': task.get('title', ''), 'kind': seed.get('kind', 'new game'),
                          'difficulty': task.get('difficulty', 'medium')})
    write_text(os.path.join(stage, 'Tasks', 'README.md'), tasks_readme(game, task_rows))
    remove_tree(tasks_tmp)

    # ---- ReplayScripts: the creation replay's package as it is (unscrubbed there), scrubbed and remapped here ----
    n_replay = 0
    if report is not None:
        for rel in files_under(rs_src):
            parts = rel.split('/')
            if '__pycache__' in parts or rel.lower().endswith(('.pyc', '.pdb')):
                continue
            copy_file(os.path.join(rs_src, *parts), os.path.join(stage, 'ReplayScripts', *parts))
            n_replay += 1
        step(f'ReplayScripts: {n_replay} files from {replay} (verdict {"PASS" if report["verdict"]["pass"] else "FAIL"})')

    # ---- every folder arrived whole (a short copy once went unnoticed in a delivery) ----
    counts_in = {}
    for rel in files_under(stage):
        top = rel.split('/')[0]
        counts_in[top] = counts_in.get(top, 0) + 1
    expect = {'UnityProject': n_project, 'Build': n_build, 'Gameplay': len(runs), 'Screenshots': len(shots),
              'Tasks': len(task_rows) * 2 + 1, 'ReplayScripts': n_replay if report is not None else 0}
    short = [f'{k}/ holds {counts_in.get(k, 0)} file(s), {v} were copied' for k, v in expect.items() if counts_in.get(k, 0) != v]
    if short:
        raise Refused('the staged delivery is incomplete: ' + '; '.join(short) + f' ({stage})')

    # ---- the scrub of everything, the README, then the scan ----
    step('scrubbing every text file of the delivery')
    counts, touched = {}, []
    scrub_tree(stage, rules, counts, touched)
    remapped = remap_tree(stage, cmap)
    step(f'scrubbed {len(touched)} file(s): ' + (', '.join(f'{k} {v}' for k, v in counts.items()) or 'nothing to replace') +
         f'; commit ids mapped in {remapped} file(s)')
    rv = None
    if report is not None:   # the manifest's replay_verification from the report as delivered (scrubbed, ids mapped)
        delivered = read_json(os.path.join(stage, 'ReplayScripts', 'Verification', 'report.json'))
        if not delivered or delivered.get('final_commit') != head:
            raise Refused(f'ReplayScripts/Verification/report.json final_commit is not the delivered release commit {head[:12]} after the id map')
        rv = replay_verification(delivered)
    ses_files = [n for n in ('messages.jsonl', 'actions.jsonl') if os.path.isfile(lp(os.path.join(hist, 'sessions', n)))]
    ctx = dict(game=game, title=title, version=args.version, head=head, exe=exe, shots=shots, task_rows=task_rows,
               readme_src=readme_src, sessions=ses_files, engine=ugfroot.project_unity_version(project) or '6000.3',
               pending=pending, runs=runs, rv=rv)
    write_text(os.path.join(stage, 'README.md'), remap_text(apply_rules(dataset_readme(ctx, False), rules, False, False), cmap))
    step('scanning every file (paths and text; binaries as ASCII and UTF-16)')
    enforced = enforced_pattern(user, identities)
    needles = binary_needles(user, identities, identity_emails(repo))
    scan = scan_tree(stage, enforced, needles, user, reviewed_hits(args.reviewed_hits))
    hits = scan['hits']
    # the bundle's commits that git.log does not show: the start branches' own messages and text blobs
    for where, text in history_texts(bare, refs):
        for mm in list(enforced.finditer(text))[:20]:
            hits.append((f'History/{game}.bundle', 'history', where, text[max(0, mm.start() - 60):mm.end() + 60].replace('\n', ' ')))
    tsv = lambda rows: ''.join('\t'.join(str(x) for x in r) + '\n' for r in rows)   # noqa: E731
    write_text(os.path.join(scratch, f'{game}.binary-hits.tsv'), 'path\toffset\tname\tcategory\tprintable_run\tword\tkind\n' + tsv(scan['binary']))
    write_text(os.path.join(scratch, f'{game}.allowlisted.tsv'), 'path\tkind\tline_or_offset\tword\n' + tsv(scan['allowed']))
    write_text(os.path.join(scratch, f'{game}.binary-emails.tsv'), 'path\toffset\taddress\n' + tsv(scan['emails']))
    write_text(os.path.join(scratch, f'{game}.leaks.tsv'), 'path\tline\ttext\n' + tsv(scan['leaks']))
    refusing = [b for b in scan['binary'] if b[6] == 'binary']
    if scan['binary']:
        warnings.append(f'{len(scan["binary"])} name(s) in {len({b[0] for b in scan["binary"]})} binary file(s), {len(refusing)} of them in a '
                        f'string: review {os.path.join(scratch, game + ".binary-hits.tsv")} (binaries are never changed)')
    if scan['allowed']:
        warnings.append(f'{len(scan["allowed"])} hit(s) allowed (codec forms, media payloads, locale ids, reviewed): '
                        f'{os.path.join(scratch, game + ".allowlisted.tsv")}')
    if scan['emails']:
        warnings.append(f'{len(scan["emails"])} e-mail address(es) in binary files, none of the history\'s people (listed only): '
                        f'{os.path.join(scratch, game + ".binary-emails.tsv")}')
    if scan['leaks']:
        warnings.append(f'{len(scan["leaks"])} other profile folder(s) in text files (listed only): {os.path.join(scratch, game + ".leaks.tsv")}')
    if not args.lenient_binaries:   # a name in a binary file's strings refuses the package, as one in a text file does
        hits += [(b[0], 'binary', b[1], f'{b[3]}: {b[5]}') for b in refusing]
    # what the scrub changed and what the scan found, counts only (the words would carry the names): beside the delivery,
    # never in it
    by_kind = {}
    for a in scan['allowed']:
        by_kind[a[1]] = by_kind.get(a[1], 0) + 1
    scrub_report = {
        'schema': 'scrub-report/1', 'game': game, 'commit': sha, 'delivered_commit': head,
        'rules': [{'id': k, 'what': RULE_TEXT.get(k, ''), 'replacements': v} for k, v in counts.items()],
        'files_touched_count': len(touched), 'files_touched': touched,
        'history': {'identities_numbered': len(authors), 'blobs_scrubbed': hstats['blobs_scrubbed'],
                    'messages_scrubbed': hstats['messages_scrubbed'], 'commit_ids_mapped_in_files': remapped,
                    'lfs_objects_patched': lfs['patched'], 'lfs_pointers_swapped': hstats['lfs_pointers_swapped'],
                    'lfs_objects_unpatchable': len(lfs['unpatchable'])},
        'sessions': {n: ses_stats.get(n) for n in ('actions.jsonl', 'messages.jsonl')},
        'scan': {'text_and_path_hits': len(scan['hits']), 'history_hits': len([h for h in hits if h[1] == 'history']),
                 'binary_refusing': len(refusing), 'binary_listed': len(scan['binary']) - len(refusing),
                 'binary_lenient': bool(args.lenient_binaries), 'allowed': by_kind,
                 'emails_in_binaries_listed': len(scan['emails']), 'other_profiles_listed': len(scan['leaks'])},
        'binary_note': 'binary files are never changed; a name in one refuses the delivery unless it is an allowed form (the audio '
                       'codec, a locale id, a media payload, compressed bytes, a reviewed hit)'}
    write_text(os.path.join(scratch, f'{game}.scrub-report.json'), json.dumps(scrub_report, indent=1) + '\n')
    errors = [p for p in problems if p.startswith('error:')]
    if hits or errors:
        write_text(os.path.join(scratch, f'{game}.refused-hits.tsv'), 'path\tkind\tline_or_offset\ttext\n' + tsv(hits) +
                   ''.join(f'-\terror\t-\t{e}\n' for e in errors))
        for e in errors[:15]:
            print('  ' + e)
        for w in warnings:
            print('  warning: ' + w)
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
    scenarios = []
    for r in runs:
        s = {'file': f'Gameplay/{game}_S{r["scenario"]}.mp4', 'scenario': r['scenario'], 'name': r['name'], 'result': r['result'],
             'seconds': r['seconds'], 'source_run': r['run']}
        if r['audio_offset_s'] is not None:
            s['audio_offset_s'] = r['audio_offset_s']
        if r['capture_notes']:   # what the recording did differently, e.g. a lower quality level
            s['capture_notes'] = r['capture_notes']
        scenarios.append(s)
    base = {'layout': LAYOUT, 'game': game, 'title': title, 'version': args.version, 'commit': head, 'status': status,
            'pending': list(pending), 'created': datetime.now().astimezone().isoformat(timespec='seconds'), 'replay_verification': rv,
            'scenarios': scenarios,
            'brief': {'brief': 'Brief/brief.md', 'design': 'Brief/design.md'}}
    write_manifest(stage, dict(base, variant='full', history=history,
                               build={'config': 'Release', 'commit': cmap.get(build_commit, head), 'exe': f'Build/{exe}',
                                      'source': build_source.replace('{}', 'the release commit' if build_commit == sha else
                                                                     f'commit {cmap.get(build_commit, head)[:12]}')},
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
        zip_path = os.path.join(out_root, zip_name)
        step(f'zipping {zip_path}')
        tmp = zip_path + '.tmp'
        n_zip = zip_tree(stage, tmp, game)
        for old in ('Dataset.zip', 'Dataset.pending.zip'):   # a pending delivery never sits next to a complete one
            if os.path.isfile(os.path.join(out_root, old)):
                os.remove(os.path.join(out_root, old))
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
            if rel.split('/')[0] in ('git.log', 'workflow.jsonl', 'Brief', 'Screenshots', 'Gameplay', 'ReplayScripts'):
                copy_file(os.path.join(stage, *rel.split('/')), os.path.join(ds, *rel.split('/')))
        write_text(os.path.join(ds, 'README.md'), remap_text(apply_rules(dataset_readme(ctx, True), rules, False, False), cmap))
        # the files are committed byte for byte as manifest.json lists them: no line-ending conversion (Git for Windows'
        # core.autocrlf with the template's "* text=auto" checks them out with CRLF, and every size and sha256 differs)
        write_text(os.path.join(ds, '.gitattributes'), '* -text\n' + ''.join(
            f'*.{e} filter=lfs diff=lfs merge=lfs -text\n' for e in ('mp4', 'png', 'jpg', 'jpeg', 'webp')))
        write_manifest(ds, dict(base, variant='repo-dataset', history=None, build=None, tasks=None))
        dv = validate(ds, True)
        if dv['errors']:
            for e in dv['errors'][:30]:
                print('  x ' + e)
            raise Refused(f'{ds} is not valid ({len(dv["errors"])} error(s))')
    remove_tree(bare)
    # the old -> new map of this delivery, kept where the next run does not empty it (the scratch is emptied each run)
    keep = os.path.join(ugfroot.out(), game, f'{game}_{head[:8]}.commit-map.tsv')
    write_text(keep, map_text)
    # the delivery's audit beside the deliveries (the scratch is emptied each run): its scrub report, the lists the
    # scan only reports, and one row per delivery in package-log.jsonl
    audit = {}
    for kind in ('scrub-report.json', 'leaks.tsv', 'allowlisted.tsv', 'binary-emails.tsv'):
        src = os.path.join(scratch, f'{game}.{kind}')
        if os.path.isfile(lp(src)):
            audit[kind] = os.path.join(ugfroot.out(), game, f'{game}_{head[:8]}.{kind}')
            copy_file(src, audit[kind])
    zip_bytes = os.path.getsize(zip_path) if zip_path else None
    with open(lp(os.path.join(ugfroot.out(), game, 'package-log.jsonl')), 'a', encoding='utf-8', newline='\n') as f:
        f.write(json.dumps({'time': datetime.now().astimezone().isoformat(timespec='seconds'), 'game': game, 'commit': sha,
                            'delivered_commit': head, 'version': args.version, 'status': status, 'pending': pending,
                            'zip': zip_path, 'zip_bytes': zip_bytes, 'files': len(files_under(stage)),
                            'release_tag': release_tag,
                            'scenarios': [r['run'] for r in runs], 'replay': None if rv is None else ('PASS' if rv['pass'] else 'FAIL'),
                            'build': build_source.replace('{}', (cmap.get(build_commit) or head)[:12]),
                            'scrubbed_files': len(touched), 'warnings': warnings, 'audit': audit,
                            'duration_s': round(time.time() - t0, 1)}, ensure_ascii=False) + '\n')

    sizes = {}
    for rel in files_under(stage):
        top = rel.split('/')[0] if '/' in rel else '(top level)'
        sizes[top] = sizes.get(top, 0) + os.path.getsize(lp(os.path.join(stage, *rel.split('/'))))
    print(f'\n{status.upper()}  {zip_path or stage}' + (f'  (pending: {", ".join(pending)})' if pending else
                                                         f'  (replay {"PASS" if rv["pass"] else "FAIL"}, {len(runs)} scenario video(s))'))
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


# ---- the tools beside the package: rescan, scrub-dir, self-check -----------------------------------------------------------
def machine_rules(repo=None):
    """(user, identities, rules, enforced pattern, binary needles) with this machine's account and machine name and, when
    the game repo is here, its history's identities and addresses."""
    user = os.environ.get('USERNAME') or getpass.getuser()
    machine = os.environ.get('COMPUTERNAME') or socket.gethostname().split('.')[0]
    identities, emails = [], []
    if repo and os.path.isdir(os.path.join(repo, '.git')):
        identities, emails = identity_terms(repo, {}), identity_emails(repo)
    return (user, identities, build_rules(user, machine, set(), identities), enforced_pattern(user, identities),
            binary_needles(user, identities, emails))


def rescan(args):
    """--rescan: a delivered dataset (its zip or its folder) scanned again with the current rules: paths, text and
    binaries as the package scan does them, the bundle's commits git.log does not show, and its identities (dev_NN
    only). PASS exits 0, FAIL 2; every hit in <out>/<slug>/<slug>.rescan-hits.tsv."""
    game = args.game
    repo = os.path.abspath(args.repo or os.path.join(ugfroot.root(), 'games', game))
    user, _identities, _rules, enforced, needles = machine_rules(repo)
    out_dir = os.path.join(ugfroot.out(), game)
    work = os.path.join(out_dir, '.rescan')
    remove_tree(work)
    target = os.path.abspath(args.rescan)
    try:
        root = target
        if os.path.isfile(target):
            with zipfile.ZipFile(target) as z:
                names = z.namelist()
                if any(n.startswith(('/', '\\')) or '..' in n.replace('\\', '/').split('/') for n in names):
                    raise Refused(f'{target}: an entry outside the zip\'s folder')
                z.extractall(lp(os.path.join(work, 'unpacked')))
            tops = {n.split('/')[0] for n in names}
            root = os.path.join(work, 'unpacked', *(list(tops) if len(tops) == 1 else []))
        step(f'rescanning {target}')
        scan = scan_tree(root, enforced, needles, user, reviewed_hits(args.reviewed_hits))
        hits = scan['hits'] + [(b[0], 'binary', b[1], f'{b[3]}: {b[5]}') for b in scan['binary'] if b[6] == 'binary']
        for b in [r for r in files_under(root) if r.startswith('History/') and r.endswith('.bundle')]:
            bare = os.path.join(work, 'history.git')
            remove_tree(bare)
            subprocess.run(['git', 'clone', '-q', '--mirror', os.path.join(root, *b.split('/')), bare], check=True, capture_output=True)
            refs = [r for r in git_text(bare, 'for-each-ref', '--format=%(refname)').split() if r]
            if 'refs/heads/main' in refs:   # git.log, scanned above, shows main's history in full
                for where, text in history_texts(bare, refs):
                    for mm in list(enforced.finditer(text))[:20]:
                        hits.append((b, 'history', where, text[max(0, mm.start() - 60):mm.end() + 60].replace('\n', ' ')))
            people = {p for p in git_text(bare, 'log', '--all', '--format=%an%n%cn%n%ae%n%ce').splitlines() if p}
            hits += [(b, 'identity', 0, p) for p in sorted(people) if not re.fullmatch(r'dev_\d+(?:@example\.invalid)?', p)]
            remove_tree(bare)
        tsv_path = os.path.join(out_dir, f'{game}.rescan-hits.tsv')
        write_text(tsv_path, 'path\tkind\tline_or_offset\ttext\n' + ''.join('\t'.join(str(x) for x in h) + '\n' for h in hits))
        by_file = {}
        for h in hits:
            by_file.setdefault(h[0], []).append(h)
        for rel, hs in sorted(by_file.items(), key=lambda kv: -len(kv[1]))[:25]:
            print(f'  {len(hs):5d}  {hs[0][1]:<8} {rel}  e.g. {str(hs[0][3])[:100]}')
        print(f'{"FAIL" if hits else "PASS"}  {target}: {len(hits)} hit(s) in {len(by_file)} file(s), {len(scan["allowed"])} allowed, '
              f'{len(scan["emails"])} e-mail address(es) and {len(scan["leaks"])} other profile folder(s) listed; {tsv_path}')
        return 2 if hits else 0
    finally:
        remove_tree(work)


def scrub_dir(args):
    """--scrub-dir: the scrub rules on every text file of a folder, in place (this machine's account, the game repo's
    identities, the session ids of its recording); a report in <out>/<slug>/<slug>.scrub-dir.json."""
    game = args.game
    repo = os.path.abspath(args.repo or os.path.join(ugfroot.root(), 'games', game))
    user, identities, _rules, _enforced, _needles = machine_rules(repo)
    recording = os.path.abspath(args.recording or os.path.join(ugfroot.root(), '.recording', game))
    ids = set()
    for name in ('actions.jsonl', 'messages.jsonl'):
        if os.path.isfile(os.path.join(recording, name)):
            with open(os.path.join(recording, name), encoding='utf-8', errors='replace') as f:
                ids |= {m.group(1).lower() for m in SESSION_RX.finditer(f.read())}
    machine = os.environ.get('COMPUTERNAME') or socket.gethostname().split('.')[0]
    rules = build_rules(user, machine, ids, identities)
    folder = os.path.abspath(args.scrub_dir)
    if not os.path.isdir(lp(folder)):
        raise Refused(f'--scrub-dir {folder}: no such folder')
    counts, touched = {}, []
    scrub_tree(folder, rules, counts, touched)
    report = {'dir': folder, 'files': len(files_under(folder)), 'touched': len(touched), 'files_touched': touched, 'replacements': counts}
    path = os.path.join(ugfroot.out(), game, f'{game}.scrub-dir.json')
    write_text(path, json.dumps(report, indent=1) + '\n')
    print(f'scrubbed {len(touched)} of {report["files"]} file(s) in {folder}' + (': ' + ', '.join(f'{k} {v}' for k, v in counts.items()) if counts else '')
          + f'; {path}')
    return 0


def self_check():
    """--self-check: the scrub and the scan on built-in samples, the account name built from this machine's at run time
    (it is never written in this file). Text samples go through the scrub first where a delivery's text would; binary
    samples are written to a temporary folder and scanned. Exit 0 when every sample comes out as expected."""
    import random, tempfile
    user = os.environ.get('USERNAME') or getpass.getuser()
    machine = os.environ.get('COMPUTERNAME') or socket.gethostname().split('.')[0]
    u = (user or 'x').lower()
    u1 = u[:1].upper() + u[1:]
    mixed = ''.join(c.upper() if i % 2 else c for i, c in enumerate(u))
    identities = [('Jane Tester', 'dev_01')]
    rules = build_rules(user, machine, {'11111111-2222-4333-8444-555555555555'}, identities)
    enforced = enforced_pattern(user, identities)
    needles = binary_needles(user, identities, ['jane.tester@corp.example'])
    cases = [('studio-and-tools', 'scrub', 'pass', 'Made with unity-game-factory at Superposition (game factory, game_factory).'),
             ('agents-and-providers', 'scrub', 'pass', 'Claude Code and Codex CLI wrote it for Anthropic and OpenAI, with gpt-5 and claude-opus-4.'),
             ('model-in-prose', 'scrub', 'pass', 'The Opus run went well.'),
             ('codec-forms', 'scan', 'pass', 'libopus, opus_decode, audio/opus, theme.opus'),
             ('email', 'scrub', 'pass', 'mail jane.tester@corp.example'),
             ('clip-names', 'scan', 'pass', 'Assets/Art/Keeper@Walk.anim'),
             ('identity', 'scrub', 'pass', 'reviewed by Jane Tester'),
             ('studio-name-left', 'scan', 'refuse', 'Made at Superposition.')]
    if len(user) >= 3:
        # inside longer words in lower case it is no hit; glued in camel case (Wu<Name>Shan) it is one, as OwnerNameDesktop
        cases += [('user-in-longer-words', 'scan', 'pass', f'music: wu{u}shan_bgm.wav, the {u}ville map, ma{u}x'),
                  ('user-camel-glued', 'scan', 'refuse', f'Wu{u1}ShanBoss1'),
                  ('user-path', 'scrub', 'pass', f'C:\\Users\\{u1}\\UnityWork\\games\\kiln'),
                  ('user-path-mixed-case', 'scrub', 'pass', f'C:\\Users\\{mixed}\\Desktop'),
                  ('user-path-no-separators', 'scrub', 'pass', f'cd C:Users{u1}UnityWorkgames'),
                  ('session-folder', 'scrub', 'pass', f'C:\\Users\\{u1}\\AppData\\Local\\Temp\\claude\\C--x\\11111111-2222-4333-8444-555555555555\\scratchpad'),
                  ('user-glued', 'scrub', 'refuse', f'the shortcut Owner{u1}Desktop'),
                  ('user-word-left', 'scan', 'refuse', f'thanks {u1}!')]
    rnd = random.Random(7)
    noise = bytes(rnd.randrange(256) for _ in range(600))

    def mp4(payload, meta=b''):
        def box(kind, p):
            return (8 + len(p)).to_bytes(4, 'big') + kind + p
        hdlr = box(b'hdlr', b'\0' * 8 + b'vide' + b'\0' * 12 + b'track\0')
        moov = box(b'moov', box(b'trak', box(b'mdia', hdlr)) + (box(b'udta', meta) if meta else b''))
        return box(b'ftyp', b'isom\0\0\0\0isom') + moov + box(b'mdat', payload)
    bins = [('bin-studio-name', 'x.dll', b'\0built by unity-game-factory tools\0', 'refuse'),
            ('bin-codec-forms', 'x.dll', b'\0opus_decode\0SpcSpOpusInfo\0libopus.dll\0', 'pass'),
            ('bin-model-name', 'x.dll', b'\0trained on claude-opus-4\0', 'refuse'),
            ('bin-opus-in-compressed-bytes', 'x.dat', noise + b'\xf3\xf2k3opusSe\xa0\x12' + noise, 'pass'),
            ('bin-media-payload', 'x.mp4', mp4(b'\0\1xx Claude xx\2'), 'pass'),
            ('bin-media-metadata', 'x.mp4', mp4(b'\0\1\2', b'\xa9cmt by Claude now'), 'refuse'),
            ('bin-identity-email', 'x.png', b'\x89PNG\r\n\x1a\n\0tEXtAuthor\0jane.tester@corp.example\0', 'refuse')]
    if len(user) >= 4:
        bins.append(('bin-user-path', 'x.dll', b'\0C:\\Users\\' + u1.encode() + b'\\Desktop\\x.fbx\0', 'refuse'))
    if 4 <= len(user) < 6:
        bins.append(('bin-short-user-in-words', 'x.dll', b'\0X' + u.encode() + b'ia.' + u.encode() + b'ish\0', 'pass'))
    bad = 0
    for cid, mode, expect, text in cases:
        t = apply_rules(text, rules, False, False) if mode == 'scrub' else text
        got = 'refuse' if enforced.search(t) else 'pass'
        bad += got != expect
        print(f'{"ok  " if got == expect else "FAIL"} {cid}: {got}' + ('' if got == expect else f' (expected {expect})'))
    tmp = tempfile.mkdtemp(prefix='ugf-selfcheck-')
    try:
        for cid, name, data, expect in bins:
            path = os.path.join(tmp, cid, name)
            write_bytes(path, data)
            rows = scan_binary(path, needles, media_payload(path), {n for n, c, m in needles if n in ('claude', 'openai', 'opus') or c == 'username'})
            got = 'refuse' if any(r[5] == 'binary' for r in rows) else 'pass'
            bad += got != expect
            print(f'{"ok  " if got == expect else "FAIL"} {cid}: {got}' + ('' if got == expect else f' (expected {expect})'))
    finally:
        remove_tree(tmp)
    total = len(cases) + len(bins)
    print(f'{"PASS" if not bad else "FAIL"}  self-check: {total - bad} of {total} samples as expected')
    return 1 if bad else 0


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
        # logs: the sessions' record and git.log, never the game's own JSON (a long hex or base64 value in game data is
        # data: replaced in UnityProject/ alone it would differ from the release commit in History/)
        new = apply_rules(text, rules, is_json, rel == 'git.log' or rel.startswith('History/sessions/'), counts)
        if new != text:
            write_bytes(full, new.encode(enc, 'replace'))
            if touched is not None:
                touched.append(rel)


COMMIT_ID = re.compile(r'(?<![0-9a-f])[0-9a-f]{40}(?![0-9a-f])')


def remap_text(text, cmap):
    """Every full commit id of the map in text -> its delivered id."""
    return COMMIT_ID.sub(lambda m: cmap.get(m.group(0), m.group(0)), text) if cmap else text


def remap_tree(root, cmap):
    """Every full commit id of the map in the text files under root -> its delivered id. Returns the files changed."""
    if not cmap:
        return 0
    n = 0
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
        new = remap_text(text, cmap)
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


def check_rules(repo):
    """The game contract and the sound rule on the repo's Assets/ (tools/validate-game.py check_rules; the owner's
    decisions of 2026-11-11): their errors, each saying what to change; [] when it meets them."""
    spec = importlib.util.spec_from_file_location('validate_game', os.path.join(HERE, 'validate-game.py'))
    vg = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(vg)
    rep = vg.Report()
    vg.check_rules(rep, repo, vg.git_ls(repo))
    return [f'{a}: {m}' for s, a, m in rep.items if s == 'error']


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
    game, title, shots, runs, rv, pending = c['game'], c['title'], c['shots'], c['runs'], c['rv'], c['pending']
    a = [f'# {title}', '']
    if shots:
        a += [f'![{shots[0][1]}](Screenshots/{shots[0][0]})', '']
    if pending:
        what = [{'ReplayScripts': '`ReplayScripts/` (the replay of the creation process)',
                 'Gameplay': '`Gameplay/` (the scenario videos)'}.get(p, f'`{p}/`') for p in pending]
        a += [f'> **Pending:** {" and ".join(what)} {"are" if len(what) > 1 else "is"} not in this delivery yet; everything else is',
              '> complete. This delivery is replaced by the complete one when they land.', '']
    intro = re.sub(r'(?s)<!--.*?-->', '', c['readme_src'].split('\n## ')[0])   # the template's notes are for the session
    intro = '\n'.join(l for l in intro.splitlines()[1:] if not re.match(r'\s*(!\[|<img)', l)).strip()
    if intro:
        a += [intro, '']
    a += [f'Version {c["version"] or "(not numbered)"}, release commit `{c["head"]}`.', '',
          '## Requirements', '',
          f'- Unity {c["engine"]} (Unity 6.3 LTS, with Windows Build Support) to open the project' + ('.' if repo else '; nothing to run the built player.'),
          '- 64-bit Windows 10/11 for the built player.', '- `git` and `git-lfs` to restore the history.']
    if rv:
        a.append('- Python 3.10+ and the Unity editor of each commit to run the creation replay (`ReplayScripts/README.md`).')
    a += ['', '## Package contents', '']
    if not repo:
        a.append('- `UnityProject/` — the completed game project at the release commit (`Assets/` with every `.meta`, `Packages/`, `ProjectSettings/`).')
    a += ['- `ReplayScripts/` — replay of the creation process from the recorded editor operations' +
          (', with its verification against the release commit (`ReplayScripts/Verification/`).' if rv else '. *(pending)*'),
          '- `workflow.jsonl` — editor, code and build operations, one row per operation, written when it happened. Rows with `actor` "user" and '
          '`op` "user.direction" summarise what the person directing the work asked for; later rows name the direction they act on.',
          '- `git.log` — every commit with its message and full diff (binary files as path and sha256).']
    if not repo:
        a.append(f'- `History/` — the full git history: `History/{game}.bundle` (every commit up to the release, and each task\'s start branch) and '
                 '`History/lfs/objects/` (every Git LFS file of every commit). Authors are anonymised as dev_NN.')
        if c['sessions']:
            a.append('  `History/sessions/` — the creation sessions as recorded, one JSON row per line, oldest first within a session: ' +
                     ('`messages.jsonl` holds every prompt the person typed (`role` "user") and every reply the model wrote (`role` "assistant") and, where the sessions were recorded with them, the reasoning summaries the agent saved (`role` "thinking"); '
                      if 'messages.jsonl' in c['sessions'] else '') +
                     ('`actions.jsonl` holds every tool call with its input and its result. ' if 'actions.jsonl' in c['sessions'] else '') +
                     '`session_id` (session_NN) and `time` tie the rows of one session together.')
    a.append('- `Brief/` — the original brief the game was built from (`Brief/brief.md`) and its design doc with story bible and status (`Brief/design.md`).')
    if not repo:
        a.append(f'- `Tasks/` — {len(c["task_rows"])} task(s) on this game for a game-creation environment (`Tasks/README.md`).')
    if runs:
        a.append(f'- `Gameplay/` — {"a video of one scenario" if len(runs) == 1 else f"videos of {len(runs)} scenarios"} of this version, played '
                 'through by the game\'s AutoPlay bot with the game audio (1920x1080, 60 fps, H.264 and AAC).')
    else:
        a.append('- `Gameplay/` — videos of the recorded scenarios, played through with the game audio. *(pending)*')
    if not repo:
        a.append(f'- `Build/` — the Windows release player (`Build/{c["exe"]}`).')
    a += ['- `Screenshots/` — the images in this README.', '- `manifest.json` — path, size and sha256 of every file, and the release metadata.', '',
          'Keep these files and folders together.', '', '## Play the game', '']
    if repo:
        a.append(f'Open the repository root as a project in Unity {c["engine"]} and press **Play**.')
    else:
        a.append(f'Run `Build/{c["exe"]}` (no installation), or open `UnityProject/` in Unity {c["engine"]} and press **Play**.')
    play = md_section(c['readme_src'], r'^(how to )?play|^controls')
    if play:
        a += ['', '\n'.join(l for l in play.splitlines() if not re.search(r'Build[/\\]', l)).strip()]
    a += ['', '## Replay the creation process', '']
    if rv:
        a += ['See `ReplayScripts/README.md` for the command and its options; the supplied project is not changed.', '',
              'The replay was run end to end, headless, from these scripts and verified against the release commit: **' +
              ('PASS' if rv['pass'] else 'FAIL') + '** (`ReplayScripts/Verification/report.md`). The verdict is metadata: the replay is',
              'part of every complete delivery, whether it passes or not.', '',
              '| Pass criterion | Result | Pass |', '|---|---|---|']
        a += [f'| {cr["text"]} | {cr["result"]} | {"yes" if cr["pass"] else "no"} |' for cr in rv['criteria']]
        if rv['exclusions']:
            a += ['', 'Known differences that are not content (normalised or not compared, listed explicitly):', '']
            a += [f'- `{e["id"]}` ({e["count"]}): {e["what"]}' for e in rv['exclusions']]
    else:
        a.append('`ReplayScripts/` is pending.')
    a += ['', '## Restore the git history', '']
    if repo:
        a.append('This repository is the history itself: every commit, with Git LFS for the binary files.')
    else:
        a += ["`History/` restores the project's repository at any commit (`git` and `git-lfs` needed):", '', '```',
              f'git clone History/{game}.bundle {game}', f'robocopy History\\lfs {game}\\.git\\lfs /E          # or: cp -r History/lfs {game}/.git/',
              f'cd {game}', 'git lfs install --local', 'git checkout <commit>      # any commit of git.log; main is the release commit',
              'git lfs checkout', '```', '', f'The release commit is `{c["head"]}`; `git.log`, ' + ('`ReplayScripts/` ' if rv else '') +
              'and the tasks use the same commit ids.']
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
    if runs:
        a += ['| Video | # | Scenario | Result | Length |', '|---|---|---|---|---|']
        a += [f'| `Gameplay/{game}_S{r["scenario"]}.mp4` | {r["scenario"]} | {r["name"]} | {r["result"]} | {r["seconds"]:.1f} s |' for r in runs]
        a.append('')
        notes = [r for r in runs if r['capture_notes']]   # what a recording did differently (manifest scenarios[].capture_notes)
        if notes:
            a += [f'Recording note, scenario {r["scenario"]}: {r["capture_notes"].rstrip(".")}.' for r in notes] + ['']
        a += ['The result (win, lose, timeout) is what the bot reached in that run; it is metadata, never a reason a run was chosen.', '']
    else:
        a += ['The scenario videos are pending.', '']
    scen = md_section(c['readme_src'], r'^scenarios')
    if scen:
        a += ['\n'.join(l for l in scen.splitlines() if 'Gameplay/' not in l).strip(), '']
    a += ['## Screenshots', '']
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
