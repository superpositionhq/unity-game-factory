// audio: what the player hears (contract section 3, docs/task-probes.md 2.16). Every AudioSource that is playing and
// matches the select, at its volume at the listener: its volume (0 when muted) x its distance attenuation at the
// listener's distance by its rolloff (logarithmic, linear or its custom curve, between min and max distance), for its
// 3D share by spatialBlend. Mixer group volumes and AudioListener.volume are left out. `level` and `peak` are the
// listener's mixed output since the previous sample (the core's AudioTap: mixers and effects included).
// "value": {"count", "audible", "volume", "max_volume", "loudest", "level", "peak", "listener"} | null without an
// AudioListener (or without the audio module).
using System;
using System.Collections.Generic;
using UnityEngine;

namespace TaskProbe
{
    [ProbeQuery("audio")]
    public sealed class AudioQuery : Query
    {
        /// <summary>A source at this volume (-60 dB) or louder is audible.</summary>
        public const double AudibleVolume = 0.001;

        string sound, soundClass;
        Sel owner;

        public override void Load()
        {
            var select = Json.Obj(Def, "select");
            if (select == null) return;
            sound = Json.Str(select, "sound");
            soundClass = Json.Str(select, "sound_class");
            var o = Json.Obj(select, "owner");
            if (o != null) owner = Sel.Parse(o);
        }

#if TASKPROBE_AUDIO
        // the tap's level is read once per sample time and shared: reading it resets it
        static int levelFrame = -1;
        static bool levelAny;
        static double levelRms, levelPeak;

        static void Level(out bool any, out double rms, out double peak)
        {
            if (levelFrame != Time.frameCount)
            {
                levelFrame = Time.frameCount;
                levelAny = AudioTap.Level(out levelRms, out levelPeak);
            }
            any = levelAny;
            rms = levelRms;
            peak = levelPeak;
        }

        /// <summary>The listener the player hears through: the first enabled AudioListener on an active object.</summary>
        public static AudioListener Listener()
        {
            foreach (var l in UnityEngine.Object.FindObjectsByType<AudioListener>(FindObjectsInactive.Exclude, FindObjectsSortMode.InstanceID))
                if (l.enabled && l.gameObject.activeInHierarchy) return l;
            return null;
        }

        public override void Sample(double t, Dictionary<string, object> sample)
        {
            Level(out var any, out var rms, out var peak);
            var listener = Listener();
            if (listener == null)
            {
                sample["value"] = null;
                return;
            }
            var here = listener.transform.position;
            var centre = Vector3.zero;
            var hasCentre = Vector3.zero;
            var ownerOk = owner == null
                          || ((owner.Near == null || Find.Point(owner.Near.Point, out centre))
                              && (owner.Has?.Near == null || Find.Point(owner.Has.Near.Point, out hasCentre)));
            int count = 0, audible = 0;
            double sum = 0.0, max = 0.0;
            string loudest = null;
            if (ownerOk)
                foreach (var source in UnityEngine.Object.FindObjectsByType<AudioSource>(FindObjectsInactive.Exclude, FindObjectsSortMode.InstanceID))
                {
                    if (source == null || !source.enabled || !source.isPlaying || Probe.IsOwn(source.gameObject)) continue;
                    var clip = source.clip;
                    if (sound != null && !Find.Wild(sound, clip != null ? clip.name : null)) continue;
                    if (soundClass != null)
                    {
                        var group = source.outputAudioMixerGroup;
                        if (group == null || !Find.Wild(soundClass, group.name)) continue;
                    }
                    if (owner != null && !Find.OwnedBy(source, owner, centre, hasCentre)) continue;
                    var v = AtListener(source, here);
                    count++;
                    if (v >= AudibleVolume) audible++;
                    sum += v;
                    if (loudest == null || v > max)
                    {
                        max = v;
                        loudest = clip != null ? clip.name : "";
                    }
                }
            sample["value"] = new Dictionary<string, object>(StringComparer.Ordinal)
            {
                ["count"] = (double)count, ["audible"] = (double)audible, ["volume"] = sum, ["max_volume"] = max,
                ["loudest"] = loudest, ["level"] = any ? rms : (object)null, ["peak"] = any ? peak : (object)null,
                ["listener"] = listener.name,
            };
        }

        /// <summary>A source's volume at the listener at `here`: volume (0 muted) x ((1 - blend) + blend x rolloff(d)).</summary>
        public static double AtListener(AudioSource s, Vector3 here)
        {
            if (s.mute) return 0.0;
            double volume = s.volume;
            var blend = Mathf.Clamp01(s.spatialBlend);
            if (blend <= 0f) return volume;
            var d = Vector3.Distance(s.transform.position, here);
            return volume * ((1.0 - blend) + blend * Rolloff(s, d));
        }

        /// <summary>The distance attenuation of a 3D source at `d` m.</summary>
        public static double Rolloff(AudioSource s, double d)
        {
            double min = Math.Max(s.minDistance, 1e-6), max = Math.Max(s.maxDistance, min);
            switch (s.rolloffMode)
            {
                case AudioRolloffMode.Logarithmic:
                    // inverse distance from min distance; it goes on falling past max distance (measured: 1/80 at
                    // 80 m with min 1, max 50), though the docs say it stops there
                    return min / Math.Max(d, min);
                case AudioRolloffMode.Linear:
                    if (max <= min) return d <= min ? 1.0 : 0.0;
                    return Math.Min(Math.Max((max - d) / (max - min), 0.0), 1.0);
                default:
                {
                    // the custom curve runs over distance / max distance; past its end it holds its last value
                    var curve = s.GetCustomCurve(AudioSourceCurveType.CustomRolloff);
                    if (curve == null || curve.length == 0) return 1.0;
                    var x = max > 0 ? (float)Math.Min(d / max, 1.0) : 1f;
                    return Math.Max(0.0, curve.Evaluate(x));
                }
            }
        }
#else
        public override void Sample(double t, Dictionary<string, object> sample)
        {
            sample["value"] = null;
        }
#endif
    }
}
