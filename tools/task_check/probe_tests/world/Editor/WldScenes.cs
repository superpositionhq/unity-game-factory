// The world family's scenes (probe_tests/world): the camera against the player (a wall that comes and goes, a trigger,
// the Ignore Raycast layer, the camera's own collider, a turn away), shots spawned and destroyed every way a game makes
// them, mesh pieces of every form (submeshes, line and point meshes, an unreadable mesh, a skinned mesh, LODs, a
// terrain's trees), and ground: a floor with a hole, a hill, a roof, a trigger, a 2D collider.
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.SceneManagement;

namespace ProbeTests.World
{
    public static class WldScenes
    {
        const string Made = "Assets/ProbeTests/world/Made";

        public static void Build()
        {
            if (!AssetDatabase.IsValidFolder(Made)) AssetDatabase.CreateFolder("Assets/ProbeTests/world", "Made");
            Lab();
            Side();
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

        /// <summary>A box collider (no renderer) from `min` to `max`, on `layer`, a trigger or not.</summary>
        static GameObject Slab(string name, Vector3 min, Vector3 max, bool trigger = false, int layer = 0, Transform parent = null)
        {
            var go = Empty(name, (min + max) / 2f, parent);
            var box = go.AddComponent<BoxCollider>();
            box.size = max - min;
            box.isTrigger = trigger;
            go.layer = layer;
            return go;
        }

        static Mesh Asset(Mesh mesh, string name)
        {
            mesh.name = name;
            AssetDatabase.CreateAsset(mesh, Made + "/" + name + ".asset");
            return mesh;
        }

        /// <summary>A mesh of submeshes, each of `triangles` triangles (or as many line or point indices) of `topology`.</summary>
        static Mesh Sub(string name, params (MeshTopology topology, int count)[] parts)
        {
            var mesh = new Mesh { subMeshCount = parts.Length };
            var vertices = new Vector3[64];
            for (var i = 0; i < vertices.Length; i++) vertices[i] = new Vector3(i % 4, i / 4 % 4, i / 16);
            mesh.vertices = vertices;
            for (var s = 0; s < parts.Length; s++)
            {
                var (topology, count) = parts[s];
                var per = topology == MeshTopology.Triangles ? 3 : topology == MeshTopology.Lines ? 2 : 1;
                var indices = new int[count * per];
                for (var i = 0; i < indices.Length; i++) indices[i] = (i * 7 + s) % vertices.Length;
                mesh.SetIndices(indices, topology, s);
            }
            mesh.RecalculateBounds();
            return Asset(mesh, name);
        }

        static GameObject Piece(string name, Vector3 at, Mesh mesh, Material material, Transform parent)
        {
            var go = Empty(name, at, parent);
            go.AddComponent<MeshFilter>().sharedMesh = mesh;
            var r = go.AddComponent<MeshRenderer>();
            var slots = new Material[mesh.subMeshCount];
            for (var i = 0; i < slots.Length; i++) slots[i] = material;
            r.sharedMaterials = slots;
            return go;
        }

        static void Lab()
        {
            var scene = New();
            var cube = Resources.GetBuiltinResource<Mesh>("Cube.fbx");
            var quad = Resources.GetBuiltinResource<Mesh>("Quad.fbx");
            var lit = GraphicsSettings.defaultRenderPipeline != null ? GraphicsSettings.defaultRenderPipeline.defaultMaterial
                : AssetDatabase.GetBuiltinExtraResource<Material>("Default-Material.mat");

            // camera: the player's pivot at its feet, its collider's centre 1 m up; the camera 6 m behind and 1.5 m up
            var hero = Empty("WldHero", Vector3.zero);
            hero.tag = "Player";
            var body = GameObject.CreatePrimitive(PrimitiveType.Capsule);
            body.name = "WldHeroBody";
            body.transform.SetParent(hero.transform, false);
            body.transform.localPosition = new Vector3(0f, 1f, 0f);
            var camera = Empty("Main Camera", new Vector3(0f, 1.5f, -6f));
            camera.tag = "MainCamera";
            camera.AddComponent<Camera>();
            camera.AddComponent<WldOrtho>();
            // the camera's own collider, just in front of it: the ray to the player passes through it
            Slab("CameraBox", new Vector3(-0.3f, 1.2f, -5.8f), new Vector3(0.3f, 1.8f, -5.4f), parent: camera.transform);
            var wall = Cube("Wall", new Vector3(0f, 1f, -3f));
            wall.transform.localScale = new Vector3(3f, 3f, 0.2f);
            Slab("Mist", new Vector3(-2f, 0f, -2.2f), new Vector3(2f, 3f, -1.8f), trigger: true);
            Slab("Glass", new Vector3(-2f, 0f, -1.6f), new Vector3(2f, 3f, -1.4f), layer: 2);
            Slab("HeroFloor", new Vector3(-5f, -1f, -5f), new Vector3(5f, 0f, 5f));
            Empty("Sun", new Vector3(0f, 10f, 0f)).AddComponent<Light>().type = LightType.Directional;

            // spawns: a template (inactive), a pool, an object that gets a WldShot later, one with a disabled WldShot
            var template = Cube("Shot", new Vector3(0f, 0f, 20f));
            template.AddComponent<WldShot>();
            template.SetActive(false);
            var poolRoot = Empty("Pool", new Vector3(5f, 0f, 20f));
            var pool = new GameObject[3];
            for (var i = 0; i < 3; i++)
            {
                pool[i] = Empty("Pooled_" + i, new Vector3(5f + i, 0f, 20f), poolRoot.transform);
                pool[i].AddComponent<WldShot>();
                pool[i].SetActive(false);
            }
            var plain = Empty("Plain", new Vector3(10f, 0f, 20f));
            var idle = Empty("Idle", new Vector3(12f, 0f, 20f));
            idle.AddComponent<WldShot>().enabled = false;
            var director = Empty("Director", new Vector3(0f, 0f, 22f)).AddComponent<WldDirector>();
            director.wall = wall;
            director.view = camera.transform;
            director.template = template;
            director.pool = pool;
            director.plain = plain;
            director.idle = idle;

            // pieces: under PieceArea, one form each
            var area = Empty("PieceArea", new Vector3(50f, 0f, 0f));
            for (var i = 0; i < 3; i++) Piece("Rock_" + i, new Vector3(50f + 2f * i, 0f, 0f), cube, lit, area.transform);
            Piece("Multi", new Vector3(50f, 0f, 4f), Sub("WldMulti", (MeshTopology.Triangles, 2), (MeshTopology.Triangles, 4)), lit, area.transform);
            Piece("Lines", new Vector3(52f, 0f, 4f), Sub("WldLines", (MeshTopology.Lines, 5)), lit, area.transform);
            Piece("Points", new Vector3(54f, 0f, 4f), Sub("WldPoints", (MeshTopology.Points, 5)), lit, area.transform);
            Piece("Mixed", new Vector3(56f, 0f, 4f), Sub("WldMixed", (MeshTopology.Triangles, 2), (MeshTopology.Lines, 3)), lit, area.transform);
            var sealedMesh = Sub("WldSealed", (MeshTopology.Triangles, 7));
            var so = new SerializedObject(sealedMesh);
            so.FindProperty("m_IsReadable").boolValue = false;
            so.ApplyModifiedPropertiesWithoutUndo();
            Piece("Sealed", new Vector3(58f, 0f, 4f), sealedMesh, lit, area.transform);
            var skin = Empty("Skin", new Vector3(50f, 0f, 8f), area.transform).AddComponent<SkinnedMeshRenderer>();
            skin.sharedMesh = cube;
            skin.sharedMaterial = lit;
            var skinLines = Empty("SkinLines", new Vector3(50f, 0f, 10f), area.transform).AddComponent<SkinnedMeshRenderer>();
            skinLines.sharedMesh = AssetDatabase.LoadAssetAtPath<Mesh>(Made + "/WldLines.asset");
            skinLines.sharedMaterial = lit;
            var lod = Empty("Lod", new Vector3(52f, 0f, 8f), area.transform);
            var near0 = Piece("Lod_0", new Vector3(52f, 0f, 8f), cube, lit, lod.transform).GetComponent<Renderer>();
            var far1 = Piece("Lod_1", new Vector3(52f, 0f, 8f), quad, lit, lod.transform).GetComponent<Renderer>();
            var far2 = Piece("Lod_2", new Vector3(52f, 0f, 8f), quad, lit, lod.transform).GetComponent<Renderer>();
            lod.AddComponent<LODGroup>().SetLODs(new[]
            {
                new LOD(0.5f, new[] { near0 }), new LOD(0.2f, new[] { far1, near0 }), new LOD(0.05f, new[] { far2 }),
            });
            Piece("Hidden", new Vector3(54f, 0f, 8f), cube, lit, area.transform).GetComponent<Renderer>().enabled = false;
            Piece("Asleep", new Vector3(56f, 0f, 8f), cube, lit, area.transform).SetActive(false);
            var still = Piece("StaticRock", new Vector3(58f, 0f, 8f), cube, lit, area.transform);
            still.isStatic = true;
            var painter = Empty("Painter", new Vector3(60f, 0f, 8f), area.transform).AddComponent<WldPainter>();
            painter.mesh = cube;
            painter.material = lit;
            Terrain(area.transform, cube, quad, lit);

            // ground: x 100-140, z 0-40; the floor has a hole at x 118-122
            var ground = Empty("GroundArea", new Vector3(120f, 0f, 20f));
            Slab("Floor_A", new Vector3(99f, -1f, -1f), new Vector3(118f, 0f, 41f), parent: ground.transform);
            Slab("Floor_B", new Vector3(122f, -1f, -1f), new Vector3(141f, 0f, 41f), parent: ground.transform);
            Slab("Hill", new Vector3(130f, 0f, 30f), new Vector3(141f, 2f, 41f), parent: ground.transform);
            Slab("Roof", new Vector3(99f, 4.8f, -1f), new Vector3(110f, 5f, 10f), parent: ground.transform);
            Slab("Fog", new Vector3(110.5f, 0f, -1f), new Vector3(114.5f, 3f, 41f), trigger: true, parent: ground.transform);
            Slab("Pane", new Vector3(115f, 0f, -1f), new Vector3(117f, 4f, 41f), layer: 2, parent: ground.transform);
            Slab("Abyss", new Vector3(110f, -2200f, -1f), new Vector3(130f, -2100f, 41f), parent: ground.transform);
            var plate = Empty("Plate2D", new Vector3(125f, 3f, 20f), ground.transform);
            plate.AddComponent<BoxCollider2D>().size = new Vector2(10f, 10f);
            EditorSceneManager.SaveScene(scene, Made + "/WorldLab.unity");
        }

        /// <summary>A terrain whose trees are two prefabs: one with a LODGroup (LOD 0 a cube, LOD 1 a quad), one with two
        /// cubes; five trees of the first, three of the second.</summary>
        static void Terrain(Transform parent, Mesh cube, Mesh quad, Material material)
        {
            var lodTree = new GameObject("WldTreeLod");
            var t0 = Piece("Trunk", Vector3.zero, cube, material, lodTree.transform).GetComponent<Renderer>();
            var t1 = Piece("Card", Vector3.zero, quad, material, lodTree.transform).GetComponent<Renderer>();
            lodTree.AddComponent<LODGroup>().SetLODs(new[] { new LOD(0.5f, new[] { t0 }), new LOD(0.1f, new[] { t1 }) });
            var p0 = PrefabUtility.SaveAsPrefabAsset(lodTree, Made + "/WldTreeLod.prefab");
            Object.DestroyImmediate(lodTree);
            var bush = new GameObject("WldBush");
            Piece("Ball_A", Vector3.zero, cube, material, bush.transform);
            Piece("Ball_B", Vector3.up, cube, material, bush.transform);
            var p1 = PrefabUtility.SaveAsPrefabAsset(bush, Made + "/WldBush.prefab");
            Object.DestroyImmediate(bush);
            var data = new TerrainData { heightmapResolution = 33, size = new Vector3(20f, 10f, 20f) };
            data.treePrototypes = new[] { new TreePrototype { prefab = p0 }, new TreePrototype { prefab = p1 } };
            var trees = new TreeInstance[8];
            for (var i = 0; i < trees.Length; i++)
                trees[i] = new TreeInstance
                {
                    prototypeIndex = i < 5 ? 0 : 1, position = new Vector3(0.1f + 0.1f * i, 0f, 0.5f),
                    widthScale = 1f, heightScale = 1f, color = Color.white, lightmapColor = Color.white,
                };
            data.SetTreeInstances(trees, true);
            AssetDatabase.CreateAsset(data, Made + "/WldTerrain.asset");
            var terrain = UnityEngine.Terrain.CreateTerrainGameObject(data);
            terrain.name = "Forest";
            terrain.transform.SetParent(parent, false);
            terrain.transform.position = new Vector3(50f, 0f, 20f);
        }

        // The scene WldDirector loads additively: two shots.
        static void Side()
        {
            var scene = New();
            Empty("SideShot_A", new Vector3(0f, 0f, 30f)).AddComponent<WldShot>();
            Empty("SideShot_B", new Vector3(2f, 0f, 30f)).AddComponent<WldShot>();
            EditorSceneManager.SaveScene(scene, Made + "/WorldSide.unity");
        }
    }
}
