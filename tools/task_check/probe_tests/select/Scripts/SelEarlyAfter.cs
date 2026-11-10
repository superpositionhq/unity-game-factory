using UnityEngine;

namespace ProbeTests.Select
{
    /// <summary>Runs just after the probe's own Update (where every query's per-frame work is done): how long it took
    /// (ms) every frame, summed (`totalMs`), and the longest (`worstMs`).</summary>
    [DefaultExecutionOrder(-31999)]
    public sealed class SelEarlyAfter : MonoBehaviour
    {
        public double totalMs, worstMs;
        public int frames;

        void Update()
        {
            var ms = (Time.realtimeSinceStartupAsDouble - SelEarlyBefore.Started) * 1000.0;
            frames++;
            totalMs += ms;
            if (ms > worstMs) worstMs = ms;
        }
    }
}
