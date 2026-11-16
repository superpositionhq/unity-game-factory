using UnityEngine;

namespace ProbeTests.Contact
{
    /// <summary>Moves 1 m/s along x by game time and stands still for six frames of its own, its 60th to its 65th: a hit
    /// stop of the object's own, 0.2 s at the play's 30 frames a second. During the stop a hit's dressing comes and
    /// goes under it: a spark made in the 61st frame and destroyed in the 64th, a number made in the 61st that rises
    /// every frame until the 80th, and `pip`, a part it had from the start, destroyed in the 63rd.</summary>
    public sealed class ContactStutter : MonoBehaviour
    {
        public GameObject pip;
        GameObject spark, number;
        int frame;

        void Update()
        {
            if (frame < 60 || frame > 65) transform.position += Vector3.right * Time.deltaTime;
            if (frame == 61)
            {
                spark = Child("Spark", new Vector3(0f, 1f, 0f));
                number = Child("Number", new Vector3(0f, 2f, 0f));
            }
            if (frame == 63 && pip != null) Destroy(pip);
            if (frame == 64) Destroy(spark);
            if (number != null)
            {
                number.transform.localPosition += Vector3.up * 0.05f;
                if (frame == 80) Destroy(number);
            }
            frame++;
        }

        GameObject Child(string name, Vector3 at)
        {
            var made = GameObject.CreatePrimitive(PrimitiveType.Sphere);
            made.name = name;
            made.transform.SetParent(transform, false);
            made.transform.localPosition = at;
            return made;
        }
    }
}
