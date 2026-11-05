"""17S-16 native Windows two-anonymous-pipe inherited HANDLE_LIST trial helper.

CI-ONLY fixed synthetic broker transport. This object makes two pipes,
marks ONLY the child's stdin-read and stdout-write handles inheritable,
and creates a deliberately inheritable unrelated EVENT as negative control.
The child handles still MUST be passed in PROC_THREAD_ATTRIBUTE_HANDLE_LIST:
bInheritHandles=True without an explicit list is never acceptable.

No owner-file access, internet, shell, or provider context is exposed here.
This is NOT a general-purpose production broker.
"""
import ctypes
from ctypes import wintypes
import os

from varyn.public_github_tool import PublicToolRejected

_MAX_FRAME = 512
_FLAG_INHERIT = 1
_BAD_HANDLE = ctypes.c_void_p(-1).value

if os.name == "nt":
    class _SecAttrs(ctypes.Structure):
        _fields_ = [("nLength", wintypes.DWORD),
                    ("lpSecurityDescriptor", ctypes.c_void_p),
                    ("bInheritHandle", wintypes.BOOL)]


def _handle_value(value):
    number = value.value if hasattr(value, "value") else value
    return int(number or 0)


class TwoInheritedAnonymousPipes:
    """Exactly two child endpoints and two parent endpoints, plus decoy."""

    def __init__(self):
        if os.name != "nt":
            raise PublicToolRejected("Native Windows pipe trial unavailable")
        self.k = ctypes.WinDLL("kernel32", use_last_error=True)
        k = self.k
        k.CreatePipe.argtypes = [
            ctypes.POINTER(wintypes.HANDLE), ctypes.POINTER(wintypes.HANDLE),
            ctypes.POINTER(_SecAttrs), wintypes.DWORD]
        k.CreatePipe.restype = wintypes.BOOL
        k.SetHandleInformation.argtypes = [
            wintypes.HANDLE, wintypes.DWORD, wintypes.DWORD]
        k.SetHandleInformation.restype = wintypes.BOOL
        k.GetHandleInformation.argtypes = [
            wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
        k.GetHandleInformation.restype = wintypes.BOOL
        k.CloseHandle.argtypes = [wintypes.HANDLE]
        k.CloseHandle.restype = wintypes.BOOL
        k.CreateEventW.argtypes = [
            ctypes.POINTER(_SecAttrs), wintypes.BOOL, wintypes.BOOL,
            wintypes.LPCWSTR]
        k.CreateEventW.restype = wintypes.HANDLE
        k.WriteFile.argtypes = [
            wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p]
        k.WriteFile.restype = wintypes.BOOL
        k.ReadFile.argtypes = [
            wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p]
        k.ReadFile.restype = wintypes.BOOL
        k.PeekNamedPipe.argtypes = [
            wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD), ctypes.POINTER(wintypes.DWORD),
            ctypes.POINTER(wintypes.DWORD)]
        k.PeekNamedPipe.restype = wintypes.BOOL
        self._all = []
        self.child_stdin = None
        self.child_stdout = None
        self.parent_write = None
        self.parent_read = None
        self.decoy = None
        self._closed = False
        self._handed_to_process = False
        self._used = False
        sa = _SecAttrs(ctypes.sizeof(_SecAttrs), None, True)
        try:
            to_child_read = wintypes.HANDLE()
            parent_write = wintypes.HANDLE()
            if not k.CreatePipe(ctypes.byref(to_child_read),
                                ctypes.byref(parent_write),
                                ctypes.byref(sa), 4096):
                raise PublicToolRejected("Synthetic stdin pipe creation refused")
            self._register(to_child_read)
            self._register(parent_write)
            parent_read = wintypes.HANDLE()
            from_child_write = wintypes.HANDLE()
            if not k.CreatePipe(ctypes.byref(parent_read),
                                ctypes.byref(from_child_write),
                                ctypes.byref(sa), 4096):
                raise PublicToolRejected("Synthetic stdout pipe creation refused")
            self._register(parent_read)
            self._register(from_child_write)
            decoy = k.CreateEventW(ctypes.byref(sa), False, False, None)
            if not decoy or _handle_value(decoy) == _BAD_HANDLE:
                raise PublicToolRejected("Decoy event handle unavailable")
            self._register(decoy)
            self.child_stdin = to_child_read
            self.child_stdout = from_child_write
            self.parent_write = parent_write
            self.parent_read = parent_read
            self.decoy = decoy
            for handle in (parent_write, parent_read):
                if not k.SetHandleInformation(handle, _FLAG_INHERIT, 0):
                    raise PublicToolRejected("Parent pipe end inheritance denied")
            for handle in (to_child_read, from_child_write, decoy):
                if not self._is_inheritable(handle):
                    raise PublicToolRejected("Expected inheritable handle missing")
            for handle in (parent_write, parent_read):
                if self._is_inheritable(handle):
                    raise PublicToolRejected("Unexpected parent handle inheritance")
        except Exception:
            self.close()
            raise

    def _register(self, handle):
        self._all.append(handle)

    def _is_inheritable(self, handle):
        flags = wintypes.DWORD()
        if not self.k.GetHandleInformation(handle, ctypes.byref(flags)):
            raise PublicToolRejected("Cannot verify kernel handle flags")
        return bool(flags.value & _FLAG_INHERIT)

    @property
    def child_allowlist(self):
        if self._closed:
            raise PublicToolRejected("Closed inherited pipe trial")
        arr = (wintypes.HANDLE * 2)(
            _handle_value(self.child_stdin),
            _handle_value(self.child_stdout))
        return arr

    @property
    def excluded_decoy_value(self):
        return _handle_value(self.decoy)

    def mark_child_created(self):
        if self._handed_to_process or self._closed:
            raise PublicToolRejected("Child endpoints already handed off")
        self._handed_to_process = True
        for handle in (self.child_stdin, self.child_stdout):
            self.k.CloseHandle(handle)
            self._all = [h for h in self._all
                         if _handle_value(h) != _handle_value(handle)]
        self.child_stdin = None
        self.child_stdout = None

    def send_once(self, payload):
        if self._closed or not self._handed_to_process or self._used:
            raise PublicToolRejected("Unready or reused anonymous pipe session")
        self._used = True
        if type(payload) is not bytes or not 1 <= len(payload) <= _MAX_FRAME:
            raise PublicToolRejected("Synthetic pipe request length rejected")
        frame = len(payload).to_bytes(2, "big") + payload
        buffer = ctypes.create_string_buffer(frame)
        written = wintypes.DWORD()
        if not self.k.WriteFile(self.parent_write, buffer, len(frame),
                                ctypes.byref(written), None):
            raise PublicToolRejected("Anonymous pipe request write failed")
        if written.value != len(frame):
            raise PublicToolRejected("Truncated anonymous pipe request")
        # Close input writer immediately, allowing child's read to reach EOF
        # if it attempts to read more than the one expected frame.
        self.k.CloseHandle(self.parent_write)
        self._all = [h for h in self._all
                     if _handle_value(h) != _handle_value(self.parent_write)]
        self.parent_write = None

    def receive_after_child_exit(self):
        if self._closed or not self._handed_to_process or not self._used:
            raise PublicToolRejected("Anonymous pipe response requested too early")
        received = wintypes.DWORD()
        available = wintypes.DWORD()
        buf = ctypes.create_string_buffer(_MAX_FRAME + 3)
        if not self.k.PeekNamedPipe(
                self.parent_read, None, 0, None,
                ctypes.byref(available), None):
            raise PublicToolRejected("Anonymous pipe response not available")
        if not 3 <= available.value <= _MAX_FRAME + 2:
            raise PublicToolRejected("Anonymous pipe response size rejected")
        if not self.k.ReadFile(
                self.parent_read, buf, available.value,
                ctypes.byref(received), None):
            raise PublicToolRejected("Anonymous pipe response read failed")
        raw = buf.raw[:received.value]
        if len(raw) < 3 or len(raw) != available.value:
            raise PublicToolRejected("Anonymous pipe response truncated")
        amount = int.from_bytes(raw[:2], "big")
        if amount == 0 or amount != len(raw) - 2:
            raise PublicToolRejected("Anonymous pipe frame length mismatch")
        return raw[2:]

    def close(self):
        if self._closed:
            return
        self._closed = True
        for handle in self._all:
            if handle and _handle_value(handle) != _BAD_HANDLE:
                self.k.CloseHandle(handle)
        self._all.clear()
