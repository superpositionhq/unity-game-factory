using UnityEngine;

namespace ProbeTests.Core
{
    /// <summary>Moves its object 1 m along x every second of game time: its x is the game's clock.</summary>
    public sealed class CoreMover : MonoBehaviour
    {
        void Update()
        {
            transform.position += Vector3.right * Time.deltaTime;
        }
    }
}
