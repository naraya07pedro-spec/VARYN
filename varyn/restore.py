"""Safe, additive restore of an existing VARYN SQLite memory backup.

This restores to a NEW path only. No database replacement or destructive
operation is permitted. Files are unencrypted and intended for test data.
"""
import argparse
import os
import shutil
import sqlite3
import tempfile
from contextlib import closing
from pathlib import Path
from urllib.parse import quote


def _validate_varyn_database(path):
    # Open read-only: never create/modify a backup as a side effect of validation.
    uri = "file:" + quote(path.as_posix(), safe="/:") + "?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as db:
        if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise sqlite3.DatabaseError("SQLite integrity check failed")
        columns = {
            row[1] for row in db.execute("PRAGMA table_info(memories)")
        }
        required = {"id", "owner_id", "project", "content", "created_at"}
        if not required.issubset(columns):
            raise ValueError("Backup is not a supported VARYN memory database")
        # Force a read of all entries so unreadable pages fail before publication.
        db.execute("SELECT COUNT(*) FROM memories").fetchone()


def restore_database(backup, destination):
    """Validate then restore into a new file, never overwriting existing data.

    The backup is expected to be an offline consistent SQLite snapshot created
    using VARYN's backup command. Do not use raw live-WAL file copies.
    """
    backup = Path(backup).resolve()
    destination = Path(destination).resolve()
    if backup == destination:
        raise ValueError("Backup and destination must differ")
    if not backup.is_file():
        raise FileNotFoundError(backup)
    if not destination.parent.is_dir():
        raise FileNotFoundError(destination.parent)
    if destination.exists():
        raise FileExistsError(destination)
    _validate_varyn_database(backup)

    fd, temporary = tempfile.mkstemp(
        prefix=".varyn-restore-", suffix=".sqlite3", dir=destination.parent
    )
    os.close(fd)
    try:
        with backup.open("rb") as source, open(temporary, "wb") as output:
            shutil.copyfileobj(source, output, length=1024 * 1024)
            output.flush()
            os.fsync(output.fileno())
        _validate_varyn_database(Path(temporary))
        # Atomic no-overwrite publication on the destination filesystem.
        # Hard links require supported filesystems; failure remains fail-closed.
        os.link(temporary, destination)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return destination


def main():
    parser = argparse.ArgumentParser(
        description="Restore an unencrypted VARYN memory backup to a NEW path"
    )
    parser.add_argument("--backup", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    print(restore_database(args.backup, args.output))


if __name__ == "__main__":
    main()
