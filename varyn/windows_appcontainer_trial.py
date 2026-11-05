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
import shutil
from tempfile import TemporaryDirectory
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
    a.ConvertSidToStringSidW.argtypes = [
        wintypes.HANDLE, ctypes.POINTER(wintypes.LPWSTR)]
    a.ConvertSidToStringSidW.restype = wintypes.BOOL
    k.LocalFree.argtypes = [wintypes.HANDLE]
    k.LocalFree.restype = wintypes.HANDLE
    u.GetAppContainerFolderPath.argtypes = [
        wintypes.LPCWSTR, ctypes.POINTER(wintypes.LPWSTR)]
    u.GetAppContainerFolderPath.restype = ctypes.c_long
    ole = ctypes.WinDLL("ole32", use_last_error=True)
    ole.CoTaskMemFree.argtypes = [ctypes.c_void_p]
    ole.CoTaskMemFree.restype = None
    u._varyn_ole32 = ole
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



def _copy_runtime_into_owned_profile(exe, sid, kernel, advapi, userenv, *, broker_trial=False):
    """Only a disposable CI-created AppContainer's OS-approved storage.

    Do not grant broad access to host Python, account directories or System32.
    """
    as_text = wintypes.LPWSTR()
    folder_text = wintypes.LPWSTR()
    try:
        if not advapi.ConvertSidToStringSidW(sid, ctypes.byref(as_text)):
            raise PublicToolRejected("Cannot convert CI profile SID to folder key")
        hr = userenv.GetAppContainerFolderPath(
            as_text, ctypes.byref(folder_text))
        if hr != 0 or not folder_text:
            raise PublicToolRejected("AppContainer owned storage unavailable")
        local_root = Path(os.environ["LOCALAPPDATA"]).resolve()
        folder = Path(folder_text.value).resolve()
        if (not folder.is_relative_to(local_root)
                or "packages" not in (p.lower() for p in folder.parts)):
            raise PublicToolRejected("Unexpected AppContainer storage location")
        runtime = folder / "varyn_offline_python_copy"
        if runtime.exists():
            raise PublicToolRejected("CI runtime copy path already exists")
        runtime.mkdir()
        # Minimal ordinary-Python bootstrap dependencies, only owned copy.
        shutil.copy2(exe, runtime / exe.name)
        dll_count = 0
        for item in exe.parent.iterdir():
            if (item.is_file() and item.suffix.lower() == ".dll" and
                    item.name.lower().startswith(("python", "vcruntime"))):
                shutil.copy2(item, runtime / item.name)
                dll_count += 1
        if dll_count == 0:
            raise PublicToolRejected("CI Python runtime DLL not found")
        standard = Path(sys.base_prefix) / "Lib"
        if not (standard / "encodings").is_dir():
            raise PublicToolRejected("CI Python basic encodings unavailable")
        shutil.copytree(standard / "encodings", runtime / "Lib" / "encodings")
        for name in ("os.py", "codecs.py"):
            if (standard / name).is_file():
                shutil.copy2(standard / name, runtime / "Lib" / name)
        if broker_trial:
            # Offline Python stdlib dependencies of HMAC/JSON/pathlib are
            # required for the real native IPC proof. Copy ONLY trusted
            # standard-library code into the disposable profile-owned tree.
            # No site-packages, env secrets, user's files, or host ACL edits.
            shutil.copytree(
                standard, runtime / "Lib", dirs_exist_ok=True,
                ignore=shutil.ignore_patterns(
                    "site-packages", "__pycache__", "test", "tests",
                    "ensurepip", "venv", "idlelib", "tkinter",
                    "turtledemo", "pydoc_data"))
            dll_dir = Path(sys.base_prefix) / "DLLs"
            if dll_dir.is_dir():
                shutil.copytree(dll_dir, runtime / "DLLs")
        return runtime / exe.name
    finally:
        if folder_text:
            userenv._varyn_ole32.CoTaskMemFree(
                ctypes.cast(folder_text, ctypes.c_void_p))
        if as_text:
            kernel.LocalFree(ctypes.cast(as_text, wintypes.HANDLE))


def run_ci_only_zero_capability_trial(*, broker_trial=False, pipe_trial=False):
    """One fixed, no-network test action. NEVER call from production UI."""
    if type(broker_trial) is not bool or type(pipe_trial) is not bool:
        raise PublicToolRejected("CI AppContainer trial flag must be boolean")
    if broker_trial and pipe_trial:
        raise PublicToolRejected("CI trial modes cannot share one child")
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
    runtime_parent = None
    private_fixture = None
    owner_read_verified = False
    broker_request = None
    broker_secret = None
    broker_response = None
    broker_total = None
    broker_replay_refused = False
    pipe_guard = None
    pipe_attested = False
    journal = None
    journal_claimed = False
    journal_finalized = False
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
        trusted_copy = _copy_runtime_into_owned_profile(
            exe, sid, kernel, advapi, userenv,
            broker_trial=(broker_trial or pipe_trial))
        runtime_parent = trusted_copy.parent
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
        # Both files are newly-created disposable OFFLINE fixtures.
        # The granted file is INSIDE the disposable container storage; the
        # owner-private file is OUTSIDE it and is readable by the host.
        allowed = trusted_copy.parent / "synthetic-granted.txt"
        allowed.write_bytes(b"varyn-17s13-granted")
        private_fixture = TemporaryDirectory(prefix="varyn-ci-appowner-")
        owner_file = Path(private_fixture.name) / "synthetic-owner-only.txt"
        owner_file.write_bytes(b"varyn-17s13-owner-only")
        owner_read_verified = (
            owner_file.is_file() and
            owner_file.read_bytes() == b"varyn-17s13-owner-only"
        )
        if not owner_read_verified:
            raise PublicToolRejected("AppContainer synthetic positive control missing")
        # CHILD cannot receive provider credentials, model input or real files.
        # Exit 73 only after read-granted, owner-private denied and (when
        # requested) a single authenticated synthetic IPC round-trip.
        if pipe_trial:
            from varyn.windows_pipe_identity import OneShotWindowsPipe
            sid_text = wintypes.LPWSTR()
            try:
                if not advapi.ConvertSidToStringSidW(
                        sid, ctypes.byref(sid_text)):
                    raise PublicToolRejected("CI AppContainer package SID unavailable")
                pipe_guard = OneShotWindowsPipe(
                    appcontainer_sid=sid_text.value)
            finally:
                if sid_text:
                    kernel.LocalFree(
                        ctypes.cast(sid_text, wintypes.HANDLE))
            root = trusted_copy.parent
            shutil.copy2(
                Path(__file__).resolve().parent / "appcontainer_pipe_child.py",
                root / "appcontainer_pipe_child.py")
            args = [
                str(trusted_copy), "-I", "-S",
                str(root / "appcontainer_pipe_child.py"),
                str(allowed), str(owner_file), pipe_guard.name,
            ]
        elif broker_trial:
            from varyn.bounded_broker_protocol import (
                new_request, canonical,
            )
            root = trusted_copy.parent
            # Copy only the reviewed, fixed child/protocol code into the
            # disposable AppContainer-owned directory. No site packages.
            source_dir = Path(__file__).resolve().parent
            for module in ("bounded_broker_child.py",
                           "bounded_broker_protocol.py"):
                shutil.copy2(source_dir / module, root / module)
            broker_secret = secrets.token_bytes(32)
            key_file = root / "trial-key.bin"
            request_file = root / "trial-request.json"
            broker_response = root / "trial-response.json"
            with open(key_file, "xb") as output:
                output.write(broker_secret)
            broker_request = new_request(broker_secret, [4, 6, 11])
            with open(request_file, "xb") as output:
                output.write(canonical(broker_request))
            # Parent-private SQLite journal, outside the child AppContainer.
            # COMMIT the synthetic dispatch claim BEFORE process creation.
            # This CI fixture is removed after the test. Production needs
            # a persistent owner-selected journal and consent workflow.
            from varyn.durable_broker_journal import DurableOneShotJournal
            journal = DurableOneShotJournal(
                str(Path(private_fixture.name) / "broker-dispatch.sqlite"))
            journal_claimed = journal.claim(broker_request["request_id"])
            args = [str(trusted_copy), "-I", "-S",
                    str(root / "bounded_broker_child.py"),
                    str(allowed), str(owner_file),
                    str(request_file), str(broker_response), str(key_file)]
        else:
            source = (
                "import sys\\n"
                "try:\\n"
                " with open(sys.argv[1],'rb') as f: ok=f.read()\\n"
                " if ok!=b'varyn-17s13-granted': sys.exit(81)\\n"
                "except Exception: sys.exit(82)\\n"
                "try:\\n"
                " with open(sys.argv[2],'rb') as f: f.read()\\n"
                " sys.exit(83)\\n"
                "except PermissionError: sys.exit(73)\\n"
                "except FileNotFoundError: sys.exit(84)\\n"
                "except Exception: sys.exit(85)\\n"
            ).replace("\\n", "\n")
            args = [str(trusted_copy), "-I", "-S", "-c", source,
                    str(allowed), str(owner_file)]
        command = ctypes.create_unicode_buffer(subprocess.list2cmdline(args))
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
                str(trusted_copy), command, None, None, False, flags,
                ctypes.cast(environment, ctypes.c_void_p),
                str(trusted_copy.parent),
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
        if pipe_trial:
            if pipe_guard is None:
                raise PublicToolRejected("Missing AppContainer pipe listener")
            proof = pipe_guard.verify_one_client(proc.dwProcessId)
            pipe_attested = bool(
                proof["os_client_pid_verified"] and
                proof["package_sid_scoped_dacl"] and
                proof["local_only"] and not proof["inherited_handles"])
            if not pipe_attested:
                raise PublicToolRejected("AppContainer named pipe OS identity rejected")
        wait = kernel.WaitForSingleObject(proc.hProcess, 8000)
        if wait != _WAIT_OBJECT_0:
            raise PublicToolRejected("AppContainer child timeout or wait failure")
        raw = wintypes.DWORD()
        if not kernel.GetExitCodeProcess(proc.hProcess, ctypes.byref(raw)):
            raise PublicToolRejected("Cannot read AppContainer child exit status")
        exit_code = raw.value
        if broker_trial and exit_code == 73:
            from varyn.bounded_broker_protocol import (
                BrokerRejected, OneShotReplyVerifier, MAX_BYTES,
            )
            if broker_request is None or broker_response is None:
                raise PublicToolRejected("Missing CI broker challenge")
            if not broker_response.is_file():
                raise PublicToolRejected("AppContainer broker response missing")
            with open(broker_response, "rb") as response_file:
                raw_response = response_file.read(MAX_BYTES + 1)
            verifier = OneShotReplyVerifier(broker_request, broker_secret)
            try:
                broker_total = verifier.consume(raw_response)
            except BrokerRejected:
                raise PublicToolRejected("AppContainer broker reply rejected") from None
            try:
                verifier.consume(raw_response)
            except BrokerRejected:
                broker_replay_refused = True
            if broker_total != 21 or not broker_replay_refused:
                raise PublicToolRejected("Synthetic broker verification failed")
            if journal is None or not journal_claimed:
                raise PublicToolRejected("Broker dispatch journal missing")
            journal_finalized = (
                journal.finalize(
                    broker_request["request_id"], succeeded=True) == "completed")
            if not journal_finalized:
                raise PublicToolRejected("Broker dispatch finalization missing")
        completed = True
    finally:
        # Do not leave an IPC endpoint live while tearing down a profile.
        if pipe_guard is not None:
            pipe_guard.close()
        # Terminate unresponsive/test-crashed child before profile deletion.
        if process_created:
            if not completed:
                kernel.TerminateProcess(proc.hProcess, 82)
                kernel.WaitForSingleObject(proc.hProcess, 3000)
            kernel.CloseHandle(proc.hThread)
            kernel.CloseHandle(proc.hProcess)
        if initialized:
            kernel.DeleteProcThreadAttributeList(attr_buf)
        if runtime_parent is not None:
            # Deleting only the known child of our newly created profile.
            shutil.rmtree(runtime_parent)
        if journal is not None:
            journal.close()
        if private_fixture is not None:
            private_fixture.cleanup()
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
        "python_runtime_executed": exit_code in (73, 81, 82, 83, 84, 85),
        "python_exit_status": exit_code,
        "network_used": False,
        "synthetic_owner_positive_control": owner_read_verified,
        "synthetic_granted_read_ok": exit_code in (73, 83, 84, 85),
        "synthetic_private_read_denied": exit_code == 73,
        "private_file_test_executed": exit_code in (73, 83, 84, 85),
        "production_tool_integrated": False,
        "one_shot_broker_trial": broker_trial,
        "named_pipe_trial": pipe_trial,
        "os_named_pipe_client_pid_attested": pipe_attested,
        "authenticated_response_verified": broker_total == 21,
        "replayed_response_refused": broker_replay_refused,
        "synthetic_broker_total": broker_total,
        "parent_journal_claimed_before_launch": journal_claimed,
        "parent_journal_completed_after_verification": journal_finalized,
    }
