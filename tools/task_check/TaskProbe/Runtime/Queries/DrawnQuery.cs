// drawn: what is drawn in a place, whatever draws it (contract section 3). Every drawn renderer whose world bounds
// reach the place is rendered alone (DrawnRender), orthographic: near a point from the four corners of a tetrahedron
// around it (64 x 64), along a line from two sides square to it (128 x 128). A pixel is in the place when its depth puts
// it there, or when it shows colour with nothing opaque behind it and its ray crosses the place (translucent particles).
// The views reach no deeper than the place's far side, so an opaque surface beyond the place hides nothing in front.
// "value" near a point: {"drawn", "motion", "base_r", "base_g", "base_b", "base_change", "pixels", "primitives"};
// along a line: {"drawn", "reach", "length", "pixels", "primitives"}; null when the place doesn't resolve or nothing
// could be rendered.
using System;
using System.Collections.Generic;
using System.Diagnostics;
using UnityEngine;

namespace TaskProbe
{
    [ProbeQuery("drawn")]
    public sealed class DrawnQuery : Query
    {
        const int NearSize = 64, LineSize = 128, LineBins = 128, MaxRenderers = 1024;
        const float Enclosing = 20f;  // a renderer around the whole place and this many times its size is left out
        const float Back = 0.5f;  // m: the cameras stand this far outside the place
        const double Step = 1.0 / 255.0;  // motion: a pixel changed when its colour (c / (1 + c)) moved more
        const double Faint = 1.0e-4;  // a translucent pixel with nothing opaque behind it counts above this luminance

        NearSel near;
        Dictionary<string, object> from, to;
        float lineRadius;
        bool wantBase;

        // motion: the previous sample's pixels in the place and their colours; base_change: the first base colour
        bool[] keptBefore;
        Vector3[] colourBefore;
        bool firstBaseSet;
        Vector3 firstBase;

        readonly List<Renderer> show = new List<Renderer>();
        readonly List<DrawnView> views = new List<DrawnView>();
        readonly List<DrawnImage> lit = new List<DrawnImage>(), dark = new List<DrawnImage>();
        int samples;
        double ms;

        public override void Load()
        {
            near = NearSel.Parse(Json.Obj(Def, "near"));
            var line = Json.Obj(Def, "line");
            if (near == null && line != null)
            {
                from = Json.Obj(line, "from");
                to = Json.Obj(line, "to");
                lineRadius = (float)Json.Num(line, "radius", 0);
                if (from == null || to == null || !(lineRadius > 0f) || lineRadius > 100f)
                    Probe.Error("drawn " + Id + ": a line needs from, to and a radius in (0, 100]");
            }
            else if (near == null) Probe.Error("drawn " + Id + ": no near or line");
            foreach (var f in Fields)
                if (f.StartsWith("base_", StringComparison.Ordinal)) wantBase = true;
        }

        public override void Sample(double t, Dictionary<string, object> sample)
        {
            sample["value"] = null;
            var clock = Stopwatch.StartNew();
            Dictionary<string, object> value = null;
            if (near != null) value = SampleNear();
            else if (from != null && to != null && lineRadius > 0f && lineRadius <= 100f) value = SampleLine();
            sample["value"] = value;
            ms += clock.Elapsed.TotalMilliseconds;
            samples++;
            if (samples == 1 || samples % 10 == 0)
                Probe.Log($"drawn {Id}: {clock.Elapsed.TotalMilliseconds:F2} ms this sample, {ms / samples:F2} ms a sample over {samples}, {show.Count} renderer(s)");
        }

        /// <summary>The drawn renderers whose bounds `touches` says reach the place, less one around the whole place
        /// (`place`) and many times its size (a sky dome, a room seen from inside: only its far side would show).</summary>
        void Gather(Bounds place, Func<Bounds, bool> touches)
        {
            show.Clear();
            DrawnRender.Drawn(out var all, out var bounds);
            var placeSize = Mathf.Max(Mathf.Max(place.size.x, Mathf.Max(place.size.y, place.size.z)), 0.01f);
            for (var i = 0; i < all.Count && show.Count < MaxRenderers; i++)
            {
                var b = bounds[i];
                if (all[i] == null || !touches(b)) continue;
                var encloses = b.min.x <= place.min.x && b.min.y <= place.min.y && b.min.z <= place.min.z &&
                               b.max.x >= place.max.x && b.max.y >= place.max.y && b.max.z >= place.max.z;
                if (encloses && Mathf.Min(b.size.x, Mathf.Min(b.size.y, b.size.z)) >= Enclosing * placeSize) continue;
                show.Add(all[i]);
            }
        }

        static double Compressed(float c) => c > 0f ? c / (1.0 + c) : 0.0;

        // ---------------------------------------------------------------- near a point

        Dictionary<string, object> SampleNear()
        {
            if (!near.Resolve(out var p) || !(near.Radius > 0f)) return null;
            var r = near.Radius;
            var baseY = near.YRelative ? p.y : 0f;
            var lo = p - Vector3.one * r;
            var hi = p + Vector3.one * r;
            if (near.YMin.HasValue) lo.y = Mathf.Max(lo.y, baseY + near.YMin.Value);
            if (near.YMax.HasValue) hi.y = Mathf.Min(hi.y, baseY + near.YMax.Value);
            show.Clear();
            if (lo.y <= hi.y)
            {
                var place = new Bounds((lo + hi) * 0.5f, hi - lo);
                Gather(place, b => b.SqrDistance(p) <= r * r && b.max.y >= lo.y && b.min.y <= hi.y);
            }
            views.Clear();
            foreach (var corner in new[] { new Vector3(1, 1, 1), new Vector3(1, -1, -1), new Vector3(-1, 1, -1), new Vector3(-1, -1, 1) })
            {
                var dir = corner.normalized;
                views.Add(new DrawnView
                {
                    Position = p + dir * (r + Back), Rotation = Quaternion.LookRotation(-dir, Vector3.up), Width = r * 2f * 1.02f,
                    Far = Back + 2.02f * r,
                });
            }
            const int n = NearSize;
            var count = views.Count * n * n;
            if (show.Count > 0)
            {
                if (!DrawnRender.Render(show, views, n, DrawnLight.White, true, lit) || lit.Count != views.Count) return null;
                if (wantBase && (!DrawnRender.Render(show, views, n, DrawnLight.Dark, false, dark) || dark.Count != views.Count)) return null;
            }
            var kept = new bool[count];
            var colour = new Vector3[count];
            long keptN = 0, opaqueN = 0;
            var baseSum = Vector3.zero;
            for (var v = 0; v < views.Count && show.Count > 0; v++)
            {
                var view = views[v];
                var right = view.Rotation * Vector3.right;
                var up = view.Rotation * Vector3.up;
                var forward = view.Rotation * Vector3.forward;
                var w = view.Width;
                var image = lit[v];
                for (var y = 0; y < n; y++)
                    for (var x = 0; x < n; x++)
                    {
                        var at = y * n + x;  // row 0 at the bottom of the view
                        var c = image.Colour[at];
                        var depth = image.Depth[at];
                        var onPlane = view.Position + right * (((x + 0.5f) / n - 0.5f) * w) + up * (((y + 0.5f) / n - 0.5f) * w);
                        bool keep = false, opaque = false;
                        if (!float.IsInfinity(depth))
                            keep = opaque = near.Contains(p, onPlane + forward * depth);
                        else if (DrawnRender.Luminance(c) > Faint)
                        {
                            var off = onPlane - p;
                            keep = (off - forward * Vector3.Dot(off, forward)).sqrMagnitude <= r * r;
                        }
                        if (!keep) continue;
                        var i = v * n * n + at;
                        kept[i] = true;
                        colour[i] = new Vector3((float)Compressed(c.r), (float)Compressed(c.g), (float)Compressed(c.b));
                        keptN++;
                        if (opaque && wantBase)
                        {
                            // the white-lit colour less the unlit one: what the ambient white light brought out of the
                            // surface, its own colour (emission and any light the probe couldn't turn off cancel out)
                            var d = dark[v].Colour[at];
                            baseSum += new Vector3(c.r - d.r, c.g - d.g, c.b - d.b);
                            opaqueN++;
                        }
                    }
            }
            var value = new Dictionary<string, object>(StringComparer.Ordinal)
            {
                ["drawn"] = keptN > 0 ? 1.0 : 0.0, ["pixels"] = (double)keptN, ["primitives"] = (double)show.Count,
            };
            // motion: of the pixels in the place now or at the previous sample, the share that changed
            if (keptBefore != null && keptBefore.Length == count)
            {
                long union = 0, changed = 0;
                for (var i = 0; i < count; i++)
                {
                    if (!kept[i] && !keptBefore[i]) continue;
                    union++;
                    var a = colour[i];
                    var b = colourBefore[i];
                    if (kept[i] != keptBefore[i] || Math.Abs(a.x - b.x) > Step || Math.Abs(a.y - b.y) > Step || Math.Abs(a.z - b.z) > Step) changed++;
                }
                value["motion"] = union > 0 ? (double)changed / union : 0.0;
            }
            else value["motion"] = null;
            keptBefore = kept;
            colourBefore = colour;
            if (wantBase && opaqueN > 0)
            {
                var mean = baseSum / opaqueN;
                value["base_r"] = (double)mean.x;
                value["base_g"] = (double)mean.y;
                value["base_b"] = (double)mean.z;
                if (!firstBaseSet)
                {
                    firstBaseSet = true;
                    firstBase = mean;
                }
                value["base_change"] = (double)Vector3.Distance(mean, firstBase);
            }
            else
            {
                value["base_r"] = null;
                value["base_g"] = null;
                value["base_b"] = null;
                value["base_change"] = null;
            }
            return value;
        }

        // ---------------------------------------------------------------- along a line

        Dictionary<string, object> SampleLine()
        {
            if (!Find.Point(from, out var a) || !Find.Point(to, out var b)) return null;
            var length = Vector3.Distance(a, b);
            if (length < 0.01f) return null;
            var r = lineRadius;
            var d = (b - a) / length;
            var place = new Bounds((a + b) * 0.5f, Vector3.zero);
            place.Encapsulate(Vector3.Min(a, b) - Vector3.one * r);
            place.Encapsulate(Vector3.Max(a, b) + Vector3.one * r);
            Gather(place, box =>
            {
                box.Expand(2f * r);
                if (box.Contains(a) || box.Contains(b)) return true;
                return box.IntersectRay(new Ray(a, d), out var hit) && hit <= length;
            });
            var side = Mathf.Abs(d.y) < 0.9f ? Vector3.Cross(d, Vector3.up).normalized : Vector3.Cross(d, Vector3.forward).normalized;
            var other = Vector3.Cross(d, side).normalized;
            var mid = (a + b) * 0.5f;
            views.Clear();
            foreach (var look in new[] { side, other })
                views.Add(new DrawnView
                {
                    Position = mid - look * (r + Back), Rotation = Quaternion.LookRotation(look, look == side ? other : side),
                    Width = length + 2f * r + 0.2f, Far = Back + 2.02f * r,
                });
            const int n = LineSize;
            if (show.Count > 0 && (!DrawnRender.Render(show, views, n, DrawnLight.White, true, lit) || lit.Count != views.Count)) return null;
            // steps along the line no finer than a pixel of the views, so a thin beam leaves no step between its pixels empty
            var steps = Mathf.Clamp(Mathf.FloorToInt(length / Mathf.Max(length / LineBins, views[0].Width / n)), 1, LineBins);
            var bins = new bool[steps];
            var reach = -1.0;
            long keptN = 0;
            for (var v = 0; v < views.Count && show.Count > 0; v++)
            {
                var view = views[v];
                var right = view.Rotation * Vector3.right;
                var up = view.Rotation * Vector3.up;
                var forward = view.Rotation * Vector3.forward;
                var w = view.Width;
                var image = lit[v];
                for (var y = 0; y < n; y++)
                    for (var x = 0; x < n; x++)
                    {
                        var at = y * n + x;
                        var depth = image.Depth[at];
                        var onPlane = view.Position + right * (((x + 0.5f) / n - 0.5f) * w) + up * (((y + 0.5f) / n - 0.5f) * w);
                        double t;
                        var keep = false;
                        if (!float.IsInfinity(depth))
                        {
                            var hit = onPlane + forward * depth;
                            t = Vector3.Dot(hit - a, d);
                            keep = (hit - (a + d * Mathf.Clamp((float)t, 0f, length))).sqrMagnitude <= r * r;
                        }
                        else if (DrawnRender.Luminance(image.Colour[at]) > Faint)
                        {
                            t = Vector3.Dot(onPlane - a, d);
                            var off = onPlane - (a + d * (float)t);
                            keep = (off - forward * Vector3.Dot(off, forward)).sqrMagnitude <= r * r;
                        }
                        else continue;
                        if (!keep || t < 0.0 || t > length) continue;
                        keptN++;
                        if (t > reach) reach = t;
                        bins[Mathf.Clamp((int)Math.Floor(t / length * steps), 0, steps - 1)] = true;
                    }
            }
            var covered = 0;
            foreach (var bin in bins)
                if (bin) covered++;
            return new Dictionary<string, object>(StringComparer.Ordinal)
            {
                ["drawn"] = keptN > 0 ? 1.0 : 0.0, ["reach"] = keptN > 0 ? reach : (object)null,
                ["length"] = (double)covered * length / steps, ["pixels"] = (double)keptN, ["primitives"] = (double)show.Count,
            };
        }
    }
}
