// light: the light reaching a point, as URP draws it (contract section 3, docs/task-probes.md 2.7). Every Light URP
// lights with at run time adds intensity x its colour's luminance (linear, the temperature colour applied) x URP's
// distance and cone attenuation; where URP draws the light's shadows, a collider between them stops it (all but the
// shadow strength's share). The ambient adds the spherical harmonics URP lights a moving object at the point with
// (the baked light probes, else the ambient probe), straight up. In Unity's light units (not lux).
// "value": {"illuminance", "exposure", "brightness", "local", "directional", "sky", "lights", "point": [x, y, z]} |
// null when the point doesn't resolve; `exposure` and `brightness` null while the grade isn't known (LightKit.GradeKnown).
using System;
using System.Collections.Generic;
using UnityEngine;

namespace TaskProbe
{
    [ProbeQuery("light")]
    public sealed class LightQuery : Query
    {
        Dictionary<string, object> point;

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
            if (!LightKit.Urp) Probe.Error("light " + Id + ": the render pipeline isn't URP: the light is URP's, not the frame's");
            double local = 0.0, directional = 0.0;
            var lit = 0;
            foreach (var l in LightKit.Lights())
            {
                if (!LightKit.Lit(l, out var shadowed)) continue;
                var lum = LightKit.Luminance(LightKit.FinalColor(l));
                if (lum <= 0.0) continue;
                if (l.type == LightType.Directional)
                {
                    // the light travels along its forward: its ray comes from TraceLength back along it
                    var c = lum * Shade(l, shadowed, p - l.transform.forward * LightKit.TraceLength, p);
                    if (c <= 0.0) continue;
                    directional += c;
                }
                else
                {
                    var c = lum * Attenuation(l, p);
                    if (c <= 0.0) continue;
                    c *= Shade(l, shadowed, l.transform.position, p);
                    if (c <= 0.0) continue;
                    local += c;
                }
                lit++;
            }
            var sky = LightKit.Ambient(p);
            if (sky > 0.0) lit++;
            var illuminance = local + directional + sky;
            var exposure = LightKit.Exposure();
            sample["value"] = new Dictionary<string, object>(StringComparer.Ordinal)
            {
                ["illuminance"] = illuminance, ["exposure"] = exposure,
                ["brightness"] = exposure.HasValue ? illuminance * exposure.Value : (object)null,
                ["local"] = local, ["directional"] = directional, ["sky"] = sky, ["lights"] = (double)lit,
                ["point"] = Json.Vec(p),
            };
        }

        /// <summary>The share of a light's light that reaches `to` from `from`: 1, or where URP draws its shadows and a
        /// collider is in the way, what its shadow strength lets through (URP lerps its shadow by the strength).</summary>
        static double Shade(Light l, bool shadowed, Vector3 from, Vector3 to)
        {
            if (!shadowed || !LightKit.Blocked(from, to, l.transform)) return 1.0;
            return 1.0 - Clamp01(l.shadowStrength);
        }

        /// <summary>URP's attenuation of a point or spot light at `p` (RealtimeLights.hlsl DistanceAttenuation x
        /// AngleAttenuation, with the constants UniversalRenderPipelineCore prepares).</summary>
        static double Attenuation(Light l, Vector3 p)
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
