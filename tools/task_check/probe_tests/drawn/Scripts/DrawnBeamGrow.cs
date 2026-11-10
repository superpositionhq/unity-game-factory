using UnityEngine;

namespace ProbeTests.Drawn
{
    /// <summary>Grows its x scale (a beam drawn from its pivot) from Start to End metres over Seconds, from Delay on.</summary>
    public sealed class DrawnBeamGrow : MonoBehaviour
    {
        public float Start = 0.5f, End = 9f, Seconds = 10f, Delay = 2f;

        void Update()
        {
            var k = Mathf.Clamp01((Time.timeSinceLevelLoad - Delay) / Seconds);
            var s = transform.localScale;
            s.x = Mathf.Lerp(Start, End, k);
            transform.localScale = s;
        }
    }
}
