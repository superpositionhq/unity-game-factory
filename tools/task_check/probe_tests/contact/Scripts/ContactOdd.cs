using UnityEngine;

namespace ProbeTests.Contact.Odd
{
    /// <summary>An interface of the contract's name that isn't the contract's: no source, a parameter without a
    /// default.</summary>
    public interface IDamageable
    {
        void TakeDamage(float amount, GameObject source, int combo);
        void TakeDamage(int amount);
    }
}

namespace ProbeTests.Contact
{
    public sealed class ContactOdd : MonoBehaviour, Odd.IDamageable
    {
        public int hits;

        public void TakeDamage(float amount, GameObject source, int combo) => hits++;

        public void TakeDamage(int amount) => hits++;
    }
}
