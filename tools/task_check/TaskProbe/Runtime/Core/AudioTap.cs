// What the listener hears, measured and then silenced. A filter on an AudioListener's object receives the final mix of
// every source (mixers and effects applied); the tap sums its level for the `audio` measure and then zeroes the buffer,
// so no play is ever heard on the machine (the original's plays run with -nosound, or -muteaudio when they measure
// audio). Only in a probe play: Follow, which only the probe calls, arms every tap; a tap anywhere else (the package
// copied into a game, a component added by code) lets the sound through untouched.
#if TASKPROBE_AUDIO
using System;
using System.Collections.Generic;
using UnityEngine;

namespace TaskProbe
{
    [AddComponentMenu("")]
    public sealed class AudioTap : MonoBehaviour
    {
        static readonly object Gate = new object();
        static double sumSquares;
        static long samples, buffers;
        static float peak;
        static volatile bool armed;  // a probe play runs: set on the main thread, read on the audio thread (which can't ask Unity objects)
        static volatile int tapped;  // how many enabled listeners carry a tap (Follow)
        static readonly List<AudioListener> listeners = new List<AudioListener>();

        /// <summary>The mix's level since the last call: its RMS over every channel and its peak (linear, 1 full scale);
        /// false when no audio buffer arrived (no tap yet, no listener, no audio device).</summary>
        public static bool Level(out double rms, out double top)
        {
            lock (Gate)
            {
                rms = samples > 0 ? Math.Sqrt(sumSquares / samples) : 0.0;
                top = peak;
                var any = buffers > 0;
                sumSquares = 0.0;
                samples = 0;
                buffers = 0;
                peak = 0f;
                return any;
            }
        }

        /// <summary>The listener the player hears through: the first enabled AudioListener on an active object, in
        /// hierarchy order.</summary>
        public static AudioListener Listener()
        {
            listeners.Clear();
            foreach (var l in FindObjectsByType<AudioListener>(FindObjectsInactive.Exclude, FindObjectsSortMode.None))
                if (l.enabled) listeners.Add(l);
            Find.SortByHierarchy(listeners);
            return listeners.Count > 0 ? listeners[0] : null;
        }

        /// <summary>In a probe play: a tap on every enabled listener, switched back on if the game switched it off with the
        /// rest of its object's behaviours. With two listeners on (Unity warns) the filters of both run one after the
        /// other on the one mix: the first tap measures and silences it, the second gets silence. Hidden from the game's
        /// FindObjectsByType (DontSave); a game reading its listener object's components with GetComponents sees it.</summary>
        public static void Follow()
        {
            armed = Probe.Active != null;
            if (!armed) return;
            listeners.Clear();
            foreach (var l in FindObjectsByType<AudioListener>(FindObjectsInactive.Exclude, FindObjectsSortMode.None))
                if (l.enabled) listeners.Add(l);
            tapped = listeners.Count;  // before a second tap runs: none of its buffers count as the mix's silence
            foreach (var l in listeners)
            {
                var tap = l.GetComponent<AudioTap>();
                if (tap == null)
                {
                    tap = l.gameObject.AddComponent<AudioTap>();
                    tap.hideFlags = HideFlags.HideInInspector | HideFlags.DontSave;
                }
                tap.enabled = true;
            }
        }

        // the audio thread
        void OnAudioFilterRead(float[] data, int channels)
        {
            if (!armed) return;  // not a probe play: the game's sound is its own
            double sum = 0.0;
            var top = 0f;
            for (var i = 0; i < data.Length; i++)
            {
                var v = data[i];
                sum += v * v;
                var a = v < 0f ? -v : v;
                if (a > top) top = a;
            }
            lock (Gate)
            {
                buffers++;
                // with two taps on the one mix, the second gets the silence the first left: a silent buffer is then
                // no part of the level (measured: counted, it brought the level down to 1/sqrt 2 of the mix's)
                if (sum > 0.0 || tapped < 2)
                {
                    sumSquares += sum;
                    samples += data.Length;
                    if (top > peak) peak = top;
                }
            }
            // silenced: no play is ever heard on the machine
            Array.Clear(data, 0, data.Length);
        }
    }
}
#endif
