// A component that changes itself and marks itself changed whenever it loads (OnValidate), in a prefab and in scenes,
// and says so in the log: the editor pass must still write nothing back, and opens each scene once.
using UnityEngine;

namespace ProbeTests.Asset
{
    public class AssetDirtier : MonoBehaviour
    {
        public int loads;

        void OnValidate()
        {
            loads++;
            Debug.Log("ASSET loaded " + gameObject.name);
#if UNITY_EDITOR
            UnityEditor.EditorUtility.SetDirty(this);
#endif
        }
    }
}
