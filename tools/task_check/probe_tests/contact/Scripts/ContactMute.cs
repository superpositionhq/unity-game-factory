using UnityEngine;

namespace ProbeTests.Contact.Mute
{
    /// <summary>A damage entry that says nothing of what the hit did.</summary>
    public interface IDamageable
    {
        void TakeDamage(float amount, GameObject source);
    }
}

namespace ProbeTests.Contact
{
    public sealed class ContactMute : MonoBehaviour, Mute.IDamageable
    {
        public int hits;

        public void TakeDamage(float amount, GameObject source) => hits++;
    }
}
