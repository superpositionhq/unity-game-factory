using UnityEngine;
using UIE = UnityEngine.UIElements;

namespace ProbeTests.Ui
{
    /// <summary>The Crowd scene's 200 UI Toolkit labels U000-U199, 20 to a row, 47 px apart from x = 10, from y = 350.</summary>
    [RequireComponent(typeof(UIE.UIDocument))]
    public sealed class UiCrowd : MonoBehaviour
    {
        void Start()
        {
            var root = GetComponent<UIE.UIDocument>().rootVisualElement;
            for (var i = 0; i < 200; i++)
            {
                var label = new UIE.Label("U" + i.ToString("D3")) { name = "U" + i.ToString("D3") };
                label.style.position = UIE.Position.Absolute;
                label.style.left = 10 + 47 * (i % 20);
                label.style.top = 350 + 18 * (i / 20);
                label.style.width = 44;
                label.style.height = 16;
                label.style.marginLeft = 0f;
                label.style.marginTop = 0f;
                label.style.marginRight = 0f;
                label.style.marginBottom = 0f;
                root.Add(label);
            }
        }
    }
}
