// The asset family's material (probe_tests/asset), made under Assets/ProbeTests/asset/Made/: a texture, a sound, a
// model, materials, a ScriptableObject, an animator controller, a mesh of two parts, prefabs (a variant and a nested one
// among them), the scenes the editor pass reads (Level, Other, Big) and the one a play opens (Facts). Some assets are
// deleted once the scenes that name them are saved (missing references); Deleted.txt says which, with their GUIDs. The
// project's own player settings are set to the least helpful ones: the play shows what the checker's build gives
// whatever a game has.
using System;
using System.IO;
using System.Linq;
using System.Text;
using UnityEditor;
using UnityEditor.Animations;
using UnityEditor.Build;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering.Universal;
using UnityEngine.UI;

namespace ProbeTests.Asset
{
    public static class AssetScenes
    {
        const string Family = "Assets/ProbeTests/asset";
        const string Made = Family + "/Made";

        public static void Build()
        {
            if (!AssetDatabase.IsValidFolder(Made)) AssetDatabase.CreateFolder(Family, "Made");
            AssetDatabase.CreateFolder(Made, "Sub Dir");
            AddTag("Terrace");
            Hostile();

            // a texture, a sound, a model
            var tex = new Texture2D(64, 64, TextureFormat.RGBA32, false);
            tex.SetPixels32(Enumerable.Repeat(new Color32(40, 160, 40, 255), 64 * 64).ToArray());
            File.WriteAllBytes(Made + "/Grass.png", tex.EncodeToPNG());
            UnityEngine.Object.DestroyImmediate(tex);
            AssetDatabase.ImportAsset(Made + "/Grass.png");
            var textureImporter = (TextureImporter)AssetImporter.GetAtPath(Made + "/Grass.png");
            textureImporter.isReadable = true;
            textureImporter.textureCompression = TextureImporterCompression.Uncompressed;
            textureImporter.maxTextureSize = 256;
            textureImporter.SaveAndReimport();
            var grass = AssetDatabase.LoadAssetAtPath<Texture2D>(Made + "/Grass.png");

            File.WriteAllBytes(Made + "/Beep.wav", Wav(44100, 2, 0.2f));
            AssetDatabase.ImportAsset(Made + "/Beep.wav");
            var audioImporter = (AudioImporter)AssetImporter.GetAtPath(Made + "/Beep.wav");
            audioImporter.forceToMono = true;
            var sampling = audioImporter.defaultSampleSettings;
            sampling.loadType = AudioClipLoadType.Streaming;
            audioImporter.defaultSampleSettings = sampling;
            audioImporter.SaveAndReimport();
            AssetDatabase.CopyAsset(Made + "/Beep.wav", Made + "/LostBeep.wav");

            File.WriteAllText(Made + "/Box.obj", "o Box\nv 0 0 0\nv 1 0 0\nv 1 1 0\nv 0 1 0\nf 1 2 3\nf 1 3 4\n");
            AssetDatabase.ImportAsset(Made + "/Box.obj");
            var modelImporter = (ModelImporter)AssetImporter.GetAtPath(Made + "/Box.obj");
            modelImporter.globalScale = 2f;
            modelImporter.animationType = ModelImporterAnimationType.None;
            modelImporter.SaveAndReimport();

            // materials: URP Lit and Unlit, the family's own shader, the error shader
            var road = Lit("Road", 0.75f);
            road.SetColor("_BaseColor", new Color(0.2f, 0.4f, 0.6f, 1f));
            road.SetFloat("_Metallic", 0.25f);
            road.SetTexture("_BaseMap", grass);
            road.SetColor("_EmissionColor", new Color(1f, 0.5f, 0f, 1f));
            road.EnableKeyword("_EMISSION");
            road.globalIlluminationFlags = MaterialGlobalIlluminationFlags.RealtimeEmissive;  // else URP's import turns _EMISSION off
            AssetDatabase.CreateAsset(road, Made + "/Road.mat");
            var glow = new Material(Shader.Find("Universal Render Pipeline/Unlit"));
            glow.SetColor("_BaseColor", new Color(1f, 0f, 0f, 0.5f));
            glow.SetFloat("_Cutoff", 0.3f);
            glow.SetFloat("_AlphaClip", 1f);
            glow.EnableKeyword("_ALPHATEST_ON");
            AssetDatabase.CreateAsset(glow, Made + "/Glow.mat");
            var fx = new Material(AssetDatabase.LoadAssetAtPath<Shader>(Family + "/Assets/Params.shader"));
            fx.SetVector("_Wind", new Vector4(1, 2, 3, 4));
            fx.SetInteger("_Steps", 5);
            AssetDatabase.CreateAsset(fx, Made + "/Fx.mat");
            var broken = new Material(Shader.Find("Hidden/InternalErrorShader"));
            AssetDatabase.CreateAsset(broken, Made + "/Broken.mat");
            AssetDatabase.CreateAsset(Lit("Road (2)", 0.5f), Made + "/Sub Dir/Road (2).mat");
            AssetDatabase.CreateAsset(Lit("Märkt Ünï", 0.25f), Made + "/Sub Dir/Märkt Ünï.mat");
            var lost = Lit("Lost", 0.5f);
            AssetDatabase.CreateAsset(lost, Made + "/Lost.mat");

            // data: a ScriptableObject, an animator controller, a mesh of two parts
            var waves = ScriptableObject.CreateInstance<AssetWaveSet>();
            waves.waves.Add(new AssetWave { count = 5 });
            waves.waves.Add(new AssetWave { count = 10 });
            waves.waves.Add(new AssetWave { count = 15, delay = 1.5f });
            waves.skin = road;
            AssetDatabase.CreateAsset(waves, Made + "/Waves.asset");
            var anim = AnimatorController.CreateAnimatorControllerAtPath(Made + "/Anim.controller");
            anim.AddParameter("Speed", AnimatorControllerParameterType.Float);
            anim.AddParameter("Run", AnimatorControllerParameterType.Bool);
            var parts = new Mesh { name = "TwoParts" };
            parts.vertices = new[] { Vector3.zero, Vector3.right, Vector3.up, new Vector3(1f, 1f, 0f) };
            parts.subMeshCount = 2;
            parts.SetTriangles(new[] { 0, 2, 1 }, 0);
            parts.SetTriangles(new[] { 1, 2, 3 }, 1);
            parts.RecalculateBounds();
            AssetDatabase.CreateAsset(parts, Made + "/TwoParts.asset");
            AssetDatabase.SaveAssets();

            // prefabs: a lamp, a variant of it, a post with a lamp in it, one that changes itself when it loads
            var lamp = new GameObject("Lamp");
            lamp.AddComponent<AssetSpinner>().speed = 90f;
            Prim(PrimitiveType.Cylinder, "Pole", lamp.transform, new Vector3(0f, 1f, 0f), road);
            var bulb = Prim(PrimitiveType.Sphere, "Bulb", lamp.transform, new Vector3(0f, 2f, 0f), glow);
            UnityEngine.Object.DestroyImmediate(bulb.GetComponent<Collider>());
            var foot = Prim(PrimitiveType.Cube, "Base", lamp.transform, Vector3.zero, null);
            foot.GetComponent<Collider>().enabled = false;
            var source = new GameObject("LightSrc");
            source.transform.SetParent(lamp.transform, false);
            source.transform.localPosition = new Vector3(0f, 2f, 0f);
            source.AddComponent<Light>().intensity = 3f;
            var lampAsset = Prefab(lamp, "Lamp");
            var variant = (GameObject)PrefabUtility.InstantiatePrefab(lampAsset);
            variant.GetComponent<AssetSpinner>().speed = 120f;
            var variantAsset = Prefab(variant, "LampVariant");
            var post = new GameObject("Post");
            var inner = (GameObject)PrefabUtility.InstantiatePrefab(lampAsset);
            inner.transform.SetParent(post.transform, false);
            inner.transform.localPosition = new Vector3(0f, 3f, 0f);
            var postAsset = Prefab(post, "Post");
            var dirty = new GameObject("Dirty");
            dirty.AddComponent<AssetDirtier>();
            Prefab(dirty, "Dirty");
            var goneAsset = Prefab(new GameObject("Gone"), "Gone");

            Level(road, glow, fx, broken, lost, lampAsset, variantAsset, postAsset, goneAsset);
            Other();
            Big();
            Facts(road, lost);

            // references to missing assets: the scenes are saved, then what they name goes
            var deleted = new StringBuilder();
            foreach (var name in new[] { "Lost.mat", "LostBeep.wav", "Gone.prefab" })
            {
                deleted.Append(name).Append(' ').Append(AssetDatabase.AssetPathToGUID(Made + "/" + name)).Append('\n');
                AssetDatabase.DeleteAsset(Made + "/" + name);
            }
            File.WriteAllText(Made + "/Deleted.txt", deleted.ToString());
            AssetDatabase.ImportAsset(Made + "/Deleted.txt");
            AssetDatabase.SaveAssets();
        }

        /// <summary>The player settings of a new project at their least helpful for the plays: the checker's build must
        /// give the plays a company name of their own, no splash screen, several instances, the player log, Mono, no
        /// static batching, no development build, and the play's window whatever these say.</summary>
        static void Hostile()
        {
            PlayerSettings.companyName = "DefaultCompany";
            PlayerSettings.SplashScreen.show = true;
            PlayerSettings.fullScreenMode = FullScreenMode.FullScreenWindow;
            PlayerSettings.defaultIsNativeResolution = false;
            PlayerSettings.defaultScreenWidth = 1920;
            PlayerSettings.defaultScreenHeight = 1080;
            PlayerSettings.resizableWindow = true;
            PlayerSettings.runInBackground = false;
            PlayerSettings.visibleInBackground = false;
            PlayerSettings.forceSingleInstance = true;
            PlayerSettings.usePlayerLog = false;
            PlayerSettings.SetScriptingBackend(NamedBuildTarget.Standalone, ScriptingImplementation.IL2CPP);
            PlayerSettings.SetStaticBatchingForPlatform(BuildTarget.StandaloneWindows64, true);
            PlayerSettings.SetManagedStrippingLevel(NamedBuildTarget.Standalone, ManagedStrippingLevel.High);
            EditorUserBuildSettings.development = true;
        }

        // Tagged cubes (A on Road with a collider, B on the default material without one, C inactive, D with slots
        // [Road, empty]); a group (Wall1 with a collider and a Trim child without, Wall2 without, Wall3 a trigger); the
        // lamp prefab on layer Water; a cube on the error shader; a spinner with a quad on the family's shader; a mesh of
        // two parts with one material; the lamp's variant; the post with its nested lamp; an object that changes itself
        // when it loads; a prefab that is gone and a material that is gone; a cube whose collider is a 2D one.
        static void Level(Material road, Material glow, Material fx, Material broken, Material lost, GameObject lamp,
            GameObject variant, GameObject post, GameObject gone)
        {
            var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            Prim(PrimitiveType.Cube, "Terrace_A", null, Vector3.zero, road).tag = "Terrace";
            var b = Prim(PrimitiveType.Cube, "Terrace_B", null, new Vector3(5f, 0f, 0f), null);
            b.tag = "Terrace";
            UnityEngine.Object.DestroyImmediate(b.GetComponent<Collider>());
            var c = Prim(PrimitiveType.Cube, "Terrace_C", null, new Vector3(10f, 0f, 0f), glow);
            c.tag = "Terrace";
            c.SetActive(false);
            var d = Prim(PrimitiveType.Cube, "Terrace_D", null, new Vector3(20f, 0f, 0f), null);
            d.tag = "Terrace";
            d.GetComponent<MeshRenderer>().sharedMaterials = new[] { road, null };
            var group = new GameObject("Group");
            group.transform.position = new Vector3(0f, 0f, 10f);
            var wall1 = Prim(PrimitiveType.Cube, "Wall1", group.transform, new Vector3(-2f, 0f, 0f), road);
            var trim = Prim(PrimitiveType.Cube, "Trim", wall1.transform, new Vector3(0f, 1f, 0f), road);
            UnityEngine.Object.DestroyImmediate(trim.GetComponent<Collider>());
            var wall2 = Prim(PrimitiveType.Cube, "Wall2", group.transform, Vector3.zero, road);
            UnityEngine.Object.DestroyImmediate(wall2.GetComponent<Collider>());
            var wall3 = Prim(PrimitiveType.Cube, "Wall3", group.transform, new Vector3(2f, 0f, 0f), road);
            ((BoxCollider)wall3.GetComponent<Collider>()).isTrigger = true;
            var lampHere = (GameObject)PrefabUtility.InstantiatePrefab(lamp, scene);
            lampHere.transform.position = new Vector3(3f, 0f, 3f);
            lampHere.layer = LayerMask.NameToLayer("Water");
            Prim(PrimitiveType.Cube, "Broken", null, new Vector3(40f, 0f, 0f), broken);
            var fan = new GameObject("FanObj");
            fan.transform.position = new Vector3(60f, 0f, 0f);
            fan.AddComponent<AssetSpinner>();
            Prim(PrimitiveType.Quad, "FxQuad", fan.transform, new Vector3(0f, 1f, 0f), fx);
            var two = new GameObject("TwoParts");
            two.transform.position = new Vector3(80f, 0f, 0f);
            two.AddComponent<MeshFilter>().sharedMesh = AssetDatabase.LoadAssetAtPath<Mesh>(Made + "/TwoParts.asset");
            two.AddComponent<MeshRenderer>().sharedMaterial = road;
            var variantHere = (GameObject)PrefabUtility.InstantiatePrefab(variant, scene);
            variantHere.name = "Variant";
            variantHere.transform.position = new Vector3(100f, 0f, 0f);
            var postHere = (GameObject)PrefabUtility.InstantiatePrefab(post, scene);
            postHere.transform.position = new Vector3(120f, 0f, 0f);
            var dirtier = new GameObject("Dirtier");
            dirtier.transform.position = new Vector3(180f, 0f, 0f);
            dirtier.AddComponent<AssetDirtier>();
            var goneHere = (GameObject)PrefabUtility.InstantiatePrefab(gone, scene);
            goneHere.transform.position = new Vector3(140f, 0f, 0f);
            Prim(PrimitiveType.Cube, "Lost", null, new Vector3(160f, 0f, 0f), lost);
            var flat = Prim(PrimitiveType.Cube, "Flat", null, new Vector3(200f, 0f, 0f), road);
            UnityEngine.Object.DestroyImmediate(flat.GetComponent<Collider>());
            flat.AddComponent<BoxCollider2D>();
            EditorSceneManager.SaveScene(scene, Made + "/Level.unity");
        }

        // A second scene with a tagged cube of its own: measures of two scenes in one pass don't mix.
        static void Other()
        {
            var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            Prim(PrimitiveType.Cube, "Other_A", null, Vector3.zero, null).tag = "Terrace";
            Prim(PrimitiveType.Cube, "Other_B", null, new Vector3(2f, 0f, 0f), null);
            EditorSceneManager.SaveScene(scene, Made + "/Other.unity");
        }

        // 5,051 objects: a marker that says when the scene loads, and 50 rows of 100 cells.
        static void Big()
        {
            var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            new GameObject("BigMarker").AddComponent<AssetDirtier>();
            for (var row = 0; row < 50; row++)
            {
                var parent = new GameObject("Row_" + row.ToString("00"));
                parent.transform.position = new Vector3(row, 0f, 0f);
                for (var cell = 0; cell < 100; cell++)
                {
                    var child = new GameObject("Cell_" + cell.ToString("000"));
                    child.transform.SetParent(parent.transform, false);
                    child.transform.localPosition = new Vector3(0f, 0f, cell);
                }
            }
            EditorSceneManager.SaveScene(scene, Made + "/Big.unity");
        }

        // The play's scene: a URP camera and a uGUI image (scripts of packages), what the build's facts are read from,
        // two cubes marked static that share a material (static batching would combine them), and references to a
        // material and a sound that are gone.
        static void Facts(Material road, Material lost)
        {
            var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            var camera = new GameObject("Main Camera");
            camera.tag = "MainCamera";
            camera.AddComponent<Camera>();
            camera.AddComponent<UniversalAdditionalCameraData>();
            camera.transform.position = new Vector3(0f, 1f, -6f);
            var sun = new GameObject("Sun");
            sun.AddComponent<Light>().type = LightType.Directional;
            sun.transform.rotation = Quaternion.Euler(50f, -30f, 0f);
            new GameObject("Facts").AddComponent<AssetFacts>();
            foreach (var (name, x) in new[] { ("Static_A", -1.5f), ("Static_B", 1.5f) })
            {
                var cube = Prim(PrimitiveType.Cube, name, null, new Vector3(x, 0f, 0f), road);
                GameObjectUtility.SetStaticEditorFlags(cube, StaticEditorFlags.BatchingStatic);
            }
            var canvas = new GameObject("Canvas", typeof(Canvas));
            canvas.GetComponent<Canvas>().renderMode = RenderMode.ScreenSpaceOverlay;
            var badge = new GameObject("Badge", typeof(Image));
            badge.transform.SetParent(canvas.transform, false);
            Prim(PrimitiveType.Cube, "Lost", null, new Vector3(0f, 0f, 5f), lost);
            new GameObject("Echo").AddComponent<AudioSource>().clip = AssetDatabase.LoadAssetAtPath<AudioClip>(Made + "/LostBeep.wav");
            EditorSceneManager.SaveScene(scene, Made + "/Facts.unity");
        }

        static Material Lit(string name, float smoothness)
        {
            var material = new Material(Shader.Find("Universal Render Pipeline/Lit")) { name = name };
            material.SetFloat("_Smoothness", smoothness);
            return material;
        }

        static GameObject Prefab(GameObject root, string name)
        {
            var asset = PrefabUtility.SaveAsPrefabAsset(root, Made + "/" + name + ".prefab");
            UnityEngine.Object.DestroyImmediate(root);
            return asset;
        }

        static GameObject Prim(PrimitiveType type, string name, Transform parent, Vector3 local, Material material)
        {
            var go = GameObject.CreatePrimitive(type);
            go.name = name;
            if (parent != null) go.transform.SetParent(parent, false);
            go.transform.localPosition = local;
            if (material != null) go.GetComponent<Renderer>().sharedMaterial = material;
            return go;
        }

        static void AddTag(string tag)
        {
            var manager = new SerializedObject(AssetDatabase.LoadAllAssetsAtPath("ProjectSettings/TagManager.asset")[0]);
            var tags = manager.FindProperty("tags");
            for (var i = 0; i < tags.arraySize; i++)
                if (tags.GetArrayElementAtIndex(i).stringValue == tag) return;
            tags.InsertArrayElementAtIndex(tags.arraySize);
            tags.GetArrayElementAtIndex(tags.arraySize - 1).stringValue = tag;
            manager.ApplyModifiedProperties();
        }

        /// <summary>`seconds` of a 440 Hz sine as a 16-bit PCM WAV file.</summary>
        static byte[] Wav(int rate, int channels, float seconds)
        {
            var frames = (int)(rate * seconds);
            var data = new byte[frames * channels * 2];
            for (var f = 0; f < frames; f++)
            {
                var s = (short)(Math.Sin(2 * Math.PI * 440 * f / rate) * 12000);
                for (var ch = 0; ch < channels; ch++)
                {
                    data[(f * channels + ch) * 2] = (byte)(s & 0xff);
                    data[(f * channels + ch) * 2 + 1] = (byte)((s >> 8) & 0xff);
                }
            }
            using (var ms = new MemoryStream())
            using (var w = new BinaryWriter(ms))
            {
                w.Write(Encoding.ASCII.GetBytes("RIFF")); w.Write(36 + data.Length); w.Write(Encoding.ASCII.GetBytes("WAVE"));
                w.Write(Encoding.ASCII.GetBytes("fmt ")); w.Write(16); w.Write((short)1); w.Write((short)channels);
                w.Write(rate); w.Write(rate * channels * 2); w.Write((short)(channels * 2)); w.Write((short)16);
                w.Write(Encoding.ASCII.GetBytes("data")); w.Write(data.Length); w.Write(data);
                w.Flush();
                return ms.ToArray();
            }
        }
    }
}
