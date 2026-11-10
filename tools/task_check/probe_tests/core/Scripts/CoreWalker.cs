using UnityEngine;
using UnityEngine.InputSystem;

namespace ProbeTests.Core
{
    /// <summary>The hero of the Stage: walks 2 m/s along z while W (forward) or S (back) is down, drifts 1 m/s along x
    /// with -coredrift (the game moving the player by itself), and keeps what it saw of the keyboard, the mouse, the
    /// gamepad and the window's focus in fields a play reads.</summary>
    public sealed class CoreWalker : MonoBehaviour
    {
        public float strayed = float.NegativeInfinity;  // the furthest along x a frame's Update found it
        public int unfocused;   // frames the game didn't count itself focused
        public int focusLost;   // OnApplicationFocus(false) calls
        public int both;        // frames W and D were down together
        public float mouseX;    // the mouse's delta x, summed
        public float scrollY;   // its scroll y, summed
        public int left;        // frames its left button was down
        public float cursorX;   // its position, pixels from the frame's bottom left
        public float cursorY;
        public int pad;         // 1 when a gamepad is there
        public float stickX;    // its left stick's x
        public int south;       // frames its south button was down
        bool drift;

        void Awake() { drift = CoreArgs.Has("-coredrift"); }

        void Update()
        {
            if (transform.position.x > strayed) strayed = transform.position.x;
            if (!Application.isFocused) unfocused++;
            var move = Vector3.zero;
            var keys = Keyboard.current;
            if (keys != null)
            {
                if (keys.wKey.isPressed) move.z += 2f;
                if (keys.sKey.isPressed) move.z -= 2f;
                if (keys.wKey.isPressed && keys.dKey.isPressed) both++;
            }
            if (drift) move.x += 1f;
            transform.position += move * Time.deltaTime;
            var mouse = Mouse.current;
            if (mouse != null)
            {
                mouseX += mouse.delta.ReadValue().x;
                scrollY += mouse.scroll.ReadValue().y;
                if (mouse.leftButton.isPressed) left++;
                var at = mouse.position.ReadValue();
                cursorX = at.x;
                cursorY = at.y;
            }
            var gamepad = Gamepad.current;
            pad = gamepad != null ? 1 : 0;
            if (gamepad == null) return;
            stickX = gamepad.leftStick.ReadValue().x;
            if (gamepad.buttonSouth.isPressed) south++;
        }

        void OnApplicationFocus(bool focus)
        {
            if (!focus) focusLost++;
        }
    }
}
