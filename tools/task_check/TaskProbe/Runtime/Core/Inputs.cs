// A play's scripted inputs (contract section 4), sent at their times: keys, buttons and axes through the Input System
// on the probe's own virtual Keyboard, Mouse and Gamepad (the game's actions read them as they read real devices; the
// real ones deliver nothing to a window without focus), widget clicks, cursor moves, teleports of the player (held
// there for a while when asked) and waits in real time. Each device's whole state is sent with every change, so two
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
                    if (item is Dictionary<string, object> row && Json.TryNum(row, "t", out _)) rows.Add(row);
            rows.Sort((a, b) => Json.Num(a, "t").CompareTo(Json.Num(b, "t")));  // List.Sort isn't stable, so ties keep
            StableByTime();                                                       // their written order below
        }

        void StableByTime()
        {
            // insertion sort by t (rows are few): equal times stay in the order the task wrote them
            for (var i = 1; i < rows.Count; i++)
            {
                var row = rows[i];
                var t = Json.Num(row, "t");
                var j = i - 1;
                while (j >= 0 && Json.Num(rows[j], "t") > t) { rows[j + 1] = rows[j]; j--; }
                rows[j + 1] = row;
            }
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
            catch (Exception e) { probe.Error("inputs: the Input System's devices couldn't be added: " + e.Message); }
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
            while (!Waiting && next < rows.Count && Json.Num(rows[next], "t") <= elapsed + 1e-9)
            {
                var row = rows[next++];
                try { SendOne(row, elapsed); }
                catch (Exception e) { probe.Error("inputs: " + Json.Write(row) + " failed: " + e.Message); }
                Sent++;
            }
        }

        /// <summary>One frame of a wait: true while it goes on. The game runs paced to real time; the wait is over when
        /// its seconds of both real and game time have passed.</summary>
        public bool WaitTick()
        {
            if (!Waiting) return false;
            waitFrames++;
            var game = waitFrames / (double)Probe.Fps;
            var real = Time.realtimeSinceStartup - waitStart;
            if (game >= waitFor && real >= waitFor)
            {
                Waiting = false;
                probe.Pace(false);
                Probe.Log($"the wait is over ({game:F1} s of game time, {real:F1} s of real time)");
                return false;
            }
            return true;
        }

        /// <summary>After the frame's game logic: a held player goes back to its spot, still.</summary>
        public void Late(double elapsed)
        {
            if (elapsed >= holdUntil) return;
            var player = probe.Player;
            if (player == null) return;
            if ((player.transform.position - holdAt).sqrMagnitude > 1e-8f) Place(player, holdAt, null);
            else Still(player);
        }

        void SendOne(Dictionary<string, object> row, double elapsed)
        {
            if (row.TryGetValue("teleport_to", out var target) && target is Dictionary<string, object> select)
            {
                TeleportTo(row, select, elapsed);
                return;
            }
            if (row.TryGetValue("teleport", out var place) && Json.TryVec3(place, out var at))
            {
                var player = probe.Player;
                if (player == null) { Probe.Log("teleport skipped (no player)"); return; }
                Place(player, at, Json.TryNum(row, "yaw", out var yaw) ? (float?)yaw : null);
                Hold(row, player, elapsed);
                return;
            }
            if (Json.TryNum(row, "wait", out var wait))
            {
                Waiting = true;
                waitFor = Math.Min(Math.Max(wait, 0.0), 600.0);
                waitFrames = 0;
                waitStart = Time.realtimeSinceStartup;
                probe.Pace(true);
                Probe.Log($"the play's clock holds at {elapsed:F2} s for {waitFor:F1} s of real time");
                return;
            }
            if (row.TryGetValue("cursor", out var cursor) && Json.TryNumbers(cursor, 2, out var xy))
            {
                Cursor(xy[0], xy[1]);
                return;
            }
            var widget = Json.Str(row, "widget");
            if (widget != null)
            {
                var clicked = Probe.WidgetClick != null && Probe.WidgetClick(widget);
                Probe.Log(clicked ? $"clicked {widget}" : $"no visible button matches '{widget}'");
                return;
            }
            var key = Json.Str(row, "key");
            if (key == null) return;
            if (Json.TryNum(row, "axis", out var axis)) Control(key, (float)axis, true);
            else Control(key, Json.Bool(row, "press", true) ? 1f : 0f, false);
        }

        // ---------------------------------------------------------------- keys, buttons, axes, the cursor

        void Cursor(double fx, double fy)
        {
#if TASKPROBE_INPUTSYSTEM
            if (mouse == null) return;
            pointer.position = new Vector2((float)(fx * Screen.width), (float)((1.0 - fy) * Screen.height));
            QueueMouse();
            Probe.Log($"cursor to ({fx:F3}, {fy:F3}) = pixel ({pointer.position.x:F0}, {pointer.position.y:F0})");
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
            ["leftButton"] = MouseButton.Left, ["press"] = MouseButton.Left, ["rightButton"] = MouseButton.Right,
            ["middleButton"] = MouseButton.Middle, ["forwardButton"] = MouseButton.Forward, ["backButton"] = MouseButton.Back,
        };

        static readonly Dictionary<string, GamepadButton> PadButtons = new Dictionary<string, GamepadButton>(StringComparer.OrdinalIgnoreCase)
        {
            ["buttonSouth"] = GamepadButton.South, ["buttonNorth"] = GamepadButton.North, ["buttonEast"] = GamepadButton.East,
            ["buttonWest"] = GamepadButton.West, ["a"] = GamepadButton.South, ["b"] = GamepadButton.East, ["x"] = GamepadButton.West,
            ["y"] = GamepadButton.North, ["cross"] = GamepadButton.South, ["circle"] = GamepadButton.East,
            ["square"] = GamepadButton.West, ["triangle"] = GamepadButton.North,
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
                else if (control == "position/x") pointer.position = new Vector2(value, pointer.position.y);
                else if (control == "position/y") pointer.position = new Vector2(pointer.position.x, value);
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

        void Hold(Dictionary<string, object> row, GameObject player, double elapsed)
        {
            if (!Json.TryNum(row, "hold", out var hold) || hold <= 0.0) return;
            holdAt = player.transform.position;
            holdUntil = elapsed + Math.Min(hold, 600.0);
            Probe.Log($"holding the player at ({holdAt.x:F2}, {holdAt.y:F2}, {holdAt.z:F2}) for {hold:F1} s");
        }

        void TeleportTo(Dictionary<string, object> row, Dictionary<string, object> select, double elapsed)
        {
            var player = probe.Player;
            if (player == null) { Probe.Log("teleport_to skipped (no player)"); return; }
            var here = player.transform.position;
            GameObject target = null;
            var best = float.MaxValue;
            foreach (var go in Find.Objects(Sel.Parse(select), int.MaxValue, out _))
            {
                if (go == player || go.transform.IsChildOf(player.transform)) continue;
                var d = (go.transform.position - here).sqrMagnitude;
                if (d < best) { best = d; target = go; }
            }
            if (target == null) { Probe.Log("teleport_to skipped (no object matches)"); return; }
            var there = target.transform.position;
            var side = here - there;
            side.y = 0f;
            if (side.sqrMagnitude < 1e-6f) side = -player.transform.forward;
            side.y = 0f;
            side = side.sqrMagnitude < 1e-6f ? Vector3.back : side.normalized;
            var offset = Vector3.zero;
            if (row.TryGetValue("offset", out var o)) Json.TryVec3(o, out offset);
            var spot = there + side * (float)Math.Min(Math.Max(Json.Num(row, "distance", 2.0), 0.0), 1000.0) + offset;
            var face = there;
            if (Json.Obj(row, "face") is Dictionary<string, object> point && Find.Point(point, out var faced)) face = faced;
            var look = face - spot;
            var yaw = Mathf.Atan2(look.x, look.z) * Mathf.Rad2Deg;
            Place(player, spot, yaw);
            var now = player.transform.position;
            Probe.Log($"teleported next to {target.name}: asked ({spot.x:F2}, {spot.y:F2}, {spot.z:F2}) yaw {yaw:F1}, now at ({now.x:F2}, {now.y:F2}, {now.z:F2})");
            Hold(row, player, elapsed);
        }

        /// <summary>The player at `position`, facing `yaw` when given, standing still: through its CharacterController,
        /// NavMeshAgent or Rigidbody when it has one, so the game's own movement doesn't snap it back.</summary>
        public static void Place(GameObject player, Vector3 position, float? yaw)
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
