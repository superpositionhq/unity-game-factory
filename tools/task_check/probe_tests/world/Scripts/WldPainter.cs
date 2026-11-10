using UnityEngine;

namespace ProbeTests.World
{
    /// <summary>Draws a mesh every frame with Graphics.RenderMesh: drawn, but no placed piece.</summary>
    public sealed class WldPainter : MonoBehaviour
    {
        public Mesh mesh;
        public Material material;

        void Update()
        {
            Graphics.RenderMesh(new RenderParams(material), mesh, 0, transform.localToWorldMatrix);
        }
    }
}
