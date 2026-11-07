"""Red-team tests for a shareable, redacted real-PC acceptance report.

The report is NOT independent provider proof. These tests make sure that
fake/corrupted records do not turn into success or leak private values.
"""
from hashlib import sha256
import json
import unittest

from varyn.acceptance_share_report import (
    create_redacted_acceptance_report, render_redacted_acceptance_report)


def fixture(*, origin="injected_test_or_custom_transport"):
    row = {
        "id": "a" * 32,
        "utc_day": "2026-11-07",
        "started_utc": "2026-11-07T08:00:00+00:00",
        "finished_utc": "2026-11-07T08:00:01+00:00",
        "status": "verification_passed",
        "provider": "openrouter",
        "model_sha256": "b" * 64,
        "source_kind": origin,
        "estimated_micro_usd": 18,
        "public_reads_attempted": 1,
        "model_requests_attempted": 1,
        "fact_matches_tool": 1,
        "observation_sha256": "c" * 64,
        "provider_response_id_sha256": "d" * 64,
        "input_tokens_reported": 41,
        "output_tokens_reported": 39,
    }
    row["receipt_sha256"] = sha256(json.dumps(
        row, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    row["local_digest_matches"] = True
    row["raw_secret_for_test"] = (
        "sk-private-openrouter-secret-DO-NOT-EXPORT")
    row["local_private_path"] = "C:\\Users\\Someone\\Documents\\Private"
    row["untrusted_response"] = "user provided personal private content"
    row["billing_card_number"] = "4111111111111111"
    return row


class RedactedShareReportTests(unittest.TestCase):
    def test_empty_history_produces_plain_offline_no_record_status(self):
        data = create_redacted_acceptance_report(None)
        self.assertEqual(data["format"], "varyn.owner_acceptance_share.v1")
        self.assertFalse(data["local_smoke_record_found"])
        self.assertEqual(data["local_evidence_category"], "no_receipt")
        self.assertIsNone(data["public_gets_attempted"])
        self.assertIsNone(data["model_requests_attempted"])
        self.assertFalse(data["safe_to_enable_unattended_spend"])

    def test_synthetic_run_is_never_promoted_to_real_account_proof(self):
        data = create_redacted_acceptance_report(fixture())
        self.assertEqual(data["local_receipt_integrity"], "intact")
        self.assertEqual(data["smoke_status"], "verification_passed")
        self.assertEqual(data["local_evidence_category"],
                         "simulated_or_custom_transport")
        self.assertEqual(data["adapter_configuration"],
                         "injected_or_custom_adapter")
        self.assertEqual(data["public_gets_attempted"], 1)
        self.assertEqual(data["model_requests_attempted"], 1)
        self.assertTrue(data["fact_match_against_tool_observation"])
        self.assertTrue(data["provider_response_id_reported"])
        self.assertTrue(data["provider_input_output_usage_reported"])
        self.assertFalse(data["provider_account_independently_authenticated"])

    def test_configured_network_run_only_candidate_not_certified(self):
        data = create_redacted_acceptance_report(
            fixture(origin="configured_network_adapters"))
        self.assertEqual(data["local_evidence_category"],
                         "owner_live_candidate_needs_provider_account_check")
        self.assertFalse(data["actual_provider_charges_independently_verified"])
        self.assertFalse(data["safe_to_enable_unattended_spend"])

    def test_relabelled_mock_without_new_digest_fails_closed(self):
        row = fixture()
        row["source_kind"] = "configured_network_adapters"
        data = create_redacted_acceptance_report(row)
        self.assertEqual(data["local_evidence_category"], "receipt_untrusted")
        self.assertEqual(data["smoke_status"], "unknown")
        self.assertEqual(data["adapter_configuration"], "unknown")
        self.assertIsNone(data["model_requests_attempted"])
        self.assertEqual(data["local_receipt_integrity"], "not_verified")

    def test_incomplete_and_interrupted_history_not_proven(self):
        row = fixture()
        row["status"] = "running_or_interrupted"
        row["local_digest_matches"] = None
        row["receipt_sha256"] = None
        data = create_redacted_acceptance_report(row)
        self.assertEqual(data["local_evidence_category"], "receipt_untrusted")
        self.assertIsNone(data["provider_response_id_reported"])
        self.assertEqual(data["smoke_status"], "unknown")

    def test_privacy_no_credentials_account_dates_hashes_or_source_text(self):
        row = fixture()
        rendered = render_redacted_acceptance_report(row)
        for sensitive in (
            "sk-private-openrouter-secret", "4111111111111111",
            "C:\\Users\\Someone", "personal private content",
            "2026-11-07", "b" * 64, "c" * 64, "d" * 64,
            "raw_secret_for_test", "billing_card_number", "request_id",
            "estimated_micro_usd", "user_message", "prompt",
        ):
            self.assertNotIn(sensitive, rendered)
        output = json.loads(rendered)
        self.assertEqual(output["provider"], "openrouter")
        self.assertFalse(output["model_weights_independently_attested"])

    def test_corrupted_or_untrusted_fields_dont_raise_or_become_proof(self):
        row = fixture()
        row["source_kind"] = ["configured_network_adapters"]
        row["provider"] = ["openrouter"]
        row["status"] = ["verification_passed"]
        row["local_digest_matches"] = True
        report = create_redacted_acceptance_report(row)
        self.assertEqual(report["local_evidence_category"], "receipt_untrusted")
        self.assertEqual(report["provider"], "unknown")
        self.assertIsNone(report["fact_match_against_tool_observation"])


if __name__ == "__main__":
    unittest.main()
