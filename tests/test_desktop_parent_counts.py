"""17S-20 owner-facing parent-only synthetic consent contract.

Automated dialog decisions are mocked; a real human click is NOT attested.
No private files, model, network, or AppContainer subprocess.
"""
import os
from unittest.mock import patch
import unittest

from varyn.bounded_broker_protocol import BrokerRejected
from varyn.desktop_parent_counts import DesktopParentCountsAction
from varyn.parent_synthetic_read_broker import ParentSyntheticReadBroker


class DesktopParentCountsTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {
            "GITHUB_ACTIONS": "false",
            "VARYN_CI_APPCONTAINER_TRIAL": "0",
        })
        self.env.start()
        self.action = DesktopParentCountsAction()
        self.addCleanup(self.env.stop)
        self.addCleanup(self.action.close)

    def test_real_generated_source_only_after_approval_and_once(self):
        with patch("varyn.parent_synthetic_read_broker.os.read",
                   side_effect=AssertionError("read before approval")):
            preview = self.action.preview()
        self.assertFalse(preview.mutates)
        self.assertEqual(self.action.broker.state, "pending")
        result = self.action.decide_and_run(preview, approved=True)
        self.assertEqual(result["total"], 21)
        self.assertEqual(result["status"], "completed")
        self.assertFalse(result["os_sandbox"])
        self.assertFalse(result["external_upload"])
        self.assertEqual(
            self.action.journal.status(preview.request_id), "completed")
        with self.assertRaises(BrokerRejected):
            self.action.decide_and_run(preview, approved=True)
        with self.assertRaises(BrokerRejected):
            self.action.broker.claim_and_prepare()

    def test_refusal_never_opens_source_or_creates_claim(self):
        preview = self.action.preview()
        with patch("varyn.parent_synthetic_read_broker.os.open",
                   side_effect=AssertionError("unexpected read")):
            result = self.action.decide_and_run(preview, approved=False)
        self.assertEqual(result["status"], "rejected")
        self.assertIsNone(self.action.journal.status(preview.request_id))

    def test_wrong_digest_cannot_authorize_read(self):
        preview = self.action.preview()
        forged = type(preview)(preview.request_id, "0" * 64,
                               preview.description, preview.expires_at)
        with self.assertRaises(BrokerRejected):
            self.action.decide_and_run(forged, approved=True)
        self.assertIsNone(self.action.journal.status(preview.request_id))

    def test_changed_generated_file_after_preview_is_rejected(self):
        preview = self.action.preview()
        (self.action.fixture.root / "synthetic-parent-counts.json").write_bytes(
            b'{"counts":[4,6,12]}')
        with self.assertRaises(BrokerRejected):
            self.action.decide_and_run(preview, approved=True)
        self.assertIsNone(self.action.journal.status(preview.request_id))

    def test_expired_preview_blocks_approved_dispatch(self):
        self.action.close()
        now = [1000]
        self.action = DesktopParentCountsAction(clock=lambda: now[0])
        self.addCleanup(self.action.close)
        preview = self.action.preview()
        now[0] = 1021
        with self.assertRaises(BrokerRejected):
            self.action.decide_and_run(preview, approved=True)
        self.assertIsNone(self.action.journal.status(preview.request_id))

    def test_no_ci_opt_in_cannot_open_arbitrary_root(self):
        with self.assertRaises(BrokerRejected):
            ParentSyntheticReadBroker(
                self.action.fixture.root, self.action.journal)
        with self.assertRaises(BrokerRejected):
            ParentSyntheticReadBroker(
                self.action.fixture.root, self.action.journal,
                desktop_fixture=object())

    def test_desktop_mode_rejects_fake_appcontainer_reply(self):
        preview = self.action.preview()
        self.action.broker.owner_decide(
            preview.request_id, preview.digest, approved=True)
        self.action.broker.claim_and_prepare()
        with self.assertRaises(BrokerRejected):
            self.action.broker.complete(b'{"status":"ok"}')
        self.assertEqual(self.action.journal.status(preview.request_id), "claimed")
        self.assertEqual(self.action.broker.complete_local_synthetic(), 21)

    def test_close_burns_pending_and_deletes_disposable_fixture(self):
        preview = self.action.preview()
        root = self.action.fixture.root
        self.action.close()
        self.assertFalse(root.exists())
        with self.assertRaises(BrokerRejected):
            self.action.decide_and_run(preview, approved=True)


if __name__ == "__main__":
    unittest.main()
