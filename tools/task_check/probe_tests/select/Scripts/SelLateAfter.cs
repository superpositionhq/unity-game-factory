using System;
using UnityEngine;

namespace ProbeTests.Select
{
    /// <summary>Runs just after the probe's late half: how long it took (ms) every frame, summed (`totalMs`), the
    /// longest (`worstMs`), and how much the managed heap grew meanwhile (`allocKb`, summed; a collection in between
    /// hides a frame's).</summary>
    [DefaultExecutionOrder(32001)]
    public sealed class SelLateAfter : MonoBehaviour
    {
        public double totalMs, worstMs, allocKb;
        public int frames;

        void LateUpdate()
        {
            var ms = (Time.realtimeSinceStartupAsDouble - SelLateBefore.Started) * 1000.0;
            var grew = GC.GetTotalMemory(false) - SelLateBefore.Heap;
            frames++;
            totalMs += ms;
            if (ms > worstMs) worstMs = ms;
            if (grew > 0) allocKb += grew / 1024.0;
        }
    }
}
