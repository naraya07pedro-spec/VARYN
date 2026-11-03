"""Restore should never overwrite a live database or accept corrupt input."""
import sqlite3
import tempfile
import unittest
from pathlib import Path

from varyn.backup import backup_database
from varyn.memory import MemoryStore
from varyn.restore import restore_database


class RestoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.original = self.base / "original.sqlite3"
        memory = MemoryStore(self.original, "demo")
        self.memory_id = memory.add("VARYN", "A decision worth remembering")
        memory.close()
        self.backup = backup_database(
            self.original, self.base / "safe-backup.sqlite3"
        )

    def tearDown(self):
        self.tmp.cleanup()

    def test_round_trip_with_persisted_content(self):
        restored = restore_database(
            self.backup, self.base / "restored.sqlite3"
        )
        memory = MemoryStore(restored, "demo")
        self.assertEqual(
            [entry["id"] for entry in memory.search("remembering")],
            [self.memory_id],
        )
        memory.close()

    def test_existing_target_is_never_overwritten(self):
        target = self.base / "existing.sqlite3"
        target.write_bytes(b"do not destroy")
        with self.assertRaises(FileExistsError):
            restore_database(self.backup, target)
        self.assertEqual(target.read_bytes(), b"do not destroy")

    def test_refuses_source_equals_target(self):
        with self.assertRaises(ValueError):
            restore_database(self.backup, self.backup)

    def test_rejects_corrupt_backup_without_target(self):
        corrupt = self.base / "corrupt.sqlite3"
        corrupt.write_bytes(b"not a sqlite database")
        output = self.base / "restored.sqlite3"
        with self.assertRaises(sqlite3.DatabaseError):
            restore_database(corrupt, output)
        self.assertFalse(output.exists())

    def test_rejects_unrelated_sqlite_database(self):
        unrelated = self.base / "unrelated.sqlite3"
        with sqlite3.connect(unrelated) as db:
            db.execute("CREATE TABLE other (id INTEGER)")
        output = self.base / "restored.sqlite3"
        with self.assertRaises(ValueError):
            restore_database(unrelated, output)
        self.assertFalse(output.exists())

    def test_missing_paths_and_owner_scope(self):
        with self.assertRaises(FileNotFoundError):
            restore_database(self.base / "no-file.sqlite3", self.base / "restore.sqlite3")
        with self.assertRaises(FileNotFoundError):
            restore_database(self.backup, self.base / "missing" / "restore.sqlite3")
        output = restore_database(self.backup, self.base / "restore.sqlite3")
        other = MemoryStore(output, "other-user")
        self.assertEqual(other.search("remembering"), [])
        other.close()


if __name__ == "__main__":
    unittest.main()
