// GradeLab: the player stands still until `startAt`, then walks +z at `speed` m/s into the local volume.
using UnityEngine;

namespace LightTests
{
    public sealed class GradeMover : MonoBehaviour
    {
        public float startAt = 6f, speed = 2f;
        Vector3 origin;

        void Start()
        {
            PlayClock.Reset();
            origin = transform.position;
        }

        void Update()
        {
            var t = PlayClock.T;
            transform.position = origin + Vector3.forward * (speed * Mathf.Max(0f, t - startAt));
        }
    }
}
