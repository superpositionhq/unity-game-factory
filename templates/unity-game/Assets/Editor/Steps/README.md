# Editor steps

Every editor operation that built this project's content: a C# static method that creates or changes scenes,
prefabs, materials, import settings or data assets, run headless with

    powershell -ExecutionPolicy Bypass -File Scripts/unity.ps1 step -Method <Namespace.Class.Method> -Reason "..."

(Unity `-batchmode -nographics -executeMethod` through the machine's heavy-job limiter). Keep every step that was
run, unchanged: write a new one (`BuildHarborV2.cs`) instead of editing one that already ran, so each `workflow.jsonl`
row's `source.script` and `source.sha256` still point at the real code.

The creation replay (not available yet) will run these steps again to rebuild the project from its history, and each
`workflow.jsonl` row already points at the step that wrote it, so, from the first step on:

- commit every step you run, here, together with what it changed (and every new asset's `.meta`);
- reach files through the project: asset paths (`"Assets/Scenes/Harbor.unity"`), `Application.dataPath`, or the
  current directory (the project root in batchmode); never an absolute path to this folder;
- steps that only look (probes, checks) are named `Inspect*`, `Measure*`, `Check*`, `Analyze*`, `Scan*` or contain
  `Probe`;
- every run logs at least one row: `WorkflowLog.Row(op, target, parameters)` (`Assets/Editor/Tools/WorkflowLog.cs`);
- a step that fails calls `EditorApplication.Exit(1)` after logging a `"failed"` row, so the run's exit code says so;
- build content from code (`EditorSceneManager`, `PrefabUtility`, `AssetDatabase`, `SerializedObject` for private
  fields), never by editing scene or prefab YAML by hand.

What the editor does that a step must allow for:

- opening a scene in Single mode (`EditorSceneManager.OpenScene`, `NewScene`) unloads the assets loaded or created
  before it: one of them assigned afterwards through `SerializedObject` (`objectReferenceValue`) reads back null at
  once and saves as `{fileID: 0}`, with no warning (it cost one game three commits). Open the scene first, then load
  the assets you assign (`AssetDatabase.LoadAssetAtPath` after the open), read each reference back before saving, and
  prove what was saved with an `Inspect*` step;
- `-nographics` draws nothing, without an error (a camera capture comes out one flat grey): a step that renders
  (screenshots, lightmap bakes, shader warm-up) runs with `-Render`;
- a package import (`AssetDatabase.ImportPackage`) imports nothing inside the method that calls it, and with `-quit`
  the editor leaves with nothing imported: run that step with `-NoQuit`, wait for
  `AssetDatabase.importPackageCompleted` / `importPackageFailed`, and call `EditorApplication.Exit` from there and
  after a time limit (a run without `-quit` ends only when the step exits; `ProjectSetup.ImportTextEssentials` in
  `Assets/Editor/Tools/` is the pattern).

A step looks like this, run with `Scripts/unity.ps1 step -Method __PROJECT__.EditorSteps.BuildHarbor.Run -Reason "..."`:

```csharp
using System.Collections.Generic;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using __PROJECT__.EditorTools;   // WorkflowLog (the project's editor tools assembly)

namespace __PROJECT__.EditorSteps
{
    public static class BuildHarbor
    {
        public static void Run()
        {
            // the scene first: opening it unloads the assets loaded before it
            var scene = EditorSceneManager.NewScene(NewSceneSetup.DefaultGameObjects, NewSceneMode.Single);
            // ... then load or create the assets, place prefabs, set up lighting ...
            EditorSceneManager.SaveScene(scene, "Assets/Scenes/Harbor.unity");
            WorkflowLog.Row("scene.build", "Assets/Scenes/Harbor.unity", new Dictionary<string, object> { ["piers"] = 4 });
        }
    }
}
```
