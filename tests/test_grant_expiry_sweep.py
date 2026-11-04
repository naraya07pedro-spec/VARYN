"""17D: expired grant lifecycle tests using synthetic temporary folders only."""
import tempfile
import unittest
from pathlib import Path

from varyn.agent_runtime import AgentRejected
from varyn.file_grants import ScopedFileGrants


class ExpiredGrantSweepTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "sample.txt").write_text("synthetic", encoding="utf-8")
        self.now = [20.0]
        self.grants = ScopedFileGrants(clock=lambda: self.now[0])

    def grant(self, duration=2):
        return self.grants.grant(
            self.root, user_confirmed=True, duration_seconds=duration,
        )

    def test_status_closes_expired_handle_without_attempted_read(self):
        grant = self.grant()
        reader = self.grants._grants[grant.grant_id]["reader"]
        self.assertFalse(reader._closed)
        self.now[0] += 3
        state = self.grants.status()
        self.assertEqual(state["active"], 0)
        self.assertTrue(reader._closed)
        self.assertNotIn(grant.grant_id, self.grants._grants)
        self.assertIn(("expired", grant.grant_id[:8]), state["audit"])
        with self.assertRaises(AgentRejected):
            self.grants.read_text(grant.grant_id, "sample.txt")

    def test_new_grant_sweeps_other_stale_handles(self):
        first = self.grant()
        old_reader = self.grants._grants[first.grant_id]["reader"]
        self.now[0] += 3
        second = self.grant()
        self.assertTrue(old_reader._closed)
        self.assertEqual(self.grants.status()["active"], 1)
        self.assertNotEqual(first.grant_id, second.grant_id)
        self.grants.revoke_all()

    def test_revoke_sweeps_other_expired_grants(self):
        old = self.grant(duration=1)
        old_reader = self.grants._grants[old.grant_id]["reader"]
        still_live = self.grant(duration=20)
        self.now[0] += 2
        self.grants.revoke(still_live.grant_id)
        self.assertTrue(old_reader._closed)
        self.assertEqual(self.grants.status()["active"], 0)

    def test_status_before_expiry_preserves_valid_grant(self):
        grant = self.grant(duration=3)
        reader = self.grants._grants[grant.grant_id]["reader"]
        self.now[0] += 2
        self.assertEqual(self.grants.status()["active"], 1)
        self.assertFalse(reader._closed)
        self.assertEqual(
            self.grants.read_text(grant.grant_id, "sample.txt")["text"],
            "synthetic",
        )
        self.grants.revoke_all()

    def test_cleanup_audit_does_not_leak_path_or_contents(self):
        grant = self.grant()
        self.now[0] += 3
        log = repr(self.grants.status())
        self.assertNotIn(str(self.root), log)
        self.assertNotIn("sample.txt", log)
        self.assertNotIn("synthetic", log)
        self.assertNotIn(grant.grant_id, log)

    def test_revoke_expired_identifier_is_fail_closed(self):
        grant = self.grant()
        self.now[0] += 3
        with self.assertRaises(AgentRejected):
            self.grants.revoke(grant.grant_id)
        self.assertEqual(self.grants.status()["active"], 0)


if __name__ == "__main__":
    unittest.main()
