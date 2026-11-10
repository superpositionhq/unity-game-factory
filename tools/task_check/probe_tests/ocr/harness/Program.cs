using System; using System.IO; using System.Collections.Generic; using TaskProbe;
class P { static void Main(string[] a) {
  var b = File.ReadAllBytes(a[0]); int w = BitConverter.ToInt32(b,0), h = BitConverter.ToInt32(b,4);
  var px = new UnityEngine.Color32[w*h];
  for (int y=0;y<h;y++) for(int x=0;x<w;x++){ int s=8+(y*w+x)*3; px[(h-1-y)*w+x]=new UnityEngine.Color32{r=b[s],g=b[s+1],b=b[s+2],a=255}; }
  var f = new FrameImage{Width=w,Height=h,Pixels=px};
  var rect = new double[]{double.Parse(a[1]),double.Parse(a[2]),double.Parse(a[3]),double.Parse(a[4])};
  var outp = new List<UiElement>(); UiOcr.Elements(f, rect, new List<UiElement>(), outp);
  foreach (var e in outp) Console.WriteLine($"'{e.Text}' {e.X:F3} {e.Y:F3} {e.W:F3} {e.H:F3}");
  Console.WriteLine("lines: "+outp.Count);
}}
