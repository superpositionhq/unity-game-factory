using UnityEngine;
using UnityEngine.UIElements;

namespace ProbeTests.Ui
{
    /// <summary>The Clicks scene's UI Toolkit buttons, each counting its clicks: UGoButton (Button.clicked), UEvtButton
    /// (a ClickEvent callback only), UNoButton (disabled), UOffButton (off the frame), UCursorButton (for the
    /// cursor).</summary>
    [RequireComponent(typeof(UIDocument))]
    public sealed class UiToolkitClicks : MonoBehaviour
    {
        public int go, evt, no, off, cursor;
        VisualElement root;

        Button Add(Button button, string name, float x, float y, float w, float h)
        {
            button.name = name;
            button.style.position = Position.Absolute;
            button.style.left = x;
            button.style.top = y;
            button.style.width = w;
            button.style.height = h;
            root.Add(button);
            return button;
        }

        void Start()
        {
            root = GetComponent<UIDocument>().rootVisualElement;
            Add(new Button(() => go++) { text = "UGO" }, "UGoButton", 620, 20, 120, 30);
            Add(new Button { text = "UEVT" }, "UEvtButton", 620, 60, 120, 30).RegisterCallback<ClickEvent>(_ => evt++);
            Add(new Button(() => no++) { text = "UNO" }, "UNoButton", 620, 100, 120, 30).SetEnabled(false);
            Add(new Button(() => off++) { text = "UOFF" }, "UOffButton", -500, 140, 120, 30);
            Add(new Button(() => cursor++) { text = "UCURSOR" }, "UCursorButton", 620, 300, 160, 40);
        }
    }
}
