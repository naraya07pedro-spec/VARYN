"""Windows DPAPI whole-image SQLite persistence regression tests."""
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from varyn.dpapi_vault import SealedDataError, UnsupportedPlatformError, seal_bytes
from varyn.sealed_memory import SealedMemorySession


class SealedMemoryPlatformTests(unittest.TestCase):
    @unittest.skipIf(os.name == "nt", "Test is for non-Windows hosts")
    def test_other_platform_fails_without_creating_file(self):
        with self.assertRaises(UnsupportedPlatformError):
            SealedMemorySession()

    def test_closed_session_rejects_operations_on_windows(self):
        if os.name != "nt":
            self.skipTest("Windows-only")
        session = SealedMemorySession()
        session.close()
        with self.assertRaises(RuntimeError):
            session.add("VARYN", "synthetic note")


@unittest.skipUnless(os.name == "nt", "DPAPI requires native Windows profile")
class SealedMemoryWindowsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.file = Path(self.tmp.name) / "snapshot01.varyn"

    def tearDown(self):
        self.tmp.cleanup()

    def test_roundtrip_and_no_plaintext_disk_image(self):
        note = "synthetic storage record 2026"
        with SealedMemorySession() as memory:
            memory.add("VARYN", note)
            memory.save_new(self.file)
        sealed = self.file.read_bytes()
        self.assertNotIn(note.encode(), sealed)
        self.assertNotIn(b"SQLite format 3", sealed)
        with SealedMemorySession(self.file) as restored:
            self.assertEqual(restored.search("storage", "VARYN")[0]["content"], note)

    def test_snapshot_includes_fts_index_without_plaintext_sidecar(self):
        with SealedMemorySession() as memory:
            memory.add("VARYN", "indexed historical note")
            memory.save_new(self.file)
        with SealedMemorySession(self.file) as memory:
            self.assertEqual(
                memory.store.db.execute(
                    "SELECT count(*) FROM memory_fts WHERE memory_fts MATCH 'historical'"
                ).fetchone()[0], 1
            )
        names = {p.name for p in self.file.parent.iterdir()}
        self.assertEqual(names, {self.file.name})

    def test_existing_snapshot_cannot_be_overwritten(self):
        with SealedMemorySession() as memory:
            memory.add("VARYN", "first record")
            memory.save_new(self.file)
            original = self.file.read_bytes()
            memory.add("VARYN", "second record")
            with self.assertRaises(FileExistsError):
                memory.save_new(self.file)
            self.assertEqual(self.file.read_bytes(), original)

    def test_tamper_rejected_before_access(self):
        with SealedMemorySession() as memory:
            memory.add("VARYN", "hello synthetic")
            memory.save_new(self.file)
        data = bytearray(self.file.read_bytes())
        data[-1] ^= 1
        self.file.write_bytes(data)
        with self.assertRaises(SealedDataError):
            SealedMemorySession(self.file)

    def test_non_sqlite_encrypted_payload_rejected(self):
        self.file.write_bytes(seal_bytes(b"not sqlite at all"))
        with self.assertRaises(SealedDataError):
            SealedMemorySession(self.file)

    def test_legacy_plaintext_database_is_never_accepted(self):
        self.file.write_bytes(b"SQLite format 3" + b"\x00" * 200)
        with self.assertRaises(SealedDataError):
            SealedMemorySession(self.file)

    def test_secret_write_guard_remains_active(self):
        from varyn.safety import SensitiveContentError
        with SealedMemorySession() as memory:
            with self.assertRaises(SensitiveContentError):
                memory.add("VARYN", "password=syntheticpassword123")
            self.assertEqual(memory.search("password"), [])

    def test_second_snapshot_is_explicit_and_immutable(self):
        second = self.file.with_name("snapshot02.varyn")
        with SealedMemorySession() as memory:
            memory.add("VARYN", "original")
            memory.save_new(self.file)
            memory.add("VARYN", "added later")
            memory.save_new(second)
        with SealedMemorySession(self.file) as old:
            self.assertEqual(len(old.search("record", "VARYN")), 0)
            self.assertEqual(len(old.search("added", "VARYN")), 0)
        with SealedMemorySession(second) as new:
            self.assertEqual(len(new.search("added", "VARYN")), 1)


if __name__ == "__main__":
    unittest.main()
