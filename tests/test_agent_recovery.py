"""14D synthetic restart/crash tests; metadata only and no automatic replay."""
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from varyn.agent_recovery import AgentRecoveryJournal, RecoveryConflict
from varyn.desktop_approval import DesktopApprovalController
from varyn.agent_runtime import AgentRejected


class AgentRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "agent_recovery.sqlite3"

    def test_approved_action_records_completed_and_survives_restart(self):
        with AgentRecoveryJournal(self.path) as journal:
            desktop = DesktopApprovalController(journal=journal)
            p = desktop.propose("stage_note", {"text": "synthetic only"})
            result = desktop.decide(p.proposal_id, p.digest, approved=True)
            self.assertEqual(result["status"], "completed")
            self.assertEqual(journal.status(p.proposal_id)["state"], "completed")
        with AgentRecoveryJournal(self.path) as later:
            self.assertEqual(later.recover()["auto_replayed"], 0)
            self.assertEqual(later.status(p.proposal_id)["state"], "completed")
            self.assertFalse(later.inventory()["contains_arguments"])

    def test_pending_proposal_requires_manual_review_after_restart(self):
        with AgentRecoveryJournal(self.path) as journal:
            p = DesktopApprovalController(journal=journal).propose(
                "stage_note", {"text": "not approved"})
            self.assertEqual(journal.status(p.proposal_id)["state"], "pending_review")
        with AgentRecoveryJournal(self.path) as later:
            restarted = DesktopApprovalController(journal=later)
            self.assertEqual(restarted.recovered["needs_review"], 1)
            self.assertEqual(restarted.status()["pending_approvals"], 0)
            self.assertEqual(later.status(p.proposal_id)["state"], "needs_review")
            self.assertEqual(restarted.status()["stored_synthetic_notes"], 0)

    def test_uncertain_dispatch_never_reexecuted(self):
        with AgentRecoveryJournal(self.path) as journal:
            p = DesktopApprovalController(journal=journal).propose(
                "stage_note", {"text": "might already have run"})
            journal.transition(p.proposal_id, p.digest,
                               from_state="pending_review",
                               to_state="dispatch_uncertain")
        with AgentRecoveryJournal(self.path) as later:
            new = DesktopApprovalController(journal=later)
            self.assertEqual(new.recovered["needs_reconciliation"], 1)
            self.assertEqual(later.status(p.proposal_id)["state"], "needs_reconciliation")
            self.assertEqual(new.status()["steps_used"], 0)
            self.assertEqual(new.status()["stored_synthetic_notes"], 0)

    def test_recovery_idempotent(self):
        with AgentRecoveryJournal(self.path) as j:
            p = DesktopApprovalController(journal=j).propose(
                "stage_note", {"text": "test"})
            a = j.recover()
            b = j.recover()
            self.assertEqual(a["needs_review"], 1)
            self.assertEqual(b["needs_review"], 0)
            self.assertEqual(j.status(p.proposal_id)["state"], "needs_review")

    def test_rejected_action_stays_rejected(self):
        with AgentRecoveryJournal(self.path) as j:
            desktop = DesktopApprovalController(journal=j)
            p = desktop.propose("stage_note", {"text": "test"})
            desktop.decide(p.proposal_id, p.digest, approved=False)
            self.assertEqual(j.status(p.proposal_id)["state"], "rejected")
        with AgentRecoveryJournal(self.path) as j:
            self.assertEqual(j.recover()["needs_review"], 0)
            self.assertEqual(j.status(p.proposal_id)["state"], "rejected")

    def test_only_metadata_not_arguments_or_tokens_persisted(self):
        secret = "synthetic-private-note-marker"
        with AgentRecoveryJournal(self.path) as j:
            desktop = DesktopApprovalController(journal=j)
            p = desktop.propose("stage_note", {"text": secret})
            desktop.decide(p.proposal_id, p.digest, approved=True)
            report = json.dumps(j.inventory())
            self.assertNotIn(secret, report)
        data = self.path.read_bytes()
        self.assertNotIn(secret.encode(), data)
        self.assertNotIn(b"approval_token", data)

    def test_unknown_and_replayed_transition_rejected(self):
        with AgentRecoveryJournal(self.path) as j:
            p = DesktopApprovalController(journal=j).propose(
                "stage_note", {"text": "test"})
            j.transition(p.proposal_id, p.digest, from_state="pending_review",
                         to_state="rejected")
            with self.assertRaises(RecoveryConflict):
                j.transition(p.proposal_id, p.digest, from_state="pending_review",
                             to_state="dispatch_uncertain")
            with self.assertRaises(RecoveryConflict):
                j.transition(p.proposal_id, p.digest, from_state="rejected",
                             to_state="completed")

    def test_wrong_digest_does_not_dispatch(self):
        with AgentRecoveryJournal(self.path) as j:
            p = DesktopApprovalController(journal=j).propose(
                "stage_note", {"text": "test"})
            with self.assertRaises(RecoveryConflict):
                j.transition(p.proposal_id, "0" * 64,
                             from_state="pending_review",
                             to_state="dispatch_uncertain")
            self.assertEqual(j.status(p.proposal_id)["state"], "pending_review")

    def test_invalid_path_and_memory_rejected(self):
        with self.assertRaises(ValueError):
            AgentRecoveryJournal(":memory:")
        with self.assertRaises(ValueError):
            AgentRecoveryJournal(self.path / "missing.sqlite3")

    def test_closed_journal_rejects_mutation(self):
        j = AgentRecoveryJournal(self.path)
        j.close()
        with self.assertRaises(RecoveryConflict):
            j.record_proposal("a" * 24, "stage_note", "0" * 64)

    def test_duplicate_proposal_is_refused(self):
        with AgentRecoveryJournal(self.path) as j:
            j.record_proposal("x" * 24, "stage_note", "a" * 64)
            with self.assertRaises(RecoveryConflict):
                j.record_proposal("x" * 24, "stage_note", "a" * 64)

    def test_journal_failure_cannot_leave_executable_pending_proposal(self):
        with AgentRecoveryJournal(self.path) as j:
            desktop = DesktopApprovalController(journal=j)
            j.close()
            with self.assertRaises(RecoveryConflict):
                desktop.propose("stage_note", {"text": "test"})
            self.assertEqual(desktop.agent.snapshot()["pending_proposals"], 0)

    def test_successful_readonly_tool_recorded_without_approval_token(self):
        with AgentRecoveryJournal(self.path) as j:
            desktop = DesktopApprovalController(journal=j)
            p = desktop.propose("inspect_status", {})
            desktop.decide(p.proposal_id, p.digest, approved=True)
            self.assertEqual(j.status(p.proposal_id)["state"], "completed")

    def test_full_db_has_no_replayable_args_after_restart(self):
        with AgentRecoveryJournal(self.path) as j:
            p = DesktopApprovalController(journal=j).propose(
                "stage_note", {"text": "synthetic example"})
        with sqlite3.connect(self.path) as raw:
            columns = [x[1] for x in raw.execute("PRAGMA table_info(agent_events)")]
        self.assertEqual(columns, [
            "proposal_id", "tool", "digest", "state", "changed_at"
        ])


if __name__ == "__main__":
    unittest.main()
