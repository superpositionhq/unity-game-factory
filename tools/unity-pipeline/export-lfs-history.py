"""Every Git LFS object of a game's history, for a delivery: clean ones as they are, ones that name the account (or an
agent or provider) patched byte for byte under a new id.

    python tools/unity-pipeline/export-lfs-history.py <repo> <out lfs objects dir> [--unpatchable-use-head]

Every LFS object a ref references (all refs but the game's tasks branch and the stash: the refs the dataset packager
rewrites) is scanned with scrub-import-paths.py's terms and safe contexts (ASCII and UTF-16LE): the account name in a
path segment, a whole length-prefixed string or an XML element, and the agent and provider names. A clean object is
linked (copied when linking fails) into <out>/<aa>/<bb>/<oid>; one with matches is patched, same length, into a new
object under its new id. The repo and its LFS store are never changed.

Prints one JSON object: {"map": {old oid: [new oid, size]}, "objects": n, "bytes": n, "patched": n,
"unpatchable": [{"oid", "path"}], "missing": [{"oid", "path"}]}. Exit 2 when an object is missing from the local store
or has a match outside a safe context; with --unpatchable-use-head, HEAD's clean version of the same path stands in for
such an object (every commit that held it then shows HEAD's). The dataset packager does the same through scan() and
copies only the objects of the history it delivers, whose pointers it swaps for the patched objects' (rewrite_history).
"""
import argparse, hashlib, importlib.util, json, os, shutil, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location('scrub_import_paths', os.path.join(HERE, 'scrub-import-paths.py'))
sip = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sip)

# the refs the packager rewrites: every ref but the tasks branch (local and remote-tracking) and the stash
HISTORY_REFS = ['--single-worktree', '--exclude=refs/heads/tasks', '--exclude=refs/heads/tasks-*', '--exclude=refs/remotes/*/tasks',
                '--exclude=refs/remotes/*/tasks-*', '--exclude=refs/stash', '--exclude=refs/original/*', '--all']


def git(repo, *args, inp=None, check=True):
    r = subprocess.run(['git', '-C', repo, '-c', 'core.quotepath=off', *args], input=inp, capture_output=True)
    if check and r.returncode:
        raise SystemExit('git %s failed: %s' % (' '.join(args[:3]), r.stderr.decode('utf-8', 'replace')[-1500:]))
    return r.stdout


def lfs_store(repo):
    """Where the repo keeps its Git LFS objects: its lfs.storage, else <git common dir>/lfs/objects (as
    tools/unity-pipeline/common.ps1 Get-LfsStore)."""
    common = git(repo, 'rev-parse', '--git-common-dir').decode().strip()
    common = common if os.path.isabs(common) else os.path.join(repo, common)
    storage = git(repo, 'config', '--get', 'lfs.storage', check=False).decode().strip()
    if storage:
        base = storage if os.path.isabs(storage) else os.path.join(common, storage)
        return os.path.join(base, 'objects') if os.path.isdir(os.path.join(base, 'objects')) else base
    return os.path.join(common, 'lfs', 'objects')


def object_path(store, oid):
    return os.path.join(store, oid[:2], oid[2:4], oid)


def referenced(repo, refs=None):
    """{oid: (size, {paths})} of every LFS pointer in every commit reachable from refs (default HISTORY_REFS)."""
    objs = git(repo, 'rev-list', '--objects', *(refs or HISTORY_REFS)).decode('utf-8', 'replace')
    chk = git(repo, 'cat-file', '--batch-check=%(objecttype) %(objectname) %(objectsize) %(rest)', inp=objs.encode()).decode('utf-8', 'replace')
    cand = []
    for line in chk.splitlines():
        p = line.split(' ', 3)
        if len(p) >= 3 and p[0] == 'blob' and int(p[2]) < 300:
            cand.append((p[1], p[3] if len(p) > 3 else ''))
    out = git(repo, 'cat-file', '--batch', inp=('\n'.join(s for s, _ in cand) + '\n').encode()) if cand else b''
    pos, res = 0, {}
    for _sha, path in cand:
        nl = out.index(b'\n', pos)
        size = int(out[pos:nl].split()[2])
        body = out[nl + 1:nl + 1 + size]
        pos = nl + 1 + size + 1
        lines = body.decode('ascii', 'replace').splitlines()
        if lines and lines[0].startswith('version https://git-lfs.github.com/spec/v1'):
            oid = next((l.split('sha256:', 1)[1].strip() for l in lines if l.startswith('oid sha256:')), None)
            sz = next((int(l.split()[1]) for l in lines if l.startswith('size ') and l.split()[1].isdigit()), None)
            if oid:
                res.setdefault(oid, (sz, set()))[1].add(path)
    return res


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def scan(repo, objects, tmp, pats=None, use_head=None):
    """Scan objects ({oid: (size, {paths})}) of the repo's store; patch those with matches into tmp. Returns
    {"map": {oid: [new oid, size]}, "files": {new oid: patched file}, "patched": n, "unpatchable": [{oid, path}],
    "missing": [{oid, path}]}. use_head: a rev whose clean version of the same path stands in for an unpatchable object."""
    pats = pats or sip.byte_patterns()
    store = lfs_store(repo)
    os.makedirs(tmp, exist_ok=True)
    res = {'map': {}, 'files': {}, 'patched': 0, 'unpatchable': [], 'missing': []}
    for oid, (size, paths) in sorted(objects.items()):
        src, path = object_path(store, oid), sorted(paths)[0]
        if not os.path.isfile(src):
            res['missing'].append({'oid': oid, 'path': path})
            continue
        counts, unpatchable, _rw = sip._stream(src, pats)
        if not counts:
            continue
        out = os.path.join(tmp, oid)
        _c, unpatchable, rewritten = sip._stream(src, pats, patch_to=out)
        if unpatchable or not rewritten:
            os.remove(out)
            res['unpatchable'].append({'oid': oid, 'path': path, 'terms': counts})
            continue
        new = sha256_file(out)
        res['map'][oid] = [new, os.path.getsize(out)]
        res['files'][new] = out
        res['patched'] += 1
    if res['unpatchable'] and use_head:
        head = {}
        for line in git(repo, 'ls-tree', '-r', use_head).decode('utf-8', 'replace').splitlines():
            meta, path = line.split('\t', 1)
            head[path] = meta.split()[2]
        ptrs = {}
        for path, blob in head.items():
            data = git(repo, 'cat-file', 'blob', blob, check=False)
            if data.startswith(sip.LFS_MAGIC):
                lines = data.decode('ascii', 'replace').splitlines()
                oid = next((l.split('sha256:', 1)[1].strip() for l in lines if l.startswith('oid sha256:')), None)
                sz = next((int(l.split()[1]) for l in lines if l.startswith('size ')), None)
                if oid:
                    ptrs[path] = (oid, sz)
        bad = {u['oid'] for u in res['unpatchable']}
        left = []
        for u in res['unpatchable']:
            rep = ptrs.get(u['path'])
            if rep and rep[0] not in bad and rep[0] not in res['map'] and rep[0] != u['oid']:
                res['map'][u['oid']] = [rep[0], rep[1]]
            else:
                left.append(u)
        res['unpatchable'] = left
    return res


def place(src, out, oid):
    dst = object_path(out, oid)
    if os.path.exists(dst):
        return dst
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    try:
        os.link(src, dst)
    except OSError:
        shutil.copyfile(src, dst)
    return dst


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('repo')
    ap.add_argument('out')
    ap.add_argument('--unpatchable-use-head', action='store_true')
    a = ap.parse_args()
    repo, out = os.path.abspath(a.repo), os.path.abspath(a.out)
    objects = referenced(repo)
    tmp = tempfile.mkdtemp(prefix='export-lfs-')
    try:
        res = scan(repo, objects, tmp, use_head='HEAD' if a.unpatchable_use_head else None)
        store, written = lfs_store(repo), {}
        for oid, (size, _paths) in sorted(objects.items()):
            if any(m['oid'] == oid for m in res['missing'] + res['unpatchable']):
                continue
            new = res['map'].get(oid, [oid])[0]
            src = res['files'].get(new) or object_path(store, new)
            if os.path.isfile(src) and new not in written:
                place(src, out, new)
                written[new] = os.path.getsize(src)
        print(json.dumps({'map': res['map'], 'objects': len(written), 'bytes': sum(written.values()), 'patched': res['patched'],
                          'unpatchable': [{'oid': u['oid'], 'path': u['path']} for u in res['unpatchable']], 'missing': res['missing']}))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return 2 if res['missing'] or res['unpatchable'] else 0


if __name__ == '__main__':
    sys.exit(main())
