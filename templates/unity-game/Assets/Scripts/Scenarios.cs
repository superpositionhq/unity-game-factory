// The game's scenarios, numbered 1..n as the design doc and the README's Scenarios table number them: scenario n's
// scene and name, and how a scenario starts.
//   - Started with -scenario <n> (and no -autoplay), the player goes straight to scenario n: past menus, tutorials and
//     popups, into its start state.
//   - In AutoPlay (-autoplay -scenario <n>, the AutoPlay drop-in in Assets/AutoPlay/), the first scene loads as usual
//     and the drop-in calls Load(n) at the recorder's go.
// Fill in Scenes and Names as scenarios are made. The scenario's own code applies its start state (Current says which
// scenario it is, 0 in normal play), calls Started() when gameplay begins, and AutoPlay.FinishRun("win" or "lose",
// score) when it ends; the bot is the game's own MonoBehaviour, acting only through AutoPlay's input calls while
// AutoPlay.IsRunning.
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.SceneManagement;

namespace __PROJECT__
{
    public static class Scenarios
    {
        /// <summary>Scenario n's scene at index n - 1, as it is in the build list (File > Build Profiles), e.g.
        /// "Assets/Scenes/Harbor.unity". One scene may serve several scenarios.</summary>
        public static readonly string[] Scenes = { };

        /// <summary>Scenario n's name at index n - 1, as the design doc names it, e.g. "First Night".</summary>
        public static readonly string[] Names = { };

        /// <summary>The scenario being played, 0 in normal play from the menus.</summary>
        public static int Current { get; private set; }

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
        static void Boot()
        {
            AutoPlay.StartScenario += Load;
            if (!AutoPlay.IsActive && AutoPlay.ScenarioArgument > 0) Load(AutoPlay.ScenarioArgument);
        }

        /// <summary>Loads scenario n's scene (the scene's own code then applies its start state).</summary>
        public static void Load(int n)
        {
            if (n < 1 || n > Scenes.Length || string.IsNullOrEmpty(Scenes[n - 1]))
            {
                var why = $"no scene for scenario {n}: Scenarios.Scenes lists {Scenes.Length}";
                Debug.LogError(why);
                AutoPlay.FinishRun("error", 0, new Dictionary<string, object> { ["reason"] = why });
                return;
            }
            Current = n;
            SceneManager.LoadScene(Scenes[n - 1]);
        }

        /// <summary>Call when the scenario's gameplay begins (the player has control, or the countdown starts): in AutoPlay
        /// this is the scenario's start, and the bot starts.</summary>
        public static void Started() => AutoPlay.ScenarioStarted(Current >= 1 && Current <= Names.Length ? Names[Current - 1] : "");
    }
}
