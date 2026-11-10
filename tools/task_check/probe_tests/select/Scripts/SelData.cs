namespace ProbeTests.Select
{
    /// <summary>A plain C# class (no Component, not serialized by Unity): a type a select can name that no component
    /// can be, and a reference a prop: path reads.</summary>
    public sealed class SelData
    {
        public int size = 4;
    }

    /// <summary>A struct a prop: path walks into.</summary>
    public struct SelPair
    {
        public float a;
        public int b;
    }

    public enum SelMode { One = 1, Two = 2, Nine = 9 }

    [System.Flags]
    public enum SelFlags { None = 0, A = 1, B = 2, C = 4 }
}
