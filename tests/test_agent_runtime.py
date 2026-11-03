"""Fully offline bounded agent tests; no model inference or external tools."""
import json
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor

from varyn.agent_runtime import (
    AgentLimitReached, AgentRejected, ApprovalRequired, BoundedAgent,
)


class AgentRuntimeTests(unittest.TestCase):
    def test_read_only_tool_does_not_need_approval(self):
        agent = BoundedAgent(max_steps=2)
        proposal = agent.propose("inspect_status", {})
        self.assertFalse(proposal.mutates)
        result = agent.execute(proposal.proposal_id)
        self.assertEqual(result.status, "completed")
        self.assertEqual(result.output["steps_used"], 1)
        self.assertEqual(agent.snapshot()["steps_used"], 1)

    def test_mutation_requires_one_time_token(self):
        agent = BoundedAgent(max_steps=2)
        proposal = agent.propose("stage_note", {"text": "synthetic note"})
        self.assertTrue(proposal.mutates)
        with self.assertRaises(ApprovalRequired):
            agent.execute(proposal.proposal_id)
        with self.assertRaises(ApprovalRequired):
            agent.execute(proposal.proposal_id, approval_token="bad")
        self.assertEqual(agent.snapshot()["steps_used"], 0)
        approval = agent.approve(proposal.proposal_id)
        result = agent.execute(proposal.proposal_id, approval_token=approval)
        self.assertEqual(result.output["stored_synthetic_notes"], 1)
        with self.assertRaises(AgentRejected):
            agent.execute(proposal.proposal_id, approval_token=approval)

    def test_rejected_proposal_cannot_be_executed(self):
        agent = BoundedAgent()
        p = agent.propose("stage_note", {"text": "test"})
        approval = agent.approve(p.proposal_id)
        agent.reject(p.proposal_id)
        with self.assertRaises(AgentRejected):
            agent.execute(p.proposal_id, approval_token=approval)
        self.assertEqual(agent.snapshot()["stored_synthetic_notes"], 0)

    def test_unknown_tool_and_shell_never_run(self):
        agent = BoundedAgent()
        for name in ("shell", "run_python", "http", "filesystem_write", "../unsafe"):
            with self.subTest(name=name), self.assertRaises(AgentRejected):
                agent.propose(name, {"command": "echo fake"})
        self.assertEqual(agent.snapshot()["steps_used"], 0)

    def test_invalid_arguments_rejected(self):
        agent = BoundedAgent()
        for args in ({}, {"text": ""}, {"text": "x" * 201},
                     {"text": "test", "other": True}, {"text": 12}):
            with self.subTest(args=str(args)[:30]), self.assertRaises(AgentRejected):
                agent.propose("stage_note", args)
        with self.assertRaises(AgentRejected):
            agent.propose("inspect_status", {"extra": 1})
        with self.assertRaises(AgentRejected):
            agent.propose("stage_note", {"text": "x" * 3000})

    def test_readonly_approval_is_disallowed(self):
        agent = BoundedAgent()
        p = agent.propose("inspect_status", {})
        with self.assertRaises(AgentRejected):
            agent.approve(p.proposal_id)

    def test_step_limit_and_pending_proposal_limit(self):
        agent = BoundedAgent(max_steps=2)
        first = agent.propose("inspect_status", {})
        second = agent.propose("inspect_status", {})
        with self.assertRaises(AgentLimitReached):
            agent.propose("inspect_status", {})
        agent.execute(first.proposal_id)
        with self.assertRaises(AgentLimitReached):
            agent.propose("inspect_status", {})
        agent.execute(second.proposal_id)
        with self.assertRaises(AgentLimitReached):
            agent.propose("inspect_status", {})

    def test_reject_frees_pending_slot(self):
        agent = BoundedAgent(max_steps=1)
        p = agent.propose("inspect_status", {})
        agent.reject(p.proposal_id)
        newer = agent.propose("inspect_status", {})
        self.assertNotEqual(p.proposal_id, newer.proposal_id)

    def test_limit_notes_and_count_failed_attempt(self):
        agent = BoundedAgent(max_steps=3, max_notes=1)
        first = agent.propose("stage_note", {"text": "one"})
        agent.execute(first.proposal_id, approval_token=agent.approve(first.proposal_id))
        second = agent.propose("stage_note", {"text": "two"})
        with self.assertRaises(AgentLimitReached):
            agent.execute(second.proposal_id,
                          approval_token=agent.approve(second.proposal_id))
        self.assertEqual(agent.snapshot()["steps_used"], 2)
        self.assertEqual(agent.snapshot()["stored_synthetic_notes"], 1)
        self.assertEqual(agent.snapshot()["audit"][-1][0], "failed")

    def test_audit_excludes_contents_and_approval_token(self):
        agent = BoundedAgent()
        p = agent.propose("stage_note", {"text": "secret synthetic test"})
        approval = agent.approve(p.proposal_id)
        agent.execute(p.proposal_id, approval_token=approval)
        report = json.dumps(agent.snapshot())
        self.assertNotIn("secret synthetic test", report)
        self.assertNotIn(approval, report)
        self.assertNotIn(p.proposal_id, report)
        self.assertFalse(agent.snapshot()["approval_authenticated"])

    def test_duplicate_concurrent_execution_single_winner(self):
        agent = BoundedAgent(max_steps=2)
        p = agent.propose("stage_note", {"text": "only once"})
        token = agent.approve(p.proposal_id)
        def attempt(_):
            try:
                agent.execute(p.proposal_id, approval_token=token)
                return True
            except AgentRejected:
                return False
        with ThreadPoolExecutor(max_workers=6) as pool:
            results = list(pool.map(attempt, range(12)))
        self.assertEqual(sum(results), 1)
        self.assertEqual(agent.snapshot()["stored_synthetic_notes"], 1)

    def test_audit_digest_fixed_for_same_tool_arguments(self):
        agent = BoundedAgent()
        a = agent.propose("stage_note", {"text": "fixture"})
        b = agent.propose("stage_note", {"text": "fixture"})
        self.assertEqual(a.digest, b.digest)
        self.assertNotEqual(a.proposal_id, b.proposal_id)

    def test_invalid_limits_rejected(self):
        for kwargs in ({"max_steps": 0}, {"max_steps": True},
                       {"max_notes": 101}, {"max_notes": False}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                BoundedAgent(**kwargs)

    def test_no_background_autonomy(self):
        agent = BoundedAgent()
        agent.propose("stage_note", {"text": "unexecuted"})
        self.assertEqual(agent.snapshot()["stored_synthetic_notes"], 0)
        self.assertEqual(agent.snapshot()["steps_used"], 0)


if __name__ == "__main__":
    unittest.main()
