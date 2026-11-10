namespace UnityEngine { public struct Color32 { public byte r, g, b, a; } }
namespace TaskProbe {
  public sealed class FrameImage { public int Width, Height; public UnityEngine.Color32[] Pixels;
    public UnityEngine.Color32 At(int x, int yFromTop) => Pixels[(Height - 1 - yFromTop) * Width + x]; }
  public sealed class UiElement { public string Name, Class, Source, Kind, Text; public bool HasRect; public double X, Y, W, H; }
}
