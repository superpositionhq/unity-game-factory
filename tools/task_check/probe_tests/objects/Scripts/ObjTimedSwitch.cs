using UnityEngine;

namespace ProbeTests.Objects
{
    // At `at` s of game time does one thing to its target, as a game would: deactivate it, disable its renderer, switch
    // its Light on or off, set its emission through a MaterialPropertyBlock (on every material, or on material `index`
    // alone), switch its own material's _EMISSION keyword on, force its renderer off, kick its Rigidbodies apart
    // (`amount` m/s outward and 2 m/s up), or spin its Rigidbody2D at `amount` deg/s.
    public class ObjTimedSwitch : MonoBehaviour
    {
        public enum Action { Deactivate, HideRenderer, LightOn, LightOff, EmissionOn, EmissionOnIndex, KeywordOn, ForceOff, Kick, Spin2D }
        public GameObject target;
        public Action action;
        public float at = 3f;
        public Color emission = new Color(4f, 4f, 4f, 1f);
        public int index;
        public float amount = 3f;
        bool done;

        void Update()
        {
            if (done || target == null || Time.timeSinceLevelLoad < at) return;
            done = true;
            var r = target.GetComponent<Renderer>();
            switch (action)
            {
                case Action.Deactivate: target.SetActive(false); break;
                case Action.HideRenderer: r.enabled = false; break;
                case Action.LightOn: target.GetComponent<Light>().enabled = true; break;
                case Action.LightOff: target.GetComponent<Light>().intensity = 0f; break;
                case Action.EmissionOn:
                case Action.EmissionOnIndex:
                {
                    var block = new MaterialPropertyBlock();
                    if (action == Action.EmissionOn) r.GetPropertyBlock(block); else r.GetPropertyBlock(block, index);
                    block.SetColor("_EmissionColor", emission);
                    if (action == Action.EmissionOn) r.SetPropertyBlock(block); else r.SetPropertyBlock(block, index);
                    break;
                }
                case Action.KeywordOn: r.material.EnableKeyword("_EMISSION"); break;  // the renderer's own copy of it
                case Action.ForceOff: r.forceRenderingOff = true; break;
                case Action.Kick:
                {
                    var centre = target.transform.position;
                    foreach (var body in target.GetComponentsInChildren<Rigidbody>())
                    {
                        var away = body.position - centre;
                        away.y = 0f;
                        body.linearVelocity = away.normalized * amount + Vector3.up * 2f;
                    }
                    break;
                }
                case Action.Spin2D: target.GetComponent<Rigidbody2D>().angularVelocity = amount; break;
            }
        }
    }
}
