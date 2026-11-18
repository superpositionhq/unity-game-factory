using UnityEngine;
using UnityEngine.UIElements;

namespace ProbeTests.Ui
{
    /// <summary>The Clicks scene's UI Toolkit buttons, each counting its clicks: UGoButton (Button.clicked), UEvtButton
    /// (a ClickEvent callback only), UNoButton (disabled), UOffButton (off the frame), UCursorButton (for the
    /// cursor), UCaptionButton (clicked by what it reads), and in a ScrollView 60 px tall UScrollInButton (in view) and
    /// UScrollOutButton (below a 150 px spacer: scrolled out of the viewport, still on the frame).</summary>
    [RequireComponent(typeof(UIDocument))]
    public sealed class UiToolkitClicks : MonoBehaviour
    {
        public int go, evt, no, off, cursor, caption, scrollIn, scrollOut;
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
            Add(new Button(() => caption++) { text = "Start run" }, "UCaptionButton", 620, 360, 120, 30);
            var view = new ScrollView { name = "UScrollView" };
            view.style.position = Position.Absolute;
            view.style.left = 800f;
            view.style.top = 20f;
            view.style.width = 120f;
            view.style.height = 60f;
            var inView = new Button(() => scrollIn++) { name = "UScrollInButton", text = "U IN VIEW" };
            inView.style.height = 30f;
            inView.style.flexShrink = 0f;
            view.Add(inView);
            var spacer = new VisualElement();
            spacer.style.height = 150f;
            spacer.style.flexShrink = 0f;
            view.Add(spacer);
            var outOfView = new Button(() => scrollOut++) { name = "UScrollOutButton", text = "U SCROLLED OUT" };
            outOfView.style.height = 30f;
            outOfView.style.flexShrink = 0f;
            view.Add(outOfView);
            root.Add(view);
        }
    }
}
