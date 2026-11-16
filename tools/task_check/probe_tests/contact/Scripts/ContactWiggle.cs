using UnityEngine;

namespace ProbeTests.Contact
{
    /// <summary>A skinned thing that stands where it is and moves one bone 1 cm a frame, but for six frames of its own,
    /// its 60th to its 65th: a stop only its pose shows.</summary>
    public sealed class ContactWiggle : MonoBehaviour
    {
        public Transform bone;
        int frame;

        void Update()
        {
            if (frame < 60 || frame > 65) bone.localPosition += Vector3.right * 0.01f;
            frame++;
        }
    }
}
