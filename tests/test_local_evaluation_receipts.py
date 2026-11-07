"""Local verification of redacted, persistent model acceptance receipts."""
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import sqlite3
import unittest

from varyn.grounded_github import GroundingRejected
from varyn.learning_kernel import LearningKernel
from varyn.local_evaluation_receipts import LocalEvaluationReceipts, ReceiptRejected
from varyn.model_registry import Offer, Registry
from varyn.owner_live_evaluation import (
    OwnerReviewedLiveEvaluation, PUBLIC_CASE_REPOSITORIES,
    LiveEvaluationRejected)
from varyn.public_github_tool import PublicGithubToolGateway
from varyn.universal_gateway import UniversalGateway
from varyn.usage_budget import UsageBudget
from varyn.verified_failure_feedback import VerifiedFailureLedger


def source(repo):
    index = PUBLIC_CASE_REPOSITORIES.index(repo)
    return {
        "format": "varyn.github_public_repo_metadata.v1",
        "repository": repo, "default_branch": "main",
        "stars": 10 + index, "open_items_including_prs": index + 1,
        "archived": False, "public": True, "read_only": True,
        "untrusted_external_data": True, "provider_handoff": False,
    }


class ReceiptIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.path = Path(self.tmp.name) / "learning.sqlite3"
        self.kernel = LearningKernel(self.path)
        self.ledger = LocalEvaluationReceipts(self.kernel)
        for i in (1, 2):
            self.kernel.record_verified_outcome(
                "github_public_facts", "real-receipt-task-" + str(i),
                format(i, "064x"), succeeded=True, verified_by_host=True)
        VerifiedFailureLedger(self.kernel).record(
            "a" * 32, GroundingRejected("Model fact does not match observation"),
            {"network_dispatched": True, "status": "completed",
             "result": source(PUBLIC_CASE_REPOSITORIES[0])},
            owner_opted_in=True)

        self.provider_mode = "improve"
        def transport(provider, payload, key, timeout):
            assert key == "synthetic-session-key-12345"
            request = json.loads(payload["messages"][0]["content"])
            facts = dict(request["public_metadata_untrusted_data"])
            hint = request["optional_untrusted_procedural_hint"]
            if self.provider_mode == "improve" and not hint and (
                    facts["repository"] == PUBLIC_CASE_REPOSITORIES[0]):
                facts["stars"] += 1
            if self.provider_mode == "none":
                response_model = None
            else:
                response_model = "test-model"
            reply = {
                "choices": [{"message": {"role": "assistant", "content":
                    json.dumps({"action": "finish", "facts": facts})},
                    "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 62, "completion_tokens": 25},
            }
            if response_model is not None:
                reply["model"] = response_model
            return json.dumps(reply).encode("utf-8")
        offer = Offer(
            "openrouter", "test-model", 0, 0,
            date.today().isoformat(),
            owner_reviewed=True, route_fixed=True, enabled=True)
        self.budget = UsageBudget(
            max_requests=10, max_reserved_output_tokens=2560)
        self.gateway = UniversalGateway(
            Registry([offer]), allow_network=True,
            budget=self.budget, api_key="synthetic-session-key-12345",
            transport=transport)
        self.public_tool = PublicGithubToolGateway(
            fetcher=source, max_requests=5)
        self.worker = OwnerReviewedLiveEvaluation(
            self.gateway, self.public_tool, self.kernel)

    def tearDown(self):
        self.public_tool.close()
        self.kernel.close()
        self.tmp.cleanup()

    def execute(self, **kw):
        args = {
            "provider": "openrouter", "owner_enabled": True,
            "review_tool": lambda _: True,
            "review_model": lambda _: True,
        }
        args.update(kw)
        return self.worker.run(**args)

    def test_success_is_quantified_and_receipt_survives_reopen(self):
        result = self.execute()
        self.assertEqual(result["status"], "promoted")
        self.assertEqual(
            (result["baseline_passes"], result["candidate_passes"],
             result["evaluated_cases"], result["regressions"]),
            (4, 5, 5, 0))
        self.assertEqual(result["provider_reported_input_tokens"], 620)
        self.assertEqual(result["provider_reported_output_tokens"], 250)
        self.assertEqual(result["responses_with_incomplete_usage"], 0)
        self.assertEqual(len(result["receipt_sha256"]), 64)
        record = self.ledger.latest()
        self.assertTrue(record["local_receipt_digest_matches"])
        self.assertEqual(record["model_requests_attempted"], 10)
        self.assertEqual(record["model_responses_succeeded"], 10)
        self.assertEqual(record["model_requests_failed_or_uncertain"], 0)
        self.assertEqual(record["status"], "completed")
        self.assertFalse(record["actual_provider_cost_known"])
        self.kernel.close()
        self.kernel = LearningKernel(self.path)
        self.ledger = LocalEvaluationReceipts(self.kernel)
        self.assertEqual(self.ledger.latest()["evidence_sha256"],
                         result["receipt_sha256"])

    def test_owner_declines_before_public_get(self):
        result = self.execute(review_tool=lambda _: False)
        self.assertEqual(result["status"], "public_read_denied")
        record = self.ledger.latest()
        self.assertEqual(record["status"], "declined")
        self.assertEqual(record["public_reads"], 0)
        self.assertEqual(record["model_requests_attempted"], 0)
        self.assertTrue(record["local_receipt_digest_matches"])
        self.assertIsNone(self.kernel.active_skill("github_public_facts"))

    def test_model_approval_declined_after_public_reads(self):
        with self.assertRaises(PermissionError):
            self.execute(review_model=lambda _: False)
        record = self.ledger.latest()
        self.assertEqual(record["status"], "needs_review")
        self.assertEqual(record["public_reads"], 5)
        self.assertEqual(record["model_requests_attempted"], 0)
        self.assertEqual(record["model_responses_succeeded"], 0)
        self.assertTrue(record["local_receipt_digest_matches"])

    def test_unverified_provider_identity_cannot_promote(self):
        self.provider_mode = "none"
        with self.assertRaises(LiveEvaluationRejected):
            self.execute()
        record = self.ledger.latest()
        self.assertEqual(record["status"], "needs_review")
        self.assertEqual(record["model_requests_attempted"], 1)
        self.assertEqual(record["model_responses_succeeded"], 1)
        self.assertTrue(record["local_receipt_digest_matches"])
        self.assertIsNone(self.kernel.active_skill("github_public_facts"))

    def test_tampered_record_is_flagged_not_silently_trusted(self):
        self.execute()
        original = self.ledger.latest()
        self.kernel.db.execute(
            "UPDATE live_evaluation_receipts SET candidate_passes=1 "
            "WHERE id=?", (original["id"],))
        self.assertFalse(self.ledger.latest()["local_receipt_digest_matches"])

    def test_no_conversation_or_secret_in_stored_record(self):
        self.execute()
        record = self.ledger.latest()
        rendered = json.dumps(record).lower()
        self.assertNotIn("synthetic-session-key-12345", rendered)
        self.assertNotIn("messages", rendered)
        self.assertNotIn("prompt", rendered)
        self.assertNotIn("private_data", rendered)
        self.assertEqual(len(record["model_sha256"]), 64)

    def test_crash_before_finish_does_not_claim_success(self):
        ident = self.ledger.begin(
            provider="openrouter", model="test-model",
            estimated_micro_usd=1000, explicit_session_approval=True)
        record = self.ledger.get(ident)
        self.assertEqual(record["status"], "running_or_interrupted")
        self.assertIsNone(record["evidence_sha256"])
        self.assertIsNone(record["local_receipt_digest_matches"])

    def test_caller_cannot_forge_quality_matrix_or_duplicate_finish(self):
        zero = {key: 0 for key in (
            "requests_reserved", "requests_succeeded",
            "requests_failed_or_uncertain", "reported_input_tokens",
            "reported_output_tokens", "responses_with_incomplete_usage")}
        with self.assertRaises(PermissionError):
            self.ledger.begin(
                provider="openrouter", model="test-model",
                estimated_micro_usd=0)
        ident = self.ledger.begin(
            provider="openrouter", model="test-model",
            estimated_micro_usd=0, explicit_session_approval=True)
        with self.assertRaises(ReceiptRejected):
            self.ledger.finish(
                ident, status="completed", before=zero,
                after=zero, public_reads=5, evaluated_cases=5,
                baseline_passes=4, candidate_passes=5,
                regressions=0, case_observations_sha256="b" * 64)
        saved = self.ledger.finish(
            ident, status="declined", before=zero, after=zero,
            public_reads=0)
        self.assertTrue(saved["local_receipt_digest_matches"])
        with self.assertRaises(ReceiptRejected):
            self.ledger.finish(
                ident, status="declined", before=zero,
                after=zero, public_reads=0)

    def test_no_approval_no_receipt(self):
        result = self.execute(owner_enabled=False)
        self.assertEqual(result["status"], "disabled")
        self.assertIsNone(self.ledger.latest())


if __name__ == "__main__":
    unittest.main()
