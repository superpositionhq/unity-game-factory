"""tools/validate-game.py on throwaway Unity game repos: a valid one (with a long-thread task on its orphan tasks branch
and a full Dataset.zip) and one broken variant per rule. Fixtures are made with plain git, no Unity and no PowerShell.

    python -m unittest discover -s tools/tests -p "test_validate_game.py" -v
"""
import hashlib, importlib.util, io, json, os, re, shutil, stat, subprocess, sys, tempfile, unittest, zipfile

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = os.path.dirname(TOOLS)
TEMPLATE = os.path.join(REPO, 'templates', 'unity-game')
CONTRACT = os.path.join(TOOLS, 'task_check', 'CONTRACT.md')


def load(name, file):
    spec = importlib.util.spec_from_file_location(name, os.path.join(TOOLS, file))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


vg = load('validate_game', 'validate-game.py')
SLUG = 'kiln-run'
HAS_LFS = subprocess.run(['git', 'lfs', 'version'], capture_output=True).returncode == 0
ENV = dict(os.environ, GIT_AUTHOR_NAME='dev_1', GIT_AUTHOR_EMAIL='dev_1@example.com', GIT_COMMITTER_NAME='dev_1',
           GIT_COMMITTER_EMAIL='dev_1@example.com', GIT_CONFIG_NOSYSTEM='1')


def git(repo, *args, input=None):
    r = subprocess.run(['git', '-C', repo, *args], capture_output=True, env=ENV, input=input)
    if r.returncode != 0:
        raise RuntimeError(f'git {" ".join(args)}: {r.stderr.decode(errors="replace")}')
    return r.stdout.decode('utf-8', 'replace').strip()


def read(path, mode='r'):
    with open(path, mode, **({} if 'b' in mode else {'encoding': 'utf-8'})) as f:
        return f.read()


def write(repo, rel, data):
    p = os.path.join(repo, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, 'wb') as f:
        f.write(data if isinstance(data, bytes) else data.encode('utf-8'))


def guid(rel):
    return hashlib.md5(rel.encode()).hexdigest()


def meta(repo, rel, folder=False):
    """rel's .meta, and its folders' .meta up to Assets/ (or the embedded package root)."""
    parts = rel.split('/')
    top = 2 if parts[0] == 'Packages' else 1
    for i in range(top + 1, len(parts) + 1):
        path = '/'.join(parts[:i])
        body = f'fileFormatVersion: 2\nguid: {guid(path)}\n'
        if i < len(parts) or folder:
            body += 'folderAsset: yes\n'
        write(repo, path + '.meta', body)


def asset(repo, rel, data):
    write(repo, rel, data)
    meta(repo, rel)


def code(cls, n):
    """A C# file of about n lines."""
    lines = [f'public class {cls} : UnityEngine.MonoBehaviour', '{']
    lines += [f'    public float field{i} = {i}f;' for i in range(n - 3)]
    return '\n'.join(lines + ['}']) + '\n'


YAML = '%YAML 1.1\n%TAG !u! tag:unity3d.com,2011:\n--- !u!1 &1\nGameObject:\n  m_Name: {}\n'


def commit(repo, msg):
    git(repo, 'add', '-A')
    git(repo, 'commit', '-q', '-m', msg)
    return git(repo, 'rev-parse', 'HEAD')


def set_tasks(repo, tasks, extra=None):
    """The orphan tasks branch with Tasks/<name>.json per task (plumbing: the work tree stays on main)."""
    entries = []
    for name, t in tasks.items():
        blob = git(repo, 'hash-object', '-w', '--stdin', input=json.dumps(t, indent=2).encode())
        entries.append(f'100644 blob {blob}\t{name}.json')
    sub = git(repo, 'mktree', input=('\n'.join(entries) + '\n').encode())
    root_entries = [f'040000 tree {sub}\tTasks']
    readme = git(repo, 'hash-object', '-w', '--stdin', input=b'# Tasks\n')
    root_entries.append(f'100644 blob {readme}\tREADME.md')
    root = git(repo, 'mktree', input=('\n'.join(root_entries) + '\n').encode())
    c = git(repo, 'commit-tree', root, *(extra or []), '-m', 'Tasks')
    git(repo, 'update-ref', 'refs/heads/tasks', c)
    return c


def workflow_row(n, op='project.create', **extra):
    row = {'schema': 'unity-workflow/v0', 'id': f'kr-{n:05d}', 'seq': n, 'time': f'2026-11-0{1 + n % 8}T10:00:00.000+01:00',
           'actor': 'agent', 'op': op, 'target': 'ProjectSettings/ProjectVersion.txt',
           'params': {'engine': 'unity 6000.3.26f1'}, 'reason': 'Create the project', 'reason_source': 'agent_note',
           'source': {'script': 'new-game.ps1', 'sha256': 'a' * 64, 'commit': None}, 'status': 'observed'}
    row.update(extra)
    return json.dumps(row)


def make_game(repo):
    """A Unity 6000.3 game with a long thread (4 commits, 5 game files, 120 code lines, 3 systems). Returns
    (start, reference) of that thread."""
    os.makedirs(repo)
    git(repo, 'init', '-q', '-b', 'main')
    hooks = os.path.join(os.path.dirname(repo), 'nohooks')
    os.makedirs(hooks, exist_ok=True)
    for k, v in (('core.hooksPath', hooks), ('core.autocrlf', 'false'), ('commit.gpgsign', 'false'),
                 ('user.name', 'dev_1'), ('user.email', 'dev_1@example.com')):
        git(repo, 'config', k, v)
    git(repo, 'lfs', 'install', '--local')
    for name in ('.gitignore', '.gitattributes'):
        shutil.copy(os.path.join(TEMPLATE, name), os.path.join(repo, name))
    for rel in ('ProjectSettings/EditorSettings.asset', 'Scripts/unity.ps1', 'Docs/ThirdPartyNotices.md',
                'Packages/manifest.json', 'Assets/Editor/Steps/README.md'):
        write(repo, rel, read(os.path.join(TEMPLATE, rel)).replace('__PROJECT__', 'KilnRun'))
    meta(repo, 'Assets/Editor/Steps/README.md')
    write(repo, 'ProjectSettings/ProjectVersion.txt', 'm_EditorVersion: 6000.3.26f1\nm_EditorVersionWithRevision: 6000.3.26f1 (x)\n')
    write(repo, 'ProjectSettings/ProjectSettings.asset', YAML.format('x') + '  companyName: Kiln Run\n  productName: Kiln Run\n')
    write(repo, 'Packages/packages-lock.json', '{"dependencies": {}}\n')
    asset(repo, 'Assets/Scenes/Main.unity', YAML.format('Main'))
    asset(repo, 'Assets/Scripts/Kiln.cs', code('Kiln', 30))
    asset(repo, 'Assets/ThirdParty/Kenney/crate.png', b'\x89PNG\r\n\x1a\n' + b'\0' * 64)
    asset(repo, 'Assets/Samples~/Ignored.cs', 'class Ignored {}\n')   # Unity skips name~ folders: no .meta
    write(repo, 'Assets/Samples~.meta', 'should not be here\n')         # ... and a .meta of one is not checked
    write(repo, 'Docs/screenshots/hero.jpg', b'\xff\xd8\xff' + b'\1' * 64)
    write(repo, 'README.md', '# Kiln Run\n\n![Kiln Run](Docs/screenshots/hero.jpg)\n\nA game.\n')
    write(repo, 'assets.manifest.json', json.dumps({'schema': 'assets-manifest/v1', 'project': 'KilnRun', 'assets': [
        {'name': 'Crates', 'source': 'Kenney', 'url': 'https://kenney.nl/assets', 'licence': 'CC0 1.0',
         'files': ['Assets/ThirdParty/Kenney/']}]}, indent=2))
    write(repo, 'workflow.jsonl', workflow_row(1) + '\n' + workflow_row(
        2, op='user.direction', actor='user', target='design', params={'direction': 'Keep the hero on the ground.',
                                                                    'via': 'direct'},
        reason_source='user_direction') + '\n')
    start = commit(repo, 'Create the project')
    asset(repo, 'Assets/Scripts/Hero.cs', code('Hero', 40))
    start_c1 = commit(repo, 'Add the hero controller')
    asset(repo, 'Assets/Scripts/Hud.cs', code('Hud', 40))
    commit(repo, 'Add the score HUD')
    asset(repo, 'Assets/Scripts/Enemy.cs', code('Enemy', 40))
    asset(repo, 'Assets/Prefabs/Hero.prefab', YAML.format('Hero'))
    commit(repo, 'Add enemies and the hero prefab')
    write(repo, 'ProjectSettings/TagManager.asset', YAML.format('tags') + '  tags:\n  - Enemy\n')
    asset(repo, 'Assets/Scripts/Kiln.cs', code('Kiln', 34))
    ref = commit(repo, 'Tag enemies and fix the kiln')
    assert start_c1
    return start, ref


def task(start, ref, **over):
    t = {
        'name': f'{SLUG}-fix-hero-hud', 'title': 'Hero falls and the score freezes',
        'instruction': 'In scenario 2 the hero drops through the floor near the kiln and the score stops counting.',
        'engine': 'unity-6000.3',
        'seed': {'game': SLUG, 'commit': start, 'reference': ref, 'kind': 'bug_fix'},
        'play_scene': 'Assets/Scenes/Main.unity', 'play_args': ['-scenario', '2'], 'player': {'tag': 'Player'},
        'difficulty': 'hard', 'tags': ['long-thread'],
        'limits': {'max_turns': 400, 'max_minutes': 480, 'max_usd': 150, 'tool_timeout_seconds': 1800},
        'milestones': [
            {'name': 'builds', 'checks': [{'name': 'player_builds', 'kind': 'build', 'weight': 0}]},
            {'name': 'boots', 'checks': [{'name': 'boots_clean', 'kind': 'boot', 'seconds': 60, 'weight': 0,
                                          'needs': ['player_builds']}]},
            {'name': 'fixed', 'checks': [
                {'name': 'hero_on_ground', 'kind': 'probe', 'weight': 3, 'needs': ['boots_clean'],
                 'describe': 'The hero stays on the ground near the kiln.', 'play': 'look',
                 'measure': {'probe': 'player', 'field': 'y', 'window': [3, 18], 'agg': 'min'},
                 'expect': {'op': '>=', 'calibrate': 0.5}},
                {'name': 'score_counts', 'kind': 'probe', 'needs': ['boots_clean'],
                 'describe': 'The score readout rises while the hero collects.',
                 'play': {'name': 'collect', 'seconds': 20, 'scene': 'Assets/Scenes/Main.unity',
                          'args': ['-scenario', '3'],
                          'inputs': [{'t': 1, 'key': '<Keyboard>/w', 'press': True},
                                     {'t': 6, 'key': '<Keyboard>/w', 'press': False},
                                     {'t': 7, 'key': '<Mouse>/delta/x', 'axis': 4.0},
                                     {'t': 8, 'widget': 'RetryButton', 'click': True}]},
                 'measure': {'probe': 'ui', 'field': 'number', 'agg': 'rises',
                             'select': {'kind': 'text', 'rect': [0, 0, 0.3, 0.1]}},
                 'expect': {'op': '>=', 'value': 1}},
                {'name': 'enemies_glow', 'kind': 'probe', 'needs': ['boots_clean'],
                 'describe': 'The enemies give off light again.', 'play': 'drive',
                 'measure': {'probe': 'objects', 'select': {'component': 'Enemy', 'has': {'lit': True}},
                             'field': 'glow', 'of': 'max'},
                 'expect': {'op': '>', 'calibrate': 0.5}}]},
            {'name': 'still_works', 'checks': [
                {'name': 'hero_moves', 'kind': 'probe', 'weight': 0, 'needs': ['boots_clean'],
                 'describe': 'The hero still moves.', 'play': 'drive',
                 'measure': {'probe': 'player', 'field': 'moved', 'agg': 'max'}, 'expect': {'op': '>', 'value': 2}}]},
            {'name': 'quality', 'checks': [
                {'name': 'worked_well', 'kind': 'actions_judge', 'required': False, 'question': 'Did it test?',
                 'rubric': [{'key': 'tested', 'criterion': 'It played the scenario after the fix.'}]}]}]}
    t.update(over)
    return t


def errors(rep, area=None):
    return [m for s, a, m in rep.items if s == 'error' and (area is None or a.startswith(area))]


def onerror(fn, path, _):
    os.chmod(path, stat.S_IWRITE)
    fn(path)


@unittest.skipUnless(HAS_LFS, 'git-lfs is not installed')
class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix='ugfv')
        cls.base = os.path.join(cls.tmp, 'base', SLUG)
        cls.start, cls.ref = make_game(cls.base)
        set_tasks(cls.base, {f'{SLUG}-fix-hero-hud': task(cls.start, cls.ref)})

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, onerror=onerror)

    def setUp(self):
        self.n = getattr(type(self), '_n', 0) + 1
        type(self)._n = self.n
        self.repo = os.path.join(self.tmp, f'{self._testMethodName[:20]}{self.n}', SLUG)
        shutil.copytree(self.base, self.repo, symlinks=True)

    def check(self):
        rep = vg.Report()
        vg.check_repo(rep, self.repo)
        return rep


class ValidGame(Base):
    def test_valid_repo(self):
        rep = self.check()
        self.assertEqual(errors(rep), [])
        notes = ' '.join(m for s, a, m in rep.items if s == 'note')
        self.assertIn('Unity 6000.3.26f1', notes)
        self.assertIn('1 task(s) on tasks', notes)

    def test_cli_exit_code(self):
        r = subprocess.run([sys.executable, os.path.join(TOOLS, 'validate-game.py'), self.repo, '--quiet'],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertTrue(r.stdout.startswith('VALID'))

    def test_seed_on_start_branch(self):
        # a made start (unity-write-tasks section 2): S = the thread taken out, R = a child with main's tree
        s = git(self.repo, 'commit-tree', f'{self.start}^{{tree}}', '-p', self.ref, '-m', 'start')
        r = git(self.repo, 'commit-tree', f'{self.ref}^{{tree}}', '-p', s, '-m', 'reference')
        name = f'{SLUG}-fix-hero-hud'
        git(self.repo, 'update-ref', f'refs/heads/starts/{name}', r)
        set_tasks(self.repo, {name: task(s, r)})
        self.assertEqual(errors(self.check()), [])
        git(self.repo, 'update-ref', '-d', f'refs/heads/starts/{name}')
        self.assertTrue(any('is not a commit of this game' in e for e in errors(self.check())))


class Meta(Base):
    def test_missing_meta(self):
        os.remove(os.path.join(self.repo, 'Assets/Scripts/Kiln.cs.meta'))
        os.remove(os.path.join(self.repo, 'Assets/ThirdParty.meta'))
        commit(self.repo, 'Lose two metas')
        errs = errors(self.check(), 'repo: .meta')
        self.assertTrue(any(e.startswith('Assets/Scripts/Kiln.cs: no .meta') for e in errs), errs)
        self.assertTrue(any(e.startswith('Assets/ThirdParty: no .meta') for e in errs), errs)

    def test_orphan_meta(self):
        write(self.repo, 'Assets/Ghost.png.meta', 'fileFormatVersion: 2\nguid: 0\n')
        write(self.repo, 'Assets/Empty.meta', 'fileFormatVersion: 2\nguid: 1\nfolderAsset: yes\n')
        commit(self.repo, 'Orphans')
        errs = errors(self.check(), 'repo: .meta')
        self.assertTrue(any(e.startswith('Assets/Ghost.png.meta: its file or folder') for e in errs), errs)
        self.assertTrue(any(e.startswith('Assets/Empty.meta') for e in errs), errs)

    def test_embedded_package(self):
        write(self.repo, 'Packages/com.kiln.tools/package.json', '{"name": "com.kiln.tools", "version": "1.0.0"}\n')
        write(self.repo, 'Packages/com.kiln.tools/Runtime/Tool.cs', 'class Tool {}\n')
        write(self.repo, 'Packages/com.kiln.tools/Documentation~/index.md', '# Tool\n')
        commit(self.repo, 'Embedded package without metas')
        errs = errors(self.check(), 'repo: .meta')
        self.assertEqual(sorted(e.split(':')[0] for e in errs),
                         ['Packages/com.kiln.tools/Runtime', 'Packages/com.kiln.tools/Runtime/Tool.cs',
                          'Packages/com.kiln.tools/package.json'])
        meta(self.repo, 'Packages/com.kiln.tools/package.json')
        meta(self.repo, 'Packages/com.kiln.tools/Runtime/Tool.cs')
        commit(self.repo, 'Metas')
        self.assertEqual(errors(self.check(), 'repo: .meta'), [])

    def test_meta_problems_unit(self):
        files = ['Assets/A/b.png', 'Assets/A/b.png.meta', 'Assets/A.meta', 'Assets/.hidden/x.txt', 'Assets/c.tmp',
                 'Assets/cvs/d.txt', 'Packages/manifest.json', 'Packages/x/package.json', 'Packages/x.meta',
                 'ProjectSettings/TagManager.asset', 'Assets/Z.meta']
        missing, orphan = vg.meta_problems(files)
        self.assertEqual(missing, ['Packages/x/package.json'])
        self.assertEqual(orphan, ['Assets/Z.meta'])


class RepoRules(Base):
    def test_banned_name(self):
        asset(self.repo, 'Assets/Data/credits.txt', 'Made with Game-Factory tools.\n')
        commit(self.repo, 'Credits')
        errs = errors(self.check(), 'repo: banned names')
        self.assertTrue(any(e.startswith('Assets/Data/credits.txt') for e in errs), errs)

    def test_unity_repo_name_banned(self):
        self.assertTrue(re.search(vg.SPEC['repo']['banned_names']['patterns'][1], 'cloned unity_game_factory here'))

    def test_wrong_editor_and_settings(self):
        write(self.repo, 'ProjectSettings/ProjectVersion.txt', 'm_EditorVersion: 2022.3.62f1\n')
        es = os.path.join(self.repo, 'ProjectSettings/EditorSettings.asset')
        text = read(es).replace('m_SerializationMode: 2', 'm_SerializationMode: 1')
        write(self.repo, 'ProjectSettings/EditorSettings.asset', text.replace('Visible Meta Files', 'Hidden Meta Files'))
        commit(self.repo, 'Downgrade')
        errs = errors(self.check(), 'repo')
        self.assertTrue(any("m_EditorVersion '2022.3.62f1'" in e for e in errs), errs)
        self.assertTrue(any('m_SerializationMode' in e for e in errs), errs)
        self.assertTrue(any('m_ExternalVersionControlSupport' in e for e in errs), errs)

    def test_gitignore_hides_assets(self):
        with open(os.path.join(self.repo, '.gitignore'), 'a') as f:
            f.write('Build/\nAssets/ThirdParty/\n')
        commit(self.repo, 'Ignore too much')
        errs = errors(self.check(), 'repo: .gitignore')
        self.assertTrue(any(e.startswith('Assets/_probe_/Build/Probe.cs would be git-ignored') for e in errs), errs)
        self.assertTrue(any(e.startswith('Assets/ThirdParty/_probe_/Probe.fbx') for e in errs), errs)

    def test_generated_folder_tracked_and_not_ignored(self):
        write(self.repo, '.gitignore', '/Dataset.zip\n/Dataset.pending.zip\n/.dataset/\n')
        write(self.repo, 'Library/ArtifactDB', 'x')
        commit(self.repo, 'Oops')
        errs = errors(self.check(), 'repo')
        self.assertTrue(any('Library/ArtifactDB' in e for e in errs), errs)
        self.assertTrue(any(e.startswith('Library/ is not ignored') for e in errs), errs)

    def test_lfs(self):
        attrs = os.path.join(self.repo, '.gitattributes')
        text = read(attrs).replace('*.[pP][nN][gG] filter=lfs diff=lfs merge=lfs -text', '')
        write(self.repo, '.gitattributes', text + '*.prefab filter=lfs diff=lfs merge=lfs -text\n')
        asset(self.repo, 'Assets/Art/plain.png', b'\x89PNG\r\n\x1a\n' + b'\2' * 64)
        asset(self.repo, 'Assets/Prefabs/Crate.prefab', YAML.format('Crate'))
        commit(self.repo, 'LFS mistakes')
        errs = errors(self.check(), 'repo: LFS')
        self.assertIn('binary tracked in plain git: Assets/Art/plain.png', errs)
        self.assertTrue(any(e.startswith('Unity YAML in LFS: Assets/Prefabs/Crate.prefab') for e in errs), errs)

    def test_assets_manifest(self):
        data = json.loads(read(os.path.join(self.repo, 'assets.manifest.json')))
        data['assets'].append({'name': 'Gone', 'source': 'x', 'url': 'https://x', 'licence': 'CC0',
                               'files': ['Content/Gone/', 'Assets/Gone.fbx']})
        write(self.repo, 'assets.manifest.json', json.dumps(data))
        commit(self.repo, 'Manifest')
        errs = errors(self.check(), 'repo: assets.manifest.json')
        self.assertIn('asset path outside Assets/, Packages/ or RawAssets/: Gone: Content/Gone/', errs)
        self.assertIn('listed asset file not present: Gone: Assets/Gone.fbx', errs)

    def test_workflow_rows(self):
        with open(os.path.join(self.repo, 'workflow.jsonl'), 'a') as f:
            f.write(workflow_row(2) + '\n' + workflow_row(3, schema='ue-workflow/v0') + '\n')
        commit(self.repo, 'Bad rows')
        errs = errors(self.check(), 'repo: workflow.jsonl')
        self.assertTrue(any('duplicate id kr-00002' in e for e in errs), errs)
        self.assertTrue(any('ue-workflow/v0' in e for e in errs), errs)

    def test_tasks_on_main(self):
        write(self.repo, f'Tasks/{SLUG}-x.json', '{}')
        commit(self.repo, 'Tasks on main')
        errs = errors(self.check(), 'repo: Tasks')
        self.assertTrue(any(e.startswith('main tracks 1 path(s) under Tasks/') for e in errs), errs)

    def test_tasks_branch_not_orphan(self):
        set_tasks(self.repo, {f'{SLUG}-fix-hero-hud': task(self.start, self.ref)}, extra=['-p', self.ref])
        self.assertTrue(any('shares history with main' in e for e in errors(self.check(), 'repo: Tasks')))

    def test_no_tasks_branch(self):
        git(self.repo, 'update-ref', '-d', 'refs/heads/tasks')
        self.assertTrue(any(e.startswith('no tasks branch') for e in errors(self.check(), 'repo: Tasks')))


class TaskRules(Base):
    def tasks(self, **over):
        set_tasks(self.repo, {f'{SLUG}-fix-hero-hud': task(self.start, self.ref, **over)})
        return errors(self.check(), 'repo: Tasks')

    def probe(self, i, **measure):
        t = task(self.start, self.ref)
        t['milestones'][2]['checks'][i]['measure'] = measure
        return t['milestones']

    def test_easy(self):
        errs = self.tasks(difficulty='easy')
        self.assertTrue(any("difficulty 'easy'" in e for e in errs), errs)

    def test_never_literal(self):
        ms = self.probe(2, probe='objects', select={'component': 'Enemy'}, field='spread', of='max')
        ms[2]['checks'][2]['expect'] = {'op': '>', 'value': 3}
        errs = self.tasks(milestones=ms)
        self.assertTrue(any("objects measure's spread depends on what a build chose" in e for e in errs), errs)
        for probe, field in (('audio', 'level'), ('components', 'glow'), ('ground', 'range')):
            m = {'probe': probe, 'field': field}
            if probe == 'components':
                m['select'] = {'component': 'Light'}
            if probe == 'ground':
                m['box'] = [0, 0, 10, 10]
            c = {'name': 'x', 'kind': 'probe', 'describe': 'x', 'play': 'look', 'measure': m,
                 'expect': {'op': '>', 'value': 0.1}}
            self.assertEqual(list(vg.check_schema(c, vg.SCHEMAS['game-task']['$defs']['Probe'],
                                                  vg.SCHEMAS['game-task'])), [], field)
            self.assertTrue(any('never a literal' in e for e in vg.probe_errors(c, {}, 'r', {})), field)

    def test_refused_play_args(self):
        ms = task(self.start, self.ref)['milestones']
        ms[2]['checks'][1]['play']['args'] = ['-screen-width', '100', '--taskProbe=x', '-Scenario', 'force-field']
        errs = self.tasks(play_args=['-batchmode', '-scenario', '2'], milestones=ms)
        self.assertTrue(any("play_args can't set -batchmode" in e for e in errs), errs)
        self.assertTrue(any("a task play can't set -screen-width" in e for e in errs), errs)
        self.assertTrue(any("a task play can't set -taskProbe" in e for e in errs), errs)
        self.assertFalse(any('Scenario' in e or 'force-field' in e for e in errs), errs)

    def test_denied_play_args_unit(self):
        self.assertEqual(list(vg.denied_play_args(
            ['-ParentHWND', '5', '-single-instance', '-force-vulkan', '-screen-fullscreen', '0', '-logFile', 'x',
             '-PopupWindow', '-monitor', '2', '-quit', '-nographics', '-executeMethod', '-projectPath', '-ok',
             'batchmode'])),
            ['ParentHWND', 'single-instance', 'force-vulkan', 'screen-fullscreen', 'logFile', 'PopupWindow',
             'monitor', 'quit', 'nographics', 'executeMethod', 'projectPath'])

    def test_bad_schema_field(self):
        ms = self.probe(2, probe='objects', select={'class': 'Enemy'}, field='bb:Speed')
        errs = self.tasks(milestones=ms, play_map='/Game/Maps/L_X')
        self.assertTrue(any('unexpected key "play_map"' in e for e in errs), errs)
        self.assertTrue(any('measure: matches none of the allowed shapes' in e for e in errs), errs)

    def test_seed_not_6000_3(self):
        pv = git(self.repo, 'hash-object', '-w', '--stdin', input=b'm_EditorVersion: 2022.3.62f1\n')
        git(self.repo, 'read-tree', self.start)
        git(self.repo, 'update-index', '--add', '--cacheinfo', f'100644,{pv},ProjectSettings/ProjectVersion.txt')
        tree = git(self.repo, 'write-tree')
        git(self.repo, 'read-tree', 'HEAD')
        old = git(self.repo, 'commit-tree', tree, '-p', self.ref, '-m', 'old editor')
        r = git(self.repo, 'commit-tree', f'{self.ref}^{{tree}}', '-p', old, '-m', 'ref')
        name = f'{SLUG}-fix-hero-hud'
        git(self.repo, 'update-ref', f'refs/heads/starts/{name}', r)
        set_tasks(self.repo, {name: task(old, r)})
        errs = errors(self.check(), 'repo: Tasks')
        self.assertTrue(any(f'seed.commit {old[:12]} is a Unity 2022.3.62f1 project' in e for e in errs), errs)
        self.assertFalse(any('seed.reference' in e and 'project' in e for e in errs), errs)

    def test_short_thread(self):
        errs = self.tasks(seed={'game': SLUG, 'commit': git(self.repo, 'rev-parse', f'{self.ref}~1'),
                                'reference': self.ref, 'kind': 'bug_fix'})
        for floor in ('game file(s) against the start, fewer than 5', 'code line(s) against the start, fewer than 100',
                      'commit(s) change the game from seed.commit to seed.reference, fewer than 4'):
            self.assertTrue(any(floor in e for e in errs), (floor, errs))

    def test_noop_and_outcomes(self):
        ms = task(self.start, self.ref)['milestones']
        ms[0]['checks'][0]['weight'] = 1
        del ms[2]['checks'][2]
        errs = self.tasks(milestones=ms, tags=[], seed={'game': 'other', 'commit': self.start, 'kind': 'feature'})
        for what in ('a no-op passes it', 'no long-thread tag', 'no seed.reference', 'fewer than 3',
                     "seed.game 'other' is not this game"):
            self.assertTrue(any(what in e for e in errs), (what, errs))

    def test_probe_rules(self):
        t = task(self.start, self.ref)
        checks = t['milestones'][2]['checks']
        checks[0]['measure'] = {'probe': 'ground', 'field': 'height', 'xz': [1, 2], 'box': [0, 0, 1, 1]}
        checks[1]['measure'] = {'probe': 'asset', 'asset': 'Assets/Materials/Lamp.mat', 'field': 'material_default'}
        checks[2]['measure'] = {'probe': 'components', 'select': {'near': {'point': {'player': True}, 'radius': 5,
                                                                          'y_min': 2, 'y_max': 1}}, 'field': 'count'}
        errs = vg.task_semantic_errors(t)
        for what in ('takes a point `xz` or a `box`', 'taken by the editor pass', 'of one asset takes no select',
                     'names its component, or `effect`', 'y_min < y_max'):
            self.assertTrue(any(what in e for e in errs), (what, errs))


# ---- the schema against the contract's examples ----------------------------------------------------------------------
def probe_check(measure, play='look', expect=None):
    return {'name': 'p', 'kind': 'probe', 'describe': 'x', 'play': play, 'measure': measure,
            'expect': expect or {'op': '>=', 'calibrate': 0.5}}


class Schema(unittest.TestCase):
    S = vg.SCHEMAS['game-task']

    def ok(self, value, ref):
        return list(vg.check_schema(value, self.S['$defs'][ref], self.S))

    def test_contract_fields(self):
        """Every measure field the contract (section 3) lists, with its prefixed forms, and nothing Unreal."""
        good = {
            'player': ['x', 'y', 'z', 'speed', 'moved', 'dist'],
            'camera': ['distance', 'height', 'pitch', 'yaw', 'fov', 'occluded', 'player_on_screen'],
            'objects': ['count', 'x', 'y', 'z', 'yaw', 'pitch', 'roll', 'scale', 'extent_x', 'extent_y', 'extent_z',
                        'active', 'hidden', 'collision', 'speed', 'spin', 'simulating', 'spread', 'changed',
                        'bounds_change', 'pose_change', 'lit', 'glow', 'prop:Health.current', 'prop:Inventory.items[2].count',
                        'prop:name', 'bone:Animator.LeftHand.y', 'rel_yaw:Turret', 'world_yaw:Head',
                        'world_pitch:Head', 'world_roll:Head', 'forward:Spot.z', 'facing_vs_velocity', 'anim:Speed',
                        'clip'],
            'components': ['count', 'active', 'visible', 'x', 'y', 'z', 'speed', 'spin', 'extent_x', 'extent_y',
                           'extent_z', 'simulating', 'changed', 'bounds_change', 'pose_change', 'lit', 'glow',
                           'intensity', 'on', 'prop:range', 'prop:colors[0].r'],
            'widgets': ['count', 'visible', 'text', 'percent', 'value', 'interactable', 'has_brush', 'brush', 'x',
                        'y', 'w', 'h'],
            'ui': ['count', 'text', 'x', 'y', 'w', 'h', 'signature', 'number', 'clock'],
            'screen': ['luminance', 'luma'], 'light': ['illuminance', 'exposure', 'brightness'],
            'grading': ['grey', 'cast', 'warmth', 'tint', 'saturation', 'contrast', 'post:Bloom.intensity',
                        'post:Vignette.intensity', 'post:ColorAdjustments.postExposure'],
            'pieces': ['count', 'visible', 'components', 'objects', 'triangles', 'visible_triangles'],
            'audio': ['count', 'audible', 'volume', 'max_volume', 'level'],
            'ground': ['height', 'hit', 'min', 'max', 'mean', 'range', 'hits'],
            'drawn': ['drawn', 'motion', 'base_r', 'base_g', 'base_b', 'base_change', 'reach', 'length'],
            'asset': ['prop:m_Shader', 'import:maxTextureSize', 'import:m_PlatformSettings.Array.data[0].maxTextureSize',
                      'shader:_BaseColor.r', 'shader:_Smoothness', 'keyword:_EMISSION', 'count', 'material_default',
                      'material:_BaseColor', 'mesh_collision', 'prop:MeshRenderer.receiveShadows'],
            'spawns': ['spawned', 'destroyed'], 'log': ['count']}
        bad = {'player': ['pawn_on_screen'], 'camera': ['pawn_on_screen'], 'objects': ['bb:Speed', 'actors'],
               'pieces': ['actors'], 'grading': ['post:BloomIntensity'], 'asset': ['shader:_BaseColor.x'],
               'components': ['prop:']}
        extra = {'objects': {'select': {'component': 'Enemy'}}, 'components': {'select': {'component': 'Light'}},
                 'widgets': {'select': {'component': 'Slider'}}, 'spawns': {'component': 'Projectile'},
                 'light': {'point': {'xyz': [0, 1, 0]}}, 'log': {'pattern': 'Error'}, 'asset': {'asset': 'Assets/x.mat'}}
        def check(probe, f):
            return self.ok(probe_check(dict({'probe': probe, 'field': f}, **extra.get(probe, {}))), 'Probe')
        for probe, fields in good.items():
            for f in fields:
                self.assertEqual(check(probe, f), [], f'{probe} {f}')
        for probe, fields in bad.items():
            for f in fields:
                self.assertNotEqual(check(probe, f), [], f'{probe} {f}')
        for unreal in ('pawn', 'actors'):
            self.assertNotEqual(check(unreal, 'x'), [])

    def test_contract_shapes(self):
        """Points, near, selects and inputs as the contract (sections 1-4) writes them."""
        sel = {'component': 'UnityEngine.UI.Button', 'tag': 'Player', 'layer': 'Ignore Raycast', 'name': 'Enemy (Clone)',
               'near': {'point': {'object': {'name': 'Kiln*'}, 'offset': [0, 1, 0]}, 'radius': 2.0,
                        'y_min': -1, 'y_max': 3, 'y_relative': True},
               'has': {'component': 'Light', 'lit': True, 'visible': True, 'simulating': True, 'movable': True},
               'player': True, 'inactive': True}
        self.assertEqual(self.ok(sel, 'Select'), [])
        for point in ({'xyz': [1, 2, 3]}, {'player': True, 'offset': [0, 1, 0]}, {'camera': True, 'forward': 5},
                      {'object': {'tag': 'Lamp'}, 'offset': [0, 0, 1]}):
            self.assertEqual(self.ok({'point': point, 'radius': 1}, 'Near'), [], point)
        self.assertNotEqual(self.ok({'point': {'pawn': True}, 'radius': 1}, 'Near'), [])
        self.assertNotEqual(self.ok({'point': {'xyz': [0, 0, 0]}, 'radius': 1, 'z_min': 0}, 'Near'), [])
        self.assertEqual(self.ok({'component': 'ParticleSystem', 'effect': True, 'name': 'Smoke*',
                                  'owner': {'tag': 'Kiln'}, 'near': {'point': {'xyz': [0, 0, 0]}, 'radius': 3},
                                  'mesh': 'Cube', 'visible': True}, 'ComponentSelect'), [])
        self.assertEqual(self.ok({'component': 'Slider', 'name': 'Health*', 'text': '^\\d+$', 'visible': True},
                                 'WidgetSelect'), [])
        self.assertNotEqual(self.ok({'slate': 'STextBlock'}, 'WidgetSelect'), [])
        self.assertEqual(self.ok({'kind': 'image', 'text': None, 'rect': [0, 0, 1, 0.2]}, 'UiSelect'), [])
        self.assertNotEqual(self.ok({'kind': 'line'}, 'UiSelect'), [])
        self.assertEqual(self.ok({'sound': 'Footstep*', 'sound_class': 'SFX', 'owner': {'player': True}},
                                 'AudioSelect'), [])
        self.assertEqual(self.ok({'component': 'MeshRenderer', 'name': 'Wall*', 'mesh': 'Brick', 'owner': {'tag': 'Town'},
                                  'near': {'point': {'xyz': [0, 0, 0]}, 'radius': 50}}, 'PieceSelect'), [])
        self.assertEqual(self.ok({'probe': 'ground', 'xz': [3, 4], 'field': 'height', 'select': {'layer': 'Ground'}},
                                 'GroundMeasure'), [])
        self.assertEqual(self.ok({'probe': 'ground', 'box': [0, 0, 10, 10], 'grid': 8, 'field': 'range'},
                                 'GroundMeasure'), [])
        self.assertNotEqual(self.ok({'probe': 'ground', 'xy': [3, 4], 'field': 'height'}, 'GroundMeasure'), [])
        self.assertEqual(self.ok({'probe': 'asset', 'scene': 'Assets/Scenes/Town.unity',
                                  'select': {'component': 'MeshRenderer', 'tag': 'Terrace'}, 'field': 'material_default',
                                  'of': 'all'}, 'AssetMeasure'), [])
        self.assertEqual(self.ok({'probe': 'asset', 'prefab': 'Assets/Prefabs/Hero (Variant).prefab',
                                  'select': {'name': 'Body'}, 'field': 'mesh_collision'}, 'AssetMeasure'), [])
        self.assertEqual(self.ok({'probe': 'spawns', 'component': 'Projectile', 'field': 'spawned'}, 'SpawnsMeasure'), [])
        self.assertEqual(self.ok({'probe': 'drawn', 'line': {'from': {'player': True}, 'to': {'camera': True, 'forward': 20},
                                                             'radius': 0.5}, 'field': 'reach'}, 'DrawnMeasure'), [])
        inputs = [{'t': 1, 'key': '<Keyboard>/w', 'press': True}, {'t': 1, 'key': '<Keyboard>/leftShift', 'press': True},
                  {'t': 1, 'key': '<Keyboard>/f2', 'press': True}, {'t': 1, 'key': '<Mouse>/leftButton', 'press': True},
                  {'t': 1, 'key': '<Gamepad>/buttonSouth', 'press': False},
                  {'t': 2, 'key': '<Mouse>/delta/x', 'axis': 4.0}, {'t': 2, 'key': '<Gamepad>/leftStick/x', 'axis': 1},
                  {'t': 2, 'key': '<Mouse>/scroll/y', 'axis': -1},
                  {'t': 3, 'widget': 'RetryButton', 'click': True}, {'t': 3, 'widget': 'Retry*', 'click': True},
                  {'t': 4, 'cursor': [0.5, 0.25]},
                  {'t': 5, 'teleport': [1, 2, 3], 'yaw': 90, 'hold': 2},
                  {'t': 6, 'teleport_to': {'component': 'Ore'}, 'distance': 2.0, 'offset': [0, 0.5, 0],
                   'face': {'object': {'tag': 'Kiln'}}, 'hold': 1},
                  {'t': 7, 'wait': 10}]
        play = {'name': 'route', 'seconds': 30, 'every': 0.5, 'inputs': inputs, 'scene': None, 'args': []}
        self.assertEqual(self.ok(play, 'TaskPlay'), [])
        for bad in ({'t': 1, 'key': 'W', 'press': True}, {'t': 1, 'key': '<Keyboard>/w'},
                    {'t': 1, 'key': '<Joystick>/trigger', 'press': True}):
            self.assertNotEqual(self.ok(dict(play, inputs=[bad]), 'TaskPlay'), [], bad)
        self.assertNotEqual(self.ok(dict(play, map='/Game/Maps/L_X'), 'TaskPlay'), [])
        self.assertNotEqual(self.ok(dict(play, scene='Assets/Scenes/X.scene'), 'TaskPlay'), [])

    def test_task_level(self):
        S = self.S
        t = task('a' * 40, 'b' * 40)
        self.assertEqual(list(vg.check_schema(t, S)), [])
        self.assertEqual(S['properties']['engine']['const'], 'unity-6000.3')
        self.assertNotIn('template', S['properties'])
        for bad in ({'engine': '5.7'}, {'template': 'blank-cpp'}, {'play_scene': '/Game/Maps/L_X'},
                    {'play_args': ['-scenario', 'two words']}, {'play_args': ['x'] * 17}):
            self.assertNotEqual(list(vg.check_schema(dict(t, **bad), S)), [], bad)
        self.assertEqual(list(vg.check_schema(dict(t, play_scene=None, play_args=[]), S)), [])
        self.assertEqual(vg.task_semantic_errors(t), [])

    def test_contract_inline_examples(self):
        """The contract's inline task examples: section 1's play_args, section 4's inputs as written there."""
        text = read(CONTRACT) if os.path.isfile(CONTRACT) else ''
        if not text:
            self.skipTest('no CONTRACT.md')
        args = json.loads(re.search(r'`play_args` \(`(\[.*?\])`\)', text).group(1))
        self.assertEqual(list(vg.check_schema(args, self.S['properties']['play_args'], self.S)), [])
        for path in set(re.findall(r'`(<(?:Keyboard|Mouse|Gamepad)>/[A-Za-z0-9/]+)`', text)):
            self.assertRegex(path, self.S['$defs']['Key']['properties']['key']['pattern'])
        self.assertEqual(self.ok({'t': 1, 'widget': 'RetryButton', 'click': True}, 'Click'), [])


# ---- the dataset ----------------------------------------------------------------------------------------------------
@unittest.skipUnless(HAS_LFS, 'git-lfs is not installed')
class Dataset(Base):
    def make_zip(self, mutate=None):
        repo, ds = self.repo, os.path.join(self.tmp, f'ds{self.n}', SLUG)
        head = git(repo, 'rev-parse', 'HEAD')
        log = ['GIT-LOG 1']
        for line in git(repo, 'log', '--reverse', '--format=%H|%P|%an|%aI|%cn|%cI|%s').splitlines():
            h, p, an, ad, cn, cd, s = line.split('|')
            log += [f'commit {h}', f'Parents: {p}', f'Author: {an}', f'AuthorDate: {ad}', f'Committer: {cn}',
                    f'CommitDate: {cd}', '', f'    {s}', '']
        write(ds, 'git.log', '\n'.join(log) + '\n')
        shutil.copy(os.path.join(repo, 'workflow.jsonl'), os.path.join(ds, 'workflow.jsonl'))
        write(ds, 'Brief/brief.md', '# Brief\n\n' + 'Build a small kiln game. ' * 20)
        write(ds, 'Brief/design.md', '# Design\n\n' + 'Systems, scenes and scenarios. ' * 20)
        os.makedirs(os.path.join(ds, 'History'))
        git(repo, 'bundle', 'create', os.path.join(ds, 'History', f'{SLUG}.bundle'), 'main')
        lfs_bytes = n_lfs = 0
        for d, _, fs in os.walk(os.path.join(repo, '.git', 'lfs', 'objects')):
            for f in fs:
                if re.fullmatch(r'[0-9a-f]{64}', f):
                    write(ds, f'History/lfs/objects/{f[:2]}/{f[2:4]}/{f}', read(os.path.join(d, f), 'rb'))
                    n_lfs += 1
                    lfs_bytes += os.path.getsize(os.path.join(d, f))
        tasks_src = os.path.join(self.tmp, f'tasks{self.n}')
        os.makedirs(tasks_src)
        name = f'{SLUG}-fix-hero-hud'
        write(tasks_src, f'{name}.json', git(repo, 'show', f'tasks:Tasks/{name}.json'))
        subprocess.run([sys.executable, os.path.join(TOOLS, 'split-tasks.py'), tasks_src, os.path.join(ds, 'Tasks')],
                       check=True, capture_output=True)
        write(ds, 'Tasks/README.md', '# Tasks\n')
        for f in vg.git_ls(repo):
            write(ds, 'UnityProject/' + f, read(os.path.join(repo, f), 'rb'))
        write(ds, 'Build/KilnRun.exe', b'MZ' + b'\0' * 30)
        write(ds, 'Screenshots/hero.jpg', read(os.path.join(repo, 'Docs/screenshots/hero.jpg'), 'rb'))
        sections = ['Requirements', 'Package contents', 'Play the game', 'Replay the creation process',
                    'Restore the git history', 'Tasks', 'Scenarios', 'Screenshots', 'Assets and licences', 'Integrity']
        write(ds, 'README.md', '# Kiln Run\n\nThis delivery is pending.\n\n' + ''.join(
            f'## {s}\n\n' + ('![hero](Screenshots/hero.jpg)\n\n' if s == 'Screenshots' else 'Text.\n\n') for s in sections))
        files = []
        for d, _, fs in os.walk(ds):
            for f in fs:
                rel = os.path.relpath(os.path.join(d, f), ds).replace('\\', '/')
                if rel.startswith('History/lfs/objects/'):
                    continue
                data = read(os.path.join(d, f), 'rb')
                files.append({'path': rel, 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()})
        m = {'layout': 'unity-dataset-layout/v1', 'game': SLUG, 'title': 'Kiln Run', 'version': '1.0', 'commit': head,
             'status': 'pending', 'variant': 'full', 'pending': ['ReplayScripts', 'Gameplay'], 'scenarios': [],
             'totals': {'files': len(files), 'bytes': sum(f['bytes'] for f in files)}, 'files': files,
             'replay_verification': None,
             'build': {'config': 'Release', 'commit': head, 'exe': 'Build/KilnRun.exe', 'backend': 'mono'},
             'history': {'bundle': f'History/{SLUG}.bundle', 'head': head,
                         'commits': int(git(repo, 'rev-list', '--count', 'main')), 'refs': ['refs/heads/main'],
                         'lfs_objects': n_lfs, 'lfs_bytes': lfs_bytes, 'authors_anonymised': True},
             'brief': {'brief': 'Brief/brief.md', 'design': 'Brief/design.md'},
             'tasks': {'count': 1, 'names': [name], 'schema': 'game-task/1'}}
        if mutate:
            mutate(m, ds)
        write(ds, 'manifest.json', json.dumps(m, indent=1))
        z = os.path.join(repo, 'Dataset.pending.zip')
        with zipfile.ZipFile(z, 'w', zipfile.ZIP_DEFLATED) as zf:
            for d, _, fs in os.walk(ds):
                for f in fs:
                    full = os.path.join(d, f)
                    zf.write(full, SLUG + '/' + os.path.relpath(full, ds).replace('\\', '/'))
        return z

    def test_valid_dataset(self):
        z = self.make_zip()
        rep = vg.Report()
        vg.check_dataset(rep, z, 'dataset')
        self.assertEqual(errors(rep), [])
        notes = ' '.join(m for s, a, m in rep.items)
        self.assertIn('1 task(s)', notes)
        self.assertIn('LFS objects referenced', notes)
        if shutil.which('powershell') or shutil.which('pwsh'):
            rep = vg.Report()
            vg.run_layout_validator(rep, z, False)
            self.assertEqual(errors(rep), [])
            self.assertTrue(any('PENDING' in m for s, a, m in rep.items), rep.items)

    def test_dataset_errors(self):
        def mutate(m, ds):
            m['tasks']['count'] = 2
            g = os.path.join(ds, 'Tasks', f'{SLUG}-fix-hero-hud', 'task.json')
            t = json.loads(read(g))
            t['milestones'] = []
            write(ds, os.path.relpath(g, ds).replace('\\', '/'), json.dumps(t))
            shutil.rmtree(os.path.join(ds, 'UnityProject', 'Assets', 'ThirdParty', 'Kenney'))
            m['files'] = [f for f in m['files'] if '/Kenney/' not in f['path']]
            m['totals'] = {'files': len(m['files']), 'bytes': sum(f['bytes'] for f in m['files'])}
        rep = vg.Report()
        vg.check_dataset(rep, self.make_zip(mutate), 'dataset')
        errs = ' | '.join(errors(rep))
        for what in ("holds the grader's half (milestones)", 'manifest tasks (count, names) differ'):
            self.assertIn(what, errs)
        self.assertIn('listed asset file not present: Crates: Assets/ThirdParty/Kenney/', errs)

    def test_cli_with_zip(self):
        self.make_zip()
        r = subprocess.run([sys.executable, os.path.join(TOOLS, 'validate-game.py'), self.repo, '--no-layout'],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


if __name__ == '__main__':
    unittest.main()
