// The run's clock: QueryPerformanceCounter, read through P/Invoke, the clock the recorder reads too. Not
// Stopwatch.GetTimestamp(): under IL2CPP that is the counter rescaled to 100 ns ticks, the same number only where the
// counter runs at 10 MHz. Safe from any thread.
using System;
using System.Diagnostics;
using System.Globalization;
using System.Runtime.InteropServices;

internal static class AutoPlayClock
{
#if UNITY_STANDALONE_WIN || UNITY_EDITOR_WIN
    [DllImport("kernel32.dll")] static extern bool QueryPerformanceCounter(out long count);
    [DllImport("kernel32.dll")] static extern bool QueryPerformanceFrequency(out long frequency);
#endif

    /// <summary>Counts per second (qpc_frequency).</summary>
    public static readonly long Frequency = ReadFrequency();

    const long UnixEpochTicks = 621355968000000000L;  // 1970-01-01T00:00:00Z

    static long ReadFrequency()
    {
#if UNITY_STANDALONE_WIN || UNITY_EDITOR_WIN
        if (QueryPerformanceFrequency(out var f) && f > 0) return f;
#endif
        return Stopwatch.Frequency;
    }

    public static long Now()
    {
#if UNITY_STANDALONE_WIN || UNITY_EDITOR_WIN
        if (QueryPerformanceCounter(out var count)) return count;
#endif
        return Stopwatch.GetTimestamp();
    }

    /// <summary>qpc * 1e9 / frequency, computed so that it never overflows 64 bits.</summary>
    public static long ToNs(long qpc)
    {
        var f = Frequency;
        return qpc / f * 1_000_000_000L + qpc % f * 1_000_000_000L / f;
    }

    /// <summary>Seconds from one reading to another.</summary>
    public static double Seconds(long from, long to) => (to - from) / (double)Frequency;

    /// <summary>A reading this many seconds from now.</summary>
    public static long After(double seconds) => Now() + (long)(seconds * Frequency);

    /// <summary>A clock.json sample: QPC read before and after the UTC wall clock (ms resolution).</summary>
    public static string Sample(string label, int frame)
    {
        var before = Now();
        var utc = DateTime.UtcNow;
        var after = Now();
        var unixNs = (utc.Ticks - UnixEpochTicks) * 100L;
        return new AutoPlayJson()
            .Add("label", label).Add("qpc", before).Add("qpc_after", after).Add("t_ns", ToNs(before))
            .Add("unix_ns", unixNs).Add("utc", utc.ToString("yyyy-MM-dd'T'HH:mm:ss.fff'Z'", CultureInfo.InvariantCulture))
            .Add("frame", frame).Close();
    }
}
