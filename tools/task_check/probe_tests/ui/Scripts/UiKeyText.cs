using UnityEngine;
using UnityEngine.UIElements;

namespace ProbeTests.Ui
{
    /// <summary>The Keys scenes' UI Toolkit text field, KeyText (20, 170, 200 x 30 px), counting its value's changes
    /// (`changes`), the Enter keys that reach it (`enters`: a KeyDownEvent of Return or KeypadEnter) and its
    /// NavigationSubmitEvents (`submits`), each caught on its way down to the field's text input.</summary>
    [RequireComponent(typeof(UIDocument))]
    public sealed class UiKeyText : MonoBehaviour
    {
        public int changes, enters, submits;

        void Start()
        {
            var field = new TextField { name = "KeyText" };
            field.style.position = Position.Absolute;
            field.style.left = 20f;
            field.style.top = 170f;
            field.style.width = 200f;
            field.style.height = 30f;
            field.RegisterValueChangedCallback(_ => changes++);
            field.RegisterCallback<KeyDownEvent>(e =>
            {
                if (e.keyCode == KeyCode.Return || e.keyCode == KeyCode.KeypadEnter) enters++;
            }, TrickleDown.TrickleDown);
            field.RegisterCallback<NavigationSubmitEvent>(_ => submits++, TrickleDown.TrickleDown);
            GetComponent<UIDocument>().rootVisualElement.Add(field);
        }
    }
}
