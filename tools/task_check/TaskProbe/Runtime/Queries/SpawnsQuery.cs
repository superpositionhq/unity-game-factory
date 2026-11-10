// spawns: objects carrying a component (its type, a base type or an interface, as an object select's `component`) that
// appeared (became active in the hierarchy) or went (were destroyed or deactivated), counted every frame since the play's
// clock started (contract section 3, "spawns"); cumulative, the checker differences them. Unity raises no event when an
// object is made, so the objects are compared frame to frame: objects there when the clock starts aren't spawned; a
// pooled object counts each time it comes and goes; an object that comes and goes within one frame isn't seen; a scene
// loaded or unloaded during the play brings and takes its objects; an object given the component counts as one that
// appeared.
// "value": {"spawned", "destroyed"} | null when no component can be of that type.
using System;
using System.Collections.Generic;
using UnityEngine;

namespace TaskProbe
{
    [ProbeQuery("spawns")]
    public sealed class SpawnsQuery : Query
    {
        string type;
        readonly List<Component> found = new List<Component>();
        HashSet<int> before, now = new HashSet<int>();
        int spawned, destroyed;

        public override void Load()
        {
            type = Sel.Text(Def, "component");
            if (type == null) Probe.Error(Kind + " " + Id + ": no component named");
            else if (!Reflect.NamesComponent(type))
            {
                Probe.Error(Kind + " " + Id + ": no component type " + type);
                type = null;
            }
        }

        public override void Frame(float dt) => Count();

        void Count()
        {
            if (type == null) return;
            found.Clear();
            Find.Components(type, false, found);
            now.Clear();
            foreach (var c in found) now.Add(c.gameObject.GetInstanceID());
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
