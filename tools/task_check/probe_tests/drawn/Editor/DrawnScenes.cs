// The drawn family's scenes (probe_tests/drawn), everything made under Assets/ProbeTests/drawn/Made:
//   DrawnLab    a row of things a `drawn` query reads (z 0), a row of light sources a glow render reads (z 20), 70
//               cubes for the glow budget (z 60), watchers behind the player's camera (z -45, -60), under a coloured
//               sun with shadows, a blue point light, fog, a realtime reflection probe and post-processing, none of
//               which a probe render may show; and the scripts that check what the renders leave behind.
//   DrawnBaked  a lightmapped cube and a light-probe-lit sphere under a red baked light.
//   DrawnCoin   coins as the sample game makes them (a gold disc on its edge that spins and bobs), children of a spawner.
// And the family's own URP asset (Forward, Forward+, Deferred and 2D renderers; one more with HDR off and render scale
// 0.75) that the pipeline plays switch to.
using System.Collections.Generic;
using System.Linq;
using UnityEditor;
using UnityEditor.Animations;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Rendering.Universal;
using UnityEngine.UI;

namespace ProbeTests.Drawn
{
    public static class DrawnScenes
    {
        const string Made = "Assets/ProbeTests/drawn/Made";
        const string Source = "Assets/ProbeTests/drawn/Assets";
        const string OnlyLayer = "DrawnOnly";  // drawn by the family's Forward renderer only through its RenderObjects feature
        const string NeverLayer = "DrawnNever";  // filtered out by the family's Forward renderer, and nothing draws it there
        const int UiLayer = 5;
        const string Label = "ProbeTestsDrawn";  // the family's URP assets, kept whole by the build

        public static void Build()
        {
            if (!AssetDatabase.IsValidFolder(Made)) AssetDatabase.CreateFolder("Assets/ProbeTests/drawn", "Made");
            var only = Layer(OnlyLayer);
            var never = Layer(NeverLayer);
            var checker = Checker();
            Pipelines(only, never, out var urp, out var plain);
            // a build keeps a URP asset's shader variants (Forward+, Deferred, 2D) only for the assets of its quality
            // levels, or for those with this label (the referenced-in-scenes rule reads the editor's list of build
            // scenes, which the checker's build doesn't use)
            var include = GraphicsSettings.GetRenderPipelineSettings<IncludeAdditionalRPAssets>();
            if (include == null) throw new System.InvalidOperationException("the URP global settings have no IncludeAdditionalRPAssets");
            include.includeAssetsByLabel = true;
            include.labelToInclude = Label;
            AssetDatabase.SetLabels(urp, new[] { Label });
            AssetDatabase.SetLabels(plain, new[] { Label });
            var global = GraphicsSettings.GetSettingsForRenderPipeline<UniversalRenderPipeline>();
            if (global != null) EditorUtility.SetDirty(global);
            Lab(checker, only, never, urp, plain);
            Baked();
            Coin();
            AssetDatabase.SaveAssets();
        }

        // ---------------------------------------------------------------- assets

        static int Layer(string name)
        {
            var manager = new SerializedObject(AssetDatabase.LoadAllAssetsAtPath("ProjectSettings/TagManager.asset")[0]);
            var layers = manager.FindProperty("layers");
            for (var i = 8; i < 32; i++)
                if (layers.GetArrayElementAtIndex(i).stringValue == name) return i;
            for (var i = 8; i < 32; i++)
                if (string.IsNullOrEmpty(layers.GetArrayElementAtIndex(i).stringValue))
                {
                    layers.GetArrayElementAtIndex(i).stringValue = name;
                    manager.ApplyModifiedPropertiesWithoutUndo();
                    return i;
                }
            throw new System.InvalidOperationException("no free layer for " + name);
        }

        static T Save<T>(T asset, string name) where T : Object
        {
            AssetDatabase.CreateAsset(asset, Made + "/" + name);
            return asset;
        }

        static Material Mat(string name, string shader, System.Action<Material> setup)
        {
            var m = new Material(Shader.Find(shader)) { name = name };
            setup(m);
            if (m.HasProperty("_Surface")) BaseShaderGUI.SetMaterialKeywords(m);
            return Save(m, name + ".mat");
        }

        static Material Lit(string name, Color baseColour, Texture tex = null, Color? emission = null) =>
            Mat(name, "Universal Render Pipeline/Lit", m =>
            {
                m.SetColor("_BaseColor", baseColour);
                m.SetFloat("_Smoothness", 0.5f);
                if (tex != null) m.SetTexture("_BaseMap", tex);
                if (emission.HasValue)
                {
                    m.SetColor("_EmissionColor", emission.Value);
                    m.EnableKeyword("_EMISSION");
                    m.globalIlluminationFlags = MaterialGlobalIlluminationFlags.RealtimeEmissive;
                }
            });

        static Material Own(string name, string shader, System.Action<Material> setup)
        {
            var m = new Material(AssetDatabase.LoadAssetAtPath<Shader>(Source + "/" + shader + ".shader")) { name = name };
            setup?.Invoke(m);
            return Save(m, name + ".mat");
        }

        static Texture2D Checker()
        {
            var tex = new Texture2D(64, 64, TextureFormat.RGBA32, true, false) { name = "Checker", wrapMode = TextureWrapMode.Repeat };
            for (var y = 0; y < 64; y++)
                for (var x = 0; x < 64; x++)
                    tex.SetPixel(x, y, ((x / 8 + y / 8) & 1) == 0 ? new Color(1, 0, 0, 1) : new Color(0, 0, 1, 1));
            tex.Apply(true);
            return Save(tex, "Checker.asset");
        }

        static GameObject Prim(string name, Vector3 at, Material m, float size = 1f, PrimitiveType type = PrimitiveType.Cube, Transform parent = null)
        {
            var go = GameObject.CreatePrimitive(type);
            go.name = name;
            if (parent != null) go.transform.SetParent(parent, false);
            go.transform.position = at;
            go.transform.localScale = Vector3.one * size;
            go.GetComponent<Renderer>().sharedMaterial = m;
            Object.DestroyImmediate(go.GetComponent<Collider>());
            return go;
        }

        static UniversalRendererData RendererData(string name, RenderingMode mode, PostProcessData post)
        {
            var data = ScriptableObject.CreateInstance<UniversalRendererData>();
            data.renderingMode = mode;
            data.postProcessData = post;
            return Save(data, name + ".asset");
        }

        static void AddFeature(ScriptableRendererData data, ScriptableRendererFeature feature)
        {
            AssetDatabase.AddObjectToAsset(feature, data);
            AssetDatabase.TryGetGUIDAndLocalFileIdentifier(feature, out _, out long id);
            var so = new SerializedObject(data);
            var features = so.FindProperty("m_RendererFeatures");
            var map = so.FindProperty("m_RendererFeatureMap");
            features.arraySize++;
            features.GetArrayElementAtIndex(features.arraySize - 1).objectReferenceValue = feature;
            map.arraySize++;
            map.GetArrayElementAtIndex(map.arraySize - 1).longValue = id;
            so.ApplyModifiedPropertiesWithoutUndo();
            EditorUtility.SetDirty(data);
        }

        static UniversalRenderPipelineAsset PipelineAsset(string name, params ScriptableRendererData[] renderers)
        {
            var asset = UniversalRenderPipelineAsset.Create(renderers[0]);
            var so = new SerializedObject(asset);
            var list = so.FindProperty("m_RendererDataList");
            list.arraySize = renderers.Length;
            for (var i = 0; i < renderers.Length; i++) list.GetArrayElementAtIndex(i).objectReferenceValue = renderers[i];
            so.FindProperty("m_DefaultRendererIndex").intValue = 0;
            so.ApplyModifiedPropertiesWithoutUndo();
            return Save(asset, name + ".asset");
        }

        // The family's own URP asset: renderer 0 is Forward with two features, a full-screen tint (which the probe must
        // leave out) and a RenderObjects pass that alone draws OnlyLayer (which it must keep), NeverLayer filtered out and
        // drawn by nothing (as in the game, the probe draws nothing there); 1 Forward+, 2 Deferred,
        // 3 the 2D renderer. And a second asset with HDR off and render scale 0.75 (which the probe must not feel).
        static void Pipelines(int only, int never, out UniversalRenderPipelineAsset urp, out UniversalRenderPipelineAsset plain)
        {
            var post = AssetDatabase.LoadAssetAtPath<PostProcessData>("Packages/com.unity.render-pipelines.universal/Runtime/Data/PostProcessData.asset");
            var forward = RendererData("DrawnForward", RenderingMode.Forward, post);
            forward.opaqueLayerMask = ~((1 << only) | (1 << never));
            forward.transparentLayerMask = ~((1 << only) | (1 << never));
            var tint = ScriptableObject.CreateInstance<FullScreenPassRendererFeature>();
            tint.name = "DrawnTint";
            tint.injectionPoint = FullScreenPassRendererFeature.InjectionPoint.BeforeRenderingTransparents;
            tint.fetchColorBuffer = true;
            tint.requirements = ScriptableRenderPassInput.Color;
            tint.passMaterial = Own("Tint", "DrawnTint", null);
            AddFeature(forward, tint);
            var layer = ScriptableObject.CreateInstance<RenderObjects>();
            layer.name = "DrawnLayer";
            layer.settings.Event = RenderPassEvent.AfterRenderingOpaques;
            layer.settings.filterSettings.RenderQueueType = RenderQueueType.Opaque;
            layer.settings.filterSettings.LayerMask = 1 << only;
            AddFeature(forward, layer);
            var plus = RendererData("DrawnForwardPlus", RenderingMode.ForwardPlus, post);
            var deferred = RendererData("DrawnDeferred", RenderingMode.Deferred, post);
            var flat = Save(ScriptableObject.CreateInstance<Renderer2DData>(), "Drawn2D.asset");
            urp = PipelineAsset("DrawnUrp", forward, plus, deferred, flat);
            urp.supportsHDR = true;
            plain = PipelineAsset("DrawnUrpPlain", RendererData("DrawnPlainForward", RenderingMode.Forward, post));
            plain.supportsHDR = false;
            plain.renderScale = 0.75f;
            EditorUtility.SetDirty(urp);
            EditorUtility.SetDirty(plain);
        }

        // ---------------------------------------------------------------- DrawnLab

        static void Lab(Texture2D checker, int only, int never, UniversalRenderPipelineAsset urp, UniversalRenderPipelineAsset plain)
        {
            var scene = EditorSceneManager.NewScene(NewSceneSetup.DefaultGameObjects, NewSceneMode.Single);
            var cam = Camera.main;
            cam.transform.position = new Vector3(40, 9, -32);
            cam.transform.LookAt(new Vector3(40, 1, 5));
            cam.farClipPlane = 300;
            cam.GetUniversalAdditionalCameraData().renderPostProcessing = true;
            var sun = Object.FindFirstObjectByType<Light>();
            sun.name = "Sun";
            sun.color = new Color(1f, 0.85f, 0.6f);
            sun.intensity = 2.5f;
            sun.shadows = LightShadows.Soft;
            var point = new GameObject("BluePoint").AddComponent<Light>();
            point.type = LightType.Point;
            point.color = new Color(0.2f, 0.3f, 1f);
            point.intensity = 20f;
            point.range = 8f;
            point.transform.position = new Vector3(1.5f, 2.5f, -1.5f);
            RenderSettings.fog = true;
            RenderSettings.fogMode = FogMode.ExponentialSquared;
            RenderSettings.fogDensity = 0.02f;
            RenderSettings.fogColor = new Color(0.6f, 0.6f, 0.65f);
            // realtime, but rendered once: a probe that renders every frame differs between two plays by itself
            var probe = new GameObject("RealtimeProbe").AddComponent<ReflectionProbe>();
            probe.mode = ReflectionProbeMode.Realtime;
            probe.refreshMode = ReflectionProbeRefreshMode.OnAwake;
            probe.size = new Vector3(120, 20, 60);
            probe.transform.position = new Vector3(40, 2, 10);
            var profile = ScriptableObject.CreateInstance<VolumeProfile>();
            var bloom = profile.Add<Bloom>(true);
            bloom.intensity.Override(3f);
            bloom.threshold.Override(0.5f);
            var adjust = profile.Add<ColorAdjustments>(true);
            adjust.postExposure.Override(0.7f);
            adjust.saturation.Override(-60f);
            adjust.colorFilter.Override(new Color(1f, 0.7f, 0.7f));
            Save(profile, "Post.asset");
            var volume = new GameObject("PostVolume").AddComponent<Volume>();
            volume.isGlobal = true;
            volume.sharedProfile = profile;

            // the drawn row (z = 0)
            Prim("RedCube", new Vector3(0, 1, 0), Lit("Red", new Color(0.8f, 0.2f, 0.1f)));
            Prim("CheckerCube", new Vector3(10, 1, 0), Lit("CheckerLit", Color.white, checker));
            var white = Lit("WhiteShared", Color.white);
            Prim("TintCube", new Vector3(20, 1, 0), white).AddComponent<DrawnBlockTint>();
            var top = Prim("TwoToneTop", new Vector3(25, 1.25f, 0), Lit("TopRed", new Color(1f, 0f, 0f)));
            top.transform.localScale = new Vector3(1f, 0.5f, 1f);
            var bottom = Prim("TwoToneBottom", new Vector3(25, 0.75f, 0), Lit("BottomBlue", new Color(0f, 0f, 1f)));
            bottom.transform.localScale = new Vector3(1f, 0.5f, 1f);
            Prim("SpinCube", new Vector3(30, 1, 0), Lit("Grey", new Color(0.5f, 0.5f, 0.5f), checker)).AddComponent<DrawnSpinner>();
            var mirror = Prim("Mirror", new Vector3(33, 1, -2), Mat("Mirror", "Universal Render Pipeline/Lit", m =>
            {
                m.SetFloat("_Metallic", 1f);
                m.SetFloat("_Smoothness", 1f);
            }), 1.5f, PrimitiveType.Sphere);
            mirror.GetComponent<Renderer>().reflectionProbeUsage = ReflectionProbeUsage.BlendProbes;
            var pan = Prim("PanQuad", new Vector3(40, 1, 0), Lit("PanLit", Color.white, checker), 2f, PrimitiveType.Quad);
            pan.transform.rotation = Quaternion.Euler(0, 180, 0);
            pan.AddComponent<DrawnTexturePan>();
            var particles = Mat("Particles", "Universal Render Pipeline/Particles/Unlit", m =>
            {
                m.SetFloat("_Surface", 1f);
                m.SetFloat("_Blend", 0f);
                m.SetColor("_BaseColor", new Color(1f, 0.5f, 0.1f, 0.6f));
            });
            Sparks("Sparks", new Vector3(50, 1, 0), particles);
            var late = new GameObject("LateHolder");
            var lateCube = Prim("LateCube", new Vector3(60, 1, 0), Lit("Yellow", new Color(0.9f, 0.8f, 0.1f)));
            lateCube.SetActive(false);
            var activator = late.AddComponent<DrawnActivateAt>();
            activator.Target = lateCube;
            activator.Seconds = 5f;
            var beamRoot = new GameObject("BeamRoot");
            beamRoot.transform.position = new Vector3(70, 1, 0);
            var beam = Prim("Beam", Vector3.zero, Lit("BeamLit", new Color(0.2f, 0.9f, 1f)), 1f, PrimitiveType.Cube, beamRoot.transform);
            beam.transform.localPosition = new Vector3(0.5f, 0, 0);
            beam.transform.localScale = new Vector3(1f, 0.2f, 0.2f);
            beamRoot.AddComponent<DrawnBeamGrow>();
            var lineGo = new GameObject("LineBeam");
            lineGo.transform.position = new Vector3(90, 1, 0);
            var line = lineGo.AddComponent<LineRenderer>();
            line.useWorldSpace = true;
            line.widthMultiplier = 0.15f;
            line.sharedMaterial = Mat("LineUnlit", "Universal Render Pipeline/Unlit", m => m.SetColor("_BaseColor", new Color(1f, 0.2f, 0.8f)));
            line.SetPositions(new[] { new Vector3(90, 1, 0), new Vector3(90.5f, 1, 0) });
            lineGo.AddComponent<DrawnLineGrow>();
            // around the first places and many times their size: left out of them
            Prim("BigSphere", new Vector3(10, 1, 0), Lit("SkyShell", new Color(0.3f, 0.5f, 0.9f)), 64f, PrimitiveType.Sphere);
            // a world-space canvas beside a cube: on the cube's layer the render draws it too; on the UI layer it doesn't
            var small = Lit("Small", new Color(0.5f, 0.5f, 0.5f));
            Prim("CanvasCube", new Vector3(110, 1, 0), small, 0.5f);
            Canvas("CanvasDefault", new Vector3(110, 1, -0.6f), 0);
            Prim("CanvasUiCube", new Vector3(115, 1, 0), small, 0.5f);
            Canvas("CanvasUi", new Vector3(115, 1, -0.6f), UiLayer);
            Prim("UiCube", new Vector3(120, 1, 0), small, 0.5f).layer = UiLayer;
            Prim("OnlyCube", new Vector3(125, 1, 0), small, 0.5f).layer = only;
            Prim("NeverCube", new Vector3(127.5f, 1, 0), small, 0.5f).layer = never;
            var victim = Prim("VictimCube", new Vector3(130, 1, 0), small, 0.5f);
            // a flat terrain, its one layer an even (0.6, 0.4, 0.2), and a cube on it
            var groundTex = new Texture2D(4, 4, TextureFormat.RGBA32, false) { name = "Ground" };
            groundTex.SetPixels32(Enumerable.Repeat(new Color32(153, 102, 51, 255), 16).ToArray());
            groundTex.Apply();
            Save(groundTex, "Ground.asset");
            var groundLayer = new TerrainLayer { name = "Ground", diffuseTexture = groundTex, tileSize = new Vector2(10, 10) };
            Save(groundLayer, "Ground.terrainlayer");
            var terrainData = new TerrainData { heightmapResolution = 33, size = new Vector3(10, 2, 10) };
            terrainData.name = "DrawnTerrain";
            terrainData.terrainLayers = new[] { groundLayer };
            Save(terrainData, "DrawnTerrain.asset");
            var terrain = Terrain.CreateTerrainGameObject(terrainData);
            terrain.name = "Terrain";
            terrain.transform.position = new Vector3(135, 0, -5);
            Prim("TerrainCube", new Vector3(140, 0.25f, 0), small, 0.5f);

            Glows(checker, white, particles, only, never);
            Watchers();

            var leak = new GameObject("LeakWatch");
            leak.AddComponent<DrawnLeakBefore>();
            leak.AddComponent<DrawnLeakWatch>();
            var callbacks = new GameObject("Callbacks").AddComponent<DrawnCallbacks>();
            callbacks.Sun = sun;
            callbacks.Victim = victim;
            var pipeline = new GameObject("Pipeline").AddComponent<DrawnPipeline>();
            pipeline.Urp = urp;
            pipeline.Plain = plain;
            var template = Prim("CrowdTemplate", new Vector3(0, -50, 0), small);
            template.SetActive(false);
            new GameObject("Crowd").AddComponent<DrawnCrowd>().Template = template;
            EditorSceneManager.SaveScene(scene, Made + "/DrawnLab.unity");
        }

        static GameObject Sparks(string name, Vector3 at, Material material)
        {
            var fx = new GameObject(name);
            fx.transform.position = at;
            var ps = fx.AddComponent<ParticleSystem>();
            ps.Stop(true, ParticleSystemStopBehavior.StopEmittingAndClear);
            ps.useAutoRandomSeed = false;  // the same sparks every play: two plays compare value for value
            ps.randomSeed = 1234;
            var main = ps.main;
            main.startLifetime = 1.5f;
            main.startSpeed = 0.8f;
            main.startSize = 0.3f;
            main.startColor = new Color(1f, 0.6f, 0.2f, 1f);
            main.simulationSpace = ParticleSystemSimulationSpace.World;
            var emission = ps.emission;
            emission.rateOverTime = 40f;
            var shape = ps.shape;
            shape.shapeType = ParticleSystemShapeType.Sphere;
            shape.radius = 0.2f;
            fx.GetComponent<ParticleSystemRenderer>().sharedMaterial = material;
            return fx;
        }

        static void Canvas(string name, Vector3 at, int layer)
        {
            var go = new GameObject(name, typeof(RectTransform));
            go.layer = layer;
            var canvas = go.AddComponent<UnityEngine.Canvas>();
            canvas.renderMode = RenderMode.WorldSpace;
            var rect = (RectTransform)go.transform;
            rect.position = at;
            rect.sizeDelta = new Vector2(100, 100);
            rect.localScale = Vector3.one * 0.01f;  // 1 m square
            var image = new GameObject("Image", typeof(RectTransform)) { layer = layer };
            image.transform.SetParent(go.transform, false);
            var r = (RectTransform)image.transform;
            r.anchorMin = Vector2.zero;
            r.anchorMax = Vector2.one;
            r.offsetMin = Vector2.zero;
            r.offsetMax = Vector2.zero;
            image.AddComponent<Image>().color = Color.white;
        }

        // The light sources (z = 20), each named G_<what>, and the budget (z = 60), B_00 to B_69.
        static void Glows(Texture2D checker, Material white, Material particles, int only, int never)
        {
            var glowLit = Lit("GlowLit", new Color(0.2f, 0.4f, 0.6f), null, new Color(2f, 1f, 0.5f));
            Prim("G_Lit", new Vector3(0, 1, 20), glowLit);
            Prim("G_LitBig", new Vector3(5, 1, 20), glowLit, 2f);
            Prim("G_LitBright", new Vector3(10, 1, 20), Lit("GlowLitBright", new Color(0.2f, 0.4f, 0.6f), null, new Color(4f, 2f, 1f)));
            Prim("G_Unlit", new Vector3(15, 1, 20), Mat("UnlitBright", "Universal Render Pipeline/Unlit", m => m.SetColor("_BaseColor", new Color(3f, 3f, 3f))));
            Prim("G_Dark", new Vector3(20, 1, 20), Lit("Dark", new Color(0.02f, 0.02f, 0.02f)));
            Prim("G_LitWhite", new Vector3(25, 1, 20), white);
            var custom = Own("CustomGlow", "DrawnGlow", m => m.SetColor("_Glow", new Color(1.5f, 1.5f, 1.5f)));
            Prim("G_Custom", new Vector3(30, 1, 20), custom);
            Prim("G_CustomBig", new Vector3(35, 1, 20), custom, 2f);
            Prim("G_CustomSphere", new Vector3(40, 1, 20), custom, 1f, PrimitiveType.Sphere);
            Sparks("G_Sparks", new Vector3(45, 1, 20), particles);
            var tilted = Prim("G_LitTilted", new Vector3(50, 1, 20), glowLit);
            tilted.transform.rotation = Quaternion.Euler(30, 45, 10);
            tilted.transform.localScale = new Vector3(2f, 0.5f, 1f);
            Skinned("G_Skinned", new Vector3(55, 1, 20), custom);
            Skinned("G_SkinnedLit", new Vector3(57.5f, 1, 20), glowLit);
            // one URP Lit material read both ways: G_Lit from its properties, this one as rendered (its second material,
            // drawing nothing, has no standard interface)
            var nothing = Own("Nothing", "DrawnNothing", null);
            Prim("G_LitRendered", new Vector3(60, 1, 20), glowLit).GetComponent<Renderer>().sharedMaterials = new[] { glowLit, nothing };
            // a white Lit surface as rendered under a strong sun, a blue lamp and ambient light: none of it reaches the render;
            // nor does the realtime reflection probe it stands in, or (the twin outside the probe's box) the sky's reflection
            Prim("G_WhiteRendered", new Vector3(90, 1, 20), white).GetComponent<Renderer>().sharedMaterials = new[] { white, nothing };
            Prim("G_WhiteOutside", new Vector3(120, 1, 20), white).GetComponent<Renderer>().sharedMaterials = new[] { white, nothing };
            Prim("G_Quad", new Vector3(65, 1, 20), custom, 1f, PrimitiveType.Quad);
            var zero = Prim("G_Zero", new Vector3(70, 1, 20), custom);
            zero.transform.localScale = Vector3.zero;
            Prim("G_Ui", new Vector3(75, 1, 20), custom).layer = UiLayer;
            Prim("G_Huge", new Vector3(0, 0, 3000), custom, 1000f);
            // as rendered on a layer only a RenderObjects pass draws, and on one nothing draws, with the family's renderer
            Prim("G_Only", new Vector3(110, 1, 20), custom).layer = only;
            Prim("G_Never", new Vector3(115, 1, 20), custom).layer = never;
            // a white sprite 1 m square (drawn on both sides), a line and a trail, each giving off its own colour
            var white32 = new Texture2D(32, 32, TextureFormat.RGBA32, false) { name = "White32" };
            white32.SetPixels32(new Color32[32 * 32].Select(_ => new Color32(255, 255, 255, 255)).ToArray());
            white32.Apply();
            Save(white32, "White32.asset");
            var sprite = Sprite.Create(white32, new Rect(0, 0, 32, 32), new Vector2(0.5f, 0.5f), 32f);
            sprite.name = "White";
            AssetDatabase.AddObjectToAsset(sprite, white32);
            var spriteGo = new GameObject("G_Sprite");
            spriteGo.transform.position = new Vector3(95, 1, 20);
            var spriteRenderer = spriteGo.AddComponent<SpriteRenderer>();
            spriteRenderer.sprite = sprite;
            spriteRenderer.sharedMaterial = AssetDatabase.GetBuiltinExtraResource<Material>("Sprites-Default.mat");
            var unlitWhite = Mat("UnlitWhite", "Universal Render Pipeline/Unlit", m => m.SetColor("_BaseColor", Color.white));
            var lineGlow = new GameObject("G_Line").AddComponent<LineRenderer>();
            lineGlow.useWorldSpace = true;
            lineGlow.widthMultiplier = 0.15f;
            lineGlow.sharedMaterial = unlitWhite;
            lineGlow.SetPositions(new[] { new Vector3(99, 1, 20), new Vector3(101, 1, 20) });
            var trailGo = new GameObject("G_Trail");
            trailGo.transform.position = new Vector3(105, 1, 20);
            var trail = trailGo.AddComponent<TrailRenderer>();
            trail.time = 1f;
            trail.widthMultiplier = 0.1f;
            trail.sharedMaterial = unlitWhite;
            trailGo.AddComponent<DrawnCircle>();

            var sh = Own("ShProbe", "DrawnGlow", m =>
            {
                m.SetColor("_Tint", Color.white);
                m.SetColor("_Glow", Color.black);
            });
            Prim("ShProbe", new Vector3(80, 1, 20), sh);
            Prim("LitWhiteProbe", new Vector3(85, 1, 20), Lit("WhiteRough", Color.white));

            var budget = new GameObject("Budget");
            for (var i = 0; i < 70; i++)
                Prim("B_" + i.ToString("D2"), new Vector3(i * 1.5f, 1, 60), custom, 0.5f, PrimitiveType.Cube, budget.transform);
        }

        // A cube mesh skinned to one root bone stretched to 2 x 1 x 1: its local bounds are in that bone's space.
        static void Skinned(string name, Vector3 at, Material material)
        {
            var cube = GameObject.CreatePrimitive(PrimitiveType.Cube);
            var mesh = Object.Instantiate(cube.GetComponent<MeshFilter>().sharedMesh);
            Object.DestroyImmediate(cube);
            mesh.name = name + "Mesh";
            var weights = new BoneWeight[mesh.vertexCount];
            for (var i = 0; i < weights.Length; i++) weights[i] = new BoneWeight { boneIndex0 = 0, weight0 = 1f };
            mesh.boneWeights = weights;
            mesh.bindposes = new[] { Matrix4x4.identity };
            Save(mesh, name + "Mesh.asset");
            var go = new GameObject(name);
            go.transform.position = at;
            var root = new GameObject("Root");
            root.transform.SetParent(go.transform, false);
            root.transform.localScale = new Vector3(2f, 1f, 1f);
            var skin = go.AddComponent<SkinnedMeshRenderer>();
            skin.sharedMesh = mesh;
            skin.bones = new[] { root.transform };
            skin.rootBone = root.transform;
            skin.localBounds = new Bounds(Vector3.zero, Vector3.one);
            skin.sharedMaterial = material;
        }

        // Behind the player's camera, shadows off (only a camera that draws them sees them): the ones at z -45 are in a
        // drawn place, the ones at z -60 in none.
        static void Watchers()
        {
            var plain = Lit("WatchGrey", new Color(0.5f, 0.5f, 0.5f));
            var clip = new AnimationClip { name = "Swing" };
            clip.SetCurve("Arm", typeof(Transform), "localPosition.x", AnimationCurve.Linear(0f, 0f, 20f, 10f));
            Save(clip, "Swing.anim");
            var controller = AnimatorController.CreateAnimatorControllerAtPathWithClip(Made + "/Swing.controller", clip);
            var fxMat = AssetDatabase.LoadAssetAtPath<Material>(Made + "/Particles.mat");
            foreach (var (where, z) in new[] { ("In", -45f), ("Away", -60f) })
            {
                var watch = Prim("Watch_" + where, new Vector3(40, 1, z), plain);
                watch.GetComponent<Renderer>().shadowCastingMode = ShadowCastingMode.Off;
                watch.AddComponent<DrawnWatcher>();
                var anim = new GameObject("Anim_" + where);
                anim.transform.position = new Vector3(42, 1, z);
                var arm = Prim("Arm", new Vector3(42, 1, z), plain, 0.5f, PrimitiveType.Cube, anim.transform);
                arm.GetComponent<Renderer>().shadowCastingMode = ShadowCastingMode.Off;
                var animator = anim.AddComponent<Animator>();
                animator.runtimeAnimatorController = controller;
                animator.cullingMode = AnimatorCullingMode.CullCompletely;
                var fx = Sparks("Fx_" + where, new Vector3(38, 1, z), fxMat);
                var main = fx.GetComponent<ParticleSystem>().main;
                main.cullingMode = ParticleSystemCullingMode.Pause;
                fx.GetComponent<ParticleSystemRenderer>().shadowCastingMode = ShadowCastingMode.Off;
            }
        }

        // ---------------------------------------------------------------- DrawnBaked

        static void Baked()
        {
            var scene = EditorSceneManager.NewScene(NewSceneSetup.DefaultGameObjects, NewSceneMode.Single);
            var cam = Camera.main;
            cam.transform.position = new Vector3(0, 4, -8);
            cam.transform.LookAt(new Vector3(0, 0.5f, 0));
            var sun = Object.FindFirstObjectByType<Light>();
            sun.color = new Color(1f, 0.1f, 0.05f);
            sun.intensity = 3f;
            sun.lightmapBakeType = LightmapBakeType.Baked;
            sun.transform.rotation = Quaternion.Euler(50, 30, 0);
            var white = Lit("BakedWhite", new Color(0.9f, 0.9f, 0.9f));
            var floor = Prim("Floor", new Vector3(0, -0.05f, 0), white);
            floor.transform.localScale = new Vector3(20, 0.1f, 20);
            var baked = Prim("BakedCube", new Vector3(-2, 0.5f, 0), white);
            foreach (var go in new[] { floor, baked })
                GameObjectUtility.SetStaticEditorFlags(go, StaticEditorFlags.ContributeGI);
            Prim("ProbeSphere", new Vector3(2, 0.5f, 0), white, 1f, PrimitiveType.Sphere);
            var group = new GameObject("Probes").AddComponent<LightProbeGroup>();
            var points = new List<Vector3>();
            for (var x = -4; x <= 4; x += 2)
                for (var z = -4; z <= 4; z += 2)
                {
                    points.Add(new Vector3(x, 0.3f, z));
                    points.Add(new Vector3(x, 2f, z));
                }
            group.probePositions = points.ToArray();
            var settings = new LightingSettings
            {
                name = "DrawnBakedLighting", bakedGI = true, realtimeGI = false, lightmapper = LightingSettings.Lightmapper.ProgressiveCPU,
                lightmapResolution = 8, lightmapPadding = 2, directSampleCount = 8, indirectSampleCount = 16, environmentSampleCount = 16,
                maxBounces = 1, mixedBakeMode = MixedLightingMode.IndirectOnly,
            };
            Save(settings, "DrawnBakedLighting.lighting");
            Lightmapping.lightingSettings = settings;
            var leak = new GameObject("LeakWatch");
            leak.AddComponent<DrawnLeakBefore>();
            leak.AddComponent<DrawnLeakWatch>();
            const string path = Made + "/DrawnBaked.unity";
            EditorSceneManager.SaveScene(scene, path);
            Lightmapping.Bake();
            EditorSceneManager.SaveScene(scene, path);
            Debug.Log("ProbeTests: drawn bake: BakedCube lightmapIndex " + baked.GetComponent<Renderer>().lightmapIndex + ", lightmaps " +
                      LightmapSettings.lightmaps.Length + ", light probes " + (LightmapSettings.lightProbes != null ? LightmapSettings.lightProbes.count : 0));
        }

        // ---------------------------------------------------------------- DrawnCoin

        // As the sample game's coin (MakeCoin, AddCoinGlow, CoinSpawner): a root "Coin" that spins and bobs, its child
        // "Disc" a cylinder turned on its edge, gold, metallic and softly emissive; the coins children of a spawner at the
        // origin, over a ground plane.
        static void Coin()
        {
            var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            var camera = new GameObject("Main Camera") { tag = "MainCamera" };
            camera.AddComponent<Camera>();
            camera.transform.position = new Vector3(3f, 2f, -2f);
            var light = new GameObject("Sun");
            light.AddComponent<Light>().type = LightType.Directional;
            light.transform.rotation = Quaternion.Euler(50f, -30f, 0f);
            var ground = GameObject.CreatePrimitive(PrimitiveType.Plane);
            ground.name = "Ground";
            ground.transform.localScale = new Vector3(10f, 1f, 10f);
            var gold = Mat("CoinGold", "Universal Render Pipeline/Lit", m =>
            {
                m.SetColor("_BaseColor", new Color(1f, 0.78f, 0.25f));
                m.SetFloat("_Metallic", 0.9f);
                m.SetFloat("_Smoothness", 0.7f);
                m.EnableKeyword("_EMISSION");
                m.globalIlluminationFlags = MaterialGlobalIlluminationFlags.RealtimeEmissive;
                m.SetColor("_EmissionColor", new Color(0.55f, 0.40f, 0.08f) * 1.4f);
            });
            var spawner = new GameObject("CoinSpawner");
            foreach (var at in new[] { new Vector3(3f, 0.8f, 4f), new Vector3(-6f, 0.8f, 9f) })
            {
                var root = new GameObject("Coin");
                root.transform.SetParent(spawner.transform, false);
                root.transform.position = at;
                var disc = GameObject.CreatePrimitive(PrimitiveType.Cylinder);
                disc.name = "Disc";
                Object.DestroyImmediate(disc.GetComponent<Collider>());
                disc.transform.SetParent(root.transform, false);
                disc.transform.localRotation = Quaternion.Euler(90f, 0f, 0f);
                disc.transform.localScale = new Vector3(0.6f, 0.04f, 0.6f);
                disc.GetComponent<MeshRenderer>().sharedMaterial = gold;
                root.AddComponent<DrawnCoinSpin>();
            }
            EditorSceneManager.SaveScene(scene, Made + "/DrawnCoin.unity");
        }
    }
}
