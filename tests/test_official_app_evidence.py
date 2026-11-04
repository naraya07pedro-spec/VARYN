"""17H: source-backed manual capabilities never become automatic app sync."""
import io
import json
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from varyn.official_app_evidence import (
    official_app_evidence, all_official_app_evidence,
)
from varyn.official_sync import official_app_capability, main


class OfficialConsumerEvidenceTests(unittest.TestCase):
    def test_all_three_providers_remain_blocked_from_any_dispatch(self):
        for provider in ("chatgpt", "claude", "gemini"):
            with self.subTest(provider=provider):
                evidence = official_app_evidence(provider)
                self.assertFalse(evidence["automatic_bidirectional_consumer_sync"])
                self.assertFalse(evidence["model_api_proves_consumer_history_access"])
                self.assertFalse(evidence["manual_import_is_automatic_sync"])
                self.assertFalse(evidence["can_dispatch"])
                self.assertEqual(evidence["official_consumer_history_read_api"],
                                 "not_verified")
                self.assertEqual(evidence["official_consumer_history_write_api"],
                                 "not_verified")
                self.assertEqual(evidence["automatic_network_operations"], 0)

    def test_export_is_manual_in_all_three_applications(self):
        for provider in ("chatgpt", "claude", "gemini"):
            self.assertEqual(
                official_app_evidence(provider)["manual_export_status"],
                "documented_manual",
            )

    def test_chatgpt_reference_upload_does_not_restore_native_history(self):
        data = official_app_evidence("chatgpt")
        self.assertEqual(data["manual_chat_history_import_status"],
                         "reference_upload_not_restored_as_history")
        self.assertEqual(data["manual_memory_import_status"], "not_verified")

    def test_claude_memory_import_is_not_full_transcript_import(self):
        data = official_app_evidence("claude")
        self.assertEqual(data["manual_memory_import_status"],
                         "documented_experimental_manual")
        self.assertEqual(data["manual_chat_history_import_status"],
                         "documented_not_supported")

    def test_gemini_full_chat_import_is_documented_but_restricted(self):
        data = official_app_evidence("gemini")
        self.assertEqual(data["manual_chat_history_import_status"],
                         "documented_manual_with_eligibility")
        self.assertEqual(data["manual_memory_import_status"],
                         "documented_manual_with_eligibility")
        self.assertIn("age and region", data["limitations"])

    def test_official_documentation_urls_and_review_date(self):
        for row in all_official_app_evidence()["providers"]:
            self.assertEqual(row["reviewed_as_of"], "2026-11-04")
            self.assertTrue(all(url.startswith("https://")
                                for url in row["official_sources"]))
            self.assertGreaterEqual(len(row["official_sources"]), 2)

    def test_returns_fresh_source_list_without_cross_mutation(self):
        first = official_app_evidence("gemini")
        first["official_sources"].clear()
        self.assertGreater(len(official_app_evidence("gemini")["official_sources"]), 0)

    def test_rejects_unknown_type_ambiguous_case_and_injection(self):
        for value in (None, "ChatGPT", "gemini\n", "other", 5, False, []):
            with self.subTest(value=value), self.assertRaises(ValueError):
                official_app_evidence(value)

    def test_old_official_sync_capability_includes_new_evidence(self):
        for provider in ("chatgpt", "claude", "gemini"):
            report = official_app_capability(provider)
            self.assertFalse(report["can_dispatch"])
            self.assertFalse(report["automatic_two_way_sync_verified"])
            self.assertEqual(report["evidence"]["provider"], provider)
            self.assertFalse(
                report["evidence"]["automatic_bidirectional_consumer_sync"]
            )

    def test_cli_reports_providers_without_contacting_network(self):
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(main(["--provider", "gemini"]), 0)
        report = json.loads(output.getvalue())
        self.assertEqual(report["evidence"]["automatic_network_operations"], 0)
        self.assertFalse(report["evidence"]["can_dispatch"])


if __name__ == "__main__":
    unittest.main()
