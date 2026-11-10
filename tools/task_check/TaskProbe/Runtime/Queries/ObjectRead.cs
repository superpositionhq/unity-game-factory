// What the objects and components queries read of a GameObject or a component (contract section 3), and the per-query
// state some fields need: the previous sample's places (speed), the first-seen state of each part (changed,
// bounds_change, pose_change) and the turn summed frame by frame (spin).
using System;
using System.Collections.Generic;
using UnityEngine;

namespace TaskProbe
{
    public static class ObjectRead
    {
        /// <summary>A row's "class" for an object (for logs): its first script's type, else its first Behaviour or
        /// Renderer (Light, Camera, MeshRenderer...), else its first other component, else "GameObject".</summary>
        public static string ClassOf(GameObject go)
        {
            string behaviour = null, other = null;
            foreach (var c in go.GetComponents<Component>())
            {
                if (c == null || c is Transform || c is MeshFilter) continue;
                if (c is MonoBehaviour) return c.GetType().Name;
                if (behaviour == null && (c is Behaviour || c is Renderer)) behaviour = c.GetType().Name;
                other ??= c.GetType().Name;
            }
            return behaviour ?? other ?? "GameObject";
        }

        /// <summary>The renderers whose bounds make an object's geometry (extent_, spread): drawn, not an effect (a
        /// particle system or trail spans where its particles went), with a box.</summary>
        static bool Geometry(Renderer r)
        {
            if (!Find.Drawn(r)) return false;
#if TASKPROBE_PARTICLES
            if (r is ParticleSystemRenderer) return false;
#endif
            if (r is TrailRenderer) return false;
            return r.bounds.extents.sqrMagnitude > 1e-12f;
        }

        /// <summary>The world-aligned union of an object's drawn renderers' bounds, descendants included; false when it
        /// draws nothing.</summary>
        public static bool DrawnBox(GameObject go, out Bounds box)
        {
            box = new Bounds();
            var have = false;
            foreach (var r in go.GetComponentsInChildren<Renderer>(false))
            {
                if (!Geometry(r)) continue;
                if (have) box.Encapsulate(r.bounds); else { box = r.bounds; have = true; }
            }
            return have;
        }

        /// <summary>spread: the diagonal of the box around its drawn renderers' bounds centres, a skinned mesh whose bones
        /// carry several Rigidbodies (a ragdoll) by each body's place; 0 with one, null with none. A whole object reads
        /// its parts' own layout; one broken into pieces that fell or flew apart reads more.</summary>
        public static object Spread(GameObject go)
        {
            var have = false;
            var box = new Bounds();
            foreach (var r in go.GetComponentsInChildren<Renderer>(false))
            {
                if (!Geometry(r)) continue;
                var bodies = 0;
#if TASKPROBE_PHYSICS
                // a ragdoll is one skinned mesh over bones that carry the bodies: its bounds stay one box however far
                // its limbs fly
                if (r is SkinnedMeshRenderer skinned) bodies = Bodies(skinned, ref box, ref have);
#endif
                if (bodies > 0) continue;
                if (have) box.Encapsulate(r.bounds.center); else { box = new Bounds(r.bounds.center, Vector3.zero); have = true; }
            }
            return have ? (object)(double)box.size.magnitude : null;
        }

#if TASKPROBE_PHYSICS
        static int Bodies(SkinnedMeshRenderer skinned, ref Bounds box, ref bool have)
        {
            var bones = skinned.bones;
            var found = 0;
            foreach (var bone in bones)
                if (bone != null && bone.gameObject.activeInHierarchy && bone.TryGetComponent<Rigidbody>(out _)) found++;
            if (found < 2) return 0;  // one body is no layout: the mesh counts by its bounds centre
            foreach (var bone in bones)
            {
                if (bone == null || !bone.gameObject.activeInHierarchy || !bone.TryGetComponent<Rigidbody>(out _)) continue;
                if (have) box.Encapsulate(bone.position); else { box = new Bounds(bone.position, Vector3.zero); have = true; }
            }
            return found;
        }
#endif

        /// <summary>hidden: inactive, or it has renderers and none is drawn.</summary>
        public static bool Hidden(GameObject go)
        {
            if (!go.activeInHierarchy) return true;
            var any = false;
            foreach (var r in go.GetComponentsInChildren<Renderer>(true))
            {
                any = true;
                if (Find.Drawn(r)) return false;
            }
            return any;
        }

        /// <summary>The velocity an object reports of itself: a non-kinematic Rigidbody's or a Dynamic Rigidbody2D's,
        /// else an enabled CharacterController's or NavMeshAgent's. False when it has none of them (its speed is then
        /// how far it moved between samples).</summary>
        public static bool OwnVelocity(GameObject go, out Vector3 v)
        {
            v = Vector3.zero;
#if TASKPROBE_PHYSICS
            if (go.TryGetComponent<Rigidbody>(out var body) && !body.isKinematic) { v = body.linearVelocity; return true; }
#endif
#if TASKPROBE_PHYSICS2D
            if (go.TryGetComponent<Rigidbody2D>(out var body2) && body2.bodyType == RigidbodyType2D.Dynamic && body2.simulated)
            {
                v = body2.linearVelocity;
                return true;
            }
#endif
#if TASKPROBE_PHYSICS
            if (go.TryGetComponent<CharacterController>(out var cc) && cc.enabled) { v = cc.velocity; return true; }
#endif
#if TASKPROBE_AI
            if (go.TryGetComponent<UnityEngine.AI.NavMeshAgent>(out var agent) && agent.enabled && agent.isOnNavMesh) { v = agent.velocity; return true; }
#endif
            return false;
        }

        // ---------------------------------------------------------------- Parts by name (rel_yaw:, world_yaw:, forward:, bone:)

#if TASKPROBE_ANIMATION
        static readonly string[] HumanNames = Enum.GetNames(typeof(HumanBodyBones));
        static readonly HumanBodyBones[] HumanBones = (HumanBodyBones[])Enum.GetValues(typeof(HumanBodyBones));
#endif

        /// <summary>bone:&lt;Component&gt;.&lt;Bone&gt;.x|y|z: the world position of a bone of a SkinnedMeshRenderer, a human
        /// bone of an Animator, or a descendant transform of that name (under the component, else under the object).</summary>
        public static object Bone(GameObject go, string path)
        {
            var first = path.IndexOf('.');
            var last = path.LastIndexOf('.');
            if (first <= 0 || last <= first) return null;
            var componentName = path.Substring(0, first);
            var boneName = path.Substring(first + 1, last - first - 1);
            var axis = path.Substring(last + 1);
            var component = Reflect.ComponentNamed(go, componentName);
            if (component == null) return null;
            Transform bone = null;
            if (component is SkinnedMeshRenderer smr)
                foreach (var b in smr.bones)
                    if (b != null && b.name == boneName) { bone = b; break; }
#if TASKPROBE_ANIMATION
            if (bone == null && component is Animator animator && animator.isHuman)
            {
                // a human bone by its name only (Enum.TryParse would take "5" or "Hips, Spine" too, and an id out of
                // range throws)
                var i = Array.FindIndex(HumanNames, n => string.Equals(n, boneName, StringComparison.OrdinalIgnoreCase));
                if (i >= 0 && HumanBones[i] != HumanBodyBones.LastBone) bone = animator.GetBoneTransform(HumanBones[i]);
            }
#endif
            if (bone == null) bone = Descendant(component.transform, boneName) ?? Descendant(go.transform, boneName);
            if (bone == null) return null;
            return Axis(bone.position, axis);
        }

        static Transform Descendant(Transform root, string name)
        {
            foreach (var t in root.GetComponentsInChildren<Transform>(true))
                if (t.name == name) return t;
            return null;
        }

        public static object Axis(Vector3 v, string axis)
        {
            switch (axis)
            {
                case "x": return (double)v.x;
                case "y": return (double)v.y;
                case "z": return (double)v.z;
            }
            return null;
        }

        /// <summary>The forward of a Part: for a Light, the way its light travels (a Light shines along its forward).</summary>
        public static object Forward(GameObject go, string path)
        {
            var dot = path.LastIndexOf('.');
            if (dot <= 0) return null;
            var part = Reflect.Part(go, path.Substring(0, dot));
            return part != null ? Axis(part.forward, path.Substring(dot + 1)) : null;
        }

        // ---------------------------------------------------------------- Animator

#if TASKPROBE_ANIMATION
        static Animator AnimatorOf(GameObject go)
        {
            var a = go.GetComponentInChildren<Animator>(false);
            return a != null && a.isActiveAndEnabled && a.runtimeAnimatorController != null ? a : null;
        }
#endif

        /// <summary>anim:&lt;Parameter&gt;: a float, int or bool parameter of its Animator (bools 1/0).</summary>
        public static object AnimParameter(GameObject go, string name)
        {
#if TASKPROBE_ANIMATION
            var a = AnimatorOf(go);
            if (a == null) return null;
            foreach (var p in a.parameters)
            {
                if (p.name != name) continue;
                switch (p.type)
                {
                    case AnimatorControllerParameterType.Float: return (double)a.GetFloat(p.nameHash);
                    case AnimatorControllerParameterType.Int: return (double)a.GetInteger(p.nameHash);
                    case AnimatorControllerParameterType.Bool: return a.GetBool(p.nameHash) ? 1.0 : 0.0;
                    default: return null;  // a trigger has no value to read
                }
            }
#endif
            return null;
        }

        /// <summary>clip: the name of its Animator's current clip on layer 0 (the heaviest), through `match`.</summary>
        public static object Clip(GameObject go)
        {
#if TASKPROBE_ANIMATION
            var a = AnimatorOf(go);
            if (a == null || a.layerCount == 0) return null;
            var clips = a.GetCurrentAnimatorClipInfo(0);
            AnimationClip best = null;
            var weight = -1f;
            foreach (var c in clips)
                if (c.clip != null && c.weight > weight) { best = c.clip; weight = c.weight; }
            return best != null ? best.name : null;
#else
            return null;
#endif
        }
    }

    /// <summary>speed by places: where each thing was at this query's previous sample.</summary>
    public sealed class Places
    {
        Dictionary<int, Vector3> before = new Dictionary<int, Vector3>(), now = new Dictionary<int, Vector3>();
        double lastT = double.NaN, t;

        public void Begin(double time)
        {
            t = time;
            now.Clear();
        }

        /// <summary>The speed of one thing at `place`: its own velocity when it reports one that isn't zero, else how far
        /// it moved since the previous sample over that time; with no own velocity and no previous place, null.
        /// `velocity`: the vector used (facing_vs_velocity).</summary>
        public double? Speed(int key, Vector3 place, bool hasOwn, Vector3 own, out Vector3 velocity)
        {
            now[key] = place;
            velocity = own;
            if (hasOwn && own.sqrMagnitude > 1e-8f) return own.magnitude;
            if (before.TryGetValue(key, out var was) && t > lastT)
            {
                velocity = (place - was) / (float)(t - lastT);
                return velocity.magnitude;
            }
            return hasOwn ? 0.0 : (double?)null;
        }

        public void End()
        {
            var swap = before;
            before = now;
            now = swap;
            lastT = t;
        }
    }

    /// <summary>spin: how far each followed transform turned in the world, summed frame by frame since the previous
    /// sample. Only what a sample read is followed until the next one.</summary>
    public sealed class Spins
    {
        sealed class Track
        {
            public Transform T;
            public Quaternion Last;
            public double Angle, Time;
        }

        readonly Dictionary<int, Track> tracks = new Dictionary<int, Track>();
        readonly Dictionary<int, Transform> read = new Dictionary<int, Transform>();
        readonly List<int> gone = new List<int>();

        public void Frame(float dt)
        {
            gone.Clear();
            foreach (var kv in tracks)
            {
                var track = kv.Value;
                if (track.T == null) { gone.Add(kv.Key); continue; }
                var q = track.T.rotation;
                track.Angle += Quaternion.Angle(track.Last, q);
                track.Last = q;
                track.Time += dt;
            }
            foreach (var key in gone) tracks.Remove(key);
        }

        /// <summary>deg/s of `t` since the previous sample; the first sample it is seen in has no value, unless it
        /// simulates physics: then its body's angular velocity.</summary>
        public double? Of(Transform t)
        {
            var key = t.GetInstanceID();
            read[key] = t;
            if (tracks.TryGetValue(key, out var track) && track.Time > 0.0)
            {
                // the turn of this frame (after the frame hook ran) counts too
                var q = t.rotation;
                track.Angle += Quaternion.Angle(track.Last, q);
                track.Last = q;
                return track.Angle / track.Time;
            }
#if TASKPROBE_PHYSICS
            if (t.TryGetComponent<Rigidbody>(out var body) && !body.isKinematic) return body.angularVelocity.magnitude * Mathf.Rad2Deg;
#endif
#if TASKPROBE_PHYSICS2D
            if (t.TryGetComponent<Rigidbody2D>(out var body2) && body2.bodyType == RigidbodyType2D.Dynamic && body2.simulated)
                return (double)Mathf.Abs(body2.angularVelocity);  // deg/s already
#endif
            return null;
        }

        /// <summary>After a sample: keep following what it read, from now.</summary>
        public void EndSample()
        {
            gone.Clear();
            foreach (var key in tracks.Keys)
                if (!read.ContainsKey(key)) gone.Add(key);
            foreach (var key in gone) tracks.Remove(key);
            foreach (var kv in read)
            {
                if (kv.Value == null) continue;
                if (!tracks.TryGetValue(kv.Key, out var track)) tracks[kv.Key] = track = new Track { T = kv.Value };
                track.Last = kv.Value.rotation;
                track.Angle = 0.0;
                track.Time = 0.0;
            }
            read.Clear();
        }
    }

    /// <summary>changed, bounds_change, pose_change: each part against the first sample it was seen in.</summary>
    public sealed class Changes
    {
        public const float Bounds = 0.01f;  // m: changed when a part's world, or a skinned mesh's local, bounds moved more
        public const float Pose = 0.05f;    // m: changed when a skinned mesh's bones moved more than this in all

        public static bool IsField(string f) => f == "changed" || f == "bounds_change" || f == "pose_change";

        sealed class State
        {
            public bool Drawn, Skinned;
            public UnityEngine.Bounds World, Local;
            public Vector3[] Bones;
        }

        public struct Reading
        {
            public bool Changed, Any, HasPose;
            public double BoundsMove, PoseMove;

            public object Field(string f)
            {
                if (f == "changed") return Changed ? 1.0 : 0.0;
                if (f == "bounds_change") return Any ? (object)BoundsMove : null;
                if (f == "pose_change") return HasPose ? (object)PoseMove : null;
                return null;
            }
        }

        readonly Dictionary<int, State> firsts = new Dictionary<int, State>();
        readonly Dictionary<int, List<int>> firstParts = new Dictionary<int, List<int>>();

        static State Now(Renderer r)
        {
            var s = new State { Drawn = Find.Drawn(r), World = r.bounds };
            if (r is SkinnedMeshRenderer smr)
            {
                s.Skinned = true;
                s.Local = smr.localBounds;
                var bones = smr.bones;
                s.Bones = new Vector3[bones.Length];
                // each bone in the mesh's own space: a pose that moves reads whatever the object itself does
                for (var i = 0; i < bones.Length; i++)
                    s.Bones[i] = bones[i] != null ? smr.transform.InverseTransformPoint(bones[i].position) : Vector3.zero;
            }
            return s;
        }

        static double BoxMove(UnityEngine.Bounds a, UnityEngine.Bounds b)
        {
            var lo = a.min - b.min;
            var hi = a.max - b.max;
            return Mathf.Max(Mathf.Max(Mathf.Abs(lo.x), Mathf.Abs(lo.y), Mathf.Abs(lo.z)), Mathf.Max(Mathf.Abs(hi.x), Mathf.Abs(hi.y), Mathf.Abs(hi.z)));
        }

        static Reading PartChange(State first, State now)
        {
            var c = new Reading { Any = true };
            c.BoundsMove = BoxMove(first.World, now.World);
            c.Changed = first.Drawn != now.Drawn || c.BoundsMove > Bounds;
            if (first.Skinned && now.Skinned)
            {
                c.HasPose = true;
                var n = Math.Min(first.Bones.Length, now.Bones.Length);
                for (var i = 0; i < n; i++) c.PoseMove += Vector3.Distance(first.Bones[i], now.Bones[i]);
                c.Changed |= first.Bones.Length != now.Bones.Length || c.PoseMove > Pose || BoxMove(first.Local, now.Local) > Bounds;
            }
            return c;
        }

        /// <summary>One renderer (a components row).</summary>
        public Reading Part(Renderer r)
        {
            var key = r.GetInstanceID();
            var now = Now(r);
            if (firsts.TryGetValue(key, out var first)) return PartChange(first, now);
            firsts[key] = now;
            return new Reading { Any = true, HasPose = now.Skinned };
        }

        /// <summary>An object: changed when any part changed, a part drawn then is gone, or a part not there then is
        /// drawn now; bounds_change its parts' largest, pose_change its skinned meshes' summed.</summary>
        public Reading Object(GameObject go)
        {
            var parts = new List<Renderer>();
            Find.MeshParts(go, parts);
            var key = go.GetInstanceID();
            var seen = firstParts.TryGetValue(key, out var before);
            var keys = new List<int>(parts.Count);
            var c = new Reading();
            foreach (var r in parts)
            {
                var id = r.GetInstanceID();
                keys.Add(id);
                var now = Now(r);
                if (!seen)
                {
                    firsts[id] = now;
                    c.Any = true;
                    c.HasPose |= now.Skinned;
                    continue;
                }
                if (!before.Contains(id) || !firsts.TryGetValue(id, out var first))
                {
                    c.Changed |= now.Drawn;  // a part added since, drawn
                    continue;
                }
                var p = PartChange(first, now);
                c.Changed |= p.Changed;
                c.Any = true;
                c.BoundsMove = Math.Max(c.BoundsMove, p.BoundsMove);
                c.HasPose |= p.HasPose;
                c.PoseMove += p.PoseMove;
            }
            if (!seen)
            {
                firstParts[key] = keys;
                return c;
            }
            foreach (var id in before)
                if (!keys.Contains(id) && firsts.TryGetValue(id, out var first) && first.Drawn)
                    c.Changed = true;  // a part drawn then is gone
            return c;
        }
    }
}
