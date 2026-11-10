using UnityEngine;

namespace ProbeTests.Objects
{
    // Moves its kinematic Rigidbody (or Rigidbody2D) back and forth along x at `speed` m/s, in physics time.
    public class ObjKinematicMover : MonoBehaviour
    {
        public float speed = 2f, span = 4f;
        Rigidbody body;
        Rigidbody2D body2;
        Vector3 origin;

        void Start()
        {
            body = GetComponent<Rigidbody>();
            body2 = GetComponent<Rigidbody2D>();
            origin = transform.position;
        }

        void FixedUpdate()
        {
            var at = origin + new Vector3(Mathf.PingPong(Time.timeSinceLevelLoad * speed, span), 0f, 0f);
            if (body != null) body.MovePosition(at);
            if (body2 != null) body2.MovePosition(at);
        }
    }
}
