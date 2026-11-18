"""Machine root for Python tools (task-check, task-try, ...); same rules as machine/lib/ugf-root.ps1.

Order: env UGF_ROOT, then "root" in the config file (env UGF_CONFIG, else %USERPROFILE%/.unity-game-factory/config.json),
then %USERPROFILE%/UnityWork.

Use from a script in the repo:
    sys.path.insert(0, os.path.join(<unity-game-factory>, "machine", "lib")); import ugfroot; ugfroot.root()
"""
import json
import os
import re

DEFAULT_UNITY_VERSION = "6000.3"   # Unity 6.3 LTS: new games use its newest installed patch, as ugf-root.ps1
DEFAULT_HUB_EDITORS = "C:/Program Files/Unity/Hub/Editor"
# a Unity version as Unity names its releases: 6000.3.28f1 (major, minor, patch, the release's letter, its number)
UNITY_VERSION = re.compile(r"^(\d+)\.(\d+)\.(\d+)([abfp])(\d+)$")
RELEASES = "abfp"  # alpha, beta, final, patch: in the order Unity releases them
LINE = "6000.3"  # the line whose project a newer patch of it opens (unity_opening); any other only on its own patch


def config_path():
    return os.environ.get("UGF_CONFIG") or os.path.join(os.path.expanduser("~"), ".unity-game-factory", "config.json")


def config():
    p = config_path()
    if os.path.isfile(p):
        with open(p, encoding="utf-8-sig") as f:
            try:
                return json.load(f)
            except ValueError as e:   # a path typed with single backslashes is the usual cause
                import sys
                sys.exit("%s is not valid JSON (%s): write a Windows path in it with doubled backslashes or forward "
                         "slashes" % (p, e))
    return {}


def project_unity_version(project):
    """m_EditorVersion of <project>/ProjectSettings/ProjectVersion.txt ("6000.3.26f1"); "" without one."""
    pv = os.path.join(project or "", "ProjectSettings", "ProjectVersion.txt")
    if not project or not os.path.isfile(pv):
        return ""
    with open(pv, encoding="utf-8-sig") as f:
        for line in f:
            m = re.match(r"\s*m_EditorVersion:\s*(\S+)", line)
            if m:
                return m.group(1)
    return ""


def version_key(version):
    """A Unity version ("6000.3.28f1") as a tuple that orders as Unity's releases do: the three numbers, then the
    release's letter (a < b < f < p) and its number, so 6000.3.28f1 > 6000.3.26f1 > 6000.3.9f1. None for a text that
    isn't a Unity version."""
    found = UNITY_VERSION.match((version or "").strip())
    if found is None:
        return None
    major, minor, patch, letter, number = found.groups()
    return int(major), int(minor), int(patch), RELEASES.index(letter), int(number)


def line_of(version):
    """The line a Unity version is of ("6000.3" for 6000.3.28f1): its first two numbers."""
    return ".".join((version or "").strip().split(".")[:2])


def installed_unity():
    """{version: Unity.exe} of every editor installed: <unity_hub_editors>/<version>/Editor/Unity.exe and every
    "unity_editors" entry that is a file, as ugf-root.ps1 Get-UGFInstalledUnity. Forward slashes."""
    c = config()
    hub = (c.get("unity_hub_editors") or DEFAULT_HUB_EDITORS).replace("\\", "/").rstrip("/")
    found = {d: "%s/%s/Editor/Unity.exe" % (hub, d) for d in (os.listdir(hub) if os.path.isdir(hub) else [])
             if os.path.isfile("%s/%s/Editor/Unity.exe" % (hub, d))}
    found.update({d: p.replace("\\", "/") for d, p in (c.get("unity_editors") or {}).items()
                  if p and os.path.isfile(p)})
    return found


def unity_opening(version):
    """(the editor's version, its Unity.exe) that opens a project naming Unity `version`, as ugf-root.ps1
    Get-UGFUnityOpening (keep the two in step): the exact patch when it is installed; else the newest installed
    editor of the same line (6000.3) at or above it, an upgrade within one LTS line, never an older editor; a project
    of another line only on its own patch. ("", "") when there is none."""
    exe = unity_for_version(version)
    if exe or version_key(version) is None or line_of(version) != LINE:
        return (version, exe) if exe else ("", "")
    want = version_key(version)
    above = [(version_key(v), v, p) for v, p in installed_unity().items()
             if line_of(v) == line_of(version) and version_key(v) is not None and version_key(v) >= want]
    return max(above)[1:] if above else ("", "")


def higher(*versions):
    """The highest of `versions` of the first one's line (version_key); the first one when no other is higher or none
    is a Unity version."""
    first = versions[0] if versions else ""
    same = [v for v in versions if version_key(v) is not None and line_of(v) == line_of(first)]
    return max(same, key=version_key) if same and version_key(first) is not None else first


def unity_for_version(version):
    """Unity.exe for an exact version: "unity_editors" in the config, else <unity_hub_editors>/<version>/Editor/Unity.exe;
    "" when not installed. Forward slashes."""
    if not version:
        return ""
    c = config()
    p = (c.get("unity_editors") or {}).get(version)
    if p and os.path.isfile(p):
        return p.replace("\\", "/")
    hub = (c.get("unity_hub_editors") or DEFAULT_HUB_EDITORS).replace("\\", "/").rstrip("/")
    p = "%s/%s/Editor/Unity.exe" % (hub, version)
    return p if os.path.isfile(p) else ""


def unity_version():
    """The editor version new games use, as ugf-root.ps1 Get-UGFUnityVersion (keep the two in step): "unity_version" in
    the config, default 6000.3 (Unity 6.3 LTS). A series ("6000.3") means its newest installed final patch; an exact
    version ("6000.3.28f1") pins it. "" when no editor of the series is installed."""
    c = config()
    v = str(c.get("unity_version") or DEFAULT_UNITY_VERSION)
    if not re.fullmatch(r"\d+\.\d+", v):
        return v
    hub = (c.get("unity_hub_editors") or DEFAULT_HUB_EDITORS).replace("\\", "/").rstrip("/")
    have = [d for d in (os.listdir(hub) if os.path.isdir(hub) else [])
            if os.path.isfile("%s/%s/Editor/Unity.exe" % (hub, d))]
    have += [d for d, p in (c.get("unity_editors") or {}).items() if p and os.path.isfile(p)]
    finals = [(int(m.group(1)), int(m.group(2)), d) for d in have
              for m in [re.fullmatch(re.escape(v) + r"\.(\d+)f(\d+)", d)] if m]
    return max(finals)[2] if finals else ""


def unity_editor(project=None, at_least=None):
    """Unity.exe for a project, as ugf-root.ps1 Get-UGFUnity (keep the two in step): the editor that opens the version
    its ProjectVersion.txt names (unity_opening: that patch, else the newest installed one of its line above it), else
    unity_version(). `at_least`: another version of the same line the same editor must open too (the other side of a
    task): the editor is then the one for the higher of the two. Exits naming what to install when there is none."""
    return unity_editor_and_version(project, at_least)[1]


def unity_editor_and_version(project=None, at_least=None):
    """(the editor's version, its Unity.exe) of unity_editor."""
    import sys
    ver = project_unity_version(project) or unity_version()
    if ver and at_least:
        ver = higher(ver, at_least)
    have, exe = unity_opening(ver)
    if not exe:
        if ver and version_key(ver) is not None and line_of(ver) == LINE:
            what = ("Unity %s is not installed, nor any newer %s patch: install it or a newer %s patch through Unity "
                    "Hub (Installs > Install Editor, or Archive for an older patch: version %s"
                    % (ver, line_of(ver), line_of(ver), ver))
        elif ver:
            what = ("Unity %s is not installed: install it through Unity Hub (Installs > Install Editor, or Archive for "
                    "an older patch: version %s" % (ver, ver))
        else:
            series = config().get("unity_version") or DEFAULT_UNITY_VERSION
            what = ("no Unity %s editor is installed: install the newest %s patch through Unity Hub (Installs > "
                    "Install Editor" % (series, series))
        sys.exit("%s, with Windows Build Support (IL2CPP)), or name its Unity.exe in unity_editors in %s"
                 % (what, config_path()))
    return have, exe


def org():
    """GitHub organisation (or user) owning unity-game-factory and the unity-game-<slug> repos: env UGF_ORG, else
    "github_org" in the config file (bootstrap.ps1 -Org writes it), else ""."""
    return (os.environ.get("UGF_ORG") or config().get("github_org") or "").strip()


def out():
    """Output root for packages: the creation replay's, and the dataset packager's commit maps, audit files and run
    lock (its zip goes next to the game repo unless --out). Env UGF_OUT, else "out" in the config file, else
    <root>/deliverables."""
    o = os.environ.get("UGF_OUT") or config().get("out")
    return os.path.abspath(o) if o else os.path.join(root(), "deliverables")


def check_free(path, what="this job"):
    """Exit when the drive holding path has less free than the floor (env UGF_MIN_FREE_GB, else "min_free_gb" in the
    config file, else 50 GB): a disk that fills mid-job corrupts the result. Returns the free GB."""
    import shutil
    import sys
    floor = float(os.environ.get("UGF_MIN_FREE_GB") or config().get("min_free_gb") or 50)
    p = os.path.abspath(path)
    while not os.path.exists(p) and os.path.dirname(p) != p:
        p = os.path.dirname(p)
    free = shutil.disk_usage(p).free / 2 ** 30
    if free < floor:
        sys.exit("%s: only %.1f GB free on %s (floor %.0f GB; UGF_MIN_FREE_GB / min_free_gb). Free space or move "
                 "--scratch (the task check and the task try) / UGF_OUT (packages) to another drive."
                 % (what, free, os.path.splitdrive(p)[0] or p, floor))
    return free


def computed_slots():
    """The hardware formula of ugf-root.ps1 Get-UGFComputedSlots (keep the two in step):
    heavy_slots = clamp(1..8, min((RAM GB - 6) // 6, logical cores // 4, (commit limit GB - 6) // 8)),
    gpu_slots = clamp(1..4, min(VRAM GB of the largest NVIDIA GPU // 4, heavy_slots - 1)); 1 without nvidia-smi."""
    import ctypes
    import subprocess

    class MS(ctypes.Structure):
        _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong), ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong), ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong), ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong), ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
    ms = MS()
    ms.dwLength = ctypes.sizeof(MS)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(ms))
    ram, commit = ms.ullTotalPhys / 2 ** 30, ms.ullTotalPageFile / 2 ** 30
    heavy = int(max(1, min(8, (ram - 6) // 6, (os.cpu_count() or 4) // 4, (commit - 6) // 8)))
    try:
        out = subprocess.run(["nvidia-smi", "--query-gpu=memory.total", "--format=csv,noheader,nounits"],
                             capture_output=True, text=True).stdout
        vram = max([int(x) for x in out.split() if x.strip().isdigit()] or [0])
    except OSError:
        vram = 0
    gpu = int(max(1, min(4, vram // 1024 // 4, heavy - 1))) if vram else 1
    return {"heavy_slots": heavy, "gpu_slots": gpu}


def slot_plan():
    """heavy_slots / gpu_slots in effect: the config's keys, else computed_slots()."""
    c = config()
    comp = None
    out = {}
    for k in ("heavy_slots", "gpu_slots"):
        try:
            v = int(c.get(k) or 0)
        except (TypeError, ValueError):
            v = 0
        if v <= 0:
            comp = comp or computed_slots()
            v = comp[k]
        out[k] = v
    return out


def root():
    if os.environ.get("UGF_ROOT"):
        return os.path.abspath(os.environ["UGF_ROOT"])
    r = config().get("root")
    if r:
        return os.path.abspath(r)
    return os.path.join(os.path.expanduser("~"), "UnityWork")
