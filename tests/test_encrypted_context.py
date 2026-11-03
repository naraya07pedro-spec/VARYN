"""End-to-end synthetic encrypted context and decision integration tests."""
import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path

from varyn.decisions import RevisionConflict
from varyn.dpapi_vault import SealedDataError, seal_bytes
from varyn.sealed_memory import SealedMemorySession
from varyn.safety import SensitiveContentError


@unittest.skipUnless(os.name == "nt", "Windows DPAPI user profile required")
class EncryptedContextWindowsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.snapshot = Path(self.temp.name) / "synthetic.varyn"

    def tearDown(self):
        self.temp.cleanup()

    def test_decision_and_memory_roundtrip_with_context(self):
        with SealedMemorySession() as session:
            session.add("VARYN", "storage historical note")
            self.assertEqual(session.put_decision(
                "VARYN", "storage", "storage on D", "fixture:original"), 1)
            preview = session.context("VARYN", "storage")
            self.assertEqual({x["type"] for x in preview["items"]}, {"memory", "decision"})
            session.save_new(self.snapshot)

        blob = self.snapshot.read_bytes()
        self.assertNotIn(b"storage historical note", blob)
        self.assertNotIn(b"storage on D", blob)
        self.assertNotIn(b"fixture:original", blob)
        self.assertNotIn(b"SQLite format 3", blob)
        with SealedMemorySession(self.snapshot) as reopened:
            self.assertEqual(reopened.current_decision("VARYN", "storage")["revision"], 1)
            self.assertEqual(reopened.decision_history("VARYN", "storage")[0]["source_ref"], "fixture:original")
            package = reopened.context("VARYN", "storage")
            self.assertEqual({x["type"] for x in package["items"]}, {"memory", "decision"})
            self.assertFalse(next(x for x in package["items"] if x["type"] == "decision")["source_verified"])

    def test_stale_revision_rejected_then_latest_revision_selected(self):
        with SealedMemorySession() as session:
            session.put_decision("VARYN", "path", "storage old", "fixture:old")
            with self.assertRaises(RevisionConflict):
                session.put_decision("VARYN", "path", "storage stale", "fixture:stale")
            self.assertEqual(session.put_decision(
                "VARYN", "path", "storage current", "fixture:new", 1), 2)
            session.save_new(self.snapshot)
        with SealedMemorySession(self.snapshot) as reopened:
            self.assertEqual([r["revision"] for r in reopened.decision_history("VARYN", "path")], [1, 2])
            items = reopened.context("VARYN", "storage")["items"]
            self.assertEqual([x["content"] for x in items], ["storage current"])

    def test_project_scope_for_memory_and_decisions(self):
        with SealedMemorySession() as session:
            session.add("Another", "storage other memory")
            session.put_decision("Another", "storage", "storage other decision", "fixture:other")
            session.add("VARYN", "storage own memory")
            session.put_decision("VARYN", "storage", "storage own decision", "fixture:own")
            session.save_new(self.snapshot)
        with SealedMemorySession(self.snapshot) as reopened:
            encoded = json.dumps(reopened.context("VARYN", "storage"))
            self.assertIn("own decision", encoded)
            self.assertNotIn("other decision", encoded)
            self.assertNotIn("other memory", encoded)

    def test_budget_and_deduplication_remain_active(self):
        with SealedMemorySession() as session:
            session.add("VARYN", "storage identical")
            session.put_decision("VARYN", "storage", "storage identical", "fixture:decision")
            package = session.context("VARYN", "storage", max_chars=500)
            self.assertEqual([x["type"] for x in package["items"]], ["decision"])
            self.assertEqual(package["duplicates_skipped"], 1)
            self.assertLessEqual(len(json.dumps(package, ensure_ascii=False, sort_keys=True, separators=(",", ":"))), 500)

    def test_secret_guard_applies_to_decisions(self):
        with SealedMemorySession() as session:
            with self.assertRaises(SensitiveContentError):
                session.put_decision("VARYN", "storage", "password=synthetic123456", "fixture:secret")
            self.assertIsNone(session.current_decision("VARYN", "storage"))

    def test_separate_old_snapshot_retains_prior_decision(self):
        second = self.snapshot.with_name("v2.varyn")
        with SealedMemorySession() as session:
            session.put_decision("VARYN", "location", "storage old", "fixture:v1")
            session.save_new(self.snapshot)
            session.put_decision("VARYN", "location", "storage new", "fixture:v2", 1)
            session.save_new(second)
        with SealedMemorySession(self.snapshot) as prior:
            self.assertEqual(prior.current_decision("VARYN", "location")["revision"], 1)
        with SealedMemorySession(second) as latest:
            self.assertEqual(latest.current_decision("VARYN", "location")["revision"], 2)

    def test_context_and_decision_calls_after_close_rejected(self):
        session = SealedMemorySession()
        session.close()
        for operation in (
            lambda: session.context("VARYN", "storage"),
            lambda: session.put_decision("VARYN", "storage", "storage", "fixture:source"),
            lambda: session.current_decision("VARYN", "storage"),
        ):
            with self.assertRaises(RuntimeError):
                operation()

    def test_tampered_snapshot_not_opened(self):
        with SealedMemorySession() as session:
            session.put_decision("VARYN", "storage", "storage note", "fixture")
            session.save_new(self.snapshot)
        data = bytearray(self.snapshot.read_bytes())
        data[-1] ^= 1
        self.snapshot.write_bytes(data)
        with self.assertRaises(SealedDataError):
            SealedMemorySession(self.snapshot)

    def test_wrong_owner_decision_snapshot_rejected(self):
        with SealedMemorySession() as session:
            session.put_decision("VARYN", "storage", "storage owned", "fixture")
            with session.store.db:
                session.store.db.execute(
                    "UPDATE decision_revisions SET owner_id='foreign' WHERE decision_key='storage'"
                )
            # Re-seal a deliberately invalid SQLite image for validation.
            session.save_new(self.snapshot)
        with self.assertRaises(SealedDataError):
            SealedMemorySession(self.snapshot)


class BorrowedConnectionTests(unittest.TestCase):
    def test_borrowed_database_stays_open_after_context(self):
        from varyn.context import build_context
        from varyn.memory import MemoryStore
        db = sqlite3.connect(":memory:")
        try:
            memory = MemoryStore(None, "fixture", connection=db)
            memory.add("VARYN", "storage example")
            context = build_context(None, "fixture", "VARYN", "storage", connection=db)
            self.assertTrue(context["items"])
            # Neither memory.close() nor context generation may close borrowed DB.
            memory.close()
            self.assertEqual(db.execute("SELECT count(*) FROM memories").fetchone()[0], 1)
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()
