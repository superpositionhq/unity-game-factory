using UnityEngine;
using UnityEngine.SceneManagement;

namespace ProbeTests.Select
{
    /// <summary>What changes in SelLab during a play, by game time: SelSide is loaded additively at Start and two clones
    /// of `template` are made; at 1 s a new root (Late_Root) appears; from 1.4 to 1.6 s a new root (Burst_0, Burst_1...)
    /// appears every frame, so one is made in the frame of the 1.5 s sample; at 1.5 s `child` leaves its parent for the
    /// root list.</summary>
    public sealed class SelDirector : MonoBehaviour
    {
        public GameObject template;
        public Transform child;
        bool made, moved;
        int bursts;

        void Start()
        {
            SceneManager.LoadScene("Assets/ProbeTests/select/Made/SelSide.unity", LoadSceneMode.Additive);
            Instantiate(template);
            Instantiate(template);
        }

        void Update()
        {
            if (!made && Time.time >= 1f)
            {
                made = true;
                new GameObject("Late_Root").AddComponent<SelRootInfo>();
            }
            if (Time.time >= 1.4f && Time.time < 1.6f) new GameObject("Burst_" + bursts++);
            if (!moved && Time.time >= 1.5f && child != null)
            {
                moved = true;
                child.SetParent(null);
            }
        }
    }
}
