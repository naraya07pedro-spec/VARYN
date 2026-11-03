"""Non-destructive encrypted checkpoint inventory tests."""
import json
import tempfile
import unittest
from pathlib import Path

from varyn.checkpoint_lifecycle import (
    CheckpointInventoryError, inventory_checkpoints, require_checkpoint_capacity,
)


class CheckpointLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.folder = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def add(self, num, contents=b"encrypted fixture"):
        path = self.folder / ("checkpoint-" + f"{num:032x}" + ".varyn")
        path.write_bytes(contents)
        return path

    def test_no_files_reports_zero_and_no_deletion(self):
        report = inventory_checkpoints(self.folder)
        self.assertEqual(report["checkpoint_count"], 0)
        self.assertEqual(report["total_ciphertext_bytes"], 0)
        self.assertFalse(report["automatic_delete_allowed"])
        self.assertFalse(report["eligible_for_unattended_pruning"])
        self.assertFalse(report["recovery_tested"])

    def test_exact_pattern_only_not_unrelated_files(self):
        self.add(1, b"x" * 20)
        (self.folder / "not-a-checkpoint.txt").write_text("secret")
        (self.folder / "checkpoint-invalid.varyn").write_bytes(b"x")
        report = inventory_checkpoints(self.folder)
        self.assertEqual(report["checkpoint_count"], 1)
        self.assertEqual(report["total_ciphertext_bytes"], 20)
        self.assertEqual(report["largest_checkpoint_bytes"], 20)

    def test_budget_and_count_alert_without_deleting(self):
        old = self.add(1, b"a" * 20)
        new = self.add(2, b"b" * 30)
        third = self.add(3, b"c" * 40)
        report = inventory_checkpoints(self.folder, keep_latest=2, max_bytes=60)
        self.assertTrue(report["over_count_target"])
        self.assertTrue(report["over_budget"])
        self.assertEqual(report["total_ciphertext_bytes"], 90)
        for entry in (old, new, third):
            self.assertTrue(entry.exists())

    def test_capacity_refuses_after_cap_without_removing(self):
        first, second = self.add(1), self.add(2)
        with self.assertRaises(CheckpointInventoryError):
            require_checkpoint_capacity(self.folder, max_checkpoints=2)
        self.assertTrue(first.exists())
        self.assertTrue(second.exists())

    def test_capacity_accepts_below_cap(self):
        self.add(1)
        require_checkpoint_capacity(self.folder, max_checkpoints=2)

    def test_invalid_limits_rejected(self):
        for kwargs in ({"keep_latest": True}, {"keep_latest": 1},
                       {"max_bytes": 0}, {"max_bytes": False}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                inventory_checkpoints(self.folder, **kwargs)
        for limit in (1, True, 10001):
            with self.subTest(limit=limit), self.assertRaises(ValueError):
                require_checkpoint_capacity(self.folder, max_checkpoints=limit)

    def test_missing_directory_rejected(self):
        with self.assertRaises(CheckpointInventoryError):
            inventory_checkpoints(self.folder / "missing")

    def test_symlink_managed_name_rejected(self):
        data = self.folder / "original.varyn"
        data.write_bytes(b"x")
        link = self.folder / ("checkpoint-" + "a" * 32 + ".varyn")
        try:
            link.symlink_to(data)
        except (NotImplementedError, OSError):
            self.skipTest("symlinks unavailable")
        with self.assertRaises(CheckpointInventoryError):
            inventory_checkpoints(self.folder)

    def test_report_contains_no_filenames_or_contents(self):
        self.add(1, b"unique fixture content")
        report = json.dumps(inventory_checkpoints(self.folder))
        self.assertNotIn("checkpoint-", report)
        self.assertNotIn("unique fixture content", report)
        self.assertNotIn(str(self.folder), report)


if __name__ == "__main__":
    unittest.main()
