"""Ledger: what the builder of a game ran, window by window, from three records.

  git history          the commits on the first-parent chain up to the final commit (the windows' boundaries)
  actions.jsonl        the agent's tool calls: editor-step runs (command lines), Write/Edit of files, apply_patch,
                       shell commands
  workflow.jsonl       the rows each step run logged (op, target, status, params, source) at the final commit

Output (work/ledger.json, schema unity-replay.ledger/v1):
  windows[]   one per commit: sha, parent, time, subject, inputs (files the builder writes: code, text, source art,
              everything outside Assets/ and ProjectSettings/ but ProjectVersion.txt), content (what the editor
              writes: Unity's serialized assets and every .meta under Assets/, ProjectSettings/), runs[] (editor-step
              runs in order, each with the text of every code file the window changes as it stood when the run
              started), drops[] and shell[] (store packs and shell copies, moves and deletes of content),
              reconstruction checks at the boundary
  blobs       sha256 -> file text, stored by the caller in work/blobs/
"""
import collections
import datetime
import fnmatch
import hashlib
import json
import os
import re
import shlex
import subprocess

import patchfx
import shellfx
import unity_replay

SCHEMA = "unity-replay.ledger/v1"

# What the editor writes (Unity's serialized assets); every .meta under Assets/ counts too, and ProjectSettings/.
CONTENT_EXT = (".unity", ".prefab", ".mat", ".asset", ".anim", ".controller", ".overridecontroller", ".mask",
               ".physicmaterial", ".physicsmaterial2d", ".mixer", ".playable", ".signal", ".lighting", ".terrainlayer",
               ".spriteatlas", ".spriteatlasv2", ".rendertexture", ".cubemap", ".flare", ".guiskin", ".fontsettings",
               ".brush", ".preset", ".giparams", ".shadervariants", ".shadergraph", ".shadersubgraph", ".vfx",
               ".vfxoperator", ".vfxblock", ".scenetemplate", ".lightingsettings")
# Files the editor compiles: a run's code is these as they stood when it started.
CODE_EXT = (".cs", ".asmdef", ".asmref", ".rsp")
TEXT_EXT = CODE_EXT + (".shader", ".hlsl", ".cginc", ".compute", ".uss", ".uxml", ".tss", ".json", ".md", ".txt",
                       ".ps1", ".psm1", ".py", ".sh", ".bat", ".cmd", ".csv", ".tsv", ".xml", ".yaml", ".yml",
                       ".inputactions", ".gitignore", ".gitattributes")
VERSION_FILE = "ProjectSettings/ProjectVersion.txt"


def sha256(b):
    return hashlib.sha256(b).hexdigest()


def git(repo, *args, binary=False):
    out = subprocess.run(["git", "-C", repo, "-c", "core.quotepath=off"] + list(args), capture_output=True, check=True)
    return out.stdout if binary else out.stdout.decode("utf-8")


def parse_time(s):
    return datetime.datetime.fromisoformat(s)


def norm_text(b):
    """Text as stored in git (LF); code is compared and replayed with LF line ends."""
    return b.replace(b"\r\n", b"\n")


def is_content(path, extra_ext=()):
    """What the editor writes: Unity's serialized assets and .meta files under Assets/, and ProjectSettings/ (but the
    editor-version pin, which the builder writes and which picks each window's editor)."""
    p = path.lower()
    if p.startswith("assets/"):
        return p.endswith(".meta") or p.endswith(CONTENT_EXT + tuple(e.lower() for e in extra_ext))
    return p.startswith("projectsettings/") and path != VERSION_FILE


def is_code(path):
    """Files the editor compiles (a run's code at its start): C# and assembly definitions under Assets/ and Packages/,
    and the package manifest."""
    return (path.startswith(("Assets/", "Packages/")) and path.lower().endswith(CODE_EXT)) or path == "Packages/manifest.json"


# ----------------------------------------------------------------------------------------------- commits
def first_parent_chain(repo, final, recorded=None):
    """The commits up to final, oldest first. "time" is the commit's own time (whole seconds); "order", what the
    recorded tool calls are compared with, is the moment the post-commit recorder wrote the commit (commits.jsonl
    recorded_at, milliseconds, just after the commit), else the end of the commit's second: a call recorded in the same
    second as the commit that followed it was taken for one made after it."""
    rows = git(repo, "log", "--first-parent", "--reverse", "--format=%H%x09%P%x09%cI%x09%s", final).splitlines()
    out = []
    for r in rows:
        sha, parents, ctime, subject = r.split("\t", 3)
        order = (recorded or {}).get(sha)
        if not order or not (parse_time(ctime) <= parse_time(order) <= parse_time(ctime) + datetime.timedelta(minutes=10)):
            order = (parse_time(ctime) + datetime.timedelta(milliseconds=999)).isoformat(timespec="milliseconds")
        out.append({"sha": sha, "parents": parents.split(), "time": ctime, "order": order, "subject": subject})
    return out


def recorded_commits(recording):
    """sha -> recorded_at of the post-commit recorder's rows (commits.jsonl)."""
    out = {}
    p = os.path.join(recording, "commits.jsonl")
    if os.path.isfile(p):
        with open(p, encoding="utf-8", errors="replace") as f:
            for line in f:
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                if r.get("sha") and r.get("recorded_at"):
                    out.setdefault(r["sha"], r["recorded_at"])
    return out


def changed_paths(repo, parent, sha):
    """[(status, path)] of sha against its first parent (renames as delete + add)."""
    if parent is None:
        names = git(repo, "ls-tree", "-r", "--name-only", sha).splitlines()
        return [("A", p) for p in names]
    out = []
    for line in git(repo, "diff", "--no-renames", "--name-status", parent, sha).splitlines():
        st, p = line.split("\t", 1)
        out.append((st[0], p))
    return out


def blob_at(repo, sha, path):
    try:
        return git(repo, "show", "%s:%s" % (sha, path), binary=True)
    except subprocess.CalledProcessError:
        return None


# ----------------------------------------------------------------------------------------------- actions
# "exit code N (S s)" (Scripts/unity.ps1) or "exit=N seconds=S" (a wrapper of the game's own)
EXIT_RE = re.compile(r"(?<!: )exit code (-?\d+)(?: \((\d+) s\))?|exit=(-?\d+)(?: seconds=(\d+))?")
SETUP_EXIT_RE = re.compile(r"setup (\w+): exit code (-?\d+)")
ROW_RE = re.compile(r"\[workflow\] ([A-Za-z0-9]+-\d+) ")
# Scripts/unity.ps1's setup table: @('<name>', @('-executeMethod', '<Method>'), $true|$false) (the last: -quit)
SETUP_STEP_RE = re.compile(r"@\(\s*'(\w+)'\s*,\s*@\(\s*'-executeMethod'\s*,\s*'([\w.]+)'\s*\)\s*,\s*\$(true|false)\s*\)", re.I)
SETUP_REASON_RE = re.compile(r"UNITY_RUN_REASON\s*=\s*if\s*\(\$Reason\)\s*\{\s*\$Reason\s*\}\s*else\s*\{\s*'([^']*)'", re.I)
METHOD_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.]*\.[A-Za-z_][A-Za-z0-9_]*$")

# a shell command that exited non-zero still ran: its file edits and editor runs happened
RAN_EVENTS = ("PostToolUse", "PostToolUseFailure")
SHELL_TOOLS = ("Bash", "PowerShell")


def _param_expand(val, op, pat):
    """${v%%pat} ${v%pat} ${v##pat} ${v#pat} with glob patterns."""
    n = len(val)
    if op == "%%":
        return next((val[:i] for i in range(0, n + 1) if fnmatch.fnmatchcase(val[i:], pat)), val)
    if op == "%":
        return next((val[:i] for i in range(n, -1, -1) if fnmatch.fnmatchcase(val[i:], pat)), val)
    if op == "##":
        return next((val[i:] for i in range(n, -1, -1) if fnmatch.fnmatchcase(val[:i], pat)), val)
    return next((val[i:] for i in range(0, n + 1) if fnmatch.fnmatchcase(val[:i], pat)), val)


def subst_var(text, var, val):
    v = re.escape(var)
    text = re.sub(r"\$\{" + v + r"(%%|%|##|#)([^}]*)\}", lambda m: _param_expand(val, m.group(1), m.group(2)), text)
    return re.sub(r"\$(?:\{" + v + r"\}|" + v + r"\b)", lambda m: val, text)


def expand_loops(cmd):
    """`for v in a "b c" d; do ... $v ...; done` (one line or several) or PowerShell `foreach ($v in "a", "b") { ... }`
    around editor runs: [(command text with one value, lo, hi, posmap)], one per value. Copy k > 0 repeats the text
    around the loop: only its loop body counts (lo..hi), so runs outside the loop are not found twice. posmap maps a
    position back to the original command (iteration k's body inside the loop's span, in iteration order)."""
    m = re.search(r"\bfor (\w+) in ([^;\n]+?)\s*(?:;|\n)\s*do\b(.*?)(?:;|\n)\s*done\b", cmd, re.S)
    if m:
        try:
            values = shlex.split(m.group(2), posix=True)
        except ValueError:
            values = m.group(2).split()
    else:
        m = re.search(r"\bforeach\s*\(\s*\$(\w+)\s+in\s+([^)]+)\)\s*\{(.*?)\}", cmd, re.S | re.I)
        if not m:
            return [(cmd, 0, len(cmd), lambda p: p)]
        values = [v.strip().strip("'\"") for v in m.group(2).split(",") if v.strip()]
    var, body = m.group(1), m.group(3)
    if not values or not re.search(r"(?i)unity\.ps1|-executeMethod|new-game\.ps1", body):
        return [(cmd, 0, len(cmd), lambda p: p)]
    n, lo0, hi0 = len(values), m.start(), m.end()

    def mapper(k, blen):
        def f(p):
            if p < lo0:
                return p
            if p < lo0 + blen:
                return lo0 + (k + (p - lo0) / max(blen, 1)) / n * (hi0 - lo0)
            return p - (lo0 + blen) + hi0
        return f
    res = []
    for k, v in enumerate(values):
        b = subst_var(body, var, v)
        c = cmd[:lo0] + b + cmd[hi0:]
        res.append((c, 0, len(c), mapper(k, len(b))) if k == 0 else (c, lo0, lo0 + len(b), mapper(k, len(b))))
    return res


# NAME=literal at the start of a simple command (not after && / ||: conditional)
ASSIGN_RE = re.compile(r"(?:^|[;\n(]|\bdo\b|\bthen\b)[ \t]*(?:export[ \t]+)?([A-Za-z_]\w*)="
                       r"(\"[^\"$`]*\"|'[^']*'|[^\s;&|)$`'\"]*)(?=[\s;&|)]|$)")


def subst_assigned(cmd, pos, text):
    """$NAME in text, for a NAME the command assigned a literal value before pos (the last such assignment)."""
    vals = {}
    for m in ASSIGN_RE.finditer(cmd[:pos]):
        vals[m.group(1)] = m.group(2).strip("\"'")
    for k in sorted(vals, key=len, reverse=True):
        text = subst_var(text, k, vals[k])
    return text


def run_env(cmd, pos):
    """VAR=value assignments in front of the simple command that holds position pos (and earlier `export`s), and
    PowerShell $env:VAR = 'value' assignments before it."""
    start, q = -1, None   # last command separator before pos, outside quotes
    for i in range(pos):
        ch = cmd[i]
        if q:
            if ch == q:
                q = None
        elif ch in "'\"":
            q = ch
        elif ch in ";|\n" or cmd.startswith("&&", i):
            start = i
    env = {}
    for m in re.finditer(r"(?:^|\s)(?:export\s+)?([A-Z][A-Z0-9_]+)=(\"[^\"]*\"|'[^']*'|[^\s;&|]+)", cmd[:pos]):
        if m.group(1) in ("MSYS_NO_PATHCONV", "PATH"):
            continue
        if m.start() >= start or "export" in m.group(0):
            env[m.group(1)] = m.group(2).strip("\"'")
    for m in re.finditer(r"\$env:([A-Za-z_]\w*)\s*=\s*(\"[^\"]*\"|'[^']*')", cmd[:pos]):
        if m.group(1).upper() not in ("PATH", "UNITY_RUN_REASON"):
            env[m.group(1)] = m.group(2)[1:-1]
    return env


def _tokens(seg):
    """Words of a simple command, quotes removed, backslashes kept (Windows paths: .\\Scripts\\unity.ps1)."""
    try:
        lx = shlex.shlex(seg, posix=True)
        lx.whitespace_split = True
        lx.escape = ""
        lx.commenters = ""
        return list(lx)
    except ValueError:
        return seg.split()


def _opts(toks):
    """PowerShell-style options after a script call: {name lower: value or True}."""
    out, i = {}, 0
    while i < len(toks):
        t = toks[i]
        if t.startswith("-") and len(t) > 1 and not re.match(r"^-\d", t):
            name = t[1:].split(":", 1)[0].lower()
            if ":" in t:
                out[name] = t.split(":", 1)[1]
            elif i + 1 < len(toks) and not toks[i + 1].startswith("-"):
                out[name] = toks[i + 1]
                i += 1
            else:
                out[name] = True
        i += 1
    return out


def _base(tok):
    return os.path.basename(tok.strip("'\"").replace("\\", "/")).lower()


def setup_table(text):
    """The first-open runs of a game's Scripts/unity.ps1 setup mode: [(name, method, quit)], and its default reason."""
    if not text:
        return [], None
    t = text.decode("utf-8", "replace") if isinstance(text, bytes) else text
    i = t.find("'setup'")
    block = t[i:] if i >= 0 else t
    steps = [(m.group(1), m.group(2), m.group(3).lower() == "true") for m in SETUP_STEP_RE.finditer(block)]
    r = SETUP_REASON_RE.search(block)
    return steps, (r.group(1) if r else None)


def find_calls(seg, repo_abs, cwd):
    """The editor runs one simple command starts: [{kind, method, reason, quit, render, args, setup}] (setup runs are
    expanded later, when the window and its Scripts/unity.ps1 are known)."""
    toks = _tokens(seg)
    out = []
    for i, t in enumerate(toks):
        b = _base(t)
        if b == "unity.ps1":
            rest = toks[i + 1:]
            mode = None
            if rest and rest[0].lower() == "-mode" and len(rest) > 1:
                mode, rest = rest[1].lower(), rest[2:]
            elif rest and not rest[0].startswith("-"):
                mode, rest = rest[0].lower(), rest[1:]
            o = _opts(rest)
            if mode == "step":
                m = str(o.get("method") or "")
                out.append({"kind": "step", "method": m if METHOD_RE.match(m) else None, "reason": o.get("reason") if isinstance(o.get("reason"), str) else None,
                            "quit": "noquit" not in o, "render": "render" in o, "args": ""})
            elif mode == "setup":
                out.append({"kind": "setup", "method": None, "reason": o.get("reason") if isinstance(o.get("reason"), str) else None,
                            "quit": True, "render": False, "args": "", "setup": "unity.ps1"})
            elif mode in ("compile", "test", "build", "play"):
                out.append({"kind": "open_" + mode, "method": None})
            break
        if b == "new-game.ps1":
            o = _opts(toks[i + 1:])
            if "nosetup" not in o:
                out.append({"kind": "setup", "method": None, "reason": None, "quit": True, "render": False, "args": "",
                            "setup": "new-game.ps1", "new_game": True})
            break
        if b in ("unity.exe", "unity"):
            rest = toks[i + 1:]
            low = [x.lower() for x in rest]
            if "-executemethod" not in low:
                if "-batchmode" in low or "-projectpath" in low:
                    out.append({"kind": "open_direct", "method": None})
                break
            k = low.index("-executemethod")
            method = rest[k + 1] if k + 1 < len(rest) else ""
            proj = rest[low.index("-projectpath") + 1] if "-projectpath" in low and low.index("-projectpath") + 1 < len(rest) else ""
            pp = shellfx.win_path(proj.replace("\\", "/")).rstrip("/")
            if pp and not os.path.isabs(pp) and cwd:
                pp = os.path.normpath(os.path.join(cwd, pp)).replace("\\", "/")
            if pp.lower() != repo_abs.lower().rstrip("/"):
                break   # another project (a scratch copy, a task check): not this game's history
            skip = {"-batchmode", "-nographics", "-quit", "-projectpath", "-logfile", "-executemethod", "-silent-crashes", "-accept-apiupdate"}
            extra, j = [], 0
            while j < len(rest):
                x = rest[j]
                if x.lower() in ("-projectpath", "-logfile", "-executemethod"):
                    j += 2
                    continue
                if x.lower() not in skip:
                    extra.append(x)
                j += 1
            out.append({"kind": "direct", "method": method if METHOD_RE.match(method) else None, "reason": None,
                        "quit": "-quit" in low, "render": "-nographics" not in low, "args": " ".join(shlex.quote(x) for x in extra)})
            break
    return out


def editor_runs(actions, repo_abs, extra_patterns=()):
    """Editor-step runs found in shell commands, in order. Each: time (end of the tool call), approximate start,
    method, reason, flags, exit code / duration when the output says so, the workflow row ids it printed."""
    # extra patterns: a regex (named groups method, reason, args), or {"pattern": regex, "method": template,
    # "reason": template, "quit": bool, "render": bool} for a wrapper of the game's own; templates take {name} for the
    # pattern's named groups
    pats = []
    for x in extra_patterns:
        pats.append((re.compile(x["pattern"] if isinstance(x, dict) else x), x if isinstance(x, dict) else {}))
    runs, opens = [], []
    prev_by_session = {}   # tool calls are sequential within a session; other sessions' rows interleave in actions.jsonl
    for a in actions:
        sid = a.get("session_id")
        prev, prev_by_session[sid] = prev_by_session.get(sid), a["time"]
        if a.get("tool") not in SHELL_TOOLS or a.get("event") not in RAN_EVENTS:
            continue
        cmd = (a.get("input") or {}).get("command", "")
        if not isinstance(cmd, str) or not cmd:
            continue
        # heredoc bodies are file contents (e.g. a wrapper script being written), not commands; loops are expanded
        # first, so a run written as `for m in A B; do ./Scripts/unity.ps1 step -Method X.$m; done` is found
        text = shellfx.protect_heredocs(cmd)[0]
        if not re.search(r"(?i)unity\.ps1|-executeMethod|new-game\.ps1", text) and not any(p.search(text) for p, _ in pats):
            continue
        cwd = shellfx._abs(a.get("cwd") or "")
        found = []
        for c, lo_k, hi_k, posmap in expand_loops(text):
            for pos, seg in shellfx.segments(c, positions=True):
                if not (lo_k <= pos < hi_k):
                    continue
                for call in find_calls(seg, repo_abs, cwd):
                    if call["kind"].startswith("open_"):
                        opens.append({"time": a["time"], "tool_use_id": a.get("tool_use_id"), "kind": call["kind"],
                                      "command": seg[:300]})
                        continue
                    call["method"] = call["method"] and subst_assigned(c, pos, call["method"])
                    if call["kind"] in ("step", "direct") and not call["method"]:
                        opens.append({"time": a["time"], "tool_use_id": a.get("tool_use_id"), "kind": "unreadable",
                                      "command": seg[:300]})
                        continue
                    found.append((posmap(pos), call, run_env(c, pos), False))
                for p, tp in pats:
                    for m in p.finditer(seg):
                        g = {k: (v or "") for k, v in m.groupdict().items()}
                        method = tp["method"].format(**g) if tp.get("method") else g.get("method")
                        if not method:
                            continue
                        found.append((posmap(pos + m.start()), {
                            "kind": "pattern", "method": subst_assigned(c, pos, method),
                            "reason": (tp["reason"].format(**g) if tp.get("reason") else g.get("reason")) or None,
                            "quit": tp.get("quit", True), "render": tp.get("render", False),
                            "args": (tp.get("args", "{args}" if "args" in g else "").format(**g)).strip()}, run_env(c, pos), True))
        if not found:
            continue
        found.sort(key=lambda x: x[0])
        resp = shellfx.response_text(a)
        raw_resp = a.get("response") if isinstance(a.get("response"), str) else json.dumps(a.get("response"))
        bg = bool(re.search(r'"backgroundTaskId"', raw_resp or "")) or bool(re.search(r"[^&]&[ \t]*(?:\n|$|;|echo\b|wait\b|disown\b)", text))
        # the output, cut per run: Scripts/unity.ps1 ends each run with "exit code N (S s)"; its setup prints
        # "setup <name>: exit code N" after each of its runs
        n_plain = sum(1 for _, c, _, _ in found if c["kind"] != "setup")
        exits = [(m.group(1) or m.group(3), m.group(2) or m.group(4) or None, m.end()) for m in EXIT_RE.finditer(resp)]
        cut = 0
        for k, (pos, call, env, via_wrapper) in enumerate(found):
            base = {"time": a["time"], "action_tool_use_id": a.get("tool_use_id"), "after": prev, "env": env,
                    "background": bg, "via_wrapper": via_wrapper, "pos": pos, "command": cmd,
                    "event": a.get("event"), "cwd": a.get("cwd")}
            if call["kind"] == "setup":
                # expanded into the runs of the game's setup table by build() (it knows the commit); the output's
                # per-run exit lines and rows go with it
                seg_end = len(resp)
                setup_exits = {m.group(1): (int(m.group(2)), m.end()) for m in SETUP_EXIT_RE.finditer(resp, cut)}
                rows = []
                last = cut
                for name, (ec, end) in sorted(setup_exits.items(), key=lambda kv: kv[1][1]):
                    rows.append((name, ec, [x.group(1) for x in ROW_RE.finditer(resp, last, end)]))
                    last = end
                runs.append(dict(base, kind="setup", setup=call.get("setup"), new_game=call.get("new_game", False),
                                 reason=call.get("reason"), setup_results=rows))
                cut = max(cut, last if rows else cut)
                continue
            ex = None
            if len(exits) == n_plain:
                i = sum(1 for _, c, _, _ in found[:k] if c["kind"] != "setup")
                ex = exits[i]
            end = ex[2] if ex else (len(resp) if k == len(found) - 1 else None)
            rows_out = [x.group(1) for x in ROW_RE.finditer(resp, cut, end)] if end is not None else []
            if end is not None:
                cut = end
            runs.append(dict(base, kind=call["kind"], method=call["method"], reason=call.get("reason"),
                             quit=call.get("quit", True), render=call.get("render", False), args=call.get("args", ""),
                             exit_code=int(ex[0]) if ex else None, duration_s=int(ex[1]) if ex and ex[1] else None,
                             rows_out=rows_out))
    return runs, opens


def repo_rel(path, repo_abs):
    p = shellfx.win_path(path.replace("\\", "/"))
    root = repo_abs.replace("\\", "/").rstrip("/") + "/"
    if p.lower().startswith(root.lower()):
        return p[len(root):]
    return None


ABSENT = object()  # sentinel: the file does not exist yet


class FileStates:
    """Text of repo files as the agent's Write/Edit calls and shell edits left them. None = unknown."""

    ABSENT = None  # set below

    def __init__(self, repo, start_sha):
        self.repo = repo
        self.base_sha = start_sha
        self.state = {}       # path -> bytes | None (unknown) | ABSENT
        self.touched = set()  # paths written or edited since the last boundary
        self.how = {}         # path -> last kind of write
        self.tracked = None   # paths reported at boundaries (set by the caller)
        self.mismatch = {}    # sha256 -> reconstructed text that did not match its commit

    def get(self, path):
        """Current text; ABSENT when the file does not exist yet, None when unknown."""
        if path not in self.state:
            b = blob_at(self.repo, self.base_sha, path)
            self.state[path] = norm_text(b) if b is not None else ABSENT
        return self.state[path]

    def write(self, path, content):
        self.state[path] = norm_text(content.encode("utf-8"))
        self.touched.add(path)

    def edit(self, path, old, new, replace_all):
        cur = self.get(path)
        self.touched.add(path)
        if cur is None or cur is ABSENT:
            self.state[path] = None
            return False
        o, n = norm_text(old.encode("utf-8")), norm_text(new.encode("utf-8"))
        if o not in cur:
            self.state[path] = None
            return False
        self.state[path] = cur.replace(o, n) if replace_all else cur.replace(o, n, 1)
        return True

    def put(self, path, content, how):
        if content is not None and content is not ABSENT:
            content = norm_text(content)
        self.state[path] = content
        self.touched.add(path)
        self.how[path] = how

    def boundary(self, sha):
        """Compare what the recorded edits left with the commit, then reset to the commit."""
        checks = []
        for p in sorted(self.touched):
            if self.tracked is not None and p not in self.tracked:
                continue
            st = self.state.get(p)
            b = blob_at(self.repo, sha, p)
            blob = norm_text(b) if b is not None else None
            c = {"path": p, "reconstructed": st is not None, "how": self.how.get(p),
                 "match": st is not None and (st == blob if blob is not None else st is ABSENT)}
            if not c["match"] and isinstance(st, bytes):
                c["sha256"] = sha256(st)
                self.mismatch[c["sha256"]] = st
            checks.append(c)
        self.state = {}
        self.touched = set()
        self.how = {}
        self.base_sha = sha
        return checks


FileStates.ABSENT = ABSENT


def class_file(repo, sha, fs, cls, ns, cache):
    """The .cs file under Assets/ that declares class `cls` (in namespace `ns`): at the run's time for files the window
    has touched, else at commit sha. None when no file does."""
    key = (sha, cls, ns)
    if key not in cache:
        try:
            hits = git(repo, "grep", "-l", "-E", r"(class|struct)\s+%s\b" % re.escape(cls), sha, "--", "*.cs").splitlines()
        except subprocess.CalledProcessError:
            hits = []
        cache[key] = [h.split(":", 1)[1] for h in hits if ":" in h]
    cands = list(cache[key]) + [p for p in fs.touched if p.endswith(".cs") and p not in cache[key]]
    best = None
    for p in cands:
        st = fs.get(p)
        if not isinstance(st, bytes):
            continue
        t = st.decode("utf-8", "replace")
        if not re.search(r"(class|struct)\s+%s\b" % re.escape(cls), t):
            continue
        if ns and not re.search(r"namespace\s+%s\b" % re.escape(ns), t):
            best = best or p
            continue
        return p
    return best


# ----------------------------------------------------------------------------------------------- build
def build(cfg):
    repo = cfg["repo"]
    repo_abs = os.path.abspath(repo).replace("\\", "/")
    final = git(repo, "rev-parse", cfg["final"]).strip()
    chain = first_parent_chain(repo, final, recorded_commits(cfg["recording"]))
    # fold_commits: commits that hold only part of the work done before them (e.g. a README-only commit while the
    # steps and code those runs used came a commit later) are not window boundaries; their work goes to the next one
    fold = [f.lower() for f in cfg.get("fold_commits", [])]
    chain = [c for c in chain if c["sha"] == final or not any(c["sha"].lower().startswith(f) for f in fold)]
    path = os.path.join(cfg["recording"], "actions.jsonl")
    actions = []
    if os.path.isfile(path):
        with open(path, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    try:
                        actions.append(json.loads(line))
                    except ValueError:
                        pass
    actions.sort(key=lambda a: a["time"])
    t_final = parse_time(chain[-1]["order"])
    actions = [a for a in actions if parse_time(a["time"]) <= t_final + datetime.timedelta(seconds=60)]
    wf_rows = [json.loads(l) for l in git(repo, "show", "%s:workflow.jsonl" % final).splitlines() if l.strip()] \
        if blob_at(repo, final, "workflow.jsonl") is not None else []
    rows_by_id = {r.get("id"): r for r in wf_rows}

    runs, opens = editor_runs(actions, repo_abs, cfg.get("run_patterns", []))
    # runs_from_rows: runs the recording missed (a gap in the action hooks; a tool call interrupted while its editor
    # kept running records no PostToolUse event), rebuilt from the workflow row the step wrote when it ran
    # ({"row": "<id>", "method": "<Ns.Class.Method>", "reason": ..., "quit": true}). Each becomes a pseudo-action at the
    # row's time, so it lands in its window like a recorded command.
    for item in cfg.get("runs_from_rows", []):
        row = rows_by_id.get(item["row"])
        if not row:
            raise SystemExit("runs_from_rows: no workflow row %s at the final commit" % item["row"])
        if not item.get("method"):
            raise SystemExit("runs_from_rows: %s needs the method that ran (\"method\": \"<Ns.Class.Method>\")" % item["row"])
        tid = "row:" + item["row"]
        runs.append({"time": row["time"], "action_tool_use_id": tid, "kind": "row", "method": item["method"],
                     "reason": item.get("reason") or row.get("reason"), "quit": item.get("quit", True), "render": False,
                     "args": "", "exit_code": (row.get("params") or {}).get("exit_code"), "duration_s": None,
                     "background": False, "after": None, "env": item.get("env", {}), "via_wrapper": False, "pos": 0,
                     "rows_out": [item["row"]], "from_row": item["row"],
                     "command": "(not in the recorded actions: rebuilt from workflow row %s)" % item["row"]})
        actions.append({"time": row["time"], "tool": "Bash", "event": "PostToolUse", "tool_use_id": tid,
                        "input": {"command": ""}, "session_id": "runs_from_rows"})
    # A run whose editor finished before a commit that the tool call itself outlived belongs before that commit: its
    # last workflow row dates its end; it is attached there through a pseudo-action, like a recorded command
    commit_times = [parse_time(c["order"]) for c in chain]
    for k, r in enumerate(runs):
        ts = [rows_by_id[i]["time"] for i in r.get("rows_out") or [] if i in rows_by_id]
        if r.get("kind") == "setup":
            ts = [rows_by_id[i]["time"] for _, _, ids in r.get("setup_results") or [] for i in ids if i in rows_by_id]
        if ts and r.get("kind") != "row":
            r["log_end"] = max(ts)
            if not r.get("new_game") and any(parse_time(r["log_end"]) < t <= parse_time(r["time"]) for t in commit_times):
                r["attach_id"] = "logend:%d:%s" % (k, r.get("action_tool_use_id"))
                actions.append({"time": r["log_end"], "tool": "Bash", "event": "PostToolUse", "tool_use_id": r["attach_id"],
                                "input": {"command": ""}, "session_id": "log_end"})
    actions.sort(key=lambda a: a["time"])
    for r in runs:
        if r.get("duration_s") is not None and not r["background"]:
            r["start"] = (parse_time(r["time"]) - datetime.timedelta(seconds=r["duration_s"])).isoformat(timespec="milliseconds")
        else:
            r["start"] = r["time"]

    # windows by commit time (the first commit has no window: it is the starting point)
    extra_ext = cfg.get("content_ext", [])
    windows = []
    for i, c in enumerate(chain):
        parent = chain[i - 1]["sha"] if i else None
        ch = changed_paths(repo, parent, c["sha"])
        windows.append({
            "index": i, "sha": c["sha"], "parent": parent, "time": c["time"], "order": c["order"], "subject": c["subject"],
            "merge_parents": c["parents"][1:],
            "inputs": [{"status": s, "path": p} for s, p in ch if not is_content(p, extra_ext)],
            "content": [{"status": s, "path": p} for s, p in ch if is_content(p, extra_ext)],
            "code_changed": sorted(p for s, p in ch if is_code(p)),
            "runs": [], "drops": [], "shell": [], "shell_unreadable": [], "reconstruction": [],
            "events": collections.Counter(),
        })

    # walk actions in time order: file states, runs (with code texts), drops, shell steps
    fs = FileStates(repo, chain[0]["sha"])
    blobs = {}
    tracked = set(x["path"] for w in windows for x in w["inputs"]
                  if x["path"].lower().endswith(TEXT_EXT) and x["path"] != "workflow.jsonl")
    sandbox = shellfx.Sandbox(repo_abs)
    fs.tracked = tracked
    aux = {}  # helper files the agent wrote outside the repo (absolute path -> text)
    run_by_tool = collections.defaultdict(list)
    for r in runs:
        run_by_tool[r.get("attach_id") or r["action_tool_use_id"]].append(r)
    drops = {d["id"]: d for d in cfg.get("asset_drops", [])}
    shells = cfg.get("shell_replay", [])
    seen_tool = set()
    class_cache = {}
    commit_blobs = {}   # (sha, path) -> code text at that commit (None when not in it)
    cur_w = 1
    run_seq = 0

    def close_until(t):
        nonlocal cur_w
        while cur_w < len(windows) and parse_time(windows[cur_w]["order"]) < parse_time(t):
            windows[cur_w]["reconstruction"] = fs.boundary(windows[cur_w]["sha"])
            cur_w += 1

    def close_through(k):
        nonlocal cur_w
        while cur_w <= k and cur_w < len(windows):
            windows[cur_w]["reconstruction"] = fs.boundary(windows[cur_w]["sha"])
            cur_w += 1

    commit_rx = re.compile(r"\bgit\b(?:\s+-c\s+\S+)*\s+commit\b")
    content_test = lambda p: is_content(p, extra_ext)

    def add_run(w, r):
        """One run in window w: expanded (setup) and given the texts it started with."""
        nonlocal run_seq
        calls = [r]
        if r.get("kind") == "setup":
            # the game's Scripts/unity.ps1 setup table as it stood then (new-game.ps1: the skeleton's, the first commit)
            st = blob_at(repo, chain[0]["sha"], "Scripts/unity.ps1") if r.get("new_game") else fs.get("Scripts/unity.ps1")
            if not isinstance(st, bytes):   # unknown or not there yet: the window's commit has the game's version
                st = blob_at(repo, w["sha"], "Scripts/unity.ps1")
            steps, default_reason = setup_table(st if isinstance(st, bytes) else None)
            results = {name: (ec, ids) for name, ec, ids in r.get("setup_results") or []}
            calls = []
            for name, method, quit_ in steps:
                ec, ids = results.get(name, (None, []))
                calls.append(dict(r, kind="setup", setup_step=name, method=method, quit=quit_, render=False, args="",
                                  reason=r.get("reason") or default_reason, exit_code=ec, duration_s=None, rows_out=ids,
                                  not_run=None if name in results or not results else
                                  "the first open stopped before this run (no exit line for it in the output)"))
        for c in calls:
            run_seq += 1
            method = c["method"]
            parts = method.split(".")
            cls, ns = (parts[-2], ".".join(parts[:-2])) if len(parts) > 1 else (parts[0], "")
            # every code file the window changes that the builder wrote in it (the recorded Write/Edit/patch/shell edits),
            # as it stood when the run started. A code file the window changes without a recorded write was changed by
            # the editor (Packages/manifest.json through the Package Manager, code a step generates) or outside the
            # recording: it keeps the commit's text (the inputs), whatever the run.
            texts, unknown, absent = {}, [], []
            for p in w["code_changed"]:
                if p not in fs.touched:
                    continue
                st = fs.get(p)
                if st is None:
                    unknown.append(p)
                elif st is ABSENT:
                    absent.append(p)
                else:
                    h = sha256(st)
                    blobs[h] = st
                    texts[p] = h
            # use_commit_text: code texts in a window the recording cannot rebuild although it seems to (the boundary
            # check shows the mismatch): runs use the window's commit text instead
            for u in cfg.get("use_commit_text", []):
                if u["script"] in texts and w["index"] in u.get("windows", [w["index"]]):
                    del texts[u["script"]]
                    unknown.append(u["script"])
            script = None
            ids = [i for i in c.get("rows_out") or [] if i in rows_by_id]
            srcs = [(rows_by_id[i].get("source") or {}).get("script") for i in ids]
            srcs = [s for s in srcs if s]
            if srcs:
                script = collections.Counter(srcs).most_common(1)[0][0]
            if not script or not script.startswith("Assets/"):
                script = class_file(repo, w["sha"], fs, cls, ns, class_cache) or script
            rr = dict(c, id="R%04d" % run_seq, window=w["index"], cls=cls, script=script or "", texts=texts,
                      unknown=unknown, absent=absent)
            rr.pop("setup_results", None)
            if not script:
                rr["script_version"] = "unknown_file"
            elif not script.startswith(("Assets/", "Packages/")):
                rr["script_version"] = "external"
            elif script in texts:
                rr["script_version"] = "reconstructed"
            elif script in unknown or script in absent:
                rr["script_version"] = "unknown_use_commit"
            elif script in w["code_changed"]:
                rr["script_version"] = "commit_text"   # changed in the window without a recorded write
            else:
                rr["script_version"] = "unchanged"
            # the code differs from the window's commit at this run's start (earlier texts of files the window changes)
            diff = []
            for p in w["code_changed"]:
                if p not in texts and p not in absent:
                    continue
                key = (w["sha"], p)
                if key not in commit_blobs:
                    b = blob_at(repo, w["sha"], p)
                    commit_blobs[key] = norm_text(b) if b is not None else None
                if p in texts:
                    if commit_blobs[key] is None or commit_blobs[key] != blobs[texts[p]]:
                        diff.append(p)
                elif p in absent and commit_blobs[key] is not None:
                    diff.append(p)
            if diff:
                rr["code_at_run_time"] = diff
            w["runs"].append(rr)

    for a in actions:
        # A command with `git commit` in it did its work around its own commits: close only the windows whose commits
        # came before the command started (after the session's previous tool call), so its edits and runs land in the
        # window the next commit closes. A run that comes after n of the command's own commits in the command text
        # lands after the n-th of them. new-game.ps1 makes the first commit and, after its first open, the second: its
        # runs go in the window the second one closes.
        tool = a.get("tool")
        cmd_text = (a.get("input") or {}).get("command", "") if tool in SHELL_TOOLS else ""
        cmd_text = cmd_text if isinstance(cmd_text, str) else ""
        prot = shellfx.protect_heredocs(cmd_text)[0] if cmd_text else ""
        ops, unread = (shellfx.content_ops(a, repo_abs, content_test) if cmd_text and a.get("event") in RAN_EVENTS else ([], []))
        my_runs = run_by_tool.get(a.get("tool_use_id"), [])
        new_game = any(r.get("new_game") for r in my_runs)
        cmd_commit_pos, cmd_windows = [], []
        if (my_runs or ops) and ("git commit" in cmd_text or new_game):
            first = my_runs[0] if my_runs else {}
            t_start = first.get("after") or first.get("start") or a["time"]
            if new_game:
                t_start = min(parse_time(t_start), parse_time(chain[0]["time"]) - datetime.timedelta(seconds=1)).isoformat()
            close_until(t_start)
            cmd_commit_pos = [m.start() for m in commit_rx.finditer(prot)] + ([len(prot)] if new_game else [])
            cmd_windows = [k for k in range(cur_w, len(windows))
                           if parse_time(t_start) <= parse_time(windows[k]["order"]) <= parse_time(a["time"])]
            # more commits in that span than the command makes: the earlier ones are not its own (the end-of-turn WIP
            # commit between two turns), so they close before its work
            extra = len(cmd_windows) - len(cmd_commit_pos)
            if extra > 0:
                close_through(cmd_windows[extra - 1])
                cmd_windows = cmd_windows[extra:]
        else:
            close_until(a["time"])
        if cur_w >= len(windows):
            break
        w = windows[cur_w]
        if a.get("event") != "PostToolUse" and not (tool in SHELL_TOOLS and a.get("event") in RAN_EVENTS):
            continue
        inp = a.get("input") or {}
        if tool in SHELL_TOOLS and cmd_text:
            fx = []
            shellfx.apply_command(a, fs, sandbox, tracked, fx, aux)
            if fx:
                w["events"]["shell_edits"] += len(fx)
                for e in fx:
                    if e[0].endswith("failed"):
                        w["events"]["shell_edit_failed"] += 1
        if tool == "Write" and not repo_rel(inp.get("file_path", ""), repo_abs):
            aux[shellfx._abs(inp.get("file_path", ""))] = inp.get("content", "")
        if tool == "Write":
            p = repo_rel(inp.get("file_path", ""), repo_abs)
            if p:
                fs.write(p, inp.get("content", ""))
                w["events"]["write"] += 1
        elif tool == "Edit":
            p = repo_rel(inp.get("file_path", ""), repo_abs)
            if p:
                ok = fs.edit(p, inp.get("old_string", ""), inp.get("new_string", ""), inp.get("replace_all", False))
                w["events"]["edit" if ok else "edit_unapplied"] += 1
        elif tool == "MultiEdit":
            p = repo_rel(inp.get("file_path", ""), repo_abs)
            if p:
                for e in inp.get("edits") or []:
                    ok = fs.edit(p, e.get("old_string", ""), e.get("new_string", ""), e.get("replace_all", False))
                    w["events"]["edit" if ok else "edit_unapplied"] += 1
        elif tool == "apply_patch" and isinstance(inp.get("command"), str):
            # one patch adds, deletes, updates or moves files (patchfx.py); a patch that does not parse or a hunk that
            # does not apply leaves the file unknown, like an Edit whose old text is not there
            try:
                pops = patchfx.parse(inp["command"])
            except ValueError:
                pops = None
                w["events"]["patch_unparsed"] += 1
            for op, ppath, data in pops or []:
                full = patchfx.resolve(ppath, a.get("cwd") or "")
                p = repo_rel(full, repo_abs)
                if op == "add":
                    if p:
                        fs.write(p, data)
                        w["events"]["patch"] += 1
                    else:
                        aux[full] = data
                elif op == "delete" and p:
                    fs.put(p, ABSENT, "apply_patch")
                    w["events"]["patch"] += 1
                elif op == "update" and p:
                    cur = fs.get(p)
                    new = patchfx.apply_update(cur.decode("utf-8", "replace"), data["hunks"]) if isinstance(cur, bytes) else None
                    dest = repo_rel(patchfx.resolve(data["move"], a.get("cwd") or ""), repo_abs) if data["move"] else p
                    if new is None:
                        fs.put(p, None, "apply_patch")
                        w["events"]["patch_unapplied"] += 1
                        continue
                    if dest != p:
                        fs.put(p, ABSENT, "apply_patch")
                    if dest:
                        fs.write(dest, new)
                    w["events"]["patch"] += 1
        elif tool == "apply_patch" and isinstance(inp.get("changes"), dict):
            # a session imported from its transcript keeps the changes, not the patch text: the files become unknown
            for ppath in inp["changes"]:
                p = repo_rel(patchfx.resolve(ppath, a.get("cwd") or ""), repo_abs)
                if p:
                    fs.put(p, None, "apply_patch_changes")
                    w["events"]["patch_unknown"] += 1
        if tool in SHELL_TOOLS:
            for d in drops.values():
                # match strings may hold {root}/{home}: the recording's own paths, on whatever machine it was made
                if d.get("match") and unity_replay.has_recorded(d["match"], cmd_text) >= 0 and d["id"] not in seen_tool:
                    seen_tool.add(d["id"])
                    w["drops"].append(dict(d, time=a["time"]))
            matched = False
            for s in shells:
                if unity_replay.has_recorded(s["match"], cmd_text) >= 0 and ("shell", s["match"]) not in seen_tool:
                    seen_tool.add(("shell", s["match"]))
                    w["shell"].append(dict(s, time=a["time"], pos=unity_replay.has_recorded(s["match"], prot)))
                    matched = True
            # items of this command in their order: runs (texts as of before the command's own later writes) and the
            # shell copies, moves and deletes of content (unless a shell_replay entry covers the command)
            items = [("run", r.get("pos") or 0, r) for r in my_runs]
            if not matched:
                items += [("op", o["pos"], o) for o in ops]
                for u in unread:
                    w["shell_unreadable"].append(dict(u, time=a["time"]))
            items.sort(key=lambda x: x[1])
            for kind, pos, item in items:
                if cmd_windows and cmd_commit_pos:
                    n = sum(1 for p in cmd_commit_pos if p < pos)
                    if n:
                        close_through(cmd_windows[min(n, len(cmd_windows)) - 1])
                        if cur_w >= len(windows):
                            continue   # after the last commit: not part of the replayed history
                        w = windows[cur_w]
                if kind == "run":
                    add_run(w, item)
                else:
                    w["shell"].append({"argv": [item["op"]] + item["src"] + ([item["dst"]] if item["dst"] else []),
                                       "op": item["op"], "src": item["src"], "dst": item["dst"], "into": item.get("into", False),
                                       "recursive": item["recursive"], "auto": True, "time": a["time"], "pos": pos,
                                       "id": "S%s_%d" % ((a.get("tool_use_id") or "x")[-8:], pos),
                                       "command": cmd_text[max(0, pos - 20):pos + 200]})
        elif my_runs:
            for r in my_runs:   # a pseudo-action (a run rebuilt from a row, or attached at its last row)
                add_run(w, r)
    close_until("9999-12-31T00:00:00+00:00")
    sandbox.close()
    blobs.update(fs.mismatch)

    # rows each run logged: the ids it printed, else by its step file and its time span
    by_script = collections.defaultdict(list)
    wrapper_by_method = collections.defaultdict(list)
    wrapper_ops = set(cfg.get("wrapper_row_ops", []))   # rows a game's run wrapper logs around each run (not the step's)
    for row in wf_rows:
        if row.get("op") in wrapper_ops:
            wrapper_by_method[str(row.get("target") or "").split(" ")[0]].append(row)
            continue
        s = (row.get("source") or {}).get("script")
        if s:
            by_script[s.replace("\\", "/")].append(row)
    all_runs = [r for w in windows for r in w["runs"]]
    for k, r in enumerate(all_runs):
        if r.get("rows_out"):
            r["rows"] = [i for i in r["rows_out"] if i in rows_by_id and rows_by_id[i].get("op") not in wrapper_ops]
            r["rows_from"] = "output"
        else:
            nxt = next((x for x in all_runs[k + 1:] if x["script"] == r["script"]), None)
            # rows are written while the tool call runs: after the previous tool call ended (tool calls are sequential)
            lo = parse_time(r["after"] or r["start"]) - datetime.timedelta(seconds=1)
            prev_same = next((x for x in reversed(all_runs[:k]) if x["script"] == r["script"] and x["time"] == r["time"]), None)
            if prev_same:  # the same step twice in one command: split at the first run's estimated end
                lo = max(lo, parse_time(prev_same["time"]))
            hi = parse_time(nxt["start"]) if nxt else parse_time(r["time"]) + datetime.timedelta(hours=2)
            hi = min(hi, parse_time(r["time"]) + datetime.timedelta(seconds=5)) if not r["background"] else hi
            r["rows"] = [x["id"] for x in by_script.get(r["script"], []) if r["script"] and lo <= parse_time(x["time"]) <= hi]
            r["rows_from"] = "time"
        for nr in cfg.get("not_run", []):
            # runs the records show never happened (a loop stopped, a refused start)
            if nr.get("tool_use_id") == r.get("action_tool_use_id") and (not nr.get("method") or nr["method"] == r["method"]):
                r["not_run"] = nr.get("reason", "listed in settings not_run")
        if wrapper_ops and r.get("via_wrapper"):
            # the game's run wrapper logs a row before every run it starts: none means the command never got there
            r["wrapper_rows"] = sum(1 for x in wrapper_by_method.get(r["method"], [])
                                    if parse_time(r["after"] or r["start"]) <= parse_time(x["time"]) <= parse_time(r["time"]) + datetime.timedelta(seconds=5))
        ro = cfg.get("readonly_patterns", [])
        r["readonly"] = any(fnmatch.fnmatchcase(r["cls"], p) for p in ro) and r["cls"] not in cfg.get("not_readonly", [])
        # not_readonly_runs: single runs of a read-only-looking step whose side effect a later run needs
        if any(n.get("tool_use_id") == r["action_tool_use_id"] and (not n.get("method") or n["method"] == r["method"])
               for n in cfg.get("not_readonly_runs", [])):
            r["readonly"] = False
    for w in windows:
        w["events"] = dict(w["events"])
    return {"schema": SCHEMA, "game": cfg["game"], "final": final, "first": chain[0]["sha"],
            "windows": windows, "editor_opens": opens, "counts": {
                "windows": len(windows) - 1, "runs": len(all_runs),
                "runs_readonly": sum(1 for r in all_runs if r["readonly"]),
                "script_version": dict(collections.Counter(r["script_version"] for r in all_runs)),
                "runs_with_unknown_code": sum(1 for r in all_runs if r["unknown"]),
                "runs_with_earlier_code": sum(1 for r in all_runs if r.get("code_at_run_time")),
                "shell_steps": sum(len(w["shell"]) for w in windows),
                "reconstruction_checks": sum(len(w["reconstruction"]) for w in windows),
                "reconstruction_match": sum(1 for w in windows for c in w["reconstruction"] if c["match"]),
                "reconstruction_unknown": sum(1 for w in windows for c in w["reconstruction"] if not c["reconstructed"]),
            }}, blobs
