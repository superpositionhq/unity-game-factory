using System.IO;
using UnityEngine;
using UnityEngine.SceneManagement;

namespace ProbeTests.Core
{
    /// <summary>What a game may do in mid-play, by the play's arguments: quit (-corequit), refuse to quit
    /// (-corerefuse), load a scene after one second (-coreload sync | async | parked), write saved data (-coresave),
    /// destroy every object it finds but the hero and the camera (-corewipe), set the frame rate and vertical sync
    /// its own way, in Start and again in every Update (-coresettings). It says in the log what saved data it found
    /// when it started, and keeps the vertical sync count and the capture and target frame rates each Update
    /// found. It writes its saved file as most games do, without making the folder first.</summary>
    public sealed class CoreDirector : MonoBehaviour
    {
        const string Stage = "Assets/ProbeTests/core/Made/Stage.unity";
        public int vsync = -1, capture = -1, target = -2;
        bool own;
        int updates;

        void Start()
        {
            var file = Path.Combine(Application.persistentDataPath, "core_token.txt");
            Debug.Log("CORE saves prefs=" + PlayerPrefs.HasKey("core_token") + " file=" + File.Exists(file)
                      + " company=" + Application.companyName + " path=" + Application.persistentDataPath);
            if (CoreArgs.Has("-coresave"))
            {
                PlayerPrefs.SetInt("core_token", 7);
                PlayerPrefs.Save();
                File.WriteAllText(file, "7");
                Debug.Log("CORE wrote saves");
            }
            if (CoreArgs.Has("-corerefuse")) Application.wantsToQuit += () => false;
            own = CoreArgs.Has("-coresettings");
            if (own) Settings();
        }

        static void Settings()
        {
            QualitySettings.vSyncCount = 1;
            Application.targetFrameRate = 5;
            Time.captureFramerate = 60;
        }

        void Update()
        {
            vsync = QualitySettings.vSyncCount;
            capture = Time.captureFramerate;
            target = Application.targetFrameRate;
            if (own) Settings();
            if (++updates == 45 && CoreArgs.Has("-corelast")) Debug.Log("CORE the last frame of a 1 s play");
            if (updates != 30) return;  // one second of game time
            if (CoreArgs.Has("-corewipe"))
            {
                var probe = false;
                foreach (var found in FindObjectsByType<GameObject>(FindObjectsInactive.Include, FindObjectsSortMode.None))
                {
                    probe |= found.name == "TaskProbe";
                    if (found != gameObject && found.name != "Hero" && found.name != "Main Camera") Destroy(found);
                }
                // a search for every script: the probe's are on an object the game's searches leave out
                var scripts = false;
                foreach (var found in FindObjectsByType<MonoBehaviour>(FindObjectsInactive.Include, FindObjectsSortMode.None))
                    scripts |= found.GetType().Namespace == "TaskProbe";
                Debug.Log("CORE wipe found the probe=" + probe + " scripts=" + scripts);
            }
            if (CoreArgs.Has("-corequit")) Application.Quit();
            var load = CoreArgs.After("-coreload");
            if (load == "sync") SceneManager.LoadScene(Stage);
            else if (load == "async") SceneManager.LoadSceneAsync(Stage, LoadSceneMode.Additive);
            else if (load == "parked") SceneManager.LoadSceneAsync(Stage, LoadSceneMode.Additive).allowSceneActivation = false;
        }
    }
}
