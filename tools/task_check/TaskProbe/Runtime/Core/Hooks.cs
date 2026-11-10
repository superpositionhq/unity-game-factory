// Where one query family uses another's work without naming it: each is set from a [ProbeInit] method, and is null when
// the family that provides it isn't there (the caller then goes without and says so).
using System;
using UnityEngine;

namespace TaskProbe
{
    /// <summary>A renderer's own light as rendered: drawn alone with every light off (ambient black, no reflections or
    /// fog), orthographic from four fixed views, HDR. `Brightest`: its brightest pixel's luminance. `Glow`: the views'
    /// luminance x pixel area over the seen bounds area, times a quarter of its bounds box's surface (m2).</summary>
    public struct RenderedGlow
    {
        public bool Ok;  // false: nothing could be rendered (no renderer facility, the object isn't drawn)
        public double Brightest;
        public double Glow;
    }

    public static class Hooks
    {
        /// <summary>lit and glow of a mesh renderer or a particle system whose material can't be read from its
        /// properties (contract section 3, "as rendered"). Set by the drawn renderer.</summary>
        public static Func<Renderer, RenderedGlow> GlowRender;
    }
}
