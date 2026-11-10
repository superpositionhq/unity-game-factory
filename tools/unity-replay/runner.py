"""prepare / run / dump / status for the Unity creation replay (see docs/unity-replay.md).

The replay project is a private clone of the game repo (objects shared, Git LFS reading the game's own store), checked
out at the first commit. `run` walks the ledger's windows: the inputs from the commit (code, text, source art, package
manifest and lock), the GUID of every new input file's .meta from the commit (its import settings come from the
replay's own import), the code as it stood when each step ran, store-pack drops and shell steps at their recorded
positions, every editor step headless through unity-heavy.ps1, then the boundary: the GUIDs of what the replay created
are given the commit's (asset identity, never content), and content no replayed step produced is taken from the commit
and listed. Resumable: work/state.json; a work/STOP file pauses it cleanly between steps.
"""
import datetime
import glob
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time

import unity_replay

HERE = os.path.dirname(os.path.abspath(__file__))
TOOL_SRC = os.path.join(HERE, "editor")
TOOL_DIR = "Assets/CreationReplayTools"   # the editor tools, put into a project for one run and removed after it
TOOL_FILES = ("CreationReplay.Editor.asmdef", "ReplayDump.cs", "ReplayWorld.cs")
SCAN_ROOTS = ("Assets", "ProjectSettings")
COMPILER_ERROR = re.compile(r"\berror CS\d+\b|Scripts have compiler errors")
CRASH = re.compile(r"Crash!!!|Native Crash Reporting|Received signal SIG|=================================================================\s*\n\s*Native")
GUID_LINE = re.compile(rb"^guid: ([0-9a-f]{32})\s*$", re.M)
IDENTITY_KEYS = ("productGUID",)   # ProjectSettings values Unity sets at random when a project is made


def heavy_path():
    return os.path.join(unity_replay.machine_root(), "tools", "unity-heavy.ps1")


# ------------------------------------------------------------------------------------------------ helpers
def now():
    return datetime.datetime.now().astimezone().isoformat(timespec="milliseconds")


def jdump(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
        f.write("\n")


def jappend(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def jload(path, default=None):
    if not os.path.exists(path):
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def git(repo, *args, check=True, binary=False, env=None, inp=None):
    e = dict(os.environ)
    if env:
        e.update(env)
    r = subprocess.run(["git", "-C", repo, "-c", "core.quotepath=off", "-c", "core.autocrlf=false"] + list(args),
                       capture_output=True, env=e, input=inp)
    if check and r.returncode != 0:
        raise RuntimeError("git %s: %s" % (" ".join(args[:3]), r.stderr.decode("utf-8", "replace")[-800:]))
    return r.stdout if binary else r.stdout.decode("utf-8", "replace")


def ps_quote(s):
    # PowerShell reads the typographic quotes as quotes too: each is doubled
    return "'" + re.sub("(['\\u2018\\u2019\\u201a\\u201b])", r"\1\1", str(s)) + "'"


def _kill_tree(pid):
    subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)], capture_output=True, check=False)


def heavy(label, argv, log_path=None, env=None, timeout=None):
    """Run one editor process through <root>/tools/unity-heavy.ps1 (the machine-wide slots), or directly on a machine
    without it; UGF_HEAVY_LOW=1 (the live replay) runs it as a low-priority job (-Low). Returns (exit code or None when
    stopped at `timeout` seconds, seconds)."""
    script = heavy_path()
    e = dict(os.environ)
    if env:
        e.update(env)
    if os.path.isfile(script):
        low = " -Low" if os.environ.get("UGF_HEAVY_LOW") == "1" else ""
        cmd = ("& %s -Label %s%s -- %s; if ($null -eq $LASTEXITCODE) { exit 1 }; exit $LASTEXITCODE"
               % (ps_quote(script), ps_quote(label), low, " ".join(ps_quote(a) for a in argv)))
        full = ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", cmd]
    else:
        full = list(argv)
    t0 = time.time()
    out = open(log_path + ".console", "wb") if log_path else subprocess.DEVNULL
    try:
        p = subprocess.Popen(full, stdout=out, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, env=e,
                             creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))
        try:
            code = p.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            _kill_tree(p.pid)
            p.wait()
            code = None
        except BaseException:
            _kill_tree(p.pid)   # an interrupted replay leaves no editor behind on the project
            p.wait()
            raise
    finally:
        if log_path:
            out.close()
    return code, round(time.time() - t0, 1)


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def git_blob_sha1_file(p):
    with open(p, "rb") as f:
        data = f.read()
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def scan(root, subs=SCAN_ROOTS):
    """{repo path: (size, mtime_ns)} of every file under root/<sub> (the editor tools' folder left out)."""
    out = {}
    tool = os.path.normcase(os.path.join(root, TOOL_DIR))
    for sub in subs:
        base = os.path.join(root, sub)
        for dp, dns, files in os.walk(base):
            if os.path.normcase(dp) == tool:
                dns[:] = []
                continue
            for fn in files:
                fp = os.path.join(dp, fn)
                rel = os.path.relpath(fp, root).replace("\\", "/")
                if rel in (TOOL_DIR + ".meta",):
                    continue
                st = os.stat(fp)
                out[rel] = (st.st_size, st.st_mtime_ns)
    return out


def diff_scan(a, b):
    added = sorted(p for p in b if p not in a)
    deleted = sorted(p for p in a if p not in b)
    changed = sorted(p for p in b if p in a and a[p] != b[p])
    return added, changed, deleted


LFS_PTR = re.compile(rb"version https://git-lfs.github.com/spec/v1\r?\noid sha256:([0-9a-f]{64})\r?\nsize (\d+)")


def tree_ids(repo, sha, prefix=""):
    """{path: ('lfs', sha256) | ('git', sha1)} for files of a commit (LFS pointers resolved to their oid)."""
    out = {}
    small = []
    for line in git(repo, "ls-tree", "-r", "-l", sha, "--", prefix or ".").splitlines():
        meta, path = line.split("\t", 1)
        mode, typ, oid, size = meta.split()
        if typ != "blob":
            continue
        out[path] = ("git", oid)
        if size != "-" and int(size) < 300:
            small.append((path, oid))
    if small:
        data = git(repo, "cat-file", "--batch", inp="\n".join(o for _, o in small).encode() + b"\n", binary=True)
        pos = 0
        for path, oid in small:
            nl = data.index(b"\n", pos)
            n = int(data[pos:nl].split()[2])
            body = data[nl + 1:nl + 1 + n]
            pos = nl + 1 + n + 1
            m = LFS_PTR.match(body)
            if m:
                out[path] = ("lfs", m.group(1).decode())
    return out


def file_matches(fp, ident):
    if not os.path.exists(fp):
        return False
    kind, oid = ident
    return (sha256_file(fp) if kind == "lfs" else git_blob_sha1_file(fp)) == oid


def is_content(cfg, path):
    import ledger
    return ledger.is_content(path, cfg.get("content_ext", []))


# ------------------------------------------------------------------------------------------------ paths
class Ctx:
    def __init__(self, cfg):
        self.cfg = cfg
        self.repo = cfg["repo"]
        self.proj = cfg["project_dir"]
        self.work = cfg["work_dir"]
        self.ledger = jload(os.path.join(self.work, "ledger.json"))
        self.state_path = os.path.join(self.work, "state.json")
        self.state = jload(self.state_path, {"window": 0, "done": [], "provenance": {}})
        self.editor = (self.state.get("editor") or "").replace("\\", "/")
        self.logs = os.path.join(self.work, "logs")
        os.makedirs(self.logs, exist_ok=True)

    def editor_for(self, project):
        """The editor for a project folder as it stands on disk: with "{editor}" settings the version its
        ProjectVersion.txt names (a game upgraded to a newer patch replays its early commits on the old one); a
        literal "editor" is used as is."""
        if self.cfg.get("_editor_per_commit"):
            return unity_replay.machine_editor(project)
        return self.cfg["editor"].replace("\\", "/")

    def save(self):
        jdump(self.state_path, self.state)

    def p(self, rel):
        return os.path.join(self.proj, rel)


# ------------------------------------------------------------------------------------------------ prepare
def clone_at(cfg, dest, sha):
    if os.path.exists(os.path.join(dest, ".git")):
        return False
    repo = cfg["repo"]
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    subprocess.run(["git", "clone", "-q", "--shared", "--no-checkout", repo, dest], check=True)
    for k, v in (("core.autocrlf", "false"), ("core.eol", "lf"), ("lfs.storage", repo.replace("\\", "/") + "/.git/lfs"),
                 ("lfs.fetchrecentalways", "false"), ("remote.origin.url", repo.replace("\\", "/"))):
        git(dest, "config", k, v)
    git(dest, "checkout", "-q", "--detach", sha, env={"GIT_LFS_SKIP_SMUDGE": "1"})
    fix_lfs_pointers_at(dest, ["."])
    return True


def cmd_prepare(cfg, a):
    ctx = Ctx(cfg)
    if ctx.ledger is None:
        sys.exit("run `ledger` first")
    first = ctx.ledger["first"]
    t0 = time.time()
    made = clone_at(cfg, ctx.proj, first)
    st = git(ctx.proj, "status", "--short")
    print("project %s at %s (%s, %.0f s); status: %s" % (ctx.proj, first[:10], "cloned" if made else "exists",
                                                          time.time() - t0, st.strip() or "clean"))
    if made or not ctx.state.get("provenance"):
        ctx.state["provenance"] = {p: "git:" + first[:10] for p in scan(ctx.proj)}
        ctx.save()
    manifest = initial_assets_manifest(cfg, ctx)
    jdump(os.path.join(ctx.work, "initial-assets.manifest.json"), manifest)
    print("initial assets: %d files, %.2f GB" % (manifest["counts"]["files"], manifest["counts"]["bytes"] / 1e9))


def external_dir(ctx, e):
    return os.path.join(ctx.work, "external", e["id"])


def build_externals(ctx):
    """External sources with a "rebuild" recipe (the builder unpacked library archives into a scratch folder that no
    longer exists): {"unzip": [{"zip": "<glob>", "to": "<subdir>", "exclude": ["*Cavity*", ...]}]} rebuilds the folder
    under work/external/<id>/; runs whose env names the recorded folder get this one (map_external_env)."""
    import fnmatch
    import zipfile
    for e in ctx.cfg.get("external_sources", []):
        rb = e.get("rebuild")
        if not rb:
            continue
        d = external_dir(ctx, e)
        if os.path.isdir(d):
            continue
        tmp = d + ".partial"
        shutil.rmtree(tmp, ignore_errors=True)
        n = 0
        for u in rb.get("unzip", []):
            zips = sorted(glob.glob(u["zip"]))
            if not zips:
                sys.exit("external source %s: no archive matches %s" % (e["id"], u["zip"]))
            for z in zips:
                with zipfile.ZipFile(z) as zf:
                    for m in zf.namelist():
                        if m.endswith("/") or any(fnmatch.fnmatch(m, x) for x in u.get("exclude", [])):
                            continue
                        zf.extract(m, os.path.join(tmp, u.get("to", "")))
                        n += 1
        os.replace(tmp, d)
        print("external source %s rebuilt: %d files -> %s" % (e["id"], n, d))


def external_target(ctx, e):
    """Where an external source is on this machine: its rebuilt folder, else its settings path."""
    return (external_dir(ctx, e) if e.get("rebuild") else e.get("path") or "").replace("\\", "/")


def map_external_env(ctx, env):
    """Env values naming an external source's recorded location (settings "recorded": a template with {home}/{root}/*,
    as the recording has it on the machine the game was built on) point at the source on this machine."""
    for e in ctx.cfg.get("external_sources", []):
        if not e.get("recorded"):
            continue
        rx = unity_replay.recorded_path_regex(e["recorded"])
        loc = external_target(ctx, e)
        for k, v in env.items():
            m = rx.match(v)
            if m:
                env[k] = loc + v[m.end():].replace("\\", "/")
    return env


def remap_step_paths(ctx):
    """External sources with "remap_scripts": recorded steps that open the recorded location by an absolute path get
    this machine's location for the run. Returns [(file, original bytes)] to put back after the run (code is compared
    byte for byte)."""
    srcs = [(unity_replay.recorded_path_regex(e["recorded"]), external_target(ctx, e))
            for e in ctx.cfg.get("external_sources", []) if e.get("remap_scripts") and e.get("recorded")]
    if not srcs:
        return []
    changed = []
    for dp, dns, fns in os.walk(ctx.p("Assets")):
        for fn in fns:
            if not fn.endswith(".cs"):
                continue
            fp = os.path.join(dp, fn)
            with open(fp, "rb") as f:
                b = f.read()
            t = b.decode("utf-8", "replace")
            t2 = t
            for rx, loc in srcs:
                t2 = rx.sub(lambda m: loc, t2)
            if t2 != t:
                with open(fp, "wb") as f:
                    f.write(t2.encode("utf-8"))
                changed.append((fp, b))
    return changed


def initial_assets_manifest(cfg, ctx):
    """Store packs dropped in from outside the game's history, and external source files the steps read, with sha256
    per file."""
    files = []
    ext = []
    for e in cfg.get("external_sources", []):
        ext.append({"id": e["id"], "role": e.get("role"), "root": "<external:%s>" % e["id"],
                    **({"rebuild": e["rebuild"]} if e.get("rebuild") else {})})
        d = external_dir(ctx, e)
        if e.get("rebuild") and os.path.isdir(d):
            for dp, _, fns in os.walk(d):
                for fn in fns:
                    fp = os.path.join(dp, fn)
                    files.append({"role": "external_source", "source": e["id"],
                                  "path": "<external:%s>/%s" % (e["id"], os.path.relpath(fp, d).replace("\\", "/")),
                                  "bytes": os.path.getsize(fp), "sha256": sha256_file(fp)})
    for d in cfg.get("asset_drops", []):
        for it in d["items"]:
            if it.get("from_git"):
                ref = it.get("ref") or ctx.ledger["final"]
                for fp, size, sha in git_tree_files(cfg["repo"], ref, it["from_git"]):
                    files.append({"role": "store_pack", "drop": d["id"], "pack": it.get("pack"), "path": fp, "bytes": size,
                                  "sha256": sha, "source": "commit %s (git/LFS)" % ref[:10]})
                continue
            if os.path.isfile(it["from"]):
                files.append({"role": "store_pack", "drop": d["id"], "pack": it.get("pack"), "path": it["to"],
                              "bytes": os.path.getsize(it["from"]), "sha256": sha256_file(it["from"])})
                continue
            for dp, _, fns in os.walk(it["from"]):
                for fn in fns:
                    fp = os.path.join(dp, fn)
                    rel = os.path.relpath(fp, it["from"]).replace("\\", "/")
                    files.append({"role": "store_pack", "drop": d["id"], "pack": it.get("pack"), "path": it["to"] + "/" + rel,
                                  "bytes": os.path.getsize(fp), "sha256": sha256_file(fp)})
    return {"schema": "unity-replay.initial-assets/v1", "game": cfg["game"], "first_commit": ctx.ledger["first"],
            "drops": [{k: v for k, v in d.items() if k != "match"} for d in cfg.get("asset_drops", [])],
            "external_sources": ext, "files": files,
            "counts": {"files": len(files), "bytes": sum(f["bytes"] for f in files)}}


# ------------------------------------------------------------------------------------------------ LFS, inputs, metas
def fix_lfs_pointers_at(proj, paths, store=None):
    """Files a checkout left as Git LFS pointer text, replaced by the object from the game's LFS store (the clone's
    lfs.storage). Also happens when an earlier commit's .gitattributes does not yet mark an extension as LFS."""
    n = 0
    for rel in paths:
        root = os.path.join(proj, rel)
        files = [root] if os.path.isfile(root) else [os.path.join(dp, f) for dp, dns, fs in os.walk(root)
                                                      for f in fs if ".git" not in dp.replace("\\", "/").split("/")]
        for fp in files:
            try:
                if os.path.getsize(fp) > 1024:
                    continue
                with open(fp, "rb") as f:
                    m = LFS_PTR.match(f.read())
            except OSError:
                continue
            if not m:
                continue
            if store is None:
                store = (git(proj, "config", "--get", "lfs.storage", check=False).strip() or os.path.join(proj, ".git", "lfs"))
            oid = m.group(1).decode()
            obj = os.path.join(store, "objects", oid[:2], oid[2:4], oid)
            if not os.path.exists(obj):
                sys.exit("LFS object %s for %s is not in %s" % (oid, fp, store))
            shutil.copyfile(obj, fp)
            n += 1
    return n


def fix_lfs_pointers(ctx, paths):
    return fix_lfs_pointers_at(ctx.proj, paths)


def checkout_paths(ctx, sha, paths):
    """Files as commit sha has them (LFS objects from the game's store)."""
    for k in range(0, len(paths), 500):
        part = paths[k:k + 500]
        git(ctx.proj, "checkout", sha, "--pathspec-from-file=-", inp="\n".join(part).encode("utf-8"),
            env={"GIT_LFS_SKIP_SMUDGE": "1"})
        fix_lfs_pointers(ctx, part)


def apply_inputs(ctx, w):
    """Files the builder writes as the commit has them (adds/modifies via checkout, deletes removed)."""
    am = [x["path"] for x in w["inputs"] if x["status"] in "AMT" and x["path"] != "workflow.jsonl"]
    dl = [x["path"] for x in w["inputs"] if x["status"] == "D"]
    if am:
        checkout_paths(ctx, w["sha"], am)
    for p in dl:
        fp = ctx.p(p)
        if os.path.exists(fp):
            os.remove(fp)
    # workflow.jsonl: the commit's version (steps append to it; their rows are cut out per run)
    if any(x["path"] == "workflow.jsonl" for x in w["inputs"]):
        data = git(ctx.proj, "show", "%s:workflow.jsonl" % w["sha"], binary=True)
        with open(ctx.p("workflow.jsonl"), "wb") as f:
            f.write(data)
    return len(am), len(dl)


def identity_part(meta):
    """The identity of a .meta: its lines up to the guid (and a folder's folderAsset line); the import settings after it
    are the replay's own."""
    lines = meta.replace(b"\r\n", b"\n").split(b"\n")
    out = []
    for ln in lines:
        out.append(ln)
        if ln.startswith(b"guid:"):
            break
    if b"folderAsset: yes" in meta:
        out.append(b"folderAsset: yes")
    return b"\n".join(out) + (b"\n" if meta.endswith(b"\n") or len(lines) > len(out) else b"")


def ensure_metas(ctx, w, tree=None):
    """Every file and folder the builder wrote under Assets/ that is in the replay project without its .meta gets the
    .meta's identity from the commit (input_meta "guid": the lines up to its guid, so Unity imports it with its own
    default settings and the replay's steps set the rest; "commit": the commit's whole .meta). Folders get the
    commit's folder .meta. Returns the paths written."""
    import ledger
    if tree is None:
        tree = set(git(ctx.proj, "ls-tree", "-r", "--name-only", w["sha"], "--", "Assets").splitlines())
    metas = [p for p in tree if p.endswith(".meta")]
    mode = ctx.cfg.get("input_meta", "guid")
    written = []
    prov = ctx.state["provenance"]
    for m in metas:
        asset = m[:-5]
        fp, ap = ctx.p(m), ctx.p(asset)
        if os.path.exists(fp) or not os.path.exists(ap):
            continue
        folder = os.path.isdir(ap)
        if not folder and ledger.is_content(asset, ctx.cfg.get("content_ext", [])):
            continue   # made by a step: its .meta comes with it, and the boundary gives it the commit's guid
        data = git(ctx.proj, "show", "%s:%s" % (w["sha"], m), binary=True)
        out = data if (folder or mode == "commit") else identity_part(data)
        os.makedirs(os.path.dirname(fp), exist_ok=True)
        with open(fp, "wb") as f:
            f.write(out)
        prov[m] = "stub:" + w["sha"][:10]
        written.append(m)
    return written


def materialize_code(ctx, run, w):
    """Code files as they stood when the run started (ledger texts); absent ones removed; unknown ones keep the
    commit's text (left alone they kept whatever an earlier run of the window had)."""
    n = 0
    for p, h in (run.get("texts") or {}).items():
        with open(os.path.join(ctx.work, "blobs", h), "rb") as f:
            data = f.read()
        fp = ctx.p(p)
        cur = None
        if os.path.exists(fp):
            with open(fp, "rb") as f:
                cur = f.read()
        if cur != data:
            os.makedirs(os.path.dirname(fp), exist_ok=True)
            with open(fp, "wb") as f:
                f.write(data)
            n += 1
    for p in run.get("absent") or []:
        fp = ctx.p(p)
        if os.path.exists(fp):
            os.remove(fp)
            n += 1
            m = fp + ".meta"
            if os.path.exists(m) and str(ctx.state["provenance"].get(p + ".meta", "")).startswith("stub:"):
                os.remove(m)   # its identity comes back with the file
    in_tree = None
    for p in run.get("unknown") or []:
        if in_tree is None:
            in_tree = set(git(ctx.proj, "ls-tree", "-r", "--name-only", w["sha"]).splitlines())
        if p in in_tree:
            checkout_paths(ctx, w["sha"], [p])
            n += 1
        elif os.path.exists(ctx.p(p)):
            os.remove(ctx.p(p))
            n += 1
    return n


def put_commit_code(ctx, sha, paths):
    """Code files back to commit sha (the ones it has) and removed where it has none."""
    in_tree = set(git(ctx.proj, "ls-tree", "-r", "--name-only", sha).splitlines())
    have = [p for p in paths if p in in_tree]
    if have:
        checkout_paths(ctx, sha, have)
    for p in paths:
        if p not in in_tree and os.path.exists(ctx.p(p)):
            os.remove(ctx.p(p))


def code_paths(ctx, sha):
    """path -> blob id of every code file (ledger.is_code) in the commit's tree."""
    import ledger
    out = {}
    for line in git(ctx.proj, "ls-tree", "-r", sha).splitlines():
        meta, _, p = line.partition("\t")
        parts = meta.split()
        if len(parts) == 3 and parts[1] == "blob" and ledger.is_code(p):
            out[p] = parts[2]
    return out


# ------------------------------------------------------------------------------------------------ editor runs
def editor_argv(ctx, project, log, method, quit_=True, extra=()):
    exe = ctx.editor if project == ctx.proj and ctx.editor else ctx.editor_for(project)
    argv = [exe] + list(ctx.cfg.get("editor_args", ["-batchmode", "-nographics"]))
    if quit_:
        argv.append("-quit")
    argv += ["-projectPath", project.replace("\\", "/"), "-logFile", log.replace("\\", "/")]
    if method:
        argv += ["-executeMethod", method]
    return argv + list(extra)


def run_step(ctx, run):
    """One recorded editor step, headless: -executeMethod with the recorded method, -quit unless the builder ran it
    with -NoQuit, the recorded -Reason as UNITY_RUN_REASON."""
    cfg = ctx.cfg
    env = {k: v.replace("{project}", ctx.proj) for k, v in cfg.get("step_env", {}).items()}
    # values the builder's shell expanded ($USERPROFILE, %USERPROFILE%, ...) as this machine has them
    env.update({k: os.path.expandvars(v) for k, v in (run.get("env") or {}).items()})
    build_externals(ctx)
    map_external_env(ctx, env)
    if cfg.get("reason_env"):
        env[cfg["reason_env"]] = run.get("reason") or ""
    log = os.path.join(ctx.logs, "runs", "%s_%s.log" % (run["id"], run["method"].split(".")[-2] if "." in run["method"] else run["method"]))
    os.makedirs(os.path.dirname(log), exist_ok=True)
    if os.path.exists(log):
        os.remove(log)
    extra = []
    if run.get("args"):
        import shlex
        extra = shlex.split(run["args"])
    argv = editor_argv(ctx, ctx.proj, log, run["method"], quit_=run.get("quit", True), extra=extra)
    code, secs = heavy("%s replay %s %s" % (cfg["game"], run["id"], run["method"].split(".")[-2] if "." in run["method"] else ""),
                       argv, env=env, timeout=cfg.get("run_timeout_s") or None)
    return code, secs, log


def log_text(log):
    try:
        with open(log, encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError:
        return ""


def compile_failed(log):
    return bool(COMPILER_ERROR.search(log_text(log)))


def editor_crashed(log):
    """The editor process died (a native crash), not an exception in the step."""
    return bool(CRASH.search(log_text(log)))


def wf_rows(path):
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return [l for l in f.read().splitlines() if l.strip()]


def install_tools(project):
    d = os.path.join(project, TOOL_DIR)
    os.makedirs(d, exist_ok=True)
    for fn in TOOL_FILES:
        shutil.copyfile(os.path.join(TOOL_SRC, fn), os.path.join(d, fn))


def remove_tools(project):
    d = os.path.join(project, TOOL_DIR)
    shutil.rmtree(d, ignore_errors=True)
    for m in (d + ".meta",):
        if os.path.exists(m):
            os.remove(m)


def run_tool(ctx, project, method, request, label, timeout=None):
    """One run of the replay's own editor tools (editor/*.cs) in a project: put into Assets/CreationReplayTools/ for
    the run and removed after it, so the project's tracked files never hold them. Returns (exit code, seconds, log)."""
    os.makedirs(os.path.join(ctx.work, "requests"), exist_ok=True)
    req = os.path.join(ctx.work, "requests", label + ".json")
    jdump(req, request)
    log = os.path.join(ctx.logs, "%s.log" % label)
    if os.path.exists(log):
        os.remove(log)
    before = scan(project)
    install_tools(project)
    try:
        argv = editor_argv(ctx, project, log, method, extra=["-replayRequest", req.replace("\\", "/")])
        code, secs = heavy("%s replay %s" % (ctx.cfg["game"], label), argv, timeout=timeout)
    finally:
        remove_tools(project)
    added, changed, deleted = diff_scan(before, scan(project))
    if added or changed or deleted:
        # the tools only read; anything else the editor wrote on opening is listed (it stays: it is the editor's)
        jappend(os.path.join(ctx.work, "tool-side-effects.jsonl"), {"time": now(), "label": label, "added": added[:50],
                                                                    "changed": changed[:50], "deleted": deleted[:50]})
    return code, secs, log


def dump(ctx, out, project=None, assets=True, scenes="all", only=None, label="dump"):
    """Structure dump (editor/ReplayDump.cs) of a project: assets.json and scenes/<scene>.json in out. scenes: "all"
    (every scene under scene_roots), a list of scene paths, or none; only: the asset paths to dump (None: all)."""
    proj = project or ctx.proj
    if os.path.exists(out):
        shutil.rmtree(out)
    os.makedirs(out, exist_ok=True)
    req = {"out": out.replace("\\", "/"), "assets": bool(assets), "all_scenes": scenes == "all",
           "scenes": scenes if isinstance(scenes, list) else [], "only": list(only or []),
           "asset_roots": ctx.cfg.get("asset_roots", ["Assets"]), "scene_roots": ctx.cfg.get("scene_roots", ["Assets"]),
           "exclude": [d["path"] for d in ctx.cfg.get("dump_exclusions", [])] + [TOOL_DIR]}
    return run_tool(ctx, proj, "CreationReplay.ReplayDump.Run", req, label, timeout=ctx.cfg.get("run_timeout_s") or None)


# ------------------------------------------------------------------------------------------------ shell steps
def _inside(ctx, rel):
    p = os.path.normpath(ctx.p(rel))
    if not os.path.normcase(p).startswith(os.path.normcase(os.path.normpath(ctx.proj)) + os.sep):
        raise SystemExit("shell step outside the replay project: " + rel)
    return p


def _copy_any(src, dst):
    if os.path.isdir(src):
        n = 0
        for dp, _, fns in os.walk(src):
            for fn in fns:
                s = os.path.join(dp, fn)
                t = os.path.join(dst, os.path.relpath(s, src))
                os.makedirs(os.path.dirname(t), exist_ok=True)
                shutil.copy2(s, t)
                n += 1
        return n
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.copy2(src, dst)
    return 1


def content_op(ctx, step):
    """A shell copy, move or delete of content, done to the replay's own files (shellfx.content_ops)."""
    op, n, missing = step["op"], 0, []
    if op == "delete":
        for rel in step["src"]:
            p = _inside(ctx, rel)
            if os.path.isdir(p):
                shutil.rmtree(p)
                n += 1
            elif os.path.exists(p):
                os.remove(p)
                n += 1
            else:
                missing.append(rel)
        return n, missing
    dst_rel = step["dst"]
    for rel in step["src"]:
        s = _inside(ctx, rel)
        if not os.path.exists(s):
            missing.append(rel)
            continue
        d_rel = dst_rel
        if step.get("into") or os.path.isdir(_inside(ctx, dst_rel)) or len(step["src"]) > 1:
            d_rel = dst_rel.rstrip("/") + "/" + os.path.basename(rel)
        d = _inside(ctx, d_rel)
        n += _copy_any(s, d)
        if op == "move":
            shutil.rmtree(s) if os.path.isdir(s) else os.remove(s)
    return n, missing


def delete_paths(ctx, step):
    """shell step 'delete path...' (files the builder removed by hand), under cwd; paths stay inside the project."""
    cwd = step.get("cwd", "")
    n = 0
    for rel in step["argv"][1:]:
        p = _inside(ctx, os.path.join(cwd, rel))
        if os.path.isdir(p):
            shutil.rmtree(p)
            n += 1
        elif os.path.exists(p):
            os.remove(p)
            n += 1
    return n


def move_merge(ctx, step):
    """shell step 'move-merge src dst' (cp -rn src/. dst/ && rm -rf src) under cwd."""
    cwd = step.get("cwd", "")
    src, dst = _inside(ctx, os.path.join(cwd, step["argv"][1])), _inside(ctx, os.path.join(cwd, step["argv"][2]))
    moved = 0
    if os.path.isdir(src):
        for dp, _, fns in os.walk(src):
            for fn in fns:
                s = os.path.join(dp, fn)
                d = os.path.join(dst, os.path.relpath(s, src))
                if not os.path.exists(d):
                    os.makedirs(os.path.dirname(d), exist_ok=True)
                    shutil.copy2(s, d)
                    moved += 1
        shutil.rmtree(src)
    return moved


def copy_paths(ctx, step):
    """shell step 'copy src dst' (cp -r src dst) under cwd, of the replay's own files."""
    cwd = step.get("cwd", "")
    return _copy_any(_inside(ctx, os.path.join(cwd, step["argv"][1])), _inside(ctx, os.path.join(cwd, step["argv"][2])))


def keep_committed(ctx, step, w):
    """shell step 'keep-committed dir...': a prune the replay cannot recompute, reproduced from its result: files under
    the dirs that the commit `ref` (settings, default the window's commit) does not have are deleted."""
    removed = 0
    ref = git(ctx.proj, "rev-parse", step.get("ref") or w["sha"]).strip()
    for rel in step["argv"][1:]:
        rel = rel.strip("/")
        root = _inside(ctx, rel)
        keep = set(git(ctx.proj, "ls-tree", "-r", "--name-only", ref, "--", rel).splitlines())
        for dp, dns, fns in os.walk(root, topdown=False):
            for fn in fns:
                p = os.path.relpath(os.path.join(dp, fn), ctx.proj).replace("\\", "/")
                if p not in keep:
                    os.remove(os.path.join(dp, fn))
                    removed += 1
            if not os.listdir(dp):
                os.rmdir(dp)
    return removed


def host_python(ctx, step):
    """shell step 'host-python script args...': a builder's own Python script (not an editor step) run in the replay
    project with this machine's Python, cwd under the project. One that names the live game repo is refused."""
    cwd = ctx.p(step.get("cwd", ""))
    script = os.path.join(cwd, step["argv"][1])
    text = open(script, encoding="utf-8", errors="replace").read()
    live = ctx.cfg["repo"].replace("\\", "/").lower()
    if live in text.replace("\\\\", "/").replace("\\", "/").lower():
        raise SystemExit("host-python %s names the live game repo; refusing" % step["argv"][1])
    r = subprocess.run([sys.executable, script] + list(step["argv"][2:]), cwd=cwd, capture_output=True, text=True, errors="replace")
    with open(os.path.join(ctx.logs, "host_%s.log" % os.path.splitext(os.path.basename(script))[0]), "a", encoding="utf-8") as f:
        f.write(r.stdout + r.stderr)
    if r.returncode:
        print("   host-python %s exit %s" % (step["argv"][1], r.returncode), flush=True)
    return r.returncode


def git_tree_files(repo, sha, path):
    """(path, bytes, sha256) of every file under path at sha; Git LFS pointers give the object's own size and oid."""
    out = []
    lines = [l for l in git(repo, "ls-tree", "-r", sha, "--", path).splitlines() if l.strip()]
    ids = [(l.split("\t", 1)[1], l.split()[2]) for l in lines]
    if not ids:
        return out
    r = subprocess.run(["git", "-C", repo, "cat-file", "--batch"], input=("\n".join(i for _, i in ids) + "\n").encode(),
                       capture_output=True)
    data, pos = r.stdout, 0
    for fp, oid in ids:
        nl = data.index(b"\n", pos)
        size = int(data[pos:nl].split()[2])
        body = data[nl + 1:nl + 1 + size]
        pos = nl + 1 + size + 1
        m = LFS_PTR.match(body)
        if m:
            out.append((fp, int(m.group(2)), m.group(1).decode()))
        else:
            out.append((fp, size, hashlib.sha256(body).hexdigest()))
    return out


def drop_assets(ctx, d):
    """A store pack the builder copied in: from_git (the pack exactly as the game committed it, restored from a
    commit's tree at the moment the builder copied it in; LFS objects from the game's store) or from (a folder or file
    on this machine)."""
    n = 0
    for it in d["items"]:
        if it.get("from_git"):
            ref = git(ctx.proj, "rev-parse", it.get("ref") or ctx.ledger["final"]).strip()
            git(ctx.proj, "restore", "--source=" + ref, "--worktree", "--", it["from_git"], env={"GIT_LFS_SKIP_SMUDGE": "1"})
            fix_lfs_pointers(ctx, [it["from_git"]])
            n += len(git(ctx.proj, "ls-tree", "-r", "--name-only", ref, "--", it["from_git"]).splitlines())
            continue
        if not os.path.exists(it["from"]):
            # a wrong source path would copy nothing without a word
            raise SystemExit("asset drop %s: source %s does not exist" % (d["id"], it["from"]))
        n += _copy_any(it["from"], ctx.p(it["to"]))
    return n


def note_outputs(ctx, before, after, tag):
    added, changed, deleted = diff_scan(before, after)
    prov = ctx.state["provenance"]
    outs = ctx.state.setdefault("window_outputs", [])
    for p in added + changed:
        prov[p] = tag
        if p not in outs:
            outs.append(p)
    for p in deleted:
        prov.pop(p, None)
    return {"added": added, "changed": changed, "deleted": deleted}


# ------------------------------------------------------------------------------------------------ boundary
def meta_guid(data):
    m = GUID_LINE.search(data or b"")
    return m.group(1).decode() if m else None


def identity_value(data, key):
    m = re.search(rb"^\s*%s: ([0-9a-f]{32})\s*$" % key.encode(), data or b"", re.M)
    return m.group(1).decode() if m else None


def adopt_identity(ctx, w, ids):
    """The GUIDs of the assets the replay created (random in every editor) become the ones the commit has at the same
    paths, in the .meta files and in every file of this window that refers to them; the same for ProjectSettings
    values Unity sets at random (IDENTITY_KEYS). Identity, never content: what refers to what stays the replay's.
    Returns {replay guid: commit guid}."""
    mapping = {}
    outs = set(ctx.state.get("window_outputs") or [])
    # .meta files the replay made in an earlier window that its commit did not have yet (an asset committed later):
    # their identity is adopted when a commit has them, in the files written since (carry)
    pending = set(ctx.state.get("unadopted_metas") or [])
    carry = set(ctx.state.get("unadopted_carry") or [])
    cands = set(p for p in outs if p.endswith(".meta")) | pending
    cands |= set(x["path"] for x in w["content"] if x["path"].endswith(".meta") and x["status"] in "AMT")
    left = sorted(m for m in cands if m not in ids and os.path.exists(ctx.p(m)) and m.startswith("Assets/"))
    ctx.state["unadopted_metas"] = left
    ctx.state["unadopted_carry"] = sorted(carry | outs) if left else []
    outs |= carry
    for m in sorted(cands):
        if m not in ids or not os.path.exists(ctx.p(m)):
            continue
        want = meta_guid(git(ctx.proj, "show", "%s:%s" % (w["sha"], m), binary=True, check=False))
        with open(ctx.p(m), "rb") as f:
            have = meta_guid(f.read())
        if want and have and want != have:
            mapping[have] = want
    ps = "ProjectSettings/ProjectSettings.asset"
    if os.path.exists(ctx.p(ps)) and ps in ids:
        with open(ctx.p(ps), "rb") as f:
            have_ps = f.read()
        want_ps = git(ctx.proj, "show", "%s:%s" % (w["sha"], ps), binary=True, check=False)
        for key in IDENTITY_KEYS:
            hv, wv = identity_value(have_ps, key), identity_value(want_ps, key)
            if hv and wv and hv != wv:
                mapping[hv] = wv
    if not mapping:
        return {}
    rx = re.compile(("(?<![0-9a-f])(%s)(?![0-9a-f])" % "|".join(mapping)).encode())
    files = set(outs) | set(p for p in scan(ctx.proj, ("ProjectSettings",)))
    for p in sorted(files):
        fp = ctx.p(p)
        if not os.path.isfile(fp) or os.path.getsize(fp) > 64 << 20:
            continue
        with open(fp, "rb") as f:
            data = f.read()
        if b"\0" in data[:8000]:
            continue   # binary
        new = rx.sub(lambda m: mapping[m.group(1).decode()].encode(), data)
        if new != data:
            with open(fp, "wb") as f:
                f.write(new)
    return mapping


def boundary(ctx, w):
    """Window check against the commit: identity adopted, then content set and identity, fallbacks for content no
    replayed step produced, inputs back to the commit."""
    prov = ctx.state["provenance"]
    res = {"fallback": [], "deleted": [], "already_deleted": [], "exact": [], "differs": [], "adopted_guids": 0}
    # inputs (and the code a run had at earlier texts) back to the commit first: the content check reads the commit's
    am = [x["path"] for x in w["inputs"] if x["status"] in "AMT" and x["path"] != "workflow.jsonl"]
    for r in w["runs"]:
        am += [p for p in list((r.get("texts") or {})) + list(r.get("absent") or []) + list(r.get("unknown") or []) if p not in am]
    if am:
        put_commit_code(ctx, w["sha"], am)
    ids = tree_ids(ctx.proj, w["sha"])
    ensure_metas(ctx, w, set(p for p in ids if p.startswith("Assets/")))
    mapping = adopt_identity(ctx, w, ids)
    res["adopted_guids"] = len(mapping)
    for x in w["content"]:
        p = x["path"]
        fp = ctx.p(p)
        if x["status"] == "D":
            if os.path.exists(fp):
                os.remove(fp)
                res["deleted"].append(p)
            else:
                res["already_deleted"].append(p)
            prov.pop(p, None)
            continue
        src = prov.get(p, "")
        if os.path.exists(fp) and file_matches(fp, ids[p]):
            res["exact"].append({"path": p, "by": src})
            continue
        if not os.path.exists(fp) or not src or src.startswith(("git:", "fallback:", "stub:")):
            checkout_paths(ctx, w["sha"], [p])
            prov[p] = "fallback:" + w["sha"][:10]
            res["fallback"].append({"path": p, "reason": "missing" if not os.path.exists(fp) or not src else
                                    "not produced by a replayed step (%s)" % src})
            continue
        res["differs"].append({"path": p, "by": src})
    # content set: what the commit tree has vs what the project has, under Assets/ and ProjectSettings/
    have = set(scan(ctx.proj))
    want = set(p for p in ids if p.startswith(tuple(s + "/" for s in SCAN_ROOTS)))
    res["missing"] = sorted(want - have)
    res["extra"] = sorted(have - want)
    ctx.state["window_outputs"] = []
    return res


# ------------------------------------------------------------------------------------------------ run
def do_shell(ctx, s, w, sid):
    if s.get("auto"):
        n, missing = content_op(ctx, s)
        return {"files": n, "missing_source": missing}
    op = s["argv"][0]
    n = (move_merge(ctx, s) if op == "move-merge" else delete_paths(ctx, s) if op == "delete" else
         copy_paths(ctx, s) if op == "copy" else keep_committed(ctx, s, w) if op == "keep-committed" else
         host_python(ctx, s) if op == "host-python" else 0)
    return {"files": n}


def run_once(ctx, r, w, wf_path, rec=None):
    """The step with its run-time code, its rows cut out of workflow.jsonl. Returns (code, secs, log, new rows)."""
    rows_before = wf_rows(wf_path)
    remapped = remap_step_paths(ctx)
    if remapped and rec is not None:
        rec["step_paths_remapped"] = sorted(os.path.relpath(p, ctx.proj).replace("\\", "/") for p, _ in remapped)
    try:
        code, secs, log = run_step(ctx, r)
    finally:
        for fp, b in remapped:   # the steps as recorded again
            with open(fp, "wb") as f:
                f.write(b)
    rows_after = wf_rows(wf_path)
    new_rows = rows_after[len(rows_before):] if rows_after[:len(rows_before)] == rows_before else rows_after
    with open(wf_path, "w", encoding="utf-8", newline="\n") as f:
        f.write("".join(l + "\n" for l in rows_before))
    return code, secs, log, new_rows


def later_code(ctx, wins, i, r, wf_path, rec):
    """The window commit's code does not compile on its editor (a mid-upgrade commit). Run with the code of the nearest
    LATER commit on the replayed chain (never beyond the final commit) under which the step compiles; the window
    commit's code comes back at the boundary. A deviation (code_from_commit), never a verdict rule."""
    w = wins[i]
    base = code_paths(ctx, w["sha"])
    tried = set()
    for j in range(i + 1, len(wins)):
        cand = wins[j]["sha"]
        want = code_paths(ctx, cand)
        key = json.dumps(sorted(want.items()))
        if want == base or key in tried:
            continue
        tried.add(key)
        put_commit_code(ctx, cand, sorted(set(want) | set(base)))
        print("   %s with the code of later commit %s (w%02d): the commit's code does not compile" % (r["id"], cand[:8], j), flush=True)
        code, secs, log, rows = run_once(ctx, r, w, wf_path)
        put_commit_code(ctx, w["sha"], sorted(set(want) | set(base)))
        if not compile_failed(log):
            rec["code_from_commit"] = {"commit": cand, "window": j, "reason": CODE_FROM_COMMIT_REASON}
            return code, secs, log, rows
    return None


CODE_FROM_COMMIT_REASON = "the commit's code does not compile on its editor"


def cmd_run(cfg, a):
    ctx = Ctx(cfg)
    led = ctx.ledger
    wins = led["windows"]
    last = a.until if getattr(a, "until", None) is not None else len(wins) - 1
    runs_log = os.path.join(ctx.work, "runs.jsonl")
    win_log = os.path.join(ctx.work, "windows.jsonl")
    rows_dir = os.path.join(ctx.work, "rows")
    os.makedirs(rows_dir, exist_ok=True)
    for i in range(ctx.state["window"] + 1, last + 1):
        w = wins[i]
        t_w = time.time()
        print("== window %02d %s %s" % (i, w["sha"][:7], w["subject"][:70]), flush=True)
        done = set(ctx.state["done"])
        sid = "w%02d.inputs" % i
        if sid not in done:
            n_am, n_d = apply_inputs(ctx, w)
            metas = ensure_metas(ctx, w)
            ctx.state["done"].append(sid)
            ctx.save()
            print("   inputs: %d written, %d deleted; %d .meta identities from the commit" % (n_am, n_d, len(metas)), flush=True)
        # the editor this commit names (ProjectVersion.txt); another one than the last run's: Library/ goes (Unity
        # imports the project again for that editor), and runs.jsonl records the switch (a report deviation)
        eng = ctx.editor_for(ctx.proj)
        if ctx.editor and eng != ctx.editor:
            for d in ("Library", "Temp"):
                shutil.rmtree(ctx.p(d), ignore_errors=True)
            jappend(runs_log, {"window": i, "kind": "editor_switch", "step": "w%02d.editor" % i, "commit": w["sha"],
                               "from": ctx.editor, "to": eng, "time": now()})
            print("   editor: %s -> %s (Library cleared)" % (ctx.editor, eng), flush=True)
        if eng != ctx.editor:
            ctx.editor = eng
            ctx.state["editor"] = eng
            ctx.save()
        # order of the recorded tool calls (each call's end time), then position inside the call
        steps = [("run", (r["time"], r.get("pos", -1), k), r) for k, r in enumerate(w["runs"])] + \
                [("drop", (d["time"], -2, 0), d) for d in w["drops"]] + \
                [("shell", (s["time"], s.get("pos", -1) if s.get("pos", -1) >= 0 else -1, 0), s) for s in w["shell"]]
        steps.sort(key=lambda s: s[1])
        wf_path = ctx.p("workflow.jsonl")
        for kind, t, s in steps:
            sid = "w%02d.%s.%s" % (i, kind, s.get("id") or (s.get("argv", ["?"])[0] + t[0][11:19]))
            if sid in set(ctx.state["done"]):
                continue
            # Clean pause between steps (no editor running): create work/STOP; delete it and run again to resume.
            if os.path.exists(os.path.join(ctx.work, "STOP")):
                print("   STOP file found: paused before %s (state saved; delete work/STOP and run again to resume)" % sid, flush=True)
                return 3
            rec = {"window": i, "commit": w["sha"], "kind": kind, "step": sid, "time_original": t[0], "start": now()}
            before = scan(ctx.proj)
            if kind == "drop":
                rec["files"] = drop_assets(ctx, s)
                rec["outputs"] = {k: len(v) for k, v in note_outputs(ctx, before, scan(ctx.proj), "drop:" + s["id"]).items()}
            elif kind == "shell":
                rec.update(do_shell(ctx, s, w, sid))
                rec["argv"] = s.get("argv")
                rec["auto"] = bool(s.get("auto"))
                rec["outputs"] = {k: len(v) for k, v in note_outputs(ctx, before, scan(ctx.proj), "shell:" + sid).items()}
            else:
                r = s
                rec.update({"run": r["id"], "method": r["method"], "script": r["script"], "readonly": r["readonly"],
                            "exit_code_original": r.get("exit_code"), "rows_original": r["rows"], "render": r.get("render", False)})
                # (an exit code means the run happened: the wrapper printed it after the editor exited)
                not_run = (r.get("not_run") or
                           ("no wrapper row and no exit code: the original command stopped before this run"
                            if r.get("wrapper_rows") == 0 and r.get("exit_code") is None else None))
                if not_run and not getattr(a, "force", False):
                    rec["skipped"] = not_run
                    print("   %s %-40s skipped: %s" % (r["id"], r["method"][-40:], not_run), flush=True)
                    jappend(runs_log, rec)
                    ctx.state["done"].append(sid)
                    ctx.save()
                    continue
                if r["readonly"] and not getattr(a, "force", False):
                    rec["skipped"] = "read-only"
                    jappend(runs_log, rec)
                    ctx.state["done"].append(sid)
                    ctx.save()
                    continue
                failed_before = json.dumps(sorted((r.get("texts") or {}).items())) in ctx.state.get("code_failed", [])
                if failed_before:
                    put_commit_code(ctx, w["sha"], w["code_changed"])
                    rec["code_at_run_time"] = "commit code (the run-time code did not compile before)"
                else:
                    rec["materialized"] = materialize_code(ctx, r, w)
                    if r.get("code_at_run_time"):
                        rec["code_at_run_time"] = "%d file(s) as at the run's start" % len(r["code_at_run_time"])
                rec["metas"] = len(ensure_metas(ctx, w))
                code, secs, log, new_rows = run_once(ctx, r, w, wf_path, rec)
                ok_before = r.get("exit_code") == 0 or bool(r.get("rows"))
                if compile_failed(log) and ok_before and r.get("code_at_run_time") and not failed_before:
                    # the code the builder had at that moment does not compile here (a mix of known and unknown texts,
                    # or an edit between two of their runs): this run gets the commit's code
                    ctx.state.setdefault("code_failed", []).append(json.dumps(sorted((r.get("texts") or {}).items())))
                    os.replace(log, log[:-4] + ".runtime-code.log")
                    put_commit_code(ctx, w["sha"], w["code_changed"])
                    rec["metas"] += len(ensure_metas(ctx, w))
                    rec["code_at_run_time"] = "commit code (the run-time code did not compile: %s)" % os.path.relpath(log[:-4] + ".runtime-code.log", ctx.work)
                    print("   %s: the run-time code does not compile; once more with the commit's code" % r["id"], flush=True)
                    code, secs2, log, new_rows = run_once(ctx, r, w, wf_path)
                    secs += secs2
                if compile_failed(log) and ok_before and cfg.get("code_from_later_commit", True):
                    got = later_code(ctx, wins, i, r, wf_path, rec)
                    if got:
                        code, secs2, log, new_rows = got
                        secs += secs2
                retried = 0
                while retried < 1 and len(new_rows) < len(r.get("rows") or []) and editor_crashed(log):
                    # the editor itself crashed before the step logged what the original did: once more, keeping the
                    # crash log
                    retried += 1
                    os.replace(log, log[:-4] + ".crash%d.log" % retried)
                    print("   %s editor crashed after %d/%d rows: retry %d" % (r["id"], len(new_rows), len(r["rows"]), retried), flush=True)
                    code, secs2, log, new_rows = run_once(ctx, r, w, wf_path)
                    secs += secs2
                if retried:
                    rec["retried_after_editor_crash"] = retried
                with open(os.path.join(rows_dir, r["id"] + ".jsonl"), "w", encoding="utf-8", newline="\n") as f:
                    f.write("".join(l + "\n" for l in new_rows))
                outs = note_outputs(ctx, before, scan(ctx.proj), "run:" + r["id"])
                scenes = sorted(set(p for p in outs["added"] + outs["changed"] if p.endswith(".unity")))
                rec.update({"exit_code": code, "timed_out": code is None, "seconds": secs, "version": r["script_version"],
                            "rows_replayed": len(new_rows), "log": os.path.relpath(log, ctx.work),
                            "compile_errors": compile_failed(log), "outputs": outs, "scenes_changed": scenes})
                if scenes and cfg.get("scene_exports"):
                    out = os.path.join(ctx.work, "scenedumps", r["id"])
                    dcode, dsecs, _ = dump(ctx, out, assets=False, scenes=scenes, label="scenedump_" + r["id"])
                    rec["scene_dump"] = {"exit_code": dcode, "seconds": dsecs, "dir": os.path.relpath(out, ctx.work)}
                print("   %s %-40s exit %s (orig %s) %5.0f s  rows %d/%d  +%d ~%d -%d%s" % (
                    r["id"], r["method"][-40:], code, r.get("exit_code"), secs, len(new_rows), len(r["rows"]),
                    len(outs["added"]), len(outs["changed"]), len(outs["deleted"]),
                    ("  scenes " + ",".join(os.path.basename(m) for m in scenes)) if scenes else ""), flush=True)
            rec["end"] = now()
            jappend(runs_log, rec)
            ctx.state["done"].append(sid)
            ctx.save()
        res = boundary(ctx, w)
        summ = {"window": i, "commit": w["sha"], "subject": w["subject"], "time": now(), "seconds": round(time.time() - t_w, 1),
                "runs": len(w["runs"]), "reconstruction": {"checks": len(w["reconstruction"]),
                                                           "match": sum(1 for c in w["reconstruction"] if c["match"])},
                "content": {k: (len(v) if isinstance(v, list) else v) for k, v in res.items()}, "detail": res}
        jappend(win_log, summ)
        print("   boundary: content %s" % json.dumps(summ["content"]), flush=True)
        ctx.state["window"] = i
        ctx.state["done"] = []
        ctx.save()


def cmd_status(cfg, a):
    ctx = Ctx(cfg)
    print(json.dumps({k: v for k, v in ctx.state.items() if k not in ("provenance", "window_outputs")}, indent=1))
    kinds = {}
    for v in ctx.state.get("provenance", {}).values():
        k = v.split(":")[0]
        kinds[k] = kinds.get(k, 0) + 1
    print("provenance:", kinds)


def cmd_dump(cfg, a):
    ctx = Ctx(cfg)
    proj = cfg["truth_dir"] if a.which == "truth" else ctx.proj
    if a.which == "truth":
        import live
        final = git(cfg["repo"], "rev-parse", (ctx.ledger or {}).get("final") or cfg["final"]).strip()
        live.sync_truth(cfg, final)   # the truth clone at the final commit (made or moved there); the dump imports it
    if a.which != "truth" and not ctx.editor:
        ctx.editor = ctx.editor_for(proj)
    out = os.path.join(ctx.work, "dump-" + a.which)
    scenes = a.only.split(",") if a.only else (cfg.get("scene_list") or "all")
    code, secs, log = dump(ctx, out, project=proj, assets=True, scenes=scenes, label="dump_" + a.which)
    print("dump %s: exit %s (%.0f s) -> %s (log %s)" % (a.which, code, secs, out, log))
    return 0 if code == 0 and os.path.exists(os.path.join(out, "done.json")) else 1
