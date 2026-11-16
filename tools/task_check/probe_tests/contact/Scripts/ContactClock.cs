using UnityEngine;

namespace ProbeTests.Contact
{
    /// <summary>Slows the game's time to a quarter for three frames (its 100th to its 102nd) and stops it for two (its
    /// 130th and 131st): a hit stop of the whole game, and a pause.</summary>
    public sealed class ContactClock : MonoBehaviour
    {
        int frame;

        void Update()
        {
            Time.timeScale = frame >= 100 && frame <= 102 ? 0.25f : frame == 130 || frame == 131 ? 0f : 1f;
            frame++;
        }

        void OnDestroy() => Time.timeScale = 1f;
    }
}
