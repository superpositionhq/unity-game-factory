// Builds the asset family's test material under Assets/AssetTest/ (materials, a texture, an audio clip, a model, a
// ScriptableObject, a prefab and a scene), and runs the editor pass from a dirty untitled scene.
using System;
using System.Collections.Generic;
using System.IO;
using System.Text;
using AssetTest;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

namespace AssetTestEditor
{
    public static class BuildAssetTest
    {
        const string Root = "Assets/AssetTest";

        public static void Run()
        {
            foreach (var dir in new[] { "Materials", "Textures", "Audio", "Models", "Data", "Prefabs", "Scenes" })
                Directory.CreateDirectory(Root + "/" + dir);
            AddTag("Terrace");

            // texture
            var tex = new Texture2D(64, 64, TextureFormat.RGBA32, false);
            var px = new Color32[64 * 64];
            for (var i = 0; i < px.Length; i++) px[i] = new Color32(40, 160, 40, 255);
            tex.SetPixels32(px);
            File.WriteAllBytes(Root + "/Textures/Grass.png", tex.EncodeToPNG());
            AssetDatabase.ImportAsset(Root + "/Textures/Grass.png");
            var ti = (TextureImporter)AssetImporter.GetAtPath(Root + "/Textures/Grass.png");
            ti.isReadable = true;
            ti.textureCompression = TextureImporterCompression.Uncompressed;
            ti.maxTextureSize = 256;
            ti.SaveAndReimport();
            var grass = AssetDatabase.LoadAssetAtPath<Texture2D>(Root + "/Textures/Grass.png");

            // audio: 0.2 s of a 440 Hz sine, 16-bit stereo
            File.WriteAllBytes(Root + "/Audio/Beep.wav", Wav(44100, 2, 0.2f));
            AssetDatabase.ImportAsset(Root + "/Audio/Beep.wav");
            var ai = (AudioImporter)AssetImporter.GetAtPath(Root + "/Audio/Beep.wav");
            ai.forceToMono = true;
            var ss = ai.defaultSampleSettings;
            ss.loadType = AudioClipLoadType.Streaming;
            ai.defaultSampleSettings = ss;
            ai.SaveAndReimport();

            // model
            File.WriteAllText(Root + "/Models/Box.obj", "o Box\nv 0 0 0\nv 1 0 0\nv 1 1 0\nv 0 1 0\nf 1 2 3\nf 1 3 4\n");
            AssetDatabase.ImportAsset(Root + "/Models/Box.obj");
            var mi = (ModelImporter)AssetImporter.GetAtPath(Root + "/Models/Box.obj");
            mi.globalScale = 2f;
            mi.animationType = ModelImporterAnimationType.None;
            mi.SaveAndReimport();

            // materials
            var road = new Material(Shader.Find("Universal Render Pipeline/Lit"));
            road.SetColor("_BaseColor", new Color(0.2f, 0.4f, 0.6f, 1f));
            road.SetFloat("_Smoothness", 0.75f);
            road.SetFloat("_Metallic", 0.25f);
            road.SetTexture("_BaseMap", grass);
            road.SetColor("_EmissionColor", new Color(1f, 0.5f, 0f, 1f));
            road.EnableKeyword("_EMISSION");
            road.globalIlluminationFlags = MaterialGlobalIlluminationFlags.RealtimeEmissive;  // else URP's import turns _EMISSION off
            AssetDatabase.CreateAsset(road, Root + "/Materials/Road.mat");
            var glow = new Material(Shader.Find("Universal Render Pipeline/Unlit"));
            glow.SetColor("_BaseColor", new Color(1f, 0f, 0f, 0.5f));
            glow.SetFloat("_Cutoff", 0.3f);
            glow.SetFloat("_AlphaClip", 1f);
            glow.EnableKeyword("_ALPHATEST_ON");
            AssetDatabase.CreateAsset(glow, Root + "/Materials/Glow.mat");
            // a shader of the test's own (Shaders/Params.shader): URP recomputes its own shaders' vectors on import
            AssetDatabase.ImportAsset(Root + "/Shaders/Params.shader");
            var fx = new Material(AssetDatabase.LoadAssetAtPath<Shader>(Root + "/Shaders/Params.shader"));
            fx.SetVector("_Wind", new Vector4(1, 2, 3, 4));
            fx.SetInteger("_Steps", 5);
            AssetDatabase.CreateAsset(fx, Root + "/Materials/Fx.mat");
            var broken = new Material(Shader.Find("Hidden/InternalErrorShader"));
            AssetDatabase.CreateAsset(broken, Root + "/Materials/Broken.mat");

            // scriptable object
            var waves = ScriptableObject.CreateInstance<WaveSet>();
            waves.waves = new List<Wave> { new Wave { count = 5 }, new Wave { count = 10 }, new Wave { count = 15, delay = 1.5f } };
            waves.skin = road;
            AssetDatabase.CreateAsset(waves, Root + "/Data/Waves.asset");
            AssetDatabase.SaveAssets();

            // prefab
            var lamp = new GameObject("Lamp");
            lamp.AddComponent<Spinner>().speed = 90f;
            Prim(PrimitiveType.Cylinder, "Pole", lamp.transform, new Vector3(0, 1, 0), road);
            var bulb = Prim(PrimitiveType.Sphere, "Bulb", lamp.transform, new Vector3(0, 2, 0), glow);
            UnityEngine.Object.DestroyImmediate(bulb.GetComponent<Collider>());
            var bas = Prim(PrimitiveType.Cube, "Base", lamp.transform, Vector3.zero, null);
            bas.GetComponent<Collider>().enabled = false;
            var ls = new GameObject("LightSrc");
            ls.transform.SetParent(lamp.transform, false);
            ls.transform.localPosition = new Vector3(0, 2, 0);
            ls.AddComponent<Light>().intensity = 3f;
            PrefabUtility.SaveAsPrefabAsset(lamp, Root + "/Prefabs/Lamp.prefab");
            UnityEngine.Object.DestroyImmediate(lamp);
            var lampAsset = AssetDatabase.LoadAssetAtPath<GameObject>(Root + "/Prefabs/Lamp.prefab");

            // scene
            var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            var a = Prim(PrimitiveType.Cube, "Terrace_A", null, new Vector3(0, 0, 0), road); a.tag = "Terrace";
            var b = Prim(PrimitiveType.Cube, "Terrace_B", null, new Vector3(5, 0, 0), null); b.tag = "Terrace";
            UnityEngine.Object.DestroyImmediate(b.GetComponent<Collider>());
            var c = Prim(PrimitiveType.Cube, "Terrace_C", null, new Vector3(10, 0, 0), glow); c.tag = "Terrace";
            c.SetActive(false);
            var d = Prim(PrimitiveType.Cube, "Terrace_D", null, new Vector3(20, 0, 0), null); d.tag = "Terrace";
            d.GetComponent<MeshRenderer>().sharedMaterials = new Material[] { road, null };
            var group = new GameObject("Group");
            group.transform.position = new Vector3(0, 0, 10);
            var w1 = Prim(PrimitiveType.Cube, "Wall1", group.transform, new Vector3(-2, 0, 0), road);
            var trim = Prim(PrimitiveType.Cube, "Trim", w1.transform, new Vector3(0, 1, 0), road);
            UnityEngine.Object.DestroyImmediate(trim.GetComponent<Collider>());
            var w2 = Prim(PrimitiveType.Cube, "Wall2", group.transform, new Vector3(0, 0, 0), road);
            UnityEngine.Object.DestroyImmediate(w2.GetComponent<Collider>());
            var w3 = Prim(PrimitiveType.Cube, "Wall3", group.transform, new Vector3(2, 0, 0), road);
            ((BoxCollider)w3.GetComponent<Collider>()).isTrigger = true;
            var inst = (GameObject)PrefabUtility.InstantiatePrefab(lampAsset, scene);
            inst.transform.position = new Vector3(3, 0, 3);
            inst.layer = LayerMask.NameToLayer("Water");
            Prim(PrimitiveType.Cube, "Broken", null, new Vector3(40, 0, 0), broken);
            var fan = new GameObject("FanObj");
            fan.transform.position = new Vector3(60, 0, 0);
            fan.AddComponent<Spinner>();
            Prim(PrimitiveType.Quad, "FxQuad", fan.transform, new Vector3(0, 1, 0), fx);
            EditorSceneManager.SaveScene(scene, Root + "/Scenes/AssetLevel.unity");
            AssetDatabase.SaveAssets();
            Debug.Log("AssetTest: built");
        }

        /// <summary>The editor pass started from a dirty untitled scene (the state the pass may meet).</summary>
        public static void RunDirty()
        {
            EditorSceneManager.NewScene(NewSceneSetup.DefaultGameObjects, NewSceneMode.Single);
            new GameObject("Unsaved");
            var pass = Type.GetType("TaskProbe.EditorTools.AssetPass, TaskProbe.Editor");
            pass.GetMethod("Run").Invoke(null, null);
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
