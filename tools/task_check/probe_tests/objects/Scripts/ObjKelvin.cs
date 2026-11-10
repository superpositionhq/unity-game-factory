using UnityEngine;
using UnityEngine.Rendering;

namespace ProbeTests.Objects
{
    // The colour the engine gives its Light's colour temperature, and whether the pipeline lights with it: what a Light's
    // glow is checked against (read with prop:ObjKelvin.rgb.r, prop:ObjKelvin.uses).
    public class ObjKelvin : MonoBehaviour
    {
        public Color rgb => Mathf.CorrelatedColorTemperatureToRGB(GetComponent<Light>().colorTemperature);
        public bool uses => GraphicsSettings.lightsUseColorTemperature;
    }
}
