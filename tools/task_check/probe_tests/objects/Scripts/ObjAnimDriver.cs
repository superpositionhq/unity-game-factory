using UnityEngine;

namespace ProbeTests.Objects
{
    // Drives its Animator's parameters by game time: Speed = play time, Count = whole seconds, Open from `openAt` s.
    public class ObjAnimDriver : MonoBehaviour
    {
        public float openAt = 3f;
        Animator animator;

        void Start() { animator = GetComponent<Animator>(); }

        void Update()
        {
            var t = Time.timeSinceLevelLoad;
            animator.SetFloat("Speed", t);
            animator.SetInteger("Count", (int)t);
            animator.SetBool("Open", t >= openAt);
        }
    }
}
