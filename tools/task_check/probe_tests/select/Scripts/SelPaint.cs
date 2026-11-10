using UnityEngine;

namespace ProbeTests.Select
{
    /// <summary>What its renderer, mesh filter and collider hold, every frame: a read through `material`, `materials` or
    /// `mesh` that gave them copies of their own would show here as "(Instance)" names and a physics material.</summary>
    public sealed class SelPaint : MonoBehaviour
    {
        public string sharedMaterialName, sharedMeshName;
        public int instancedMaterials, colliderMaterial;

        void LateUpdate()
        {
            var r = GetComponent<Renderer>();
            sharedMaterialName = r.sharedMaterial != null ? r.sharedMaterial.name : "";
            instancedMaterials = 0;
            foreach (var m in r.sharedMaterials)
                if (m != null && m.name.Contains("(Instance)")) instancedMaterials++;
            var f = GetComponent<MeshFilter>();
            sharedMeshName = f.sharedMesh != null ? f.sharedMesh.name : "";
            colliderMaterial = GetComponent<Collider>().sharedMaterial != null ? 1 : 0;
        }
    }
}
