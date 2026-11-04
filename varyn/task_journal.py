"""17P metadata-only SQLite task journal; never replays interrupted work."""
import hashlib
import json
import re
import sqlite3
from pathlib import Path
from secrets import token_urlsafe

_ID = re.compile(r"^[A-Za-z0-9_-]{16,96}$")


class JournalConflict(RuntimeError):
    pass


def digest_plan(plan):
    from varyn.task_planner import TaskStep
    from varyn.agent_runtime import BoundedAgent
    if type(plan) is not tuple or not 1 <= len(plan) <= 6:
        raise ValueError("Invalid compiled plan")
    rows = []
    for step in plan:
        if type(step) is not TaskStep:
            raise ValueError("Invalid step")
        BoundedAgent._validate(step.tool, step.arguments)
        rows.append({"tool": step.tool, "arguments": step.arguments})
    data = json.dumps(rows, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode()
    return hashlib.sha256(data).hexdigest()


class TaskJournal:
    """Persists only random ID, plan digest, cursor, state and count."""
    def __init__(self, path):
        p = Path(path)
        if p == Path(":memory:") or p.is_symlink() or not p.parent.is_dir():
            raise ValueError("Explicit on-disk journal path required")
        self.db = sqlite3.connect(str(p), isolation_level=None)
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.execute("PRAGMA journal_mode=DELETE")
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS task_checkpoints("
            "task_id TEXT PRIMARY KEY, digest TEXT NOT NULL,"
            "total INTEGER NOT NULL, cursor INTEGER NOT NULL,"
            "status TEXT NOT NULL)"
        )
        self._closed = False

    def create(self, plan):
        self._check_open()
        task_id = token_urlsafe(24)
        d = digest_plan(plan)
        self.db.execute(
            "INSERT INTO task_checkpoints VALUES(?,?,?,0,'planned')",
            (task_id, d, len(plan)),
        )
        return task_id, d

    def _check_open(self):
        if self._closed:
            raise JournalConflict("Journal closed")

    def _change(self, task_id, digest, index, previous, next_state, increment=0):
        self._check_open()
        if (type(task_id) is not str or not _ID.fullmatch(task_id) or
            type(digest) is not str or len(digest) != 64 or
            type(index) is not int or index < 0):
            raise ValueError("Invalid task journal reference")
        cursor = self.db.execute(
            "UPDATE task_checkpoints SET status=?, cursor=cursor+? "
            "WHERE task_id=? AND digest=? AND cursor=? AND status=?",
            (next_state, increment, task_id, digest, index, previous),
        )
        if cursor.rowcount != 1:
            raise JournalConflict("State mismatch; no replay permitted")

    def begin(self, task_id, digest, index):
        self._change(task_id, digest, index,
                     "planned" if index == 0 else "ready", "uncertain")

    def complete(self, task_id, digest, index):
        self._change(task_id, digest, index, "uncertain", "ready", 1)

    def stop(self, task_id, digest, index, *, denied=False):
        self._change(task_id, digest, index, "uncertain",
                     "denied" if denied else "failed_uncertain")

    def finish(self, task_id, digest, total):
        self._change(task_id, digest, total, "ready", "completed")

    def recover(self):
        self._check_open()
        review = self.db.execute(
            "UPDATE task_checkpoints SET status='needs_review' "
            "WHERE status IN ('planned','ready')"
        ).rowcount
        uncertain = self.db.execute(
            "UPDATE task_checkpoints SET status='needs_reconciliation' "
            "WHERE status='uncertain'"
        ).rowcount
        return {"needs_review": review, "needs_reconciliation": uncertain,
                "auto_replayed": 0}

    def inspect(self, task_id):
        self._check_open()
        if type(task_id) is not str or not _ID.fullmatch(task_id):
            raise ValueError("Invalid task ID")
        row = self.db.execute(
            "SELECT digest,total,cursor,status FROM task_checkpoints "
            "WHERE task_id=?", (task_id,),
        ).fetchone()
        return None if row is None else dict(
            zip(("digest","total","cursor","status"),row),
            executable=False,
        )

    def close(self):
        if not self._closed:
            self.db.close()
            self._closed = True
