using UnityEngine;
using UnityEngine.EventSystems;

namespace ProbeTests.Ui
{
    /// <summary>Whether there is an EventSystem, and the name of the object it has selected ("" for none).</summary>
    public sealed class UiClickWatch : MonoBehaviour
    {
        public int system;
        public string selected = "";

        void LateUpdate()
        {
            var events = EventSystem.current;
            system = events != null ? 1 : 0;
            selected = events != null && events.currentSelectedGameObject != null ? events.currentSelectedGameObject.name : "";
        }
    }
}
