// Test data for the asset family: a ScriptableObject with fields of every plain kind.
using System;
using System.Collections.Generic;
using UnityEngine;

namespace AssetTest
{
    public enum Difficulty { Easy, Normal, Hard }

    [Serializable]
    public class Wave
    {
        public int count;
        public float delay;
    }

    [CreateAssetMenu]
    public class WaveSet : ScriptableObject
    {
        public int level = 3;
        public float speed = 2.5f;
        public string title = "Night";
        public bool boss = true;
        public Difficulty difficulty = Difficulty.Hard;
        public List<Wave> waves = new List<Wave>();
        public Color tint = new Color(0.1f, 0.2f, 0.3f, 1f);
        public Material skin;
        public Material none;
        [SerializeField] int secret = 7;
        public int Secret => secret;
    }
}
