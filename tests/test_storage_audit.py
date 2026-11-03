"""Audit must not claim readiness or expose local filesystem information."""
import json
import os
import stat
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from varyn.storage_audit import audit_storage


class StorageAuditTests(unittest.TestCase):
    def setUp(self):
        self.work = tempfile.TemporaryDirectory()
        self.path = Path(self.work.name) / "synthetic.sqlite3"
        self.path.write_bytes(b"synthetic only")

    def tearDown(self):
        self.work.cleanup()

    def test_existing_file_is_never_approved(self):
        result = audit_storage(self.path)
        self.assertEqual(result["status"], "blocked")
        self.assertFalse(result["ready_for_sensitive_data"])
        self.assertIn("database_not_encrypted", result["checks"])
        self.assertIn("owner_label_not_authenticated", result["checks"])

    def test_missing_file_rejected(self):
        result = audit_storage(self.path.parent / "missing.sqlite3")
        self.assertEqual(result["status"], "rejected")
        self.assertIn("missing_path", result["checks"])

    def test_directory_rejected(self):
        result = audit_storage(self.path.parent)
        self.assertIn("not_regular_file", result["checks"])

    def test_symlink_rejected(self):
        link = self.path.parent / "shortcut.sqlite3"
        try:
            link.symlink_to(self.path)
        except (OSError, NotImplementedError):
            self.skipTest("symlink creation forbidden by host policy")
        result = audit_storage(link)
        self.assertEqual(result["status"], "rejected")
        self.assertIn("symlink_path_rejected", result["checks"])

    def test_report_does_not_include_path_or_contents(self):
        raw = json.dumps(audit_storage(self.path))
        self.assertNotIn(self.path.name, raw)
        self.assertNotIn(str(self.path.parent), raw)
        self.assertNotIn("synthetic only", raw)

    @unittest.skipIf(os.name == "nt", "POSIX permission mode only")
    def test_posix_world_readable_is_flagged(self):
        self.path.chmod(0o644)
        self.assertIn("group_or_other_permissions", audit_storage(self.path)["checks"])

    @unittest.skipIf(os.name == "nt", "POSIX permission mode only")
    def test_posix_owner_only_still_not_ready(self):
        self.path.chmod(0o600)
        report = audit_storage(self.path)
        self.assertIn("posix_mode_owner_only", report["checks"])
        self.assertFalse(report["ready_for_sensitive_data"])

    def test_windows_acl_is_not_inferred_from_posix_bits(self):
        with patch("varyn.storage_audit.os.name", "nt"):
            # Pure read-only reporting behavior, independent of Windows privileges.
            report = audit_storage(self.path)
        self.assertIn("windows_acl_not_inspected", report["checks"])
        self.assertFalse(report["ready_for_sensitive_data"])


if __name__ == "__main__":
    unittest.main()
