// AutoPlay's part of every frame after the game's scripts (execution order 32000): a row for each control held through
// the frame, the cursor freed again, and the run's files written out.
using UnityEngine;

[DefaultExecutionOrder(32000)]
[AddComponentMenu("")]
internal sealed class AutoPlayLate : MonoBehaviour
{
    void LateUpdate() => AutoPlayRun.LateUpdate();
}
