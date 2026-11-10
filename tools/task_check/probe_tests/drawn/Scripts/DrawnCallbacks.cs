using System;
using UnityEngine;
using UnityEngine.Rendering;

namespace ProbeTests.Drawn
{
    /// <summary>With -drawnCallback, a game whose camera callbacks get in the way of the probe's render (it knows the
    /// probe's camera by its name): from 2.75 to 3.75 s of play it throws when it sees that camera; from 5.75 to 6.75 s it
    /// switches the sun and fog back on inside that render; from 8.75 s it destroys a renderer the render is drawing
    /// (Victim) inside it; at 10.75 s it destroys the probe's camera object itself, as a "destroy everything" restart
    /// that finds hidden objects too would. The counters say what it did.</summary>
    public sealed class DrawnCallbacks : MonoBehaviour
    {
        public Light Sun;
        public GameObject Victim;
        public int thrown, changed, destroyed, rigs;
        bool on;

        void OnEnable()
        {
            on = Array.IndexOf(Environment.GetCommandLineArgs(), "-drawnCallback") >= 0;
            if (on) RenderPipelineManager.beginCameraRendering += Begin;
        }

        void OnDisable()
        {
            if (on) RenderPipelineManager.beginCameraRendering -= Begin;
        }

        static bool Probes(Camera camera) => camera != null && camera.name == "TaskProbe.Render";

        void Begin(ScriptableRenderContext context, Camera camera)
        {
            if (!Probes(camera)) return;
            var t = Time.timeSinceLevelLoad;
            if (t >= 2.75f && t < 3.75f)
            {
                thrown++;
                throw new InvalidOperationException("DrawnCallbacks: the game's callback threw at the probe's camera");
            }
            if (t >= 5.75f && t < 6.75f)
            {
                changed++;
                if (Sun != null) Sun.enabled = true;
                RenderSettings.fog = true;
            }
            // in the render of the victim's own place: a renderer the render is drawing, gone in the middle of it
            if (t >= 8.75f && Victim != null && (camera.transform.position - Victim.transform.position).sqrMagnitude < 9f)
            {
                destroyed++;
                DestroyImmediate(Victim);
            }
        }

        void Update()
        {
            if (!on || rigs > 0 || Time.timeSinceLevelLoad < 10.75f) return;
            foreach (var c in Resources.FindObjectsOfTypeAll<Camera>())
                if (Probes(c) && c.gameObject.scene.IsValid())
                {
                    Destroy(c.gameObject);
                    rigs++;
                }
        }
    }
}
