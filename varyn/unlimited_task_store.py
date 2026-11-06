"""Persistent non-capped task registry, not an autonomous scheduler.

No artificial total task count cap; bounded individual records and batch reads.
Uses owner-local SQLite. Scheduling only marks due, NEVER executes actions.
"""
from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path
import argparse
import json
import sqlite3
import uuid

_STATUSES = frozenset(("pending", "due", "paused", "completed", "cancelled"))
_MAX_TITLE = 256
_MAX_DETAIL = 4096


class TaskRejected(ValueError):
    pass


def utcnow():
    return datetime.now(timezone.utc)


def _timestamp(value):
    if type(value) is not str or len(value) > 40:
        raise TaskRejected("Invalid UTC due date")
    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        raise TaskRejected("Invalid UTC due date") from None
    if dt.tzinfo is None:
        raise TaskRejected("Timezone required")
    return dt.astimezone(timezone.utc).isoformat()


class TaskStore:
    def __init__(self, path):
        path = Path(path)
        if path.suffix not in (".sqlite", ".sqlite3", ".db") or not path.parent.is_dir():
            raise TaskRejected("Select an existing local directory and SQLite filename")
        self.connection = sqlite3.connect(str(path), timeout=10, isolation_level=None)
        self.connection.execute("PRAGMA busy_timeout=10000")
        self.connection.execute("PRAGMA journal_mode=WAL")
        self.connection.execute("PRAGMA foreign_keys=ON")
        self.connection.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                detail TEXT NOT NULL,
                status TEXT NOT NULL CHECK(status IN
                    ('pending','due','paused','completed','cancelled')),
                due_utc TEXT,
                created_utc TEXT NOT NULL,
                updated_utc TEXT NOT NULL
            )""")
        self.connection.execute(
            "CREATE INDEX IF NOT EXISTS tasks_schedule_idx "
            "ON tasks(status, due_utc, created_utc)"
        )

    def close(self):
        self.connection.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def create(self, title, *, detail="", due_utc=None):
        if (type(title) is not str or not title.strip() or
                len(title) > _MAX_TITLE or type(detail) is not str or
                len(detail) > _MAX_DETAIL):
            raise TaskRejected("Task fields invalid or too long")
        due = _timestamp(due_utc) if due_utc is not None else None
        now = utcnow().isoformat()
        task_id = uuid.uuid4().hex
        self.connection.execute(
            "INSERT INTO tasks(id,title,detail,status,due_utc,created_utc,updated_utc) "
            "VALUES (?,?,?,'pending',?,?,?)",
            (task_id, title, detail, due, now, now),
        )
        return task_id

    def list(self, *, status=None, limit=50, offset=0):
        if status is not None and status not in _STATUSES:
            raise TaskRejected("Invalid task status")
        if (type(limit) is not int or not 1 <= limit <= 200 or
                type(offset) is not int or offset < 0):
            raise TaskRejected("Invalid pagination")
        if status is None:
            cur = self.connection.execute(
                "SELECT id,title,status,due_utc,created_utc FROM tasks "
                "ORDER BY created_utc DESC,id DESC LIMIT ? OFFSET ?",
                (limit, offset))
        else:
            cur = self.connection.execute(
                "SELECT id,title,status,due_utc,created_utc FROM tasks "
                "WHERE status=? ORDER BY created_utc DESC,id DESC LIMIT ? OFFSET ?",
                (status, limit, offset))
        return [dict(zip(("id","title","status","due_utc","created_utc"), row))
                for row in cur.fetchall()]

    def count(self, *, status=None):
        if status is not None and status not in _STATUSES:
            raise TaskRejected("Invalid task status")
        if status is None:
            return self.connection.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
        return self.connection.execute(
            "SELECT COUNT(*) FROM tasks WHERE status=?", (status,)
        ).fetchone()[0]

    def mark_due(self, *, now=None, batch_size=100):
        """Advance scheduled state only. No network, subprocess or plugin call."""
        if type(batch_size) is not int or not 1 <= batch_size <= 200:
            raise TaskRejected("Batch size must be 1..200")
        now_text = _timestamp(now) if now is not None else utcnow().isoformat()
        with self.connection:
            ids = [row[0] for row in self.connection.execute(
                "SELECT id FROM tasks WHERE status='pending' AND due_utc IS NOT NULL "
                "AND due_utc<=? ORDER BY due_utc,id LIMIT ?", (now_text,batch_size))]
            self.connection.executemany(
                "UPDATE tasks SET status='due',updated_utc=? "
                "WHERE id=? AND status='pending'",
                [(now_text, task_id) for task_id in ids])
        return ids

    def transition(self, task_id, status):
        if (type(task_id) is not str or len(task_id)!=32 or
                any(c not in "0123456789abcdef" for c in task_id) or
                status not in ("paused","completed","cancelled")):
            raise TaskRejected("Invalid task state transition")
        allowed = {
            "paused": ("pending","due"),
            "completed": ("due",),
            "cancelled": ("pending","due","paused"),
        }[status]
        placeholders = ",".join("?" for _ in allowed)
        cursor = self.connection.execute(
            f"UPDATE tasks SET status=?,updated_utc=? "
            f"WHERE id=? AND status IN ({placeholders})",
            (status,utcnow().isoformat(),task_id,*allowed))
        if cursor.rowcount != 1:
            raise TaskRejected("Task missing or incompatible state")


def main(argv=None):
    parser = argparse.ArgumentParser(description="VARYN owner-local task ledger; NO automatic execution")
    parser.add_argument("--db",required=True)
    commands = parser.add_subparsers(dest="action",required=True)
    add = commands.add_parser("add")
    add.add_argument("--title",required=True)
    add.add_argument("--detail",default="")
    add.add_argument("--due-utc")
    listing = commands.add_parser("list")
    listing.add_argument("--status",choices=sorted(_STATUSES))
    listing.add_argument("--limit",type=int,default=50)
    listing.add_argument("--offset",type=int,default=0)
    commands.add_parser("count")
    due = commands.add_parser("mark-due")
    due.add_argument("--batch-size",type=int,default=100)
    args=parser.parse_args(argv)
    with TaskStore(args.db) as store:
        if args.action=="add":
            result={"id":store.create(args.title,detail=args.detail,due_utc=args.due_utc)}
        elif args.action=="list":
            result={"tasks":store.list(status=args.status,limit=args.limit,offset=args.offset)}
        elif args.action=="count":
            result={"total":store.count()}
        else:
            result={"marked_due_ids":store.mark_due(batch_size=args.batch_size)}
    print(json.dumps(result,ensure_ascii=False))


if __name__=="__main__":
    main()
