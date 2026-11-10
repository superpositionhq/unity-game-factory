using System;
using UnityEngine;

namespace ProbeTests.Drawn
{
    /// <summary>With -drawnCrowd, a large scene: 3000 cubes in a grid behind the player's camera, away from every place
    /// (what a render looks through each frame), and 1100 small cubes inside one place (more than a place renders).</summary>
    public sealed class DrawnCrowd : MonoBehaviour
    {
        public GameObject Template;

        void Start()
        {
            if (Array.IndexOf(Environment.GetCommandLineArgs(), "-drawnCrowd") < 0) return;
            var far = new GameObject("CrowdFar").transform;
            for (var i = 0; i < 3000; i++)
                Make("Far" + i, new Vector3(-50f + (i % 60) * 1.5f, 0.5f, -150f - (i / 60) * 1.5f), 1f, far);
            var near = new GameObject("CrowdNear").transform;
            for (var i = 0; i < 1100; i++)
                Make("Near" + i, new Vector3(-0.5f + (i % 11) * 0.1f, 0.55f + (i / 11 % 10) * 0.1f, -100.45f + i / 110 * 0.1f), 0.05f, near);
        }

        void Make(string name, Vector3 at, float size, Transform parent)
        {
            var c = Instantiate(Template, at, Quaternion.identity, parent);
            c.name = name;
            c.transform.localScale = Vector3.one * size;
            c.SetActive(true);
        }
    }
}
