"""Windows-specific checkpoint cap: reject mutation before RAM write."""
import os
import tempfile
import unittest
from pathlib import Path

from varyn.checkpoint_lifecycle import CheckpointInventoryError
from varyn.sealed_memory import SealedMemorySession


@unittest.skipUnless(os.name == "nt", "Windows DPAPI required")
class CheckpointCapIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.folder = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def test_cap_stops_mutation_and_preserves_prior_snapshots(self):
        with SealedMemorySession(checkpoint_dir=self.folder, max_checkpoints=2) as session:
            session.add("VARYN", "storage first")
            session.add("VARYN", "storage second")
            previous = {p.name: p.read_bytes() for p in self.folder.iterdir()}
            with self.assertRaises(CheckpointInventoryError):
                session.add("VARYN", "storage third")
            self.assertEqual(len(session.search("storage", "VARYN")), 2)
            self.assertFalse(session.has_unsaved_changes)
            self.assertEqual(
                {p.name: p.read_bytes() for p in self.folder.iterdir()}, previous
            )

    def test_cap_stops_decision_revision_before_write(self):
        with SealedMemorySession(checkpoint_dir=self.folder, max_checkpoints=2) as session:
            session.put_decision("VARYN", "path", "storage first", "fixture:one")
            session.put_decision("VARYN", "path", "storage second", "fixture:two", 1)
            with self.assertRaises(CheckpointInventoryError):
                session.put_decision("VARYN", "path", "storage third", "fixture:three", 2)
            self.assertEqual(session.current_decision("VARYN", "path")["revision"], 2)


if __name__ == "__main__":
    unittest.main()
