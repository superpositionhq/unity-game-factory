"""A commit of the game as a project folder outside its repo, for the checker to build and play.

- materialize: the game's files at a commit, exactly as committed, read straight from its repository (git objects, and
  the Git LFS objects in its local store), written into a scratch folder; each LFS file is a hardlink of its object when
  the folder is on the repo's volume (it costs no disk), else a copy. Nothing in the repo is written or checked out, and
  nothing from another commit is added: a task is built exactly as committed (no port, no patch).
- what a task's agent never sees is left out (ANSWERS): Tasks/, History/, Dataset/ and Dataset.zip at the root.
- add_probe: the TaskProbe package as an embedded package, Packages/com.taskprobe/ (Unity loads every folder under
  Packages/ that holds a package.json, so Packages/manifest.json and the rest of the game's files stay exactly as
  committed). The only thing the checker adds.
- check_length: Unity fails on paths past 260 characters, and a project's own deepest paths (Library/PackageCache,
  Library/Bee) take most of that, so a scratch project folder is at most MAX_FOLDER characters long.
Assets a played scene names that the commit doesn't hold (e.g. a store pack committed only later) are found by the
build (unity.py, its result's `missing`): a fault of the task's commit, which the checker reports and never fills in."""

import hashlib
import os
import re
import shutil
import stat
import subprocess
from pathlib import Path

LFS_POINTER = re.compile(rb"^version https://git-lfs\.github\.com/spec/v1\noid sha256:([0-9a-f]{64})\nsize (\d+)\n")
POINTER_MAX = 300  # bytes: a Git LFS pointer is smaller (about 130)
PROBE = "Packages/com.taskprobe"
PROBE_SOURCE = Path(__file__).resolve().parent / "TaskProbe"
PROBE_JUNK = ("obj", "bin", ".vs", "__pycache__")  # build leftovers an IDE may leave in the package's folder
ANSWERS = ("tasks", "history", "dataset", "dataset.zip")  # never materialized (case-insensitive, at the root)
ENGINE = "6000.3"
VERSION_FILE = "ProjectSettings/ProjectVersion.txt"
MAX_FOLDER = 90  # characters: the longest scratch project folder (Unity fails past 260-character paths)


class WrongEngine(ValueError):
    """A start that isn't a Unity 6000.3 project as committed."""


class PathTooLong(ValueError):
    """A scratch project folder too long for Unity's 260-character paths."""


def _git(repo, *args, data=None):
    found = subprocess.run(["git", "-C", str(repo), *args], input=data, capture_output=True, check=False)
    if found.returncode != 0:
        raise RuntimeError(f"git {args[0]} in {Path(repo).name} failed: {found.stderr.decode(errors='replace')[:300]}")
    return found.stdout


def resolve(repo, commit):
    """The full sha of `commit` in `repo`."""
    return _git(repo, "rev-parse", "--verify", f"{commit}^{{commit}}").decode().strip()


def lfs_store(repo):
    """Where a repository keeps its Git LFS objects: its lfs.storage, else .git/lfs/objects (lfs/objects when bare)."""
    repo = Path(repo)
    found = subprocess.run(["git", "-C", str(repo), "config", "--get", "lfs.storage"], capture_output=True, text=True)
    if found.returncode == 0 and found.stdout.strip():
        base = Path(found.stdout.strip())
        base = base if base.is_absolute() else Path(_git(repo, "rev-parse", "--absolute-git-dir").decode().strip()) / base
        return base / "objects" if (base / "objects").is_dir() else base
    git_dir = Path(_git(repo, "rev-parse", "--absolute-git-dir").decode().strip())
    common = _git(repo, "rev-parse", "--git-common-dir").decode().strip()
    common = Path(common) if os.path.isabs(common) else (Path(repo) / common).resolve()
    for base in (common, git_dir):
        if (base / "lfs" / "objects").is_dir():
            return base / "lfs" / "objects"
    return common / "lfs" / "objects"


def answer(path):
    """Whether a project-relative path (posix) is under ANSWERS."""
    return path.split("/", 1)[0].lower() in ANSWERS


def place(stored, target, link=True):
    """`target` as a hardlink of the LFS object `stored` (a copy across volumes or when `link` is off)."""
    if link:
        try:
            os.link(stored, target)
            return "linked"
        except OSError:
            pass
    shutil.copyfile(stored, target)
    return "copied"


def materialize(repo, commit, dest, link=True):
    """Write the files of `repo` at `commit` into `dest` (which must not exist), each Git LFS pointer replaced by its
    object from the repo's LFS store (hardlinked when `link` and the volume allows, else copied), and none of ANSWERS.
    Raises FileNotFoundError when an object isn't in the local store (`git lfs fetch` it first). {"files", "linked",
    "copied", "objects"}."""
    repo, dest = Path(repo), Path(dest)
    if dest.exists():
        raise FileExistsError(dest)
    listing = _git(repo, "ls-tree", "-r", "-z", "--full-tree", commit).split(b"\0")
    entries = []
    for line in listing:
        if not line:
            continue
        meta, path = line.split(b"\t", 1)
        mode, kind, oid = meta.split()
        path = path.decode("utf-8")
        if kind == b"blob" and not answer(path):
            entries.append((path, oid.decode()))
    lfs = lfs_store(repo)
    counts = {"files": 0, "linked": 0, "copied": 0, "objects": {}}  # objects: LFS sha -> its file in the store
    missing = []
    with subprocess.Popen(["git", "-C", str(repo), "cat-file", "--batch"], stdin=subprocess.PIPE,
                          stdout=subprocess.PIPE) as batch:
        for path, oid in entries:
            batch.stdin.write(oid.encode() + b"\n")
            batch.stdin.flush()
            header = batch.stdout.readline().split()
            size = int(header[2])
            data = batch.stdout.read(size)
            batch.stdout.read(1)  # the newline after each object
            target = dest / path
            target.parent.mkdir(parents=True, exist_ok=True)
            pointer = LFS_POINTER.match(data) if size < POINTER_MAX else None
            counts["files"] += 1
            if pointer:
                sha = pointer.group(1).decode()
                stored = lfs / sha[:2] / sha[2:4] / sha
                if not stored.is_file():
                    missing.append(path)
                    continue
                counts[place(stored, target, link)] += 1
                counts["objects"][sha] = stored
            else:
                target.write_bytes(data)
        batch.stdin.close()
    if missing:
        raise FileNotFoundError(f"{len(missing)} Git LFS object(s) of {commit[:12]} aren't in {repo.name}'s local store "
                                f"(e.g. {missing[0]}): run `git -C {repo} lfs fetch origin {commit}` first")
    return counts


def engine_of(project):
    """m_EditorVersion of the project's ProjectSettings/ProjectVersion.txt ("6000.3.26f1"); "" without one."""
    path = Path(project) / VERSION_FILE
    if not path.is_file():
        return ""
    found = re.search(r"^\s*m_EditorVersion:\s*(\S+)", path.read_text(encoding="utf-8-sig", errors="replace"), re.M)
    return found.group(1) if found else ""


def add_probe(project):
    """Add the TaskProbe package to `project` as Packages/com.taskprobe/. Raises WrongEngine when the project isn't a
    Unity 6000.3 project: a task starts from a commit that builds on 6000.3 as committed."""
    project = Path(project)
    engine = engine_of(project)
    if engine.split(".")[:2] != ENGINE.split("."):
        raise WrongEngine(f"{VERSION_FILE} names Unity {engine or '?'}: a task's commits must be Unity {ENGINE} "
                          "projects as committed")
    target = project / PROBE
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(PROBE_SOURCE, target, ignore=shutil.ignore_patterns(*PROBE_JUNK))
    return project


def too_long(folder):
    """Why `folder` can't hold a scratch project (longer than MAX_FOLDER characters), or None."""
    length = len(str(Path(folder).absolute()))
    if length <= MAX_FOLDER:
        return None
    return (f"the scratch project folder {Path(folder).absolute()} is longer than {MAX_FOLDER} characters ({length}): "
            "Unity fails on paths past 260 characters and a project's own deepest paths take the rest; pass --scratch "
            "with a short folder on the repo's drive (e.g. --scratch C:\\tc)")


def check_length(folder):
    """Raises PathTooLong when `folder` is too long for a scratch project."""
    why = too_long(folder)
    if why:
        raise PathTooLong(why)
    return Path(folder)


LIBRARY = "Library"
LIBRARY_LEFT = ("TaskProbe", "Bee", "ScriptAssemblies", "PlayerDataCache", "PlayerScriptAssemblies", "BuildPlayerData",
                "StateCache", "il2cpp_cache", "BurstCache")  # of the other copy's code and builds: made again here


def seed_library(donor, project):
    """Unity's import cache (Library/) of the built scratch copy `donor`, copied into `project` when it has none yet,
    so its first build imports only the assets that differ. The cache is keyed by each asset's content and import
    settings, and is never part of the game: both copies stay exactly as committed. What belongs to the other copy's
    code and builds is left out (compiled scripts, build caches). False when there was nothing to copy or it failed
    (the copy then imports everything itself, as before)."""
    source, target = Path(donor) / LIBRARY, Path(project) / LIBRARY
    if not source.is_dir() or target.exists():
        return False

    def skip(folder, names):
        return [n for n in names if n in LIBRARY_LEFT] if Path(folder) == source else []

    try:
        shutil.copytree(source, target, ignore=skip)
    except (OSError, shutil.Error):
        shutil.rmtree(target, ignore_errors=True)
        return False
    return True


SAVES = re.compile(r"TaskProbe[._][0-9a-f]{12}")  # the only names forget_saves ever deletes


def saves_company(project):
    """The company name the probe's build gives a scratch copy's player (TaskProbe/Editor/Build.cs `Tag`): "TaskProbe."
    and 12 hex digits of its folder's sha256. A play's saved data (PlayerPrefs in the registry, the persistent data
    folder) goes under that name, never under the real game's, and the probe clears it when a play starts."""
    folder = os.path.abspath(str(project)).lower()
    return "TaskProbe." + hashlib.sha256(folder.encode("utf-8")).hexdigest()[:12]


def _saves_folders():
    """(LocalLow, the temp folder) as Windows gives them to a player, None for one it doesn't. LocalLow is the known
    folder, which no environment variable moves (taken from USERPROFILE, it was "~", a relative path, with that
    unset); the temp folder is GetTempPathW's, from the environment the player inherits."""
    import ctypes
    from ctypes import wintypes

    class Guid(ctypes.Structure):
        _fields_ = [("data1", ctypes.c_uint32), ("data2", ctypes.c_uint16), ("data3", ctypes.c_uint16),
                    ("data4", ctypes.c_ubyte * 8)]

    local_low = Guid(0xA520A1A4, 0x1780, 0x4FF6, (ctypes.c_ubyte * 8)(0xBD, 0x18, 0x16, 0x73, 0x43, 0xC5, 0xAF, 0x16))
    shell32, ole32, kernel32 = ctypes.WinDLL("shell32"), ctypes.WinDLL("ole32"), ctypes.WinDLL("kernel32")
    shell32.SHGetKnownFolderPath.argtypes = [ctypes.POINTER(Guid), wintypes.DWORD, wintypes.HANDLE,
                                             ctypes.POINTER(ctypes.c_void_p)]
    shell32.SHGetKnownFolderPath.restype = ctypes.c_long
    ole32.CoTaskMemFree.argtypes = [ctypes.c_void_p]
    kernel32.GetTempPathW.argtypes = [wintypes.DWORD, wintypes.LPWSTR]
    kernel32.GetTempPathW.restype = wintypes.DWORD
    found = ctypes.c_void_p()
    failed = shell32.SHGetKnownFolderPath(ctypes.byref(local_low), 0, None, ctypes.byref(found))
    low = None if failed else ctypes.wstring_at(found.value)
    ole32.CoTaskMemFree(found)  # whether it found the folder or not
    buffer = ctypes.create_unicode_buffer(32768)
    return low, buffer.value if kernel32.GetTempPathW(len(buffer), buffer) else None


def _drop_folder(parent, name):
    """The folder `name` in `parent` deleted when `name` is of SAVES' form and `parent` an absolute path: nothing else.
    rmtree never goes through a link (it refuses a junction or symlink, and unlinks those inside without following)."""
    if parent and os.path.isabs(parent) and SAVES.fullmatch(name):
        shutil.rmtree(os.path.join(parent, name), ignore_errors=True)


def _drop_key(root, name):
    """The registry key `name` under `root` deleted with every key under it, as far as it can be. Each key's subkeys are
    listed once (one that couldn't be deleted kept the walk going for ever), and a symbolic link is neither followed
    nor deleted: through one, the walk deleted its target, a key that isn't the company's."""
    import winreg

    try:
        with winreg.OpenKey(root, name, winreg.REG_OPTION_OPEN_LINK, winreg.KEY_READ) as key:
            try:
                winreg.QueryValueEx(key, "SymbolicLinkValue")
                return  # a link
            except OSError:
                pass
            subkeys = []
            while True:
                try:
                    subkeys.append(winreg.EnumKey(key, len(subkeys)))
                except OSError:
                    break
            for subkey in subkeys:
                _drop_key(key, subkey)
        winreg.DeleteKey(root, name)
    except OSError:
        pass  # not there, or not ours to delete


def forget_saves(project):
    """What the plays of the scratch copy `project` left outside it, under its company name: its PlayerPrefs (the
    registry key HKCU\\Software\\<company>), its persistent data and temporary cache (<company> with its dot as an
    underscore, as Unity writes those folders, in LocalLow and in the temp folder) and its crash handler's reports (the
    temp folder's <company>, dot kept). Only a name of SAVES' form directly under one of those three is ever deleted."""
    company = saves_company(project)
    if os.name != "nt" or not SAVES.fullmatch(company):
        return
    import winreg

    _drop_key(winreg.HKEY_CURRENT_USER, "Software\\" + company)
    low, temp = _saves_folders()
    for parent, name in ((low, company.replace(".", "_")), (temp, company.replace(".", "_")), (temp, company)):
        _drop_folder(parent, name)


def _projects(path, depth=3):
    """The Unity projects at or under `path`, down to `depth` folders."""
    path = Path(path)
    if (path / "ProjectSettings" / "ProjectVersion.txt").is_file():
        return [path]
    if depth <= 0 or not path.is_dir():
        return []
    found = []
    try:
        for child in path.iterdir():
            if child.is_dir() and not child.is_symlink():
                found += _projects(child, depth - 1)
    except OSError:
        pass
    return found


def remove(path):
    """`path` removed, read-only files included, and with a scratch copy the saved data its plays left outside it."""

    def writable(func, target, _):
        os.chmod(target, stat.S_IWRITE)
        func(target)

    if Path(path).exists():
        for project in _projects(path):
            forget_saves(project)
        shutil.rmtree(path, onexc=writable)

