"""17S-11: native suspended Windows process with restricted PRIMARY token.

An OFFLINE, trusted-host primitive for testing a real kernel security boundary.
This is not yet wired to production GitHub HTTP or private-file tools.

No access-control fallback, no inherited handles, no user-selected command and
no secrets in the child environment. The child is suspended until an external
Job Object + Low MIC guard has attached and attested it. Always fail closed.
"""
import ctypes
from ctypes import wintypes
import os
from pathlib import Path
import subprocess
import sys

from varyn.public_github_tool import PublicToolRejected

# Diagnostic broad SID solely to isolate startup ACL failure.
# Everyone is NOT a dedicated sandbox SID; no private-data read claim.
# Production private-file access remains disabled pending dedicated ACL grants.
_RESTRICTING_SID = "S-1-1-0"  # BUILTIN\\Users
_TOKEN_ASSIGN_PRIMARY = 0x0001
_TOKEN_DUPLICATE = 0x0002
_TOKEN_IMPERSONATE = 0x0004
_TOKEN_QUERY = 0x0008
_DISABLE_MAX_PRIVILEGE = 0x00000001
_CREATE_SUSPENDED = 0x00000004
_CREATE_NO_WINDOW = 0x08000000
_CREATE_UNICODE_ENVIRONMENT = 0x00000400
_WAIT_OBJECT_0 = 0
_WAIT_TIMEOUT = 258
_STILL_ACTIVE = 259
_TOKEN_RESTRICTED_SIDS = 11
_TOKEN_DEFAULT_DACL = 6
_TOKEN_USER = 1
_GENERIC_ALL = 0x10000000


if os.name == "nt":
    class _SidAndAttributes(ctypes.Structure):
        _fields_ = [("Sid", wintypes.HANDLE), ("Attributes", wintypes.DWORD)]

    class _TokenDefaultDacl(ctypes.Structure):
        _fields_ = [("DefaultDacl", ctypes.c_void_p)]

    class _AclHeader(ctypes.Structure):
        _fields_ = [("AclRevision", ctypes.c_uint8),
                    ("Sbz1", ctypes.c_uint8),
                    ("AclSize", ctypes.c_uint16),
                    ("AceCount", ctypes.c_uint16),
                    ("Sbz2", ctypes.c_uint16)]

    class _StartupInfo(ctypes.Structure):
        _fields_ = [
            ("cb", wintypes.DWORD), ("lpReserved", wintypes.LPWSTR),
            ("lpDesktop", wintypes.LPWSTR), ("lpTitle", wintypes.LPWSTR),
            ("dwX", wintypes.DWORD), ("dwY", wintypes.DWORD),
            ("dwXSize", wintypes.DWORD), ("dwYSize", wintypes.DWORD),
            ("dwXCountChars", wintypes.DWORD), ("dwYCountChars", wintypes.DWORD),
            ("dwFillAttribute", wintypes.DWORD), ("dwFlags", wintypes.DWORD),
            ("wShowWindow", wintypes.WORD), ("cbReserved2", wintypes.WORD),
            ("lpReserved2", ctypes.c_void_p), ("hStdInput", wintypes.HANDLE),
            ("hStdOutput", wintypes.HANDLE), ("hStdError", wintypes.HANDLE),
        ]

    class _ProcessInfo(ctypes.Structure):
        _fields_ = [("hProcess", wintypes.HANDLE),
                    ("hThread", wintypes.HANDLE),
                    ("dwProcessId", wintypes.DWORD),
                    ("dwThreadId", wintypes.DWORD)]


def _apis():
    if os.name != "nt":
        raise PublicToolRejected("Windows restricted primary token unavailable")
    k = ctypes.WinDLL("kernel32", use_last_error=True)
    a = ctypes.WinDLL("advapi32", use_last_error=True)
    k.GetCurrentProcess.argtypes = []
    k.GetCurrentProcess.restype = wintypes.HANDLE
    k.CloseHandle.argtypes = [wintypes.HANDLE]
    k.CloseHandle.restype = wintypes.BOOL
    k.LocalFree.argtypes = [wintypes.HANDLE]
    k.LocalFree.restype = wintypes.HANDLE
    k.ResumeThread.argtypes = [wintypes.HANDLE]
    k.ResumeThread.restype = wintypes.DWORD
    k.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
    k.TerminateProcess.restype = wintypes.BOOL
    k.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    k.WaitForSingleObject.restype = wintypes.DWORD
    k.GetExitCodeProcess.argtypes = [wintypes.HANDLE,
                                     ctypes.POINTER(wintypes.DWORD)]
    k.GetExitCodeProcess.restype = wintypes.BOOL
    a.OpenProcessToken.argtypes = [
        wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE)]
    a.OpenProcessToken.restype = wintypes.BOOL
    a.ConvertStringSidToSidW.argtypes = [
        wintypes.LPCWSTR, ctypes.POINTER(wintypes.HANDLE)]
    a.ConvertStringSidToSidW.restype = wintypes.BOOL
    a.CreateRestrictedToken.argtypes = [
        wintypes.HANDLE, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p,
        wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD,
        ctypes.POINTER(_SidAndAttributes), ctypes.POINTER(wintypes.HANDLE)]
    a.CreateRestrictedToken.restype = wintypes.BOOL
    a.IsTokenRestricted.argtypes = [wintypes.HANDLE]
    a.IsTokenRestricted.restype = wintypes.BOOL
    a.GetTokenInformation.argtypes = [
        wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD)]
    a.GetTokenInformation.restype = wintypes.BOOL
    a.IsValidSid.argtypes = [wintypes.HANDLE]
    a.IsValidSid.restype = wintypes.BOOL
    a.GetLengthSid.argtypes = [wintypes.HANDLE]
    a.GetLengthSid.restype = wintypes.DWORD
    a.SetTokenInformation.argtypes = [
        wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
    a.SetTokenInformation.restype = wintypes.BOOL
    a.InitializeAcl.argtypes = [ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD]
    a.InitializeAcl.restype = wintypes.BOOL
    a.AddAccessAllowedAce.argtypes = [
        ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    a.AddAccessAllowedAce.restype = wintypes.BOOL
    a.CreateProcessAsUserW.argtypes = [
        wintypes.HANDLE, wintypes.LPCWSTR, wintypes.LPWSTR,
        ctypes.c_void_p, ctypes.c_void_p, wintypes.BOOL, wintypes.DWORD,
        ctypes.c_void_p, wintypes.LPCWSTR, ctypes.POINTER(_StartupInfo),
        ctypes.POINTER(_ProcessInfo)]
    a.CreateProcessAsUserW.restype = wintypes.BOOL
    return k, a


def _os_restricted_token_verified(token, advapi):
    if not advapi.IsTokenRestricted(token):
        return False
    needed = wintypes.DWORD()
    advapi.GetTokenInformation(token, _TOKEN_RESTRICTED_SIDS,
                               None, 0, ctypes.byref(needed))
    if not 8 <= needed.value <= 65536:
        return False
    buffer = ctypes.create_string_buffer(needed.value)
    if not advapi.GetTokenInformation(token, _TOKEN_RESTRICTED_SIDS,
                                      buffer, needed, ctypes.byref(needed)):
        return False
    count = ctypes.cast(buffer, ctypes.POINTER(wintypes.DWORD)).contents.value
    if not 1 <= count <= 32:
        return False
    # SID_AND_ATTRIBUTES[] follows a DWORD, pointer aligned.
    offset = (ctypes.sizeof(wintypes.DWORD) +
              ctypes.alignment(_SidAndAttributes) - 1)
    offset -= offset % ctypes.alignment(_SidAndAttributes)
    if offset + count * ctypes.sizeof(_SidAndAttributes) > needed.value:
        return False
    base = ctypes.addressof(buffer) + offset
    for i in range(count):
        item = _SidAndAttributes.from_address(
            base + i * ctypes.sizeof(_SidAndAttributes))
        if not item.Sid or not advapi.IsValidSid(item.Sid):
            return False
        size = advapi.GetLengthSid(item.Sid)
        if not 8 <= size <= 68:
            return False
        observed = ctypes.string_at(item.Sid, size)
        # Exact current restricting SID in canonical binary SID format.
        expected = bytes((1, 1, 0, 0, 0, 0, 0, 1)) + (0).to_bytes(4, "little")
        if observed == expected:
            return True
    return False



def _set_restricted_token_default_dacl(source, restricted, sid, kernel, advapi):
    """Grant only owner/SYSTEM and restricting SID for newly created objects.

    A restricted token can otherwise create an object whose default DACL
    fails its own second (restricting-SID) access check. Do NOT apply this
    DACL to any existing user files or public directories.
    """
    needed = wintypes.DWORD()
    advapi.GetTokenInformation(source, _TOKEN_USER, None, 0,
                               ctypes.byref(needed))
    if not 16 <= needed.value <= 65536:
        raise PublicToolRejected("Caller token SID inaccessible")
    user_buf = ctypes.create_string_buffer(needed.value)
    if not advapi.GetTokenInformation(source, _TOKEN_USER, user_buf,
                                      needed, ctypes.byref(needed)):
        raise PublicToolRejected("Cannot read caller token user")
    user_sid = ctypes.cast(user_buf, ctypes.POINTER(_SidAndAttributes)).contents.Sid
    if not user_sid or not advapi.IsValidSid(user_sid):
        raise PublicToolRejected("Caller SID not OS validated")

    system_sid = wintypes.HANDLE()
    try:
        if not advapi.ConvertStringSidToSidW("S-1-5-18",
                                             ctypes.byref(system_sid)):
            raise PublicToolRejected("SYSTEM SID unavailable")
        acl = ctypes.create_string_buffer(512)
        if not advapi.InitializeAcl(acl, ctypes.sizeof(acl), 2):
            raise PublicToolRejected("Cannot initialize restricted object ACL")
        for item in (user_sid, sid, system_sid):
            if not advapi.AddAccessAllowedAce(acl, 2, _GENERIC_ALL, item):
                raise PublicToolRejected("Cannot add restricted default ACL")
        label = _TokenDefaultDacl(ctypes.addressof(acl))
        if not advapi.SetTokenInformation(
                restricted, _TOKEN_DEFAULT_DACL,
                ctypes.byref(label), ctypes.sizeof(label)):
            raise PublicToolRejected("Cannot set restricted token default ACL")
        required = wintypes.DWORD()
        advapi.GetTokenInformation(restricted, _TOKEN_DEFAULT_DACL,
                                   None, 0, ctypes.byref(required))
        if not 16 <= required.value <= 65536:
            raise PublicToolRejected("Restricted default ACL unreadable")
        observed_buf = ctypes.create_string_buffer(required.value)
        if not advapi.GetTokenInformation(
                restricted, _TOKEN_DEFAULT_DACL, observed_buf,
                required, ctypes.byref(required)):
            raise PublicToolRejected("Cannot attest restricted default ACL")
        observed = ctypes.cast(
            observed_buf, ctypes.POINTER(_TokenDefaultDacl)).contents
        if not observed.DefaultDacl:
            raise PublicToolRejected("Restricted default ACL missing")
        header = ctypes.cast(
            observed.DefaultDacl, ctypes.POINTER(_AclHeader)).contents
        if header.AclRevision != 2 or header.AceCount != 3:
            raise PublicToolRejected("Restricted default ACL rejected by OS")
    finally:
        if system_sid:
            kernel.LocalFree(system_sid)


class SuspendedRestrictedProcess:
    """Owner of a real suspended Windows process; NO stdio or handle inheritance."""

    def __init__(self, process_handle, thread_handle, kernel):
        self._handle = int(process_handle)
        self._thread = int(thread_handle)
        self._kernel = kernel
        self._resumed = False
        self._closed = False
        self.returncode = None

    def resume(self):
        if self._closed or self._resumed:
            raise PublicToolRejected("Restricted process not resumable")
        result = self._kernel.ResumeThread(self._thread)
        if result == 0xffffffff:
            raise PublicToolRejected("Could not resume restricted process")
        self._resumed = True

    def poll(self):
        if self.returncode is not None:
            return self.returncode
        code = wintypes.DWORD()
        if not self._kernel.GetExitCodeProcess(self._handle, ctypes.byref(code)):
            raise PublicToolRejected("Cannot inspect restricted process")
        if code.value != _STILL_ACTIVE:
            self.returncode = code.value
        return self.returncode

    def wait(self, timeout=5):
        if type(timeout) not in (int, float) or not 0 <= timeout <= 20:
            raise ValueError("Bounded wait required")
        result = self._kernel.WaitForSingleObject(self._handle, int(timeout * 1000))
        if result == _WAIT_TIMEOUT:
            raise subprocess.TimeoutExpired("restricted-child", timeout)
        if result != _WAIT_OBJECT_0:
            raise PublicToolRejected("Restricted child wait failed")
        return self.poll()

    def kill(self):
        if self._closed or self.poll() is not None:
            return
        if not self._kernel.TerminateProcess(self._handle, 23):
            raise PublicToolRejected("Could not terminate restricted child")

    def close(self):
        if self._closed:
            return
        try:
            if self.poll() is None:
                self.kill()
                self.wait(timeout=3)
        finally:
            self._closed = True
            self._kernel.CloseHandle(self._thread)
            self._kernel.CloseHandle(self._handle)


def spawn_suspended_restricted_primary(argv, *, cwd):
    """Only a trusted test harness may call this. No arbitrary tool execution.

    The returned process MUST be attached to WindowsChildJob before resume().
    If startup fails, no normal subprocess is spawned in its place.
    """
    if os.name != "nt":
        raise PublicToolRejected("Restricted-primary-token process requires Windows")
    if (type(argv) is not tuple or len(argv) < 2 or len(argv) > 6 or
            not all(type(x) is str and x and len(x) <= 1024 for x in argv)):
        raise PublicToolRejected("Invalid trusted process arguments")
    exe = Path(argv[0]).resolve()
    if not exe.is_file() or exe != Path(sys.executable).resolve():
        raise PublicToolRejected("Only the trusted current Python interpreter can launch")
    if type(cwd) is not str or Path(cwd).resolve() != exe.parent:
        raise PublicToolRejected("Untrusted working directory")
    # Never inherit parent environment or secrets; Python needs SystemRoot.
    system_root = os.environ.get("SystemRoot")
    if not system_root:
        raise PublicToolRejected("Windows SystemRoot unavailable")
    env = ctypes.create_unicode_buffer("SystemRoot=" + system_root + "\0\0")
    k, a = _apis()
    owner = wintypes.HANDLE()
    restricted = wintypes.HANDLE()
    sid = wintypes.HANDLE()
    pi = _ProcessInfo()
    created = False
    try:
        rights = (_TOKEN_ASSIGN_PRIMARY | _TOKEN_DUPLICATE |
                  _TOKEN_QUERY | _TOKEN_IMPERSONATE)
        if not a.OpenProcessToken(k.GetCurrentProcess(),
                                  rights, ctypes.byref(owner)):
            raise PublicToolRejected("Cannot open caller primary token")
        if not a.ConvertStringSidToSidW(_RESTRICTING_SID, ctypes.byref(sid)):
            raise PublicToolRejected("Restricted SID unavailable")
        restrict = _SidAndAttributes(sid, 0)
        if not a.CreateRestrictedToken(owner, _DISABLE_MAX_PRIVILEGE,
                                       0, None, 0, None, 1,
                                       ctypes.byref(restrict),
                                       ctypes.byref(restricted)):
            raise PublicToolRejected("Cannot create restricted primary token")
        if not _os_restricted_token_verified(restricted, a):
            raise PublicToolRejected("Restricted primary token missing kernel SID")
        # Restrict token-created kernel object DACL, not filesystem DACL.
        _set_restricted_token_default_dacl(owner, restricted, sid, k, a)
        startup = _StartupInfo()
        startup.cb = ctypes.sizeof(startup)
        # Default noninteractive window station. No stdio handles inherited.
        command = ctypes.create_unicode_buffer(subprocess.list2cmdline(argv))
        flags = (_CREATE_SUSPENDED | _CREATE_NO_WINDOW |
                 _CREATE_UNICODE_ENVIRONMENT)
        if not a.CreateProcessAsUserW(
                restricted, str(exe), command, None, None, False,
                flags, ctypes.cast(env, ctypes.c_void_p),
                str(exe.parent), ctypes.byref(startup), ctypes.byref(pi)):
            raise PublicToolRejected("Restricted primary process launch denied")
        created = True
        # Verify the ACTUAL newly created OS process primary token, not just
        # the token passed to CreateProcessAsUser.
        child_token = wintypes.HANDLE()
        try:
            if not a.OpenProcessToken(pi.hProcess, _TOKEN_QUERY,
                                      ctypes.byref(child_token)):
                raise PublicToolRejected("Cannot attest child primary token")
            if not _os_restricted_token_verified(child_token, a):
                raise PublicToolRejected("Child primary token lacks restricted SID")
        finally:
            if child_token:
                k.CloseHandle(child_token)
        result = SuspendedRestrictedProcess(pi.hProcess, pi.hThread, k)
        created = False
        return result
    except Exception:
        if created:
            k.TerminateProcess(pi.hProcess, 25)
            k.CloseHandle(pi.hThread)
            k.CloseHandle(pi.hProcess)
        raise PublicToolRejected("Restricted primary process refused; no fallback") from None
    finally:
        if restricted:
            k.CloseHandle(restricted)
        if owner:
            k.CloseHandle(owner)
        if sid:
            k.LocalFree(sid)
