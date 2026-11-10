// Test component for the asset family's prop: reads.
using System.Collections.Generic;
using UnityEngine;

namespace AssetTest
{
    public class Spinner : MonoBehaviour
    {
        public float speed = 45f;
        public string label = "fan";
        public List<int> steps = new List<int> { 1, 2, 3, 4 };
        public Vector3 axis = Vector3.up;
        [SerializeField] int hiddenCount = 9;
    }
}
