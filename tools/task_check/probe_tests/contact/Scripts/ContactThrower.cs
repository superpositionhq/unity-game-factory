using System;
using UnityEngine;

namespace ProbeTests.Contact
{
    /// <summary>Its damage entry throws.</summary>
    public sealed class ContactThrower : MonoBehaviour, IDamageable
    {
        public float TakeDamage(float amount, GameObject source) => throw new InvalidOperationException("ContactThrower takes no damage");
    }
}
