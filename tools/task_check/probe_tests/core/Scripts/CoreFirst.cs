using System.IO;
using UnityEngine;
using UnityEngine.InputSystem;

namespace ProbeTests.Core
{
    /// <summary>In the game's first scene: says in the log what it lives through (a play that names a scene asks for it
    /// before this one has woken up). With -corekeeper it leaves an object that outlives the scene. With -coreselftest
    /// (the player started without -taskProbe) it says what the probe did to the game, which must be nothing, and
    /// quits.</summary>
    public sealed class CoreFirst : MonoBehaviour
    {
        int updates;

        void Awake()
        {
            Debug.Log("CORE First Awake");
            if (CoreArgs.Has("-corekeeper")) DontDestroyOnLoad(new GameObject("CoreKeeper"));
        }

        void OnEnable() { Debug.Log("CORE First OnEnable"); }
        void Start() { Debug.Log("CORE First Start"); }
        void OnDestroy() { Debug.Log("CORE First OnDestroy"); }

        void Update()
        {
            if (updates++ == 0) Debug.Log("CORE First Update");
            if (updates != 20 || !CoreArgs.Has("-coreselftest")) return;
            try
            {
                var devices = 0;
                foreach (var device in InputSystem.devices)
                    if (device.name.StartsWith("TaskProbe")) devices++;
                Debug.Log("CORE selftest probe=" + (GameObject.Find("TaskProbe") != null) + " capture=" + Time.captureFramerate
                          + " devices=" + devices + " prefs=" + PlayerPrefs.HasKey("core_token")
                          + " file=" + File.Exists(Path.Combine(Application.persistentDataPath, "core_token.txt")));
            }
            finally { Application.Quit(); }
        }
    }
}
