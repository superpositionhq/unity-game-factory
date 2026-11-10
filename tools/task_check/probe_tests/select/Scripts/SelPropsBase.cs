using UnityEngine;

namespace ProbeTests.Select
{
    /// <summary>SelProps's base: members a prop: path reads through the derived type (one private, one protected, one
    /// public).</summary>
    public abstract class SelPropsBase : MonoBehaviour
    {
#pragma warning disable 0414  // read by prop: paths, not by code
        int hidden = 11;
#pragma warning restore 0414
        protected int guarded = 12;
        public int inherited = 13;
    }
}
