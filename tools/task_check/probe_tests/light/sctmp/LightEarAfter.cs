using UnityEngine;

namespace ProbeTests.Lighting
{
    /// <summary>On a listener's object, added after the probe's tap (LightEarKeeper): what leaves the tap, the sound the
    /// machine would play (the loudest sample since it was added, how many buffers came through).</summary>
    public sealed class LightEarAfter : MonoBehaviour
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
