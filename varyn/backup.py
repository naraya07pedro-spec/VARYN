"""Consistent SQLite backup snapshots for VARYN's local prototype.

The backups are unencrypted. Store only synthetic/test data for now.
"""

import argparse
import os
import sqlite3
import tempfile
from contextlib import closing
from pathlib import Path


def backup_database(source, destination):
    """Create a consistent snapshot, without replacing any existing backup.

    Uses SQLite's online backup interface and atomically publishes the completed
    file in the destination directory. Source database must already exist.
    """
    source = Path(source).resolve()
    destination = Path(destination).resolve()
    if not source.is_file():
        raise FileNotFoundError(source)
    if source == destination:
        raise ValueError("Source and destination must differ")
    if not destination.parent.is_dir():
        raise FileNotFoundError(destination.parent)
    if destination.exists():
        raise FileExistsError(destination)

    fd, temporary = tempfile.mkstemp(prefix=".varyn-backup-", suffix=".sqlite3", dir=destination.parent)
    os.close(fd)
    try:
        with closing(sqlite3.connect(f"file:{source.as_posix()}?mode=ro", uri=True)) as origin:
            with closing(sqlite3.connect(temporary)) as snapshot:
                origin.backup(snapshot)
                if snapshot.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                    raise sqlite3.DatabaseError("Backup failed SQLite integrity check")
        # Atomically publish only if the destination is still absent.
        # os.link fails instead of overwriting a file created concurrently.
        os.link(temporary, destination)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return destination


def main():
    parser = argparse.ArgumentParser(description="VARYN local SQLite backup (unencrypted)")
    parser.add_argument("--db", required=True, help="Existing local SQLite database")
    parser.add_argument("--output", required=True, help="New backup path (will not overwrite)")
    args = parser.parse_args()
    print(backup_database(args.db, args.output))


if __name__ == "__main__":
    main()
