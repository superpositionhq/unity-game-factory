// grading: the colour pipeline at the player's camera (contract section 3, docs/task-probes.md 2.8). The URP volume
// stack in effect at the camera (LightKit.StackAt: blended for the camera's volume trigger and layer mask at the
// sample, or the camera's own scripted stack), read as the shader constants URP's ColorGradingLutPass prepares, plus
// the key lights (the sun, the ambient) and the fog. The checker turns it into grey, cast, warmth, tint, saturation and
// contrast (tools/task_check/colour.py).
// "value": {"source", "pipeline", "post_processing", "grading_mode", "color_balance", "contrast", "saturation",
// "color_filter", "post_exposure", "hue_shift", "lift", "gamma", "gain", "tonemapping", "sun", "sky", "fog",
// "post:<Component>.<parameter>[.<channel>]"...}. Colours are linear rgb.
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
            if (LightKit.Urp)
            {
#if TASKPROBE_URP
                v["pipeline"] = "urp";
                var stack = LightKit.StackAt(out var source, out var post);
                v["source"] = source;
                v["post_processing"] = post ? 1.0 : 0.0;
                v["grading_mode"] = ((UniversalRenderPipelineAsset)pipeline).colorGradingMode == ColorGradingMode.HighDynamicRange ? "hdr" : "ldr";
                // a camera that renders no post-processing draws the image ungraded: the constants are neutral
                Grade(post ? stack : null, v);
                foreach (var name in posts) v[name] = stack != null ? Post(stack, name) : null;
#endif
            }
            else
            {
                Probe.Error("grading " + Id + ": the render pipeline isn't URP: no grading is read (the constants are neutral, post: has no value)");
                v["pipeline"] = pipeline != null ? pipeline.GetType().Name : "builtin";
                v["source"] = "none";
                v["post_processing"] = 0.0;
                v["grading_mode"] = "ldr";
                Neutral(v);
                foreach (var name in posts) v[name] = null;
            }
            v["sun"] = Sun();
            LightKit.Sky(out var mode, out var colour, out var intensity);
            v["sky"] = new Dictionary<string, object>(StringComparer.Ordinal)
            {
                ["mode"] = mode, ["color"] = Json.Rgb(colour), ["intensity"] = intensity,
            };
            v["fog"] = new Dictionary<string, object>(StringComparer.Ordinal)
            {
                ["enabled"] = RenderSettings.fog ? 1.0 : 0.0, ["density"] = (double)RenderSettings.fogDensity,
                ["color"] = Json.Rgb(Find.Linear(RenderSettings.fogColor)), ["mode"] = RenderSettings.fogMode.ToString(),
            };
            sample["value"] = v;
        }

        static void Neutral(Dictionary<string, object> v)
        {
#if TASKPROBE_URP
            v["color_balance"] = Json.Vec(ColorUtils.ColorBalanceToLMSCoeffs(0f, 0f));
#else
            v["color_balance"] = Json.Vec(Vector3.one);
#endif
            v["contrast"] = 1.0;
            v["saturation"] = 1.0;
            v["color_filter"] = Json.Rgb(Color.white);
            v["post_exposure"] = 0.0;
            v["hue_shift"] = 0.0;
            v["lift"] = Json.Rgb(Color.black);
            v["gamma"] = Json.Rgb(Color.white);
            v["gain"] = Json.Rgb(Color.white);
            v["tonemapping"] = "None";
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
            v["color_balance"] = Json.Vec(ColorUtils.ColorBalanceToLMSCoeffs(white.temperature.value, white.tint.value));
            v["contrast"] = (double)(adjust.contrast.value / 100f + 1f);
            v["saturation"] = (double)(adjust.saturation.value / 100f + 1f);
            v["color_filter"] = Json.Rgb(adjust.colorFilter.value.linear);
            v["post_exposure"] = (double)adjust.postExposure.value;
            v["hue_shift"] = (double)adjust.hueShift.value;
            var (lift, gamma, gain) = ColorUtils.PrepareLiftGammaGain(lgg.lift.value, lgg.gamma.value, lgg.gain.value);
            v["lift"] = Json.Rgb(lift);
            v["gamma"] = Json.Rgb(gamma);
            v["gain"] = Json.Rgb(gain);
            v["tonemapping"] = tone.mode.value.ToString();
        }

        static readonly Dictionary<string, Type> Components = new Dictionary<string, Type>(StringComparer.Ordinal);

        static Type ComponentType(string name)
        {
            if (Components.TryGetValue(name, out var found)) return found;
            foreach (var t in VolumeManager.instance.baseComponentTypeArray ?? Array.Empty<Type>())
                if (t.Name == name || t.FullName == name) { found = t; break; }
            Components[name] = found;
            return found;
        }

        /// <summary>post:&lt;Component&gt;.&lt;parameter&gt;[.&lt;channel&gt;]: the parameter's value in the stack (its blend of
        /// every volume's override, else the component's default). Floats, ints, bools as 1/0, enums as their value, an
        /// object reference 1 when set, a colour's or a vector's channel. Null when it doesn't resolve.</summary>
        object Post(VolumeStack stack, string field)
        {
            var parts = field.Substring(5).Split('.');
            if (parts.Length < 2 || parts.Length > 3)
            {
                Probe.Error("grading " + Id + ": " + field + " names no parameter (post:<Component>.<parameter>[.<channel>])");
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
            var member = type.GetField(parts[1], BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic);
            if (member == null || !typeof(VolumeParameter).IsAssignableFrom(member.FieldType))
            {
                Probe.Error("grading " + Id + ": " + parts[0] + " has no parameter " + parts[1]);
                return null;
            }
            var parameter = member.GetValue(component);
            if (parameter == null) return null;
            var value = Reflect.Get(parameter, "value");
            if (parts.Length == 3)
            {
                if (Channel(value, parts[2], out var part)) return part;
                Probe.Error("grading " + Id + ": " + field + ": " + parts[0] + "." + parts[1] + " has no channel " + parts[2]);
                return null;
            }
            if (value is Color || value is Vector2 || value is Vector3 || value is Vector4)
            {
                Probe.Error("grading " + Id + ": " + field + " is a " + value.GetType().Name + ": name a part (.r .g .b .a or .x .y .z .w)");
                return null;
            }
            var plain = Reflect.Plain(value);
            if (plain is double) return plain;
            Probe.Error("grading " + Id + ": " + field + " is a " + value.GetType().Name + ": it has no single number");
            return null;
        }

        /// <summary>A colour's or a vector's channel by either spelling, as the editor pass reads one: r or x the first, g
        /// or y the second, b or z the third, a or w the fourth.</summary>
        static bool Channel(object value, string name, out double part)
        {
            part = 0.0;
            Vector4 v;
            int size;
            switch (value)
            {
                case Color c: v = c; size = 4; break;
                case Vector4 v4: v = v4; size = 4; break;
                case Vector3 v3: v = v3; size = 3; break;
                case Vector2 v2: v = v2; size = 2; break;
                default: return false;
            }
            var i = name == "r" || name == "x" ? 0 : name == "g" || name == "y" ? 1 : name == "b" || name == "z" ? 2 : name == "a" || name == "w" ? 3 : -1;
            if (i < 0 || i >= size) return false;
            part = v[i];
            return true;
        }
#endif

        /// <summary>The strongest directional light that is on (by intensity; of equals the first in hierarchy order): its
        /// colour (linear), intensity, temperature and the colour it lights with (colour x the temperature colour when
        /// used). Null when there is none.</summary>
        static object Sun()
        {
            Light sun = null;
            foreach (var l in LightKit.Lights())
                if (l != null && l.type == LightType.Directional && Find.LightOn(l) && (sun == null || l.intensity > sun.intensity)) sun = l;
            if (sun == null) return null;
            return new Dictionary<string, object>(StringComparer.Ordinal)
            {
                ["name"] = sun.name, ["color"] = Json.Rgb(Find.Linear(sun.color)), ["intensity"] = (double)sun.intensity,
                ["temperature"] = (double)sun.colorTemperature, ["use_temperature"] = sun.useColorTemperature ? 1.0 : 0.0,
                ["lit_color"] = Json.Rgb(LightKit.LitColor(sun)),
            };
        }
    }
}
