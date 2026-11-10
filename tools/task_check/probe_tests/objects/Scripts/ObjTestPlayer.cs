using UnityEngine;
using UnityEngine.InputSystem;

namespace ProbeTests.Objects
{
    // The player: W/A/S/D on world axes at 4 m/s through a CharacterController, Space jumps; it faces where it moves.
    [RequireComponent(typeof(CharacterController))]
    public class ObjTestPlayer : MonoBehaviour
    {
        public float speed = 4f;
        float vy;
        CharacterController cc;

        void Awake() { cc = GetComponent<CharacterController>(); }

        void Update()
        {
            var k = Keyboard.current;
            var move = Vector3.zero;
            if (k != null)
            {
                if (k.wKey.isPressed) move.z += 1f;
                if (k.sKey.isPressed) move.z -= 1f;
                if (k.dKey.isPressed) move.x += 1f;
                if (k.aKey.isPressed) move.x -= 1f;
                if (k.spaceKey.wasPressedThisFrame && cc.isGrounded) vy = 5f;
            }
            if (cc.isGrounded && vy < 0f) vy = -1f;
            vy -= 9.81f * Time.deltaTime;
            var v = move.normalized * speed;
            if (move.sqrMagnitude > 0f) transform.rotation = Quaternion.LookRotation(move.normalized, Vector3.up);
            cc.Move(new Vector3(v.x, vy, v.z) * Time.deltaTime);
        }
    }
}
