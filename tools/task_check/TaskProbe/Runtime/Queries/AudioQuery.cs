// audio: what the player hears (contract section 3, docs/task-probes.md 2.16). Every AudioSource that is playing and
// matches the select, at its volume at the listener: its volume (0 when muted) x its distance attenuation at the
// listener's distance by its rolloff (logarithmic, linear or its custom curve, between min and max distance), for its
// 3D share by spatialBlend. Mixer group volumes and AudioListener.volume are left out. `level` and `peak` are the
// listener's mixed output since the previous sample (the core's AudioTap: mixers and effects included).
// The sounds that start are seen once a frame (AudioStarts): a source that plays and didn't the frame before, however
// short its sound, counted in the sample's interval in which it was told.
// "value": {"count", "audible", "volume", "max_volume", "loudest", "level", "peak", "listener", "started",
// "started_audible", "starts": [{"t", "sound", "named"}] (the first 64), "starts_total"} | null without an
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

        /// <summary>A sample lists this many starts by name; `starts_total` says how many there were.</summary>
        const int StartsListed = 64;

        string sound, soundClass;
        Sel owner;
        NearSel near;

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
            near = NearSel.Parse(Json.Obj(select, "near"));
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

        // the starts this query's select took since the previous sample
        int started, startedAudible;
        readonly List<object> starts = new List<object>();
        readonly HashSet<AudioStarts.Start> quiet = new HashSet<AudioStarts.Start>();  // taken, not audible yet

        public override void Frame(float dt)
        {
            AudioStarts.Frame(Probe);
            foreach (var start in AudioStarts.Told)
            {
                if (!Takes(start)) continue;
                started++;
                if (starts.Count < StartsListed)
                    starts.Add(new Dictionary<string, object>(StringComparer.Ordinal) { ["t"] = start.T, ["sound"] = start.Named ? start.Sound : null, ["named"] = start.Named });
                quiet.Add(start);
            }
            foreach (var start in AudioStarts.Heard)
                if (quiet.Remove(start)) startedAudible++;
            quiet.RemoveWhere(s => s.Over);
        }

        /// <summary>Whether the select takes a sound that started: by its clip's name (one without a name it can tell,
        /// a one-shot's, matches no `sound`), its mixer group, the objects it was on and the place it started at (a 2D
        /// sound is near nothing).</summary>
        bool Takes(AudioStarts.Start start)
        {
            if (sound != null && !(start.Named && Find.Wild(sound, start.Sound))) return false;
            if (soundClass != null && (start.Group == null || !Find.Wild(soundClass, start.Group))) return false;
            if (owner != null)
            {
                var owners = Find.Owners(owner);
                if (!start.On.Exists(go => go != null && owners.Contains(go))) return false;
            }
            if (near != null && !(start.Placed && near.Resolve(out var centre) && near.Contains(centre, start.At))) return false;
            return true;
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
            var centre = Vector3.zero;
            var placed = near == null || near.Resolve(out centre);  // a near whose point doesn't resolve is near nothing
            if (placed && (owners == null || owners.Count > 0))
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
                    if (near != null && !(source.spatialBlend > 0f && near.Contains(centre, source.transform.position))) continue;
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
                ["listener"] = listener.name, ["started"] = (double)started, ["started_audible"] = (double)startedAudible,
                ["starts"] = new List<object>(starts), ["starts_total"] = (double)started,
            };
            started = startedAudible = 0;
            starts.Clear();
        }

        /// <summary>A source's volume at the listener at `here`: volume (0 muted) x ((1 - blend) + blend x rolloff(d)).</summary>
        internal static double AtListener(AudioSource s, Vector3 here)
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

#if TASKPROBE_AUDIO
    /// <summary>The sounds that start, seen once a frame for every audio query: an enabled AudioSource on an active
    /// object that plays and didn't the frame before (a new source, a source played again after it ended, a
    /// PlayClipAtPoint's own source), or one that isn't looping whose clip went back (played again while playing).
    /// A source that goes on where it stood (unpaused, AudioListener.pause lifted) starts nothing.
    /// A start is told once its name is settled: its source's clip when that clip is what plays (its position in the
    /// clip moved), within 5 frames; else it has no name the probe can tell (a PlayOneShot plays a clip the source
    /// doesn't show). A one-shot on a source that is already playing starts nothing the engine shows: not seen.
    /// A start is heard once it reads 0.001 or louder at the listener, in the frame it started or a later one.</summary>
    public static class AudioStarts
    {
        const int SettleFrames = 5;
        const double AudibleVolume = 0.001;

        public sealed class Start
        {
            public AudioSource Source;
            public AudioClip Clip;
            public int Samples, Frames;
            public string Sound, Group;
            public bool Named, Placed, Loud, Over;  // Loud: audible in the frame it started
            public Vector3 At;
            public double T;
            public readonly List<GameObject> On = new List<GameObject>();  // its object and the objects above it
        }

        sealed class Playing
        {
            public AudioSource Source;
            public AudioClip Clip;
            public int Samples;   // its position in its clip the last frame it played
            public bool Idle;     // it didn't play the frame before
            public int Seen;
        }

        /// <summary>The starts told this frame, in the order they started (of one frame: in hierarchy order), and those
        /// of the told ones first heard this frame.</summary>
        public static readonly List<Start> Told = new List<Start>(), Heard = new List<Start>();
        static readonly Dictionary<int, Playing> playing = new Dictionary<int, Playing>();
        static readonly List<Start> settling = new List<Start>(), quiet = new List<Start>();
        static readonly List<AudioSource> fresh = new List<AudioSource>();
        static readonly List<int> gone = new List<int>();
        static int frame = -1;

        public static void Frame(Probe probe)
        {
            if (frame == Time.frameCount) return;
            frame = Time.frameCount;
            Told.Clear();
            Heard.Clear();
            // the starts of the frames before, once their names are settled
            for (var i = 0; i < settling.Count; i++)
            {
                var s = settling[i];
                var alive = s.Source != null && s.Source.isPlaying;
                if (alive && s.Clip != null && s.Source.clip == s.Clip && s.Source.timeSamples != s.Samples)
                {
                    s.Named = true;
                    s.Sound = s.Clip.name;
                }
                else if (alive && ++s.Frames < SettleFrames) continue;
                settling.RemoveAt(i--);
                Told.Add(s);
                quiet.Add(s);
            }
            var listener = AudioTap.Listener();
            // what plays now
            fresh.Clear();
            foreach (var source in UnityEngine.Object.FindObjectsByType<AudioSource>(FindObjectsInactive.Exclude, FindObjectsSortMode.None))
            {
                if (source == null || !source.enabled || !source.isPlaying || Find.IsOwn(source)) continue;
                var id = source.GetInstanceID();
                var samples = source.timeSamples;
                if (!playing.TryGetValue(id, out var state))
                {
                    playing[id] = state = new Playing { Source = source };
                    fresh.Add(source);
                }
                else if (state.Idle)
                {
                    // it plays again: on from where it stood (a pause lifted) is no start
                    if (!(state.Samples > 0 && samples >= state.Samples && source.clip == state.Clip)) fresh.Add(source);
                }
                else if (!source.loop && source.clip != null && samples < state.Samples) fresh.Add(source);
                state.Samples = samples;
                state.Clip = source.clip;
                state.Idle = false;
                state.Seen = frame;
            }
            gone.Clear();
            foreach (var kv in playing)
            {
                if (kv.Value.Seen == frame) continue;
                if (kv.Value.Source == null) gone.Add(kv.Key);
                else kv.Value.Idle = true;
            }
            foreach (var id in gone) playing.Remove(id);
            Find.SortByHierarchy(fresh);
            foreach (var source in fresh)
            {
                var start = new Start
                {
                    Source = source, Clip = source.clip, Samples = source.timeSamples, T = probe.Elapsed,
                    Group = source.outputAudioMixerGroup != null ? source.outputAudioMixerGroup.name : null,
                    Placed = source.spatialBlend > 0f, At = source.transform.position,
                };
                start.Loud = listener != null && AudioQuery.AtListener(source, listener.transform.position) >= AudibleVolume;
                for (var t = source.transform; t != null; t = t.parent) start.On.Add(t.gameObject);
                settling.Add(start);
            }
            // the told ones not heard yet
            for (var i = 0; i < quiet.Count; i++)
            {
                var s = quiet[i];
                if (s.Loud) Heard.Add(s);
                else if (s.Source == null || !s.Source.isPlaying) s.Over = true;
                else if (listener != null && AudioQuery.AtListener(s.Source, listener.transform.position) >= AudibleVolume) Heard.Add(s);
                else continue;
                quiet.RemoveAt(i--);
            }
        }
    }
#endif
}
