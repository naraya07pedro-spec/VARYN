"""17S-5 native Windows Job Object containment and OS token SID consistency.

A Job Object enforces limited resources/process-tree cleanup. It is NOT a
security sandbox, restricted access token, credential boundary, or human login.
No third-party dependencies. Fail closed if native setup/assignment fails.
"""
import ctypes
import os

from varyn.public_github_tool import PublicToolRejected

MAX_CHILD_COMMIT_BYTES = 192 * 1024 * 1024
_JOB_OBJECT_LIMIT_ACTIVE_PROCESS = 0x00000008
_JOB_OBJECT_LIMIT_PROCESS_MEMORY = 0x00000100
_JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
_EXTENDED_LIMIT_INFORMATION = 9
_TOKEN_QUERY = 0x0008
_TOKEN_USER = 1


if os.name == "nt":
    _DWORD = ctypes.c_uint32
    _HANDLE = ctypes.c_void_p
    _SIZE_T = ctypes.c_size_t

    class _BasicLimit(ctypes.Structure):
        _fields_ = [
            ("PerProcessUserTimeLimit", ctypes.c_int64),
            ("PerJobUserTimeLimit", ctypes.c_int64),
            ("LimitFlags", _DWORD),
            ("MinimumWorkingSetSize", _SIZE_T),
            ("MaximumWorkingSetSize", _SIZE_T),
            ("ActiveProcessLimit", _DWORD),
            ("Affinity", _SIZE_T),
            ("PriorityClass", _DWORD),
            ("SchedulingClass", _DWORD),
        ]

    class _IoCounters(ctypes.Structure):
        _fields_ = [(name, ctypes.c_uint64) for name in (
            "ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
            "ReadTransferCount", "WriteTransferCount", "OtherTransferCount",
        )]

    class _ExtendedLimit(ctypes.Structure):
        _fields_ = [
            ("BasicLimitInformation", _BasicLimit),
            ("IoInfo", _IoCounters),
            ("ProcessMemoryLimit", _SIZE_T),
            ("JobMemoryLimit", _SIZE_T),
            ("PeakProcessMemoryUsed", _SIZE_T),
            ("PeakJobMemoryUsed", _SIZE_T),
        ]


def _native_apis():
    if os.name != "nt":
        raise PublicToolRejected("Windows kernel limits not available")
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    advapi = ctypes.WinDLL("advapi32", use_last_error=True)
    kernel.CreateJobObjectW.argtypes = [_HANDLE, ctypes.c_wchar_p]
    kernel.CreateJobObjectW.restype = _HANDLE
    kernel.SetInformationJobObject.argtypes = [
        _HANDLE, ctypes.c_int, ctypes.c_void_p, _DWORD]
    kernel.SetInformationJobObject.restype = ctypes.c_int
    kernel.AssignProcessToJobObject.argtypes = [_HANDLE, _HANDLE]
    kernel.AssignProcessToJobObject.restype = ctypes.c_int
    kernel.IsProcessInJob.argtypes = [
        _HANDLE, _HANDLE, ctypes.POINTER(ctypes.c_int)]
    kernel.IsProcessInJob.restype = ctypes.c_int
    kernel.CloseHandle.argtypes = [_HANDLE]
    kernel.CloseHandle.restype = ctypes.c_int
    kernel.GetCurrentProcess.argtypes = []
    kernel.GetCurrentProcess.restype = _HANDLE
    advapi.OpenProcessToken.argtypes = [
        _HANDLE, _DWORD, ctypes.POINTER(_HANDLE)]
    advapi.OpenProcessToken.restype = ctypes.c_int
    advapi.GetTokenInformation.argtypes = [
        _HANDLE, ctypes.c_int, ctypes.c_void_p, _DWORD,
        ctypes.POINTER(_DWORD)]
    advapi.GetTokenInformation.restype = ctypes.c_int
    advapi.GetLengthSid.argtypes = [_HANDLE]
    advapi.GetLengthSid.restype = _DWORD
    return kernel, advapi


def _token_user_sid(process_handle, kernel, advapi):
    """Read OS-issued user SID bytes; no username/env spoofing accepted."""
    token = _HANDLE()
    if not advapi.OpenProcessToken(
            _HANDLE(process_handle), _TOKEN_QUERY, ctypes.byref(token)):
        raise PublicToolRejected("Windows process user token unavailable")
    try:
        needed = _DWORD()
        advapi.GetTokenInformation(
            token, _TOKEN_USER, None, 0, ctypes.byref(needed))
        if not 8 <= needed.value <= 65536:
            raise PublicToolRejected("Unexpected Windows token size")
        buffer = ctypes.create_string_buffer(needed.value)
        if not advapi.GetTokenInformation(
                token, _TOKEN_USER, buffer, needed,
                ctypes.byref(needed)):
            raise PublicToolRejected("Windows token SID read denied")
        sid_pointer = ctypes.cast(buffer, ctypes.POINTER(_HANDLE))[0]
        if not sid_pointer:
            raise PublicToolRejected("Missing token SID")
        sid_length = advapi.GetLengthSid(_HANDLE(sid_pointer))
        if not 8 <= sid_length <= 68:
            raise PublicToolRejected("Invalid Windows SID length")
        return ctypes.string_at(sid_pointer, sid_length)
    finally:
        kernel.CloseHandle(token)


class WindowsChildJob:
    """One per child; parent holds last job handle, no breakaway allowed."""

    def __init__(self, proc, *, memory_cap=MAX_CHILD_COMMIT_BYTES):
        if os.name != "nt":
            raise PublicToolRejected("Windows job only supported on Windows")
        if type(memory_cap) is not int or not (
                64 * 1024 * 1024 <= memory_cap <= 512 * 1024 * 1024):
            raise PublicToolRejected("Unsafe Windows job memory limit")
        process_handle = getattr(proc, "_handle", None)
        if not isinstance(process_handle, (int,)) and not (
                process_handle is not None and
                hasattr(process_handle, "__int__")):
            raise PublicToolRejected("Trusted Windows process handle missing")
        self._kernel, advapi = _native_apis()
        self._job = None
        try:
            parent_handle = self._kernel.GetCurrentProcess()
            parent_sid = _token_user_sid(parent_handle, self._kernel, advapi)
            child_sid = _token_user_sid(int(process_handle), self._kernel, advapi)
            if child_sid != parent_sid:
                raise PublicToolRejected("Child user SID does not match owner process")
            job = self._kernel.CreateJobObjectW(None, None)
            if not job:
                raise PublicToolRejected("Windows Job Object creation denied")
            self._job = job
            limits = _ExtendedLimit()
            limits.BasicLimitInformation.LimitFlags = (
                _JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
                | _JOB_OBJECT_LIMIT_ACTIVE_PROCESS
                | _JOB_OBJECT_LIMIT_PROCESS_MEMORY
            )
            limits.BasicLimitInformation.ActiveProcessLimit = 1
            limits.ProcessMemoryLimit = memory_cap
            if not self._kernel.SetInformationJobObject(
                    _HANDLE(job), _EXTENDED_LIMIT_INFORMATION,
                    ctypes.byref(limits), ctypes.sizeof(limits)):
                raise PublicToolRejected("Windows job limits refused")
            if not self._kernel.AssignProcessToJobObject(
                    _HANDLE(job), _HANDLE(int(process_handle))):
                raise PublicToolRejected("Windows child job assignment denied")
            confirmed = ctypes.c_int(0)
            if not self._kernel.IsProcessInJob(
                    _HANDLE(int(process_handle)), _HANDLE(job),
                    ctypes.byref(confirmed)) or not confirmed.value:
                raise PublicToolRejected("Windows job membership unverified")
        except Exception:
            self.close()
            raise PublicToolRejected(
                "Windows child OS identity or process limits not established"
            ) from None

    def close(self):
        """KILL_ON_JOB_CLOSE terminates descendants if this is last job handle."""
        job, self._job = self._job, None
        if job:
            self._kernel.CloseHandle(_HANDLE(job))

    @property
    def attached(self):
        return self._job is not None


def attach_windows_child_guard(proc):
    """Production factory: never return a fake guard or insecure fallback."""
    return WindowsChildJob(proc)
