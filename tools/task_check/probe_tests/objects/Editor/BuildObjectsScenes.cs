// Builds the objects family's test scenes from code (run with probe.py exec ObjectsTest.BuildObjectsScenes.Run):
//   Assets/Scenes/ObjTest.unity   - one of every thing the objects/components/camera/spawns/pieces/ground kinds read
//   Assets/Scenes/ObjStress.unity - 3000 cubes (colliders, emissive materials, spinners, lights) to time the sampling
using System.Collections.Generic;
using System.IO;
using UnityEditor;
using UnityEditor.Animations;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;

namespace ObjectsTest
{
    public static class BuildObjectsScenes
    {
        const string Dir = "Assets/TestMats";

        public static void Run()
        {
            Directory.CreateDirectory(Dir);
            TagsAndLayers();
            BuildTest();
            BuildStress();
            AssetDatabase.SaveAssets();
        }

        // ---------------------------------------------------------------- project setup

        static void TagsAndLayers()
        {
            var tm = new SerializedObject(AssetDatabase.LoadAllAssetsAtPath("ProjectSettings/TagManager.asset")[0]);
            var tags = tm.FindProperty("tags");
            foreach (var tag in new[] { "Lamp", "Enemy" })
            {
                var have = false;
                for (var i = 0; i < tags.arraySize; i++) have |= tags.GetArrayElementAtIndex(i).stringValue == tag;
                if (have) continue;
                tags.InsertArrayElementAtIndex(tags.arraySize);
                tags.GetArrayElementAtIndex(tags.arraySize - 1).stringValue = tag;
            }
            tm.FindProperty("layers").GetArrayElementAtIndex(8).stringValue = "Props";
            tm.ApplyModifiedProperties();
        }

        static Material Mat(string name, string shader, System.Action<Material> setup)
        {
            var path = Dir + "/" + name + ".mat";
            AssetDatabase.DeleteAsset(path);
            var m = new Material(Shader.Find(shader)) { name = name };
            setup?.Invoke(m);
            AssetDatabase.CreateAsset(m, path);
            return m;
        }

        static Material Lit(string name, Color c) => Mat(name, "Universal Render Pipeline/Lit", m => m.SetColor("_BaseColor", c));

        static Material Emissive(string name, Color emission, Texture map = null) => Mat(name, "Universal Render Pipeline/Lit", m =>
        {
            m.SetColor("_BaseColor", new Color(0.2f, 0.2f, 0.2f));
            m.EnableKeyword("_EMISSION");
            m.SetColor("_EmissionColor", emission);
            if (map != null) m.SetTexture("_EmissionMap", map);
            m.globalIlluminationFlags = MaterialGlobalIlluminationFlags.RealtimeEmissive;
        });

        static Texture2D HalfTexture()
        {
            // left half white, right half black: a mean of 0.5 (non-readable once imported: read through the blit)
            var path = Dir + "/Half.png";
            var tex = new Texture2D(64, 64, TextureFormat.RGBA32, false);
            var pixels = new Color32[64 * 64];
            for (var y = 0; y < 64; y++)
                for (var x = 0; x < 64; x++) pixels[y * 64 + x] = x < 32 ? new Color32(255, 255, 255, 255) : new Color32(0, 0, 0, 255);
            tex.SetPixels32(pixels);
            File.WriteAllBytes(path, tex.EncodeToPNG());
            Object.DestroyImmediate(tex);
            AssetDatabase.ImportAsset(path, ImportAssetOptions.ForceUpdate);
            return AssetDatabase.LoadAssetAtPath<Texture2D>(path);
        }

        static GameObject Prim(PrimitiveType type, string name, Vector3 at, Vector3 scale, Material m, bool collider = true, Transform parent = null)
        {
            var go = GameObject.CreatePrimitive(type);
            go.name = name;
            if (parent != null) go.transform.SetParent(parent, false);
            go.transform.localPosition = at;
            go.transform.localScale = scale;
            if (m != null) go.GetComponent<Renderer>().sharedMaterial = m;
            if (!collider) Object.DestroyImmediate(go.GetComponent<Collider>());
            return go;
        }

        static TimedSwitch Switch(GameObject host, GameObject target, TimedSwitch.Action action, float at)
        {
            var s = host.AddComponent<TimedSwitch>();
            s.target = target;
            s.action = action;
            s.at = at;
            return s;
        }

        // ---------------------------------------------------------------- the rich test scene

        static void BuildTest()
        {
            var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            var grey = Lit("Grey", new Color(0.5f, 0.5f, 0.5f));
            var plain = Lit("Plain", new Color(0.8f, 0.3f, 0.3f));
            var emissive = Emissive("LampEmissive", new Color(4f, 3f, 2f));
            var mapped = Emissive("LampMapped", new Color(2f, 2f, 2f), HalfTexture());
            var switchable = Emissive("LampSwitch", Color.black);
            var unlit = Mat("LampUnlit", "Universal Render Pipeline/Unlit", m => m.SetColor("_BaseColor", new Color(1f, 0.9f, 0.5f)));
            var custom = Mat("LampCustom", "Custom/ProbeTestGlow", null);
            var particle = Mat("Particle", "Universal Render Pipeline/Particles/Unlit", m => m.SetColor("_BaseColor", new Color(1f, 0.6f, 0.2f)));

            // sun and camera
            var sun = new GameObject("Sun");
            var sunLight = sun.AddComponent<Light>();
            sunLight.type = LightType.Directional;
            sunLight.intensity = 1.5f;
            sun.transform.rotation = Quaternion.Euler(50f, -30f, 0f);

            // floor (a flat 100 x 100 m slab, top at y 0) and a ramp
            Prim(PrimitiveType.Cube, "Floor", new Vector3(0f, -0.5f, 0f), new Vector3(100f, 1f, 100f), grey);
            var ramp = Prim(PrimitiveType.Cube, "Ramp", new Vector3(30f, 0f, 30f), new Vector3(6f, 1f, 10f), grey);
            ramp.transform.rotation = Quaternion.Euler(-20f, 0f, 0f);
            // a roof over a spot: ground with select Floor traces through it
            Prim(PrimitiveType.Cube, "Roof", new Vector3(-20f, 4f, -20f), new Vector3(4f, 0.2f, 4f), plain);

            // the player
            var hero = Prim(PrimitiveType.Capsule, "Hero", new Vector3(0f, 1.1f, 0f), Vector3.one, plain, false);
            hero.tag = "Player";
            hero.AddComponent<CharacterController>();
            hero.AddComponent<TestPlayer>();
            var visor = Prim(PrimitiveType.Cube, "Visor", new Vector3(0f, 0.5f, 0.5f), new Vector3(0.6f, 0.2f, 0.2f), grey, false, hero.transform);
            visor.transform.localRotation = Quaternion.Euler(0f, 30f, 0f);

            var cam = new GameObject("Main Camera");
            cam.tag = "MainCamera";
            var camera = cam.AddComponent<Camera>();
            camera.fieldOfView = 60f;
            cam.AddComponent<FollowCam>().target = hero.transform;
            cam.transform.position = new Vector3(0f, 4f, -6f);

            var wall = Prim(PrimitiveType.Cube, "Wall", new Vector3(0f, -100f, 0f), new Vector3(4f, 4f, 0.3f), plain);
            wall.AddComponent<Occluder>().target = hero.transform;

            // physics
            var crate = Prim(PrimitiveType.Cube, "Crate", new Vector3(3f, 8f, 3f), Vector3.one, plain);
            crate.AddComponent<Rigidbody>();
            var lift = Prim(PrimitiveType.Cube, "Lift", new Vector3(-3f, 0.5f, -3f), Vector3.one, plain);
            lift.AddComponent<Rigidbody>().isKinematic = true;
            lift.AddComponent<KinematicMover>();

            // a fan: its blade spins at 180 deg/s and carries a trail at its tip
            var fan = new GameObject("Fan");
            fan.transform.position = new Vector3(5f, 1.5f, -5f);
            var blade = Prim(PrimitiveType.Cube, "Blade", Vector3.zero, new Vector3(3f, 0.1f, 0.3f), plain, false, fan.transform);
            blade.AddComponent<Spinner>().degreesPerSecond = 180f;
            var tracer = new GameObject("Tracer");
            tracer.transform.SetParent(blade.transform, false);
            tracer.transform.localPosition = new Vector3(0.5f, 0f, 0f);
            var trail = tracer.AddComponent<TrailRenderer>();
            trail.time = 0.5f;
            trail.widthMultiplier = 0.1f;
            trail.sharedMaterial = particle;

            // things that go: deactivated at 3 s, renderer disabled at 3 s
            var switches = new GameObject("Switches");
            var vanisher = Prim(PrimitiveType.Cube, "Vanisher", new Vector3(-6f, 0.5f, 0f), Vector3.one, plain);
            var ghost = Prim(PrimitiveType.Cube, "Ghost", new Vector3(-6f, 0.5f, 2f), Vector3.one, plain);
            Switch(switches, vanisher, TimedSwitch.Action.Deactivate, 3f);
            Switch(switches, ghost, TimedSwitch.Action.HideRenderer, 3f);

            // lamps, a row at z 10, tagged Lamp on layer Props
            var lamps = new List<GameObject>();
            var lampLight = new GameObject("LampLight");
            lampLight.transform.position = new Vector3(-8f, 2f, 10f);
            var l1 = lampLight.AddComponent<Light>();
            l1.type = LightType.Point;
            l1.intensity = 5f;
            l1.range = 8f;
            lamps.Add(lampLight);
            lamps.Add(Prim(PrimitiveType.Cube, "LampEmissive", new Vector3(-6f, 0.5f, 10f), Vector3.one, emissive));
            lamps.Add(Prim(PrimitiveType.Sphere, "LampUnlit", new Vector3(-4f, 0.5f, 10f), Vector3.one, unlit));
            lamps.Add(Prim(PrimitiveType.Cube, "LampMapped", new Vector3(-2f, 0.5f, 10f), Vector3.one, mapped));
            var lampSwitch = Prim(PrimitiveType.Cube, "LampSwitch", new Vector3(0f, 0.5f, 10f), Vector3.one, switchable);
            lamps.Add(lampSwitch);
            Switch(switches, lampSwitch, TimedSwitch.Action.EmissionOn, 4f);
            var lampLater = new GameObject("LampLater");
            lampLater.transform.position = new Vector3(2f, 2f, 10f);
            var l2 = lampLater.AddComponent<Light>();
            l2.type = LightType.Spot;
            l2.intensity = 3f;
            l2.color = new Color(1f, 0.5f, 0.25f);
            l2.enabled = false;
            lamps.Add(lampLater);
            Switch(switches, lampLater, TimedSwitch.Action.LightOn, 4f);
            var lampOff = new GameObject("LampOff");
            lampOff.transform.position = new Vector3(3f, 2f, 10f);
            lampOff.AddComponent<Light>().intensity = 2f;
            lamps.Add(lampOff);
            Switch(switches, lampOff, TimedSwitch.Action.LightOff, 4f);
            lamps.Add(Prim(PrimitiveType.Cube, "LampCustom", new Vector3(4f, 0.5f, 10f), Vector3.one, custom));
            lamps.Add(Prim(PrimitiveType.Cube, "Dark", new Vector3(6f, 0.5f, 10f), Vector3.one, plain));
            foreach (var lamp in lamps)
            {
                lamp.tag = "Lamp";
                lamp.layer = 8;
            }

            // two bulbs, one above the other: near with a height band picks the upper one
            Prim(PrimitiveType.Sphere, "Bulb", new Vector3(8f, 0.5f, 8f), new Vector3(0.4f, 0.4f, 0.4f), emissive);
            Prim(PrimitiveType.Sphere, "Bulb", new Vector3(8f, 3f, 8f), new Vector3(0.4f, 0.4f, 0.4f), emissive);

            // a particle system
            var sparks = new GameObject("Sparks");
            sparks.transform.position = new Vector3(10f, 1f, 10f);
            var ps = sparks.AddComponent<ParticleSystem>();
            var main = ps.main;
            main.loop = true;
            main.startLifetime = 1f;
            main.startSpeed = 2f;
            main.startSize = 0.2f;
            var emission = ps.emission;
            emission.rateOverTime = 20f;
            sparks.GetComponent<ParticleSystemRenderer>().sharedMaterial = particle;
            // a stopped one (no live effect) and two decals, one enabled
            var stopped = new GameObject("SparksOff");
            stopped.transform.position = new Vector3(12f, 1f, 10f);
            var ps2 = stopped.AddComponent<ParticleSystem>();
            ps2.Stop(true, ParticleSystemStopBehavior.StopEmittingAndClear);
            var main2 = ps2.main;
            main2.playOnAwake = false;
            stopped.GetComponent<ParticleSystemRenderer>().sharedMaterial = particle;
            new GameObject("Decal").AddComponent<UnityEngine.Rendering.Universal.DecalProjector>().transform.position = new Vector3(14f, 0f, 10f);
            var decalOff = new GameObject("DecalOff").AddComponent<UnityEngine.Rendering.Universal.DecalProjector>();
            decalOff.transform.position = new Vector3(15f, 0f, 10f);
            decalOff.enabled = false;

            // enemies with a Health script
            for (var i = 0; i < 3; i++)
            {
                var enemy = Prim(PrimitiveType.Cube, "Enemy_" + i, new Vector3(-10f + 2f * i, 0.5f, -8f), Vector3.one, plain);
                enemy.tag = "Enemy";
                var health = enemy.AddComponent<Health>();
                health.drainPerSecond = 5f * (i + 1);
                health.target = i == 0 ? hero.transform : null;
            }

            // a LODGroup: one piece
            var rock = new GameObject("Rock");
            rock.transform.position = new Vector3(-8f, 0.5f, -4f);
            var r0 = Prim(PrimitiveType.Cube, "Rock_LOD0", Vector3.zero, Vector3.one, grey, false, rock.transform);
            var r1 = Prim(PrimitiveType.Sphere, "Rock_LOD1", Vector3.zero, Vector3.one, grey, false, rock.transform);
            rock.AddComponent<LODGroup>().SetLODs(new[]
            {
                new LOD(0.5f, new Renderer[] { r0.GetComponent<Renderer>() }),
                new LOD(0.01f, new Renderer[] { r1.GetComponent<Renderer>() }),
            });

            // a spawner: a clone every 0.5 s (destroyed after 1 s) and a pool of 3 (deactivated after 0.7 s)
            var gun = new GameObject("Gun");
            gun.transform.SetPositionAndRotation(new Vector3(-5f, 1f, 5f), Quaternion.Euler(0f, 90f, 0f));
            var bullet = Prim(PrimitiveType.Sphere, "Bullet", Vector3.zero, Vector3.one * 0.2f, plain, false);
            bullet.AddComponent<Projectile>();
            bullet.SetActive(false);
            var pool = new GameObject[3];
            for (var i = 0; i < 3; i++)
            {
                pool[i] = Prim(PrimitiveType.Sphere, "PoolBullet", new Vector3(0f, -50f, 0f), Vector3.one * 0.2f, plain, false);
                var p = pool[i].AddComponent<Projectile>();
                p.pooled = true;
                p.life = 0.7f;
                pool[i].SetActive(false);
            }
            var spawner = gun.AddComponent<Spawner>();
            spawner.template = bullet;
            spawner.pool = pool;

            BuildArm(plain);
            BuildTerrain(grey);

            const string path = "Assets/Scenes/ObjTest.unity";
            EditorSceneManager.SaveScene(scene, path);
        }

        /// <summary>A skinned arm: a box of three rings on two bones (Lower, Upper), its Animator going from Idle to
        /// Bend (Upper slides sideways) when Open is set.</summary>
        static void BuildArm(Material m)
        {
            var arm = new GameObject("Arm");
            var lower = new GameObject("Lower").transform;
            lower.SetParent(arm.transform, false);
            var upper = new GameObject("Upper").transform;
            upper.SetParent(lower, false);
            upper.localPosition = new Vector3(0f, 1f, 0f);

            var mesh = new Mesh { name = "ArmMesh" };
            var verts = new List<Vector3>();
            var weights = new List<BoneWeight>();
            const float h = 0.2f;
            var corners = new[] { new Vector2(-h, -h), new Vector2(h, -h), new Vector2(h, h), new Vector2(-h, h) };
            for (var ring = 0; ring < 3; ring++)
                foreach (var c in corners)
                {
                    verts.Add(new Vector3(c.x, ring, c.y));
                    weights.Add(ring == 0 ? new BoneWeight { boneIndex0 = 0, weight0 = 1f }
                        : ring == 1 ? new BoneWeight { boneIndex0 = 0, weight0 = 0.5f, boneIndex1 = 1, weight1 = 0.5f }
                        : new BoneWeight { boneIndex0 = 1, weight0 = 1f });
                }
            var tris = new List<int>();
            for (var ring = 0; ring < 2; ring++)
                for (var s = 0; s < 4; s++)
                {
                    int a = ring * 4 + s, b = ring * 4 + (s + 1) % 4, c = a + 4, d = b + 4;
                    tris.AddRange(new[] { a, c, b, b, c, d });
                }
            tris.AddRange(new[] { 0, 1, 2, 0, 2, 3, 8, 10, 9, 8, 11, 10 });
            mesh.SetVertices(verts);
            mesh.SetTriangles(tris, 0);
            mesh.boneWeights = weights.ToArray();
            mesh.bindposes = new[] { lower.worldToLocalMatrix * arm.transform.localToWorldMatrix, upper.worldToLocalMatrix * arm.transform.localToWorldMatrix };
            mesh.RecalculateNormals();
            mesh.RecalculateBounds();
            AssetDatabase.DeleteAsset(Dir + "/ArmMesh.asset");
            AssetDatabase.CreateAsset(mesh, Dir + "/ArmMesh.asset");

            var smr = arm.AddComponent<SkinnedMeshRenderer>();
            smr.sharedMesh = mesh;
            smr.bones = new[] { lower, upper };
            smr.rootBone = lower;
            smr.sharedMaterial = m;
            smr.updateWhenOffscreen = true;
            smr.localBounds = mesh.bounds;

            var idle = new AnimationClip { name = "Idle" };
            AnimationUtility.SetEditorCurve(idle, EditorCurveBinding.FloatCurve("Lower/Upper", typeof(Transform), "m_LocalPosition.x"), AnimationCurve.Constant(0f, 1f, 0f));
            AnimationUtility.SetEditorCurve(idle, EditorCurveBinding.FloatCurve("Lower/Upper", typeof(Transform), "m_LocalPosition.y"), AnimationCurve.Constant(0f, 1f, 1f));
            AnimationUtility.SetEditorCurve(idle, EditorCurveBinding.FloatCurve("Lower/Upper", typeof(Transform), "m_LocalPosition.z"), AnimationCurve.Constant(0f, 1f, 0f));
            var bend = new AnimationClip { name = "Bend" };
            AnimationUtility.SetEditorCurve(bend, EditorCurveBinding.FloatCurve("Lower/Upper", typeof(Transform), "m_LocalPosition.x"), AnimationCurve.Linear(0f, 0f, 1f, 0.6f));
            AnimationUtility.SetEditorCurve(bend, EditorCurveBinding.FloatCurve("Lower/Upper", typeof(Transform), "m_LocalPosition.y"), AnimationCurve.Constant(0f, 1f, 1f));
            AnimationUtility.SetEditorCurve(bend, EditorCurveBinding.FloatCurve("Lower/Upper", typeof(Transform), "m_LocalPosition.z"), AnimationCurve.Constant(0f, 1f, 0f));
            foreach (var clip in new[] { idle, bend })
            {
                var settings = AnimationUtility.GetAnimationClipSettings(clip);
                settings.loopTime = clip == idle;
                AnimationUtility.SetAnimationClipSettings(clip, settings);
                AssetDatabase.DeleteAsset(Dir + "/" + clip.name + ".anim");
                AssetDatabase.CreateAsset(clip, Dir + "/" + clip.name + ".anim");
            }
            AssetDatabase.DeleteAsset(Dir + "/Arm.controller");
            var controller = AnimatorController.CreateAnimatorControllerAtPath(Dir + "/Arm.controller");
            controller.AddParameter("Speed", AnimatorControllerParameterType.Float);
            controller.AddParameter("Count", AnimatorControllerParameterType.Int);
            controller.AddParameter("Open", AnimatorControllerParameterType.Bool);
            var sm = controller.layers[0].stateMachine;
            var idleState = sm.AddState("Idle");
            idleState.motion = idle;
            var bendState = sm.AddState("Bend");
            bendState.motion = bend;
            sm.defaultState = idleState;
            var go = idleState.AddTransition(bendState);
            go.hasExitTime = false;
            go.duration = 0f;
            go.AddCondition(AnimatorConditionMode.If, 0f, "Open");

            arm.transform.position = new Vector3(12f, 0f, -6f);
            var animator = arm.AddComponent<Animator>();
            animator.runtimeAnimatorController = controller;
            arm.AddComponent<AnimDriver>();
        }

        /// <summary>A 40 x 40 m Terrain at x 60-100, z -20-20, with hills up to 6 m and 6 trees of a cube + sphere
        /// prefab.</summary>
        static void BuildTerrain(Material m)
        {
            var proto = new GameObject("TreeProto");
            Prim(PrimitiveType.Cube, "Trunk", new Vector3(0f, 1f, 0f), new Vector3(0.3f, 2f, 0.3f), m, false, proto.transform);
            Prim(PrimitiveType.Sphere, "Crown", new Vector3(0f, 2.5f, 0f), new Vector3(1.5f, 1.5f, 1.5f), m, false, proto.transform);
            var prefab = PrefabUtility.SaveAsPrefabAsset(proto, Dir + "/TreeProto.prefab");
            Object.DestroyImmediate(proto);

            var td = new TerrainData { heightmapResolution = 33 };
            td.size = new Vector3(40f, 6f, 40f);
            var heights = new float[33, 33];
            for (var y = 0; y < 33; y++)
                for (var x = 0; x < 33; x++)
                    heights[y, x] = 0.5f + 0.5f * Mathf.Sin(x * 0.4f) * Mathf.Cos(y * 0.3f);
            td.SetHeights(0, 0, heights);
            td.treePrototypes = new[] { new TreePrototype { prefab = prefab } };
            var trees = new List<TreeInstance>();
            for (var i = 0; i < 6; i++)
                trees.Add(new TreeInstance
                {
                    position = new Vector3(0.15f + 0.13f * i, 0f, 0.2f + 0.1f * i), prototypeIndex = 0, widthScale = 1f, heightScale = 1f,
                    color = Color.white, lightmapColor = Color.white,
                });
            td.SetTreeInstances(trees.ToArray(), true);
            AssetDatabase.DeleteAsset(Dir + "/Terrain.asset");
            AssetDatabase.CreateAsset(td, Dir + "/Terrain.asset");
            var tgo = Terrain.CreateTerrainGameObject(td);
            tgo.name = "Hills";
            tgo.transform.position = new Vector3(60f, 0f, -20f);
            var terrain = tgo.GetComponent<Terrain>();
            if (GraphicsSettings.currentRenderPipeline != null && GraphicsSettings.currentRenderPipeline.defaultTerrainMaterial != null)
                terrain.materialTemplate = GraphicsSettings.currentRenderPipeline.defaultTerrainMaterial;
        }

        // ---------------------------------------------------------------- the stress scene

        static void BuildStress()
        {
            var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            var grey = AssetDatabase.LoadAssetAtPath<Material>(Dir + "/Grey.mat");
            var emissive = AssetDatabase.LoadAssetAtPath<Material>(Dir + "/LampEmissive.mat");
            var sun = new GameObject("Sun").AddComponent<Light>();
            sun.type = LightType.Directional;
            sun.transform.rotation = Quaternion.Euler(50f, -30f, 0f);
            Prim(PrimitiveType.Cube, "Floor", new Vector3(0f, -0.5f, 0f), new Vector3(200f, 1f, 200f), grey);
            var cam = new GameObject("Main Camera");
            cam.tag = "MainCamera";
            cam.AddComponent<Camera>();
            cam.transform.SetPositionAndRotation(new Vector3(0f, 40f, -80f), Quaternion.Euler(30f, 0f, 0f));
            var root = new GameObject("Boxes").transform;
            for (var i = 0; i < 3000; i++)
            {
                var x = (i % 60) * 2f - 60f;
                var z = (i / 60) * 2f - 50f;
                var box = Prim(PrimitiveType.Cube, "Box_" + i, new Vector3(x, 0.5f, z), Vector3.one * 0.8f, i % 3 == 0 ? emissive : grey, true, root);
                if (i % 30 == 0) box.AddComponent<Spinner>();
                if (i % 100 == 0) box.AddComponent<Light>().intensity = 1f;
                if (i % 10 == 0) box.tag = "Enemy";
            }
            EditorSceneManager.SaveScene(scene, "Assets/Scenes/ObjStress.unity");
        }
    }
}
