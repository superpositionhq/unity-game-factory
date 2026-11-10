using System.Collections.Generic;
using UnityEngine;

namespace ProbeTests.Objects
{
    // An interface a select may name: the objects and components carrying a component that implements it match.
    public interface IObjHurt
    {
        float Hurt { get; }
    }

    // Members of every kind for prop: reads, drained by game time.
    public class ObjHealth : MonoBehaviour, IObjHurt
    {
        public enum State { Idle, Hurt, Dead }
        public float current = 100f;
        [SerializeField] int armour = 7;
        public State state = State.Idle;
        public string label = "grunt";
        public List<int> items = new List<int> { 3, 5, 9 };
        public Color tint = new Color(0.25f, 0.5f, 1f, 1f);
        public Transform target;
        public float drainPerSecond = 5f;
        public int sibling => transform.GetSiblingIndex();
        public int rootIndex => System.Array.IndexOf(gameObject.scene.GetRootGameObjects(), gameObject);
        public float Hurt => 100f - current;

        void Update()
        {
            current = Mathf.Max(0f, current - drainPerSecond * Time.deltaTime);
            state = current <= 0f ? State.Dead : current < 90f ? State.Hurt : State.Idle;
            armour = armour + 0;
        }
    }
}
