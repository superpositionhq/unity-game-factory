"""Machine root for Python tools (task check, packaging, ...); same rules as machine/lib/ugf-root.ps1.

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


def config_path():
    return os.environ.get("UGF_CONFIG") or os.path.join(os.path.expanduser("~"), ".unity-game-factory", "config.json")


def config():
    p = config_path()
    if os.path.isfile(p):
        with open(p, encoding="utf-8-sig") as f:
            return json.load(f)
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


def unity_editor(project=None):
    """Unity.exe for a project, as ugf-root.ps1 Get-UGFUnity (keep the two in step): the exact version its
    ProjectVersion.txt names, else unity_version(). Exits naming what to install when it is missing."""
    import sys
    ver = project_unity_version(project) or unity_version()
    exe = unity_for_version(ver)
    if not exe:
        if ver:
            what = ("Unity %s is not installed: install it through Unity Hub (Installs > Install Editor, or Archive for "
                    "an older patch: version %s" % (ver, ver))
        else:
            series = config().get("unity_version") or DEFAULT_UNITY_VERSION
            what = ("no Unity %s editor is installed: install the newest %s patch through Unity Hub (Installs > "
                    "Install Editor" % (series, series))
        sys.exit("%s, with Windows Build Support (IL2CPP)), or name its Unity.exe in unity_editors in %s"
                 % (what, config_path()))
    return exe


def org():
    """GitHub organisation (or user) owning unity-game-factory and the unity-game-<slug> repos: env UGF_ORG, else
    "github_org" in the config file (bootstrap.ps1 -Org writes it), else ""."""
    return (os.environ.get("UGF_ORG") or config().get("github_org") or "").strip()


def out():
    """Output root for packages and dataset zips: env UGF_OUT, else "out" in the config file, else <root>/deliverables."""
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
    res = {}
    for k in ("heavy_slots", "gpu_slots"):
        try:
            v = int(c.get(k) or 0)
        except (TypeError, ValueError):
            v = 0
        if v <= 0:
            comp = comp or computed_slots()
            v = comp[k]
        res[k] = v
    return res


def root():
    if os.environ.get("UGF_ROOT"):
        return os.path.abspath(os.environ["UGF_ROOT"])
    p = config_path()
    if os.path.isfile(p):
        with open(p, encoding="utf-8-sig") as f:
            r = json.load(f).get("root")
        if r:
            return os.path.abspath(r)
    return os.path.join(os.path.expanduser("~"), "UnityWork")
