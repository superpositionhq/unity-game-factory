// The task checker's probe (unity-game-factory tools/task_check): a timed, scripted play of the game for a task
// check. The player is started with -taskProbe <spec file> (contract section 5): `shots` screenshots evenly over
// `seconds` of play time, the scripted inputs at their times, the player's position and the camera every `every`
// seconds, the spec's queries sampled with them, then probe.json in `out` and a clean exit. Without -taskProbe it
// does nothing.
//
// The play's clock is a fixed 30 fps (Time.captureFramerate): every frame is 1/30 s of play, however fast the machine
// renders, and it counts whether or not the game pauses itself (timeScale 0). It starts once the play's scene has
// loaded, and holds while a scene is still loading (an async load takes real time, not game time) and during a wait.
using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Reflection;
using System.Text;
using System.Threading;
using UnityEngine;
using UnityEngine.SceneManagement;

namespace TaskProbe
{
    [DefaultExecutionOrder(-32000)]  // before the game's scripts: this frame's inputs are queued first
    [AddComponentMenu("")]
    public sealed class Probe : MonoBehaviour
    {
        public const int Fps = 30;
        public const int Width = 960, Height = 540;
        const int MaxQueries = 256, MaxErrors = 50;

        public static Probe Active { get; private set; }
        static StreamWriter logFile;

        Dictionary<string, object> spec;
        string outDir, scene;
        double seconds = 20.0, every = 0.5;
        int shots;
        bool sound;
        Sel playerSel;
        Inputs inputs;
        readonly List<Query> queries = new List<Query>();
        readonly Dictionary<string, List<object>> measures = new Dictionary<string, List<object>>(StringComparer.Ordinal);
        readonly List<string> errors = new List<string>();
        readonly HashSet<string> errorsSeen = new HashSet<string>(StringComparer.Ordinal);
        readonly List<object> track = new List<object>(), cameraRows = new List<object>(), shotNames = new List<object>();

        bool started, done, sceneAsked;
        int frames, framesWaited, shotsTaken, startFrames;
        double nextSample;
        GameObject player;
        int playerFrame = -1;

        readonly List<string> pendingShots = new List<string>();
        readonly List<KeyValuePair<Query, Dictionary<string, object>>> pendingFrames = new List<KeyValuePair<Query, Dictionary<string, object>>>();
        Texture2D frameTexture;

        /// <summary>Play time, seconds.</summary>
        public double Elapsed => frames / (double)Fps;
        public double Every => every;
        public Dictionary<string, object> Spec => spec;

        // ---------------------------------------------------------------- start

        /// <summary>At the earliest moment scripts run. On the user's own desktop (a play started by hand, not by the
        /// checker) the window goes away at once; Unity activates it again a little later, so Begin moves it once more.</summary>
        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.SubsystemRegistration)]
        static void Hide()
        {
            var args = Environment.GetCommandLineArgs();
            if (Array.FindIndex(args, a => string.Equals(a, "-taskProbe", StringComparison.OrdinalIgnoreCase)) < 0) return;
            Application.runInBackground = true;
            Window.MoveAway();
        }

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.BeforeSceneLoad)]
        static void Boot()
        {
            var args = Environment.GetCommandLineArgs();
            var at = Array.FindIndex(args, a => string.Equals(a, "-taskProbe", StringComparison.OrdinalIgnoreCase));
            if (at < 0 || at + 1 >= args.Length) return;
            Dictionary<string, object> spec;
            try { spec = Json.Obj(Json.Parse(File.ReadAllText(args[at + 1], Encoding.UTF8))); }
            catch (Exception e)
            {
                Debug.LogError("TaskProbe: the play spec " + args[at + 1] + " couldn't be read: " + e.Message);
                return;
            }
            if (spec == null) return;
            var go = new GameObject("TaskProbe");
            DontDestroyOnLoad(go);
            var probe = go.AddComponent<Probe>();
            go.AddComponent<ProbeLate>();
            probe.Begin(spec);
        }

        void Begin(Dictionary<string, object> play)
        {
            Active = this;
            spec = play;
            outDir = Json.Str(spec, "out") ?? Path.Combine(Application.persistentDataPath, "TaskProbe");
            Directory.CreateDirectory(outDir);
            logFile = new StreamWriter(Path.Combine(outDir, "probe.log"), false, new UTF8Encoding(false)) { AutoFlush = true };
            seconds = Math.Min(Math.Max(Json.Num(spec, "seconds", 20.0), 1.0), 600.0);
            every = Math.Min(Math.Max(Json.Num(spec, "every", 0.5), 0.1), 1.0);
            shots = (int)Math.Min(Math.Max(Json.Num(spec, "shots", 0.0), 0.0), 64.0);
            scene = Json.Str(spec, "scene");
            sound = Json.Bool(spec, "sound");
            if (Json.Obj(spec, "player") is Dictionary<string, object> select)
            {
                playerSel = Sel.Parse(select);
                playerSel.Player = false;
            }

            // a fresh start every play: this build's saves and settings are its own (the checker's build gives it its
            // own company name), so nothing a play wrote reaches the next one
            if (Application.companyName.StartsWith("TaskProbe.", StringComparison.Ordinal))
            {
                PlayerPrefs.DeleteAll();
                try { if (Directory.Exists(Application.persistentDataPath)) Directory.Delete(Application.persistentDataPath, true); }
                catch (Exception e) { Log("the saved data couldn't be cleared: " + e.Message); }
            }

            Application.runInBackground = true;
            QualitySettings.vSyncCount = 0;
            Time.captureFramerate = Fps;
            Pace(false);
            Window.MoveAway();

            LoadQueries();
            inputs = new Inputs(this, Json.Arr(spec, "inputs"));
            inputs.Start();
            Application.quitting += OnQuitting;
            StartCoroutine(EndOfFrames());
            // The play's scene is asked for before the game's first scene has woken up: that scene's objects still get
            // Awake and OnEnable (Unity has already loaded it), but it is replaced before their Start and first Update.
            if (scene != null)
            {
                sceneAsked = true;
                if (SceneUtility.GetBuildIndexByScenePath(scene) < 0) Error("the play's scene " + scene + " isn't in the build: the game's own first scene is played");
                else SceneManager.LoadScene(scene, LoadSceneMode.Single);
            }
            Log($"play: {seconds:F1} s, every {every:F2} s, {shots} shot(s), {queries.Count} query(ies), scene {scene ?? "(the game's own)"}"
                + (Window.OnOwnDesktop() ? ", on its own desktop" : ", on the user's desktop (window moved off-screen)"));
        }

        /// <summary>Real-time pacing: on during a wait and a scene load, and always in a play that measures audio (sound
        /// plays in real time); else the play runs as fast as the machine renders.</summary>
        public void Pace(bool realTime)
        {
            Application.targetFrameRate = realTime || sound ? Fps : -1;
        }

        static IEnumerable<Type> SafeTypes()
        {
            Type[] types;
            try { types = typeof(Probe).Assembly.GetTypes(); }
            catch (ReflectionTypeLoadException e) { types = e.Types; }
            foreach (var t in types)
                if (t != null) yield return t;
        }

        void LoadQueries()
        {
            var kinds = new Dictionary<string, Type>(StringComparer.Ordinal);
            foreach (var type in SafeTypes())
            {
                var mark = type.GetCustomAttribute<ProbeQueryAttribute>();
                if (mark != null && typeof(Query).IsAssignableFrom(type) && !type.IsAbstract) kinds[mark.Kind] = type;
            }
            var asked = Json.Arr(Json.Obj(spec, "queries"), "queries");
            if (asked == null) return;
            foreach (var item in asked)
            {
                if (!(item is Dictionary<string, object> def)) continue;
                var id = Json.Str(def, "id");
                var kind = Json.Str(def, "kind");
                if (id == null || kind == null) { Error("a query has no id or kind"); continue; }
                if (queries.Count >= MaxQueries) { Error("more than " + MaxQueries + " queries: the rest are left out"); break; }
                if (!kinds.TryGetValue(kind, out var type)) { Error("no query kind " + kind); measures[id] = new List<object>(); continue; }
                try
                {
                    var q = (Query)Activator.CreateInstance(type);
                    q.Id = id;
                    q.Kind = kind;
                    q.Def = def;
                    q.Fields = Json.Strings(def, "fields");
                    q.Probe = this;
                    q.Load();
                    queries.Add(q);
                    measures[id] = new List<object>();
                }
                catch (Exception e)
                {
                    Error(kind + " " + id + ": " + (e.InnerException ?? e).Message);
                    measures[id] = new List<object>();
                }
            }
        }

        // ---------------------------------------------------------------- what queries read

        /// <summary>The probe's own objects are never selected.</summary>
        public static bool IsOwn(GameObject go) => Active != null && go == Active.gameObject;

        /// <summary>The player object (contract section 1), looked up once a frame; null when the scene has none.</summary>
        public GameObject Player
        {
            get
            {
                if (playerFrame != Time.frameCount)
                {
                    playerFrame = Time.frameCount;
                    player = FindPlayer();
                }
                return player;
            }
        }

        GameObject FindPlayer()
        {
            if (playerSel != null) return Find.First(playerSel);
            try
            {
                var tagged = GameObject.FindGameObjectWithTag("Player");
                if (tagged != null) return tagged;
            }
            catch (UnityException) { }
            foreach (var name in new[] { "PlayerInput", "CharacterController" })
            {
                var type = Reflect.TypeNamed(name);
                if (type == null || !typeof(Component).IsAssignableFrom(type)) continue;
                var found = FindFirstObjectByType(type) as Component;
                if (found != null) return found.gameObject;
            }
            var view = View;
            return view != null ? view.transform.root.gameObject : null;
        }

        /// <summary>The camera the player sees through: the main camera, else the enabled screen camera of highest depth.</summary>
        public Camera View
        {
            get
            {
                var main = Camera.main;
                if (main != null) return main;
                Camera best = null;
                foreach (var c in Camera.allCameras)
                    if (c.targetTexture == null && (best == null || c.depth > best.depth)) best = c;
                return best;
            }
        }

        /// <summary>Something a query couldn't read; goes to probe.json "query_errors" (once each, at most 50).</summary>
        public void Error(string message)
        {
            if (!errorsSeen.Add(message)) return;  // a query that fails every sample says so once
            Log("error: " + message);
            if (errors.Count < MaxErrors) errors.Add(message);
        }

        /// <summary>A line in the play's probe.log (beside probe.json), not in the game's own log.</summary>
        public static void Log(string message)
        {
            try { logFile?.WriteLine((Active != null ? Active.Elapsed.ToString("F2") : "0.00") + " [" + Time.realtimeSinceStartup.ToString("F1") + " s] " + message); }
            catch { }
        }

        // ---------------------------------------------------------------- the frame, before the game's scripts

        static bool Loading()
        {
            for (var i = 0; i < SceneManager.sceneCount; i++)
                if (!SceneManager.GetSceneAt(i).isLoaded) return true;
            return false;
        }

        void Update()
        {
            if (done) return;
            if (Time.captureFramerate != Fps) Time.captureFramerate = Fps;
            if (!started)
            {
                // the play's scene (asked for in Begin) must be the one in play before the clock starts
                if (scene != null && sceneAsked && SceneUtility.GetBuildIndexByScenePath(scene) >= 0
                    && !string.Equals(SceneManager.GetActiveScene().path, scene, StringComparison.OrdinalIgnoreCase))
                {
                    if (startFrames++ < 600) return;
                    Error("the play's scene " + scene + " didn't become the active scene: playing " + SceneManager.GetActiveScene().path);
                }
                if (Loading()) return;
                started = true;
#if TASKPROBE_AUDIO
                AudioTap.Follow();
#endif
                Log("the play's clock starts in " + SceneManager.GetActiveScene().path);
            }
            if (inputs.Waiting)
            {
                inputs.WaitTick();
                FrameQueries();
                return;
            }
            if (Loading())
            {
                Pace(true);  // let the loader work in real time; the clock holds
                return;
            }
            Pace(false);
            frames++;
            FrameQueries();
            inputs.Send(Elapsed);
        }

        void FrameQueries()
        {
            foreach (var q in queries)
            {
                try { q.Frame(1f / Fps); }
                catch (Exception e) { Error(q.Kind + " " + q.Id + " (frame): " + e.Message); }
            }
        }

        // ---------------------------------------------------------------- the frame, after the game's scripts

        internal void Late()
        {
            if (done || !started) return;
#if TASKPROBE_AUDIO
            // every few frames, so a listener that appears or changes (a scene load, a camera switch) is silenced at once
            if ((Time.frameCount & 3) == 0) AudioTap.Follow();
#endif
            if ((Time.frameCount & 15) == 0)
            {
                if (Screen.fullScreen || Screen.width != Width || Screen.height != Height) Screen.SetResolution(Width, Height, FullScreenMode.Windowed);
                Window.KeepAway();
            }
            if (inputs.Waiting || Loading()) return;
            var t = Elapsed;
            inputs.Late(t);
            if (t >= nextSample - 1e-9)
            {
                nextSample += every;
                TakeSample(t);
            }
            if (shots > 0 && shotsTaken < shots && t >= seconds * (shotsTaken + 0.5) / shots)
            {
                var name = $"shot_{shotsTaken:D2}.png";
                pendingShots.Add(name);
                shotNames.Add(name);
                shotsTaken++;
            }
            if (t >= seconds + 0.5)
            {
                // a sample that reads the frame drawn after it waits for that frame (a few frames at most)
                if ((pendingFrames.Count > 0 || pendingShots.Count > 0) && framesWaited++ < 5) return;
                Finish("time");
            }
        }

        void TakeSample(double t)
        {
            var who = Player;
            var row = new List<object> { t };
            if (who != null)
            {
                var p = who.transform.position;
                row.Add((double)p.x);
                row.Add((double)p.y);
                row.Add((double)p.z);
            }
            track.Add(row);
            var view = View;
            if (view != null)
            {
                var p = view.transform.position;
                var e = view.transform.eulerAngles;
                cameraRows.Add(new List<object>
                {
                    t, (double)p.x, (double)p.y, (double)p.z, Find.Angle(e.x), Find.Angle(e.y),
                    view.orthographic ? 0.0 : (double)view.fieldOfView,
                });
            }
            foreach (var q in queries)
            {
                var sample = new Dictionary<string, object>(StringComparer.Ordinal) { ["t"] = t };
                try { q.Sample(t, sample); }
                catch (Exception e) { Error(q.Kind + " " + q.Id + ": " + e.Message); }
                measures[q.Id].Add(sample);
                if (q.Needs != FrameNeed.None) pendingFrames.Add(new KeyValuePair<Query, Dictionary<string, object>>(q, sample));
            }
        }

        // ---------------------------------------------------------------- the frame as drawn

        IEnumerator EndOfFrames()
        {
            var wait = new WaitForEndOfFrame();
            while (!done)
            {
                yield return wait;
                if (pendingShots.Count == 0 && pendingFrames.Count == 0) continue;
                FrameImage frame = null;
                var wantPixels = pendingShots.Count > 0;
                foreach (var pending in pendingFrames)
                    if (pending.Key.Needs == FrameNeed.Pixels) wantPixels = true;
                if (wantPixels)
                {
                    try { frame = ReadFrame(); }
                    catch (Exception e) { Error("the frame couldn't be read: " + e.Message); }
                }
#if TASKPROBE_IMAGECONVERSION
                if (frame != null)
                    foreach (var name in pendingShots)
                    {
                        try { File.WriteAllBytes(Path.Combine(outDir, name), frameTexture.EncodeToPNG()); }
                        catch (Exception e) { Error("screenshot " + name + ": " + e.Message); }
                    }
#endif
                pendingShots.Clear();
                foreach (var pending in pendingFrames)
                {
                    try { pending.Key.FrameDrawn(frame, pending.Value); }
                    catch (Exception e) { Error(pending.Key.Kind + " " + pending.Key.Id + " (frame): " + e.Message); }
                }
                pendingFrames.Clear();
            }
        }

        FrameImage ReadFrame()
        {
            int w = Screen.width, h = Screen.height;
            if (frameTexture == null || frameTexture.width != w || frameTexture.height != h)
            {
                if (frameTexture != null) Destroy(frameTexture);
                frameTexture = new Texture2D(w, h, TextureFormat.RGBA32, false);
            }
            frameTexture.ReadPixels(new Rect(0, 0, w, h), 0, 0, false);
            frameTexture.Apply(false);
            return new FrameImage { Width = w, Height = h, Pixels = frameTexture.GetPixels32() };
        }

        // ---------------------------------------------------------------- the end

        void OnQuitting()
        {
            if (!done) Finish("shutdown", false);
        }

        void Finish(string reason, bool quit = true)
        {
            done = true;
            var who = Player;
            var result = new Dictionary<string, object>(StringComparer.Ordinal)
            {
                ["format"] = "unity-probe/1",
                ["ended"] = reason,
                ["seconds"] = Elapsed,
                ["scene"] = SceneManager.GetActiveScene().path,
                ["player"] = who != null ? who.name : null,
                ["inputs_sent"] = (double)(inputs != null ? inputs.Sent : 0),
                ["screenshots"] = shotNames,
                ["track"] = track,
                ["camera"] = cameraRows,
            };
            if (queries.Count > 0 || measures.Count > 0)
            {
                var all = new Dictionary<string, object>(StringComparer.Ordinal);
                foreach (var kv in measures) all[kv.Key] = kv.Value;
                result["measures"] = all;
            }
            if (errors.Count > 0) result["query_errors"] = new List<object>(errors);
            try { File.WriteAllText(Path.Combine(outDir, "probe.json"), Json.Write(result), new UTF8Encoding(false)); }
            catch (Exception e) { Log("probe.json couldn't be written: " + e.Message); }
            Log("the play ended: " + reason);
            try { logFile?.Dispose(); } catch { }
            logFile = null;
            if (!quit) return;
            // a game may refuse to quit (Application.wantsToQuit) or hang in its shutdown: the process ends either way
            new Thread(() =>
            {
                Thread.Sleep(5000);
                try { System.Diagnostics.Process.GetCurrentProcess().Kill(); } catch { }
            }) { IsBackground = true }.Start();
            Application.Quit(0);
        }
    }

    /// <summary>The probe's late half: after every script's LateUpdate (the camera has moved), it holds a held player,
    /// takes the samples and ends the play.</summary>
    [DefaultExecutionOrder(32000)]
    [AddComponentMenu("")]
    public sealed class ProbeLate : MonoBehaviour
    {
        void LateUpdate()
        {
            if (Probe.Active != null) Probe.Active.Late();
        }
    }
}
