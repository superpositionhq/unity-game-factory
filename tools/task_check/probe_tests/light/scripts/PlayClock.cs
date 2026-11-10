// The play's clock as the probe counts it: frames since this scene started, at the probe's fixed 30 fps. It runs on
// whether or not the game pauses itself (timeScale 0, AudioListener.pause).
using UnityEngine;

namespace LightTests
{
    public static class PlayClock
    {
        static int start = -1;
        public static void Reset() { start = Time.frameCount; }
        public static float T => start < 0 ? 0f : (Time.frameCount - start) / 30f;
    }
}
