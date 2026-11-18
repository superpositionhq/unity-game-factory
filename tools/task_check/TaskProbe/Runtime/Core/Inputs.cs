// A play's scripted inputs (contract section 4), sent at their times: keys, buttons and axes through the Input System
// on the probe's own virtual Keyboard, Mouse and Gamepad (the game's actions read them as they read real devices; the
// real ones deliver nothing to a window without focus), widget clicks, cursor moves, teleports of the player (held
// there for a while when asked), waits in real time, named screenshots, scene loads and view turns: one launch can
// visit several places and scenes and picture each. Each device's whole state is sent with every change, so two
// inputs in one frame never undo each other. And touches, as a phone's screen sends them (a tap, a long press, a drag,
// several fingers at once: docs/task-probes.md, section 1.3), through the probe's own virtual Touchscreen: the Input
// System's UI module, its on-screen controls and a game's own touch code read it as they read a phone's.
using System;
using System.Collections.Generic;
using UnityEngine;
#if TASKPROBE_INPUTSYSTEM
using UnityEngine.InputSystem;
using UnityEngine.InputSystem.Controls;
using UnityEngine.InputSystem.LowLevel;
#endif

namespace TaskProbe
{
    public sealed class Inputs
    {
        readonly Probe probe;
        readonly List<Dictionary<string, object>> rows = new List<Dictionary<string, object>>();
        int next;

        Vector3 holdAt;
        double holdUntil = -1.0;

        double waitFor;
        int waitFrames;
        float waitStart;

        public int Sent;
        /// <summary>A wait input holds the play's clock.</summary>
        public bool Waiting { get; private set; }

        /// <summary>The stages of a contact: pins, damage, properties set.</summary>
        public readonly Stages Stages;

        public Inputs(Probe probe, List<object> spec, bool touch = false)
        {
            this.probe = probe;
            Stages = new Stages(probe);
            touchPlay = touch;
            if (spec != null)
                foreach (var item in spec)
                    if (item is Dictionary<string, object> row && Kind(row) != null) rows.Add(row);
            // by time, rows of one time in the order the task wrote them (List.Sort isn't stable; rows are few)
            for (var i = 1; i < rows.Count; i++)
            {
                var row = rows[i];
                var j = i - 1;
                while (j >= 0 && At(rows[j]) > At(row)) { rows[j + 1] = rows[j]; j--; }
                rows[j + 1] = row;
            }
        }

        static double At(Dictionary<string, object> row) => Json.Num(row, "t", 0.0);

        /// <summary>What a row asks for: a widget click, a cursor move, a teleport_to, a teleport, a named shot, a scene
        /// load, a view turn, a wait, a key or an axis, tried in this order; null for a row that is none of them (it is
        /// left out).</summary>
        static string Kind(Dictionary<string, object> row)
        {
            if (Json.Obj(row, "pin") != null) return "pin";
            if (row.ContainsKey("damage") && Json.Obj(row, "to") != null) return "damage";
            if (Json.Str(row, "set") != null && Json.Obj(row, "on") != null) return "set";
            if (row.ContainsKey("tap")) return "tap";
            if (row.ContainsKey("drag")) return "drag";
            if (!string.IsNullOrEmpty(Json.Str(row, "widget")) && Json.Bool(row, "click")) return "click";
            if (row.TryGetValue("cursor", out var cursor) && Json.TryNumbers(cursor, 2, out _)) return "cursor";
            if (Json.Obj(row, "teleport_to") != null) return "teleport_to";
            if (row.TryGetValue("teleport", out var place) && Json.TryNumbers(place, 3, out _)) return "teleport";
            if (Json.Str(row, "shot") != null) return "shot";
            if (Json.Str(row, "scene") != null) return "scene";
            if (row.TryGetValue("view", out var view) && Json.TryNumbers(view, 2, out _)) return "view";
            if (Json.TryNum(row, "wait", out _)) return "wait";
            return Json.Str(row, "key") != null ? "key" : null;
        }

        // ---------------------------------------------------------------- devices

#if TASKPROBE_INPUTSYSTEM
        Keyboard keyboard;
        Mouse mouse;
        Gamepad gamepad;
        KeyboardState keys;
        MouseState pointer;
        GamepadState pad;
        bool padUsed;
        Touchscreen screen;
#endif
        readonly bool touchPlay;  // the play's spec says `touch` (a mobile game's): the touch screen is there from the start

        /// <summary>The virtual devices, added before the game's first frame so its input code sees them from the start.</summary>
        public void Start()
        {
#if TASKPROBE_INPUTSYSTEM
            try
            {
                // input is sent to a window that never has focus
                InputSystem.settings.backgroundBehavior = InputSettings.BackgroundBehavior.IgnoreFocus;
                keyboard = InputSystem.AddDevice<Keyboard>("TaskProbeKeyboard");
                mouse = InputSystem.AddDevice<Mouse>("TaskProbeMouse");
                pointer.position = new Vector2(Screen.width / 2f, Screen.height / 2f);
                InputSystem.QueueStateEvent(mouse, pointer);
                foreach (var row in rows)
                    if (Json.Str(row, "key", "").StartsWith("<Gamepad>", StringComparison.Ordinal)) padUsed = true;
                if (padUsed) gamepad = InputSystem.AddDevice<Gamepad>("TaskProbeGamepad");  // only when asked: a gamepad switches many games' prompts
                var touches = touchPlay;
                foreach (var row in rows)
                    if (row.ContainsKey("tap") || row.ContainsKey("drag")) touches = true;
                // only when asked too: a game may show its touch controls when it finds a touch screen
                if (touches) screen = InputSystem.AddDevice<Touchscreen>("TaskProbeTouchscreen");
                keyboard.MakeCurrent();
                mouse.MakeCurrent();
            }
            catch (Exception e) { probe.Failed("inputs: {0} adding the Input System's devices, so keys, axes and the cursor can't be sent", e); }
#else
            foreach (var row in rows)
                if (row.ContainsKey("key") || row.ContainsKey("cursor") || row.ContainsKey("tap") || row.ContainsKey("drag"))
                {
                    probe.Error("inputs: the project has no Input System package, so keys, axes, the cursor and touches can't be sent");
                    break;
                }
#endif
        }

        // ---------------------------------------------------------------- the play's frames

        /// <summary>Sends every input due at play time `elapsed`; stops at a wait (the inputs after it wait for its end).</summary>
        public void Send(double elapsed)
        {
            MoveTouches(elapsed);  // the fingers already down: the part of each due by now
            while (!Waiting && next < rows.Count && At(rows[next]) <= elapsed + 1e-9)
            {
                var row = rows[next++];
                sending = At(row);
                try { SendOne(row, elapsed); }
                catch (Exception e)
                {
                    probe.Failed("inputs: {0} sending an input", e);
                    var kind = Kind(row);
                    if (kind == "pin" || kind == "damage" || kind == "set") probe.Missed(sending, kind, "stage", "it threw " + e.GetType().Name);
                    Probe.Log("the input was " + Json.Write(row));
                }
                Sent++;
            }
        }

        /// <summary>One frame of a wait. The game runs paced to real time; the wait is over when its seconds of both real
        /// and game time have passed.</summary>
        public void WaitTick()
        {
            waitFrames++;
            var game = waitFrames / (double)Probe.Fps;
            var real = Time.realtimeSinceStartup - waitStart;
            if (game < waitFor || real < waitFor) return;
            Waiting = false;
            probe.Pace(false);
            Probe.Log(FormattableString.Invariant($"the wait is over ({game:F1} s of game time, {real:F1} s of real time)"));
        }

        /// <summary>After the frame's game logic: a held player goes back to its spot, still.</summary>
        public void Hold(double elapsed)
        {
            Stages.Hold(elapsed);
            if (elapsed >= holdUntil) return;
            var player = probe.Player;
            if (player == null) return;
            if ((player.transform.position - holdAt).sqrMagnitude > 1e-6f) Place(player, holdAt, null);
            else Still(player);
        }

        double sending;  // the time of the input being sent

        /// <summary>The input being sent didn't land: a row of probe.json "inputs_missed".</summary>
        void Miss(string kind, string target, string why) => probe.Missed(sending, kind, target, why);

        void SendOne(Dictionary<string, object> row, double elapsed)
        {
            switch (Kind(row))
            {
                case "pin":
                    Stages.Pin(row, elapsed);
                    break;
                case "damage":
                    Stages.Damage(row);
                    break;
                case "set":
                    Stages.Set(row);
                    break;
                case "tap":
                case "drag":
                    StartTouch(row, elapsed);
                    break;
                case "click":
                {
                    var widget = Json.Str(row, "widget");
                    var clicked = UiScan.Click(widget);
                    if (clicked != null) Probe.Log("clicked " + clicked);
                    else if (UiScan.ShownDisabled(widget) is string disabled)
                    {
                        // shown, but a player's click on it does nothing: a miss of its own (a task's click may expect it)
                        Probe.Log($"{disabled} matches '{widget}', shown but disabled: not clicked");
                        Miss("click", widget, "shown but disabled");
                    }
                    else
                    {
                        Probe.Log($"no visible button matches '{widget}'");
                        Miss("click", widget, "no visible button matches it");
                    }
                    break;
                }
                case "cursor":
                    Json.TryNumbers(row["cursor"], 2, out var xy);
                    Cursor(xy[0], xy[1]);
                    break;
                case "teleport_to":
                    TeleportTo(row, Json.Obj(row, "teleport_to"), elapsed);
                    break;
                case "teleport":
                {
                    var player = probe.Player;
                    if (player == null) { Probe.Log("teleport skipped (no player)"); Miss("teleport", "player", "no player"); break; }
                    Json.TryVec3(row["teleport"], out var at);
                    Place(player, at, Json.TryNum(row, "yaw", out var yaw) ? (float?)yaw : null);
                    StartHold(row, player, elapsed);
                    break;
                }
                case "shot":
                    probe.Shot(Json.Str(row, "shot"));
                    break;
                case "scene":
                    probe.LoadScene(Json.Str(row, "scene"));
                    break;
                case "view":
                {
                    // the player turns to the yaw and the main camera to the pitch and yaw, once: a camera rig that sets
                    // its own rotation every frame may turn it back (teleport_to with face places the player instead)
                    Json.TryNumbers(row["view"], 2, out var pitchYaw);
                    var pitch = (float)Math.Min(Math.Max(pitchYaw[0], -89.0), 89.0);
                    var yaw = (float)pitchYaw[1];
                    var player = probe.Player;
                    if (player != null) player.transform.rotation = Quaternion.Euler(player.transform.eulerAngles.x, yaw, player.transform.eulerAngles.z);
                    var cam = Camera.main;
                    if (cam != null) cam.transform.rotation = Quaternion.Euler(pitch, yaw, 0f);
                    Probe.Log(FormattableString.Invariant($"view turned to pitch {pitch:F1} yaw {yaw:F1}") + (cam == null ? " (no main camera)" : ""));
                    break;
                }
                case "wait":
                    Waiting = true;
                    waitFor = Math.Min(Math.Max(Json.Num(row, "wait"), 0.0), 600.0);
                    waitFrames = 0;
                    waitStart = Time.realtimeSinceStartup;
                    probe.Pace(true);
                    Probe.Log(FormattableString.Invariant($"the play's clock holds at {elapsed:F2} s for {waitFor:F1} s of real time"));
                    break;
                case "key":
                    if (Json.TryNum(row, "axis", out var axis)) Control(Json.Str(row, "key"), (float)axis, true);
                    else Control(Json.Str(row, "key"), Json.Bool(row, "press", true) ? 1f : 0f, false);
                    break;
            }
        }

        // ---------------------------------------------------------------- keys, buttons, axes, the cursor

        void Cursor(double fx, double fy)
        {
#if TASKPROBE_INPUTSYSTEM
            if (mouse == null) return;
            fx = Math.Min(Math.Max(fx, 0.0), 1.0);
            fy = Math.Min(Math.Max(fy, 0.0), 1.0);
            pointer.position = new Vector2((float)(fx * Screen.width), (float)((1.0 - fy) * Screen.height));
            QueueMouse();
            Probe.Log(FormattableString.Invariant($"cursor to ({fx:F3}, {fy:F3}) = pixel ({pointer.position.x:F0}, {pointer.position.y:F0})"));
#endif
        }

#if TASKPROBE_INPUTSYSTEM
        void QueueMouse()
        {
            InputSystem.QueueStateEvent(mouse, pointer);
            mouse.MakeCurrent();
            // delta and scroll are impulses: the Input System resets them every frame, and so does the state sent next
            pointer.delta = Vector2.zero;
            pointer.scroll = Vector2.zero;
        }

        static readonly Dictionary<string, MouseButton> MouseButtons = new Dictionary<string, MouseButton>(StringComparer.OrdinalIgnoreCase)
        {
            ["leftButton"] = MouseButton.Left, ["rightButton"] = MouseButton.Right,
            ["middleButton"] = MouseButton.Middle, ["forwardButton"] = MouseButton.Forward, ["backButton"] = MouseButton.Back,
        };

        static readonly Dictionary<string, GamepadButton> PadButtons = new Dictionary<string, GamepadButton>(StringComparer.OrdinalIgnoreCase)
        {
            ["buttonSouth"] = GamepadButton.South, ["buttonNorth"] = GamepadButton.North, ["buttonEast"] = GamepadButton.East,
            ["buttonWest"] = GamepadButton.West,
            ["leftShoulder"] = GamepadButton.LeftShoulder, ["rightShoulder"] = GamepadButton.RightShoulder,
            ["start"] = GamepadButton.Start, ["select"] = GamepadButton.Select,
            ["leftStickPress"] = GamepadButton.LeftStick, ["rightStickPress"] = GamepadButton.RightStick,
            ["dpad/up"] = GamepadButton.DpadUp, ["dpad/down"] = GamepadButton.DpadDown, ["dpad/left"] = GamepadButton.DpadLeft,
            ["dpad/right"] = GamepadButton.DpadRight,
        };
#endif

        /// <summary>A control path's value: a key or button pressed or released, or an axis set.</summary>
        void Control(string path, float value, bool isAxis)
        {
#if TASKPROBE_INPUTSYSTEM
            var slash = path.IndexOf('/');
            if (slash < 0) { probe.Error("inputs: no control " + path); Miss("key", path, "no such control"); return; }
            var device = path.Substring(0, slash);
            var control = path.Substring(slash + 1);
            if (device == "<Keyboard>" && keyboard != null)
            {
                var found = keyboard.TryGetChildControl(control) as KeyControl;
                if (found == null) { probe.Error("inputs: the keyboard has no key " + control); Miss("key", path, "the keyboard has no such key"); return; }
                keys.Set(found.keyCode, value != 0f);
                InputSystem.QueueStateEvent(keyboard, keys);
                keyboard.MakeCurrent();
                return;
            }
            if (device == "<Mouse>" && mouse != null)
            {
                if (MouseButtons.TryGetValue(control, out var button)) pointer = pointer.WithButton(button, value != 0f);
                else if (control == "delta/x") pointer.delta = new Vector2(value, pointer.delta.y);
                else if (control == "delta/y") pointer.delta = new Vector2(pointer.delta.x, value);
                else if (control == "scroll/x") pointer.scroll = new Vector2(value, pointer.scroll.y);
                else if (control == "scroll/y") pointer.scroll = new Vector2(pointer.scroll.x, value);
                else { probe.Error("inputs: the mouse has no control " + control); Miss("key", path, "the mouse has no such control"); return; }
                QueueMouse();
                return;
            }
            if (device == "<Gamepad>" && gamepad != null)
            {
                if (PadButtons.TryGetValue(control, out var button)) pad = pad.WithButton(button, value != 0f);
                else if (control == "leftStick/x") pad.leftStick = new Vector2(value, pad.leftStick.y);
                else if (control == "leftStick/y") pad.leftStick = new Vector2(pad.leftStick.x, value);
                else if (control == "rightStick/x") pad.rightStick = new Vector2(value, pad.rightStick.y);
                else if (control == "rightStick/y") pad.rightStick = new Vector2(pad.rightStick.x, value);
                else if (control == "leftTrigger") pad.leftTrigger = value;
                else if (control == "rightTrigger") pad.rightTrigger = value;
                else { probe.Error("inputs: the gamepad has no control " + control); Miss("key", path, "the gamepad has no such control"); return; }
                InputSystem.QueueStateEvent(gamepad, pad);
                gamepad.MakeCurrent();
                return;
            }
            probe.Error("inputs: no device for " + path);
            Miss("key", path, "no such device");
#else
            Miss("key", path, "the project has no Input System package");
#endif
        }

        // ---------------------------------------------------------------- touches

        /// <summary>A finger on the screen: sent a part each frame of the play's clock until it lifts.</summary>
        sealed class Touching
        {
            public string Kind;  // tap, drag: what a miss is said as
            public int Finger;
            public double Start, Over, Hold;
            public readonly List<Vector2> Points = new List<Vector2>();  // its path in screen pixels, resolved when it went down
            public Vector2 Last;
        }

        readonly List<Touching> touching = new List<Touching>();

        /// <summary>Where a spot is on the screen, in pixels from the bottom left: a viewport point [fx, fy] (fractions,
        /// y down from the top), or {"widget": name}: the centre of the first visible widget of that name (a wildcard)
        /// or type, whatever its kind, as it is laid out now, else the first button that reads so (UiScan.Caption).
        /// False for a widget that isn't on screen.</summary>
        static bool Spot(object spot, out Vector2 at, out string named)
        {
            at = default;
            if (Json.TryNumbers(spot, 2, out var xy))
            {
                var fx = Math.Min(Math.Max(xy[0], 0.0), 1.0);
                var fy = Math.Min(Math.Max(xy[1], 0.0), 1.0);
                named = FormattableString.Invariant($"({fx:F3}, {fy:F3})");
                at = new Vector2((float)(fx * Screen.width), (float)((1.0 - fy) * Screen.height));
                return true;
            }
            named = spot is Dictionary<string, object> o ? Json.Str(o, "widget") : null;
            if (string.IsNullOrEmpty(named)) { named = "(no spot)"; return false; }
            // by name first, any object of a canvas or any element; then by type
            foreach (var byType in new[] { false, true })
                foreach (var w in UiScan.Widgets(byType ? named : null, byType ? null : named, null, true))
                {
                    if (!(w.Field("x") is double x) || !(w.Field("y") is double y) || !(w.Field("w") is double width)
                        || !(w.Field("h") is double height) || width <= 0.0 || height <= 0.0) continue;  // never laid out: nothing a finger could touch
                    at = new Vector2((float)((x + width / 2) * Screen.width), (float)((1.0 - (y + height / 2)) * Screen.height));
                    named = w.Name + " (" + w.Class + ")";
                    return true;
                }
            // then a button by what it reads (one the task itself adds has no name at the start)
            if (UiScan.CaptionSpot(named, out var cx, out var cy, out var cw, out var ch, out var captioned))
            {
                at = new Vector2((float)((cx + cw / 2) * Screen.width), (float)((1.0 - (cy + ch / 2)) * Screen.height));
                named = captioned;
                return true;
            }
            return false;
        }

        /// <summary>A finger goes down: its spots are resolved now, its first part is sent, and MoveTouches sends the
        /// rest. A touch that can't be made (a widget that isn't on screen, a finger still down, no touch screen) is a
        /// miss: one line of the play's query_errors, and nothing is touched.</summary>
        void StartTouch(Dictionary<string, object> row, double elapsed)
        {
            var drag = row.ContainsKey("drag");
            var t = new Touching
            {
                Kind = drag ? "drag" : "tap", Finger = (int)Math.Round(Json.Num(row, "finger", 0.0)), Start = elapsed,
                Over = Math.Min(Math.Max(Json.Num(row, "over", 0.0), 0.0), 120.0), Hold = Math.Min(Math.Max(Json.Num(row, "hold", 0.0), 0.0), 120.0),
            };
            var at = FormattableString.Invariant($"at {Json.Num(row, "t", 0.0):F2} s");
            if (t.Finger < 0 || t.Finger > 9) { probe.Error($"inputs: the {t.Kind} {at} missed: finger {t.Finger} (a finger is 0 to 9)"); Miss(t.Kind, "finger " + t.Finger, "a finger is 0 to 9"); return; }
            var spots = drag ? Json.Arr(row, "drag") : new List<object> { row["tap"] };
            if (spots == null || spots.Count < (drag ? 2 : 1) || spots.Count > 16) { probe.Error($"inputs: the {t.Kind} {at} missed: it names no spots"); Miss(t.Kind, "spots", "it names no spots"); return; }
            foreach (var spot in spots)
            {
                if (!Spot(spot, out var point, out var named))
                {
                    probe.Error($"inputs: the {t.Kind} {at} missed: no visible widget matches '{named}'");
                    Miss(t.Kind, named, "no visible widget matches it");
                    return;
                }
                t.Points.Add(point);
                if (t.Points.Count == 1) Probe.Log($"{t.Kind}: finger {t.Finger} goes down on {named}");
            }
            if (!drag) t.Over = 0.0;
#if TASKPROBE_INPUTSYSTEM
            if (screen == null) { probe.Error($"inputs: the {t.Kind} {at} missed: no touch screen"); Miss(t.Kind, "finger " + t.Finger, "no touch screen"); return; }
            if (touching.Exists(other => other.Finger == t.Finger))
            {
                probe.Error($"inputs: the {t.Kind} {at} missed: finger {t.Finger} is still down from an earlier touch");
                Miss(t.Kind, "finger " + t.Finger, "it is still down from an earlier touch");
                return;
            }
            t.Last = t.Points[0];
            QueueTouch(t, UnityEngine.InputSystem.TouchPhase.Began);
            touching.Add(t);
#endif
        }

        /// <summary>Every finger's part due by play time `elapsed`: a move when its place changed, and its lift once its
        /// path and its hold are over, never in the frame it went down (a tap is a press in one frame and a release in
        /// the next).</summary>
        void MoveTouches(double elapsed)
        {
#if TASKPROBE_INPUTSYSTEM
            for (var i = touching.Count - 1; i >= 0; i--)
            {
                var t = touching[i];
                var since = elapsed - t.Start;
                if (since <= 1e-9) continue;
                var to = t.Points[t.Points.Count - 1];
                if (t.Points.Count > 1 && t.Over > 0.0 && since < t.Over)
                {
                    var along = since / t.Over * (t.Points.Count - 1);
                    var k = Math.Min((int)Math.Floor(along), t.Points.Count - 2);
                    to = Vector2.Lerp(t.Points[k], t.Points[k + 1], (float)(along - k));
                }
                if ((to - t.Last).sqrMagnitude > 1e-4f)
                {
                    t.Last = to;
                    QueueTouch(t, UnityEngine.InputSystem.TouchPhase.Moved);
                }
                if (since < t.Over + t.Hold - 1e-9) continue;
                QueueTouch(t, UnityEngine.InputSystem.TouchPhase.Ended);
                touching.RemoveAt(i);
                Probe.Log(FormattableString.Invariant($"{t.Kind}: finger {t.Finger} lifts at pixel ({t.Last.x:F0}, {t.Last.y:F0}) after {since:F2} s"));
            }
#endif
        }

#if TASKPROBE_INPUTSYSTEM
        void QueueTouch(Touching t, UnityEngine.InputSystem.TouchPhase phase)
        {
            // a touch's id is never 0 (the Touchscreen reads 0 as no touch): finger n is touch n + 1 for the whole play
            InputSystem.QueueStateEvent(screen, new TouchState { touchId = t.Finger + 1, phase = phase, position = t.Last, pressure = 1f });
        }
#endif

        // ---------------------------------------------------------------- teleports

        void StartHold(Dictionary<string, object> row, GameObject player, double elapsed)
        {
            var hold = Math.Min(Math.Max(Json.Num(row, "hold", 0.0), 0.0), 600.0);
            if (hold <= 0.0) return;
            holdAt = player.transform.position;
            holdUntil = elapsed + hold;
            Probe.Log(FormattableString.Invariant($"holding the player at ({holdAt.x:F2}, {holdAt.y:F2}, {holdAt.z:F2}) for {hold:F1} s"));
        }

        void TeleportTo(Dictionary<string, object> row, Dictionary<string, object> select, double elapsed)
        {
            var player = probe.Player;
            if (player == null) { Probe.Log("teleport_to skipped (no player)"); Miss("teleport_to", "player", "no player"); return; }
            var here = player.transform.position;
            GameObject target = null;
            var best = float.MaxValue;
            foreach (var go in Find.Objects(Sel.Parse(select, "inputs: teleport_to"), int.MaxValue, out _))
            {
                if (go == player || go.transform.IsChildOf(player.transform)) continue;
                var d = (go.transform.position - here).sqrMagnitude;
                if (d < best) { best = d; target = go; }
            }
            if (target == null)
            {
                Probe.Log("teleport_to skipped (no object matches)");
                Miss("teleport_to", "select", "no object but the player matches it");
                return;
            }
            var there = target.transform.position;
            var side = here - there;
            side.y = 0f;
            if (side.sqrMagnitude < 1e-6f) side = -target.transform.forward;  // the player is right above it: the side its back is to
            side.y = 0f;
            side = side.sqrMagnitude < 1e-6f ? Vector3.back : side.normalized;
            var offset = Vector3.zero;
            if (row.TryGetValue("offset", out var o)) Json.TryVec3(o, out offset);
            var spot = there + side * (float)Math.Min(Math.Max(Json.Num(row, "distance", 2.0), 0.0), 1000.0) + offset;
            var face = there;
            if (Json.Obj(row, "face") is Dictionary<string, object> point && Find.Point(point, out var faced)) face = faced;
            var look = face - spot;
            // nothing to face within a centimetre on the ground: it keeps its own yaw
            var yaw = look.x * look.x + look.z * look.z > 1e-4f ? Mathf.Atan2(look.x, look.z) * Mathf.Rad2Deg : player.transform.eulerAngles.y;
            Place(player, spot, yaw);
            var now = player.transform.position;
            Probe.Log(FormattableString.Invariant($"teleported next to {target.name}: asked ({spot.x:F2}, {spot.y:F2}, {spot.z:F2}) yaw {yaw:F1}, now at ({now.x:F2}, {now.y:F2}, {now.z:F2})"));
            StartHold(row, player, elapsed);
        }

        /// <summary>The player at `position`, facing `yaw` when given, standing still: through its CharacterController,
        /// NavMeshAgent or Rigidbody when it has one, so the game's own movement doesn't snap it back.</summary>
        internal static void Place(GameObject player, Vector3 position, float? yaw)
        {
            var t = player.transform;
            var rotation = yaw.HasValue ? Quaternion.Euler(t.eulerAngles.x, yaw.Value, t.eulerAngles.z) : t.rotation;
#if TASKPROBE_PHYSICS
            var controller = player.GetComponent<CharacterController>();
            var wasOn = controller != null && controller.enabled;
            if (wasOn) controller.enabled = false;  // a CharacterController ignores a transform set under it
#endif
            var warped = false;
#if TASKPROBE_AI
            var agent = player.GetComponent<UnityEngine.AI.NavMeshAgent>();
            if (agent != null && agent.enabled && agent.isOnNavMesh) warped = agent.Warp(position);
#endif
            if (!warped) t.position = position;
            t.rotation = rotation;
#if TASKPROBE_PHYSICS
            var body = player.GetComponent<Rigidbody>();
            if (body != null)
            {
                body.position = position;
                body.rotation = rotation;
            }
            if (wasOn) controller.enabled = true;
            Physics.SyncTransforms();
#endif
#if TASKPROBE_PHYSICS2D
            var body2 = player.GetComponent<Rigidbody2D>();
            if (body2 != null) body2.position = position;
            Physics2D.SyncTransforms();
#endif
            Still(player);
        }

        internal static void Still(GameObject player)
        {
#if TASKPROBE_PHYSICS
            var body = player.GetComponent<Rigidbody>();
            if (body != null && !body.isKinematic)
            {
                body.linearVelocity = Vector3.zero;
                body.angularVelocity = Vector3.zero;
            }
#endif
#if TASKPROBE_PHYSICS2D
            var body2 = player.GetComponent<Rigidbody2D>();
            if (body2 != null && body2.bodyType == RigidbodyType2D.Dynamic)
            {
                body2.linearVelocity = Vector2.zero;
                body2.angularVelocity = 0f;
            }
#endif
        }
    }
}
