"""tools/validate-game.py on throwaway Unity game repos: a valid one (with a long-thread task on its orphan tasks branch
and a full Dataset.zip) and one broken variant per rule. Fixtures are made with plain git, no Unity and no PowerShell.

    python -m unittest discover -s tools/tests -p "test_validate_game.py" -v
"""
import hashlib, importlib.util, io, json, os, re, shutil, stat, subprocess, sys, tempfile, unittest, unittest.mock, warnings
import zipfile

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
        data = t if isinstance(t, str) else json.dumps(t, indent=2)   # a string as written: a file that is no JSON
        blob = git(repo, 'hash-object', '-w', '--stdin', input=data.encode())
        entries.append(f'100644 blob {blob}\t{name}.json')
    sub = git(repo, 'mktree', input=''.join(e + '\n' for e in entries).encode())
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
    """A Unity 6000.3 game with a long thread (4 commits, 6 game files, 124 code lines, 3 systems). Returns
    (start, reference) of that thread."""
    os.makedirs(repo)
    git(repo, 'init', '-q', '-b', 'main')
    hooks = os.path.join(os.path.dirname(repo), 'nohooks')
    os.makedirs(hooks, exist_ok=True)
    for k, v in (('core.hooksPath', hooks), ('core.autocrlf', 'false'), ('commit.gpgsign', 'false'),
                 ('user.name', 'dev_1'), ('user.email', 'dev_1@example.com')):
        git(repo, 'config', k, v)
    git(repo, 'lfs', 'install', '--local', '--skip-repo')   # its filters, none of its hooks (0.4 s a commit)
    for name in ('.gitignore', '.gitattributes'):
        shutil.copy(os.path.join(TEMPLATE, name), os.path.join(repo, name))
    for rel in ('ProjectSettings/EditorSettings.asset', 'Scripts/unity.ps1', 'Docs/ThirdPartyNotices.md',
                'Packages/manifest.json', 'Assets/Editor/Steps/README.md'):
        write(repo, rel, read(os.path.join(TEMPLATE, rel)).replace('__PROJECT__', 'KilnRun'))
    meta(repo, 'Assets/Editor/Steps/README.md')
    write(repo, 'ProjectSettings/ProjectVersion.txt', 'm_EditorVersion: 6000.3.26f1\nm_EditorVersionWithRevision: 6000.3.26f1 (x)\n')
    write(repo, 'ProjectSettings/ProjectSettings.asset', YAML.format('x') + '  companyName: Kiln Run\n  productName: Kiln Run\n')
    write(repo, 'ProjectSettings/NavMeshAreas.asset', YAML.format('areas'))   # YAML: plain git, as the template keeps it
    write(repo, 'ProjectSettings/VersionControlSettings.asset', '%YAML 1.1\n%TAG !u! tag:unity3d.com,2011:\n'
          '--- !u!890905787 &1\nVersionControlSettings:\n  m_ObjectHideFlags: 0\n  m_Mode: Visible Meta Files\n'
          '  m_TrackPackagesOutsideProject: 0\n')   # as Unity 6000.3 writes it on the first open
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


BASE = {}   # the valid game, made once for the module (it takes seconds); every test works on a copy of it


def tearDownModule():
    if BASE:
        shutil.rmtree(BASE['tmp'], onerror=onerror)


@unittest.skipUnless(HAS_LFS, 'git-lfs is not installed')
class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not BASE:
            tmp = tempfile.mkdtemp(prefix='ugfv')
            base = os.path.join(tmp, 'base', SLUG)
            start, ref = make_game(base)
            set_tasks(base, {f'{SLUG}-fix-hero-hud': task(start, ref)})
            BASE.update(tmp=tmp, base=base, start=start, ref=ref)
        cls.tmp = tempfile.mkdtemp(prefix='ugfv')
        cls.base, cls.start, cls.ref = BASE['base'], BASE['start'], BASE['ref']

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
                 'ProjectSettings/TagManager.asset', 'Assets/Z.meta',
                 'Assets/Keep/.gitkeep', 'Assets/Keep.meta',          # Unity imports the folder: it has its .meta
                 'Assets/hero.cs', 'Assets/Hero.cs.meta']             # a rename in case only, the .meta left behind
        missing, orphan, metas = vg.meta_problems(files)
        self.assertEqual(missing, ['Assets/hero.cs', 'Packages/x/package.json'])
        self.assertEqual(orphan, ['Assets/Hero.cs.meta', 'Assets/Z.meta'])
        self.assertNotIn('Packages/x.meta', metas)

    def test_meta_guids(self):
        """Every .meta names a GUID of its own (a copied folder keeps its .meta files); paths with spaces and letters
        beyond ASCII; a folder that holds only a name Unity skips still needs its .meta."""
        shutil.copy(os.path.join(self.repo, 'Assets/Scripts/Kiln.cs.meta'),
                    os.path.join(self.repo, 'Assets/Scripts/Kiln Copy.cs.meta'))
        write(self.repo, 'Assets/Scripts/Kiln Copy.cs', code('KilnCopy', 5))
        asset(self.repo, 'Assets/Données/Carte été.asset', YAML.format('carte'))
        write(self.repo, 'Assets/Bad.txt', 'x\n')
        write(self.repo, 'Assets/Bad.txt.meta', 'fileFormatVersion: 2\n')
        write(self.repo, 'Assets/Lost/.gitkeep', '')
        commit(self.repo, 'Meta contents')
        errs = errors(self.check(), 'repo: .meta')
        self.assertEqual(len(errs), 3, errs)
        for what in ('Assets/Lost: no .meta tracked', 'Assets/Bad.txt.meta: no guid',
                     'Assets/Scripts/Kiln Copy.cs.meta and Assets/Scripts/Kiln.cs.meta share the guid'):
            self.assertTrue(any(e.startswith(what) for e in errs), (what, errs))


class RepoRules(Base):
    def test_banned_name(self):
        asset(self.repo, 'Assets/Data/credits.txt', 'Made with Game-Factory tools.\n')
        asset(self.repo, 'Assets/Data/paths.txt', 'Saved to C:/Users/Kilnmaker/AppData.\n')    # the machine's account
        asset(self.repo, 'Assets/Editor/Steps/BuildYard.cs', '// ran from C:/Users/Kilnmaker/Work\n')  # a step that ran
        write(self.repo, 'Dataset/README.md', 'Built with Claude.\n')                       # the packager's, skipped
        commit(self.repo, 'Credits')
        with unittest.mock.patch.dict(os.environ, {'USERNAME': 'Kilnmaker'}):
            errs = errors(self.check(), 'repo: banned names')
        self.assertTrue(any(e.startswith('Assets/Data/credits.txt') for e in errs), errs)
        self.assertIn('Assets/Data/paths.txt: the account name x1', errs)
        self.assertEqual(len(errs), 2, errs)

    def test_unity_repo_name_banned(self):
        rx = vg.SPEC['repo']['banned_names']['patterns'][1]
        self.assertTrue(re.search(rx, 'cloned unity_game_factory here'))
        self.assertFalse(re.search(rx, f'the repo unity-game-{SLUG}'))   # a game's own repo name is no tool name

    def test_wrong_editor_and_settings(self):
        write(self.repo, 'ProjectSettings/ProjectVersion.txt', 'm_EditorVersion: 2022.3.62f1\n')
        es = os.path.join(self.repo, 'ProjectSettings/EditorSettings.asset')
        text = read(es).replace('m_SerializationMode: 2', 'm_SerializationMode: 1')
        write(self.repo, 'ProjectSettings/EditorSettings.asset', text.replace('Visible Meta Files', 'Hidden Meta Files'))
        vcs = os.path.join(self.repo, 'ProjectSettings/VersionControlSettings.asset')
        write(self.repo, 'ProjectSettings/VersionControlSettings.asset', read(vcs).replace('Visible', 'Hidden'))
        commit(self.repo, 'Downgrade')
        errs = errors(self.check(), 'repo')
        self.assertTrue(any("m_EditorVersion '2022.3.62f1'" in e for e in errs), errs)
        self.assertTrue(any('m_SerializationMode' in e for e in errs), errs)
        self.assertTrue(any(e.startswith("ProjectSettings/VersionControlSettings.asset: m_Mode is 'Hidden Meta Files'")
                            for e in errs), errs)
        self.assertFalse(any('m_ExternalVersionControlSupport' in e for e in errs), errs)   # the obsolete place
        os.remove(vcs)
        commit(self.repo, 'No mode')
        self.assertTrue(any(e.startswith(r'missing ^ProjectSettings/VersionControlSettings\.asset$')
                            for e in errors(self.check(), 'repo')))

    def test_gitignore_hides_assets(self):
        with open(os.path.join(self.repo, '.gitignore'), 'a') as f:
            f.write('Build/\nAssets/ThirdParty/\n')
        commit(self.repo, 'Ignore too much')
        errs = errors(self.check(), 'repo: .gitignore')
        self.assertTrue(any(e.startswith('Assets/_probe_/Build/Probe.cs would be git-ignored') for e in errs), errs)
        self.assertTrue(any(e.startswith('Assets/ThirdParty/_probe_/Probe.fbx') for e in errs), errs)

    def test_generated_folder_tracked_and_not_ignored(self):
        write(self.repo, '.gitignore', '/Dataset.zip\n/Dataset.pending.zip\n')
        write(self.repo, 'Library/ArtifactDB', 'x')
        write(self.repo, 'KilnRun.csproj', '<Project/>\n')
        write(self.repo, 'Unity_v6000.x.ulf', 'licence\n')
        commit(self.repo, 'Oops')
        errs = errors(self.check(), 'repo')
        self.assertTrue(any('Library/ArtifactDB' in e for e in errs), errs)
        self.assertTrue(any(e.startswith('Library/ is not ignored') for e in errs), errs)
        for what in ('(e.g. KilnRun.csproj): Unity regenerates', '(e.g. Unity_v6000.x.ulf): a Unity licence file',
                     'missing /.dataset/'):
            self.assertTrue(any(what in e for e in errs), (what, errs))

    def test_lfs(self):
        attrs = os.path.join(self.repo, '.gitattributes')
        text = read(attrs).replace('*.[pP][nN][gG] filter=lfs diff=lfs merge=lfs -text', '')
        text = text.replace('Assets/**/NavMesh*.asset filter=lfs diff=lfs merge=lfs -text', '')
        write(self.repo, '.gitattributes', text + '*.prefab filter=lfs diff=lfs merge=lfs -text\n'
              'ProjectSettings/NavMeshAreas.asset filter=lfs diff=lfs merge=lfs -text\n'
              'Assets/Pack/*.asset filter=lfs diff=lfs merge=lfs -text\n')
        asset(self.repo, 'Assets/Art/plain.png', b'\x89PNG\r\n\x1a\n' + b'\2' * 64)
        asset(self.repo, 'Assets/Prefabs/Crate.prefab', YAML.format('Crate'))
        asset(self.repo, 'Assets/Scenes/Main/NavMesh.asset', b'\0\1binary navmesh')
        asset(self.repo, 'Assets/Pack/Binary.asset', b'\0\1a store pack\'s binary asset')
        asset(self.repo, 'Assets/Data/Packed.asset', b'\0\1binary, with no LFS pattern of its own')
        commit(self.repo, 'LFS mistakes')   # the copy's files are all re-added: the base's crate.png and Hero.prefab too
        self.assertIn('ProjectSettings/NavMeshAreas.asset', git(self.repo, 'lfs', 'ls-files', '--name-only'))
        errs = errors(self.check(), 'repo: LFS')
        self.assertEqual(sorted(errs), sorted(
            [f'binary tracked in plain git: {f}' for f in ('Assets/Art/plain.png', 'Assets/Scenes/Main/NavMesh.asset',
                                                          'Assets/ThirdParty/Kenney/crate.png')] +
            [f"Unity YAML or C# in LFS: {f} (it loses its diffs and merges; .gitattributes must keep it plain git text, "
             "as the template's does)" for f in ('Assets/Prefabs/Crate.prefab', 'Assets/Prefabs/Hero.prefab',
                                                 'ProjectSettings/NavMeshAreas.asset')]))   # a binary .asset in LFS is right
        self.assertIn(('warning', 'repo: LFS', 'binary content in plain git: Assets/Data/Packed.asset (give its type an '
                       'LFS pattern in .gitattributes)'), self.check().items)
        real = subprocess.run

        def no_lfs(args, **kw):   # a machine without Git LFS: git says lfs is no git command
            if 'lfs' in args:
                return subprocess.CompletedProcess(args, 1, '', "git: 'lfs' is not a git command.")
            return real(args, **kw)
        with unittest.mock.patch.object(vg.subprocess, 'run', no_lfs):
            errs = errors(self.check(), 'repo: LFS')
        self.assertEqual(len(errs), 1, errs)
        self.assertTrue(errs[0].startswith('git lfs ls-files failed, so LFS is not checked'), errs)

    def test_assets_manifest(self):
        data = json.loads(read(os.path.join(self.repo, 'assets.manifest.json')))
        data['assets'].append({'name': 'Gone', 'source': 'x', 'url': 'https://x', 'licence': 'CC0',
                               'files': ['Content/Gone/', 'Assets/Gone.fbx']})
        data['assets'] += [{'name': 'Ours', 'source': 'the studio', 'origin': 'studio', 'licence': 'own',
                            'files': ['Assets/Scripts/Kiln.cs']},     # the schema's if: studio needs a description
                           {'name': 'Theirs', 'source': 'x', 'licence': 'CC0',
                            'files': ['Assets/Scripts/Kiln.cs']}]     # else: an https url
        write(self.repo, 'assets.manifest.json', json.dumps(data))
        commit(self.repo, 'Manifest')
        errs = errors(self.check(), 'repo: assets.manifest.json')
        self.assertIn('asset path outside Assets/, Packages/ or RawAssets/: Gone: Content/Gone/', errs)
        self.assertIn('listed asset file not present: Gone: Assets/Gone.fbx', errs)
        self.assertIn('$.assets[2] (Ours): origin studio needs a "description"', errs)
        self.assertTrue(any(e.startswith('$.assets[3] (Theirs): needs an https "url"') for e in errs), errs)

    def test_workflow_rows(self):
        with open(os.path.join(self.repo, 'workflow.jsonl'), 'a') as f:
            f.write(workflow_row(2) + '\n' + workflow_row(3, schema='ue-workflow/v0') + '\n')
        commit(self.repo, 'Bad rows')
        errs = errors(self.check(), 'repo: workflow.jsonl')
        self.assertTrue(any('duplicate id kr-00002' in e for e in errs), errs)
        self.assertTrue(any('ue-workflow/v0' in e for e in errs), errs)

    def test_readme(self):
        write(self.repo, 'README.md', '# Kiln Run\n\n![hero](Docs/screenshots/hero.jpg "The kiln")\n'
              '<img src="./Docs/screenshots/gone.jpg">\n![web](https://example.com/x.png)\n<!-- ![old](old.png) -->\n')
        commit(self.repo, 'Readme')
        rep = self.check()
        self.assertEqual(errors(rep, 'repo: README'), ['links Docs/screenshots/gone.jpg, which is not committed'])
        self.assertIn(('warning', 'repo: README', '2 images; the rule is a hero + gallery of 5-7 gameplay stills'),
                      rep.items)
        write(self.repo, 'README.md', '# Kiln Run\n\nNo stills yet.\n')
        commit(self.repo, 'Readme without stills')
        self.assertEqual(errors(self.check(), 'repo: README'), ['shows no gameplay image'])
        for f in ('workflow.jsonl', 'assets.manifest.json'):   # tracked, gone from the checkout: an error, no traceback
            os.remove(os.path.join(self.repo, f))
        self.assertEqual(errors(self.check(), 'repo')[0], '2 tracked file(s) not in the working tree (e.g. '
                                                          'assets.manifest.json): check out the release commit as it is')

    def test_task_files(self):
        set_tasks(self.repo, {f'{SLUG}-a': 'not json', f'{SLUG}-b': [1],
                              f'{SLUG}-c': task(self.start, self.ref, name='other')})
        errs = errors(self.check(), 'repo: Tasks')
        for what in (f'tasks:Tasks/{SLUG}-a.json: not JSON', f'tasks:Tasks/{SLUG}-b.json: not a task object',
                     f"tasks:Tasks/{SLUG}-c.json: name 'other' differs from the file name"):
            self.assertTrue(any(e.startswith(what) for e in errs), (what, errs))
        set_tasks(self.repo, {})
        self.assertTrue(any(e.startswith('no task files in Tasks/ on tasks') for e in errors(self.check(), 'repo: Tasks')))

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
    def check(self):   # these tests change the tasks branch alone: its rules, without the rest of the repo's
        rep = vg.Report()
        vg.check_repo_tasks(rep, self.repo)
        return rep

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
             'batchmode', '-nolog', '--NoLog', '-window-mode', 'exclusive', 'nolog'])),
            ['ParentHWND', 'single-instance', 'force-vulkan', 'screen-fullscreen', 'logFile', 'PopupWindow',
             'monitor', 'quit', 'nographics', 'executeMethod', 'projectPath', 'nolog', 'NoLog', 'window-mode'])

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
        r = subprocess.run([sys.executable, os.path.join(TOOLS, 'thread-stats.py'), self.repo, self.ref, '--span',
                            f'{self.start}..{self.ref}'], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)   # counted as the validator counts: the whole thread meets the floors
        self.assertIn('span: 4 game commit(s), 6 game file(s), 124 code line(s), 3 system(s) (code, config, prefab)',
                      r.stdout)
        self.assertIn('below the floors on its own: 1 game commits (floor 4); 2 game files (floor 5)', r.stdout)

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


class Units(unittest.TestCase):
    """The validator's rules on their own, without a repo."""

    def test_thread_definitions(self):
        """The Unreal factory's eight systems in Unity terms; an editor step (the creation's record) or a .meta is no
        game file, though a step's lines are code lines."""
        for path, system in (('Assets/Scripts/Hero.cs', 'code'), ('Assets/Editor/HeroInspector.cs', 'code'),
                             ('Assets/Game.asmdef', 'code'), ('ProjectSettings/TagManager.asset', 'config'),
                             ('Packages/manifest.json', 'config'), ('Packages/packages-lock.json', 'config'),
                             ('Packages/com.kiln.tools/Runtime/Tool.cs', 'package'), ('Assets/Scenes/Yard.unity', 'scene'),
                             ('Assets/Materials/M_Bulb.mat', 'material'), ('Assets/Shaders/Glow.shader', 'material'),
                             ('Assets/Shaders/Glow.hlsl', 'material'), ('Assets/Art/Crate.PNG', 'material'),
                             ('Assets/Prefabs/Hero.prefab', 'prefab'), ('Assets/UI/Hud.uxml', 'prefab'),
                             ('Assets/Anim/Hero.controller', 'prefab'), ('Assets/Data/Coins.asset', 'data'),
                             ('Assets/Data/waves.csv', 'data'), ('Assets/Audio/hit.wav', 'asset'),
                             ('Assets/Anim/Run.anim', 'asset'), ('Assets/Models/Crate.fbx', 'asset')):
            self.assertEqual(vg.thread_system(path), system, path)
        for path in ('Assets/Editor/Steps/BuildYard.cs', 'Assets/Scripts/Hero.cs.meta', 'Assets/Scenes.meta',
                     'workflow.jsonl', 'Docs/Design.md', 'Scripts/unity.ps1'):
            self.assertIsNone(vg.GAME_FILE.search(path), path)
        numstat = ('40\t0\tAssets/Editor/Steps/BuildYard.cs\n2\t0\tAssets/Editor/Steps/BuildYard.cs.meta\n'
                   '9\t3\tAssets/Scenes/Yard.unity\n-\t-\tAssets/Art/crate.png\n30\t0\tAssets/ThirdParty/Pack/P.cs\n'
                   '25\t5\tAssets/Scripts/Hero.cs\n')
        self.assertEqual(vg.thread_size(numstat), (40 + 25 + 5, 3))   # code, scene, material

    def test_game_paths(self):
        """The git pathspecs that count a thread's game files and commits (GAME_PATHS) name exactly the files GAME_FILE
        matches, which the systems and thread-stats.py count: no editor step, no .meta, any name."""
        tmp = tempfile.mkdtemp(prefix='ugfp')
        self.addCleanup(shutil.rmtree, tmp, onerror=onerror)
        git(tmp, 'init', '-q')
        paths = ['Assets/Scripts/Hero.cs', 'Assets/Scripts/Hero.cs.meta', 'Assets/Editor/Steps/BuildYard.cs',
                 'Assets/Editor/Steps.meta', 'Assets/Editor/StepsOld/Keep.cs', 'Assets/Editor/HeroInspector.cs',
                 'Assets/Données/Carte été.asset', 'Assets/Store Pack/Sky Box.png', 'Packages/manifest.json',
                 'Packages/com.kiln.tools/Runtime/Tool.cs', 'Packages/com.kiln.tools/Runtime/Tool.cs.meta',
                 'ProjectSettings/TagManager.asset', 'Scripts/unity.ps1', 'Docs/Design.md', 'RawAssets/Hero.blend',
                 'workflow.jsonl']
        blob = git(tmp, 'hash-object', '-w', '--stdin', input=b'')
        git(tmp, 'update-index', '-z', '--index-info', input=''.join(f'100644 {blob}\t{p}\0' for p in paths).encode())
        listed = git(tmp, '-c', 'core.quotepath=off', 'ls-files', '-z', '--', *vg.GAME_PATHS).split('\0')
        self.assertEqual(sorted(p for p in listed if p), sorted(p for p in paths if vg.GAME_FILE.search(p)))

    def test_what_a_run_would_refuse(self):
        """What the probe or the checker refuses at run time (or stops on) is refused when the task is written."""
        def errs(measure, play='look', expect=None):
            c = {'name': 'p', 'kind': 'probe', 'describe': 'x', 'play': play, 'measure': measure,
                 'expect': expect or {'op': '>=', 'calibrate': 0.5}}
            return ' | '.join(vg.task_semantic_errors(task('a' * 40, 'b' * 40, milestones=[{'name': 'm', 'checks': [c]}])))
        scene = {'probe': 'asset', 'scene': 'Assets/Scenes/Main.unity', 'field': 'count'}
        for select in ({'player': True}, {'near': {'point': {'player': True}, 'radius': 2}},
                       {'near': {'point': {'object': {'near': {'point': {'camera': True, 'forward': 2}, 'radius': 1}}},
                                 'radius': 2}}):
            self.assertIn('a scene as saved has no player or camera', errs(dict(scene, select=select), 'editor'), select)
        self.assertEqual(errs(dict(scene, select={'near': {'point': {'xyz': [0, 0, 0]}, 'radius': 2}}), 'editor'), '')
        self.assertIn('a screen rect is [x0, y0, x1, y1] with x0 < x1 and y0 < y1',
                      errs({'probe': 'screen', 'rect': [0.75, 0.25, 0.25, 0.75], 'field': 'luminance'}))
        dist = {'probe': 'player', 'field': 'dist', 'agg': 'min'}
        self.assertIn("a player measure's dist is the distance to its `to` point, which it lacks", errs(dist))
        self.assertEqual(errs(dict(dist, to={'xyz': [0, 0, 0]})), '')
        self.assertIn('`to_angle` or `to_axis`, not both',
                      errs({'probe': 'camera', 'field': 'yaw', 'to_angle': 90, 'to_axis': 0}, expect={'op': '<=', 'value': 5}))
        height = {'probe': 'player', 'field': 'y', 'window': [0, 1], 'at': [5.0]}
        self.assertIn('`window` or `at`, not both', errs(height, expect={'op': '>=', 'value': 0}))
        self.assertEqual(errs(dict(height, at=None), expect={'op': '>=', 'value': 0}), '')
        literal = {'op': '>=', 'value': 1}
        for measure in ({'probe': 'log', 'pattern': '([unclosed'}, {'probe': 'widgets', 'select': {'text': '[a'}},
                        {'probe': 'objects', 'select': {'name': 'Hud'}, 'field': 'prop:Hud.label', 'match': '(', 'of': 'first'}):
            self.assertIn("isn't a regular expression", errs(measure, expect=literal), measure)
        for player in ({'player': True}, {'tag': 'Hero', 'near': {'point': {'player': True}, 'radius': 2}}):
            self.assertIn('player: this select says which object the player is',
                          ' '.join(vg.task_semantic_errors(task('a' * 40, 'b' * 40, player=player))), player)
        self.assertEqual(vg.task_semantic_errors(task('a' * 40, 'b' * 40, player={
            'tag': 'Hero', 'near': {'point': {'camera': True, 'forward': 2}, 'radius': 9}})), [])
        absent = {'name': 'clean', 'kind': 'log_absent', 'pattern': 'Exception('}
        self.assertIn("'Exception(' isn't a regular expression",
                      ' '.join(vg.task_semantic_errors(task('a' * 40, 'b' * 40, milestones=[{'name': 'm', 'checks': [absent]}]))))

    def test_task_rules(self):
        """The rules beyond the schema the other tests leave out: task plays, the ui, drawn, ground, asset and pieces
        measures' own rules, a threshold from the start, a start that doesn't build, judges, check names and needs, and
        a task without a required probe."""
        def errs(*checks, **over):
            t = task('a' * 40, 'b' * 40, milestones=[{'name': 'm', 'checks': list(checks)}], **over)
            return ' | '.join(vg.task_semantic_errors(t))

        def probe(measure, play='look', expect=None, name='p'):
            return {'name': name, 'kind': 'probe', 'describe': 'x', 'play': play, 'measure': measure,
                    'expect': expect or {'op': '>=', 'value': 1}}
        x, near = {'probe': 'player', 'field': 'x'}, {'point': {'xyz': [0, 0, 0]}, 'radius': 1}
        key, wait = {'t': 5, 'key': '<Keyboard>/w', 'press': True}, {'t': 1, 'wait': 200}
        line = {'from': {'xyz': [0, 0, 0]}, 'to': {'xyz': [0, 0, 5]}, 'radius': 0.5}
        for check, said in (
                (probe(x, {'name': 'drive', 'seconds': 10}), "check p: a task play can't be named drive"),
                (probe(x, {'name': 'fire', 'seconds': 5, 'inputs': [key]}),
                 'check p: play fire has an input at or after its end (5 s)'),
                (probe(x, {'name': 'fire', 'seconds': 60, 'inputs': [wait, dict(wait, t=2)]}),
                 'check p: play fire waits 400 s in all, more than 300 s'),
                (probe({'probe': 'ui', 'field': 'count', 'select': {'rect': [0.5, 0, 0.2, 1]}}),
                 'check p: a ui select rect is [x0, y0, x1, y1] with x0 < x1 and y0 < y1'),
                (probe({'probe': 'ui', 'field': 'count', 'select': {'kind': 'box', 'text': 'x'}}),
                 "check p: a ui select's `text` picks text elements"),
                (probe({'probe': 'drawn', 'field': 'drawn'}), 'check p: a drawn measure takes `near` (a point) or a `line`'),
                (probe({'probe': 'drawn', 'field': 'reach', 'near': near}), 'check p: a drawn measure near a point reads'),
                (probe({'probe': 'drawn', 'field': 'drawn', 'line': line, 'near': near}), 'one of them'),
                (probe({'probe': 'drawn', 'field': 'motion', 'line': line}), 'check p: a drawn measure along a line reads'),
                (probe({'probe': 'ground', 'field': 'hits', 'xz': [0, 0]}), 'check p: a ground measure at a point reads'),
                (probe({'probe': 'ground', 'field': 'hit', 'box': [0, 0, 1, 1]}), 'check p: a ground measure over a box'),
                (probe({'probe': 'ground', 'field': 'hits', 'box': [10, 0, 0, 10]}),
                 'check p: a ground box is [x0, z0, x1, z1] with x0 < x1 and z0 < z1'),
                (probe({'probe': 'asset', 'scene': 'Assets/Scenes/Main.unity', 'field': 'import:x'}, 'editor'),
                 "check p: a scene's objects are read with count"),
                (probe({'probe': 'pieces', 'select': {}, 'field': 'triangles'}),
                 'check p: how many triangles a fair build draws depends on the meshes it chose'),
                (probe(x, expect={'op': '>=', 'start_plus': 1}), 'check p sets its threshold from the start')):
            self.assertIn(said, errs(check, seed=None) if 'from the start' in said else errs(check), said)
        rubric = [{'key': 'k', 'criterion': 'c'}]
        broken = {'name': 'b', 'kind': 'build', 'fails_at_start': True}
        before = {'name': 'j', 'kind': 'judge', 'question': 'q', 'rubric': rubric, 'before': True}
        said = errs(broken, probe(x, expect={'op': '>=', 'start_plus': 1}), before)
        self.assertIn("check p: its threshold is relative to the start (start_plus), but the start doesn't build "
                      '(b: fails_at_start)', said)
        self.assertIn("check j compares with the start (before: true), but the start doesn't build", said)
        said = errs({'name': 'c', 'kind': 'code_judge', 'question': 'q', 'rubric': rubric}, before,
                    dict(before, name='r', before=False, reference=True), seed=None)
        for what in ('check c: a code judge needs seed.reference', 'check j: a before/after judge needs a seed',
                     'check r: a reference judge needs seed.reference'):
            self.assertIn(what, said)
        said = errs(probe(x), probe(x), dict(broken, name='q', needs=['p', 'z']))
        self.assertIn('check p is named twice', said)
        self.assertIn("check q needs ['z'], which come later or do not exist", said)
        t = task('a' * 40, 'b' * 40)
        for c in (c for m in t['milestones'] for c in m['checks'] if c['kind'] == 'probe'):
            c['required'] = False
        rep = vg.Report()
        vg.check_task(rep, 'repo: Tasks', 'x', t, SLUG, None)
        self.assertIn('x: no required probe check: pass/fail must be deterministic (unity-write-tasks section 5)',
                      errors(rep))

    def test_schema_keywords(self):
        """Every keyword the schemas use is one check_schema reads, an annotation, or the if/then/else that
        check_assets_manifest evaluates by hand (a keyword it ignored would be a rule never checked); each works."""
        read = {'type', 'required', 'properties', 'additionalProperties', 'minProperties', 'enum', 'const', 'pattern',
                'minLength', 'maxLength', 'minimum', 'maximum', 'exclusiveMinimum', 'exclusiveMaximum', 'items',
                'minItems', 'maxItems', '$ref', 'allOf', 'anyOf', 'oneOf', 'discriminator'}
        notes = {'$schema', '$id', '$defs', '$comment', 'title', 'description', 'default', 'propertyName', 'mapping'}
        used = set()

        def walk(node, names=False):
            if isinstance(node, dict):
                for k, v in node.items():
                    used.update(() if names else (k,))
                    walk(v, not names and k in ('properties', '$defs', 'mapping'))
            elif isinstance(node, list):
                for v in node:
                    walk(v)
        for s in vg.SCHEMAS.values():
            walk(s)
        self.assertEqual(used - read - notes - {'if', 'then', 'else'}, set())
        patterns = []

        def collect(node):
            if isinstance(node, dict):
                patterns.extend(v for k, v in node.items() if k == 'pattern' and isinstance(v, str))
                for v in node.values():
                    collect(v)
            elif isinstance(node, list):
                for v in node:
                    collect(v)
        for s in vg.SCHEMAS.values():
            collect(s)
        for p in patterns:   # what _ecma relies on: a pattern's `$` is its last character, never escaped
            self.assertTrue('$' not in p[:-1] and not p.endswith('\\$'), p)
        self.assertNotEqual(list(vg.check_schema(['-scenario\n'], vg.SCHEMAS['game-task']['properties']['play_args'],
                                                 vg.SCHEMAS['game-task'])), [])
        either = [{'type': 'string'}, {'type': 'integer'}]
        for schema, good, bad in (
                ({'type': 'integer'}, 3, True), ({'type': ['string', 'null']}, None, 3), ({'required': ['a']}, {'a': 1}, {}),
                ({'properties': {'a': {'type': 'string'}}}, {'a': 'x'}, {'a': 1}),
                ({'properties': {'a': {}}, 'additionalProperties': False}, {'a': 1}, {'b': 1}),
                ({'minProperties': 1}, {'a': 1}, {}), ({'enum': ['a', 1]}, 1, True), ({'const': True}, True, 1),
                ({'pattern': '^a+$'}, 'aa', 'ab'), ({'pattern': '^a+$'}, 'aa', 'aa\n'),   # $ ends the string
                ({'pattern': '^\\d$'}, '7', '٧'),                                  # \d is 0-9, as in ECMA-262
                ({'minLength': 1}, 'a', ''), ({'maxLength': 1}, 'a', 'ab'),
                ({'minimum': 0}, 0, -1), ({'maximum': 1}, 1, 2), ({'exclusiveMinimum': 0}, 0.5, 0),
                ({'exclusiveMaximum': 1}, 0.5, 1), ({'items': {'type': 'string'}}, ['a'], ['a', 1]),
                ({'minItems': 1}, [1], []), ({'maxItems': 1}, [1], [1, 2]),
                ({'$defs': {'S': {'type': 'string'}}, '$ref': '#/$defs/S'}, 'a', 1),
                ({'allOf': [{'minimum': 0}, {'maximum': 1}]}, 0.5, 2), ({'anyOf': either}, 'a', None),
                ({'oneOf': [{'minimum': 0}, {'maximum': 1}]}, 5, 0.5),   # 0.5 fits both
                ({'oneOf': either + [{'type': 'number'}], 'discriminator': {'propertyName': 'k'}}, 2, None)):
            self.assertEqual(list(vg.check_schema(good, schema)), [], (schema, good))
            self.assertNotEqual(list(vg.check_schema(bad, schema)), [], (schema, bad))

    def test_workflow_rows_unit(self):
        """workflow.jsonl beyond one row: JSON, seq order, user.direction rows and the links to them, an empty reason
        (a warning), no rows."""
        lines = [workflow_row(1), 'not json', workflow_row(3, seq=1),
                 workflow_row(4, op='user.direction', actor='user', reason_source='user_direction', params={'via': 'x'}),
                 workflow_row(5, direction='kr-00009'), workflow_row(6, reason=' ')]
        rep = vg.Report()
        self.assertEqual(vg.check_workflow(rep, 'w', lines), {'kr-00004'})
        errs = ' | '.join(errors(rep))
        for what in ('line 2: not JSON', 'line 3: seq 1 not after 1', 'line 4: user.direction row needs actor user',
                     'line 5: direction kr-00009 is not an earlier user.direction row'):
            self.assertIn(what, errs)
        self.assertIn(('warning', 'w', '1 row(s) with an empty reason'), rep.items)
        rep = vg.Report()
        vg.check_workflow(rep, 'w', [])
        self.assertEqual(errors(rep), ['no rows'])

    def test_git_log_unit(self):
        """git.log's form: its first line, commit lines, the fields in order, dev_NN authors, ISO dates, each commit
        once, its last commit returned."""
        a, b = 'a' * 40, 'b' * 40

        def entry(sha, author='dev_1', date='2026-11-01T10:00:00+01:00'):
            return [f'commit {sha}', 'Parents: ', f'Author: {author}', f'AuthorDate: {date}', 'Committer: dev_1',
                    'CommitDate: 2026-11-01T10:00:00Z', '', '    A message', '']
        rep = vg.Report()
        self.assertEqual(vg.check_git_log(rep, 'g', io.StringIO('\n'.join(['GIT-LOG 1', '# a header'] + entry(a)))), a)
        self.assertEqual(errors(rep), [])
        bad = ['GIT-LOG 2', 'commit xyz'] + entry(b, 'Jane Doe', 'yesterday') + [f'commit {a}', 'Parents: ', 'Commit: x']
        rep = vg.Report()
        vg.check_git_log(rep, 'g', io.StringIO('\n'.join(bad + entry(b))))
        errs = ' | '.join(errors(rep))
        for what in ('first line must be "GIT-LOG 1"', "bad commit line 'commit xyz'", 'Author "Jane Doe" is not anonymised',
                     'AuthorDate "yesterday" is not ISO 8601', 'expected "Author:" after commit aaaaaaaa',
                     'a commit appears twice'):
            self.assertIn(what, errs)
        rep = vg.Report()
        vg.check_git_log(rep, 'g', io.StringIO('GIT-LOG 1\n'))
        self.assertEqual(errors(rep), ['no commits'])

    def test_dataset_rules_unit(self):
        """A repo Dataset/ folder's cross-file rules, and a zip's one top folder (no git needed)."""
        tmp = tempfile.mkdtemp(prefix='ugfd')
        self.addCleanup(shutil.rmtree, tmp, onerror=onerror)
        ds = os.path.join(tmp, 'Dataset')
        # a line separator inside a string, raw as JSON allows it: one row, as the repo's check reads it
        write(ds, 'workflow.jsonl', workflow_row(1, reason='Create the project').replace('\\u2028', ' ') + '\n')
        write(ds, 'Brief/brief.md', '# Brief\n')
        write(ds, 'History/x.txt', 'x')
        write(ds, 'Tasks/README.md', 'x')
        scenario = {'file': f'Gameplay/{SLUG}_S1.mp4', 'scenario': 1, 'name': 'Rush', 'result': 'win', 'seconds': 30}

        def check(**over):
            m = {'layout': 'unity-dataset-layout/v1', 'game': SLUG, 'title': 'Kiln Run', 'version': '1.0',
                 'commit': 'a' * 40, 'status': 'pending', 'variant': 'repo-dataset', 'pending': ['Gameplay'],
                 'scenarios': [scenario], 'totals': {'files': 5, 'bytes': 0},
                 'files': [{'path': 'workflow.jsonl', 'bytes': 1, 'sha256': '0' * 64},
                           {'path': 'Gone.txt', 'bytes': 1, 'sha256': '0' * 64}],
                 'replay_verification': None, 'build': {'config': 'Release', 'commit': 'a' * 40, 'exe': 'Build/K.exe'},
                 'history': None, 'brief': {'brief': 'Brief/brief.md', 'design': 'Brief/design.md'}, 'tasks': None}
            write(ds, 'manifest.json', json.dumps(dict(m, **over)))
            rep = vg.Report()
            vg.check_dataset(rep, ds, 'dataset')
            return rep, ' | '.join(errors(rep))
        rep, errs = check()
        for what in ('files[] lists Gone.txt, not in the dataset', 'workflow.jsonl: ', 'totals do not match files[]',
                     f'scenario file Gameplay/{SLUG}_S1.mp4 not in files[]', 'variant repo-dataset has build null',
                     'replay_verification is null but ReplayScripts/ is not listed as pending', 'no git.log',
                     'no Brief/design.md', 'Brief/brief.md is nearly empty', 'a repo Dataset/ has no History/',
                     'a repo Dataset/ has no Tasks/'):
            self.assertIn(what, errs)
        self.assertNotIn('not JSON', errs)
        warns = ' | '.join(m for s, a, m in rep.items if s == 'warning')
        self.assertIn('status pending: Gameplay', warns)
        self.assertIn('no user.direction rows', warns)
        rep, errs = check(status='complete', pending=['ReplayScripts'], scenarios=[])
        for what in ('status complete but no ReplayScripts/Verification/report.json', 'status complete with pending entries',
                     'status complete needs replay_verification with pass true or false', 'no scenario videos'):
            self.assertIn(what, errs)
        for cut in ('ReplayScripts/Verification/report.json', 'UnityProject/assets.manifest.json'):
            write(ds, cut, '{"schema": ')   # cut short: an error, never a traceback
        rep, errs = check(variant='full')
        self.assertEqual([a for s, a, m in rep.items if m.startswith('not JSON: ')],
                         ['dataset: report.json', 'dataset: UnityProject/assets.manifest.json'])
        write(ds, 'manifest.json', 'not json')
        rep = vg.Report()
        vg.check_dataset(rep, ds, 'dataset')
        self.assertTrue(errors(rep)[0].startswith('manifest.json is not JSON'), rep.items)
        z = os.path.join(tmp, 'two.zip')
        with zipfile.ZipFile(z, 'w') as zf:
            zf.writestr('a/manifest.json', '{}')
            zf.writestr('b/x.txt', 'x')
        rep = vg.Report()
        vg.check_dataset(rep, z, 'dataset')
        self.assertEqual(errors(rep), ['the zip must hold exactly one top folder (<game>/)'])

    def test_split_tasks(self):
        """split-tasks.py: the agent's half (everything but milestones, the seed without its reference: play_scene,
        play_args and player included) and the grader's half (milestones, seed.reference), which merge back into the
        task; exit 2 for a file that isn't JSON or whose name isn't its file's."""
        tmp = tempfile.mkdtemp(prefix='ugfs')
        self.addCleanup(shutil.rmtree, tmp, onerror=onerror)
        t = task('a' * 40, 'b' * 40)
        write(tmp, f'in/{t["name"]}.json', json.dumps(t))
        write(tmp, 'in/broken.json', '{')
        write(tmp, 'in/other.json', json.dumps(dict(t, name='renamed')))
        r = subprocess.run([sys.executable, os.path.join(TOOLS, 'split-tasks.py'), os.path.join(tmp, 'in'),
                            os.path.join(tmp, 'out')], capture_output=True, text=True)
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertEqual(json.loads(r.stdout), [{'name': t['name'], 'title': t['title'], 'kind': 'bug_fix',
                                                 'difficulty': 'hard'}])
        agent = json.loads(read(os.path.join(tmp, 'out', t['name'], 'task.json')))
        grader = json.loads(read(os.path.join(tmp, 'out', t['name'], 'grader.json')))
        self.assertEqual(sorted(agent), sorted(k for k in t if k != 'milestones'))
        self.assertNotIn('reference', agent['seed'])
        self.assertEqual(grader, {'name': t['name'], 'seed': {'reference': 'b' * 40}, 'milestones': t['milestones']})
        self.assertEqual(dict(agent, milestones=grader['milestones'], seed=dict(agent['seed'], **grader['seed'])), t)

    def test_files_closed(self):
        """Every file the validator reads is closed once read (an open one is a ResourceWarning, which the task try's
        tests make an error): the format files it loads at import, and a repo's assets.manifest.json."""
        tmp = tempfile.mkdtemp(prefix='ugfr')
        self.addCleanup(shutil.rmtree, tmp, onerror=onerror)
        git(tmp, 'init', '-q')
        write(tmp, 'assets.manifest.json', json.dumps({'schema': 'assets-manifest/v1', 'project': 'KilnRun', 'assets': []}))
        git(tmp, 'add', 'assets.manifest.json')
        with warnings.catch_warnings(record=True) as seen:
            warnings.simplefilter('always', ResourceWarning)
            again = load('validate_game_again', 'validate-game.py')
            again.check_repo(again.Report(), tmp)
        self.assertEqual([str(w.message) for w in seen if issubclass(w.category, ResourceWarning)], [])

    def test_cli_any_name(self):
        """The findings print whatever the console's code page: a name it lacks (Ω, not in cp1252) is printed, and the
        verdict is the exit code, never a traceback."""
        tmp = tempfile.mkdtemp(prefix='ugfc')
        self.addCleanup(shutil.rmtree, tmp, onerror=onerror)
        repo = os.path.join(tmp, SLUG)
        os.makedirs(repo)
        git(repo, 'init', '-q', '-b', 'main')
        for k, v in (('core.hooksPath', os.path.join(tmp, 'nohooks')), ('commit.gpgsign', 'false')):
            git(repo, 'config', k, v)
        write(repo, 'Assets/Ω.txt', 'x\n')
        commit(repo, 'A file without its .meta')
        r = subprocess.run([sys.executable, os.path.join(TOOLS, 'validate-game.py'), repo, '--quiet'], capture_output=True,
                           env=dict(os.environ, PYTHONIOENCODING='cp1252'))
        self.assertEqual(r.returncode, 2, r.stderr.decode('utf-8', 'replace'))
        self.assertIn('Assets/Ω.txt: no .meta tracked', r.stdout.decode('utf-8'))

    def test_wildcard_takes_one(self):
        """A select that takes one object by a wildcard name alone is a warning, never an error (the sample game's
        grab_coin teleported to CoinSpawner); one narrowed by its component, tag or full name is not."""
        def report(teleport, point, first):
            t = task('a' * 40, 'b' * 40)
            checks = t['milestones'][2]['checks']
            checks[0]['measure'] = {'probe': 'player', 'field': 'dist', 'to': {'object': point}, 'agg': 'min'}
            checks[1]['play']['inputs'].append({'t': 9, 'teleport_to': teleport, 'distance': 0.3, 'hold': 0.5})
            checks[2]['measure'] = {'probe': 'objects', 'select': first, 'field': 'glow', 'of': 'first'}
            rep = vg.Report()
            vg.check_task(rep, 'repo: Tasks', 'x', t, SLUG, None)
            self.assertEqual(errors(rep), [])
            return [m for s, a, m in rep.items if s == 'warning']
        ws = report({'name': 'Coin*'}, {'name': 'Lamp*'}, {'name': 'Coin?'})
        self.assertEqual(len(ws), 3, ws)
        for start in ('x: play collect: teleport_to {"name": "Coin*"} goes to the nearest object whose name fits',
                      'x: check hero_on_ground: the point {"object": {"name": "Lamp*"}} stands at the first',
                      'x: check enemies_glow: the select {"name": "Coin?"} reads the first'):
            self.assertTrue(any(w.startswith(start) for w in ws), (start, ws))
        self.assertEqual(report({'name': 'Coin*', 'component': 'Coin'}, {'name': 'Lamp_1'},
                                {'name': 'Coin*', 'tag': 'Coin'}), [])
        for key, value in (('effect', True), ('owner', {'tag': 'Yard'}), ('mesh', 'Rock_LOD0'), ('text', '^SCORE')):
            self.assertFalse(vg.wild({'name': 'Smoke*', key: value}), key)   # a components or widgets select's own keys
        t = task('a' * 40, 'b' * 40)
        t['milestones'][2]['checks'][2]['measure'] = {'probe': 'components', 'select': {'name': 'Smoke*', 'effect': True},
                                                      'field': 'active', 'of': 'first'}
        self.assertEqual(vg.task_warnings(t), [])

    def test_schema_first(self):
        """A task the schema refuses gets the schema's errors, never a traceback from the rules that read its values."""
        t = task('a' * 40, 'b' * 40)
        t['milestones'][2]['checks'][0]['weight'] = '3'
        t['milestones'][2]['checks'][1]['measure']['select']['rect'] = ['a', 0, 1, 1]
        t['milestones'][3]['checks'][0]['name'] = ['hero_moves']
        rep = vg.Report()
        self.assertFalse(vg.check_task(rep, 'repo: Tasks', 'x', t, SLUG, None))
        self.assertTrue(errors(rep), rep.items)
        rep = vg.Report()
        self.assertTrue(vg.check_task(rep, 'repo: Tasks', 'x', task('a' * 40, 'b' * 40), SLUG, None))
        self.assertEqual(errors(rep), [])


# ---- the schema against the contract's examples ----------------------------------------------------------------------
def probe_check(measure, play='look', expect=None):
    return {'name': 'p', 'kind': 'probe', 'describe': 'x', 'play': play, 'measure': measure,
            'expect': expect or {'op': '>=', 'calibrate': 0.5}}


class Schema(unittest.TestCase):
    S = vg.SCHEMAS['game-task']
    KINDS = ('player', 'objects', 'components', 'widgets', 'camera', 'light', 'grading', 'spawns', 'log', 'asset',
             'trace', 'pieces', 'screen', 'audio', 'ground', 'ui', 'drawn')   # the probe kinds (contract section 2)
    MEASURE = {kind: ref.split('/')[-1]
               for kind, ref in S['$defs']['Probe']['properties']['measure']['discriminator']['mapping'].items()}
    SHAPE = {kind: ref.split('/')[-1]   # the check kinds' definitions
             for kind, ref in S['$defs']['Milestone']['properties']['checks']['items']['discriminator']['mapping'].items()}
    RUBRIC = [{'key': 'k', 'criterion': 'x'}]
    # a valid check of each kind, given its name and kind where it is used
    CHECKS = {'build': {}, 'boot': {'seconds': 60}, 'package': {}, 'log_absent': {'pattern': 'Error'},
              'file_exists': {'glob': '*.cs'}, 'judge': {'question': 'q', 'rubric': RUBRIC},
              'code_judge': {'question': 'q', 'rubric': RUBRIC}, 'actions_judge': {'question': 'q', 'rubric': RUBRIC},
              'probe': probe_check({'probe': 'log', 'pattern': 'Error'})}
    # every character a play argument (one at its 60) and a scene's path may hold (contract section 2)
    ARGS = ['-Level=Yard_2', '--seed:7,8', '-config/night.cfg', 'X', 'x' * 60]
    SCENE = 'Assets/Scenes/Town_2-b.Night (1).unity'

    def ok(self, value, ref):
        return list(vg.check_schema(value, self.S['$defs'][ref], self.S))

    def test_contract_fields(self):
        """Every measure field the contract (section 3) lists, with its prefixed forms, and nothing Unreal: each kind's
        good fields in a whole probe check, its bad ones against its field alone (so each fails for itself)."""
        good = {
            'player': ['x', 'y', 'z', 'speed', 'moved', 'dist'],
            'camera': ['distance', 'height', 'pitch', 'yaw', 'fov', 'occluded', 'player_on_screen'],
            'objects': ['count', 'x', 'y', 'z', 'yaw', 'pitch', 'roll', 'scale', 'extent_x', 'extent_y', 'extent_z',
                        'active', 'hidden', 'collision', 'speed', 'spin', 'simulating', 'spread', 'changed',
                        'bounds_change', 'pose_change', 'lit', 'glow', 'prop:Health.current', 'prop:Inventory.items[2].count',
                        'prop:name', 'bone:Animator.LeftHand.y', 'rel_yaw:Turret', 'world_yaw:Head',
                        'world_pitch:Head', 'world_roll:Head', 'forward:Spot.z', 'facing_vs_velocity', 'anim:Speed',
                        'clip',
                        # names as Unity has them: Mixamo's, a duplicate's, Blender's (contract section 2)
                        'bone:SkinnedMeshRenderer.mixamorig:Hips.y', 'rel_yaw:Lamp (1)', 'bone:Animator.hand.L.x',
                        'forward:Cube.001.z', 'world_roll:upper_arm.R', 'anim:Is Grounded'],
            'components': ['count', 'active', 'visible', 'x', 'y', 'z', 'speed', 'spin', 'extent_x', 'extent_y',
                           'extent_z', 'simulating', 'changed', 'bounds_change', 'pose_change', 'lit', 'glow',
                           'intensity', 'on', 'prop:range', 'prop:colors[0].r'],
            'widgets': ['count', 'visible', 'text', 'percent', 'value', 'interactable', 'has_brush', 'brush', 'x',
                        'y', 'w', 'h'],
            'ui': ['count', 'text', 'x', 'y', 'w', 'h', 'signature', 'number', 'clock'],
            'screen': ['luminance', 'luma'], 'light': ['illuminance', 'exposure', 'brightness'],
            'grading': ['grey', 'cast', 'warmth', 'tint', 'saturation', 'contrast', 'post:Bloom.intensity',
                        'post:Vignette.intensity', 'post:ColorAdjustments.postExposure',
                        # a colour's or vector's channel, one more part (GradingQuery.Post)
                        'post:Vignette.color.r', 'post:LiftGammaGain.lift.w', 'post:Vignette.center.x'],
            'pieces': ['count', 'visible', 'components', 'objects', 'triangles', 'visible_triangles'],
            'audio': ['count', 'audible', 'volume', 'max_volume', 'level'],
            'ground': ['height', 'hit', 'min', 'max', 'mean', 'range', 'hits'],
            'drawn': ['drawn', 'motion', 'base_r', 'base_g', 'base_b', 'base_change', 'reach', 'length'],
            # the editor pass reads a colour's or vector's channel by either name (.r-.a, .x-.w), a texture's name, the
            # shader's name and, per material slot, a keyword (TaskProbe/Editor/AssetValues.cs MaterialValue)
            'asset': ['prop:m_Shader', 'import:maxTextureSize', 'import:m_PlatformSettings.Array.data[0].maxTextureSize',
                      'shader:_BaseColor.r', 'shader:_BaseColor.x', 'shader:_Offset.w', 'shader:_Smoothness',
                      'shader:_BaseMap', 'shader:_BaseMap.name', 'shader:name', 'keyword:_EMISSION', 'count',
                      'material_default', 'material:_BaseColor', 'material:_BaseColor.g', 'material:_BaseMap.name',
                      'material:shader', 'material:keyword:_EMISSION', 'mesh_collision',
                      'prop:MeshRenderer.receiveShadows'],
            'spawns': ['spawned', 'destroyed'], 'log': ['count'],
            'trace': ['built_after_last_change', 'played_after_last_change', 'read_before_first_edit',
                      'build_ok_at_end', 'edits_outside_project']}
        # the original's names, another kind's fields, a value's other keys, and prefixes without their name
        bad = {'player': ['pawn_on_screen', 'yaw'], 'camera': ['pawn_on_screen', 'roll'],
               'objects': ['bb:Speed', 'actors', 'prop:', 'bone:Hand.x', 'forward:Spot', 'clip:Run', 'world_yaw:.L'],
               'components': ['prop:', 'hidden', 'clip', 'anim:Speed'], 'widgets': ['slate', 'enabled'],
               'ui': ['kind', 'source'], 'screen': ['brightness'], 'light': ['lux', 'local'],
               'grading': ['post:BloomIntensity', 'post:Bloom', 'white_temp', 'post:Vignette.color.rgb',
                           'post:Vignette.color.r.g', 'post:Vignette.color.linear'],
               'pieces': ['actors', 'instances'],
               'audio': ['loudest', 'peak'], 'ground': ['points', 'z'], 'drawn': ['pixels', 'primitives'],
               'asset': ['shader:_BaseColor.q', 'shader:_BaseColor.rgb', 'material:_BaseMap.name.r', 'keyword:',
                         'import:', 'material:'],
               'spawns': ['count'], 'log': ['lines'], 'trace': ['built']}
        # every prefix that names a Part, bone or parameter takes every character the contract lists, up to 64; a
        # channel goes by either spelling wherever one is read
        for form in ('rel_yaw:{}', 'world_yaw:{}', 'world_pitch:{}', 'world_roll:{}', 'anim:{}', 'forward:{}.x',
                     'bone:Rig_2.{}.y'):
            good['objects'] += [form.format(n) for n in ('mixamorig:Upper_Arm.L (1)-2', '_Hips', '2' + 'a' * 63)]
            bad['objects'].append(form.format('2' + 'a' * 64))
        for c in 'rgbaxyzw':
            good['asset'] += ['shader:_BaseColor.' + c, 'material:_BaseColor.' + c]
            good['grading'].append('post:Vignette.color.' + c)
        extra = {'objects': {'select': {'component': 'Enemy'}}, 'components': {'select': {'component': 'Light'}},
                 'widgets': {'select': {'component': 'Slider'}}, 'spawns': {'component': 'Projectile'},
                 'light': {'point': {'xyz': [0, 1, 0]}}, 'log': {'pattern': 'Error'}, 'asset': {'asset': 'Assets/x.mat'}}
        self.assertEqual(sorted(self.MEASURE), sorted(self.KINDS))
        self.assertEqual((sorted(good), sorted(bad)), (sorted(self.KINDS), sorted(self.KINDS)))

        def key(probe):
            return 'fact' if probe == 'trace' else 'field'

        def check(probe, f):
            plays = {'asset': 'editor', 'trace': 'trace'}
            measure = dict({'probe': probe, key(probe): f}, **extra.get(probe, {}))
            return self.ok(probe_check(measure, plays.get(probe, 'look'), {'op': '>=', 'value': 1}), 'Probe')

        for probe, fields in good.items():
            for f in fields:
                self.assertEqual(check(probe, f), [], f'{probe} {f}')
        for probe, fields in bad.items():
            schema = self.S['$defs'][self.MEASURE[probe]]['properties'][key(probe)]
            for f in fields:
                self.assertNotEqual(list(vg.check_schema(f, schema, self.S)), [], f'{probe} {f}')
        for unreal in ('pawn', 'actors'):
            self.assertNotEqual(check(unreal, 'x'), [])

    def test_contract_shapes(self):
        """Points, near, selects and inputs as the contract (sections 1-4) writes them: every key of each select, every
        input row, and none of the original's keys Unity names otherwise or doesn't have."""
        x = {'xyz': [0, 0, 0]}
        sel = {'component': 'UnityEngine.UI.Button', 'tag': 'Player', 'layer': 'Ignore Raycast', 'name': 'Enemy (Clone)',
               'near': {'point': {'object': {'name': 'Kiln*'}, 'offset': [0, 1, 0]}, 'radius': 2.0,
                        'y_min': -1, 'y_max': 3, 'y_relative': True},
               'has': {'component': 'Light', 'lit': True, 'visible': True, 'near': {'point': x, 'radius': 1},
                       'simulating': True},
               'player': True, 'inactive': True}
        self.assertEqual(self.ok(sel, 'Select'), [])
        for point in ({'xyz': [1, 2, 3]}, {'player': True, 'offset': [0, 1, 0]}, {'camera': True, 'forward': 5},
                      {'object': {'tag': 'Lamp'}, 'offset': [0, 0, 1]}):
            self.assertEqual(self.ok({'point': point, 'radius': 1}, 'Near'), [], point)
        for ref, value in (
                ('ComponentSelect', {'component': 'ParticleSystem', 'effect': True, 'name': 'Smoke*',
                                     'owner': {'tag': 'Kiln'}, 'near': {'point': x, 'radius': 3}, 'mesh': 'Cube',
                                     'visible': True, 'inactive': True}),
                ('WidgetSelect', {'component': 'Slider', 'name': 'Health*', 'text': '^\\d+$', 'visible': True}),
                ('UiSelect', {'kind': 'image', 'text': None, 'rect': [0, 0, 1, 0.2]}),
                ('AudioSelect', {'sound': 'Footstep*', 'sound_class': 'SFX', 'owner': {'player': True}}),
                ('PieceSelect', {'component': 'MeshRenderer', 'name': 'Wall*', 'mesh': 'Brick', 'owner': {'tag': 'Town'},
                                 'near': {'point': x, 'radius': 50}}),
                ('GroundMeasure', {'probe': 'ground', 'xz': [3, 4], 'field': 'height', 'select': {'layer': 'Ground'}}),
                ('GroundMeasure', {'probe': 'ground', 'box': [0, 0, 10, 10], 'grid': 8, 'field': 'range'}),
                ('AssetMeasure', {'probe': 'asset', 'scene': 'Assets/Scenes/Town.unity',
                                  'select': {'component': 'MeshRenderer', 'tag': 'Terrace'}, 'field': 'material_default',
                                  'of': 'all'}),
                ('AssetMeasure', {'probe': 'asset', 'prefab': 'Assets/Prefabs/Hero (Variant).prefab',
                                  'select': {'name': 'Body'}, 'field': 'mesh_collision'}),
                ('AssetMeasure', {'probe': 'asset', 'asset': 'Assets/Characters/Hero@Run.fbx',
                                  'field': 'import:importAnimation'}),
                ('SpawnsMeasure', {'probe': 'spawns', 'component': 'Projectile', 'field': 'spawned'}),
                ('DrawnMeasure', {'probe': 'drawn', 'line': {'from': {'player': True}, 'to': {'camera': True, 'forward': 20},
                                                             'radius': 0.5}, 'field': 'reach'}),
                ('DrawnMeasure', {'probe': 'drawn', 'near': {'point': {'player': True}, 'radius': 1, 'y_min': 0,
                                                             'y_relative': True}, 'field': 'motion'}),
                ('LightMeasure', {'probe': 'light', 'point': {'camera': True, 'forward': 2}, 'field': 'brightness'}),
                ('PlayerMeasure', {'probe': 'player', 'field': 'dist', 'to': {'object': {'name': 'Gate'},
                                                                              'offset': [0, 0, 1]}})):
            self.assertEqual(self.ok(value, ref), [], (ref, value))
        # wherever a select takes them: a type by its full name, a wildcard with every character the contract lists;
        # and every character an asset's, a scene's and a prefab's path may hold
        full, wild = 'Game_2.UI.RetryButton3', 'Lamp_2.b (Clone)-?*'
        for ref, value in (
                ('Select', {'component': full, 'name': wild}), ('Has', {'component': full}),
                ('ComponentSelect', {'component': full, 'name': wild, 'mesh': wild}),
                ('WidgetSelect', {'component': full, 'name': wild}),
                ('AudioSelect', {'sound': wild, 'sound_class': wild}),
                ('PieceSelect', {'component': full, 'name': wild, 'mesh': wild}),
                ('SpawnsMeasure', {'probe': 'spawns', 'component': full, 'field': 'spawned'}),
                ('Click', {'t': 3, 'widget': wild, 'click': True}),
                ('AssetMeasure', {'probe': 'asset', 'asset': 'Packages/com.game.kit-2/Art/Lit_2 (b)@x.mat',
                                  'field': 'shader:_BaseColor.r'}),
                ('AssetMeasure', {'probe': 'asset', 'scene': self.SCENE, 'select': {'name': 'Body'}, 'field': 'count'}),
                ('AssetMeasure', {'probe': 'asset', 'prefab': 'Packages/com.game.kit-2/Prefabs/Hero_1 (Variant).prefab',
                                  'select': {'name': 'Body'}, 'field': 'count'})):
            self.assertEqual(self.ok(value, ref), [], (ref, value))
        for ref, value in (
                ('Select', {'class': 'BP_Wall_C'}), ('Has', {'class': 'PointLightComponent'}), ('Has', {'movable': True}),
                ('ComponentSelect', {'class': 'NiagaraComponent'}), ('PieceSelect', {'class': 'StaticMeshComponent'}),
                ('WidgetSelect', {'class': 'TextBlock'}), ('WidgetSelect', {'slate': 'STextBlock'}),
                ('UiSelect', {'kind': 'line'}), ('Near', {'point': {'pawn': True}, 'radius': 1}),
                ('Near', {'point': x, 'radius': 1, 'z_min': 0}), ('AtObject', {'actor': {'tag': 'Lamp'}}),
                ('GroundMeasure', {'probe': 'ground', 'xy': [3, 4], 'field': 'height'}),
                ('AssetMeasure', {'probe': 'asset', 'map': '/Game/Maps/L_Level6', 'select': {'tag': 'Terrace'},
                                  'field': 'count'}),
                ('AssetMeasure', {'probe': 'asset', 'asset': '/Game/Materials/M_Road', 'field': 'prop:two_sided'}),
                ('AssetMeasure', {'probe': 'asset', 'asset': 'Assets/.hidden/M_Road.mat', 'field': 'shader:_Cull'}),
                ('SpawnsMeasure', {'probe': 'spawns', 'class': 'BP_Coin_C', 'field': 'spawned'}),
                ('Has', {}), ('Has', {'lit': False}), ('Select', {'player': False})):
            self.assertNotEqual(self.ok(value, ref), [], (ref, value))
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
                    {'t': 1, 'key': '<Joystick>/trigger', 'press': True}, {'t': 121, 'key': '<Keyboard>/w', 'press': True},
                    {'t': 2, 'key': 'MouseX', 'axis': 4.0}, {'t': 2, 'key': '<Mouse>/delta/x', 'axis': 1001},
                    {'t': 3, 'widget': 'RetryButton', 'click': False}, {'t': 3, 'widget': 'Hud/Retry', 'click': True},
                    {'t': 4, 'cursor': [1.5, 0.5]}, {'t': 4, 'cursor': [0.5]},
                    {'t': 5, 'teleport': [1, 2]}, {'t': 5, 'teleport': [1, 2, 3], 'hold': 0},
                    {'t': 5, 'teleport': [1, 2, 3], 'yaw': 361}, {'t': 6, 'teleport_to': {'actor': 'Ore'}},
                    {'t': 6, 'teleport_to': {'tag': 'Ore'}, 'distance': -1}, {'t': 7, 'wait': 0}, {'t': 7, 'wait': 301}):
            self.assertNotEqual(self.ok(dict(play, inputs=[bad]), 'TaskPlay'), [], bad)
        self.assertNotEqual(self.ok(dict(play, map='/Game/Maps/L_X'), 'TaskPlay'), [])
        self.assertNotEqual(self.ok(dict(play, scene='Assets/Scenes/X.scene'), 'TaskPlay'), [])
        self.assertNotEqual(self.ok(dict(play, args=['-x'] * 17), 'TaskPlay'), [])
        self.assertNotEqual(self.ok(dict(play, args=['x' * 61]), 'TaskPlay'), [])
        self.assertEqual(self.ok(dict(play, args=self.ARGS, scene=self.SCENE), 'TaskPlay'), [])

    def test_task_level(self):
        S = self.S
        t = task('a' * 40, 'b' * 40)
        self.assertEqual(list(vg.check_schema(t, S)), [])
        self.assertEqual(S['properties']['engine']['const'], 'unity-6000.3')
        self.assertNotIn('template', S['properties'])
        for bad in ({'engine': '5.7'}, {'template': 'blank-cpp'}, {'play_scene': '/Game/Maps/L_X'},
                    {'play_scene': 'Assets/' + 'a' * 288 + '.unity'}, {'play_args': ['-scenario', 'two words']},
                    {'play_args': ['x'] * 17}, {'play_args': ['-' + 'x' * 61]}, {'play_args': ['x' * 61]},
                    {'player': {'class': 'BP_Hero_C'}}, {'play_map': '/Game/Maps/L_X'}):
            self.assertNotEqual(list(vg.check_schema(dict(t, **bad), S)), [], bad)
        for good in ({'play_scene': None, 'play_args': []}, {'play_scene': 'Assets/Scenes/Level (2).unity'},
                     {'play_scene': 'Assets/' + 'a' * 287 + '.unity'}, {'play_args': ['-x'] * 16},
                     {'play_scene': self.SCENE, 'play_args': self.ARGS},
                     {'player': {'name': 'Hero', 'component': 'Game.HeroController'}}, {'player': None}):
            self.assertEqual(list(vg.check_schema(dict(t, **good), S)), [], good)
        self.assertEqual(vg.task_semantic_errors(t), [])

    def test_contract_inline_examples(self):
        """The contract's inline task examples: section 1's play_args, section 4's inputs as written there; and the
        examples the schema's own descriptions show."""
        text = read(CONTRACT) if os.path.isfile(CONTRACT) else ''
        if not text:
            self.skipTest('no CONTRACT.md')
        shown = re.search(r'`play_args` \(`(\[.*?\])`\)', text)
        self.assertIsNotNone(shown, 'section 1 shows play_args as `play_args` (`[...]`)')
        self.assertEqual(list(vg.check_schema(json.loads(shown.group(1)), self.S['properties']['play_args'], self.S)), [])
        key = self.S['$defs']['Key']['properties']['key']['pattern']
        paths = set(re.findall(r'`(<(?:Keyboard|Mouse|Gamepad)>/[A-Za-z0-9/]+)`', text))
        self.assertGreater(len(paths), 5, paths)
        for path in paths:
            self.assertRegex(path, key)
        self.assertEqual(self.ok({'t': 1, 'widget': 'RetryButton', 'click': True}, 'Click'), [])
        # the schema's own: control paths (not the <Mouse>/delta/* kind), play_args and a judge's route
        described = json.dumps(self.S)
        own = set(re.findall(r'<(?:Keyboard|Mouse|Gamepad)>/[A-Za-z0-9/]*[A-Za-z0-9](?![A-Za-z0-9/*])', described))
        self.assertGreater(len(own), 4, own)
        for path in own:
            self.assertRegex(path, key)
        args = re.search(r'\[.*?\]', self.S['properties']['play_args']['description']).group(0)
        self.assertEqual(list(vg.check_schema(json.loads(args), self.S['properties']['play_args'], self.S)), [])
        route = re.search(r'e\.g\. ([^\s);]+)', self.S['$defs']['Judge']['description']).group(1)
        self.assertEqual(list(vg.check_schema(route, self.S['$defs']['Judge']['properties']['route'], self.S)), [])

    def test_check_names_its_kind(self):
        """A check without `kind` passed (build, boot and package take a name alone, and the checks' discriminator hides a
        second match) and the checker then had no kind to run it by: every check names its kind, with no default."""
        self.assertEqual(sorted(self.CHECKS), sorted(self.SHAPE))
        for kind, rest in self.CHECKS.items():
            check = dict(rest, name='c', kind=kind)
            self.assertEqual(self.ok({'name': 'm', 'checks': [check]}, 'Milestone'), [], kind)
            del check['kind']
            self.assertNotEqual(self.ok({'name': 'm', 'checks': [check]}, 'Milestone'), [], kind)
            self.assertNotIn('default', self.S['$defs'][self.SHAPE[kind]]['properties']['kind'], kind)

    def test_limits_in_metres(self):
        """The original's limits in centimetres, scaled to metres as its defaults are (contract section 1: 200 cm -> 2 m,
        2 km -> 2000 m): a value at its limit passes, one past it fails."""
        x = {'xyz': [0, 0, 0]}
        for ref, key, limit, rest in (('AtCamera', 'forward', 1000, {'camera': True}),
                                      ('Line', 'radius', 100, {'from': x, 'to': x}),
                                      ('Near', 'radius', 100000, {'point': x}),
                                      ('Near', 'y_max', 100000, {'point': x, 'radius': 1}),
                                      ('Near', 'y_max', -100000, {'point': x, 'radius': 1}),
                                      ('Near', 'y_min', 100000, {'point': x, 'radius': 1}),
                                      ('Near', 'y_min', -100000, {'point': x, 'radius': 1}),
                                      ('TeleportTo', 'distance', 1000, {'t': 0, 'teleport_to': {'tag': 'Ore'}})):
            past = limit + (0.5 if limit > 0 else -0.5)
            self.assertEqual(self.ok(dict(rest, **{key: limit}), ref), [], (ref, key, limit))
            self.assertNotEqual(self.ok(dict(rest, **{key: past}), ref), [], (ref, key, past))

    def test_defaults_are_the_checkers(self):
        """A key left out means the schema's default: what the checker fills in for it (tools/task_check/tasks.py)."""
        tasks = load('task_check_tasks', os.path.join('task_check', 'tasks.py'))
        d = self.S['$defs']

        def default(ref, key):
            return d[ref]['properties'][key]['default']

        turn, beside = tasks.inputs([{'t': 0, 'teleport': [0, 0, 0]}, {'t': 0, 'teleport_to': {'tag': 'Ore'}}])
        self.assertEqual(turn['yaw'], default('Teleport', 'yaw'))
        self.assertEqual(beside['distance'], default('TeleportTo', 'distance'))
        self.assertEqual(tasks.point({'camera': True})['forward'], default('AtCamera', 'forward'))
        ground = tasks.measure({'probe': 'ground', 'field': 'range', 'box': [0, 0, 1, 1]})
        self.assertEqual(ground['grid'], default('GroundMeasure', 'grid'))
        self.assertEqual(tasks.measure({'probe': 'log', 'pattern': 'x'})['field'], default('LogMeasure', 'field'))
        for probe, rest in (('objects', {'select': {}}), ('components', {'select': {'effect': True}}),
                            ('widgets', {'select': {}}), ('ui', {}), ('asset', {'asset': 'Assets/x.mat'})):
            m = tasks.measure(dict({'probe': probe, 'field': 'count'}, **rest))
            self.assertEqual((m['of'], m['match']), (default(self.MEASURE[probe], 'of'),
                                                     default(self.MEASURE[probe], 'match')), probe)
        for kind, rest in self.CHECKS.items():
            check = tasks.check(dict(rest, name='c', kind=kind))
            for key in ('required', 'weight'):
                self.assertEqual(check[key], default(self.SHAPE[kind], key), (kind, key))
        self.assertEqual(tasks.check({'name': 'b', 'kind': 'build'})['fails_at_start'],
                         default('Build', 'fails_at_start'))
        self.assertEqual(tasks.check({'name': 'b', 'kind': 'boot'})['seconds'], default('Boot', 'seconds'))
        self.assertEqual(tasks.check({'name': 'f', 'kind': 'file_exists', 'glob': '*'})['min_count'],
                         default('FileExists', 'min_count'))
        top = self.S['properties']
        self.assertEqual(tasks.place({}, 'look'), (top['play_scene']['default'], top['play_args']['default']))
        self.assertEqual(tasks.player({}), top['player']['default'])

    def test_unity_words(self):
        """Titles and descriptions name Unity's things in Unity's words (contract section 1), and no definition keeps a
        key of the original's that Unity names otherwise or doesn't have."""
        texts, keys = [], set()

        def walk(node):
            if isinstance(node, dict):
                for k, v in node.items():
                    if k in ('title', 'description', '$comment') and isinstance(v, str):
                        texts.append(v)
                    else:
                        if k == 'properties' and isinstance(v, dict):
                            keys.update(v)
                        walk(v)
            elif isinstance(node, list):
                for v in node:
                    walk(v)

        walk(self.S)
        unreal = re.compile(r'\b(actors?|pawns?|UMG|Slate|Blueprints?|Niagara|Cascade|cm|Z up|play_map|uproject)\b|'
                            r'/Game/|`map`', re.I)
        self.assertEqual([m.group(0) for t in texts for m in unreal.finditer(t)], [])
        self.assertEqual(keys & {'actor', 'pawn', 'class', 'slate', 'map', 'play_map', 'template', 'xy', 'z_min', 'z_max',
                                 'z_relative'}, set())


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
             'build': {'config': 'Release', 'commit': head, 'exe': 'Build/KilnRun.exe'},
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
            with open(os.path.join(ds, 'workflow.jsonl'), 'a', encoding='utf-8') as f:
                f.write(workflow_row(3, reason='Asked Claude to tidy the HUD') + '\n')
            os.remove(os.path.join(ds, 'UnityProject', 'ProjectSettings', 'ProjectVersion.txt'))
            m['files'] = [f for f in m['files'] if not f['path'].endswith('/ProjectVersion.txt')]
        rep = vg.Report()
        z = self.make_zip(mutate)
        vg.check_dataset(rep, z, 'dataset')
        errs = ' | '.join(errors(rep))
        for what in ("holds the grader's half (milestones)", 'manifest tasks (count, names) differ',
                     'banned name (?i)\\bclaude\\b x1'):
            self.assertIn(what, errs)
        self.assertIn('listed asset file not present: Crates: Assets/ThirdParty/Kenney/', errs)
        if shutil.which('powershell') or shutil.which('pwsh'):
            rep = vg.Report()
            vg.run_layout_validator(rep, z, False)
            self.assertIn('UnityProject/ has no ProjectSettings/ProjectVersion.txt', errors(rep))

    def test_cli_with_zip(self):
        self.make_zip()
        r = subprocess.run([sys.executable, os.path.join(TOOLS, 'validate-game.py'), self.repo, '--no-layout'],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


if __name__ == '__main__':
    unittest.main()
