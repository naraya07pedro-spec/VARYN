"""Explicit unsaved-change guard tests for Windows DPAPI sessions."""
import os
import tempfile
import unittest
from pathlib import Path

from varyn.sealed_memory import SealedMemorySession

@unittest.skipUnless(os.name == "nt", "Native Windows DPAPI session required")
class UnsavedChangeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "saved.varyn"

    def tearDown(self):
        self.temp.cleanup()

    def test_clean_session_can_close_checked(self):
        session = SealedMemorySession()
        self.assertFalse(session.has_unsaved_changes)
        session.close_checked()
        with self.assertRaises(RuntimeError):
            _ = session.has_unsaved_changes

    def test_unsaved_memory_rejected_without_closing(self):
        session = SealedMemorySession()
        try:
            session.add("VARYN", "storage pending")
            self.assertTrue(session.has_unsaved_changes)
            with self.assertRaisesRegex(RuntimeError, "Unsaved changes"):
                session.close_checked()
            self.assertEqual(len(session.search("storage", "VARYN")), 1)
            session.save_new(self.path)
            self.assertFalse(session.has_unsaved_changes)
            session.close_checked()
        finally:
            session.close()

    def test_unsaved_decision_is_tracked(self):
        session = SealedMemorySession()
        try:
            session.put_decision("VARYN", "location", "storage on D", "fixture")
            self.assertTrue(session.has_unsaved_changes)
            with self.assertRaises(RuntimeError):
                session.close_checked()
            session.save_new(self.path)
            session.close_checked()
        finally:
            session.close()

    def test_failed_save_does_not_mark_clean_or_overwrite(self):
        session = SealedMemorySession()
        try:
            session.add("VARYN", "storage initial")
            session.save_new(self.path)
            old = self.path.read_bytes()
            session.add("VARYN", "storage new")
            with self.assertRaises(FileExistsError):
                session.save_new(self.path)
            self.assertTrue(session.has_unsaved_changes)
            self.assertEqual(self.path.read_bytes(), old)
        finally:
            session.close()

    def test_reopened_snapshot_starts_clean(self):
        with SealedMemorySession() as session:
            session.add("VARYN", "storage persisted")
            session.save_new(self.path)
        reopened = SealedMemorySession(self.path)
        self.assertFalse(reopened.has_unsaved_changes)
        reopened.close_checked()


if __name__ == "__main__":
    unittest.main()
