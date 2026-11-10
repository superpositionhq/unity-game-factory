using UnityEngine;

namespace DrawnTest
{
    /// <summary>Activates a child (inactive at the start) at a play time.</summary>
    public sealed class ActivateAt : MonoBehaviour
    {
        public float Seconds = 5f;
        public GameObject Target;
        void Update()
        {
            if (Target != null && !Target.activeSelf && Time.timeSinceLevelLoad >= Seconds) Target.SetActive(true);
        }
    }
}
