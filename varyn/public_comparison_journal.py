"""17S-8: opt-in, metadata-only durable journal for reviewed public comparisons.

Never stores repo names, responses, prompt, credentials, approval tokens or
authorization. An interrupted action is UNCERTAIN and is NEVER replayed.
"""
import re
import sqlite3
from pathlib import Path
from secrets import token_urlsafe

from varyn.task_journal import JournalConflict

_ID = re.compile(r"^[A-Za-z0-9_-]{16,96}$")
_DIGEST = re.compile(r"^[0-9a-f]{64}$")


class PublicComparisonJournal:
    """SQLite state machine. Caller must enforce permission for EACH GET."""

    def __init__(self, path):
        p = Path(path)
        if p == Path(":memory:") or p.is_symlink() or not p.parent.is_dir():
            raise ValueError("Explicit on-disk metadata journal path required")
        self.db = sqlite3.connect(str(p), isolation_level=None)
        self._closed = False
        try:
            self.db.execute("PRAGMA synchronous=FULL")
            self.db.execute("PRAGMA journal_mode=DELETE")
            self.db.execute(
                "CREATE TABLE IF NOT EXISTS public_comparison_checkpoints ("
                "task_id TEXT PRIMARY KEY, digest TEXT NOT NULL,"
                "cursor INTEGER NOT NULL CHECK(cursor BETWEEN 0 AND 2),"
                "status TEXT NOT NULL)"
            )
        except Exception:
            # On Windows an open SQLite connection locks a corrupt journal
            # even after __init__ raises; always release it on failure.
            self.db.close()
            self._closed = True
            raise

    def _check(self, task_id, digest):
        if self._closed:
            raise JournalConflict("Comparison journal is closed")
        if (type(task_id) is not str or not _ID.fullmatch(task_id) or
                type(digest) is not str or not _DIGEST.fullmatch(digest)):
            raise ValueError("Invalid comparison journal reference")

    def create(self, digest):
        if self._closed:
            raise JournalConflict("Comparison journal is closed")
        if type(digest) is not str or not _DIGEST.fullmatch(digest):
            raise ValueError("Invalid plan digest")
        task_id = token_urlsafe(24)
        self.db.execute(
            "INSERT INTO public_comparison_checkpoints VALUES (?,?,0,'ready')",
            (task_id, digest),
        )
        return task_id

    def _change(self, task_id, digest, cursor, previous, state, *, advance=False):
        self._check(task_id, digest)
        if type(cursor) is not int or not 0 <= cursor <= 2:
            raise ValueError("Invalid cursor")
        n = self.db.execute(
            "UPDATE public_comparison_checkpoints "
            "SET cursor=cursor+?, status=? "
            "WHERE task_id=? AND digest=? AND cursor=? AND status=?",
            (int(advance), state, task_id, digest, cursor, previous),
        ).rowcount
        if n != 1:
            raise JournalConflict("Comparison journal mismatch; no replay allowed")

    def begin_step(self, task_id, digest, index):
        """Durably mark uncertain BEFORE submitting the reviewed GET."""
        if type(index) is not int or index not in (0, 1):
            raise ValueError("Only two fixed steps supported")
        self._change(task_id, digest, index, "ready", "uncertain")

    def complete_step(self, task_id, digest, index):
        """Only after host has checked exact result against approved step."""
        if type(index) is not int or index not in (0, 1):
            raise ValueError("Only two fixed steps supported")
        self._change(task_id, digest, index, "uncertain", "ready", advance=True)

    def finish(self, task_id, digest):
        self._change(task_id, digest, 2, "ready", "completed")

    def abort(self, task_id, digest):
        """Conservatively preserve ambiguity of a possibly-sent GET."""
        self._check(task_id, digest)
        n = self.db.execute(
            "UPDATE public_comparison_checkpoints SET status="
            "CASE WHEN status='uncertain' THEN 'needs_reconciliation' "
            "ELSE 'cancelled' END "
            "WHERE task_id=? AND digest=? AND status IN ('ready','uncertain')",
            (task_id, digest),
        ).rowcount
        return n == 1

    def recover(self):
        """Reclassify abandoned tasks; NEVER resume them or create approval."""
        if self._closed:
            raise JournalConflict("Comparison journal is closed")
        needs_review = self.db.execute(
            "UPDATE public_comparison_checkpoints SET status='needs_review' "
            "WHERE status='ready'"
        ).rowcount
        needs_reconciliation = self.db.execute(
            "UPDATE public_comparison_checkpoints "
            "SET status='needs_reconciliation' WHERE status='uncertain'"
        ).rowcount
        return {"needs_review": needs_review,
                "needs_reconciliation": needs_reconciliation,
                "auto_replayed": 0}

    def inspect(self, task_id):
        if self._closed:
            raise JournalConflict("Comparison journal is closed")
        if type(task_id) is not str or not _ID.fullmatch(task_id):
            raise ValueError("Invalid task ID")
        row = self.db.execute(
            "SELECT digest,cursor,status FROM public_comparison_checkpoints "
            "WHERE task_id=?", (task_id,),
        ).fetchone()
        return None if row is None else {
            "digest": row[0], "cursor": row[1], "status": row[2],
            "executable": False, "authorization_persisted": False,
        }

    def close(self):
        if not self._closed:
            self._closed = True
            self.db.close()
