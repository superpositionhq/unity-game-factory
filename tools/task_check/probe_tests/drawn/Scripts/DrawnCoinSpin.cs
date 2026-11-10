using UnityEngine;

namespace ProbeTests.Drawn
{
    /// <summary>A coin as the sample game spins it: 180 degrees a second about the vertical, bobbing 0.12 m.</summary>
    public sealed class DrawnCoinSpin : MonoBehaviour
    {
        public float spinDegreesPerSecond = 180f;
        public float bobHeight = 0.12f;
        public float bobSpeed = 2f;
        Vector3 home;

        void Start() => home = transform.position;

        void Update()
        {
            transform.Rotate(0f, spinDegreesPerSecond * Time.deltaTime, 0f, Space.World);
            transform.position = home + Vector3.up * (Mathf.Sin(Time.timeSinceLevelLoad * bobSpeed) * bobHeight);
        }
    }
}
