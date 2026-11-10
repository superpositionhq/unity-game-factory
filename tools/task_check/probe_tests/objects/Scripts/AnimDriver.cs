using UnityEngine;

// Drives the Animator's parameters: Speed = play time, Open from `openAt` s, Count = whole seconds.
public class AnimDriver : MonoBehaviour
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
