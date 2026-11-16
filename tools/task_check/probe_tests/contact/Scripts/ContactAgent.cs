using System.Collections.Generic;
using UnityEngine;
using UnityEngine.AI;

namespace ProbeTests.Contact
{
    /// <summary>Walks on a NavMesh it bakes itself over the scene's colliders when the scene starts, towards a point far
    /// along z.</summary>
    public sealed class ContactAgent : MonoBehaviour
    {
        void Start()
        {
            var bounds = new Bounds(Vector3.zero, new Vector3(150f, 10f, 150f));
            var sources = new List<NavMeshBuildSource>();
            NavMeshBuilder.CollectSources(bounds, 1 << LayerMask.NameToLayer("Water"), NavMeshCollectGeometry.PhysicsColliders, 0, new List<NavMeshBuildMarkup>(), sources);
            NavMesh.AddNavMeshData(NavMeshBuilder.BuildNavMeshData(NavMesh.GetSettingsByID(0), sources, bounds, Vector3.zero, Quaternion.identity));
            var agent = GetComponent<NavMeshAgent>();
            agent.enabled = true;
            agent.SetDestination(new Vector3(transform.position.x, 0f, 60f));
        }
    }
}
