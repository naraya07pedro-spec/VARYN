"""17S-17: independently inspect real suspended child handle inheritance.

Only CI test handles: two explicitly selected anonymous pipe ends plus one
inheritable excluded EVENT. Native DuplicateHandle runs from the trusted
parent BEFORE ResumeThread, avoiding invalid-handle errors surfaced by
Python inside the AppContainer and excluding post-start handle reuse.

This checks the three known fixture objects, NOT the complete process
handle table or every possible inherited/duplicated OS resource.
"""
import ctypes
from ctypes import wintypes
import os

from varyn.public_github_tool import PublicToolRejected


def _number(value):
    return int(value.value if hasattr(value, "value") else value)


def attest_suspended_child_fixture_handles(process_handle, fixture):
    if os.name != "nt":
        raise PublicToolRejected("Suspended Windows child attestation unavailable")
    if not process_handle or fixture is None:
        raise PublicToolRejected("No child or expected handles for attestation")
    k = ctypes.WinDLL("kernel32", use_last_error=True)
    k.GetCurrentProcess.argtypes = []
    k.GetCurrentProcess.restype = wintypes.HANDLE
    k.DuplicateHandle.argtypes = [
        wintypes.HANDLE, wintypes.HANDLE,
        wintypes.HANDLE, ctypes.POINTER(wintypes.HANDLE),
        wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    k.DuplicateHandle.restype = wintypes.BOOL
    k.CloseHandle.argtypes = [wintypes.HANDLE]
    k.CloseHandle.restype = wintypes.BOOL
    compare = getattr(k, "CompareObjectHandles", None)
    if compare is None:
        raise PublicToolRejected("Native Windows handle identity API unavailable")
    compare.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    compare.restype = wintypes.BOOL
    current = k.GetCurrentProcess()
    target = wintypes.HANDLE()
    checked = []
    try:
        for expected in (fixture.child_stdin, fixture.child_stdout):
            target = wintypes.HANDLE()
            if not k.DuplicateHandle(
                    process_handle, expected, current,
                    ctypes.byref(target), 0, False, 0x2):
                raise PublicToolRejected(
                    "Expected allowlisted child handle absent")
            try:
                if not compare(target, expected):
                    raise PublicToolRejected(
                        "Child handle did not reference expected pipe")
                checked.append(True)
            finally:
                k.CloseHandle(target)
        # A deliberately inheritable event was *omitted* from the explicit
        # handle list. If a same-valued handle is present in child, compare
        # the kernel object, not the numeric value alone.
        target = wintypes.HANDLE()
        if k.DuplicateHandle(
                process_handle, fixture.decoy, current,
                ctypes.byref(target), 0, False, 0x2):
            try:
                if compare(target, fixture.decoy):
                    raise PublicToolRejected(
                        "UNLISTED PARENT EVENT LEAKED INTO CHILD")
                # Different OS object at the same numeric slot: does not
                # demonstrate that this specific decoy was inherited.
                decoy_absent = True
                reused_slot = True
            finally:
                k.CloseHandle(target)
        else:
            error = ctypes.get_last_error()
            if error != 6:  # Win32 ERROR_INVALID_HANDLE
                raise PublicToolRejected(
                    "Unlisted event presence cannot be attested")
            decoy_absent = True
            reused_slot = False
        if len(checked) != 2 or not all(checked) or not decoy_absent:
            raise PublicToolRejected("Invalid native fixture handle result")
        return {
            "two_expected_pipe_objects_verified": True,
            "excluded_parent_event_verified_absent": True,
            "decoy_numeric_slot_reused": reused_slot,
            "process_was_suspended": True,
            "full_handle_table_audited": False,
        }
    finally:
        # Duplicated handles are released individually, even on errors.
        pass
