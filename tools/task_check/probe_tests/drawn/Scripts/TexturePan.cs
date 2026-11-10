using UnityEngine;

namespace DrawnTest
{
    /// <summary>Pans its renderer's base map (a material animation the transform doesn't show).</summary>
    public sealed class TexturePan : MonoBehaviour
    {
        public Vector2 PerSecond = new Vector2(0.37f, 0f);
        Material material;
        void Start() => material = GetComponent<Renderer>().material;
        void Update() => material.SetTextureOffset("_BaseMap", PerSecond * Time.time);
    }
}
