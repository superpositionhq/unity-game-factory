using System;
using UnityEngine;

namespace ProbeTests.Lighting
{
    /// <summary>Last in a listener's filter chain in the stray run (no probe play, so no tap silences it): the test's own
    /// silence, so the machine plays nothing.</summary>
    public sealed class LightMute : MonoBehaviour
    {
        void OnAudioFilterRead(float[] data, int channels)
        {
            Array.Clear(data, 0, data.Length);
        }
    }
}
