// AudioLab: starts a source mid-play, fires a PlayOneShot and a PlayClipAtPoint, pauses the listener, stops time, goes
// silent, moves the listener to a second camera, then loads AudioLab2. Logs what Unity reports at each step.
using UnityEngine;
using UnityEngine.SceneManagement;

namespace LightTests
{
    public sealed class AudioDirector : MonoBehaviour
    {
        public AudioSource late, shooter, loop3D;
        public AudioClip shot, point;
        public AudioListener mainListener, secondListener;
        public string nextScene = "Assets/Scenes/LightTests/AudioLab2.unity";
        int step;
        float nextLog;

        void Start()
        {
            PlayClock.Reset();
            if (secondListener != null) secondListener.enabled = false;
        }

        void Update()
        {
            var t = PlayClock.T;
            if (step == 0 && t >= 4f) { step++; late.Play(); Log("late source started"); }
            if (step == 1 && t >= 6f)
            {
                step++;
                shooter.PlayOneShot(shot, 1f);
                Log($"PlayOneShot: shooter.isPlaying={shooter.isPlaying} clip={(shooter.clip != null ? shooter.clip.name : "null")}");
            }
            if (step == 2 && t >= 7.5f)
            {
                step++;
                AudioSource.PlayClipAtPoint(point, new Vector3(0f, 0f, 3f), 1f);
                var made = GameObject.Find("One shot audio");
                var src = made != null ? made.GetComponent<AudioSource>() : null;
                Log($"PlayClipAtPoint: object={(made != null ? made.name : "none")} isPlaying={(src != null && src.isPlaying)} clip={(src != null && src.clip != null ? src.clip.name : "null")} blend={(src != null ? src.spatialBlend : -1f)} rolloff={(src != null ? src.rolloffMode.ToString() : "")} min={(src != null ? src.minDistance : -1f)} max={(src != null ? src.maxDistance : -1f)}");
            }
            if (step == 3 && t >= 9f) { step++; AudioListener.pause = true; Log($"AudioListener.pause=true: loop3D.isPlaying={loop3D.isPlaying}"); }
            if (step == 4 && t >= 10.5f) { step++; AudioListener.pause = false; Log($"AudioListener.pause=false: loop3D.isPlaying={loop3D.isPlaying}"); }
            if (step == 5 && t >= 11f) { step++; Time.timeScale = 0f; Log($"timeScale=0: loop3D.isPlaying={loop3D.isPlaying}"); }
            if (step == 6 && t >= 12.5f) { step++; Time.timeScale = 1f; Log($"timeScale=1: loop3D.isPlaying={loop3D.isPlaying}"); }
            if (step == 7 && t >= 13f)
            {
                step++;
                foreach (var s in FindObjectsByType<AudioSource>(FindObjectsSortMode.None)) s.Stop();
                Log("every source stopped");
            }
            if (step == 8 && t >= 14.5f)
            {
                step++;
                mainListener.enabled = false;
                secondListener.enabled = true;
                foreach (var s in secondListener.GetComponentsInChildren<AudioSource>()) s.Play();
                Log("listener moved to " + secondListener.name);
            }
            if (step == 9 && t >= 17f) { step++; Log("loading " + nextScene); SceneManager.LoadScene(nextScene); }
            if (t >= nextLog)
            {
                nextLog += 0.5f;
                Log($"tick: shooter.isPlaying={shooter.isPlaying} loop3D.isPlaying={loop3D.isPlaying} taps={TapLog.Taps()}");
            }
        }

        static void Log(string what) => Debug.Log($"AT: t={PlayClock.T:F2} {what}");
    }
}
