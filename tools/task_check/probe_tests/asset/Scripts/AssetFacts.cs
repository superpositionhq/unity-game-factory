// The player the checker builds, as the game sees it when its scene wakes: the company name, whether a splash screen
// is showing, the scripting backend, a development build, the window; and a property no code calls (only the probe, by
// reflection), which code stripping must leave in.
using System;
using UnityEngine;
using UnityEngine.Rendering;

namespace ProbeTests.Asset
{
    public class AssetFacts : MonoBehaviour
    {
        public string company, backend, mode;
        public bool splashDone, development;
        public int width, height;

        public int Unread => 42;

        void Awake()
        {
            company = Application.companyName;
            splashDone = SplashScreen.isFinished;
            backend = Type.GetType("Mono.Runtime") != null ? "mono" : "il2cpp";
            development = Debug.isDebugBuild;
            width = Screen.width;
            height = Screen.height;
            mode = Screen.fullScreenMode.ToString();
            Debug.Log("ASSET facts " + company);
        }
    }
}
