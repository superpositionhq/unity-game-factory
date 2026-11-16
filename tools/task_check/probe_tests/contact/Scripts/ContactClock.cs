using System;
using System.Collections;
using UnityEngine;

namespace ProbeTests.Contact
{
    /// <summary>Slows the game's time to a quarter for three frames (its 100th to its 102nd) and stops it for two (its
    /// 130th and 131st): a hit stop of the whole game, and a pause. Started with -contactreal it stops the game's time
    /// once instead, at its 120th frame, for 0.1 s of real time: a hit stop as games time one, on the only clock that
    /// runs while the game's time stands still.</summary>
    public sealed class ContactClock : MonoBehaviour
    {
        bool real;
        int frame;

        void Awake() => real = Array.IndexOf(Environment.GetCommandLineArgs(), "-contactreal") >= 0;

        void Update()
        {
            if (real)
            {
                if (frame == 120) StartCoroutine(Stop());
            }
            else Time.timeScale = frame >= 100 && frame <= 102 ? 0.25f : frame == 130 || frame == 131 ? 0f : 1f;
            frame++;
        }

        IEnumerator Stop()
        {
            Time.timeScale = 0f;
            yield return new WaitForSecondsRealtime(0.1f);
            Time.timeScale = 1f;
        }

        void OnDestroy() => Time.timeScale = 1f;
    }
}
