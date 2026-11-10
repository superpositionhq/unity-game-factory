// Builds the drawn family's test scenes (run with probe.py exec DrawnTest.BuildDrawnScenes.Run):
//   Assets/Scenes/DrawnTest.unity   one row of things a `drawn` query reads (z = 0), one row of light sources for
//                                   Hooks.GlowRender (z = 20), 70 small cubes for its budget (z = 60), under a strong
//                                   coloured sun, a blue point light, fog, a realtime reflection probe and a post-
//                                   processing volume, none of which a drawn render may show.
//   Assets/Scenes/DrawnBaked.unity  a lightmapped cube and a light-probe-lit sphere under a red baked light.
using System.Collections.Generic;
using System.IO;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Rendering.Universal;

namespace DrawnTest
{
    public static class BuildDrawnScenes
    {
        const string Dir = "Assets/Drawn";

        static Material Mat(string name, string shader, System.Action<Material> setup)
        {
            var path = Dir + "/" + name + ".mat";
            AssetDatabase.DeleteAsset(path);
            var m = new Material(Shader.Find(shader));
            setup(m);
            if (m.HasProperty("_Surface")) BaseShaderGUI.SetMaterialKeywords(m);
            AssetDatabase.CreateAsset(m, path);
            return m;
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

        static GameObject Cube(string name, Vector3 at, Material m, float size = 1f, PrimitiveType type = PrimitiveType.Cube)
        {
            var go = GameObject.CreatePrimitive(type);
            go.name = name;
            go.transform.position = at;
            go.transform.localScale = Vector3.one * size;
            go.GetComponent<Renderer>().sharedMaterial = m;
            Object.DestroyImmediate(go.GetComponent<Collider>());
            return go;
        }

        static Texture2D Checker()
        {
            var path = Dir + "/Checker.asset";
            AssetDatabase.DeleteAsset(path);
            var tex = new Texture2D(64, 64, TextureFormat.RGBA32, true, false) { name = "Checker", wrapMode = TextureWrapMode.Repeat };
            for (var y = 0; y < 64; y++)
                for (var x = 0; x < 64; x++)
                    tex.SetPixel(x, y, ((x / 8 + y / 8) & 1) == 0 ? new Color(1, 0, 0, 1) : new Color(0, 0, 1, 1));
            tex.Apply(true);
            AssetDatabase.CreateAsset(tex, path);
            return tex;
        }

        public static void Run()
        {
            Directory.CreateDirectory(Dir);
            Directory.CreateDirectory("Assets/Scenes");
            AssetDatabase.Refresh();
            var checker = Checker();

            // ---------------------------------------------------------------- DrawnTest
            var scene = EditorSceneManager.NewScene(NewSceneSetup.DefaultGameObjects, NewSceneMode.Single);
            var cam = Camera.main;
            cam.transform.position = new Vector3(40, 9, -32);
            cam.transform.LookAt(new Vector3(40, 1, 5));
            cam.farClipPlane = 300;
            cam.GetUniversalAdditionalCameraData().renderPostProcessing = true;
            var sun = Object.FindFirstObjectByType<Light>();
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
            var probe = new GameObject("RealtimeProbe").AddComponent<ReflectionProbe>();
            probe.mode = ReflectionProbeMode.Realtime;
            probe.refreshMode = ReflectionProbeRefreshMode.EveryFrame;
            probe.size = new Vector3(120, 20, 60);
            probe.transform.position = new Vector3(40, 2, 10);

            var profilePath = Dir + "/Post.asset";
            AssetDatabase.DeleteAsset(profilePath);
            var profile = ScriptableObject.CreateInstance<VolumeProfile>();
            var bloom = profile.Add<Bloom>(true);
            bloom.intensity.Override(3f);
            bloom.threshold.Override(0.5f);
            var adjust = profile.Add<ColorAdjustments>(true);
            adjust.postExposure.Override(0.7f);
            adjust.saturation.Override(-60f);
            adjust.colorFilter.Override(new Color(1f, 0.7f, 0.7f));
            AssetDatabase.CreateAsset(profile, profilePath);
            var volume = new GameObject("PostVolume").AddComponent<Volume>();
            volume.isGlobal = true;
            volume.sharedProfile = profile;

            // the drawn row (z = 0)
            Cube("RedCube", new Vector3(0, 1, 0), Lit("Red", new Color(0.8f, 0.2f, 0.1f)));
            Cube("CheckerCube", new Vector3(10, 1, 0), Lit("CheckerLit", Color.white, checker));
            var white = Lit("WhiteShared", Color.white);
            Cube("TintCube", new Vector3(20, 1, 0), white).AddComponent<BlockTint>();
            Cube("SpinCube", new Vector3(30, 1, 0), Lit("Grey", new Color(0.5f, 0.5f, 0.5f), checker)).AddComponent<Spinner>();
            var pan = Cube("PanQuad", new Vector3(40, 1, 0), Lit("PanLit", Color.white, checker), 2f, PrimitiveType.Quad);
            pan.transform.rotation = Quaternion.Euler(0, 180, 0);
            pan.AddComponent<TexturePan>();
            var particleMat = Mat("Particles", "Universal Render Pipeline/Particles/Unlit", m =>
            {
                m.SetFloat("_Surface", 1f);
                m.SetFloat("_Blend", 0f);
                m.SetColor("_BaseColor", new Color(1f, 0.5f, 0.1f, 0.6f));
            });
            var fx = new GameObject("Sparks");
            fx.transform.position = new Vector3(50, 1, 0);
            var ps = fx.AddComponent<ParticleSystem>();
            ps.useAutoRandomSeed = false;  // the same sparks every play: plays compare frame for frame
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
            fx.GetComponent<ParticleSystemRenderer>().sharedMaterial = particleMat;
            var late = new GameObject("LateHolder");
            var lateCube = Cube("LateCube", new Vector3(60, 1, 0), Lit("Yellow", new Color(0.9f, 0.8f, 0.1f)));
            lateCube.SetActive(false);
            var activator = late.AddComponent<ActivateAt>();
            activator.Target = lateCube;
            activator.Seconds = 5f;
            var beamRoot = new GameObject("BeamRoot");
            beamRoot.transform.position = new Vector3(70, 1, 0);
            var beam = Cube("Beam", Vector3.zero, Lit("BeamLit", new Color(0.2f, 0.9f, 1f)));
            beam.transform.SetParent(beamRoot.transform, false);
            beam.transform.localPosition = new Vector3(0.5f, 0, 0);
            beam.transform.localScale = new Vector3(1f, 0.2f, 0.2f);
            beamRoot.AddComponent<BeamGrow>();
            var lineGo = new GameObject("LineBeam");
            lineGo.transform.position = new Vector3(90, 1, 0);
            var line = lineGo.AddComponent<LineRenderer>();
            line.useWorldSpace = true;
            line.widthMultiplier = 0.15f;
            line.sharedMaterial = Mat("LineUnlit", "Universal Render Pipeline/Unlit", m => m.SetColor("_BaseColor", new Color(1f, 0.2f, 0.8f)));
            line.SetPositions(new[] { new Vector3(90, 1, 0), new Vector3(90.5f, 1, 0) });
            lineGo.AddComponent<LineGrow>();
            // around the first places, many times their size: left out of them
            Cube("BigSphere", new Vector3(10, 1, 0), Lit("SkyShell", new Color(0.3f, 0.5f, 0.9f)), 64f, PrimitiveType.Sphere);
            // red over blue: a band above y = 1 must read red only
            var top = Cube("TwoToneTop", new Vector3(25, 1.25f, 0), Lit("TopRed", new Color(1f, 0f, 0f)));
            top.transform.localScale = new Vector3(1f, 0.5f, 1f);
            var bottom = Cube("TwoToneBottom", new Vector3(25, 0.75f, 0), Lit("BottomBlue", new Color(0f, 0f, 1f)));
            bottom.transform.localScale = new Vector3(1f, 0.5f, 1f);

            // the light sources row (z = 20), each on its own
            var glowLit = Lit("GlowLit", new Color(0.2f, 0.4f, 0.6f), null, new Color(2f, 1f, 0.5f));
            Cube("GlowLit", new Vector3(0, 1, 20), glowLit);
            Cube("GlowLitBig", new Vector3(5, 1, 20), glowLit, 2f);
            Cube("GlowLitBright", new Vector3(10, 1, 20), Lit("GlowLitBright", new Color(0.2f, 0.4f, 0.6f), null, new Color(4f, 2f, 1f)));
            Cube("UnlitBright", new Vector3(15, 1, 20), Mat("UnlitBright", "Universal Render Pipeline/Unlit", m => m.SetColor("_BaseColor", new Color(3f, 3f, 3f))));
            Cube("DarkCube", new Vector3(20, 1, 20), Lit("Dark", new Color(0.02f, 0.02f, 0.02f)));
            Cube("LitWhiteCube", new Vector3(25, 1, 20), white);
            var custom = new Material(AssetDatabase.LoadAssetAtPath<Shader>(Dir + "/GlowNoEmission.shader"));
            custom.SetColor("_Glow", new Color(1.5f, 1.5f, 1.5f));
            AssetDatabase.DeleteAsset(Dir + "/CustomGlow.mat");
            AssetDatabase.CreateAsset(custom, Dir + "/CustomGlow.mat");
            Cube("CustomGlow", new Vector3(30, 1, 20), custom);
            Cube("CustomGlowBig", new Vector3(35, 1, 20), custom, 2f);
            var sphereGlow = Cube("CustomGlowSphere", new Vector3(40, 1, 20), custom, 1f, PrimitiveType.Sphere);
            var sh = new Material(custom);
            sh.SetColor("_Tint", Color.white);
            sh.SetColor("_Glow", Color.black);
            AssetDatabase.DeleteAsset(Dir + "/ShProbe.mat");
            AssetDatabase.CreateAsset(sh, Dir + "/ShProbe.mat");
            Cube("ShProbe", new Vector3(60, 1, 20), sh);
            Cube("LitWhiteProbe", new Vector3(65, 1, 20), Lit("WhiteRough", Color.white));
            var fx2 = Object.Instantiate(fx);
            fx2.name = "GlowSparks";
            fx2.transform.position = new Vector3(45, 1, 20);
            var tilted = Cube("GlowLitTilted", new Vector3(50, 1, 20), glowLit);
            tilted.transform.rotation = Quaternion.Euler(30, 45, 10);
            tilted.transform.localScale = new Vector3(2f, 0.5f, 1f);

            // the budget (z = 60)
            var budget = new GameObject("Budget");
            for (var i = 0; i < 70; i++)
            {
                var c = Cube("BudgetCube" + i.ToString("D2"), new Vector3(i * 1.5f, 1, 60), glowLit, 0.5f);
                c.transform.SetParent(budget.transform, true);
            }
            var report = new GameObject("Reports");
            report.AddComponent<GlowReport>().Names = new[]
            {
                "GlowLit", "GlowLitBig", "GlowLitBright", "UnlitBright", "DarkCube", "LitWhiteCube", "CustomGlow", "CustomGlowBig",
                "CustomGlowSphere", "GlowSparks", "GlowLitTilted", "RedCube",
            };
            report.AddComponent<LeakWatch>();
            EditorSceneManager.SaveScene(scene, "Assets/Scenes/DrawnTest.unity");

            BuildBaked();
            var list = new List<EditorBuildSettingsScene>(EditorBuildSettings.scenes);
            foreach (var p in new[] { "Assets/Scenes/DrawnTest.unity", "Assets/Scenes/DrawnBaked.unity" })
                if (!list.Exists(s => s.path == p)) list.Add(new EditorBuildSettingsScene(p, true));
            EditorBuildSettings.scenes = list.ToArray();
            AssetDatabase.SaveAssets();
            Debug.Log("DRAWNTEST scenes built");
        }

        static void BuildBaked()
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
            var floor = Cube("Floor", new Vector3(0, -0.05f, 0), white);
            floor.transform.localScale = new Vector3(20, 0.1f, 20);
            var baked = Cube("BakedCube", new Vector3(-2, 0.5f, 0), white);
            foreach (var go in new[] { floor, baked })
                GameObjectUtility.SetStaticEditorFlags(go, StaticEditorFlags.ContributeGI | StaticEditorFlags.BatchingStatic);
            Cube("ProbeSphere", new Vector3(2, 0.5f, 0), white, 1f, PrimitiveType.Sphere);
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
            AssetDatabase.DeleteAsset(Dir + "/DrawnBakedLighting.lighting");
            AssetDatabase.CreateAsset(settings, Dir + "/DrawnBakedLighting.lighting");
            Lightmapping.lightingSettings = settings;
            var report = new GameObject("Reports");
            report.AddComponent<GlowReport>().Names = new[] { "BakedCube", "ProbeSphere" };
            report.AddComponent<LeakWatch>();
            const string path = "Assets/Scenes/DrawnBaked.unity";
            EditorSceneManager.SaveScene(scene, path);
            var ok = Lightmapping.Bake();
            EditorSceneManager.SaveScene(scene, path);
            Debug.Log("DRAWNTEST bake " + (ok ? "done" : "failed") + ": BakedCube lightmapIndex " + baked.GetComponent<Renderer>().lightmapIndex +
                      ", lightmaps " + LightmapSettings.lightmaps.Length + ", probes " + (LightmapSettings.lightProbes != null ? LightmapSettings.lightProbes.count : 0));
        }
    }
}
