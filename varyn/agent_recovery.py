"""Durable metadata-only agent recovery journal (Checkpoint 14D).

SQLite records proposal IDs, tool names, digests and states ONLY. It NEVER
persists user arguments, approval tokens, responses, notes or credentials.
Crash recovery marks unresolved work for manual reconciliation; no replay.
"""
import re
import sqlite3
from pathlib import Path
from threading import RLock

_ID = re.compile(r"\A[A-Za-z0-9_-]{16,96}\Z")
_DIGEST = re.compile(r"\A[0-9a-f]{64}\Z")
_TOOLS = frozenset({"inspect_status", "stage_note"})
_TERMINAL = frozenset({"completed", "rejected", "failed_uncertain"})
_UNRESOLVED = frozenset({"needs_review", "needs_reconciliation"})
_STATES = _TERMINAL | _UNRESOLVED | {"pending_review", "dispatch_uncertain"}
_SCHEMA = """
CREATE TABLE IF NOT EXISTS agent_events (
    proposal_id TEXT PRIMARY KEY,
    tool TEXT NOT NULL,
    digest TEXT NOT NULL,
    state TEXT NOT NULL,
    changed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
)
"""


class RecoveryConflict(RuntimeError):
    """State change refused to prevent replay or ambiguous dispatch."""


class AgentRecoveryJournal:
    """Explicitly opened metadata journal, no background process or polling."""

    def __init__(self, database_path):
        path = Path(database_path)
        if path == Path(":memory:"):
            raise ValueError("Recovery journal requires an on-disk database")
        if not path.parent.is_dir() or path.is_symlink():
            raise ValueError("Journal path must be inside an existing directory")
        self._lock = RLock()
        self._connection = sqlite3.connect(str(path), timeout=5,
                                           check_same_thread=False,
                                           isolation_level=None)
        self._closed = False
        try:
            self._connection.execute("PRAGMA journal_mode=DELETE")
            self._connection.execute("PRAGMA synchronous=FULL")
            self._connection.execute("PRAGMA busy_timeout=5000")
            self._connection.execute(_SCHEMA)
        except Exception:
            self._connection.close()
            raise

    def _require_open(self):
        if self._closed:
            raise RecoveryConflict("Journal is closed")

    @staticmethod
    def _check(proposal_id, tool=None, digest=None):
        if not isinstance(proposal_id, str) or not _ID.fullmatch(proposal_id):
            raise ValueError("Invalid proposal identifier")
        if tool is not None and tool not in _TOOLS:
            raise ValueError("Unknown tool")
        if digest is not None and (not isinstance(digest, str)
                                   or not _DIGEST.fullmatch(digest)):
            raise ValueError("Invalid digest")

    def record_proposal(self, proposal_id, tool, digest):
        self._check(proposal_id, tool, digest)
        with self._lock:
            self._require_open()
            try:
                self._connection.execute(
                    "INSERT INTO agent_events(proposal_id,tool,digest,state) "
                    "VALUES(?,?,?,'pending_review')",
                    (proposal_id, tool, digest),
                )
            except sqlite3.IntegrityError:
                raise RecoveryConflict("Duplicate proposal identifier") from None

    def transition(self, proposal_id, digest, *, from_state, to_state):
        self._check(proposal_id, digest=digest)
        allowed = {
            ("pending_review", "rejected"),
            ("pending_review", "dispatch_uncertain"),
            ("dispatch_uncertain", "completed"),
            ("dispatch_uncertain", "failed_uncertain"),
        }
        if (from_state, to_state) not in allowed:
            raise RecoveryConflict("Unsupported journal transition")
        with self._lock:
            self._require_open()
            cursor = self._connection.execute(
                "UPDATE agent_events SET state=?, changed_at=CURRENT_TIMESTAMP "
                "WHERE proposal_id=? AND digest=? AND state=?",
                (to_state, proposal_id, digest, from_state),
            )
            if cursor.rowcount != 1:
                raise RecoveryConflict("Proposal state mismatch; no dispatch allowed")

    def recover(self):
        """Persist fail-closed restart labels; NO reconstructed executable work."""
        with self._lock:
            self._require_open()
            self._connection.execute("BEGIN IMMEDIATE")
            try:
                pending = self._connection.execute(
                    "UPDATE agent_events SET state='needs_review', "
                    "changed_at=CURRENT_TIMESTAMP "
                    "WHERE state='pending_review'"
                ).rowcount
                uncertain = self._connection.execute(
                    "UPDATE agent_events SET state='needs_reconciliation', "
                    "changed_at=CURRENT_TIMESTAMP "
                    "WHERE state='dispatch_uncertain'"
                ).rowcount
                self._connection.execute("COMMIT")
            except BaseException:
                self._connection.execute("ROLLBACK")
                raise
            return {"needs_review": pending, "needs_reconciliation": uncertain,
                    "auto_replayed": 0}

    def status(self, proposal_id):
        self._check(proposal_id)
        with self._lock:
            self._require_open()
            row = self._connection.execute(
                "SELECT tool,digest,state FROM agent_events WHERE proposal_id=?",
                (proposal_id,),
            ).fetchone()
        return None if row is None else {
            "tool": row[0], "digest": row[1], "state": row[2]
        }

    def inventory(self):
        with self._lock:
            self._require_open()
            rows = self._connection.execute(
                "SELECT state,COUNT(*) FROM agent_events GROUP BY state"
            ).fetchall()
        return {"format": "varyn.agent_recovery.v1",
                "states": {state: count for state, count in rows},
                "requires_reconciliation": sum(
                    count for state, count in rows if state in _UNRESOLVED),
                "no_replay": True, "contains_arguments": False,
                "approval_tokens_persisted": False}

    def close(self):
        with self._lock:
            if not self._closed:
                self._connection.close()
                self._closed = True

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.close()
