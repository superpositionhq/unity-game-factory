using UnityEngine;
using UnityEngine.SceneManagement;

namespace ProbeTests.Lighting
{
    /// <summary>AudioLab's events, by frame (play time x 30). A clip that ends is 0.3 s long and starts at k.4 s: it is
    /// playing at k.5 s and over at k+1 s, with 0.3 s to spare for the mix's own delay and the real-time pacing's drift
    /// (measured: a clip of 0.55 s still played at k+1 s in one play of two). Menu ignores AudioListener.pause, set here:
    /// an AudioSource doesn't save it.</summary>
    public sealed class LightAudioDirector : MonoBehaviour
    {
        public AudioSource late, menu, pausable, ender, shooter, shooterClip, near;
        public AudioClip shot, point;
        public AudioListener first, second;
        public string next;
        int frames;

        void Awake()
        {
            menu.ignoreListenerPause = true;
        }

        void Update()
        {
            switch (++frames)
            {
                case 72: ender.Play(); break;                                     // 2.4 s
                case 120: late.Play(); break;                                     // 4 s
                case 150: pausable.Pause(); break;                                // 5 s
                case 192: shooter.PlayOneShot(shot); break;                       // 6.4 s: a source without a clip
                case 222: shooterClip.PlayOneShot(shot); break;                   // 7.4 s: a source with a clip of its own
                case 252: AudioSource.PlayClipAtPoint(point, new Vector3(0f, 0f, 3f)); break;  // 8.4 s
                case 270: AudioListener.pause = true; break;                      // 9 s
                case 315: AudioListener.pause = false; break;                     // 10.5 s
                case 330: Time.timeScale = 0f; break;                             // 11 s
                case 375: Time.timeScale = 1f; break;                             // 12.5 s
                case 390: second.enabled = true; break;                           // 13 s: two listeners on
                case 435:                                                         // 14.5 s: the second alone
                    first.enabled = false;
                    near.Play();
                    break;
                case 480: second.enabled = false; break;                          // 16 s: no listener
                case 525: SceneManager.LoadScene(next); break;                    // 17.5 s
            }
        }
    }
}
