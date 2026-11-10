using System.Collections.Generic;
using System.Text;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Rendering.Universal;

namespace ProbeTests.Drawn
{
    /// <summary>Everything a probe render changes, as one text (RenderSettings, the active render texture, every Light,
    /// reflection probe with its pictures, the default reflection, every renderer and terrain, the URP asset's render
    /// scale and HDR, every renderer feature), taken just before the probe samples (DrawnLeakBefore) and here just after
    /// it: a frame where the two differ is a leak of the probe's into the game. The tests read `frames` and `leaks`; the
    /// first differences go to the player log.</summary>
    [DefaultExecutionOrder(32010)]
    public sealed class DrawnLeakWatch : MonoBehaviour
    {
        public int frames, leaks;
        internal static string Before;
        int said;

        internal static string State()
        {
            var s = new StringBuilder();
            s.Append("ambient ").Append(RenderSettings.ambientMode).Append(' ').Append(RenderSettings.ambientLight).Append(' ')
                .Append(RenderSettings.ambientSkyColor).Append(' ').Append(RenderSettings.ambientEquatorColor).Append(' ')
                .Append(RenderSettings.ambientGroundColor).Append(' ').Append(RenderSettings.ambientIntensity.ToString("R"));
            var sh = RenderSettings.ambientProbe;
            for (var c = 0; c < 3; c++)
                for (var k = 0; k < 9; k++) s.Append(' ').Append(sh[c, k].ToString("R"));
            s.Append("\nfog ").Append(RenderSettings.fog).Append(" reflection ").Append(RenderSettings.defaultReflectionMode).Append(' ')
                .Append(RenderSettings.customReflectionTexture != null ? RenderSettings.customReflectionTexture.name : "none").Append(' ')
                .Append(RenderSettings.reflectionIntensity.ToString("R"));
            s.Append("\nactive ").Append(RenderTexture.active != null ? RenderTexture.active.name + "#" + RenderTexture.active.GetInstanceID() : "none");
            foreach (var l in FindObjectsByType<Light>(FindObjectsInactive.Include, FindObjectsSortMode.InstanceID))
                s.Append("\nlight ").Append(l.name).Append(' ').Append(l.enabled).Append(' ').Append(l.intensity.ToString("R"));
            s.Append("\ndefault reflection ").Append(ReflectionProbe.defaultTexture != null ? ReflectionProbe.defaultTexture.GetInstanceID() : 0);
            foreach (var p in FindObjectsByType<ReflectionProbe>(FindObjectsInactive.Include, FindObjectsSortMode.InstanceID))
                s.Append("\nprobe ").Append(p.name).Append(' ').Append(p.enabled).Append(' ').Append(p.intensity.ToString("R")).Append(' ')
                    .Append(p.texture != null ? p.texture.GetInstanceID() : 0).Append(' ')
                    .Append(p.realtimeTexture != null ? p.realtimeTexture.GetInstanceID() : 0);
            foreach (var r in FindObjectsByType<Renderer>(FindObjectsInactive.Include, FindObjectsSortMode.InstanceID))
            {
                if (r.name.StartsWith("Victim")) continue;  // destroyed by DrawnCallbacks inside a render, on purpose
                s.Append("\nrenderer ").Append(r.name).Append(' ').Append(r.gameObject.layer).Append(' ').Append(r.enabled).Append(' ')
                    .Append(r.forceRenderingOff).Append(' ').Append(r.lightmapIndex).Append(' ').Append(r.lightProbeUsage).Append(' ')
                    .Append(r.reflectionProbeUsage);
            }
            foreach (var t in FindObjectsByType<Terrain>(FindObjectsInactive.Include, FindObjectsSortMode.InstanceID))
                s.Append("\nterrain ").Append(t.name).Append(' ').Append(t.drawHeightmap).Append(' ').Append(t.drawTreesAndFoliage).Append(' ')
                    .Append(t.lightmapIndex).Append(' ').Append(t.reflectionProbeUsage);
            if (GraphicsSettings.currentRenderPipeline is UniversalRenderPipelineAsset asset)
            {
                s.Append("\nurp ").Append(asset.name).Append(' ').Append(asset.renderScale.ToString("R")).Append(' ').Append(asset.supportsHDR);
                foreach (var data in asset.rendererDataList)
                    if (data != null)
                        foreach (var f in data.rendererFeatures)
                            if (f != null) s.Append("\nfeature ").Append(data.name).Append(' ').Append(f.name).Append(' ').Append(f.isActive);
            }
            return s.ToString();
        }

        void LateUpdate()
        {
            if (Before == null) return;
            var now = State();
            frames++;
            if (now != Before)
            {
                leaks++;
                if (said++ < 5)
                {
                    var was = new HashSet<string>(Before.Split('\n'));
                    var lines = new StringBuilder("DRAWN LEAK at frame ").Append(Time.frameCount);
                    foreach (var line in now.Split('\n'))
                        if (!was.Contains(line)) lines.Append("\n  now ").Append(line);
                    Debug.Log(lines.ToString());
                }
            }
            Before = null;
        }
    }
}
