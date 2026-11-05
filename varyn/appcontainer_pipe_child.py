"""17S-15 native AppContainer LOCAL pipe client, fixed offline marker only.

The process runs only inside a disposable Windows CI AppContainer and does
not use a shared HMAC secret, arbitrary code execution, network, providers,
or real host files. Parent must verify the actual OS client PID and token.
"""
import ctypes
from ctypes import wintypes
import sys
import time


def main(argv):
    if len(argv) != 3:
        return 90
    allowed, denied, pipe_name = argv
    if not pipe_name.startswith(r"\\.\pipe\LOCAL\Varyn15_"):
        return 91
    try:
        with open(allowed, "rb") as stream:
            if stream.read(40) != b"varyn-17s13-granted":
                return 81
    except Exception:
        return 82
    try:
        with open(denied, "rb") as stream:
            stream.read(1)
        return 83
    except PermissionError:
        pass
    except FileNotFoundError:
        return 84
    except Exception:
        return 85

    k = ctypes.WinDLL("kernel32", use_last_error=True)
    k.CreateFileW.argtypes = [
        wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
        ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    k.CreateFileW.restype = wintypes.HANDLE
    k.WriteFile.argtypes = [
        wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p]
    k.WriteFile.restype = wintypes.BOOL
    k.CloseHandle.argtypes = [wintypes.HANDLE]
    k.CloseHandle.restype = wintypes.BOOL
    invalid = ctypes.c_void_p(-1).value
    pipe = None
    observed_error = 0
    for _ in range(20):
        # FILE_WRITE_DATA ONLY; do not request GENERIC_WRITE, which can
        # include FILE_CREATE_PIPE_INSTANCE on named pipes.
        pipe = k.CreateFileW(pipe_name, 0x00000002, 0, None, 3, 0, None)
        if pipe is not None and int(pipe) != invalid:
            break
        observed_error = ctypes.get_last_error()
        time.sleep(.1)
    else:
        # Only generic OS error categories are encoded in exit status.
        # 2/3 = namespace path missing; 5 = ACL/integrity denied.
        # Does not disclose the named pipe path or any profile metadata.
        if observed_error in (2, 3):
            return 92
        if observed_error == 5:
            return 95
        return 96
    try:
        data = ctypes.create_string_buffer(b"varyn-os-pid-v15")
        written = wintypes.DWORD()
        if not k.WriteFile(pipe, data, 16, ctypes.byref(written), None):
            return 93
        if written.value != 16:
            return 94
        time.sleep(.15)  # Keep pipe alive for parent OS PID query.
        return 73
    finally:
        k.CloseHandle(pipe)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
