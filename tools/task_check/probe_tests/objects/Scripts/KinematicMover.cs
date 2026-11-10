using UnityEngine;

// Moves its kinematic Rigidbody back and forth along x at `speed` m/s.
public class KinematicMover : MonoBehaviour
{
    public float speed = 2f, span = 4f;
    Rigidbody body;
    Vector3 origin;

    void Start() { body = GetComponent<Rigidbody>(); origin = transform.position; }

    void FixedUpdate()
    {
        var x = Mathf.PingPong(Time.timeSinceLevelLoad * speed, span);
        body.MovePosition(origin + new Vector3(x, 0f, 0f));
    }
}
