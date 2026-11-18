using UnityEngine;
using UnityEngine.InputSystem;

namespace ProbeTests.Ui
{
    /// <summary>The game's own reading of the keyboard in the Keys scenes, whatever the UI does with a key: an
    /// InputAction bound to the A key counting its presses (`aPresses`), and the characters every keyboard's
    /// onTextInput gave, in order (`typed`).</summary>
    public sealed class UiKeyGame : MonoBehaviour
    {
        public int aPresses;
        public string typed = "";
        InputAction a;

        void OnEnable()
        {
            a = new InputAction(type: InputActionType.Button, binding: "<Keyboard>/a");
            a.performed += _ => aPresses++;
            a.Enable();
            foreach (var device in InputSystem.devices)
                if (device is Keyboard keyboard) keyboard.onTextInput += Typed;
        }

        void OnDisable()
        {
            a.Disable();
            foreach (var device in InputSystem.devices)
                if (device is Keyboard keyboard) keyboard.onTextInput -= Typed;
        }

        void Typed(char c) => typed += c;
    }
}
