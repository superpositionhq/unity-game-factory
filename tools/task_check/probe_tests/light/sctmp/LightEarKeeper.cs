using System;
using UnityEngine;

namespace ProbeTests.Lighting
{
    /// <summary>Puts a LightEarAfter behind the probe's tap on every enabled listener once the tap is there (found by its
    /// type name: tests can't see the probe's types). With -lightstray (the player started without a probe play) it
    /// adds the probe's AudioTap itself, as a game that carries the package might, then the after-ear and LightMute,
    /// and after `seconds` of real time (no probe fixes the frame rate there) logs what each ear heard and quits:
    /// "LIGHT stray tap=... before=... after=...". `seen`: how
    /// many of the probe's taps the game's own FindObjectsByType finds (the probe hides them from it).</summary>
    public sealed class LightEarKeeper : MonoBehaviour
    {
        public float seconds = 2f;
        public int seen;
        bool stray;
        float began;

        void Start()
        {
            stray = Array.IndexOf(Environment.GetCommandLineArgs(), "-lightstray") >= 0;
            if (!stray) return;
            began = Time.realtimeSinceStartup;
            var listener = FindFirstObjectByType<AudioListener>();
            var tap = Type.GetType("TaskProbe.AudioTap, TaskProbe");
            if (tap != null) listener.gameObject.AddComponent(tap);
            listener.gameObject.AddComponent<LightEarAfter>();
            listener.gameObject.AddComponent<LightMute>();
        }

        void Update()
        {
            if (stray)
            {
                if (began < 0f || Time.realtimeSinceStartup - began < seconds) return;
                began = -1f;
                var listener = FindFirstObjectByType<AudioListener>();
                var before = listener.GetComponent<LightEar>();
                var after = listener.GetComponent<LightEarAfter>();
                Debug.Log($"LIGHT stray tap={Tapped(listener.gameObject)} before={before.peak:R} after={after.peak:R} buffers={after.buffers}");
                Application.Quit(0);
                return;
            }
            foreach (var l in FindObjectsByType<AudioListener>(FindObjectsSortMode.None))
                if (l.enabled && Tapped(l.gameObject) && l.GetComponent<LightEarAfter>() == null)
                    l.gameObject.AddComponent<LightEarAfter>();
            seen = 0;
            foreach (var b in FindObjectsByType<MonoBehaviour>(FindObjectsSortMode.None))
                if (b != null && b.GetType().Name == "AudioTap") seen++;
        }

        static bool Tapped(GameObject go)
        {
            foreach (var c in go.GetComponents<Component>())
                if (c != null && c.GetType().Name == "AudioTap") return true;
            return false;
        }
    }
}
