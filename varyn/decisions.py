"""Experimental revisioned decisions with provenance and stale-write protection.

Separate from legacy 'memories' table; this does NOT authenticate owner labels.
Use only synthetic data until security and authorization are implemented.
"""
import sqlite3
from datetime import datetime, timezone
from varyn.safety import assert_no_obvious_secrets


class RevisionConflict(Exception):
    """The expected revision is no longer the current revision."""


def _required(value, name, limit):
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > limit:
        raise ValueError(f"{name} must be a nonempty string up to {limit} characters")
    return value.strip()


class DecisionJournal:
    def __init__(self, path, owner_id, *, connection=None):
        self.owner_id = _required(owner_id, "owner_id", 128)
        self._owns_connection = connection is None
        self.db = sqlite3.connect(path, timeout=10) if connection is None else connection
        self.db.row_factory = sqlite3.Row
        self.db.execute("""CREATE TABLE IF NOT EXISTS decision_revisions (
            id INTEGER PRIMARY KEY,
            owner_id TEXT NOT NULL,
            project TEXT NOT NULL,
            decision_key TEXT NOT NULL,
            revision INTEGER NOT NULL,
            content TEXT NOT NULL,
            source_ref TEXT NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE(owner_id, project, decision_key, revision)
        )""")
        self.db.execute("""CREATE INDEX IF NOT EXISTS decision_lookup
            ON decision_revisions(owner_id, project, decision_key, revision DESC)""")
        self.db.commit()

    def close(self):
        if self._owns_connection:
            self.db.close()

    def put(self, project, key, content, source_ref, expected_revision=0):
        """Append a revision only if the caller saw the current revision.

        Set expected_revision=0 to create a new key. An existing key must be
        explicitly revised using the previously observed revision number.
        """
        project = _required(project, "project", 120)
        key = _required(key, "key", 120)
        content = _required(content, "content", 20000)
        source_ref = _required(source_ref, "source_ref", 2048)
        assert_no_obvious_secrets(content, source_ref)
        if type(expected_revision) is not int or expected_revision < 0:
            raise ValueError("expected_revision must be a non-negative integer")

        # BEGIN IMMEDIATE serializes competing writers before reading revision.
        self.db.execute("BEGIN IMMEDIATE")
        try:
            row = self.db.execute(
                """SELECT MAX(revision) AS latest FROM decision_revisions
                WHERE owner_id=? AND project=? AND decision_key=?""",
                (self.owner_id, project, key),
            ).fetchone()
            current = row["latest"] or 0
            if current != expected_revision:
                raise RevisionConflict(f"Expected revision {expected_revision}, found {current}")
            revision = current + 1
            self.db.execute(
                """INSERT INTO decision_revisions(
                    owner_id,project,decision_key,revision,content,source_ref,created_at
                ) VALUES (?,?,?,?,?,?,?)""",
                (self.owner_id, project, key, revision, content,
                 source_ref, datetime.now(timezone.utc).isoformat()),
            )
            self.db.commit()
        except BaseException:
            self.db.rollback()
            raise
        return revision

    def history(self, project, key):
        project = _required(project, "project", 120)
        key = _required(key, "key", 120)
        rows = self.db.execute(
            """SELECT revision,content,source_ref,created_at
            FROM decision_revisions WHERE owner_id=? AND project=? AND decision_key=?
            ORDER BY revision ASC""", (self.owner_id, project, key))
        return [dict(row) for row in rows]

    def current(self, project, key):
        history = self.history(project, key)
        return history[-1] if history else None

    def list_current(self, project, limit=50):
        project = _required(project, "project", 120)
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")
        rows = self.db.execute(
            """SELECT d.decision_key,d.revision,d.content,d.source_ref,d.created_at
            FROM decision_revisions AS d
            WHERE d.owner_id=? AND d.project=? AND d.revision=(
              SELECT MAX(r.revision) FROM decision_revisions AS r
              WHERE r.owner_id=d.owner_id AND r.project=d.project
                AND r.decision_key=d.decision_key
            )
            ORDER BY d.decision_key LIMIT ?""", (self.owner_id, project, limit))
        return [dict(row) for row in rows]
