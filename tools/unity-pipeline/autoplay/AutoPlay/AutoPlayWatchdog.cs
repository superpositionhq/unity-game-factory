// The exit watchdog: ends a player that hangs, so a hang in gameplay or in the engine's shutdown cannot hold the GPU
// until its caller's own timeout, whoever started it (the recorder, a hand test). A background thread, independent of
// the main thread and of the shutdown: at the deadline it writes watchdog.json (prepared when armed) and ends the
// process with exit code 124. Deadlines only move earlier; once the run has ended, the reason is "shutdown".
using System;
using System.IO;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading;

internal static class AutoPlayWatchdog
{
    public const int ExitCode = 124;

    static readonly object Gate = new object();
    static long deadline;  // QPC; 0 = not armed
    static string notePath;
    static byte[] note;
    static Thread thread;

#if UNITY_STANDALONE_WIN && !UNITY_EDITOR
    [DllImport("kernel32.dll")] static extern IntPtr GetCurrentProcess();
    [DllImport("kernel32.dll")] static extern bool TerminateProcess(IntPtr process, uint exitCode);
#endif

    /// <summary>End the process `seconds` from now unless it is gone by then; `reason` "run" (a hang in gameplay) or
    /// "shutdown" (a hang after run_end).</summary>
    public static void Arm(double seconds, string reason, string path)
    {
        var now = AutoPlayClock.Now();
        var at = now + (long)(seconds * AutoPlayClock.Frequency);
        lock (Gate)
        {
            if (deadline != 0 && deadline <= at)
            {
                // an earlier deadline stays; after the run's end a hang is one of the shutdown
                if (reason == "shutdown") note = Note(reason, now, AutoPlayClock.Seconds(now, deadline));
                return;
            }
            deadline = at;
            notePath = path;
            note = Note(reason, now, seconds);
            if (thread != null) return;
            thread = new Thread(Loop) { IsBackground = true, Name = "AutoPlay watchdog" };
            thread.Start();
        }
    }

    static byte[] Note(string reason, long now, double seconds) => new UTF8Encoding(false).GetBytes(new AutoPlayJson()
        .Add("schema", "autoplay-watchdog/1").Add("reason", reason).Add("armed_t_ns", AutoPlayClock.ToNs(now))
        .Add("after_s", Math.Round(seconds, 3)).Add("exit_code", ExitCode).Close() + "\n");

    static void Loop()
    {
        for (;;)
        {
            Thread.Sleep(250);
            string path;
            byte[] text;
            lock (Gate)
            {
                if (deadline == 0 || AutoPlayClock.Now() < deadline) continue;
                path = notePath;
                text = note;
            }
            try { File.WriteAllBytes(path, text); }
            catch (Exception) { /* the exit matters more than the note */ }
            EndProcess(ExitCode);
            return;
        }
    }

    /// <summary>Ends the process at once with `code`, without the engine's shutdown.</summary>
    public static void EndProcess(int code)
    {
#if UNITY_STANDALONE_WIN && !UNITY_EDITOR
        TerminateProcess(GetCurrentProcess(), (uint)code);
#else
        Environment.Exit(code);
#endif
    }
}
