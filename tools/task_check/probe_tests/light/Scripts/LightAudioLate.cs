using UnityEngine;

namespace ProbeTests.Lighting
{
    /// <summary>AudioLab2's events, by its own frames (the scene is loaded at 17.5 s of the play, so frame n is about
    /// 17.53 + n / 30 s): a source played, then given another clip and played again while the first still sounds; a
    /// one-shot on a source without a clip; and a one-shot four frames before the play's last sample.</summary>
    public sealed class LightAudioLate : MonoBehaviour
    {
        public AudioSource takes, shots, last;
        public AudioClip second, shot;
        int frames;

        void Update()
        {
            switch (++frames)
            {
                case 80: takes.Play(); break;                 // 20.2 s
                case 86:                                      // 20.4 s: another take on the source that still sounds
                    takes.clip = second;
                    takes.Play();
                    break;
                case 92: shots.PlayOneShot(shot); break;      // 20.6 s
                case 114: last.PlayOneShot(shot); break;      // 21.33 s: its name is still unsettled when the play ends
            }
        }
    }
}
