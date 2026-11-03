"""Headless approval dialog controller tests, no Tk or external provider."""
import json
import unittest

from varyn.agent_runtime import AgentRejected, BoundedAgent
from varyn.desktop_approval import DesktopApprovalController


class DesktopApprovalTests(unittest.TestCase):
    def test_approved_synthetic_note_executes_exactly_once(self):
        desk = DesktopApprovalController()
        p = desk.propose("stage_note", {"text": "synthetic fixture"})
        self.assertTrue(p.mutates)
        self.assertIn("synthetic fixture", p.summary)
        self.assertIn("in-memory", p.risk)
        outcome = desk.decide(p.proposal_id, p.digest, approved=True)
        self.assertEqual(outcome["status"], "completed")
        self.assertEqual(desk.status()["stored_synthetic_notes"], 1)
        with self.assertRaises(AgentRejected):
            desk.decide(p.proposal_id, p.digest, approved=True)

    def test_reject_does_not_change_notes_or_consume_step(self):
        desk = DesktopApprovalController()
        p = desk.propose("stage_note", {"text": "synthetic fixture"})
        outcome = desk.decide(p.proposal_id, p.digest, approved=False)
        self.assertEqual(outcome["status"], "rejected")
        self.assertEqual(desk.status()["stored_synthetic_notes"], 0)
        self.assertEqual(desk.status()["steps_used"], 0)

    def test_digest_mismatch_is_rejected_without_approval(self):
        desk = DesktopApprovalController()
        p = desk.propose("stage_note", {"text": "synthetic fixture"})
        with self.assertRaises(AgentRejected):
            desk.decide(p.proposal_id, "0" * 64, approved=True)
        self.assertEqual(desk.status()["pending_approvals"], 1)
        self.assertEqual(desk.status()["stored_synthetic_notes"], 0)

    def test_ids_cannot_be_cross_approved_even_for_same_tool(self):
        desk = DesktopApprovalController()
        one = desk.propose("stage_note", {"text": "first"})
        two = desk.propose("stage_note", {"text": "second"})
        with self.assertRaises(AgentRejected):
            desk.decide(one.proposal_id, two.digest, approved=True)
        desk.decide(two.proposal_id, two.digest, approved=False)
        desk.decide(one.proposal_id, one.digest, approved=True)
        self.assertEqual(desk.status()["stored_synthetic_notes"], 1)

    def test_nonboolean_decision_is_refused(self):
        desk = DesktopApprovalController()
        p = desk.propose("stage_note", {"text": "test"})
        for value in ("yes", 1, None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                desk.decide(p.proposal_id, p.digest, approved=value)
        self.assertEqual(desk.status()["stored_synthetic_notes"], 0)

    def test_unregistered_tools_remain_forbidden(self):
        desk = DesktopApprovalController()
        for name in ("shell", "filesystem_write", "http"):
            with self.assertRaises(AgentRejected):
                desk.propose(name, {})
        self.assertEqual(desk.status()["pending_approvals"], 0)

    def test_readonly_inspection_can_complete(self):
        desk = DesktopApprovalController()
        p = desk.propose("inspect_status", {})
        self.assertFalse(p.mutates)
        outcome = desk.decide(p.proposal_id, p.digest, approved=True)
        self.assertEqual(outcome["output"]["stored_synthetic_notes"], 0)
        self.assertEqual(desk.status()["steps_used"], 1)

    def test_pending_rejected_on_window_close(self):
        desk = DesktopApprovalController()
        a = desk.propose("stage_note", {"text": "alpha"})
        b = desk.propose("stage_note", {"text": "beta"})
        desk.reject_all_pending()
        self.assertEqual(desk.status()["pending_approvals"], 0)
        self.assertEqual(desk.status()["steps_used"], 0)
        for proposal in (a, b):
            with self.assertRaises(AgentRejected):
                desk.decide(proposal.proposal_id, proposal.digest, approved=True)

    def test_report_never_leaks_note_text_or_approval_token(self):
        desk = DesktopApprovalController()
        p = desk.propose("stage_note", {"text": "synthetic private test"})
        desk.decide(p.proposal_id, p.digest, approved=True)
        report = json.dumps(desk.status())
        self.assertNotIn("synthetic private test", report)
        self.assertNotIn(p.proposal_id, report)
        self.assertFalse(desk.status()["authenticated_identity"])
        self.assertFalse(desk.status()["live_actions"])

    def test_limiting_agent_still_enforces_approval_step_budget(self):
        desk = DesktopApprovalController(BoundedAgent(max_steps=1))
        p = desk.propose("stage_note", {"text": "test"})
        desk.decide(p.proposal_id, p.digest, approved=True)
        with self.assertRaises(RuntimeError):
            desk.propose("stage_note", {"text": "next"})

    def test_approval_after_rejection_does_not_replay(self):
        desk = DesktopApprovalController()
        p = desk.propose("stage_note", {"text": "fixture"})
        desk.decide(p.proposal_id, p.digest, approved=False)
        with self.assertRaises(AgentRejected):
            desk.decide(p.proposal_id, p.digest, approved=True)
        self.assertEqual(desk.status()["stored_synthetic_notes"], 0)


if __name__ == "__main__":
    unittest.main()
