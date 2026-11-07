"""Offline acceptance of real VARYN model gateway + consent-gated public reads.

No provider credentials, internet access or model account are used in CI.
"""
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import unittest

from varyn.budgeted_reflection_scheduler import (
    BudgetedReflectionScheduler, conservative_public_fact_reflector)
from varyn.grounded_github import GroundingRejected
from varyn.learning_kernel import LearningKernel
from varyn.model_registry import Offer, Registry
from varyn.owner_live_evaluation import (
    OwnerReviewedLiveEvaluation, LiveEvaluationRejected,
    PUBLIC_CASE_REPOSITORIES)
from varyn.public_github_tool import PublicGithubToolGateway
from varyn.universal_gateway import UniversalGateway
from varyn.usage_budget import UsageBudget
from varyn.verified_failure_feedback import VerifiedFailureLedger


def public_record(repo):
    offset = PUBLIC_CASE_REPOSITORIES.index(repo)
    return {
        "format": "varyn.github_public_repo_metadata.v1",
        "repository": repo,
        "default_branch": ("main" if offset % 2 == 0 else "master"),
        "stars": 10 * (offset + 1),
        "open_items_including_prs": offset + 2,
        "archived": offset == 3,
        "public": True, "read_only": True,
        "untrusted_external_data": True,
        "provider_handoff": False,
    }


def provider_response(message):
    return json.dumps({
        "model": "test-model",
        "choices": [{"message": {"role": "assistant", "content": message},
                     "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 75, "completion_tokens": 45},
    }).encode("utf-8")


class OwnerLiveEvaluationTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.kernel = LearningKernel(
            Path(self.temp.name) / "learning.sqlite3")
        self.ledger = VerifiedFailureLedger(self.kernel)
        self.model_payloads = []
        self.public_reads = []
        self.responses = "improvement"

        def transport(provider, payload, api_key, timeout):
            question = json.loads(payload["messages"][0]["content"])
            self.model_payloads.append(question)
            fields = question["public_metadata_untrusted_data"]
            selected = question["optional_untrusted_procedural_hint"]
            index = PUBLIC_CASE_REPOSITORIES.index(fields["repository"])
            if self.responses == "improvement":
                if not selected and index == 0:
                    fields["stars"] += 1
            elif self.responses == "equal":
                pass
            elif self.responses == "regression":
                if selected and index == 0:
                    fields["stars"] += 1
                elif not selected and index == 1:
                    fields["stars"] += 1
            return provider_response(json.dumps({
                "action": "finish", "facts": fields}))

        offer = Offer(
            "openrouter", "test-model", 0, 0,
            date.today().isoformat(),
            owner_reviewed=True, route_fixed=True, enabled=True)
        self.budget = UsageBudget(
            max_requests=10, max_reserved_output_tokens=2560)
        self.gateway = UniversalGateway(
            Registry([offer]), allow_network=True,
            budget=self.budget, api_key="local-test-key-only",
            transport=transport)
        self.tool = PublicGithubToolGateway(
            fetcher=lambda repo: self.public_reads.append(repo) or
            public_record(repo), max_requests=5)
        self.worker = OwnerReviewedLiveEvaluation(
            self.gateway, self.tool, self.kernel)

    def tearDown(self):
        self.tool.close()
        self.kernel.close()
        self.temp.cleanup()

    def evidence(self):
        for i in (1, 2):
            self.kernel.record_verified_outcome(
                "github_public_facts", "verified-task-" + str(i),
                format(i, "064x"), succeeded=True,
                verified_by_host=True)
        self.ledger.record(
            "a" * 32,
            GroundingRejected("Model fact does not match observation"),
            {"status": "completed", "network_dispatched": True,
             "result": public_record(PUBLIC_CASE_REPOSITORIES[0])},
            owner_opted_in=True)

    def run_reviewed(self, **changes):
        inputs = {
            "provider": "openrouter",
            "owner_enabled": True,
            "review_model": lambda payload: True,
            "review_tool": lambda review: True,
        }
        inputs.update(changes)
        return self.worker.run(**inputs)

    def test_without_explicit_permission_no_dispatch(self):
        self.evidence()
        result = self.run_reviewed(owner_enabled=False)
        self.assertEqual(result["status"], "disabled")
        self.assertEqual(self.public_reads, [])
        self.assertEqual(self.model_payloads, [])

    def test_not_enough_evidence_no_public_reads(self):
        result = self.run_reviewed()
        self.assertEqual(result["status"], "insufficient_evidence")
        self.assertEqual(self.public_reads, [])
        self.assertEqual(self.model_payloads, [])

    def test_owner_denies_first_github_read_no_inference(self):
        self.evidence()
        result = self.run_reviewed(review_tool=lambda review: False)
        self.assertEqual(result["status"], "public_read_denied")
        self.assertEqual(result["public_reads"], 0)
        self.assertEqual(self.public_reads, [])
        self.assertEqual(self.model_payloads, [])

    def test_exact_5_public_reads_and_10_reviewed_live_shape_calls(self):
        self.evidence()
        seen = []
        result = self.run_reviewed(
            review_model=lambda p: seen.append(p) or True)
        self.assertEqual(result["status"], "promoted")
        self.assertEqual(result["public_reads"], 5)
        self.assertEqual(result["model_calls"], 10)
        self.assertEqual(self.public_reads, list(PUBLIC_CASE_REPOSITORIES))
        self.assertEqual(len(self.model_payloads), 10)
        self.assertEqual(len(seen), 10)
        self.assertEqual(self.budget.snapshot()["requests_reserved"], 10)
        self.assertFalse(result["provider_billing_cap_enforced"])
        self.assertTrue(result["skill_promoted"])
        self.assertIsNotNone(self.kernel.active_skill("github_public_facts"))

    def test_equal_baseline_and_candidate_must_not_promote(self):
        self.evidence()
        self.responses = "equal"
        result = self.run_reviewed()
        self.assertEqual(result["status"], "rejected")
        self.assertFalse(result["skill_promoted"])
        self.assertIsNone(self.kernel.active_skill("github_public_facts"))

    def test_regression_rejects_despite_other_gains(self):
        self.evidence()
        self.responses = "regression"
        result = self.run_reviewed()
        self.assertEqual(result["status"], "rejected")
        self.assertEqual(result["regressions"], 1)
        self.assertFalse(result["skill_promoted"])

    def test_owner_denies_model_request_and_retains_uncertain_reservation(self):
        self.evidence()
        with self.assertRaises(PermissionError):
            self.run_reviewed(review_model=lambda p: False)
        self.assertEqual(len(self.public_reads), 5)
        self.assertEqual(self.model_payloads, [])
        history = BudgetedReflectionScheduler(
            self.kernel, self.ledger).history()
        self.assertEqual(history[0]["status"], "needs_review")
        self.assertEqual(history[0]["reserved_evaluator_calls"], 10)

    def test_no_automatic_replay_after_crash_with_new_gateway(self):
        self.evidence()
        with self.assertRaises(PermissionError):
            self.run_reviewed(review_model=lambda p: False)
        # A new trusted gateway session has fresh public read quota. The
        # scheduler must refuse the already-used evidence batch.
        second_tool = PublicGithubToolGateway(
            fetcher=public_record, max_requests=5)
        second_gateway = UniversalGateway(
            self.gateway.registry, allow_network=True,
            budget=UsageBudget(
                max_requests=10, max_reserved_output_tokens=2560),
            api_key="local-test-key-only",
            transport=lambda provider, payload, key, timeout:
                provider_response('{"action":"finish","facts":{}}'))
        try:
            second_worker = OwnerReviewedLiveEvaluation(
                second_gateway, second_tool, self.kernel)
            outcome = second_worker.run(
                provider="openrouter", owner_enabled=True,
                review_model=lambda p: True,
                review_tool=lambda p: True)
            self.assertEqual(outcome["status"], "already_processed")
        finally:
            second_tool.close()

    def test_insufficient_local_budget_prevents_reads(self):
        self.evidence()
        self.budget.reserve(256)
        result = self.run_reviewed()
        self.assertEqual(result["status"], "insufficient_model_budget")
        self.assertEqual(self.public_reads, [])

    def test_reject_unreviewed_or_malicious_repositories(self):
        self.evidence()
        with self.assertRaises(LiveEvaluationRejected):
            self.run_reviewed(repositories=(
                "localhost/admin", *PUBLIC_CASE_REPOSITORIES[1:]))
        with self.assertRaises(LiveEvaluationRejected):
            self.run_reviewed(repositories=(
                PUBLIC_CASE_REPOSITORIES[0],) * 5)
        self.assertEqual(self.public_reads, [])

    def test_real_billing_estimate_limit_is_not_ensured_cap(self):
        self.evidence()
        readiness = self.worker.readiness(provider="openrouter")
        self.assertFalse(readiness["provider_billing_cap_enforced"])
        self.assertEqual(readiness["max_model_requests"], 10)
        self.assertEqual(readiness["max_public_reads"], 5)
        self.assertEqual(readiness["estimated_micro_usd"], 0)

    def test_exact_prompt_does_not_include_provider_credentials(self):
        self.evidence()
        self.run_reviewed()
        for prompt in self.model_payloads:
            rendered = json.dumps(prompt)
            self.assertNotIn("local-test-key-only", rendered)
            self.assertNotIn("private", rendered.lower())


if __name__ == "__main__":
    unittest.main()
