"""17I: Option C must stay blocked absent reviewed consumer-history read/write."""
import io
import json
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from varyn.option_c_gate import (
    _REQUIRED, _PROVIDERS, full_option_c_gate, provider_option_c_gate, main,
)


class OptionCProofGateTests(unittest.TestCase):
    def test_each_official_app_is_blocked_with_seven_explicit_gates(self):
        for provider in _PROVIDERS:
            with self.subTest(provider=provider):
                row = provider_option_c_gate(provider)
                self.assertEqual(row["status"], "blocked_pending_provider_authority")
                self.assertEqual(len(row["requirements"]), 7)
                self.assertEqual(row["blocker_count"], 7)
                self.assertFalse(row["can_dispatch"])
                self.assertFalse(row["automatic_two_way_sync_verified"])
                self.assertEqual(row["requests_performed"], 0)

    def test_read_and_write_are_independent_unverified_gates(self):
        for provider in _PROVIDERS:
            x = provider_option_c_gate(provider)
            checks = {v["gate"]: v["status"] for v in x["requirements"]}
            self.assertEqual(checks["consumer_history_read_api"], "not_verified")
            self.assertEqual(checks["consumer_history_write_api"], "not_verified")
            self.assertFalse(x["official_consumer_history_read_verified"])
            self.assertFalse(x["official_consumer_history_write_verified"])

    def test_manual_gemini_import_does_not_unlock_two_way_sync(self):
        row = provider_option_c_gate("gemini")
        self.assertEqual(row["manual_history_import"],
                         "documented_manual_with_eligibility")
        self.assertEqual(row["blocker_count"], 7)
        self.assertFalse(row["model_api_can_substitute"])

    def test_manual_claude_memory_import_does_not_unlock_sync(self):
        row = provider_option_c_gate("claude")
        self.assertEqual(row["manual_memory_import"],
                         "documented_experimental_manual")
        self.assertFalse(row["can_dispatch"])

    def test_full_gate_requires_all_three_and_has_no_dispatch_path(self):
        report = full_option_c_gate()
        self.assertEqual(report["provider_count"], 3)
        self.assertEqual(report["providers_verified"], 0)
        self.assertEqual([r["provider"] for r in report["providers"]],
                         list(_PROVIDERS))
        self.assertFalse(report["automatic_bidirectional_three_app_sync"])
        self.assertFalse(report["can_dispatch"])

    def test_requirements_are_distinct_and_nonempty(self):
        names = [name for name, _ in _REQUIRED]
        self.assertEqual(len(set(names)), len(names))
        self.assertEqual(len(names), 7)
        self.assertTrue(all(description.strip() for _, description in _REQUIRED))

    def test_unknown_provider_and_type_injection_denied(self):
        for value in (None, 0, False, True, "ChatGPT", "chatgpt ", "gemini\n", []):
            with self.subTest(value=value), self.assertRaises(ValueError):
                provider_option_c_gate(value)

    def test_returned_proof_lists_are_not_shared(self):
        first = provider_option_c_gate("chatgpt")
        first["requirements"][0]["status"] = "verified"
        second = provider_option_c_gate("chatgpt")
        self.assertEqual(second["requirements"][0]["status"], "not_verified")
        self.assertFalse(second["can_dispatch"])

    def test_no_provider_calls_even_when_diags_print(self):
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(main([]), 0)
        record = json.loads(out.getvalue())
        self.assertEqual(record["provider_requests_performed"], 0)
        self.assertFalse(record["can_dispatch"])
        self.assertEqual(record["providers_verified"], 0)

    def test_per_provider_cli_prints_blocked_not_ready(self):
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(main(["--provider", "gemini"]), 0)
        data = json.loads(out.getvalue())
        self.assertEqual(data["blocker_count"], 7)
        self.assertEqual(data["provider"], "gemini")
        self.assertFalse(data["can_dispatch"])


if __name__ == "__main__":
    unittest.main()
