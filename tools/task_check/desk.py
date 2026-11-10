"""Run a program on a Windows desktop of its own, so a play never touches the desktop of whoever is using the machine:

    python desk.py <exe> [args...]      exits with the program's exit code

(From Git Bash, an argument that starts with a slash reaches it rewritten as a path, `cmd /c` as `cmd C:/`, and that
cmd then waits for input on a desktop nobody sees: set MSYS_NO_PATHCONV=1 first. PowerShell passes it as it is.)

A play is a real windowed player (Unity doesn't draw the screen in batchmode). On the user's desktop it would take the
keyboard focus when it starts, and a game that locks the mouse cursor would grab the real one (measured: the cursor
was moved and clipped for the whole play). A window on another desktop of the same window station shows nothing on
screen, can never be the foreground window, and cannot move or clip the cursor, yet the player renders as usual (the
frame read back is identical) and counts itself focused throughout, so a game that pauses when it loses focus plays
on. Nobody sees that desktop either, so the program runs in a job object that kills it, and whatever it started, when
desk.py goes for any reason (killed on its own included): a play never outlives the checker that started it.
Windows only; elsewhere the program runs as it is. Standard library only."""

import ctypes
import subprocess
import sys

DESKTOP = "TaskProbe"
GENERIC_ALL = 0x10000000
INFINITE = 0xFFFFFFFF
WAIT_OBJECT_0 = 0
CREATE_SUSPENDED = 0x4
KILL_ON_JOB_CLOSE = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
EXTENDED_LIMITS = 9  # JobObjectExtendedLimitInformation


def run(argv, name=DESKTOP):
    """Run `argv` on the desktop `name`, made when it isn't there, and wait: its exit code (an NTSTATUS such as
    0xC0000005 as a negative number). Raises OSError naming the Windows call that failed."""
    if sys.platform != "win32":
        return subprocess.run([str(a) for a in argv], check=False).returncode
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

    class BasicLimits(ctypes.Structure):  # JOBOBJECT_BASIC_LIMIT_INFORMATION
        _fields_ = [("PerProcessUserTimeLimit", ctypes.c_int64), ("PerJobUserTimeLimit", ctypes.c_int64),
                    ("LimitFlags", wintypes.DWORD), ("MinimumWorkingSetSize", ctypes.c_size_t),
                    ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", wintypes.DWORD),
                    ("Affinity", ctypes.c_size_t), ("PriorityClass", wintypes.DWORD), ("SchedulingClass", wintypes.DWORD)]

    class Limits(ctypes.Structure):  # JOBOBJECT_EXTENDED_LIMIT_INFORMATION
        _fields_ = [("BasicLimitInformation", BasicLimits), ("IoInfo", ctypes.c_uint64 * 6),
                    ("ProcessMemoryLimit", ctypes.c_size_t), ("JobMemoryLimit", ctypes.c_size_t),
                    ("PeakProcessMemoryUsed", ctypes.c_size_t), ("PeakJobMemoryUsed", ctypes.c_size_t)]

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    handle, flag, dword = wintypes.HANDLE, wintypes.BOOL, wintypes.DWORD
    for dll, function, restype, argtypes in (  # handles are pointer-sized: an int restype would cut them to 32 bits
            (user32, "CreateDesktopW", handle, [wintypes.LPCWSTR, wintypes.LPCWSTR, ctypes.c_void_p, dword, dword,
                                                ctypes.c_void_p]),
            (user32, "CloseDesktop", flag, [handle]),
            (kernel32, "CreateJobObjectW", handle, [ctypes.c_void_p, wintypes.LPCWSTR]),
            (kernel32, "SetInformationJobObject", flag, [handle, ctypes.c_int, ctypes.c_void_p, dword]),
            (kernel32, "CreateProcessW", flag, [wintypes.LPCWSTR, wintypes.LPWSTR, ctypes.c_void_p, ctypes.c_void_p,
                                                flag, dword, ctypes.c_void_p, wintypes.LPCWSTR,
                                                ctypes.POINTER(StartupInfo), ctypes.POINTER(ProcessInformation)]),
            (kernel32, "AssignProcessToJobObject", flag, [handle, handle]),
            (kernel32, "ResumeThread", dword, [handle]),
            (kernel32, "TerminateProcess", flag, [handle, wintypes.UINT]),
            (kernel32, "WaitForSingleObject", dword, [handle, dword]),
            (kernel32, "GetExitCodeProcess", flag, [handle, ctypes.POINTER(dword)]),
            (kernel32, "CloseHandle", flag, [handle])):
        getattr(dll, function).restype, getattr(dll, function).argtypes = restype, argtypes

    def failed(what):
        error = ctypes.get_last_error()
        return OSError(None, f"{what}: {ctypes.FormatError(error).strip()}", None, error)

    # opens the desktop when another play already made it; it goes when the last handle and process on it are gone
    desktop = user32.CreateDesktopW(name, None, None, 0, GENERIC_ALL, None)
    if not desktop:
        raise failed(f"CreateDesktopW {name}")
    try:
        job = kernel32.CreateJobObjectW(None, None)
        if not job:
            raise failed("CreateJobObjectW")
        try:
            limits = Limits()
            limits.BasicLimitInformation.LimitFlags = KILL_ON_JOB_CLOSE
            if not kernel32.SetInformationJobObject(job, EXTENDED_LIMITS, ctypes.byref(limits), ctypes.sizeof(limits)):
                raise failed("SetInformationJobObject")
            startup = StartupInfo()
            startup.cb = ctypes.sizeof(startup)
            startup.lpDesktop = "WinSta0\\" + name
            made = ProcessInformation()
            command = ctypes.create_unicode_buffer(subprocess.list2cmdline([str(a) for a in argv]))
            # suspended until it is in the job, so nothing it starts can escape it
            if not kernel32.CreateProcessW(None, command, None, None, False, CREATE_SUSPENDED, None, None,
                                           ctypes.byref(startup), ctypes.byref(made)):
                raise failed(f"CreateProcessW {argv[0]}")
            try:
                if not kernel32.AssignProcessToJobObject(job, made.hProcess):
                    error = failed("AssignProcessToJobObject")
                    kernel32.TerminateProcess(made.hProcess, 1)  # it never ran
                    raise error
                if kernel32.ResumeThread(made.hThread) == 0xFFFFFFFF:
                    raise failed("ResumeThread")
                if kernel32.WaitForSingleObject(made.hProcess, INFINITE) != WAIT_OBJECT_0:
                    raise failed("WaitForSingleObject")
                code = wintypes.DWORD()
                if not kernel32.GetExitCodeProcess(made.hProcess, ctypes.byref(code)):
                    raise failed("GetExitCodeProcess")
                return code.value if code.value < 0x80000000 else code.value - 0x100000000
            finally:
                kernel32.CloseHandle(made.hThread)
                kernel32.CloseHandle(made.hProcess)
        finally:
            kernel32.CloseHandle(job)  # kills whatever of the job still runs
    finally:
        user32.CloseDesktop(desktop)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    try:
        sys.exit(run(sys.argv[1:]))
    except OSError as exc:
        sys.exit(f"desk.py: {exc}")
