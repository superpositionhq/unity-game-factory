using UnityEngine;
using UnityEngine.Rendering;

namespace ProbeTests.Objects
{
    // What the engine does with a colour on its way to a shader, which a lamp's expected glow rests on (read with
    // prop:ObjFacts.litHdr and so on): whether a shader marks _EmissionColor [HDR] (Unity hands an [HDR] colour to the
    // shader as the material holds it, any other made linear), and what a MaterialPropertyBlock gives back of a colour
    // and of a vector set on it (the same: a block can't say whether it holds a colour, which Unity makes linear for the
    // shader, or a vector, which it hands on as it is).
    public class ObjFacts : MonoBehaviour
    {
        public Material lit, standard;  // a URP Lit material and a built-in Standard one

        public bool litHdr => Hdr(lit);
        public bool standardHdr => Hdr(standard);

        public float blockColour
        {
            get
            {
                var block = new MaterialPropertyBlock();
                block.SetColor("_ObjFact", new Color(0.5f, 0.5f, 0.5f, 1f));
                return block.GetColor("_ObjFact").r;
            }
        }

        public float vectorAsColour
        {
            get
            {
                var block = new MaterialPropertyBlock();
                block.SetVector("_ObjFact", new Vector4(0.5f, 0.5f, 0.5f, 1f));
                return block.HasColor("_ObjFact") ? block.GetColor("_ObjFact").r : -1f;
            }
        }

        static bool Hdr(Material m)
        {
            if (m == null) return false;
            var i = m.shader.FindPropertyIndex("_EmissionColor");
            return i >= 0 && (m.shader.GetPropertyFlags(i) & ShaderPropertyFlags.HDR) != 0;
        }
    }
}
