"""Opt-in, Windows-only prototype: whole SQLite image sealed at rest.

Keeps working SQLite and FTS5 index in :memory:, not a plaintext disk file.
Each save creates a NEW immutable DPAPI snapshot. This is not a replacement
for legacy MemoryStore/backup/restore or real authenticated multi-user storage.
"""
import os
import sqlite3
from pathlib import Path
from uuid import uuid4

from varyn.dpapi_vault import (
    UnsupportedPlatformError, SealedDataError, read_sealed, write_sealed,
)
from varyn.index import ensure_memory_index
from varyn.decisions import DecisionJournal
from varyn.context import build_context
from varyn.memory import MemoryStore
from varyn.checkpoint_lifecycle import require_checkpoint_capacity

_OWNER = "local-windows-session"


def _require_windows():
    if os.name != "nt":
        raise UnsupportedPlatformError("This sealed memory prototype requires Windows")


class SealedMemorySession:
    """Single-user, explicit-save memory prototype, without plaintext disk DB."""

    def __init__(self, source=None, *, recovery_source=None, recovery_passphrase=None, checkpoint_dir=None, max_checkpoints=100):
        _require_windows()
        if source is not None and recovery_source is not None:
            raise ValueError("Choose DPAPI source or recovery source, not both")
        if (recovery_source is None) != (recovery_passphrase is None):
            raise ValueError("Recovery source and passphrase must be supplied together")
        if not hasattr(sqlite3.Connection, "serialize") or not hasattr(sqlite3.Connection, "deserialize"):
            raise RuntimeError("This Python SQLite build lacks serialize/deserialize")
        if type(max_checkpoints) is not int or not 2 <= max_checkpoints <= 10000:
            raise ValueError("max_checkpoints must be an integer from 2 to 10000")
        directory = None
        if checkpoint_dir is not None:
            directory = Path(checkpoint_dir)
            if directory.is_symlink() or not directory.is_dir():
                raise ValueError("Checkpoint directory must exist and not be a symlink")
        self.store = MemoryStore(":memory:", _OWNER)
        self._closed = False
        self._change_count = 0
        self._saved_change_count = 0
        self._checkpoint_dir = directory
        self._max_checkpoints = max_checkpoints
        self._last_checkpoint = None
        self.journal = None
        try:
            if source is not None or recovery_source is not None:
                if source is not None:
                    image = read_sealed(source)
                else:
                    # Optional cryptography dependency is needed only for portable recovery.
                    from varyn.recovery import read_recovery
                    image = read_recovery(recovery_source, recovery_passphrase)
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
        if self._checkpoint_dir is not None:
            require_checkpoint_capacity(self._checkpoint_dir, max_checkpoints=self._max_checkpoints)
        new_id = self.store.add(project, content)
        self._change_count += 1
        self._checkpoint_after_write()
        return new_id

    def search(self, query, project=None, limit=20):
        self._active()
        return self.store.search(query, project, limit)

    def put_decision(self, project, key, content, source_ref, expected_revision=0):
        """Append a revision to the SAME in-memory encrypted snapshot."""
        self._active()
        if self._checkpoint_dir is not None:
            require_checkpoint_capacity(self._checkpoint_dir, max_checkpoints=self._max_checkpoints)
        revision = self.journal.put(
            project, key, content, source_ref, expected_revision
        )
        self._change_count += 1
        self._checkpoint_after_write()
        return revision

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
        result = write_sealed(destination, image)
        self._saved_change_count = self._change_count
        return result

    def export_recovery(self, destination, passphrase):
        """Portable password-encrypted NEW snapshot. Never emit plaintext SQLite."""
        self._active()
        self.store.db.commit()
        from varyn.recovery import write_recovery
        image = self.store.db.serialize()
        result = write_recovery(destination, image, passphrase)
        self._saved_change_count = self._change_count
        return result

    def _checkpoint_after_write(self):
        """Best-effort encrypted checkpoint immediately after each public write.

        A successful return means a new encrypted snapshot was published; an
        exception leaves the in-memory write and earlier snapshots untouched.
        Files are immutable and never silently rotated or deleted.
        """
        if self._checkpoint_dir is None:
            return
        destination = self._checkpoint_dir / ("checkpoint-" + uuid4().hex + ".varyn")
        self.save_new(destination)
        self._last_checkpoint = destination

    @property
    def last_checkpoint(self):
        self._active()
        return self._last_checkpoint

    @property
    def has_unsaved_changes(self):
        """Only changes made through this session's public add/put methods."""
        self._active()
        return self._change_count != self._saved_change_count

    def close_checked(self):
        """Refuse to discard tracked changes; session remains usable on error.

        This strict opt-in gate does not protect against sudden process death,
        memory exhaustion or direct writes through .store.db.
        """
        self._active()
        if self.has_unsaved_changes:
            raise RuntimeError("Unsaved changes: publish a new snapshot before closing")
        self.close()

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
