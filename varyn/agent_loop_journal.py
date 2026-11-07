"""Metadata-only fail-closed journal for owner-gated agent runs.

No prompts, keys, tool arguments, private paths, or answers are persisted.
Interruption is never automatically retried or replayed.
"""
from hashlib import sha256
from pathlib import Path
from secrets import token_hex
import re
import sqlite3


class LoopJournalConflict(RuntimeError):
    pass


_STATES = {
    "prepared": {"model_in_flight", "denied"},
    "model_in_flight": {"model_decided", "completed"},
    "model_decided": {"tool_pending"},
    "tool_pending": {"tool_in_flight", "denied"},
    "tool_in_flight": {"observation_ready"},
    "observation_ready": {"synthesis_in_flight", "denied", "observation_only"},
    "synthesis_in_flight": {"completed", "verification_failed"},
}


class AgentLoopJournal:
    def __init__(self, path):
        p = Path(path)
        if (p.suffix not in (".sqlite", ".sqlite3", ".db")
                or not p.parent.is_dir() or p.is_symlink()):
            raise ValueError("Explicit local SQLite file required")
        self.db = sqlite3.connect(str(p), timeout=10, isolation_level=None)
        self.db.execute("PRAGMA busy_timeout=10000")
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS agent_loop_runs("
            "id TEXT PRIMARY KEY, goal_hash TEXT NOT NULL, "
            "state TEXT NOT NULL, changed_at TEXT NOT NULL "
            "DEFAULT CURRENT_TIMESTAMP)"
        )

    def create(self, goal):
        if type(goal) is not str or not goal:
            raise ValueError("Invalid goal")
        ident = token_hex(16)
        self.db.execute(
            "INSERT INTO agent_loop_runs(id,goal_hash,state) "
            "VALUES(?,?,'prepared')",
            (ident, sha256(goal.encode("utf-8")).hexdigest()))
        return ident

    def move(self, ident, expected, target):
        if (type(ident) is not str
                or re.fullmatch(r"[0-9a-f]{32}", ident) is None
                or target not in _STATES.get(expected, set())):
            raise LoopJournalConflict("Unsupported state transition")
        updated = self.db.execute(
            "UPDATE agent_loop_runs "
            "SET state=?,changed_at=CURRENT_TIMESTAMP "
            "WHERE id=? AND state=?", (target, ident, expected))
        if updated.rowcount != 1:
            raise LoopJournalConflict("State conflict; automatic replay forbidden")

    def status(self, ident):
        if type(ident) is not str or re.fullmatch(r"[0-9a-f]{32}", ident) is None:
            raise LoopJournalConflict("Invalid run ID")
        row = self.db.execute(
            "SELECT goal_hash,state FROM agent_loop_runs WHERE id=?",
            (ident,)).fetchone()
        return None if row is None else {
            "goal_hash": row[0], "state": row[1], "auto_replay": False}

    def recover(self):
        review = self.db.execute(
            "UPDATE agent_loop_runs SET state='needs_review' "
            "WHERE state IN ('prepared','model_decided','tool_pending',"
            "'observation_ready')").rowcount
        uncertain = self.db.execute(
            "UPDATE agent_loop_runs SET state='needs_reconciliation' "
            "WHERE state IN ('model_in_flight','tool_in_flight',"
            "'synthesis_in_flight')").rowcount
        return {"needs_review": review, "needs_reconciliation": uncertain,
                "auto_replayed": 0}

    def close(self):
        self.db.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
