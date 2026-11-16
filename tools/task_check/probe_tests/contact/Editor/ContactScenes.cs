// The contact family's scenes (probe_tests/contact): a duel to stage, and a scene whose time stops.
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.SceneManagement;

namespace ProbeTests.Contact
{
    public static class ContactScenes
    {
        const string Made = "Assets/ProbeTests/contact/Made";

        public static void Build()
        {
            if (!AssetDatabase.IsValidFolder(Made)) AssetDatabase.CreateFolder("Assets/ProbeTests/contact", "Made");
            Duel();
            Stops();
        }

        static Scene New() => EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);

        static void Camera()
        {
            var camera = new GameObject("Main Camera") { tag = "MainCamera" };
            camera.AddComponent<Camera>();
            camera.transform.position = new Vector3(0f, 3f, -8f);
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

        // A hero facing +z on flat ground, two live foes ahead of it that walk along x, a dead one nearer than both,
        // and a crate that takes no damage.
        static void Duel()
        {
            var scene = New();
            Camera();
            Cube("Ground", new Vector3(0f, -0.5f, 0f)).transform.localScale = new Vector3(200f, 1f, 200f);
            Cube("Hero", new Vector3(0f, 0.5f, 0f), "Player").AddComponent<ContactHero>();
            Cube("FoeNear", new Vector3(0f, 0.5f, 6f)).AddComponent<ContactFoe>();
            Cube("FoeFar", new Vector3(0f, 0.5f, 12f)).AddComponent<ContactFoe>();
            var fallen = Cube("FoeDead", new Vector3(2f, 0.5f, 3f)).AddComponent<ContactFoe>();
            fallen.dead = true;
            fallen.walk = 0f;
            Cube("Crate", new Vector3(-3f, 0.5f, 0f));
            // far from the fight: an entry with optional parameters after the contract's two, and one that isn't the
            // contract's
            Cube("Armored", new Vector3(-30f, 0.5f, 0f)).AddComponent<ContactArmored>();
            Cube("Odd", new Vector3(-40f, 0.5f, 0f)).AddComponent<ContactOdd>();
            EditorSceneManager.SaveScene(scene, Made + "/Duel.unity");
        }

        // An object that stops for six frames of its own, and a clock that slows the game's time, then stops it.
        static void Stops()
        {
            var scene = New();
            Camera();
            Cube("Hero", Vector3.zero, "Player");
            var stutter = Cube("Stutter", new Vector3(0f, 0f, 5f)).AddComponent<ContactStutter>();
            var pip = Cube("Pip", new Vector3(0f, 0f, 5f));
            pip.transform.SetParent(stutter.transform, true);
            pip.transform.localPosition = new Vector3(0f, -1f, 0f);
            stutter.pip = pip;
            new GameObject("Clock").AddComponent<ContactClock>();
            EditorSceneManager.SaveScene(scene, Made + "/Stops.unity");
        }
    }
}
