// Logs which listeners carry the probe's tap, every second (AudioLab2, after the scene load).
using UnityEngine;

namespace LightTests
{
    public sealed class TapLog : MonoBehaviour
    {
        float next;

        void Start() { PlayClock.Reset(); }

        void Update()
        {
            if (PlayClock.T < next) return;
            next += 1f;
            Debug.Log($"AT2: t={PlayClock.T:F2} taps {Taps()}");
        }

        /// <summary>Every listener, enabled or not, and whether it carries the probe's tap (found by type name).</summary>
        public static string Taps()
        {
            var s = "";
            foreach (var l in FindObjectsByType<AudioListener>(FindObjectsInactive.Include, FindObjectsSortMode.InstanceID))
            {
                var tapped = false;
                foreach (var c in l.GetComponents<Component>())
                    if (c != null && c.GetType().Name == "AudioTap") tapped = true;
                s += $"[{l.name} enabled={l.enabled} tap={tapped}]";
            }
            return s;
        }
    }
}
