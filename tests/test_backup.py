import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from varyn.backup import backup_database


class BackupTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.source = self.base / "memory.sqlite3"
        with closing(sqlite3.connect(self.source)) as db:
            db.execute("CREATE TABLE entries (content TEXT)")
            db.execute("INSERT INTO entries VALUES (?)", ("VARYN milestone",))
            db.commit()

    def tearDown(self):
        self.tmp.cleanup()

    def test_consistent_snapshot_and_original_unchanged(self):
        copy = backup_database(self.source, self.base / "copy.sqlite3")
        with closing(sqlite3.connect(copy)) as db:
            self.assertEqual(db.execute("SELECT content FROM entries").fetchone()[0], "VARYN milestone")
        with closing(sqlite3.connect(self.source)) as db:
            db.execute("INSERT INTO entries VALUES ('later')")
            db.commit()
        with closing(sqlite3.connect(copy)) as db:
            self.assertEqual(db.execute("SELECT count(*) FROM entries").fetchone()[0], 1)

    def test_does_not_overwrite(self):
        target = self.base / "copy.sqlite3"
        target.write_bytes(b"existing")
        with self.assertRaises(FileExistsError):
            backup_database(self.source, target)
        self.assertEqual(target.read_bytes(), b"existing")

    def test_missing_source_or_directory(self):
        with self.assertRaises(FileNotFoundError):
            backup_database(self.base / "missing.db", self.base / "copy.sqlite3")
        with self.assertRaises(FileNotFoundError):
            backup_database(self.source, self.base / "missing" / "copy.sqlite3")

    def test_refuses_self_overwrite(self):
        with self.assertRaises(ValueError):
            backup_database(self.source, self.source)


if __name__ == "__main__":
    unittest.main()
