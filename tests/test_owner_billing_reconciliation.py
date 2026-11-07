"""No-network tests for hashed ID capture and owner-supplied cost matching.

The CSV fixture is NOT an official authenticated provider invoice.
"""
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
from hashlib import sha256
import json
import unittest

from varyn.gateway_chat import reported_response_id
from varyn.grounded_github import GroundingRejected
from varyn.learning_kernel import LearningKernel
from varyn.local_evaluation_receipts import LocalEvaluationReceipts
from varyn.model_registry import Offer, Registry
from varyn.owner_billing_reconciliation import (
    OwnerBillingReconciliation, BillingReconciliationRejected)
from varyn.owner_live_evaluation import (
    OwnerReviewedLiveEvaluation, PUBLIC_CASE_REPOSITORIES)
from varyn.public_github_tool import PublicGithubToolGateway
from varyn.universal_gateway import UniversalGateway
from varyn.usage_budget import UsageBudget
from varyn.verified_failure_feedback import VerifiedFailureLedger


def github_record(repo):
    index = PUBLIC_CASE_REPOSITORIES.index(repo)
    return {
        "format": "varyn.github_public_repo_metadata.v1",
        "repository": repo, "default_branch": "main",
        "stars": index + 1, "open_items_including_prs": index,
        "archived": False, "public": True, "read_only": True,
        "untrusted_external_data": True, "provider_handoff": False,
    }


class BillingCorrelationTests(unittest.TestCase):
    def setUp(self):
        self.folder = TemporaryDirectory()
        self.path = Path(self.folder.name) / "learn.sqlite3"
        self.kernel = LearningKernel(self.path)
        self.receipts = LocalEvaluationReceipts(self.kernel)
        self.billing = OwnerBillingReconciliation(self.kernel)
        self.numbers = []
        self.omit_id = False
        self.duplicate_id = False
        self.count = 0

        def transport(provider, payload, key, timeout):
            self.count += 1
            fields = json.loads(payload["messages"][0]["content"])
            facts = dict(fields["public_metadata_untrusted_data"])
            if not fields["optional_untrusted_procedural_hint"] and (
                    facts["repository"] == PUBLIC_CASE_REPOSITORIES[0]):
                facts["stars"] += 1
            label = ("eval-response-0001" if self.duplicate_id
                     else "eval-response-%04d" % self.count)
            self.numbers.append(label)
            data = {
                "model": "test-model",
                "choices": [{"message": {"role": "assistant", "content":
                    json.dumps({"action": "finish", "facts": facts})},
                    "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 75, "completion_tokens": 30},
            }
            if not self.omit_id:
                data["id"] = label
            return json.dumps(data).encode("utf-8")

        offer = Offer("openrouter", "test-model", 0, 0,
                      date.today().isoformat(),
                      owner_reviewed=True, route_fixed=True, enabled=True)
        self.gateway = UniversalGateway(
            Registry([offer]), allow_network=True,
            budget=UsageBudget(
                max_requests=10, max_reserved_output_tokens=2560),
            transport=transport, api_key="synthetic-only-token")
        self.tool = PublicGithubToolGateway(
            max_requests=5, fetcher=github_record)
        self.worker = OwnerReviewedLiveEvaluation(
            self.gateway, self.tool, self.kernel)
        for i in range(2):
            self.kernel.record_verified_outcome(
                "github_public_facts", "task-" + str(i),
                format(i + 1, "064x"), succeeded=True,
                verified_by_host=True)
        VerifiedFailureLedger(self.kernel).record(
            "a" * 32, GroundingRejected("Model fact does not match observation"),
            {"status": "completed", "network_dispatched": True,
             "result": github_record(PUBLIC_CASE_REPOSITORIES[0])},
            owner_opted_in=True)

    def tearDown(self):
        self.tool.close()
        self.kernel.close()
        self.folder.cleanup()

    def live(self):
        return self.worker.run(
            provider="openrouter", owner_enabled=True,
            review_model=lambda _: True, review_tool=lambda _: True)

    def csv(self, *, missing=False, more=False):
        labels = self.numbers[:10]
        if missing:
            labels[-1] = "someone-elses-request"
        lines = ["request_id,charged_micro_usd"]
        lines += [name + "," + str(index + 1)
                  for index, name in enumerate(labels)]
        if more:
            lines.append("extra-request-id,1")
        return "\n".join(lines) + "\n"

    def test_exact_ten_provider_ids_match_owner_supplied_rows(self):
        result = self.live()
        self.assertEqual(result["status"], "promoted")
        self.assertEqual(len(self.numbers), 10)
        session_id = result["receipt_id"]
        stored = [row[0] for row in self.kernel.db.execute(
            "SELECT response_id_sha256 FROM live_provider_response_fingerprints "
            "WHERE session_id=?", (session_id,))]
        self.assertEqual(len(stored), 10)
        self.assertEqual(set(stored), {
            sha256(i.encode()).hexdigest() for i in self.numbers})
        csv_text = self.csv()
        preview = self.billing.preview(session_id, csv_text)
        self.assertEqual(preview["status"], "ready_for_owner_review")
        self.assertEqual(preview["owner_reported_total_micro_usd"], 55)
        self.assertFalse(preview["provider_account_verified"])
        with self.assertRaises(PermissionError):
            self.billing.reconcile(session_id, csv_text)
        saved = self.billing.reconcile(
            session_id, csv_text, owner_approved=True)
        self.assertEqual(saved["matched_response_ids"], 10)
        self.assertTrue(saved["local_checksum_matches"])
        self.assertFalse(saved["actual_provider_cost_independently_verified"])
        self.assertTrue(saved["owner_supplied_data_only"])
        self.assertEqual(saved["difference_micro_usd"], 55)
        self.kernel.close()
        self.kernel = LearningKernel(self.path)
        self.billing = OwnerBillingReconciliation(self.kernel)
        self.assertTrue(self.billing.get(session_id)["local_checksum_matches"])
        self.assertFalse(
            LocalEvaluationReceipts(self.kernel).get(session_id)[
                "actual_provider_cost_known"])

    def test_mismatched_csv_ids_rejected_without_stored_comparison(self):
        result = self.live()
        ident = result["receipt_id"]
        preview = self.billing.preview(ident, self.csv(missing=True))
        self.assertEqual(preview["status"], "id_mismatch")
        self.assertEqual(preview["matched_count"], 9)
        with self.assertRaises(BillingReconciliationRejected):
            self.billing.reconcile(
                ident, self.csv(missing=True), owner_approved=True)
        self.assertIsNone(self.billing.get(ident))

    def test_duplicate_and_extra_rows_rejected(self):
        ident = self.live()["receipt_id"]
        content = self.csv()
        with self.assertRaises(BillingReconciliationRejected):
            self.billing.preview(ident, self.csv(more=True))
        with self.assertRaises(BillingReconciliationRejected):
            self.billing.preview(
                ident, content.replace(self.numbers[-1], self.numbers[0]))
        with self.assertRaises(BillingReconciliationRejected):
            self.billing.preview(ident, content.replace(
                "1\n", "-5\n"))
        with self.assertRaises(BillingReconciliationRejected):
            self.billing.preview(
                ident, "=SUM(A1:A9),1\n" + content)
        self.assertIsNone(self.billing.get(ident))

    def test_missing_response_ids_cannot_look_like_verified_billing(self):
        self.omit_id = True
        outcome = self.live()
        self.assertEqual(outcome["status"], "promoted")
        with self.assertRaises(BillingReconciliationRejected):
            self.billing.preview(outcome["receipt_id"], self.csv())

    def test_duplicate_provider_id_aborts_and_keeps_failure_receipt(self):
        self.duplicate_id = True
        with self.assertRaises(BillingReconciliationRejected):
            self.live()
        record = self.receipts.latest()
        self.assertEqual(record["status"], "needs_review")
        self.assertIsNone(self.billing.get(record["id"]))
        self.assertEqual(self.kernel.db.execute(
            "SELECT COUNT(*) FROM live_provider_response_fingerprints"
        ).fetchone()[0], 1)

    def test_csv_reconciliation_cannot_be_replaced(self):
        ident = self.live()["receipt_id"]
        csv_text = self.csv()
        self.billing.reconcile(ident, csv_text, owner_approved=True)
        with self.assertRaises(BillingReconciliationRejected):
            self.billing.reconcile(ident, csv_text, owner_approved=True)

    def test_tampered_comparison_fails_local_checksum(self):
        ident = self.live()["receipt_id"]
        self.billing.reconcile(ident, self.csv(), owner_approved=True)
        self.kernel.db.execute(
            "UPDATE owner_billing_reconciliation "
            "SET owner_reported_total_micro_usd=100 WHERE session_id=?",
            (ident,))
        self.assertFalse(self.billing.get(ident)["local_checksum_matches"])

    def test_no_real_bill_authenticated_or_provider_spend_cap(self):
        ident = self.live()["receipt_id"]
        saved = self.billing.reconcile(
            ident, self.csv(), owner_approved=True)
        self.assertFalse(saved["provider_account_verified"])
        self.assertFalse(saved["spend_hard_cap_enforced"])
        self.assertFalse(saved["actual_provider_cost_independently_verified"])
        self.assertFalse(saved["raw_csv_stored"])
        self.assertFalse(saved["raw_response_ids_stored"])
        dump = str([dict(row) for row in self.kernel.db.execute(
            "SELECT * FROM owner_billing_reconciliation")])
        for label in self.numbers:
            self.assertNotIn(label, dump)

    def test_malformed_response_ids_never_count_as_billing_proof(self):
        for raw in (
            b'{"id":"eval-ok-0001"}',
            b'{"id":"https://example.com"}',
            b'{"id":5}',
            b'{"id":"=INJECT"}',
            b'{"id":"a\\nb"}',
        ):
            value = reported_response_id(raw)
            if raw == b'{"id":"eval-ok-0001"}':
                self.assertIsNotNone(value)
            else:
                self.assertIsNone(value)


if __name__ == "__main__":
    unittest.main()
