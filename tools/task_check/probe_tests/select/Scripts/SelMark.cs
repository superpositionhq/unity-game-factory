using UnityEngine;

namespace ProbeTests.Select
{
    /// <summary>A marker a select names in the crowd; a pickup too, so a spawns query can name its interface.</summary>
    public sealed class SelMark : MonoBehaviour, ISelPickup
    {
        public int mark = 1;
        public int Worth => mark;
    }
}
