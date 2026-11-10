using System;
using UnityEngine;

namespace ProbeTests.Select
{
    /// <summary>A crowd for the cost plays: with the player argument -selCrowd N (default 3000), N objects made when the
    /// scene wakes, in trees of 21 (a root, 4 children, 16 grandchildren); every 10th carries SelMark.</summary>
    public sealed class SelCrowd : MonoBehaviour
    {
        public int made;

        void Awake()
        {
            var n = 3000;
            var args = Environment.GetCommandLineArgs();
            var at = Array.IndexOf(args, "-selCrowd");
            if (at >= 0 && at + 1 < args.Length) int.TryParse(args[at + 1], out n);
            while (made < n)
            {
                var root = Make("Crowd_" + made, null);
                for (var i = 0; i < 4 && made < n; i++)
                {
                    var child = Make("Kid_" + made, root.transform);
                    for (var j = 0; j < 4 && made < n; j++) Make("Grandkid_" + made, child.transform);
                }
            }
        }

        GameObject Make(string name, Transform parent)
        {
            var go = new GameObject(name);
            go.transform.SetParent(parent, false);
            go.transform.localPosition = new Vector3(made % 100, 0f, made / 100);
            if (made % 10 == 0) go.AddComponent<SelMark>();
            made++;
            return go;
        }
    }
}
