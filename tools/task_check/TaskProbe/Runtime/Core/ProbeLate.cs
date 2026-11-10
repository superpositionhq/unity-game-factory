// The probe's late half: after every script's LateUpdate (the camera has moved), it puts a held player back, takes the
// samples and ends the play (Probe.Late). Its own file: Unity keeps a MonoBehaviour's execution order with its script.
using UnityEngine;

namespace TaskProbe
{
    [DefaultExecutionOrder(32000)]
    [AddComponentMenu("")]
    public sealed class ProbeLate : MonoBehaviour
    {
        void LateUpdate()
        {
            if (Probe.Active != null) Probe.Active.Late();
        }
    }
}
