// The probe tests' one editor entry (run.py beside this file copies it into the test project): every family's scene
// builders in one start of the editor.
//   Unity -batchmode -quit -projectPath <project> -executeMethod ProbeTests.Setup.Run -probeTestsSetup <A.B.Method,C.D.Method>
// Each method is a static method without arguments that makes its family's scenes and assets under
// Assets/ProbeTests/<family>/Made/ and returns. The editor exits with 1 when one is missing or throws.
using System;
using System.Reflection;
using UnityEditor;
using UnityEngine;

namespace ProbeTests
{
    public static class Setup
    {
        public static void Run()
        {
            var args = Environment.GetCommandLineArgs();
            var at = Array.IndexOf(args, "-probeTestsSetup");
            var names = at >= 0 && at + 1 < args.Length ? args[at + 1].Split(',') : new string[0];
            foreach (var name in names)
            {
                var dot = name.LastIndexOf('.');
                Type type = null;
                foreach (var assembly in AppDomain.CurrentDomain.GetAssemblies())
                {
                    type = dot > 0 ? assembly.GetType(name.Substring(0, dot)) : null;
                    if (type != null) break;
                }
                var method = type?.GetMethod(name.Substring(dot + 1), BindingFlags.Static | BindingFlags.Public | BindingFlags.NonPublic,
                    null, Type.EmptyTypes, null);
                if (method == null)
                {
                    Debug.LogError("ProbeTests: no static method " + name);
                    EditorApplication.Exit(1);
                    return;
                }
                try { method.Invoke(null, null); }
                catch (Exception e)
                {
                    Debug.LogError("ProbeTests: " + name + " failed: " + (e.InnerException ?? e));
                    EditorApplication.Exit(1);
                    return;
                }
                Debug.Log("ProbeTests: ran " + name);
            }
            AssetDatabase.SaveAssets();
        }
    }
}
