"""17M explicit project-scoped desktop memory, opt-in SQLite only.

The original MemoryStore database is UNENCRYPTED. Deliberately synthetic-only
until secure owner-key management and encrypted storage are independently
verified. Never implicitly load notes into chat, collaboration, tools or APIs.
Owner label is not authorization. Caller must provide an explicit DB path.
"""
import re
from pathlib import Path

from varyn.memory import MemoryStore

_PROJECT = re.compile(r"\A[A-Za-z][A-Za-z0-9_-]{0,39}\Z")
_MAX_NOTE_CHARS = 1000
_MAX_SEARCH_CHARS = 100


class DesktopMemory:
    """Local explicit synthetic notes, per-project reads/deletes only."""

    def __init__(self, path, *, owner_label="varyn-local-demo"):
        if not isinstance(path, (str, Path)) or not str(path).strip():
            raise ValueError("Explicit local memory path is required")
        p = Path(path)
        if not p.parent.is_dir() or p.is_symlink() or p.is_dir():
            raise ValueError("Memory path must be a non-symlink regular file destination")
        if p.exists() and not p.is_file():
            raise ValueError("Memory path must be a regular file")
        # Caller must specify a destination, never derive one from Documents,
        # Downloads, browser cookies, or other private directories.
        self._store = MemoryStore(p, owner_label)
        self._closed = False

    @staticmethod
    def _project(project):
        if type(project) is not str or not _PROJECT.fullmatch(project):
            raise ValueError("Project must be 1..40 safe letters, digits, _ or -")
        return project

    @staticmethod
    def _note(note):
        if type(note) is not str or not 1 <= len(note.strip()) <= _MAX_NOTE_CHARS:
            raise ValueError("Note must be 1..1000 characters")
        if not note.strip().startswith("SYNTHETIC:"):
            raise PermissionError("Unencrypted prototype permits only explicitly marked synthetic notes")
        return note.strip()

    def _ensure(self):
        if self._closed:
            raise RuntimeError("Memory database already closed")

    def save(self, project, note, *, confirmed=False):
        self._ensure()
        project = self._project(project)
        note = self._note(note)
        if confirmed is not True:
            raise PermissionError("Explicit local save confirmation required")
        return self._store.add(project, note)

    def search(self, project, query):
        self._ensure()
        project = self._project(project)
        if type(query) is not str or not 1 <= len(query.strip()) <= _MAX_SEARCH_CHARS:
            raise ValueError("Search must be 1..100 characters")
        # Search is restricted to EXACT project and owner labels, never cross-project.
        return self._store.search(query.strip(), project=project, limit=10)

    def delete(self, project, memory_id, *, confirmed=False):
        self._ensure()
        project = self._project(project)
        if confirmed is not True:
            raise PermissionError("Explicit local deletion confirmation required")
        return self._store.delete(memory_id, project=project)

    def close(self):
        if not self._closed:
            self._closed = True
            self._store.close()
