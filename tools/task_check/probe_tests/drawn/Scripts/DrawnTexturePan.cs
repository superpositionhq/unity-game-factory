using UnityEngine;

namespace ProbeTests.Drawn
{
    /// <summary>Pans its renderer's base map by game time (a material animation the transform doesn't show).</summary>
    public sealed class DrawnTexturePan : MonoBehaviour
    {
        public Vector2 PerSecond = new Vector2(0.37f, 0f);
        Material material;

        void Start() => material = GetComponent<Renderer>().material;
        void Update() => material.SetTextureOffset("_BaseMap", PerSecond * Time.timeSinceLevelLoad);
    }
}
