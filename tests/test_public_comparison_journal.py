"""17S-8 crash/revocation/no-replay checks for opt-in public comparison journal."""
import sqlite3
import tempfile
import unittest
from pathlib import Path

from varyn.public_comparison_journal import PublicComparisonJournal
from varyn.task_journal import JournalConflict

D = "a" * 64


class PublicComparisonJournalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "comparison.sqlite3"
        self.journal = PublicComparisonJournal(self.path)

    def tearDown(self):
        self.journal.close()
        self.temp.cleanup()

    def test_complete_two_step_flow_has_no_authorization(self):
        tid = self.journal.create(D)
        self.journal.begin_step(tid, D, 0)
        self.journal.complete_step(tid, D, 0)
        self.journal.begin_step(tid, D, 1)
        self.journal.complete_step(tid, D, 1)
        self.journal.finish(tid, D)
        state = self.journal.inspect(tid)
        self.assertEqual(state["cursor"], 2)
        self.assertEqual(state["status"], "completed")
        self.assertFalse(state["executable"])
        self.assertFalse(state["authorization_persisted"])
        self.assertEqual(self.journal.recover()["auto_replayed"], 0)
        with self.assertRaises(JournalConflict):
            self.journal.begin_step(tid, D, 1)

    def test_crash_before_dispatch_needs_fresh_review(self):
        tid = self.journal.create(D)
        self.journal.close()
        self.journal = PublicComparisonJournal(self.path)
        self.assertEqual(self.journal.recover(),
                         {"needs_review": 1, "needs_reconciliation": 0,
                          "auto_replayed": 0})
        self.assertEqual(self.journal.inspect(tid)["status"], "needs_review")
        with self.assertRaises(JournalConflict):
            self.journal.begin_step(tid, D, 0)

    def test_crash_after_begin_is_uncertain_not_replayed(self):
        tid = self.journal.create(D)
        self.journal.begin_step(tid, D, 0)
        self.journal.close()
        self.journal = PublicComparisonJournal(self.path)
        self.assertEqual(self.journal.recover(),
                         {"needs_review": 0, "needs_reconciliation": 1,
                          "auto_replayed": 0})
        self.assertEqual(self.journal.inspect(tid)["cursor"], 0)
        self.assertEqual(self.journal.inspect(tid)["status"], "needs_reconciliation")
        with self.assertRaises(JournalConflict):
            self.journal.complete_step(tid, D, 0)
        with self.assertRaises(JournalConflict):
            self.journal.begin_step(tid, D, 0)

    def test_crash_between_steps_preserves_cursor_but_needs_review(self):
        tid = self.journal.create(D)
        self.journal.begin_step(tid, D, 0)
        self.journal.complete_step(tid, D, 0)
        self.journal.close()
        self.journal = PublicComparisonJournal(self.path)
        self.assertEqual(self.journal.recover()["needs_review"], 1)
        self.assertEqual(self.journal.inspect(tid)["cursor"], 1)
        with self.assertRaises(JournalConflict):
            self.journal.begin_step(tid, D, 1)

    def test_abort_pending_vs_inflight_classification(self):
        ready = self.journal.create(D)
        inflight = self.journal.create(D)
        self.journal.begin_step(inflight, D, 0)
        self.assertTrue(self.journal.abort(ready, D))
        self.assertTrue(self.journal.abort(inflight, D))
        self.assertEqual(self.journal.inspect(ready)["status"], "cancelled")
        self.assertEqual(self.journal.inspect(inflight)["status"], "needs_reconciliation")
        self.assertFalse(self.journal.abort(ready, D))
        self.assertEqual(self.journal.recover()["auto_replayed"], 0)

    def test_wrong_digest_replay_and_out_of_order_are_rejected(self):
        tid = self.journal.create(D)
        with self.assertRaises(JournalConflict):
            self.journal.begin_step(tid, "b" * 64, 0)
        with self.assertRaises(JournalConflict):
            self.journal.begin_step(tid, D, 1)
        with self.assertRaises(JournalConflict):
            self.journal.complete_step(tid, D, 0)
        self.journal.begin_step(tid, D, 0)
        with self.assertRaises(JournalConflict):
            self.journal.begin_step(tid, D, 0)
        with self.assertRaises(JournalConflict):
            self.journal.finish(tid, D)

    def test_database_never_stores_raw_repo_names_results_or_approvals(self):
        tid = self.journal.create(D)
        self.journal.begin_step(tid, D, 0)
        self.journal.complete_step(tid, D, 0)
        records = self.journal.db.execute(
            "SELECT * FROM public_comparison_checkpoints"
        ).fetchall()
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0][0], tid)
        self.assertEqual(records[0][1], D)
        self.assertEqual(len(records[0]), 4)
        self.assertNotIn("repo", repr(records).lower())

    def test_invalid_path_closed_and_recovery_are_rejected(self):
        with self.assertRaises(ValueError):
            PublicComparisonJournal(":memory:")
        with self.assertRaises(ValueError):
            self.journal.create("wrong")
        with self.assertRaises(ValueError):
            self.journal.begin_step("bad", D, 0)
        tid = self.journal.create(D)
        self.journal.close()
        with self.assertRaises(JournalConflict):
            self.journal.recover()
        with self.assertRaises(JournalConflict):
            self.journal.begin_step(tid, D, 0)


if __name__ == "__main__":
    unittest.main()
