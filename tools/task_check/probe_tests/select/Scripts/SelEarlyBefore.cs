using UnityEngine;

namespace ProbeTests.Select
{
    /// <summary>Runs just before the probe's own Update (order -32000): notes the time.</summary>
    [DefaultExecutionOrder(-32001)]
    public sealed class SelEarlyBefore : MonoBehaviour
    {
        public static double Started;

        void Update()
        {
            Started = Time.realtimeSinceStartupAsDouble;
        }
    }
}
