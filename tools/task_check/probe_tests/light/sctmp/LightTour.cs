using UnityEngine;

namespace ProbeTests.Lighting
{
    /// <summary>Moves its camera from station to station by the play's clock: station k (1-based) from 0.5 s before
    /// play time k to 0.5 s after, so the samples at whole seconds see one station each. Frames, not time, so every
    /// play moves it in the same frames.</summary>
    public sealed class LightTour : MonoBehaviour
    {
        public Vector3[] at;
        public Vector3[] euler;
        int frames;

        void Update()
        {
            frames++;
            var k = Mathf.Clamp((frames + 15) / 30, 1, at.Length);
            transform.SetPositionAndRotation(at[k - 1], Quaternion.Euler(euler[k - 1]));
        }
    }
}
