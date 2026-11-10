using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Reflection;
using System.Text;
using UnityEngine;
using UnityEngine.Rendering;
using Debug = UnityEngine.Debug;

namespace DrawnTest
{
    [DefaultExecutionOrder(32050)]  // after the probe's own late half: the frame's samples are taken
    public sealed class GlowReport : MonoBehaviour
    {
        public string[] Names = new string[0];
        public string BudgetPrefix = "BudgetCube";
        Delegate hook;
        FieldInfo ok, brightest, glow;
        bool budgetDone;

        void Start()
        {
            var hooks = Type.GetType("TaskProbe.Hooks, TaskProbe");
            hook = hooks?.GetField("GlowRender")?.GetValue(null) as Delegate;
            var type = Type.GetType("TaskProbe.RenderedGlow, TaskProbe");
            if (type != null)
            {
                ok = type.GetField("Ok");
                brightest = type.GetField("Brightest");
                glow = type.GetField("Glow");
            }
            Debug.Log("GLOWTEST hook " + (hook != null ? "set" : "missing"));
        }

        object Call(Renderer r) => hook.DynamicInvoke(r);

        void LateUpdate()
        {
            if (hook == null || Time.frameCount % 15 != 0 || Time.timeSinceLevelLoad < 1f) return;
            var line = new StringBuilder();
            foreach (var name in Names)
            {
                var go = GameObject.Find(name);
                var r = go != null ? go.GetComponent<Renderer>() : null;
                if (r == null) { Debug.Log("GLOWTEST " + name + " missing"); continue; }
                var clock = Stopwatch.StartNew();
                var read = Call(r);
                var ms = clock.Elapsed.TotalMilliseconds;
                clock.Restart();
                Call(r);  // the same frame again: from the cache
                var again = clock.Elapsed.TotalMilliseconds;
                Debug.Log($"GLOWTEST t={Time.timeSinceLevelLoad:F2} {name} ok={ok.GetValue(read)} brightest={(double)brightest.GetValue(read):G6} glow={(double)glow.GetValue(read):G6} ms={ms:F3} again_ms={again:F4}");
            }
            if (!budgetDone && Time.timeSinceLevelLoad > 6f)
            {
                budgetDone = true;
                int okCount = 0, notOk = 0;
                foreach (var r in FindObjectsByType<MeshRenderer>(FindObjectsSortMode.InstanceID))
                {
                    if (!r.name.StartsWith(BudgetPrefix, StringComparison.Ordinal)) continue;
                    if ((bool)ok.GetValue(Call(r))) okCount++; else notOk++;
                }
                Debug.Log($"GLOWTEST budget: {okCount} ok, {notOk} refused (after {Names.Length} named renders this frame)");
            }
        }
    }
}
