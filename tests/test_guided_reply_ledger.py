"""17S-36 full local replies, claimed provenance and bounded excerpts only."""
import unittest
from varyn.guided_trio_flow import GuidedThreeAppFlow
from varyn.guided_reply_ledger import (
    GuidedReplyLedger, GuidedLedgerRejected, GuidedHistorySelection,
)
from varyn.official_manual_relay import OfficialManualRelay, ManualRelayRejected


def complete(relay, guided, provider, reply):
    prior = relay.status()
    task = guided.current_task
    selection = guided.history_selection() if guided.status()["stage"] > 1 else None
    preview = relay.prepare(provider, task, guided_history=selection)
    guided.require_copy(provider, prior, task)
    relay.decide(preview, approved=True, copied=True)
    guided.copied(prior, relay.status(), provider, task)
    before = relay.status()
    pending = relay.begin_return_review(reply)
    relay.finish_return_review(pending, approved=True)
    guided.reviewed_reply(before, relay.status(), reply_text=reply,
                          receipt=relay.last_return_receipt())
    return preview


class FullThreeReplyTests(unittest.TestCase):
    def setUp(self):
        self.relay = OfficialManualRelay(clock=lambda: 1000)
        self.flow = GuidedThreeAppFlow()

    def test_full_replies_in_ram_bounded_individual_source_excerpts_to_gemini(self):
        self.flow.start("SYNTHETIC: imaginary observatory schedule", self.relay.status())
        first = "SYNTHETIC: ChatGPT first full " + "A"*800
        second = "SYNTHETIC: Claude second full " + "B"*800
        third = "SYNTHETIC: Gemini third full"
        complete(self.relay, self.flow, "chatgpt", first)
        self.flow.prepare_next(self.relay.status())
        complete(self.relay, self.flow, "claude", second)
        self.flow.prepare_next(self.relay.status())
        gemini = complete(self.relay, self.flow, "gemini", third)
        self.assertIn("claimed source: chatgpt", gemini.packet)
        self.assertIn("claimed source: claude", gemini.packet)
        self.assertIn("TRUNCATED", gemini.packet)
        self.assertEqual(gemini.packet.count("UNTRUSTED USER-PASTED CONTENT:"), 2)
        self.assertNotIn(first, gemini.packet)
        self.assertNotIn(second, gemini.packet)
        self.assertEqual(self.flow.ledger.count, 3)
        full = self.flow.ledger.full_review_text()
        for reply in (first, second, third):
            self.assertIn(reply, full)
        self.assertFalse(self.flow.ledger.status()["provider_reply_origins_verified"])
        self.assertFalse(self.flow.ledger.status()["automatic_bidirectional_sync_verified"])
        self.assertEqual(self.flow.phase, "completed")
        self.flow.reset()
        self.assertEqual(self.flow.ledger.count, 0)
        with self.assertRaises(GuidedLedgerRejected):
            self.flow.ledger.full_review_text()

    def test_altered_review_text_and_wrong_claimed_provider_denied(self):
        self.flow.start("SYNTHETIC: fictional work", self.relay.status())
        prior = self.relay.status()
        p = self.relay.prepare("chatgpt", self.flow.current_task)
        self.relay.decide(p, approved=True, copied=True)
        self.flow.copied(prior, self.relay.status(), "chatgpt", self.flow.current_task)
        before = self.relay.status()
        pending = self.relay.begin_return_review("SYNTHETIC: original")
        self.relay.finish_return_review(pending, approved=True)
        receipt = self.relay.last_return_receipt()
        with self.assertRaises(GuidedLedgerRejected):
            self.flow.reviewed_reply(before, self.relay.status(),
                reply_text="SYNTHETIC: modified", receipt=receipt)
        with self.assertRaises(GuidedLedgerRejected):
            self.flow.reviewed_reply(before, self.relay.status(),
                reply_text="SYNTHETIC: original",
                receipt=dict(receipt, provider_claim="gemini"))
        self.assertEqual(self.flow.phase, "awaiting_reply")
        self.assertEqual(self.flow.ledger.count, 0)
        self.flow.reviewed_reply(before, self.relay.status(),
            reply_text="SYNTHETIC: original", receipt=receipt)
        self.assertEqual(self.flow.phase, "ready_next")

    def test_secret_or_non_synthetic_and_forged_history_fail_closed(self):
        receipt = {
            "provider_claim": "chatgpt", "manual_only": True,
            "provider_origin_verified": False,
            "outbound_request_id": "a"*32, "outbound_digest": "b"*64,
            "reply_digest": "c"*64, "local_chain_digest": "d"*64,
        }
        ledger = GuidedReplyLedger()
        for text in ("actual private text", "SYNTHETIC: password=longsecretvalue1234",
                     "SYNTHETIC: " + "X"*1600):
            with self.assertRaises(GuidedLedgerRejected):
                ledger.record(1, "chatgpt", text, receipt)
        self.assertEqual(ledger.count, 0)
        with self.assertRaises(GuidedLedgerRejected):
            ledger.record(2, "claude", "SYNTHETIC: wrong order", receipt)
        with self.assertRaises(GuidedLedgerRejected):
            GuidedHistorySelection(())
        with self.assertRaises(GuidedLedgerRejected):
            GuidedHistorySelection((object(),))
        with self.assertRaises(ManualRelayRejected):
            self.relay.prepare("claude", "SYNTHETIC: fixture",
                guided_history={"injected": "history"})


if __name__ == "__main__":
    unittest.main()
