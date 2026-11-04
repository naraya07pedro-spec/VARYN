"""Windows crash-recovery simulations for immutable DPAPI checkpoints."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from varyn.sealed_memory import SealedMemorySession


@unittest.skipUnless(os.name == "nt", "Requires native Windows DPAPI")
class CheckpointReliabilityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.dir = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def test_memory_auto_checkpoint_survives_abandoned_session(self):
        session = SealedMemorySession(checkpoint_dir=self.dir)
        try:
            session.add("VARYN", "storage automatic note")
            snapshot = session.last_checkpoint
            self.assertTrue(snapshot.is_file())
            self.assertFalse(session.has_unsaved_changes)
            self.assertNotIn(b"storage automatic note", snapshot.read_bytes())
            # Simulate app abandoning state after durable checkpoint.
            session.close()
            with SealedMemorySession(snapshot) as recovered:
                self.assertEqual(
                    recovered.search("automatic", "VARYN")[0]["content"],
                    "storage automatic note",
                )
        finally:
            session.close()

    def test_decision_checkpoint_preserves_revision_chain(self):
        with SealedMemorySession(checkpoint_dir=self.dir) as session:
            session.put_decision("VARYN", "path", "storage old", "fixture:old")
            first = session.last_checkpoint
            session.put_decision("VARYN", "path", "storage new", "fixture:new", 1)
            second = session.last_checkpoint
        self.assertNotEqual(first, second)
        self.assertEqual(len(list(self.dir.glob("*.varyn"))), 2)
        with SealedMemorySession(first) as recovered:
            self.assertEqual(recovered.current_decision("VARYN", "path")["revision"], 1)
        with SealedMemorySession(second) as recovered:
            self.assertEqual(recovered.current_decision("VARYN", "path")["revision"], 2)

    def test_failed_encrypted_publication_retains_previous_checkpoint(self):
        with SealedMemorySession(checkpoint_dir=self.dir) as session:
            session.add("VARYN", "storage first")
            good = session.last_checkpoint
            before = good.read_bytes()
            with patch("varyn.sealed_memory.write_sealed", side_effect=OSError("synthetic disk full")):
                with self.assertRaises(OSError):
                    session.add("VARYN", "storage second")
            self.assertTrue(session.has_unsaved_changes)
            self.assertEqual(session.last_checkpoint, good)
            self.assertEqual(good.read_bytes(), before)
            self.assertEqual(len(session.search("second", "VARYN")), 1)
            session.save_new(self.dir / "manual-recovery.varyn")
            self.assertFalse(session.has_unsaved_changes)

    def test_invalid_write_produces_no_checkpoint(self):
        with SealedMemorySession(checkpoint_dir=self.dir) as session:
            with self.assertRaises(ValueError):
                session.add("VARYN", "")
            self.assertIsNone(session.last_checkpoint)
            self.assertEqual(list(self.dir.iterdir()), [])

    def test_reopened_latest_checkpoint_can_continue(self):
        with SealedMemorySession(checkpoint_dir=self.dir) as session:
            session.add("VARYN", "storage original")
            path = session.last_checkpoint
        with SealedMemorySession(path, checkpoint_dir=self.dir) as session:
            session.add("VARYN", "storage continued")
            latest = session.last_checkpoint
        with SealedMemorySession(latest) as restored:
            self.assertEqual(len(restored.search("storage", "VARYN")), 2)

    def test_missing_checkpoint_directory_rejected(self):
        with self.assertRaises(ValueError):
            SealedMemorySession(checkpoint_dir=self.dir / "missing")


if __name__ == "__main__":
    unittest.main()
