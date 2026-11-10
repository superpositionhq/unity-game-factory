using UnityEngine;

namespace ProbeTests.Objects
{
    // From `from` to `to` s it stands halfway between the camera and the target (the camera can't see the target); else
    // far away below the floor.
    [DefaultExecutionOrder(1000)]
    public class ObjOccluder : MonoBehaviour
    {
        public Transform target;
        public float from = 6f, to = 8f;

        void LateUpdate()
        {
            var t = Time.timeSinceLevelLoad;
            var cam = Camera.main;
            if (target != null && cam != null && t >= from && t < to)
            {
                transform.position = (cam.transform.position + target.position + Vector3.up) * 0.5f;
                transform.rotation = Quaternion.LookRotation(cam.transform.forward);
            }
            else transform.position = new Vector3(0f, -100f, 0f);
        }
    }
}
