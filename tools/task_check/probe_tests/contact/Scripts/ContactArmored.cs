using UnityEngine;

namespace ProbeTests.Contact.Extra
{
    /// <summary>A damage entry with more to say: parameters after the contract's two, each with a default.</summary>
    public interface IDamageable
    {
        float TakeDamage(float amount, GameObject source, string kind = "blunt", int combo = 2);
    }
}

namespace ProbeTests.Contact
{
    /// <summary>Takes half of every hit, and keeps what the hit said of itself.</summary>
    public sealed class ContactArmored : MonoBehaviour, Extra.IDamageable
    {
        public float health = 10f;
        public string kind = "";
        public int combo;

        public float TakeDamage(float amount, GameObject source, string kind = "blunt", int combo = 2)
        {
            this.kind = kind;
            this.combo = combo;
            health -= amount / 2f;
            return amount / 2f;
        }
    }
}
