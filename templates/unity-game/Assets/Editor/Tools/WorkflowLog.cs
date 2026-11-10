// Appends one row to the project's workflow.jsonl (schema unity-workflow/v0) at the moment an editor step acts.
// Every editor step logs at least one row per run: WorkflowLog.Row("scene.build", "Assets/Scenes/Harbor.unity", ...).
// The row's source is the calling step's own file (project-relative) and the sha256 of it as committed, so the record
// points at the code that really ran; that is why a step that ran is never edited (write a new step instead).
using System;
using System.Collections;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Runtime.CompilerServices;
using System.Security.Cryptography;
using System.Text;
using System.Text.RegularExpressions;
using UnityEngine;

namespace __PROJECT__.EditorTools
{
    public static class WorkflowLog
    {
        public const string Schema = "unity-workflow/v0";

        /// <summary>The project root (the folder that holds Assets/).</summary>
        public static string ProjectRoot => Directory.GetParent(Application.dataPath).FullName;

        static string FilePath => Path.Combine(ProjectRoot, "workflow.jsonl");

        /// <summary>
        /// Append a row and return its id. `parameters` holds what the step did (strings, numbers, bools, lists and
        /// dictionaries of those). `reason` defaults to the -Reason given to Scripts/unity.ps1 (UNITY_RUN_REASON).
        /// `status`: observed, failed or reverted. `direction`: the user.direction row this acts on, if any.
        /// </summary>
        public static string Row(string op, string target, IDictionary<string, object> parameters = null,
            string reason = null, string status = "observed", string direction = null,
            [CallerFilePath] string callerFile = "")
        {
            var (prefix, number, seq) = Last();
            var id = $"{prefix}-{number + 1:D5}";
            var source = SourceOf(callerFile);
            var row = new List<KeyValuePair<string, object>>
            {
                new("schema", Schema),
                new("id", id),
                new("seq", seq + 1),
                new("time", DateTimeOffset.Now.ToString("yyyy-MM-dd'T'HH:mm:ss.fffzzz", CultureInfo.InvariantCulture)),
                new("actor", "agent"),
                new("op", op),
                new("target", target),
                new("params", parameters ?? new Dictionary<string, object>()),
                new("reason", reason ?? Environment.GetEnvironmentVariable("UNITY_RUN_REASON") ?? ""),
                new("reason_source", "agent_note"),
                new("status", status),
                new("source", source),
            };
            if (!string.IsNullOrEmpty(direction)) row.Add(new KeyValuePair<string, object>("direction", direction));
            var sb = new StringBuilder();
            // a file whose last line has no line break (a row appended by hand without one) gets one first: glued to
            // it, this row would make both unreadable
            if (!EndsWithLineBreak()) sb.Append('\n');
            WriteObject(sb, row);
            // one write of one whole line; another writer (a direction appended by hand) may hold the file for a moment
            for (var i = 0; ; i++)
            {
                try { File.AppendAllText(FilePath, sb.ToString() + "\n", new UTF8Encoding(false)); break; }
                catch (IOException) when (i < 4) { System.Threading.Thread.Sleep(50 * (i + 1)); }
            }
            // a failed row says why on its one console line, the line Scripts/unity.ps1 prints
            var error = status != "observed" && parameters != null && parameters.TryGetValue("error", out var e)
                ? ": " + Regex.Replace(Convert.ToString(e, CultureInfo.InvariantCulture) ?? "", @"\s+", " ").Trim() : "";
            Debug.Log($"[workflow] {id} {op} {target}{(status == "observed" ? "" : $" ({status}{error})")}");
            return id;
        }

        /// <summary>The id prefix, the last row number and the last seq, read from the last line that has an id (a
        /// line cut short, by a crash or by hand, is passed over rather than stopping every later step).</summary>
        static (string prefix, int number, int seq) Last()
        {
            Match id = null, seq = null;
            if (File.Exists(FilePath))
            {
                // read beside another writer: File.ReadLines refuses a file that one has open, and the step then
                // failed without its row (measured: a row appended by hand at that moment)
                using var r = new StreamReader(new FileStream(FilePath, FileMode.Open, FileAccess.Read, FileShare.ReadWrite));
                for (string line; (line = r.ReadLine()) != null;)
                {
                    var m = Regex.Match(line, "\"id\"\\s*:\\s*\"([A-Za-z0-9]+)-(\\d+)\"");
                    if (!m.Success) continue;
                    id = m;
                    seq = Regex.Match(line, "\"seq\"\\s*:\\s*(\\d+)");
                }
            }
            if (id == null) throw new InvalidOperationException("workflow.jsonl has no rows: the project was not created by new-game.ps1");
            var n = int.Parse(id.Groups[2].Value, CultureInfo.InvariantCulture);
            return (id.Groups[1].Value, n, seq.Success ? int.Parse(seq.Groups[1].Value, CultureInfo.InvariantCulture) : n);
        }

        static bool EndsWithLineBreak()
        {
            if (!File.Exists(FilePath)) return true;
            using var f = new FileStream(FilePath, FileMode.Open, FileAccess.Read, FileShare.ReadWrite);
            if (f.Length == 0) return true;
            f.Seek(-1, SeekOrigin.End);
            return f.ReadByte() == '\n';
        }

        static IDictionary<string, object> SourceOf(string callerFile)
        {
            string rel = null, sha = null;
            if (!string.IsNullOrEmpty(callerFile))
            {
                var norm = callerFile.Replace('\\', '/');
                var at = norm.LastIndexOf("/Assets/", StringComparison.Ordinal);
                rel = at >= 0 ? norm.Substring(at + 1) : Path.GetFileName(norm);
                var abs = Path.Combine(ProjectRoot, rel);
                if (File.Exists(abs))
                {
                    using var h = SHA256.Create();
                    sha = BitConverter.ToString(h.ComputeHash(AsCommitted(File.ReadAllBytes(abs)))).Replace("-", "").ToLowerInvariant();
                }
            }
            return new Dictionary<string, object> { ["script"] = rel, ["sha256"] = sha, ["commit"] = null };
        }

        /// <summary>The bytes as git commits them: C# is text in .gitattributes, so CRLF is stored as LF. A step written
        /// with CRLF (PowerShell's Set-Content does) would otherwise get a hash that no checkout of it ever matches.</summary>
        static byte[] AsCommitted(byte[] bytes)
        {
            var o = new List<byte>(bytes.Length);
            for (var i = 0; i < bytes.Length; i++)
                if (bytes[i] != '\r' || i + 1 == bytes.Length || bytes[i + 1] != '\n') o.Add(bytes[i]);
            return o.ToArray();
        }

        // A small JSON writer: Unity's JsonUtility cannot write dictionaries, and no JSON package is assumed.
        static void WriteObject(StringBuilder sb, IEnumerable<KeyValuePair<string, object>> pairs)
        {
            sb.Append('{');
            var first = true;
            foreach (var kv in pairs)
            {
                if (!first) sb.Append(',');
                first = false;
                WriteString(sb, kv.Key);
                sb.Append(':');
                WriteValue(sb, kv.Value);
            }
            sb.Append('}');
        }

        static void WriteValue(StringBuilder sb, object v)
        {
            switch (v)
            {
                case null: sb.Append("null"); break;
                case string s: WriteString(sb, s); break;
                case bool b: sb.Append(b ? "true" : "false"); break;
                // JSON has no NaN or Infinity: a row holding one would not parse, and rows are never edited
                case float f: sb.Append(float.IsNaN(f) || float.IsInfinity(f) ? "null" : f.ToString("R", CultureInfo.InvariantCulture)); break;
                case double d: sb.Append(double.IsNaN(d) || double.IsInfinity(d) ? "null" : d.ToString("R", CultureInfo.InvariantCulture)); break;
                case IFormattable n when v is int || v is long || v is short || v is byte || v is sbyte || v is uint || v is ulong || v is ushort || v is decimal:
                    sb.Append(n.ToString(null, CultureInfo.InvariantCulture)); break;
                case IDictionary dict:
                    var pairs = new List<KeyValuePair<string, object>>();
                    foreach (DictionaryEntry e in dict) pairs.Add(new KeyValuePair<string, object>(Convert.ToString(e.Key, CultureInfo.InvariantCulture), e.Value));
                    WriteObject(sb, pairs);
                    break;
                case IEnumerable<KeyValuePair<string, object>> kvs: WriteObject(sb, kvs); break;
                case IEnumerable list:
                    sb.Append('[');
                    var first = true;
                    foreach (var item in list)
                    {
                        if (!first) sb.Append(',');
                        first = false;
                        WriteValue(sb, item);
                    }
                    sb.Append(']');
                    break;
                default: WriteString(sb, Convert.ToString(v, CultureInfo.InvariantCulture)); break;
            }
        }

        static void WriteString(StringBuilder sb, string s)
        {
            sb.Append('"');
            foreach (var c in s)
            {
                switch (c)
                {
                    case '"': sb.Append("\\\""); break;
                    case '\\': sb.Append("\\\\"); break;
                    case '\n': sb.Append("\\n"); break;
                    case '\r': sb.Append("\\r"); break;
                    case '\t': sb.Append("\\t"); break;
                    default:
                        if (c < 0x20) sb.Append("\\u").Append(((int)c).ToString("x4", CultureInfo.InvariantCulture));
                        else sb.Append(c);
                        break;
                }
            }
            sb.Append('"');
        }
    }
}
