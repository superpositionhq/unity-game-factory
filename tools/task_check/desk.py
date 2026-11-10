"""Run a program on a Windows desktop of its own, so a play never touches the desktop of whoever is using the machine:

    python desk.py <exe> [args...]      exits with the program's exit code

A play is a real windowed player (Unity doesn't draw the screen in batchmode). On the user's desktop it would take the
keyboard focus when it starts, and a game that locks the mouse cursor would grab the real one (measured: the cursor
was moved and clipped for the whole play). A window on another desktop of the same window station shows nothing on
screen, can never be the foreground window, and cannot move or clip the cursor, yet the player renders as usual (the
frame read back is identical) and counts itself focused throughout, so a game that pauses when it loses focus plays
on. Windows only; elsewhere the program runs as it is. Standard library only."""

import ctypes
import subprocess
import sys

DESKTOP = "TaskProbe"
GENERIC_ALL = 0x10000000
INFINITE = 0xFFFFFFFF


def run(argv, cwd=None, name=DESKTOP):
    """Run `argv` (in `cwd`) on the desktop `name`, made when it isn't there, and wait: its exit code."""
    if sys.platform != "win32":
        return subprocess.run([str(a) for a in argv], cwd=cwd, check=False).returncode
    from ctypes import wintypes

    class StartupInfo(ctypes.Structure):
        _fields_ = [("cb", wintypes.DWORD), ("lpReserved", wintypes.LPWSTR), ("lpDesktop", wintypes.LPWSTR),
                    ("lpTitle", wintypes.LPWSTR), ("dwX", wintypes.DWORD), ("dwY", wintypes.DWORD),
                    ("dwXSize", wintypes.DWORD), ("dwYSize", wintypes.DWORD), ("dwXCountChars", wintypes.DWORD),
                    ("dwYCountChars", wintypes.DWORD), ("dwFillAttribute", wintypes.DWORD), ("dwFlags", wintypes.DWORD),
                    ("wShowWindow", wintypes.WORD), ("cbReserved2", wintypes.WORD), ("lpReserved2", ctypes.c_void_p),
                    ("hStdInput", wintypes.HANDLE), ("hStdOutput", wintypes.HANDLE), ("hStdError", wintypes.HANDLE)]

    class ProcessInformation(ctypes.Structure):
        _fields_ = [("hProcess", wintypes.HANDLE), ("hThread", wintypes.HANDLE), ("dwProcessId", wintypes.DWORD),
                    ("dwThreadId", wintypes.DWORD)]

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.CreateDesktopW.restype = wintypes.HANDLE
    user32.CreateDesktopW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR, ctypes.c_void_p, wintypes.DWORD,
                                      wintypes.DWORD, ctypes.c_void_p]
    user32.CloseDesktop.argtypes = [wintypes.HANDLE]
    kernel32.CreateProcessW.argtypes = [wintypes.LPCWSTR, wintypes.LPWSTR, ctypes.c_void_p, ctypes.c_void_p,
                                        wintypes.BOOL, wintypes.DWORD, ctypes.c_void_p, wintypes.LPCWSTR,
                                        ctypes.POINTER(StartupInfo), ctypes.POINTER(ProcessInformation)]
    kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel32.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]

    # opens the desktop when another play already made it; it goes when the last handle and process on it are gone
    desktop = user32.CreateDesktopW(name, None, None, 0, GENERIC_ALL, None)
    if not desktop:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        startup = StartupInfo()
        startup.cb = ctypes.sizeof(startup)
        startup.lpDesktop = "WinSta0\\" + name
        made = ProcessInformation()
        command = ctypes.create_unicode_buffer(subprocess.list2cmdline([str(a) for a in argv]))
        if not kernel32.CreateProcessW(None, command, None, None, False, 0, None, str(cwd) if cwd else None,
                                       ctypes.byref(startup), ctypes.byref(made)):
            raise ctypes.WinError(ctypes.get_last_error())
        kernel32.WaitForSingleObject(made.hProcess, INFINITE)
        code = wintypes.DWORD()
        kernel32.GetExitCodeProcess(made.hProcess, ctypes.byref(code))
        kernel32.CloseHandle(made.hThread)
        kernel32.CloseHandle(made.hProcess)
        return code.value if code.value < 0x80000000 else code.value - 0x100000000
    finally:
        user32.CloseDesktop(desktop)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    sys.exit(run(sys.argv[1:]))
