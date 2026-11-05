"""17S-18 offline host-approval and read-only fixture broker adversarial tests.

All owner approvals are SIMULATED by trusted test code and all fixtures
are newly created, disposable synthetic data. NO real user permissions.
"""
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from varyn.bounded_broker_protocol import BrokerRejected, canonical
from varyn.durable_broker_journal import DurableOneShotJournal
from varyn.parent_synthetic_read_broker import (
    ParentSyntheticReadBroker,
)


class SyntheticParentBrokerTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {
            "GITHUB_ACTIONS": "true",
            "VARYN_CI_APPCONTAINER_TRIAL": "1",
        })
        self.env.start()
        self.temp = TemporaryDirectory(prefix="varyn-17s18-parent-")
        self.root = Path(self.temp.name)
        self.file = self.root / "synthetic-parent-counts.json"
        self.file.write_bytes(b'{"counts":[4,6,11]}')
        self.journal = DurableOneShotJournal(
            str(self.root / "parent-journal.sqlite"))
        self.now = 1000
        self.broker = ParentSyntheticReadBroker(
            self.root, self.journal, clock=lambda: self.now)

    def tearDown(self):
        self.journal.close()
        self.temp.cleanup()
        self.env.stop()

    def grant(self):
        preview = self.broker.preview()
        self.assertFalse(preview.mutates)
        self.assertEqual(preview.expires_at, 1020)
        self.assertTrue(self.broker.owner_decide(
            preview.request_id, preview.digest, approved=True))
        return preview

    @staticmethod
    def response(request, *, total=21, nonce=None, decoy="verified_absent"):
        return canonical({
            "version": "varyn.anon-pipes.v1",
            "request_id": request["request_id"],
            "nonce": request["nonce"] if nonce is None else nonce,
            "status": "ok", "total": total, "decoy_status": decoy,
        })

    def test_unapproved_and_denied_requests_never_dispatch(self):
        with self.assertRaises(BrokerRejected):
            self.broker.claim_and_prepare()
        preview = self.broker.preview()
        with self.assertRaises(BrokerRejected):
            self.broker.owner_decide(preview.request_id, preview.digest,
                                     approved="true")
        self.assertFalse(self.broker.owner_decide(
            preview.request_id, preview.digest, approved=False))
        with self.assertRaises(BrokerRejected):
            self.broker.claim_and_prepare()
        self.assertIsNone(self.journal.status(preview.request_id))

    def test_forged_digest_wrong_id_and_double_preview_rejected(self):
        p = self.broker.preview()
        with self.assertRaises(BrokerRejected):
            self.broker.preview()
        with self.assertRaises(BrokerRejected):
            self.broker.owner_decide("f" * 32, p.digest, approved=True)
        with self.assertRaises(BrokerRejected):
            self.broker.owner_decide(p.request_id, "0" * 64, approved=True)
        self.assertIsNone(self.journal.status(p.request_id))
        self.assertTrue(self.broker.owner_decide(
            p.request_id, p.digest, approved=True))

    def test_real_synthetic_fixture_read_only_after_explicit_decision(self):
        with patch("varyn.parent_synthetic_read_broker.os.open",
                   side_effect=AssertionError("Read before owner approval")):
            p = self.broker.preview()
        self.broker.owner_decide(p.request_id, p.digest, approved=True)
        req = self.broker.claim_and_prepare()
        self.assertEqual(req["counts"], [4, 6, 11])
        self.assertEqual(
            set(req), {"version", "action", "request_id", "nonce", "counts"})
        self.assertNotIn(str(self.root), str(req))
        self.assertNotIn("synthetic-parent-counts.json", str(req))
        self.assertEqual(self.journal.status(p.request_id), "claimed")
        self.assertEqual(self.broker.complete(self.response(req)), 21)
        self.assertEqual(self.journal.status(p.request_id), "completed")
        with self.assertRaises(BrokerRejected):
            self.broker.complete(self.response(req))
        with self.assertRaises(BrokerRejected):
            self.broker.claim_and_prepare()
        with self.assertRaises(BrokerRejected):
            self.journal.claim(p.request_id)

    def test_crash_style_reopen_preserves_claim_and_blocks_replay(self):
        preview = self.grant()
        req = self.broker.claim_and_prepare()
        self.assertEqual(self.journal.status(req["request_id"]), "claimed")
        self.journal.close()
        self.journal = DurableOneShotJournal(
            str(self.root / "parent-journal.sqlite"))
        self.assertEqual(self.journal.status(preview.request_id), "claimed")
        with self.assertRaises(BrokerRejected):
            self.journal.claim(req["request_id"])

    def test_revoked_before_or_after_dispatch_stays_fail_closed(self):
        preview = self.grant()
        self.assertTrue(self.broker.revoke())
        with self.assertRaises(BrokerRejected):
            self.broker.claim_and_prepare()
        self.assertIsNone(self.journal.status(preview.request_id))
        self.assertFalse(self.broker.revoke())

        other = ParentSyntheticReadBroker(
            self.root, self.journal, clock=lambda: self.now)
        p2 = other.preview()
        other.owner_decide(p2.request_id, p2.digest, approved=True)
        req = other.claim_and_prepare()
        self.assertTrue(other.revoke())
        self.assertEqual(self.journal.status(p2.request_id), "failed")
        with self.assertRaises(BrokerRejected):
            other.complete(self.response(req))
        with self.assertRaises(BrokerRejected):
            self.journal.claim(req["request_id"])

    def test_changed_fixture_after_preview_revokes_once(self):
        p = self.grant()
        self.file.write_bytes(b'{"counts":[4,6,12]}')
        with self.assertRaises(BrokerRejected):
            self.broker.claim_and_prepare()
        self.assertEqual(self.broker.state, "consumed")
        self.assertIsNone(self.journal.status(p.request_id))

    def test_expiry_at_decision_and_before_dispatch(self):
        p = self.broker.preview()
        self.now = 1021
        with self.assertRaises(BrokerRejected):
            self.broker.owner_decide(p.request_id, p.digest, approved=True)
        self.assertIsNone(self.journal.status(p.request_id))

        other = ParentSyntheticReadBroker(
            self.root, self.journal, clock=lambda: self.now)
        p2 = other.preview()
        other.owner_decide(p2.request_id, p2.digest, approved=True)
        self.now = 1042
        with self.assertRaises(BrokerRejected):
            other.claim_and_prepare()
        self.assertIsNone(self.journal.status(p2.request_id))

    def test_malformed_duplicate_nonfinite_boolean_and_bounds_rejected(self):
        for payload in (
                b'{"counts":[1],"counts":[2]}',
                b'{"counts":[NaN]}',
                b'{"counts":[True]}',
                b'{"counts":[true]}',
                b'{"counts":[]}',
                b'{"counts":[10001]}',
                b'{"counts":[1],"action":"shell"}',
                b"x" * 513):
            with self.subTest(payload=payload[:20]):
                self.file.write_bytes(payload)
                new = ParentSyntheticReadBroker(
                    self.root, self.journal, clock=lambda: self.now)
                try:
                    p = new.preview()
                except BrokerRejected:  # >512-byte source can fail at preview.
                    continue
                new.owner_decide(p.request_id, p.digest, approved=True)
                with self.assertRaises(BrokerRejected):
                    new.claim_and_prepare()
                self.assertIsNone(self.journal.status(p.request_id))

    def test_forged_nonce_wrong_total_and_response_replay_denied(self):
        p = self.grant()
        req = self.broker.claim_and_prepare()
        with self.assertRaises(BrokerRejected):
            self.broker.complete(self.response(req, nonce="f" * 32))
        self.assertEqual(self.journal.status(p.request_id), "failed")
        with self.assertRaises(BrokerRejected):
            self.broker.complete(self.response(req))
        with self.assertRaises(BrokerRejected):
            self.journal.claim(p.request_id)

    def test_unsigned_child_extra_fields_and_bad_result_rejected(self):
        for bad in (
                lambda req: b'{"total":21}',
                lambda req: self.response(req, total=True),
                lambda req: self.response(req, total=22),
                lambda req: self.response(req, decoy="unrecognized"),
                lambda req: self.response(req) + b"x",
                lambda req: self.response(req)[:-1],
        ):
            new = ParentSyntheticReadBroker(
                self.root, self.journal, clock=lambda: self.now)
            p = new.preview()
            new.owner_decide(p.request_id, p.digest, approved=True)
            req = new.claim_and_prepare()
            with self.assertRaises(BrokerRejected):
                new.complete(bad(req))
            self.assertEqual(self.journal.status(p.request_id), "failed")

    def test_only_fixed_synthetic_filename_allowed(self):
        self.file.unlink()
        (self.root / "user-private.txt").write_text("test-only",
                                                      encoding="utf-8")
        with self.assertRaises(BrokerRejected):
            self.broker.preview()

    def test_symlink_fixture_rejected(self):
        replacement = self.root / "synthetic-other.json"
        replacement.write_bytes(b'{"counts":[4,6,11]}')
        self.file.unlink()
        try:
            self.file.symlink_to(replacement)
        except (OSError, NotImplementedError):
            self.skipTest("Windows symlink creation not permitted by runner")
        with self.assertRaises(BrokerRejected):
            self.broker.preview()

    def test_hardlinked_synthetic_fixture_is_refused(self):
        other = self.root / "second-name.json"
        try:
            os.link(self.file, other)
        except (OSError, NotImplementedError):
            self.skipTest("Fixture filesystem cannot create hardlinks")
        with self.assertRaises(BrokerRejected):
            self.broker.preview()
        self.assertIsNone(self.journal.status(self.broker.request_id))

    def test_mutation_during_open_read_is_refused_before_journal_claim(self):
        p = self.grant()
        original_read = os.read

        def mutating_read(fd, length):
            data = original_read(fd, length)
            # Mutate the same open file *after* content was obtained, so the
            # post-read fstat must detect the changed source identity.
            self.file.write_bytes(b'{"counts":[4,6,12]}')
            return data

        with patch("varyn.parent_synthetic_read_broker.os.read",
                   side_effect=mutating_read):
            with self.assertRaises(BrokerRejected):
                self.broker.claim_and_prepare()
        self.assertEqual(self.broker.state, "consumed")
        self.assertIsNone(self.journal.status(p.request_id))

    def test_non_ci_environment_cannot_construct_read_broker(self):
        with patch.dict(os.environ, {"GITHUB_ACTIONS": "false"}):
            with self.assertRaises(BrokerRejected):
                ParentSyntheticReadBroker(self.root, self.journal)
        with patch.dict(os.environ, {"VARYN_CI_APPCONTAINER_TRIAL": "0"}):
            with self.assertRaises(BrokerRejected):
                ParentSyntheticReadBroker(self.root, self.journal)


if __name__ == "__main__":
    unittest.main()
