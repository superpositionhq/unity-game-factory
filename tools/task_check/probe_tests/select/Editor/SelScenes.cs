// The select family's scenes (probe_tests/select): objects for every key of an object select and its points, the
// orders matches come in (scenes, roots, children, objects made at run time, several components on one object), a
// member of every kind for prop: paths, and a crowd for the cost plays.
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.SceneManagement;

namespace ProbeTests.Select
{
    public static class SelScenes
    {
        const string Made = "Assets/ProbeTests/select/Made";

        public static void Build()
        {
            if (!AssetDatabase.IsValidFolder(Made)) AssetDatabase.CreateFolder("Assets/ProbeTests/select", "Made");
            var layer = TagAndLayer();
            Lab(layer);
            Side();
            Big();
        }

        /// <summary>The tag SelTag and a user layer named SelLayer (the first free one); its index.</summary>
        static int TagAndLayer()
        {
            var manager = new SerializedObject(AssetDatabase.LoadAllAssetsAtPath("ProjectSettings/TagManager.asset")[0]);
            var tags = manager.FindProperty("tags");
            var have = false;
            for (var i = 0; i < tags.arraySize; i++) have |= tags.GetArrayElementAtIndex(i).stringValue == "SelTag";
            if (!have)
            {
                tags.InsertArrayElementAtIndex(tags.arraySize);
                tags.GetArrayElementAtIndex(tags.arraySize - 1).stringValue = "SelTag";
            }
            var layers = manager.FindProperty("layers");
            var at = -1;
            for (var i = 8; i < 32 && at < 0; i++) if (layers.GetArrayElementAtIndex(i).stringValue == "SelLayer") at = i;
            for (var i = 8; i < 32 && at < 0; i++) if (string.IsNullOrEmpty(layers.GetArrayElementAtIndex(i).stringValue)) at = i;
            layers.GetArrayElementAtIndex(at).stringValue = "SelLayer";
            manager.ApplyModifiedProperties();
            return at;
        }

        static Scene New() => EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);

        static GameObject Empty(string name, Vector3 at, Transform parent = null)
        {
            var go = new GameObject(name);
            go.transform.SetParent(parent, false);
            go.transform.position = at;
            return go;
        }

        static GameObject Cube(string name, Vector3 at, Transform parent = null)
        {
            var go = GameObject.CreatePrimitive(PrimitiveType.Cube);
            go.name = name;
            go.transform.SetParent(parent, false);
            go.transform.position = at;
            return go;
        }

        static GameObject Lamp(string name, Vector3 at, float intensity, bool enabled)
        {
            var lamp = Empty(name, at);
            var bulb = Empty(name + "_Bulb", at + Vector3.up, lamp.transform);
            var light = bulb.AddComponent<Light>();
            light.type = LightType.Point;
            light.range = 3f;
            light.intensity = intensity;
            light.enabled = enabled;
            return lamp;
        }

        // Everything the select plays read. Roots are made in the order the Hierarchy shows them; a test that needs an
        // order the player decides (the roots of one scene) reads it from the saved scene file.
        static void Lab(int layer)
        {
            var scene = New();
            var camera = Empty("Main Camera", new Vector3(0f, 6f, -14f));
            camera.tag = "MainCamera";
            camera.transform.rotation = Quaternion.Euler(20f, 0f, 0f);
            camera.AddComponent<Camera>();
            camera.AddComponent<AudioListener>();
            var sun = Empty("Sun", new Vector3(0f, 10f, 0f));
            sun.AddComponent<Light>().type = LightType.Directional;
            sun.transform.rotation = Quaternion.Euler(50f, -30f, 0f);
            var hero = Cube("SelHero", new Vector3(0f, 0.5f, 0f));
            hero.tag = "Player";

            // the roots of one scene, made one after the other; UI roots (a RectTransform, one a canvas) and instances of a
            // prefab, which the player's root list may place by other rules
            foreach (var name in new[] { "Root_A", "Root_B", "Root_C", "Root_D" })
                Empty(name, new Vector3(30f, 0f, 0f)).AddComponent<SelRootInfo>();
            new GameObject("Ui_Rect", typeof(RectTransform)).AddComponent<SelRootInfo>();
            new GameObject("Ui_Canvas", typeof(Canvas)).AddComponent<SelRootInfo>();
            var prefab = RootPrefab();
            foreach (var name in new[] { "Pre_A", "Pre_B", "Pre_C", "Pre_D" })
                ((GameObject)PrefabUtility.InstantiatePrefab(prefab, scene)).name = name;

            // component: two types of one name, an interface, a base type, a nested type
            var twins = Empty("Twins", new Vector3(-20f, 0f, 0f));
            Empty("TwinA", new Vector3(-20f, 0f, 0f), twins.transform).AddComponent<SelTwin>();
            Empty("TwinB", new Vector3(-20f, 0f, 1f), twins.transform).AddComponent<Other.SelTwin>();
            var coins = Empty("Coins", new Vector3(-22f, 0f, 0f));
            Empty("Coin1", new Vector3(-22f, 0f, 0f), coins.transform).AddComponent<SelCoin>();
            Empty("Coin2", new Vector3(-22f, 0f, 1f), coins.transform).AddComponent<SelCoin>().value = 2;
            Empty("Based", new Vector3(-24f, 0f, 0f)).AddComponent<SelBase>();
            Empty("Derived", new Vector3(-24f, 0f, 1f)).AddComponent<SelDerived>();
            Empty("Nester", new Vector3(-26f, 0f, 0f)).AddComponent<SelNest>();

            // tag, layer, name
            Empty("Tagged1", new Vector3(-28f, 0f, 0f)).tag = "SelTag";
            Empty("Tagged2", new Vector3(-28f, 0f, 1f)).tag = "SelTag";
            Empty("Layered", new Vector3(-30f, 0f, 0f)).layer = layer;
            var x = 50f;
            foreach (var name in new[] { "Lamp (1)", "Lamp.Post", "LampXPost", "lamp_low", "LAMP_HIGH", "Snö☃" })
                Empty(name, new Vector3(x++, 0f, 0f));

            // inactive objects
            var sleeper = Empty("Sleeper", new Vector3(-32f, 0f, 0f));
            Empty("SleeperKid", new Vector3(-32f, 0f, 1f), sleeper.transform);
            sleeper.SetActive(false);
            var waker = Empty("Waker", new Vector3(-34f, 0f, 0f));
            Empty("Napper", new Vector3(-34f, 0f, 1f), waker.transform).SetActive(false);

            // near: around (10, 0, 0), the player's point with an offset, the camera's, an object's
            Empty("Near_0", new Vector3(10f, 0f, 0f));
            Empty("Near_1", new Vector3(10f, 1f, 0f));
            Empty("Near_2", new Vector3(10f, 2.5f, 0f));
            Empty("Near_3", new Vector3(12f, 0f, 0f));
            Empty("Near_Anchor", new Vector3(20f, 0f, 0f));
            Empty("NearObj", new Vector3(20.5f, 0f, 0f));
            var mark = camera.transform.position + camera.transform.forward * 10f;
            Empty("CamMark", mark);

            // has: lit, visible, a part far from its object, an object with nothing but its transform, bodies
            Lamp("Light_On", new Vector3(-40f, 0f, 0f), 1f, true);
            Lamp("Light_Off", new Vector3(-40f, 0f, 4f), 0f, true);
            Lamp("Light_Dark", new Vector3(-40f, 0f, 8f), 1f, false);
            var shown = Empty("Shown", new Vector3(-44f, 0f, 0f));
            Cube("Shown_Mesh", new Vector3(-44f, 0f, 0f), shown.transform);
            var unshown = Empty("Unshown", new Vector3(-44f, 0f, 4f));
            Cube("Unshown_Mesh", new Vector3(-44f, 0f, 4f), unshown.transform).GetComponent<Renderer>().enabled = false;
            var holder = Empty("Holder", new Vector3(0f, 0f, 30f));
            Cube("Far_Part", new Vector3(0f, 0f, 40f), holder.transform);
            Empty("EmptyNear", new Vector3(0f, 0f, 50f));
            var carrier = Empty("Carrier", new Vector3(-48f, 0f, 0f));
            Empty("CarrierLamp", new Vector3(-48f, 1f, 0f), carrier.transform).AddComponent<Light>().intensity = 1f;
            Body("Crate", new Vector3(0f, 0f, 60f), false, true);
            Body("Kinematic", new Vector3(3f, 0f, 60f), true, true);
            Body("Breakable", new Vector3(6f, 0f, 60f), false, false);
            var flat = Empty("Flat2D", new Vector3(9f, 0f, 60f));
            var flatBody = Empty("Flat2D_Body", new Vector3(9f, 0f, 60f), flat.transform).AddComponent<Rigidbody2D>();
            flatBody.gravityScale = 0f;
            var stiff = Empty("Kinematic2D", new Vector3(12f, 0f, 60f));
            Empty("Kinematic2D_Body", new Vector3(12f, 0f, 60f), stiff.transform).AddComponent<Rigidbody2D>().bodyType = RigidbodyType2D.Kinematic;
            var statue = Cube("Statue", new Vector3(15f, 0f, 60f));
            statue.isStatic = true;
            Cube("Pawn", new Vector3(18f, 0f, 60f));

            // the order of children; several components of one type on one object
            var family = Empty("Family", new Vector3(-50f, 0f, 0f));
            foreach (var name in new[] { "Kid_C", "Kid_A", "Kid_B" }) Empty(name, new Vector3(-50f, 0f, 0f), family.transform);
            var two = Empty("TwoBoxes", new Vector3(-55f, 0f, 0f));
            two.AddComponent<BoxCollider>().size = Vector3.one;
            two.AddComponent<BoxCollider>().size = Vector3.one * 3f;

            // more matches than the rows hold: Fill_000 ... Fill_299 at x = 0 ... 299
            var fillers = Empty("Fillers", new Vector3(0f, -50f, 0f));
            for (var i = 0; i < 300; i++) Empty("Fill_" + i.ToString("D3"), new Vector3(i, -50f, 0f), fillers.transform);

            // prop: a member of every kind; a component in a descendant; reads that must not copy an asset
            var doomed = Empty("Doomed", new Vector3(-60f, 0f, 0f));
            var props = Empty("Props", new Vector3(-62f, 0f, 0f)).AddComponent<SelProps>();
            props.target = hero;
            props.gone = doomed;
            Empty("PropsKid", new Vector3(-62f, 0f, 1f), props.transform).AddComponent<SelBase>().level = 5;
            var painted = Cube("Painted", new Vector3(-64f, 0f, 0f));
            painted.AddComponent<SelPaint>();
            Empty("TextLike", new Vector3(-66f, 0f, 0f)).AddComponent<SelTextLike>().fontSharedMaterial = painted.GetComponent<Renderer>().sharedMaterial;

            // what changes during a play: the DontDestroyOnLoad scene, an additive scene, clones, a new root, a reparent
            var keeper = Empty("Keeper", new Vector3(-70f, 0f, 0f));
            keeper.AddComponent<SelKeeper>();
            keeper.AddComponent<SelRootInfo>();
            var template = Empty("CoinT", new Vector3(-72f, 0f, 0f));
            template.AddComponent<SelCoin>();
            var mover = Empty("Mover", new Vector3(-74f, 0f, 0f));
            var moved = Empty("Moved_Child", new Vector3(-74f, 0f, 1f), mover.transform);
            moved.AddComponent<SelRootInfo>();
            var director = Empty("Director", new Vector3(-76f, 0f, 0f)).AddComponent<SelDirector>();
            director.template = template;
            director.child = moved.transform;
            Empty("Locale", new Vector3(-78f, 0f, 0f)).AddComponent<SelLocale>();
            EditorSceneManager.SaveScene(scene, Made + "/SelLab.unity");
        }

        /// <summary>A prefab whose root carries SelRootInfo, with a child: SelLab holds instances of it as roots.</summary>
        static GameObject RootPrefab()
        {
            var root = new GameObject("SelRootPrefab", typeof(SelRootInfo));
            new GameObject("SelRootPrefab_Kid").transform.SetParent(root.transform, false);
            var prefab = PrefabUtility.SaveAsPrefabAsset(root, Made + "/SelRootPrefab.prefab");
            Object.DestroyImmediate(root);
            return prefab;
        }

        /// <summary>An object whose child carries a Rigidbody without gravity (kinematic or not), the child active or not.</summary>
        static void Body(string name, Vector3 at, bool kinematic, bool active)
        {
            var root = Empty(name, at);
            var body = Cube(name + "_Body", at, root.transform);
            var rb = body.AddComponent<Rigidbody>();
            rb.useGravity = false;
            rb.isKinematic = kinematic;
            body.SetActive(active);
        }

        // The scene SelDirector loads additively.
        static void Side()
        {
            var scene = New();
            Empty("Side_Root", new Vector3(-80f, 0f, 0f)).AddComponent<SelRootInfo>();
            Empty("SideCoin", new Vector3(-80f, 0f, 2f)).AddComponent<SelCoin>();
            EditorSceneManager.SaveScene(scene, Made + "/SelSide.unity");
        }

        // The cost plays' scene: a camera, a light, the crowd (made when it wakes) and the timers around the probe's two
        // halves.
        static void Big()
        {
            var scene = New();
            var camera = Empty("Main Camera", new Vector3(50f, 30f, -40f));
            camera.tag = "MainCamera";
            camera.transform.rotation = Quaternion.Euler(30f, 0f, 0f);
            camera.AddComponent<Camera>();
            Empty("Sun", new Vector3(0f, 10f, 0f)).AddComponent<Light>().type = LightType.Directional;
            Empty("Crowd", Vector3.zero).AddComponent<SelCrowd>();
            var timer = Empty("Timer", Vector3.zero);
            timer.AddComponent<SelEarlyBefore>();
            timer.AddComponent<SelEarlyAfter>();
            timer.AddComponent<SelLateBefore>();
            timer.AddComponent<SelLateAfter>();
            EditorSceneManager.SaveScene(scene, Made + "/SelBig.unity");
        }
    }
}
