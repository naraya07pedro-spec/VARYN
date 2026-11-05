"""17S-15: native Windows named-pipe OS-client-PID proof primitive.

Synthetic TEST ONLY: a unique single-instance local-only pipe with an explicit
owner-only DACL and bInheritHandle=FALSE. Uses bounded overlapped accept/read
and GetNamedPipeClientProcessId, not a PID supplied in a JSON payload.

This primitive alone has NOT authenticated an AppContainer package SID and
MUST NOT be used for production private-file or mutating tools.
"""
import ctypes
from ctypes import wintypes
import os
import secrets

from varyn.public_github_tool import PublicToolRejected

_TOKEN_QUERY = 0x0008
_TOKEN_USER = 1
_PIPE_ACCESS_INBOUND = 0x00000001
_FILE_FLAG_OVERLAPPED = 0x40000000
_FILE_FLAG_FIRST_PIPE_INSTANCE = 0x00080000
_PIPE_TYPE_BYTE = 0
_PIPE_WAIT = 0
_PIPE_REJECT_REMOTE_CLIENTS = 0x00000008
_ERROR_IO_PENDING = 997
_ERROR_PIPE_CONNECTED = 535
_INVALID = ctypes.c_void_p(-1).value
_WAIT_OBJECT_0 = 0

if os.name == "nt":
    class _SecurityAttributes(ctypes.Structure):
        _fields_ = [
            ("nLength", wintypes.DWORD),
            ("lpSecurityDescriptor", ctypes.c_void_p),
            ("bInheritHandle", wintypes.BOOL),
        ]

    class _Overlapped(ctypes.Structure):
        _fields_ = [
            ("Internal", ctypes.c_void_p),
            ("InternalHigh", ctypes.c_void_p),
            ("Offset", wintypes.DWORD),
            ("OffsetHigh", wintypes.DWORD),
            ("hEvent", wintypes.HANDLE),
        ]

    class _SidAndAttributes(ctypes.Structure):
        _fields_ = [("Sid", wintypes.HANDLE),
                    ("Attributes", wintypes.DWORD)]


def _api():
    if os.name != "nt":
        raise PublicToolRejected("Windows named-pipe attestation unavailable")
    k = ctypes.WinDLL("kernel32", use_last_error=True)
    a = ctypes.WinDLL("advapi32", use_last_error=True)
    k.GetCurrentProcess.argtypes = []
    k.GetCurrentProcess.restype = wintypes.HANDLE
    k.CloseHandle.argtypes = [wintypes.HANDLE]
    k.CloseHandle.restype = wintypes.BOOL
    k.LocalFree.argtypes = [wintypes.HANDLE]
    k.LocalFree.restype = wintypes.HANDLE
    k.CreateEventW.argtypes = [
        ctypes.c_void_p, wintypes.BOOL, wintypes.BOOL, wintypes.LPCWSTR]
    k.CreateEventW.restype = wintypes.HANDLE
    k.CreateNamedPipeW.argtypes = [
        wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.DWORD,
        wintypes.DWORD, wintypes.DWORD, wintypes.DWORD,
        ctypes.POINTER(_SecurityAttributes)]
    k.CreateNamedPipeW.restype = wintypes.HANDLE
    k.ConnectNamedPipe.argtypes = [wintypes.HANDLE, ctypes.POINTER(_Overlapped)]
    k.ConnectNamedPipe.restype = wintypes.BOOL
    k.GetOverlappedResult.argtypes = [
        wintypes.HANDLE, ctypes.POINTER(_Overlapped),
        ctypes.POINTER(wintypes.DWORD), wintypes.BOOL]
    k.GetOverlappedResult.restype = wintypes.BOOL
    k.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    k.WaitForSingleObject.restype = wintypes.DWORD
    k.CancelIoEx.argtypes = [wintypes.HANDLE, ctypes.POINTER(_Overlapped)]
    k.CancelIoEx.restype = wintypes.BOOL
    k.ReadFile.argtypes = [
        wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD), ctypes.POINTER(_Overlapped)]
    k.ReadFile.restype = wintypes.BOOL
    k.GetNamedPipeClientProcessId.argtypes = [
        wintypes.HANDLE, ctypes.POINTER(wintypes.ULONG)]
    k.GetNamedPipeClientProcessId.restype = wintypes.BOOL
    a.OpenProcessToken.argtypes = [
        wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE)]
    a.OpenProcessToken.restype = wintypes.BOOL
    a.GetTokenInformation.argtypes = [
        wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD)]
    a.GetTokenInformation.restype = wintypes.BOOL
    a.ConvertSidToStringSidW.argtypes = [
        wintypes.HANDLE, ctypes.POINTER(wintypes.LPWSTR)]
    a.ConvertSidToStringSidW.restype = wintypes.BOOL
    a.ConvertStringSecurityDescriptorToSecurityDescriptorW.argtypes = [
        wintypes.LPCWSTR, wintypes.DWORD, ctypes.POINTER(ctypes.c_void_p),
        ctypes.POINTER(wintypes.DWORD)]
    a.ConvertStringSecurityDescriptorToSecurityDescriptorW.restype = wintypes.BOOL
    return k, a


def _own_user_sid(kernel, advapi):
    token = wintypes.HANDLE()
    sid_text = wintypes.LPWSTR()
    try:
        if not advapi.OpenProcessToken(kernel.GetCurrentProcess(), _TOKEN_QUERY,
                                      ctypes.byref(token)):
            raise PublicToolRejected("Cannot attest local pipe owner")
        needed = wintypes.DWORD()
        advapi.GetTokenInformation(token, _TOKEN_USER,
                                   None, 0, ctypes.byref(needed))
        if not 16 <= needed.value <= 65536:
            raise PublicToolRejected("Owner SID size rejected")
        raw = ctypes.create_string_buffer(needed.value)
        if not advapi.GetTokenInformation(
                token, _TOKEN_USER, raw, needed, ctypes.byref(needed)):
            raise PublicToolRejected("Owner SID query failed")
        sid = ctypes.cast(raw, ctypes.POINTER(_SidAndAttributes)).contents.Sid
        if not sid or not advapi.ConvertSidToStringSidW(
                sid, ctypes.byref(sid_text)):
            raise PublicToolRejected("Owner SID conversion failed")
        return sid_text.value
    finally:
        if sid_text:
            kernel.LocalFree(ctypes.cast(sid_text, wintypes.HANDLE))
        if token:
            kernel.CloseHandle(token)


class OneShotWindowsPipe:
    """Owned, one-client OS PID attestation. Never inherits its server handle."""

    def __init__(self):
        kernel, advapi = _api()
        self._k = kernel
        self._pipe = None
        self._closed = False
        self._connected = False
        # The LOCAL namespace is required for future AppContainer research.
        self.name = (r"\\.\pipe\LOCAL\Varyn15_"
                     + str(os.getpid()) + "_" + secrets.token_hex(8))
        descriptor = ctypes.c_void_p()
        try:
            sid = _own_user_sid(kernel, advapi)
            # Explicitly omit Everyone/Anonymous/Authenticated Users.
            # A future AppContainer trial must grant its *specific* package
            # SID separately, not silently widen this owner-only ACL.
            sddl = "D:P(A;;GA;;;SY)(A;;GA;;;" + sid + ")"
            if not advapi.ConvertStringSecurityDescriptorToSecurityDescriptorW(
                    sddl, 1, ctypes.byref(descriptor), None):
                raise PublicToolRejected("Pipe DACL creation refused")
            sa = _SecurityAttributes(ctypes.sizeof(_SecurityAttributes),
                                     descriptor, False)
            handle = kernel.CreateNamedPipeW(
                self.name,
                _PIPE_ACCESS_INBOUND | _FILE_FLAG_FIRST_PIPE_INSTANCE |
                _FILE_FLAG_OVERLAPPED,
                _PIPE_TYPE_BYTE | _PIPE_WAIT | _PIPE_REJECT_REMOTE_CLIENTS,
                1, 256, 256, 2000, ctypes.byref(sa),
            )
            if handle is None or int(handle) == _INVALID:
                raise PublicToolRejected("Local-only pipe instance refused")
            self._pipe = handle
        finally:
            if descriptor:
                kernel.LocalFree(descriptor)

    def _bounded_io(self, method, length, timeout_ms):
        if not 1 <= timeout_ms <= 8000:
            raise PublicToolRejected("Pipe time bound rejected")
        event = self._k.CreateEventW(None, True, False, None)
        if not event:
            raise PublicToolRejected("Pipe event creation failed")
        try:
            ov = _Overlapped()
            ov.hEvent = event
            count = wintypes.DWORD()
            data = ctypes.create_string_buffer(length)
            if method == "connect":
                result = self._k.ConnectNamedPipe(self._pipe, ctypes.byref(ov))
            else:
                result = self._k.ReadFile(
                    self._pipe, data, length, ctypes.byref(count),
                    ctypes.byref(ov))
            error = ctypes.get_last_error() if not result else 0
            if not result and error not in (
                    _ERROR_IO_PENDING,
                    _ERROR_PIPE_CONNECTED if method == "connect" else -1):
                raise PublicToolRejected("Native pipe I/O refused")
            if not result and error == _ERROR_IO_PENDING:
                if self._k.WaitForSingleObject(event, timeout_ms) != _WAIT_OBJECT_0:
                    self._k.CancelIoEx(self._pipe, ctypes.byref(ov))
                    self._k.WaitForSingleObject(event, 1000)
                    raise PublicToolRejected("Native pipe I/O bounded timeout")
                if not self._k.GetOverlappedResult(
                        self._pipe, ctypes.byref(ov),
                        ctypes.byref(count), False):
                    raise PublicToolRejected("Native pipe overlapped I/O failed")
            if method == "connect":
                return b""
            return data.raw[:count.value]
        finally:
            self._k.CloseHandle(event)

    def verify_one_client(self, expected_pid, expected_message=b"varyn-os-pid-v15"):
        """Require OS-issued PID BEFORE consuming any peer-controlled content."""
        if self._closed or self._connected:
            raise PublicToolRejected("Pipe session already consumed")
        self._connected = True  # failure also burns the one-shot session
        if type(expected_pid) is not int or expected_pid < 1:
            raise PublicToolRejected("Expected child PID invalid")
        self._bounded_io("connect", 1, 6000)
        observed = wintypes.ULONG()
        if not self._k.GetNamedPipeClientProcessId(
                self._pipe, ctypes.byref(observed)):
            raise PublicToolRejected("OS client PID attestation unavailable")
        if observed.value != expected_pid:
            raise PublicToolRejected("OS client PID mismatch")
        received = self._bounded_io("read", 128, 3000)
        if received != expected_message:
            raise PublicToolRejected("Unexpected pipe payload")
        return {"os_client_pid_verified": True,
                "one_shot": True, "local_only": True,
                "owner_only_dacl": True, "inherited_handles": False,
                "appcontainer_sid_verified": False}

    def close(self):
        if self._closed:
            return
        self._closed = True
        if self._pipe:
            self._k.CloseHandle(self._pipe)
