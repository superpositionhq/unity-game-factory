using System;
using UnityEngine;
using UnityEngine.SceneManagement;

namespace ProbeTests.Lighting
{
    /// <summary>The stray run (the built player started by a check with -lightstray and no -taskProbe): it opens the
    /// Stray scene, whose LightEarKeeper adds the probe's AudioTap outside a probe play. Every other start of the player
    /// is left alone.</summary>
    public static class LightStrayBoot
    {
        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.BeforeSceneLoad)]
        static void Boot()
        {
            if (Array.IndexOf(Environment.GetCommandLineArgs(), "-lightstray") < 0) return;
            SceneManager.LoadScene("Assets/ProbeTests/light/Made/Stray.unity");
        }
    }
}
