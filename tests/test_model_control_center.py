"""17S-40: exact owner quote, cost review, and hard permission-contract tests."""
from datetime import date, timedelta
from decimal import Decimal
import json
import unittest

from varyn.model_control_center import (
    ModelCenterRejected, price_to_micro, create_reviewed_offer,
    build_exact_preview,
)
from varyn.model_registry import Registry, RegistryRejected


class CenterContractTests(unittest.TestCase):
    def test_exact_usd_prices_do_not_round_silently(self):
        self.assertEqual(price_to_micro("0"), 0)
        self.assertEqual(price_to_micro("0.10"), 100000)
        self.assertEqual(price_to_micro("1.125001"), 1125001)
        self.assertEqual(price_to_micro("10000"), 10000000000)
        for value in ("", "0.0000001", "-0.1", "nan", "Infinity",
                      "1e100", "10000.01", "abc", "0,5", "1 2"):
            with self.subTest(value=value), self.assertRaises(ModelCenterRejected):
                price_to_micro(value)

    def test_owner_price_and_fixed_route_flags_required(self):
        args = {
            "provider": "openrouter", "model": "free/free-id",
            "input_usd": "0", "output_usd": "0",
            "date_text": date.today().isoformat(),
        }
        with self.assertRaises(ModelCenterRejected):
            create_reviewed_offer(**args, reviewed=False, fixed=True)
        with self.assertRaises(ModelCenterRejected):
            create_reviewed_offer(**args, reviewed=True, fixed=False)
        allowed = create_reviewed_offer(**args, reviewed=True, fixed=True)
        self.assertTrue(allowed.owner_reviewed)
        self.assertTrue(allowed.route_fixed)
        self.assertTrue(allowed.enabled)
        self.assertEqual(allowed.model, "free/free-id")
        self.assertEqual(
            Registry([allowed]).choose(
                input_estimate=100, output_limit=128,
                ceiling_micro_usd=0, today=date.today(),
            )[0], allowed,
        )

    def test_preview_show_exact_quote_but_no_credentials_or_sync(self):
        offer = create_reviewed_offer(
            provider="9router", model="glm/demo",
            input_usd="0.15", output_usd="0.55",
            date_text=date.today().isoformat(),
            reviewed=True, fixed=True,
        )
        content = build_exact_preview(
            offer, "SYNTHETIC: something fictional", 120, 256, 160,
        )
        result = json.loads(content)
        self.assertEqual(result["model"], "glm/demo")
        self.assertEqual(result["provider"], "9router")
        self.assertEqual(result["maximum_ESTIMATED_USD"], "0.00016")
        self.assertEqual(result["max_output_tokens"], 256)
        self.assertIn("switch UPSTREAM", result["warning"])
        self.assertIs(result["native_consumer_memory_sync"], False)
        self.assertIs(result["provider_price_independently_verified"], False)
        self.assertIs(result["actual_bill_hard_cap"], False)
        self.assertNotIn("api_key", content.lower())

    def test_stale_quote_fails_even_if_owner_checked(self):
        offer = create_reviewed_offer(
            provider="deepseek", model="deepseek-chat",
            input_usd="0.01", output_usd="0.02",
            date_text=(date.today() - timedelta(days=31)).isoformat(),
            reviewed=True, fixed=True,
        )
        with self.assertRaises(RegistryRejected):
            Registry([offer]).choose(
                input_estimate=50, output_limit=100,
                ceiling_micro_usd=10000, today=date.today(),
            )


if __name__ == "__main__":
    unittest.main()
