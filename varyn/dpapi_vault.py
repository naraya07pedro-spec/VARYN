"""Experimental Windows-user-bound DPAPI envelope for NEW standalone blobs.

NOT integrated with VARYN's plaintext SQLite database or backup functions.
NOT app-level login/authentication, cross-device portability, or a secure vault.
Windows DPAPI depends on the Windows user profile and OS account protections.
"""
import ctypes
import os
import tempfile
from ctypes import wintypes
from pathlib import Path

_MAGIC = b"VARYN-DPAPI-v1\x00"
_MAX_BYTES = 1024 * 1024
_UI_FORBIDDEN = 0x1


class UnsupportedPlatformError(RuntimeError):
    """DPAPI requires Windows."""


class SealedDataError(ValueError):
    """Invalid or undecryptable envelope; no sensitive details are returned."""


class _Blob(ctypes.Structure):
    _fields_ = [
        ("cbData", wintypes.DWORD),
        ("pbData", ctypes.POINTER(ctypes.c_ubyte)),
    ]


def _windows_functions():
    if os.name != "nt":
        raise UnsupportedPlatformError("Windows DPAPI is unavailable")
    crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    crypt32.CryptProtectData.argtypes = [
        ctypes.POINTER(_Blob), wintypes.LPCWSTR, ctypes.POINTER(_Blob),
        ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(_Blob),
    ]
    crypt32.CryptProtectData.restype = wintypes.BOOL
    crypt32.CryptUnprotectData.argtypes = [
        ctypes.POINTER(_Blob), ctypes.c_void_p, ctypes.POINTER(_Blob),
        ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(_Blob),
    ]
    crypt32.CryptUnprotectData.restype = wintypes.BOOL
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    kernel.LocalFree.restype = ctypes.c_void_p
    return crypt32, kernel


def _transform(data, decrypt):
    crypt32, kernel = _windows_functions()
    data = bytes(data)
    # create_string_buffer must stay alive throughout the native call.
    native_input = ctypes.create_string_buffer(data)
    source = _Blob(len(data), ctypes.cast(native_input, ctypes.POINTER(ctypes.c_ubyte)))
    destination = _Blob()
    try:
        if decrypt:
            ok = crypt32.CryptUnprotectData(
                ctypes.byref(source), None, None, None, None,
                _UI_FORBIDDEN, ctypes.byref(destination),
            )
        else:
            ok = crypt32.CryptProtectData(
                ctypes.byref(source), "VARYN experimental local blob", None,
                None, None, _UI_FORBIDDEN, ctypes.byref(destination),
            )
        if not ok:
            raise SealedDataError("DPAPI operation failed")
        return ctypes.string_at(destination.pbData, destination.cbData)
    finally:
        if destination.pbData:
            kernel.LocalFree(ctypes.cast(destination.pbData, ctypes.c_void_p))


def seal_bytes(data):
    if not isinstance(data, bytes) or not 1 <= len(data) <= _MAX_BYTES:
        raise ValueError("Expected nonempty bytes, at most 1 MiB")
    return _MAGIC + _transform(data, decrypt=False)


def unseal_bytes(data):
    if not isinstance(data, bytes) or not data.startswith(_MAGIC):
        raise SealedDataError("Invalid sealed envelope")
    payload = data[len(_MAGIC):]
    if not payload or len(payload) > _MAX_BYTES + 65536:
        raise SealedDataError("Invalid sealed envelope size")
    plaintext = _transform(payload, decrypt=True)
    if not 1 <= len(plaintext) <= _MAX_BYTES:
        raise SealedDataError("Invalid decrypted envelope size")
    return plaintext


def write_sealed(path, plaintext):
    """Publish to a NEW file only. No plaintext is written to a disk temp file."""
    sealed = seal_bytes(plaintext)
    target = Path(path).absolute()
    if not target.parent.is_dir():
        raise FileNotFoundError("Destination folder missing")
    if target.exists() or target.is_symlink():
        raise FileExistsError("Destination already exists")
    fd, temporary = tempfile.mkstemp(prefix=".varyn-sealed-", dir=target.parent)
    try:
        with os.fdopen(fd, "wb") as output:
            output.write(sealed)
            output.flush()
            os.fsync(output.fileno())
        # Atomic fail-closed no-overwrite publication on the same filesystem.
        os.link(temporary, target)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return target


def read_sealed(path):
    """Read a sealed file; refuse a symlink and never echo decrypted contents."""
    target = Path(path)
    if target.is_symlink() or not target.is_file():
        raise SealedDataError("Invalid sealed file")
    if target.stat().st_size > _MAX_BYTES + 65536 + len(_MAGIC):
        raise SealedDataError("Invalid sealed file size")
    return unseal_bytes(target.read_bytes())
