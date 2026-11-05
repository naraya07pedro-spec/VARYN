"""17S-15 fixed synthetic named-pipe client for real Windows PID checks.

The child is an ordinary same-user desktop process, NOT AppContainer. It
sends one constant marker to one owner-only/local-only named pipe and exits.
No provider, disk data, network, command loop or privileged operation.
"""
import ctypes
from ctypes import wintypes
import sys
import time

def main(argv):
    if len(argv) != 1:
        return 4
    address = argv[0]
    if not address.startswith(r"\\.\pipe\LOCAL\Varyn15_"):
        return 5
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
    bad = ctypes.c_void_p(-1).value
    pipe = None
    for _ in range(40):
        pipe = k.CreateFileW(address, 0x40000000, 0, None, 3, 0, None)
        if pipe is not None and int(pipe) != bad:
            break
        time.sleep(.05)
    else:
        return 6
    try:
        payload = ctypes.create_string_buffer(b"varyn-os-pid-v15")
        count = wintypes.DWORD()
        if not k.WriteFile(pipe, payload, 16, ctypes.byref(count), None):
            return 7
        if count.value != 16:
            return 8
        time.sleep(.25)  # keep the client connection live for OS PID lookup
        return 0
    finally:
        k.CloseHandle(pipe)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
