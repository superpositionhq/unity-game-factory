using UnityEngine;
using UnityEngine.Rendering;

namespace ProbeTests.Drawn
{
    /// <summary>What the game can see of the probe's renders, on an object behind the player's camera (its shadows off,
    /// so only a camera that draws it sees it): how often it became visible or invisible, how often it was about to be
    /// rendered, in how many frames it is visible after the probe's samples; how many cameras the game counts and finds,
    /// whether the main camera is the game's; and how many renders of another camera the game's callbacks saw.</summary>
    [DefaultExecutionOrder(32020)]
    public sealed class DrawnWatcher : MonoBehaviour
    {
        public int becameVisible, becameInvisible, willRender, visibleFrames;
        public int allCameras, foundCameras, mainIsGame, otherRenders;
        public string otherCamera = "";

        void OnEnable() => RenderPipelineManager.beginCameraRendering += Begin;
        void OnDisable() => RenderPipelineManager.beginCameraRendering -= Begin;

        void Begin(ScriptableRenderContext context, Camera camera)
        {
            if (camera == null || camera.CompareTag("MainCamera")) return;
            otherRenders++;
            otherCamera = camera.name;
        }

        void OnBecameVisible() => becameVisible++;
        void OnBecameInvisible() => becameInvisible++;
        void OnWillRenderObject() => willRender++;

        void LateUpdate()
        {
            if (GetComponent<Renderer>().isVisible) visibleFrames++;
            allCameras = Camera.allCamerasCount;
            foundCameras = FindObjectsByType<Camera>(FindObjectsInactive.Include, FindObjectsSortMode.None).Length;
            var main = Camera.main;
            mainIsGame = main != null && main.name == "Main Camera" ? 1 : 0;
        }
    }
}
