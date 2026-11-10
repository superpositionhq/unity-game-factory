// The task checker's probe (unity-game-factory tools/task_check): a timed, scripted play of the game for a task
// check. The player is started with -taskProbe <spec file> (contract section 5): `shots` screenshots evenly over
// `seconds` of play time, the scripted inputs at their times, the player's position and the camera every `every`
// seconds, the spec's queries sampled with them, then probe.json in `out` and a clean exit. Without -taskProbe it
// does nothing.
//
// The play's clock is a fixed 30 fps (Time.captureFramerate): every frame is 1/30 s of play, however fast the machine
// renders, and it counts whether or not the game pauses itself (timeScale 0). It starts once the play's scene has
// loaded, and holds while a scene is still loading (an async load takes real time, not game time; at most ten
// seconds of frames, since a load the game parks never finishes) and during a wait.
using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Reflection;
using System.Runtime.InteropServices;
using System.Text;
using System.Text.RegularExpressions;
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
        const int MaxLoadFrames = 10 * Fps;  // the clock holds this long for one load at most
        const string SpecFormat = "unity-probe-play/1", QueriesFormat = "game-probe-queries/1";
        // the company name Editor/Build.cs gives the checker's build of a scratch copy, and nothing else has
        static readonly Regex OwnCompany = new Regex("^TaskProbe\\.[0-9a-f]{12}$", RegexOptions.CultureInvariant);

        public static Probe Active { get; private set; }
        /// <summary>Goes up before the game's scripts, after their Updates and after their LateUpdates. What is looked
        /// up once for one pass over the scene (the player, a select's order, a render's budget) is kept by it: a
        /// search an input makes before the game's scripts never serves the samples taken after them.</summary>
        public static int Stamp { get; private set; }
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
        bool counted;  // this frame is one of the play's clock (not one of a wait or of a scene loading)
        bool quitAsked;  // the play is over and the probe asked the game to quit
        int frames, framesWaited, shotsTaken, startFrames, loadFrames, framesAfterQuit, errorsLeftOut;
        double nextSample;
        GameObject player;
        int playerStamp = -1;

        readonly List<string> pendingShots = new List<string>();
        readonly List<KeyValuePair<Query, Dictionary<string, object>>> pendingFrames = new List<KeyValuePair<Query, Dictionary<string, object>>>();
        Texture2D frameTexture;

        /// <summary>Play time, seconds.</summary>
        public double Elapsed => frames / (double)Fps;

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
            if (at < 0) return;
            Dictionary<string, object> spec = null;
            var why = "no file is named";
            if (at + 1 < args.Length)
            {
                try
                {
                    spec = Json.Obj(Json.Parse(File.ReadAllText(args[at + 1], Encoding.UTF8)));
                    why = spec == null ? "it isn't a JSON object" : Json.Str(spec, "format") != SpecFormat ? "its format isn't " + SpecFormat : null;
                }
                catch (Exception e) { why = e.Message; }
            }
            if (why != null)
            {
                // no play can come of it: the player ends at once, not at the checker's timeout as a game left running
                Debug.LogError("TaskProbe: the play spec" + (at + 1 < args.Length ? " " + args[at + 1] : "") + " couldn't be read: " + why);
                Application.Quit(2);
                return;
            }
            var go = new GameObject("TaskProbe");
            DontDestroyOnLoad(go);
            // not an object of the game: its searches (FindObjectsByType and the like leave out what isn't saved) never
            // find the probe, so a game that destroys every object it finds to start over leaves the play running
            go.hideFlags = HideFlags.HideAndDontSave;
            var probe = go.AddComponent<Probe>();
            go.AddComponent<ProbeLate>();
            probe.Begin(spec);
        }

        void Begin(Dictionary<string, object> play)
        {
            Active = this;
            spec = play;
            outDir = Json.Str(spec, "out") ?? Path.Combine(Application.persistentDataPath, "TaskProbe");
            var kept = ForgetSaves();  // before anything is written: without `out` the play's folder is in the saved data
            Directory.CreateDirectory(outDir);
            logFile = new StreamWriter(Path.Combine(outDir, "probe.log"), false, new UTF8Encoding(false)) { AutoFlush = true };
            if (kept != null) Log(kept);
            seconds = Math.Min(Math.Max(Json.Num(spec, "seconds", 20.0), 1.0), 600.0);
            every = Math.Min(Math.Max(Json.Num(spec, "every", 0.5), 0.1), 1.0);
            shots = (int)Math.Min(Math.Max(Json.Num(spec, "shots", 4.0), 0.0), 64.0);
            scene = Json.Str(spec, "scene");
            sound = Json.Bool(spec, "sound");
            if (Json.Obj(spec, "player") is Dictionary<string, object> select)
            {
                playerSel = Sel.Parse(select, "the play's player select");
                playerSel.Player = false;
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
            StartCoroutine(AfterUpdates());
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

        /// <summary>A fresh start every play: what an earlier play saved (PlayerPrefs, the persistent data folder) is
        /// gone. Only ever in the checker's own build of a scratch copy: its company name is "TaskProbe." and 12 hex
        /// digits, so the registry key and the folder are that build's alone, never a game's own. Anything else (the
        /// package copied into a real project, a real game started with -taskProbe) keeps its saved data: the line
        /// for probe.log saying so, else null.</summary>
        static string ForgetSaves()
        {
            var company = Application.companyName ?? "";
            if (!OwnCompany.IsMatch(company)) return "the saved data is kept: '" + company + "' isn't the company name of the checker's build";
            var folder = Application.persistentDataPath ?? "";
            // <user>/AppData/LocalLow/<company>/<product>; Unity writes the company's dot as an underscore
            var owner = Path.GetFileName(Path.GetDirectoryName(folder.TrimEnd('/', '\\')) ?? "");
            if (owner != company.Replace('.', '_') && owner != company) return "the saved data is kept: " + folder + " isn't this build's own folder";
            PlayerPrefs.DeleteAll();
            try { if (Directory.Exists(folder)) Directory.Delete(folder, true); }
            catch (Exception e) { return "the saved data couldn't be cleared: " + e.Message; }
            return null;
        }

        /// <summary>Real-time pacing: on during a wait and a scene load, and always in a play that measures audio (sound
        /// plays in real time); else the play runs as fast as the machine renders.</summary>
        public void Pace(bool realTime)
        {
            Application.targetFrameRate = realTime || sound ? Fps : -1;
        }

        void LoadQueries()
        {
            var kinds = new Dictionary<string, Type>(StringComparer.Ordinal);
            Type[] types;
            try { types = typeof(Probe).Assembly.GetTypes(); }
            catch (ReflectionTypeLoadException e) { types = e.Types; }
            foreach (var type in types)
            {
                var mark = type?.GetCustomAttribute<ProbeQueryAttribute>();
                if (mark != null && typeof(Query).IsAssignableFrom(type) && !type.IsAbstract) kinds[mark.Kind] = type;
            }
            var file = Json.Obj(spec, "queries");
            if (file == null) return;
            var format = Json.Str(file, "format", "");
            if (format != QueriesFormat) { Error("queries format '" + format + "' is not " + QueriesFormat); return; }
            var asked = Json.Arr(file, "queries");
            if (asked == null) { Error("the queries have no queries array"); return; }
            foreach (var item in asked)
            {
                if (!(item is Dictionary<string, object> def)) { Error("a query is not an object"); continue; }
                var id = Json.Str(def, "id", "");
                if (id.Length == 0 || measures.ContainsKey(id)) { Error("a query has a missing or repeated id '" + id + "'"); continue; }
                if (queries.Count >= MaxQueries) { Error("more than " + MaxQueries + " queries: '" + id + "' and later ones dropped"); break; }
                var kind = Json.Str(def, "kind", "");
                Query q = null;
                if (!kinds.TryGetValue(kind, out var type)) Error("query '" + id + "': unknown kind '" + kind + "' (null values)");
                else
                {
                    try
                    {
                        q = (Query)Activator.CreateInstance(type);
                        Fill(q, id, kind, def);
                        q.Load();
                    }
                    catch (Exception e)
                    {
                        Failed(kind + " " + id + ": {0} in Load (null values)", e);
                        q = null;
                    }
                }
                if (q == null) Fill(q = new NoQuery(), id, kind, def);
                queries.Add(q);
                measures[id] = new List<object>();
            }
        }

        void Fill(Query q, string id, string kind, Dictionary<string, object> def)
        {
            q.Id = id;
            q.Kind = kind;
            q.Def = def;
            q.Probe = this;
            foreach (var field in Json.Strings(def, "fields"))
                if (field.Length > 0 && !q.Fields.Contains(field)) q.Fields.Add(field);
        }

        /// <summary>A query the probe can't run (an unknown kind, a definition its kind can't load): null values.</summary>
        sealed class NoQuery : Query
        {
            public override void Sample(double t, Dictionary<string, object> sample) { sample["value"] = null; }
        }

        // ---------------------------------------------------------------- what queries read

        /// <summary>The probe's own objects are never selected.</summary>
        public static bool IsOwn(GameObject go) => Active != null && go != null && go.transform.root == Active.transform;

        /// <summary>The player object (contract section 1), looked up once a frame; null when the scene has none.</summary>
        public GameObject Player
        {
            get
            {
                if (playerStamp != Stamp)
                {
                    playerStamp = Stamp;
                    player = FindPlayer();
                }
                return player;
            }
        }

        GameObject FindPlayer()
        {
            if (playerSel != null) return Find.First(playerSel);
            var found = new List<GameObject>();
            try { found.AddRange(GameObject.FindGameObjectsWithTag("Player")); }
            catch (UnityException) { }  // the project has no such tag
            foreach (var name in new[] { "PlayerInput", "CharacterController" })
            {
                if (found.Count > 0) break;
                var type = Reflect.TypeNamed(name);
                if (type == null || !typeof(Component).IsAssignableFrom(type)) continue;
                foreach (var o in FindObjectsByType(type, FindObjectsSortMode.None))
                    if (o is Component c) found.Add(c.gameObject);
            }
            if (found.Count > 0)
            {
                Find.SortByHierarchy(found);  // of several, the first in the hierarchy: the same one in every play
                return found[0];
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
            else errorsLeftOut++;
        }

        /// <summary>An exception out of a query or an input: an error that reads the same each time it happens (`what`
        /// with {0} for the exception's type), and the exception with its stack in probe.log.</summary>
        public void Failed(string what, Exception e)
        {
            if (e is TargetInvocationException && e.InnerException != null) e = e.InnerException;
            var message = what.Replace("{0}", e.GetType().Name) + " (the exception is in probe.log)";
            if (errorsSeen.Contains(message)) return;
            Error(message);
            Log(e.ToString());
        }

        /// <summary>A line in the play's probe.log (beside probe.json), not in the game's own log.</summary>
        public static void Log(string message)
        {
            try { logFile?.WriteLine((Active != null ? Active.Elapsed.ToString("F2") : "0.00") + " [" + Time.realtimeSinceStartup.ToString("F1") + " s] " + message); }
            catch { }
        }

        // ---------------------------------------------------------------- the frame, before the game's scripts

        /// <summary>Whether the clock holds this frame for a scene that is still loading. One load holds it for
        /// MaxLoadFrames at most: a load the game parks (allowSceneActivation false, a level kept ready) never
        /// finishes, and the play must.</summary>
        bool Loading()
        {
            var loading = false;
            for (var i = 0; i < SceneManager.sceneCount && !loading; i++) loading = !SceneManager.GetSceneAt(i).isLoaded;
            if (!loading) { loadFrames = 0; return false; }
            if (loadFrames < MaxLoadFrames) { loadFrames++; return true; }
            if (loadFrames++ == MaxLoadFrames)
                Log("a scene has been loading for " + MaxLoadFrames + " frames (a load the game parks never finishes): the play's clock goes on");
            return false;
        }

        void Update()
        {
            Stamp++;
            counted = false;
            if (done)
            {
                // frames go on after the probe asked to quit: the game said no (Application.wantsToQuit)
                if (quitAsked && ++framesAfterQuit > 3) Terminate();
                return;
            }
#if TASKPROBE_AUDIO
            AudioTap.Follow();  // every frame, before the clock starts too: a listener without its tap is heard
#endif
            if (Time.captureFramerate != Fps) Time.captureFramerate = Fps;
            // with vertical sync on, Unity ignores the target frame rate: a play that measures audio would run at the
            // screen's rate instead of 30 frames a second of real time
            if (QualitySettings.vSyncCount != 0) QualitySettings.vSyncCount = 0;
            var loading = Loading();
            if (!started)
            {
                // the play's scene (asked for in Begin) must be the one in play before the clock starts
                if (scene != null && sceneAsked && SceneUtility.GetBuildIndexByScenePath(scene) >= 0
                    && !string.Equals(SceneManager.GetActiveScene().path, scene, StringComparison.OrdinalIgnoreCase))
                {
                    if (startFrames++ < 600) return;
                    Error("the play's scene " + scene + " didn't become the active scene: playing " + SceneManager.GetActiveScene().path);
                }
                if (loading) return;
                started = true;
                Log("the play's clock starts in " + SceneManager.GetActiveScene().path);
            }
            if (inputs.Waiting)
            {
                inputs.WaitTick();
                FrameQueries();
                return;
            }
            if (loading)
            {
                Pace(true);  // let the loader work in real time; the clock holds
                FrameQueries();  // the game runs on meanwhile, as in a wait
                return;
            }
            Pace(false);
            frames++;
            counted = true;
            FrameQueries();
            inputs.Send(Elapsed);
        }

        /// <summary>After every script's Update and before any LateUpdate: a held player goes back to its spot, so a
        /// camera that follows it in LateUpdate stands where it stands for a player at the spot.</summary>
        IEnumerator AfterUpdates()
        {
            while (!done)
            {
                yield return null;
                Stamp++;
                if (started && !done) HoldPlayer();
            }
        }

        void HoldPlayer()
        {
            try { inputs.Hold(Elapsed); }
            catch (Exception e) { Failed("inputs: {0} holding the player", e); }
        }

        void FrameQueries()
        {
            foreach (var q in queries)
            {
                try { q.Frame(1f / Fps); }
                catch (Exception e) { Failed(q.Kind + " " + q.Id + ": {0} in Frame", e); }
            }
        }

        // ---------------------------------------------------------------- the frame, after the game's scripts

        internal void Late()
        {
            Stamp++;
            if (done) return;
#if TASKPROBE_AUDIO
            // after the game's scripts as well: Unity takes up a new listener in the frame's audio update, which comes
            // after LateUpdate, so one that came on in this frame has its tap before it is heard
            AudioTap.Follow();
#endif
            if (!started) return;
            if ((Time.frameCount & 15) == 0)
            {
                if (Screen.fullScreen || Screen.width != Width || Screen.height != Height) Screen.SetResolution(Width, Height, FullScreenMode.Windowed);
                Window.KeepAway();
            }
            var t = Elapsed;
            HoldPlayer();  // after every frame's game logic, the clock running or not: a hold lasts through a wait
            if (!counted) return;  // a frame of a wait or of a scene loading: the clock stands still
            if (t >= nextSample - 1e-9)
            {
                nextSample += every;
                TakeSample(t);
            }
            if (shots > 0 && shotsTaken < shots && t >= seconds * (shotsTaken + 0.5) / shots)
            {
#if TASKPROBE_IMAGECONVERSION
                var name = $"shot_{shotsTaken:D2}.png";
                pendingShots.Add(name);
                shotNames.Add(name);
#else
                Error("screenshots can't be written: the project has no ImageConversion module");
#endif
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
                catch (Exception e) { Failed(q.Kind + " " + q.Id + ": {0} in Sample", e); }
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
                    catch (Exception e) { Failed("the frame couldn't be read: {0}", e); }
                }
#if TASKPROBE_IMAGECONVERSION
                if (frame != null)
                    foreach (var name in pendingShots)
                    {
                        try { File.WriteAllBytes(Path.Combine(outDir, name), frameTexture.EncodeToPNG()); }
                        catch (Exception e) { Failed("a screenshot couldn't be written: {0}", e); }
                    }
#endif
                pendingShots.Clear();
                foreach (var pending in pendingFrames)
                {
                    try { pending.Key.FrameDrawn(frame, pending.Value); }
                    catch (Exception e) { Failed(pending.Key.Kind + " " + pending.Key.Id + ": {0} in FrameDrawn", e); }
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
                frameTexture = new Texture2D(w, h, TextureFormat.RGB24, false);  // no alpha: a screenshot is opaque
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
            if (errors.Count > 0)
            {
                var said = new List<object>(errors);
                if (errorsLeftOut > 0) said.Add(errorsLeftOut + " more in probe.log");
                result["query_errors"] = said;
            }
            try { File.WriteAllText(Path.Combine(outDir, "probe.json"), Json.Write(result), new UTF8Encoding(false)); }
            catch (Exception e) { Log("probe.json couldn't be written: " + e.Message); }
            Log("the play ended: " + reason);
            try { logFile?.Dispose(); } catch { }
            logFile = null;
            if (!quit) return;
            // The play is over and probe.json is written: the process ends, whatever the game does. A game may
            // refuse to quit (Update sees the frames go on) or hang in its shutdown (this thread, after 5 s).
            quitAsked = true;
            new Thread(() =>
            {
                Thread.Sleep(5000);
                Terminate();
            }) { IsBackground = true }.Start();
            Application.Quit(0);
        }

#if UNITY_STANDALONE_WIN && !UNITY_EDITOR
        [DllImport("kernel32.dll")] static extern IntPtr GetCurrentProcess();
        [DllImport("kernel32.dll")] static extern bool TerminateProcess(IntPtr process, uint exitCode);
#endif

        /// <summary>Ends the player's process with exit code 0, as the quit it didn't do would have. Only ever called
        /// after a -taskProbe play has ended and written its files.</summary>
        static void Terminate()
        {
#if UNITY_STANDALONE_WIN && !UNITY_EDITOR
            TerminateProcess(GetCurrentProcess(), 0);
#else
            try { System.Diagnostics.Process.GetCurrentProcess().Kill(); } catch { }
#endif
        }
    }
}
