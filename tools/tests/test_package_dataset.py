"""tools/package-dataset.py on a throwaway Unity game (the fixture of test_validate_game.py, with a person's commit, a
start branch, a recording and a player build): the zip it writes, what the scrub leaves, the sessions' record, and what
refuses a package. Plain git and git-lfs; no Unity and no PowerShell.

    python -m unittest discover -s tools/tests -p "test_package_dataset.py" -v
"""
import hashlib, io, json, os, re, shutil, subprocess, sys, tempfile, time, unittest, zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_validate_game as base  # noqa: E402  the fixture: make_game, task, set_tasks, git, write

TOOLS, SLUG, vg = base.TOOLS, base.SLUG, base.vg
ACCOUNT = 'jtester'
S1, S2, S3 = ('11111111-2222-4333-8444-555555555555', '66666666-7777-4888-9999-aaaaaaaaaaaa', 'bbbbbbbb-cccc-4ddd-8eee-ffffffffffff')
BANNED = re.compile(r'(?i)superposition|game[-_ ]?factory|\banthropic\b|\bclaude\b|\bopenai\b|jtester|jane|tester@|corp\.example')


def row(**kv):
    return json.dumps(kv)


def make_inputs(tmp):
    """A game with tasks, one commit by a named person with an agent trailer, a start branch, and next to it the
    recording, the build and the brief files. Returns the paths."""
    root = os.path.join(tmp, 'root')
    repo = os.path.join(root, 'games', SLUG)
    os.makedirs(os.path.dirname(repo))
    start, ref = base.make_game(repo)
    base.write(repo, 'Docs/Notes.md', f'Built on C:\\Users\\{ACCOUNT}\\UnityWork with unity-game-factory and Claude Code.\n'
                                      'Mail jane.tester@corp.example. The Opus run went well; libopus stays.\n'
                                      f'Git Bash ate the backslashes: cd C:Users{ACCOUNT}UnityWorkgames failed.\n'
                                      'The keeper clip is Assets/Art/Keeper@Walk.anim (from Keeper.fbx).\n')
    base.write(repo, 'Docs/data/tiles.json', json.dumps({'tiles': 'ab12' * 75}) + '\n')   # game data: a long hex value
    env = dict(base.ENV, GIT_AUTHOR_NAME='Jane Tester', GIT_AUTHOR_EMAIL='jane.tester@corp.example',
               GIT_COMMITTER_NAME='Jane Tester', GIT_COMMITTER_EMAIL='jane.tester@corp.example')
    subprocess.run(['git', '-C', repo, 'add', '-A'], check=True, env=env)
    subprocess.run(['git', '-C', repo, 'commit', '-q', '-m', 'Add the notes\n\nBy Jane.\n\nCo-Authored-By: Claude <noreply@anthropic.com>'],
                   check=True, env=env)
    head = base.git(repo, 'rev-parse', 'HEAD')
    when = base.git(repo, 'log', '-1', '--format=%cI', head)
    # a task's own start branch, and a stray branch the delivery must not carry
    base.git(repo, 'branch', f'starts/{SLUG}-fix-hero-hud', start)
    base.git(repo, 'branch', 'experiment', start)
    base.git(repo, 'update-ref', 'refs/remotes/origin/starts/made-elsewhere', start)   # a start branch only origin has
    base.set_tasks(repo, {f'{SLUG}-fix-hero-hud': base.task(start, ref)})
    rec = os.path.join(root, '.recording', SLUG)
    cwd = f'C:\\Users\\{ACCOUNT}\\UnityWork\\games\\{SLUG}'
    before, after = when[:11] + '00:00:01' + when[19:], '2099-01-01T00:00:00+00:00'
    base.write(rec, 'actions.jsonl', '\n'.join([
        row(schema='agent-action/v0', time=before, project=SLUG, session_id=S1, agent='claude', event='PostToolUse', cwd=cwd,
            tool='Bash', tool_use_id='t1', input={'command': f'git -C {cwd} log --format=%H -1', 'session_id': S1,
                                                  'cut': f'C:\\Users\\{ACCOUNT}\\AppData\\Local\\Temp\\claude\\C--Users-{ACCOUNT}-UnityWork\\{S1[:16]}',
                                                  'notes': f'C:\\Users\\{ACCOUNT}\\AppData\\Roaming\\Claude\\side-session-notes\\local_{S1}\\notes.md'},
            response=f'{ref}\nsee C:\\Users\\{ACCOUNT}\\UnityWork\\unity-game-factory\\tools ' + 'QUJD' * 100),
        row(schema='agent-action/v0', time=before, project=SLUG, session_id=S2, agent='codex', event='PostToolUse', cwd=cwd,
            tool='apply_patch', tool_use_id='t2', input={'command': '*** Begin Patch'}, response='ok: runs/pilot-2c-opus-siege/summary.json'),
        row(schema='agent-action/v0', time=before, project=SLUG, session_id=S3, agent='claude', event='PostToolUse', cwd=cwd,
            tool='Bash', tool_use_id='t3', input={'command': 'python tools/package-dataset.py kiln-run'}, response='ok'),
        row(schema='agent-action/v0', time=after, project=SLUG, session_id=S1, agent='claude', event='Stop', cwd=cwd)]) + '\n')
    base.write(rec, 'messages.jsonl', '\n'.join([
        row(schema='agent-message/v0', time=before, project=SLUG, session_id=S1, agent='claude', role='user', message_id='m1',
            text='Keep the hero on the ground. Ask jane.tester@corp.example if Superposition agrees.'),
        row(schema='agent-message/v0', time=before, project=SLUG, session_id=S1, agent='claude', role='assistant', message_id='m2',
            model='claude-opus-5-5', text='Done by Claude; OpenAI was not used.'),
        row(schema='agent-message/v0', time=before, project=SLUG, session_id=S2, agent='codex', role='user', message_id='m3', text='Add the HUD.'),
        row(schema='agent-message/v0', time=before, project=SLUG, session_id=S3, agent='claude', role='user', message_id='m4', text='Package it.'),
        row(schema='agent-message/v0', time=after, project=SLUG, session_id=S1, agent='claude', role='user', message_id='m5', text='Later.')]) + '\n')
    build = os.path.join(tmp, 'build')
    for rel, data in (('KilnRun.exe', b'MZ' + b'\0' * 30), ('KilnRun_Data/app.info', b'Kiln Run\n'), ('UnityPlayer.dll', b'MZ\0\0'),
                      ('KilnRun.pdb', b'pdb'), ('KilnRun_BurstDebugInformation_DoNotShip/x.txt', b'x')):
        base.write(build, rel, data)
    base.write(tmp, 'brief.md', '# Brief\n\n' + 'Build a small kiln game. ' * 20)
    base.write(tmp, 'design.md', '# Design\n\n' + 'Systems, scenes and scenarios. ' * 20)
    return dict(root=root, repo=repo, build=build, head=head, start=start, ref=ref,
                brief=os.path.join(tmp, 'brief.md'), design=os.path.join(tmp, 'design.md'))


def run(inp, *extra, env=None, build=True, brief=True):
    # UGF_OUT and UGF_CONFIG inside the test's folder: what the packager keeps in the out folder stays there, and no test
    # reads this machine's config
    env = dict(dict(base.ENV, UGF_ROOT=inp['root'], UGF_OUT=os.path.join(inp['root'], 'deliverables'),
                    UGF_CONFIG=os.path.join(inp['root'], 'no-config.json'), UGF_MIN_FREE_GB='0', USERNAME=ACCOUNT,
                    COMPUTERNAME='JT-DESKTOP'), **(env or {}))
    args = [sys.executable, os.path.join(TOOLS, 'package-dataset.py'), SLUG, '--version', '1.0']
    args += ['--build', inp['build']] if build else []
    args += ['--brief', inp['brief'], '--design', inp['design']] if brief else []
    return subprocess.run(args + list(extra), capture_output=True, text=True, env=env)


PKG = base.load('package_dataset', 'package-dataset.py')
_PROBE = PKG.find_ffprobe()   # this machine's ffmpeg, when it has one: the videos are then real ones a probe accepts
FFMPEG = _PROBE and os.path.join(os.path.dirname(_PROBE), os.path.basename(_PROBE).replace('ffprobe', 'ffmpeg'))
_MP4 = []


def gameplay_mp4():
    """An mp4 the layout accepts (1920x1080 h264 + aac, one second) when ffmpeg is here, else bytes no probe reads (the
    tests' packager finds no ffprobe under their root, and the validators then note that the videos were not probed)."""
    if not _MP4:
        data = b'\0\0\0\x18ftypmp42' + bytes(range(256)) * 4
        if FFMPEG and os.path.isfile(FFMPEG):
            out = os.path.join(tempfile.mkdtemp(prefix='ugfv'), 'v.mp4')
            r = subprocess.run([FFMPEG, '-v', 'error', '-f', 'lavfi', '-i', 'color=c=black:s=1920x1080:r=60:d=1', '-f', 'lavfi',
                                '-i', 'anullsrc=r=48000:cl=stereo', '-t', '1', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-c:a', 'aac',
                                '-shortest', out], capture_output=True)
            if r.returncode == 0:
                data = base.read(out, 'rb')
            shutil.rmtree(os.path.dirname(out), ignore_errors=True)
        _MP4.append(data)
    return _MP4[0]


def pipeline_build(inp, commit, hits=(), status='ok', config='release'):
    """A pipeline build of commit, as build.ps1 leaves one: <root>/builds/<slug>/<sha8>/Windows/ (the fixture's player) and
    build_info.json (unity-build/1)."""
    d = os.path.join(inp['root'], 'builds', SLUG, commit[:8])
    shutil.copytree(inp['build'], os.path.join(d, 'Windows'))
    base.write(d, 'build_info.json', json.dumps({'schema': 'unity-build/1', 'game': SLUG, 'commit': commit, 'short_sha': commit[:8],
                                                 'status': status, 'config': config, 'backend': 'il2cpp', 'autoplay_version': 1,
                                                 'leak_scan': {'scanned': 'Windows\\', 'hits': list(hits)}}))
    return d


def bundle(inp, commit, scenario, stamp, status='ok', result='win', marker=None, notes=None):
    """A recording as record.ps1 leaves one: <root>/recordings/<slug>/<run id>/ with metadata.json, validation.json,
    gameplay.mp4 and eight stills (also in recordings/<slug>/_stills/). Returns the run id."""
    run_id = f'{SLUG}_S{scenario}_{stamp}_s7'
    d = os.path.join(inp['root'], 'recordings', SLUG, run_id)
    base.write(d, 'metadata.json', json.dumps({
        'schema': 'unity-autoplay-bundle/v1', 'run_id': run_id, 'game': SLUG, 'scenario': scenario, 'scenario_name': f'Kiln {scenario}',
        'result': result, 'capture_notes': notes, 'status': status, 'video_start_offset_ns': 1000000000,
        'system_audio': {'start_offset_ns': 1250000000, 'aligned': True},
        'build': {'commit': commit, 'short_sha': commit[:8], 'config': 'release', 'backend': 'il2cpp',
                  'path': f'C:\\Users\\{ACCOUNT}\\UnityWork\\builds\\{SLUG}\\{commit[:8]}'},
        'gameplay_mp4': {'file': 'gameplay.mp4', 'duration_s': 21.5, 'audio_offset_s': 0.25, 'error': None}}))
    base.write(d, 'validation.json', json.dumps({'status': status, 'problems': [], 'checks': {'video': {'duration_s': 21.5}}}))
    base.write(d, 'gameplay.mp4', gameplay_mp4())
    for i in range(1, 9):
        still = b'\xff\xd8\xff\xe0' + bytes([scenario, i]) * 40
        base.write(d, f'stills/{i:02d}.jpg', still)
        base.write(os.path.join(inp['root'], 'recordings', SLUG, '_stills'), f'{run_id}_{i:02d}.jpg', still)
    if marker:
        base.write(d, marker, 'excluded\n')
    return run_id


def replay(inp, commit, passed=False, ready=True):
    """The creation replay's package of commit, as unity_replay.py release leaves it: <out>/_replay/<slug>/<sha8>/ with
    ReplayScripts/ (unscrubbed) and READY."""
    d = os.path.join(inp['root'], 'deliverables', '_replay', SLUG, commit[:8])
    rs = os.path.join(d, 'ReplayScripts')
    base.write(rs, 'Verification/report.json', json.dumps({
        'schema': 'unity-replay.verification/v1', 'game': SLUG, 'final_commit': commit, 'time': '2026-11-10T00:00:00+00:00',
        'files': {}, 'assets': {'total': 3}, 'scenes': {}, 'rows': {}, 'windows': [{'window': 1, 'commit': commit}],
        'verdict': {'pass': passed, 'criteria': [{'id': 'files', 'text': 'every tracked file outside Assets/ byte-identical',
                                                  'result': '3 identical, 1 differs', 'pass': passed}],
                    'exclusions': [{'id': 'guid', 'what': 'GUID strings Unity writes at random', 'count': 2, 'items': []}]}}, indent=1))
    base.write(rs, 'Verification/report.md', f'# Replay verification\n\n## Verdict: {"PASS" if passed else "FAIL"}\n')
    base.write(rs, 'README.md', '# ReplayScripts: creation replay of kiln-run\n')
    base.write(rs, 'ledger.json', json.dumps({'final': commit, 'note': f'replayed in C:\\Users\\{ACCOUNT}\\UnityWork\\unity-replay\\{SLUG}'}))
    base.write(rs, 'unity_replay.py', 'print("replay")\n')
    base.write(rs, '__pycache__/unity_replay.cpython-312.pyc', b'\0\0pyc')
    if ready:
        base.write(d, 'READY', '2026-11-10T00:00:00+00:00\n')
    return d


def manifest_of(path):
    with zipfile.ZipFile(path) as z:
        return json.loads(z.read(f'{SLUG}/manifest.json'))


def commit(repo, files, message):
    """Write files ({repo path: text or bytes}) and commit them, by the fixture's dev_1."""
    for rel, data in files.items():
        base.write(repo, rel, data)
    base.git(repo, 'add', '-A')
    base.git(repo, 'commit', '-q', '-m', message)
    return base.git(repo, 'rev-parse', 'HEAD')


@unittest.skipUnless(base.HAS_LFS, 'git-lfs is not installed')
class Package(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix='ugfp')
        cls.inp = make_inputs(cls.tmp)
        cls.res = run(cls.inp)
        cls.zip = os.path.join(cls.inp['repo'], 'Dataset.pending.zip')

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, onerror=base.onerror)

    def members(self):
        with zipfile.ZipFile(self.zip) as z:
            return {n[len(SLUG) + 1:]: z.read(n) for n in z.namelist()}

    def test_writes_a_valid_pending_zip(self):
        self.assertEqual(self.res.returncode, 0, self.res.stdout + self.res.stderr)
        self.assertTrue(os.path.isfile(self.zip))
        rep = vg.Report()
        vg.check_dataset(rep, self.zip, 'dataset')
        self.assertEqual(base.errors(rep), [])
        m = json.loads(self.members()['manifest.json'])
        self.assertEqual((m['status'], m['pending'], m['variant'], m['version']), ('pending', ['ReplayScripts', 'Gameplay'], 'full', '1.0'))
        self.assertEqual(m['build']['exe'], 'Build/KilnRun.exe')
        self.assertEqual(m['tasks']['names'], [f'{SLUG}-fix-hero-hud'])

    def test_entries(self):
        names = set(self.members())
        for want in ('README.md', 'git.log', 'workflow.jsonl', 'Brief/brief.md', 'Brief/design.md', f'History/{SLUG}.bundle',
                     'History/sessions/messages.jsonl', 'History/sessions/actions.jsonl', f'Tasks/{SLUG}-fix-hero-hud/task.json',
                     f'Tasks/{SLUG}-fix-hero-hud/grader.json', 'Tasks/README.md', 'UnityProject/ProjectSettings/ProjectVersion.txt',
                     'UnityProject/Assets/Scripts/Kiln.cs', 'Screenshots/hero.jpg', 'Build/KilnRun.exe', 'Build/KilnRun_Data/app.info'):
            self.assertIn(want, names)
        self.assertFalse([n for n in names if n.endswith('.pdb') or 'DoNotShip' in n or n.startswith(('Gameplay/', 'ReplayScripts/'))])
        # an LFS file of the project arrives as its content, and as its object in the history
        self.assertTrue(self.members()['UnityProject/Docs/screenshots/hero.jpg'].startswith(b'\xff\xd8\xff'))
        self.assertTrue([n for n in names if n.startswith('History/lfs/objects/')])

    def test_no_name_is_left_in_text(self):
        for name, data in self.members().items():
            if name.endswith('.bundle') or name.startswith('History/lfs/objects/') or b'\0' in data[:8000]:
                continue
            hit = BANNED.search(data.decode('utf-8', 'replace'))
            self.assertIsNone(hit, f'{name}: {hit and hit.group(0)}')
        notes = self.members()['UnityProject/Docs/Notes.md'].decode()
        self.assertIn('C:\\Users\\dev\\UnityWork with studio-tools and agent-tool', notes)
        self.assertIn('The Model run went well; libopus stays.', notes)
        self.assertIn('cd C:UsersdevUnityWorkgames failed', notes)   # a path whose separators a shell dropped
        self.assertIn('Assets/Art/Keeper@Walk.anim', notes)          # a clip's file name is no e-mail address
        tiles = json.loads(self.members()['UnityProject/Docs/data/tiles.json'])
        self.assertEqual(tiles['tiles'], 'ab12' * 75)                  # the game's data stays as committed

    def test_history_is_rewritten(self):
        m = json.loads(self.members()['manifest.json'])
        h = m['history']
        self.assertEqual(sorted(h['refs']), ['refs/heads/main', f'refs/heads/starts/{SLUG}-fix-hero-hud', 'refs/heads/starts/made-elsewhere'])
        self.assertNotEqual(m['commit'], self.inp['head'])
        work = os.path.join(self.tmp, 'restored.git')
        with open(os.path.join(self.tmp, 'h.bundle'), 'wb') as f:
            f.write(self.members()[h['bundle']])
        subprocess.run(['git', 'clone', '-q', '--bare', '--mirror', os.path.join(self.tmp, 'h.bundle'), work], check=True, capture_output=True)
        log = base.git(work, 'log', '--all', '--format=%an|%ae|%cn|%ce|%B')
        self.assertNotRegex(log, r'(?i)jane|tester|claude|anthropic')
        self.assertRegex(log, r'dev_\d+\|dev_\d+@example\.invalid')
        self.assertEqual(base.git(work, 'rev-parse', 'refs/heads/main'), m['commit'])
        self.assertEqual(base.git(work, 'for-each-ref', '--format=%(refname)').split(), sorted(h['refs']))   # no side branch
        self.assertEqual(base.git(work, 'symbolic-ref', 'HEAD'), 'refs/heads/main')
        self.assertEqual(int(base.git(work, 'rev-list', '--all', '--count')), h['commits'])
        # the task's seeds name commits of the delivered history
        t = json.loads(self.members()[f'Tasks/{SLUG}-fix-hero-hud/task.json'])
        g = json.loads(self.members()[f'Tasks/{SLUG}-fix-hero-hud/grader.json'])
        for c in (t['seed']['commit'], g['seed']['reference']):
            self.assertEqual(base.git(work, 'cat-file', '-t', c), 'commit')
        self.assertNotIn('reference', t['seed'])
        self.assertEqual(t['seed']['history'], 'dataset')   # the seed names commits of the delivered history
        self.assertNotIn('milestones', t)
        self.assertTrue(self.members()['git.log'].decode().startswith('GIT-LOG 1\n'))
        self.assertIn(f'commit {m["commit"]}\n', self.members()['git.log'].decode())

    def test_sessions(self):
        mem = self.members()
        msgs = [json.loads(l) for l in mem['History/sessions/messages.jsonl'].decode().splitlines()]
        acts = [json.loads(l) for l in mem['History/sessions/actions.jsonl'].decode().splitlines()]
        # rows after the release commit and the packaging session are left out; ids are numbered the same in both files
        self.assertEqual([(r['session_id'], r['role']) for r in msgs],
                         [('session_01', 'user'), ('session_01', 'assistant'), ('session_02', 'user')])
        self.assertEqual([(r['session_id'], r['tool']) for r in acts], [('session_01', 'Bash'), ('session_02', 'apply_patch')])
        self.assertEqual(msgs[0]['text'], 'Keep the hero on the ground. Ask <redacted-email> if Studio agrees.')
        self.assertEqual(msgs[1]['text'], 'Done by Agent; Provider was not used.')
        self.assertEqual(msgs[1]['model'], 'agent-model')
        self.assertEqual(acts[0]['input']['session_id'], 'session')            # a session id inside a tool's input
        self.assertEqual(acts[0]['input']['cut'], 'C:\\Users\\dev\\AppData\\Local\\Temp\\session')   # a session folder cut short
        self.assertEqual(acts[0]['input']['notes'], 'C:\\Users\\dev\\AppData\\Roaming\\session\\notes\\notes.md')
        self.assertIn('<base64 omitted, 300 bytes', acts[0]['response'])
        self.assertEqual(acts[1]['response'], 'ok: runs/pilot-2c-model-siege/summary.json')   # the model's name as a segment
        m = json.loads(mem['manifest.json'])
        delivered = json.loads(mem[f'Tasks/{SLUG}-fix-hero-hud/grader.json'])['seed']['reference']
        self.assertTrue(acts[0]['response'].startswith(delivered + '\n'))   # a commit id is the delivered history's
        self.assertNotEqual(delivered, self.inp['ref'])
        self.assertEqual(m['history']['sessions'], {'messages': {'file': 'History/sessions/messages.jsonl', 'rows': 3},
                                                    'actions': {'file': 'History/sessions/actions.jsonl', 'rows': 2}})
        readme = mem['README.md'].decode()
        self.assertIn('History/sessions/', readme)
        self.assertIn('pending', readme.lower())

    def test_repo_dataset_folder(self):
        ds = os.path.join(self.inp['repo'], 'Dataset')
        rep = vg.Report()
        vg.check_dataset(rep, ds, 'dataset')
        self.assertEqual(base.errors(rep), [])
        self.assertEqual(sorted(os.listdir(ds)), ['.gitattributes', 'Brief', 'README.md', 'Screenshots', 'git.log', 'manifest.json',
                                                  'workflow.jsonl'])
        self.assertTrue(base.read(os.path.join(ds, '.gitattributes')).startswith('* -text\n'))   # committed byte for byte
        self.assertIsNone(json.loads(base.read(os.path.join(ds, 'manifest.json')))['history'])
        self.assertFalse(os.path.exists(os.path.join(self.inp['repo'], '.dataset', f'{SLUG}.history.git')))
        self.assertEqual(base.git(self.inp['repo'], 'rev-parse', 'HEAD'), self.inp['head'])   # the game's history is not changed
        self.assertIn('original\tdelivered', base.read(os.path.join(self.inp['repo'], '.dataset', f'{SLUG}.commit-map.tsv')))


@unittest.skipUnless(base.HAS_LFS, 'git-lfs is not installed')
class Complete(unittest.TestCase):
    """A release with the pipeline's build, recordings and the creation replay: Dataset.zip, status complete."""
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix='ugfc')
        inp = cls.inp = make_inputs(cls.tmp)
        head, start = inp['head'], inp['start']
        pipeline_build(inp, head)
        cls.runs = {
            'failed': bundle(inp, head, 1, '20990101-000000', status='failed', marker='FAILED'),
            's1': bundle(inp, head, 1, '20990101-000100', result='lose'),
            's1_later': bundle(inp, head, 1, '20990101-000200'),
            's2': bundle(inp, head, 2, '20990101-000300', result='timeout', notes='Low quality for 60 fps capture'),
            'invalid': bundle(inp, head, 3, '20990101-000400', marker='INVALID'),
            'older': bundle(inp, start, 4, '20990101-000500')}
        replay(inp, head)
        cls.res = run(inp, build=False)   # the player: the pipeline's build of the release commit
        cls.zip = os.path.join(inp['repo'], 'Dataset.zip')

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, onerror=base.onerror)

    def members(self):
        with zipfile.ZipFile(self.zip) as z:
            return {n[len(SLUG) + 1:]: z.read(n) for n in z.namelist()}

    def test_a_complete_zip(self):
        self.assertEqual(self.res.returncode, 0, self.res.stdout + self.res.stderr)
        self.assertFalse(os.path.exists(os.path.join(self.inp['repo'], 'Dataset.pending.zip')))
        rep = vg.Report()
        vg.check_dataset(rep, self.zip, 'dataset')
        self.assertEqual(base.errors(rep), [])
        m = manifest_of(self.zip)
        self.assertEqual((m['status'], m['pending']), ('complete', []))
        self.assertIn('COMPLETE', self.res.stdout)

    def test_gameplay_from_the_first_valid_run_of_each_scenario(self):
        m, mem = manifest_of(self.zip), self.members()
        self.assertEqual([(s['scenario'], s['source_run'], s['result']) for s in m['scenarios']],
                         [(1, self.runs['s1'], 'lose'), (2, self.runs['s2'], 'timeout')])   # the result never picks a run
        s1 = m['scenarios'][0]
        self.assertEqual((s1['file'], s1['name'], s1['seconds'], s1['audio_offset_s']), (f'Gameplay/{SLUG}_S1.mp4', 'Kiln 1', 21.5, 0.25))
        self.assertNotIn('capture_notes', s1)
        self.assertEqual(m['scenarios'][1]['capture_notes'], 'Low quality for 60 fps capture')
        self.assertEqual(sorted(n for n in mem if n.startswith('Gameplay/')), [f'Gameplay/{SLUG}_S1.mp4', f'Gameplay/{SLUG}_S2.mp4'])
        self.assertEqual(mem[f'Gameplay/{SLUG}_S1.mp4'], gameplay_mp4())
        readme = mem['README.md'].decode()
        self.assertIn(f'| `Gameplay/{SLUG}_S2.mp4` | 2 | Kiln 2 | timeout | 21.5 s |', readme)
        self.assertIn('Recording note, scenario 2: Low quality for 60 fps capture.', readme)
        for k in ('failed', 'invalid', 'older'):   # FAILED, INVALID and a run of another commit are named, never taken
            self.assertIn(f'recording {self.runs[k]} not taken', self.res.stdout)

    def test_replay_scripts_with_a_fail_verdict(self):
        m, mem = manifest_of(self.zip), self.members()
        rv = m['replay_verification']
        self.assertEqual((rv['pass'], rv['report']), (False, 'ReplayScripts/Verification/report.md'))
        self.assertEqual(rv['criteria'], [{'id': 'files', 'text': 'every tracked file outside Assets/ byte-identical',
                                           'result': '3 identical, 1 differs', 'pass': False}])
        self.assertEqual(rv['exclusions'], [{'id': 'guid', 'what': 'GUID strings Unity writes at random', 'count': 2}])
        report = json.loads(mem['ReplayScripts/Verification/report.json'])
        self.assertEqual(report['final_commit'], m['commit'])   # the replay's commit ids are the delivered history's
        self.assertEqual(report['windows'][0]['commit'], m['commit'])
        ledger = json.loads(mem['ReplayScripts/ledger.json'])
        self.assertEqual(ledger['note'], f'replayed in C:\\Users\\dev\\UnityWork\\unity-replay\\{SLUG}')   # scrubbed like the rest
        self.assertFalse([n for n in mem if '__pycache__' in n])
        readme = mem['README.md'].decode()
        self.assertIn('verified against the release commit: **FAIL**', readme)
        self.assertNotIn('**Pending:**', readme)

    def test_the_pipelines_player(self):
        m = manifest_of(self.zip)
        self.assertEqual(m['build']['commit'], m['commit'])
        self.assertEqual(m['build']['source'], "the pipeline's release build of the release commit (tools/unity-pipeline/build.ps1, il2cpp)")
        self.assertIn('Build/KilnRun.exe', self.members())

    def test_the_audit_beside_the_deliveries(self):
        m = manifest_of(self.zip)
        out = os.path.join(self.inp['root'], 'deliverables', SLUG)
        report = json.loads(base.read(os.path.join(out, f'{SLUG}_{m["commit"][:8]}.scrub-report.json')))
        self.assertEqual((report['schema'], report['delivered_commit'], report['commit']), ('scrub-report/1', m['commit'], self.inp['head']))
        self.assertGreater(report['files_touched_count'], 0)
        self.assertEqual(report['scan']['text_and_path_hits'], 0)
        self.assertIn('username', {r['id'] for r in report['rules']})
        (row,) = [json.loads(l) for l in base.read(os.path.join(out, 'package-log.jsonl')).splitlines()]
        self.assertEqual((row['status'], row['delivered_commit'], row['replay']), ('complete', m['commit'], 'FAIL'))
        self.assertEqual(row['zip'], self.zip)
        self.assertTrue(os.path.isfile(row['audit']['leaks.tsv']))
        self.assertFalse([n for n in self.members() if 'scrub-report' in n or n.endswith('.tsv')])   # never in the delivery

    def test_the_repo_dataset_folder_has_gameplay_and_replay(self):
        ds = os.path.join(self.inp['repo'], 'Dataset')
        rep = vg.Report()
        vg.check_dataset(rep, ds, 'dataset')
        self.assertEqual(base.errors(rep), [])
        self.assertTrue(os.path.isfile(os.path.join(ds, 'Gameplay', f'{SLUG}_S2.mp4')))
        self.assertTrue(os.path.isfile(os.path.join(ds, 'ReplayScripts', 'Verification', 'report.json')))
        self.assertEqual(json.loads(base.read(os.path.join(ds, 'manifest.json')))['status'], 'complete')


@unittest.skipUnless(base.HAS_LFS, 'git-lfs is not installed')
class Products(unittest.TestCase):
    """What the release's build, recordings and replay decide, one case each."""
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='ugfq')
        self.inp = make_inputs(self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp, onerror=base.onerror)

    def test_without_ready_the_replay_is_pending(self):
        head = self.inp['head']
        bundle(self.inp, head, 1, '20990101-000100')
        replay(self.inp, head, ready=False)   # a replay still being packaged
        r = run(self.inp, '--no-repo-dataset')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn('is not finished (no READY)', r.stdout)
        m = manifest_of(os.path.join(self.inp['repo'], 'Dataset.pending.zip'))
        self.assertEqual((m['status'], m['pending'], m['replay_verification']), ('pending', ['ReplayScripts'], None))
        self.assertEqual(len(m['scenarios']), 1)

    def test_a_replay_of_another_commit_refuses(self):
        head = self.inp['head']
        d = replay(self.inp, head)
        rp = os.path.join(d, 'ReplayScripts', 'Verification', 'report.json')
        report = json.loads(base.read(rp))
        report['final_commit'] = self.inp['start']
        base.write(os.path.dirname(rp), 'report.json', json.dumps(report))
        r = run(self.inp, '--dry-run')
        self.assertEqual(r.returncode, 2)
        self.assertIn('not the release commit', r.stdout)

    def test_leak_scan_hits_refuse(self):
        pipeline_build(self.inp, self.inp['head'], hits=[{'file': 'Windows\\GameAssembly.dll', 'pattern': 'claude', 'count': 1}])
        r = run(self.inp, '--dry-run', build=False)
        self.assertEqual(r.returncode, 2)
        self.assertIn('leak-scan hit(s) in build_info.json', r.stdout)

    def test_an_earlier_pipeline_build_is_named(self):
        pipeline_build(self.inp, self.inp['start'])   # the release commit has no build of its own
        r = run(self.inp, '--no-repo-dataset', '--no-zip', build=False)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn('commit(s) before the release commit', r.stdout)
        m = json.loads(base.read(os.path.join(self.inp['repo'], '.dataset', SLUG, 'manifest.json')))
        self.assertNotEqual(m['build']['commit'], m['commit'])
        self.assertNotIn(self.inp['start'], json.dumps(m))   # the build's commit by its delivered id
        self.assertIn(f"the pipeline's release build of commit {m['build']['commit'][:12]}", m['build']['source'])

    def test_a_build_outside_the_release_history_refuses(self):
        base.git(self.inp['repo'], 'switch', '-q', '-c', 'side', self.inp['start'])
        side = commit(self.inp['repo'], {'Docs/Side.md': 'side work\n'}, 'Side work')
        base.git(self.inp['repo'], 'switch', '-q', 'main')
        d = pipeline_build(self.inp, side)
        r = run(self.inp, '--dry-run', '--build', d, build=False)
        self.assertEqual(r.returncode, 2)
        self.assertIn('which is not in the history of the release commit', r.stdout)

    @unittest.skipUnless(os.name == 'nt', 'the pipeline lock is a Windows file opened without sharing')
    def test_the_pipelines_lock_refuses(self):
        import ctypes
        from ctypes import wintypes
        k32 = ctypes.WinDLL('kernel32', use_last_error=True)
        k32.CreateFileW.restype = wintypes.HANDLE
        k32.CreateFileW.argtypes = (wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD,
                                    wintypes.HANDLE)
        k32.CloseHandle.argtypes = (wintypes.HANDLE,)
        builds = os.path.join(self.inp['root'], 'builds')
        base.write(builds, f'_pipeline-{SLUG}.lock.json', json.dumps({'pid': 4242, 'job': f'build {SLUG} 0123abcd', 'since': 'now'}))
        # as common.ps1 Enter-PipelineLock holds it: read and write, no sharing, opened or created
        h = k32.CreateFileW(os.path.join(builds, f'_pipeline-{SLUG}.lock'), 0xC0000000, 0, None, 4, 0x80, None)
        self.assertNotIn(h, (None, ctypes.c_void_p(-1).value))
        try:
            r = run(self.inp, '--dry-run')
        finally:
            k32.CloseHandle(h)
        self.assertEqual(r.returncode, 2)
        self.assertIn(f'the pipeline is working on {SLUG} right now: build {SLUG} 0123abcd (pid 4242', r.stdout)
        self.assertEqual(run(self.inp, '--dry-run').returncode, 0)   # freed: the file alone is no lock

    def test_screenshots_fall_back_to_the_recordings_stills(self):
        repo = self.inp['repo']
        readme = base.read(os.path.join(repo, 'README.md'))
        head = commit(repo, {'README.md': re.sub(r'(?m)^.*(!\[|<img).*\n', '', readme)}, 'The README without images')
        shutil.rmtree(os.path.join(repo, 'Docs', 'screenshots'), onerror=base.onerror)
        head = commit(repo, {}, 'No screenshots folder')
        run_id = bundle(self.inp, head, 1, '20990101-000100')
        r = run(self.inp, '--no-repo-dataset', '--no-zip')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        shots = sorted(os.listdir(os.path.join(repo, '.dataset', SLUG, 'Screenshots')))
        self.assertEqual(shots, [f'{run_id}_{n}.jpg' for n in ('01', '03', '05', '07')])
        self.assertIn('Screenshots/ holds stills of the recordings', r.stdout)

    def test_a_session_build_before_a_content_change_is_named(self):
        # D14: the template's flow commits the build's workflow row after the build; only a later change to the game's
        # content or code (Assets/, Packages/) means the build is not the release's
        repo, exe = self.inp['repo'], os.path.join(self.inp['build'], 'KilnRun.exe')
        future = int(time.time()) + 100
        os.utime(exe, (future, future))
        env = dict(base.ENV, GIT_COMMITTER_DATE=f'{future + 50} +0000', GIT_AUTHOR_DATE=f'{future + 50} +0000')
        base.write(repo, 'workflow.jsonl', base.read(os.path.join(repo, 'workflow.jsonl')) + '\n')
        subprocess.run(['git', '-C', repo, 'commit', '-qam', 'Record the build row'], check=True, env=env)
        r = run(self.inp, '--dry-run')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertNotIn('was built before', r.stdout)
        base.write(repo, 'Assets/Scripts/Kiln.cs', base.read(os.path.join(repo, 'Assets', 'Scripts', 'Kiln.cs')) + '// later\n')
        subprocess.run(['git', '-C', repo, 'commit', '-qam', 'Change the kiln after the build'], check=True, env=env)
        r = run(self.inp, '--dry-run')
        self.assertIn('Build/KilnRun.exe was built before 1 commit(s) that changed Assets/ or Packages/', r.stdout)

    def test_the_brief_comes_from_the_release_commit(self):
        repo = self.inp['repo']
        commit(repo, {'Brief/brief.md': '# Brief\n\n' + 'The committed brief. ' * 20, 'Brief/design.md': '# Design\n\n' + 'Committed. ' * 30},
               'Add the brief and the design doc')
        base.write(repo, 'Brief/brief.md', '# Brief\n\n' + 'An edit nobody committed. ' * 20)
        r = run(self.inp, '--no-repo-dataset', '--no-zip', brief=False)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertTrue(base.read(os.path.join(repo, '.dataset', SLUG, 'Brief', 'brief.md')).startswith('# Brief\n\nThe committed brief.'))


def box(kind, payload):
    return (8 + len(payload)).to_bytes(4, 'big') + kind + payload


def mp4(payload, handler=b'vide', meta=b''):
    """A minimal MP4: ftyp, moov with one track (its hdlr) and a udta of meta, mdat holding payload."""
    hdlr = box(b'hdlr', b'\0' * 8 + handler + b'\0' * 12 + b'track\0')
    moov = box(b'moov', box(b'trak', box(b'mdia', hdlr)) + (box(b'udta', meta) if meta else b''))
    return box(b'ftyp', b'isom\0\0\0\0isom') + moov + box(b'mdat', payload)


def ebml(eid, payload):
    n = len(payload)
    return eid + (bytes([0x80 | n]) if n < 127 else bytes([0x40 | (n >> 8), n & 0xFF])) + payload


def mkv(frame, tags=b''):
    """A minimal Matroska: one video track, one cluster with a SimpleBlock of frame data, and a Tags element of tags."""
    head = ebml(b'\x1a\x45\xdf\xa3', ebml(b'\x42\x82', b'matroska'))
    tracks = ebml(b'\x16\x54\xae\x6b', ebml(b'\xae', ebml(b'\xd7', b'\x01') + ebml(b'\x83', b'\x01')))
    cluster = ebml(b'\x1f\x43\xb6\x75', ebml(b'\xe7', b'\x00') + ebml(b'\xa3', b'\x81\x00\x00\x80' + frame))
    return head + ebml(b'\x18\x53\x80\x67', tracks + cluster + (ebml(b'\x12\x54\xc3\x67', tags) if tags else b''))


class Scan(unittest.TestCase):
    """The scan's rules on files made here: what refuses, what is listed and what is allowed."""
    USER = 'nora'

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='ugfs')
        self.needles = PKG.binary_needles(self.USER, [('Jane Tester', 'dev_01'), ('jtester42', 'dev_01')], ['jane.tester@corp.example'])

    def tearDown(self):
        shutil.rmtree(self.tmp, onerror=base.onerror)

    def scan(self, files, reviewed=None):
        for rel, data in files.items():
            base.write(self.tmp, rel, data)
        return PKG.scan_tree(self.tmp, PKG.enforced_pattern(self.USER, []), self.needles, self.USER, reviewed)

    def kinds(self, out, rel):
        return sorted({b[6] for b in out['binary'] if b[0] == rel} | {a[1] for a in out['allowed'] if a[0] == rel})

    def test_the_opus_codec_and_the_models_name(self):
        rnd = __import__('random').Random(7)
        noise = lambda: bytes(rnd.randrange(256) for _ in range(600))   # noqa: E731
        out = self.scan({'Build/a.dll': b'\0opus_decode\0SpcSpOpusInfo\0libopus.dll\0audio/opus\0',   # the codec's own forms
                         'Build/b.dat': noise() + b'\xf3\xf2k3opusSe\xa0\x12' + noise(),               # compressed bytes spell it
                         'Build/c.dll': b'\0trained on claude-opus-4 weights\0'})                     # the model's name
        self.assertEqual(self.kinds(out, 'Build/a.dll'), ['allowed-codec'])
        self.assertEqual(self.kinds(out, 'Build/b.dat'), ['allowed-entropy'])
        self.assertEqual(self.kinds(out, 'Build/c.dll'), ['binary'])

    def test_media_payloads_allow_short_terms_their_metadata_does_not(self):
        frame = b'\x00\x01' + b'xx Claude xx' + b'\x02'
        out = self.scan({'Gameplay/kiln-run_S1.mp4': mp4(frame), 'Gameplay/kiln-run_S2.mp4': mp4(b'\0\1\2', meta=b'\xa9cmt Made by Claude now'),
                         'UnityProject/Assets/a.wav': b'RIFF\x30\0\0\0WAVEdata\x10\0\0\0' + frame[:16],
                         'UnityProject/Assets/b.mkv': mkv(frame), 'UnityProject/Assets/c.mkv': mkv(b'\0\1\2', tags=b'by Claude here!')})
        self.assertEqual(self.kinds(out, 'Gameplay/kiln-run_S1.mp4'), ['allowed-stream'])
        self.assertEqual(self.kinds(out, 'Gameplay/kiln-run_S2.mp4'), ['binary'])
        self.assertEqual(self.kinds(out, 'UnityProject/Assets/a.wav'), ['allowed-stream'])
        self.assertEqual(self.kinds(out, 'UnityProject/Assets/b.mkv'), ['allowed-stream'])
        self.assertEqual(self.kinds(out, 'UnityProject/Assets/c.mkv'), ['binary'])
        # an mp4 with a track that is neither video nor audio (subtitles) gets no allowance
        out = self.scan({'Gameplay/kiln-run_S3.mp4': mp4(frame, handler=b'sbtl')})
        self.assertEqual(self.kinds(out, 'Gameplay/kiln-run_S3.mp4'), ['binary'])

    def test_a_short_account_name(self):
        out = self.scan({'Build/locale.bin': b'\0\1zh_nora\0\1',        # a locale id
                         'Build/cstring.bin': b'\x01\x02\0Nora\0\x03',  # a whole C string, however short
                         'Build/random.bin': b'\x01\x02\x7fNora\x03',   # a few letters among random bytes: listed only
                         'Build/word.bin': b'\0Manor.Minoratoria\0'})    # inside longer words: no hit
        self.assertEqual(self.kinds(out, 'Build/locale.bin'), ['allowed-locale'])
        self.assertEqual(self.kinds(out, 'Build/cstring.bin'), ['binary'])
        self.assertEqual(self.kinds(out, 'Build/random.bin'), ['binary-info'])
        self.assertEqual(self.kinds(out, 'Build/word.bin'), [])

    def test_the_historys_people_and_addresses(self):
        out = self.scan({'UnityProject/Assets/a.png': b'\x89PNG\r\n\x1a\n\0tEXtAuthor\0jane.tester@corp.example\0',
                         'UnityProject/Assets/b.fbx': b'\0Kaydara\0Creator\0Jane Tester\0',
                         'UnityProject/Assets/c.fbx': b'\0Creator\0Jane Testers Guild\0',      # a longer name: not theirs
                         'Build/UnityPlayer.dll': b'\0contact vrpn@cs.unc.edu for help\0'})
        self.assertEqual(self.kinds(out, 'UnityProject/Assets/a.png'), ['binary'])
        self.assertEqual(self.kinds(out, 'UnityProject/Assets/b.fbx'), ['binary'])
        self.assertEqual(self.kinds(out, 'UnityProject/Assets/c.fbx'), [])
        self.assertEqual([(e[0], e[2]) for e in out['emails']], [('Build/UnityPlayer.dll', 'vrpn@cs.unc.edu')])   # listed only

    def test_a_reviewed_hit(self):
        data = b'\x10\x11\x12' + b'random claudeXYZ bytes' + b'\x13'
        out = self.scan({'Build/x.bin': data})
        (hit,) = [b for b in out['binary'] if b[6] == 'binary']
        reviewed = {(hashlib.sha256(data).hexdigest(), hit[1]): hit[5]}
        out = self.scan({'Build/x.bin': data}, reviewed)
        self.assertEqual(self.kinds(out, 'Build/x.bin'), ['allowed-reviewed'])
        out = self.scan({'Build/x.bin': data + b'\0'}, reviewed)   # another version of the file: refuses again
        self.assertEqual(self.kinds(out, 'Build/x.bin'), ['binary'])

    def test_text_allowances_and_other_profiles(self):
        out = self.scan({'History/sessions/actions.jsonl': '{"r": "zh_nora", "b": "\\\\x86\\\\x12\\\\x99Nora\\\\x1c\\\\x00\\\\x01"}\n',
                         'UnityProject/Docs/Notes.md': 'Copied from C:\\Users\\bob\\Desktop and /home/alice/art; see C:\\Users\\dev\\x.\n'})
        self.assertEqual(out['hits'], [])
        self.assertEqual(sorted(a[1] for a in out['allowed']), ['allowed-escaped-bytes', 'allowed-locale'])
        self.assertEqual(sorted(l[2] for l in out['leaks']), ['/home/alice', 'C:\\Users\\bob'])


@unittest.skipUnless(base.HAS_LFS, 'git-lfs is not installed')
class Refusals(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='ugfr')
        self.inp = make_inputs(self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp, onerror=base.onerror)

    def test_no_build(self):
        shutil.rmtree(self.inp['build'])
        r = run(self.inp)
        self.assertEqual(r.returncode, 2)
        self.assertIn('no player build', r.stdout)
        self.assertFalse(os.path.exists(os.path.join(self.inp['repo'], 'Dataset.pending.zip')))

    def test_only_this_games_release_player(self):
        # a development player: its UnityPlayer.dll names the development variant's debug symbols
        base.write(self.inp['build'], 'UnityPlayer.dll', b'MZ\0\0' + b'C:\\build\\UnityPlayer_Win64_player_development_mono_x64.pdb\0')
        r = run(self.inp, '--dry-run')
        self.assertEqual(r.returncode, 2)
        self.assertIn('KilnRun.exe is a development player', r.stdout)
        # another product's release player (app.info: company, then product)
        base.write(self.inp['build'], 'UnityPlayer.dll', b'MZ\0\0' + b'C:\\build\\UnityPlayer_Win64_player_mono_x64.pdb\0')
        base.write(self.inp['build'], 'KilnRun_Data/app.info', b'Other Studio\nLamp Keeper')
        r = run(self.inp, '--dry-run')
        self.assertEqual(r.returncode, 2)
        self.assertIn('is a player of "Lamp Keeper", not of this game ("Kiln Run"', r.stdout)
        base.write(self.inp['build'], 'KilnRun_Data/app.info', b'Kiln Run\nKiln Run')
        self.assertEqual(run(self.inp, '--dry-run').returncode, 0)

    def test_no_tasks(self):
        base.git(self.inp['repo'], 'update-ref', '-d', 'refs/heads/tasks')
        r = run(self.inp)
        self.assertEqual(r.returncode, 2)
        self.assertIn('no tasks', r.stdout)

    def test_dry_run_writes_nothing(self):
        r = run(self.inp, '--dry-run')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertFalse(os.path.exists(os.path.join(self.inp['repo'], '.dataset')))
        self.assertFalse(os.path.exists(os.path.join(self.inp['repo'], 'Dataset.pending.zip')))

    def test_one_run_per_game(self):
        # a run holds <out>/<slug>/.package.lock: a second one at the same time is refused before it touches the scratch
        lock = os.path.join(self.inp['root'], 'deliverables', SLUG, '.package.lock')
        os.makedirs(os.path.dirname(lock))
        with open(lock, 'a+b') as f:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            r = run(self.inp, '--no-repo-dataset')
        self.assertEqual(r.returncode, 2)
        self.assertIn('another package-dataset run of this game', r.stderr)
        r = run(self.inp, '--no-repo-dataset')   # the lock freed
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        maps = [n for n in os.listdir(os.path.dirname(lock)) if n.endswith('.commit-map.tsv')]
        self.assertEqual(len(maps), 1)   # kept beside the deliveries: <slug>_<delivered head 8>.commit-map.tsv

    def test_a_second_run(self):
        # git writes its pack files read-only: the first run's scratch must not stop the second (on Windows it did)
        for _ in range(2):
            r = run(self.inp, '--no-repo-dataset')
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertFalse(os.path.exists(os.path.join(self.inp['repo'], '.dataset', f'{SLUG}.history.git')))

    def test_the_committed_dataset_folder_checks_out_unchanged(self):
        # a session commits Dataset/, and a checkout with core.autocrlf (Git for Windows' default) must give back the bytes
        # manifest.json lists
        r = run(self.inp)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        repo = self.inp['repo']
        base.git(repo, 'config', 'core.autocrlf', 'true')
        base.git(repo, 'add', 'Dataset')
        base.git(repo, 'commit', '-q', '-m', 'Commit the dataset folder')
        shutil.rmtree(os.path.join(repo, 'Dataset'), onerror=base.onerror)
        base.git(repo, 'checkout', '--', 'Dataset')
        rep = vg.Report()
        vg.check_dataset(rep, os.path.join(repo, 'Dataset'), 'dataset')
        self.assertEqual(base.errors(rep), [])

    def test_a_name_in_a_binary_refuses_unless_lenient(self):
        base.write(self.inp['build'], 'KilnRun_Data/level0', b'\0\1\2' + b'built by unity-game-factory tools' + b'\0\1')
        r = run(self.inp)
        self.assertEqual(r.returncode, 2)
        self.assertIn('name(s) left', r.stderr)
        r = run(self.inp, '--lenient-binaries')   # listed only: to review a refusal
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn('binary file(s)', r.stdout)
        hits = base.read(os.path.join(self.inp['repo'], '.dataset', f'{SLUG}.binary-hits.tsv'))
        self.assertIn('Build/KilnRun_Data/level0', hits)

    def test_a_short_account_name_inside_a_longer_word_is_no_hit(self):
        # the engine's own files spell a short account name inside longer words and identifiers, in any case; a path
        # with the name in a binary is a hit
        base.write(self.inp['build'], 'KilnRun_Data/Managed/System.Core.dll', b'\0\1' + b'.ManorAccess.Minoratoria.' * 3 + b'\0')
        r = run(self.inp, env={'USERNAME': 'nora'})
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        base.write(self.inp['build'], 'KilnRun_Data/level0', b'\0\1\2' + b'C:\\Users\\Nora\\Desktop\\kiln.fbx' + b'\0\1')
        r = run(self.inp, env={'USERNAME': 'nora'})
        self.assertEqual(r.returncode, 2)
        self.assertIn('KilnRun_Data/level0', base.read(os.path.join(self.inp['repo'], '.dataset', f'{SLUG}.refused-hits.tsv')))

    def test_a_name_on_a_start_branch_alone_refuses(self):
        # git.log shows main's history only; a start branch's own commits are in the bundle alone, and are scanned there
        repo = self.inp['repo']
        base.git(repo, 'switch', '-q', f'starts/{SLUG}-fix-hero-hud')
        commit(repo, {'Docs/Start.md': f'The art went to {ACCOUNT}_old first.\n'}, 'Make the start')
        base.git(repo, 'switch', '-q', 'main')
        r = run(self.inp, '--no-repo-dataset')
        self.assertEqual(r.returncode, 2)
        hits = base.read(os.path.join(repo, '.dataset', f'{SLUG}.refused-hits.tsv'))
        self.assertIn(f'History/{SLUG}.bundle\thistory\tDocs/Start.md', hits)

    def test_the_account_name_glued_into_a_word_refuses(self):
        # OwnerNameDesktop: a lower -> upper boundary is a word's edge, so the name is found where the scrub leaves it
        commit(self.inp['repo'], {'Docs/Owner.md': f'The shortcut was named Owner{ACCOUNT.capitalize()}Desktop.\n'}, 'Add the owner note')
        r = run(self.inp, '--no-repo-dataset')
        self.assertEqual(r.returncode, 2)
        self.assertIn('UnityProject/Docs/Owner.md', base.read(os.path.join(self.inp['repo'], '.dataset', f'{SLUG}.refused-hits.tsv')))

    def test_excluded_session(self):
        r = run(self.inp, '--exclude-sessions', S2, '--no-repo-dataset')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        with zipfile.ZipFile(os.path.join(self.inp['repo'], 'Dataset.pending.zip')) as z:
            msgs = [json.loads(l) for l in io.TextIOWrapper(z.open(f'{SLUG}/History/sessions/messages.jsonl'), encoding='utf-8')]
        self.assertEqual({m['session_id'] for m in msgs}, {'session_01'})
        self.assertFalse(os.path.isfile(os.path.join(self.inp['repo'], 'Dataset', 'manifest.json')))


if __name__ == '__main__':
    unittest.main()
