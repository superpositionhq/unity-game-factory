using UnityEngine;

namespace ProbeTests.Select
{
    /// <summary>Moves its (root) object to the DontDestroyOnLoad scene when it wakes.</summary>
    public sealed class SelKeeper : MonoBehaviour
    {
        void Awake()
        {
            DontDestroyOnLoad(gameObject);
        }
    }
}
