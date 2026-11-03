"""Offline usage-budget regressions."""
import unittest
from concurrent.futures import ThreadPoolExecutor

from varyn.multi_provider import ProviderRouter
from varyn.providers import ModelReply, ProviderError
from varyn.usage_budget import BudgetedRouter, BudgetExceeded, UsageBudget


class UsageBudgetTests(unittest.TestCase):
    def test_request_cap(self):
        budget = UsageBudget(max_requests=1)
        router = BudgetedRouter(ProviderRouter(), budget)
        router.generate("fake", "hi", model="fake-test", max_output_tokens=16)
        with self.assertRaises(BudgetExceeded):
            router.generate("fake", "hi", model="fake-test", max_output_tokens=16)
        self.assertEqual(budget.snapshot()["requests_reserved"], 1)

    def test_reserved_output_token_cap(self):
        budget = UsageBudget(max_requests=5, max_reserved_output_tokens=32)
        router = BudgetedRouter(ProviderRouter(), budget)
        router.generate("fake", "hi", model="fake-test", max_output_tokens=32)
        with self.assertRaises(BudgetExceeded):
            router.generate("fake", "hi", model="fake-test", max_output_tokens=16)
        self.assertEqual(budget.snapshot()["output_tokens_reserved"], 32)

    def test_invalid_input_does_not_reserve(self):
        budget = UsageBudget()
        router = BudgetedRouter(ProviderRouter(), budget)
        with self.assertRaises(ValueError):
            router.generate("fake", "", model="fake-test")
        with self.assertRaises(ValueError):
            router.generate("unsupported", "hi", model="fake-test")
        self.assertEqual(budget.snapshot()["requests_reserved"], 0)

    def test_context_consent_preflight(self):
        budget = UsageBudget()
        context = {"format": "varyn.context.v1", "items": []}
        with self.assertRaises(PermissionError):
            BudgetedRouter(ProviderRouter(), budget).generate(
                "fake", "hi", model="fake-test", context=context
            )
        self.assertEqual(budget.snapshot()["requests_reserved"], 0)

    def test_failures_consume_reservation(self):
        budget = UsageBudget(max_requests=1)
        router = BudgetedRouter(ProviderRouter(), budget)
        with self.assertRaises(PermissionError):
            router.generate("openai", "hi", model="demo-model", max_output_tokens=16)
        self.assertEqual(budget.snapshot()["requests_failed_or_uncertain"], 1)
        with self.assertRaises(BudgetExceeded):
            router.generate("fake", "hi", model="fake-test", max_output_tokens=16)

    def test_provider_failure_no_retry(self):
        calls = []
        class Failing:
            def generate(self, *args, **kwargs):
                calls.append(1)
                raise ProviderError("not available")
        budget = UsageBudget()
        router = BudgetedRouter(
            ProviderRouter(providers={"fake": Failing()}), budget
        )
        with self.assertRaises(ProviderError):
            router.generate("fake", "hi", model="demo")
        self.assertEqual(calls, [1])
        self.assertEqual(budget.snapshot()["requests_failed_or_uncertain"], 1)

    def test_usage_counts_only(self):
        class Counting:
            def generate(self, *args, **kwargs):
                return ModelReply("test result", "fake", "demo", {
                    "input_tokens": 7, "output_tokens": 3,
                })
        budget = UsageBudget()
        router = BudgetedRouter(ProviderRouter(providers={"fake": Counting()}), budget)
        router.generate("fake", "hi", model="demo")
        state = budget.snapshot()
        self.assertEqual(state["reported_input_tokens"], 7)
        self.assertEqual(state["reported_output_tokens"], 3)
        self.assertNotIn("test result", str(state))
        self.assertIsNone(state["estimated_or_actual_cost"])

    def test_missing_usage_marked(self):
        budget = UsageBudget()
        BudgetedRouter(ProviderRouter(), budget).generate(
            "fake", "hi", model="fake-test"
        )
        self.assertEqual(budget.snapshot()["responses_with_incomplete_usage"], 1)

    def test_parallel_reservations_atomic(self):
        budget = UsageBudget(max_requests=12, max_reserved_output_tokens=192)
        def attempt(_):
            try:
                budget.reserve(16)
                return True
            except BudgetExceeded:
                return False
        with ThreadPoolExecutor(max_workers=12) as pool:
            outcome = list(pool.map(attempt, range(60)))
        self.assertEqual(sum(outcome), 12)
        self.assertEqual(budget.snapshot()["output_tokens_reserved"], 192)

    def test_invalid_limits(self):
        for config in ({"max_requests": 0}, {"max_requests": True},
                       {"max_reserved_output_tokens": 15}):
            with self.assertRaises(ValueError):
                UsageBudget(**config)

    def test_not_persistent(self):
        one = UsageBudget()
        one.reserve(16)
        two = UsageBudget()
        self.assertEqual(two.snapshot()["requests_reserved"], 0)
        self.assertFalse(one.snapshot()["persistent"])


if __name__ == "__main__":
    unittest.main()
