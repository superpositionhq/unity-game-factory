// The run: the command line, the run's files, its phases (boot, ready, go, running, the result hold, the end), the
// display and timing rules, and the quit. Everything here runs on the main thread.
using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Runtime.InteropServices;
using System.Text;
using UnityEngine;
using UnityEngine.SceneManagement;

internal static class AutoPlayRun
{
    enum Phase { Off, Boot, WaitingForGo, Running, Holding, Done }

    const int Width = 1920, Height = 1080, FrameRate = 60;
    const double ReadyDelay = 1.0, HoldSeconds = 2.0, ShutdownSeconds = 30.0;
    static readonly string[] Reserved = { "t_ns", "qpc", "frame", "event" };
    static readonly string[] Stale = { "go", "ready.json", "outcome.json", "clock.json", "watchdog.json" };
    static readonly UTF8Encoding Utf8 = new UTF8Encoding(false);

    // ------------------------------------------------------------------------------------------- the command line

    static bool parsed, active, allowInput, mute, probePlay;
    static int scenario = 1, scenarioArgument, seed;
    static float skill = 1f;
    static double maxSeconds = 600.0, goTimeout = 60.0, watchdogSeconds = 120.0;
    static string scenarioName = "", outputDir, buildCommit = "", runId = "", game = "", quality;
    static readonly List<string> flagErrors = new List<string>();

    internal static bool Active { get { Parse(); return active; } }
    internal static int Scenario { get { Parse(); return scenario; } }
    internal static int ScenarioArgument { get { Parse(); return scenarioArgument; } }
    internal static string ScenarioName { get { Parse(); return scenarioName; } }
    internal static int Seed { get { Parse(); return seed; } }
    internal static float Skill { get { Parse(); return skill; } }
    internal static double MaxSeconds { get { Parse(); return maxSeconds; } }
    internal static string OutputDir { get { Parse(); return outputDir; } }
    internal static bool IsRunning => phase == Phase.Running;

    internal static Action<int> StartScenario;
    internal static Action Timeout;

    /// <summary>Read once, when first asked (the game may ask before this assembly's boot has run).</summary>
    static void Parse()
    {
        if (parsed) return;
        parsed = true;
        string[] args;
        try { args = Environment.GetCommandLineArgs(); }
        catch (Exception) { args = new string[0]; }
        var s = Value(args, "-scenario");
        if (s != null)
        {
            if (int.TryParse(s, NumberStyles.Integer, CultureInfo.InvariantCulture, out var n) && n >= 1) scenarioArgument = n;
            else flagErrors.Add("-scenario " + s + ": not a scenario number (1, 2, ...)");
        }
        scenario = scenarioArgument > 0 ? scenarioArgument : 1;
        active = !Application.isEditor && Flag(args, "-autoplay");
        if (!active)
        {
            foreach (var e in flagErrors) Log(e, LogType.Error);
            return;
        }
        probePlay = Flag(args, "-taskProbe");
        allowInput = Flag(args, "-autoplayAllowInput");
        mute = Flag(args, "-autoplayMute");
        scenarioName = Value(args, "-scenarioName") ?? "";
        seed = (int)Number(args, "-seed", 0, int.MinValue, int.MaxValue, true);
        skill = (float)Number(args, "-skill", 1.0, 0.0, 1.0, false);
        maxSeconds = Number(args, "-maxSeconds", 600.0, 0.0, 86400.0, false);
        goTimeout = Number(args, "-goTimeout", probePlay ? 0.0 : 60.0, 0.0, 86400.0, false);
        watchdogSeconds = Number(args, "-autoplayWatchdog", 120.0, 0.0, 86400.0, false);
        buildCommit = Value(args, "-buildCommit") ?? "";
        runId = Value(args, "-runId") ?? "";
        quality = Value(args, "-autoplayQuality");
        var dir = Value(args, "-outputDir");
        if (string.IsNullOrEmpty(dir))
            dir = Path.Combine(Application.persistentDataPath, "AutoPlay", DateTime.Now.ToString("yyyyMMdd-HHmmss", CultureInfo.InvariantCulture));
        try { outputDir = Path.GetFullPath(dir); }
        catch (Exception) { outputDir = dir; }
        // the exe's name (<Game>_Data is its data folder), as the game's code knows it
        var data = Path.GetFileName(Application.dataPath.TrimEnd('/', '\\'));
        game = data.EndsWith("_Data", StringComparison.Ordinal) ? data.Substring(0, data.Length - 5) : Application.productName;
    }

    /// <summary>A flag's value: the next argument, unless that is another flag ("-5" is a value).</summary>
    static string Value(string[] args, string name)
    {
        for (var i = 1; i < args.Length - 1; i++)
        {
            if (!string.Equals(args[i], name, StringComparison.OrdinalIgnoreCase)) continue;
            var v = args[i + 1];
            if (v.Length > 1 && v[0] == '-' && char.IsLetter(v[1])) return null;
            return v;
        }
        return null;
    }

    static bool Flag(string[] args, string name)
    {
        for (var i = 1; i < args.Length; i++)
            if (string.Equals(args[i], name, StringComparison.OrdinalIgnoreCase)) return true;
        return false;
    }

    static double Number(string[] args, string name, double fallback, double min, double max, bool integer)
    {
        var s = Value(args, name);
        if (s == null) return fallback;
        var ok = integer
            ? long.TryParse(s, NumberStyles.Integer, CultureInfo.InvariantCulture, out var l) && l >= min && l <= max
            : double.TryParse(s, NumberStyles.Float, CultureInfo.InvariantCulture, out _);
        if (!ok)
        {
            flagErrors.Add($"{name} {s}: not a number{(integer ? $" from {min} to {max}" : "")}; {fallback.ToString(CultureInfo.InvariantCulture)} is used");
            return fallback;
        }
        var v = double.Parse(s, NumberStyles.Float, CultureInfo.InvariantCulture);
        if (v < min || v > max)
        {
            flagErrors.Add($"{name} {s}: outside {min.ToString(CultureInfo.InvariantCulture)}..{max.ToString(CultureInfo.InvariantCulture)}, held to it");
            v = Math.Min(Math.Max(v, min), max);
        }
        return v;
    }

    // ------------------------------------------------------------------------------------------- state

    static Phase phase;
    static StreamWriter inputs, telemetry;
    static readonly object WriteGate = new object();
    static readonly List<string> clockSamples = new List<string>();
    static long goQpc, scenarioStartQpc, scenarioEndQpc, holdUntil, readyAt, goDeadline, nextGoPoll, nextWindowFix;
    static int goFrame, scenarioStartFrame, scenarioEndFrame, updates, windowTries, windowErrors;
    static bool settingsApplied, readyWritten, goTimedOut;
    static double score;
    static string result = "", extraJson = "{}";

    [DllImport("kernel32.dll")] static extern uint GetCurrentProcessId();

    // ------------------------------------------------------------------------------------------- boot

    [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.BeforeSceneLoad)]
    static void Boot()
    {
        Parse();
        if (!active || phase != Phase.Off) return;
        try
        {
            Directory.CreateDirectory(outputDir);
            foreach (var name in Stale)  // an earlier run's handshake in the same folder would start this one at once
            {
                var p = Path.Combine(outputDir, name);
                if (File.Exists(p)) File.Delete(p);
            }
            inputs = Open("inputs.jsonl");
            telemetry = Open("telemetry.jsonl");
        }
        catch (Exception e)
        {
            Log($"AutoPlay: the run's folder {outputDir} cannot be written ({e.Message}): quitting", LogType.Error);
            phase = Phase.Done;
            AutoPlayWatchdog.EndProcess(1);  // no run can come of it: at once, not after the recorder's wait for ready.json
            return;
        }
        phase = Phase.Boot;
        InputRow(Stamp().Add("type", "header").Add("schema", "autoplay-inputs/2"), true);
        TelemetryRow(Stamp().Add("event", "header").Add("schema", "autoplay-telemetry/2"), true);
        foreach (var e in flagErrors) Error(e);
        clockSamples.Add(AutoPlayClock.Sample("start", Time.frameCount));
        UnityEngine.Random.InitState(seed);
        Application.runInBackground = true;
        if (!probePlay)
        {
            var level = QualityLevel();
            if (level >= 0 && level != QualitySettings.GetQualityLevel()) QualitySettings.SetQualityLevel(level, true);
            QualitySettings.vSyncCount = 0;  // after the level: each level has its own
            Application.targetFrameRate = FrameRate;
        }
        AutoPlayAudio.Mute = mute;
        AutoPlayInput.Boot(allowInput);
        var host = new GameObject("AutoPlay");
        UnityEngine.Object.DontDestroyOnLoad(host);
        host.hideFlags = HideFlags.HideAndDontSave;  // the game's searches never find it
        host.AddComponent<AutoPlayEarly>();
        host.AddComponent<AutoPlayLate>();
        Application.quitting += OnQuitting;
        Log(FormattableString.Invariant(
            $"AutoPlay: scenario {scenario} seed {seed} skill {skill} max {maxSeconds} s; the run's files in {outputDir}"));
    }

    static StreamWriter Open(string name) =>
        new StreamWriter(new FileStream(Path.Combine(outputDir, name), FileMode.Create, FileAccess.Write,
            FileShare.ReadWrite | FileShare.Delete), Utf8, 1 << 16) { NewLine = "\n" };

    /// <summary>The quality level of the run: -autoplayQuality (an index or a name), else the highest the build
    /// ships.</summary>
    static int QualityLevel()
    {
        var names = QualitySettings.names;
        if (names.Length == 0) return -1;
        if (string.IsNullOrEmpty(quality)) return names.Length - 1;
        if (int.TryParse(quality, NumberStyles.Integer, CultureInfo.InvariantCulture, out var i) && i >= 0 && i < names.Length) return i;
        for (var n = 0; n < names.Length; n++)
            if (string.Equals(names[n], quality, StringComparison.OrdinalIgnoreCase)) return n;
        Error($"-autoplayQuality {quality}: no such quality level ({string.Join(", ", names)}); the highest is used");
        return names.Length - 1;
    }

    // ------------------------------------------------------------------------------------------- every frame

    /// <summary>Before the game's scripts (AutoPlayEarly, execution order -32000).</summary>
    internal static void EarlyUpdate()
    {
        if (phase == Phase.Off || phase == Phase.Done) return;
        var now = AutoPlayClock.Now();
        Enforce(now);
        AutoPlayAudio.Follow();
        switch (phase)
        {
            case Phase.Boot:
                BootFrame(now);
                break;
            case Phase.WaitingForGo:
                if (now < nextGoPoll) break;
                nextGoPoll = now + AutoPlayClock.Frequency / 20;
                var go = File.Exists(Path.Combine(outputDir, "go"));
                if (go || now >= goDeadline) BeginRun(!go);
                break;
            case Phase.Running:
                if (maxSeconds > 0.0 && AutoPlayClock.Seconds(goQpc, now) >= maxSeconds) TimeUp();
                break;
            case Phase.Holding:
                if (now < holdUntil) break;
                Export();
                End();
                break;
        }
    }

    /// <summary>After the game's scripts (AutoPlayLate, execution order 32000).</summary>
    internal static void LateUpdate()
    {
        if (phase == Phase.Off || phase == Phase.Done) return;
        AutoPlayInput.LateUpdate();
        if (!allowInput && Cursor.lockState != CursorLockMode.None) Cursor.lockState = CursorLockMode.None;
        AutoPlayAudio.Flush();
        lock (WriteGate)
        {
            try
            {
                inputs?.Flush();
                telemetry?.Flush();
            }
            catch (Exception e) { Log("AutoPlay: the run's files could not be written: " + e.Message, LogType.Error); }
        }
    }

    /// <summary>The display, timing and input rules, every frame: a game that changes them gets them back.</summary>
    static void Enforce(long now)
    {
        if (!Application.runInBackground) Application.runInBackground = true;
        if (!allowInput)
        {
            // never trap the cursor of the person using the machine
            if (Cursor.lockState != CursorLockMode.None) Cursor.lockState = CursorLockMode.None;
            AutoPlayInput.Enforce();
        }
        if (probePlay) return;  // a task check's play: its probe owns the window and the frame rate
        if (QualitySettings.vSyncCount != 0) QualitySettings.vSyncCount = 0;
        if (Application.targetFrameRate != FrameRate) Application.targetFrameRate = FrameRate;
        if (!readyWritten || WindowRight() || now < nextWindowFix || windowErrors > 10) return;
        nextWindowFix = now + AutoPlayClock.Frequency;
        windowErrors++;
        Error(windowErrors > 10
            ? $"the window stays {WindowText()}: left as it is"
            : $"the window became {WindowText()}: set back to {Width}x{Height} windowed");
        if (windowErrors <= 10) Screen.SetResolution(Width, Height, FullScreenMode.Windowed);
    }

    static bool WindowRight() => Screen.width == Width && Screen.height == Height && Screen.fullScreenMode == FullScreenMode.Windowed;

    static string WindowText() => $"{Screen.width}x{Screen.height} {Screen.fullScreenMode}";

    /// <summary>After the first rendered frame: the window (1920x1080 windowed), 1 s to settle, then ready.json.</summary>
    static void BootFrame(long now)
    {
        if (!settingsApplied)
        {
            if (++updates < 2) return;  // this frame's Update comes after the first frame was drawn
            settingsApplied = true;
            // only when it is not so already (the recorder starts the player with -screen-* at that size): a change of
            // the window can move it
            if (!probePlay && !WindowRight()) Screen.SetResolution(Width, Height, FullScreenMode.Windowed);
            readyAt = now + (long)(ReadyDelay * AutoPlayClock.Frequency);
            return;
        }
        if (now < readyAt) return;
        if (!probePlay && !WindowRight() && windowTries < 5)
        {
            windowTries++;
            Screen.SetResolution(Width, Height, FullScreenMode.Windowed);
            readyAt = now + (long)(ReadyDelay * AutoPlayClock.Frequency);
            return;
        }
        if (!probePlay && !WindowRight()) Error($"the window is {WindowText()}, not {Width}x{Height} windowed");
        var ready = new AutoPlayJson().Add("pid", (long)ProcessId()).Add("title", Application.productName)
            .Add("window", new Vector2(Screen.width, Screen.height)).Add("fullscreen_mode", Screen.fullScreenMode.ToString())
            .Add("scenario", scenario).Add("scenario_name", scenarioName).Add("autoplay_version", AutoPlay.Version);
        AddStamp(ready);
        try { WriteFile("ready.json", ready.Close() + "\n"); }
        catch (Exception e) { Error("ready.json could not be written: " + e.Message); }
        readyWritten = true;
        var level = QualitySettings.GetQualityLevel();
        TelemetryRow(Event("autoplay_ready").Add("window", new Vector2(Screen.width, Screen.height))
            .Add("fullscreen_mode", Screen.fullScreenMode.ToString())
            .Add("quality", level >= 0 && level < QualitySettings.names.Length ? QualitySettings.names[level] : "")
            .Add("quality_level", level).Add("vsync_count", QualitySettings.vSyncCount).Add("target_fps", Application.targetFrameRate));
        AutoPlayInput.Center(Screen.width, Screen.height);
        phase = Phase.WaitingForGo;
        goDeadline = now + (long)(goTimeout * AutoPlayClock.Frequency);
        nextGoPoll = now;
        Log(FormattableString.Invariant($"AutoPlay: ready ({WindowText()}); waiting up to {goTimeout} s for the go file"));
    }

    static uint ProcessId()
    {
#if UNITY_STANDALONE_WIN || UNITY_EDITOR_WIN
        try { return GetCurrentProcessId(); }
        catch (Exception) { }
#endif
        return 0;
    }

    // ------------------------------------------------------------------------------------------- the run

    static void BeginRun(bool timedOut)
    {
        goTimedOut = timedOut;
        goQpc = AutoPlayClock.Now();
        goFrame = Time.frameCount;
        clockSamples.Add(AutoPlayClock.Sample("go", goFrame));
        UnityEngine.Random.InitState(seed);
        var why = AutoPlayAudio.Start(outputDir);
        clockSamples.Add(AutoPlayClock.Sample("audio_start", Time.frameCount));
        if (maxSeconds > 0.0 && watchdogSeconds > 0.0)
            AutoPlayWatchdog.Arm(maxSeconds + watchdogSeconds, "run", Path.Combine(outputDir, "watchdog.json"));
        phase = Phase.Running;
        TelemetryRow(Event("run_start").Add("scenario", scenario).Add("seed", seed).Add("skill", skill).Add("go_timed_out", timedOut));
        if (why != null) Error("audio.wav could not be opened: " + why);
        Log(FormattableString.Invariant($"AutoPlay: go{(timedOut ? " (no go file: started at the timeout)" : "")}; StartScenario({scenario})"));
        var handler = StartScenario;
        if (handler == null)
        {
            Error("the game set no AutoPlay.StartScenario handler");
            FinishRun("error", 0.0, new Dictionary<string, object> { ["reason"] = "no StartScenario handler" });
            return;
        }
        try { handler(scenario); }
        catch (Exception e)
        {
            Debug.LogException(e);
            Error($"StartScenario({scenario}) threw {e.GetType().Name}: {e.Message}");
            FinishRun("error", 0.0, new Dictionary<string, object> { ["reason"] = $"StartScenario threw {e.GetType().Name}" });
        }
    }

    internal static void ScenarioStarted(string name)
    {
        if (!Active) return;
        if (phase != Phase.Running)
        {
            Log("AutoPlay: ScenarioStarted is only taken between go and FinishRun", LogType.Warning);
            return;
        }
        if (!string.IsNullOrEmpty(name)) scenarioName = name;
        if (scenarioStartQpc == 0)
        {
            scenarioStartQpc = AutoPlayClock.Now();
            scenarioStartFrame = Time.frameCount;
        }
        TelemetryRow(Event("scenario_start").Add("scenario", scenario).Add("scenario_name", scenarioName)
            .Add("scene", SceneManager.GetActiveScene().path));
        Log("AutoPlay: scenario started: " + scenarioName);
    }

    internal static void SetScore(double value)
    {
        if (Active) score = value;
    }

    internal static void FinishRun(string res, double finalScore, IDictionary<string, object> extra)
    {
        if (!Active || phase != Phase.Running) return;
        scenarioEndQpc = AutoPlayClock.Now();
        scenarioEndFrame = Time.frameCount;
        result = res ?? "";
        score = finalScore;
        extraJson = extra != null ? AutoPlayJson.Text(extra) : "{}";
        phase = Phase.Holding;  // the bot's calls stop here; the drop-in's own release rows follow
        AutoPlayInput.ReleaseAll(true);
        TelemetryRow(Event("scenario_end").Add("result", result).Add("score", score).AddRaw("extra", extraJson));
        holdUntil = AutoPlayClock.After(HoldSeconds);  // the result screen stays on the video
        Log(FormattableString.Invariant($"AutoPlay: the run ended: {result}, score {score}"));
    }

    static void TimeUp()
    {
        var handler = Timeout;
        if (handler != null)
        {
            try { handler(); }
            catch (Exception e)
            {
                Debug.LogException(e);
                Error($"a Timeout handler threw {e.GetType().Name}: {e.Message}");
            }
        }
        if (phase == Phase.Running) FinishRun("timeout", score, null);
    }

    /// <summary>After the result hold: the sound's files finished, then outcome.json.</summary>
    static void Export()
    {
        AutoPlayAudio.Stop();
        clockSamples.Add(AutoPlayClock.Sample("audio_stop", Time.frameCount));
        var end = scenarioEndQpc != 0 ? scenarioEndQpc : AutoPlayClock.Now();
        var started = scenarioStartQpc != 0;
        var o = new AutoPlayJson().Add("schema", "autoplay-outcome/2");
        Header(o);
        o.Add("result", result).Add("score", score)
            .Add("duration_s", Math.Round(AutoPlayClock.Seconds(started ? scenarioStartQpc : goQpc, end), 6))
            .Add("run_duration_s", Math.Round(AutoPlayClock.Seconds(goQpc, end), 6))
            .Add("go_qpc", goQpc);
        if (started) o.Add("scenario_start_qpc", scenarioStartQpc);
        else o.AddNull("scenario_start_qpc");
        o.Add("scenario_end_qpc", scenarioEndQpc)
            .Add("frames", (long)(scenarioEndFrame - (started ? scenarioStartFrame : goFrame)))
            .Add("inputs_injected", AutoPlayInput.Injected).Add("go_timed_out", goTimedOut)
            .Add("build_config", Debug.isDebugBuild ? "development" : "release").Add("engine_version", Application.unityVersion)
#if ENABLE_IL2CPP
            .Add("scripting_backend", "il2cpp")
#else
            .Add("scripting_backend", "mono")
#endif
            .Add("audio_frames", AutoPlayAudio.Frames).Add("audio_silence_frames", AutoPlayAudio.SilenceFrames)
            .Add("audio_gaps", AutoPlayAudio.Gaps).AddRaw("extra", extraJson);
        try { WriteFile("outcome.json", o.Close() + "\n"); }
        catch (Exception e) { Error("outcome.json could not be written: " + e.Message); }
    }

    /// <summary>The run's last files: clock.json, telemetry run_end, the rows closed; then the process ends.</summary>
    static void End()
    {
        clockSamples.Add(AutoPlayClock.Sample("end", Time.frameCount));
        WriteClock();
        TelemetryRow(Event("run_end").Add("audio_ok", AutoPlayAudio.Frames > 0));
        CloseFiles();
        phase = Phase.Done;
        Exit();
    }

    /// <summary>The player quits on its own (the game quit, the window was closed): a run that ended keeps its files;
    /// one that had not ended keeps what it has, with telemetry run_aborted.</summary>
    static void OnQuitting()
    {
        switch (phase)
        {
            case Phase.Holding:
                Export();
                End();
                return;
            case Phase.Boot:
            case Phase.WaitingForGo:
            case Phase.Running:
                AutoPlayInput.ReleaseAll(true);  // release rows for what the bot still held
                TelemetryRow(Event("run_aborted").Add("phase", PhaseName(phase)));
                if (phase == Phase.Running) AutoPlayAudio.Stop();  // the sound so far
                clockSamples.Add(AutoPlayClock.Sample("end", Time.frameCount));
                WriteClock();
                CloseFiles();
                phase = Phase.Done;
                Exit();
                return;
        }
    }

    /// <summary>The process ends at once, exit code 0, its files written and closed. The engine's shutdown is no part
    /// of a run: in it Unity saves the window it has (the run's 1920x1080 windowed) as the player's own settings for its
    /// next normal start (measured), a game may refuse to quit, and on a busy machine it can take minutes. The game's
    /// OnApplicationQuit does not run either, so a run reaches none of the player's saves that way. The exit watchdog
    /// stays armed (30 s, "shutdown") in case the process does not end.</summary>
    static void Exit()
    {
        if (watchdogSeconds > 0.0) AutoPlayWatchdog.Arm(ShutdownSeconds, "shutdown", Path.Combine(outputDir, "watchdog.json"));
        Log("AutoPlay: the run's files are written; the player ends");
        AutoPlayWatchdog.EndProcess(0);
    }

    static string PhaseName(Phase p) =>
        p == Phase.WaitingForGo ? "waiting_for_go" : p == Phase.Running ? "running" : p == Phase.Holding ? "holding" : "boot";

    // ------------------------------------------------------------------------------------------- the files

    /// <summary>The fields every header and outcome.json carry.</summary>
    static void Header(AutoPlayJson j) =>
        j.Add("autoplay_version", AutoPlay.Version).Add("engine", "unity").Add("game", game).Add("run_id", runId)
            .Add("scenario", scenario).Add("scenario_name", scenarioName).Add("seed", seed).Add("skill", skill)
            .Add("max_seconds", maxSeconds).Add("qpc_frequency", AutoPlayClock.Frequency).Add("build_commit", buildCommit);

    static void AddStamp(AutoPlayJson j)
    {
        var q = AutoPlayClock.Now();
        j.Add("t_ns", AutoPlayClock.ToNs(q)).Add("qpc", q).Add("frame", Time.frameCount);
    }

    /// <summary>A row's start: the stamp every row carries (t_ns, qpc, frame).</summary>
    internal static AutoPlayJson Stamp()
    {
        var j = new AutoPlayJson();
        AddStamp(j);
        return j;
    }

    static AutoPlayJson Event(string name) => Stamp().Add("event", name);

    internal static void InputRow(AutoPlayJson row) => InputRow(row, false);

    static void InputRow(AutoPlayJson row, bool header)
    {
        if (header) Header(row);
        lock (WriteGate) inputs?.WriteLine(row.Close());
    }

    static void TelemetryRow(AutoPlayJson row, bool header = false)
    {
        if (header) Header(row);
        lock (WriteGate) telemetry?.WriteLine(row.Close());
    }

    internal static void GameTelemetry(string name, IDictionary<string, object> fields)
    {
        if (!Active || telemetry == null || string.IsNullOrEmpty(name)) return;
        TelemetryRow(Event(name).AddAll(fields, Reserved));
    }

    /// <summary>A line of the player log (game.log), without the stack trace Unity adds to a script's lines.</summary>
    internal static void Log(string message, LogType type = LogType.Log) =>
        Debug.LogFormat(type, LogOption.NoStacktrace, null, "{0}", message);

    /// <summary>A telemetry error row and the player log's line.</summary>
    internal static void Error(string message)
    {
        Log("AutoPlay: " + message, LogType.Error);
        if (telemetry != null) TelemetryRow(Event("error").Add("message", message));
    }

    static void WriteClock()
    {
        var j = new AutoPlayJson().Add("schema", "autoplay-clock/2").Add("scenario", scenario).Add("scenario_name", scenarioName)
            .Add("qpc_frequency", AutoPlayClock.Frequency).Add("t_ns_definition", "qpc * 1e9 / qpc_frequency")
            .AddRaw("samples", "[" + string.Join(",", clockSamples) + "]");
        try { WriteFile("clock.json", j.Close() + "\n"); }
        catch (Exception e) { Error("clock.json could not be written: " + e.Message); }
    }

    /// <summary>Written whole, then renamed into place: whoever waits for the file never reads half of it.</summary>
    static void WriteFile(string name, string text)
    {
        var path = Path.Combine(outputDir, name);
        var part = path + ".part";
        File.WriteAllText(part, text, Utf8);
        if (File.Exists(path)) File.Delete(path);
        File.Move(part, path);
    }

    static void CloseFiles()
    {
        lock (WriteGate)
        {
            try { inputs?.Dispose(); } catch (Exception) { }
            try { telemetry?.Dispose(); } catch (Exception) { }
            inputs = null;
            telemetry = null;
        }
    }
}
