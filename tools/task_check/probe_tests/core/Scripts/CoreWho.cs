using UnityEngine;

namespace ProbeTests.Core
{
    /// <summary>Takes away the likelier players, so each rule for finding the player has its play: -corewho input
    /// (no tagged object), controller (nor a PlayerInput), camera (nor a CharacterController), none (nor a camera).
    /// -corecam ortho makes the main camera orthographic; -corecam high leaves no main camera, only a higher one.</summary>
    public sealed class CoreWho : MonoBehaviour
    {
        void Awake()
        {
            var who = CoreArgs.After("-corewho");
            var gone = who == "input" ? 2 : who == "controller" ? 3 : who == "camera" ? 4 : who == "none" ? 5 : 0;
            var names = new[] { "Tagged", "Tagged2", "Inputter", "Body", "Rig" };
            for (var i = 0; i < gone; i++) GameObject.Find(names[i]).SetActive(false);  // by name, wherever it hangs
            var cam = CoreArgs.After("-corecam");
            if (cam == "ortho") Camera.main.orthographic = true;
            if (cam != "high") return;
            Camera.main.tag = "Untagged";
            foreach (var camera in Resources.FindObjectsOfTypeAll<Camera>())
                if (camera.name == "High") camera.gameObject.SetActive(true);
        }
    }
}
