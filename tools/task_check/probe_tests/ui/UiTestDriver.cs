// The ui test scene's HUD logic: a TMP score that counts up, a health slider that falls, a fill bar that rises, a button
// that changes a label, a button for the cursor click, all found by name.
using TMPro;
using UnityEngine;
using UnityEngine.UI;

public class UiTestDriver : MonoBehaviour
{
    TMP_Text score;
    Slider health;
    Image fill;
    Text clickLabel, cursorLabel;
    int clicks, cursorClicks;

    static T Named<T>(string name) where T : Component
    {
        var go = GameObject.Find(name);
        return go != null ? go.GetComponent<T>() : null;
    }

    void Start()
    {
        score = Named<TMP_Text>("ScoreText");
        health = Named<Slider>("HealthSlider");
        fill = Named<Image>("FillBar");
        clickLabel = Named<Text>("ClickLabel");
        cursorLabel = Named<Text>("CursorLabel");
        var change = Named<Button>("ChangeButton");
        if (change != null) change.onClick.AddListener(() => { clicks++; clickLabel.text = "CLICKED " + clicks; Debug.Log("UiTest: ChangeButton clicked"); });
        var cursor = Named<Button>("CursorButton");
        if (cursor != null) cursor.onClick.AddListener(() => { cursorClicks++; cursorLabel.text = "CURSOR " + cursorClicks; Debug.Log("UiTest: CursorButton clicked"); });
    }

    void Update()
    {
        var t = Time.timeSinceLevelLoad;
        if (score != null) score.text = "SCORE " + (Mathf.FloorToInt(t * 2f) * 10);
        if (health != null) health.value = Mathf.Max(0f, 100f - 5f * t);
        if (fill != null) fill.fillAmount = Mathf.Repeat(t / 10f, 1f);
    }
}
