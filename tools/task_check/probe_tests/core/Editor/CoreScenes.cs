// The core family's scenes (probe_tests/core): the play loop's own behaviour, with as little game as it takes.
using System;
using System.Linq;
using Object = UnityEngine.Object;
using UnityEditor;
using UnityEditor.Build;
using UnityEditor.Build.Reporting;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.SceneManagement;
using UnityEngine.UI;

namespace ProbeTests.Core
{
    public static class CoreScenes
    {
        const string Made = "Assets/ProbeTests/core/Made";

        public static void Build()
        {
            if (!AssetDatabase.IsValidFolder(Made)) AssetDatabase.CreateFolder("Assets/ProbeTests/core", "Made");
            First();
            Clock();
            Stage();
            Who();
            Bodies();
            // First.unity is the game's first build scene: what a play without a scene of its own opens, and what
            // wakes up before any play's scene is asked for
            var first = Made + "/First.unity";
            var scenes = EditorBuildSettings.scenes.Where(s => s.path != first).ToList();
            scenes.Insert(0, new EditorBuildSettingsScene(first, true));
            EditorBuildSettings.scenes = scenes.ToArray();
            Foreign();
        }

        // The Clock scene built as a project builds its own game: a company name of its own, not the checker's. The
        // player has the probe in it (the package is in the project), as when someone copies the package into a
        // real project: started with -taskProbe it must leave that game's saved data alone.
        static void Foreign()
        {
            var company = PlayerSettings.companyName;
            var backend = PlayerSettings.GetScriptingBackend(NamedBuildTarget.Standalone);
            var stripping = PlayerSettings.GetManagedStrippingLevel(NamedBuildTarget.Standalone);
            try
            {
                PlayerSettings.companyName = "ProbeTestsForeignCo";
                // whatever another family set for the project (IL2CPP, stripping): this build needs neither the
                // IL2CPP module nor the linker's minutes
                PlayerSettings.SetScriptingBackend(NamedBuildTarget.Standalone, ScriptingImplementation.Mono2x);
                PlayerSettings.SetManagedStrippingLevel(NamedBuildTarget.Standalone, ManagedStrippingLevel.Disabled);
                var report = BuildPipeline.BuildPlayer(new BuildPlayerOptions
                {
                    scenes = new[] { Made + "/Clock.unity" }, locationPathName = "Build/ProbeTestsForeign/Game.exe",
                    target = BuildTarget.StandaloneWindows64, options = BuildOptions.None,
                });
                if (report.summary.result != BuildResult.Succeeded) throw new Exception("the foreign player didn't build: " + report.summary.result);
            }
            finally
            {
                PlayerSettings.companyName = company;
                PlayerSettings.SetScriptingBackend(NamedBuildTarget.Standalone, backend);
                PlayerSettings.SetManagedStrippingLevel(NamedBuildTarget.Standalone, stripping);
            }
        }

        static Scene New() => EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);

        static GameObject Camera(string name, Vector3 at, bool main = true)
        {
            var camera = new GameObject(name);
            if (main) camera.tag = "MainCamera";
            camera.AddComponent<Camera>();
            camera.transform.position = at;
            return camera;
        }

        static void Sun()
        {
            var light = new GameObject("Sun");
            light.AddComponent<Light>().type = LightType.Directional;
            light.transform.rotation = Quaternion.Euler(50f, -30f, 0f);
        }

        static GameObject Cube(string name, Vector3 at, string tag = null)
        {
            var cube = GameObject.CreatePrimitive(PrimitiveType.Cube);
            cube.name = name;
            cube.transform.position = at;
            if (tag != null) cube.tag = tag;
            return cube;
        }

        // The game's first scene: one object that says what it lives through.
        static void First()
        {
            var scene = New();
            Camera("Main Camera", new Vector3(0f, 1f, -5f));
            new GameObject("FirstMarker").AddComponent<CoreFirst>();
            EditorSceneManager.SaveScene(scene, Made + "/First.unity");
        }

        // A hero that moves 1 m along x every second of game time, a camera, a light, and the director of the plays
        // that quit, load scenes and write saved data.
        static void Clock()
        {
            var scene = New();
            Camera("Main Camera", new Vector3(0f, 2f, -8f));
            Sun();
            Cube("Hero", Vector3.zero, "Player").AddComponent<CoreMover>();
            new GameObject("Director").AddComponent<CoreDirector>();
            EditorSceneManager.SaveScene(scene, Made + "/Clock.unity");
        }

        // A hero that walks by the keyboard (and drifts along x when asked), a camera that follows it in LateUpdate,
        // two posts to be teleported to, a button, and a magenta badge of UI in the frame's top left corner.
        static void Stage()
        {
            var scene = New();
            Camera("Main Camera", new Vector3(0f, 3f, -6f)).AddComponent<CoreFollow>();
            Sun();
            Cube("Hero", Vector3.zero, "Player").AddComponent<CoreWalker>();
            Cube("Post", new Vector3(10f, 0f, 5f));
            Cube("Post", new Vector3(40f, 0f, 40f));

            var canvas = new GameObject("Canvas", typeof(Canvas), typeof(GraphicRaycaster));
            canvas.GetComponent<Canvas>().renderMode = RenderMode.ScreenSpaceOverlay;
            var badge = new GameObject("Badge", typeof(Image));
            badge.transform.SetParent(canvas.transform, false);
            badge.GetComponent<Image>().color = new Color(1f, 0f, 1f, 1f);
            Corner(badge.GetComponent<RectTransform>(), new Vector2(0f, 1f), new Vector2(96f, 54f));
            var button = new GameObject("PushButton", typeof(Image), typeof(Button), typeof(CoreButton));
            button.transform.SetParent(canvas.transform, false);
            Corner(button.GetComponent<RectTransform>(), new Vector2(1f, 0f), new Vector2(96f, 54f));
            EditorSceneManager.SaveScene(scene, Made + "/Stage.unity");
        }

        static void Corner(RectTransform rect, Vector2 corner, Vector2 size)
        {
            rect.anchorMin = rect.anchorMax = rect.pivot = corner;
            rect.anchoredPosition = Vector2.zero;
            rect.sizeDelta = size;
        }

        // Three players the game moves by itself (CoreStroll), each through another kind of body, standing on ground
        // of their own kind: a CharacterController, a Rigidbody, a Rigidbody2D.
        static void Bodies()
        {
            var scene = New();
            Camera("Main Camera", new Vector3(10f, 3f, -14f));
            Sun();
            var ground = Cube("Ground", new Vector3(0f, -0.5f, 0f));
            ground.transform.localScale = new Vector3(200f, 1f, 20f);
            var ground2 = new GameObject("Ground2D");
            ground2.transform.position = new Vector3(0f, -0.5f, 0f);
            ground2.AddComponent<BoxCollider2D>().size = new Vector2(200f, 1f);

            var walker = GameObject.CreatePrimitive(PrimitiveType.Capsule);
            walker.name = "BodyCc";
            Object.DestroyImmediate(walker.GetComponent<Collider>());
            walker.transform.position = new Vector3(0f, 1.08f, 0f);
            walker.AddComponent<CharacterController>();
            walker.AddComponent<CoreStroll>();

            var box = Cube("BodyRb", new Vector3(10f, 0.5f, 0f));
            box.AddComponent<Rigidbody>();
            box.AddComponent<CoreStroll>();

            var flat = Cube("Body2d", new Vector3(20f, 0.5f, 0f));
            Object.DestroyImmediate(flat.GetComponent<Collider>());
            flat.AddComponent<BoxCollider2D>();
            flat.AddComponent<Rigidbody2D>();
            flat.AddComponent<CoreStroll>();
            EditorSceneManager.SaveScene(scene, Made + "/Bodies.unity");
        }

        // Every kind of object the player can be, in the order the probe looks for them, and a director that takes
        // the first ones away when asked.
        static void Who()
        {
            var scene = New();
            new GameObject("Director").AddComponent<CoreWho>();
            // two tagged objects under one parent: the order of siblings is the scene's own (a player lists a scene's
            // roots in the order of the scene file, which no window shows)
            var crowd = new GameObject("Crowd");
            Cube("Tagged", new Vector3(1f, 0f, 0f), "Player").transform.SetParent(crowd.transform, true);
            Cube("Tagged2", new Vector3(2f, 0f, 0f), "Player").transform.SetParent(crowd.transform, true);
            Cube("Inputter", new Vector3(3f, 0f, 0f)).AddComponent<UnityEngine.InputSystem.PlayerInput>();
            Cube("Body", new Vector3(4f, 0f, 0f)).AddComponent<CharacterController>();
            var rig = new GameObject("Rig");
            rig.transform.position = new Vector3(5f, 0f, 0f);
            var eye = Camera("Main Camera", new Vector3(5f, 2f, -8f));
            eye.transform.SetParent(rig.transform, true);
            eye.transform.rotation = Quaternion.Euler(10f, 200f, 0f);
            var high = Camera("High", new Vector3(0f, 9f, 0f), false);
            high.GetComponent<Camera>().depth = 5f;
            high.SetActive(false);
            Sun();
            EditorSceneManager.SaveScene(scene, Made + "/Who.unity");
        }
    }
}
