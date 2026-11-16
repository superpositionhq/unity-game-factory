using UnityEngine;

namespace ProbeTests.Contact
{
    /// <summary>The game contract's damage entry (docs/game-format.md), as a game declares it.</summary>
    public interface IDamageable
    {
        float TakeDamage(float amount, GameObject source);
    }
}
