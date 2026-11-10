using UnityEngine;

namespace ProbeTests.Objects
{
    // Flies forward; after `life` s it is destroyed, or deactivated when pooled.
    public class ObjProjectile : MonoBehaviour
    {
        public float speed = 8f, life = 1f;
        public bool pooled;
        float born;

        void OnEnable() { born = Time.timeSinceLevelLoad; }

        void Update()
        {
            transform.position += transform.forward * speed * Time.deltaTime;
            if (Time.timeSinceLevelLoad - born < life) return;
            if (pooled) gameObject.SetActive(false); else Destroy(gameObject);
        }
    }
}
