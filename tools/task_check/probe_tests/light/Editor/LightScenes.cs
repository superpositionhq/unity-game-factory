// The light family's scenes (probe_tests/light): light, grading and audio, each set where the frame or the mix can
// tell what the engine did. Everything they use is made here under Made/: a white diffuse material and an unlit 0.18
// grey, volume profiles, sine-tone clips and a mixer with a -20 dB group, and one scene's lighting bake.
// The namespace is ProbeTests.Lighting: a namespace ProbeTests.Light would hide UnityEngine.Light from every other
// family's code in a ProbeTests namespace.
using System;
using System.Collections.Generic;
using System.IO;
using System.Reflection;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Audio;
using UnityEngine.Rendering;
using UnityEngine.Rendering.Universal;
using Object = UnityEngine.Object;

namespace ProbeTests.Lighting
{
    public static class LightScenes
    {
        const string Made = "Assets/ProbeTests/light/Made";
        static Material white, grey;
        static Dictionary<string, AudioClip> clips;
        static AudioMixerGroup sfx;

        public static void Build()
        {
            if (!AssetDatabase.IsValidFolder(Made)) AssetDatabase.CreateFolder("Assets/ProbeTests/light", "Made");
            white = Save(WhiteMaterial(), "White.mat");
            grey = Save(GreyMaterial(), "Grey018.mat");
            clips = MakeClips();
            sfx = MakeMixer();
            LightLab();
            BakeLab();
            SkyLab();
            GradeLab();
            AudioLab();
            AudioLab2();
            AudioRolloff();
            Stray();
            AssetDatabase.SaveAssets();
        }

        // ---------------------------------------------------------------- materials, objects

        /// <summary>Simple Lit, white, no specular: a surface lit only diffusely, its colour the light falling on it. Simple
        /// Lit's _SpecularHighlights is its specular source (SimpleLitGUI.SpecularSource: 0 specular colour, 1 none), from
        /// which URP's material import sets the keywords again; the specular colour black as well.</summary>
        static Material WhiteMaterial()
        {
            var m = new Material(Shader.Find("Universal Render Pipeline/Simple Lit"));
            m.SetColor("_BaseColor", Color.white);
            m.SetFloat("_SpecularHighlights", 1f);
            m.SetColor("_SpecColor", Color.black);
            m.DisableKeyword("_SPECULAR_COLOR");
            m.DisableKeyword("_SPECGLOSSMAP");
            return m;
        }

        /// <summary>Unlit, linear 0.18 grey.</summary>
        static Material GreyMaterial()
        {
            var m = new Material(Shader.Find("Universal Render Pipeline/Unlit"));
            m.SetColor("_BaseColor", new Color(0.18f, 0.18f, 0.18f).gamma);
            return m;
        }

        static T Save<T>(T asset, string name) where T : Object
        {
            AssetDatabase.CreateAsset(asset, Made + "/" + name);
            return asset;
        }

        static void NewScene() => EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);

        static void SaveScene(string name) => EditorSceneManager.SaveScene(EditorSceneManager.GetActiveScene(), Made + "/" + name + ".unity");

        static GameObject Box(string name, Vector3 centre, Vector3 size, Transform parent = null)
        {
            var go = GameObject.CreatePrimitive(PrimitiveType.Cube);
            go.name = name;
            go.transform.position = centre;
            go.transform.localScale = size;
            go.GetComponent<Renderer>().sharedMaterial = white;
            if (parent != null) go.transform.SetParent(parent, true);
            return go;
        }

        /// <summary>A closed room of 10 x 4 x 10 m around (x, 2, 0): floor (its top at y 0), roof (its underside at 4) and
        /// four walls, 0.2 m thick; with `split` a wall across it at z 0.</summary>
        static Transform Room(string name, float x, bool split = false)
        {
            var root = new GameObject(name).transform;
            Box("Floor", new Vector3(x, -0.1f, 0f), new Vector3(10.4f, 0.2f, 10.4f), root);
            Box("Roof", new Vector3(x, 4.1f, 0f), new Vector3(10.4f, 0.2f, 10.4f), root);
            Box("WallN", new Vector3(x, 2f, 5.1f), new Vector3(10.4f, 4.4f, 0.2f), root);
            Box("WallS", new Vector3(x, 2f, -5.1f), new Vector3(10.4f, 4.4f, 0.2f), root);
            Box("WallE", new Vector3(x + 5.1f, 2f, 0f), new Vector3(0.2f, 4.4f, 10.4f), root);
            Box("WallW", new Vector3(x - 5.1f, 2f, 0f), new Vector3(0.2f, 4.4f, 10.4f), root);
            if (split) Box("SplitWall", new Vector3(x, 2f, 0f), new Vector3(10f, 4f, 0.2f), root);
            return root;
        }

        /// <summary>A white quad seen by the camera: no collider, casts no shadow; facing up unless `facing` says.</summary>
        static GameObject Card(string name, Vector3 at, float size, Quaternion? facing = null)
        {
            var go = GameObject.CreatePrimitive(PrimitiveType.Quad);
            go.name = name;
            Object.DestroyImmediate(go.GetComponent<Collider>());
            go.transform.SetPositionAndRotation(at, facing ?? Quaternion.Euler(90f, 0f, 0f));
            go.transform.localScale = new Vector3(size, size, 1f);
            var r = go.GetComponent<MeshRenderer>();
            r.sharedMaterial = white;
            r.shadowCastingMode = ShadowCastingMode.Off;
            return go;
        }

        static Light Lamp(string name, LightType type, Vector3 at, Color colour, float intensity, float range,
            LightShadows shadows = LightShadows.None, Transform parent = null)
        {
            var go = new GameObject(name);
            go.transform.position = at;
            if (parent != null) go.transform.SetParent(parent, true);
            var l = go.AddComponent<Light>();
            l.type = type;
            l.color = colour;
            l.intensity = intensity;
            l.range = range;
            l.shadows = shadows;
            l.useColorTemperature = false;  // the colour as given (a lamp that wants its temperature sets it)
            l.lightmapBakeType = LightmapBakeType.Realtime;
            return l;
        }

        static Light Sun(string name, Vector3 euler, Color colour, float intensity, LightShadows shadows)
        {
            var l = Lamp(name, LightType.Directional, new Vector3(0f, 50f, 0f), colour, intensity, 10f, shadows);
            l.transform.rotation = Quaternion.Euler(euler);
            return l;
        }

        /// <summary>A camera that draws its frame plainly (no post-processing, anti-aliasing or dithering) unless `post`.</summary>
        static Camera MakeCamera(string name, Vector3 at, Vector3 euler, bool post = false, Transform parent = null, bool main = true)
        {
            var go = new GameObject(name);
            if (parent != null) go.transform.SetParent(parent, false);
            go.transform.SetPositionAndRotation(at, Quaternion.Euler(euler));
            var cam = go.AddComponent<Camera>();
            if (main) go.tag = "MainCamera";
            var data = go.AddComponent<UniversalAdditionalCameraData>();
            data.renderPostProcessing = post;
            data.antialiasing = AntialiasingMode.None;
            data.dithering = false;
            return cam;
        }

        static readonly Vector3 Down = new Vector3(90f, 0f, 0f);

        static void Tour(Camera cam, params (Vector3 at, Vector3 euler)[] stations)
        {
            var tour = cam.gameObject.AddComponent<LightTour>();
            tour.at = new Vector3[stations.Length];
            tour.euler = new Vector3[stations.Length];
            for (var i = 0; i < stations.Length; i++)
            {
                tour.at[i] = stations[i].at;
                tour.euler[i] = stations[i].euler;
            }
        }

        /// <summary>A station looking straight down at a card 1.5 m below.</summary>
        static (Vector3, Vector3) Above(float x, float y, float z) => (new Vector3(x, y + 1.5f, z), Down);

        // ---------------------------------------------------------------- LightLab

        // Closed rooms with lamps, an open field under a sun, and white cards where the light is measured; the camera
        // visits the cards one per second (LightTour), LightEvents changes the lighting between visits.
        static void LightLab()
        {
            NewScene();
            RenderSettings.ambientMode = AmbientMode.Flat;
            RenderSettings.ambientLight = new Color(0.2f, 0.3f, 0.4f);
            RenderSettings.ambientIntensity = 1f;
            RenderSettings.skybox = AssetDatabase.GetBuiltinExtraResource<Material>("Default-Skybox.mat");
            RenderSettings.fog = false;
            // intensity 0.8: no card is lit above 1 in a channel, where the frame clips (at 1.2 the card facing the sun read
            // red 1.23, and under gradient ambient 1.13)
            var sun = Sun("Sun", new Vector3(50f, -30f, 0f), Color.white, 0.8f, LightShadows.Soft);
            sun.useColorTemperature = true;
            sun.colorTemperature = 4000f;

            var a = Room("RoomA", 0f);
            Lamp("PointA", LightType.Point, new Vector3(0f, 3f, 0f), Color.white, 2f, 10f, parent: a);
            var switched = Lamp("SwitchedA", LightType.Point, new Vector3(3f, 3f, 3f), new Color(1f, 0.5f, 0.25f), 1.5f, 8f, parent: a);
            switched.useColorTemperature = true;
            switched.colorTemperature = 2700f;
            switched.enabled = false;
            Card("CardA", new Vector3(0f, 1f, 0f), 2f);

            var b = Room("RoomB", 20f);
            var spot = Lamp("SpotB", LightType.Spot, new Vector3(20f, 3f, 0f), Color.white, 3f, 10f, parent: b);
            spot.transform.rotation = Quaternion.Euler(90f, 0f, 0f);
            spot.spotAngle = 60f;
            spot.innerSpotAngle = 30f;
            Card("CardB", new Vector3(20f, 1f, 0f), 4f);

            // a lamp behind a wall: no shadows (URP lights through the wall), shadows on (the project's URP asset draws
            // none for point lights until LightEvents turns them on), shadows at half strength
            var c = Room("RoomC", 40f, true);
            Lamp("PointC", LightType.Point, new Vector3(40f, 3f, -3f), Color.white, 2f, 12f, parent: c);
            Card("CardC1", new Vector3(40f, 1f, 3f), 2f);
            Card("CardC2", new Vector3(40f, 1f, -1f), 1.6f);
            var d = Room("RoomD", 120f, true);
            Lamp("ShadowLamp", LightType.Point, new Vector3(120f, 3f, -3f), Color.white, 2f, 12f, LightShadows.Soft, d);
            Card("CardD", new Vector3(120f, 1f, 3f), 2f);
            var e = Room("RoomE", 140f, true);
            Lamp("HalfLamp", LightType.Point, new Vector3(140f, 3f, -3f), Color.white, 2f, 12f, LightShadows.Soft, e).shadowStrength = 0.5f;
            Card("CardE", new Vector3(140f, 1f, 3f), 2f);

            // the field: a roof on nothing, a card facing the sun and one facing up
            Box("Ground", new Vector3(75f, -0.1f, 0f), new Vector3(50f, 0.2f, 40f));
            Box("Shelter", new Vector3(73f, 3f, 0f), new Vector3(6f, 0.2f, 6f));
            var toward = Quaternion.Euler(50f, -30f, 0f) * Vector3.forward;
            Card("CardF1", new Vector3(60f, 1f, 0f), 2f, Quaternion.LookRotation(toward));
            Card("CardF2", new Vector3(73f, 1f, 0f), 2f);
            Card("CardF3", new Vector3(64f, 1f, 0f), 2f);

            // what stops a lamp's light, with its shadows on (they count once LightEvents turns them on): a lantern's
            // housing around its bulb, a crate the point is inside, a trigger, the Ignore Raycast layer, a 2D collider,
            // the player, and a plain slab
            var lantern = new GameObject("Lantern");
            lantern.transform.position = new Vector3(55f, 3f, 10f);
            lantern.AddComponent<SphereCollider>().radius = 0.3f;
            Lamp("LanternLight", LightType.Point, lantern.transform.position, Color.white, 1f, 3f, LightShadows.Soft, lantern.transform);
            Lamp("CrateLamp", LightType.Point, new Vector3(60f, 3f, 10f), Color.white, 1f, 3f, LightShadows.Soft);
            Box("Crate", new Vector3(60f, 0.5f, 10f), Vector3.one);
            Lamp("TriggerLamp", LightType.Point, new Vector3(65f, 3f, 10f), Color.white, 1f, 3f, LightShadows.Soft);
            Box("TriggerSlab", new Vector3(65f, 1.5f, 10f), new Vector3(2f, 0.2f, 2f)).GetComponent<Collider>().isTrigger = true;
            Lamp("IgnoreLamp", LightType.Point, new Vector3(70f, 3f, 10f), Color.white, 1f, 3f, LightShadows.Soft);
            Box("IgnoreSlab", new Vector3(70f, 1.5f, 10f), new Vector3(2f, 0.2f, 2f)).layer = 2;
            Lamp("FlatLamp", LightType.Point, new Vector3(75f, 3f, 10f), Color.white, 1f, 3f, LightShadows.Soft);
            var flat = Box("FlatSlab", new Vector3(75f, 1.5f, 10f), new Vector3(2f, 0.2f, 2f));
            Object.DestroyImmediate(flat.GetComponent<Collider>());
            flat.AddComponent<BoxCollider2D>();
            Lamp("HeroLamp", LightType.Point, new Vector3(80f, 3f, 10f), Color.white, 1f, 3f, LightShadows.Soft);
            var hero = new GameObject("Hero") { tag = "Player" };
            hero.transform.position = new Vector3(80f, 0f, 10f);
            var body = hero.AddComponent<CapsuleCollider>();
            body.center = new Vector3(0f, 1f, 0f);
            body.height = 2f;
            body.radius = 0.5f;
            Lamp("SlabLamp", LightType.Point, new Vector3(85f, 3f, 10f), Color.white, 1f, 3f, LightShadows.Soft);
            Box("Slab", new Vector3(85f, 1.5f, 10f), new Vector3(2f, 0.2f, 2f));

            var cam = MakeCamera("Camera", new Vector3(0f, 2.5f, 0f), Down);
            Tour(cam, Above(0f, 1f, 0f), Above(20f, 1f, 0f), Above(20.8f, 1f, 0f), Above(0f, 1f, 0f), Above(40f, 1f, 3f),
                Above(40f, 1f, -1f), Above(120f, 1f, 3f), Above(73f, 1f, 0f),
                (new Vector3(60f, 1f, 0f) - toward * 1.5f, Quaternion.LookRotation(toward).eulerAngles),
                Above(73f, 1f, 0f), Above(64f, 1f, 0f), Above(64f, 1f, 0f), Above(64f, 1f, 0f), Above(64f, 1f, 0f), Above(64f, 1f, 0f),
                Above(0f, 1f, 0f), Above(73f, 1f, 0f));
            var cull = MakeCamera("CullCheck", new Vector3(70f, 150f, 0f), Down, main: false);
            cull.orthographic = true;
            cull.orthographicSize = 50f;
            cull.farClipPlane = 400f;
            cull.enabled = false;
            var director = new GameObject("Director");
            var events = director.AddComponent<LightEvents>();
            events.switched = switched;
            events.sun = sun;
            var log = director.AddComponent<LightCull>();
            log.cull = cull;
            log.at = 120;
            // a play that doesn't measure sound is silenced too: a listener with an ear, and a quiet hum
            var ears = new GameObject("LabEars");
            ears.AddComponent<AudioListener>();
            ears.AddComponent<LightEar>();
            Source("Hum", Vector3.zero, "Quiet440", 1f, 0f, true);
            Keeper();
            SaveScene("LightLab");
        }

        // ---------------------------------------------------------------- BakeLab

        // Three lamps over static floors, baked with light probes around them, the ambient black: one Baked, one
        // Mixed (baked indirect), and one set to Baked after the bake (never baked). A moving white card under each
        // (lit by the light probes and real-time lights), the camera visiting the cards, then the floors.
        static void BakeLab()
        {
            NewScene();
            RenderSettings.ambientMode = AmbientMode.Flat;
            RenderSettings.ambientLight = Color.black;
            RenderSettings.skybox = null;
            RenderSettings.fog = false;
            var probes = new List<Vector3>();
            foreach (var x in new[] { 0f, 30f, 60f })
            {
                var floor = Box("Floor" + x, new Vector3(x, -0.1f, 0f), new Vector3(8f, 0.2f, 8f));
                GameObjectUtility.SetStaticEditorFlags(floor, StaticEditorFlags.ContributeGI);
                Card("Card" + x, new Vector3(x, 1f, 0f), 2f);
                for (var dx = -3; dx <= 3; dx += 3)
                    for (var dz = -3; dz <= 3; dz += 3)
                    {
                        probes.Add(new Vector3(x + dx, 0.5f, dz));
                        probes.Add(new Vector3(x + dx, 2f, dz));
                    }
            }
            new GameObject("Probes").AddComponent<LightProbeGroup>().probePositions = probes.ToArray();
            // intensity 1: its light in the probes stays below the frame's 1 (at 2 it read 1.28 and the frame clipped)
            Lamp("BakedLamp", LightType.Point, new Vector3(0f, 3f, 0f), Color.white, 1f, 6f).lightmapBakeType = LightmapBakeType.Baked;
            Lamp("MixedLamp", LightType.Point, new Vector3(30f, 3f, 0f), Color.white, 2f, 6f).lightmapBakeType = LightmapBakeType.Mixed;
            var cam = MakeCamera("Camera", new Vector3(0f, 2.5f, 0f), Down);
            Tour(cam, Above(0f, 1f, 0f), Above(30f, 1f, 0f), Above(60f, 1f, 0f), Above(0f, 0f, 2.5f), Above(30f, 0f, 2.5f), Above(60f, 0f, 2.5f));
            var cull = MakeCamera("CullCheck", new Vector3(30f, 100f, 0f), Down, main: false);
            cull.orthographic = true;
            cull.orthographicSize = 40f;
            cull.enabled = false;
            var log = new GameObject("Director").AddComponent<LightCull>();
            log.cull = cull;
            log.at = 30;
            var settings = new LightingSettings
            {
                name = "BakeLabLighting", bakedGI = true, realtimeGI = false, lightmapper = LightingSettings.Lightmapper.ProgressiveCPU,
                lightmapResolution = 4, lightmapPadding = 2, directSampleCount = 32, indirectSampleCount = 64,
                environmentSampleCount = 16, maxBounces = 2, mixedBakeMode = MixedLightingMode.IndirectOnly,
            };
            Save(settings, "BakeLabLighting.lighting");
            Lightmapping.lightingSettings = settings;
            SaveScene("BakeLab");
            var baked = Lightmapping.Bake();
            Debug.Log("ProbeTests: BakeLab bake " + (baked ? "done" : "failed") + ", " + LightmapSettings.lightmaps.Length + " lightmap(s), "
                      + (LightmapSettings.lightProbes != null ? LightmapSettings.lightProbes.count : 0) + " light probe(s)");
            Lamp("LateLamp", LightType.Point, new Vector3(60f, 3f, 0f), Color.white, 2f, 6f).lightmapBakeType = LightmapBakeType.Baked;
            SaveScene("BakeLab");
        }

        // ---------------------------------------------------------------- SkyLab

        // A scene saved with skybox ambient and never baked, a white sun, a card; the camera renders post-processing
        // with no volume in the scene (an untouched stack: the project's default profile). LightSkyRefresh makes the
        // environment lighting from the skybox at 2 s.
        static void SkyLab()
        {
            NewScene();
            RenderSettings.ambientMode = AmbientMode.Skybox;
            RenderSettings.ambientIntensity = 1f;
            RenderSettings.skybox = AssetDatabase.GetBuiltinExtraResource<Material>("Default-Skybox.mat");
            RenderSettings.fog = false;
            // intensity 0.6: the card stays below 1 in every channel (at 1 the sky's blue took it to 1.14, clipped)
            Sun("Sun", new Vector3(50f, -30f, 0f), Color.white, 0.6f, LightShadows.Soft);
            Card("Card", new Vector3(0f, 1f, 0f), 2f);
            MakeCamera("Camera", new Vector3(0f, 2.5f, 0f), Down, post: true);
            new GameObject("Director").AddComponent<LightSkyRefresh>().at = 60;
            // the scene's listener on an object of its own with no script: the probe puts its tap on it
            new GameObject("Ears").AddComponent<AudioListener>();
            SaveScene("SkyLab");
        }

        // ---------------------------------------------------------------- GradeLab

        static T Add<T>(VolumeProfile profile) where T : VolumeComponent
        {
            var c = profile.Add<T>(false);
            c.name = typeof(T).Name;
            AssetDatabase.AddObjectToAsset(c, profile);
            return c;
        }

        static Volume MakeVolume(string name, VolumeProfile profile, float priority, bool global = true)
        {
            EditorUtility.SetDirty(profile);
            var v = new GameObject(name).AddComponent<Volume>();
            v.isGlobal = global;
            v.priority = priority;
            v.sharedProfile = profile;
            return v;
        }

        // A camera carrying an unlit card of linear 0.18 grey that fills its view, through a global grade; the player
        // stands until 6 s, then walks into a local volume (a 10 m box, blend distance 10 m). A volume of weight 0.5, a
        // disabled one and one on a layer the camera's volume mask leaves out. Two directional lights of one intensity.
        static void GradeLab()
        {
            NewScene();
            RenderSettings.ambientMode = AmbientMode.Flat;
            RenderSettings.ambientLight = new Color(0.1f, 0.1f, 0.1f);
            RenderSettings.fog = true;
            RenderSettings.fogMode = FogMode.ExponentialSquared;
            RenderSettings.fogDensity = 0.001f;
            RenderSettings.fogColor = new Color(0.5f, 0.55f, 0.6f);
            // two suns of one intensity under one root: SunTwin, made after Sun, first among its siblings is the grading's
            // sun (a player keeps the order below a root, not the order of a scene's roots: Find's hierarchy order)
            var suns = new GameObject("Suns").transform;
            var sun = Sun("Sun", new Vector3(45f, 30f, 0f), new Color(1f, 0.95f, 0.9f), 1.5f, LightShadows.None);
            sun.useColorTemperature = true;
            sun.colorTemperature = 5000f;
            sun.transform.SetParent(suns, true);
            var twin = Sun("SunTwin", new Vector3(30f, 0f, 0f), Color.white, 1.5f, LightShadows.None).transform;
            twin.SetParent(suns, true);
            twin.SetSiblingIndex(0);
            Sun("Fill", new Vector3(60f, 200f, 0f), Color.white, 0.5f, LightShadows.None);

            var player = new GameObject("Player") { tag = "Player" };
            player.transform.position = new Vector3(0f, 1.5f, -30f);
            var cam = MakeCamera("Camera", new Vector3(0f, 1.5f, -30f), Vector3.zero, post: true, parent: player.transform);
            var walker = player.AddComponent<LightGradeWalker>();
            walker.view = cam;
            var card = GameObject.CreatePrimitive(PrimitiveType.Quad);
            card.name = "GreyCard";
            Object.DestroyImmediate(card.GetComponent<Collider>());
            card.transform.SetParent(cam.transform, false);
            card.transform.localPosition = new Vector3(0f, 0f, 2f);
            card.transform.localScale = new Vector3(8f, 8f, 1f);
            card.GetComponent<MeshRenderer>().sharedMaterial = grey;

            var global = Save(ScriptableObject.CreateInstance<VolumeProfile>(), "GradeGlobal.asset");
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
            Add<Tonemapping>(global).mode.Override(TonemappingMode.None);
            Add<Bloom>(global).intensity.Override(0.5f);
            MakeVolume("GlobalVolume", global, 0f);
            walker.global = global;

            var local = Save(ScriptableObject.CreateInstance<VolumeProfile>(), "GradeLocal.asset");
            Add<ColorAdjustments>(local).postExposure.Override(1f);
            Add<Bloom>(local).intensity.Override(2f);
            var vignette = Add<Vignette>(local);
            vignette.intensity.Override(0.4f);
            vignette.color.Override(new Color(0.2f, 0f, 0f));
            var box = MakeVolume("LocalVolume", local, 1f, false);
            box.transform.position = new Vector3(0f, 1.5f, 0f);
            box.blendDistance = 10f;
            var trigger = box.gameObject.AddComponent<BoxCollider>();
            trigger.size = new Vector3(10f, 10f, 10f);
            trigger.isTrigger = true;

            var weighted = Save(ScriptableObject.CreateInstance<VolumeProfile>(), "GradeWeighted.asset");
            Add<PaniniProjection>(weighted).distance.Override(0.6f);
            MakeVolume("WeightedVolume", weighted, 2f).weight = 0.5f;
            var off = Save(ScriptableObject.CreateInstance<VolumeProfile>(), "GradeOff.asset");
            Add<ChromaticAberration>(off).intensity.Override(0.9f);
            MakeVolume("DisabledVolume", off, 5f).enabled = false;
            var masked = Save(ScriptableObject.CreateInstance<VolumeProfile>(), "GradeMasked.asset");
            Add<ChromaticAberration>(masked).intensity.Override(0.7f);
            MakeVolume("MaskedVolume", masked, 6f).gameObject.layer = 4;  // Water: not in the camera's volume mask
            SaveScene("GradeLab");
        }

        // ---------------------------------------------------------------- audio

        static readonly (string name, float hz, float seconds, float amplitude, bool stream)[] Tones =
        {
            ("Tone440", 440f, 2f, 0.5f, false), ("Music220", 220f, 2f, 0.5f, false), ("Muted330", 330f, 2f, 0.5f, false),
            ("Mixed550", 550f, 2f, 0.5f, false), ("Custom770", 770f, 2f, 0.5f, false), ("Stream385", 385f, 2f, 0.5f, true),
            ("Menu495", 495f, 2f, 0.5f, false), ("Pause275", 275f, 2f, 0.5f, false), ("Late660", 660f, 2f, 0.5f, false),
            ("End1000", 1000f, 0.3f, 0.5f, false), ("Shot880", 880f, 0.3f, 0.5f, false), ("Main605", 605f, 2f, 0.5f, false),
            ("Point990", 990f, 0.3f, 0.5f, false), ("Near715", 715f, 2f, 0.5f, false), ("Room523", 523f, 2f, 0.5f, false),
            ("Quiet440", 440f, 2f, 0.05f, false), ("Faint1100", 1100f, 2f, 0.5f, false),
        };

        static Dictionary<string, AudioClip> MakeClips()
        {
            var found = new Dictionary<string, AudioClip>();
            foreach (var (name, hz, seconds, amplitude, stream) in Tones)
            {
                var path = $"{Made}/{name}.wav";
                WriteWav(path, hz, seconds, amplitude);
                AssetDatabase.ImportAsset(path, ImportAssetOptions.ForceUpdate);
                var importer = (AudioImporter)AssetImporter.GetAtPath(path);
                var s = importer.defaultSampleSettings;
                s.compressionFormat = AudioCompressionFormat.PCM;  // the samples as written: the level is exact
                s.loadType = stream ? AudioClipLoadType.Streaming : AudioClipLoadType.DecompressOnLoad;
                importer.defaultSampleSettings = s;
                importer.SaveAndReimport();
                found[name] = AssetDatabase.LoadAssetAtPath<AudioClip>(path);
                if (found[name] == null) throw new InvalidOperationException("no clip at " + path);
            }
            return found;
        }

        /// <summary>A mono 16-bit 44.1 kHz sine of `amplitude` (whole cycles for a whole second's length: it loops cleanly).</summary>
        static void WriteWav(string path, float hz, float seconds, float amplitude)
        {
            const int rate = 44100;
            var n = (int)Math.Round(rate * seconds);
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
                w.Write((short)Math.Round(Math.Sin(2.0 * Math.PI * hz * i / rate) * amplitude * 32767.0));
        }

        /// <summary>TestMix.mixer with a child group "SFX" at -20 dB, made through the editor's AudioMixerController (Unity
        /// has no public API that makes a mixer).</summary>
        static AudioMixerGroup MakeMixer()
        {
            const string path = Made + "/TestMix.mixer";
            const BindingFlags all = BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Static | BindingFlags.Instance;
            var controller = typeof(Editor).Assembly.GetType("UnityEditor.Audio.AudioMixerController");
            var mixer = controller.GetMethod("CreateMixerControllerAtPath", all).Invoke(null, new object[] { path });
            var master = controller.GetProperty("masterGroup", all).GetValue(mixer);
            var group = controller.GetMethod("CreateNewGroup", all).Invoke(mixer, new object[] { "SFX", false });
            controller.GetMethod("AddChildToParent", all).Invoke(mixer, new[] { group, master });
            var snapshot = controller.GetProperty("TargetSnapshot", all).GetValue(mixer);
            group.GetType().GetMethod("SetValueForVolume", all).Invoke(group, new[] { mixer, snapshot, (object)(-20f) });
            EditorUtility.SetDirty((Object)mixer);
            AssetDatabase.SaveAssets();
            var groups = AssetDatabase.LoadAssetAtPath<AudioMixer>(path).FindMatchingGroups("SFX");
            if (groups.Length == 0) throw new InvalidOperationException("the mixer has no SFX group");
            return groups[0];
        }

        static AudioSource Source(string name, Vector3 at, string clip, float volume, float blend, bool play, Transform parent = null)
        {
            var go = new GameObject(name);
            if (parent != null) go.transform.SetParent(parent, false);
            go.transform.position = at;
            var s = go.AddComponent<AudioSource>();
            s.clip = clip != null ? clips[clip] : null;
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

        static AnimationCurve Linear(params Keyframe[] keys)
        {
            var curve = new AnimationCurve(keys);
            for (var i = 0; i < curve.length; i++)
            {
                AnimationUtility.SetKeyLeftTangentMode(curve, i, AnimationUtility.TangentMode.Linear);
                AnimationUtility.SetKeyRightTangentMode(curve, i, AnimationUtility.TangentMode.Linear);
            }
            return curve;
        }

        /// <summary>A player root at `at` with a camera child that carries an AudioListener and a LightEar.</summary>
        static AudioListener Listener(string name, Vector3 at, bool main, bool on = true)
        {
            var root = new GameObject(name);
            if (main) root.tag = "Player";
            root.transform.position = at;
            var cam = MakeCamera(name + "Camera", at, Vector3.zero, parent: root.transform, main: main);
            cam.enabled = main;
            var l = cam.gameObject.AddComponent<AudioListener>();
            l.enabled = on;
            cam.gameObject.AddComponent<LightEar>();
            return l;
        }

        static void Keeper(float seconds = 2f) => new GameObject("EarKeeper").AddComponent<LightEarKeeper>().seconds = seconds;

        // Sources of every kind around the listener, and LightAudioDirector's events (see it for the times).
        static void AudioLab()
        {
            NewScene();
            Sun("Sun", new Vector3(50f, -30f, 0f), Color.white, 1f, LightShadows.None);
            var first = Listener("Player", Vector3.zero, true);
            var second = Listener("Second", new Vector3(100f, 0f, 0f), false, false);
            // both under one root, Player first: a player keeps the order below a root, not the order of a scene's
            // roots, and the measure takes the first enabled listener in hierarchy order
            var rig = new GameObject("Listeners").transform;
            first.transform.parent.SetParent(rig, true);
            second.transform.parent.SetParent(rig, true);
            Source("Loop3D", new Vector3(0f, 0f, 5f), "Tone440", 0.8f, 1f, true);
            Source("Music2D", new Vector3(30f, 0f, 30f), "Music220", 0.5f, 0f, true);
            Source("Muted", new Vector3(0f, 0f, 2f), "Muted330", 1f, 1f, true).mute = true;
            Source("Mixed", Vector3.zero, "Mixed550", 1f, 0f, true).outputAudioMixerGroup = sfx;
            var custom = Source("Custom", new Vector3(0f, 0f, -8f), "Custom770", 1f, 1f, true);
            custom.rolloffMode = AudioRolloffMode.Custom;
            custom.maxDistance = 20f;
            custom.SetCustomCurve(AudioSourceCurveType.CustomRolloff, Linear(new Keyframe(0f, 1f), new Keyframe(0.5f, 0.25f), new Keyframe(1f, 0f)));
            Source("Stream", Vector3.zero, "Stream385", 0.3f, 0f, true);
            var menu = Source("Menu", Vector3.zero, "Menu495", 0.2f, 0f, true);  // ignores AudioListener.pause (LightAudioDirector)
            var pausable = Source("Pausable", Vector3.zero, "Pause275", 0.1f, 0f, true);
            Source("Faint", Vector3.zero, "Faint1100", 0.0009f, 0f, true);  // just under the audible floor (0.001)
            var late = Source("Late", new Vector3(10.5f, 0f, 0f), "Late660", 1f, 0.5f, false);
            late.rolloffMode = AudioRolloffMode.Linear;
            late.maxDistance = 20f;
            var ender = Source("Ender", Vector3.zero, "End1000", 0.05f, 0f, false);
            ender.loop = false;
            var shooter = Source("Shooter", new Vector3(2f, 0f, 0f), null, 0.9f, 0f, false);
            shooter.loop = false;
            var shooterClip = Source("ShooterClip", new Vector3(3f, 0f, 0f), "Main605", 0.9f, 0f, false);
            shooterClip.loop = false;
            var near = Source("Near", new Vector3(100f, 0f, 2f), "Near715", 0.5f, 1f, false, second.transform.parent);
            near.transform.position = new Vector3(100f, 0f, 2f);
            Keeper();
            var director = new GameObject("Director").AddComponent<LightAudioDirector>();
            director.late = late;
            director.menu = menu;
            director.pausable = pausable;
            director.ender = ender;
            director.shooter = shooter;
            director.shooterClip = shooterClip;
            director.near = near;
            director.shot = clips["Shot880"];
            director.point = clips["Point990"];
            director.first = first;
            director.second = second;
            director.next = Made + "/AudioLab2.unity";
            SaveScene("AudioLab");
        }

        // Where AudioLab's scene load arrives: a new listener and one source.
        static void AudioLab2()
        {
            NewScene();
            Sun("Sun", new Vector3(50f, -30f, 0f), Color.white, 1f, LightShadows.None);
            Listener("Player2", Vector3.zero, true);
            Source("Room", new Vector3(0f, 0f, 2f), "Room523", 0.6f, 1f, true);
            Keeper();
            SaveScene("AudioLab2");
        }

        // One tone moved through the rolloff steps of LightRolloff.
        static void AudioRolloff()
        {
            NewScene();
            Sun("Sun", new Vector3(50f, -30f, 0f), Color.white, 1f, LightShadows.None);
            Listener("Player", Vector3.zero, true);
            var s = Source("Mover", new Vector3(0f, 0f, 1f), "Tone440", 1f, 1f, true);
            Keeper();
            var director = new GameObject("Director").AddComponent<LightRolloff>();
            director.source = s;
            director.quiet = sfx;
            director.custom = Linear(new Keyframe(0f, 1f), new Keyframe(0.5f, 0.25f), new Keyframe(1f, 0f));
            SaveScene("AudioRolloff");
        }

        // A listener with a quiet tone: played by the probe (the tap silences it) and started without a probe play
        // (LightStrayBoot, -lightstray: a tap added by the game must let it through).
        static void Stray()
        {
            NewScene();
            Listener("Stray", Vector3.zero, true);
            Source("StrayTone", Vector3.zero, "Quiet440", 1f, 0f, true);
            Keeper(2f);
            SaveScene("Stray");
        }
    }
}
