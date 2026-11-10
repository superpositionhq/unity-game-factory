using System;
using UnityEngine;
using UnityEngine.EventSystems;

namespace ProbeTests.Ui
{
    /// <summary>Counts what its object's EventTrigger entries fire (pointer down, up, click).</summary>
    public sealed class UiTriggerCount : MonoBehaviour
    {
        public int downs, ups, clicks;

        void Awake()
        {
            var trigger = GetComponent<EventTrigger>();
            Entry(trigger, EventTriggerType.PointerDown, () => downs++);
            Entry(trigger, EventTriggerType.PointerUp, () => ups++);
            Entry(trigger, EventTriggerType.PointerClick, () => clicks++);
        }

        static void Entry(EventTrigger trigger, EventTriggerType type, Action count)
        {
            var entry = new EventTrigger.Entry { eventID = type };
            entry.callback.AddListener(_ => count());
            trigger.triggers.Add(entry);
        }
    }
}
