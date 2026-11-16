// audio: what the player hears (contract section 3, docs/task-probes.md 2.16). Every AudioSource that is playing and
// matches the select, at its volume at the listener: its volume (0 when muted) x its distance attenuation at the
// listener's distance by its rolloff (logarithmic, linear or its custom curve, between min and max distance), for its
// 3D share by spatialBlend. Mixer group volumes and AudioListener.volume are left out. `level` and `peak` are the
// listener's mixed output since the previous sample (the core's AudioTap: mixers and effects included).
// The sounds that start are seen once a frame (AudioStarts): a source that plays and didn't the frame before, however
// short its sound, counted in the sample's interval in which it was told.
// "value": {"count", "audible", "volume", "max_volume", "loudest", "level", "peak", "listener", "started",
// "started_audible", "starts": [{"t", "sound", "named"}] (the first 64), "starts_total"} | null without an
// AudioListener (or without the audio module). With a `near` whose point doesn't resolve, what the select picks has
// no value: count to loudest at that sample, the started keys when a sound began while it didn't. Nor have the
// started keys a value in an interval in which a `sound` select met a start without a name: it could be that sound.
// `started` and `started_audible` count a start in the interval it began in (with a `sound` select: in the one its
// name was told in); `starts` and `starts_total` are the starts whose names were told in the interval.
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
        int started, startedAudible, named;
        bool blind;  // a start the select couldn't judge: the near's point didn't resolve, or a `sound` select met a nameless one
        readonly List<object> starts = new List<object>();
        readonly HashSet<AudioStarts.Start> mine = new HashSet<AudioStarts.Start>();  // taken by where it began, name not settled yet

        public override void Frame(float dt)
        {
            AudioStarts.Frame(Probe);
            // by what is true in the frame it began: its group, the objects it is on, its place (a source that is
            // destroyed before its name settles is still taken). Without a `sound` select it counts at once; with
            // one, when its name is told.
            foreach (var start in AudioStarts.Begun)
            {
                if (!Places(start)) continue;
                mine.Add(start);
                if (sound == null) Count(start);
            }
            Name(AudioStarts.Told);
        }

        void Count(AudioStarts.Start start)
        {
            started++;
            if (start.Loud) startedAudible++;
        }

        /// <summary>The starts whose names are settled: each of this query's gets its row, and with a `sound` select
        /// is counted now when its name fits. One without a name could be the sound asked for (a PlayOneShot shows no
        /// clip): the interval's count can't be told then.</summary>
        void Name(List<AudioStarts.Start> told)
        {
            foreach (var start in told)
            {
                if (!mine.Remove(start)) continue;
                if (sound != null)
                {
                    if (!start.Named) { blind = true; continue; }
                    if (!Find.Wild(sound, start.Sound)) continue;
                    Count(start);
                }
                named++;
                if (starts.Count < StartsListed)
                    starts.Add(new Dictionary<string, object>(StringComparer.Ordinal) { ["t"] = start.T, ["sound"] = start.Named ? start.Sound : null, ["named"] = start.Named });
            }
        }

        /// <summary>Whether the select takes a sound that begins this frame, but for its name: its mixer group, the
        /// objects it is on and the place it starts at (a 2D sound is near nothing).</summary>
        bool Places(AudioStarts.Start start)
        {
            if (soundClass != null && (start.Group == null || !Find.Wild(soundClass, start.Group))) return false;
            if (owner != null)
            {
                var owners = Find.Owners(owner);
                if (!start.On.Exists(go => go != null && owners.Contains(go))) return false;
            }
            if (near != null)
            {
                if (!near.Resolve(out var centre)) { blind = true; return false; }
                if (!(start.Placed && near.Contains(centre, start.At))) return false;
            }
            return true;
        }

        public override void Sample(double t, Dictionary<string, object> sample)
        {
            // the play's last sample: what is still settling is told now, named or not
            if (Probe.LastSample) Name(AudioStarts.Rest());
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
            // a near whose point doesn't resolve can't say what is near: no value, never 0
            var placed = near == null || near.Resolve(out centre);
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
            var value = new Dictionary<string, object>(StringComparer.Ordinal)
            {
                ["level"] = any ? rms : (object)null, ["peak"] = any ? peak : (object)null, ["listener"] = listener.name,
            };
            if (placed)
            {
                value["count"] = (double)count;
                value["audible"] = (double)audible;
                value["volume"] = sum;
                value["max_volume"] = max;
                value["loudest"] = loudest;
            }
            if (placed && !blind)
            {
                value["started"] = (double)started;
                value["started_audible"] = (double)startedAudible;
                value["starts"] = new List<object>(starts);
                value["starts_total"] = (double)named;
            }
            sample["value"] = value;
            started = startedAudible = named = 0;
            blind = false;
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
    /// PlayClipAtPoint's own source), or a playing one whose clip went back to its beginning (played again while it
    /// plays; a looping clip that comes round at its end is no start) or was changed for another. A source that goes on where it stood
    /// (unpaused, AudioListener.pause lifted) starts nothing. A start begins in the frame it is seen (what it is on,
    /// where, how loud at the listener: all as they are then) and is told once its name is settled: its source's clip
    /// when that clip is what plays (its position in the clip moved), within 5 frames; else it has no name the probe
    /// can tell (a PlayOneShot plays a clip the source doesn't show; an AudioResource that is no clip has none). A
    /// one-shot on a source that is already playing starts nothing the engine shows: not seen.</summary>
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
            public bool Named, Placed, Loud;  // Loud: 0.001 or louder at the listener in the frame it began
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

        /// <summary>The starts that began this frame (of one frame: in hierarchy order), and those told this frame, in
        /// the order they began.</summary>
        public static readonly List<Start> Begun = new List<Start>(), Told = new List<Start>();
        static readonly List<Start> rest = new List<Start>();

        /// <summary>At the play's last sample: every start still settling, told as it is now (the same list for every
        /// query of the sample).</summary>
        public static List<Start> Rest()
        {
            foreach (var s in settling)
            {
                if (s.Source != null && s.Clip != null && s.Source.clip == s.Clip && s.Source.timeSamples != s.Samples)
                {
                    s.Named = true;
                    s.Sound = s.Clip.name;
                }
                rest.Add(s);
            }
            settling.Clear();
            return rest;
        }
        static readonly Dictionary<int, Playing> playing = new Dictionary<int, Playing>();
        static readonly List<Start> settling = new List<Start>();
        static readonly List<AudioSource> fresh = new List<AudioSource>();
        static readonly List<int> gone = new List<int>();
        static int frame = -1;

        public static void Frame(Probe probe)
        {
            if (frame == Time.frameCount) return;
            frame = Time.frameCount;
            Begun.Clear();
            Told.Clear();
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
            }
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
                else if (source.clip != state.Clip) fresh.Add(source);  // another clip on a source that still sounded
                else if (samples < state.Samples && source.clip != null && !CameRound(source, state.Samples))
                    fresh.Add(source);  // played again while it plays
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
            var listener = AudioTap.Listener();
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
                Begun.Add(start);
            }
        }

        /// <summary>Whether a looping source whose position fell back from `before` only came round at its clip's end:
        /// it was within half a second of the end (a play runs at 30 frames a second, a sound in real time).</summary>
        static bool CameRound(AudioSource source, int before)
        {
            if (!source.loop) return false;
            var clip = source.clip;
            return before + clip.frequency / 2 >= clip.samples;
        }
    }
#endif
}
