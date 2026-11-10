// A component of the asset family's scenes and prefabs, with members of the kinds a prop: path reads.
using System.Collections.Generic;
using UnityEngine;

namespace ProbeTests.Asset
{
    public class AssetSpinner : MonoBehaviour
    {
        public float speed = 45f;
        public string label = "fan";
        public List<int> steps = new List<int> { 1, 2, 3, 4 };
        public Vector3 axis = Vector3.up;
        public Transform target;
        [SerializeField] int hiddenCount = 9;

        public int HiddenCount => hiddenCount;
    }
}
