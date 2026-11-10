using UnityEngine;

// At `at` s does one thing to its target: deactivate it, disable its renderer, switch its Light on, or set its
// emission through a MaterialPropertyBlock.
public class TimedSwitch : MonoBehaviour
{
    public enum Action { Deactivate, HideRenderer, LightOn, EmissionOn, LightOff }
    public GameObject target;
    public Action action;
    public float at = 3f;
    public Color emission = new Color(4f, 4f, 4f, 1f);
    bool done;

    void Update()
    {
        if (done || target == null || Time.timeSinceLevelLoad < at) return;
        done = true;
        switch (action)
        {
            case Action.Deactivate: target.SetActive(false); break;
            case Action.HideRenderer: target.GetComponent<Renderer>().enabled = false; break;
            case Action.LightOn: target.GetComponent<Light>().enabled = true; break;
            case Action.LightOff: target.GetComponent<Light>().intensity = 0f; break;
            case Action.EmissionOn:
                var block = new MaterialPropertyBlock();
                target.GetComponent<Renderer>().GetPropertyBlock(block);
                block.SetColor("_EmissionColor", emission);
                target.GetComponent<Renderer>().SetPropertyBlock(block);
                break;
        }
    }
}
