"""17S-24: exact outbound->return receipt binding, user-pasted provenance NOT verified."""
from dataclasses import replace
import hashlib
import unittest
from unittest.mock import patch

from varyn.official_manual_relay import (
    ManualRelayRejected, OfficialManualRelay, ManualReturnPreview,
)


class BoundReturnReviewTests(unittest.TestCase):
    def setUp(self):
        self.t = [1000]
        self.relay = OfficialManualRelay(clock=lambda: self.t[0])
        self.sent = self.relay.prepare("chatgpt", "SYNTHETIC: test context")
        self.relay.decide(self.sent, approved=True, copied=True)

    def test_exact_review_receipt_survives_only_one_acceptance(self):
        preview = self.relay.begin_return_review("SYNTHETIC: sample answer")
        self.assertIs(type(preview), ManualReturnPreview)
        self.assertEqual(preview.outbound_request_id, self.sent.request_id)
        self.assertEqual(preview.outbound_digest, self.sent.digest)
        self.assertEqual(preview.provider, "chatgpt")
        self.assertFalse(preview.origin_verified)
        self.assertTrue(self.relay.status()["return_review_pending"])
        accepted = self.relay.finish_return_review(preview, approved=True)
        receipt = accepted["return_receipt"]
        self.assertFalse(receipt["provider_origin_verified"])
        self.assertEqual(receipt["outbound_request_id"], self.sent.request_id)
        self.assertEqual(receipt["outbound_digest"], self.sent.digest)
        self.assertEqual(receipt["reply_digest"], preview.reply_digest)
        self.assertEqual(
            self.relay.last_return_receipt()["local_chain_digest"],
            hashlib.sha256(
                ("0"*64 + "\n" + self.sent.digest + "\n" +
                 preview.reply_digest).encode("ascii")
            ).hexdigest(),
        )
        self.assertNotIn("sample answer", str(self.relay.status()))
        self.assertNotIn("sample answer", str(receipt))
        self.assertTrue(self.relay.status()["reply_in_ram"])
        self.assertFalse(self.relay.status()["return_review_pending"])
        with self.assertRaises(ManualRelayRejected):
            self.relay.finish_return_review(preview, approved=True)

    def test_review_denial_allows_correct_fresh_review(self):
        initial = self.relay.begin_return_review("UNVERIFIED: wrong")
        refused = self.relay.finish_return_review(initial, approved=False)
        self.assertEqual(refused["status"], "return_declined")
        self.assertFalse(self.relay.status()["reply_in_ram"])
        self.assertTrue(self.relay.status()["awaiting_user_pasteback"])
        newer = self.relay.begin_return_review("SYNTHETIC: correct")
        self.assertNotEqual(newer.reply_digest, initial.reply_digest)
        self.relay.finish_return_review(newer, approved=True)
        self.assertTrue(self.relay.status()["return_receipt_available"])

    def test_tampered_copied_or_stale_preview_rejected(self):
        original = self.relay.begin_return_review("SYNTHETIC: normal")
        for changed in (
            replace(original, provider="gemini"),
            replace(original, outbound_request_id="forged"),
            replace(original, reply_digest="0"*64),
            replace(original, reply_text="malicious switch"),
            replace(original),
        ):
            with self.subTest(changed=changed), self.assertRaises(ManualRelayRejected):
                self.relay.finish_return_review(changed, approved=True)
        self.assertTrue(self.relay.status()["return_review_pending"])
        self.relay.finish_return_review(original, approved=False)

    def test_nested_discard_before_return_modal_closes_denies(self):
        pending = self.relay.begin_return_review("SYNTHETIC: stale")
        self.relay.discard_pending()
        with self.assertRaises(ManualRelayRejected):
            self.relay.finish_return_review(pending, approved=True)
        self.assertFalse(self.relay.status()["reply_in_ram"])
        self.assertIsNone(self.relay.last_return_receipt())

    def test_expiry_blocks_stale_return_and_burns_one_shot(self):
        pending = self.relay.begin_return_review("SYNTHETIC: expired")
        self.t[0] = pending.expires_at + 1
        with self.assertRaises(ManualRelayRejected):
            self.relay.finish_return_review(pending, approved=True)
        self.assertFalse(self.relay.status()["reply_in_ram"])
        self.assertFalse(self.relay.status()["return_review_pending"])
        self.assertTrue(self.relay.status()["awaiting_user_pasteback"])

    def test_legacy_unbound_accept_blocked_while_exact_modal_pending(self):
        pending = self.relay.begin_return_review("SYNTHETIC: bound")
        with self.assertRaises(ManualRelayRejected):
            self.relay.record_pasted_reply("SYNTHETIC: bypass", reviewed=True)
        self.relay.finish_return_review(pending, approved=True)

    def test_only_one_modal_and_boolean_owner_review(self):
        pending = self.relay.begin_return_review("SYNTHETIC: one")
        with self.assertRaises(ManualRelayRejected):
            self.relay.begin_return_review("SYNTHETIC: second")
        for bad in ("yes", 1, None):
            with self.subTest(value=bad), self.assertRaises(ManualRelayRejected):
                self.relay.finish_return_review(pending, approved=bad)
        self.assertTrue(self.relay.status()["return_review_pending"])
        self.relay.finish_return_review(pending, approved=False)

    def test_outbound_receipt_is_embedded_only_in_explicit_next_packet(self):
        initial = self.relay.begin_return_review("SYNTHETIC: claimed reply")
        self.relay.finish_return_review(initial, approved=True)
        with patch("varyn.multi_provider._post",
                   side_effect=AssertionError("No hidden provider HTTP")):
            nxt = self.relay.prepare("claude", "Critique prior unverified answer")
        self.assertIn("LOCAL OWNER-REVIEWED RETURN RECEIPT", nxt.packet)
        self.assertIn(self.sent.request_id, nxt.packet)
        self.assertIn("NOT authenticated", nxt.packet)
        self.assertIn("claimed reply", nxt.packet)
        self.assertFalse(self.relay.status()["automatic_sync"])
        self.assertEqual(self.relay.status()["provider_requests"], 0)
        self.relay.decide(nxt, approved=False)
        self.relay.reset()
        self.assertIsNone(self.relay.last_return_receipt())
        self.assertFalse(self.relay.status()["reply_in_ram"])

    def test_direct_legacy_record_cannot_be_mistaken_for_verified_receipt(self):
        result = self.relay.record_pasted_reply("SYNTHETIC: legacy", reviewed=True)
        self.assertFalse(result["origin_verified"])
        self.assertIsNone(self.relay.last_return_receipt())
        self.assertFalse(self.relay.status()["return_receipt_available"])

    def test_unpaired_unicode_or_large_return_is_not_reviewable(self):
        for text in ("", " ", "\x00", "\ud800", "x"*1601):
            with self.subTest(text=repr(text)), self.assertRaises(ManualRelayRejected):
                self.relay.begin_return_review(text)
        self.assertFalse(self.relay.status()["return_review_pending"])


if __name__ == "__main__":
    unittest.main()
