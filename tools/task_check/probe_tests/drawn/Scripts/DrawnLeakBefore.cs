using System.Collections.Generic;
using System.Text;
using UnityEngine;

namespace ProbeTests.Drawn
{
    /// <summary>The state DrawnLeakWatch compares, taken just before the probe's own late update samples; and how often it
    /// changed from one frame to the next (`drifts`): in a scene whose lights, probes and renderers nothing changes, a
    /// change there is something a render left behind that showed only later (an environment the engine built again, a
    /// probe's picture made again). From the third frame: the scene's realtime reflection probe makes its picture in the
    /// first. The first differences go to the player log.</summary>
    [DefaultExecutionOrder(31990)]
    public sealed class DrawnLeakBefore : MonoBehaviour
    {
        public int drifts;
        string last;
        int said;

        void LateUpdate()
        {
            var now = DrawnLeakWatch.State();
            if (last != null && now != last && Time.frameCount > 2)
            {
                drifts++;
                if (said++ < 5)
                {
                    var was = new HashSet<string>(last.Split('\n'));
                    var lines = new StringBuilder("DRAWN DRIFT at frame ").Append(Time.frameCount);
                    foreach (var line in now.Split('\n'))
                        if (!was.Contains(line)) lines.Append("\n  now ").Append(line);
                    Debug.Log(lines.ToString());
                }
            }
            last = now;
            DrawnLeakWatch.Before = now;
        }
    }
}
