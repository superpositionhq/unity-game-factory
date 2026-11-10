using UnityEngine;

namespace ProbeTests.Drawn
{
    /// <summary>Moves its object round a horizontal circle (Radius m, one turn every Seconds) by game time: a trail behind it.</summary>
    public sealed class DrawnCircle : MonoBehaviour
    {
        public float Radius = 0.5f, Seconds = 1f;
        Vector3 centre;

        void Awake() => centre = transform.position;

        void Update()
        {
            var a = Time.timeSinceLevelLoad / Seconds * Mathf.PI * 2f;
            transform.position = centre + new Vector3(Mathf.Cos(a), 0f, Mathf.Sin(a)) * Radius;
        }
    }
}
