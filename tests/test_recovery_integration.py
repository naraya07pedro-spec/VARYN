"""Windows recovery integration tests (synthetic, never actual passwords)."""
import os
import tempfile
import unittest
from pathlib import Path

from varyn.recovery import RecoveryError
from varyn.sealed_memory import SealedMemorySession

PHRASE = "synthetic recovery phrase for VARYN testing 2026"


@unittest.skipUnless(os.name == "nt", "Requires Windows DPAPI profile")
class RecoveryIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.folder = Path(self.temp.name)
        self.export = self.folder / "portable.varyn-recovery"
        self.dpapi = self.folder / "restored.varyn"

    def tearDown(self):
        self.temp.cleanup()

    def test_recovery_reopens_memory_decision_and_search(self):
        with SealedMemorySession() as session:
            session.add("VARYN", "storage note synthetic")
            session.put_decision("VARYN", "storage", "storage on D", "fixture:verified")
            session.export_recovery(self.export, PHRASE)
        encrypted = self.export.read_bytes()
        for text in (b"storage note synthetic", b"storage on D", b"SQLite format 3"):
            self.assertNotIn(text, encrypted)
        with SealedMemorySession(
            recovery_source=self.export, recovery_passphrase=PHRASE,
        ) as recovered:
            self.assertEqual(recovered.search("storage", "VARYN")[0]["content"], "storage note synthetic")
            self.assertEqual(recovered.current_decision("VARYN", "storage")["revision"], 1)
            self.assertEqual(len(recovered.context("VARYN", "storage")["items"]), 2)
            recovered.save_new(self.dpapi)
        with SealedMemorySession(self.dpapi) as regular:
            self.assertEqual(regular.current_decision("VARYN", "storage")["content"], "storage on D")

    def test_wrong_phrase_does_not_publish_dpapi_file(self):
        with SealedMemorySession() as session:
            session.add("VARYN", "storage note")
            session.export_recovery(self.export, PHRASE)
        with self.assertRaises(RecoveryError):
            SealedMemorySession(
                recovery_source=self.export,
                recovery_passphrase="wrong but lengthy recovery phrase",
            )
        self.assertFalse(self.dpapi.exists())

    def test_rejects_conflicting_sources_and_missing_phrase(self):
        with self.assertRaises(ValueError):
            SealedMemorySession(source="one", recovery_source="two", recovery_passphrase=PHRASE)
        with self.assertRaises(ValueError):
            SealedMemorySession(recovery_source="two")


if __name__ == "__main__":
    unittest.main()
