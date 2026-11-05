"""17S-35 local guided three-app official relay; no authenticated consumer sync."""
import unittest

from varyn.guided_trio_flow import GuidedThreeAppFlow, GuidedTrioRejected
from varyn.official_manual_relay import OfficialManualRelay


def copied_and_reviewed(relay, guided, provider, answer):
    before = relay.status()
    task = guided.current_task
    guided.require_copy(provider, before, task)
    preview = relay.prepare(provider, task)
    relay.decide(preview, approved=True, copied=True)
    guided.copied(before, relay.status(), provider, task)
    before_reply = relay.status()
    guided.require_reply(before_reply)
    review = relay.begin_return_review(answer)
    relay.finish_return_review(review, approved=True)
    guided.reviewed_reply(
        before_reply, relay.status(), reply_text=answer,
        receipt=relay.last_return_receipt(),
    )


class GuidedTrioContractTests(unittest.TestCase):
    def setUp(self):
        self.flow = GuidedThreeAppFlow()
        self.relay = OfficialManualRelay(clock=lambda: 1000)

    def test_all_three_app_sequence_with_review_before_next_stage(self):
        root = "SYNTHETIC: design an imaginary library schedule"
        start = self.flow.start(root, self.relay.status())
        self.assertEqual(start, {"provider": "chatgpt", "task": root})
        self.assertEqual(self.flow.status()["stage"], 1)
        with self.assertRaises(GuidedTrioRejected):
            self.flow.prepare_next(self.relay.status())
        copied_and_reviewed(
            self.relay, self.flow, "chatgpt", "SYNTHETIC: sample draft"
        )
        self.assertEqual(self.flow.phase, "ready_next")
        second = self.flow.prepare_next(self.relay.status())
        self.assertEqual(second["provider"], "claude")
        self.assertIn("Critically review", second["task"])
        self.assertEqual(self.flow.status()["stage"], 2)
        second_preview = self.relay.prepare("claude", second["task"])
        self.assertIn("claimed source: chatgpt", second_preview.packet)
        self.relay.decide(second_preview, approved=True, copied=True)
        # second was copied outside GuidedThreeAppFlow; it must fail-closed
        with self.assertRaises(GuidedTrioRejected):
            self.flow.prepare_next(self.relay.status())
        self.flow.reset()
        self.assertFalse(self.flow.active)

    def test_three_stages_complete_with_each_copy_and_review(self):
        root = "SYNTHETIC: write a fictional task plan"
        self.flow.start(root, self.relay.status())
        for stage, provider in enumerate(("chatgpt", "claude", "gemini")):
            self.assertEqual(self.flow.provider, provider)
            self.assertEqual(self.flow.phase, "ready")
            before = self.relay.status()
            task = self.flow.current_task
            preview = self.relay.prepare(provider, task)
            self.relay.decide(preview, approved=True, copied=True)
            self.flow.copied(before, self.relay.status(), provider, task)
            self.assertEqual(self.flow.phase, "awaiting_reply")
            with self.assertRaises(GuidedTrioRejected):
                self.flow.prepare_next(self.relay.status())
            before_reply = self.relay.status()
            receipt = self.relay.begin_return_review(
                "SYNTHETIC: unverified response " + provider
            )
            self.relay.finish_return_review(receipt, approved=True)
            self.flow.reviewed_reply(
                before_reply, self.relay.status(),
                reply_text="SYNTHETIC: unverified response " + provider,
                receipt=self.relay.last_return_receipt(),
            )
            if stage < 2:
                upcoming = self.flow.prepare_next(self.relay.status())
                self.assertEqual(upcoming["provider"],
                                 ("chatgpt", "claude", "gemini")[stage+1])
                self.assertTrue(upcoming["task"].startswith("SYNTHETIC:"))
        self.assertEqual(self.flow.phase, "completed")
        self.assertEqual(self.flow.status()["stage"], 3)
        self.assertEqual(self.relay.status()["hops_used"], 3)
        self.assertEqual(self.flow.ledger.count, 3)
        self.assertFalse(self.flow.status()["browser_delivery_verified"])
        self.assertFalse(self.flow.status()["consumer_history_sync_verified"])
        self.assertEqual(self.flow.status()["provider_requests"], 0)

    def test_wrong_provider_or_bypassed_review_refused(self):
        self.flow.start("SYNTHETIC: sample", self.relay.status())
        with self.assertRaises(GuidedTrioRejected):
            self.flow.require_copy("gemini", self.relay.status(), self.flow.current_task)
        with self.assertRaises(GuidedTrioRejected):
            self.flow.require_copy("chatgpt", self.relay.status(), "SYNTHETIC: edited-in-the-middle")
        first = self.relay.prepare("chatgpt", "SYNTHETIC: sample")
        self.relay.decide(first, approved=True, copied=True)
        with self.assertRaises(GuidedTrioRejected):
            self.flow.require_reply(self.relay.status())
        with self.assertRaises(GuidedTrioRejected):
            self.flow.prepare_next(self.relay.status())

    def test_existing_relay_and_forged_status_rejected(self):
        before = self.relay.prepare("claude", "SYNTHETIC: preexisting")
        self.relay.decide(before, approved=True, copied=True)
        with self.assertRaises(GuidedTrioRejected):
            self.flow.start("SYNTHETIC: new", self.relay.status())
        for invalid in (None, {}, [], {"hops_used": True}):
            with self.subTest(invalid=invalid), self.assertRaises(GuidedTrioRejected):
                self.flow.start("SYNTHETIC: new", invalid)

    def test_non_synthetic_credential_or_oversize_refused(self):
        for task in (
            "real transcript without prefix",
            "SYNTHETIC: password=anexposedpassphrase1234",
            "SYNTHETIC: " + ("x"*650),
            "",
            None,
        ):
            with self.subTest(task=type(task).__name__), \
                 self.assertRaises(GuidedTrioRejected):
                self.flow.start(task, self.relay.status())
        self.assertFalse(self.flow.active)

if __name__ == '__main__':
    unittest.main()
