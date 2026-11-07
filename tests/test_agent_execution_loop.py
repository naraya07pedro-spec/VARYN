"""Deterministic no-network integration tests with real VARYN gateway APIs."""
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import unittest

from varyn.agent_execution_loop import (
    AgentLoopRejected, OwnerApprovedAgentLoop, parse_decision,
    submit_verified_result)
from varyn.agent_loop_journal import AgentLoopJournal
from varyn.learning_kernel import LearningKernel, LearningRejected
from varyn.model_registry import Offer, Registry
from varyn.public_github_tool import PublicGithubToolGateway
from varyn.universal_gateway import UniversalGateway
from varyn.usage_budget import UsageBudget

REPO = "naraya07pedro-spec/VARYN"
READ = '{"action":"read_public_github","repository":"' + REPO + '"}'
FINISH = '{"action":"finish","answer":"Public repository details retrieved."}'


def model_response(text):
    return json.dumps({
        "model": "test-model",
        "choices": [{"message": {"role": "assistant", "content": text},
                     "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 20, "completion_tokens": 30},
    }).encode("utf-8")


def public_metadata(repository):
    return {
        "format": "varyn.github_public_repo_metadata.v1",
        "repository": repository,
        "default_branch": "main",
        "stars": 3,
        "open_items_including_prs": 2,
        "archived": False,
        "public": True, "read_only": True,
        "untrusted_external_data": True,
        "provider_handoff": False,
    }


class LoopTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.journal = AgentLoopJournal(
            Path(self.temp.name) / "agent-runs.sqlite3")
        self.model_calls = []
        self.tool_calls = []
        self.responses = [READ, FINISH]

        def transport(provider, payload, key, timeout):
            self.model_calls.append((provider, payload, key))
            return model_response(self.responses.pop(0))

        registry = Registry([Offer(
            "openrouter", "test-model", 0, 0,
            date.today().isoformat(),
            owner_reviewed=True, route_fixed=True, enabled=True)])
        self.budget = UsageBudget(
            max_requests=4, max_reserved_output_tokens=2048)
        self.gateway = UniversalGateway(
            registry, allow_network=True, budget=self.budget,
            transport=transport, api_key="local-test-key-1234")
        self.tool = PublicGithubToolGateway(
            fetcher=lambda repo: self.tool_calls.append(repo)
            or public_metadata(repo))
        self.agent = OwnerApprovedAgentLoop(
            self.gateway, self.tool, self.journal)

    def tearDown(self):
        self.tool.close()
        self.journal.close()
        self.temp.cleanup()

    def go(self, **changes):
        kwargs = {
            "goal": "Read public metadata for " + REPO,
            "provider": "openrouter",
            "review_model": lambda preview: True,
            "review_tool": lambda review: True,
            "allow_public_network": True,
            "allow_metadata_upload": True,
        }
        kwargs.update(changes)
        return self.agent.run(**kwargs)

    def test_two_model_requests_one_tool_and_clean_journal(self):
        previews = []
        result = self.go(
            review_model=lambda p: previews.append(p) or True)
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["model_calls"], 2)
        self.assertEqual(result["tool_calls"], 1)
        self.assertFalse(result["owner_verified"])
        self.assertEqual(self.tool_calls, [REPO])
        self.assertEqual(len(self.model_calls), 2)
        self.assertEqual(len(previews), 2)
        self.assertIn("untrusted_public_metadata",
                      previews[1]["exact_outgoing_prompt"])
        self.assertEqual(self.journal.status(result["run_id"])["state"],
                         "completed")
        self.assertEqual(self.budget.snapshot()["requests_reserved"], 2)

    def test_denied_model_never_dispatches(self):
        result = self.go(review_model=lambda p: False)
        self.assertEqual(result["status"], "denied")
        self.assertEqual(self.model_calls, [])
        self.assertEqual(self.tool_calls, [])

    def test_tool_network_off_even_if_model_requests_tool(self):
        result = self.go(allow_public_network=False)
        self.assertEqual(result["status"], "tool_network_denied")
        self.assertEqual(len(self.model_calls), 1)
        self.assertEqual(self.tool_calls, [])

    def test_tool_review_denied(self):
        result = self.go(review_tool=lambda p: False)
        self.assertEqual(result["status"], "tool_denied")
        self.assertEqual(self.tool_calls, [])
        self.assertEqual(len(self.model_calls), 1)

    def test_metadata_does_not_leave_device_by_default(self):
        result = self.go(allow_metadata_upload=False)
        self.assertEqual(result["status"], "observation_only")
        self.assertFalse(result["model_handoff"])
        self.assertEqual(len(self.model_calls), 1)
        self.assertEqual(self.tool_calls, [REPO])

    def test_second_exact_prompt_must_be_reviewed(self):
        choices = iter([True, False])
        result = self.go(review_model=lambda p: next(choices))
        self.assertEqual(result["status"], "synthesis_denied")
        self.assertEqual(len(self.model_calls), 1)
        self.assertEqual(self.tool_calls, [REPO])

    def test_model_may_finish_without_tool(self):
        self.responses = [FINISH]
        result = self.go()
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["model_calls"], 1)
        self.assertEqual(result["tool_calls"], 0)

    def test_rogue_commands_and_duplicate_json_denied(self):
        for text in (
            '{"action":"delete_file","repository":"a/b"}',
            '{"action":"read_public_github","repository":"file:///etc/passwd"}',
            '{"action":"read_public_github","repository":"a/b","extra":1}',
            '{"action":"finish","answer":"a","answer":"b"}',
            "The model proposes to call a tool.",
        ):
            with self.subTest(text=text):
                with self.assertRaises(AgentLoopRejected):
                    parse_decision(text)

    def test_second_model_cannot_chain_another_tool(self):
        self.responses = [READ, READ]
        with self.assertRaises(AgentLoopRejected):
            self.go()
        self.assertEqual(len(self.tool_calls), 1)
        self.assertEqual(self.journal.recover()["needs_reconciliation"], 1)

    def test_nonboolean_owner_approval_denied(self):
        with self.assertRaises(AgentLoopRejected):
            self.go(review_model=lambda p: "yes")
        self.assertEqual(self.model_calls, [])
        self.assertEqual(self.tool_calls, [])

    def test_failed_network_is_not_auto_replayed(self):
        self.responses = []
        with self.assertRaises(IndexError):
            self.go()
        recovery = self.journal.recover()
        self.assertEqual(recovery["needs_reconciliation"], 1)
        self.assertEqual(recovery["auto_replayed"], 0)

    def test_sensitive_goal_never_written_to_journal(self):
        result = self.go(allow_metadata_upload=False)
        rows = self.journal.db.execute(
            "SELECT goal_hash,state FROM agent_loop_runs").fetchall()
        self.assertEqual(len(rows[0][0]), 64)
        self.assertNotIn("metadata", str(rows))
        self.assertEqual(self.journal.status(result["run_id"])["state"],
                         "observation_only")

    def test_skill_bridge_requires_real_host_verification(self):
        self.responses = [FINISH]
        result = self.go()
        with LearningKernel(Path(self.temp.name) / "learning.sqlite3") as kernel:
            with self.assertRaises(LearningRejected):
                submit_verified_result(
                    kernel, result, family="github_triage", task_id="id-1")
            ident = submit_verified_result(
                kernel, result, family="github_triage", task_id="id-1",
                verified_by_host=True)
            self.assertEqual(len(ident), 32)


if __name__ == "__main__":
    unittest.main()
