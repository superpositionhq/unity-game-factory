"""Take the account name out of the Git LFS objects of a game's own history (assets committed before
scrub-import-paths.py fixed them), byte for byte, and point every commit at the fixed objects.

    python tools/unity-pipeline/scrub-lfs-history.py <game>            # dry run: the objects and what the patch would do
    python tools/unity-pipeline/scrub-lfs-history.py <game> --apply

Options: --quiet-minutes N (default 10), --unpatchable-use-head, --repo <folder> (testing: a repo elsewhere).

The dataset packager already delivers patched copies of such objects (export-lfs-history.py); this rewrites the game
repo itself, for a repo that is handed out as it is. scrub-history.ps1 rewrites text blobs, messages and identities and
never touches LFS content. Here every LFS object any ref references is scanned (scrub-import-paths.py's terms and safe
contexts, ASCII and UTF-16LE); each object with matches is rewritten, same length, into a NEW object in the repo's LFS
store, and every commit that pointed at the old object is rewritten to point at the new one (git filter-branch
--index-filter over all refs, tags kept). An object with a match outside a safe context stops the run, unless
--unpatchable-use-head finds HEAD's clean version of the same path, which then stands in for it in every commit.

--apply refuses with uncommitted changes, while the game's recording was written within --quiet-minutes (its session
looks active), or while an editor has the project open. It first archives a verified git bundle of all refs to
<root>/.recording/<game>/original-history/ (the old LFS objects stay in the store, so the bundle and the store restore
everything); afterwards it checks that no referenced object still holds a term, that HEAD's tree is unchanged unless
HEAD itself referenced a patched object, and `git lfs fsck`; then it removes filter-branch's refs/original backups.
It never pushes and never runs gc. Commit ids change from the first commit that referenced a patched object;
workflow.jsonl rows and the recording that name old ids are not rewritten.
"""
import argparse, datetime, importlib.util, json, os, shutil, subprocess, sys, tempfile, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'machine', 'lib'))
import ugfroot  # noqa: E402


def _load(name, file):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, file))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


sip = _load('scrub_import_paths', 'scrub-import-paths.py')
elh = _load('export_lfs_history', 'export-lfs-history.py')
git = elh.git


def referenced_pointers(repo):
    """{pointer blob sha: (oid, size, {paths})} for every LFS pointer blob reachable from any ref but refs/original."""
    refs = [r for r in git(repo, 'for-each-ref', '--format=%(refname)').decode().split() if not r.startswith('refs/original/')]
    if not refs:
        return {}
    objs = git(repo, 'rev-list', '--objects', *refs).decode('utf-8', 'replace')
    chk = git(repo, 'cat-file', '--batch-check=%(objecttype) %(objectname) %(objectsize) %(rest)', inp=objs.encode()).decode('utf-8', 'replace')
    cand = [(p[1], p[3] if len(p) > 3 else '') for p in (l.split(' ', 3) for l in chk.splitlines())
            if len(p) >= 3 and p[0] == 'blob' and int(p[2]) < 300]
    out = git(repo, 'cat-file', '--batch', inp=('\n'.join(s for s, _ in cand) + '\n').encode()) if cand else b''
    pos, res = 0, {}
    for sha, path in cand:
        nl = out.index(b'\n', pos)
        size = int(out[pos:nl].split()[2])
        body = out[nl + 1:nl + 1 + size]
        pos = nl + 1 + size + 1
        lines = body.decode('ascii', 'replace').splitlines()
        if lines and lines[0].startswith('version https://git-lfs.github.com/spec/v1'):
            oid = next((l.split('sha256:', 1)[1].strip() for l in lines if l.startswith('oid sha256:')), None)
            sz = next((int(l.split()[1]) for l in lines if l.startswith('size ') and l.split()[1].isdigit()), None)
            if oid:
                res.setdefault(sha, (oid, sz, set()))[2].add(path)
    return res


def scan(repo, pointers, pats):
    """[(pointer sha, oid, paths, counts)] of the objects with matches; stops when an object is not in the local store."""
    store, hits = elh.lfs_store(repo), []
    for sha, (oid, _sz, paths) in pointers.items():
        fp = elh.object_path(store, oid)
        if not os.path.exists(fp):
            raise SystemExit('LFS object %s (%s) is not in the local store: git lfs fetch --all first' % (oid, sorted(paths)[0]))
        counts, _unpatchable, _rw = sip._stream(fp, pats)
        if counts:
            hits.append((sha, oid, sorted(paths), counts))
    return hits


def recording_quiet(root, game, minutes):
    p = os.path.join(root, '.recording', game, 'actions.jsonl')
    return not os.path.exists(p) or time.time() - os.path.getmtime(p) > minutes * 60


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('game')
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--quiet-minutes', type=int, default=10)
    ap.add_argument('--unpatchable-use-head', action='store_true')
    ap.add_argument('--repo', help='testing only: this repo instead of <root>/games/<game>')
    a = ap.parse_args()
    root = ugfroot.root()
    repo = os.path.abspath(a.repo or os.path.join(root, 'games', a.game))
    pats = sip.byte_patterns()
    print('== scrub-lfs-history %s (%s) repo %s; terms: %s' % (a.game, 'APPLY' if a.apply else 'dry run', repo,
                                                                ', '.join(sorted({p[0].split(' ')[0] for p in pats}))))
    pointers = referenced_pointers(repo)
    hits = scan(repo, pointers, pats)
    print('%d LFS pointers in the history, %d name an object with a term' % (len(pointers), len(hits)))
    tmp = tempfile.mkdtemp(prefix='scrub-lfs-')
    store = elh.lfs_store(repo)
    plan = []
    for sha, oid, paths, counts in hits:
        out = os.path.join(tmp, oid)
        _c, unpatchable, rewritten = sip._stream(elh.object_path(store, oid), pats, patch_to=out)
        print('  %s %s  %s  rewritten %d%s' % (oid[:12], paths[0], json.dumps(counts), rewritten,
                                             ('  UNPATCHABLE %d (not a path, a whole string or an element)' % unpatchable) if unpatchable else ''))
        plan.append((sha, oid, paths, out, unpatchable, rewritten))
    head_ptr = {}
    for line in git(repo, 'ls-tree', '-r', 'HEAD').decode('utf-8', 'replace').splitlines():
        meta, path = line.split('\t', 1)
        head_ptr[path] = meta.split()[2]
    substitute = {}
    for sha, oid, paths, out, unpatchable, rewritten in plan:
        if not (unpatchable or not rewritten) or not a.unpatchable_use_head:
            continue
        hs = next((head_ptr[p] for p in paths if p in head_ptr and head_ptr[p] in pointers), None)
        if hs and not any(h[0] == hs for h in hits):
            substitute[sha] = hs
            print("  %s %s: HEAD's version (pointer %s) stands in for it in every commit" % (oid[:12], paths[0], hs[:10]))
    bad = [p for p in plan if (p[4] or not p[5]) and p[0] not in substitute]
    if bad:
        shutil.rmtree(tmp, ignore_errors=True)
        raise SystemExit('%d object(s) have matches outside a safe context: nothing changed. Re-export them, or pass '
                         '--unpatchable-use-head when HEAD has a clean version of the same path' % len(bad))
    plan = [p for p in plan if p[0] not in substitute]
    if not a.apply or not (plan or substitute):
        print('dry run: nothing changed' if not a.apply else 'nothing to do')
        shutil.rmtree(tmp, ignore_errors=True)
        return 0

    # ---- safety ----
    if git(repo, 'status', '--porcelain', '--untracked-files=no').strip():
        raise SystemExit('uncommitted changes in %s: commit them first' % repo)
    if not a.repo and not recording_quiet(root, a.game, a.quiet_minutes):
        raise SystemExit("the game's recording was written in the last %d min: is its session still working?" % a.quiet_minutes)
    if sip.editor_open(repo):
        raise SystemExit('an editor has %s open' % repo)
    stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    arch = os.path.join(root, '.recording', a.game, 'original-history') if not a.repo else os.path.join(tmp, 'archive')
    os.makedirs(arch, exist_ok=True)
    bundle = os.path.join(arch, '%s-%s-before-lfs-scrub.bundle' % (a.game, stamp))
    git(repo, 'bundle', 'create', bundle, '--all')
    git(repo, 'bundle', 'verify', bundle)
    print('archived all refs: %s' % bundle)
    head_tree = git(repo, 'rev-parse', 'HEAD^{tree}').decode().strip()
    head_had = bool(set(head_ptr.values()) & set(p[0] for p in plan))

    # ---- the new objects and pointer blobs ----
    mapping = {}
    for sha, oid, paths, out, _u, _r in plan:
        new_oid = elh.sha256_file(out)
        size = os.path.getsize(out)
        dst = elh.object_path(store, new_oid)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        if not os.path.exists(dst):
            shutil.copyfile(out, dst)
        ptr = 'version https://git-lfs.github.com/spec/v1\noid sha256:%s\nsize %d\n' % (new_oid, size)
        mapping[sha] = git(repo, 'hash-object', '-w', '--stdin', inp=ptr.encode()).decode().strip()
    mapping.update(substitute)
    mfile = os.path.join(tmp, 'map.txt')
    with open(mfile, 'w', encoding='ascii', newline='\n') as f:
        f.write(''.join('%s %s\n' % kv for kv in mapping.items()))
    pl = os.path.join(tmp, 'swap.pl')
    with open(pl, 'w', encoding='ascii', newline='\n') as f:
        f.write('open(M, "<", $ARGV[0]) or die; my %m; while (<M>) { chomp; my ($a, $b) = split / /; $m{$a} = $b; } close M;\n'
                'while (<STDIN>) { if (/^(\\d+) ([0-9a-f]{40}) (\\d+)\\t(.*)$/s && exists $m{$2}) { print "$1 $m{$2} $3\\t$4"; } }\n')
    to_sh = (lambda p: '/' + p[0].lower() + p[2:].replace('\\', '/')) if os.name == 'nt' else (lambda p: p)
    idx = "git ls-files -s | perl '%s' '%s' | git update-index --index-info" % (to_sh(pl), to_sh(mfile))
    env = dict(os.environ, FILTER_BRANCH_SQUELCH_WARNING='1')
    r = subprocess.run(['git', '-C', repo, 'filter-branch', '-f', '--index-filter', idx, '--tag-name-filter', 'cat', '--', '--all'],
                       capture_output=True, env=env)
    flog = os.path.join(arch, '%s-%s-filter-branch.log' % (a.game, stamp))
    with open(flog, 'wb') as f:
        f.write(r.stdout + r.stderr)
    if r.returncode:
        raise SystemExit("filter-branch failed (see %s); restore with: git fetch %s '+refs/*:refs/*'" % (flog, bundle))

    # ---- verify ----
    left = scan(repo, referenced_pointers(repo), pats)
    new_tree = git(repo, 'rev-parse', 'HEAD^{tree}').decode().strip()
    fsck = subprocess.run(['git', '-C', repo, 'lfs', 'fsck'], capture_output=True, text=True)
    tail = (fsck.stdout + fsck.stderr).strip().splitlines()
    print('after: %d referenced LFS objects with a term; HEAD tree %s; git lfs fsck: %s' % (
        len(left), 'unchanged' if new_tree == head_tree else 'changed' + (' (expected: HEAD referenced a patched object)' if head_had else ''),
        tail[-1] if tail else 'ok'))
    if left or fsck.returncode or (new_tree != head_tree and not head_had):
        raise SystemExit('verification failed: refs/original/* still hold the old history; bundle %s' % bundle)
    for ref in git(repo, 'for-each-ref', '--format=%(refname)', 'refs/original/').decode().split():
        git(repo, 'update-ref', '-d', ref)
    print('done: %d objects patched, %d pointer blobs swapped; the old history is in %s (filter-branch log %s)' % (
        len(plan), len(mapping), bundle, flog))
    shutil.rmtree(tmp, ignore_errors=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
