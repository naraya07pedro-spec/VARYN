"""17S-22: manual official consumer app relay, no hidden provider sync."""
from dataclasses import replace
import unittest
from unittest.mock import patch

from varyn.official_manual_relay import (
    OFFICIAL_APP_LINKS, ManualRelayRejected, OfficialManualRelay,
)


class ManualConsumerRelayTests(unittest.TestCase):
    def setUp(self):
        self.now = [1000]
        self.relay = OfficialManualRelay(clock=lambda: self.now[0])

    def test_reviewed_packet_has_real_destination_but_no_sync_authority(self):
        for provider in OFFICIAL_APP_LINKS:
            with self.subTest(provider=provider):
                relay = OfficialManualRelay(clock=lambda: 1000)
                draft = relay.prepare(provider, "Review this synthetic task.")
                self.assertIn("USER-AUTHORED REQUEST:", draft.packet)
                self.assertIn("NOT synced account history", draft.packet)
                self.assertTrue(draft.destination_url.startswith("https://"))
                self.assertFalse(draft.automatic_sync)
                self.assertEqual(len(draft.digest), 64)
                self.assertFalse(relay.status()["automatic_sync"])
                self.assertEqual(relay.status()["provider_requests"], 0)
                self.assertEqual(relay.status()["local_files_read"], 0)

    def test_denial_does_not_mark_clipboard_or_remote_app(self):
        draft = self.relay.prepare("chatgpt", "Synthetic task")
        result = self.relay.decide(draft, approved=False)
        self.assertEqual(result["status"], "denied")
        self.assertFalse(self.relay.status()["awaiting_user_pasteback"])
        self.assertEqual(self.relay.status()["hops_used"], 0)
        with self.assertRaises(ManualRelayRejected):
            self.relay.decide(draft, approved=True, copied=True)

    def test_approved_clipboard_is_not_a_claim_of_paste_or_sync(self):
        draft = self.relay.prepare("gemini", "Compare this synthetic task")
        result = self.relay.decide(draft, approved=True, copied=True)
        self.assertEqual(result["status"], "copied_to_os_clipboard_not_pasted_to_app")
        self.assertFalse(result["official_account_access_verified"])
        self.assertTrue(self.relay.status()["awaiting_user_pasteback"])
        self.assertEqual(self.relay.status()["hops_used"], 1)
        with self.assertRaises(ManualRelayRejected):
            self.relay.decide(draft, approved=True, copied=True)

    def test_pasteback_user_claim_staged_and_quoted_on_next_hop(self):
        packet = self.relay.prepare("chatgpt", "Think about this fixture")
        self.relay.decide(packet, approved=True, copied=True)
        result = self.relay.record_pasted_reply(
            "UNVERIFIED answer from browser", reviewed=True)
        self.assertEqual(result["claimed_provider"], "chatgpt")
        self.assertFalse(result["origin_verified"])
        self.assertFalse(result["history_imported"])
        next_packet = self.relay.prepare("claude", "Critique the pasted answer")
        self.assertIn("claimed source: chatgpt", next_packet.packet)
        self.assertIn("UNVERIFIED answer from browser", next_packet.packet)
        self.assertIn("untrusted reference", next_packet.packet)
        self.assertNotIn("account authenticated", next_packet.packet)

    def test_unreviewed_reply_and_no_outbound_are_blocked(self):
        with self.assertRaises(ManualRelayRejected):
            self.relay.record_pasted_reply("Pretend data", reviewed=True)
        draft = self.relay.prepare("chatgpt", "Synthetic")
        self.relay.decide(draft, approved=True, copied=True)
        with self.assertRaises(ManualRelayRejected):
            self.relay.record_pasted_reply("Returned text", reviewed=False)
        self.assertTrue(self.relay.status()["awaiting_user_pasteback"])

    def test_stale_forged_and_tampered_previews_fail_closed(self):
        draft = self.relay.prepare("claude", "Synthetic fixture")
        tampered = replace(draft, digest="0"*64)
        with self.assertRaises(ManualRelayRejected):
            self.relay.decide(tampered, approved=True, copied=True)
        copied = replace(draft)
        with self.assertRaises(ManualRelayRejected):
            self.relay.decide(copied, approved=True, copied=True)
        self.assertEqual(self.relay.decide(
            draft, approved=False)["status"], "denied")

    def test_ttl_expiry_blocks_copy(self):
        draft = self.relay.prepare("chatgpt", "Synthetic")
        self.now[0] = draft.expires_at + 1
        with self.assertRaises(ManualRelayRejected):
            self.relay.decide(draft, approved=True, copied=True)
        self.assertFalse(self.relay.status()["awaiting_user_pasteback"])

    def test_wrong_target_and_invalid_input_refused(self):
        for target in ("", "openai", "ChatGPT", "gemini\n", None, 12, False):
            with self.subTest(target=target), self.assertRaises(ManualRelayRejected):
                self.relay.prepare(target, "Synthetic")
        for body in ("", " ", "\x00", "x"*1001, "\ud800"):
            with self.subTest(body=repr(body)), self.assertRaises(ManualRelayRejected):
                self.relay.prepare("chatgpt", body)

    def test_no_new_outgoing_while_return_unresolved(self):
        draft = self.relay.prepare("chatgpt", "Synthetic")
        with self.assertRaises(ManualRelayRejected):
            self.relay.prepare("claude", "Other")
        self.relay.decide(draft, approved=True, copied=True)
        with self.assertRaises(ManualRelayRejected):
            self.relay.prepare("claude", "Other")

    def test_declared_max_three_hops_then_reset(self):
        for p in ("chatgpt", "claude", "gemini"):
            draft = self.relay.prepare(p, "Synthetic task")
            self.relay.decide(draft, approved=True, copied=True)
            self.relay.record_pasted_reply("Synthetic reply", reviewed=True)
        self.assertEqual(self.relay.status()["hops_used"], 3)
        with self.assertRaises(ManualRelayRejected):
            self.relay.prepare("chatgpt", "Fourth")
        self.relay.reset()
        self.assertEqual(self.relay.status()["hops_used"], 0)
        self.assertFalse(self.relay.status()["reply_in_ram"])

    def test_pending_and_return_discarded_without_disk_persistence(self):
        draft = self.relay.prepare("gemini", "Synthetic")
        self.assertTrue(self.relay.discard_pending())
        with self.assertRaises(ManualRelayRejected):
            self.relay.decide(draft, approved=True, copied=True)
        new = self.relay.prepare("gemini", "Synthetic")
        self.relay.decide(new, approved=True, copied=True)
        self.relay.record_pasted_reply("Sensitive-looking but fake", reviewed=True)
        self.relay.reset()
        self.assertFalse(self.relay.status()["reply_in_ram"])
        self.assertFalse(self.relay.status()["awaiting_user_pasteback"])
        self.assertEqual(self.relay.status()["provider_requests"], 0)

    def test_bool_and_review_contracts(self):
        draft = self.relay.prepare("chatgpt", "Synthetic")
        for invalid in (1, "true", None):
            with self.subTest(invalid=invalid), self.assertRaises(ManualRelayRejected):
                self.relay.decide(draft, approved=invalid)
        with self.assertRaises(ManualRelayRejected):
            self.relay.decide(draft, approved=False, copied=True)
        self.assertEqual(self.relay.status()["hops_used"], 0)

    def test_provider_fetch_is_never_implicitly_called(self):
        with patch("varyn.multi_provider._post",
                   side_effect=AssertionError("No provider HTTP allowed")):
            draft = self.relay.prepare("chatgpt", "Synthetic")
            self.relay.decide(draft, approved=True, copied=True)
            self.relay.record_pasted_reply("Pasted by human", reviewed=True)
        self.assertEqual(self.relay.status()["provider_requests"], 0)


if __name__ == "__main__":
    unittest.main()
