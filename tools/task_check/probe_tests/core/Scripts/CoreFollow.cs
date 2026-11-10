using UnityEngine;

namespace ProbeTests.Core
{
    /// <summary>A follow camera: after the game's Updates it stands 3 m above and 6 m behind the hero.</summary>
    public sealed class CoreFollow : MonoBehaviour
    {
        Transform hero;

        void Start() { hero = GameObject.Find("Hero").transform; }

        void LateUpdate()
        {
            transform.position = hero.position + new Vector3(0f, 3f, -6f);
        }
    }
}
