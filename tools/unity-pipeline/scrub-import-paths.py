"""Take the account name and the agent and provider names out of a Unity project's binary files, byte for byte.

    python tools/unity-pipeline/scrub-import-paths.py <game>              # dry run: what --apply would do
    python tools/unity-pipeline/scrub-import-paths.py <game> --apply      # rewrite the safe matches in place
    python tools/unity-pipeline/scrub-import-paths.py <game> --verify     # list what is left (expect nothing)

Options: --repo <folder> (a project elsewhere than <root>/games/<game>), --report <file.json> (the per-file report).

Binary assets remember where and by whom they were made: an FBX names the file it was exported from and the
exporting tool's user (C:\\Users\\<name>\\Desktop\\hero.blend, a Creator field), a .blend its own and its images'
paths, a PSD, PNG or JPG its XMP history (file:///C:/Users/<name>/..., <dc:creator>), an audio file its tags. The
dataset packager scrubs text but never changes a binary, and a name left in a binary's strings refuses the delivery:
this tool fixes the project itself, before the files are committed again.

A byte scan (ASCII and UTF-16LE, any case, streamed) of the project's binary files under Assets/, Packages/ and
ProjectSettings/ (text files are the packager's to scrub; Library/ and the other folders Unity makes are left out) for
terms(): the account name (one of fewer than 6 letters only where it stands as a word of its own, as the packager
counts it), "Claude (agent)", "claude" and "anthropic". A match is rewritten, with a stand-in of the same length, only
in a safe context:
  - a path segment: between separators (/ \\ -), as in C:\\Users\\<name>\\... and file:///C:/Users/<name>/...;
  - a whole length-prefixed string: an FBX property (uint32 length, then the bytes) or a length + 1 string ending in
    NUL;
  - a whole XML element's text, as XMP keeps an author (<rdf:li><name></rdf:li>).
Same length keeps every offset, length and checksum-free structure of the file valid. A match anywhere else (inside
story text, spelled by compressed pixels) is UNHANDLED: a person re-exports or edits that file. --apply refuses while
an editor has the project open. Git LFS files are scanned in the working tree (a file still a pointer is skipped and
named); the history's own objects are scrub-lfs-history.py's. Standard library, Python 3.10+.
"""
import argparse, json, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'machine', 'lib'))
import ugfroot  # noqa: E402

# Formats that are binary whatever their first bytes say (the packager's list); any other file is binary when its first
# 8000 bytes hold a NUL.
BINARY_EXT = frozenset('''.png .jpg .jpeg .tga .psd .exr .hdr .bmp .tif .tiff .dds .ktx .ktx2 .gif .webp .ico .raw .r16 .r8
.fbx .obj .glb .gltf .abc .blend .max .ma .mb .3ds .dae .usd .usdc .usdz .ply .stl .spp .sbsar
.wav .ogg .mp3 .flac .aif .aiff .m4a .opus .wem .bank .bnk .mp4 .mov .mkv .webm .avi .bk2
.ttf .otf .ttc .woff .woff2 .zip .7z .rar .gz .tgz .tar .unitypackage .upack .pdf .xlsx .docx .pptx
.exe .dll .pdb .lib .so .dylib .a .bin .dat .ies .bytes .bundle .speedtree .assets .resource .ress'''.split())
ROOTS = ('Assets', 'Packages', 'ProjectSettings')
LFS_MAGIC = b'version https://git-lfs.github.com/spec/'


def log(msg):
    print('scrub-import-paths: ' + msg, flush=True)


def placeholder(n):
    """A stand-in for the account name of the same length: 'user' and underscores, 'u..' for fewer than 4 letters."""
    return ('user' + '_' * max(0, n - 4))[:n] if n >= 4 else 'u' * n


class Term:
    def __init__(self, label, text, rep, short=False):
        self.label, self.text, self.rep, self.short = label, text, rep, short


def terms(user=None):
    name = os.environ.get('USERNAME', '') if user is None else user
    out = [Term('username', name, placeholder(len(name)), short=len(name) < 6)] if len(name) >= 3 else []
    return out + [Term('agent-name', 'Claude (agent)', 'Developer team'), Term('agent-name', 'claude', 'helper'),
                  Term('provider-name', 'anthropic', 'assistant')]


def byte_patterns(user=None):
    """[(label, width, lower-case pattern bytes, term)] in ASCII and UTF-16LE, longest first."""
    pats = []
    for tm in terms(user):
        for width, enc in ((1, 'ascii'), (2, 'utf-16-le')):
            pats.append((tm.label + (' (utf-16)' if width == 2 else ''), width, tm.text.lower().encode(enc), tm))
    pats.sort(key=lambda x: -len(x[2]))
    return pats


CHUNK = 8 * 1024 * 1024   # files are streamed: a multi-GB file is never read whole
CTX_BEFORE, CTX_AFTER = 8, 2


def _seps(width):
    return [c.encode('ascii' if width == 1 else 'utf-16-le') for c in ('/', '\\', '-')]


def word_of_its_own(buf, i, n, width):
    """Whether a short name at buf[i] stands as a word: spelled as words are (name, Name, NAME), after a non-letter or
    at a lower -> upper boundary, and not followed by a lower-case letter (the packager's short-token rule)."""
    if width == 2 and any(buf[i + 2 * k + 1] for k in range(n)):
        return False
    s = bytes(buf[i + width * k] for k in range(n)).decode('latin-1')
    if not (s.islower() or s.isupper() or (s[0].isupper() and s[1:].islower())):
        return False

    def char(p):
        return buf[p] if 0 <= p < len(buf) and (width == 1 or (p + 1 < len(buf) and buf[p + 1] == 0)) else 0
    prev, nxt = char(i - width), char(i + n * width)
    letter = lambda c: 65 <= c <= 90 or 97 <= c <= 122   # noqa: E731
    return (not letter(prev) or (97 <= prev <= 122 and s[0].isupper())) and not 97 <= nxt <= 122


def _context(buf, low, i, nb, width, n_chars):
    """'path', 'string', 'element' or None for a match at low[i:i+nb]."""
    before, after = low[max(0, i - width):i], low[i + nb:i + nb + width]
    seps = _seps(width)
    if before in seps and after in seps:
        return 'path'
    if i >= 4:
        ln = int.from_bytes(low[i - 4:i], 'little', signed=True)
        if width == 1 and ln == n_chars:   # an FBX property: uint32 length, then exactly the bytes
            return 'string'
        if (width == 1 and ln == n_chars + 1 and after == b'\x00') or (width == 2 and ln == -(n_chars + 1) and after == b'\x00\x00'):
            return 'string'
    lt, gt = ('<', '>') if width == 1 else ('<\0', '>\0')
    if before == gt.encode('latin-1') and after == lt.encode('latin-1'):
        return 'element'
    return None


def _matches(buf, low, lo, hi, pats, claimed):
    """Matches starting in [lo, hi): [(i, nb, label, width, term, context)], longest terms first, none inside an earlier
    (longer) match."""
    out = []
    for label, width, b, tm in pats:
        i = low.find(b, lo)
        while i != -1 and i < hi:
            if not any(s <= i < e for s, e in claimed) and (not tm.short or word_of_its_own(buf, i, len(tm.text), width)):
                out.append((i, len(b), label, width, tm, _context(buf, low, i, len(b), width, len(tm.text))))
                claimed.append((i, i + len(b)))
            i = low.find(b, i + 1)
    return out


def _stream(path, pats, patch_to=None):
    """Walk the file in CHUNK pieces: ({label: count}, unpatchable count, rewritten count). With patch_to, write the file
    there with every safe-context match rewritten (same length). Each buffer is the carried tail plus the next chunk;
    matches starting before `lo` were handled in the previous buffer and those past `cutoff` wait for the next, so
    every match has its context bytes and is handled once."""
    maxlen = max(len(b) for _l, _w, b, _t in pats)
    counts, unpatchable, rewritten = {}, 0, 0
    dst = open(patch_to, 'wb') if patch_to else None
    try:
        with open(path, 'rb') as f:
            pending, lo = b'', 0
            while True:
                chunk = f.read(CHUNK)
                eof = not chunk
                buf = bytearray(pending + chunk)
                low = bytes(buf).lower()   # ASCII letters only: the NUL bytes of UTF-16LE stay as they are
                cutoff = len(buf) if eof else max(lo, len(buf) - (maxlen + CTX_AFTER))
                for i, nb, label, width, tm, ctx in _matches(buf, low, lo, cutoff, pats, []):
                    counts[label] = counts.get(label, 0) + 1
                    if ctx is None:
                        unpatchable += 1
                        continue
                    if dst is not None:
                        rep = tm.rep[:1].upper() + tm.rep[1:] if bytes(buf[i:i + 1]).isupper() else tm.rep
                        buf[i:i + nb] = rep.encode('ascii' if width == 1 else 'utf-16-le')
                        rewritten += 1
                if eof:
                    if dst is not None:
                        dst.write(buf)
                    break
                cut = max(0, cutoff - CTX_BEFORE)
                if dst is not None:
                    dst.write(buf[:cut])
                pending = bytes(buf[cut:])
                lo = cutoff - cut
    finally:
        if dst is not None:
            dst.close()
    return counts, unpatchable, rewritten


def is_binary(path):
    if os.path.splitext(path)[1].lower() in BINARY_EXT:
        return True
    with open(path, 'rb') as f:
        head = f.read(8000)
    return head[:2] not in (b'\xff\xfe', b'\xfe\xff') and b'\0' in head


def project_files(project):
    """The binary files of a project under Assets/, Packages/ and ProjectSettings/ (Unity's own folders left out)."""
    out = []
    for top in ROOTS:
        for d, dirs, fs in os.walk(os.path.join(project, top)):
            dirs[:] = [x for x in dirs if x not in ('.git', 'Library', 'Temp', 'Logs', 'obj')]
            out += [os.path.join(d, f) for f in fs if is_binary(os.path.join(d, f))]
    return sorted(out)


def editor_open(project):
    """Whether a Unity editor has the project open: its Temp/UnityLockfile held, or a Unity.exe naming the project."""
    lock = os.path.join(project, 'Temp', 'UnityLockfile')
    if os.path.isfile(lock):
        try:
            with open(lock, 'r+b'):
                pass
        except PermissionError:
            return True
        except OSError:
            pass
    if os.name != 'nt':
        return False
    r = subprocess.run(['powershell', '-NoProfile', '-Command',
                        "Get-CimInstance Win32_Process -Filter \"Name='Unity.exe'\" | ForEach-Object { $_.CommandLine }"],
                       capture_output=True, text=True)
    want = os.path.normcase(os.path.abspath(project)).replace('/', '\\').rstrip('\\')
    return any(want in os.path.normcase(l).replace('/', '\\') for l in r.stdout.splitlines())


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0], formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('game')
    ap.add_argument('--repo', help='the project, when it is not <root>/games/<game>')
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument('--apply', action='store_true', help='rewrite the safe-context matches in place')
    mode.add_argument('--verify', action='store_true', help='list the files with matches left')
    ap.add_argument('--report', help='write the per-file report here (JSON)')
    a = ap.parse_args(argv)
    project = os.path.abspath(a.repo or os.path.join(ugfroot.root(), 'games', a.game))
    if not os.path.isdir(os.path.join(project, 'Assets')):
        log(f'no Unity project at {project}')
        return 2
    pats = byte_patterns()
    log(f'project {project}, mode {"apply" if a.apply else "verify" if a.verify else "dry run"}, terms: '
        + ', '.join(sorted({p[0].split(' ')[0] for p in pats})))
    if a.apply and editor_open(project):
        log(f'an editor has {project} open: close it first (nothing changed)')
        return 2
    report, pointers, unhandled, patched, left = [], [], 0, 0, 0
    for path in project_files(project):
        rel = os.path.relpath(path, project).replace('\\', '/')
        if os.path.getsize(path) < 300:
            with open(path, 'rb') as f:
                if f.read().startswith(LFS_MAGIC):
                    pointers.append(rel)
                    continue
        counts, unpatchable, _ = _stream(path, pats)
        if not counts:
            continue
        row = {'file': rel, 'terms': counts, 'unpatchable': unpatchable}
        if a.apply and sum(counts.values()) > unpatchable:
            tmp = path + '.scrubtmp'
            _c, _u, n = _stream(path, pats, patch_to=tmp)
            if n and os.path.getsize(tmp) == os.path.getsize(path):
                os.replace(tmp, path)
                row['rewritten'] = n
                patched += 1
                log(f'PATCHED {rel} ({n} rewritten{f", {unpatchable} left: not a path, a whole string or an element" if unpatchable else ""})')
            else:
                os.remove(tmp)
        elif not a.apply:
            safe = sum(counts.values()) - unpatchable
            log(f'{"HIT" if a.verify else "WOULD PATCH" if safe else "HIT"} {rel}: {json.dumps(counts)}'
                + (f'; {safe} in a safe context' if safe and not a.verify else ''))
        if unpatchable:
            unhandled += 1
            log(f'UNHANDLED {rel}: {unpatchable} match(es) outside a path, a whole string or an element: re-export or edit it')
        left += 1
        report.append(row)
    for rel in pointers:
        log(f'SKIPPED {rel}: a Git LFS pointer in the working tree (git lfs checkout first)')
    log(f'{left} file(s) with matches' + (f', {patched} patched' if a.apply else '') + f', {unhandled} unhandled')
    if a.report:
        with open(a.report, 'w', encoding='utf-8') as f:
            json.dump({'project': project, 'mode': 'apply' if a.apply else 'verify' if a.verify else 'dry-run', 'files': report,
                       'lfs_pointers_skipped': pointers}, f, indent=1)
    if a.verify:
        return 1 if left else 0
    return 1 if unhandled else 0


if __name__ == '__main__':
    sys.exit(main())
