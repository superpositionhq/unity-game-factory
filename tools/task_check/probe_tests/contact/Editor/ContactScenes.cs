// The contact family's scenes (probe_tests/contact): a duel to stage, and a scene whose time stops.
using System.Linq;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.AI;
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
            Bodies();
            Flat();
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
            Skinned();
            EditorSceneManager.SaveScene(scene, Made + "/Stops.unity");
        }

        // A skinned quad on two bones that stands still while one bone moves (ContactWiggle).
        static void Skinned()
        {
            var owner = new GameObject("Skinned");
            owner.transform.position = new Vector3(0f, 0f, 10f);
            var bones = new[] { new GameObject("Root").transform, new GameObject("Tip").transform };
            foreach (var b in bones) b.SetParent(owner.transform, false);
            bones[1].localPosition = new Vector3(0f, 1f, 0f);
            var mesh = new Mesh { name = "SkinnedQuad" };
            mesh.SetVertices(new[] { new Vector3(-0.5f, 0f, 0f), new Vector3(0.5f, 0f, 0f), new Vector3(-0.5f, 1f, 0f), new Vector3(0.5f, 1f, 0f) });
            mesh.SetTriangles(new[] { 0, 2, 1, 1, 2, 3 }, 0);
            mesh.boneWeights = new[] { 0, 0, 1, 1 }.Select(i => new BoneWeight { boneIndex0 = i, weight0 = 1f }).ToArray();
            mesh.bindposes = bones.Select(b => b.worldToLocalMatrix * owner.transform.localToWorldMatrix).ToArray();
            mesh.RecalculateNormals();
            mesh.RecalculateBounds();
            AssetDatabase.CreateAsset(mesh, Made + "/SkinnedQuad.asset");
            var skin = owner.AddComponent<SkinnedMeshRenderer>();
            skin.sharedMesh = mesh;
            skin.bones = bones;
            skin.rootBone = bones[0];
            skin.updateWhenOffscreen = true;
            owner.AddComponent<ContactWiggle>().bone = bones[1];
        }

        // What a pin holds through its own body: a cube under gravity, and an agent walking a NavMesh it bakes over
        // the ground (the ground alone is on the layer it bakes). And two damage entries that say nothing: one that
        // throws, one that returns no number.
        static void Bodies()
        {
            var scene = New();
            Camera();
            var ground = Cube("Ground", new Vector3(0f, -0.5f, 0f));
            ground.transform.localScale = new Vector3(200f, 1f, 200f);
            ground.layer = LayerMask.NameToLayer("Water");
            Cube("Hero", new Vector3(0f, 0.5f, 0f), "Player");
            Cube("Body", new Vector3(3f, 0.5f, 5f)).AddComponent<Rigidbody>();
            var walker = Cube("Agent", new Vector3(-3f, 0.5f, 5f));
            var agent = walker.AddComponent<NavMeshAgent>();
            agent.enabled = false;  // on once its NavMesh is there (ContactAgent)
            agent.baseOffset = 0.5f;
            agent.radius = 0.5f;
            agent.height = 1f;
            agent.speed = 2f;
            agent.acceleration = 100f;
            walker.AddComponent<ContactAgent>();
            Cube("Thrower", new Vector3(-30f, 0.5f, 0f)).AddComponent<ContactThrower>();
            Cube("Mute", new Vector3(-40f, 0.5f, 0f)).AddComponent<ContactMute>();
            EditorSceneManager.SaveScene(scene, Made + "/Bodies.unity");
        }

        // A 2D game: a hero that faces -x (its scale in x is -1) on a 2D floor, and a foe 2 m deep that walks along x.
        static void Flat()
        {
            var scene = New();
            Camera();
            var floor = new GameObject("Floor");
            floor.transform.position = new Vector3(0f, -0.5f, 0f);
            floor.AddComponent<BoxCollider2D>().size = new Vector2(200f, 1f);
            var hero = new GameObject("Hero") { tag = "Player" };
            hero.transform.position = new Vector3(0f, 0.5f, 0f);
            hero.transform.localScale = new Vector3(-1f, 1f, 1f);
            hero.AddComponent<BoxCollider2D>();
            var foe = new GameObject("Foe2D");
            foe.transform.position = new Vector3(5f, 0.5f, 2f);
            foe.AddComponent<BoxCollider2D>();
            foe.AddComponent<ContactFoe>();
            EditorSceneManager.SaveScene(scene, Made + "/Flat.unity");
        }
    }
}
