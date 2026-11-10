using UnityEngine;

// Follows the target from behind and above; looks away (turned 180 degrees) between lookAwayFrom and lookAwayTo s.
public class FollowCam : MonoBehaviour
{
    public Transform target;
    public Vector3 offset = new Vector3(0f, 3f, -6f);
    public float lookAwayFrom = 10f, lookAwayTo = 11f;

    void LateUpdate()
    {
        if (target == null) return;
        transform.position = target.position + offset;
        transform.LookAt(target.position + Vector3.up);
        var t = Time.timeSinceLevelLoad;
        if (t >= lookAwayFrom && t < lookAwayTo) transform.Rotate(0f, 180f, 0f, Space.World);
    }
}
