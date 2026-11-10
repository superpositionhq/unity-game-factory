// Builds the light / grading / audio test scenes of the TaskProbe light family (run with probe.py exec
// LightTests.EditorSteps.LightTestScenes.Run). Everything is made from code: sine-tone WAV files, an AudioMixer with a
// -20 dB "SFX" group (through the editor's internal AudioMixerController, by reflection), volume profiles, materials.
using System;
using System.Collections.Generic;
using System.IO;
using System.Reflection;
using LightTests;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Audio;
using UnityEngine.Rendering;
using UnityEngine.Rendering.Universal;

namespace LightTests.EditorSteps
{
    public static class LightTestScenes
    {
        const string Dir = "Assets/LightTests";
        const string SceneDir = "Assets/Scenes/LightTests";

        public static void Run()
        {
            Directory.CreateDirectory(Dir);
            Directory.CreateDirectory(SceneDir);
            var clips = MakeClips();
            var sfx = MakeMixer();
            var scenes = new List<string>
            {
                LightLab(), GradeLab(), AudioLab(clips, sfx), AudioLab2(clips), AudioRolloff(clips, sfx),
            };
            var list = new List<EditorBuildSettingsScene>(EditorBuildSettings.scenes);
            foreach (var s in scenes)
                if (!list.Exists(e => e.path == s)) list.Add(new EditorBuildSettingsScene(s, true));
            EditorBuildSettings.scenes = list.ToArray();
            AssetDatabase.SaveAssets();
            Debug.Log("LightTestScenes: built " + string.Join(", ", scenes));
        }

        // ---------------------------------------------------------------- audio assets

        static Dictionary<string, AudioClip> MakeClips()
        {
            var tones = new (string name, float hz, float seconds)[]
            {
                ("Tone440", 440f, 2f), ("Music220", 220f, 2f), ("Late660", 660f, 2f), ("Muted330", 330f, 2f),
                ("Mixed550", 550f, 2f), ("Custom770", 770f, 2f), ("Shot880", 880f, 1.5f), ("Point990", 990f, 1.5f),
                ("Room2_495", 495f, 2f), ("Near2_605", 605f, 2f),
            };
            var found = new Dictionary<string, AudioClip>();
            foreach (var (name, hz, seconds) in tones)
            {
                var path = $"{Dir}/{name}.wav";
                WriteWav(path, hz, seconds, 0.5f);
                AssetDatabase.ImportAsset(path, ImportAssetOptions.ForceUpdate);
                found[name] = AssetDatabase.LoadAssetAtPath<AudioClip>(path);
                if (found[name] == null) Debug.LogError("LightTestScenes: no clip at " + path);
            }
            return found;
        }

        /// <summary>A mono 16-bit 44.1 kHz sine of whole cycles (so it loops without a click).</summary>
        static void WriteWav(string path, float hz, float seconds, float amplitude)
        {
            const int rate = 44100;
            var n = (int)(rate * seconds);
            using var w = new BinaryWriter(File.Create(path));
            w.Write(new[] { (byte)'R', (byte)'I', (byte)'F', (byte)'F' });
            w.Write(36 + n * 2);
            w.Write(new[] { (byte)'W', (byte)'A', (byte)'V', (byte)'E', (byte)'f', (byte)'m', (byte)'t', (byte)' ' });
            w.Write(16);
            w.Write((short)1);
            w.Write((short)1);
            w.Write(rate);
            w.Write(rate * 2);
            w.Write((short)2);
            w.Write((short)16);
            w.Write(new[] { (byte)'d', (byte)'a', (byte)'t', (byte)'a' });
            w.Write(n * 2);
            for (var i = 0; i < n; i++)
                w.Write((short)Mathf.RoundToInt(Mathf.Sin(2f * Mathf.PI * hz * i / rate) * amplitude * 32767f));
        }

        /// <summary>TestMix.mixer with a child group "SFX" at -20 dB, made through the editor's internal
        /// AudioMixerController (Unity has no public API to make a mixer). Null when that fails.</summary>
        static AudioMixerGroup MakeMixer()
        {
            const string path = Dir + "/TestMix.mixer";
            try
            {
                AssetDatabase.DeleteAsset(path);
                var controller = typeof(Editor).Assembly.GetType("UnityEditor.Audio.AudioMixerController");
                const BindingFlags all = BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Static | BindingFlags.Instance;
                var mixer = controller.GetMethod("CreateMixerControllerAtPath", all).Invoke(null, new object[] { path });
                var master = controller.GetProperty("masterGroup", all).GetValue(mixer);
                var group = controller.GetMethod("CreateNewGroup", all).Invoke(mixer, new object[] { "SFX", false });
                controller.GetMethod("AddChildToParent", all).Invoke(mixer, new[] { group, master });
                var snapshot = controller.GetProperty("TargetSnapshot", all).GetValue(mixer);
                var setVolume = group.GetType().GetMethod("SetValueForVolume", all);
                setVolume.Invoke(group, new[] { mixer, snapshot, (object)(-20f) });
                EditorUtility.SetDirty((UnityEngine.Object)mixer);
                AssetDatabase.SaveAssets();
                var asset = AssetDatabase.LoadAssetAtPath<AudioMixer>(path);
                var groups = asset.FindMatchingGroups("SFX");
                Debug.Log($"LightTestScenes: mixer {path}: {groups.Length} SFX group(s)");
                return groups.Length > 0 ? groups[0] : null;
            }
            catch (Exception e)
            {
                Debug.LogError("LightTestScenes: the AudioMixer couldn't be made: " + (e.InnerException ?? e));
                return null;
            }
        }

        // ---------------------------------------------------------------- helpers

        static GameObject Box(string name, Vector3 centre, Vector3 size, Transform parent = null)
        {
            var go = GameObject.CreatePrimitive(PrimitiveType.Cube);
            go.name = name;
            go.transform.position = centre;
            go.transform.localScale = size;
            if (parent != null) go.transform.SetParent(parent, true);
            return go;
        }

        /// <summary>A closed room of 10 x 4 x 10 m around (x, 2, z): floor, roof and four walls 0.2 m thick.</summary>
        static Transform Room(string name, float x, float z = 0f)
        {
            var root = new GameObject(name).transform;
            Box("Floor", new Vector3(x, -0.1f, z), new Vector3(10.4f, 0.2f, 10.4f), root);
            Box("Roof", new Vector3(x, 4.1f, z), new Vector3(10.4f, 0.2f, 10.4f), root);
            Box("WallN", new Vector3(x, 2f, z + 5.1f), new Vector3(10.4f, 4.4f, 0.2f), root);
            Box("WallS", new Vector3(x, 2f, z - 5.1f), new Vector3(10.4f, 4.4f, 0.2f), root);
            Box("WallE", new Vector3(x + 5.1f, 2f, z), new Vector3(0.2f, 4.4f, 10.4f), root);
            Box("WallW", new Vector3(x - 5.1f, 2f, z), new Vector3(0.2f, 4.4f, 10.4f), root);
            return root;
        }

        static Light MakeLight(string name, LightType type, Vector3 at, Vector3 euler, Color colour, float intensity, float range, Transform parent = null)
        {
            var go = new GameObject(name);
            go.transform.position = at;
            go.transform.eulerAngles = euler;
            if (parent != null) go.transform.SetParent(parent, true);
            var l = go.AddComponent<Light>();
            l.type = type;
            l.color = colour;
            l.intensity = intensity;
            l.range = range;
            l.shadows = LightShadows.None;
            l.lightmapBakeType = LightmapBakeType.Realtime;
            return l;
        }

        static Camera MakeCamera(string name, Vector3 at, Vector3 euler, Transform parent = null, bool main = true)
        {
            var go = new GameObject(name);
            if (parent != null) go.transform.SetParent(parent, false);
            go.transform.position = at;
            go.transform.eulerAngles = euler;
            var cam = go.AddComponent<Camera>();
            if (main) go.tag = "MainCamera";
            var data = go.AddComponent<UniversalAdditionalCameraData>();
            data.renderPostProcessing = true;
            return cam;
        }

        static string Save(string name)
        {
            var path = $"{SceneDir}/{name}.unity";
            EditorSceneManager.SaveScene(EditorSceneManager.GetActiveScene(), path);
            return path;
        }

        static T Add<T>(VolumeProfile profile) where T : VolumeComponent
        {
            var c = profile.Add<T>(false);
            c.name = typeof(T).Name;
            AssetDatabase.AddObjectToAsset(c, profile);
            return c;
        }

        static VolumeProfile Profile(string name)
        {
            var path = $"{Dir}/{name}.asset";
            AssetDatabase.DeleteAsset(path);
            var p = ScriptableObject.CreateInstance<VolumeProfile>();
            AssetDatabase.CreateAsset(p, path);
            return p;
        }

        // ---------------------------------------------------------------- LightLab

        static string LightLab()
        {
            EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            RenderSettings.ambientMode = AmbientMode.Flat;
            RenderSettings.ambientLight = new Color(0.2f, 0.3f, 0.4f);
            RenderSettings.skybox = AssetDatabase.GetBuiltinExtraResource<Material>("Default-Skybox.mat");

            // A: a point light 2 m above the point; a second, warm and on a colour temperature, switched on at 3 s
            var a = Room("RoomA", 0f);
            MakeLight("PointA", LightType.Point, new Vector3(0f, 3f, 0f), Vector3.zero, Color.white, 2f, 10f, a);
            var warm = MakeLight("SwitchedA", LightType.Point, new Vector3(3f, 3f, 3f), Vector3.zero, new Color(1f, 0.5f, 0.25f), 1.5f, 8f, a);
            warm.useColorTemperature = true;
            warm.colorTemperature = 2700f;
            // B: a spot straight down, 60 degrees outer, 30 inner
            var b = Room("RoomB", 20f);
            var spot = MakeLight("SpotB", LightType.Spot, new Vector3(20f, 3f, 0f), new Vector3(90f, 0f, 0f), Color.white, 3f, 10f, b);
            spot.spotAngle = 60f;
            spot.innerSpotAngle = 30f;
            // C: a point light behind a wall that splits the room
            var c = Room("RoomC", 40f);
            MakeLight("PointC", LightType.Point, new Vector3(40f, 3f, -3f), Vector3.zero, Color.white, 2f, 12f, c);
            Box("SplitWall", new Vector3(40f, 2f, 0f), new Vector3(10f, 4f, 0.2f), c);
            // outdoors: ground, a roof on posts, the sun on a colour temperature
            Box("Ground", new Vector3(75f, -0.1f, 0f), new Vector3(50f, 0.2f, 40f));
            Box("Shelter", new Vector3(73f, 3f, 0f), new Vector3(6f, 0.2f, 6f));
            var sun = MakeLight("Sun", LightType.Directional, new Vector3(0f, 50f, 0f), new Vector3(50f, -30f, 0f), Color.white, 1.2f, 10f);
            sun.useColorTemperature = true;
            sun.colorTemperature = 4000f;
            sun.shadows = LightShadows.Soft;

            var cam = MakeCamera("Camera", new Vector3(66f, 3f, -12f), new Vector3(10f, 0f, 0f));
            var checker = MakeCamera("CullCheck", new Vector3(40f, 150f, 0f), new Vector3(90f, 0f, 0f), null, false);
            checker.orthographic = true;
            checker.orthographicSize = 60f;
            checker.farClipPlane = 400f;
            checker.enabled = false;
            var director = new GameObject("Director").AddComponent<LightDirector>();
            director.switchOn = warm;
            director.cullFrom = checker;
            return Save("LightLab");
        }

        // ---------------------------------------------------------------- GradeLab

        static string GradeLab()
        {
            EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            RenderSettings.ambientMode = AmbientMode.Flat;
            RenderSettings.ambientLight = new Color(0.1f, 0.1f, 0.1f);
            RenderSettings.fog = true;
            RenderSettings.fogMode = FogMode.ExponentialSquared;
            RenderSettings.fogDensity = 0.001f;
            RenderSettings.fogColor = new Color(0.5f, 0.55f, 0.6f);

            var sun = MakeLight("Sun", LightType.Directional, Vector3.zero, new Vector3(45f, 30f, 0f), new Color(1f, 0.95f, 0.9f), 1.5f, 10f);
            sun.useColorTemperature = true;
            sun.colorTemperature = 5000f;
            MakeLight("Fill", LightType.Directional, Vector3.zero, new Vector3(60f, 200f, 0f), Color.white, 0.5f, 10f);

            var player = new GameObject("Player") { tag = "Player" };
            player.transform.position = new Vector3(0f, 1.5f, -30f);
            player.AddComponent<GradeMover>();
            var cam = MakeCamera("Camera", new Vector3(0f, 1.5f, -30f), Vector3.zero, player.transform);
            cam.GetComponent<UniversalAdditionalCameraData>().antialiasing = AntialiasingMode.None;
            cam.GetComponent<UniversalAdditionalCameraData>().dithering = false;

            // a quad of linear 0.18 grey that fills the view, 2 m in front of the camera, unlit
            var mat = new Material(Shader.Find("Universal Render Pipeline/Unlit"));
            mat.SetColor("_BaseColor", new Color(0.18f, 0.18f, 0.18f).gamma);  // the linear value is 0.18
            AssetDatabase.DeleteAsset(Dir + "/Grey018.mat");
            AssetDatabase.CreateAsset(mat, Dir + "/Grey018.mat");
            var quad = GameObject.CreatePrimitive(PrimitiveType.Quad);
            quad.name = "GreyCard";
            UnityEngine.Object.DestroyImmediate(quad.GetComponent<Collider>());
            quad.transform.SetParent(cam.transform, false);
            quad.transform.localPosition = new Vector3(0f, 0f, 2f);
            quad.transform.localScale = new Vector3(8f, 8f, 1f);
            quad.GetComponent<MeshRenderer>().sharedMaterial = mat;

            // the global grade
            var global = Profile("GradeGlobal");
            var wb = Add<WhiteBalance>(global);
            wb.temperature.Override(30f);
            wb.tint.Override(-20f);
            var ca = Add<ColorAdjustments>(global);
            ca.contrast.Override(25f);
            ca.saturation.Override(-30f);
            ca.colorFilter.Override(new Color(1f, 0.9f, 0.8f));
            ca.postExposure.Override(0f);
            var lgg = Add<LiftGammaGain>(global);
            lgg.lift.Override(new Vector4(1f, 1f, 0.9f, 0.02f));
            lgg.gamma.Override(new Vector4(0.95f, 1f, 1.05f, 0f));
            lgg.gain.Override(new Vector4(1.05f, 1f, 0.95f, 0.1f));
            var tm = Add<Tonemapping>(global);
            tm.mode.Override(TonemappingMode.None);
            var bloomG = Add<Bloom>(global);
            bloomG.intensity.Override(0.5f);
            EditorUtility.SetDirty(global);
            var gv = new GameObject("GlobalVolume").AddComponent<Volume>();
            gv.isGlobal = true;
            gv.priority = 0f;
            gv.sharedProfile = global;

            // the local volume: a 10 m box around the origin, blend distance 10 m, post exposure +1 EV, bloom 2,
            // vignette 0.4 (only those parameters overridden)
            var local = Profile("GradeLocal");
            var ca2 = Add<ColorAdjustments>(local);
            ca2.postExposure.Override(1f);
            var bloomL = Add<Bloom>(local);
            bloomL.intensity.Override(2f);
            var vig = Add<Vignette>(local);
            vig.intensity.Override(0.4f);
            vig.color.Override(new Color(0.2f, 0f, 0f));
            EditorUtility.SetDirty(local);
            var lvGo = new GameObject("LocalVolume");
            lvGo.transform.position = new Vector3(0f, 1.5f, 0f);
            var box = lvGo.AddComponent<BoxCollider>();
            box.size = new Vector3(10f, 10f, 10f);
            box.isTrigger = true;
            var lv = lvGo.AddComponent<Volume>();
            lv.isGlobal = false;
            lv.blendDistance = 10f;
            lv.priority = 1f;
            lv.sharedProfile = local;
            return Save("GradeLab");
        }

        // ---------------------------------------------------------------- AudioLab

        static AudioSource Source(string name, Vector3 at, AudioClip clip, float volume, float blend, bool play, Transform parent = null)
        {
            var go = new GameObject(name);
            if (parent != null) go.transform.SetParent(parent, false);
            go.transform.position = at;
            var s = go.AddComponent<AudioSource>();
            s.clip = clip;
            s.volume = volume;
            s.spatialBlend = blend;
            s.loop = true;
            s.playOnAwake = play;
            s.dopplerLevel = 0f;
            s.rolloffMode = AudioRolloffMode.Logarithmic;
            s.minDistance = 1f;
            s.maxDistance = 50f;
            return s;
        }

        static AnimationCurve LinearCurve(params Keyframe[] keys)
        {
            var curve = new AnimationCurve(keys);
            for (var i = 0; i < curve.length; i++)
            {
                AnimationUtility.SetKeyLeftTangentMode(curve, i, AnimationUtility.TangentMode.Linear);
                AnimationUtility.SetKeyRightTangentMode(curve, i, AnimationUtility.TangentMode.Linear);
            }
            return curve;
        }

        static AudioListener Listener(string name, Vector3 at, bool main)
        {
            var root = new GameObject(name);
            if (main) root.tag = "Player";
            root.transform.position = at;
            var cam = MakeCamera(name + "Camera", at, Vector3.zero, root.transform, main);
            if (!main) cam.depth = -5f;
            var l = cam.gameObject.AddComponent<AudioListener>();
            l.enabled = main;
            return l;
        }

        static string AudioLab(Dictionary<string, AudioClip> clips, AudioMixerGroup sfx)
        {
            EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            MakeLight("Sun", LightType.Directional, Vector3.zero, new Vector3(50f, -30f, 0f), Color.white, 1f, 10f);
            var listener = Listener("Player", Vector3.zero, true);
            Source("Loop3D", new Vector3(0f, 0f, 5f), clips["Tone440"], 0.8f, 1f, true);
            Source("Music2D", new Vector3(30f, 0f, 30f), clips["Music220"], 0.5f, 0f, true);
            var late = Source("Late", new Vector3(10.5f, 0f, 0f), clips["Late660"], 1f, 0.5f, false);
            late.rolloffMode = AudioRolloffMode.Linear;
            late.maxDistance = 20f;
            var muted = Source("Muted", new Vector3(0f, 0f, 2f), clips["Muted330"], 1f, 1f, true);
            muted.mute = true;
            var mixed = Source("Mixed", new Vector3(0f, 0f, 0f), clips["Mixed550"], 1f, 0f, true);
            mixed.outputAudioMixerGroup = sfx;
            var custom = Source("Custom", new Vector3(0f, 0f, -8f), clips["Custom770"], 1f, 1f, true);
            custom.rolloffMode = AudioRolloffMode.Custom;
            custom.maxDistance = 20f;
            custom.SetCustomCurve(AudioSourceCurveType.CustomRolloff,
                LinearCurve(new Keyframe(0f, 1f), new Keyframe(0.5f, 0.25f), new Keyframe(1f, 0f)));
            var shooter = Source("Shooter", new Vector3(2f, 0f, 0f), null, 1f, 0f, false);
            shooter.loop = false;
            var second = Listener("Second", new Vector3(100f, 0f, 0f), false);
            var near = Source("Near2", new Vector3(100f, 0f, 2f), clips["Near2_605"], 0.5f, 1f, false, second.transform);
            near.transform.position = new Vector3(100f, 0f, 2f);
            var director = new GameObject("Director").AddComponent<AudioDirector>();
            director.late = late;
            director.shooter = shooter;
            director.loop3D = GameObject.Find("Loop3D").GetComponent<AudioSource>();
            director.shot = clips["Shot880"];
            director.point = clips["Point990"];
            director.mainListener = listener;
            director.secondListener = second;
            director.nextScene = SceneDir + "/AudioLab2.unity";
            return Save("AudioLab");
        }

        static string AudioLab2(Dictionary<string, AudioClip> clips)
        {
            EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            MakeLight("Sun", LightType.Directional, Vector3.zero, new Vector3(50f, -30f, 0f), Color.white, 1f, 10f);
            Listener("Player2", Vector3.zero, true);
            Source("Room2", new Vector3(0f, 0f, 2f), clips["Room2_495"], 0.6f, 1f, true);
            new GameObject("TapLog").AddComponent<TapLog>();
            return Save("AudioLab2");
        }

        static string AudioRolloff(Dictionary<string, AudioClip> clips, AudioMixerGroup sfx)
        {
            EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            MakeLight("Sun", LightType.Directional, Vector3.zero, new Vector3(50f, -30f, 0f), Color.white, 1f, 10f);
            Listener("Player", Vector3.zero, true);
            var s = Source("Mover", new Vector3(0f, 0f, 1f), clips["Tone440"], 1f, 1f, true);
            var director = new GameObject("Director").AddComponent<RolloffDirector>();
            director.source = s;
            director.quiet = sfx;
            director.custom = LinearCurve(new Keyframe(0f, 1f), new Keyframe(0.5f, 0.25f), new Keyframe(1f, 0f));
            return Save("AudioRolloff");
        }
    }
}
