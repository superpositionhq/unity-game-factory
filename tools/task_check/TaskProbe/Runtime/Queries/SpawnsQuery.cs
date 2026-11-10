// spawns: objects carrying a component that appeared (became active, or were made active) or went (were destroyed or
// deactivated), counted every frame since the play's clock started (contract section 3, "spawns"); cumulative, the
// checker differences them. Objects there when the clock starts aren't counted as spawned. A pooled object that is
// deactivated and reused counts each time it comes and goes.
// "value": {"spawned", "destroyed"} | null when the component type is unknown.
using System;
using System.Collections.Generic;
using UnityEngine;

namespace TaskProbe
{
    [ProbeQuery("spawns")]
    public sealed class SpawnsQuery : Query
    {
        Type type;
        HashSet<int> before, now = new HashSet<int>();
        int spawned, destroyed;

        public override void Load()
        {
            var name = Json.Str(Def, "component");
            type = Reflect.TypeNamed(name);
            if (type == null || !typeof(Component).IsAssignableFrom(type))
            {
                Probe.Error("spawns: no component type " + (name ?? "(none)"));
                type = null;
            }
        }

        public override void Frame(float dt) => Count();

        void Count()
        {
            if (type == null) return;
            now.Clear();
            foreach (var o in UnityEngine.Object.FindObjectsByType(type, FindObjectsInactive.Exclude, FindObjectsSortMode.None))
                if (o is Component c && c != null && !Probe.IsOwn(c.gameObject)) now.Add(c.gameObject.GetInstanceID());
            if (before == null)
            {
                before = new HashSet<int>(now);  // the clock's first frame: what is there already
                return;
            }
            foreach (var id in now)
                if (!before.Contains(id)) spawned++;
            foreach (var id in before)
                if (!now.Contains(id)) destroyed++;
            var swap = before;
            before = now;
            now = swap;
        }

        public override void Sample(double t, Dictionary<string, object> sample)
        {
            if (type == null) { sample["value"] = null; return; }
            // this frame's own comings and goings (after the game's scripts) count now, not next frame
            Count();
            sample["value"] = new Dictionary<string, object>(StringComparer.Ordinal) { ["spawned"] = (double)spawned, ["destroyed"] = (double)destroyed };
        }
    }
}
