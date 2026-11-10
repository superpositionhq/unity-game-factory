using UnityEngine;

namespace ProbeTests.Select
{
    /// <summary>A component shaped like TextMeshPro's text: `fontMaterial` makes a copy of `fontSharedMaterial` each
    /// time it is read (counted in `copies`), as TMP_Text's does.</summary>
    public sealed class SelTextLike : MonoBehaviour
    {
        public Material fontSharedMaterial;
        public int copies;

        public Material fontMaterial
        {
            get
            {
                copies++;
                return fontSharedMaterial;
            }
        }
    }
}
