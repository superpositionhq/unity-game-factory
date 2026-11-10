using System;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Rendering.Universal;

namespace ProbeTests.Lighting
{
    /// <summary>GradeLab's player: stands still until frame 180 (6 s), then walks +z at 2 m/s into the local volume, by
    /// frames. With -gradescript its camera's volumes are updated by script only: URP makes the camera's stack once,
    /// as soon as its volume framework is up, and renders with it. With -gradeexposed the global grade gets a post
    /// exposure of 1 before the first frame.</summary>
    public sealed class LightGradeWalker : MonoBehaviour
    {
        public Camera view;
        public VolumeProfile global;
        Vector3 origin;
        int frames;
        bool scripted;

        void Awake()
        {
            origin = transform.position;
            scripted = Array.IndexOf(Environment.GetCommandLineArgs(), "-gradescript") >= 0;
            if (Array.IndexOf(Environment.GetCommandLineArgs(), "-gradeexposed") >= 0 && global.TryGet<ColorAdjustments>(out var adjust))
                adjust.postExposure.Override(1f);
            Script();
        }

        /// <summary>The camera's volumes by script only, once URP has set up its volume framework (before, URP can't make
        /// the camera's stack).</summary>
        void Script()
        {
            if (!scripted || !VolumeManager.instance.isInitialized) return;
            scripted = false;
            view.SetVolumeFrameworkUpdateMode(VolumeFrameworkUpdateMode.ViaScripting);
        }

        void Update()
        {
            Script();
            frames++;
            transform.position = origin + Vector3.forward * (2f * Mathf.Max(0, frames - 180) / 30f);
        }
    }
}
