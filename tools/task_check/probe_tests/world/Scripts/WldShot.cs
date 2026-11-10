using UnityEngine;

namespace ProbeTests.World
{
    /// <summary>What the spawns plays count. With `life` above 0 it destroys its object that many seconds of game time
    /// after it woke.</summary>
    public sealed class WldShot : WldShotBase, IWldShot
    {
        public float life;
        float age;

        public float Life => life;

        void Update()
        {
            age += Time.deltaTime;
            if (life > 0f && age >= life) Destroy(gameObject);
        }
    }
}
