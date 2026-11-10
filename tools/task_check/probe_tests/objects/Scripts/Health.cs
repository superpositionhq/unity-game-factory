using System.Collections.Generic;
using UnityEngine;

// Fields for prop: reads.
public class Health : MonoBehaviour
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
    public int rootCount => gameObject.scene.rootCount;
    public int rootIndex => System.Array.IndexOf(gameObject.scene.GetRootGameObjects(), gameObject);

    void Update()
    {
        current = Mathf.Max(0f, current - drainPerSecond * Time.deltaTime);
        state = current <= 0f ? State.Dead : current < 90f ? State.Hurt : State.Idle;
        armour = armour + 0;
    }
}
