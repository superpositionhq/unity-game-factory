using UnityEngine;

namespace ProbeTests.Contact
{
    /// <summary>Moves 1 m/s along x by game time and stands still for six frames of its own, its 60th to its 65th: a hit
    /// stop of the object's own, 0.2 s at the play's 30 frames a second.</summary>
    public sealed class ContactStutter : MonoBehaviour
    {
        int frame;

        void Update()
        {
            if (frame < 60 || frame > 65) transform.position += Vector3.right * Time.deltaTime;
            frame++;
        }
    }
}
