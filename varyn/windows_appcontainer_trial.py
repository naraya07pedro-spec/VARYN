"""17S-13: CI-only native Windows AppContainer process-creation experiment.

This MUST NEVER run in production, on the owner's laptop, or on user files:
- requires the hosted GitHub Windows runner's CI environment and explicit opt-in
- creates a UNIQUE disposable AppContainer profile and deletes only that profile
- launches only the currently trusted Python interpreter with fixed -I -S code
- allows ZERO capability SIDs, ZERO inherited handles and ZERO network calls
- checks the ACTUAL suspended child primary token before resuming execution
- returns bounded booleans/status codes, never SID, path, env or file contents

This does not implement a broker, a private-file tool, or Option C synchronization.
"""
import ctypes
from ctypes import wintypes
import os
from pathlib import Path
import secrets
import subprocess
import sys

from varyn.public_github_tool import PublicToolRejected

_SCHEMA = "varyn.windows_appcontainer_trial.v1"
_TOKEN_QUERY = 0x0008
_TOKEN_IS_APPCONTAINER = 29
_TOKEN_CAPABILITIES = 30
_TOKEN_APPCONTAINER_SID = 31
_ATTR_SECURITY_CAPABILITIES = 0x00020009
_EXTENDED_STARTUPINFO_PRESENT = 0x00080000
_CREATE_SUSPENDED = 0x00000004
_CREATE_NO_WINDOW = 0x08000000
_CREATE_UNICODE_ENV = 0x00000400
_WAIT_OBJECT_0 = 0
_WAIT_TIMEOUT = 258
_STILL_ACTIVE = 259

if os.name == "nt":
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

    class _StartupInfoEx(ctypes.Structure):
        _fields_ = [("StartupInfo", _StartupInfo),
                    ("lpAttributeList", ctypes.c_void_p)]

    class _ProcessInfo(ctypes.Structure):
        _fields_ = [("hProcess", wintypes.HANDLE),
                    ("hThread", wintypes.HANDLE),
                    ("dwProcessId", wintypes.DWORD),
                    ("dwThreadId", wintypes.DWORD)]

    class _SecurityCapabilities(ctypes.Structure):
        _fields_ = [("AppContainerSid", wintypes.HANDLE),
                    ("Capabilities", ctypes.c_void_p),
                    ("CapabilityCount", wintypes.DWORD),
                    ("Reserved", wintypes.DWORD)]


def _native():
    if os.name != "nt":
        raise PublicToolRejected("AppContainer unavailable outside Windows")
    k = ctypes.WinDLL("kernel32", use_last_error=True)
    a = ctypes.WinDLL("advapi32", use_last_error=True)
    u = ctypes.WinDLL("userenv", use_last_error=True)

    k.InitializeProcThreadAttributeList.argtypes = [
        ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD,
        ctypes.POINTER(ctypes.c_size_t)]
    k.InitializeProcThreadAttributeList.restype = wintypes.BOOL
    k.UpdateProcThreadAttribute.argtypes = [
        ctypes.c_void_p, wintypes.DWORD, ctypes.c_size_t,
        ctypes.c_void_p, ctypes.c_size_t, ctypes.c_void_p,
        ctypes.c_void_p]
    k.UpdateProcThreadAttribute.restype = wintypes.BOOL
    k.DeleteProcThreadAttributeList.argtypes = [ctypes.c_void_p]
    k.DeleteProcThreadAttributeList.restype = None
    k.CreateProcessW.argtypes = [
        wintypes.LPCWSTR, wintypes.LPWSTR, ctypes.c_void_p,
        ctypes.c_void_p, wintypes.BOOL, wintypes.DWORD,
        ctypes.c_void_p, wintypes.LPCWSTR,
        ctypes.POINTER(_StartupInfoEx), ctypes.POINTER(_ProcessInfo)]
    k.CreateProcessW.restype = wintypes.BOOL
    k.ResumeThread.argtypes = [wintypes.HANDLE]
    k.ResumeThread.restype = wintypes.DWORD
    k.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
    k.TerminateProcess.restype = wintypes.BOOL
    k.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    k.WaitForSingleObject.restype = wintypes.DWORD
    k.GetExitCodeProcess.argtypes = [wintypes.HANDLE,
                                     ctypes.POINTER(wintypes.DWORD)]
    k.GetExitCodeProcess.restype = wintypes.BOOL
    k.CloseHandle.argtypes = [wintypes.HANDLE]
    k.CloseHandle.restype = wintypes.BOOL
    a.OpenProcessToken.argtypes = [
        wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE)]
    a.OpenProcessToken.restype = wintypes.BOOL
    a.GetTokenInformation.argtypes = [
        wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p,
        wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
    a.GetTokenInformation.restype = wintypes.BOOL
    a.EqualSid.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    a.EqualSid.restype = wintypes.BOOL
    a.IsValidSid.argtypes = [wintypes.HANDLE]
    a.IsValidSid.restype = wintypes.BOOL
    a.FreeSid.argtypes = [wintypes.HANDLE]
    a.FreeSid.restype = ctypes.c_void_p
    u.CreateAppContainerProfile.argtypes = [
        wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.LPCWSTR,
        ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE)]
    u.CreateAppContainerProfile.restype = ctypes.c_long
    u.DeleteAppContainerProfile.argtypes = [wintypes.LPCWSTR]
    u.DeleteAppContainerProfile.restype = ctypes.c_long
    return k, a, u


def _token_data(token, category, size_limit, advapi):
    size = wintypes.DWORD()
    advapi.GetTokenInformation(token, category, None, 0, ctypes.byref(size))
    if not 4 <= size.value <= size_limit:
        raise PublicToolRejected("Untrusted AppContainer attestation size")
    buf = ctypes.create_string_buffer(size.value)
    if not advapi.GetTokenInformation(
            token, category, buf, size, ctypes.byref(size)):
        raise PublicToolRejected("AppContainer native token readback failed")
    return buf


def _attest_child(process, expected_sid, advapi, kernel):
    token = wintypes.HANDLE()
    try:
        if not advapi.OpenProcessToken(process, _TOKEN_QUERY,
                                       ctypes.byref(token)):
            raise PublicToolRejected("Cannot inspect child AppContainer primary token")
        flag = _token_data(token, _TOKEN_IS_APPCONTAINER, 64, advapi)
        if ctypes.cast(flag, ctypes.POINTER(wintypes.DWORD)).contents.value != 1:
            raise PublicToolRejected("Actual child is not AppContainer")
        info = _token_data(token, _TOKEN_APPCONTAINER_SID, 256, advapi)
        sid = ctypes.cast(info, ctypes.POINTER(wintypes.HANDLE)).contents.value
        if (not sid or not advapi.IsValidSid(sid)
                or not advapi.EqualSid(sid, expected_sid)):
            raise PublicToolRejected("Actual child AppContainer SID mismatch")
        cap_buf = _token_data(token, _TOKEN_CAPABILITIES, 4096, advapi)
        count = ctypes.cast(cap_buf, ctypes.POINTER(wintypes.DWORD)).contents.value
        if count != 0:
            raise PublicToolRejected("Unexpected child AppContainer capabilities")
        return True
    finally:
        if token:
            kernel.CloseHandle(token)


def run_ci_only_zero_capability_trial():
    """One fixed, no-network test action. NEVER call from production UI."""
    if (os.name != "nt" or os.environ.get("GITHUB_ACTIONS") != "true"
            or os.environ.get("RUNNER_OS") != "Windows"
            or os.environ.get("VARYN_CI_APPCONTAINER_TRIAL") != "1"):
        raise PublicToolRejected("AppContainer experiment only allowed on opted-in Windows CI")
    exe = Path(sys.executable).resolve()
    if not exe.is_file() or exe.suffix.lower() != ".exe":
        raise PublicToolRejected("CI trusted Windows Python unavailable")
    kernel, advapi, userenv = _native()
    # Unique random profile. Refuse existing profiles, never overwrite them.
    name = "VarynCi13_" + str(os.getpid()) + "_" + secrets.token_hex(8)
    sid = wintypes.HANDLE()
    created = False
    attr_buf = None
    initialized = False
    proc = _ProcessInfo()
    process_created = False
    completed = False
    exit_code = None
    cleaned = False
    try:
        hr = userenv.CreateAppContainerProfile(
            name, name, "Disposable offline VARYN CI restricted process test",
            None, 0, ctypes.byref(sid))
        if hr != 0:
            # Any failure including "already exists" is fail-closed. Never
            # delete profiles that this invocation did not itself create.
            raise PublicToolRejected("Could not create unique CI AppContainer profile")
        created = True
        if not sid or not advapi.IsValidSid(sid):
            raise PublicToolRejected("Created CI AppContainer SID invalid")
        length = ctypes.c_size_t()
        measured = kernel.InitializeProcThreadAttributeList(
            None, 1, 0, ctypes.byref(length))
        last_error = ctypes.get_last_error()
        # Microsoft's documented size query returns FALSE with
        # ERROR_INSUFFICIENT_BUFFER (122), even on success of size discovery.
        if measured or last_error != 122 or not 16 <= length.value <= 65536:
            raise PublicToolRejected("Unexpected AppContainer attribute size")
        attr_buf = ctypes.create_string_buffer(length.value)
        if not kernel.InitializeProcThreadAttributeList(
                attr_buf, 1, 0, ctypes.byref(length)):
            raise PublicToolRejected("AppContainer attribute initialization failed")
        initialized = True
        security = _SecurityCapabilities(
            sid, None, 0, 0
        )  # No network or other capability SIDs.
        if not kernel.UpdateProcThreadAttribute(
                attr_buf, 0, _ATTR_SECURITY_CAPABILITIES,
                ctypes.byref(security), ctypes.sizeof(security),
                None, None):
            raise PublicToolRejected("No-capability process attribute refused")

        si = _StartupInfoEx()
        si.StartupInfo.cb = ctypes.sizeof(si)
        si.lpAttributeList = ctypes.addressof(attr_buf)
        # No user-controlled command, no network intent, no inherited handles.
        # Python reaching the fixed returncode 73 proves runtime bootstrap.
        source = "import sys; sys.exit(73)"
        command = ctypes.create_unicode_buffer(
            subprocess.list2cmdline([str(exe), "-I", "-S", "-c", source]))
        systemroot = os.environ.get("SystemRoot")
        localappdata = os.environ.get("LOCALAPPDATA")
        if not systemroot or not localappdata:
            raise PublicToolRejected("Windows CI AppContainer environment unavailable")
        # CreateProcessW resolves AppContainer profile storage under
        # LOCALAPPDATA. Never inherit the full host environment or secrets.
        environment = ctypes.create_unicode_buffer(
            "LOCALAPPDATA=" + localappdata + "\0" +
            "SystemRoot=" + systemroot + "\0\0")
        flags = (_EXTENDED_STARTUPINFO_PRESENT | _CREATE_SUSPENDED |
                 _CREATE_NO_WINDOW | _CREATE_UNICODE_ENV)
        if not kernel.CreateProcessW(
                str(exe), command, None, None, False, flags,
                ctypes.cast(environment, ctypes.c_void_p), str(exe.parent),
                ctypes.byref(si), ctypes.byref(proc)):
            code = ctypes.get_last_error()
            # The Win32 numeric status is safe to report in an OFFLINE CI
            # diagnostic; never include raw executable/owner paths.
            raise PublicToolRejected(
                "AppContainer process creation denied (win32="
                + str(code) + ")")
        process_created = True
        _attest_child(proc.hProcess, sid, advapi, kernel)
        # Keep process suspended until its actual primary token is attested.
        resumed = kernel.ResumeThread(proc.hThread)
        if resumed == 0xffffffff or resumed != 1:
            raise PublicToolRejected("AppContainer child resume refused")
        wait = kernel.WaitForSingleObject(proc.hProcess, 8000)
        if wait != _WAIT_OBJECT_0:
            raise PublicToolRejected("AppContainer child timeout or wait failure")
        raw = wintypes.DWORD()
        if not kernel.GetExitCodeProcess(proc.hProcess, ctypes.byref(raw)):
            raise PublicToolRejected("Cannot read AppContainer child exit status")
        exit_code = raw.value
        completed = True
    finally:
        # Terminate unresponsive/test-crashed child before profile deletion.
        if process_created:
            if not completed:
                kernel.TerminateProcess(proc.hProcess, 82)
                kernel.WaitForSingleObject(proc.hProcess, 3000)
            kernel.CloseHandle(proc.hThread)
            kernel.CloseHandle(proc.hProcess)
        if initialized:
            kernel.DeleteProcThreadAttributeList(attr_buf)
        if sid:
            advapi.FreeSid(sid)
        if created:
            # Only own profile, never a pre-existing name. No profile
            # reference remains open. A failed delete is a hard failure.
            hr = userenv.DeleteAppContainerProfile(name)
            cleaned = (hr == 0)
            if not cleaned:
                raise PublicToolRejected("CI AppContainer profile cleanup failed")
    if not completed:
        raise PublicToolRejected("AppContainer CI process incomplete")
    return {
        "format": _SCHEMA,
        "native_primary_appcontainer_attested": True,
        "zero_capability_sids_attested": True,
        "inherited_handles": False,
        "process_terminated": True,
        "disposable_profile_deleted": cleaned,
        "python_runtime_executed": exit_code == 73,
        "python_exit_status": exit_code,
        "network_used": False,
        "private_file_test_executed": False,
        "production_tool_integrated": False,
    }
