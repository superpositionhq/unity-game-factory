// AudioRolloff: one tone straight ahead of the listener, held 2 s at each step: logarithmic, linear and custom rolloff
// at several distances, a half-2D blend, then 2D direct and through the -20 dB mixer group. The level per step against
// the probe's volume shows whether the probe's rolloff is Unity's.
using UnityEngine;
using UnityEngine.Audio;

namespace LightTests
{
    public sealed class RolloffDirector : MonoBehaviour
    {
        public AudioSource source;
        public AudioMixerGroup quiet;
        public AnimationCurve custom;
        int step = -1;

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
        };

        void Start()
        {
            PlayClock.Reset();
            source.SetCustomCurve(AudioSourceCurveType.CustomRolloff, custom);
        }

        void Update()
        {
            var want = Mathf.FloorToInt(PlayClock.T / 2f);
            if (want == step || want >= Steps.Length) return;
            step = want;
            var s = Steps[step];
            source.rolloffMode = s.mode;
            source.minDistance = 1f;
            source.maxDistance = s.mode == AudioRolloffMode.Logarithmic ? 50f : 20f;
            if (s.mode == AudioRolloffMode.Custom) source.SetCustomCurve(AudioSourceCurveType.CustomRolloff, custom);
            source.spatialBlend = s.blend;
            source.outputAudioMixerGroup = s.mixer ? quiet : null;
            source.transform.position = new Vector3(0f, 0f, s.z);
            Debug.Log($"RT: t={PlayClock.T:F2} step {step}: {s.mode} d={s.z} blend={s.blend} mixer={s.mixer}");
        }
    }
}
