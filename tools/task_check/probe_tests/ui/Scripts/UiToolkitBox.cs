using UnityEngine;
using UnityEngine.UIElements;

namespace ProbeTests.Ui
{
    /// <summary>One named box in its document's panel, at `rect` in the panel's own units.</summary>
    [RequireComponent(typeof(UIDocument))]
    public sealed class UiToolkitBox : MonoBehaviour
    {
        public string boxName;
        public Rect rect;

        void Start()
        {
            var box = new VisualElement { name = boxName };
            box.style.position = Position.Absolute;
            box.style.left = rect.x;
            box.style.top = rect.y;
            box.style.width = rect.width;
            box.style.height = rect.height;
            box.style.backgroundColor = Color.cyan;
            GetComponent<UIDocument>().rootVisualElement.Add(box);
        }
    }
}
