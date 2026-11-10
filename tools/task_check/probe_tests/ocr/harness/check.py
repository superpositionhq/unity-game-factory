"""The frame reader (TaskProbe/Runtime/Queries/UiOcr.cs) outside Unity, against its reference readings: frames.py's
synthetic frames read by UiOcr.cs, every reading compared with the reader's reference reading of the same frame
(expected.txt). It compiles UiOcr.cs with the Unity editor's own C# compiler and
runs it on the editor's Mono (the runtime a player runs it on), so it needs the editor and nothing else.

    python check.py [--unity <the editor folder: ...\\Hub\\Editor\\6000.3.x\\Editor>] [--keep DIR]

Prints each reading that differs and the count; exit code 0 when every reading is the reference's. About two and a half
minutes. Standard library only."""
import argparse
import glob
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
UIOCR = os.path.normpath(os.path.join(HERE, "..", "..", "..", "TaskProbe", "Runtime", "Queries", "UiOcr.cs"))
sys.path.insert(0, HERE)
import frames  # noqa: E402


def editor(given):
    found = [given] if given else sorted(glob.glob(r"C:\Program Files\Unity\Hub\Editor\6000.3.*\Editor"))
    for folder in reversed(found):
        data = folder if os.path.basename(folder) == "Data" else os.path.join(folder, "Data")
        if os.path.isdir(os.path.join(data, "DotNetSdkRoslyn")):
            return data
    sys.exit("no Unity 6000.3 editor found: pass --unity <the editor folder>")


def same_sources():
    """What the readings can't show: the reader's glyph table is the reference table (table.txt, which the frames are
    drawn from), and Read.cs reads a frame as Query.cs does (FrameImage's At and Area)."""
    with open(UIOCR, encoding="utf-8") as f:
        table = re.findall(r"S\('(.)', \"([^\"]*)\"\)", f.read())
    if table != frames.TABLE:
        sys.exit("UiOcr.cs's glyph table is not the reference table (harness/table.txt)")

    def members(path):
        with open(path, encoding="utf-8") as f:
            text = f.read().replace("UnityEngine.", "")
        found = re.findall(r"At\(int x, int yFromTop\) => [^;]+;|[xy][01] = Clamp\([^;]+;|int Clamp\(double v, int lo, int hi\) => [^;]+;", text)
        return [" ".join(m.split()) for m in found]

    query, read = members(os.path.join(os.path.dirname(UIOCR), "..", "Core", "Query.cs")), members(os.path.join(HERE, "Read.cs"))
    if len(query) != 6 or query != read:
        sys.exit("harness/Read.cs no longer reads a frame as Query.cs does (FrameImage.At, Area):\n  " + "\n  ".join(
            f"{q}\n  {r}" for q, r in zip(query, read) if q != r) or "a member is missing")


def main():
    same_sources()
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--unity")
    parser.add_argument("--keep", help="write the frames and the reader here, and keep them")
    args = parser.parse_args()
    data = editor(args.unity)
    work = args.keep or tempfile.mkdtemp(prefix="ocr_")
    try:
        frames.main(work)
        exe, api = os.path.join(work, "read.exe"), os.path.join(data, "MonoBleedingEdge", "lib", "mono", "4.7.1-api")
        dotnet = os.path.join(data, "NetCoreRuntime", "dotnet.exe" if os.name == "nt" else "dotnet")
        built = subprocess.run([dotnet, os.path.join(data, "DotNetSdkRoslyn", "csc.dll"), "-nologo", "-noconfig", "-nostdlib",
                                "-optimize+", "-langversion:9", "-r:" + os.path.join(api, "mscorlib.dll"),
                                "-r:" + os.path.join(api, "System.dll"), "-r:" + os.path.join(api, "System.Core.dll"),
                                "-out:" + exe, UIOCR, os.path.join(HERE, "Read.cs")], capture_output=True, text=True)
        if built.returncode != 0:
            sys.exit("UiOcr.cs didn't compile:\n" + built.stdout + built.stderr)
        mono = os.path.join(data, "MonoBleedingEdge", "bin", "mono.exe" if os.name == "nt" else "mono")
        ran = subprocess.run([mono, exe, os.path.join(work, "cases.txt")], capture_output=True, text=True)
        if ran.returncode != 0:
            sys.exit("the reader failed:\n" + ran.stdout[-2000:] + ran.stderr[-2000:])
        got = [line.strip() for line in ran.stdout.splitlines() if line.strip()]
        with open(os.path.join(HERE, "expected.txt"), encoding="utf-8") as f:
            want = [line.strip() for line in f if line.strip() and not line.startswith("#")]
        differ = [(w, g) for w, g in zip(want, got) if w != g]
        for w, g in differ:
            print(f"  expected: {w}\n  read:     {g}")
        if len(got) != len(want):
            print(f"{len(want)} readings expected, {len(got)} read")
        print(f"{len(want)} readings, {sum(w.count(' | ') for w in want)} lines in the reference readings: "
              + ("every reading the reference's" if not differ and len(got) == len(want) else f"{len(differ)} differ"))
        return 0 if not differ and len(got) == len(want) else 1
    finally:
        if not args.keep:
            shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
