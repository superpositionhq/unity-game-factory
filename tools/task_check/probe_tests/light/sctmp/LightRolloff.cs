using UnityEngine;
using UnityEngine.Audio;

namespace ProbeTests.Lighting
{
    /// <summary>AudioRolloff: one tone straight ahead of the listener, 2 s (60 frames) at each step: logarithmic, linear
    /// and custom rolloff at several distances, a half-2D blend, then 2D, direct, through the -20 dB mixer group, and
    /// with AudioListener.volume at 0.5.</summary>
    public sealed class LightRolloff : MonoBehaviour
    {
        public AudioSource source;
        public AudioMixerGroup quiet;
        public AnimationCurve custom;
        int frames, step = -1;

        static readonly (AudioRolloffMode mode, float z, float blend, bool mixer)[] Steps =
        {
            (AudioRolloffMode.Logarithmic, 1f, 1f, false), (AudioRolloffMode.Logarithmic, 2f, 1f, false),
            (AudioRolloffMode.Logarithmic, 4f, 1f, false), (AudioRolloffMode.Logarithmic, 8f, 1f, false),
            (AudioRolloffMode.Logarithmic, 80f, 1f, false),
            (AudioRolloffMode.Linear, 0.5f, 1f, false), (AudioRolloffMode.Linear, 5.75f, 1f, false),
            (AudioRolloffMode.Linear, 10.5f, 1f, false), (AudioRolloffMode.Linear, 15.25f, 1f, false),
            (AudioRolloffMode.Custom, 0.01f, 1f, false), (AudioRolloffMode.Custom, 8f, 1f, false), (AudioRolloffMode.Custom, 14f, 1f, false),
            (AudioRolloffMode.Logarithmic, 4f, 0.5f, false),
            (AudioRolloffMode.Logarithmic, 4f, 0f, false), (AudioRolloffMode.Logarithmic, 4f, 0f, true),
            (AudioRolloffMode.Logarithmic, 4f, 0f, false),
        };

        void Update()
        {
            var want = Mathf.Min(frames++ / 60, Steps.Length - 1);
            if (want == step) return;
            step = want;
            var s = Steps[step];
            source.rolloffMode = s.mode;
            source.minDistance = 1f;
            source.maxDistance = s.mode == AudioRolloffMode.Logarithmic ? 50f : 20f;
            if (s.mode == AudioRolloffMode.Custom) source.SetCustomCurve(AudioSourceCurveType.CustomRolloff, custom);
            source.spatialBlend = s.blend;
            source.outputAudioMixerGroup = s.mixer ? quiet : null;
            source.transform.position = new Vector3(0f, 0f, s.z);
            AudioListener.volume = step == Steps.Length - 1 ? 0.5f : 1f;
        }
    }
}
