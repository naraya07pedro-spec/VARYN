"""Synthetic tests for source-aware, append-only decision revisions."""
import tempfile
import unittest
from pathlib import Path
from varyn.decisions import DecisionJournal, RevisionConflict


class DecisionJournalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp.name) / "decisions.sqlite3"
        self.journal = DecisionJournal(self.db_path, "owner")

    def tearDown(self):
        self.journal.close()
        self.temp.cleanup()

    def test_first_entry_has_source_and_revision(self):
        version = self.journal.put("VARYN", "storage", "Use D drive", "meeting:001")
        self.assertEqual(version, 1)
        entry = self.journal.current("VARYN", "storage")
        self.assertEqual(entry["source_ref"], "meeting:001")
        self.assertEqual(entry["revision"], 1)

    def test_revisions_keep_history_and_latest(self):
        self.journal.put("VARYN", "storage", "Use D drive", "note:001")
        self.journal.put("VARYN", "storage", "Use external drive", "note:002", 1)
        self.assertEqual([x["revision"] for x in self.journal.history("VARYN", "storage")], [1, 2])
        self.assertEqual(self.journal.current("VARYN", "storage")["content"], "Use external drive")

    def test_stale_revision_rejected_without_new_row(self):
        self.journal.put("VARYN", "storage", "D", "source:A")
        with self.assertRaises(RevisionConflict):
            self.journal.put("VARYN", "storage", "C", "source:B", 0)
        self.assertEqual(len(self.journal.history("VARYN", "storage")), 1)

    def test_owner_isolation(self):
        self.journal.put("VARYN", "secret", "Synthetic private value", "fixture:1")
        other = DecisionJournal(self.db_path, "different-owner")
        try:
            self.assertIsNone(other.current("VARYN", "secret"))
            self.assertEqual(other.list_current("VARYN"), [])
        finally:
            other.close()

    def test_project_isolation_and_current_listing(self):
        self.journal.put("VARYN", "storage", "D", "fixture:1")
        self.journal.put("VARYN", "storage", "D preferred", "fixture:2", 1)
        self.journal.put("RepoPilot", "storage", "S3", "fixture:3")
        items = self.journal.list_current("VARYN")
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["revision"], 2)
        self.assertEqual(items[0]["content"], "D preferred")

    def test_invalid_source_or_revision_rejected(self):
        with self.assertRaises(ValueError):
            self.journal.put("VARYN", "storage", "D", "")
        with self.assertRaises(ValueError):
            self.journal.put("VARYN", "storage", "D", "fixture", True)
        with self.assertRaises(ValueError):
            self.journal.list_current("VARYN", 0)

    def test_reopen_keeps_decisions(self):
        self.journal.put("VARYN", "version", "Remember me", "fixture:1")
        self.journal.close()
        self.journal = DecisionJournal(self.db_path, "owner")
        self.assertEqual(self.journal.current("VARYN", "version")["revision"], 1)


if __name__ == "__main__":
    unittest.main()
