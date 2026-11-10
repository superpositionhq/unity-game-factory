using UnityEngine;

namespace DrawnTest
{
    public sealed class Spinner : MonoBehaviour
    {
        public Vector3 DegreesPerSecond = new Vector3(0, 90, 0);
        void Update() => transform.Rotate(DegreesPerSecond * Time.deltaTime, Space.Self);
    }
}
