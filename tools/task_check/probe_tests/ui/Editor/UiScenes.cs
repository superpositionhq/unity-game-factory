// The ui family's scenes (probe_tests/ui): uGUI and UI Toolkit widgets of every kind widgets and ui read, each at a
// known place, the ways a widget is or isn't on screen, buttons for widget and cursor clicks under each input module,
// a frame of known greys for screen, and a HUD of 500 texts.
using System;
using System.Collections.Generic;
using System.IO;
using System.IO.Compression;
using System.Text;
using TMPro;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.EventSystems;
using UnityEngine.InputSystem.UI;
using UnityEngine.Rendering;
using UnityEngine.Rendering.Universal;
using UnityEngine.SceneManagement;
using UnityEngine.UI;
using UnityEngine.UIElements;
using Image = UnityEngine.UI.Image;
using Slider = UnityEngine.UI.Slider;
using Toggle = UnityEngine.UI.Toggle;

namespace ProbeTests.Ui
{
    public static class UiScenes
    {
        const string MadeFolder = "Assets/ProbeTests/ui/Made";

        enum Module { InputSystem, Standalone, None }

        public static void Build()
        {
            if (!AssetDatabase.IsValidFolder(MadeFolder)) AssetDatabase.CreateFolder("Assets/ProbeTests/ui", "Made");
            TextEssentials();
            Checker();
            Panel("UiPanel", Theme(), null);
            Hud();
            Clicks("Clicks", Module.InputSystem);
            Clicks("ClicksOld", Module.Standalone);
            Clicks("ClicksNone", Module.None);
            Grey();
            Crowd();
        }

        // An asset made before a scene is opened is unloaded with the scene it was made in: load it again after.
        static T Made<T>(string file) where T : UnityEngine.Object => AssetDatabase.LoadAssetAtPath<T>(MadeFolder + "/" + file);

        // ---------------------------------------------------------------- assets

        // TextMeshPro's essential resources (its settings, default font and shaders), when the project has none: taken
        // from the package's own .unitypackage (a gzip tar of <guid>/asset, asset.meta, pathname) into Made/ with their
        // own GUIDs, so TMP text draws as in a game made from the template. AssetDatabase.ImportPackage doesn't finish
        // in -batchmode -quit.
        static void TextEssentials()
        {
            if (AssetDatabase.FindAssets("t:TMP_Settings").Length > 0) return;
            var info = UnityEditor.PackageManager.PackageInfo.FindForAssembly(typeof(TMP_Text).Assembly);
            var package = Path.Combine(info.resolvedPath, "Package Resources", "TMP Essential Resources.unitypackage");
            var parts = new Dictionary<string, Dictionary<string, byte[]>>(StringComparer.Ordinal);
            using (var tar = new GZipStream(File.OpenRead(package), CompressionMode.Decompress))
            {
                var header = new byte[512];
                while (Fill(tar, header))
                {
                    var name = Field(header, 0, 100);
                    if (name.Length == 0) break;
                    var size = Convert.ToInt64(Field(header, 124, 12).Trim(), 8);
                    var data = new byte[size];
                    Fill(tar, data);
                    Fill(tar, new byte[(512 - size % 512) % 512]);
                    var bits = name.TrimStart('.', '/').Split('/');
                    if (bits.Length != 2 || header[156] == (byte)'5') continue;
                    if (!parts.TryGetValue(bits[0], out var part)) parts[bits[0]] = part = new Dictionary<string, byte[]>(StringComparer.Ordinal);
                    part[bits[1]] = data;
                }
            }
            foreach (var part in parts.Values)
            {
                if (!part.TryGetValue("pathname", out var where) || !part.TryGetValue("asset", out var asset)) continue;
                var path = Encoding.UTF8.GetString(where).Split('\n')[0].Trim();
                if (!path.StartsWith("Assets/", StringComparison.Ordinal)) continue;
                var target = MadeFolder + path.Substring("Assets".Length);
                Directory.CreateDirectory(Path.GetDirectoryName(target));
                File.WriteAllBytes(target, asset);
                if (part.TryGetValue("asset.meta", out var meta)) File.WriteAllBytes(target + ".meta", meta);
            }
            AssetDatabase.Refresh(ImportAssetOptions.ForceSynchronousImport);
        }

        static bool Fill(Stream stream, byte[] buffer)
        {
            for (var at = 0; at < buffer.Length;)
            {
                var n = stream.Read(buffer, at, buffer.Length - at);
                if (n <= 0) return false;
                at += n;
            }
            return true;
        }

        static string Field(byte[] header, int at, int length)
        {
            var end = Array.IndexOf(header, (byte)0, at, length);
            return Encoding.ASCII.GetString(header, at, (end < 0 ? at + length : end) - at);
        }

        static void Checker()
        {
            var texture = new Texture2D(8, 8, TextureFormat.RGBA32, false) { filterMode = FilterMode.Point };
            for (var y = 0; y < 8; y++)
                for (var x = 0; x < 8; x++)
                    texture.SetPixel(x, y, (x + y) % 2 == 0 ? Color.white : Color.black);
            texture.Apply();
            AssetDatabase.CreateAsset(texture, MadeFolder + "/UiChecker.asset");
        }

        static ThemeStyleSheet Theme()
        {
            var path = MadeFolder + "/UiTheme.tss";
            File.WriteAllText(path, "@import url(\"unity-theme://default\");\n");
            AssetDatabase.ImportAsset(path, ImportAssetOptions.ForceUpdate);
            return AssetDatabase.LoadAssetAtPath<ThemeStyleSheet>(path);
        }

        static PanelSettings Panel(string name, ThemeStyleSheet theme, Action<PanelSettings> set)
        {
            var settings = ScriptableObject.CreateInstance<PanelSettings>();
            settings.themeStyleSheet = theme;
            settings.scaleMode = PanelScaleMode.ConstantPixelSize;
            settings.scale = 1f;
            set?.Invoke(settings);
            AssetDatabase.CreateAsset(settings, MadeFolder + "/" + name + ".asset");
            return settings;
        }

        static RenderTexture Target(string name)
        {
            var texture = new RenderTexture(256, 128, 16);
            AssetDatabase.CreateAsset(texture, MadeFolder + "/" + name + ".renderTexture");
            return texture;
        }

        static DefaultControls.Resources Skin() => new DefaultControls.Resources
        {
            standard = AssetDatabase.GetBuiltinExtraResource<Sprite>("UI/Skin/UISprite.psd"),
            background = AssetDatabase.GetBuiltinExtraResource<Sprite>("UI/Skin/Background.psd"),
            inputField = AssetDatabase.GetBuiltinExtraResource<Sprite>("UI/Skin/InputFieldBackground.psd"),
            knob = AssetDatabase.GetBuiltinExtraResource<Sprite>("UI/Skin/Knob.psd"),
            checkmark = AssetDatabase.GetBuiltinExtraResource<Sprite>("UI/Skin/Checkmark.psd"),
            dropdown = AssetDatabase.GetBuiltinExtraResource<Sprite>("UI/Skin/DropdownArrow.psd"),
            mask = AssetDatabase.GetBuiltinExtraResource<Sprite>("UI/Skin/UIMask.psd"),
        };

        // ---------------------------------------------------------------- objects

        static Scene New() => EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);

        static void Save(Scene scene, string name) => EditorSceneManager.SaveScene(scene, MadeFolder + "/" + name + ".unity");

        // At (0, 1, -10) looking along +z, 60 degrees of vertical field of view.
        static Camera MainCamera(Color background)
        {
            var go = new GameObject("Main Camera", typeof(Camera));
            go.tag = "MainCamera";
            go.transform.position = new Vector3(0f, 1f, -10f);
            var camera = go.GetComponent<Camera>();
            camera.clearFlags = CameraClearFlags.SolidColor;
            camera.backgroundColor = background;
            camera.fieldOfView = 60f;
            return camera;
        }

        static Transform NewCanvas(string name, int order = 0, RenderMode mode = RenderMode.ScreenSpaceOverlay)
        {
            var go = new GameObject(name, typeof(RectTransform), typeof(Canvas), typeof(GraphicRaycaster));
            var canvas = go.GetComponent<Canvas>();
            canvas.renderMode = mode;
            canvas.sortingOrder = order;
            return go.transform;
        }

        // A rectangle `w` x `h` pixels whose top left corner is `x`, `y` pixels from the parent's top left (y down).
        static RectTransform Place(RectTransform rect, Transform parent, float x, float y, float w, float h)
        {
            rect.SetParent(parent, false);
            rect.anchorMin = rect.anchorMax = rect.pivot = new Vector2(0f, 1f);
            rect.anchoredPosition = new Vector2(x, -y);
            rect.sizeDelta = new Vector2(w, h);
            return rect;
        }

        static GameObject Ui(string name, Transform parent, float x, float y, float w, float h, params Type[] components)
        {
            var go = new GameObject(name, typeof(RectTransform));
            foreach (var component in components) go.AddComponent(component);
            Place((RectTransform)go.transform, parent, x, y, w, h);
            return go;
        }

        static Text Legacy(string name, Transform parent, string text, float x, float y, float w, float h)
        {
            var t = Ui(name, parent, x, y, w, h, typeof(Text)).GetComponent<Text>();
            t.font = Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf");
            t.fontSize = 16;
            t.color = Color.white;
            t.text = text;
            return t;
        }

        static TextMeshProUGUI Tmp(string name, Transform parent, string text, float x, float y, float w, float h)
        {
            var t = Ui(name, parent, x, y, w, h, typeof(TextMeshProUGUI)).GetComponent<TextMeshProUGUI>();
            t.fontSize = 20;
            t.color = Color.white;
            t.text = text;
            return t;
        }

        static Image Box(string name, Transform parent, float x, float y, float w, float h, Color color, Sprite sprite = null)
        {
            var image = Ui(name, parent, x, y, w, h, typeof(Image)).GetComponent<Image>();
            image.color = color;
            image.sprite = sprite;
            return image;
        }

        static GameObject Control(GameObject go, string name, Transform parent, float x, float y, float w, float h)
        {
            go.name = name;
            Place((RectTransform)go.transform, parent, x, y, w, h);
            return go;
        }

        static GameObject MakeButton(DefaultControls.Resources skin, string name, Transform parent, float x, float y, float w, float h, string label)
        {
            var go = Control(DefaultControls.CreateButton(skin), name, parent, x, y, w, h);
            go.GetComponentInChildren<Text>().text = label;
            go.AddComponent<UiClickCount>();
            return go;
        }

        static GameObject Document(string name, PanelSettings settings)
        {
            var go = new GameObject(name, typeof(UIDocument));
            go.GetComponent<UIDocument>().panelSettings = settings;
            return go;
        }

        // ---------------------------------------------------------------- the HUD: what widgets and ui read

        // uGUI on the left (x below 600 px), UI Toolkit on the right; every name says what it tests: Vis* the ways a
        // widget is or isn't on screen, Rect* the ways a rectangle is placed. Positions in pixels of the 960x540 frame.
        static void Hud()
        {
            var scene = New();
            var checker = Made<Texture2D>("UiChecker.asset");
            var theme = Made<ThemeStyleSheet>("UiTheme.tss");
            var camera = MainCamera(new Color(0.1f, 0.12f, 0.18f));
            new GameObject("EventSystem", typeof(EventSystem), typeof(InputSystemUIInputModule));
            var skin = Skin();
            var tmpSkin = new TMP_DefaultControls.Resources
            {
                standard = skin.standard, background = skin.background, inputField = skin.inputField, knob = skin.knob,
                checkmark = skin.checkmark, dropdown = skin.dropdown, mask = skin.mask,
            };

            var hud = NewCanvas("HudCanvas");
            Tmp("ScoreText", hud, "<b>SCORE</b> 0", 20, 10, 240, 30);
            Tmp("TypeText", hud, "HELLO WORLD", 270, 10, 150, 30).maxVisibleCharacters = 5;
            Legacy("VisUnder", hud, "UNDER", 430, 10, 120, 30);
            Legacy("LegacyLabel", hud, "<color=#ffcc00>LEGACY</color> TEXT", 20, 45, 240, 25);
            Legacy("RawTagText", hud, "<b>RAW</b>", 270, 45, 150, 25).supportRichText = false;
            Legacy("DoomedText", hud, "DOOMED", 430, 45, 120, 25);

            var slider = Control(DefaultControls.CreateSlider(skin), "HealthSlider", hud, 20, 75, 200, 20).GetComponent<Slider>();
            slider.minValue = 0f;
            slider.maxValue = 100f;
            slider.value = 100f;
            var fill = Box("FillBar", hud, 230, 75, 150, 20, new Color(0.9f, 0.6f, 0.1f), skin.standard);
            fill.type = Image.Type.Filled;
            fill.fillMethod = Image.FillMethod.Horizontal;
            fill.fillAmount = 0f;
            var empty = Box("EmptyFill", hud, 390, 75, 100, 20, Color.white, skin.standard);
            empty.type = Image.Type.Filled;
            empty.fillAmount = 0f;

            var toggle = Control(DefaultControls.CreateToggle(skin), "SoundToggle", hud, 20, 100, 160, 20);
            toggle.GetComponent<Toggle>().isOn = true;
            toggle.GetComponentInChildren<Text>().text = "Sound";
            var bar = Control(DefaultControls.CreateScrollbar(skin), "PageBar", hud, 190, 100, 150, 20).GetComponent<Scrollbar>();
            bar.direction = Scrollbar.Direction.LeftToRight;
            bar.size = 0.2f;
            bar.value = 0.25f;

            var name = Control(DefaultControls.CreateInputField(skin), "NameField", hud, 20, 125, 180, 30).GetComponent<InputField>();
            name.placeholder.GetComponent<Text>().text = "Enter name...";
            name.text = "BOB";
            var hint = Control(DefaultControls.CreateInputField(skin), "EmptyField", hud, 210, 125, 180, 30).GetComponent<InputField>();
            hint.placeholder.GetComponent<Text>().text = "TYPE HERE";
            hint.text = "";

            var mode = Control(DefaultControls.CreateDropdown(skin), "ModeDropdown", hud, 20, 160, 180, 30).GetComponent<Dropdown>();
            mode.options = new List<Dropdown.OptionData> { new Dropdown.OptionData("EASY"), new Dropdown.OptionData("HARD") };
            mode.value = 1;
            mode.RefreshShownValue();
            var tmpMode = Control(TMP_DefaultControls.CreateDropdown(tmpSkin), "TmpDropdown", hud, 210, 160, 180, 30).GetComponent<TMP_Dropdown>();
            tmpMode.options = new List<TMP_Dropdown.OptionData> { new TMP_Dropdown.OptionData("ONE"), new TMP_Dropdown.OptionData("TWO") };
            tmpMode.value = 0;
            tmpMode.RefreshShownValue();
            Control(TMP_DefaultControls.CreateInputField(tmpSkin), "TmpField", hud, 400, 160, 180, 30).GetComponent<TMP_InputField>().text = "TMPNAME";

            Ui("PictureRaw", hud, 20, 195, 30, 30, typeof(RawImage)).GetComponent<RawImage>().texture = checker;
            Ui("BlankRaw", hud, 60, 195, 30, 30, typeof(RawImage));
            Box("SpriteImage", hud, 100, 195, 30, 30, Color.white, skin.standard);
            Box("PlainImage", hud, 140, 195, 30, 30, new Color(0.8f, 0.2f, 0.2f));
            Box("ScorePanel", hud, 180, 195, 60, 30, new Color(0.2f, 0.2f, 0.6f)).gameObject.AddComponent<UiScoreKeeper>();
            var hudRoot = Ui("HudRoot", hud, 250, 195, 30, 30, typeof(UiHudMarker));
            Legacy("HudChild", hudRoot.transform, "OWNED", 0, 0, 30, 30);  // a widget under a game's own component
            Ui("BarePanel", hud, 560, 45, 30, 25, typeof(CanvasGroup));  // a panel with no graphic: found by its name
            var stale = Ui("StalePanel", hud, 290, 195, 150, 30);
            Tmp("StaleText", stale.transform, "BEFORE", 0, 0, 150, 30);
            Tmp("TmpSprite", hud, "STAR <sprite=0>", 450, 195, 140, 30);

            // the ways a uGUI widget is or isn't on screen
            Legacy("VisClear", hud, "CLEAR", 20, 230, 60, 20).color = new Color(1f, 1f, 1f, 0f);
            Legacy("VisFaint", hud, "FAINT", 85, 230, 60, 20).color = new Color(1f, 1f, 1f, 0.004f);
            Legacy("VisDim", hud, "DIM", 150, 230, 60, 20).color = new Color(1f, 1f, 1f, 0.01f);
            var half = Ui("VisHalf", hud, 215, 230, 60, 20, typeof(CanvasGroup));
            half.GetComponent<CanvasGroup>().alpha = 0.5f;
            Legacy("VisHalfText", half.transform, "HALF", 0, 0, 60, 20).color = new Color(1f, 1f, 1f, 0.5f);
            Box("VisZero", hud, 280, 230, 30, 20, Color.white).transform.localScale = Vector3.zero;
            Box("VisOff", hud, -300, 230, 100, 20, Color.white);
            Box("VisEdge", hud, -50, 255, 100, 20, Color.white);
            var clip = Ui("VisClip", hud, 60, 255, 100, 40, typeof(RectMask2D));
            Box("VisClipped", clip.transform, 150, 0, 40, 20, Color.white);
            Box("VisClippedIn", clip.transform, 10, 10, 30, 20, Color.white);
            var off = Ui("VisOffCanvas", hud, 170, 255, 80, 20, typeof(Canvas));
            off.GetComponent<Canvas>().enabled = false;
            Legacy("VisOffCanvasText", off.transform, "OFFCANVAS", 0, 0, 80, 20);
            Legacy("VisOffGraphic", hud, "OFFGRAPHIC", 260, 255, 80, 20).enabled = false;
            Control(DefaultControls.CreateButton(skin), "VisMuted", hud, 350, 255, 80, 20).GetComponent<UnityEngine.UI.Button>().enabled = false;
            Control(DefaultControls.CreateButton(skin), "VisLocked", hud, 440, 255, 80, 20).GetComponent<UnityEngine.UI.Button>().interactable = false;
            // a button whose first label is inactive: its text is the first label that shows
            var shown = Control(DefaultControls.CreateButton(skin), "FirstShown", hud, 530, 255, 70, 20);
            shown.GetComponentInChildren<Text>().text = "SHOWN";
            var notShown = Legacy("NotShown", shown.transform, "HIDDEN", 0, 0, 70, 20);
            notShown.transform.SetAsFirstSibling();
            notShown.gameObject.SetActive(false);
            var hidden = Box("VisHidden", hud, 20, 300, 150, 30, Color.gray).gameObject;
            hidden.AddComponent<CanvasGroup>().alpha = 0f;
            Legacy("VisHiddenText", hidden.transform, "SECRET", 5, 5, 140, 20);
            var inactive = Box("VisInactive", hud, 180, 300, 150, 30, Color.gray).gameObject;
            Legacy("VisInactiveText", inactive.transform, "INACTIVE", 5, 5, 140, 20);
            inactive.SetActive(false);
            var mask = Box("VisMask", hud, 340, 300, 120, 30, Color.white, skin.standard);
            mask.gameObject.AddComponent<Mask>().showMaskGraphic = false;
            Legacy("VisMaskedText", mask.transform, "MASKED", 5, 5, 110, 20);
            Legacy("VisMaskedOut", mask.transform, "OUTSIDE", 130, 5, 100, 20);  // as if scrolled out of the Mask's rect

            // a row laid out by a HorizontalLayoutGroup: LayoutA (50 px), 10 px, LayoutB; the driver takes LayoutA away at 1 s
            var row = Ui("LayoutRow", hud, 300, 495, 300, 30, typeof(HorizontalLayoutGroup)).GetComponent<HorizontalLayoutGroup>();
            row.spacing = 10f;
            row.childControlWidth = row.childControlHeight = true;
            row.childForceExpandWidth = row.childForceExpandHeight = false;
            foreach (var cell in new[] { "LayoutA", "LayoutB" })
            {
                var element = Box(cell, row.transform, 0, 0, 50, 30, new Color(0.9f, 0.9f, 0.3f)).gameObject.AddComponent<LayoutElement>();
                element.preferredWidth = 50f;
                element.preferredHeight = 30f;
            }

            // turned 45 degrees about its centre, at (520, 360)
            var turned = Box("RectTurned", hud, 0, 0, 60, 60, new Color(0.3f, 0.8f, 0.3f)).rectTransform;
            turned.pivot = new Vector2(0.5f, 0.5f);
            turned.anchoredPosition = new Vector2(520f, -360f);
            turned.localRotation = Quaternion.Euler(0f, 0f, 45f);

            // another canvas drawn over VisUnder
            Box("CoverBox", NewCanvas("CoverCanvas", 5), 430, 10, 120, 30, new Color(0.9f, 0.5f, 0.1f));

            // scaled from 1920x1080 to the frame: (576, 864) 192 x 108 is (288, 432) 96 x 54
            var scaled = NewCanvas("ScaledCanvas", 1);
            var scaler = scaled.gameObject.AddComponent<CanvasScaler>();
            scaler.uiScaleMode = CanvasScaler.ScaleMode.ScaleWithScreenSize;
            scaler.referenceResolution = new Vector2(1920f, 1080f);
            scaler.matchWidthOrHeight = 0f;
            Box("RectScaled", scaled, 576, 864, 192, 108, new Color(0.6f, 0.3f, 0.9f));

            // a Screen Space - Camera canvas: 240 x 60 at 20 px from the left and 60 px from the bottom
            var cam = NewCanvas("CamCanvas", 0, RenderMode.ScreenSpaceCamera);
            cam.GetComponent<Canvas>().worldCamera = camera;
            cam.GetComponent<Canvas>().planeDistance = 2f;
            var camPanel = Box("RectCam", cam, 0, 0, 240, 60, new Color(0.1f, 0.2f, 0.7f)).rectTransform;
            camPanel.anchorMin = camPanel.anchorMax = camPanel.pivot = Vector2.zero;
            camPanel.anchoredPosition = new Vector2(20f, 60f);
            Tmp("CamText", camPanel, "CAMERA", 0, 0, 240, 60);

            // a camera canvas drawn into a render texture: not on the screen
            var tvCamera = new GameObject("TvCamera", typeof(Camera));
            tvCamera.transform.position = new Vector3(0f, 100f, 0f);
            tvCamera.GetComponent<Camera>().targetTexture = Target("UiTvCameraTarget");
            tvCamera.GetComponent<Camera>().depth = -5f;
            var tv = NewCanvas("TvCanvas", 0, RenderMode.ScreenSpaceCamera);
            tv.GetComponent<Canvas>().worldCamera = tvCamera.GetComponent<Camera>();
            Legacy("RectTv", tv, "TV", 10, 10, 100, 40);

            // a camera canvas whose camera is off: drawn by no one
            var offCamera = new GameObject("OffCamera", typeof(Camera)).GetComponent<Camera>();
            offCamera.enabled = false;
            var camOff = NewCanvas("CamOffCanvas", 0, RenderMode.ScreenSpaceCamera);
            camOff.GetComponent<Canvas>().worldCamera = offCamera;
            Box("RectCamOff", camOff, 120, 420, 100, 40, new Color(0.7f, 0.2f, 0.2f));

            // world-space canvases: 3 x 1 m, 10 m in front of the camera, and one behind it
            World("WorldCanvas", "RectWorld", new Vector3(0f, 1f, 0f));
            World("BackCanvas", "RectBack", new Vector3(0f, 1f, -20f));

            new GameObject("HudDriver").AddComponent<UiHudDriver>();

            Document("UitkDoc", Made<PanelSettings>("UiPanel.asset")).AddComponent<UiToolkitHud>().checker = checker;
            // a panel scaled from 1920x1080: (1344, 864) 192 x 108 is (672, 432) 96 x 54
            var scaledPanel = Panel("UiPanelScaled", theme, p =>
            {
                p.scaleMode = PanelScaleMode.ScaleWithScreenSize;
                p.referenceResolution = new Vector2Int(1920, 1080);
                p.screenMatchMode = PanelScreenMatchMode.MatchWidthOrHeight;
                p.match = 0f;
            });
            var scaledBox = Document("UitkScaledDoc", scaledPanel).AddComponent<UiToolkitBox>();
            scaledBox.boxName = "RectUitkScaled";
            scaledBox.rect = new Rect(1344f, 864f, 192f, 108f);
            var tvPanel = Panel("UiPanelTv", theme, p => p.targetTexture = Target("UiTvPanelTarget"));
            var tvBox = Document("UitkTvDoc", tvPanel).AddComponent<UiToolkitBox>();
            tvBox.boxName = "RectUitkTv";
            tvBox.rect = new Rect(10f, 10f, 100f, 40f);
            new GameObject("NoPanelDoc", typeof(UIDocument));
            Save(scene, "Hud");
        }

        static void World(string canvasName, string textName, Vector3 at)
        {
            var canvas = (RectTransform)NewCanvas(canvasName, 0, RenderMode.WorldSpace);
            canvas.sizeDelta = new Vector2(300f, 100f);
            canvas.pivot = new Vector2(0.5f, 0.5f);
            canvas.position = at;
            canvas.localScale = Vector3.one * 0.01f;
            var text = Legacy(textName, canvas, "WORLD", 0, 0, 300, 100).rectTransform;
            text.anchorMin = Vector2.zero;
            text.anchorMax = Vector2.one;
            text.pivot = new Vector2(0.5f, 0.5f);
            text.offsetMin = text.offsetMax = Vector2.zero;
        }

        // ---------------------------------------------------------------- clicks

        // The same buttons under each input module: the Input System's UI module, the old StandaloneInputModule (the
        // Input Manager, which the probe can't drive), and no EventSystem at all.
        static void Clicks(string sceneName, Module module)
        {
            var scene = New();
            MainCamera(new Color(0.15f, 0.15f, 0.15f));
            if (module != Module.None)
            {
                var events = new GameObject("EventSystem", typeof(EventSystem));
                if (module == Module.InputSystem) events.AddComponent<InputSystemUIInputModule>();
                else events.AddComponent<StandaloneInputModule>();
            }
            var skin = Skin();
            var canvas = NewCanvas("ClickCanvas");
            MakeButton(skin, "GoButton", canvas, 20, 20, 120, 30, "GO");
            var toggle = Control(DefaultControls.CreateToggle(skin), "GoToggle", canvas, 160, 20, 120, 20);
            toggle.GetComponent<Toggle>().isOn = true;
            toggle.AddComponent<UiClickCount>();
            var slider = Control(DefaultControls.CreateSlider(skin), "GoSlider", canvas, 300, 20, 200, 20);
            slider.GetComponent<Slider>().minValue = 0f;
            slider.GetComponent<Slider>().maxValue = 10f;
            slider.GetComponent<Slider>().value = 2f;
            slider.AddComponent<UiClickCount>();
            Control(DefaultControls.CreateInputField(skin), "GoField", canvas, 20, 60, 160, 30);
            var dropdown = Control(DefaultControls.CreateDropdown(skin), "GoDropdown", canvas, 200, 60, 160, 30).GetComponent<Dropdown>();
            dropdown.options = new List<Dropdown.OptionData> { new Dropdown.OptionData("A"), new Dropdown.OptionData("B") };
            var trigger = MakeButton(skin, "TriggerButton", canvas, 380, 60, 120, 30, "TRIGGER");
            trigger.AddComponent<EventTrigger>();
            trigger.AddComponent<UiTriggerCount>();
            MakeButton(skin, "NavNoneButton", canvas, 20, 100, 120, 30, "NAV").GetComponent<UnityEngine.UI.Button>().navigation =
                new Navigation { mode = Navigation.Mode.None };
            MakeButton(skin, "LockedButton", canvas, 160, 100, 120, 30, "LOCKED").GetComponent<UnityEngine.UI.Button>().interactable = false;
            MakeButton(skin, "LockedButton2", canvas, 300, 100, 120, 30, "LOCKED2");
            MakeButton(skin, "MutedButton", canvas, 440, 100, 120, 30, "MUTED").GetComponent<UnityEngine.UI.Button>().enabled = false;
            MakeButton(skin, "Twin", Ui("TwinRowA", canvas, 20, 140, 120, 30).transform, 0, 0, 120, 30, "TWIN A");
            MakeButton(skin, "Twin", Ui("TwinRowB", canvas, 160, 140, 120, 30).transform, 0, 0, 120, 30, "TWIN B");
            MakeButton(skin, "OffButton", canvas, -300, 180, 120, 30, "OFF");
            MakeButton(skin, "BlockedButton", canvas, 20, 220, 120, 30, "BLOCKED");
            MakeButton(skin, "CursorButton", canvas, 20, 300, 160, 40, "CURSOR");
            // a fully transparent button (a tap-anywhere overlay): a player's click fires it
            MakeButton(skin, "GhostButton", canvas, 300, 180, 120, 30, "").GetComponent<Image>().color = new Color(1f, 1f, 1f, 0f);
            // a Slider under a parent that takes clicks: the Slider takes the press, the parent the click
            var holder = Ui("SliderHolder", canvas, 300, 220, 200, 30, typeof(UiClickCount));
            Control(DefaultControls.CreateSlider(skin), "HeldSlider", holder.transform, 0, 5, 200, 20);
            // a half-transparent image on a canvas above, over BlockedButton: it takes the cursor's raycast
            Box("Blocker", NewCanvas("BlockCanvas", 10), 0, 210, 200, 50, new Color(0f, 0f, 0f, 0.5f));
            new GameObject("Watch").AddComponent<UiClickWatch>();
            Document("UitkClicks", Made<PanelSettings>("UiPanel.asset")).AddComponent<UiToolkitClicks>();
            Save(scene, sceneName);
        }

        // ---------------------------------------------------------------- screen

        // The camera clears to sRGB grey 64; the UI covers the right half with grey 192 and the top left corner with a
        // white and a black box, each 96 x 54. A volume (off unless the play says -uipost) doubles the exposure.
        static void Grey()
        {
            var scene = New();
            MainCamera(new Color32(64, 64, 64, 255));
            var canvas = NewCanvas("GreyCanvas");
            Box("GreyRight", canvas, 480, 0, 480, 540, new Color32(192, 192, 192, 255));
            Box("WhiteBox", canvas, 0, 0, 96, 54, Color.white);
            Box("BlackBox", canvas, 96, 0, 96, 54, Color.black);
            var profile = ScriptableObject.CreateInstance<VolumeProfile>();
            AssetDatabase.CreateAsset(profile, MadeFolder + "/UiGreyPost.asset");
            var adjust = profile.Add<ColorAdjustments>(true);
            adjust.postExposure.Override(1f);
            AssetDatabase.AddObjectToAsset(adjust, profile);
            EditorUtility.SetDirty(profile);
            AssetDatabase.SaveAssets();
            var volume = new GameObject("GreyVolume", typeof(Volume)).GetComponent<Volume>();
            volume.isGlobal = true;
            volume.sharedProfile = profile;
            volume.enabled = false;
            new GameObject("Grey").AddComponent<UiGrey>().volume = volume;
            Save(scene, "Grey");
        }

        // ---------------------------------------------------------------- cost and the cap

        // 300 uGUI texts T000-T299 and 200 UI Toolkit labels U000-U199, 20 to a row, 47 px apart from x = 10.
        static void Crowd()
        {
            var scene = New();
            MainCamera(Color.black);
            var canvas = NewCanvas("CrowdCanvas");
            for (var i = 0; i < 300; i++)
                Legacy("T" + i.ToString("D3"), canvas, "T" + i.ToString("D3"), 10 + 47 * (i % 20), 10 + 22 * (i / 20), 44, 20);
            Document("CrowdDoc", Made<PanelSettings>("UiPanel.asset")).AddComponent<UiCrowd>();
            Save(scene, "Crowd");
        }
    }
}
