"""17S-10 OFFLINE Windows restricted-token read probe, never a production tool.

This file lives under tests/ and is not packaged in the VARYN desktop ZIP.
The parent test supplies a disposable synthetic file; this process never
receives personal context, network URLs, or provider tokens.

CreateRestrictedToken with a restricting SID requires TWO Windows DACL
access checks; the second one must also allow the read. Normal same-user
files do not grant explicit access to NT AUTHORITY\RESTRICTED (S-1-5-12).
This is a restricted *thread impersonation* demonstration, NOT proof that
the live GitHub subprocess has a restricted primary process token.
"""
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import sys

_TOKEN_DUPLICATE = 0x0002
_TOKEN_IMPERSONATE = 0x0004
_TOKEN_QUERY = 0x0008
_DISABLE_MAX_PRIVILEGE = 0x00000001


class _SidAndAttributes(ctypes.Structure):
    _fields_ = [("Sid", wintypes.HANDLE), ("Attributes", wintypes.DWORD)]


def _native_probe(path):
    if os.name != "nt":
        raise RuntimeError("Native Windows token proof requires Windows")

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    advapi = ctypes.WinDLL("advapi32", use_last_error=True)

    kernel.GetCurrentProcess.argtypes = []
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.restype = wintypes.BOOL
    kernel.LocalFree.argtypes = [wintypes.HANDLE]
    kernel.LocalFree.restype = wintypes.HANDLE

    advapi.OpenProcessToken.argtypes = [
        wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE)]
    advapi.OpenProcessToken.restype = wintypes.BOOL
    advapi.ConvertStringSidToSidW.argtypes = [
        wintypes.LPCWSTR, ctypes.POINTER(wintypes.HANDLE)]
    advapi.ConvertStringSidToSidW.restype = wintypes.BOOL
    advapi.CreateRestrictedToken.argtypes = [
        wintypes.HANDLE, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p,
        wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD,
        ctypes.POINTER(_SidAndAttributes), ctypes.POINTER(wintypes.HANDLE)]
    advapi.CreateRestrictedToken.restype = wintypes.BOOL
    advapi.IsTokenRestricted.argtypes = [wintypes.HANDLE]
    advapi.IsTokenRestricted.restype = wintypes.BOOL
    advapi.ImpersonateLoggedOnUser.argtypes = [wintypes.HANDLE]
    advapi.ImpersonateLoggedOnUser.restype = wintypes.BOOL
    advapi.RevertToSelf.argtypes = []
    advapi.RevertToSelf.restype = wintypes.BOOL

    token = wintypes.HANDLE()
    restricted = wintypes.HANDLE()
    sid = wintypes.HANDLE()
    impersonating = False
    try:
        # First establish a positive control before restricting the thread.
        with open(path, "rb") as handle:
            before = handle.read()
        if before != b"varyn-synthetic-owner-only":
            raise RuntimeError("Synthetic input mismatch")
        rights = _TOKEN_DUPLICATE | _TOKEN_IMPERSONATE | _TOKEN_QUERY
        if not advapi.OpenProcessToken(kernel.GetCurrentProcess(),
                                       rights, ctypes.byref(token)):
            raise OSError(ctypes.get_last_error(), "OpenProcessToken failed")
        if not advapi.ConvertStringSidToSidW(
                "S-1-5-12", ctypes.byref(sid)):
            raise OSError(ctypes.get_last_error(), "ConvertStringSid failed")
        restrict = _SidAndAttributes(sid, 0)
        if not advapi.CreateRestrictedToken(
                token, _DISABLE_MAX_PRIVILEGE, 0, None, 0, None,
                1, ctypes.byref(restrict), ctypes.byref(restricted)):
            raise OSError(ctypes.get_last_error(), "CreateRestrictedToken failed")
        if not advapi.IsTokenRestricted(restricted):
            raise RuntimeError("OS denied restricted token attestation")
        if not advapi.ImpersonateLoggedOnUser(restricted):
            raise OSError(ctypes.get_last_error(), "Restricted impersonation denied")
        impersonating = True
        # Windows kernel enforces the file open against the restricted token,
        # not an application-level comparison of file paths or names.
        try:
            with open(path, "rb") as handle:
                handle.read()
            denied = False
        except PermissionError:
            denied = True
        # We DO NOT read any other file while impersonating.
        if not advapi.RevertToSelf():
            raise OSError(ctypes.get_last_error(), "RevertToSelf failed")
        impersonating = False
        return {"format": "varyn.windows_restricted_read_probe.v1",
                "positive_control_read": True,
                "restricted_token_native": True,
                "synthetic_read_denied": denied,
                "provider_calls": 0,
                "production_subprocess_restricted": False}
    finally:
        if impersonating and not advapi.RevertToSelf():
            # Fatal in this disposable child; never continue with a
            # privileged / half-restored thread.
            os._exit(17)
        if restricted:
            kernel.CloseHandle(restricted)
        if token:
            kernel.CloseHandle(token)
        if sid:
            kernel.LocalFree(sid)


def main():
    if os.name != "nt" or len(sys.argv) != 1:
        return 2
    try:
        # The only input is the test-created synthetic path.
        target = sys.stdin.buffer.readline(2048).decode("utf-8", "strict").rstrip("\r\n")
        if not target or len(target) > 1024:
            return 3
        result = _native_probe(target)
        sys.stdout.write(json.dumps(result, sort_keys=True))
        return 0 if result["synthetic_read_denied"] else 4
    except Exception as exc:
        # No target or file bytes, token data, or environment values leak.
        sys.stdout.write(json.dumps({"format": "varyn.windows_restricted_read_probe.v1",
                                     "status": "denied_or_failed",
                                     "error_type": type(exc).__name__}))
        return 5


if __name__ == "__main__":
    raise SystemExit(main())
