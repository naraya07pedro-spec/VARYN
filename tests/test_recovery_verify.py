"""Portable recovery verification with synthetic whole-image SQLite fixtures."""
import sqlite3
import tempfile
import unittest
from pathlib import Path

from varyn.decisions import DecisionJournal
from varyn.index import ensure_memory_index
from varyn.memory import MemoryStore
from varyn.recovery import RecoveryError, write_recovery
from varyn.recovery_verify import inspect_recovery

PHRASE = "long synthetic recovery phrase for tests 2026"


class RecoveryInspectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "inspect.varyn-recovery"
        self.db = sqlite3.connect(":memory:")
        self.store = MemoryStore(None, "local-windows-session", connection=self.db)
        self.decisions = DecisionJournal(None, "local-windows-session", connection=self.db)
        self.store.add("VARYN", "storage synthetic inspection")
        self.decisions.put("VARYN", "storage", "storage on D", "fixture:verification")
        ensure_memory_index(self.db)

    def tearDown(self):
        self.decisions.close()
        self.store.close()
        self.db.close()
        self.temp.cleanup()

    def export(self):
        self.db.commit()
        write_recovery(self.path, self.db.serialize(), PHRASE)

    def test_authentic_recovery_has_counts_and_fts(self):
        self.export()
        info = inspect_recovery(self.path, PHRASE)
        self.assertEqual(info["memories"], 1)
        self.assertEqual(info["decision_revisions"], 1)
        self.assertTrue(info["contains_fts5_table"])
        self.assertTrue(info["authenticated"])
        self.assertFalse(info["ready_for_sensitive_data"])

    def test_report_never_exposes_source_text_or_path(self):
        self.export()
        report = str(inspect_recovery(self.path, PHRASE))
        for secret in ("storage synthetic inspection", "fixture:verification", PHRASE, self.path.name):
            self.assertNotIn(secret, report)

    def test_wrong_password_rejected(self):
        self.export()
        with self.assertRaises(RecoveryError):
            inspect_recovery(self.path, "wrong synthetic password phrase 2026")

    def test_ciphertext_tampering_rejected(self):
        self.export()
        blob = bytearray(self.path.read_bytes())
        blob[-1] ^= 0x01
        self.path.write_bytes(blob)
        with self.assertRaises(RecoveryError):
            inspect_recovery(self.path, PHRASE)

    def test_wrong_owner_label_rejected_even_with_valid_encryption(self):
        self.db.execute("UPDATE memories SET owner_id='foreign'")
        self.export()
        with self.assertRaises(RecoveryError):
            inspect_recovery(self.path, PHRASE)

    def test_invalid_decision_table_rejected(self):
        self.db.execute("DROP TABLE decision_revisions")
        self.db.execute("CREATE TABLE decision_revisions(x TEXT)")
        self.export()
        with self.assertRaises(RecoveryError):
            inspect_recovery(self.path, PHRASE)

    def test_missing_required_memory_schema_rejected(self):
        self.db.execute("DROP TRIGGER memory_fts_insert")
        self.db.execute("DROP TRIGGER memory_fts_delete")
        self.db.execute("DROP TRIGGER memory_fts_update")
        self.db.execute("DROP TABLE memory_fts")
        self.db.execute("DROP TABLE memories")
        self.db.execute("CREATE TABLE memories(x TEXT)")
        self.export()
        with self.assertRaises(RecoveryError):
            inspect_recovery(self.path, PHRASE)


if __name__ == "__main__":
    unittest.main()
