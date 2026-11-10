using UnityEngine;

namespace ProbeTests.Core
{
    /// <summary>A player the game moves by itself, 1 m/s along x, through whatever moves its object: a
    /// CharacterController (SimpleMove, which also lets it fall), a Rigidbody or a Rigidbody2D (its velocity).</summary>
    public sealed class CoreStroll : MonoBehaviour
    {
        CharacterController controller;
        Rigidbody body;
        Rigidbody2D body2;

        void Awake()
        {
            controller = GetComponent<CharacterController>();
            body = GetComponent<Rigidbody>();
            body2 = GetComponent<Rigidbody2D>();
        }

        void Update()
        {
            if (controller != null) controller.SimpleMove(Vector3.right);
        }

        void FixedUpdate()
        {
            if (body != null) body.linearVelocity = new Vector3(1f, body.linearVelocity.y, 0f);
            if (body2 != null) body2.linearVelocity = new Vector2(1f, body2.linearVelocity.y);
        }
    }
}
