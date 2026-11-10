// light: the light reaching a point, as URP computes it (contract section 3, docs/task-probes.md 2.7). Every Light that
// is on adds intensity x its colour's luminance (linear, the temperature colour applied) x URP's attenuation, if a
// trace between it and the point is clear; the ambient adds the ambient probe's upward value x the open share of 9
// upward rays. In Unity's light units (not lux).
// "value": {"illuminance", "exposure", "brightness", "local", "directional", "sky", "lights", "point": [x, y, z]} |
// null when the point doesn't resolve.
using System;
using System.Collections.Generic;
using UnityEngine;

namespace TaskProbe
{
    [ProbeQuery("light")]
    public sealed class LightQuery : Query
    {
        Dictionary<string, object> point;
        static readonly Vector3[] SkyRays = BuildSkyRays();

        // straight up and 8 at 45 degrees around it
        static Vector3[] BuildSkyRays()
        {
            var rays = new Vector3[9];
            rays[0] = Vector3.up;
            const float h = 0.70710678f;
            for (var i = 1; i < 9; i++)
            {
                var a = (i - 1) * Mathf.PI / 4f;
                rays[i] = new Vector3(Mathf.Cos(a) * h, h, Mathf.Sin(a) * h);
            }
            return rays;
        }

        public override void Load()
        {
            point = Json.Obj(Def, "point");
            if (point == null) Probe.Error("light " + Id + ": no point");
        }

        public override void Sample(double t, Dictionary<string, object> sample)
        {
            if (point == null || !Find.Point(point, out var p))
            {
                sample["value"] = null;
                return;
            }
            double local = 0.0, directional = 0.0;
            var lit = 0;
            foreach (var l in LightKit.Lights())
            {
                if (!LightKit.On(l)) continue;
                var lum = LightKit.Luminance(LightKit.FinalColor(l));
                if (lum <= 0.0) continue;
                switch (l.type)
                {
                    case LightType.Directional:
                    {
                        // the light travels along its forward: the trace goes the other way, toward it
                        if (LightKit.BlockedToward(p, -l.transform.forward, l.transform)) continue;
                        directional += lum;
                        lit++;
                        break;
                    }
                    case LightType.Point:
                    case LightType.Spot:
                    {
                        var c = lum * Attenuation(l, p);
                        if (c <= 0.0 || LightKit.Blocked(l.transform.position, p, l.transform)) continue;
                        local += c;
                        lit++;
                        break;
                    }
                    // area (rect, disc) lights are baked only in URP: they light nothing at run time
                }
            }
            var ambient = LightKit.Ambient(out _, out _, out _);
            var sky = 0.0;
            if (ambient > 0.0)
            {
                var open = 0;
                foreach (var dir in SkyRays)
                    if (!LightKit.BlockedToward(p, dir, null)) open++;
                sky = ambient * open / SkyRays.Length;
                if (sky > 0.0) lit++;
            }
            var illuminance = local + directional + sky;
            var exposure = LightKit.Exposure();
            sample["value"] = new Dictionary<string, object>(StringComparer.Ordinal)
            {
                ["illuminance"] = illuminance, ["exposure"] = exposure, ["brightness"] = illuminance * exposure,
                ["local"] = local, ["directional"] = directional, ["sky"] = sky, ["lights"] = (double)lit,
                ["point"] = Json.Vec(p),
            };
        }

        /// <summary>URP's attenuation of a point or spot light at `p` (RealtimeLights.hlsl DistanceAttenuation x
        /// AngleAttenuation, with the constants UniversalRenderPipelineCore prepares).</summary>
        public static double Attenuation(Light l, Vector3 p)
        {
            var toLight = l.transform.position - p;
            // the shader clamps the squared distance at HALF_MIN
            var distanceSqr = Math.Max((double)toLight.sqrMagnitude, 6.103515625e-5);
            // GetPunctualLightDistanceAttenuation: x = 1 / range^2; smooth = saturate(1 - (d^2/r^2)^2)^2
            var rangeSqr = (double)l.range * l.range;
            var factor = distanceSqr * (1.0 / Math.Max(0.0001, rangeSqr));
            var smooth = Clamp01(1.0 - factor * factor);
            var atten = smooth * smooth / distanceSqr;
            if (l.type != LightType.Spot) return atten;
            // GetSpotAngleAttenuation: saturate(SdotL * invRange - cosOuter * invRange)^2, angles clamped as URP does
            double spotAngle = l.spotAngle, inner = l.innerSpotAngle;
            if (spotAngle < 2.6)
            {
                spotAngle = 2.6;
                inner = Math.Min(inner, 2.6);
            }
            var cosOuter = Math.Cos(Mathf.Deg2Rad * spotAngle * 0.5);
            var cosInner = Math.Cos(inner * Mathf.Deg2Rad * 0.5);
            var invRange = 1.0 / Math.Max(0.001, cosInner - cosOuter);
            var length = Math.Sqrt(distanceSqr);
            var sDotL = Vector3.Dot(l.transform.forward, -toLight) / length;
            var a = Clamp01(sDotL * invRange - cosOuter * invRange);
            return atten * a * a;
        }

        static double Clamp01(double v) => v < 0.0 ? 0.0 : v > 1.0 ? 1.0 : v;
    }
}
