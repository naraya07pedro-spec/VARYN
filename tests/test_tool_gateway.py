"""17S-1: test one-use synthetic disk-read permission adapter and desktop UI."""
import json
import unittest
from unittest.mock import patch

from varyn.file_grants import ScopedFileGrants
from varyn.synthetic_fixture import SyntheticFixture, _FIXTURE_FILES
from varyn.tool_gateway import SyntheticReadToolGateway, ToolGatewayRejected


class ToolGatewayTests(unittest.TestCase):
    def setUp(self):
        self.fixture = SyntheticFixture()
        self.addCleanup(self.fixture.close)
        self.time = [100.0]
        self.grants = ScopedFileGrants(clock=lambda: self.time[0])
        self.addCleanup(self.grants.revoke_all)
        self.grant = self.grants.grant(self.fixture.root, user_confirmed=True,
                                      duration_seconds=30, max_operations=3)
        self.gateway = SyntheticReadToolGateway(self.grants)

    def proposal(self):
        return self.gateway.propose("read_generated_sample", {"name": "sample.txt"},
                                    grant_id=self.grant.grant_id)

    def test_approved_read_is_real_scoped_read_and_offline(self):
        p = self.proposal()
        out = self.gateway.decide(p.proposal_id, p.digest, approved=True)
        self.assertEqual(out["output"]["text"], _FIXTURE_FILES["sample.txt"])
        self.assertFalse(out["external_upload"])
        self.assertFalse(self.gateway.status()["model_connected"])

    def test_proposal_cannot_read(self):
        with patch.object(self.grants, "read_text", side_effect=AssertionError("read")):
            self.proposal()

    def test_denial_prevents_read_and_replay(self):
        p = self.proposal()
        with patch.object(self.grants, "read_text", side_effect=AssertionError("read")):
            self.assertEqual(self.gateway.decide(p.proposal_id, p.digest,
                                                 approved=False)["status"], "rejected")
        with self.assertRaises(ToolGatewayRejected):
            self.gateway.decide(p.proposal_id, p.digest, approved=True)

    def test_tampered_digest_not_authorized(self):
        p = self.proposal()
        with self.assertRaises(ToolGatewayRejected):
            self.gateway.decide(p.proposal_id, "0" * 64, approved=True)
        self.assertEqual(self.gateway.status()["pending"], 1)
        self.gateway.decide(p.proposal_id, p.digest, approved=False)

    def test_consumed_success_cannot_replay(self):
        p = self.proposal()
        self.gateway.decide(p.proposal_id, p.digest, approved=True)
        with self.assertRaises(ToolGatewayRejected):
            self.gateway.decide(p.proposal_id, p.digest, approved=True)

    def test_revoked_or_expired_grant_fails_closed(self):
        p = self.proposal()
        self.grants.revoke(self.grant.grant_id)
        with self.assertRaises(ToolGatewayRejected):
            self.gateway.decide(p.proposal_id, p.digest, approved=True)
        self.assertEqual(self.gateway.status()["pending"], 0)

    def test_expiry_blocks_read(self):
        p = self.proposal()
        self.time[0] += 31
        with self.assertRaises(ToolGatewayRejected):
            self.gateway.decide(p.proposal_id, p.digest, approved=True)

    def test_modified_sample_never_returned(self):
        p = self.proposal()
        (self.fixture.root / "sample.txt").write_text("PRIVATE CONTENT", encoding="utf-8")
        with self.assertRaises(ToolGatewayRejected):
            self.gateway.decide(p.proposal_id, p.digest, approved=True)
        self.assertNotIn("PRIVATE CONTENT", repr(self.gateway.status()))

    def test_unapproved_tool_names_and_paths_denied(self):
        bad = [
            ("shell", {"name": "sample.txt"}),
            ("read_generated_sample", {"name": "../private.txt"}),
            ("read_generated_sample", {"name": "secrets.md"}),
            ("read_generated_sample", {"name": "sample.txt", "path": "D:\\private"}),
            ("read_generated_sample", {"name": 2}),
        ]
        for tool, args in bad:
            with self.subTest(tool=tool), self.assertRaises(ToolGatewayRejected):
                self.gateway.propose(tool, args, grant_id=self.grant.grant_id)
        self.assertEqual(self.gateway.status()["pending"], 0)

    def test_boolean_ui_consent_exact_type(self):
        p = self.proposal()
        for wrong in (1, None, "true"):
            with self.assertRaises(ToolGatewayRejected):
                self.gateway.decide(p.proposal_id, p.digest, approved=wrong)
        self.assertEqual(self.gateway.status()["pending"], 1)

    def test_audit_never_contains_path_content_or_token(self):
        p = self.proposal()
        self.gateway.decide(p.proposal_id, p.digest, approved=True)
        report = repr(self.gateway.status())
        for x in (str(self.fixture.root), self.grant.grant_id,
                  p.proposal_id, p.digest, "VARYN local-only"):
            self.assertNotIn(x, report)

    def test_pending_limit_and_discard(self):
        gate = SyntheticReadToolGateway(self.grants, max_pending=1)
        p = gate.propose("read_generated_sample", {"name": "notes.md"},
                         grant_id=self.grant.grant_id)
        with self.assertRaises(ToolGatewayRejected):
            gate.propose("read_generated_sample", {"name": "notes.md"},
                         grant_id=self.grant.grant_id)
        self.assertEqual(gate.reject_all_pending(), 1)
        with self.assertRaises(ToolGatewayRejected):
            gate.decide(p.proposal_id, p.digest, approved=True)

    def test_decision_limit(self):
        gate = SyntheticReadToolGateway(self.grants, max_decisions=1)
        p = gate.propose("read_generated_sample", {"name": "notes.md"},
                         grant_id=self.grant.grant_id)
        gate.decide(p.proposal_id, p.digest, approved=False)
        with self.assertRaises(ToolGatewayRejected):
            gate.propose("read_generated_sample", {"name": "notes.md"},
                         grant_id=self.grant.grant_id)

    def test_repeated_discard_cannot_grow_audit_without_bound(self):
        for _ in range(100):
            self.proposal()
            self.gateway.reject_all_pending()
        self.assertLessEqual(len(self.gateway._events), 64)
        self.assertEqual(self.gateway.status()["pending"], 0)

    def test_manager_type_restricted(self):
        with self.assertRaises(TypeError):
            SyntheticReadToolGateway(object())

    def test_untrusted_task_plan_cannot_use_gateway(self):
        from varyn.task_planner import TaskPlanError, compile_plan
        raw = json.dumps({"format": "varyn.task_plan.v1", "steps": [
            {"tool": "read_generated_sample", "arguments": {"name": "sample.txt"}}]})
        with self.assertRaises(TaskPlanError):
            compile_plan(raw)


class DesktopToolTests(unittest.TestCase):
    def test_confirm_and_deny_path_without_provider(self):
        from varyn.desktop import VarynDesktop
        class Fake:
            _busy = False
            _closing = False
            _file_grant_id = None
            _file_fixture = None
            def __init__(self):
                self._file_grants = ScopedFileGrants()
                self.messages = []
            def _append(self, role, text):
                self.messages.append((role, text))
        ui = Fake()
        fixture = SyntheticFixture()
        try:
            preview = ui._file_grants.grant(fixture.root, user_confirmed=True)
            ui._file_grant_id, ui._file_fixture = preview.grant_id, fixture
            with patch("varyn.desktop.messagebox.askyesno", return_value=False) as dialog:
                VarynDesktop._read_reviewed_synthetic_sample(ui)
            self.assertEqual(dialog.call_count, 1)
            self.assertIn("declined", repr(ui.messages))
            with patch("varyn.desktop.messagebox.askyesno", return_value=True):
                VarynDesktop._read_reviewed_synthetic_sample(ui)
            self.assertIn("VARYN local-only synthetic test record", repr(ui.messages))
            self.assertFalse(ui._synthetic_tools.status()["provider_handoff_allowed"])
            self.assertNotIn(str(fixture.root), repr(ui.messages))
        finally:
            ui._file_grants.revoke_all()
            fixture.close()


if __name__ == "__main__":
    unittest.main()
