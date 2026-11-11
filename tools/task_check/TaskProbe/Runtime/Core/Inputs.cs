// A play's scripted inputs (contract section 4), sent at their times: keys, buttons and axes through the Input System
// on the probe's own virtual Keyboard, Mouse and Gamepad (the game's actions read them as they read real devices; the
// real ones deliver nothing to a window without focus), widget clicks, cursor moves, teleports of the player (held
// there for a while when asked), waits in real time, named screenshots, scene loads and view turns: one launch can
// visit several places and scenes and picture each. Each device's whole state is sent with every change, so two
// inputs in one frame never undo each other.
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

        public Inputs(Probe probe, List<object> spec)
        {
            this.probe = probe;
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
#endif

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
                keyboard.MakeCurrent();
                mouse.MakeCurrent();
            }
            catch (Exception e) { probe.Failed("inputs: {0} adding the Input System's devices, so keys, axes and the cursor can't be sent", e); }
#else
            foreach (var row in rows)
                if (row.ContainsKey("key") || row.ContainsKey("cursor"))
                {
                    probe.Error("inputs: the project has no Input System package, so keys, axes and the cursor can't be sent");
                    break;
                }
#endif
        }

        // ---------------------------------------------------------------- the play's frames

        /// <summary>Sends every input due at play time `elapsed`; stops at a wait (the inputs after it wait for its end).</summary>
        public void Send(double elapsed)
        {
            while (!Waiting && next < rows.Count && At(rows[next]) <= elapsed + 1e-9)
            {
                var row = rows[next++];
                try { SendOne(row, elapsed); }
                catch (Exception e)
                {
                    probe.Failed("inputs: {0} sending an input", e);
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
            if (elapsed >= holdUntil) return;
            var player = probe.Player;
            if (player == null) return;
            if ((player.transform.position - holdAt).sqrMagnitude > 1e-6f) Place(player, holdAt, null);
            else Still(player);
        }

        void SendOne(Dictionary<string, object> row, double elapsed)
        {
            switch (Kind(row))
            {
                case "click":
                {
                    var widget = Json.Str(row, "widget");
                    var clicked = UiScan.Click(widget);
                    Probe.Log(clicked != null ? "clicked " + clicked : $"no visible button matches '{widget}'");
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
                    if (player == null) { Probe.Log("teleport skipped (no player)"); break; }
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
            if (slash < 0) { probe.Error("inputs: no control " + path); return; }
            var device = path.Substring(0, slash);
            var control = path.Substring(slash + 1);
            if (device == "<Keyboard>" && keyboard != null)
            {
                var found = keyboard.TryGetChildControl(control) as KeyControl;
                if (found == null) { probe.Error("inputs: the keyboard has no key " + control); return; }
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
                else { probe.Error("inputs: the mouse has no control " + control); return; }
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
                else { probe.Error("inputs: the gamepad has no control " + control); return; }
                InputSystem.QueueStateEvent(gamepad, pad);
                gamepad.MakeCurrent();
                return;
            }
            probe.Error("inputs: no device for " + path);
#endif
        }

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
            if (player == null) { Probe.Log("teleport_to skipped (no player)"); return; }
            var here = player.transform.position;
            GameObject target = null;
            var best = float.MaxValue;
            foreach (var go in Find.Objects(Sel.Parse(select, "inputs: teleport_to"), int.MaxValue, out _))
            {
                if (go == player || go.transform.IsChildOf(player.transform)) continue;
                var d = (go.transform.position - here).sqrMagnitude;
                if (d < best) { best = d; target = go; }
            }
            if (target == null) { Probe.Log("teleport_to skipped (no object matches)"); return; }
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
        static void Place(GameObject player, Vector3 position, float? yaw)
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

        static void Still(GameObject player)
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
