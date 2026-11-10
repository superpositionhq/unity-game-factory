// AutoPlay: the game plays itself for a recording. A player started with -autoplay reads the run's flags, keeps its
// window at 1920x1080 and 60 fps, ignores the real keyboard, mouse and gamepads, waits for the recorder's "go" file,
// calls the game's StartScenario(n), and writes the run's files: every input the bot injects (inputs.jsonl), the
// game's telemetry (telemetry.jsonl), the result (outcome.json), the clock (clock.json) and the game's sound
// (audio.wav with audio_clock.jsonl), all on one clock (QueryPerformanceCounter). It quits when the run ends.
//
// The game supplies three things: a StartScenario handler (load scenario n and apply its start state), the calls
// ScenarioStarted(name) and FinishRun(result, score), and the bot, a MonoBehaviour of its own that acts only through
// Hold, Release, MouseDelta, Scroll and SetCursor below. Copy this folder into the game unchanged (Assets/AutoPlay/):
// every game then writes identical files. Without -autoplay, and always in the editor, nothing here acts.
using System;
using System.Collections.Generic;
using UnityEngine;

public static class AutoPlay
{
    /// <summary>The drop-in's version, written as autoplay_version in every file: it goes up when the files change
    /// shape.</summary>
    public const int Version = 1;

    // ------------------------------------------------------------------------------------------- the command line

    /// <summary>Started with -autoplay (a player only; the editor's Play mode never is).</summary>
    public static bool IsActive => AutoPlayRun.Active;

    /// <summary>From "go" to FinishRun: the only time the bot acts.</summary>
    public static bool IsRunning => AutoPlayRun.IsRunning;

    /// <summary>The run's scenario: -scenario &lt;n&gt; (1-based, the design doc's numbers), 1 without it.</summary>
    public static int Scenario => AutoPlayRun.Scenario;

    /// <summary>-scenario &lt;n&gt; as given on the command line, with or without -autoplay; 0 without it. A game
    /// started with -scenario n alone goes straight to scenario n's start state.</summary>
    public static int ScenarioArgument => AutoPlayRun.ScenarioArgument;

    /// <summary>The scenario's name: what ScenarioStarted was given, else -scenarioName, else "".</summary>
    public static string ScenarioName => AutoPlayRun.ScenarioName;

    /// <summary>-seed: UnityEngine.Random is seeded with it at boot and again at go; seed the game's own
    /// System.Random from it. Determinism is not required.</summary>
    public static int Seed => AutoPlayRun.Seed;

    /// <summary>-skill, 0..1: 0 a clumsy novice (slow reactions, noisy aim, poor choices, still trying), 1 the best the
    /// bot can do (a competent human; it need not win).</summary>
    public static float Skill => AutoPlayRun.Skill;

    /// <summary>-maxSeconds: the run ends with result "timeout" this long after go (0 = no limit).</summary>
    public static double MaxSeconds => AutoPlayRun.MaxSeconds;

    /// <summary>The run's folder (-outputDir), null when AutoPlay is off.</summary>
    public static string OutputDir => AutoPlayRun.Active ? AutoPlayRun.OutputDir : null;

    // ------------------------------------------------------------------------------------------- the game's side

    /// <summary>Required: called once at go with the scenario number. Load the scenario's scene and apply its start
    /// state, past menus, tutorials and popups. Subscribe from something that exists from boot (a
    /// [RuntimeInitializeOnLoadMethod], or the first scene's Awake), and only once.</summary>
    public static event Action<int> StartScenario
    {
        add => AutoPlayRun.StartScenario += value;
        remove => AutoPlayRun.StartScenario -= value;
    }

    /// <summary>Called when -maxSeconds have passed since go. A handler may compute a final score and call FinishRun
    /// itself; otherwise the run ends with FinishRun("timeout", the last SetScore).</summary>
    public static event Action Timeout
    {
        add => AutoPlayRun.Timeout += value;
        remove => AutoPlayRun.Timeout -= value;
    }

    /// <summary>Call when the scenario's gameplay begins (its scene loaded, the player has control or the countdown
    /// starts), with the scenario's name ("First Night"): telemetry scenario_start; the bot starts now. The first call
    /// of a run marks the start; one after an in-run restart only adds a telemetry row.</summary>
    public static void ScenarioStarted(string name) => AutoPlayRun.ScenarioStarted(name);

    /// <summary>Keep the score current: a run that times out ends with it.</summary>
    public static void SetScore(double score) => AutoPlayRun.SetScore(score);

    /// <summary>End the run: result "win", "lose" or "abort" (the bot is stuck: the game's call); "timeout" comes from
    /// the drop-in, "error" from a run that could not start its scenario. `extra` holds the game's own results (stars,
    /// lap times, times spotted) for outcome.json. Held inputs are released; the result stays on screen 2 s, then the
    /// files are finished and the player quits. A restart inside a run is not the end of the run.</summary>
    public static void FinishRun(string result, double score, IDictionary<string, object> extra = null) =>
        AutoPlayRun.FinishRun(result, score, extra);

    /// <summary>One telemetry row: the event's name and its fields (strings, numbers, bools, Vector2/3 as [x, y, z],
    /// a Quaternion as its euler angles [pitch, yaw, roll], lists and dictionaries of those). Every game writes
    /// "score" {score, delta, reason} on every change, "state" at 10 Hz {position [x, y, z] m, rotation [pitch, yaw,
    /// roll], velocity, and its own numbers} and "restart" {reason}; add the genre's own events freely. Written from
    /// boot to the end of the run; the keys t_ns, qpc, frame and event are the drop-in's.</summary>
    public static void Telemetry(string eventName, IDictionary<string, object> fields = null) =>
        AutoPlayRun.GameTelemetry(eventName, fields);

    // ------------------------------------------------------------------------------------------- the bot's input

    /// <summary>Press a key or button and keep it down until Release: "&lt;Keyboard&gt;/w", "&lt;Keyboard&gt;/space",
    /// "&lt;Mouse&gt;/leftButton", "&lt;Gamepad&gt;/buttonSouth", "&lt;Gamepad&gt;/dpad/up"; a trigger takes 0..1
    /// ("&lt;Gamepad&gt;/rightTrigger", 0.6f). A value of 0 releases it. Only while IsRunning.</summary>
    public static void Hold(string control, float value = 1f) => AutoPlayInput.Hold(control, new Vector2(value, 0f), false);

    /// <summary>Push a stick and keep it there until Release: "&lt;Gamepad&gt;/leftStick",
    /// "&lt;Gamepad&gt;/rightStick" (x right, y up, each -1..1). Vector2.zero releases it.</summary>
    public static void Hold(string control, Vector2 value) => AutoPlayInput.Hold(control, value, true);

    /// <summary>Let go of a control held with Hold.</summary>
    public static void Release(string control) => AutoPlayInput.Release(control);

    /// <summary>Let go of every held control.</summary>
    public static void ReleaseAll() => AutoPlayInput.ReleaseAll(false);

    /// <summary>Move the mouse by this many pixels for one frame (look); call it every frame the bot turns.</summary>
    public static void MouseDelta(float x, float y) => AutoPlayInput.MouseDelta(new Vector2(x, y));

    /// <summary>Turn the mouse wheel for one frame (y: forward is positive).</summary>
    public static void Scroll(float y, float x = 0f) => AutoPlayInput.Scroll(new Vector2(x, y));

    /// <summary>Point the virtual mouse at a screen position (pixels, origin bottom left, as Mouse.current.position
    /// reads it); a following Hold/Release of "&lt;Mouse&gt;/leftButton" clicks there. In AutoPlay Mouse.current is
    /// the virtual mouse: draw a visible cursor at it so the video shows where the bot points.</summary>
    public static void SetCursor(Vector2 screenPosition) => AutoPlayInput.SetCursor(screenPosition);

    // ------------------------------------------------------------------------------------------- the clock

    /// <summary>QueryPerformanceCounter now: the clock of every row (qpc).</summary>
    public static long Qpc() => AutoPlayClock.Now();

    /// <summary>QueryPerformanceFrequency (qpc_frequency).</summary>
    public static long QpcFrequency => AutoPlayClock.Frequency;

    /// <summary>qpc * 1e9 / qpc_frequency, without overflow: the t_ns of every row.</summary>
    public static long QpcToNs(long qpc) => AutoPlayClock.ToNs(qpc);
}
