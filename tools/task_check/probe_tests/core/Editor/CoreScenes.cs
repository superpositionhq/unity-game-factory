// The core family's scenes (probe_tests/core): the play loop's own behaviour, with as little game as it takes.
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

namespace ProbeTests.Core
{
    public static class CoreScenes
    {
        const string Made = "Assets/ProbeTests/core/Made";

        public static void Build()
        {
            if (!AssetDatabase.IsValidFolder(Made)) AssetDatabase.CreateFolder("Assets/ProbeTests/core", "Made");
            Clock();
        }

        // A hero that moves 1 m along x every second of play, a camera behind it, a light.
        static void Clock()
        {
            var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            var camera = new GameObject("Main Camera") { tag = "MainCamera" };
            camera.AddComponent<Camera>();
            camera.transform.position = new Vector3(0f, 2f, -8f);
            var light = new GameObject("Sun");
            light.AddComponent<Light>().type = LightType.Directional;
            light.transform.rotation = Quaternion.Euler(50f, -30f, 0f);
            var hero = GameObject.CreatePrimitive(PrimitiveType.Cube);
            hero.name = "Hero";
            hero.tag = "Player";
            hero.AddComponent<CoreMover>();
            EditorSceneManager.SaveScene(scene, Made + "/Clock.unity");
        }
    }
}
