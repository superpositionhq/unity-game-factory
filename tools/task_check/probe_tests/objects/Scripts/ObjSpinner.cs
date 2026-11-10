using UnityEngine;

namespace ProbeTests.Objects
{
    // Turns about its own up axis at degreesPerSecond of game time.
    public class ObjSpinner : MonoBehaviour
    {
        public float degreesPerSecond = 180f;

        void Update() { transform.Rotate(0f, degreesPerSecond * Time.deltaTime, 0f, Space.Self); }
    }
}
