using System;
using UnityEngine;

namespace ProbeTests.Contact
{
    public enum ContactFoeState { Idle, Chasing, Stunned }

    [Serializable]
    public struct ContactGauge
    {
        public float level;
    }

    /// <summary>A foe of the Duel: walks `walk` m/s along x whatever happens to it, and takes damage through the
    /// contract's entry: what it returns is what it applied, never more than the health it had.</summary>
    public sealed class ContactFoe : MonoBehaviour, IDamageable
    {
        public float health = 10f;
        public bool dead;
        public ContactFoeState state;
        public string label = "";
        public string lastSource = "";
        public float walk = 1f;
        public ContactGauge gauge;
        public readonly int born = 3;
        public int Armor { get; private set; }
        public int Sealed => 7;
        float morale = 3f;

        /// <summary>A setter that keeps its own bounds: 0 to 5.</summary>
        public float Morale
        {
            get => morale;
            set => morale = Mathf.Clamp(value, 0f, 5f);
        }

        public float TakeDamage(float amount, GameObject source)
        {
            var applied = Mathf.Min(amount, health);
            health -= applied;
            if (health <= 0f) dead = true;
            lastSource = source != null ? source.name : "none";
            return applied;
        }

        void Update() => transform.position += Vector3.right * (walk * Time.deltaTime);
    }
}
