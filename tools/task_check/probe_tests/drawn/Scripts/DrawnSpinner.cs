using UnityEngine;

namespace ProbeTests.Drawn
{
    /// <summary>Turns its object about its own axes by game time.</summary>
    public sealed class DrawnSpinner : MonoBehaviour
    {
        public Vector3 DegreesPerSecond = new Vector3(0, 90, 0);
        void Update() => transform.Rotate(DegreesPerSecond * Time.deltaTime, Space.Self);
    }
}
