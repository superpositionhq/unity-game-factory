// Appends one row to the project's workflow.jsonl (schema unity-workflow/v0) at the moment an editor step acts.
// Every editor step logs at least one row per run: WorkflowLog.Row("scene.build", "Assets/Scenes/Harbor.unity", ...).
// The row's source is the calling step's own file (project-relative) and its sha256, so the record points at the code
// that really ran; that is why a step that ran is never edited (write a new step instead).
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
            WriteObject(sb, row);
            File.AppendAllText(FilePath, sb.Append('\n').ToString(), new UTF8Encoding(false));
            Debug.Log($"[workflow] {id} {op} {target}");
            return id;
        }

        /// <summary>The id prefix, the last row number and the last seq, read from the file's last row.</summary>
        static (string prefix, int number, int seq) Last()
        {
            string last = null;
            if (File.Exists(FilePath))
                foreach (var line in File.ReadLines(FilePath))
                    if (!string.IsNullOrWhiteSpace(line)) last = line;
            if (last == null) throw new InvalidOperationException("workflow.jsonl has no rows: the project was not created by new-game.ps1");
            var id = Regex.Match(last, "\"id\"\\s*:\\s*\"([A-Za-z0-9]+)-(\\d+)\"");
            var seq = Regex.Match(last, "\"seq\"\\s*:\\s*(\\d+)");
            if (!id.Success) throw new InvalidOperationException("the last workflow.jsonl row has no id");
            var n = int.Parse(id.Groups[2].Value, CultureInfo.InvariantCulture);
            return (id.Groups[1].Value, n, seq.Success ? int.Parse(seq.Groups[1].Value, CultureInfo.InvariantCulture) : n);
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
                    sha = BitConverter.ToString(h.ComputeHash(File.ReadAllBytes(abs))).Replace("-", "").ToLowerInvariant();
                }
            }
            return new Dictionary<string, object> { ["script"] = rel, ["sha256"] = sha, ["commit"] = null };
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
                case float f: sb.Append(f.ToString("R", CultureInfo.InvariantCulture)); break;
                case double d: sb.Append(d.ToString("R", CultureInfo.InvariantCulture)); break;
                case IFormattable n when v is int || v is long || v is short || v is byte || v is uint || v is ulong || v is decimal:
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
