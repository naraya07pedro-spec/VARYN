"""No-network, end-to-end acceptance tests for the real gateway contract.

The transport and public GitHub responses are injected. No owner API key or
external account is accessed in GitHub Actions.
"""
from datetime import date
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import unittest

from varyn.learning_kernel import LearningKernel
from varyn.model_registry import Offer, Registry
from varyn.owner_provider_acceptance import OwnerProviderAcceptance, SmokeRejected
from varyn.public_github_tool import PublicGithubToolGateway
from varyn.universal_gateway import UniversalGateway
from varyn.usage_budget import UsageBudget


OBSERVED = {
    "format": "varyn.github_public_repo_metadata.v1",
    "repository": "python/cpython", "default_branch": "main",
    "stars": 1234, "open_items_including_prs": 99, "archived": False,
    "public": True, "read_only": True,
    "untrusted_external_data": True, "provider_handoff": False,
}


class ProviderAcceptanceSmokeTests(unittest.TestCase):
    def setUp(self):
        self.dir = TemporaryDirectory()
        self.path = Path(self.dir.name) / "learning.sqlite3"
        self.kernel = LearningKernel(self.path)
        self.public_gets = []
        self.model_requests = []
        self.mode = "match"

        def transport(provider, payload, key, timeout):
            self.assertEqual(key, "synthetic-test-credential-only")
            self.model_requests.append(payload)
            p = json.loads(payload["messages"][0]["content"])
            fields = dict(p["public_metadata_untrusted_data"])
            if self.mode == "mismatch":
                fields["stars"] += 1
            if self.mode == "exception":
                raise TimeoutError("network uncertain")
            result = {
                "id": "eval-test-response-a001",
                "model": ("wrong-upstream" if self.mode == "wrong_model" else "mock-model"),
                "choices": [{"message": {"role": "assistant",
                             "content": json.dumps({"action": "finish", "facts": fields})},
                             "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 91, "completion_tokens": 48},
            }
            if self.mode == "missing_model":
                del result["model"]
            return json.dumps(result).encode()

        model = Offer(
            "openrouter", "mock-model", 0, 0, date.today().isoformat(),
            owner_reviewed=True, route_fixed=True, enabled=True)
        self.budget = UsageBudget(
            max_requests=1, max_reserved_output_tokens=256)
        self.gateway = UniversalGateway(
            Registry([model]), budget=self.budget, allow_network=True,
            api_key="synthetic-test-credential-only",
            transport=transport)
        self.tool = PublicGithubToolGateway(
            max_requests=1,
            fetcher=lambda repo: self.public_gets.append(repo) or dict(OBSERVED))
        self.acceptance = OwnerProviderAcceptance(
            self.gateway, self.tool, self.kernel)

    def tearDown(self):
        self.tool.close()
        self.kernel.close()
        self.dir.cleanup()

    def run_approved(self, **changes):
        kwargs = {
            "provider": "openrouter", "owner_enabled": True,
            "review_tool": lambda p: True,
            "review_model": lambda p: True,
        }
        kwargs.update(changes)
        return self.acceptance.run(**kwargs)

    def test_optin_defaults_off_and_saves_nothing(self):
        res = self.run_approved(owner_enabled=False)
        self.assertEqual(res["status"], "disabled")
        self.assertEqual(self.public_gets, [])
        self.assertEqual(self.model_requests, [])
        self.assertIsNone(self.acceptance.latest())

    def test_one_public_get_and_one_model_request_only(self):
        seen = []
        res = self.run_approved(
            review_model=lambda p: seen.append(p) or True)
        self.assertEqual(res["status"], "verification_passed")
        self.assertEqual(res["public_reads_attempted"], 1)
        self.assertEqual(res["model_requests_attempted"], 1)
        self.assertEqual(self.public_gets, ["python/cpython"])
        self.assertEqual(len(self.model_requests), 1)
        self.assertEqual(len(seen), 1)
        self.assertEqual(self.budget.snapshot()["requests_reserved"], 1)
        self.assertTrue(res["local_digest_matches"])
        self.assertEqual(
            res["provider_response_id_sha256"],
            sha256(b"eval-test-response-a001").hexdigest())
        self.assertEqual(res["input_tokens_reported"], 91)
        self.assertEqual(res["output_tokens_reported"], 48)
        self.assertEqual(res["source_kind"], "injected_test_or_custom_transport")
        self.assertEqual(
            self.acceptance.acceptance_gate(res)["status"],
            "simulated_or_custom_transport")
        self.assertFalse(res["network_account_independently_verified"])
        self.assertFalse(res["provider_billing_verified"])

    def test_denied_read_never_dispatches(self):
        r = self.run_approved(review_tool=lambda _: False)
        self.assertEqual(r["status"], "approved_public_read_denied")
        self.assertEqual(self.public_gets, [])
        self.assertEqual(self.model_requests, [])
        self.assertTrue(r["local_digest_matches"])

    def test_denied_model_only_public_get(self):
        r = self.run_approved(review_model=lambda _: False)
        self.assertEqual(r["status"], "approved_model_request_denied")
        self.assertEqual(len(r["observation_sha256"]), 64)
        self.assertEqual(self.public_gets, ["python/cpython"])
        self.assertEqual(self.model_requests, [])
        self.assertTrue(r["local_digest_matches"])

    def test_wrong_public_facts_are_verification_failed_not_success(self):
        self.mode = "mismatch"
        r = self.run_approved()
        self.assertEqual(r["status"], "verification_failed")
        self.assertEqual(r["fact_matches_tool"], 0)
        self.assertEqual(len(r["observation_sha256"]), 64)
        self.assertEqual(self.kernel.db.execute(
            "SELECT COUNT(*) FROM outcomes").fetchone()[0], 0)

    def test_failed_fact_carries_exact_same_observation_hash_as_success(self):
        import json
        fail = self.run_approved(
            review_model=lambda _: False)
        # Because one session/day is already reserved, use source snapshot
        # from the existing denied-model read and compare canonical hash.
        selected = {key: OBSERVED[key] for key in (
            "repository", "default_branch", "stars",
            "open_items_including_prs", "archived")}
        digest = sha256(json.dumps(
            selected, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        self.assertEqual(fail["observation_sha256"], digest)

    def test_private_helper_cannot_mark_unverified_claim_passed(self):
        current = self.acceptance.preflight(provider="openrouter")
        ident = self.acceptance._begin(
            provider="openrouter", model=current["model"],
            quoted=current["estimated_micro_usd"],
            now=__import__("datetime").datetime.now(
                __import__("datetime").timezone.utc))
        with self.assertRaises(SmokeRejected):
            self.acceptance._finish(
                ident, status="verification_passed",
                public_reads=1, model_requests=1,
                observation_sha256="a" * 64)
        with self.assertRaises(SmokeRejected):
            self.acceptance._finish(
                ident, status="verification_failed",
                public_reads=1, model_requests=1)
        self.assertEqual(self.acceptance.latest()["status"],
                         "running_or_interrupted")

    def test_pure_gate_never_claims_independently_proven_account(self):
        record = self.run_approved()
        forged = dict(record)
        forged["source_kind"] = "configured_network_adapters"
        fake = self.acceptance.acceptance_gate(forged)
        self.assertEqual(
            fake["status"], "owner_live_candidate_needs_provider_account_check")
        self.assertFalse(fake["real_account_proven"])
        self.assertFalse(fake["actual_provider_billing_verified"])
        self.assertFalse(fake["ready_for_unattended_autonomy"])
        forged["provider_response_id_sha256"] = None
        self.assertEqual(
            self.acceptance.acceptance_gate(forged)["status"],
            "provider_usage_evidence_incomplete")
        forged["local_digest_matches"] = False
        self.assertEqual(
            self.acceptance.acceptance_gate(forged)["status"],
            "receipt_untrusted")

    def test_upstream_identity_missing_or_wrong_must_not_claim_pass(self):
        for case in ("missing_model", "wrong_model"):
            with self.subTest(case=case):
                # Distinct local storage per case: one session/day.
                self.mode = case
                if self.acceptance.latest() is not None:
                    self.kernel.db.execute("DELETE FROM owner_provider_smoke")
                    self.budget = UsageBudget(
                        max_requests=1, max_reserved_output_tokens=256)
                    self.gateway.budget = self.budget
                    self.tool.close()
                    self.tool = PublicGithubToolGateway(
                        max_requests=1, fetcher=lambda repo: dict(OBSERVED))
                    self.acceptance = OwnerProviderAcceptance(
                        self.gateway, self.tool, self.kernel)
                with self.assertRaises(SmokeRejected):
                    self.run_approved()
                record = self.acceptance.latest()
                self.assertEqual(record["status"], "needs_review")
                self.assertEqual(record["model_requests_attempted"], 1)
                self.assertIsNone(record["fact_matches_tool"])

    def test_gateway_uncertainty_keeps_quota_and_never_retries(self):
        self.mode = "exception"
        with self.assertRaises(Exception):
            self.run_approved()
        status = self.acceptance.latest()
        self.assertEqual(status["status"], "needs_review")
        self.assertEqual(status["model_requests_attempted"], 1)
        self.assertEqual(self.budget.snapshot()["requests_reserved"], 1)
        self.assertEqual(self.acceptance.preflight(
            provider="openrouter")["status"], "already_attempted_today")
        again = self.run_approved()
        self.assertEqual(again["status"], "already_attempted_today")
        self.assertEqual(len(self.model_requests), 1)

    def test_restart_retains_receipt_and_daily_no_replay(self):
        r = self.run_approved()
        ident = r["id"]
        self.kernel.close()
        self.kernel = LearningKernel(self.path)
        other = OwnerProviderAcceptance(self.gateway, self.tool, self.kernel)
        stored = other.get(ident)
        self.assertEqual(stored["receipt_sha256"], r["receipt_sha256"])
        self.assertTrue(stored["local_digest_matches"])
        self.assertEqual(other.preflight(
            provider="openrouter")["status"], "already_attempted_today")

    def test_tampered_local_receipt_detected(self):
        r = self.run_approved()
        self.kernel.db.execute(
            "UPDATE owner_provider_smoke SET input_tokens_reported=999 "
            "WHERE id=?", (r["id"],))
        self.assertFalse(self.acceptance.latest()["local_digest_matches"])

    def test_concurrent_utc_day_reservation_denies_another_session(self):
        # Two independently configured callers cannot both reserve the day.
        info = self.acceptance.preflight(provider="openrouter")
        started = self.acceptance._begin(
            provider="openrouter", model=info["model"],
            quoted=info["estimated_micro_usd"],
            now=__import__("datetime").datetime.now(
                __import__("datetime").timezone.utc))
        self.assertIsNotNone(started)
        with self.assertRaises(SmokeRejected):
            self.acceptance._begin(
                provider="openrouter", model=info["model"],
                quoted=info["estimated_micro_usd"],
                now=__import__("datetime").datetime.now(
                    __import__("datetime").timezone.utc))
        self.assertEqual(self.acceptance.latest()["status"],
                         "running_or_interrupted")
        self.assertEqual(len(self.public_gets), 0)

    def test_no_leak_secrets_or_raw_provider_message_into_receipt(self):
        result = self.run_approved()
        data = json.dumps(result).lower()
        self.assertNotIn("synthetic-test-credential-only", data)
        self.assertNotIn("messages", data)
        self.assertNotIn("payload", data)
        self.assertNotIn("eval-test-response-a001", data)
        self.assertFalse(result["general_model_quality_verified"])


if __name__ == "__main__":
    unittest.main()
