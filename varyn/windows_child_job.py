"""17S-5/6 native Windows child Job Object, SID and Low integrity gating.

Windows MIC low integrity prevents writes to ordinary medium-integrity objects.
It does NOT prevent reads, revoke the user SID, or create an AppContainer.
No third-party dependencies. Fail closed before sending tool input.
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
_TOKEN_ADJUST_DEFAULT = 0x0080
_TOKEN_USER = 1
_TOKEN_INTEGRITY_LEVEL = 25
_SE_GROUP_INTEGRITY = 0x00000020
_LOW_INTEGRITY_RID = 4096
# Valid Windows integrity SID: revision 1, one subauthority,
# SECURITY_MANDATORY_LABEL_AUTHORITY = {0,0,0,0,0,16}, RID=4096.
_LOW_INTEGRITY_SID = bytes((1, 1, 0, 0, 0, 0, 0, 16)) + (
    _LOW_INTEGRITY_RID.to_bytes(4, "little")
)


if os.name == "nt":
    _DWORD = ctypes.c_uint32
    _HANDLE = ctypes.c_void_p
    _SIZE_T = ctypes.c_size_t

    class _SidAndAttributes(ctypes.Structure):
        _fields_ = [("Sid", _HANDLE), ("Attributes", _DWORD)]

    class _TokenMandatoryLabel(ctypes.Structure):
        _fields_ = [("Label", _SidAndAttributes)]

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
    kernel.QueryInformationJobObject.argtypes = [
        _HANDLE, ctypes.c_int, ctypes.c_void_p, _DWORD,
        ctypes.POINTER(_DWORD)]
    kernel.QueryInformationJobObject.restype = ctypes.c_int
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
    advapi.IsValidSid.argtypes = [_HANDLE]
    advapi.IsValidSid.restype = ctypes.c_int
    advapi.SetTokenInformation.argtypes = [
        _HANDLE, ctypes.c_int, ctypes.c_void_p, _DWORD,
    ]
    advapi.SetTokenInformation.restype = ctypes.c_int
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


def _enforce_child_low_integrity(process_handle, kernel, advapi):
    """Use OS-issued *child* primary token; verify Low IL readback.

    This guarantees a Low Mandatory Integrity Level, not a restricted token
    with read-deny ACLs. The child has already started but is held on stdin;
    caller MUST attach Job and apply this gate before sending tool intent.
    """
    if os.name != "nt":
        raise PublicToolRejected("Windows MIC unavailable")
    token = _HANDLE()
    if not advapi.OpenProcessToken(
            _HANDLE(process_handle), _TOKEN_QUERY | _TOKEN_ADJUST_DEFAULT,
            ctypes.byref(token)):
        raise PublicToolRejected("Cannot open child token for MIC reduction")
    try:
        sid_buffer = ctypes.create_string_buffer(_LOW_INTEGRITY_SID)
        sid_ptr = ctypes.cast(sid_buffer, _HANDLE)
        if not advapi.IsValidSid(sid_ptr):
            raise PublicToolRejected("Low integrity SID failed native validation")
        label = _TokenMandatoryLabel(
            _SidAndAttributes(sid_ptr, _SE_GROUP_INTEGRITY),
        )
        # Windows requires sizeof(TOKEN_MANDATORY_LABEL) plus SID bytes.
        # It is safe to set this on a child blocked on stdin.
        size = ctypes.sizeof(label) + len(_LOW_INTEGRITY_SID)
        if not advapi.SetTokenInformation(
                token, _TOKEN_INTEGRITY_LEVEL,
                ctypes.byref(label), size):
            raise PublicToolRejected("Windows refused Low child integrity level")

        needed = _DWORD()
        advapi.GetTokenInformation(
            token, _TOKEN_INTEGRITY_LEVEL, None, 0, ctypes.byref(needed))
        if not ctypes.sizeof(_TokenMandatoryLabel) <= needed.value <= 65536:
            raise PublicToolRejected("Unexpected child integrity query size")
        output = ctypes.create_string_buffer(needed.value)
        if not advapi.GetTokenInformation(
                token, _TOKEN_INTEGRITY_LEVEL, output, needed,
                ctypes.byref(needed)):
            raise PublicToolRejected("Cannot verify child integrity level")
        observed = ctypes.cast(output, ctypes.POINTER(_TokenMandatoryLabel)).contents
        observed_sid = observed.Label.Sid
        if not observed_sid or not advapi.IsValidSid(_HANDLE(observed_sid)):
            raise PublicToolRejected("Invalid child integrity SID")
        sid_len = advapi.GetLengthSid(_HANDLE(observed_sid))
        if sid_len != len(_LOW_INTEGRITY_SID):
            raise PublicToolRejected("Child integrity is not Low")
        if ctypes.string_at(observed_sid, sid_len) != _LOW_INTEGRITY_SID:
            raise PublicToolRejected("Child integrity readback is not Low")
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
            observed = _ExtendedLimit()
            length = _DWORD()
            if not self._kernel.QueryInformationJobObject(
                    _HANDLE(job), _EXTENDED_LIMIT_INFORMATION,
                    ctypes.byref(observed), ctypes.sizeof(observed),
                    ctypes.byref(length)):
                raise PublicToolRejected("Windows Job Object limits unreadable")
            required = (
                _JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
                | _JOB_OBJECT_LIMIT_ACTIVE_PROCESS
                | _JOB_OBJECT_LIMIT_PROCESS_MEMORY
            )
            if (observed.BasicLimitInformation.LimitFlags & required != required or
                    observed.BasicLimitInformation.ActiveProcessLimit != 1 or
                    observed.ProcessMemoryLimit != memory_cap):
                raise PublicToolRejected("Windows Job Object limits not enforced")
            if not self._kernel.AssignProcessToJobObject(
                    _HANDLE(job), _HANDLE(int(process_handle))):
                raise PublicToolRejected("Windows child job assignment denied")
            confirmed = ctypes.c_int(0)
            if not self._kernel.IsProcessInJob(
                    _HANDLE(int(process_handle)), _HANDLE(job),
                    ctypes.byref(confirmed)) or not confirmed.value:
                raise PublicToolRejected("Windows job membership unverified")
            # 17S-6: enforce MIC *after* Job membership and *before* stdin.
            # Failure closes Job, killing the child. No downgrade/fallback.
            _enforce_child_low_integrity(int(process_handle), self._kernel, advapi)
        except Exception:
            self.close()
            raise PublicToolRejected(
                "Windows child Job, SID or Low MIC not established"
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


class WindowsSuspendedAppContainerJob:
    """17S-17 CI-only strict Job for a *suspended* native AppContainer.

    Does not change the security token's MIC or SID. The caller must separately
    attest the child's actual AppContainer primary token and keep it suspended
    until this Job's membership and limits are independently read back.
    Fails closed rather than retrying unguarded.
    """
    def __init__(self, process_handle, *, memory_cap=MAX_CHILD_COMMIT_BYTES):
        if os.name != "nt":
            raise PublicToolRejected("Windows AppContainer job unavailable")
        if type(memory_cap) is not int or not (
                64 * 1024 * 1024 <= memory_cap <= 256 * 1024 * 1024):
            raise PublicToolRejected("AppContainer Job memory cap rejected")
        if not process_handle:
            raise PublicToolRejected("Suspended process handle unavailable")
        self._kernel, _ = _native_apis()
        self._job = None
        self._memory_cap = memory_cap
        try:
            job = self._kernel.CreateJobObjectW(None, None)
            if not job:
                raise PublicToolRejected("AppContainer Job creation refused")
            self._job = job
            info = _ExtendedLimit()
            required = (
                _JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE |
                _JOB_OBJECT_LIMIT_ACTIVE_PROCESS |
                _JOB_OBJECT_LIMIT_PROCESS_MEMORY)
            info.BasicLimitInformation.LimitFlags = required
            info.BasicLimitInformation.ActiveProcessLimit = 1
            info.ProcessMemoryLimit = memory_cap
            if not self._kernel.SetInformationJobObject(
                    _HANDLE(job), _EXTENDED_LIMIT_INFORMATION,
                    ctypes.byref(info), ctypes.sizeof(info)):
                raise PublicToolRejected("AppContainer Job limits refused")
            output = _ExtendedLimit()
            length = _DWORD()
            if not self._kernel.QueryInformationJobObject(
                    _HANDLE(job), _EXTENDED_LIMIT_INFORMATION,
                    ctypes.byref(output), ctypes.sizeof(output),
                    ctypes.byref(length)):
                raise PublicToolRejected("AppContainer Job readback denied")
            if (output.BasicLimitInformation.LimitFlags & required != required
                    or output.BasicLimitInformation.ActiveProcessLimit != 1
                    or output.ProcessMemoryLimit != memory_cap):
                raise PublicToolRejected("AppContainer Job readback mismatch")
            if not self._kernel.AssignProcessToJobObject(
                    _HANDLE(job), _HANDLE(int(process_handle))):
                raise PublicToolRejected("AppContainer Job assignment refused")
            yes = ctypes.c_int()
            if not self._kernel.IsProcessInJob(
                    _HANDLE(int(process_handle)), _HANDLE(job),
                    ctypes.byref(yes)) or yes.value != 1:
                raise PublicToolRejected("AppContainer Job membership unverified")
        except Exception:
            self.close()
            raise PublicToolRejected(
                "Native suspended AppContainer Job containment not established"
            ) from None

    @property
    def attached(self):
        return self._job is not None

    @property
    def active_process_limit(self):
        return 1 if self.attached else 0

    @property
    def memory_cap_bytes(self):
        return self._memory_cap if self.attached else 0

    def close(self):
        handle, self._job = self._job, None
        if handle:
            self._kernel.CloseHandle(_HANDLE(handle))
