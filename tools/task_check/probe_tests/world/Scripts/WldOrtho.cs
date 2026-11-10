using System;
using UnityEngine;

namespace ProbeTests.World
{
    /// <summary>With the player argument -wldOrtho its camera is orthographic.</summary>
    public sealed class WldOrtho : MonoBehaviour
    {
        void Awake()
        {
            if (Array.IndexOf(Environment.GetCommandLineArgs(), "-wldOrtho") >= 0) GetComponent<Camera>().orthographic = true;
        }
    }
}
