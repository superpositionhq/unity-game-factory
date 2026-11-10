"""The probe in a project that isn't the template: does the package compile, and does a play still write probe.json,
when the project lacks a package or a built-in module the probe can use (the Input System, uGUI and TextMeshPro, URP,
physics, audio, UI Toolkit, particles, terrain, AI, ...).

    python tools/task_check/probe_tests/variants.py <template project> [--package DIR]

<template project>: a Unity 6000.3 project that has been opened once and has URP, the Input System and uGUI (the one
`run.py` runs in will do): its `Library/ScriptAssemblies` gives the packages' assemblies to compile against. Nothing
in it is changed.

What it does, without starting the editor: compiles the package's runtime assembly with the editor's own C# compiler
against the engine's module assemblies, once for every way of leaving a part out:
1. each define of Runtime/TaskProbe.asmdef off alone, with the assemblies it stands for taken away (and those of the
   modules that need that module: no terrain physics without physics). A guard for one part that leans on another
   compiles when both are gone and fails here;
2. every package off, every module off, and both (the barest project Unity opens);
3. each built-in module a project can remove (those with a com.unity.modules.<name> package) taken away alone with
   every define on: a failure names a module the code uses outside its own guard. That is right only when the guard
   it sits under brings the module with it (uGUI needs the UI and IMGUI modules; UI Toolkit needs IMGUI, the UI
   module and physics): USES below says which, and anything else fails.
It also checks the asmdef against the code: a define the code uses and the asmdef doesn't set, or the reverse.

This proves the C# compiles under each set of defines. That Unity sets exactly those defines in such a project, that a
play there writes probe.json, and what each kind then gives, only a real project can tell: see README.md.

Exit code 0 when everything compiled. Standard library only (Python 3.12)."""

import argparse
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent))
sys.path.insert(0, str(HERE.parent.parent.parent / "machine" / "lib"))
import ugfroot  # noqa: E402
from task_check import seeds  # noqa: E402

# the assemblies each package's define stands for (the asmdef's references)
PACKAGES = {"com.unity.inputsystem": ["Unity.InputSystem"], "com.unity.ugui": ["UnityEngine.UI", "Unity.TextMeshPro"],
            "com.unity.textmeshpro": ["Unity.TextMeshPro"],
            "com.unity.render-pipelines.universal": ["Unity.RenderPipelines.Core.Runtime", "Unity.RenderPipelines.Universal.Runtime"]}
# a module the code may use outside that module's own guard, because the guard it is under brings it along
# (read from the editor's built-in package manifests and the packages' own: uGUI needs the UI and IMGUI modules; UI
# Toolkit needs IMGUI, the UI module and physics)
BROUGHT = {"UnityEngine.UIModule": ("TASKPROBE_UGUI", "TASKPROBE_UITK"), "UnityEngine.IMGUIModule": ("TASKPROBE_UGUI", "TASKPROBE_UITK")}
ALWAYS = ("UnityEngine", "UnityEngine.CoreModule", "UnityEngine.SharedInternalsModule")
PLAYER = ["UNITY_6000_3_OR_NEWER", "UNITY_6000_0_OR_NEWER", "UNITY_STANDALONE_WIN", "UNITY_STANDALONE", "UNITY_64", "ENABLE_MONO",
          "NET_STANDARD_2_1", "NET_STANDARD"]


class Compiler:
    """The editor's C# compiler and the assemblies a player's scripts compile against."""

    def __init__(self, project, package):
        data = Path(ugfroot.unity_editor(str(project))).parent / "Data"
        self.dotnet, self.csc = data / "NetCoreRuntime" / "dotnet.exe", data / "DotNetSdkRoslyn" / "csc.dll"
        self.netstandard = data / "NetStandard" / "ref" / "2.1.0" / "netstandard.dll"
        self.engine = {p.stem: p for p in (data / "Managed" / "UnityEngine").glob("UnityEngine*.dll")}
        self.modules = self._modules(data / "Resources" / "PackageManager" / "BuiltInPackages")
        self.library = project / "Library" / "ScriptAssemblies"
        self.package = package
        self.sources = sorted((package / "Runtime").rglob("*.cs"))
        asmdef = json.loads((package / "Runtime" / "TaskProbe.asmdef").read_text(encoding="utf-8"))
        self.defines = {}  # define: (engine module assemblies, package assemblies) it stands for
        for entry in asmdef["versionDefines"]:
            modules, packages = self.defines.setdefault(entry["define"], ([], []))
            name = entry["name"]
            if name.startswith("com.unity.modules."):
                modules += [m for m in self._with_dependents(name) if m not in modules]
            else:
                packages += [a for a in PACKAGES.get(name, []) if a not in packages]

    def _modules(self, builtin):
        """{module package: (its engine assembly, the module packages it needs)} from the editor's own manifests."""
        found = {}
        by_stem = {stem.lower(): stem for stem in self.engine}
        for manifest in builtin.glob("com.unity.modules.*/package.json"):
            data = json.loads(manifest.read_text(encoding="utf-8"))
            stem = by_stem.get("unityengine." + data["name"].split(".")[-1] + "module")
            found[data["name"]] = (stem, [d for d in (data.get("dependencies") or {}) if d.startswith("com.unity.modules.")])
        return found

    def _with_dependents(self, module):
        """The engine assemblies that go when `module` goes: its own and those of every module that needs it."""
        gone, todo = [], [module]
        while todo:
            name = todo.pop()
            stem = self.modules.get(name, (None, []))[0]
            if stem and stem not in gone:
                gone.append(stem)
            todo += [other for other, (_, needs) in self.modules.items() if name in needs and self.modules[other][0] not in gone]
        return gone

    def compile(self, off=(), without=()):
        """The runtime assembly with the defines `off` not set and their assemblies gone (and the engine assemblies
        `without` gone): (compiled, [error lines])."""
        on = [d for d in self.defines if d not in off]
        keep = {m for d in on for m in self.defines[d][0]}
        gone = ({m for d in off for m in self.defines[d][0]} - keep) | set(without)
        packages = list(dict.fromkeys(a for d in on for a in self.defines[d][1]))
        refs = [self.netstandard] + [p for stem, p in sorted(self.engine.items()) if stem not in gone] \
            + [self.library / f"{a}.dll" for a in packages]
        with tempfile.TemporaryDirectory() as work:
            rsp = Path(work) / "probe.rsp"
            rsp.write_text("\n".join(["-target:library", "-nostdlib", "-noconfig", "-nologo", "-langversion:9",
                                      "-nowarn:1701,1702,0618,0649,0169,0414", f"-out:{Path(work) / 'TaskProbe.dll'}",
                                      f"-define:{';'.join(PLAYER + on)}"]
                                     + [f'-reference:"{r}"' for r in refs] + [f'"{s}"' for s in self.sources]), encoding="utf-8")
            ran = subprocess.run([str(self.dotnet), str(self.csc), f"@{rsp}"], capture_output=True, text=True, check=False)
        errors = [line.replace(str(self.package) + "\\", "") for line in (ran.stdout + ran.stderr).splitlines() if "error" in line]
        return ran.returncode == 0, errors

    def guard_of(self, error):
        """The defines an error's line sits under (the #if blocks open at that line of its file)."""
        found = re.match(r"(.+?)\((\d+),\d+\)", error)
        if not found:
            return set()
        open_ifs = []
        for number, line in enumerate((self.package / found.group(1)).read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            if number > int(found.group(2)):
                break
            word = line.strip()
            if word.startswith("#if"):
                open_ifs.append(set(re.findall(r"TASKPROBE_\w+", word)))
            elif word.startswith("#else") and open_ifs:
                open_ifs[-1] = set()
            elif word.startswith("#endif") and open_ifs:
                open_ifs.pop()
        return set().union(*open_ifs) if open_ifs else set()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("project")
    parser.add_argument("--package")
    args = parser.parse_args(argv)
    project = Path(args.project).resolve()
    package = Path(args.package).resolve() if args.package else seeds.PROBE_SOURCE
    if not (project / "Library" / "ScriptAssemblies").is_dir():
        sys.exit(f"{project} has no Library/ScriptAssemblies: open the project once (run.py does)")
    c = Compiler(project, package)
    print(f"probe variants: {package} compiled against {project.name}'s assemblies", flush=True)
    ok = True

    used = set()
    for source in c.sources:
        for line in source.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.lstrip().startswith("#"):
                used.update(re.findall(r"TASKPROBE_\w+", line))
    for define in sorted(used - set(c.defines)):
        ok = False
        print(f"FAIL  {define} is used in the code, but the asmdef never sets it")
    for define in sorted(set(c.defines) - used):
        ok = False
        print(f"FAIL  the asmdef sets {define}, but no file uses it")

    def variant(label, off):
        nonlocal ok
        good, errors = c.compile(off=off)
        ok &= good
        print(f"{'ok  ' if good else 'FAIL'}  {label}" + "".join("\n      " + e[:220] for e in errors[:8]), flush=True)

    for define in c.defines:
        variant("without " + define, {define})
    variant("without every package", {d for d, (_, packages) in c.defines.items() if packages})
    variant("without every optional module", {d for d, (modules, _) in c.defines.items() if modules})
    variant("without every package and optional module", set(c.defines))

    guarded = {m for modules, _ in c.defines.values() for m in modules}
    for stem in sorted(stem for stem, _ in c.modules.values() if stem):  # the modules a project can remove
        if stem in ALWAYS or stem in guarded:
            continue
        good, errors = c.compile(without={stem})
        if good:
            continue
        outside = [e for e in errors if not (c.guard_of(e) & set(BROUGHT.get(stem, ())))]
        ok &= not outside
        print(f"{'FAIL' if outside else 'USES'}  {stem}: " + (
            "used where no guard brings it" if outside else "only under " + " / ".join(BROUGHT[stem]) + ", which bring it")
            + "".join("\n      " + e[:220] for e in (outside or errors)[:4]), flush=True)
    print("every variant compiled" if ok else "FAILED", flush=True)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
