using UnityEngine;

namespace ProbeTests.Select
{
    /// <summary>Adds a nested MonoBehaviour type (SelNest.Inner, a type no scene can hold) to its object when it wakes.</summary>
    public sealed class SelNest : MonoBehaviour
    {
        public sealed class Inner : MonoBehaviour
        {
            public int kind = 7;
        }

        void Awake()
        {
            gameObject.AddComponent<Inner>();
        }
    }
}
