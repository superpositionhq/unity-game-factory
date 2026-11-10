using System;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Rendering.Universal;

namespace ProbeTests.Ui
{
    /// <summary>The Grey scene's switches: -uipost turns the main camera's post-processing and the exposure volume on;
    /// -uiquit quits the game at 1 s, in the frame of a sample, before the probe takes it.</summary>
    public sealed class UiGrey : MonoBehaviour
    {
        public Volume volume;
        int frames;
        bool quit;

        void Awake()
        {
            var args = Environment.GetCommandLineArgs();
            if (Array.IndexOf(args, "-uipost") >= 0)
            {
                volume.enabled = true;
                Camera.main.GetUniversalAdditionalCameraData().renderPostProcessing = true;
            }
            quit = Array.IndexOf(args, "-uiquit") >= 0;
        }

        void LateUpdate()
        {
            if (quit && ++frames == 30) Application.Quit();
        }
    }
}
