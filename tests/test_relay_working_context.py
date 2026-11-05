"""17S-25: project-scoped, owner-reviewed RAM context; never trusted memory."""
from dataclasses import replace
import unittest
from varyn.relay_working_context import (
    WorkingContextBoard, WorkingContextRejected, WorkingContextSelection,
)
from varyn.official_manual_relay import OfficialManualRelay, ManualRelayRejected


class WorkingContextBoardTests(unittest.TestCase):
    def setUp(self):
        self.time = [1000]
        self.board = WorkingContextBoard(clock=lambda: self.time[0])

    def _save(self, project="VARYN", topic="next_step",
              note="SYNTHETIC: test scoped note", source=None):
        p = self.board.propose(project, topic, note, source_receipt=source)
        return self.board.decide(p, approved=True, source_receipt=source)

    def test_reviewed_note_never_becomes_verified_or_persistent_memory(self):
        self.assertEqual(self._save()["status"], "added")
        snapshot = self.board.selection("VARYN")
        self.assertIs(type(snapshot), WorkingContextSelection)
        self.assertFalse(snapshot.source_verified)
        self.assertFalse(snapshot.notes[0].source_verified)
        self.assertEqual(snapshot.notes[0].revision, 1)
        self.assertFalse(self.board.status()["persistent"])
        self.assertEqual(self.board.status()["network_requests"], 0)
        self.assertIn("not verified facts", snapshot.render())
        self.assertIn("owner_written", snapshot.render())

    def test_denial_is_non_mutating_and_burns_review(self):
        p = self.board.propose("VARYN", "topic", "SYNTHETIC: not saved")
        self.assertEqual(
            self.board.decide(p, approved=False)["status"], "declined")
        self.assertEqual(self.board.status()["saved_count"], 0)
        with self.assertRaises(WorkingContextRejected):
            self.board.decide(p, approved=True)

    def test_duplicate_does_not_create_second_revision(self):
        self._save()
        p = self.board.propose("VARYN", "next_step",
                               "SYNTHETIC: test scoped note")
        self.assertFalse(p.conflict)
        self.assertEqual(self.board.decide(p, approved=True)["status"], "duplicate")
        self.assertEqual(self.board.selection("VARYN").notes[0].revision, 1)

    def test_conflict_requires_explicit_approval_and_version_increment(self):
        self._save()
        newer = self.board.propose("VARYN", "next_step",
                                    "SYNTHETIC: changed owner interpretation")
        self.assertTrue(newer.conflict)
        self.assertIn("test scoped", newer.previous_note.text)
        with self.assertRaises(WorkingContextRejected):
            self.board.decide(newer, approved=True, allow_replace=False)
        self.assertIn("test scoped", self.board.selection("VARYN").render())
        newer = self.board.propose("VARYN", "next_step",
                                    "SYNTHETIC: changed owner interpretation")
        result = self.board.decide(newer, approved=True, allow_replace=True)
        self.assertEqual(result["status"], "replaced")
        self.assertEqual(result["revision"], 2)
        self.assertNotIn("test scoped", self.board.selection("VARYN").render())
        self.assertIn("changed owner", self.board.selection("VARYN").render())

    def test_no_silent_cross_project_context_leak(self):
        self._save(project="VARYN", topic="a")
        self._save(project="OTHER", topic="b",
                   note="SYNTHETIC: unrelated project")
        one = self.board.selection("VARYN")
        self.assertNotIn("unrelated project", one.render())
        self.assertEqual(one.project, "VARYN")
        self.assertNotIn("test scoped", self.board.selection("OTHER").render())

    def test_stale_tampered_preview_denied_and_expires(self):
        p = self.board.propose("VARYN", "topic", "SYNTHETIC: one")
        for value in (replace(p), replace(p, digest="0"*64),
                      replace(p, text="SYNTHETIC: switched")):
            with self.assertRaises(WorkingContextRejected):
                self.board.decide(value, approved=True)
        self.time[0] = p.expires_at + 1
        with self.assertRaises(WorkingContextRejected):
            self.board.decide(p, approved=True)
        self.assertEqual(self.board.status()["saved_count"], 0)

    def test_nested_reset_blocks_stale_approved_modal(self):
        p = self.board.propose("VARYN", "topic", "SYNTHETIC: original")
        self.board.reset()
        with self.assertRaises(WorkingContextRejected):
            self.board.decide(p, approved=True)
        self.assertEqual(self.board.status()["saved_count"], 0)

    def test_local_receipt_is_unverified_and_requires_current_binding(self):
        receipt = {
            "provider_origin_verified": False, "manual_only": True,
            "outbound_request_id": "1"*32, "reply_digest": "a"*64,
        }
        p = self.board.propose(
            "VARYN", "topic", "SYNTHETIC: hypothesis from pasted answer",
            source_receipt=receipt,
        )
        with self.assertRaises(WorkingContextRejected):
            self.board.decide(p, approved=True, source_receipt=None)
        p = self.board.propose(
            "VARYN", "topic", "SYNTHETIC: hypothesis from pasted answer",
            source_receipt=receipt,
        )
        self.board.decide(p, approved=True, source_receipt=receipt)
        rendered = self.board.selection("VARYN").render()
        self.assertIn("user_pasted_claim_unverified", rendered)
        self.assertNotIn("verified_by_provider", rendered)

    def test_fake_verified_provider_receipt_rejected(self):
        receipt = {
            "provider_origin_verified": True, "manual_only": True,
            "outbound_request_id": "1"*32, "reply_digest": "a"*64,
        }
        with self.assertRaises(WorkingContextRejected):
            self.board.propose(
                "VARYN", "topic", "SYNTHETIC: note", source_receipt=receipt)

    def test_many_scopes_and_size_bounds_fail_closed(self):
        for project, topic, note in (
            ("../VARYN", "topic", "SYNTHETIC: ok"),
            ("VARYN", "x/y", "SYNTHETIC: ok"),
            ("VARYN", "topic", "secret with no synthetic prefix"),
            ("VARYN", "topic", "SYNTHETIC: " + "x"*330),
            ("VARYN", "topic", "SYNTHETIC: \uD800"),
            ("VARYN", "topic", "SYNTHETIC: \x00"),
        ):
            with self.subTest(project=project, topic=topic), self.assertRaises(
                    WorkingContextRejected):
                self.board.propose(project, topic, note)

    def test_select_at_most_three_owner_notes_and_limit_eight_total(self):
        for i in range(4):
            self._save(topic="t"+str(i), note="SYNTHETIC: item "+str(i))
        with self.assertRaises(WorkingContextRejected):
            self.board.selection("VARYN")
        for i in range(4, 8):
            self._save(project="OTHER", topic="t"+str(i),
                       note="SYNTHETIC: item "+str(i))
        with self.assertRaises(WorkingContextRejected):
            self.board.propose("OTHER", "ninth", "SYNTHETIC: overflow")
        self.board.reset()
        self.assertEqual(self.board.status()["saved_count"], 0)

    def test_relay_requires_explicit_valid_selection_and_exact_preview(self):
        self._save()
        relay = OfficialManualRelay(clock=lambda: 1000)
        without = relay.prepare("claude", "SYNTHETIC: work")
        self.assertNotIn("TEMPORARY PROJECT NOTES", without.packet)
        relay.decide(without, approved=False)
        selected = self.board.selection("VARYN")
        preview = relay.prepare(
            "claude", "SYNTHETIC: work", reviewed_context=selected)
        self.assertIn("HUMAN-REVIEWED TEMPORARY PROJECT NOTES", preview.packet)
        self.assertIn("SYNTHETIC: test scoped note", preview.packet)
        relay.decide(preview, approved=False)
        for wrong in ("SYNTHETIC: arbitrary trusted", {}, []):
            with self.assertRaises(ManualRelayRejected):
                relay.prepare("claude", "SYNTHETIC: work",
                              reviewed_context=wrong)
        self.assertEqual(relay.status()["provider_requests"], 0)


if __name__ == "__main__":
    unittest.main()
