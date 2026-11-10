using UnityEngine;

namespace ProbeTests.Objects
{
    // What the probe's queries must leave as they found it, looked at after the probe's samples of every frame: the
    // active render texture (as it was before the frame's late updates), and the materials and property blocks of the
    // renderers it watches. Each count is the frames that found it changed (read with prop:ObjWatch.<count>).
    [DefaultExecutionOrder(32050)]
    public class ObjWatch : MonoBehaviour
    {
        public Renderer[] watched = new Renderer[0];
        public int activeChanged, materialsChanged, blocksChanged;
        RenderTexture active;
        int[][] materials;
        bool[] blocks;

        static int[] Ids(Renderer r)
        {
            var shared = r.sharedMaterials;
            var ids = new int[shared.Length];
            for (var i = 0; i < shared.Length; i++) ids[i] = shared[i] != null ? shared[i].GetInstanceID() : 0;
            return ids;
        }

        void Start()
        {
            materials = new int[watched.Length][];
            blocks = new bool[watched.Length];
            for (var i = 0; i < watched.Length; i++)
            {
                if (watched[i] == null) continue;
                materials[i] = Ids(watched[i]);
                blocks[i] = watched[i].HasPropertyBlock();
            }
        }

        void Update() { active = RenderTexture.active; }

        void LateUpdate()
        {
            if (RenderTexture.active != active) activeChanged++;
            var materialChange = false;
            var blockChange = false;
            for (var i = 0; i < watched.Length; i++)
            {
                if (watched[i] == null || materials[i] == null) continue;
                materialChange |= !System.Linq.Enumerable.SequenceEqual(Ids(watched[i]), materials[i]);
                blockChange |= watched[i].HasPropertyBlock() != blocks[i];
            }
            if (materialChange) materialsChanged++;
            if (blockChange) blocksChanged++;
        }
    }
}
