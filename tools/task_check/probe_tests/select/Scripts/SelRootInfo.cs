using System;
using UnityEngine;
using UnityEngine.SceneManagement;

namespace ProbeTests.Select
{
    /// <summary>Where its object stands, as the player itself sees it, every frame: its sibling index, its place in its
    /// scene's root list (-1 when it isn't a root), its scene's build index and place in SceneManager's list, and the
    /// names of its scene's roots in the order of that list, separated by "|".</summary>
    public sealed class SelRootInfo : MonoBehaviour
    {
        public int sibling, rootIndex = -1, buildIndex, sceneAt = -1;
        public string roots = "";

        void LateUpdate()
        {
            sibling = transform.GetSiblingIndex();
            var scene = gameObject.scene;
            buildIndex = scene.buildIndex;
            var list = scene.GetRootGameObjects();
            rootIndex = transform.parent == null ? Array.IndexOf(list, gameObject) : -1;
            roots = string.Join("|", Array.ConvertAll(list, root => root.name));
            sceneAt = -1;
            for (var i = 0; i < SceneManager.sceneCount; i++)
                if (SceneManager.GetSceneAt(i) == scene) sceneAt = i;
        }
    }
}
