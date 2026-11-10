using System;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.UIElements;

namespace ProbeTests.Ui
{
    /// <summary>The Hud's UI Toolkit document, built in code: each element at a known place (margins 0), the ways an
    /// element is or isn't on screen (Vis*), and a counter in rich text and a progress bar set every frame by the frame
    /// count. UitkMover moves at 1 s. With -uilife it adds UitkBorn at 1 s.</summary>
    [RequireComponent(typeof(UIDocument))]
    public sealed class UiToolkitHud : MonoBehaviour
    {
        public Texture2D checker;
        public int frames;
        public float progress;
        VisualElement root, mover;
        Label counter;
        ProgressBar bar;
        bool life;

        static T At<T>(T e, float x, float y, float w, float h) where T : VisualElement
        {
            e.style.position = Position.Absolute;
            e.style.left = x;
            e.style.top = y;
            e.style.width = w;
            e.style.height = h;
            e.style.marginLeft = 0f;
            e.style.marginTop = 0f;
            e.style.marginRight = 0f;
            e.style.marginBottom = 0f;
            return e;
        }

        T Add<T>(T e, string name, float x, float y, float w, float h) where T : VisualElement
        {
            e.name = name;
            root.Add(At(e, x, y, w, h));
            return e;
        }

        void Start()
        {
            root = GetComponent<UIDocument>().rootVisualElement;
            life = Array.IndexOf(Environment.GetCommandLineArgs(), "-uilife") >= 0;
            counter = Add(new Label("<b>UITK</b> 0"), "UitkLabel", 620, 10, 200, 30);
            Add(new Image { image = checker }, "UitkImage", 830, 10, 40, 40);
            Add(new VisualElement(), "UitkBox", 880, 10, 40, 40).style.backgroundColor = Color.red;
            bar = Add(new ProgressBar { lowValue = 0f, highValue = 100f, title = "LOAD" }, "UitkProgress", 620, 45, 250, 25);
            Add(new UnityEngine.UIElements.Slider(0f, 10f) { value = 2.5f }, "UitkSlider", 620, 75, 200, 25);
            Add(new SliderInt(0, 4) { value = 1 }, "UitkSliderInt", 620, 105, 200, 25);
            Add(new UnityEngine.UIElements.Toggle { value = true, text = "MUSIC" }, "UitkToggle", 620, 135, 200, 25);
            Add(new DropdownField(new List<string> { "RED", "BLUE" }, 1), "UitkDropdown", 620, 165, 200, 25);
            Add(new TextField { value = "ABC" }, "UitkField", 620, 195, 150, 25);
            Add(new TextField(), "UitkEmptyField", 780, 195, 150, 25).textEdition.placeholder = "HINT";
            Add(new Scroller(0f, 100f, null, SliderDirection.Horizontal) { value = 50f }, "UitkScroller", 620, 225, 200, 20);
            var border = Add(new VisualElement(), "UitkBorder", 830, 60, 40, 40);
            border.style.borderLeftWidth = 2f;
            border.style.borderRightWidth = 2f;
            border.style.borderTopWidth = 2f;
            border.style.borderBottomWidth = 2f;
            border.style.borderLeftColor = Color.white;
            border.style.borderRightColor = Color.white;
            border.style.borderTopColor = Color.white;
            border.style.borderBottomColor = Color.white;
            Add(new VisualElement(), "UitkPlain", 880, 60, 40, 40);

            // the ways an element is or isn't on screen
            Add(new Label("HIDDEN"), "VisUitkHidden", 620, 250, 100, 20).style.display = DisplayStyle.None;
            Add(new Label("INVISIBLE"), "VisUitkInvisible", 730, 250, 100, 20).style.visibility = Visibility.Hidden;
            var parent = Add(new VisualElement(), "VisUitkHiddenParent", 840, 250, 100, 40);
            parent.style.visibility = Visibility.Hidden;
            var child = At(new VisualElement { name = "VisUitkShownChild" }, 0, 0, 100, 40);
            child.style.visibility = Visibility.Visible;
            child.style.backgroundColor = Color.green;
            parent.Add(child);
            Add(new Label("CLEAR"), "VisUitkClear", 620, 275, 100, 20).style.opacity = 0f;
            Add(new Label("FAINT"), "VisUitkFaint", 730, 275, 100, 20).style.opacity = 0.004f;
            Add(new Label("OFF"), "VisUitkOff", -500, 275, 100, 20);
            Add(new VisualElement(), "VisUitkZero", 840, 300, 0, 20).style.backgroundColor = Color.blue;
            Add(new UnityEngine.UIElements.Button { text = "NOPE" }, "VisUitkDisabled", 620, 300, 100, 25).SetEnabled(false);
            Add(new UnityEngine.UIElements.Button { text = "GO" }, "UitkButton", 730, 300, 100, 25);

            // turned 45 degrees about its centre, at (900, 360)
            var turned = Add(new VisualElement(), "RectUitkTurned", 870, 330, 60, 60);
            turned.style.rotate = new Rotate(new Angle(45f, AngleUnit.Degree));
            turned.style.backgroundColor = Color.yellow;
            // an element without a name: its row is named by its type
            root.Add(At(new Label("ANON"), 620, 330, 100, 20));
            // a box that moves from x 620 to 700 at 1 s
            mover = Add(new VisualElement(), "UitkMover", 620, 400, 60, 20);
            mover.style.backgroundColor = Color.magenta;
        }

        void Update()
        {
            frames++;
            counter.text = "<b>UITK</b> " + frames;
            progress = Mathf.Min(100f, frames);
            bar.value = progress;
            if (frames == 30) mover.style.left = 700f;  // laid out anew before the frame is drawn
            if (life && frames == 30) Add(new Label("BORN"), "UitkBorn", 620, 360, 100, 20);
        }
    }
}
