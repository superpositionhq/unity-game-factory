using UnityEngine;

namespace ProbeTests.Drawn
{
    /// <summary>Activates Target (inactive at the start) at a play time.</summary>
    public sealed class DrawnActivateAt : MonoBehaviour
    {
        public float Seconds = 5f;
        public GameObject Target;

        void Update()
        {
            if (Target != null && !Target.activeSelf && Time.timeSinceLevelLoad >= Seconds) Target.SetActive(true);
        }
    }
}
