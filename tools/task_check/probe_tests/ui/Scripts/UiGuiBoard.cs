using UnityEngine;
using UnityEngine.InputSystem;

namespace ProbeTests.Ui
{
    /// <summary>A menu drawn in OnGUI (IMGUI), as a game paints one: a GUI.Button (600, 400, 120 x 40 px, y down)
    /// counting its clicks (`guiClicks`), and a box (780, 400, 120 x 40) whose clicks are counted two ways: by the
    /// Input System's mouse, read in Update (`boxClicks`; a press elsewhere is `missed`), and by IMGUI's own
    /// MouseDown events in OnGUI (`eventClicks`). `mouseX`, `mouseY`: the Input System mouse's position, pixels from
    /// the bottom left.</summary>
    public sealed class UiGuiBoard : MonoBehaviour
    {
        public int guiClicks, eventClicks, boxClicks, missed;
        public float mouseX, mouseY;
        static readonly Rect ButtonRect = new Rect(600f, 400f, 120f, 40f);
        static readonly Rect BoxRect = new Rect(780f, 400f, 120f, 40f);

        void Update()
        {
            var mouse = Mouse.current;
            if (mouse == null) return;
            var at = mouse.position.ReadValue();
            mouseX = at.x;
            mouseY = at.y;
            if (!mouse.leftButton.wasPressedThisFrame) return;
            // IMGUI's points are pixels with y down from the top
            if (BoxRect.Contains(new Vector2(at.x, Screen.height - at.y))) boxClicks++;
            else missed++;
        }

        void OnGUI()
        {
            if (GUI.Button(ButtonRect, "GUI GO")) guiClicks++;
            GUI.Box(BoxRect, "HIT BOX");
            var e = Event.current;
            if (e.type == EventType.MouseDown && BoxRect.Contains(e.mousePosition)) eventClicks++;
        }
    }
}
