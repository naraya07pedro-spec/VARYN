"""17S-12 OFFLINE Windows restricted-token resource access diagnostic.

Runs in its OWN disposable process, under normal user context until its
restricted impersonation probe. Opens only fixed paths provided by its test
harness, never reads bytes, never writes, never sends network requests.
Reports only resource CATEGORY and access disposition; paths are never echoed.
This does NOT establish restricted PRIMARY process startup or OS isolation.
"""
import ctypes
from ctypes import wintypes
import json
import os
import sys

SCHEMA = "varyn.windows_startup_acl_probe.v1"
_CATEGORIES = frozenset({
    "synthetic_allowed", "synthetic_denied", "runtime_copy_executable",
    "runtime_copy_dll", "runtime_copy_dir", "runtime_ancestor_1",
    "runtime_ancestor_2", "runtime_ancestor_3", "system_dll",
})
_BAD_HANDLE = ctypes.c_void_p(-1).value
_GENERIC_READ = 0x80000000
_FILE_EXECUTE_OR_TRAVERSE = 0x0020
_SHARE = 1 | 2 | 4
_OPEN_EXISTING = 3
_DIR_FLAG = 0x02000000
_NO_PRIVILEGES = 1
_TOKEN_DUPLICATE = 2
_TOKEN_QUERY = 8
_TOKEN_IMPERSONATE = 4


class _SidAndAttributes(ctypes.Structure):
    _fields_ = [("Sid", wintypes.HANDLE),
                ("Attributes", wintypes.DWORD)]


def _native_apis():
    if os.name != "nt":
        raise RuntimeError("Windows-only")
    k = ctypes.WinDLL("kernel32", use_last_error=True)
    a = ctypes.WinDLL("advapi32", use_last_error=True)
    k.GetCurrentProcess.argtypes = []
    k.GetCurrentProcess.restype = wintypes.HANDLE
    k.CloseHandle.argtypes = [wintypes.HANDLE]
    k.CloseHandle.restype = wintypes.BOOL
    k.LocalFree.argtypes = [wintypes.HANDLE]
    k.LocalFree.restype = wintypes.HANDLE
    k.CreateFileW.argtypes = [
        wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p,
        wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    k.CreateFileW.restype = wintypes.HANDLE
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
    a.ImpersonateLoggedOnUser.argtypes = [wintypes.HANDLE]
    a.ImpersonateLoggedOnUser.restype = wintypes.BOOL
    a.RevertToSelf.argtypes = []
    a.RevertToSelf.restype = wintypes.BOOL
    return k, a


def _open_disposition(path, kind, k, desired_access=_GENERIC_READ):
    # No contents are read; the kernel performs a real ACL check on open.
    handle = k.CreateFileW(path, desired_access, _SHARE, None,
                           _OPEN_EXISTING, _DIR_FLAG if kind == "directory" else 0,
                           None)
    if handle is not None and int(handle) != _BAD_HANDLE:
        k.CloseHandle(handle)
        return "allowed"
    code = ctypes.get_last_error()
    if code in (5, 1314):  # ACCESS_DENIED / PRIVILEGE_NOT_HELD
        return "denied"
    if code in (2, 3):  # FILE_NOT_FOUND / PATH_NOT_FOUND
        return "missing"
    return "other"


def probe(targets):
    if os.name != "nt":
        raise RuntimeError("Windows-only")
    if (type(targets) is not dict or not 2 <= len(targets) <= 10
            or not set(targets) <= _CATEGORIES):
        raise ValueError("Invalid offline resource categories")
    for resource in targets.values():
        if (type(resource) is not dict or set(resource) != {"path", "kind"}
                or type(resource["path"]) is not str
                or not 3 <= len(resource["path"]) <= 1024
                or resource["kind"] not in ("file", "directory")):
            raise ValueError("Invalid offline resource target")
    k, a = _native_apis()
    token = wintypes.HANDLE()
    restricted = wintypes.HANDLE()
    sid = wintypes.HANDLE()
    impersonating = False
    try:
        # Baseline must happen BEFORE impersonation. Only paths explicitly
        # provided by this offline synthetic regression are opened.
        baseline = {
            name: _open_disposition(resource["path"], resource["kind"], k)
            for name, resource in targets.items()
        }
        # FILE_TRAVERSE on directories and FILE_EXECUTE on images require
        # fewer permissions than GENERIC_READ. Do not conflate them.
        baseline_minimal = {
            name: _open_disposition(resource["path"], resource["kind"], k,
                                    _FILE_EXECUTE_OR_TRAVERSE)
            for name, resource in targets.items()
        }
        if not a.OpenProcessToken(k.GetCurrentProcess(),
                                  _TOKEN_DUPLICATE | _TOKEN_QUERY |
                                  _TOKEN_IMPERSONATE,
                                  ctypes.byref(token)):
            raise RuntimeError("OpenProcessToken refused")
        if not a.ConvertStringSidToSidW("S-1-5-12", ctypes.byref(sid)):
            raise RuntimeError("Restricting SID unavailable")
        entries = _SidAndAttributes(sid, 0)
        if not a.CreateRestrictedToken(token, _NO_PRIVILEGES,
                                       0, None, 0, None, 1,
                                       ctypes.byref(entries),
                                       ctypes.byref(restricted)):
            raise RuntimeError("Restricted token unavailable")
        if not a.IsTokenRestricted(restricted):
            raise RuntimeError("Restricted token unverified")
        if not a.ImpersonateLoggedOnUser(restricted):
            raise RuntimeError("Restricted impersonation refused")
        impersonating = True
        observed = {
            name: _open_disposition(resource["path"], resource["kind"], k)
            for name, resource in targets.items()
        }
        observed_minimal = {
            name: _open_disposition(resource["path"], resource["kind"], k,
                                    _FILE_EXECUTE_OR_TRAVERSE)
            for name, resource in targets.items()
        }
        if not a.RevertToSelf():
            raise RuntimeError("Cannot revert restricted impersonation")
        impersonating = False
        return {"format": SCHEMA, "restricted_thread_token": True,
                "restricted_primary_runtime_executed": False,
                "normal": baseline, "restricted": observed,
                "normal_minimal": baseline_minimal,
                "restricted_minimal": observed_minimal,
                "minimal_mode": "FILE_TRAVERSE(directory)/FILE_EXECUTE(file)",
                "raw_paths_persisted": False, "private_bytes_read": False}
    finally:
        if impersonating and not a.RevertToSelf():
            # Disposable test subprocess: never carry on under confused token.
            os._exit(19)
        if restricted:
            k.CloseHandle(restricted)
        if token:
            k.CloseHandle(token)
        if sid:
            k.LocalFree(sid)


def main():
    if os.name != "nt":
        return 2
    try:
        raw = sys.stdin.buffer.read(6145)
        if len(raw) > 6144:
            return 3
        obj = json.loads(raw.decode("utf-8", "strict"))
        if type(obj) is not dict or set(obj) != {"format", "targets"}:
            return 3
        if obj["format"] != SCHEMA:
            return 3
        result = probe(obj["targets"])
        sys.stdout.write(json.dumps(result, sort_keys=True, separators=(",", ":")))
        return 0
    except Exception as exc:
        # No original paths, user SIDs, file contents, token bytes or
        # sensitive native call arguments are included in this response.
        sys.stdout.write(json.dumps({"format": SCHEMA, "status": "failed",
                                     "error_type": type(exc).__name__}))
        return 5


if __name__ == "__main__":
    raise SystemExit(main())
