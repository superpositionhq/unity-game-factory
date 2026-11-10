using UnityEngine;

namespace ProbeTests.Lighting
{
    /// <summary>On a listener's object, placed in the scene and so ahead of the probe's tap in its filter chain: the
    /// mix as it reaches the tap (the loudest sample since the play began, how many buffers came through). Only the
    /// listener Unity mixes through gets buffers.</summary>
    public sealed class LightEar : MonoBehaviour
    {
        public float peak;
        public int buffers;

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
