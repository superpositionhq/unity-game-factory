// What the listener hears, measured and then silenced. A filter on the AudioListener's object receives the final mix
// of every source (mixers and effects applied); the tap sums its level for the `audio` measure and then zeroes the
// buffer, so no play is ever heard on the machine. The probe keeps one on whichever listener is active.
#if TASKPROBE_AUDIO
using System;
using UnityEngine;

namespace TaskProbe
{
    [AddComponentMenu("")]
    public sealed class AudioTap : MonoBehaviour
    {
        static readonly object Gate = new object();
        static double sumSquares;
        static long samples;
        static float peak;

        /// <summary>The mix's level since the last call: its RMS and peak (linear, 0-1 for full scale); false when no
        /// audio buffer arrived (no listener, no audio device).</summary>
        public static bool Level(out double rms, out double top)
        {
            lock (Gate)
            {
                rms = samples > 0 ? Math.Sqrt(sumSquares / samples) : 0.0;
                top = peak;
                var any = samples > 0;
                sumSquares = 0.0;
                samples = 0;
                peak = 0f;
                return any;
            }
        }

        /// <summary>A tap on the listener in use (the first enabled one), added when it has none.</summary>
        public static void Follow()
        {
            // the enabled one: FindFirstObjectByType also returns a disabled listener component (a game that switches
            // cameras by disabling one listener and enabling another), which hears nothing
            AudioListener listener = null;
            foreach (var l in FindObjectsByType<AudioListener>(FindObjectsInactive.Exclude, FindObjectsSortMode.InstanceID))
                if (l.enabled) { listener = l; break; }
            if (listener == null || listener.GetComponent<AudioTap>() != null) return;
            var tap = listener.gameObject.AddComponent<AudioTap>();
            tap.hideFlags = HideFlags.HideInInspector | HideFlags.DontSave;
        }

        // the audio thread
        void OnAudioFilterRead(float[] data, int channels)
        {
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
                sumSquares += sum;
                samples += data.Length;
                if (top > peak) peak = top;
            }
            Array.Clear(data, 0, data.Length);
        }
    }
}
#endif
