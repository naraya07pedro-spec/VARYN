"""17S-46 focused contracts: opt-in real tasks, no hidden dispatch."""
from datetime import date
import unittest

from varyn.gateway_chat import prepare
from varyn.model_registry import Offer, Registry
from varyn.safety import SensitiveContentError
from varyn.universal_gateway import UniversalGateway
from varyn.usage_budget import UsageBudget


TASK = "Tolong jelaskan perbedaan webhook dan polling dalam 3 kalimat."


class RealTaskGateTests(unittest.TestCase):
    def _fake(self):
        offer = Offer(
            "fake", "fake-test", 0, 0, date.today().isoformat(),
            owner_reviewed=True, route_fixed=True, enabled=True,
        )
        budget = UsageBudget(max_requests=2)
        return UniversalGateway(Registry([offer]), budget=budget), budget

    def test_synthetic_remains_default_and_real_requires_explicit_flag(self):
        sample = prepare("fake-test", "SYNTHETIC: a harmless item.", max_tokens=32)
        self.assertEqual(sample["messages"][0]["content"], "SYNTHETIC: a harmless item.")
        with self.assertRaises(ValueError):
            prepare("fake-test", TASK, max_tokens=32)
        self.assertEqual(
            prepare("fake-test", TASK, max_tokens=32, allow_real_task=True)
            ["messages"][0]["content"], TASK,
        )
        for bad in ("", "   ", "x" * 4001, "text\x00nul"):
            with self.subTest(task=bad[:12]), self.assertRaises(ValueError):
                prepare("fake-test", bad, max_tokens=32, allow_real_task=True)

    def test_no_owner_consent_or_opt_in_means_zero_requests(self):
        gateway, budget = self._fake()
        with self.assertRaises(ValueError):
            gateway.generate(
                TASK, input_estimate=100, max_output_tokens=32,
                ceiling_micro_usd=0, approve_request=True,
            )
        with self.assertRaises(PermissionError):
            gateway.generate(
                TASK, input_estimate=100, max_output_tokens=32,
                ceiling_micro_usd=0, allow_real_task=True,
            )
        self.assertEqual(budget.snapshot()["requests_reserved"], 0)
        result = gateway.generate(
            TASK, input_estimate=100, max_output_tokens=32,
            ceiling_micro_usd=0, allow_real_task=True,
            approve_request=True,
        )
        self.assertEqual(result["reply"].provider, "fake")
        self.assertEqual(budget.snapshot()["requests_reserved"], 1)

    def test_obvious_secret_rejected_before_quota(self):
        gateway, budget = self._fake()
        with self.assertRaises(SensitiveContentError):
            gateway.generate(
                "Set my api_key=supersecret12345", input_estimate=100,
                max_output_tokens=32, ceiling_micro_usd=0,
                allow_real_task=True, approve_request=True,
            )
        self.assertEqual(budget.snapshot()["requests_reserved"], 0)


if __name__ == "__main__":
    unittest.main()
