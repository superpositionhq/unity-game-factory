"""tools/validate-game.py on throwaway Unity game repos: a valid one (with five long-thread tasks on its orphan tasks
branch and a full Dataset.zip) and one broken variant per rule. Fixtures are made with plain git, no Unity and no PowerShell.

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
                 'describe': 'The enemies give off light again.', 'play': 'drive',   # selected by what they do:
                 'measure': {'probe': 'objects', 'select': {'has': {'lit': True}},  # Enemy is only the reference's
                             'field': 'glow', 'of': 'max'},
                 'expect': {'op': '>', 'calibrate': 0.5}}]},
            {'name': 'still_works', 'checks': [
                {'name': 'hero_moves', 'kind': 'probe', 'weight': 0, 'needs': ['boots_clean'],
                 'describe': 'The hero still moves.', 'play': 'drive',
                 'measure': {'probe': 'player', 'field': 'moved', 'agg': 'max'}, 'expect': {'op': '>', 'value': 2}}]}]}
    t.update(over)
    return t


TASKS = ('fix-hero-hud', 'feat-enemy-glow', 'fix-kiln-tags', 'feat-score-hud', 'fix-hero-prefab')


def game_tasks(start, ref, **over):
    """The five hard tasks a valid game ships ({name: task}; they share the one thread); over changes the first."""
    tasks = {}
    for i, n in enumerate(TASKS):
        kind = 'feature' if n.startswith('feat-') else 'bug_fix'
        t = task(start, ref, name=f'{SLUG}-{n}', seed={'game': SLUG, 'commit': start, 'reference': ref, 'kind': kind})
        tasks[t['name']] = dict(t, **over) if i == 0 else t
    return tasks


def mobile_settings(orientation='landscape', product='Kiln Run', package='com.kilnrun.game'):
    """(ProjectSettings.asset, QualitySettings.asset, GraphicsSettings.asset): the lines rule `mobile` reads, as Unity
    6000.3.26f1 wrote them for a game made with new-game.ps1 -Platform mobile -Orientation <orientation>."""
    portrait = orientation == 'portrait'
    width, height = (1080, 1920) if portrait else (1920, 1080)
    project = f"""%YAML 1.1
%TAG !u! tag:unity3d.com,2011:
--- !u!129 &1
PlayerSettings:
  m_ObjectHideFlags: 0
  serializedVersion: 28
  defaultScreenOrientation: {0 if portrait else 4}
  companyName: {product}
  productName: {product}
  defaultScreenWidth: {width}
  defaultScreenHeight: {height}
  defaultScreenWidthWeb: 960
  defaultScreenHeightWeb: 600
  allowedAutorotateToPortrait: 0
  allowedAutorotateToPortraitUpsideDown: 0
  allowedAutorotateToLandscapeRight: {0 if portrait else 1}
  allowedAutorotateToLandscapeLeft: {0 if portrait else 1}
  resizableWindow: 0
  fullscreenMode: 3
  bundleVersion: 1.0
  applicationIdentifier:
    Android: {package}
  buildNumber:
    Standalone: 0
  AndroidBundleVersionCode: 1
  AndroidMinSdkVersion: 26
  AndroidTargetSdkVersion: 34
  AndroidTargetArchitectures: 2
  m_BuildTargetGraphicsAPIs:
  - m_BuildTarget: AndroidPlayer
    m_APIs: 15000000
    m_Automatic: 0
  m_BuildTargetVRSettings: []
  scriptingBackend:
    Android: 1
    Standalone: 0
  il2cppCompilerConfiguration: {{}}
"""
    quality = """%YAML 1.1
%TAG !u! tag:unity3d.com,2011:
--- !u!47 &1
QualitySettings:
  m_ObjectHideFlags: 0
  serializedVersion: 5
  m_CurrentQuality: 0
  m_QualitySettings:
  - serializedVersion: 5
    name: Mobile
    pixelLightCount: 1
    skinWeights: 4
    antiAliasing: 0
    vSyncCount: 1
    lodBias: 1
    customRenderPipeline: {fileID: 11400000, guid: 389207dfd0a67cf4b9cba2d88b7c4666, type: 2}
    excludedTargetPlatforms: []
  m_TextureMipmapLimitGroupNames: []
  m_PerPlatformDefaultQuality:
    Android: 0
    Standalone: 0
"""
    graphics = """%YAML 1.1
%TAG !u! tag:unity3d.com,2011:
--- !u!30 &1
GraphicsSettings:
  m_ObjectHideFlags: 0
  m_CustomRenderPipeline: {fileID: 11400000, guid: 389207dfd0a67cf4b9cba2d88b7c4666, type: 2}
"""
    return project, quality, graphics


def make_mobile(repo, orientation='landscape'):
    """Turns the fixture game in `repo` into a mobile game held in `orientation`: Platform.json and the project
    settings the mobile setup leaves. Not committed."""
    project, quality, graphics = mobile_settings(orientation)
    write(repo, 'Platform.json', json.dumps({'platform': 'mobile', 'orientation': orientation}) + '\n')
    write(repo, 'ProjectSettings/ProjectSettings.asset', project)
    write(repo, 'ProjectSettings/QualitySettings.asset', quality)
    write(repo, 'ProjectSettings/GraphicsSettings.asset', graphics)


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
            set_tasks(base, game_tasks(start, ref))
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
        self.assertIn('5 task(s) on tasks', notes)

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
        set_tasks(self.repo, dict(game_tasks(self.start, self.ref), **{name: task(s, r)}))
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
        set_tasks(self.repo, game_tasks(self.start, self.ref), extra=['-p', self.ref])
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
        set_tasks(self.repo, game_tasks(self.start, self.ref, **over))
        return errors(self.check(), 'repo: Tasks')

    def probe(self, i, **measure):
        t = task(self.start, self.ref)
        t['milestones'][2]['checks'][i]['measure'] = measure
        return t['milestones']

    def test_easy(self):
        errs = self.tasks(difficulty='easy')
        self.assertTrue(any("difficulty 'easy'" in e for e in errs), errs)

    def test_fewer_than_five_tasks(self):
        tasks = game_tasks(self.start, self.ref)
        del tasks[f'{SLUG}-{TASKS[-1]}']
        set_tasks(self.repo, tasks)
        self.assertEqual(errors(self.check(), 'repo: Tasks'),
                         ['tasks: 4 task(s): a game ships at least 5 (unity-write-tasks section 1)'])

    def test_at_least_four_hard(self):
        self.assertEqual(self.tasks(difficulty='medium'), [])   # four hard and one medium: the game stands
        tasks = game_tasks(self.start, self.ref, difficulty='medium')
        del tasks[f'{SLUG}-{TASKS[1]}']['difficulty']           # no difficulty: medium, the schema's default
        set_tasks(self.repo, tasks)
        self.assertEqual(errors(self.check(), 'repo: Tasks'),
                         [f'tasks: 3 hard task(s): a game needs at least 4 hard tasks (medium: {SLUG}-{TASKS[1]}, '
                          f'{SLUG}-{TASKS[0]}); the others may be medium (unity-write-tasks section 1)'])
        tasks[f'{SLUG}-{TASKS[0]}']['difficulty'] = 'hard'
        set_tasks(self.repo, tasks)
        self.assertEqual(errors(self.check(), 'repo: Tasks'), [])   # four hard, and the one that names none is medium
        for i in range(6):                                      # ten tasks, four hard and six medium: the game stands
            t = dict(tasks[f'{SLUG}-{TASKS[0]}'], name=f'{SLUG}-fix-more-{i}', difficulty='medium')
            tasks[t['name']] = t
        set_tasks(self.repo, tasks)
        self.assertEqual(errors(self.check(), 'repo: Tasks'), [])

    def test_reference_only_name(self):
        ms = self.probe(2, probe='objects', select={'component': 'Enemy', 'has': {'lit': True}}, field='glow', of='max')
        self.assertEqual(self.tasks(milestones=ms),
                         [f'tasks:Tasks/{SLUG}-{TASKS[0]}.json: check enemies_glow names Enemy, which only the reference '
                          'has: another fair build names it otherwise; select by what it does or where it is, press a '
                          'control by words the start shows or the instruction states (unity-write-tasks section 5)'])
        ms[2]['checks'][2]['measure']['select']['component'] = 'Kiln'   # the start has it: any build can match it
        self.assertEqual(self.tasks(milestones=ms), [])
        ms[2]['checks'][2]['measure']['select']['component'] = 'Enemy'
        ms[2]['checks'][2]['required'] = False                          # an optional probe gates nothing
        errs = self.tasks(milestones=ms)
        self.assertFalse([e for e in errs if 'only the reference' in e], errs)

    def test_reference_only_play_inputs(self):
        """A play's click, tap and drag widgets, its set stages, its command-line flags and the task's play_args name
        nothing only the reference has (Hud, Enemy, field29, field30), unless the instruction states a shown name."""
        def names(t):
            return sorted(re.search(r'names (\S+), which only|set -(\S+), a flag', e).group(1, 2)
                          for e in self.tasks(**t) if 'only the reference has' in e)
        ms = task(self.start, self.ref)['milestones']
        play = ms[2]['checks'][1]['play']
        play['inputs'] += [{'t': 9, 'widget': 'Hud', 'click': True}, {'t': 10, 'tap': {'widget': 'Enemy'}},
                           {'t': 11, 'drag': [{'widget': 'Kiln'}, [0.5, 0.5]]},
                           {'t': 12, 'set': 'field30', 'on': {'component': 'Kiln'}, 'value': 1},
                           {'t': 13, 'widget': 'Hu*', 'click': True}]   # a wildcard matches by pattern: never refused
        play['args'] += ['-field29']
        self.assertEqual(names({'milestones': ms}), [('Enemy', None), ('Hud', None), ('field29', None),
                                                     ('field30', None)])
        # a widget or flag the instruction states is the ticket's own word; a member never is
        said = task(self.start, self.ref)['instruction'] + ' QA presses Hud, then Enemy, with the field29 option.'
        self.assertEqual(names({'milestones': ms, 'instruction': said}), [('field30', None)])
        # the task's play_args start every play
        ms = task(self.start, self.ref)['milestones']
        self.assertEqual(names({'milestones': ms, 'play_args': ['-scenario', '2', '-field29']}), [(None, 'field29')])
        # a required judge's plays are held to it; an optional one gates nothing
        judge = {'name': 'looks_as_asked', 'kind': 'judge', 'needs': ['boots_clean'], 'question': 'Does it read?',
                 'rubric': [{'key': 'x', 'criterion': 'The score is legible.', 'required': True}],
                 'plays': [{'name': 'open_hud', 'seconds': 5, 'inputs': [{'t': 1, 'widget': 'Hud', 'click': True}]}]}
        ms[2]['checks'].append(judge)
        self.assertEqual(names({'milestones': ms}), [('Hud', None)])
        judge['required'] = False
        self.assertEqual(names({'milestones': ms}), [])

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
        self.assertTrue(any('measure.select: unexpected key "class"' in e for e in errs), errs)
        self.assertTrue(any("measure.field: 'bb:Speed' does not match" in e for e in errs), errs)

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
        set_tasks(self.repo, dict(game_tasks(self.start, self.ref), **{name: task(old, r)}))
        errs = errors(self.check(), 'repo: Tasks')
        self.assertTrue(any(f'seed.commit {old[:12]} is a Unity 2022.3.62f1 project' in e for e in errs), errs)
        self.assertFalse(any('seed.reference' in e and 'project' in e for e in errs), errs)

    def test_short_thread(self):
        """The size of a span is a soft bar (owner, 2026-11-19): a start and a reference one commit apart get a warning
        for each number they are under, and no error."""
        set_tasks(self.repo, game_tasks(self.start, self.ref, seed={
            'game': SLUG, 'commit': git(self.repo, 'rev-parse', f'{self.ref}~1'), 'reference': self.ref,
            'kind': 'bug_fix'}))
        rep = self.check()
        warns = [m for s, a, m in rep.items if s == 'warning' and a.startswith('repo: Tasks')]
        for floor in ('game file(s) against the start, fewer than 5', 'code line(s) against the start, fewer than 100',
                      'commit(s) change the game from seed.commit to seed.reference, fewer than 4'):
            self.assertTrue(any(floor in w and 'soft bar' in w for w in warns), (floor, warns))
            self.assertFalse(any(floor in e for e in errors(rep, 'repo: Tasks')), floor)
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
        """The eight systems a game file falls into; an editor step (the creation's record) or a .meta is no game file,
        though a step's lines are code lines."""
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

    def test_task_bar(self):
        """A game's bar: at least 5 tasks, at least 4 of them hard; the others may be medium (what a task that names
        none is)."""
        hard = {f't{i}': 'hard' for i in range(5)}
        self.assertEqual(vg.task_bar_errors(hard), [])
        self.assertEqual(vg.task_bar_errors(dict(hard, t0='medium')), [])   # 4 hard + 1 medium
        self.assertEqual(vg.task_bar_errors(dict(hard, t0=None)), [])
        self.assertEqual(vg.task_bar_errors(dict({f'm{i}': 'medium' for i in range(6)}, t0='hard', t1='hard', t2='hard',
                                                 t3='hard')), [])           # 10 tasks: 4 hard + 6 medium
        self.assertEqual(vg.task_bar_errors(dict(hard, t4='medium', t1=None)),   # 3 hard + 2 medium
                         ['3 hard task(s): a game needs at least 4 hard tasks (medium: t1, t4); the others may be medium'])
        self.assertEqual(vg.task_bar_errors({f't{i}': 'hard' for i in range(4)}), ['4 task(s): a game ships at least 5'])
        self.assertEqual(vg.task_bar_errors({'t0': 'hard', 't1': 'hard'}),
                         ['2 task(s): a game ships at least 5',
                          '2 hard task(s): a game needs at least 4 hard tasks; the others may be medium'])
        self.assertEqual(vg.task_bar_errors(dict(hard, t0='easy')), [])   # an easy task is thread_errors' finding
        self.assertEqual(vg.task_bar_errors(dict(hard, t0='trivial')), ['t0: difficulty \'trivial\': a task is "hard"'])
        self.assertEqual(vg.thread_errors({'difficulty': 'easy'}, 3)[0],
                         'difficulty \'easy\': a task is "hard" or "medium" (a game needs at least 4 "hard")')
        self.assertTrue(any("difficulty 'easy'" in e for e in vg.thread_errors({'difficulty': 'easy'}, 3)))

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
        for anchor, path in (('asset', 'Assets/a/../../b.mat'), ('scene', 'Assets/../ProjectSettings/X.unity'),
                             ('prefab', 'Packages/./x.prefab')):
            said = errs({'probe': 'asset', anchor: path, 'field': 'count' if anchor != 'asset' else 'prop:m_Name',
                         **({'select': {'name': 'x'}} if anchor != 'asset' else {})}, 'editor', {'op': '>=', 'value': 1})
            self.assertIn(f'{path} has a "." or ".." part', said, anchor)
        look = {'probe': 'player', 'field': 'y', 'agg': 'min'}
        self.assertIn('play fire: Assets/Scenes/../X.unity has a "." or ".." part',
                      errs(look, {'name': 'fire', 'seconds': 5, 'scene': 'Assets/Scenes/../X.unity'},
                           {'op': '>=', 'value': 0}))
        self.assertIn('play_scene: Assets/../X.unity has a "." or ".." part', ' '.join(vg.task_semantic_errors(
            task('a' * 40, 'b' * 40, play_scene='Assets/../X.unity'))))
        self.assertEqual(errs({'probe': 'asset', 'asset': 'Assets/Art/Hero.v2/Road..mat', 'field': 'prop:m_Name'},
                              'editor', {'op': '>=', 'value': 1}), '', 'dots inside a name are a name')
        # an empty part: the schema's patterns let these through, the editor pass and the build refuse them
        for anchor, path in (('asset', 'Assets/Art//Road.mat'), ('asset', 'Assets/Art/'),
                             ('scene', 'Assets//Scenes/X.unity'), ('prefab', 'Assets/Prefabs//x.prefab')):
            said = errs({'probe': 'asset', anchor: path, 'field': 'count' if anchor != 'asset' else 'prop:m_Name',
                         **({'select': {'name': 'x'}} if anchor != 'asset' else {})}, 'editor', {'op': '>=', 'value': 1})
            self.assertIn(f'{path} has an empty part', said, path)
        self.assertIn('play_scene: Assets/Scenes//X.unity has an empty part', ' '.join(vg.task_semantic_errors(
            task('a' * 40, 'b' * 40, play_scene='Assets/Scenes//X.unity'))))
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
        menu = {'name': 'menu', 'seconds': 6, 'inputs': [{'t': 1, 'key': '<Keyboard>/u', 'press': True}]}
        shown = dict(before, before=False, plays=[menu])
        self.assertEqual(errs(probe(x, menu), shown, dict(shown, name='k', shots=20)), '')
        self.assertEqual(errs(dict(shown, plays=[dict(menu, name=f'm{i}') for i in range(4)])), '')
        for check, said in (
                (dict(shown, plays=[menu, menu]), 'judge check j names a play twice'),
                (dict(shown, plays=[dict(menu, name='look')]), "check j: a task play can't be named look"),
                (dict(shown, plays=[dict(menu, seconds=5, inputs=[key])]), 'check j: play menu has an input at or after'),
                (dict(shown, plays=[dict(menu, args=['-batchmode'])]), "check j: a task play can't set -batchmode"),
                (dict(shown, plays=[dict(menu, scene='Assets/../A.unity')]), 'check j: play menu: Assets/../A.unity has'),
                (dict(shown, plays=[dict(menu, inputs=[{'t': 1, 'teleport_to': {
                    'tag': 'Ore', 'near': dict(near, y_min=5, y_max=1)}}])]), 'check j: a near band has y_min < y_max'),
                (dict(before, before=False, shots=8), 'judge check j sets shots but names no play of its own'),
                (dict(shown, plays=[menu, dict(menu, name='m2')], shots=11),
                 "judge check j asks 2 plays of 11 screenshots: more than a judge's 20"),
                (dict(shown, plays=[dict(menu, name=f'm{i}') for i in range(4)], shots=6), "more than a judge's 20")):
            self.assertIn(said, errs(check), said)
        self.assertIn('check j: task play menu differs from another play of that name',
                      errs(probe(x, menu), dict(shown, plays=[dict(menu, seconds=9)])))
        self.assertIn('check p: task play menu differs from another play of that name',
                      errs(shown, probe(x, dict(menu, seconds=9))))
        coin = dict(shown, plays=[dict(menu, inputs=[{'t': 1, 'teleport_to': {'name': 'Coin*'}}])])
        t = task('a' * 40, 'b' * 40, milestones=[{'name': 'm', 'checks': [coin]}])
        self.assertIn('play menu: teleport_to {"name": "Coin*"} goes to the nearest', ' | '.join(vg.task_warnings(t)))
        ok = lambda v: list(vg.check_schema(v, vg.SCHEMAS['game-task']['$defs']['Judge'], vg.SCHEMAS['game-task']))  # noqa: E731
        self.assertEqual(ok(dict(shown, shots=20)), [])
        for bad in (dict(shown, shots=1), dict(shown, shots=21), dict(shown, shots=7.5), dict(shown, plays=['look']),
                    dict(shown, plays=[dict(menu, name=f'm{i}') for i in range(5)])):
            self.assertNotEqual(ok(bad), [], bad)
        step = probe(dict(x, agg='step'))
        self.assertEqual(list(vg.check_schema(step, vg.SCHEMAS['game-task']['$defs']['Probe'], vg.SCHEMAS['game-task'])), [])
        self.assertNotEqual(list(vg.check_schema(probe(dict(x, agg='jolt')), vg.SCHEMAS['game-task']['$defs']['Probe'],
                                                 vg.SCHEMAS['game-task'])), [])
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

    def test_required_quality_judges(self):
        """A required judge is noted as one that should be optional, but for the judges of the brief's looks: a `judge`
        named `looks_as_asked` and a `judge` in `still_works`."""
        def judge(name, kind='judge', **over):
            return {'name': name, 'kind': kind, 'question': 'q', 'rubric': [{'key': 'k', 'criterion': 'c'}], **over}
        t = {'milestones': [
            {'name': 'done', 'checks': [judge('looks_as_asked'), judge('reads_well'), judge('optional', required=False),
                                        judge('looks_as_asked', 'code_judge'), judge('worked_well', 'actions_judge')]},
            {'name': 'still_works', 'checks': [judge('hud_unchanged'), judge('code', 'code_judge')]}]}
        self.assertEqual(vg.required_quality_judges(t), ['reads_well', 'looks_as_asked', 'code'])

    def test_play_after(self):
        """A task play's `after`: task plays of the task, named once, never itself, no cycle, and of two named
        together one runs after the other, in either order."""
        def reads(name, after=None):
            play = {'name': name, 'seconds': 10}
            return {'kind': 'probe', 'name': name, 'play': dict(play, after=after) if after else play}
        ok = [reads('one'), reads('two', ['one']), reads('three', ['two', 'one'])]
        self.assertEqual(vg.play_after_errors(ok), [])
        for checks, said in (
                ([reads('one', ['none'])], 'runs after none, which is no task play of the task'),
                ([reads('one', ['one'])], 'names itself in its after'),
                ([reads('one'), reads('two', ['one', 'one'])], 'task play two names one twice in its after'),
                ([reads('one', ['two']), reads('two', ['one'])], 'a cycle'),
                ([reads('one'), reads('two'), reads('three', ['one', 'two'])], 'neither runs after the other'),
                ([reads('one'), dict(reads('two'), play={'name': 'two', 'seconds': 10, 'after': ['one'], 'fresh': True})],
                 'task play two is fresh (it starts with the saved data cleared), so it runs after no play')):
            self.assertTrue(any(said in e for e in vg.play_after_errors(checks)), (said, vg.play_after_errors(checks)))
        fresh = [reads('one'), dict(reads('two'), play={'name': 'two', 'seconds': 10, 'fresh': True})]
        self.assertEqual(vg.play_after_errors(fresh), [], 'fresh alone: as any play that names no after')

    def test_event_rules(self):
        """A measure's `since` and a shot's `when` (task-probes.md 2.23): an event's measure is one the probe samples,
        with no window, at, agg or since of its own, and every rule of a measure; a shot's is one the probe reads every
        frame itself."""
        frames = {'probe': 'objects', 'select': {'name': 'HudDriver'}, 'field': 'prop:UiHudDriver.frames', 'of': 'first'}

        def since(measure):
            return {'name': 'p', 'kind': 'probe', 'describe': 'x', 'play': 'look', 'expect': {'op': '>=', 'value': 1},
                    'measure': dict(frames, at=[0], since={'measure': measure, 'expect': {'op': '>=', 'value': 45}})}

        def when(measure):
            play = {'name': 'events', 'seconds': 10, 'inputs': [
                {'t': 1, 'shot': 'win', 'when': {'measure': measure, 'expect': {'op': '>=', 'value': 1}, 'within': 3}}]}
            return {'name': 'p', 'kind': 'probe', 'describe': 'x', 'play': play, 'expect': {'op': '>=', 'value': 1},
                    'measure': frames}
        self.assertEqual(vg.probe_errors(since(frames), None, None, {}), [])
        self.assertEqual(vg.probe_errors(when(frames), None, None, {}), [])
        for measure, said in ((dict(frames, window=[0, 1]), 'check p: its since: its measure takes no window of its own'),
                              (dict(frames, agg='max'), 'its measure takes no agg of its own'),
                              ({'probe': 'log', 'pattern': 'x'}, 'its measure is read from samples of the play'),
                              ({'probe': 'ui', 'field': 'text'}, 'a ui measure takes `match` exactly when its field is text')):
            found = vg.probe_errors(since(measure), None, None, {})
            self.assertTrue(any(said in e for e in found), (said, found))
        for measure, said in (({'probe': 'player', 'field': 'x'}, "the probe reads a shot's event itself every frame"),
                              ({'probe': 'ui', 'field': 'count', 'select': {'rect': [0, 0, 0.5, 0.5]}},
                               'its ui select takes no rect'),
                              (dict(frames, to_axis=90), "a shot's event takes no to_angle or to_axis")):
            found = vg.probe_errors(when(measure), None, None, {})
            self.assertTrue(any("check p: play events: shot win's when: " in e and said in e for e in found), (said, found))

    def test_seen_rules(self):
        """A `seen` measure (task-probes.md 2.22), as the Lab's grader takes it: the schema's shape, then the rules
        beyond it, each with the grader's words."""
        play = {'name': 'combo', 'seconds': 10, 'inputs': [{'t': 3, 'shot': 'hud'}, {'t': 5, 'shot': 'hud_later'}]}

        def check(play=play, **measure):
            return {'name': 'p', 'kind': 'probe', 'describe': 'x', 'play': play,
                    'measure': {'probe': 'seen', 'shot': 'hud', 'read': 'number', **measure},
                    'expect': {'op': '>=', 'value': 3}}

        def schema(c):
            return list(vg.check_schema(c, vg.SCHEMAS['game-task']['$defs']['Probe'], vg.SCHEMAS['game-task']))

        def errs(c):
            t = task('a' * 40, 'b' * 40, milestones=[{'name': 'm', 'checks': [c]}])
            return ' | '.join(vg.task_semantic_errors(t))

        good = (check(), check(read='text', match='COMBO\\s*x\\d'), check(read='clock', rect=[0.6, 0, 1, 0.25]),
                check(rect=[0.5, 0.5, 0.52, 0.52]), check(shot=['hud', 'hud_later'], agg='rises'),
                check(shot=['hud_later', 'hud'], read='clock', agg='delta'),
                dict(check(), expect={'op': '>=', 'calibrate': 0.5}))
        for c in good:
            self.assertEqual((schema(c), errs(c)), ([], ''), c['measure'])
        for c in (check(shot='Hud'), check(shot='h' * 33), check(shot=['hud']), check(shot=['a', 'b', 'c', 'd', 'e']),
                  check(shot=['hud', 'Bad'], agg='max'), check(rect=[0, 0, 1]), check(rect=[0, 0, 1.2, 1]),
                  check(read='words'), check(read='text', match=''), check(read='text', match='x' * 201),
                  check(agg='mean'), check(field='text'), check(window=[0, 5]), {**check(), 'measure': {
                      'probe': 'seen', 'read': 'number'}}, {**check(), 'measure': {'probe': 'seen', 'shot': 'hud'}}):
            self.assertNotEqual(schema(c), [], c['measure'])
        self.assertEqual(schema(check(read='text', match='x' * 200)), [])
        for c, said in (
                (check(play='look'), 'check p: a seen measure reads a named shot of a task play of its own, never of '
                                     'look'),
                (check(play='drive'), 'never of drive'),
                (check(play='editor'), 'never of editor'),
                (check(shot='menu'), 'check p: its play combo takes no shot named menu (a `shot` input)'),
                (check(shot=['hud', 'menu'], agg='max'), 'check p: its play combo takes no shot named menu'),
                (check(rect=[0.5, 0.5, 0.51, 0.9]), 'check p: a seen rect is [x0, y0, x1, y1], at least 0.02 of the '
                                                    'frame each way'),
                (check(rect=[0.9, 0.5, 0.1, 0.9]), 'at least 0.02 of the frame each way'),
                (check(rect=[0.1, 0.5, 0.9, 0.505]), 'at least 0.02 of the frame each way'),
                (check(read='text'), 'check p: a seen measure takes `match` exactly when it reads text'),
                (check(read='text', match=None), 'takes `match` exactly when it reads text'),
                (check(match='x'), 'takes `match` exactly when it reads text'),
                (check(match=None), 'takes `match` exactly when it reads text'),
                (check(shot=['hud', 'hud_later']), 'check p: a seen measure reads a list of shots as a number or a '
                                                   'clock, with an `agg`'),
                (check(shot=['hud', 'hud_later'], agg=None), 'as a number or a clock, with an `agg`'),
                (check(shot=['hud', 'hud_later'], read='text', match='x', agg='max'), 'as a number or a clock'),
                (check(shot=['hud', 'hud'], agg='max'), 'check p: a seen measure names a shot twice'),
                (check(agg='max'), 'check p: a seen measure of one shot takes no `agg`'),
                (check(agg=None), 'check p: a seen measure of one shot takes no `agg`'),
                (check(read='text', match='('), "check p: '(' isn't a regular expression")):
            self.assertIn(said, errs(c), c['measure'])

    def test_a_seen_probe_is_a_visual_check(self):
        """A `seen` probe goes with the judges: it is no required probe and no outcome probe, earns no no-op score,
        and a task needs its own required probes besides it."""
        play = {'name': 'combo', 'seconds': 10, 'inputs': [{'t': 3, 'shot': 'hud'}]}
        seen = {'name': 'combo_shows', 'kind': 'probe', 'describe': 'x', 'play': play,
                'measure': {'probe': 'seen', 'shot': 'hud', 'read': 'number'}, 'expect': {'op': '>=', 'value': 3}}
        judge = {'name': 'j', 'kind': 'judge', 'question': 'q', 'rubric': [{'key': 'k', 'criterion': 'c'}]}
        self.assertTrue(vg.visual(seen) and vg.visual(judge))
        self.assertFalse(vg.visual(dict(seen, measure={'probe': 'ui', 'field': 'count'})))
        self.assertFalse(vg.visual(dict(judge, kind='code_judge')))
        t = task('a' * 40, 'b' * 40)
        t['milestones'][2]['checks'].append(seen)
        rep = vg.Report()
        self.assertTrue(vg.check_task(rep, 'repo: Tasks', 'x', t, SLUG, None))
        self.assertEqual(errors(rep), [], 'a seen probe beside the required probes')
        self.assertEqual([c['name'] for c in vg.outcome_probes(t)], ['hero_on_ground', 'score_counts', 'enemies_glow'])
        t['milestones'][2]['checks'] = [seen, dict(seen, name='combo_again'), dict(seen, name='combo_third')]
        self.assertEqual(vg.outcome_probes(t), [])
        rep = vg.Report()
        vg.check_task(rep, 'repo: Tasks', 'x', t, SLUG, None)
        said = errors(rep)
        self.assertIn('x: 0 required outcome probe(s) of weight above 0 outside still_works, fewer than 3 (a required '
                      'probe of weight 0 is a guard, not an outcome) (unity-write-tasks section 1: only long threads '
                      "of multiple edits); seen probe(s) ['combo_shows', 'combo_again', 'combo_third'] are visual "
                      'checks, never outcome probes', said)
        self.assertIn('x: no required outcome check carries weight, so no run can score (unity-write-tasks section 1: '
                      'only long threads of multiple edits)', said)
        t['milestones'][3]['checks'] = [dict(seen, name='still_combo', weight=0)]
        rep = vg.Report()
        vg.check_task(rep, 'repo: Tasks', 'x', t, SLUG, None)
        self.assertIn("x: no required probe check: pass/fail must be deterministic (unity-write-tasks section 5); seen "
                      "probe(s) ['combo_shows', 'combo_again', 'combo_third', 'still_combo'] are visual checks, counted "
                      'with the judges', errors(rep))

    def test_a_guard_is_no_outcome(self):
        """The long-thread bar counts required probes of weight above 0 outside still_works: a required probe of
        weight 0 is a guard, not an outcome."""
        def probe(name, **over):
            return {'name': name, 'kind': 'probe', **over}
        t = {'milestones': [
            {'name': 'done', 'checks': [probe('a'), probe('b', weight=2), probe('guard', weight=0),
                                        probe('extra', required=False), {'name': 'j', 'kind': 'judge'}]},
            {'name': 'still_works', 'checks': [probe('kept', weight=0), probe('kept_too')]}]}
        self.assertEqual([c['name'] for c in vg.outcome_probes(t)], ['a', 'b'])
        self.assertIn('2 required outcome probe(s) of weight above 0 outside still_works, fewer than 3 (a required '
                      'probe of weight 0 is a guard, not an outcome)', vg.thread_errors(t, len(vg.outcome_probes(t))))
        t['milestones'][0]['checks'].append(probe('c'))
        self.assertFalse(any('fewer than 3' in e for e in vg.thread_errors(t, len(vg.outcome_probes(t)))))

    def test_retired_checks(self):
        """`actions_judge` checks and `trace` probes are retired: a task that still carries one matches the schema
        (check_task refuses it, below); a task without one has none. A trace probe never counted as a required
        or an outcome probe, so no floor moves."""
        def check(name, kind, **over):
            return {'name': name, 'kind': kind, 'question': 'q', 'rubric': [{'key': 'k', 'criterion': 'c'}], **over}
        old = {'milestones': [{'name': 'done', 'checks': [check('looks_as_asked', 'judge')]},
                              {'name': 'quality', 'checks': [check('worked_well', 'actions_judge', required=False),
                                                             check('worked', 'actions_judge')]}]}
        trace = {'name': 'built', 'kind': 'probe', 'required': False, 'describe': 'The last build worked.',
                 'play': 'trace', 'measure': {'probe': 'trace', 'fact': 'build_ok_at_end'},
                 'expect': {'op': '>=', 'value': 1}}
        old['milestones'][1]['checks'].append(trace)
        self.assertEqual(vg.retired_checks(old), ['worked_well', 'worked', 'built'])
        self.assertEqual(list(vg.check_schema(trace, vg.SCHEMAS['game-task']['$defs']['Probe'], vg.SCHEMAS['game-task'])), [])
        self.assertEqual(vg.probe_errors(trace, {'commit': 'a', 'reference': 'b'}, 'b', {}), [])
        self.assertEqual(vg.required_quality_judges(old), [])
        schema = vg.SCHEMAS['game-task']
        for c in old['milestones'][1]['checks'][:2]:
            self.assertEqual(list(vg.check_schema(c, schema['$defs']['ActionsJudge'], schema)), [])
        new = {'milestones': [{'name': 'done', 'checks': [check('looks_as_asked', 'judge')]}]}
        self.assertEqual(vg.retired_checks(new), [])

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

    def test_retired_actions_judge(self):
        """A task that still carries an `actions_judge` check or a `trace` probe is refused (owner, 2026-11-19), as the
        Lab's grader refuses it: no trace play there (every run gets reward 0) and no actions_judge kind (it fails
        every run). A task without one has no such error."""
        def retired(t):
            rep = vg.Report()
            self.assertTrue(vg.check_task(rep, 'repo: Tasks', 'x', t, SLUG, None))
            return [m for m in errors(rep) if 'retired' in m]
        t = task('a' * 40, 'b' * 40)
        self.assertEqual(retired(t), [])
        t['milestones'].append({'name': 'quality', 'checks': [
            {'name': 'worked_well', 'kind': 'actions_judge', 'required': False, 'question': 'Did it test?',
             'rubric': [{'key': 'tested', 'criterion': 'It played the scenario after the fix.'}]}]})
        t['milestones'][-1]['checks'].append(
            {'name': 'built', 'kind': 'probe', 'required': False, 'describe': 'The last build worked.', 'play': 'trace',
             'measure': {'probe': 'trace', 'fact': 'build_ok_at_end'}, 'expect': {'op': '>=', 'value': 1}})
        self.assertEqual(retired(t), ["x: check(s) ['worked_well', 'built']: `actions_judge` checks and `trace` probes "
                                      "are retired: remove it (the Lab's grader gives a task with a trace probe reward "
                                      "0 on every run and fails an actions_judge check on every run) "
                                      '(unity-write-tasks section 5)'])

    def test_one_look_judge(self):
        """The one look judge (owner, 2026-11-19): `looks_as_asked` with asked_ and keep_ items sits in an outcome
        milestone with weight; with keep_ items alone, in still_works with weight 0; every item marked and required;
        no other required judge in still_works. A task whose judges mark no key (the older pair) is not held to it."""
        def errs(t):
            rep = vg.Report()
            self.assertTrue(vg.check_task(rep, 'repo: Tasks', 'x', t, SLUG, None))
            return [m for m in errors(rep) if 'judge looks_as_asked' in m]

        def look(*keys, **over):
            return {'name': 'looks_as_asked', 'kind': 'judge', 'needs': ['boots_clean'], 'before': True,
                    'reference': True, 'question': 'Does it look as asked?',
                    'rubric': [{'key': k, 'criterion': 'The sign is lit.', 'required': True} for k in keys], **over}
        old = task('a' * 40, 'b' * 40)
        old['milestones'][2]['checks'].append(look('sign_lit'))
        old['milestones'][3]['checks'].append(dict(look('door_red', weight=0), name='still_looks', reference=False))
        self.assertEqual(errs(old), [])                          # the older pair stands
        t = task('a' * 40, 'b' * 40)
        t['milestones'][2]['checks'].append(look('asked_sign_lit', 'keep_door_red'))
        self.assertEqual(errs(t), [])
        t['milestones'][3]['checks'].append(dict(look('door_red', weight=0), name='still_looks', reference=False))
        self.assertTrue(any("put the looks of required judge(s) ['still_looks'] in it" in e for e in errs(t)), errs(t))
        t = task('a' * 40, 'b' * 40)
        bad = look('asked_sign_lit', 'door_red', weight=0, before=False)
        bad['rubric'][0]['required'] = False
        t['milestones'][2]['checks'].append(bad)
        found = errs(t)
        for what in ("item(s) ['door_red'] are marked neither", "item(s) ['asked_sign_lit'] are not required",
                     'never still_works, with a weight above 0', '("before": true, "reference": true)'):
            self.assertTrue(any(what in e for e in found), (what, found))
        t = task('a' * 40, 'b' * 40)
        t['milestones'][3]['checks'].append(look('keep_door_red', weight=0, reference=False))
        self.assertEqual(errs(t), [])                            # keep items alone: in still_works, weight 0
        t = task('a' * 40, 'b' * 40)
        t['milestones'][2]['checks'].append(look('keep_door_red'))
        self.assertTrue(any('keep_ items only: it sits in still_works with "weight": 0' in e for e in errs(t)))

    def test_package_check_refused(self):
        """A `package` check never passes in a Unity task (the Lab's Unity grader fails it closed on every run), so the
        validator refuses one, required or not (owner, 2026-11-19)."""
        def packaged(t):
            rep = vg.Report()
            self.assertTrue(vg.check_task(rep, 'repo: Tasks', 'x', t, SLUG, None))
            return [m for m in errors(rep) if 'package' in m]
        t = task('a' * 40, 'b' * 40)
        self.assertEqual(packaged(t), [])
        t['milestones'][1]['checks'].append({'name': 'release_packages', 'kind': 'package', 'weight': 0,
                                             'needs': ['player_builds']})
        t['milestones'][1]['checks'].append({'name': 'ships', 'kind': 'package', 'required': False, 'weight': 0})
        self.assertEqual(packaged(t), ["x: check(s) ['release_packages', 'ships']: a Unity task carries no `package` "
                                       "check: the Lab's Unity grader can't package a game and fails it on every run, "
                                       'so no solution passes it: remove it (a repair, never easing; an ask it stood '
                                       'for gets its own probe) (unity-write-tasks section 5)'])

    def test_a_union_with_a_tag_reports_the_shape_its_tag_names(self):
        """A check is told apart by its kind and a measure by its probe: a missing or unknown tag says so and lists
        the ones there are, and anything else is the named shape's own problem, at its own path."""
        def problems(change):
            t = task('a' * 40, 'b' * 40)
            change(t['milestones'][2]['checks'][1])
            return list(vg.check_schema(t, vg.SCHEMAS['game-task']))
        at = '$.milestones[2].checks[1]'
        self.assertEqual(problems(lambda c: c.pop('kind')), [f'{at}: missing "kind"'])
        (wrong,) = problems(lambda c: c.update(kind='probes'))
        self.assertTrue(wrong.startswith(f'{at}.kind: "probes" not one of [') and "'build'" in wrong
                        and "'probe'" in wrong, wrong)
        self.assertEqual(problems(lambda c: c['measure'].pop('probe')), [f'{at}.measure: missing "probe"'])
        (refused,) = problems(lambda c: c['measure'].update(probe='actors'))
        self.assertTrue(refused.startswith(f'{at}.measure.probe: "actors" not one of [') and "'objects'" in refused,
                        refused)
        self.assertEqual(problems(lambda c: c['measure'].update(sample=1)),
                         [f'{at}.measure: unexpected key "sample"'], "the measure's own shape, never 'matches none'")
        self.assertEqual(problems(lambda c: None), [])


# ---- the schema against the contract's examples ----------------------------------------------------------------------
def probe_check(measure, play='look', expect=None):
    return {'name': 'p', 'kind': 'probe', 'describe': 'x', 'play': play, 'measure': measure,
            'expect': expect or {'op': '>=', 'calibrate': 0.5}}


class Schema(unittest.TestCase):
    S = vg.SCHEMAS['game-task']
    KINDS = ('player', 'objects', 'components', 'widgets', 'camera', 'light', 'grading', 'spawns', 'log', 'asset',
             'trace', 'pieces', 'screen', 'audio', 'ground', 'ui', 'drawn', 'render', 'world')   # the probe kinds (contract section 2)
    GRADER_KINDS = ('seen',)   # measures the grader reads from a play's screenshots, never the probe (task-probes.md 2.22)
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
        """Every measure field the contract (section 3) lists, with its prefixed forms, and nothing else: each kind's
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
            'audio': ['count', 'audible', 'volume', 'max_volume', 'level', 'started', 'started_audible', 'sounds',
                      'repeats'],
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
            'spawns': ['spawned', 'destroyed'], 'log': ['count'], 'render': ['draw_calls', 'triangles', 'texture_mb'],
            'world': ['time_scale', 'paused'],
            'trace': ['built_after_last_change', 'played_after_last_change', 'read_before_first_edit',
                      'build_ok_at_end', 'edits_outside_project']}
        # names the contract doesn't use, another kind's fields, a value's other keys, and prefixes without their name
        bad = {'player': ['pawn_on_screen', 'yaw'], 'camera': ['pawn_on_screen', 'roll'],
               'objects': ['bb:Speed', 'actors', 'prop:', 'bone:Hand.x', 'forward:Spot', 'clip:Run', 'world_yaw:.L'],
               'components': ['prop:', 'hidden', 'clip', 'anim:Speed'], 'widgets': ['slate', 'enabled'],
               'ui': ['kind', 'source'], 'screen': ['brightness'], 'light': ['lux', 'local'],
               'grading': ['post:BloomIntensity', 'post:Bloom', 'white_temp', 'post:Vignette.color.rgb',
                           'post:Vignette.color.r.g', 'post:Vignette.color.linear'],
               'pieces': ['actors', 'instances'],
               'audio': ['loudest', 'peak', 'starts', 'starts_total'], 'ground': ['points', 'z'], 'drawn': ['pixels', 'primitives'],
               'asset': ['shader:_BaseColor.q', 'shader:_BaseColor.rgb', 'material:_BaseMap.name.r', 'keyword:',
                         'import:', 'material:'],
               'spawns': ['count'], 'log': ['lines'], 'render': ['batches', 'vertices'], 'world': ['time_dilation', 'speed'],
               'trace': ['built']}
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
        self.assertEqual(sorted(self.MEASURE), sorted(self.KINDS + self.GRADER_KINDS))
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
        for refused in ('pawn', 'actors'):
            self.assertNotEqual(check(refused, 'x'), [])

    def test_contract_shapes(self):
        """Points, near, selects and inputs as the contract (sections 1-4) writes them: every key of each select, every
        input row, and no key the contract doesn't list."""
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
                                  'select': {'name': 'Body'}, 'field': 'count'}),
                ('Select', {'player': False, 'where': [{'prop': 'Foe.dead', 'op': '==', 'value': False},
                                                       {'prop': 'Foe.state', 'op': '!=', 'value': 'Down'}]})):
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
                ('Has', {}), ('Has', {'lit': False}), ('Select', {'player': 'no'}), ('Select', {'where': []}),
                ('Select', {'where': [{'prop': 'Foe.dead', 'op': '=', 'value': 0}]}),
                ('Select', {'inactive': False})):
            self.assertNotEqual(self.ok(value, ref), [], (ref, value))
        inputs = [{'t': 1, 'key': '<Keyboard>/w', 'press': True}, {'t': 1, 'key': '<Keyboard>/leftShift', 'press': True},
                  {'t': 1, 'key': '<Keyboard>/f2', 'press': True}, {'t': 1, 'key': '<Mouse>/leftButton', 'press': True},
                  {'t': 1, 'key': '<Gamepad>/buttonSouth', 'press': False},
                  {'t': 2, 'key': '<Mouse>/delta/x', 'axis': 4.0}, {'t': 2, 'key': '<Gamepad>/leftStick/x', 'axis': 1},
                  {'t': 2, 'key': '<Mouse>/scroll/y', 'axis': -1},
                  {'t': 3, 'widget': 'RetryButton', 'click': True}, {'t': 3, 'widget': 'Retry*', 'click': True},
                  {'t': 3, 'widget': 'Save/Load: 开始!', 'click': True, 'optional': True, 'disabled': True},
                  {'t': 4, 'cursor': [0.5, 0.25]},
                  {'t': 5, 'teleport': [1, 2, 3], 'yaw': 90, 'hold': 2},
                  {'t': 6, 'teleport_to': {'component': 'Ore'}, 'distance': 2.0, 'offset': [0, 0.5, 0],
                   'face': {'object': {'tag': 'Kiln'}}, 'hold': 1},
                  {'t': 7, 'wait': 10}]
        play = {'name': 'route', 'seconds': 30, 'every': 0.5, 'inputs': inputs, 'scene': None, 'args': []}
        self.assertEqual(self.ok(play, 'TaskPlay'), [])
        for bad in ({'t': 1, 'key': 'W', 'press': True}, {'t': 1, 'key': '<Keyboard>/w'},
                    {'t': 1, 'key': '<Joystick>/trigger', 'press': True}, {'t': 1201, 'key': '<Keyboard>/w', 'press': True},
                    {'t': 2, 'key': 'MouseX', 'axis': 4.0}, {'t': 2, 'key': '<Mouse>/delta/x', 'axis': 1001},
                    {'t': 3, 'widget': 'RetryButton', 'click': False}, {'t': 3, 'widget': ' Retry', 'click': True},
                    {'t': 3, 'widget': 'Re\ntry', 'click': True}, {'t': 3, 'widget': 'R' * 121, 'click': True},
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

    def test_a_play_lasts_up_to_1200_seconds(self):
        """A task play and every time in it go up to 1200 s (probe 1.7.0, as the Lab's grader; 300 s before): its
        seconds, an input's t, a hold, a touch's hold and spread, an `at` and an event's within; one more is refused. A
        wait stays 300 s of real time."""
        late = [{'t': 1199, 'key': '<Keyboard>/w', 'press': True}, {'t': 1, 'teleport': [0, 0, 0], 'hold': 1200},
                {'t': 1, 'tap': [0.5, 0.5], 'hold': 1200}, {'t': 1, 'drag': [[0.1, 0.1], [0.9, 0.9]], 'over': 1200},
                {'t': 1198, 'shot': 'late', 'when': {'measure': {'probe': 'objects', 'select': {'name': 'Boss'},
                                                                 'field': 'count'},
                                                     'expect': {'op': '==', 'value': 0}, 'within': 1200}}]
        play = {'name': 'long', 'seconds': 1200, 'inputs': late}
        self.assertEqual(self.ok(play, 'TaskPlay'), [])
        self.assertNotEqual(self.ok(dict(play, seconds=1201), 'TaskPlay'), [])
        for bad in ({'t': 1200.5, 'key': '<Keyboard>/w', 'press': True}, {'t': 1, 'teleport': [0, 0, 0], 'hold': 1201},
                    {'t': 1, 'tap': [0.5, 0.5], 'hold': 1201}, {'t': 1, 'drag': [[0.1, 0.1], [0.9, 0.9]], 'over': 1201}):
            self.assertNotEqual(self.ok(dict(play, inputs=[bad]), 'TaskPlay'), [], bad)
        self.assertNotEqual(self.ok(dict(play, inputs=[{'t': 1, 'wait': 301}]), 'TaskPlay'), [])
        measure = {'probe': 'player', 'field': 'z', 'at': [1199.5]}
        self.assertEqual(self.ok(measure, 'PlayerMeasure'), [])
        self.assertNotEqual(self.ok(dict(measure, at=[1200.5]), 'PlayerMeasure'), [])

    def test_unreal_only_play_and_audio_shapes_are_refused(self):
        """What the Lab's Unity grader does not take of Unreal's grader 1.18.0 and 1.19.0 (its decision 65), refused as
        the Lab refuses it: a play's `attended` (no Unity play is launched with a flag a game reads as an automated
        run), a play's `continues` (a play that names `after` already starts as a new process on what they saved) and
        the audio field `waves` (a start is told by its clip, which `sounds` counts)."""
        play = {'name': 'menu', 'seconds': 20, 'inputs': []}
        self.assertEqual(self.ok(play, 'TaskPlay'), [])
        self.assertNotEqual(self.ok(dict(play, attended=True), 'TaskPlay'), [])
        self.assertNotEqual(self.ok(dict(play, continues='first'), 'TaskPlay'), [])
        self.assertEqual(self.ok({'probe': 'audio', 'field': 'sounds', 'window': [1, 9]}, 'AudioMeasure'), [])
        self.assertNotEqual(self.ok({'probe': 'audio', 'field': 'waves', 'window': [1, 9]}, 'AudioMeasure'), [])

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
        """The limits in metres (contract section 1): a value at its limit passes, one past it fails."""
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
        key that isn't Unity's word for its thing."""
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
        foreign = re.compile(r'\b(actors?|pawns?|UMG|Slate|Blueprints?|Niagara|Cascade|cm|Z up|play_map|uproject)\b|'
                            r'/Game/|`map`', re.I)
        self.assertEqual([m.group(0) for t in texts for m in foreign.finditer(t)], [])
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
        names = sorted(f'{SLUG}-{n}' for n in TASKS)
        for name in names:
            write(tasks_src, f'{name}.json', git(repo, 'show', f'tasks:Tasks/{name}.json'))
        subprocess.run([sys.executable, os.path.join(TOOLS, 'split-tasks.py'), tasks_src, os.path.join(ds, 'Tasks')],
                       check=True, capture_output=True)
        write(ds, 'Tasks/README.md', '# Tasks\n')
        for f in vg.git_ls(repo):
            write(ds, 'UnityProject/' + f, read(os.path.join(repo, f), 'rb'))
        write(ds, 'Build/KilnRun.exe', b'MZ' + b'\0' * 30)
        write(ds, 'Screenshots/hero.jpg', read(os.path.join(repo, 'Docs/screenshots/hero.jpg'), 'rb'))
        write(ds, f'Gameplay/{SLUG}_S1.mp4', b'\0\0\0\x18ftypmp42' + b'\0' * 64)   # a full delivery has a gameplay video
        sections = ['Requirements', 'Package contents', 'Play the game', 'Replay the creation process',
                    'Restore the git history', 'Tasks', 'Scenarios', 'Screenshots', 'Assets and licences', 'Integrity']
        write(ds, 'README.md', '# Kiln Run\n\nThis delivery is pending.\n\n' + ''.join(
            f'## {s}\n\n' + ('![hero](Screenshots/hero.jpg)\n\n' if s == 'Screenshots' else
                             f'1. Rush: Gameplay/{SLUG}_S1.mp4\n\n' if s == 'Scenarios' else 'Text.\n\n') for s in sections))
        files = []
        for d, _, fs in os.walk(ds):
            for f in fs:
                rel = os.path.relpath(os.path.join(d, f), ds).replace('\\', '/')
                if rel.startswith('History/lfs/objects/'):
                    continue
                data = read(os.path.join(d, f), 'rb')
                files.append({'path': rel, 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()})
        m = {'layout': 'unity-dataset-layout/v1', 'game': SLUG, 'title': 'Kiln Run', 'version': '1.0', 'commit': head,
             'status': 'pending', 'variant': 'full', 'pending': ['ReplayScripts'],
             'scenarios': [{'file': f'Gameplay/{SLUG}_S1.mp4', 'scenario': 1, 'name': 'Rush', 'result': 'win', 'seconds': 30}],
             'totals': {'files': len(files), 'bytes': sum(f['bytes'] for f in files)}, 'files': files,
             'replay_verification': None,
             'build': {'config': 'Release', 'commit': head, 'exe': 'Build/KilnRun.exe'},
             'history': {'bundle': f'History/{SLUG}.bundle', 'head': head,
                         'commits': int(git(repo, 'rev-list', '--count', 'main')), 'refs': ['refs/heads/main'],
                         'lfs_objects': n_lfs, 'lfs_bytes': lfs_bytes, 'authors_anonymised': True},
             'brief': {'brief': 'Brief/brief.md', 'design': 'Brief/design.md'},
             'tasks': {'count': len(names), 'names': names, 'schema': 'game-task/1'}}
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
        self.assertIn('5 task(s)', notes)
        self.assertIn('LFS objects referenced', notes)
        if shutil.which('powershell') or shutil.which('pwsh'):
            # The layout check probes gameplay videos with the ffprobe it finds: the machine root's pinned ffmpeg, else
            # PATH. A scratch root keeps the machine's ffmpeg away from the stub video above (the probe is then noted
            # as skipped); an ffprobe on PATH would still probe the stub, which is no video.
            if shutil.which('ffprobe'):
                self.skipTest('an ffprobe on PATH would probe the stub gameplay video')
            with unittest.mock.patch.dict(os.environ, {'UGF_ROOT': self.tmp, 'UGF_CONFIG': os.path.join(self.tmp, 'none.json')}):
                rep = vg.Report()
                vg.run_layout_validator(rep, z, False)
            self.assertEqual(errors(rep), [])
            self.assertTrue(any('PENDING' in m for s, a, m in rep.items), rep.items)

    def test_dataset_errors(self):
        def mutate(m, ds):
            m['tasks']['count'] = 2
            shutil.rmtree(os.path.join(ds, 'Tasks', f'{SLUG}-{TASKS[1]}'))   # four tasks left, two of them medium
            for n, level in ((TASKS[2], 'medium'), (TASKS[3], None)):
                g = os.path.join(ds, 'Tasks', f'{SLUG}-{n}', 'task.json')
                t = dict(json.loads(read(g)), difficulty=level)
                write(ds, os.path.relpath(g, ds).replace('\\', '/'), json.dumps({k: v for k, v in t.items() if v is not None}))
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
                     'banned name (?i)\\bclaude\\b x1', 'Tasks/: 4 task(s): a game ships at least 5',
                     f'Tasks/: 2 hard task(s): a game needs at least 4 hard tasks (medium: {SLUG}-{TASKS[3]}, {SLUG}-{TASKS[2]})'):
            self.assertIn(what, errs)
        self.assertIn('listed asset file not present: Crates: Assets/ThirdParty/Kenney/', errs)
        if shutil.which('powershell') or shutil.which('pwsh'):
            rep = vg.Report()
            vg.run_layout_validator(rep, z, False)
            self.assertIn('UnityProject/ has no ProjectSettings/ProjectVersion.txt', errors(rep))

    def test_gameplay_pending(self):
        """A game without a gameplay video is rejected: a full delivery never lists Gameplay/ as pending (a pending
        ReplayScripts/ stays allowed, as test_valid_dataset has it)."""
        def mutate(m, ds):
            shutil.rmtree(os.path.join(ds, 'Gameplay'))
            m['files'] = [f for f in m['files'] if not f['path'].startswith('Gameplay/')]
            m['totals'] = {'files': len(m['files']), 'bytes': sum(f['bytes'] for f in m['files'])}
            m.update(pending=['ReplayScripts', 'Gameplay'], scenarios=[])
        rep = vg.Report()
        vg.check_dataset(rep, self.make_zip(mutate), 'dataset')
        self.assertEqual(errors(rep), ['Gameplay/ is pending: a game is rejected without a gameplay video; record a scenario '
                                       'of the release commit and package again'])

    def test_cli_with_zip(self):
        self.make_zip()
        r = subprocess.run([sys.executable, os.path.join(TOOLS, 'validate-game.py'), self.repo, '--no-layout'],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


class Mobile(unittest.TestCase):
    """A game's platform (docs/game-format.md, "Platform"): the one reader of Platform.json, rule `mobile` on a mobile
    game's project settings, a mobile dataset's manifest, and the mobile template; a desktop game is not looked at."""

    def game(self, platform=None, settings=None):
        d = tempfile.mkdtemp(prefix='ugfm')
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        if platform is not None:
            write(d, 'Platform.json', platform if isinstance(platform, str) else json.dumps(platform))
        for rel, text in zip((vg.PROJECT_SETTINGS, vg.QUALITY_SETTINGS, vg.GRAPHICS_SETTINGS), settings or ()):
            write(d, rel, text)
        return d

    def said(self, d, files=('Platform.json',)):
        rep = vg.Report()
        vg.check_mobile(rep, d, list(files))
        return errors(rep, 'mobile')

    def test_the_reader(self):
        self.assertIsNone(vg.read_platform(self.game()))
        self.assertEqual(vg.platform_of(self.game()), {'platform': 'desktop'})
        d = self.game({'platform': 'mobile', 'orientation': 'portrait'})
        self.assertEqual(vg.read_platform(d), 'portrait')
        self.assertEqual(vg.platform_of(d), {'platform': 'mobile', 'orientation': 'portrait', 'width': 1080, 'height': 1920})
        self.assertEqual(vg.platform_of(self.game('﻿{"platform": "mobile", "orientation": "landscape"}')),
                         {'platform': 'mobile', 'orientation': 'landscape', 'width': 1920, 'height': 1080})
        for bad in ('{"platform": "desktop"}', '{"platform": "mobile"}', 'not json', '["mobile", "portrait"]',
                    '{"platform": "mobile", "orientation": "sideways"}',
                    '{"platform": "mobile", "orientation": "portrait", "tablet": true}'):
            with self.assertRaises(ValueError, msg=bad):
                vg.read_platform(self.game(bad))
            with self.assertRaises(ValueError, msg=bad):
                vg.platform_said(bad)

    def test_the_reader_from_the_command_line(self):
        tool = os.path.join(TOOLS, 'validate-game.py')
        r = subprocess.run([sys.executable, tool, '--platform', self.game()], capture_output=True, text=True)
        self.assertEqual((r.returncode, json.loads(r.stdout)), (0, {'platform': 'desktop'}))
        r = subprocess.run([sys.executable, tool, '--platform', self.game({'platform': 'mobile', 'orientation': 'landscape'})],
                           capture_output=True, text=True)
        self.assertEqual(json.loads(r.stdout), {'platform': 'mobile', 'orientation': 'landscape', 'width': 1920, 'height': 1080})
        r = subprocess.run([sys.executable, tool, '--platform', self.game('{"platform": "mobile"}')], capture_output=True, text=True)
        self.assertEqual((r.returncode, r.stdout), (2, ''))
        self.assertIn('Platform.json must be', r.stderr)

    def test_a_desktop_game_is_not_looked_at(self):
        self.assertEqual(self.said(self.game(), files=()), [])
        self.assertEqual(self.said(self.game(settings=mobile_settings('portrait')), files=()), [])

    def test_a_mobile_game_as_the_setup_leaves_it_passes(self):
        for orientation in vg.ORIENTATIONS:
            self.assertEqual(vg.mobile_project_errors(orientation, *mobile_settings(orientation)), [])
            d = self.game({'platform': 'mobile', 'orientation': orientation}, mobile_settings(orientation))
            self.assertEqual(self.said(d), [])
        # held on its side, one fixed side is as good as either
        project, quality, graphics = mobile_settings('landscape')
        fixed = project.replace('defaultScreenOrientation: 4', 'defaultScreenOrientation: 3')
        self.assertEqual(vg.mobile_project_errors('landscape', fixed, quality, graphics), [])

    def test_each_setting_that_disagrees_is_named(self):
        project, quality, graphics = mobile_settings('portrait')

        def errs(old, new, orientation='portrait', text='project'):
            texts = {'project': project, 'quality': quality, 'graphics': graphics}
            self.assertIn(old, texts[text])
            texts[text] = texts[text].replace(old, new)
            return vg.mobile_project_errors(orientation, texts['project'], texts['quality'], texts['graphics'])
        self.assertIn('but Platform.json says landscape', errs('m_ObjectHideFlags', 'm_ObjectHideFlags', 'landscape')[0])
        self.assertIn('defaultScreenOrientation is 4', errs('defaultScreenOrientation: 0', 'defaultScreenOrientation: 4')[0])
        self.assertEqual(errs('defaultScreenOrientation: 0', 'defaultScreenOrientation: 4\n  allowedAutorotateToPortrait: 1'), [])
        self.assertIn('with allowedAutorotateToLandscapeLeft on', errs(
            'defaultScreenOrientation: 0', 'defaultScreenOrientation: 4\n  allowedAutorotateToPortrait: 1\n'
            '  allowedAutorotateToLandscapeLeft: 1')[0])
        self.assertIn("package name is 'com.Company.Product'", errs('Android: com.kilnrun.game', 'Android: com.Company.Product')[0])
        self.assertIn('AndroidMinSdkVersion is 25: at least 26', errs('AndroidMinSdkVersion: 26', 'AndroidMinSdkVersion: 25')[0])
        self.assertIn('AndroidTargetSdkVersion is 0: at least 34', errs('AndroidTargetSdkVersion: 34', 'AndroidTargetSdkVersion: 0')[0])
        self.assertIn('arm64 alone', errs('AndroidTargetArchitectures: 2', 'AndroidTargetArchitectures: 3')[0])
        self.assertIn('not IL2CPP', errs('    Android: 1\n', '    Android: 0\n')[0])
        self.assertIn('not Vulkan alone', errs('m_APIs: 15000000', 'm_APIs: 150000000b000000')[0])
        self.assertIn('not Vulkan alone', errs('m_Automatic: 0', 'm_Automatic: 1')[0])
        self.assertIn('opens at 1920x1080', errs('defaultScreenWidth: 1080\n  defaultScreenHeight: 1920',
                                                 'defaultScreenWidth: 1920\n  defaultScreenHeight: 1080')[0])
        self.assertIn('quality levels are Mobile, Ultra', errs(
            '  m_TextureMipmapLimitGroupNames', '  - serializedVersion: 5\n    name: Ultra\n  m_TextureMipmapLimitGroupNames',
            text='quality')[0])
        self.assertIn("is not the project's default one", errs('389207dfd0a67cf4b9cba2d88b7c4666', 'a' * 32, text='graphics')[0])

    def test_a_platform_file_that_says_neither_is_an_error_never_desktop(self):
        for bad in ('{"platform": "desktop"}', '{"platform": "mobile"}', 'not json'):
            self.assertEqual(len(self.said(self.game(bad, mobile_settings()))), 1, bad)

    def test_an_uncommitted_platform_file_and_missing_settings_are_named(self):
        d = self.game({'platform': 'mobile', 'orientation': 'portrait'}, mobile_settings('portrait'))
        self.assertIn('not committed', self.said(d, files=())[0])
        self.assertIn('no ProjectSettings/ProjectSettings.asset', self.said(self.game({'platform': 'mobile', 'orientation': 'portrait'}))[0])

    def test_the_rule_is_one_of_the_games_rules(self):
        d = self.game({'platform': 'mobile', 'orientation': 'portrait'}, mobile_settings('landscape'))
        rep = vg.Report()
        vg.check_rules(rep, d, ['Platform.json'])
        self.assertTrue(errors(rep, 'mobile'))

    # ---- the mobile template -------------------------------------------------------------------------------------------
    OVERLAY = os.path.join(REPO, 'templates', 'unity-game-mobile')
    PLACEHOLDERS = {'__PROJECT__', '__SLUG__', '__TITLE__', '__DESCRIPTION__', '__UNITY_VERSION__', '__ORIENTATION__',
                    '__PORTRAIT__', '__PHONE_WIDTH__', '__PHONE_HEIGHT__', '__ANDROID_NAME__'}

    def test_the_overlay_uses_only_the_placeholders_new_game_fills(self):
        new_game = read(os.path.join(REPO, 'templates', 'new-game.ps1'))
        for d, _, files in os.walk(self.OVERLAY):
            for f in files:
                used = set(re.findall(r'__[A-Z_]+?__', read(os.path.join(d, f)) + f))
                self.assertFalse(used - self.PLACEHOLDERS, f)
        for name in self.PLACEHOLDERS:
            self.assertIn(f"'{name}'", new_game)
        self.assertIn("[ValidateSet('desktop', 'mobile')][string]$Platform = 'desktop'", new_game)
        self.assertIn("[ValidateSet('landscape', 'portrait')][string]$Orientation", new_game)

    def test_the_overlay_adds_files_and_replaces_only_the_readme(self):
        over = {os.path.relpath(os.path.join(d, f), self.OVERLAY).replace('\\', '/')
                for d, _, files in os.walk(self.OVERLAY) for f in files}
        base = {os.path.relpath(os.path.join(d, f), TEMPLATE).replace('\\', '/') for d, _, files in os.walk(TEMPLATE) for f in files}
        self.assertEqual(over & base, {'README.md'})
        self.assertEqual(over - base, {'Assets/Editor/Tools/BuildAndroid.cs', 'Assets/Editor/Tools/Urp/MobileSetup.cs',
                                       'Assets/Scripts/Phone.cs'})

    def test_the_mobile_setup_is_a_fifth_run_the_replay_reads(self):
        """templates/new-game.ps1 adds it to the game's own setup table (machine/lib/ugf-root.ps1
        Add-UGFMobileSetupStep), where the creation replay reads the first open's runs."""
        unity_ps1 = read(os.path.join(TEMPLATE, 'Scripts', 'unity.ps1'))
        lib = read(os.path.join(REPO, 'machine', 'lib', 'ugf-root.ps1'))
        last = "@('configure', @('-executeMethod', '__PROJECT__.EditorTools.ProjectSetup.Configure'), $true)"
        self.assertEqual(unity_ps1.count(last), 1)
        self.assertIn("""$last = "@('configure', @('-executeMethod', '$Project.EditorTools.ProjectSetup.Configure'), `$true)\"""", lib)
        added = "@('mobile', @('-executeMethod', '__PROJECT__.EditorTools.Urp.MobileSetup.Apply'), $true)"
        sys.path.insert(0, os.path.join(TOOLS, 'unity-replay'))   # ledger.py imports its neighbours
        self.addCleanup(sys.path.remove, os.path.join(TOOLS, 'unity-replay'))
        ledger = load('ledger', os.path.join('unity-replay', 'ledger.py'))
        steps, _ = ledger.setup_table(unity_ps1.replace(last, last + ',\n      ' + added))
        self.assertEqual([(name, method.split('.')[-2]) for name, method, _ in steps],
                         [('packages', 'ProjectSetup'), ('urp', 'UrpSetup'), ('text', 'ProjectSetup'),
                          ('configure', 'ProjectSetup'), ('mobile', 'MobileSetup')])

    def test_the_setup_writes_what_the_rule_holds_it_to(self):
        setup = read(os.path.join(self.OVERLAY, 'Assets', 'Editor', 'Tools', 'Urp', 'MobileSetup.cs'))
        self.assertIn(f'MinSdk = {vg.MOBILE_MIN_SDK}, TargetSdk = {vg.MOBILE_TARGET_SDK}', setup)
        self.assertIn(f'Quality = "{vg.MOBILE_QUALITY}"', setup)
        self.assertIn('Package = "com.__ANDROID_NAME__.game"', setup)
        self.assertIn('AndroidArchitecture.ARM64', setup)
        self.assertIn('GraphicsDeviceType.Vulkan', setup)

    # ---- a mobile dataset's manifest ---------------------------------------------------------------------------------
    class View:
        def __init__(self, platform_json=None):
            self.text = platform_json

        def open_text(self, rel):
            if self.text is None:
                raise KeyError(rel)
            return io.StringIO(self.text)

    APK = {'apk': 'KilnRun.apk', 'package': 'com.kilnrun.game', 'version_code': 1, 'version_name': '1.0', 'min_sdk': 26,
           'target_sdk': 34}

    def platform(self, manifest, platform_json=None, files=('Build/KilnRun.apk',)):
        rep = vg.Report()
        m = dict({'variant': 'full', 'build': {'config': 'Release', 'exe': 'Build/KilnRun.exe'}}, **manifest)
        vg.check_dataset_platform(rep, 'dataset', self.View(platform_json), m, set(files))
        return errors(rep), [msg for sev, _, msg in rep.items if sev == 'warning']

    def test_a_desktop_dataset_says_nothing_of_a_platform(self):
        self.assertEqual(self.platform({}), ([], []))
        self.assertEqual(self.platform({'platform': {'kind': 'desktop'}}), ([], []))
        self.assertIn('desktop game', self.platform({'build': dict(self.APK, exe='Build/KilnRun.exe')})[0][0])
        self.assertIn('says mobile, portrait', self.platform({}, '{"platform": "mobile", "orientation": "portrait"}')[0][0])

    def test_a_mobile_dataset_agrees_with_its_project_and_names_its_apk(self):
        mobile = {'platform': {'kind': 'mobile', 'orientation': 'portrait'}}
        held = '{"platform": "mobile", "orientation": "portrait"}'
        self.assertEqual(self.platform(dict(mobile, build=dict(self.APK, exe='Build/KilnRun.exe')), held), ([], []))
        found, warned = self.platform(mobile, held)   # a mobile game is delivered with its APK
        self.assertEqual(warned, [])
        self.assertIn('a mobile game without its APK in Build/', found[0])
        self.assertIn('there is no UnityProject/Platform.json', self.platform(mobile)[0][0])
        self.assertIn('says mobile, landscape', self.platform(mobile, held.replace('portrait', 'landscape'))[0][0])
        self.assertIn('says its orientation', self.platform({'platform': {'kind': 'mobile'}}, held)[0][0])
        for change, why in (({'min_sdk': 24}, 'minSdk 24'), ({'package': 'com.Company.Product'}, 'package name'),
                            ({'apk': 'Other.apk'}, 'not in files[]')):
            build = dict(self.APK, exe='Build/KilnRun.exe', **change)
            self.assertIn(why, self.platform(dict(mobile, build=build), held)[0][0], change)
        del build['target_sdk']
        self.assertIn('without target_sdk', self.platform(dict(mobile, build=dict(build, apk='KilnRun.apk')), held)[0][0])

    def test_the_manifest_schema_takes_a_platform_and_an_apk(self):
        schema = vg.SCHEMAS['dataset-manifest']['properties']
        self.assertEqual(list(vg.check_schema({'kind': 'mobile', 'orientation': 'portrait'}, schema['platform'])), [])
        self.assertTrue(list(vg.check_schema({'kind': 'phone'}, schema['platform'])))
        build = dict(self.APK, config='Release', commit='a' * 40, exe='Build/KilnRun.exe')
        self.assertEqual(list(vg.check_schema(build, schema['build'], vg.SCHEMAS['dataset-manifest'])), [])
        self.assertTrue(list(vg.check_schema(dict(build, apk='Build/KilnRun.apk'), schema['build'], vg.SCHEMAS['dataset-manifest'])))


if __name__ == '__main__':
    unittest.main()
