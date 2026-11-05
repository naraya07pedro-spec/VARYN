"""17S-15: crash-safe, parent-owned one-shot broker dispatch journal.

Records only hash identifiers and control status, never prompts, tokens,
file paths, provider histories, payloads, outputs or HMAC secrets. Designed
to be held by the trusted parent, NOT in an AppContainer shared directory.

'Claim before execute' intentionally sacrifices automatic recovery to avoid
accidental duplicate effects after a crash. A claimed but uncompleted request
MUST require a new owner-reviewed request with a different ID; never replay.
"""
import hashlib
from pathlib import Path
import sqlite3
import time

from varyn.bounded_broker_protocol import BrokerRejected

_SCHEMA = 1
_ALLOWED = {"claimed", "completed", "failed"}


def _digest_id(request_id):
    if (type(request_id) is not str or len(request_id) != 32
            or any(c not in "0123456789abcdef" for c in request_id)):
        raise BrokerRejected("Invalid broker request identifier")
    return hashlib.sha256(bytes.fromhex(request_id)).hexdigest()


class DurableOneShotJournal:
    def __init__(self, path):
        if type(path) is not str or path == ":memory:":
            raise BrokerRejected("Durable parent journal path required")
        target = Path(path)
        if not target.is_absolute() or not target.parent.is_dir():
            raise BrokerRejected("Trusted journal parent directory missing")
        self.db = None
        self._closed = False
        try:
            self.db = sqlite3.connect(str(target), timeout=3, isolation_level=None)
            self.db.execute("PRAGMA busy_timeout=3000")
            self.db.execute("PRAGMA synchronous=FULL")
            mode = self.db.execute("PRAGMA journal_mode=WAL").fetchone()[0]
            if str(mode).lower() != "wal":
                raise BrokerRejected("Durable WAL unavailable")
            self.db.execute("""
                CREATE TABLE IF NOT EXISTS broker_dispatch (
                    request_digest TEXT PRIMARY KEY,
                    state TEXT NOT NULL CHECK (
                        state IN ('claimed','completed','failed')),
                    claimed_at INTEGER NOT NULL,
                    finalized_at INTEGER
                )
            """)
            self.db.execute(f"PRAGMA user_version={_SCHEMA}")
            self.db.execute(
                "SELECT request_digest, state, claimed_at, finalized_at "
                "FROM broker_dispatch LIMIT 1"
            ).fetchall()
        except Exception:
            if self.db is not None:
                self.db.close()
            self._closed = True
            raise

    def _ready(self):
        if self._closed or self.db is None:
            raise BrokerRejected("Parent broker journal is closed")

    def claim(self, request_id, *, now=None):
        """Atomically record the attempt BEFORE child spawn/pipe dispatch.

        All duplicate states, even failed/claimed, are refused. COMMIT occurs
        before returning True; if anything fails, do not dispatch.
        """
        self._ready()
        digest = _digest_id(request_id)
        timestamp = int(time.time()) if now is None else now
        if type(timestamp) is not int or timestamp < 1:
            raise BrokerRejected("Invalid broker journal timestamp")
        try:
            self.db.execute("BEGIN IMMEDIATE")
            self.db.execute(
                "INSERT INTO broker_dispatch "
                "(request_digest,state,claimed_at,finalized_at) "
                "VALUES (?,'claimed',?,NULL)",
                (digest, timestamp),
            )
            self.db.execute("COMMIT")
        except sqlite3.Error as exc:
            if self.db.in_transaction:
                self.db.execute("ROLLBACK")
            raise BrokerRejected("Broker dispatch already claimed or unavailable") from None
        except Exception:
            if self.db.in_transaction:
                self.db.execute("ROLLBACK")
            raise
        return True

    def finalize(self, request_id, *, succeeded, now=None):
        """One legal transition only: claimed -> completed/failed."""
        self._ready()
        digest = _digest_id(request_id)
        if type(succeeded) is not bool:
            raise BrokerRejected("Explicit broker outcome required")
        timestamp = int(time.time()) if now is None else now
        if type(timestamp) is not int or timestamp < 1:
            raise BrokerRejected("Invalid broker journal timestamp")
        status = "completed" if succeeded else "failed"
        try:
            self.db.execute("BEGIN IMMEDIATE")
            cur = self.db.execute(
                "UPDATE broker_dispatch SET state=?,finalized_at=? "
                "WHERE request_digest=? AND state='claimed'",
                (status, timestamp, digest),
            )
            if cur.rowcount != 1:
                raise BrokerRejected("Broker outcome cannot be replayed")
            self.db.execute("COMMIT")
        except Exception:
            if self.db.in_transaction:
                self.db.execute("ROLLBACK")
            raise
        return status

    def status(self, request_id):
        self._ready()
        digest = _digest_id(request_id)
        row = self.db.execute(
            "SELECT state FROM broker_dispatch WHERE request_digest=?",
            (digest,),
        ).fetchone()
        return None if row is None else row[0]

    def close(self):
        if self._closed:
            return
        self._closed = True
        self.db.close()
