"""Scoped read-only text-file prototype; 17B pins POSIX directory handles.

The user/host chooses an ABSOLUTE root directory outside any model output.
Only top-level ordinary .txt/.md files are accessible by basename. No shell,
recursive walk, writes, network, model execution, or automatic context upload.

POSIX opens are tied to the original directory FD, protecting content reads
from path replacement after scope selection. Windows still uses best-effort
metadata checks, NOT a secure handle-based containment boundary.
"""
import os
import re
import stat
from pathlib import Path

from varyn.agent_runtime import AgentRejected

_NAME = re.compile(r"\A[A-Za-z0-9][A-Za-z0-9_. -]{0,119}\.(?:txt|md)\Z", re.I)


_REPARSE = getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0x400)


def _unsafe_windows_metadata(meta):
    """Conservative reparse/hardlink check; not a native Windows sandbox."""
    return (os.name == 'nt' and
            (bool(getattr(meta, 'st_file_attributes', 0) & _REPARSE)
             or getattr(meta, 'st_nlink', 1) != 1))


class ScopedLocalReader:
    """The host explicitly supplies a directory, never the model or prompt."""

    def __init__(self, root, *, max_bytes=16384, max_list=40):
        if type(max_bytes) is not int or not 128 <= max_bytes <= 65536:
            raise ValueError("max_bytes must be 128..65536")
        if type(max_list) is not int or not 1 <= max_list <= 100:
            raise ValueError("max_list must be 1..100")
        base = Path(root)
        if not base.is_absolute() or base.is_symlink() or not base.is_dir():
            raise ValueError("Root must be an existing, absolute, non-symlink directory")
        if os.name == 'nt':
            for parent in (base, *base.parents):
                try:
                    meta = parent.lstat()
                    if (parent.is_symlink() or
                            bool(getattr(meta, 'st_file_attributes', 0) & _REPARSE)):
                        raise ValueError('Reparse-point path component denied')
                except OSError:
                    raise ValueError('Folder path cannot be validated') from None
        self._root = base
        self._root_stat = base.stat()
        if _unsafe_windows_metadata(self._root_stat):
            raise ValueError('Unsafe root metadata')
        self._max_bytes = max_bytes
        self._max_list = max_list
        self._closed = False
        self._root_fd = None
        if os.name != "nt":
            flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
            flags |= getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
            fd = None
            try:
                fd = os.open(base, flags)
                opened = os.fstat(fd)
                if (not stat.S_ISDIR(opened.st_mode)
                        or opened.st_dev != self._root_stat.st_dev
                        or opened.st_ino != self._root_stat.st_ino):
                    raise ValueError("Approved directory changed during scope creation")
            except BaseException:
                if fd is not None:
                    os.close(fd)
                raise
            self._root_fd = fd

    def close(self):
        """Release original directory descriptor and refuse future operations."""
        if not self._closed:
            self._closed = True
            fd, self._root_fd = self._root_fd, None
            if fd is not None:
                os.close(fd)

    def __del__(self):
        if getattr(self, "_closed", True) is False:
            try:
                self.close()
            except OSError:
                pass

    def _active(self):
        if self._closed:
            raise AgentRejected("Approved directory reader is closed")


    def _check_root(self):
        self._active()
        if os.name == "nt":
            # Catch detectable parent junction/reparse changes on EACH access.
            # Still subject to concurrent Windows path swaps between checks.
            try:
                for parent in (self._root, *self._root.parents):
                    ancestor = parent.lstat()
                    if (parent.is_symlink() or
                            bool(getattr(ancestor, "st_file_attributes", 0) & _REPARSE)):
                        raise AgentRejected("Approved directory ancestry changed")
            except OSError:
                raise AgentRejected("Approved directory ancestry unavailable") from None
        try:
            meta = self._root.lstat()
            if (not stat.S_ISDIR(meta.st_mode)
                    or meta.st_dev != self._root_stat.st_dev
                    or meta.st_ino != self._root_stat.st_ino
                    or _unsafe_windows_metadata(meta)):
                raise AgentRejected("Approved directory changed")
        except OSError:
            raise AgentRejected("Approved directory unavailable") from None

    @staticmethod
    def _name(name):
        if not isinstance(name, str) or not _NAME.fullmatch(name):
            raise AgentRejected("Only top-level .txt/.md basenames are permitted")
        stem = name.rsplit(".", 1)[0].rstrip(" .").upper()
        if (stem in {"CON", "PRN", "AUX", "NUL"} or
                re.fullmatch(r"(?:COM|LPT)[1-9]", stem)):
            raise AgentRejected("Reserved device name denied")
        if name in (".", "..") or name.startswith("."):
            raise AgentRejected("Hidden and special names are refused")
        return name

    def list_files(self):
        """List basename metadata only, capped; contents are not read."""
        self._check_root()
        found = []
        try:
            # POSIX fd scan remains anchored if a directory path is swapped.
            with os.scandir(self._root_fd if self._root_fd is not None else self._root) as entries:
                for entry in entries:
                    try:
                        self._name(entry.name)
                        if entry.is_symlink() or not entry.is_file(follow_symlinks=False):
                            continue
                        # Windows DirEntry.stat may omit reliable link metadata.
                        # Use the same lstat path as read_text before listing.
                        meta = (Path(entry.path).lstat() if os.name == 'nt'
                                else entry.stat(follow_symlinks=False))
                        if (not _unsafe_windows_metadata(meta)
                                and 0 <= meta.st_size <= self._max_bytes):
                            found.append({"name": entry.name, "bytes": meta.st_size})
                    except (AgentRejected, OSError):
                        continue
        except OSError:
            raise AgentRejected("Cannot list approved directory") from None
        found.sort(key=lambda item: item["name"].casefold())
        return {"format": "varyn.scoped_file_listing.v1",
                "files": found[:self._max_list],
                "truncated": len(found) > self._max_list,
                "recursive": False, "read_only": True}

    def read_text(self, filename):
        """Read bounded UTF-8 text; never follow a basename path through subdirs."""
        name = self._name(filename)
        self._check_root()
        path = self._root / name
        try:
            before = path.lstat()
            if (not stat.S_ISREG(before.st_mode)
                    or _unsafe_windows_metadata(before)
                    or before.st_size > self._max_bytes):
                raise AgentRejected("Not a permitted regular text file")
            flags = os.O_RDONLY | getattr(os, "O_BINARY", 0)
            flags |= getattr(os, "O_NOFOLLOW", 0)
            # POSIX openat pins reads to the original approved directory.
            # Windows does not support dir_fd here and remains synthetic-only.
            fd = (os.open(name, flags, dir_fd=self._root_fd)
                  if self._root_fd is not None else os.open(path, flags))
            if self._root_fd is None:
                # Windows recheck narrows exposure but does not close OS races.
                try:
                    self._check_root()
                except BaseException:
                    os.close(fd)
                    raise
            try:
                opened = os.fstat(fd)
                if (not stat.S_ISREG(opened.st_mode)
                        or opened.st_dev != before.st_dev
                        or opened.st_ino != before.st_ino
                        or _unsafe_windows_metadata(opened)):
                    raise AgentRejected("File identity changed before read")
                with os.fdopen(fd, "rb", closefd=False) as handle:
                    data = handle.read(self._max_bytes + 1)
            finally:
                os.close(fd)
            if len(data) > self._max_bytes:
                raise AgentRejected("File exceeded read limit")
            try:
                content = data.decode("utf-8", errors="strict")
            except UnicodeDecodeError:
                raise AgentRejected("Only UTF-8 text is supported") from None
            if "\x00" in content:
                raise AgentRejected("Binary-like content not allowed")
            return {"format": "varyn.scoped_file_read.v1",
                    "name": name, "bytes": len(data), "text": content,
                    "read_only": True, "external_upload": False}
        except (OSError, ValueError):
            raise AgentRejected("File unavailable or unsafe") from None
