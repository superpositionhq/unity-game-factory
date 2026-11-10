using UnityEngine;
using UnityEngine.EventSystems;
using UnityEngine.UI;

namespace ProbeTests.Ui
{
    /// <summary>Counts the pointer events its object gets and what its Button, Toggle or Slider fires.</summary>
    public sealed class UiClickCount : MonoBehaviour, IPointerEnterHandler, IPointerDownHandler, IPointerUpHandler, IPointerClickHandler,
        IPointerExitHandler
    {
        public int enters, downs, ups, clicks, exits, fired;

        void Awake()
        {
            if (TryGetComponent<Button>(out var button)) button.onClick.AddListener(() => fired++);
            else if (TryGetComponent<Toggle>(out var toggle)) toggle.onValueChanged.AddListener(_ => fired++);
            else if (TryGetComponent<Slider>(out var slider)) slider.onValueChanged.AddListener(_ => fired++);
        }

        public void OnPointerEnter(PointerEventData eventData) => enters++;
        public void OnPointerDown(PointerEventData eventData) => downs++;
        public void OnPointerUp(PointerEventData eventData) => ups++;
        public void OnPointerClick(PointerEventData eventData) => clicks++;
        public void OnPointerExit(PointerEventData eventData) => exits++;
    }
}
