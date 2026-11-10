using UnityEngine;

namespace ProbeTests.Core
{
    /// <summary>Moves its object 1 m along x every second of game time: its x is the game's clock. It also keeps, since
    /// its first Update, how far Time.time, Time.unscaledTime and the wall clock (Time.realtimeSinceStartup) went.</summary>
    public sealed class CoreMover : MonoBehaviour
    {
        public float game, unscaled, real;
        float game0, unscaled0, real0;
        bool began;

        void Update()
        {
            if (!began)
            {
                began = true;
                game0 = Time.time;
                unscaled0 = Time.unscaledTime;
                real0 = Time.realtimeSinceStartup;
            }
            game = Time.time - game0;
            unscaled = Time.unscaledTime - unscaled0;
            real = Time.realtimeSinceStartup - real0;
            transform.position += Vector3.right * Time.deltaTime;
        }
    }
}
