using UnityEngine;

namespace ProbeTests.Lighting
{
    /// <summary>On a listener's object, placed in the scene and so ahead of the probe's tap in its filter chain: the
    /// mix as it reaches the tap (the loudest sample since the play began, how many buffers came through). `tapped`:
    /// whether the probe's tap is on the object, enabled, when asked (found by its type name: tests can't see the probe's
    /// types, and the probe's own readers leave its tap out).</summary>
    public sealed class LightEar : MonoBehaviour
    {
        public float peak;
        public int buffers;

        public int tapped
        {
            get
            {
                foreach (var b in GetComponents<Behaviour>())
                    if (b != null && b.enabled && b.GetType().Name == "AudioTap") return 1;
                return 0;
            }
        }

        void OnAudioFilterRead(float[] data, int channels)
        {
            var top = 0f;
            for (var i = 0; i < data.Length; i++)
            {
                var a = data[i] < 0f ? -data[i] : data[i];
                if (a > top) top = a;
            }
            if (top > peak) peak = top;
            buffers++;
        }
    }
}
