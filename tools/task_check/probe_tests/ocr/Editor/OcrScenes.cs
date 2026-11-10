// The ocr family's scene (probe_tests/ocr): a dark orthographic camera at one unit a pixel, and the lab that puts up what
// each play shows (OcrLab, by the play's arguments), with the materials its GL and mesh readouts draw with.
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;

namespace ProbeTests.Ocr
{
    public static class OcrScenes
    {
        const string Made = "Assets/ProbeTests/ocr/Made";

        public static void Build()
        {
            if (!AssetDatabase.IsValidFolder(Made)) AssetDatabase.CreateFolder("Assets/ProbeTests/ocr", "Made");
            // GL immediate mode draws with a shader of its own (the engine's colour shader); the mesh with URP's unlit
            var gl = new Material(Shader.Find("Hidden/Internal-Colored"));
            gl.SetInt("_SrcBlend", (int)BlendMode.SrcAlpha);
            gl.SetInt("_DstBlend", (int)BlendMode.OneMinusSrcAlpha);
            gl.SetInt("_Cull", (int)CullMode.Off);
            gl.SetInt("_ZWrite", 0);
            gl.SetInt("_ZTest", (int)CompareFunction.Always);
            AssetDatabase.CreateAsset(gl, Made + "/OcrGl.mat");
            var unlit = new Material(Shader.Find("Universal Render Pipeline/Unlit"));
            unlit.SetColor("_BaseColor", Color.white);
            unlit.SetFloat("_Cull", (float)CullMode.Off);
            AssetDatabase.CreateAsset(unlit, Made + "/OcrMesh.mat");

            var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            var camera = new GameObject("Main Camera");
            camera.tag = "MainCamera";
            camera.transform.position = new Vector3(0f, 0f, -10f);
            var cam = camera.AddComponent<Camera>();
            cam.orthographic = true;
            cam.orthographicSize = 270f;
            cam.clearFlags = CameraClearFlags.SolidColor;
            cam.backgroundColor = new Color(0.08f, 0.08f, 0.12f, 1f);
            var lab = new GameObject("Lab").AddComponent<OcrLab>();
            lab.glMaterial = gl;
            lab.meshMaterial = unlit;
            EditorSceneManager.SaveScene(scene, Made + "/OcrLab.unity");
        }
    }
}
