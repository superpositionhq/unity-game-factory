using UnityEngine;
using UnityEngine.Rendering;

namespace ProbeTests.Objects
{
    // What the engine does with a colour on its way to a shader, which a lamp's expected glow rests on (read with
    // prop:ObjFacts.litHdr and so on): whether a shader marks _EmissionColor [HDR] (Unity hands an [HDR] colour to the
    // shader as the material holds it, any other made linear), and what a MaterialPropertyBlock gives back of a colour
    // set on it.
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

        static bool Hdr(Material m)
        {
            if (m == null) return false;
            var i = m.shader.FindPropertyIndex("_EmissionColor");
            return i >= 0 && (m.shader.GetPropertyFlags(i) & ShaderPropertyFlags.HDR) != 0;
        }
    }
}
