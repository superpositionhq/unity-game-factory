using UnityEngine;

namespace DrawnTest
{
    /// <summary>Grows a LineRenderer along +x from its position.</summary>
    public sealed class LineGrow : MonoBehaviour
    {
        public float Start = 0.5f, End = 9f, Seconds = 10f, Delay = 2f;
        LineRenderer line;
        void Awake() => line = GetComponent<LineRenderer>();
        void Update()
        {
            var k = Mathf.Clamp01((Time.timeSinceLevelLoad - Delay) / Seconds);
            line.positionCount = 2;
            line.SetPosition(0, transform.position);
            line.SetPosition(1, transform.position + Vector3.right * Mathf.Lerp(Start, End, k));
        }
    }
}
