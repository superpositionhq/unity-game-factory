// grading: the colour pipeline at the player's camera (contract section 3, docs/task-probes.md 2.8). The URP volume
// stack in effect at the camera (LightKit.StackAt: blended for the camera's volume trigger and layer mask at the
// sample, or the camera's own scripted stack), read as the shader constants URP's ColorGradingLutPass prepares, plus
// the key lights (the sun, the ambient) and the fog. The checker turns it into grey, cast, warmth, tint, saturation and
// contrast (tools/task_check/colour.py).
// "value": {"source", "pipeline", "post_processing", "grading_mode", "color_balance", "contrast", "saturation",
// "color_filter", "post_exposure", "hue_shift", "lift", "gamma", "gain", "tonemapping", "sun", "sky", "fog",
// "post:<Component>.<parameter>[.<sub>]"...}. Colours are linear rgb.
using System;
using System.Collections.Generic;
using System.Reflection;
using UnityEngine;
using UnityEngine.Rendering;
#if TASKPROBE_URP
using UnityEngine.Rendering.Universal;
#endif

namespace TaskProbe
{
    [ProbeQuery("grading")]
    public sealed class GradingQuery : Query
    {
        readonly List<string> posts = new List<string>();

        public override void Load()
        {
            foreach (var f in Fields)
                if (f.StartsWith("post:", StringComparison.Ordinal) && f.Length > 5 && !posts.Contains(f)) posts.Add(f);
        }

        public override void Sample(double t, Dictionary<string, object> sample)
        {
            var v = new Dictionary<string, object>(StringComparer.Ordinal);
            var pipeline = GraphicsSettings.currentRenderPipeline;
#if TASKPROBE_URP
            v["pipeline"] = pipeline is UniversalRenderPipelineAsset ? "urp" : pipeline != null ? pipeline.GetType().Name : "builtin";
            var stack = LightKit.StackAt(out var source, out var post);
            v["source"] = source;
            v["post_processing"] = post ? 1.0 : 0.0;
            var urp = pipeline as UniversalRenderPipelineAsset;
            v["grading_mode"] = urp != null && urp.colorGradingMode == ColorGradingMode.HighDynamicRange ? "hdr" : "ldr";
            // a camera that renders no post-processing draws the image ungraded: the constants are neutral
            Grade(post ? stack : null, v);
            foreach (var name in posts) v[name] = stack != null ? Post(stack, name) : null;
#else
            v["pipeline"] = pipeline != null ? pipeline.GetType().Name : "builtin";
            v["source"] = "none";
            v["post_processing"] = 0.0;
            v["grading_mode"] = "ldr";
            Neutral(v);
            foreach (var name in posts) v[name] = null;
#endif
            v["sun"] = Sun();
            LightKit.Ambient(out var mode, out var colour, out var intensity);
            v["sky"] = new Dictionary<string, object>(StringComparer.Ordinal)
            {
                ["mode"] = mode, ["color"] = Json.Rgb(colour), ["intensity"] = intensity,
            };
            v["fog"] = new Dictionary<string, object>(StringComparer.Ordinal)
            {
                ["enabled"] = RenderSettings.fog ? 1.0 : 0.0, ["density"] = (double)RenderSettings.fogDensity,
                ["color"] = Json.Rgb(LightKit.Working(RenderSettings.fogColor)), ["mode"] = RenderSettings.fogMode.ToString(),
            };
            sample["value"] = v;
        }

        static List<object> Rgb(Vector4 c) => new List<object> { (double)c.x, (double)c.y, (double)c.z };

        static void Neutral(Dictionary<string, object> v)
        {
            v["color_balance"] = Rgb(LmsNeutral());
            v["contrast"] = 1.0;
            v["saturation"] = 1.0;
            v["color_filter"] = new List<object> { 1.0, 1.0, 1.0 };
            v["post_exposure"] = 0.0;
            v["hue_shift"] = 0.0;
            v["lift"] = new List<object> { 0.0, 0.0, 0.0 };
            v["gamma"] = new List<object> { 1.0, 1.0, 1.0 };
            v["gain"] = new List<object> { 1.0, 1.0, 1.0 };
            v["tonemapping"] = "None";
        }

        static Vector3 LmsNeutral()
        {
#if TASKPROBE_URP
            return ColorUtils.ColorBalanceToLMSCoeffs(0f, 0f);
#else
            return Vector3.one;
#endif
        }

#if TASKPROBE_URP
        /// <summary>The constants ColorGradingLutPass hands the LUT builder (null stack: neutral).</summary>
        static void Grade(VolumeStack stack, Dictionary<string, object> v)
        {
            if (stack == null)
            {
                Neutral(v);
                return;
            }
            var white = stack.GetComponent<WhiteBalance>();
            var adjust = stack.GetComponent<ColorAdjustments>();
            var lgg = stack.GetComponent<LiftGammaGain>();
            var tone = stack.GetComponent<Tonemapping>();
            v["color_balance"] = Rgb(ColorUtils.ColorBalanceToLMSCoeffs(white.temperature.value, white.tint.value));
            v["contrast"] = (double)(adjust.contrast.value / 100f + 1f);
            v["saturation"] = (double)(adjust.saturation.value / 100f + 1f);
            v["color_filter"] = Json.Rgb(adjust.colorFilter.value.linear);
            v["post_exposure"] = (double)adjust.postExposure.value;
            v["hue_shift"] = (double)adjust.hueShift.value;
            var (lift, gamma, gain) = ColorUtils.PrepareLiftGammaGain(lgg.lift.value, lgg.gamma.value, lgg.gain.value);
            v["lift"] = Rgb(lift);
            v["gamma"] = Rgb(gamma);
            v["gain"] = Rgb(gain);
            v["tonemapping"] = tone.mode.value.ToString();
        }

        static readonly Dictionary<string, Type> Components = new Dictionary<string, Type>(StringComparer.Ordinal);

        static Type ComponentType(string name)
        {
            if (Components.TryGetValue(name, out var found)) return found;
            var types = VolumeManager.instance.baseComponentTypeArray;
            if (types != null)
                foreach (var t in types)
                    if (t.Name == name || t.FullName == name) { found = t; break; }
            if (found == null)
                foreach (var t in types ?? Array.Empty<Type>())
                    if (string.Equals(t.Name, name, StringComparison.OrdinalIgnoreCase)) { found = t; break; }
            Components[name] = found;
            return found;
        }

        /// <summary>post:&lt;Component&gt;.&lt;parameter&gt;[.&lt;sub&gt;]: the parameter's value in the stack (its blend of every
        /// volume's override, else the component's default). Floats, ints, bools as 1/0, enums as their value, a colour's
        /// or vector's .r/.x... with one more part, an object reference 1 when set. Null when it doesn't resolve.</summary>
        object Post(VolumeStack stack, string field)
        {
            var parts = field.Substring(5).Split(new[] { '.' }, 3);
            if (parts.Length < 2)
            {
                Probe.Error("grading " + Id + ": " + field + " names no parameter (post:<Component>.<parameter>)");
                return null;
            }
            var type = ComponentType(parts[0]);
            if (type == null)
            {
                Probe.Error("grading " + Id + ": no volume component " + parts[0]);
                return null;
            }
            var component = stack.GetComponent(type);
            if (component == null || !component.active) return null;
            var member = type.GetField(parts[1], BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic)
                         ?? type.GetField(parts[1], BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.IgnoreCase);
            if (member == null || !typeof(VolumeParameter).IsAssignableFrom(member.FieldType))
            {
                Probe.Error("grading " + Id + ": " + parts[0] + " has no parameter " + parts[1]);
                return null;
            }
            var parameter = member.GetValue(component);
            if (parameter == null) return null;
            var value = Reflect.Get(parameter, "value");
            if (parts.Length > 2)
            {
                var sub = Reflect.ReadPath(value, parts[2], out var ok);
                if (!ok)
                {
                    Probe.Error("grading " + Id + ": " + field + ": no member " + parts[2]);
                    return null;
                }
                value = sub;
            }
            if (value is Color || value is Vector2 || value is Vector3 || value is Vector4)
            {
                Probe.Error("grading " + Id + ": " + field + " is a " + value.GetType().Name + ": name a part (.r .g .b .a or .x .y .z .w)");
                return null;
            }
            var plain = Reflect.Plain(value);
            return plain is string ? null : plain;
        }
#endif

        /// <summary>The strongest directional light that is on (by intensity): its colour (linear), intensity, temperature
        /// and the colour it lights with (colour x the temperature colour when used). Null when there is none.</summary>
        static object Sun()
        {
            Light sun = null;
            foreach (var l in LightKit.Lights())
                if (l.type == LightType.Directional && LightKit.On(l) && (sun == null || l.intensity > sun.intensity)) sun = l;
            if (sun == null) return null;
            return new Dictionary<string, object>(StringComparer.Ordinal)
            {
                ["name"] = sun.name, ["color"] = Json.Rgb(LightKit.Working(sun.color)), ["intensity"] = (double)sun.intensity,
                ["temperature"] = (double)sun.colorTemperature, ["use_temperature"] = sun.useColorTemperature ? 1.0 : 0.0,
                ["lit_color"] = Json.Rgb(LightKit.LitColor(sun)),
            };
        }
    }
}
