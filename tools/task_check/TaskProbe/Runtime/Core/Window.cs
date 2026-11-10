// The play's window and the desktop of whoever is using the machine. The checker starts the player on a Windows desktop
// of its own (tools/task_check/desk.py): nothing shows on the user's screen, the window can't take the keyboard and a
// game that locks the cursor can't grab the real one, while the game counts itself focused throughout. Then there is
// nothing to do here. Started by hand on the user's own desktop (a developer trying a play), the window is moved off
// every screen and never activated instead, the best that can be done there: it renders the same, but the game sees
// itself lose focus at its first frame. Windows standalone only; elsewhere this does nothing.
using System;
using System.Runtime.InteropServices;
using UnityEngine;

namespace TaskProbe
{
    public static class Window
    {
#if UNITY_STANDALONE_WIN && !UNITY_EDITOR
        delegate bool EnumProc(IntPtr hWnd, IntPtr lParam);

        [DllImport("user32.dll")] static extern bool EnumThreadWindows(uint threadId, EnumProc callback, IntPtr lParam);
        [DllImport("kernel32.dll")] static extern uint GetCurrentThreadId();
        [DllImport("user32.dll")] static extern bool IsWindowVisible(IntPtr hWnd);
        [DllImport("user32.dll")] static extern bool ShowWindow(IntPtr hWnd, int command);
        [DllImport("user32.dll")] static extern bool SetWindowPos(IntPtr hWnd, IntPtr after, int x, int y, int cx, int cy, uint flags);
        [DllImport("user32.dll", EntryPoint = "GetWindowLongPtrW")] static extern IntPtr GetWindowLongPtr(IntPtr hWnd, int index);
        [DllImport("user32.dll", EntryPoint = "SetWindowLongPtrW")] static extern IntPtr SetWindowLongPtr(IntPtr hWnd, int index, IntPtr value);
        [DllImport("user32.dll")] static extern bool GetWindowRect(IntPtr hWnd, out Rect rect);
        [DllImport("user32.dll")] static extern IntPtr GetThreadDesktop(uint threadId);
        [DllImport("user32.dll", CharSet = CharSet.Unicode)] static extern bool GetUserObjectInformationW(IntPtr handle, int index, System.Text.StringBuilder info, int length, out int needed);

        [StructLayout(LayoutKind.Sequential)] struct Rect { public int Left, Top, Right, Bottom; }

        const int GwlExStyle = -20;
        const long WsExToolWindow = 0x00000080L, WsExAppWindow = 0x00040000L, WsExNoActivate = 0x08000000L;
        const int SwHide = 0, SwShowNoActivate = 4;
        const uint SwpNoSize = 0x0001, SwpNoZOrder = 0x0004, SwpNoActivate = 0x0010;
        const int Away = -20000;  // left and above any monitor layout

        static IntPtr window;
        static int ownDesktop = -1;  // unknown

        [AOT.MonoPInvokeCallback(typeof(EnumProc))]
        static bool Visit(IntPtr hWnd, IntPtr lParam)
        {
            if (!IsWindowVisible(hWnd)) return true;
            window = hWnd;
            return false;
        }

        static IntPtr Main()
        {
            if (window == IntPtr.Zero) EnumThreadWindows(GetCurrentThreadId(), Visit, IntPtr.Zero);
            return window;
        }
#endif

        /// <summary>Whether the player runs on a desktop of its own (not the user's "Default" one).</summary>
        public static bool OnOwnDesktop()
        {
#if UNITY_STANDALONE_WIN && !UNITY_EDITOR
            if (ownDesktop < 0)
            {
                var name = new System.Text.StringBuilder(256);
                var desktop = GetThreadDesktop(GetCurrentThreadId());
                const int UoiName = 2;
                var known = desktop != IntPtr.Zero && GetUserObjectInformationW(desktop, UoiName, name, name.Capacity * 2, out _);
                ownDesktop = known && !string.Equals(name.ToString(), "Default", StringComparison.OrdinalIgnoreCase) ? 1 : 0;
            }
            return ownDesktop == 1;
#else
            return false;
#endif
        }

        /// <summary>On the user's own desktop: hides the window from it for the rest of the play. Hiding it first hands
        /// the keyboard back to the window that had it; showing it again without activation keeps it rendering.</summary>
        public static void MoveAway()
        {
#if UNITY_STANDALONE_WIN && !UNITY_EDITOR
            if (Application.isBatchMode || OnOwnDesktop()) return;
            var hwnd = Main();
            if (hwnd == IntPtr.Zero) return;
            ShowWindow(hwnd, SwHide);
            var style = GetWindowLongPtr(hwnd, GwlExStyle).ToInt64();
            SetWindowLongPtr(hwnd, GwlExStyle, new IntPtr((style | WsExToolWindow | WsExNoActivate) & ~WsExAppWindow));
            SetWindowPos(hwnd, IntPtr.Zero, Away, Away, 0, 0, SwpNoSize | SwpNoZOrder | SwpNoActivate);
            ShowWindow(hwnd, SwShowNoActivate);
#endif
        }

        /// <summary>Puts the window back off-screen when something moved it (a resolution or fullscreen change).</summary>
        public static void KeepAway()
        {
#if UNITY_STANDALONE_WIN && !UNITY_EDITOR
            if (Application.isBatchMode || OnOwnDesktop()) return;
            var hwnd = Main();
            if (hwnd == IntPtr.Zero || !GetWindowRect(hwnd, out var rect)) return;
            if (rect.Left != Away || rect.Top != Away)
                SetWindowPos(hwnd, IntPtr.Zero, Away, Away, 0, 0, SwpNoSize | SwpNoZOrder | SwpNoActivate);
#endif
        }
    }
}
