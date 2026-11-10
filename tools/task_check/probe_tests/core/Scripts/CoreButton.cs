using UnityEngine;
using UnityEngine.UI;

namespace ProbeTests.Core
{
    /// <summary>Counts the clicks of its Button.</summary>
    public sealed class CoreButton : MonoBehaviour
    {
        public int clicks;

        void Awake() { GetComponent<Button>().onClick.AddListener(() => clicks++); }
    }
}
