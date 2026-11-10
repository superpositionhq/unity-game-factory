// drawn: what is drawn in a place, whatever draws it (contract section 3). Every drawn renderer and terrain whose world
// bounds reach the place (but one enclosing the whole place and 20 times its size: a sky dome, a room seen from inside)
// is rendered alone (DrawnRender), orthographic: near a point from the four corners of a tetrahedron around it (64 x 64),
// along a line from two sides square to it (128 x 128). A pixel is in the place when its depth puts it there, or when
// it is translucent with nothing opaque behind it and its ray crosses the place. The views reach no deeper than the
// place's far side, so an opaque surface beyond the place hides nothing in front of it.
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
        const int NearSize = 64;  // pixels square, each of the four views of a place near a point
        const int LineSize = 128;  // pixels square, each of the two views of a line
        const int LineBins = 128;  // the line's length read in at most this many steps (length), none finer than a pixel
        const float Enclosing = 20f;  // a renderer around the whole place and this many times its size is left out
        const double Step = 1.0 / 255.0;  // motion: a pixel changed when its colour (c / (1 + c)) moved more
        const double Faint = 1.0e-4;  // a translucent pixel with nothing opaque behind it counts above this luminance
        const int RendererCap = 1024;  // renderers one place renders at most

        // the fields of a place near a point and along a line; pixels and primitives are always in the value
        static readonly HashSet<string> NearFields = new HashSet<string>(StringComparer.Ordinal)
            { "drawn", "motion", "base_r", "base_g", "base_b", "base_change", "pixels", "primitives" };
        static readonly HashSet<string> LineFields = new HashSet<string>(StringComparer.Ordinal) { "drawn", "reach", "length", "pixels", "primitives" };

        NearSel near;
        Dictionary<string, object> from, to;
        float lineRadius;
        bool line, wantBase;

        // motion: this sample's pixels in the place and their colours, and the previous sample's (swapped each sample);
        // base_change: the first base colour
        bool[] kept, keptBefore;
        Vector3[] colour, colourBefore;
        bool firstBaseSet;
        double firstR, firstG, firstB;

        readonly List<Component> show = new List<Component>();
        readonly List<DrawnView> views = new List<DrawnView>();
        readonly List<DrawnImage> lit = new List<DrawnImage>(), dark = new List<DrawnImage>();
        int samples;
        double ms;

        public override void Load()
        {
            near = NearSel.Parse(Json.Obj(Def, "near"));
            var place = Json.Obj(Def, "line");
            if (near == null && place != null)
            {
                from = Json.Obj(place, "from");
                to = Json.Obj(place, "to");
                lineRadius = (float)Json.Num(place, "radius", 0);
                line = from != null && to != null && lineRadius > 0f;
                if (!line) Probe.Error("drawn " + Id + ": a line needs from, to and a radius above 0");
            }
            else if (near == null) Probe.Error("drawn " + Id + ": no near or line");
            if (near != null) KnownFields(NearFields);
            else if (line) KnownFields(LineFields);
            foreach (var f in Fields)
                if (f.StartsWith("base_", StringComparison.Ordinal)) wantBase = true;
        }

        public override void Sample(double t, Dictionary<string, object> sample)
        {
            sample["value"] = null;
            var clock = Stopwatch.StartNew();
            Dictionary<string, object> value = null;
            if (near != null) value = SampleNear();
            else if (line) value = SampleLine();
            sample["value"] = value;
            ms += clock.Elapsed.TotalMilliseconds;
            samples++;
            if (samples == 1 || samples % 10 == 0)
                Probe.Log($"drawn {Id}: {clock.Elapsed.TotalMilliseconds:F2} ms this sample, {ms / samples:F2} ms a sample over {samples}, {show.Count} renderer(s)");
        }

        /// <summary>The drawn renderers and terrains whose bounds `touches` says reach the place, but one whose bounds
        /// enclose the whole place (`place`) and are many times its size (a sky dome, a room seen from inside: only its far
        /// side would show); past the cap, the first in hierarchy order, so the same ones in every play.</summary>
        void Gather(Bounds place, Func<Bounds, bool> touches)
        {
            show.Clear();
            DrawnRender.Drawn(out var all, out var bounds);
            var placeSize = Mathf.Max(Mathf.Max(place.size.x, Mathf.Max(place.size.y, place.size.z)), 0.01f);
            for (var i = 0; i < all.Count; i++)
            {
                var b = bounds[i];
                if (all[i] == null || !touches(b)) continue;
                var encloses = b.min.x < place.min.x && b.min.y < place.min.y && b.min.z < place.min.z &&
                               b.max.x > place.max.x && b.max.y > place.max.y && b.max.z > place.max.z;
                if (encloses && Mathf.Min(b.size.x, Mathf.Min(b.size.y, b.size.z)) >= Enclosing * placeSize) continue;
                show.Add(all[i]);
            }
            if (show.Count <= RendererCap) return;
            Find.SortByHierarchy(show);
            show.RemoveRange(RendererCap, show.Count - RendererCap);
        }

        static double Compressed(float c) => c > 0f ? c / (1.0 + c) : 0.0;

        /// <summary>This sample's pixel buffers: the previous sample's, emptied (allocated the first time).</summary>
        void Fresh(int count)
        {
            if (kept == null || kept.Length != count)
            {
                kept = new bool[count];
                colour = new Vector3[count];
            }
            else Array.Clear(kept, 0, count);
        }

        // ---------------------------------------------------------------- near a point

        Dictionary<string, object> SampleNear()
        {
            // a sphere around the point, cut to its height band; four views from the corners of a tetrahedron
            if (!near.Resolve(out var p) || !(near.Radius > 0f)) return null;
            var r = near.Radius;
            var baseY = near.YRelative ? p.y : 0f;
            var lo = p - Vector3.one * r;
            var hi = p + Vector3.one * r;
            if (near.YMin.HasValue) lo.y = Mathf.Max(lo.y, baseY + near.YMin.Value);
            if (near.YMax.HasValue) hi.y = Mathf.Min(hi.y, baseY + near.YMax.Value);
            show.Clear();
            if (lo.y <= hi.y)
                Gather(new Bounds((lo + hi) * 0.5f, hi - lo), b => b.SqrDistance(p) <= r * r && b.max.y >= lo.y && b.min.y <= hi.y);
            views.Clear();
            foreach (var corner in DrawnRender.Tetrahedron)
            {
                var dir = corner.normalized;
                views.Add(new DrawnView
                {
                    Position = p + dir * (r + DrawnRender.Back), Rotation = Quaternion.LookRotation(-dir, Vector3.up),
                    Width = r * 2f * 1.02f, Far = DrawnRender.Back + 2.02f * r,
                });
            }
            const int n = NearSize;
            var count = views.Count * n * n;
            if (show.Count > 0)
            {
                if (!DrawnRender.Render(show, views, n, DrawnLight.White, true, lit)) return null;  // nothing renders
                if (wantBase && !DrawnRender.Render(show, views, n, DrawnLight.Dark, false, dark)) return null;
            }
            // each pixel: kept when what it shows is in the place (its depth puts it inside the sphere and the band), or
            // a translucent pixel with nothing opaque behind it whose ray crosses the sphere
            Fresh(count);
            long keptN = 0, opaqueN = 0;
            double sumR = 0.0, sumG = 0.0, sumB = 0.0;
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
                        else if (Find.Luminance(c.r, c.g, c.b) > Faint)
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
                            // the white-lit colour less the unlit one: what the white ambient brought out of the surface,
                            // its own colour (emission and any light the probe couldn't turn off cancel out)
                            var d = dark[v].Colour[at];
                            sumR += (double)c.r - d.r;
                            sumG += (double)c.g - d.g;
                            sumB += (double)c.b - d.b;
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
            (kept, keptBefore) = (keptBefore, kept);
            (colour, colourBefore) = (colourBefore, colour);
            // base colour: the mean of the opaque pixels in the place; base_change its distance from the first sample's
            if (wantBase && opaqueN > 0)
            {
                double mr = sumR / opaqueN, mg = sumG / opaqueN, mb = sumB / opaqueN;
                value["base_r"] = mr;
                value["base_g"] = mg;
                value["base_b"] = mb;
                if (!firstBaseSet)
                {
                    firstBaseSet = true;
                    firstR = mr;
                    firstG = mg;
                    firstB = mb;
                }
                value["base_change"] = Math.Sqrt((mr - firstR) * (mr - firstR) + (mg - firstG) * (mg - firstG) + (mb - firstB) * (mb - firstB));
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
            // a line from `from` to `to`: what is drawn within `radius` of it, seen from two sides square to it
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
                    Position = mid - look * (r + DrawnRender.Back), Rotation = Quaternion.LookRotation(look, look == side ? other : side),
                    Width = length + 2f * r + 0.2f, Far = DrawnRender.Back + 2.02f * r,
                });
            const int n = LineSize;
            if (show.Count > 0 && !DrawnRender.Render(show, views, n, DrawnLight.White, true, lit)) return null;
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
                        var c = image.Colour[at];
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
                        else if (Find.Luminance(c.r, c.g, c.b) > Faint)
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
