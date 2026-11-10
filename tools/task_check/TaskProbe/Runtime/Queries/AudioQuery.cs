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
        const double AudibleVolume = 0.001;

        string sound, soundClass;
        Sel owner;

        public override void Load()
        {
#if !TASKPROBE_AUDIO
            Probe.Error("audio " + Id + ": the project has no Audio module: no sound is read");
#endif
            var select = Json.Obj(Def, "select");
            if (select == null) return;
            sound = Json.Str(select, "sound");
            soundClass = Json.Str(select, "sound_class");
            var o = Json.Obj(select, "owner");
            if (o != null) owner = Sel.Parse(o, Kind + " " + Id);
        }

#if TASKPROBE_AUDIO
        // the tap's level is read once a pass and shared by every audio query: reading it resets it
        static int levelStamp = -1;
        static bool levelAny;
        static double levelRms, levelPeak;
        static readonly List<AudioSource> sources = new List<AudioSource>();

        static void Level(out bool any, out double rms, out double peak)
        {
            if (levelStamp != Probe.Stamp)
            {
                levelStamp = Probe.Stamp;
                levelAny = AudioTap.Level(out levelRms, out levelPeak);
            }
            any = levelAny;
            rms = levelRms;
            peak = levelPeak;
        }

        public override void Sample(double t, Dictionary<string, object> sample)
        {
            Level(out var any, out var rms, out var peak);
            var listener = AudioTap.Listener();
            if (listener == null)
            {
                sample["value"] = null;
                return;
            }
            var here = listener.transform.position;
            // an owner select that matches nothing (its point doesn't resolve) owns nothing
            var owners = owner != null ? Find.Owners(owner) : null;
            int count = 0, audible = 0;
            double sum = 0.0, max = 0.0;
            string loudest = null;
            if (owners == null || owners.Count > 0)
            {
                // in hierarchy order: the sum and a tie for the loudest come out the same in every play
                sources.Clear();
                sources.AddRange(UnityEngine.Object.FindObjectsByType<AudioSource>(FindObjectsInactive.Exclude, FindObjectsSortMode.None));
                Find.SortByHierarchy(sources);
                foreach (var source in sources)
                {
                    if (source == null || !source.enabled || !source.isPlaying || Find.IsOwn(source)) continue;
                    var clip = source.clip;
                    if (sound != null && !Find.Wild(sound, clip != null ? clip.name : null)) continue;
                    if (soundClass != null)
                    {
                        var group = source.outputAudioMixerGroup;
                        if (group == null || !Find.Wild(soundClass, group.name)) continue;
                    }
                    if (owners != null && !Find.OwnedBy(source, owners)) continue;
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
            }
            sample["value"] = new Dictionary<string, object>(StringComparer.Ordinal)
            {
                ["count"] = (double)count, ["audible"] = (double)audible, ["volume"] = sum, ["max_volume"] = max,
                ["loudest"] = loudest, ["level"] = any ? rms : (object)null, ["peak"] = any ? peak : (object)null,
                ["listener"] = listener.name,
            };
        }

        /// <summary>A source's volume at the listener at `here`: volume (0 muted) x ((1 - blend) + blend x rolloff(d)).</summary>
        static double AtListener(AudioSource s, Vector3 here)
        {
            if (s.mute) return 0.0;
            double volume = s.volume;
            var blend = Mathf.Clamp01(s.spatialBlend);
            if (blend <= 0f) return volume;
            var d = Vector3.Distance(s.transform.position, here);
            return volume * ((1.0 - blend) + blend * Rolloff(s, d));
        }

        /// <summary>The distance attenuation of a 3D source at `d` m.</summary>
        static double Rolloff(AudioSource s, double d)
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
