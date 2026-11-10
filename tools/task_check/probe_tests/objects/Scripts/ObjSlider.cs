using UnityEngine;

namespace ProbeTests.Objects
{
    // Slides along x at `speed` m/s of game time by its transform alone: it has no velocity of its own to read.
    public class ObjSlider : MonoBehaviour
    {
        public float speed = 2f;

        void Update() { transform.position += new Vector3(speed * Time.deltaTime, 0f, 0f); }
    }
}
