using UnityEngine;

namespace ProbeTests.Select
{
    /// <summary>A pickup: implements ISelPickup.</summary>
    public sealed class SelCoin : MonoBehaviour, ISelPickup
    {
        public int value = 1;
        public int Worth => value;
    }
}
