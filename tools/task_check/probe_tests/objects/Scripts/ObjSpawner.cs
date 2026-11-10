using UnityEngine;

namespace ProbeTests.Objects
{
    // Every `every` s from `start` to `stop`: a clone of `template` (destroyed after its life), and one object of the
    // pool reactivated at the muzzle (it deactivates itself after its life).
    public class ObjSpawner : MonoBehaviour
    {
        public GameObject template;
        public GameObject[] pool;
        public float every = 0.5f, start = 1f, stop = 9f;
        float next;
        int at;

        void Start() { next = start; }

        void Update()
        {
            var t = Time.timeSinceLevelLoad;
            if (t < next || t > stop) return;
            next += every;
            var clone = Instantiate(template, transform.position, transform.rotation);
            clone.SetActive(true);
            if (pool != null && pool.Length > 0)
            {
                var p = pool[at++ % pool.Length];
                if (!p.activeSelf)
                {
                    p.transform.SetPositionAndRotation(transform.position + Vector3.up, transform.rotation);
                    p.SetActive(true);
                }
            }
        }
    }
}
