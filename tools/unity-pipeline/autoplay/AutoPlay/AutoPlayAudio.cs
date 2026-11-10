// The game's sound from go until the result hold ends: audio.wav (16-bit PCM at the output's sample rate and channel
// count) and audio_clock.jsonl (one row per audio buffer, in WAV order). A filter on the AudioListener's object
// (AutoPlayAudioTap) receives the final mix on the audio thread; each buffer is stamped with QPC when it arrives. A
// buffer that arrives later than the wall clock allows (more than max(2048, 2 buffers) frames behind) has the missing
// time written as silence first, so a WAV position is the time since the first buffer. The listener usually changes
// with the scene (it sits on the camera): the tap follows it to the new one, and the frames in between become silence
// the same way. The main thread writes what the audio thread produced, every frame.
using System;
using System.Collections.Generic;
using System.IO;
using System.Text;
#if AUTOPLAY_AUDIO
using UnityEngine;
#else
#pragma warning disable CS0169, CS0649  // without the Audio module there is no tap: the files stay empty
#endif

internal static class AutoPlayAudio
{
    struct Row
    {
        public long Frame, Qpc, Silence;
        public int Frames, Channels, Rate;
        public double Clock;
    }

    static readonly object Gate = new object();
    static volatile bool armed;          // capturing: from go to the end of the result hold
    static volatile int currentTap;      // the one tap whose buffers count
    internal static volatile bool Mute;  // -autoplayMute: the speakers get silence, the WAV the sound

    // written by the audio thread under Gate
    static int outChannels, outRate;
    static long startQpc, written, silenceFrames;
    static int gaps;
    static short[] pending = new short[1 << 15];
    static int pendingCount;
    static List<Row> rows = new List<Row>(64);
    static volatile bool dspTimeFails;

    // the main thread's
    static int rateHint;
    static short[] spare = new short[1 << 15];
    static List<Row> spareRows = new List<Row>(64);
    static byte[] bytes = new byte[1 << 16];
    static readonly byte[] Zeros = new byte[1 << 16];
    static FileStream wav;
    static StreamWriter clockFile;
    static long dataBytes;

    public static long Frames { get { lock (Gate) return written; } }
    public static long SilenceFrames { get { lock (Gate) return silenceFrames; } }
    public static int Gaps { get { lock (Gate) return gaps; } }

    /// <summary>Opens audio.wav and audio_clock.jsonl in `dir` and starts capturing: null, or why it could not.</summary>
    public static string Start(string dir)
    {
        try
        {
            wav = new FileStream(Path.Combine(dir, "audio.wav"), FileMode.Create, FileAccess.ReadWrite, FileShare.Read);
            wav.Write(Zeros, 0, 44);  // the header once the format is known
            clockFile = new StreamWriter(new FileStream(Path.Combine(dir, "audio_clock.jsonl"), FileMode.Create,
                FileAccess.Write, FileShare.Read), new UTF8Encoding(false)) { NewLine = "\n" };
        }
        catch (Exception e)
        {
            Close();
            return e.Message;
        }
#if AUTOPLAY_AUDIO
        rateHint = AudioSettings.outputSampleRate;
        Follow();
#else
        AutoPlayRun.Error("the project has no Audio module: audio.wav stays empty");
#endif
        lock (Gate)
        {
            outChannels = outRate = gaps = pendingCount = 0;
            startQpc = written = silenceFrames = 0;
            rows.Clear();
        }
        dataBytes = 0;
        armed = true;
        return null;
    }

    /// <summary>Ends the capture: the rest written, the WAV header patched, both files closed.</summary>
    public static void Stop()
    {
        armed = false;
        lock (Gate) { }  // a buffer being stored on the audio thread is stored before the last write
        Flush(true);
        Close();
    }

    static void Close()
    {
        try { wav?.Dispose(); } catch (Exception) { }
        try { clockFile?.Dispose(); } catch (Exception) { }
        wav = null;
        clockFile = null;
    }

#if AUTOPLAY_AUDIO
    static AudioListener listener;
    static AutoPlayAudioTap tap;
    static int nextTapId;
    static long nextSearch;
    static readonly List<AudioListener> found = new List<AudioListener>();

    /// <summary>Every frame of an AutoPlay run: one tap, on the listener the player hears through. A listener that went
    /// (its scene unloaded) or was switched off is replaced by the first enabled one on an active object.</summary>
    public static void Follow()
    {
        if (listener != null && listener.isActiveAndEnabled && tap != null && tap.Id == currentTap) return;
        if (listener == null || !listener.isActiveAndEnabled)
        {
            var now = AutoPlayClock.Now();
            if (now < nextSearch) return;
            nextSearch = now + AutoPlayClock.Frequency / 10;  // 10 searches a second while there is none
            listener = null;
            found.Clear();
            foreach (var l in UnityEngine.Object.FindObjectsByType<AudioListener>(FindObjectsInactive.Exclude, FindObjectsSortMode.None))
                if (l.isActiveAndEnabled) found.Add(l);
            if (found.Count > 0) listener = found[0];
            found.Clear();
            if (listener == null)
            {
                currentTap = 0;
                tap = null;
                return;
            }
        }
        tap = listener.GetComponent<AutoPlayAudioTap>();
        if (tap == null)
        {
            tap = listener.gameObject.AddComponent<AutoPlayAudioTap>();
            // the game's own searches (FindObjectsByType) leave out what is not saved
            tap.hideFlags = HideFlags.HideInInspector | HideFlags.DontSave;
        }
        tap.Id = ++nextTapId;
        currentTap = tap.Id;
    }
#else
    public static void Follow() { }
#endif

    // ----------------------------------------------------------------------------------------- the audio thread

    public static void OnBuffer(int tapId, float[] data, int channels)
    {
        var now = AutoPlayClock.Now();
        if (data == null || channels <= 0) return;
        if (armed && tapId == currentTap) Store(now, data, channels);
        if (Mute) Array.Clear(data, 0, data.Length);
    }

    static void Store(long now, float[] data, int channels)
    {
        var frames = data.Length / channels;
        if (frames <= 0) return;
        double clock = -1.0;
#if AUTOPLAY_AUDIO
        if (!dspTimeFails)
        {
            try { clock = AudioSettings.dspTime; }
            catch (Exception) { dspTimeFails = true; }
        }
#endif
        lock (Gate)
        {
            if (!armed) return;
            var f = (double)AutoPlayClock.Frequency;
            if (outChannels == 0)
            {
                outChannels = channels;
                outRate = rateHint > 0 ? rateHint : 48000;
                startQpc = now - (long)(frames / (double)outRate * f);  // frame 0 = the start of the first buffer
            }
            // where this buffer ends on the wall clock, against where the WAV would put it
            var expectedEnd = (long)((now - startQpc) / f * outRate);
            var late = expectedEnd - (written + frames);
            var tolerance = Math.Max(2048L, 2L * frames);
            long silence = 0;
            if (late > tolerance)
            {
                silence = late;
                written += silence;
                silenceFrames += silence;
                gaps++;
            }
            rows.Add(new Row
            {
                Frame = written, Frames = frames, Qpc = now - (long)(frames / (double)outRate * f), Silence = silence,
                Clock = clock, Channels = channels, Rate = outRate,
            });
            var need = pendingCount + frames * outChannels;
            if (need > pending.Length)
            {
                var bigger = new short[Math.Max(need, pending.Length * 2)];
                Array.Copy(pending, bigger, pendingCount);
                pending = bigger;
            }
            for (var i = 0; i < frames; i++)
            {
                var at = i * channels;
                for (var c = 0; c < outChannels; c++)
                {
                    // a device change can change the channel count: keep the first layout
                    var s = data[at + Math.Min(c, channels - 1)];
                    var v = float.IsNaN(s) ? 0 : (int)Math.Round(s * 32767.0);
                    pending[pendingCount++] = (short)(v > 32767 ? 32767 : v < -32768 ? -32768 : v);
                }
            }
            written += frames;
        }
    }

    // ----------------------------------------------------------------------------------------- the main thread

    /// <summary>Writes what the audio thread stored since the last call, every frame: the samples, the WAV header
    /// (patched to the new length), then the buffers' clock rows, so a player that crashes or hangs leaves a readable
    /// WAV whose rows never describe more than it holds. `patch`: write the header even with nothing new.</summary>
    public static void Flush(bool patch = false)
    {
        if (wav == null) return;
        List<Row> outRows;
        short[] outSamples;
        int outCount, channels, rate;
        lock (Gate)
        {
            outRows = rows;
            rows = spareRows;
            outSamples = pending;
            pending = spare;
            outCount = pendingCount;
            pendingCount = 0;
            channels = outChannels;
            rate = outRate;
        }
        try
        {
            if (outRows.Count == 0 && !patch) return;
            var at = 0;
            foreach (var r in outRows)
            {
                for (var z = r.Silence * channels * 2L; z > 0;)
                {
                    var n = (int)Math.Min(z, Zeros.Length);
                    wav.Write(Zeros, 0, n);
                    dataBytes += n;
                    z -= n;
                }
                var count = Math.Min(r.Frames * channels, outCount - at);
                if (count <= 0) continue;
                if (bytes.Length < count * 2) bytes = new byte[count * 2];
                Buffer.BlockCopy(outSamples, at * 2, bytes, 0, count * 2);
                wav.Write(bytes, 0, count * 2);
                dataBytes += count * 2L;
                at += count;
            }
            Header(channels > 0 ? channels : 2, rate > 0 ? rate : (rateHint > 0 ? rateHint : 48000));
            foreach (var r in outRows)
            {
                var row = new AutoPlayJson().Add("frame", r.Frame).Add("frames", r.Frames).Add("qpc", r.Qpc)
                    .Add("t_ns", AutoPlayClock.ToNs(r.Qpc)).Add("silence_before", r.Silence);
                if (r.Clock >= 0.0) row.Add("audio_clock", r.Clock);
                else row.AddNull("audio_clock");
                clockFile.WriteLine(row.Add("channels", r.Channels).Add("rate", r.Rate).Close());
            }
            clockFile.Flush();
        }
        catch (Exception e)
        {
            AutoPlayRun.Error("audio.wav could not be written: " + e.Message);
            Close();
        }
        finally
        {
            outRows.Clear();
            spareRows = outRows;
            spare = outSamples;
        }
    }

    static readonly byte[] h = new byte[44];

    /// <summary>The 44-byte header for the data written so far, then everything to the OS (a crash loses none of it).</summary>
    static void Header(int channels, int rate)
    {
        void Put(int at, string s) { for (var i = 0; i < 4; i++) h[at + i] = (byte)s[i]; }
        void U32(int at, long v) { for (var i = 0; i < 4; i++) h[at + i] = (byte)((v >> (8 * i)) & 0xFF); }
        void U16(int at, int v) { h[at] = (byte)(v & 0xFF); h[at + 1] = (byte)((v >> 8) & 0xFF); }
        Put(0, "RIFF"); U32(4, 36 + dataBytes); Put(8, "WAVE");
        Put(12, "fmt "); U32(16, 16); U16(20, 1); U16(22, channels); U32(24, rate); U32(28, (long)rate * channels * 2);
        U16(32, channels * 2); U16(34, 16);
        Put(36, "data"); U32(40, dataBytes);
        var end = wav.Position;
        wav.Seek(0, SeekOrigin.Begin);
        wav.Write(h, 0, h.Length);
        wav.Seek(end, SeekOrigin.Begin);
        wav.Flush();
    }
}
