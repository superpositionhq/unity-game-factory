"""tools/package-dataset.py on a throwaway Unity game (the fixture of test_validate_game.py, with a person's commit, a
start branch, a recording and a player build): the zip it writes, what the scrub leaves, the sessions' record, and what
refuses a package. Plain git and git-lfs; no Unity and no PowerShell.

    python -m unittest discover -s tools/tests -p "test_package_dataset.py" -v
"""
import io, json, os, re, shutil, subprocess, sys, tempfile, unittest, zipfile

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
            tool='Bash', tool_use_id='t1', input={'command': f'git -C {cwd} log --format=%H -1', 'session_id': S1},
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


def run(inp, *extra, env=None):
    # UGF_OUT and UGF_CONFIG inside the test's folder: what the packager keeps in the out folder stays there, and no test
    # reads this machine's config
    env = dict(dict(base.ENV, UGF_ROOT=inp['root'], UGF_OUT=os.path.join(inp['root'], 'deliverables'),
                    UGF_CONFIG=os.path.join(inp['root'], 'no-config.json'), UGF_MIN_FREE_GB='0', USERNAME=ACCOUNT,
                    COMPUTERNAME='JT-DESKTOP'), **(env or {}))
    return subprocess.run([sys.executable, os.path.join(TOOLS, 'package-dataset.py'), SLUG, '--build', inp['build'], '--brief', inp['brief'],
                           '--design', inp['design'], '--version', '1.0', *extra], capture_output=True, text=True, env=env)


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
