// AutoPlay's part of every frame before the game's scripts (execution order -32000): the display and input rules,
// the audio tap's listener, and the run's phases (ready, go, the time limit, the result hold).
using UnityEngine;

[DefaultExecutionOrder(-32000)]
[AddComponentMenu("")]
internal sealed class AutoPlayEarly : MonoBehaviour
{
    void Update() => AutoPlayRun.EarlyUpdate();
}
