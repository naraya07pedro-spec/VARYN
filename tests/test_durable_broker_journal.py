"""17S-15 parent-only durable dispatch/no-replay regressions."""
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest

from varyn.bounded_broker_protocol import BrokerRejected
from varyn.durable_broker_journal import DurableOneShotJournal


FIRST = "00112233445566778899aabbccddeeff"
SECOND = "11223344556677889900aabbccddeeff"


class DurableBrokerJournalTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory(prefix="varyn-broker-journal-")
        self.path = str(Path(self.temp.name) / "broker.sqlite")
        self.journal = DurableOneShotJournal(self.path)

    def tearDown(self):
        self.journal.close()
        self.temp.cleanup()

    def test_claim_is_committed_before_dispatch_and_survives_restart(self):
        self.assertTrue(self.journal.claim(FIRST, now=500))
        self.assertEqual(self.journal.status(FIRST), "claimed")
        self.journal.close()
        self.journal = DurableOneShotJournal(self.path)
        self.assertEqual(self.journal.status(FIRST), "claimed")
        with self.assertRaises(BrokerRejected):
            self.journal.claim(FIRST, now=501)
        self.assertEqual(self.journal.finalize(FIRST, succeeded=True, now=502),
                         "completed")
        self.journal.close()
        self.journal = DurableOneShotJournal(self.path)
        self.assertEqual(self.journal.status(FIRST), "completed")
        with self.assertRaises(BrokerRejected):
            self.journal.claim(FIRST)
        with self.assertRaises(BrokerRejected):
            self.journal.finalize(FIRST, succeeded=False)
        self.assertEqual(self.journal.status(FIRST), "completed")

    def test_failed_request_cannot_be_resubmitted_with_same_id(self):
        self.journal.claim(FIRST)
        self.assertEqual(self.journal.finalize(FIRST, succeeded=False), "failed")
        with self.assertRaises(BrokerRejected):
            self.journal.claim(FIRST)
        self.assertTrue(self.journal.claim(SECOND))
        self.assertEqual(self.journal.status(SECOND), "claimed")

    def test_two_independent_connections_cannot_claim_same_id(self):
        second = DurableOneShotJournal(self.path)
        try:
            self.assertTrue(self.journal.claim(FIRST))
            with self.assertRaises(BrokerRejected):
                second.claim(FIRST)
            self.assertEqual(second.status(FIRST), "claimed")
            self.assertEqual(second.finalize(FIRST, succeeded=False), "failed")
            with self.assertRaises(BrokerRejected):
                self.journal.finalize(FIRST, succeeded=True)
        finally:
            second.close()

    def test_database_contains_only_digest_and_status_not_original_id(self):
        self.journal.claim(FIRST)
        rows = self.journal.db.execute(
            "SELECT request_digest,state FROM broker_dispatch"
        ).fetchall()
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(rows[0][0]), 64)
        self.assertNotEqual(rows[0][0], FIRST)
        self.assertEqual(rows[0][1], "claimed")
        schema = self.journal.db.execute(
            "SELECT sql FROM sqlite_master WHERE name='broker_dispatch'"
        ).fetchone()[0]
        for disallowed in ("payload", "secret", "response", "prompt",
                           "file_path", "provider"):
            self.assertNotIn(disallowed, schema.lower())

    def test_bad_ids_types_and_timestamps_never_create_claim(self):
        for bad in ("", "1234", "G" * 32, "f" * 33, True, 42, None):
            with self.subTest(bad=bad):
                with self.assertRaises(BrokerRejected):
                    self.journal.claim(bad)
        for timestamp in (0, -1, True, "50"):
            with self.subTest(timestamp=timestamp):
                with self.assertRaises(BrokerRejected):
                    self.journal.claim(FIRST, now=timestamp)
        self.assertIsNone(self.journal.status(FIRST))
        self.journal.claim(FIRST)
        with self.assertRaises(BrokerRejected):
            self.journal.finalize(FIRST, succeeded=1)
        self.assertEqual(self.journal.status(FIRST), "claimed")

    def test_unreadable_existing_database_never_silently_resets(self):
        self.journal.close()
        Path(self.path).write_bytes(b"NOT-SQLITE-VARYN")
        with self.assertRaises((sqlite3.DatabaseError, BrokerRejected)):
            DurableOneShotJournal(self.path)
        self.assertEqual(Path(self.path).read_bytes(), b"NOT-SQLITE-VARYN")

    def test_closed_journal_cannot_grant_dispatch(self):
        self.journal.close()
        with self.assertRaises(BrokerRejected):
            self.journal.claim(FIRST)


if __name__ == "__main__":
    unittest.main()
