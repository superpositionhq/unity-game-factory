using System;
using System.Collections.Generic;
using UnityEngine;

namespace ProbeTests.Select
{
    /// <summary>A member of every kind for prop: paths. Values come from the field initialisers (the scene saves the
    /// same); `gone` is destroyed at Start, `clock` is the game's time, `reads` counts the calls of `Counted`.</summary>
    public sealed class SelProps : SelPropsBase
    {
        public float f = 1.5f;
        public double d = 0.1;
        public double third = 1.0 / 3.0;
        public double hard = 0.84551240822557006;  // a double .NET Framework's "R" format didn't write back exactly
        public int i = -3;
        public long big = 9007199254740993;  // 2^53 + 1: no double holds it
        public ulong huge = ulong.MaxValue;
        public uint u = 4000000000;
        public short s = -7;
        public byte b = 200;
        public sbyte sb = -100;
        public decimal money = 12.25m;
        public char c = 'x';
        public bool on = true;
        public string text = "Lamp (1) \"q\" \\ \u00e9 \u2713 \ud83d\ude00\n\ttab";
        public string empty = "";
        public string nothing;
        public SelMode mode = SelMode.Nine;
        public SelFlags flags = SelFlags.A | SelFlags.C;
        public Vector3 v = new Vector3(1f, 2f, 3f);
        public Color col = new Color(0.25f, 0.5f, 0.75f, 1f);
        public Quaternion q = new Quaternion(0f, 0.70710677f, 0f, 0.70710677f);
        public SelPair pair = new SelPair { a = 2.5f, b = 3 };
        public int[] arr = { 4, 5, 6 };
        public List<int> list = new List<int> { 7, 8 };
        public List<Vector3> points = new List<Vector3> { new Vector3(1f, 1f, 1f), new Vector3(2f, 4f, 2f) };
        public Dictionary<string, int> counts = new Dictionary<string, int> { ["coins"] = 3 };
        public HashSet<int> set = new HashSet<int> { 1, 2, 5 };
        public GameObject target;
        public Transform none;
        public GameObject gone;
        public SelData data = new SelData();
        public SelData noData;
        public float nan = float.NaN;
        public float inf = float.PositiveInfinity;
        public float ninf = float.NegativeInfinity;
        public double negZero = -0.0;
        public double e21 = 1e21;
        public double small = 1e-7;
        public float fmax = float.MaxValue;
        public static int stat = 42;
#pragma warning disable 0414  // read by prop: paths, not by code
        int priv = 17;
#pragma warning restore 0414
        public int Getter => i * 2;
        public int Throws => throw new InvalidOperationException("SelProps.Throws");
        public int this[int k] => k;
        public int reads;
        public int Counted => ++reads;
        public double clock;

        void Start()
        {
            if (gone != null) Destroy(gone);
        }

        void Update()
        {
            clock = Time.time;
        }
    }
}
