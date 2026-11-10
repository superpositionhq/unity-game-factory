using UnityEngine;

// Between from and to s it stands halfway between the camera and the target (so the camera can't see it); else far away.
[DefaultExecutionOrder(1000)]
public class Occluder : MonoBehaviour
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
