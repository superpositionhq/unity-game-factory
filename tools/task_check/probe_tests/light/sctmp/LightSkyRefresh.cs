using UnityEngine;

namespace ProbeTests.Lighting
{
    /// <summary>SkyLab: a scene saved in skybox ambient mode and never baked; at frame `at` the environment lighting is
    /// made from the skybox at run time (DynamicGI.UpdateEnvironment).</summary>
    public sealed class LightSkyRefresh : MonoBehaviour
    {
        public int at = 60;
        int frames;

        void Update()
        {
            if (++frames == at) DynamicGI.UpdateEnvironment();
        }
    }
}
