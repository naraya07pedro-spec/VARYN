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
from varyn.decisions import DecisionJournal
from varyn.context import build_context
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
        self.journal = None
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
            # Reject malformed decision tables and owner-label mismatches before
            # creating a journal. This is consistency validation, NOT login.
            exists = self.store.db.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' "
                "AND name='decision_revisions'"
            ).fetchone()
            if exists:
                required = {
                    "id", "owner_id", "project", "decision_key", "revision",
                    "content", "source_ref", "created_at",
                }
                try:
                    fields = {
                        row[1] for row in self.store.db.execute(
                            "PRAGMA table_info(decision_revisions)"
                        )
                    }
                    if not required <= fields:
                        raise SealedDataError("Unsupported encrypted decision schema")
                    if self.store.db.execute(
                        "SELECT 1 FROM decision_revisions "
                        "WHERE owner_id <> ? LIMIT 1", (_OWNER,)
                    ).fetchone():
                        raise SealedDataError("Unsupported encrypted decision ownership")
                except sqlite3.Error as error:
                    raise SealedDataError("Invalid encrypted decision journal") from error
            # The journal and FTS index share the SAME in-memory SQLite image.
            ensure_memory_index(self.store.db)
            self.journal = DecisionJournal(
                None, _OWNER, connection=self.store.db
            )
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

    def put_decision(self, project, key, content, source_ref, expected_revision=0):
        """Append a revision to the SAME in-memory encrypted snapshot."""
        self._active()
        return self.journal.put(
            project, key, content, source_ref, expected_revision
        )

    def decision_history(self, project, key):
        self._active()
        return self.journal.history(project, key)

    def current_decision(self, project, key):
        self._active()
        return self.journal.current(project, key)

    def context(self, project, query, max_chars=4000, max_candidates=500):
        """Build the existing bounded context without disk SQLite sidecars."""
        self._active()
        return build_context(
            None, _OWNER, project, query, max_chars=max_chars,
            max_candidates=max_candidates, connection=self.store.db,
        )

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
            if self.journal is not None:
                self.journal.close()
            self.store.close()

    def __enter__(self):
        self._active()
        return self

    def __exit__(self, exception_type, exception, traceback):
        self.close()
