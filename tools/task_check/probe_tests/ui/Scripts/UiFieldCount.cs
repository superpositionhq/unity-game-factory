using UnityEngine;
using UnityEngine.Events;
using UnityEngine.UI;
using TMPro;

namespace ProbeTests.Ui
{
    /// <summary>Counts what its InputField or TMP_InputField fires as keys edit it (`changes`: onValueChanged, `ends`:
    /// onEndEdit, `submits`: onSubmit), and whether it is being edited (`focused`, 1 or 0, after the frame's Updates).</summary>
    public sealed class UiFieldCount : MonoBehaviour
    {
        public int changes, ends, submits, focused;

        void Awake()
        {
            if (TryGetComponent<InputField>(out var field)) Listen(field, field.onValueChanged, field.onEndEdit);
            else if (TryGetComponent<TMP_InputField>(out var tmp)) Listen(tmp, tmp.onValueChanged, tmp.onEndEdit);
        }

        void Listen(Component field, UnityEvent<string> changed, UnityEvent<string> ended)
        {
            changed.AddListener(_ => changes++);
            ended.AddListener(_ => ends++);
            // onSubmit by its name: a uGUI InputField without one submits through onEndEdit alone
            if (field.GetType().GetProperty("onSubmit")?.GetValue(field) is UnityEvent<string> submitted) submitted.AddListener(_ => submits++);
        }

        void LateUpdate()
        {
            focused = TryGetComponent<InputField>(out var field) ? (field.isFocused ? 1 : 0)
                : TryGetComponent<TMP_InputField>(out var tmp) && tmp.isFocused ? 1 : 0;
        }
    }
}
