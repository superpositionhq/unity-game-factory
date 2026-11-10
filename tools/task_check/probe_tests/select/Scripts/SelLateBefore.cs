using System;
using UnityEngine;

namespace ProbeTests.Select
{
    /// <summary>Runs just before the probe's late half (ProbeLate, order 32000): notes the time and the managed heap.</summary>
    [DefaultExecutionOrder(31999)]
    public sealed class SelLateBefore : MonoBehaviour
    {
        public static double Started;
        public static long Heap;

        void LateUpdate()
        {
            Heap = GC.GetTotalMemory(false);
            Started = Time.realtimeSinceStartupAsDouble;
        }
    }
}
