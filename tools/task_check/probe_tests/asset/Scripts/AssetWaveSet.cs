// A ScriptableObject of the asset family with fields of every plain kind, and data that marks itself changed whenever
// it loads (OnValidate), as some games' data does: the editor pass must still write nothing back.
using System;
using System.Collections.Generic;
using UnityEngine;

namespace ProbeTests.Asset
{
    public enum AssetDifficulty { Easy = 1, Normal = 2, Hard = 4 }

    [Serializable]
    public class AssetWave
    {
        public int count;
        public float delay;
    }

    public class AssetWaveSet : ScriptableObject
    {
        public int level = 3;
        public float speed = 2.5f;
        public string title = "Night";
        public bool boss = true;
        public AssetDifficulty difficulty = AssetDifficulty.Hard;
        public List<AssetWave> waves = new List<AssetWave>();
        public Color tint = new Color(0.1f, 0.2f, 0.3f, 1f);
        public Material skin;
        public Material none;
        public float nan = float.NaN;
        public float inf = float.PositiveInfinity;
        public AnimationCurve curve = new AnimationCurve(new Keyframe(0f, 0f), new Keyframe(0.5f, 2f), new Keyframe(1f, 1f));
        public int loads;
        [SerializeField] int secret = 7;

        public int Secret => secret;

        void OnValidate()
        {
            loads++;
            Debug.Log("ASSET loaded " + name);
#if UNITY_EDITOR
            UnityEditor.EditorUtility.SetDirty(this);
#endif
        }
    }
}
