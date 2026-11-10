using System;
using TMPro;
using UnityEngine;
using UnityEngine.SceneManagement;
using UnityEngine.UI;

namespace ProbeTests.Ui
{
    /// <summary>The Hud's uGUI values, set every frame by the frame count (frame k is play time k / 30): a TMP score in
    /// rich text, a slider falling 10 a second, a fill bar rising. TypeText shows its first 5 characters. StalePanel goes
    /// away at 0.5 s and its TMP text changes at 1 s while hidden; LayoutA leaves its row at 1 s. With -uilife, at 1 s it
    /// destroys DoomedText (after Update, before the frame is drawn) and makes a canvas, and at 1.5 s it loads the Grey
    /// scene.</summary>
    public sealed class UiHudDriver : MonoBehaviour
    {
        public int frames, score;
        public float health, fill;
        TMP_Text scoreText, staleText;
        Slider slider;
        Image fillBar;
        GameObject stalePanel, doomed, layoutA;
        bool life;

        static T Named<T>(string name) where T : Component
        {
            var go = GameObject.Find(name);
            return go != null ? go.GetComponent<T>() : null;
        }

        void Start()
        {
            scoreText = Named<TMP_Text>("ScoreText");
            Named<TMP_Text>("TypeText").maxVisibleCharacters = 5;  // a typewriter: TMP doesn't save this with the scene
            staleText = Named<TMP_Text>("StaleText");
            stalePanel = GameObject.Find("StalePanel");
            slider = Named<Slider>("HealthSlider");
            fillBar = Named<Image>("FillBar");
            doomed = GameObject.Find("DoomedText");
            layoutA = GameObject.Find("LayoutA");
            life = Array.IndexOf(Environment.GetCommandLineArgs(), "-uilife") >= 0;
        }

        void Update()
        {
            frames++;
            score = frames * 10;
            scoreText.text = "<b>SCORE</b> " + score;
            health = 100f - frames / 3f;
            slider.value = health;
            fill = frames % 300 / 300f;
            fillBar.fillAmount = fill;
            if (frames == 15) stalePanel.SetActive(false);
            if (frames == 30) staleText.text = "AFTER";
            if (frames == 30) layoutA.SetActive(false);  // LayoutB moves to the row's start when the layout is rebuilt
            if (life && frames == 30) Born();
            if (life && frames == 45) SceneManager.LoadScene("Assets/ProbeTests/ui/Made/Grey.unity");
        }

        void LateUpdate()
        {
            if (life && frames == 30 && doomed != null) Destroy(doomed);
        }

        static void Born()
        {
            var canvas = new GameObject("BornCanvas", typeof(RectTransform), typeof(Canvas));
            canvas.GetComponent<Canvas>().renderMode = RenderMode.ScreenSpaceOverlay;
            var go = new GameObject("BornText", typeof(RectTransform), typeof(Text));
            var rect = (RectTransform)go.transform;
            rect.SetParent(canvas.transform, false);
            rect.anchorMin = rect.anchorMax = rect.pivot = new Vector2(0f, 1f);
            rect.anchoredPosition = new Vector2(430f, -75f);
            rect.sizeDelta = new Vector2(120f, 20f);
            var text = go.GetComponent<Text>();
            text.font = Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf");
            text.text = "BORN";
        }
    }
}
