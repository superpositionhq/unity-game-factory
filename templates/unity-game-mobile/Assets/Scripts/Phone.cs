// This game is an Android phone game, held in __ORIENTATION__ for good and played by touch (Platform.json at the repo
// root says so to every tool). On the PC it is built, played, pictured and recorded as its Windows player in a window
// of the phone's size, __PHONE_WIDTH__x__PHONE_HEIGHT__, drawn with the project's one quality level (Mobile).
//   - Any start of the Windows player draws at that size: in a window of it, or, on a display too small to hold one
//     (a phone held upright is 1920 pixels high), full screen with the phone's picture scaled to fit.
//   - The AutoPlay drop-in is told the game is a phone game: its runs keep the window at the phone's size, and the
//     bot plays with fingers (AutoPlay.Touch, AutoPlay.TouchUp) and the back button ("<Keyboard>/escape", which is
//     what Android's back button is to the Input System) and nothing else.
// Keep this file as it is.
using UnityEngine;

namespace __PROJECT__
{
    public static class Phone
    {
        public const bool Portrait = __PORTRAIT__;
        public const int Width = __PHONE_WIDTH__, Height = __PHONE_HEIGHT__;

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.SubsystemRegistration)]
        static void Tell() => AutoPlay.Phone(Portrait);

#if UNITY_STANDALONE && !UNITY_EDITOR
        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.BeforeSceneLoad)]
        static void Size()
        {
            // not in a play a tool runs: the AutoPlay drop-in and the task check's probe hold the window themselves
            if (Application.isBatchMode || AutoPlay.IsActive || System.Array.IndexOf(System.Environment.GetCommandLineArgs(), "-taskProbe") >= 0) return;
            var display = Screen.currentResolution;
            var mode = display.width >= Width && display.height >= Height ? FullScreenMode.Windowed : FullScreenMode.FullScreenWindow;
            if (Screen.fullScreenMode != mode || Screen.width != Width || Screen.height != Height) Screen.SetResolution(Width, Height, mode);
        }
#endif
    }
}
