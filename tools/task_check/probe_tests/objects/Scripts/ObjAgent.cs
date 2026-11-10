using System.Collections.Generic;
using UnityEngine;
using UnityEngine.AI;

namespace ProbeTests.Objects
{
    // Walks its NavMeshAgent to `goal` on a NavMesh built from `pad` (a box) at the start, with the engine's own builder:
    // no package needed. The agent starts disabled and is enabled once its NavMesh is there.
    public class ObjAgent : MonoBehaviour
    {
        public Transform pad;
        public Vector3 goal;

        void Start()
        {
            var source = new NavMeshBuildSource
            {
                shape = NavMeshBuildSourceShape.Box, size = Vector3.one, transform = pad.localToWorldMatrix, area = 0,
            };
            var data = NavMeshBuilder.BuildNavMeshData(NavMesh.GetSettingsByID(0), new List<NavMeshBuildSource> { source },
                new Bounds(pad.position, pad.lossyScale + Vector3.one * 4f), Vector3.zero, Quaternion.identity);
            NavMesh.AddNavMeshData(data);
            var agent = GetComponent<NavMeshAgent>();
            agent.enabled = true;
            agent.SetDestination(goal);
        }
    }
}
