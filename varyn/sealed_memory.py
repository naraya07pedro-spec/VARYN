"""Opt-in, Windows-only prototype: whole SQLite image sealed at rest.

Keeps working SQLite and FTS5 index in :memory:, not a plaintext disk file.
Each save creates a NEW immutable DPAPI snapshot. This is not a replacement
for legacy MemoryStore/backup/restore or real authenticated multi-user storage.
"""
import os
import sqlite3

from varyn.dpapi_vault import (
    UnsupportedPlatformError, SealedDataError, read_sealed, write_sealed,
)
from varyn.index import ensure_memory_index
from varyn.memory import MemoryStore

_OWNER = "local-windows-session"


def _require_windows():
    if os.name != "nt":
        raise UnsupportedPlatformError("This sealed memory prototype requires Windows")


class SealedMemorySession:
    """Single-user, explicit-save memory prototype, without plaintext disk DB."""

    def __init__(self, source=None):
        _require_windows()
        if not hasattr(sqlite3.Connection, "serialize") or not hasattr(sqlite3.Connection, "deserialize"):
            raise RuntimeError("This Python SQLite build lacks serialize/deserialize")
        self.store = MemoryStore(":memory:", _OWNER)
        self._closed = False
        try:
            if source is not None:
                image = read_sealed(source)
                if not image.startswith(b"SQLite format 3\x00"):
                    raise SealedDataError("Invalid encrypted SQLite image")
                try:
                    self.store.db.deserialize(image)
                    if self.store.db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                        raise SealedDataError("Encrypted image failed integrity check")
                    fields = {row[1] for row in self.store.db.execute("PRAGMA table_info(memories)")}
                    if not {"id", "owner_id", "project", "content", "created_at"} <= fields:
                        raise SealedDataError("Unsupported encrypted memory schema")
                    # Refuse snapshots containing other owner labels rather than
                    # silently granting access via a caller-chosen identity.
                    other = self.store.db.execute(
                        "SELECT 1 FROM memories WHERE owner_id <> ? LIMIT 1", (_OWNER,)
                    ).fetchone()
                    if other:
                        raise SealedDataError("Unsupported encrypted memory ownership")
                except sqlite3.Error as error:
                    raise SealedDataError("Invalid encrypted memory snapshot") from error
            # FTS5 virtual table and its backing data stay inside in-memory DB.
            ensure_memory_index(self.store.db)
        except BaseException:
            self.store.close()
            self._closed = True
            raise

    def _active(self):
        if self._closed:
            raise RuntimeError("The sealed memory session is closed")

    def add(self, project, content):
        self._active()
        return self.store.add(project, content)

    def search(self, query, project=None, limit=20):
        self._active()
        return self.store.search(query, project, limit)

    def save_new(self, destination):
        """Encrypt the complete SQLite snapshot, including FTS index, to NEW file."""
        self._active()
        self.store.db.commit()
        image = self.store.db.serialize()
        # write_sealed enforces the DPAPI 1-MiB plaintext size limit and never
        # publishes a plaintext intermediate database file.
        return write_sealed(destination, image)

    def close(self):
        if not self._closed:
            self._closed = True
            self.store.close()

    def __enter__(self):
        self._active()
        return self

    def __exit__(self, exception_type, exception, traceback):
        self.close()
