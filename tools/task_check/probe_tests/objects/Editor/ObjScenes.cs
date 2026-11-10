// The objects family's scenes (probe_tests/objects), made from code under Assets/ProbeTests/objects/Made/:
//   ObjLab    one of every thing the objects, components, camera, spawns, pieces and ground kinds read
//   ObjMore   what ObjLab lacks: lit/glow sources of every kind, 2D physics, a NavMeshAgent, a humanoid, a ragdoll
//   ObjBudget more renderers to render for lit than a sample may render
//   ObjStress 3000 boxes, to time a whole-scene sample
using System.Collections.Generic;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEditor.Animations;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.AI;
using UnityEngine.Rendering;
using UnityEngine.Rendering.Universal;
using UnityEngine.VFX;

namespace ProbeTests.Objects
{
    public static class ObjScenes
    {
        const string Family = "Assets/ProbeTests/objects";
        const string Made = Family + "/Made";
        const string VfxTemplate = "Packages/com.unity.visualeffectgraph/Editor/Templates/02_Simple_Loop.vfx";
        const string GraphTemplate = "Packages/com.unity.shadergraph/GraphTemplates/Cross Pipeline/Unlit Simple.shadergraph";
        static int props;

        public static void Build()
        {
            if (!AssetDatabase.IsValidFolder(Made)) AssetDatabase.CreateFolder(Family, "Made");
            props = TagsAndLayer();
            Lab();
            More();
            Budget();
            Stress();
            AssetDatabase.SaveAssets();
        }

        // ---------------------------------------------------------------- project settings, assets

        /// <summary>The tags ObjLamp and ObjEnemy, and a user layer named ObjProps (the first free one); its index.</summary>
        static int TagsAndLayer()
        {
            var manager = new SerializedObject(AssetDatabase.LoadAllAssetsAtPath("ProjectSettings/TagManager.asset")[0]);
            var tags = manager.FindProperty("tags");
            foreach (var tag in new[] { "ObjLamp", "ObjEnemy" })
            {
                var have = false;
                for (var i = 0; i < tags.arraySize; i++) have |= tags.GetArrayElementAtIndex(i).stringValue == tag;
                if (have) continue;
                tags.InsertArrayElementAtIndex(tags.arraySize);
                tags.GetArrayElementAtIndex(tags.arraySize - 1).stringValue = tag;
            }
            var layers = manager.FindProperty("layers");
            var at = -1;
            for (var i = 8; i < 32 && at < 0; i++) if (layers.GetArrayElementAtIndex(i).stringValue == "ObjProps") at = i;
            for (var i = 8; i < 32 && at < 0; i++) if (string.IsNullOrEmpty(layers.GetArrayElementAtIndex(i).stringValue)) at = i;
            layers.GetArrayElementAtIndex(at).stringValue = "ObjProps";
            manager.ApplyModifiedProperties();
            return at;
        }

        static Material Mat(string name, string shader, System.Action<Material> setup)
        {
            var m = new Material(Shader.Find(shader)) { name = name };
            setup?.Invoke(m);
            AssetDatabase.CreateAsset(m, Made + "/" + name + ".mat");
            return m;
        }

        static Material Lit(string name, Color c) => Mat(name, "Universal Render Pipeline/Lit", m => m.SetColor("_BaseColor", c));

        /// <summary>URP Lit with emission: `on` sets the _EMISSION keyword. URP's material import sets the keyword from the
        /// global illumination flags (measured: a material saved with the keyword off and the realtime emissive flag
        /// had it on again), so off is "emissive is black" there.</summary>
        static Material Emissive(string name, Color emission, Texture map = null, bool on = true) => Mat(name, "Universal Render Pipeline/Lit", m =>
        {
            m.SetColor("_BaseColor", new Color(0.2f, 0.2f, 0.2f));
            m.SetColor("_EmissionColor", emission);
            if (map != null) m.SetTexture("_EmissionMap", map);
            m.globalIlluminationFlags = on ? MaterialGlobalIlluminationFlags.RealtimeEmissive : MaterialGlobalIlluminationFlags.EmissiveIsBlack;
            if (on) m.EnableKeyword("_EMISSION"); else m.DisableKeyword("_EMISSION");
        });

        /// <summary>A PNG made of `pixel(x, y)`, imported (not readable, or as a sprite of 1 m).</summary>
        static Texture2D Png(string name, int size, System.Func<int, int, Color32> pixel, bool sprite = false)
        {
            var path = Made + "/" + name + ".png";
            var tex = new Texture2D(size, size, TextureFormat.RGBA32, false);
            var pixels = new Color32[size * size];
            for (var y = 0; y < size; y++)
                for (var x = 0; x < size; x++) pixels[y * size + x] = pixel(x, y);
            tex.SetPixels32(pixels);
            File.WriteAllBytes(path, tex.EncodeToPNG());
            Object.DestroyImmediate(tex);
            AssetDatabase.ImportAsset(path, ImportAssetOptions.ForceUpdate);
            if (sprite)
            {
                var importer = (TextureImporter)AssetImporter.GetAtPath(path);
                importer.textureType = TextureImporterType.Sprite;
                importer.spriteImportMode = SpriteImportMode.Single;
                importer.spritePixelsPerUnit = size;
                importer.SaveAndReimport();
            }
            return AssetDatabase.LoadAssetAtPath<Texture2D>(path);
        }

        /// <summary>Left half white, right half black: a mean of 0.5.</summary>
        static Texture2D Half() => Png("Half", 64, (x, y) => x < 32 ? new Color32(255, 255, 255, 255) : new Color32(0, 0, 0, 255));

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

        static ObjTimedSwitch Switch(GameObject host, GameObject target, ObjTimedSwitch.Action action, float at)
        {
            var s = host.AddComponent<ObjTimedSwitch>();
            s.target = target;
            s.action = action;
            s.at = at;
            return s;
        }

        static GameObject Sun()
        {
            var sun = new GameObject("Sun");
            var light = sun.AddComponent<Light>();
            light.type = LightType.Directional;
            light.intensity = 1.5f;
            sun.transform.rotation = Quaternion.Euler(50f, -30f, 0f);
            return sun;
        }

        static Camera MainCamera(Vector3 at, Quaternion turn)
        {
            var go = new GameObject("Main Camera") { tag = "MainCamera" };
            var camera = go.AddComponent<Camera>();
            camera.fieldOfView = 60f;
            go.transform.SetPositionAndRotation(at, turn);
            return camera;
        }

        static ObjWatch Watch(params GameObject[] watched)
        {
            var watch = new GameObject("Watch").AddComponent<ObjWatch>();
            watch.watched = watched.Select(go => go.GetComponent<Renderer>()).ToArray();
            return watch;
        }

        // ---------------------------------------------------------------- ObjLab

        static void Lab()
        {
            var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            var grey = Lit("Grey", new Color(0.5f, 0.5f, 0.5f));
            var plain = Lit("Plain", new Color(0.8f, 0.3f, 0.3f));
            var emissive = Emissive("LampEmissive", new Color(4f, 3f, 2f));
            var mapped = Emissive("LampMapped", new Color(2f, 2f, 2f), Half());
            var switchable = Emissive("LampSwitch", Color.black);
            var unlit = Mat("LampUnlit", "Universal Render Pipeline/Unlit", m => m.SetColor("_BaseColor", new Color(1f, 0.9f, 0.5f)));
            var custom = Mat("LampCustom", "ProbeTests/ObjGlow", null);
            var particle = Mat("Particle", "Universal Render Pipeline/Particles/Unlit", m => m.SetColor("_BaseColor", new Color(1f, 0.6f, 0.2f)));

            Sun();
            // a flat 100 x 100 m floor (top at y 0), a ramp, a roof over a spot (ground with select Floor traces through it)
            Prim(PrimitiveType.Cube, "Floor", new Vector3(0f, -0.5f, 0f), new Vector3(100f, 1f, 100f), grey);
            Prim(PrimitiveType.Cube, "Ramp", new Vector3(30f, 0f, 30f), new Vector3(6f, 1f, 10f), grey).transform.rotation = Quaternion.Euler(-20f, 0f, 0f);
            Prim(PrimitiveType.Cube, "Roof", new Vector3(-20f, 4f, -20f), new Vector3(4f, 0.2f, 4f), plain);

            // the player, its camera, and a wall that comes between them from 6 to 8 s
            var hero = Prim(PrimitiveType.Capsule, "Hero", new Vector3(0f, 1.1f, 0f), Vector3.one, plain, false);
            hero.tag = "Player";
            hero.AddComponent<CharacterController>();
            hero.AddComponent<ObjTestPlayer>();
            var visor = Prim(PrimitiveType.Cube, "Visor", new Vector3(0f, 0.5f, 0.5f), new Vector3(0.6f, 0.2f, 0.2f), grey, false, hero.transform);
            visor.transform.localRotation = Quaternion.Euler(0f, 30f, 0f);
            MainCamera(new Vector3(0f, 4f, -6f), Quaternion.identity).gameObject.AddComponent<ObjFollowCam>().target = hero.transform;
            Prim(PrimitiveType.Cube, "Wall", new Vector3(0f, -100f, 0f), new Vector3(4f, 4f, 0.3f), plain).AddComponent<ObjOccluder>().target = hero.transform;

            // physics: a crate that falls from 8 m, a kinematic lift moved at 2 m/s
            Prim(PrimitiveType.Cube, "Crate", new Vector3(3f, 8f, 3f), Vector3.one, plain).AddComponent<Rigidbody>();
            var lift = Prim(PrimitiveType.Cube, "Lift", new Vector3(-3f, 0.5f, -3f), Vector3.one, plain);
            lift.AddComponent<Rigidbody>().isKinematic = true;
            lift.AddComponent<ObjKinematicMover>();

            // a fan: its blade spins at 180 deg/s and carries a trail at its tip
            var fan = new GameObject("Fan");
            fan.transform.position = new Vector3(5f, 1.5f, -5f);
            var blade = Prim(PrimitiveType.Cube, "Blade", Vector3.zero, new Vector3(3f, 0.1f, 0.3f), plain, false, fan.transform);
            blade.AddComponent<ObjSpinner>().degreesPerSecond = 180f;
            var tracer = new GameObject("Tracer");
            tracer.transform.SetParent(blade.transform, false);
            tracer.transform.localPosition = new Vector3(0.5f, 0f, 0f);
            var trail = tracer.AddComponent<TrailRenderer>();
            trail.time = 0.5f;
            trail.widthMultiplier = 0.1f;
            trail.sharedMaterial = particle;

            // things that go at 3 s: one deactivated, one whose renderer is disabled
            var switches = new GameObject("Switches");
            var vanisher = Prim(PrimitiveType.Cube, "Vanisher", new Vector3(-6f, 0.5f, 0f), Vector3.one, plain);
            var ghost = Prim(PrimitiveType.Cube, "Ghost", new Vector3(-6f, 0.5f, 2f), Vector3.one, plain);
            Switch(switches, vanisher, ObjTimedSwitch.Action.Deactivate, 3f);
            Switch(switches, ghost, ObjTimedSwitch.Action.HideRenderer, 3f);

            // lamps in a row at z 10, tagged ObjLamp, on layer ObjProps
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
            var lampMapped = Prim(PrimitiveType.Cube, "LampMapped", new Vector3(-2f, 0.5f, 10f), Vector3.one, mapped);
            lamps.Add(lampMapped);
            var lampSwitch = Prim(PrimitiveType.Cube, "LampSwitch", new Vector3(0f, 0.5f, 10f), Vector3.one, switchable);
            lamps.Add(lampSwitch);
            Switch(switches, lampSwitch, ObjTimedSwitch.Action.EmissionOn, 4f);
            var lampLater = new GameObject("LampLater");
            lampLater.transform.position = new Vector3(2f, 2f, 10f);
            var l2 = lampLater.AddComponent<Light>();
            l2.type = LightType.Spot;
            l2.intensity = 3f;
            l2.color = new Color(1f, 0.5f, 0.25f);
            l2.enabled = false;
            lamps.Add(lampLater);
            Switch(switches, lampLater, ObjTimedSwitch.Action.LightOn, 4f);
            var lampOff = new GameObject("LampOff");
            lampOff.transform.position = new Vector3(3f, 2f, 10f);
            lampOff.AddComponent<Light>().intensity = 2f;
            lamps.Add(lampOff);
            Switch(switches, lampOff, ObjTimedSwitch.Action.LightOff, 4f);
            var lampCustom = Prim(PrimitiveType.Cube, "LampCustom", new Vector3(4f, 0.5f, 10f), Vector3.one, custom);
            lamps.Add(lampCustom);
            var dark = Prim(PrimitiveType.Cube, "Dark", new Vector3(6f, 0.5f, 10f), Vector3.one, plain);
            lamps.Add(dark);
            foreach (var lamp in lamps)
            {
                lamp.tag = "ObjLamp";
                lamp.layer = props;
            }

            // a lamp the game lights in the frame an input selects it by has.lit (before the game's scripts): the sample
            // after the game's scripts in that frame must read it lit
            var lampLate = Prim(PrimitiveType.Cube, "LampLate", new Vector3(8f, 0.5f, 12f), Vector3.one, switchable);
            Switch(switches, lampLate, ObjTimedSwitch.Action.EmissionOn, 3.99f);

            // two bulbs, one above the other: near with a height band picks one
            Prim(PrimitiveType.Sphere, "Bulb", new Vector3(8f, 0.5f, 8f), new Vector3(0.4f, 0.4f, 0.4f), emissive);
            Prim(PrimitiveType.Sphere, "Bulb", new Vector3(8f, 3f, 8f), new Vector3(0.4f, 0.4f, 0.4f), emissive);

            // a live particle system, a stopped one, an enabled decal and a disabled one
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
            var stopped = new GameObject("SparksOff");
            stopped.transform.position = new Vector3(12f, 1f, 10f);
            var ps2 = stopped.AddComponent<ParticleSystem>();
            ps2.Stop(true, ParticleSystemStopBehavior.StopEmittingAndClear);
            var main2 = ps2.main;
            main2.playOnAwake = false;
            stopped.GetComponent<ParticleSystemRenderer>().sharedMaterial = particle;
            new GameObject("Decal").AddComponent<DecalProjector>().transform.position = new Vector3(14f, 0f, 10f);
            var decalOff = new GameObject("DecalOff").AddComponent<DecalProjector>();
            decalOff.transform.position = new Vector3(15f, 0f, 10f);
            decalOff.enabled = false;

            // enemies with a health script (members of every kind)
            for (var i = 0; i < 3; i++)
            {
                var enemy = Prim(PrimitiveType.Cube, "Enemy_" + i, new Vector3(-10f + 2f * i, 0.5f, -8f), Vector3.one, plain);
                enemy.tag = "ObjEnemy";
                var health = enemy.AddComponent<ObjHealth>();
                health.drainPerSecond = 5f * (i + 1);
                health.target = i == 0 ? hero.transform : null;
            }

            // a LODGroup: a cube as LOD 0, a sphere as LOD 1
            var rock = new GameObject("Rock");
            rock.transform.position = new Vector3(-8f, 0.5f, -4f);
            var r0 = Prim(PrimitiveType.Cube, "Rock_LOD0", Vector3.zero, Vector3.one, grey, false, rock.transform);
            var r1 = Prim(PrimitiveType.Sphere, "Rock_LOD1", Vector3.zero, Vector3.one, grey, false, rock.transform);
            rock.AddComponent<LODGroup>().SetLODs(new[]
            {
                new LOD(0.5f, new[] { r0.GetComponent<Renderer>() }),
                new LOD(0.01f, new[] { r1.GetComponent<Renderer>() }),
            });

            // a spawner: a clone every 0.5 s (destroyed after 1 s) and a pool of 3 (deactivated after 0.7 s)
            var gun = new GameObject("Gun");
            gun.transform.SetPositionAndRotation(new Vector3(-5f, 1f, 5f), Quaternion.Euler(0f, 90f, 0f));
            var bullet = Prim(PrimitiveType.Sphere, "Bullet", Vector3.zero, Vector3.one * 0.2f, plain, false);
            bullet.AddComponent<ObjProjectile>();
            bullet.SetActive(false);
            var pool = new GameObject[3];
            for (var i = 0; i < 3; i++)
            {
                pool[i] = Prim(PrimitiveType.Sphere, "PoolBullet", new Vector3(0f, -50f, 0f), Vector3.one * 0.2f, plain, false);
                var p = pool[i].AddComponent<ObjProjectile>();
                p.pooled = true;
                p.life = 0.7f;
                pool[i].SetActive(false);
            }
            var spawner = gun.AddComponent<ObjSpawner>();
            spawner.template = bullet;
            spawner.pool = pool;

            Arm(plain);
            Terrain(grey);
            Watch(lampMapped, lampCustom, dark, vanisher);
            EditorSceneManager.SaveScene(scene, Made + "/ObjLab.unity");
        }

        /// <summary>A skinned arm: a box of three rings on two bones (Lower, Upper); its Animator goes from Idle to Bend
        /// (Upper slides 0.6 m sideways in a second) when Open is set.</summary>
        static void Arm(Material m)
        {
            var arm = new GameObject("Arm");
            var lower = new GameObject("Lower").transform;
            lower.SetParent(arm.transform, false);
            var upper = new GameObject("Upper").transform;
            upper.SetParent(lower, false);
            upper.localPosition = new Vector3(0f, 1f, 0f);
            var mesh = Rings("ArmMesh", 0.2f, new[] { lower, upper }, arm.transform);
            var smr = arm.AddComponent<SkinnedMeshRenderer>();
            smr.sharedMesh = mesh;
            smr.bones = new[] { lower, upper };
            smr.rootBone = lower;
            smr.sharedMaterial = m;
            smr.updateWhenOffscreen = true;
            smr.localBounds = mesh.bounds;

            var idle = Clip("Idle", AnimationCurve.Constant(0f, 1f, 0f), true);
            var bend = Clip("Bend", AnimationCurve.Linear(0f, 0f, 1f, 0.6f), false);
            var controller = AnimatorController.CreateAnimatorControllerAtPath(Made + "/Arm.controller");
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
            arm.AddComponent<Animator>().runtimeAnimatorController = controller;
            arm.AddComponent<ObjAnimDriver>();
        }

        /// <summary>A box of three square rings (half-width h, 1 m apart) on two bones: the bottom ring on the first, the
        /// middle one shared, the top one on the second; bind poses from the bones as they stand.</summary>
        static Mesh Rings(string name, float h, Transform[] bones, Transform owner)
        {
            var mesh = new Mesh { name = name };
            var verts = new List<Vector3>();
            var weights = new List<BoneWeight>();
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
            mesh.bindposes = bones.Select(b => b.worldToLocalMatrix * owner.localToWorldMatrix).ToArray();
            mesh.RecalculateNormals();
            mesh.RecalculateBounds();
            AssetDatabase.CreateAsset(mesh, Made + "/" + name + ".asset");
            return mesh;
        }

        /// <summary>A clip moving Lower/Upper along x by `x` (y 1, z 0).</summary>
        static AnimationClip Clip(string name, AnimationCurve x, bool loop)
        {
            var clip = new AnimationClip { name = name };
            AnimationUtility.SetEditorCurve(clip, EditorCurveBinding.FloatCurve("Lower/Upper", typeof(Transform), "m_LocalPosition.x"), x);
            AnimationUtility.SetEditorCurve(clip, EditorCurveBinding.FloatCurve("Lower/Upper", typeof(Transform), "m_LocalPosition.y"), AnimationCurve.Constant(0f, 1f, 1f));
            AnimationUtility.SetEditorCurve(clip, EditorCurveBinding.FloatCurve("Lower/Upper", typeof(Transform), "m_LocalPosition.z"), AnimationCurve.Constant(0f, 1f, 0f));
            var settings = AnimationUtility.GetAnimationClipSettings(clip);
            settings.loopTime = loop;
            AnimationUtility.SetAnimationClipSettings(clip, settings);
            AssetDatabase.CreateAsset(clip, Made + "/" + name + ".anim");
            return clip;
        }

        /// <summary>A 40 x 40 m Terrain at x 60-100, z -20-20, hills up to 6 m, and 6 trees of a cube + sphere prefab.</summary>
        static void Terrain(Material m)
        {
            var proto = new GameObject("TreeProto");
            Prim(PrimitiveType.Cube, "Trunk", new Vector3(0f, 1f, 0f), new Vector3(0.3f, 2f, 0.3f), m, false, proto.transform);
            Prim(PrimitiveType.Sphere, "Crown", new Vector3(0f, 2.5f, 0f), new Vector3(1.5f, 1.5f, 1.5f), m, false, proto.transform);
            var prefab = PrefabUtility.SaveAsPrefabAsset(proto, Made + "/TreeProto.prefab");
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
            AssetDatabase.CreateAsset(td, Made + "/Terrain.asset");
            var tgo = UnityEngine.Terrain.CreateTerrainGameObject(td);
            tgo.name = "Hills";
            tgo.transform.position = new Vector3(60f, 0f, -20f);
            var terrain = tgo.GetComponent<UnityEngine.Terrain>();
            if (GraphicsSettings.currentRenderPipeline != null && GraphicsSettings.currentRenderPipeline.defaultTerrainMaterial != null)
                terrain.materialTemplate = GraphicsSettings.currentRenderPipeline.defaultTerrainMaterial;
        }

        // ---------------------------------------------------------------- ObjMore

        static void More()
        {
            var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            var grey = AssetDatabase.LoadAssetAtPath<Material>(Made + "/Grey.mat");
            var plain = AssetDatabase.LoadAssetAtPath<Material>(Made + "/Plain.mat");
            var emissive = AssetDatabase.LoadAssetAtPath<Material>(Made + "/LampEmissive.mat");
            var switchable = AssetDatabase.LoadAssetAtPath<Material>(Made + "/LampSwitch.mat");
            var custom = AssetDatabase.LoadAssetAtPath<Material>(Made + "/LampCustom.mat");
            var half = AssetDatabase.LoadAssetAtPath<Texture2D>(Made + "/Half.png");
            Sun();
            MainCamera(new Vector3(0f, 6f, -12f), Quaternion.Euler(20f, 0f, 0f));
            Prim(PrimitiveType.Cube, "Floor", new Vector3(0f, -0.5f, 0f), new Vector3(100f, 1f, 100f), grey);
            var switches = new GameObject("Switches");

            // lit / glow sources in a row at z 4
            var temp = new GameObject("LampTemp");
            temp.transform.position = new Vector3(-10f, 2f, 4f);
            var warm = temp.AddComponent<Light>();
            warm.type = LightType.Point;
            warm.intensity = 2f;
            warm.useColorTemperature = true;
            warm.colorTemperature = 3000f;
            temp.AddComponent<ObjKelvin>();
            var twoMat = Prim(PrimitiveType.Cube, "LampTwoMat", new Vector3(-8f, 0.5f, 4f), Vector3.one, plain);
            twoMat.GetComponent<Renderer>().sharedMaterials = new[] { plain, switchable };
            var byIndex = Switch(switches, twoMat, ObjTimedSwitch.Action.EmissionOnIndex, 2f);
            byIndex.index = 1;
            Prim(PrimitiveType.Cube, "LampStandard", new Vector3(-6f, 0.5f, 4f), Vector3.one, Mat("LampStandard", "Standard", m =>
            {
                m.SetColor("_EmissionColor", new Color(2f, 2f, 2f));
                m.EnableKeyword("_EMISSION");
                m.globalIlluminationFlags = MaterialGlobalIlluminationFlags.RealtimeEmissive;
            }));
            var atlas = Emissive("Atlas", new Color(4f, 4f, 4f), half);
            Prim(PrimitiveType.Cube, "AtlasWhite", new Vector3(-4f, 0.5f, 4f), Vector3.one, atlas).GetComponent<MeshFilter>().sharedMesh = Uvs("AtlasWhite", 0.25f);
            Prim(PrimitiveType.Cube, "AtlasBlack", new Vector3(-2f, 0.5f, 4f), Vector3.one, atlas).GetComponent<MeshFilter>().sharedMesh = Uvs("AtlasBlack", 0.75f);
            var keyword = Prim(PrimitiveType.Cube, "LampKeyword", new Vector3(0f, 0.5f, 4f), Vector3.one, Emissive("LampKeyword", new Color(4f, 4f, 4f), null, false));
            Switch(switches, keyword, ObjTimedSwitch.Action.KeywordOn, 2f);
            var forced = Prim(PrimitiveType.Cube, "LampForced", new Vector3(2f, 0.5f, 4f), Vector3.one, emissive);
            Switch(switches, forced, ObjTimedSwitch.Action.ForceOff, 0f);
            // either side of the floor (luminance 0.01): 0.09 grey is 0.0085 in linear, 0.11 grey 0.0116
            Prim(PrimitiveType.Cube, "LampDim", new Vector3(-12f, 0.5f, 6f), Vector3.one, Emissive("LampDim", new Color(0.09f, 0.09f, 0.09f)));
            Prim(PrimitiveType.Cube, "LampFaint", new Vector3(-10f, 0.5f, 6f), Vector3.one, Emissive("LampFaint", new Color(0.11f, 0.11f, 0.11f)));
            Prim(PrimitiveType.Cube, "LampUnlitMap", new Vector3(-8f, 0.5f, 6f), Vector3.one, Mat("LampUnlitMap", "Universal Render Pipeline/Unlit", m =>
            {
                m.SetColor("_BaseColor", new Color(1f, 0.9f, 0.5f));
                m.SetTexture("_BaseMap", half);
            }));
            if (AssetDatabase.CopyAsset(GraphTemplate, Made + "/ObjUnlitGraph.shadergraph"))
            {
                AssetDatabase.ImportAsset(Made + "/ObjUnlitGraph.shadergraph", ImportAssetOptions.ForceSynchronousImport);
                var graph = AssetDatabase.LoadAssetAtPath<Shader>(Made + "/ObjUnlitGraph.shadergraph");
                var m = new Material(graph) { name = "LampGraph" };
                m.SetColor("_BaseColor", new Color(0.5f, 1f, 0.25f));
                AssetDatabase.CreateAsset(m, Made + "/LampGraph.mat");
                Prim(PrimitiveType.Cube, "LampGraph", new Vector3(4f, 0.5f, 4f), Vector3.one, m);
            }
            var white = AssetDatabase.LoadAssetAtPath<Sprite>(AssetDatabase.GetAssetPath(Png("White", 32, (x, y) => new Color32(255, 255, 255, 255), true)));
            Sprite2D("SpriteLamp", new Vector3(6f, 1f, 4f), white, new Color(1f, 0.5f, 0.25f));
            Sprite2D("SpriteDark", new Vector3(8f, 1f, 4f), white, Color.black);
            var line = new GameObject("LineLamp").AddComponent<LineRenderer>();
            line.transform.position = new Vector3(10f, 1f, 4f);
            line.useWorldSpace = false;
            line.positionCount = 2;
            line.SetPositions(new[] { Vector3.zero, new Vector3(2f, 0f, 0f) });
            line.widthMultiplier = 0.2f;
            line.startColor = line.endColor = new Color(1f, 0.5f, 0.25f);
            line.sharedMaterial = new Material(Shader.Find("Sprites/Default"));
            AssetDatabase.CreateAsset(line.sharedMaterial, Made + "/Line.mat");
            Tube("TubeLit", new Vector3(14f, 0f, 4f), emissive);
            Tube("TubeCustom", new Vector3(16f, 0f, 4f), custom);
            var vfxAsset = AssetDatabase.CopyAsset(VfxTemplate, Made + "/ObjLoop.vfx") ? AssetDatabase.LoadAssetAtPath<VisualEffectAsset>(Made + "/ObjLoop.vfx") : null;
            if (vfxAsset != null)
            {
                var vfx = new GameObject("Vfx").AddComponent<VisualEffect>();
                vfx.transform.position = new Vector3(18f, 1f, 4f);
                vfx.visualEffectAsset = vfxAsset;
            }

            // 2D physics in the plane z 20: a ground, a box that falls on it, a kinematic body moved at 2 m/s, a body
            // spun at 90 deg/s from the start
            var ground = new GameObject("Ground2D");
            ground.transform.position = new Vector3(-30f, 0f, 20f);
            ground.AddComponent<BoxCollider2D>().size = new Vector2(20f, 1f);
            var box = Sprite2D("Box2D", new Vector3(-32f, 6f, 20f), white, new Color(0.5f, 0.5f, 0.5f));
            box.AddComponent<BoxCollider2D>().size = Vector2.one;
            box.AddComponent<Rigidbody2D>();
            var kin = Sprite2D("Kin2D", new Vector3(-28f, 3f, 20f), white, new Color(0.5f, 0.5f, 0.5f));
            kin.AddComponent<Rigidbody2D>().bodyType = RigidbodyType2D.Kinematic;
            kin.AddComponent<ObjKinematicMover>();
            var spin = Sprite2D("Spin2D", new Vector3(-24f, 3f, 20f), white, new Color(0.5f, 0.5f, 0.5f));
            var spun = spin.AddComponent<Rigidbody2D>();
            spun.gravityScale = 0f;
            spun.angularDamping = 0f;
            Switch(switches, spin, ObjTimedSwitch.Action.Spin2D, 0f).amount = 90f;

            // a NavMeshAgent walking 2 m/s on a pad of its own NavMesh (built when the play starts)
            var pad = Prim(PrimitiveType.Cube, "NavPad", new Vector3(-30f, -0.45f, -20f), new Vector3(12f, 1f, 4f), grey);
            var walker = Prim(PrimitiveType.Capsule, "Walker", new Vector3(-34f, 1.05f, -20f), Vector3.one, plain, false);
            var agent = walker.AddComponent<NavMeshAgent>();
            agent.speed = 2f;
            agent.acceleration = 100f;
            agent.angularSpeed = 3600f;
            agent.enabled = false;
            var walk = walker.AddComponent<ObjAgent>();
            walk.pad = pad.transform;
            walk.goal = new Vector3(-26f, 0.05f, -20f);

            Humanoid(new Vector3(-10f, 0f, -20f));
            Ragdoll(new Vector3(0f, 0f, -20f), plain, switches);
            // a slider moved by its transform alone at 2 m/s, and a spinner (speed and spin across a wait)
            Prim(PrimitiveType.Cube, "Slider", new Vector3(10f, 0.5f, -20f), Vector3.one, plain, false).AddComponent<ObjSlider>();
            Prim(PrimitiveType.Cube, "Turner", new Vector3(20f, 0.5f, -20f), new Vector3(2f, 0.2f, 0.2f), plain, false).AddComponent<ObjSpinner>();
            // a component of a type and nothing else: its object's class is that type
            new GameObject("OnlyCollider").AddComponent<BoxCollider>().transform.position = new Vector3(30f, 0.5f, -20f);

            Watch(GameObject.Find("AtlasWhite"), GameObject.Find("AtlasBlack"), forced, GameObject.Find("LampStandard"), GameObject.Find("TubeLit"),
                GameObject.Find("SpriteLamp"), GameObject.Find("TubeCustom"));
            EditorSceneManager.SaveScene(scene, Made + "/ObjMore.unity");
        }

        /// <summary>The cube mesh with every UV at (u, 0.5): it shows one point of its texture, as a mesh shows its part of
        /// an atlas.</summary>
        static Mesh Uvs(string name, float u)
        {
            var cube = GameObject.CreatePrimitive(PrimitiveType.Cube);
            var mesh = Object.Instantiate(cube.GetComponent<MeshFilter>().sharedMesh);
            Object.DestroyImmediate(cube);
            mesh.name = name;
            mesh.uv = Enumerable.Repeat(new Vector2(u, 0.5f), mesh.vertexCount).ToArray();
            AssetDatabase.CreateAsset(mesh, Made + "/" + name + ".asset");
            return mesh;
        }

        static GameObject Sprite2D(string name, Vector3 at, Sprite sprite, Color colour)
        {
            var go = new GameObject(name);
            go.transform.position = at;
            var r = go.AddComponent<SpriteRenderer>();
            r.sprite = sprite;
            r.color = colour;
            return go;
        }

        /// <summary>A skinned box of rings (0.4 x 2 x 0.4 m) whose root bone is scaled 2 while the mesh's object isn't, as an
        /// FBX converted from other units has it: its local bounds are in the root bone's frame (half its size there).</summary>
        static void Tube(string name, Vector3 at, Material m)
        {
            var tube = new GameObject(name);
            tube.transform.position = at;
            var root = new GameObject("TubeRoot").transform;
            root.SetParent(tube.transform, false);
            root.localScale = new Vector3(2f, 2f, 2f);
            var top = new GameObject("TubeTop").transform;
            top.SetParent(root, false);
            top.localPosition = new Vector3(0f, 0.5f, 0f);
            var mesh = Rings(name + "Mesh", 0.2f, new[] { root, top }, tube.transform);
            var smr = tube.AddComponent<SkinnedMeshRenderer>();
            smr.sharedMesh = mesh;
            smr.bones = new[] { root, top };
            smr.rootBone = root;
            smr.sharedMaterial = m;
            var b = mesh.bounds;
            smr.localBounds = new Bounds(b.center * 0.5f, b.size * 0.5f);
        }

        /// <summary>A stick figure with a humanoid avatar; its head bone is named Skull, so `bone:Animator.Head` can only
        /// find it as the human bone.</summary>
        static void Humanoid(Vector3 at)
        {
            var human = new GameObject("Human");
            Transform Bone(string name, Transform parent, Vector3 local)
            {
                var t = new GameObject(name).transform;
                t.SetParent(parent, false);
                t.localPosition = local;
                return t;
            }
            var hips = Bone("Hips", human.transform, new Vector3(0f, 1f, 0f));
            var spine = Bone("Spine", hips, new Vector3(0f, 0.2f, 0f));
            var chest = Bone("Chest", spine, new Vector3(0f, 0.2f, 0f));
            var neck = Bone("Neck", chest, new Vector3(0f, 0.2f, 0f));
            Bone("Skull", neck, new Vector3(0f, 0.15f, 0f));
            foreach (var side in new[] { "Left", "Right" })
            {
                var x = side == "Left" ? -1f : 1f;
                var upperArm = Bone(side + "UpperArm", chest, new Vector3(0.2f * x, 0.15f, 0f));
                var lowerArm = Bone(side + "LowerArm", upperArm, new Vector3(0.3f * x, 0f, 0f));
                Bone(side + "Hand", lowerArm, new Vector3(0.25f * x, 0f, 0f));
                var upperLeg = Bone(side + "UpperLeg", hips, new Vector3(0.1f * x, -0.05f, 0f));
                var lowerLeg = Bone(side + "LowerLeg", upperLeg, new Vector3(0f, -0.45f, 0f));
                Bone(side + "Foot", lowerLeg, new Vector3(0f, -0.45f, 0f));
            }
            var humanBones = new[]
            {
                "Hips", "Spine", "Chest", "Neck", "LeftUpperArm", "LeftLowerArm", "LeftHand", "RightUpperArm", "RightLowerArm",
                "RightHand", "LeftUpperLeg", "LeftLowerLeg", "LeftFoot", "RightUpperLeg", "RightLowerLeg", "RightFoot",
            }.Select(n => new HumanBone { humanName = n, boneName = n, limit = new HumanLimit { useDefaultValues = true } }).ToList();
            humanBones.Add(new HumanBone { humanName = "Head", boneName = "Skull", limit = new HumanLimit { useDefaultValues = true } });
            var description = new HumanDescription
            {
                human = humanBones.ToArray(),
                skeleton = human.GetComponentsInChildren<Transform>().Select(t => new SkeletonBone
                {
                    name = t.name, position = t.localPosition, rotation = t.localRotation, scale = t.localScale,
                }).ToArray(),
                upperArmTwist = 0.5f, lowerArmTwist = 0.5f, upperLegTwist = 0.5f, lowerLegTwist = 0.5f, armStretch = 0.05f,
                legStretch = 0.05f, feetSpacing = 0f, hasTranslationDoF = false,
            };
            var avatar = AvatarBuilder.BuildHumanAvatar(human, description);
            avatar.name = "Human";
            if (!avatar.isValid || !avatar.isHuman) Debug.LogError("ProbeTests: the stick figure's avatar isn't a valid humanoid");
            AssetDatabase.CreateAsset(avatar, Made + "/Human.asset");
            var controller = AnimatorController.CreateAnimatorControllerAtPath(Made + "/Human.controller");
            controller.layers[0].stateMachine.AddState("Stand");
            human.transform.position = at;
            var animator = human.AddComponent<Animator>();
            animator.avatar = avatar;
            animator.runtimeAnimatorController = controller;
        }

        /// <summary>A ragdoll: one skinned mesh of three boxes, each on a bone that carries a Rigidbody and a collider,
        /// resting on the floor 0.6 m apart; kicked apart at 1 s.</summary>
        static void Ragdoll(Vector3 at, Material m, GameObject switches)
        {
            var doll = new GameObject("Ragdoll");
            doll.transform.position = at;
            var bones = new Transform[3];
            var verts = new List<Vector3>();
            var weights = new List<BoneWeight>();
            var tris = new List<int>();
            var cube = GameObject.CreatePrimitive(PrimitiveType.Cube);
            var unit = cube.GetComponent<MeshFilter>().sharedMesh;
            Object.DestroyImmediate(cube);
            for (var i = 0; i < 3; i++)
            {
                var bone = new GameObject("Body" + "ABC"[i]).transform;
                bone.SetParent(doll.transform, false);
                bone.localPosition = new Vector3(0.6f * (i - 1), 0.25f, 0f);
                bone.gameObject.AddComponent<BoxCollider>().size = new Vector3(0.5f, 0.5f, 0.5f);
                bone.gameObject.AddComponent<Rigidbody>();
                bones[i] = bone;
                var first = verts.Count;
                foreach (var v in unit.vertices) verts.Add(bone.localPosition + v * 0.5f);
                foreach (var _ in unit.vertices) weights.Add(new BoneWeight { boneIndex0 = i, weight0 = 1f });
                foreach (var t in unit.triangles) tris.Add(first + t);
            }
            var mesh = new Mesh { name = "RagdollMesh" };
            mesh.SetVertices(verts);
            mesh.SetTriangles(tris, 0);
            mesh.boneWeights = weights.ToArray();
            mesh.bindposes = bones.Select(b => b.worldToLocalMatrix * doll.transform.localToWorldMatrix).ToArray();
            mesh.RecalculateNormals();
            mesh.RecalculateBounds();
            AssetDatabase.CreateAsset(mesh, Made + "/RagdollMesh.asset");
            var smr = doll.AddComponent<SkinnedMeshRenderer>();
            smr.sharedMesh = mesh;
            smr.bones = bones;
            smr.rootBone = bones[1];
            smr.sharedMaterial = m;
            smr.updateWhenOffscreen = true;
            Switch(switches, doll, ObjTimedSwitch.Action.Kick, 1f).amount = 3f;
        }

        // ---------------------------------------------------------------- ObjBudget

        /// <summary>80 cubes drawn with the custom shader (each read as rendered), then 4 drawn with an emission map: one
        /// sample may render 64.</summary>
        static void Budget()
        {
            var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            var custom = AssetDatabase.LoadAssetAtPath<Material>(Made + "/LampCustom.mat");
            var mapped = AssetDatabase.LoadAssetAtPath<Material>(Made + "/LampMapped.mat");
            Sun();
            MainCamera(new Vector3(0f, 10f, -20f), Quaternion.Euler(30f, 0f, 0f));
            var lamps = new GameObject("Lamps").transform;
            for (var i = 0; i < 84; i++)
                Prim(PrimitiveType.Cube, i < 80 ? "Glow_" + i.ToString("00") : "Mapped_" + (i - 80), new Vector3((i % 12) * 2f - 11f, 0.5f, (i / 12) * 2f),
                    Vector3.one, i < 80 ? custom : mapped, false, lamps);
            EditorSceneManager.SaveScene(scene, Made + "/ObjBudget.unity");
        }

        // ---------------------------------------------------------------- ObjStress

        /// <summary>3000 boxes with colliders: every 3rd emissive, every 30th spinning, every 100th a Light, every 10th
        /// tagged ObjEnemy.</summary>
        static void Stress()
        {
            var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            var grey = AssetDatabase.LoadAssetAtPath<Material>(Made + "/Grey.mat");
            var emissive = AssetDatabase.LoadAssetAtPath<Material>(Made + "/LampEmissive.mat");
            Sun();
            Prim(PrimitiveType.Cube, "Floor", new Vector3(0f, -0.5f, 0f), new Vector3(200f, 1f, 200f), grey);
            MainCamera(new Vector3(0f, 40f, -80f), Quaternion.Euler(30f, 0f, 0f));
            var root = new GameObject("Boxes").transform;
            for (var i = 0; i < 3000; i++)
            {
                var box = Prim(PrimitiveType.Cube, "Box_" + i, new Vector3((i % 60) * 2f - 60f, 0.5f, (i / 60) * 2f - 50f), Vector3.one * 0.8f,
                    i % 3 == 0 ? emissive : grey, true, root);
                if (i % 30 == 0) box.AddComponent<ObjSpinner>();
                if (i % 100 == 0) box.AddComponent<Light>().intensity = 1f;
                if (i % 10 == 0) box.tag = "ObjEnemy";
            }
            EditorSceneManager.SaveScene(scene, Made + "/ObjStress.unity");
        }
    }
}
