"""Checkpoint 16B grant lifecycle tests using synthetic folders only."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, Mock
from types import SimpleNamespace

from varyn.agent_runtime import AgentRejected
from varyn.file_grants import ScopedFileGrants
from varyn.scoped_files import ScopedLocalReader, _unsafe_windows_metadata


class GrantTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name)
        (self.folder / "safe.txt").write_text("synthetic", encoding="utf-8")
        self.time = 100.0
        self.grants = ScopedFileGrants(clock=lambda: self.time)

    def grant(self, **kwargs):
        return self.grants.grant(self.folder, user_confirmed=True, **kwargs)

    def test_explicit_consent_required(self):
        with self.assertRaises(PermissionError):
            self.grants.grant(self.folder)
        self.assertEqual(self.grants.status()["active"], 0)

    def test_valid_read_after_explicit_grant(self):
        g = self.grant()
        self.assertEqual(self.grants.read_text(g.grant_id, "safe.txt")["text"],
                         "synthetic")
        self.assertFalse(g.can_write)
        self.assertFalse(self.grants.status()["model_connected"])

    def test_revocation_blocks_read_and_listing(self):
        g = self.grant()
        self.grants.revoke(g.grant_id)
        with self.assertRaises(AgentRejected):
            self.grants.read_text(g.grant_id, "safe.txt")
        with self.assertRaises(AgentRejected):
            self.grants.list_files(g.grant_id)

    def test_expiration_is_fail_closed(self):
        g = self.grant(duration_seconds=2)
        self.time += 2
        with self.assertRaises(PermissionError):
            self.grants.read_text(g.grant_id, "safe.txt")
        self.assertEqual(self.grants.status()["active"], 0)

    def test_operation_cap_includes_failed_attempt(self):
        g = self.grant(max_operations=1)
        with self.assertRaises(AgentRejected):
            self.grants.read_text(g.grant_id, "../invalid.txt")
        with self.assertRaises(PermissionError):
            self.grants.read_text(g.grant_id, "safe.txt")

    def test_read_and_listing_share_quota(self):
        g = self.grant(max_operations=2)
        self.grants.list_files(g.grant_id)
        self.grants.read_text(g.grant_id, "safe.txt")
        with self.assertRaises(PermissionError):
            self.grants.list_files(g.grant_id)

    def test_unknown_or_forged_grant_rejected(self):
        with self.assertRaises(AgentRejected):
            self.grants.read_text("fake", "safe.txt")
        g = self.grant()
        with self.assertRaises(AgentRejected):
            self.grants.read_text(g.grant_id + "x", "safe.txt")

    def test_grant_cannot_expand_scope(self):
        g = self.grant()
        outside = self.folder.parent / ("outside_" + self.folder.name + ".txt")
        outside.write_text("outside", encoding="utf-8")
        self.addCleanup(lambda: outside.unlink(missing_ok=True))
        with self.assertRaises(AgentRejected):
            self.grants.read_text(g.grant_id, outside.as_posix())

    def test_audit_does_not_log_content_or_path(self):
        g = self.grant()
        self.grants.read_text(g.grant_id, "safe.txt")
        report = repr(self.grants.status())
        self.assertNotIn("synthetic", report)
        self.assertNotIn(str(self.folder), report)
        self.assertNotIn(g.grant_id, report)
        self.assertFalse(self.grants.status()["file_contents_logged"])

    def test_revoke_all(self):
        g1, g2 = self.grant(), self.grant()
        self.grants.revoke_all()
        for g in (g1, g2):
            with self.assertRaises(AgentRejected):
                self.grants.read_text(g.grant_id, "safe.txt")

    def test_limits_and_bad_consent(self):
        for kwargs in ({"duration_seconds": 0}, {"duration_seconds": 3601},
                       {"max_operations": 0}, {"max_operations": True},
                       {"max_bytes": 12}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                self.grant(**kwargs)
        with self.assertRaises(PermissionError):
            self.grants.grant(self.folder, user_confirmed=1)

    def test_failed_scope_creation_does_not_create_grant(self):
        with self.assertRaises(ValueError):
            self.grants.grant(self.folder / "missing", user_confirmed=True)
        self.assertEqual(self.grants.status()["active"], 0)

    def test_reserved_windows_device_names_rejected(self):
        grant = self.grant(max_operations=10)
        for name in ("CON.txt", "nul.md", "COM1.txt", "LPT9.md"):
            with self.subTest(name=name), self.assertRaises(AgentRejected):
                self.grants.read_text(grant.grant_id, name)

    def test_windows_reparse_metadata_deny(self):
        fake = SimpleNamespace(st_file_attributes=0x400, st_nlink=1)
        with patch("varyn.scoped_files.os.name", "nt"):
            self.assertTrue(_unsafe_windows_metadata(fake))

    def test_windows_hardlink_metadata_deny(self):
        fake = SimpleNamespace(st_file_attributes=0, st_nlink=2)
        with patch("varyn.scoped_files.os.name", "nt"):
            self.assertTrue(_unsafe_windows_metadata(fake))

    def test_non_windows_metadata_unchanged(self):
        fake = SimpleNamespace(st_file_attributes=0x400, st_nlink=2)
        with patch("varyn.scoped_files.os.name", "posix"):
            self.assertFalse(_unsafe_windows_metadata(fake))


if __name__ == "__main__":
    unittest.main()
