// AutoPlay's tap on the AudioListener's object: a filter there receives the final mix of every source on the audio
// thread (AutoPlayAudio stores it). It changes nothing the player hears, unless the run was started with
// -autoplayMute.
#if AUTOPLAY_AUDIO
using UnityEngine;

[AddComponentMenu("")]
internal sealed class AutoPlayAudioTap : MonoBehaviour
{
    internal volatile int Id;

    void OnAudioFilterRead(float[] data, int channels) => AutoPlayAudio.OnBuffer(Id, data, channels);
}
#endif
