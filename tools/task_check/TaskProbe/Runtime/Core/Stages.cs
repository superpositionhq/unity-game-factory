// The stages of a contact (contract section 4, docs/task-probes.md 1.4): what a play does to set up a blow, a shot or
// a hit taken at a time it knows. An object pinned where the player's own blow lands (held at its place while its own
// logic runs on), damage dealt through the game's own damage entry (the game contract's IDamageable.TakeDamage, found
// by reflection), and a property the task's start names written. Each takes the match of its select nearest to the
// player. A stage nothing takes is a miss the play lists (probe.json inputs_missed).
using System;
using System.Collections.Generic;
using System.Globalization;
using System.Reflection;
using UnityEngine;

namespace TaskProbe
{
    public sealed class Stages
    {
        const string Damageable = "IDamageable", TakeDamage = "TakeDamage";

        sealed class Pinned
        {
            public GameObject Object;
            public Vector3 At;
            public double Until;
        }

        readonly Probe probe;
        readonly List<Pinned> pinned = new List<Pinned>();
        static readonly Dictionary<int, double> Taken = new Dictionary<int, double>();

        public Stages(Probe probe)
        {
            this.probe = probe;
            Taken.Clear();
        }

        /// <summary>What an object's TakeDamage returned for the play's damage stages so far, summed (damage_taken); no
        /// value for an object no stage struck.</summary>
        public static double? DamageTaken(GameObject go) => go != null && Taken.TryGetValue(go.GetInstanceID(), out var sum) ? sum : (double?)null;

        /// <summary>The match of `select` nearest to the player: the player itself for {"player": true}, else never the
        /// player nor anything under it; without a player, the first match in hierarchy order. `all`: every match
        /// that could be it.</summary>
        public GameObject Nearest(Dictionary<string, object> select, string about, List<GameObject> all = null)
        {
            var sel = Sel.Parse(select, about);
            var player = probe.Player;
            if (sel.Player) { if (player != null) all?.Add(player); return player; }
            GameObject best = null;
            var least = float.MaxValue;
            foreach (var go in Find.Objects(sel, int.MaxValue, out _))
            {
                if (player != null && (go == player || go.transform.IsChildOf(player.transform))) continue;
                all?.Add(go);
                var d = player != null ? (go.transform.position - player.transform.position).sqrMagnitude : float.MaxValue;
                if (best == null || d < least) { best = go; least = d; }
            }
            return best;
        }

        // ---------------------------------------------------------------- pin

        /// <summary>{"t", "pin": select, "hold": s, "front": m | "at": point, "offset": [x, y, z]}. An object of a 2D
        /// game (a sprite, a 2D body or collider on it or under it) is never turned, and `front` is along the player's
        /// facing in X. A second pin on an object takes the first's place.</summary>
        public void Pin(Dictionary<string, object> row, double elapsed)
        {
            var t = Json.Num(row, "t", 0.0);
            var go = Nearest(Json.Obj(row, "pin"), "inputs: pin");
            if (go == null) { probe.Missed(t, "pin", "select", "no object but the player matches it"); return; }
            var player = probe.Player;
            var offset = Vector3.zero;
            if (row.TryGetValue("offset", out var o)) Json.TryVec3(o, out offset);
            var at = Json.Obj(row, "at");
            var flat = Flat(go);
            Vector3? spot = null;
            if (at != null)
            {
                if (!Find.Point(at, out var point)) { probe.Missed(t, "pin", "at", "its point doesn't resolve (no object matches it, or no player)"); return; }
                spot = point + offset;
            }
            else if (Json.TryNum(row, "front", out var metres))
            {
                if (player == null) { probe.Missed(t, "pin", "front", "no player to set it ahead of"); return; }
                spot = flat ? Ahead2D(player, go, (float)metres, offset) : Ahead(player, go, (float)metres, offset);
            }
            if (spot.HasValue)
            {
                float? yaw = null;
                if (!flat && player != null)
                {
                    var look = player.transform.position - spot.Value;
                    if (look.x * look.x + look.z * look.z > 1e-4f) yaw = Mathf.Atan2(look.x, look.z) * Mathf.Rad2Deg;
                }
                Inputs.Place(go, spot.Value, yaw);
                var now = go.transform.position;
                if ((now - spot.Value).magnitude > 0.1f)
                {
                    probe.Missed(t, "pin", go.name, FormattableString.Invariant(
                        $"it couldn't be set at ({spot.Value.x:F2}, {spot.Value.y:F2}, {spot.Value.z:F2}): it is at ({now.x:F2}, {now.y:F2}, {now.z:F2})"));
                    return;
                }
            }
            var hold = Math.Min(Math.Max(Json.Num(row, "hold", 0.0), 0.0), 600.0);
            var here = go.transform.position;
            pinned.RemoveAll(p => p.Object == go);
            pinned.Add(new Pinned { Object = go, At = here, Until = elapsed + hold });
            Probe.Log(FormattableString.Invariant($"pinned {go.name} at ({here.x:F2}, {here.y:F2}, {here.z:F2}) for {hold:F1} s"));
        }

        /// <summary>Whether an object is a 2D game's: a SpriteRenderer, a Rigidbody2D or a Collider2D on it or under it.</summary>
        static bool Flat(GameObject go)
        {
            if (go.GetComponentInChildren<SpriteRenderer>(true) != null) return true;
#if TASKPROBE_PHYSICS2D
            if (go.GetComponentInChildren<Rigidbody2D>(true) != null || go.GetComponentInChildren<Collider2D>(true) != null) return true;
#endif
            return false;
        }

        /// <summary>Where a pin sets an object ahead of the player: `front` metres along the player's facing on the level
        /// (plus the offset), at the height above the ground below it that it had.</summary>
        static Vector3 Ahead(GameObject player, GameObject go, float front, Vector3 offset)
        {
            var forward = player.transform.forward;
            forward.y = 0f;
            forward = forward.sqrMagnitude < 1e-6f ? Vector3.forward : forward.normalized;
            var feet = player.transform.position;
            var spot = feet + forward * front + new Vector3(offset.x, 0f, offset.z);
            var here = go.transform.position;
            var above = Ground(here, player, go, out var was) ? here.y - was : here.y - feet.y;
            var y = Ground(new Vector3(spot.x, feet.y, spot.z), player, go, out var now) ? now + above : feet.y + above;
            return new Vector3(spot.x, y + offset.y, spot.z);
        }

        /// <summary>The same in a 2D game: `front` metres along the player's facing in X (its right, the other way when
        /// its scale in X is negative or its sprite is flipped), at the height above the ground below it that it had,
        /// its own depth kept.</summary>
        static Vector3 Ahead2D(GameObject player, GameObject go, float front, Vector3 offset)
        {
            var facing = player.transform.right.x >= 0f ? 1f : -1f;
            if (player.transform.lossyScale.x < 0f) facing = -facing;
            var sprite = player.GetComponentInChildren<SpriteRenderer>();
            if (sprite != null && sprite.flipX) facing = -facing;
            var feet = player.transform.position;
            var x = feet.x + facing * front + offset.x;
            var here = go.transform.position;
            var above = Ground2D(here, player, go, out var was) ? here.y - was : here.y - feet.y;
            var y = Ground2D(new Vector3(x, feet.y, here.z), player, go, out var now) ? now + above : feet.y + above;
            return new Vector3(x, y + offset.y, here.z + offset.z);
        }

        static bool Ground2D(Vector3 at, GameObject player, GameObject go, out float height)
        {
            height = 0f;
#if TASKPROBE_PHYSICS2D
            var found = false;
            foreach (var hit in Physics2D.RaycastAll(new Vector2(at.x, at.y + 5f), Vector2.down, 55f))
            {
                if (hit.collider == null || hit.collider.isTrigger) continue;
                var t = hit.collider.transform;
                if (t.IsChildOf(player.transform) || t.IsChildOf(go.transform)) continue;
                if (!found || hit.point.y > height) { height = hit.point.y; found = true; }
            }
            return found;
#else
            return false;
#endif
        }

        /// <summary>The height of the ground under a place: the nearest solid collider below 5 m above it that is neither
        /// the player's nor the pinned object's; false with none within 50 m, or in a project without Physics.</summary>
        static bool Ground(Vector3 at, GameObject player, GameObject go, out float height)
        {
            height = 0f;
#if TASKPROBE_PHYSICS
            var found = false;
            foreach (var hit in Physics.RaycastAll(at + Vector3.up * 5f, Vector3.down, 55f, ~0, QueryTriggerInteraction.Ignore))
            {
                var t = hit.collider.transform;
                if (t.IsChildOf(player.transform) || t.IsChildOf(go.transform)) continue;
                if (!found || hit.point.y > height) { height = hit.point.y; found = true; }
            }
            return found;
#else
            return false;
#endif
        }

        /// <summary>After the frame's game logic: every pinned object back at its place, its movement stopped (its own
        /// logic, turning, animation and attacks run on).</summary>
        public void Hold(double elapsed)
        {
            for (var i = pinned.Count - 1; i >= 0; i--)
            {
                var p = pinned[i];
                if (p.Object == null || elapsed >= p.Until) { pinned.RemoveAt(i); continue; }
                if ((p.Object.transform.position - p.At).sqrMagnitude > 1e-6f) Inputs.Place(p.Object, p.At, null);
                else Inputs.Still(p.Object);
            }
        }

        // ---------------------------------------------------------------- damage

        /// <summary>{"t", "damage": points, "to": select, "from": select}: the game's own damage entry, as its own
        /// attacks call it: TakeDamage(float amount, GameObject source) of the IDamageable on the target (itself, else
        /// an object above it, else one under it).</summary>
        public void Damage(Dictionary<string, object> row)
        {
            var t = Json.Num(row, "t", 0.0);
            var amount = Json.Num(row, "damage", 0.0);
            var target = Nearest(Json.Obj(row, "to"), "inputs: damage to");
            if (target == null) { probe.Missed(t, "damage", "to", "no object matches it"); return; }
            var player = probe.Player;
            GameObject from;
            if (Json.Obj(row, "from") is Dictionary<string, object> select)
            {
                from = Nearest(select, "inputs: damage from");
                if (from == null) { probe.Missed(t, "damage", "from", "no object matches it"); return; }
            }
            else if (target == player) from = Nearest(new Dictionary<string, object> { ["component"] = Damageable }, null);
            else from = player;
            var part = Entry(target, out var method, out var named);
            if (part == null)
            {
                probe.Missed(t, "damage", target.name, named
                    ? "its " + Damageable + " has no " + TakeDamage + "(float, GameObject) (parameters after those two must be optional)"
                    : "it has no component implementing " + Damageable + ": the game takes no damage through the game contract's entry");
                return;
            }
            // (amount, source), and its own default for every optional parameter after them
            var parameters = method.GetParameters();
            var arguments = new object[parameters.Length];
            arguments[0] = (float)amount;
            arguments[1] = from;
            for (var i = 2; i < parameters.Length; i++) arguments[i] = parameters[i].DefaultValue;
            object returned;
            try { returned = method.Invoke(part, arguments); }
            catch (Exception e)
            {
                probe.Missed(t, "damage", target.name, TakeDamage + " threw " + (e.InnerException ?? e).GetType().Name);
                Probe.Log((e.InnerException ?? e).ToString());
                return;
            }
            // the contract's TakeDamage returns the damage applied, a number: one that returns none says nothing of
            // what the hit did, so the object's damage_taken keeps no value for it
            var numeric = returned != null && returned.GetType().IsPrimitive && !(returned is bool) && !(returned is char);
            var took = numeric ? Convert.ToDouble(returned, CultureInfo.InvariantCulture) : double.NaN;
            if (double.IsNaN(took) || double.IsInfinity(took))
            {
                Probe.Log(FormattableString.Invariant($"{amount:F1} damage to {target.name} from {(from != null ? from.name : "nothing")}: its {TakeDamage} returned no number, so its damage_taken has no value"));
                return;
            }
            Taken[target.GetInstanceID()] = (DamageTaken(target) ?? 0.0) + took;
            Probe.Log(FormattableString.Invariant($"{amount:F1} damage to {target.name} from {(from != null ? from.name : "nothing")}: it took {took:F1}"));
        }

        /// <summary>The damage entry of `target`: a component whose type implements an interface named IDamageable that
        /// declares TakeDamage(float, GameObject), with nothing or only optional parameters after those two, on the
        /// object, else above it, else under it. `named`: a component implements an IDamageable, whatever it declares.</summary>
        static Component Entry(GameObject target, out MethodInfo method, out bool named)
        {
            method = null;
            named = false;
            var candidates = new List<Component>();
            for (var t = target.transform; t != null; t = t.parent) candidates.AddRange(t.GetComponents<Component>());
            candidates.AddRange(target.GetComponentsInChildren<Component>(false));
            foreach (var c in candidates)
            {
                if (c == null || Find.IsOwn(c)) continue;
                foreach (var face in c.GetType().GetInterfaces())
                {
                    if (face.Name != Damageable) continue;
                    named = true;
                    foreach (var m in face.GetMethods())
                    {
                        var p = m.GetParameters();
                        if (m.Name != TakeDamage || p.Length < 2 || p[0].ParameterType != typeof(float) || p[1].ParameterType != typeof(GameObject)) continue;
                        var optional = true;
                        for (var i = 2; i < p.Length; i++) optional &= p[i].HasDefaultValue;
                        if (!optional) continue;
                        method = m;
                        return c;
                    }
                }
            }
            return null;
        }

        // ---------------------------------------------------------------- set

        /// <summary>{"t", "set": path, "on": select, "value": v, "all": bool}: the member a prop: field of that path
        /// reads, written on the nearest match, or on every match.</summary>
        public void Set(Dictionary<string, object> row)
        {
            var t = Json.Num(row, "t", 0.0);
            var path = Json.Str(row, "set", "");
            var all = new List<GameObject>();
            var nearest = Nearest(Json.Obj(row, "on"), "inputs: set on", all);
            if (nearest == null) { probe.Missed(t, "set", path, "no object matches its select"); return; }
            if (!Json.Bool(row, "all")) { all.Clear(); all.Add(nearest); }
            row.TryGetValue("value", out var value);
            int done = 0;
            string why = null;
            foreach (var go in all)
            {
                var took = Reflect.Write(go, path, value, out var failed);
                if (took) done++; else why = failed;
                Probe.Log("set " + path + " on " + go.name + ": " + (took ? "done" : failed));
            }
            if (done < all.Count) probe.Missed(t, "set", path, (all.Count - done) + " of " + all.Count + " objects didn't take it: " + why);
        }
    }
}
