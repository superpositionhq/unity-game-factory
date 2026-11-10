"""What a task's thread is made of in a Unity game repo: which files are the game, which lines are code, which system a
file belongs to, and the floors every task meets (unity-write-tasks skill, sections 1 and 6). Shared by
thread-stats.py and the task validator, so both count the same way. Standard library only."""

import re

# The bar every task meets: only long threads of multiple edits qualify (unity-write-tasks sections 1, 6)
MIN_OUTCOME_PROBES = 3      # required probes outside still_works: one per issue the thread settled
MIN_THREAD_FILES = 5        # game files the reference changes against the start
MIN_THREAD_COMMITS = 4      # commits from seed.commit to seed.reference that change the game (a seed on main)
MIN_THREAD_CODE_LINES = 100   # code lines added plus removed from start to reference
MIN_THREAD_SYSTEMS = 2        # systems the change crosses, as thread_system counts them

# The game itself: Assets/ (scripts, scenes, prefabs, data, art), Packages/ (manifest, lock, embedded packages) and
# ProjectSettings/. A .meta file only follows its asset (GUID, import settings), so it never counts as a file of its
# own; its asset does.
GAME_FILE = re.compile(r'^(Assets|Packages|ProjectSettings)/(?!.*\.meta$)')
GAME_PATHS = ('Assets', 'Packages', 'ProjectSettings', ':(exclude)*.meta')   # git pathspecs
CODE_FILE = re.compile(r'\.(cs|shader|hlsl|cginc|compute|uss|uxml|asmdef|asmref|py|ps1|bat|cmd|sh|js)$', re.I)
NOT_CODE_DIR = re.compile(r'^(Dataset|Docs|RawAssets)/|/ThirdParty/')   # store packs' own code is not the thread's

MATERIAL_EXT = ('.mat', '.shadergraph', '.shadersubgraph', '.png', '.jpg', '.jpeg', '.tga', '.psd', '.exr', '.hdr',
                '.tif', '.tiff')
ANIM_EXT = ('.anim', '.controller', '.overridecontroller', '.mask', '.playable', '.signal')


def thread_system(path):
    """Which system a changed game file belongs to, by its folder and extension."""
    low = path.lower()
    name = low.rsplit('/', 1)[-1]
    if low.startswith(('projectsettings/', 'packages/')):
        return 'config'
    if low.endswith(('.cs', '.asmdef', '.asmref')):
        return 'editor-code' if '/editor/' in low else 'code'
    if low.endswith(('.shader', '.hlsl', '.cginc', '.compute')):
        return 'shader'
    if low.endswith('.unity'):
        return 'scene'
    if low.endswith('.prefab'):
        return 'prefab'
    if low.endswith(MATERIAL_EXT):
        return 'material'
    if low.endswith(ANIM_EXT):
        return 'animation'
    if low.endswith(('.uxml', '.uss', '.tss')) or '/ui/' in low or name.startswith('ui_'):
        return 'ui'
    if low.endswith(('.mixer', '.wav', '.ogg', '.mp3', '.aif', '.aiff', '.flac')):
        return 'audio'
    if low.endswith(('.asset', '.json', '.txt', '.csv')):
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
