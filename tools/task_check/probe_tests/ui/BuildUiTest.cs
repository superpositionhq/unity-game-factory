// Builds the ui family's test scene (Assets/Scenes/UiTest.unity). Run ImportTmp first (once): TextMeshPro's essential
// resources (TMP Settings, the default SDF font) come from a .unitypackage inside com.unity.ugui.
using System.IO;
using TMPro;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.EventSystems;
using UnityEngine.InputSystem.UI;
using UnityEngine.UI;
using UnityEngine.UIElements;
using Button = UnityEngine.UI.Button;
using Image = UnityEngine.UI.Image;
using Slider = UnityEngine.UI.Slider;
using Toggle = UnityEngine.UI.Toggle;

namespace UiTest.EditorTools
{
    public static class BuildUiTest
    {
        public static void ImportTmp()
        {
            var info = UnityEditor.PackageManager.PackageInfo.FindForAssembly(typeof(TMP_Text).Assembly);
            var path = Path.Combine(info.resolvedPath, "Package Resources", "TMP Essential Resources.unitypackage");
            Debug.Log("UiTest: importing " + path + " exists=" + File.Exists(path));
            AssetDatabase.ImportPackage(path, false);
            AssetDatabase.Refresh();
            Debug.Log("UiTest: TMP settings after import: " + AssetDatabase.FindAssets("t:TMP_Settings").Length);
        }

        static RectTransform Rect(GameObject go, Transform parent, Vector2 topLeft, Vector2 size)
        {
            go.transform.SetParent(parent, false);
            var rt = go.GetComponent<RectTransform>() ?? go.AddComponent<RectTransform>();
            rt.anchorMin = rt.anchorMax = new Vector2(0f, 1f);
            rt.pivot = new Vector2(0f, 1f);
            rt.anchoredPosition = new Vector2(topLeft.x, -topLeft.y);
            rt.sizeDelta = size;
            return rt;
        }

        static Text LegacyText(string name, Transform parent, string text, Vector2 at, Vector2 size, int fontSize = 20)
        {
            var go = new GameObject(name, typeof(RectTransform), typeof(Text));
            Rect(go, parent, at, size);
            var t = go.GetComponent<Text>();
            t.font = Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf");
            t.text = text;
            t.fontSize = fontSize;
            t.color = Color.white;
            return t;
        }

        static TextMeshProUGUI TmpText(string name, Transform parent, string text, Vector2 at, Vector2 size, float fontSize = 30)
        {
            var go = new GameObject(name, typeof(RectTransform));
            Rect(go, parent, at, size);
            var t = go.AddComponent<TextMeshProUGUI>();
            t.text = text;
            t.fontSize = fontSize;
            t.color = Color.white;
            return t;
        }

        public static void Run()
        {
            var scene = EditorSceneManager.NewScene(NewSceneSetup.DefaultGameObjects, NewSceneMode.Single);
            var cam = Camera.main;
            cam.clearFlags = CameraClearFlags.SolidColor;
            cam.backgroundColor = new Color(0.2f, 0.28f, 0.38f);
            var cube = GameObject.CreatePrimitive(PrimitiveType.Cube);
            cube.name = "SpinCube";
            cube.transform.position = new Vector3(0f, 0f, 6f);

            var es = new GameObject("EventSystem", typeof(EventSystem), typeof(InputSystemUIInputModule));

            var resources = new DefaultControls.Resources
            {
                standard = AssetDatabase.GetBuiltinExtraResource<Sprite>("UI/Skin/UISprite.psd"),
                background = AssetDatabase.GetBuiltinExtraResource<Sprite>("UI/Skin/Background.psd"),
                knob = AssetDatabase.GetBuiltinExtraResource<Sprite>("UI/Skin/Knob.psd"),
                checkmark = AssetDatabase.GetBuiltinExtraResource<Sprite>("UI/Skin/Checkmark.psd"),
            };

            // the overlay HUD
            var hud = new GameObject("HudCanvas", typeof(Canvas), typeof(CanvasScaler), typeof(GraphicRaycaster));
            hud.GetComponent<Canvas>().renderMode = RenderMode.ScreenSpaceOverlay;
            var ht = hud.transform;
            TmpText("ScoreText", ht, "SCORE 0", new Vector2(20, 20), new Vector2(300, 40), 32);
            LegacyText("LegacyLabel", ht, "LEGACY TEXT", new Vector2(20, 70), new Vector2(300, 30));
            var slider = DefaultControls.CreateSlider(resources);
            slider.name = "HealthSlider";
            Rect(slider, ht, new Vector2(20, 110), new Vector2(200, 20));
            var s = slider.GetComponent<Slider>();
            s.minValue = 0; s.maxValue = 100; s.value = 100;
            var fillGo = new GameObject("FillBar", typeof(RectTransform), typeof(Image));
            Rect(fillGo, ht, new Vector2(20, 140), new Vector2(200, 20));
            var fill = fillGo.GetComponent<Image>();
            fill.sprite = resources.standard;
            fill.type = Image.Type.Filled;
            fill.fillMethod = Image.FillMethod.Horizontal;
            fill.color = new Color(0.9f, 0.6f, 0.1f);
            var toggle = DefaultControls.CreateToggle(resources);
            toggle.name = "SoundToggle";
            Rect(toggle, ht, new Vector2(20, 170), new Vector2(160, 20));
            toggle.GetComponent<Toggle>().isOn = true;
            toggle.GetComponentInChildren<Text>().text = "Sound";
            var hidden = new GameObject("HiddenPanel", typeof(RectTransform), typeof(Image), typeof(CanvasGroup));
            Rect(hidden, ht, new Vector2(20, 200), new Vector2(200, 40));
            hidden.GetComponent<CanvasGroup>().alpha = 0f;
            LegacyText("HiddenText", hidden.transform, "SECRET", new Vector2(5, 5), new Vector2(190, 30));
            var inactive = new GameObject("InactivePanel", typeof(RectTransform), typeof(Image));
            Rect(inactive, ht, new Vector2(20, 250), new Vector2(200, 40));
            LegacyText("InactiveText", inactive.transform, "INACTIVE", new Vector2(5, 5), new Vector2(190, 30));
            inactive.SetActive(false);
            var change = DefaultControls.CreateButton(resources);
            change.name = "ChangeButton";
            Rect(change, ht, new Vector2(20, 300), new Vector2(160, 30));
            change.GetComponentInChildren<Text>().text = "PRESS";
            LegacyText("ClickLabel", ht, "NOT CLICKED", new Vector2(200, 300), new Vector2(200, 30));
            var cursor = DefaultControls.CreateButton(resources);
            cursor.name = "CursorButton";
            Rect(cursor, ht, new Vector2(20, 340), new Vector2(200, 40));
            cursor.GetComponentInChildren<Text>().text = "CURSOR";
            LegacyText("CursorLabel", ht, "CURSOR 0", new Vector2(240, 345), new Vector2(200, 30));
            hud.AddComponent<UiTestDriver>();

            // a Screen Space - Camera canvas, bottom right
            var camCanvas = new GameObject("CamCanvas", typeof(Canvas), typeof(CanvasScaler), typeof(GraphicRaycaster));
            var cc = camCanvas.GetComponent<Canvas>();
            cc.renderMode = RenderMode.ScreenSpaceCamera;
            cc.worldCamera = cam;
            cc.planeDistance = 2f;
            var panel = new GameObject("CamPanel", typeof(RectTransform), typeof(Image));
            panel.transform.SetParent(camCanvas.transform, false);
            var prt = panel.GetComponent<RectTransform>();
            prt.anchorMin = prt.anchorMax = prt.pivot = new Vector2(1f, 0f);
            prt.anchoredPosition = new Vector2(-20f, 120f);
            prt.sizeDelta = new Vector2(240f, 60f);
            panel.GetComponent<Image>().color = new Color(0.1f, 0.2f, 0.7f);
            var camText = TmpText("CamText", panel.transform, "CAMERA CANVAS", Vector2.zero, new Vector2(240, 60), 24);
            var ctr = camText.rectTransform;
            ctr.anchorMin = Vector2.zero; ctr.anchorMax = Vector2.one; ctr.offsetMin = ctr.offsetMax = Vector2.zero;
            camText.alignment = TextAlignmentOptions.Center;

            // a world-space canvas in front of the camera (not a ui element)
            var world = new GameObject("WorldCanvas", typeof(Canvas));
            var wc = world.GetComponent<Canvas>();
            wc.renderMode = RenderMode.WorldSpace;
            var wrt = world.GetComponent<RectTransform>();
            wrt.sizeDelta = new Vector2(300, 100);
            world.transform.position = cam.transform.position + new Vector3(0f, -1.2f, 5f);
            world.transform.localScale = Vector3.one * 0.01f;
            var wt = LegacyText("WorldText", world.transform, "WORLD TEXT", Vector2.zero, new Vector2(300, 100), 40);
            var wtr = wt.rectTransform;
            wtr.anchorMin = Vector2.zero; wtr.anchorMax = Vector2.one; wtr.offsetMin = wtr.offsetMax = Vector2.zero;

            // UI Toolkit: a PanelSettings with the default runtime theme, the document's elements built in code
            Directory.CreateDirectory("Assets/UiTest");
            const string tssPath = "Assets/UiTest/UiTestTheme.tss";
            File.WriteAllText(tssPath, "@import url(\"unity-theme://default\");\n");
            AssetDatabase.ImportAsset(tssPath, ImportAssetOptions.ForceUpdate);
            const string settingsPath = "Assets/UiTest/UiTestPanel.asset";
            var settings = AssetDatabase.LoadAssetAtPath<PanelSettings>(settingsPath);
            if (settings == null)
            {
                settings = ScriptableObject.CreateInstance<PanelSettings>();
                AssetDatabase.CreateAsset(settings, settingsPath);
            }
            settings.themeStyleSheet = AssetDatabase.LoadAssetAtPath<ThemeStyleSheet>(tssPath);
            settings.scaleMode = PanelScaleMode.ConstantPixelSize;
            settings.scale = 1f;
            EditorUtility.SetDirty(settings);
            AssetDatabase.SaveAssets();
            var docGo = new GameObject("UitkDoc", typeof(UIDocument));
            docGo.GetComponent<UIDocument>().panelSettings = settings;
            docGo.AddComponent<UitkTestPanel>();

            // a readout no UI component draws
            new GameObject("StrokeReadout", typeof(StrokeReadout));
            // a uGUI text over the readout's second line, all but transparent (alpha 0.01: on screen for ui, no pixels):
            // the frame reader leaves a line an element already reads to that element
            var overlap = LegacyText("OverlapLabel", ht, "HP", new Vector2(30, 462), new Vector2(240, 44));
            overlap.color = new Color(1f, 1f, 1f, 0.01f);

            const string path = "Assets/Scenes/UiTest.unity";
            EditorSceneManager.SaveScene(scene, path);
            Debug.Log("UiTest: saved " + path + " theme=" + (settings.themeStyleSheet != null) + " tmpFont=" + (TMP_Settings.defaultFontAsset != null));
        }
    }
}
