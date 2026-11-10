// The ui test scene's UI Toolkit document, built in code: a counting label, a button that counts its clicks, a progress
// bar that rises, a label hidden by display none and one by visibility hidden, and a big button for the cursor click.
using UnityEngine;
using UnityEngine.UIElements;

[RequireComponent(typeof(UIDocument))]
public class UitkTestPanel : MonoBehaviour
{
    Label counter, clicks, cursorClicks;
    ProgressBar progress;
    int clickCount, cursorCount;

    static void Place(VisualElement e, float left, float top, float width, float height)
    {
        e.style.position = Position.Absolute;
        e.style.left = left;
        e.style.top = top;
        e.style.width = width;
        e.style.height = height;
    }

    void Start()
    {
        var root = GetComponent<UIDocument>().rootVisualElement;
        counter = new Label("UITK 0") { name = "UitkLabel" };
        Place(counter, 620, 20, 200, 30);
        counter.style.fontSize = 22;
        counter.style.color = Color.white;
        root.Add(counter);

        var button = new Button(() => { clickCount++; clicks.text = "CLICKS " + clickCount; Debug.Log("UiTest: UitkButton clicked"); }) { name = "UitkButton", text = "GO" };
        Place(button, 620, 60, 100, 30);
        root.Add(button);
        clicks = new Label("CLICKS 0") { name = "UitkClicks" };
        Place(clicks, 740, 60, 150, 30);
        clicks.style.color = Color.white;
        root.Add(clicks);

        progress = new ProgressBar { name = "UitkProgress", title = "LOAD", lowValue = 0, highValue = 100, value = 0 };
        Place(progress, 620, 100, 250, 30);
        root.Add(progress);

        var hidden = new Label("HIDDEN") { name = "UitkHidden" };
        Place(hidden, 620, 140, 150, 30);
        hidden.style.display = DisplayStyle.None;
        root.Add(hidden);
        var invisible = new Label("INVISIBLE") { name = "UitkInvisible" };
        Place(invisible, 620, 170, 150, 30);
        invisible.style.visibility = Visibility.Hidden;
        root.Add(invisible);

        var cursorButton = new Button(() => { cursorCount++; cursorClicks.text = "UCURSOR " + cursorCount; Debug.Log("UiTest: UitkCursorButton clicked"); }) { name = "UitkCursorButton", text = "UITK CURSOR" };
        Place(cursorButton, 600, 400, 200, 60);
        root.Add(cursorButton);
        cursorClicks = new Label("UCURSOR 0") { name = "UitkCursorLabel" };
        Place(cursorClicks, 600, 470, 200, 30);
        cursorClicks.style.color = Color.white;
        root.Add(cursorClicks);
    }

    void Update()
    {
        var t = Time.timeSinceLevelLoad;
        if (counter != null) counter.text = "UITK " + Mathf.FloorToInt(t);
        if (progress != null) progress.value = Mathf.Min(100f, 10f * t);
    }
}
