// One JSON object, written by hand: JsonUtility cannot write dictionaries, and no JSON package is assumed. Numbers are
// written with the invariant culture (a player on a German PC would write 0,5 otherwise); JSON has no NaN or Infinity,
// so those are null.
using System;
using System.Collections;
using System.Collections.Generic;
using System.Globalization;
using System.Text;
using UnityEngine;

internal sealed class AutoPlayJson
{
    readonly StringBuilder sb = new StringBuilder(160);
    bool first = true;

    public AutoPlayJson() => sb.Append('{');

    AutoPlayJson Key(string key)
    {
        if (!first) sb.Append(',');
        first = false;
        Str(sb, key);
        sb.Append(':');
        return this;
    }

    public AutoPlayJson Add(string key, string value) { Key(key); Str(sb, value); return this; }
    public AutoPlayJson Add(string key, long value) { Key(key); sb.Append(value.ToString(CultureInfo.InvariantCulture)); return this; }
    public AutoPlayJson Add(string key, double value) { Key(key); Num(sb, value); return this; }
    public AutoPlayJson Add(string key, float value) { Key(key); Num(sb, value); return this; }
    public AutoPlayJson Add(string key, bool value) { Key(key); sb.Append(value ? "true" : "false"); return this; }
    public AutoPlayJson Add(string key, Vector2 value) { Key(key); Value(sb, value); return this; }
    public AutoPlayJson AddNull(string key) { Key(key); sb.Append("null"); return this; }
    public AutoPlayJson AddValue(string key, object value) { Key(key); Value(sb, value); return this; }
    /// <summary>A value that is already JSON text.</summary>
    public AutoPlayJson AddRaw(string key, string json) { Key(key); sb.Append(json); return this; }

    /// <summary>Every key and value of a dictionary, but the keys `skip` names (the caller's own).</summary>
    public AutoPlayJson AddAll(IDictionary<string, object> fields, ICollection<string> skip)
    {
        if (fields == null) return this;
        foreach (var kv in fields)
        {
            if (kv.Key == null || (skip != null && skip.Contains(kv.Key))) continue;
            Key(kv.Key);
            Value(sb, kv.Value);
        }
        return this;
    }

    /// <summary>The object's text, closed.</summary>
    public string Close() => sb.Append('}').ToString();

    // ----------------------------------------------------------------------------------------------- values

    public static string Text(object value)
    {
        var b = new StringBuilder(64);
        Value(b, value);
        return b.ToString();
    }

    static void Num(StringBuilder b, double v)
    {
        if (double.IsNaN(v) || double.IsInfinity(v)) b.Append("null");
        else b.Append(v.ToString("R", CultureInfo.InvariantCulture));
    }

    static void Num(StringBuilder b, float v)
    {
        if (float.IsNaN(v) || float.IsInfinity(v)) b.Append("null");
        else b.Append(v.ToString("R", CultureInfo.InvariantCulture));
    }

    static void Value(StringBuilder b, object v, int depth = 0)
    {
        if (depth > 16) { b.Append("null"); return; }
        switch (v)
        {
            case null: b.Append("null"); return;
            case string s: Str(b, s); return;
            case bool x: b.Append(x ? "true" : "false"); return;
            case float f: Num(b, f); return;
            case double d: Num(b, d); return;
            case decimal m: b.Append(m.ToString(CultureInfo.InvariantCulture)); return;
            case int _: case long _: case short _: case byte _: case sbyte _: case uint _: case ulong _: case ushort _:
                b.Append(((IFormattable)v).ToString(null, CultureInfo.InvariantCulture)); return;
            case Enum e: Str(b, e.ToString()); return;
            case Vector2 a: b.Append('['); Num(b, a.x); b.Append(','); Num(b, a.y); b.Append(']'); return;
            case Vector3 a: b.Append('['); Num(b, a.x); b.Append(','); Num(b, a.y); b.Append(','); Num(b, a.z); b.Append(']'); return;
            case Vector4 a:
                b.Append('['); Num(b, a.x); b.Append(','); Num(b, a.y); b.Append(','); Num(b, a.z); b.Append(','); Num(b, a.w); b.Append(']');
                return;
            case Vector2Int a: b.Append('[').Append(a.x.ToString(CultureInfo.InvariantCulture)).Append(',').Append(a.y.ToString(CultureInfo.InvariantCulture)).Append(']'); return;
            case Vector3Int a:
                b.Append('[').Append(a.x.ToString(CultureInfo.InvariantCulture)).Append(',').Append(a.y.ToString(CultureInfo.InvariantCulture))
                    .Append(',').Append(a.z.ToString(CultureInfo.InvariantCulture)).Append(']');
                return;
            case Quaternion q: Value(b, q.eulerAngles, depth + 1); return;  // [pitch, yaw, roll], degrees
            case Color c:
                b.Append('['); Num(b, c.r); b.Append(','); Num(b, c.g); b.Append(','); Num(b, c.b); b.Append(','); Num(b, c.a); b.Append(']');
                return;
            case IDictionary dict:
            {
                b.Append('{');
                var firstKey = true;
                foreach (DictionaryEntry e in dict)
                {
                    if (!firstKey) b.Append(',');
                    firstKey = false;
                    Str(b, Convert.ToString(e.Key, CultureInfo.InvariantCulture) ?? "");
                    b.Append(':');
                    Value(b, e.Value, depth + 1);
                }
                b.Append('}');
                return;
            }
            case IEnumerable list:
            {
                b.Append('[');
                var firstItem = true;
                foreach (var item in list)
                {
                    if (!firstItem) b.Append(',');
                    firstItem = false;
                    Value(b, item, depth + 1);
                }
                b.Append(']');
                return;
            }
            default:
                Str(b, Convert.ToString(v, CultureInfo.InvariantCulture) ?? "");
                return;
        }
    }

    public static void Str(StringBuilder b, string s)
    {
        b.Append('"');
        if (s != null)
            foreach (var c in s)
            {
                switch (c)
                {
                    case '"': b.Append("\\\""); break;
                    case '\\': b.Append("\\\\"); break;
                    case '\n': b.Append("\\n"); break;
                    case '\r': b.Append("\\r"); break;
                    case '\t': b.Append("\\t"); break;
                    default:
                        if (c < 0x20) b.Append("\\u").Append(((int)c).ToString("x4", CultureInfo.InvariantCulture));
                        else b.Append(c);
                        break;
                }
            }
        b.Append('"');
    }
}
