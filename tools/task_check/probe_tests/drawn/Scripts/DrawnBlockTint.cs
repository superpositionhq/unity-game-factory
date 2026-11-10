using UnityEngine;

namespace ProbeTests.Drawn
{
    /// <summary>Tints its renderer through a MaterialPropertyBlock (the shared material stays white).</summary>
    public sealed class DrawnBlockTint : MonoBehaviour
    {
        public Color Colour = new Color(0.1f, 0.6f, 0.3f, 1f);

        void Start()
        {
            var block = new MaterialPropertyBlock();
            var r = GetComponent<Renderer>();
            r.GetPropertyBlock(block);
            block.SetColor("_BaseColor", Colour);
            r.SetPropertyBlock(block);
        }
    }
}
