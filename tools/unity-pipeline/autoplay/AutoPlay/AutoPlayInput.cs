// The bot's input: a virtual Keyboard and Mouse of the Input System (and a Gamepad once the bot first uses one: a
// gamepad switches many games' button prompts; in a phone game's run a Touchscreen from the start, the only device its
// bot plays with besides the back button), fed with state events, each device's whole state with every change.
// The game's own InputActions, Keyboard.current and Mouse.current read them exactly as they read real devices; the
// real ones (every device the native backend reports) are disabled for the whole run, so the person using the machine
// never reaches the game. Every change is a row of inputs.jsonl. An input queued in frame f reaches the game at the
// Input System's next update, at the start of frame f + 1.
using System;
using System.Collections.Generic;
using UnityEngine;
#if AUTOPLAY_INPUT_SYSTEM
using UnityEngine.InputSystem;
using UnityEngine.InputSystem.Controls;
using UnityEngine.InputSystem.LowLevel;
#else
#pragma warning disable CS0169, CS0649  // without the Input System package most of this has nothing to do
#endif

internal static class AutoPlayInput
{
    enum Kind { Key, MouseButton, PadButton, Trigger, Stick, Finger }
    const string BackButton = "<Keyboard>/escape";  // what Android's back button is to the Input System

    sealed class Held
    {
        public string Path;
        public Kind Kind;
        public Vector2 Value;
        public int Frame;
#if AUTOPLAY_INPUT_SYSTEM
        public Key Key;
        public MouseButton Mouse;
        public GamepadButton Pad;
        public bool Left;
        public int Finger;
#endif
    }

    static readonly Dictionary<string, Held> held = new Dictionary<string, Held>(StringComparer.Ordinal);
    static readonly List<Held> scratch = new List<Held>();
    static readonly HashSet<string> described = new HashSet<string>(StringComparer.Ordinal);
    static readonly HashSet<string> refused = new HashSet<string>(StringComparer.Ordinal);
    static Vector2 cursor;
    static bool cursorLogged, allowReal;

    /// <summary>inject rows written: outcome.json's inputs_injected.</summary>
    public static long Injected;

    // ------------------------------------------------------------------------------------------- the devices

#if AUTOPLAY_INPUT_SYSTEM
    static Keyboard keyboard;
    static Mouse mouse;
    static Gamepad gamepad;
    static Touchscreen screen;
    static KeyboardState keys;
    static MouseState pointer;
    static GamepadState pad;

    /// <summary>At boot, before the first scene: the virtual devices, and the real ones disabled (unless
    /// -autoplayAllowInput).</summary>
    public static void Boot(bool allowRealInput)
    {
        allowReal = allowRealInput;
        try
        {
            // the window is not focused while it is recorded: the devices keep delivering anyway
            InputSystem.settings.backgroundBehavior = InputSettings.BackgroundBehavior.IgnoreFocus;
            keyboard = InputSystem.AddDevice<Keyboard>("AutoPlayKeyboard");
            mouse = InputSystem.AddDevice<Mouse>("AutoPlayMouse");
            keyboard.MakeCurrent();
            mouse.MakeCurrent();
            // a phone game finds its touch screen from the first frame
            if (AutoPlayRun.IsPhone) screen = InputSystem.AddDevice<Touchscreen>("AutoPlayTouchscreen");
            if (allowReal) return;
            InputSystem.onDeviceChange += OnDeviceChange;
            DisableReal();
        }
        catch (Exception e)
        {
            Debug.LogException(e);
            AutoPlayRun.Error($"the Input System's devices could not be set up ({e.GetType().Name}: {e.Message}): the bot's input reaches nothing");
        }
    }

    /// <summary>Every frame: a real device that came back (plugged in, enabled by someone) is disabled again.</summary>
    public static void Enforce()
    {
        if (!allowReal && keyboard != null) DisableReal();
    }

    static void DisableReal()
    {
        foreach (var device in InputSystem.devices)
            if (device.native && device.enabled) Disable(device);
    }

    static void OnDeviceChange(InputDevice device, InputDeviceChange change)
    {
        if (!device.native || !device.enabled) return;
        if (change == InputDeviceChange.Added || change == InputDeviceChange.Reconnected || change == InputDeviceChange.Enabled)
            Disable(device);
    }

    static void Disable(InputDevice device)
    {
        try { InputSystem.DisableDevice(device); }
        catch (Exception e) { AutoPlayRun.Error($"the real device {device.displayName} could not be disabled: {e.Message}"); }
    }

    /// <summary>The virtual mouse at the window's centre before go (not a row: it is not the bot's input).</summary>
    public static void Center(int width, int height)
    {
        if (mouse == null) return;
        pointer.position = new Vector2(width / 2f, height / 2f);
        cursor = pointer.position;
        QueueMouse();
    }

    static void QueueMouse()
    {
        InputSystem.QueueStateEvent(mouse, pointer);
        mouse.MakeCurrent();
        // delta and scroll are one frame's movement: the Mouse adds up those of a frame's events, then resets them
        pointer.delta = Vector2.zero;
        pointer.scroll = Vector2.zero;
    }

    static readonly Dictionary<string, MouseButton> MouseButtons = new Dictionary<string, MouseButton>(StringComparer.OrdinalIgnoreCase)
    {
        ["leftButton"] = MouseButton.Left, ["rightButton"] = MouseButton.Right, ["middleButton"] = MouseButton.Middle,
        ["forwardButton"] = MouseButton.Forward, ["backButton"] = MouseButton.Back,
    };

    // the gamepad's controls by every name the Input System gives them (its aliases a/cross, b/circle ... included)
    static readonly Dictionary<string, string> PadNames = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase)
    {
        ["buttonSouth"] = "buttonSouth", ["a"] = "buttonSouth", ["cross"] = "buttonSouth",
        ["buttonEast"] = "buttonEast", ["b"] = "buttonEast", ["circle"] = "buttonEast",
        ["buttonWest"] = "buttonWest", ["x"] = "buttonWest", ["square"] = "buttonWest",
        ["buttonNorth"] = "buttonNorth", ["y"] = "buttonNorth", ["triangle"] = "buttonNorth",
        ["leftShoulder"] = "leftShoulder", ["rightShoulder"] = "rightShoulder",
        ["start"] = "start", ["select"] = "select",
        ["leftStickPress"] = "leftStickPress", ["rightStickPress"] = "rightStickPress",
        ["dpad/up"] = "dpad/up", ["dpad/down"] = "dpad/down", ["dpad/left"] = "dpad/left", ["dpad/right"] = "dpad/right",
        ["leftTrigger"] = "leftTrigger", ["rightTrigger"] = "rightTrigger",
        ["leftStick"] = "leftStick", ["rightStick"] = "rightStick",
    };

    static readonly Dictionary<string, GamepadButton> PadButtons = new Dictionary<string, GamepadButton>(StringComparer.Ordinal)
    {
        ["buttonSouth"] = GamepadButton.South, ["buttonEast"] = GamepadButton.East, ["buttonWest"] = GamepadButton.West,
        ["buttonNorth"] = GamepadButton.North, ["leftShoulder"] = GamepadButton.LeftShoulder,
        ["rightShoulder"] = GamepadButton.RightShoulder, ["start"] = GamepadButton.Start, ["select"] = GamepadButton.Select,
        ["leftStickPress"] = GamepadButton.LeftStick, ["rightStickPress"] = GamepadButton.RightStick,
        ["dpad/up"] = GamepadButton.DpadUp, ["dpad/down"] = GamepadButton.DpadDown, ["dpad/left"] = GamepadButton.DpadLeft,
        ["dpad/right"] = GamepadButton.DpadRight,
    };

    /// <summary>A control path read as one of the virtual devices' controls; false (and one error row per path) for
    /// anything else. `twoD`: whether the caller gave a Vector2 (null: either).</summary>
    static bool Resolve(string path, bool? twoD, out Held target, out InputControl control)
    {
        target = null;
        control = null;
        if (keyboard == null) return Refuse(path, "the Input System's devices are not set up");
        if (AutoPlayRun.IsPhone && !string.Equals(path, BackButton, StringComparison.OrdinalIgnoreCase))
            return Refuse(path, "a phone game is played by touch: the bot has Touch, TouchUp and " + BackButton + " (the back button)");
        var slash = path == null ? -1 : path.IndexOf('/');
        if (slash < 3 || path[0] != '<' || path[slash - 1] != '>')
            return Refuse(path, "a control is <Keyboard>/<key>, <Mouse>/<button> or <Gamepad>/<control>");
        var device = path.Substring(1, slash - 2);
        var rest = path.Substring(slash + 1);
        if (device.Equals("Keyboard", StringComparison.OrdinalIgnoreCase))
        {
            if (keyboard.TryGetChildControl(rest) is KeyControl key)
            {
                target = new Held { Path = "<Keyboard>/" + key.name, Kind = Kind.Key, Key = key.keyCode };
                control = key;
            }
            else return Refuse(path, "the keyboard has no key " + rest);
        }
        else if (device.Equals("Mouse", StringComparison.OrdinalIgnoreCase))
        {
            if (!MouseButtons.TryGetValue(rest, out var button))
                return Refuse(path, rest.StartsWith("position", StringComparison.OrdinalIgnoreCase) ? "the cursor moves with SetCursor"
                    : rest.StartsWith("delta", StringComparison.OrdinalIgnoreCase) ? "the mouse moves with MouseDelta"
                    : rest.StartsWith("scroll", StringComparison.OrdinalIgnoreCase) ? "the wheel turns with Scroll"
                    : "the mouse has no button " + rest);
            control = mouse.TryGetChildControl(rest);
            target = new Held { Path = "<Mouse>/" + (control != null ? control.name : rest), Kind = Kind.MouseButton, Mouse = button };
        }
        else if (device.Equals("Gamepad", StringComparison.OrdinalIgnoreCase))
        {
            if (!PadNames.TryGetValue(rest, out var name)) return Refuse(path, "the gamepad has no control " + rest);
            if (gamepad == null)
            {
                gamepad = InputSystem.AddDevice<Gamepad>("AutoPlayGamepad");
                gamepad.MakeCurrent();
            }
            control = gamepad.TryGetChildControl(name);
            target = new Held { Path = "<Gamepad>/" + name };
            if (PadButtons.TryGetValue(name, out var button)) { target.Kind = Kind.PadButton; target.Pad = button; }
            else if (name.EndsWith("Trigger", StringComparison.Ordinal)) { target.Kind = Kind.Trigger; target.Left = name == "leftTrigger"; }
            else { target.Kind = Kind.Stick; target.Left = name == "leftStick"; }
        }
        else return Refuse(path, "no device " + device + ": the bot has <Keyboard>, <Mouse> and <Gamepad>");
        if (twoD == false && target.Kind == Kind.Stick) return Refuse(path, target.Path + " takes a Vector2");
        if (twoD == true && target.Kind != Kind.Stick) return Refuse(path, target.Path + " takes a number");
        return true;
    }

    /// <summary>Sets a control's state and queues the device's whole state.</summary>
    static void Apply(Held c, Vector2 value)
    {
        var on = value != Vector2.zero;
        switch (c.Kind)
        {
            case Kind.Key:
                keys.Set(c.Key, on);
                InputSystem.QueueStateEvent(keyboard, keys);
                keyboard.MakeCurrent();
                return;
            case Kind.MouseButton:
                pointer = pointer.WithButton(c.Mouse, on);
                QueueMouse();
                return;
            case Kind.PadButton:
                pad = pad.WithButton(c.Pad, on);
                break;
            case Kind.Trigger:
                if (c.Left) pad.leftTrigger = Mathf.Clamp01(value.x);
                else pad.rightTrigger = Mathf.Clamp01(value.x);
                break;
            case Kind.Stick:
                if (c.Left) pad.leftStick = value;
                else pad.rightStick = value;
                break;
            case Kind.Finger:
                return;  // a finger's events are queued where it moves (QueueFinger)
        }
        InputSystem.QueueStateEvent(gamepad, pad);
        gamepad.MakeCurrent();
    }

    /// <summary>The first time the bot uses a control: a control_info row with the game's enabled InputActions bound to
    /// it ("Map/Action").</summary>
    static void Describe(string path, InputControl control)
    {
        if (!described.Add(path)) return;
        var actions = new List<string>();
        if (control != null)
        {
            try
            {
                foreach (var action in InputSystem.ListEnabledActions())
                    foreach (var bound in action.controls)
                        if (Related(bound, control))
                        {
                            actions.Add(action.actionMap != null ? action.actionMap.name + "/" + action.name : action.name);
                            break;
                        }
            }
            catch (Exception) { /* the row says what was found */ }
        }
        AutoPlayRun.InputRow(AutoPlayRun.Stamp().Add("type", "control_info").Add("key", path).AddValue("actions", actions));
    }

    static bool Related(InputControl a, InputControl b)
    {
        for (var x = a; x != null; x = x.parent) if (x == b) return true;
        for (var x = b; x != null; x = x.parent) if (x == a) return true;
        return false;
    }
#else
    public static void Boot(bool allowRealInput)
    {
        allowReal = allowRealInput;
        AutoPlayRun.Error("the project has no Input System package: the bot's input reaches nothing");
    }

    public static void Enforce() { }
    public static void Center(int width, int height) { }
#endif

    static bool Refuse(string path, string why)
    {
        if (refused.Add(path ?? "")) AutoPlayRun.Error($"input {path}: {why}");
        return false;
    }

    // ------------------------------------------------------------------------------------------- the bot's calls

    static object Logged(Held c, Vector2 value)
    {
        switch (c.Kind)
        {
            case Kind.Stick: return value;
            case Kind.Finger: return value;
            case Kind.Trigger: return Mathf.Clamp01(value.x);
            default: return value != Vector2.zero ? 1 : 0;
        }
    }

    static void Row(string type, Held c, Vector2 value, string edge)
    {
        var row = AutoPlayRun.Stamp().Add("type", type).Add("key", c.Path).AddValue("value", Logged(c, value)).Add("edge", edge);
        AutoPlayRun.InputRow(row);
        if (type == "inject") Injected++;
    }

    public static void Hold(string control, Vector2 value, bool twoD)
    {
#if AUTOPLAY_INPUT_SYSTEM
        if (!AutoPlayRun.IsRunning) return;
        if (!Resolve(control, twoD, out var target, out var c)) return;
        if (target.Kind != Kind.Stick && value.x == 0f) value = Vector2.zero;
        if (value == Vector2.zero)
        {
            Release(target.Path);
            return;
        }
        held.TryGetValue(target.Path, out var h);
        if (h != null && h.Value == value) return;  // as it is: the frame's hold row says so
        try { Apply(target, value); }
        catch (Exception e)
        {
            AutoPlayRun.Error($"input {target.Path}: {e.GetType().Name}: {e.Message}");
            return;
        }
        Describe(target.Path, c);
        var edge = h == null ? "down" : "hold";
        if (h == null) held[target.Path] = h = target;
        h.Value = value;
        h.Frame = Time.frameCount;
        Row("inject", h, value, edge);
#endif
    }

    public static void Release(string control)
    {
#if AUTOPLAY_INPUT_SYSTEM
        if (!AutoPlayRun.IsRunning || control == null) return;
        if (!held.TryGetValue(control, out var h))
        {
            // the bot may name it another way ("<keyboard>/W"): read it as a control first
            if (!Resolve(control, null, out var target, out _) || !held.TryGetValue(target.Path, out h)) return;
        }
        if (h.Kind == Kind.Finger) { TouchUp(h.Finger); return; }
        held.Remove(h.Path);
        try { Apply(h, Vector2.zero); }
        catch (Exception e) { AutoPlayRun.Error($"input {h.Path}: {e.GetType().Name}: {e.Message}"); }
        Row("inject", h, Vector2.zero, "up");
#endif
    }

    /// <summary>Every held control let go: inject rows ("up") from the bot, release rows at the run's end.</summary>
    public static void ReleaseAll(bool atEnd)
    {
#if AUTOPLAY_INPUT_SYSTEM
        if (held.Count == 0) return;
        if (!atEnd && !AutoPlayRun.IsRunning) return;
        scratch.Clear();
        scratch.AddRange(held.Values);
        held.Clear();
        foreach (var h in scratch)
        {
            if (h.Kind == Kind.Finger)
            {
                try { QueueFinger(h, UnityEngine.InputSystem.TouchPhase.Ended); }
                catch (Exception e) { AutoPlayRun.Error($"input {h.Path}: {e.GetType().Name}: {e.Message}"); }
                AutoPlayRun.InputRow(AutoPlayRun.Stamp().Add("type", atEnd ? "release" : "inject").Add("key", h.Path).Add("value", h.Value).Add("edge", "up"));
                if (!atEnd) Injected++;
                continue;
            }
            try { Apply(h, Vector2.zero); }
            catch (Exception e) { AutoPlayRun.Error($"input {h.Path}: {e.GetType().Name}: {e.Message}"); }
            Row(atEnd ? "release" : "inject", h, Vector2.zero, "up");
        }
        scratch.Clear();
#endif
    }

    // ------------------------------------------------------------------------------------------- fingers

    public static void Touch(int finger, Vector2 position)
    {
#if AUTOPLAY_INPUT_SYSTEM
        if (!AutoPlayRun.IsRunning) return;
        var path = "<Touchscreen>/touch" + finger;
        if (finger < 0 || finger > 9) { Refuse(path, "a finger is 0 to 9"); return; }
        if (keyboard == null) { Refuse(path, "the Input System's devices are not set up"); return; }
        try
        {
            // a game that is no phone game may be touched too: its touch screen comes with the first touch
            if (screen == null) screen = InputSystem.AddDevice<Touchscreen>("AutoPlayTouchscreen");
            held.TryGetValue(path, out var h);
            if (h != null && (h.Value - position).sqrMagnitude < 1e-4f) return;  // where it is: the frame's hold row says so
            var down = h == null;
            if (down) held[path] = h = new Held { Path = path, Kind = Kind.Finger, Finger = finger };
            h.Value = position;
            h.Frame = Time.frameCount;
            QueueFinger(h, down ? UnityEngine.InputSystem.TouchPhase.Began : UnityEngine.InputSystem.TouchPhase.Moved);
            Describe(path, screen.touches[finger]);
            AutoPlayRun.InputRow(AutoPlayRun.Stamp().Add("type", "inject").Add("key", path).Add("value", position).Add("edge", down ? "down" : "move"));
            Injected++;
        }
        catch (Exception e) { AutoPlayRun.Error($"input {path}: {e.GetType().Name}: {e.Message}"); }
#endif
    }

    public static void TouchUp(int finger)
    {
#if AUTOPLAY_INPUT_SYSTEM
        var path = "<Touchscreen>/touch" + finger;
        if (!AutoPlayRun.IsRunning || !held.TryGetValue(path, out var h)) return;
        held.Remove(path);
        try { QueueFinger(h, UnityEngine.InputSystem.TouchPhase.Ended); }
        catch (Exception e) { AutoPlayRun.Error($"input {path}: {e.GetType().Name}: {e.Message}"); }
        AutoPlayRun.InputRow(AutoPlayRun.Stamp().Add("type", "inject").Add("key", path).Add("value", h.Value).Add("edge", "up"));
        Injected++;
#endif
    }

#if AUTOPLAY_INPUT_SYSTEM
    static void QueueFinger(Held h, UnityEngine.InputSystem.TouchPhase phase)
    {
        // a touch's id is never 0 (the Touchscreen reads 0 as no touch): finger n is touch n + 1 for the whole run
        InputSystem.QueueStateEvent(screen, new TouchState { touchId = h.Finger + 1, phase = phase, position = h.Value, pressure = 1f });
    }

    /// <summary>A phone has no mouse: said once per call name.</summary>
    static bool PhoneRefuses(string path) =>
        AutoPlayRun.IsPhone && !Refuse(path, "a phone game is played by touch: the bot has Touch, TouchUp and " + BackButton + " (the back button)");
#endif

    public static void MouseDelta(Vector2 delta)
    {
#if AUTOPLAY_INPUT_SYSTEM
        if (AutoPlayRun.IsRunning && PhoneRefuses("<Mouse>/delta")) return;
        if (!AutoPlayRun.IsRunning || mouse == null || delta == Vector2.zero) return;
        pointer.delta = delta;
        Impulse("<Mouse>/delta", mouse.delta, delta);
#endif
    }

    public static void Scroll(Vector2 scroll)
    {
#if AUTOPLAY_INPUT_SYSTEM
        if (AutoPlayRun.IsRunning && PhoneRefuses("<Mouse>/scroll")) return;
        if (!AutoPlayRun.IsRunning || mouse == null || scroll == Vector2.zero) return;
        pointer.scroll = scroll;
        Impulse("<Mouse>/scroll", mouse.scroll, scroll);
#endif
    }

#if AUTOPLAY_INPUT_SYSTEM
    static void Impulse(string path, InputControl control, Vector2 value)
    {
        try { QueueMouse(); }
        catch (Exception e)
        {
            AutoPlayRun.Error($"input {path}: {e.GetType().Name}: {e.Message}");
            return;
        }
        Describe(path, control);
        AutoPlayRun.InputRow(AutoPlayRun.Stamp().Add("type", "inject").Add("key", path).Add("value", value).Add("edge", "impulse"));
        Injected++;
    }
#endif

    public static void SetCursor(Vector2 position)
    {
#if AUTOPLAY_INPUT_SYSTEM
        if (AutoPlayRun.IsRunning && PhoneRefuses("<Mouse>/position")) return;
        if (!AutoPlayRun.IsRunning || mouse == null) return;
        if (cursorLogged && (position - cursor).sqrMagnitude < 1e-4f) return;
        pointer.position = position;
        try { QueueMouse(); }
        catch (Exception e)
        {
            AutoPlayRun.Error($"input <Mouse>/position: {e.GetType().Name}: {e.Message}");
            return;
        }
        cursor = position;
        cursorLogged = true;
        AutoPlayRun.InputRow(AutoPlayRun.Stamp().Add("type", "cursor").Add("key", "<Mouse>/position").Add("value", position));
#endif
    }

    /// <summary>The end of every frame of the run: a hold row for each control held through it.</summary>
    public static void LateUpdate()
    {
        if (held.Count == 0 || !AutoPlayRun.IsRunning) return;
        var frame = Time.frameCount;
        foreach (var h in held.Values)
        {
            if (h.Frame >= frame) continue;
            h.Frame = frame;
            Row("inject", h, h.Value, "hold");
        }
    }
}
