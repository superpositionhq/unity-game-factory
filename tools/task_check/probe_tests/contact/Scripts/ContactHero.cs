using UnityEngine;

namespace ProbeTests.Contact
{
    /// <summary>The player of the Duel: stands still and takes every point of damage it is dealt.</summary>
    public sealed class ContactHero : MonoBehaviour, IDamageable
    {
        public float health = 100f;
        public string lastSource = "";

        public float TakeDamage(float amount, GameObject source)
        {
            health -= amount;
            lastSource = source != null ? source.name : "none";
            return amount;
        }
    }
}
