using UnityEngine;

namespace ProbeTests.Objects
{
    // At `at` s of game time does one thing to its target, as a game would: deactivate it, disable its renderer, switch
    // its Light on or off, set its emission colour through a MaterialPropertyBlock (on every material, or on material
    // `index` alone) or set it as a vector, switch its own material's _EMISSION keyword on, force its renderer off, kick
    // its Rigidbodies apart (`amount` m/s outward and 2 m/s up), or spin its Rigidbody2D at `amount` deg/s.
    public class ObjTimedSwitch : MonoBehaviour
    {
        public enum Action { Deactivate, HideRenderer, LightOn, LightOff, EmissionOn, EmissionOnIndex, EmissionVector, KeywordOn, ForceOff, Kick, Spin2D }
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
                case Action.EmissionVector:
                {
                    var block = new MaterialPropertyBlock();
                    var one = action == Action.EmissionOnIndex;
                    if (one) r.GetPropertyBlock(block, index); else r.GetPropertyBlock(block);
                    if (action == Action.EmissionVector) block.SetVector("_EmissionColor", emission);
                    else block.SetColor("_EmissionColor", emission);
                    if (one) r.SetPropertyBlock(block, index); else r.SetPropertyBlock(block);
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
