"""Portable, read-only encrypted recovery inspection in an in-memory SQLite DB.

Does not publish plaintext or write SQLite to disk. It verifies cryptographic
authentication, SQLite integrity and minimum VARYN tables but is not a security
audit, recovery guarantee, or authorization mechanism.
"""
import sqlite3

from varyn.recovery import RecoveryError, read_recovery

_REQUIRED_MEM = {"id", "owner_id", "project", "content", "created_at"}
_REQUIRED_DEC = {
    "id", "owner_id", "project", "decision_key", "revision",
    "content", "source_ref", "created_at",
}
_LOCAL_OWNER = "local-windows-session"


def inspect_recovery(path, passphrase):
    """Authenticate/decrypt and validate a recovery image in RAM only.

    Return safe metadata and counts; never return paths, notes or passphrases.
    Invalid inputs use generic RecoveryError messages.
    """
    image = read_recovery(path, passphrase)
    db = sqlite3.connect(":memory:")
    try:
        try:
            db.deserialize(image)
            if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise RecoveryError("Recovery SQLite integrity failed")
            tables = {
                row[0] for row in db.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
            if "memories" not in tables:
                raise RecoveryError("Unsupported recovery schema")
            mem_columns = {row[1] for row in db.execute("PRAGMA table_info(memories)")}
            if not _REQUIRED_MEM <= mem_columns:
                raise RecoveryError("Unsupported recovery schema")
            if db.execute(
                "SELECT 1 FROM memories WHERE owner_id<>? LIMIT 1", (_LOCAL_OWNER,)
            ).fetchone():
                raise RecoveryError("Unsupported recovery owner label")
            mem_count = db.execute("SELECT count(*) FROM memories").fetchone()[0]
            decision_count = 0
            if "decision_revisions" in tables:
                dec_columns = {
                    row[1] for row in db.execute(
                        "PRAGMA table_info(decision_revisions)"
                    )
                }
                if not _REQUIRED_DEC <= dec_columns:
                    raise RecoveryError("Unsupported recovery decision schema")
                if db.execute(
                    "SELECT 1 FROM decision_revisions WHERE owner_id<>? LIMIT 1",
                    (_LOCAL_OWNER,),
                ).fetchone():
                    raise RecoveryError("Unsupported recovery decision owner")
                decision_count = db.execute(
                    "SELECT count(*) FROM decision_revisions"
                ).fetchone()[0]
            return {
                "format": "varyn.recovery.inspection.v1",
                "authenticated": True,
                "sqlite_integrity": "ok",
                "memories": mem_count,
                "decision_revisions": decision_count,
                "contains_fts5_table": "memory_fts" in tables,
                "ready_for_sensitive_data": False,
            }
        except sqlite3.Error as exc:
            raise RecoveryError("Invalid recovery SQLite image") from None
    finally:
        db.close()
