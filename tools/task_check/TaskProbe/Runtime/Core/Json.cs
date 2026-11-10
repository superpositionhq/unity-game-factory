// A small JSON reader and writer for the probe's files (the play spec in, probe.json out). Values are
// Dictionary<string, object> (an object), List<object> (an array), double, bool, string and null. No package is
// assumed: Unity's JsonUtility cannot read or write dictionaries.
using System;
using System.Collections;
using System.Collections.Generic;
using System.Globalization;
using System.Text;
using UnityEngine;

namespace TaskProbe
{
    public static class Json
    {
        // ---------------------------------------------------------------- reading

        const int MaxDepth = 512;  // nested arrays and objects: a deeper text would overflow the stack, which no catch stops

        /// <summary>The value `text` holds; throws FormatException on bad JSON (or nesting deeper than 512).</summary>
        public static object Parse(string text)
        {
            var at = 0;
            var value = ReadValue(text, ref at, 0);
            SkipSpace(text, ref at);
            if (at != text.Length) throw new FormatException("JSON: text after the value at " + at);
            return value;
        }

        static void SkipSpace(string s, ref int i)
        {
            while (i < s.Length && (s[i] == ' ' || s[i] == '\n' || s[i] == '\r' || s[i] == '\t' || s[i] == '\uFEFF')) i++;
        }

        static object ReadValue(string s, ref int i, int depth)
        {
            SkipSpace(s, ref i);
            if (i >= s.Length) throw new FormatException("JSON: ended early");
            var c = s[i];
            if ((c == '{' || c == '[') && depth >= MaxDepth) throw new FormatException("JSON: nested deeper than " + MaxDepth + " at " + i);
            if (c == '{')
            {
                var obj = new Dictionary<string, object>(StringComparer.Ordinal);
                i++;
                SkipSpace(s, ref i);
                if (i < s.Length && s[i] == '}') { i++; return obj; }
                while (true)
                {
                    SkipSpace(s, ref i);
                    var key = ReadString(s, ref i);
                    SkipSpace(s, ref i);
                    if (i >= s.Length || s[i] != ':') throw new FormatException("JSON: ':' expected at " + i);
                    i++;
                    obj[key] = ReadValue(s, ref i, depth + 1);
                    SkipSpace(s, ref i);
                    if (i < s.Length && s[i] == ',') { i++; continue; }
                    if (i < s.Length && s[i] == '}') { i++; return obj; }
                    throw new FormatException("JSON: ',' or '}' expected at " + i);
                }
            }
            if (c == '[')
            {
                var list = new List<object>();
                i++;
                SkipSpace(s, ref i);
                if (i < s.Length && s[i] == ']') { i++; return list; }
                while (true)
                {
                    list.Add(ReadValue(s, ref i, depth + 1));
                    SkipSpace(s, ref i);
                    if (i < s.Length && s[i] == ',') { i++; continue; }
                    if (i < s.Length && s[i] == ']') { i++; return list; }
                    throw new FormatException("JSON: ',' or ']' expected at " + i);
                }
            }
            if (c == '"') return ReadString(s, ref i);
            if (string.CompareOrdinal(s, i, "true", 0, 4) == 0) { i += 4; return true; }
            if (string.CompareOrdinal(s, i, "false", 0, 5) == 0) { i += 5; return false; }
            if (string.CompareOrdinal(s, i, "null", 0, 4) == 0) { i += 4; return null; }
            var start = i;
            while (i < s.Length && (char.IsDigit(s[i]) || s[i] == '-' || s[i] == '+' || s[i] == '.' || s[i] == 'e' || s[i] == 'E')) i++;
            if (i == start || !double.TryParse(s.Substring(start, i - start), NumberStyles.Float, CultureInfo.InvariantCulture, out var number))
                throw new FormatException("JSON: unexpected character at " + start);
            return number;
        }

        static string ReadString(string s, ref int i)
        {
            if (i >= s.Length || s[i] != '"') throw new FormatException("JSON: string expected at " + i);
            i++;
            var sb = new StringBuilder();
            while (i < s.Length)
            {
                var c = s[i++];
                if (c == '"') return sb.ToString();
                if (c != '\\') { sb.Append(c); continue; }
                if (i >= s.Length) break;
                var e = s[i++];
                switch (e)
                {
                    case 'n': sb.Append('\n'); break;
                    case 'r': sb.Append('\r'); break;
                    case 't': sb.Append('\t'); break;
                    case 'b': sb.Append('\b'); break;
                    case 'f': sb.Append('\f'); break;
                    case 'u':
                        if (i + 4 > s.Length) throw new FormatException("JSON: bad \\u escape");
                        sb.Append((char)int.Parse(s.Substring(i, 4), NumberStyles.HexNumber, CultureInfo.InvariantCulture));
                        i += 4;
                        break;
                    default: sb.Append(e); break;
                }
            }
            throw new FormatException("JSON: string not closed");
        }

        // ---------------------------------------------------------------- writing

        /// <summary>`value` as JSON text. NaN and infinities are written as null.</summary>
        public static string Write(object value)
        {
            var sb = new StringBuilder(1024);
            WriteValue(sb, value);
            return sb.ToString();
        }

        static void WriteValue(StringBuilder sb, object v)
        {
            switch (v)
            {
                case null: sb.Append("null"); return;
                case string s: WriteString(sb, s); return;
                case bool b: sb.Append(b ? "true" : "false"); return;
                case double d: WriteNumber(sb, d); return;
                case float f: WriteNumber(sb, f); return;
                case int n: sb.Append(n.ToString(CultureInfo.InvariantCulture)); return;
                case long n: sb.Append(n.ToString(CultureInfo.InvariantCulture)); return;
                case uint n: sb.Append(n.ToString(CultureInfo.InvariantCulture)); return;
                case ulong n: sb.Append(n.ToString(CultureInfo.InvariantCulture)); return;
                case short n: sb.Append(n.ToString(CultureInfo.InvariantCulture)); return;
                case byte n: sb.Append(n.ToString(CultureInfo.InvariantCulture)); return;
                case decimal n: sb.Append(n.ToString(CultureInfo.InvariantCulture)); return;
                case IDictionary<string, object> obj:
                {
                    sb.Append('{');
                    var first = true;
                    foreach (var kv in obj)
                    {
                        if (!first) sb.Append(',');
                        first = false;
                        WriteString(sb, kv.Key);
                        sb.Append(':');
                        WriteValue(sb, kv.Value);
                    }
                    sb.Append('}');
                    return;
                }
                case IEnumerable list:
                {
                    sb.Append('[');
                    var first = true;
                    foreach (var item in list)
                    {
                        if (!first) sb.Append(',');
                        first = false;
                        WriteValue(sb, item);
                    }
                    sb.Append(']');
                    return;
                }
                default: WriteString(sb, Convert.ToString(v, CultureInfo.InvariantCulture)); return;
            }
        }

        static void WriteNumber(StringBuilder sb, double d)
        {
            if (double.IsNaN(d) || double.IsInfinity(d)) { sb.Append("null"); return; }
            if (d == Math.Floor(d) && Math.Abs(d) < 1e15) { sb.Append(((long)d).ToString(CultureInfo.InvariantCulture)); return; }
            // 17 significant digits: they always read back as the same double. Mono's
            // "R" writes 15 digits for a few that read back as another (0.08993034534618741 as 0.0899303453461874), and
            // its own double.Parse rounds those the same wrong way, so a shorter form can't be checked here
            sb.Append(d.ToString("G17", CultureInfo.InvariantCulture));
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

        // ---------------------------------------------------------------- reading values out of parsed JSON

        public static Dictionary<string, object> Obj(object o) => o as Dictionary<string, object>;

        /// <summary>o[key] as an object, or null.</summary>
        public static Dictionary<string, object> Obj(Dictionary<string, object> o, string key) =>
            o != null && o.TryGetValue(key, out var v) ? v as Dictionary<string, object> : null;

        public static List<object> Arr(Dictionary<string, object> o, string key) =>
            o != null && o.TryGetValue(key, out var v) ? v as List<object> : null;

        public static string Str(Dictionary<string, object> o, string key, string fallback = null) =>
            o != null && o.TryGetValue(key, out var v) && v is string s ? s : fallback;

        public static bool TryNum(Dictionary<string, object> o, string key, out double value)
        {
            value = 0;
            if (o == null || !o.TryGetValue(key, out var v)) return false;
            if (v is double d) { value = d; return true; }
            return false;
        }

        public static double Num(Dictionary<string, object> o, string key, double fallback = 0) =>
            TryNum(o, key, out var v) ? v : fallback;

        public static bool Bool(Dictionary<string, object> o, string key, bool fallback = false) =>
            o != null && o.TryGetValue(key, out var v) && v is bool b ? b : fallback;

        /// <summary>[a, b, ...] of at least `count` numbers.</summary>
        public static bool TryNumbers(object value, int count, out double[] numbers)
        {
            numbers = null;
            if (!(value is List<object> list) || list.Count < count) return false;
            var found = new double[count];
            for (var i = 0; i < count; i++)
            {
                if (!(list[i] is double d)) return false;
                found[i] = d;
            }
            numbers = found;
            return true;
        }

        public static bool TryVec3(object value, out Vector3 v)
        {
            v = Vector3.zero;
            if (!TryNumbers(value, 3, out var n)) return false;
            v = new Vector3((float)n[0], (float)n[1], (float)n[2]);
            return true;
        }

        public static List<object> Vec(Vector3 v) => new List<object> { (double)v.x, (double)v.y, (double)v.z };
        public static List<object> Rgb(Color c) => new List<object> { (double)c.r, (double)c.g, (double)c.b };

        /// <summary>The strings of o[key] (an array of strings), empty when unset.</summary>
        public static List<string> Strings(Dictionary<string, object> o, string key)
        {
            var found = new List<string>();
            var list = Arr(o, key);
            if (list != null)
                foreach (var item in list)
                    if (item is string s) found.Add(s);
            return found;
        }
    }
}
