"""17S-38: owner-selected old synthetic excerpt in a FRESH manual packet."""
from dataclasses import replace
import hashlib
import unittest

from varyn.archive_continuation import (
    ArchiveContinuationRejected, ArchivedExcerptSelection,
    CONTINUATION_TASK, select_excerpt, selection_review,
)
from varyn.guided_reply_ledger import GuidedReplyLedger
from varyn.official_manual_relay import OfficialManualRelay, ManualRelayRejected
from varyn.three_app_archive import snapshot, ArchiveRejected


def completed_archive(*, long_reply=False):
    ledger = GuidedReplyLedger()
    for stage, provider in enumerate(("chatgpt", "claude", "gemini"), 1):
        content = ("SYNTHETIC: imaginary historical " + provider +
                   (" " + "A" * 850 if long_reply and stage == 3 else ""))
        rid = format(stage, "032x")
        outbound = format(stage, "064x")
        digest = hashlib.sha256(
            (rid + "\n" + outbound + "\n" + content).encode()
        ).hexdigest()
        ledger.record(stage, provider, content, {
            "provider_claim": provider,
            "manual_only": True, "provider_origin_verified": False,
            "outbound_request_id": rid, "outbound_digest": outbound,
            "reply_digest": digest,
            "local_chain_digest": format(stage, "064x"),
        })
    return snapshot(ledger, phase="completed")


class ArchiveContinuationContracts(unittest.TestCase):
    def test_each_old_app_stage_selection_is_explicit_and_unverified(self):
        archive = completed_archive()
        for stage, provider in enumerate(("chatgpt", "claude", "gemini"), 1):
            with self.subTest(stage=stage):
                selected = select_excerpt(archive, stage=stage)
                self.assertIs(type(selected), ArchivedExcerptSelection)
                self.assertEqual(selected.stage, stage)
                self.assertEqual(selected.claimed_provider, provider)
                self.assertIn(provider, selected.excerpt)
                self.assertIn("UNTRUSTED DATA", selected.render())
                self.assertIn("NO", selection_review(selected).upper())
                self.assertFalse(selected.provider_origin_verified)
                self.assertFalse(selected.account_history_authenticated)
                self.assertFalse(selected.relay_authority_restored)
                self.assertFalse(selected.automatic_bidirectional_sync)
                self.assertEqual(len(selected.archive_digest), 64)

    def test_truncated_previous_reply_is_disclosed_and_not_full_replay(self):
        archive = completed_archive(long_reply=True)
        selected = select_excerpt(archive, stage=3)
        self.assertTrue(selected.truncated)
        self.assertEqual(len(selected.excerpt), 480)
        self.assertTrue(selected.full_characters > len(selected.excerpt))
        self.assertIn("TRUNCATED", selected.render())
        self.assertNotIn(archive["records"][2]["reply_text"], selected.render())
        self.assertIn("Proposed new local task", selection_review(selected))
        self.assertTrue(CONTINUATION_TASK.startswith("SYNTHETIC:"))

    def test_malformed_forged_and_authority_flags_refused(self):
        archive = completed_archive()
        for bad in (0, True, 4, 1.0, "3", None):
            with self.subTest(stage=bad), self.assertRaises(ArchiveContinuationRejected):
                select_excerpt(archive, stage=bad)
        selection = select_excerpt(archive, stage=3)
        for mutation in (
            {"stage": 1},
            {"claimed_provider": "chatgpt"},
            {"excerpt": "non synthetic text"},
            {"excerpt": selection.excerpt + " tampered"},
            {"truncated": True},
            {"archive_digest": "wrong"},
            {"local_reply_digest": "0" * 63},
            {"manual_only": False},
            {"provider_origin_verified": True},
            {"account_history_authenticated": True},
            {"relay_authority_restored": True},
            {"automatic_bidirectional_sync": True},
        ):
            with self.subTest(mutation=mutation), self.assertRaises(ArchiveContinuationRejected):
                replace(selection, **mutation)
        with self.assertRaises(ArchiveContinuationRejected):
            selection_review({"not": "an owner-selected context"})
        with self.assertRaises(ArchiveRejected):
            select_excerpt(dict(archive, automatic_sync=True), stage=3)

    def test_fresh_relay_requires_new_individual_clipboard_review(self):
        archived = select_excerpt(completed_archive(), stage=3)
        relay = OfficialManualRelay(clock=lambda: 1000)
        self.assertEqual(relay.status()["hops_used"], 0)
        preview = relay.prepare("chatgpt", CONTINUATION_TASK,
                                archived_excerpt=archived)
        self.assertIn("EXPLICITLY SELECTED READ-ONLY ARCHIVE", preview.packet)
        self.assertIn("claimed", preview.packet.lower())
        self.assertIn("imaginary historical gemini", preview.packet)
        self.assertFalse(preview.automatic_sync)
        self.assertEqual(relay.status()["hops_used"], 0)
        self.assertFalse(relay.status()["awaiting_user_pasteback"])
        relay.decide(preview, approved=False)
        self.assertEqual(relay.status()["hops_used"], 0)
        self.assertFalse(relay.status()["awaiting_user_pasteback"])
        second = relay.prepare("chatgpt", CONTINUATION_TASK,
                               archived_excerpt=archived)
        relay.decide(second, approved=True, copied=True)
        self.assertEqual(relay.status()["hops_used"], 1)
        self.assertTrue(relay.status()["awaiting_user_pasteback"])
        with self.assertRaises(ManualRelayRejected):
            relay.prepare("claude", CONTINUATION_TASK,
                          archived_excerpt=archived)
        bound = relay.begin_return_review("SYNTHETIC: new unverified reply")
        relay.finish_return_review(bound, approved=True)
        with self.assertRaises(ManualRelayRejected):
            relay.prepare("claude", CONTINUATION_TASK,
                          archived_excerpt=archived)
        relay.reset()
        self.assertEqual(relay.status()["hops_used"], 0)
        self.assertFalse(relay.status()["return_receipt_available"])

    def test_reject_untyped_selection_before_any_pending_copy(self):
        relay = OfficialManualRelay(clock=lambda: 1000)
        for bad in ({"fake": "context"}, "fake", None):
            if bad is None:
                preview = relay.prepare("claude", CONTINUATION_TASK)
                self.assertNotIn("ARCHIVE", preview.packet)
                relay.decide(preview, approved=False)
                continue
            with self.assertRaises(ManualRelayRejected):
                relay.prepare("claude", CONTINUATION_TASK,
                              archived_excerpt=bad)
            self.assertEqual(relay.status()["hops_used"], 0)
            self.assertFalse(relay.status()["awaiting_user_pasteback"])


if __name__ == "__main__":
    unittest.main()
