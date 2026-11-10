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
    [DefaultExecutionOrder(-31000)]
    public sealed class LeakWatch : MonoBehaviour
    {
        string before;
        int frames, leaks;

        // test switches (-drawnScene noprobe,nosparks): take a nondeterministic part out of the scene
        void Start()
        {
            var args = Environment.GetCommandLineArgs();
            var at = Array.IndexOf(args, "-drawnScene");
            var what = at >= 0 && at + 1 < args.Length ? args[at + 1] : "";
            if (what.Contains("noprobe"))
                foreach (var p in FindObjectsByType<ReflectionProbe>(FindObjectsSortMode.None)) p.gameObject.SetActive(false);
            if (what.Contains("nosparks"))
                foreach (var p in FindObjectsByType<ParticleSystem>(FindObjectsSortMode.None)) p.gameObject.SetActive(false);
        }

        static string State()
        {
            var s = new StringBuilder();
            s.Append("ambient ").Append(RenderSettings.ambientMode).Append(' ').Append(RenderSettings.ambientLight).Append(' ')
                .Append(RenderSettings.ambientSkyColor).Append(' ').Append(RenderSettings.ambientIntensity).Append(' ')
                .Append(RenderSettings.ambientProbe[0, 0].ToString("R")).Append(' ').Append(RenderSettings.ambientProbe[1, 3].ToString("R")).Append('\n');
            s.Append("fog ").Append(RenderSettings.fog).Append(" reflection ").Append(RenderSettings.defaultReflectionMode).Append(' ')
                .Append(RenderSettings.customReflectionTexture != null ? RenderSettings.customReflectionTexture.name : "none").Append(' ')
                .Append(RenderSettings.reflectionIntensity).Append('\n');
            foreach (var l in FindObjectsByType<Light>(FindObjectsInactive.Include, FindObjectsSortMode.InstanceID))
                s.Append("light ").Append(l.name).Append(' ').Append(l.enabled).Append(' ').Append(l.intensity).Append('\n');
            foreach (var p in FindObjectsByType<ReflectionProbe>(FindObjectsInactive.Include, FindObjectsSortMode.InstanceID))
                s.Append("probe ").Append(p.name).Append(' ').Append(p.enabled).Append('\n');
            foreach (var r in FindObjectsByType<Renderer>(FindObjectsInactive.Include, FindObjectsSortMode.InstanceID))
                s.Append("renderer ").Append(r.name).Append(' ').Append(r.gameObject.layer).Append(' ').Append(r.enabled).Append(' ')
                    .Append(r.forceRenderingOff).Append(' ').Append(r.lightmapIndex).Append(' ').Append(r.lightProbeUsage).Append(' ')
                    .Append(r.reflectionProbeUsage).Append('\n');
            var asset = GraphicsSettings.currentRenderPipeline;
            if (asset != null)
            {
                foreach (var name in new[] { "supportsHDR", "renderScale" })
                    s.Append("urp ").Append(name).Append(' ').Append(asset.GetType().GetProperty(name)?.GetValue(asset)).Append('\n');
            }
            return s.ToString();
        }

        void Update()
        {
            var now = State();
            frames++;
            if (before != null && now != before)
            {
                var a = new HashSet<string>(before.Split('\n'));
                var b = new HashSet<string>(now.Split('\n'));
                foreach (var line in b)
                    if (!a.Contains(line) && !line.Contains("LateCube"))
                    {
                        leaks++;
                        Debug.Log("LEAK now: " + line);
                    }
                foreach (var line in a)
                    if (!b.Contains(line) && !line.Contains("LateCube")) Debug.Log("LEAK was: " + line);
            }
            before = now;
            if (frames % 150 == 0) Debug.Log($"LEAKWATCH {frames} frames, {leaks} leak line(s)");
        }
    }
}
