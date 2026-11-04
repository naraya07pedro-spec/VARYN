"""17C: Windows-only scoped directory-handle file access, synthetic prototype.

A trusted host selects an absolute folder. The directory is pinned by a
non-inheritable Win32 handle, and children are opened by NtCreateFile with
OBJECT_ATTRIBUTES.RootDirectory, FILE_OPEN_REPARSE_POINT, FILE_OPEN only.
No writes, no recursive traversal, no execution or network access.

Windows native behavior MUST pass independent windows-latest CI tests.
This is not an OS process sandbox, identity authentication, or approval to read
sensitive files. Unavailable native primitives FAIL CLOSED, never fall back to
an unanchored pathname.
"""
import ctypes
import os
import re
from ctypes import wintypes

from varyn.agent_runtime import AgentRejected

_REPARSE = 0x400
_DIRECTORY = 0x10
_OFFLINE = 0x00001000
_RECALL_ON_OPEN = 0x00040000
_RECALL_ON_DATA_ACCESS = 0x00400000
_UNSAFE_REMOTE_ATTRIBUTES = (_REPARSE | _OFFLINE |
                             _RECALL_ON_OPEN | _RECALL_ON_DATA_ACCESS)
_DRIVE_FIXED = 3
_FILE_LIST_DIRECTORY = 0x0001
_FILE_READ_DATA = 0x0001
_FILE_READ_ATTRIBUTES = 0x0080
_SYNCHRONIZE = 0x00100000
_SHARE_ALL = 0x00000007
_OPEN_EXISTING = 3
_FILE_OPEN = 1
_FLAG_OPEN_REPARSE = 0x00200000
_FLAG_NON_DIRECTORY = 0x40
_FLAG_SYNC_NONALERT = 0x20
_FLAG_BACKUP_SEMANTICS = 0x02000000
_FLAG_WIN32_OPEN_REPARSE = 0x00200000
_OBJ_CASE_INSENSITIVE = 0x40
_FILE_NAMES_INFORMATION = 12
_STATUS_NO_MORE_FILES = 0x80000006
_MAX_ENUMERATED = 2048
_INVALID_HANDLE = ctypes.c_void_p(-1).value
_SAFE_NAME = re.compile(r"\A[A-Za-z0-9][A-Za-z0-9_. -]{0,119}\.(?:txt|md)\Z", re.I)


class _UnicodeString(ctypes.Structure):
    _fields_ = [
        ("Length", wintypes.USHORT),
        ("MaximumLength", wintypes.USHORT),
        ("Buffer", ctypes.c_void_p),
    ]


class _ObjectAttributes(ctypes.Structure):
    _fields_ = [
        ("Length", wintypes.ULONG),
        ("RootDirectory", wintypes.HANDLE),
        ("ObjectName", ctypes.POINTER(_UnicodeString)),
        ("Attributes", wintypes.ULONG),
        ("SecurityDescriptor", ctypes.c_void_p),
        ("SecurityQualityOfService", ctypes.c_void_p),
    ]


class _IoStatusBlock(ctypes.Structure):
    _fields_ = [("Status", ctypes.c_void_p), ("Information", ctypes.c_size_t)]


class _ByHandleFileInformation(ctypes.Structure):
    _fields_ = [
        ("dwFileAttributes", wintypes.DWORD),
        ("ftCreationTime", wintypes.FILETIME),
        ("ftLastAccessTime", wintypes.FILETIME),
        ("ftLastWriteTime", wintypes.FILETIME),
        ("dwVolumeSerialNumber", wintypes.DWORD),
        ("nFileSizeHigh", wintypes.DWORD),
        ("nFileSizeLow", wintypes.DWORD),
        ("nNumberOfLinks", wintypes.DWORD),
        ("nFileIndexHigh", wintypes.DWORD),
        ("nFileIndexLow", wintypes.DWORD),
    ]


def _windows_apis():
    if os.name != "nt":
        raise AgentRejected("Windows native directory handles unavailable")
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    ntdll = ctypes.WinDLL("ntdll", use_last_error=True)
    kernel.CreateFileW.argtypes = (
        wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p,
        wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE,
    )
    kernel.CreateFileW.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
    kernel.CloseHandle.restype = wintypes.BOOL
    kernel.GetDriveTypeW.argtypes = (wintypes.LPCWSTR,)
    kernel.GetDriveTypeW.restype = wintypes.UINT
    kernel.GetFileInformationByHandle.argtypes = (
        wintypes.HANDLE, ctypes.POINTER(_ByHandleFileInformation),
    )
    kernel.GetFileInformationByHandle.restype = wintypes.BOOL
    kernel.ReadFile.argtypes = (
        wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p,
    )
    kernel.ReadFile.restype = wintypes.BOOL
    ntdll.NtCreateFile.argtypes = (
        ctypes.POINTER(wintypes.HANDLE), wintypes.DWORD,
        ctypes.POINTER(_ObjectAttributes), ctypes.POINTER(_IoStatusBlock),
        ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.DWORD,
        wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD,
    )
    ntdll.NtCreateFile.restype = ctypes.c_long
    ntdll.NtQueryDirectoryFile.argtypes = (
        wintypes.HANDLE, wintypes.HANDLE, ctypes.c_void_p, ctypes.c_void_p,
        ctypes.POINTER(_IoStatusBlock), ctypes.c_void_p,
        wintypes.ULONG, wintypes.ULONG, wintypes.BOOLEAN,
        ctypes.c_void_p, wintypes.BOOLEAN,
    )
    ntdll.NtQueryDirectoryFile.restype = ctypes.c_long
    return kernel, ntdll


def _file_info(kernel, handle):
    info = _ByHandleFileInformation()
    if not kernel.GetFileInformationByHandle(handle, ctypes.byref(info)):
        raise AgentRejected("Windows native file metadata unavailable")
    size = (int(info.nFileSizeHigh) << 32) | int(info.nFileSizeLow)
    file_id = (int(info.nFileIndexHigh) << 32) | int(info.nFileIndexLow)
    return info, size, file_id


def _require_fixed_local_volume(path, kernel):
    """Reject UNC, mapped remote, removable, and unknown-volume paths."""
    anchor = str(path.anchor)
    if (len(anchor) != 3 or anchor[1:] != ":\\" or
            not ("A" <= anchor[0].upper() <= "Z")):
        raise AgentRejected("Windows scope requires a drive-letter root")
    if kernel.GetDriveTypeW(anchor) != _DRIVE_FIXED:
        raise AgentRejected("Windows scope requires a fixed local volume")


def _content_signature(info, size, file_id):
    """Best-effort same-handle change detector, NOT immutable snapshot proof."""
    return (
        info.dwVolumeSerialNumber, file_id, size,
        info.dwFileAttributes, info.nNumberOfLinks,
        info.ftLastWriteTime.dwHighDateTime,
        info.ftLastWriteTime.dwLowDateTime,
    )


class WindowsScopedDirectory:
    """Single folder pin. ONLY caller-validated top-level basenames are accepted."""

    def __init__(self, path, expected_inode):
        self._handle = None
        self._kernel, self._ntdll = _windows_apis()
        _require_fixed_local_volume(path, self._kernel)
        handle = self._kernel.CreateFileW(
            str(path),
            _FILE_LIST_DIRECTORY | _FILE_READ_ATTRIBUTES | _SYNCHRONIZE,
            _SHARE_ALL, None, _OPEN_EXISTING,
            _FLAG_BACKUP_SEMANTICS | _FLAG_WIN32_OPEN_REPARSE, None,
        )
        if handle in (None, _INVALID_HANDLE):
            raise AgentRejected("Cannot open approved Windows directory")
        try:
            info, _, identity = _file_info(self._kernel, handle)
            if (not info.dwFileAttributes & _DIRECTORY
                    or info.dwFileAttributes & _UNSAFE_REMOTE_ATTRIBUTES
                    or info.nNumberOfLinks != 1
                    or (expected_inode and identity != expected_inode)):
                raise AgentRejected("Approved Windows directory identity mismatch")
        except BaseException:
            self._kernel.CloseHandle(handle)
            raise
        self._handle = handle

    def _active(self):
        if self._handle is None:
            raise AgentRejected("Approved Windows directory handle is closed")
        return self._handle

    def _open_child(self, basename):
        root = self._active()
        if type(basename) is not str or not _SAFE_NAME.fullmatch(basename):
            raise AgentRejected("Invalid native relative filename")
        stem = basename.rsplit(".", 1)[0]
        if stem.rstrip(" .") != stem:
            raise AgentRejected("Ambiguous native filename denied")
        device = stem.split(".", 1)[0].rstrip(" ").upper()
        if (device in {"CON", "PRN", "AUX", "NUL"} or
                re.fullmatch(r"(?:COM|LPT)[1-9]", device)):
            raise AgentRejected("Reserved Windows device name")
        name = ctypes.create_unicode_buffer(basename)
        unicode_name = _UnicodeString(
            len(basename.encode("utf-16-le")),
            len(basename.encode("utf-16-le")) + 2,
            ctypes.cast(name, ctypes.c_void_p),
        )
        attrs = _ObjectAttributes(
            ctypes.sizeof(_ObjectAttributes), root,
            ctypes.pointer(unicode_name), _OBJ_CASE_INSENSITIVE, None, None,
        )
        iosb = _IoStatusBlock()
        opened = wintypes.HANDLE()
        status = self._ntdll.NtCreateFile(
            ctypes.byref(opened),
            _FILE_READ_DATA | _FILE_READ_ATTRIBUTES | _SYNCHRONIZE,
            ctypes.byref(attrs), ctypes.byref(iosb),
            None, 0, _SHARE_ALL, _FILE_OPEN,
            _FLAG_OPEN_REPARSE | _FLAG_NON_DIRECTORY | _FLAG_SYNC_NONALERT,
            None, 0,
        )
        if status < 0 or opened.value in (None, _INVALID_HANDLE):
            raise AgentRejected("Windows file unavailable or unsafe")
        try:
            info, size, _ = _file_info(self._kernel, opened)
            if (info.dwFileAttributes & (_DIRECTORY | _UNSAFE_REMOTE_ATTRIBUTES)
                    or info.nNumberOfLinks != 1):
                raise AgentRejected("Windows file link or reparse point denied")
        except BaseException:
            self._kernel.CloseHandle(opened)
            raise
        return opened, size

    def size_of(self, basename):
        handle, size = self._open_child(basename)
        try:
            return size
        finally:
            self._kernel.CloseHandle(handle)

    def read_bounded(self, basename, max_bytes):
        if type(max_bytes) is not int or not 1 <= max_bytes <= 65536:
            raise AgentRejected("Invalid Windows file limit")
        handle, size = self._open_child(basename)
        try:
            before, before_size, before_id = _file_info(self._kernel, handle)
            if (before_size != size or before_size > max_bytes or
                    before.dwFileAttributes & (_DIRECTORY | _UNSAFE_REMOTE_ATTRIBUTES)
                    or before.nNumberOfLinks != 1):
                raise AgentRejected("Windows file changed before read")
            signature = _content_signature(before, before_size, before_id)
            buffer = ctypes.create_string_buffer(max_bytes + 1)
            received = wintypes.DWORD()
            if not self._kernel.ReadFile(
                handle, buffer, max_bytes + 1, ctypes.byref(received), None,
            ):
                raise AgentRejected("Windows file read failed")
            after, after_size, after_id = _file_info(self._kernel, handle)
            if (received.value != before_size or received.value > max_bytes or
                    _content_signature(after, after_size, after_id) != signature):
                raise AgentRejected("Windows file changed during read")
            return buffer.raw[:received.value]
        finally:
            self._kernel.CloseHandle(handle)

    def list_names(self):
        """Enumerate via the PINNED handle; never scan its mutable path."""
        root = self._active()
        names = []
        seen = set()
        restart = 1
        for _ in range(_MAX_ENUMERATED + 1):
            buf = ctypes.create_string_buffer(4096)
            iosb = _IoStatusBlock()
            status = self._ntdll.NtQueryDirectoryFile(
                root, None, None, None, ctypes.byref(iosb), buf,
                len(buf), _FILE_NAMES_INFORMATION, 1, None, restart,
            )
            restart = 0
            if status & 0xffffffff == _STATUS_NO_MORE_FILES:
                return names
            if status < 0 or iosb.Information < 12:
                raise AgentRejected("Windows directory enumeration failed")
            raw = buf.raw
            length = int.from_bytes(raw[8:12], "little")
            if length == 0 or length % 2 or length > min(2048, iosb.Information - 12):
                raise AgentRejected("Windows directory entry malformed")
            try:
                name = raw[12:12 + length].decode("utf-16-le", "strict")
            except UnicodeDecodeError:
                raise AgentRejected("Windows directory entry encoding invalid") from None
            if name not in (".", "..") and name not in seen:
                names.append(name)
                seen.add(name)
        raise AgentRejected("Approved folder exceeds safe Windows scan limit")

    def close(self):
        handle, self._handle = self._handle, None
        if handle is not None:
            self._kernel.CloseHandle(handle)
