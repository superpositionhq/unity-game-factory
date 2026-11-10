using UnityEngine;
using UnityEngine.SceneManagement;

namespace ProbeTests.World
{
    /// <summary>The world plays' timeline, in seconds of game time since its first Update (play time minus a frame):
    /// the camera's wall stands from 1.25 to 1.75 s and the camera turns round at 3.25 s; a shot is made every 0.5 s from
    /// 0.25 s (six, each living 0.5 s); the pool's objects come and go at 0.4, 1.4 and 2.4 s; at 2.1 s a shot is made and
    /// destroyed in one frame; at 2.6 s `plain` gets a WldShot; at 3.1 s `idle` (a WldShot from the start, disabled) is
    /// destroyed; WorldSide (two shots) is loaded additively at 3.6 s and unloaded at 4.1 s.</summary>
    public sealed class WldDirector : MonoBehaviour
    {
        public GameObject wall, template, plain, idle;
        public Transform view;
        public GameObject[] pool;
        float clock;
        int shots, step;

        void Update()
        {
            clock += Time.deltaTime;
            wall.SetActive(clock >= 1.25f && clock < 1.75f);
            if (clock >= 3.25f) view.rotation = Quaternion.Euler(0f, 180f, 0f);
            while (shots < 6 && clock >= 0.25f + 0.5f * shots)
            {
                var shot = Instantiate(template);
                shot.GetComponent<WldShot>().life = 0.5f;
                shot.SetActive(true);
                shots++;
            }
            if (step == 0 && clock >= 0.4f) { pool[0].SetActive(true); step++; }
            if (step == 1 && clock >= 1.4f) { pool[0].SetActive(false); pool[1].SetActive(true); step++; }
            if (step == 2 && clock >= 2.1f)
            {
                var flash = Instantiate(template);
                flash.SetActive(true);
                Destroy(flash);
                step++;
            }
            if (step == 3 && clock >= 2.4f) { pool[1].SetActive(false); pool[0].SetActive(true); step++; }
            if (step == 4 && clock >= 2.6f) { plain.AddComponent<WldShot>(); step++; }
            if (step == 5 && clock >= 3.1f) { Destroy(idle); step++; }
            if (step == 6 && clock >= 3.6f)
            {
                SceneManager.LoadScene("Assets/ProbeTests/world/Made/WorldSide.unity", LoadSceneMode.Additive);
                step++;
            }
            if (step == 7 && clock >= 4.1f)
            {
                SceneManager.UnloadSceneAsync("Assets/ProbeTests/world/Made/WorldSide.unity");
                step++;
            }
        }
    }
}
