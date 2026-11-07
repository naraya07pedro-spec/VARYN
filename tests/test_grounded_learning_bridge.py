"""Offline tests: structured factual verification and learning bridge."""
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import unittest

from varyn.agent_execution_loop import AgentLoopRejected, OwnerApprovedAgentLoop
from varyn.agent_loop_journal import AgentLoopJournal
from varyn.grounded_github import (
    GroundingRejected, record_grounded_fact_receipt, validate_grounded_claim)
from varyn.learning_kernel import LearningKernel
from varyn.model_registry import Offer, Registry
from varyn.public_github_tool import PublicGithubToolGateway
from varyn.universal_gateway import UniversalGateway
from varyn.usage_budget import UsageBudget

REPO = "naraya07pedro-spec/VARYN"
READ = json.dumps({"action": "read_public_github", "repository": REPO})
FACTS = {
    "repository": REPO, "default_branch": "main", "stars": 3,
    "open_items_including_prs": 2, "archived": False,
}
REPORT = json.dumps({"action": "finish", "facts": FACTS})


def observation():
    return {
        "status": "completed", "network_dispatched": True,
        "result": {
            "format": "varyn.github_public_repo_metadata.v1",
            **FACTS, "public": True, "read_only": True,
            "untrusted_external_data": True, "provider_handoff": False,
        },
    }


def completion(text):
    return json.dumps({
        "model": "test-model",
        "choices": [{"message": {"role": "assistant", "content": text},
                     "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 50, "completion_tokens": 50},
    }).encode("utf-8")


class GroundedClaims(unittest.TestCase):
    def test_exact_facts_verified_and_prose_derived_from_tool(self):
        result = validate_grounded_claim(REPORT, observation())
        self.assertIn("Stars: 3", result["report"])
        self.assertIn(REPO, result["report"])
        self.assertTrue(result["verified_against_tool_observation"])
        self.assertFalse(result["third_party_truth_independently_verified"])
        self.assertFalse(result["model_prose_verified"])

    def test_mismatches_and_untrusted_tool_responses_fail_closed(self):
        variations = [
            {**FACTS, "stars": 4},
            {**FACTS, "stars": True},
            {**FACTS, "archived": 0},
            {**FACTS, "repository": "other/repo"},
            {**FACTS, "default_branch": "agent-injected"},
            {**FACTS, "unexpected": "extra"},
        ]
        for facts in variations:
            with self.subTest(facts=facts), self.assertRaises(GroundingRejected):
                validate_grounded_claim(json.dumps({
                    "action": "finish", "facts": facts}), observation())
        for raw in (
            '{"action":"finish","facts":{},"facts":{}}',
            '{"action":"finish","facts":null}',
            '{"action":"delete_repo","facts":{}}',
            '{"action":"finish","answer":"Stars: 3"}',
            "Here are my facts: " + REPORT,
            '{"action":"finish","facts":{"stars":NaN}}',
        ):
            with self.subTest(raw=raw), self.assertRaises(GroundingRejected):
                validate_grounded_claim(raw, observation())
        bad = observation()
        bad["network_dispatched"] = False
        with self.assertRaises(GroundingRejected):
            validate_grounded_claim(REPORT, bad)

    def test_duplicate_receipt_is_not_new_independent_evidence(self):
        with TemporaryDirectory() as folder:
            with LearningKernel(Path(folder) / "learning.sqlite3") as kernel:
                checked = validate_grounded_claim(REPORT, observation())
                self.assertEqual(
                    record_grounded_fact_receipt(kernel, checked)["status"],
                    "recorded")
                self.assertEqual(
                    record_grounded_fact_receipt(kernel, checked)["status"],
                    "duplicate")
                self.assertEqual(kernel.db.execute(
                    "SELECT COUNT(*) FROM outcomes").fetchone()[0], 1)


class RealGatewayBridge(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        folder = Path(self.tmp.name)
        self.journal = AgentLoopJournal(folder / "runs.sqlite3")
        self.learning = LearningKernel(folder / "learning.sqlite3")
        self.results = [READ, REPORT]
        self.outgoing = []
        self.public_reads = []

        def transport(provider, payload, api_key, timeout):
            self.outgoing.append(payload)
            return completion(self.results.pop(0))

        offer = Offer("openrouter", "test-model", 0, 0,
                      date.today().isoformat(),
                      owner_reviewed=True, route_fixed=True, enabled=True)
        budget = UsageBudget(max_requests=10,
                             max_reserved_output_tokens=8000)
        self.gateway = UniversalGateway(
            Registry([offer]), allow_network=True, budget=budget,
            transport=transport, api_key="local-test-key-1234")
        self.tool = PublicGithubToolGateway(
            fetcher=lambda repo: self.public_reads.append(repo)
            or observation()["result"])
        self.loop = OwnerApprovedAgentLoop(
            self.gateway, self.tool, self.journal,
            learning_kernel=self.learning)

    def tearDown(self):
        self.tool.close()
        self.journal.close()
        self.learning.close()
        self.tmp.cleanup()

    def go(self, **changes):
        args = {
            "goal": "Report public facts for " + REPO,
            "provider": "openrouter",
            "review_model": lambda preview: True,
            "review_tool": lambda review: True,
            "allow_public_network": True,
            "allow_metadata_upload": True,
            "verify_public_facts": True,
            "persist_grounded_receipt": True,
        }
        args.update(changes)
        return self.loop.run(**args)

    def test_exact_verification_and_durable_evidence(self):
        result = self.go()
        self.assertEqual(result["status"], "completed")
        self.assertTrue(result["verified_public_facts"])
        self.assertFalse(result["third_party_truth_independently_verified"])
        self.assertIn("Stars: 3", result["answer"])
        self.assertEqual(result["learning_receipt_status"], "recorded")
        self.assertEqual(self.learning.db.execute(
            "SELECT COUNT(*) FROM outcomes").fetchone()[0], 1)
        self.assertEqual(self.journal.status(result["run_id"])["state"],
                         "completed")
        self.assertEqual(len(self.outgoing), 2)
        prompt = json.loads(self.outgoing[1]["messages"][0]["content"])
        self.assertIn("facts", prompt["output"])
        self.assertEqual(prompt["untrusted_public_metadata"]["stars"], 3)

    def test_model_hallucinated_fields_are_not_learned(self):
        incorrect = {**FACTS, "stars": 999}
        self.results = [
            READ, json.dumps({"action": "finish", "facts": incorrect})]
        with self.assertRaises(GroundingRejected):
            self.go()
        self.assertEqual(self.learning.db.execute(
            "SELECT COUNT(*) FROM outcomes").fetchone()[0], 0)
        row = self.journal.db.execute(
            "SELECT state FROM agent_loop_runs").fetchone()[0]
        self.assertEqual(row, "verification_failed")
        self.assertEqual(self.journal.recover()["auto_replayed"], 0)

    def test_no_receipt_without_opt_in(self):
        result = self.go(persist_grounded_receipt=False)
        self.assertTrue(result["verified_public_facts"])
        self.assertEqual(result["learning_receipt_status"], "disabled")
        self.assertEqual(self.learning.db.execute(
            "SELECT COUNT(*) FROM outcomes").fetchone()[0], 0)

    def test_identical_read_receipt_is_deduplicated_across_runs(self):
        first = self.go()
        self.results = [READ, REPORT]
        second = self.go()
        self.assertEqual(first["learning_receipt_status"], "recorded")
        self.assertEqual(second["learning_receipt_status"], "duplicate")
        self.assertEqual(self.learning.db.execute(
            "SELECT COUNT(*) FROM outcomes").fetchone()[0], 1)

    def test_skill_context_is_opt_in_and_exactly_reviewable(self):
        ids = [
            self.learning.record_verified_outcome(
                "github_public_facts", "source-" + str(i),
                str(i) * 64, succeeded=True, verified_by_host=True)
            for i in (1, 2)
        ]
        body = "Use verified GitHub public metadata fields. Do not invent branch names."
        candidate = self.learning.propose_skill(
            "github_public_facts", body, ids)
        cases = ("case1", "case2", "case3", "case4", "case5")
        selected = self.learning.evaluate_and_select(
            candidate, cases, lambda text, case: text == body)
        self.assertTrue(selected["accepted"])
        seen = []
        self.go(
            persist_grounded_receipt=False, include_learned_skill=True,
            review_model=lambda p: seen.append(p) or True)
        self.assertIn("untrusted_procedural_hint",
                      seen[0]["exact_outgoing_prompt"])
        self.assertIn(body, seen[0]["exact_outgoing_prompt"])
        self.assertIn(body, seen[1]["exact_outgoing_prompt"])

    def test_skill_not_sent_without_opt_in(self):
        seen = []
        self.go(persist_grounded_receipt=False,
                include_learned_skill=False,
                review_model=lambda p: seen.append(p) or True)
        self.assertNotIn("untrusted_procedural_hint",
                         seen[0]["exact_outgoing_prompt"])

    def test_unverified_finish_never_creates_fact_receipt(self):
        self.results = ['{"action":"finish","answer":"No tool needed"}']
        result = self.go()
        self.assertEqual(result["tool_calls"], 0)
        self.assertNotIn("verified_public_facts", result)
        self.assertEqual(self.learning.db.execute(
            "SELECT COUNT(*) FROM outcomes").fetchone()[0], 0)

    def test_no_persistence_without_fact_verification(self):
        with self.assertRaises(AgentLoopRejected):
            self.go(verify_public_facts=False)
        self.assertEqual(self.outgoing, [])


if __name__ == "__main__":
    unittest.main()
