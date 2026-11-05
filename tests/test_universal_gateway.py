"""17S-39 strict offline model registry, API boundaries, owner consent tests."""
import json
import os
from datetime import date, timedelta
import unittest
from unittest.mock import patch

from varyn.gateway_chat import URLS, KEY_ENVS, prepare, parse, post
from varyn.model_registry import Offer, Registry, RegistryRejected, offline_demo
from varyn.providers import ProviderError
from varyn.universal_gateway import UniversalGateway
from varyn.usage_budget import UsageBudget


TODAY = date(2026, 11, 5)
TASK = "SYNTHETIC: classify three imaginary test widgets."
KEY = "synthetic-fake-api-key-never-valid"


def offer(provider, model, *, price_in=1000000, price_out=2000000,
          days_old=0, reviewed=True, fixed=True, enabled=True):
    return Offer(provider, model, price_in, price_out,
                 (TODAY - timedelta(days=days_old)).isoformat(),
                 owner_reviewed=reviewed, route_fixed=fixed, enabled=enabled)


def response(text="synthetic API completion"):
    return json.dumps({
        "choices": [{"finish_reason": "stop",
                     "message": {"role": "assistant", "content": text}}],
        "usage": {"prompt_tokens": 18, "completion_tokens": 7},
    }).encode()


class RegistryTests(unittest.TestCase):
    def test_choose_cheapest_reviewed_and_free_with_real_slash_ids(self):
        choices = Registry([
            offer("deepseek", "deepseek-chat"),
            offer("openrouter", "openrouter/free", price_in=0, price_out=0),
            offer("9router", "glm/glm-4", price_in=500000, price_out=500000),
        ])
        winner, amount = choices.choose(input_estimate=100,
                                        output_limit=200, ceiling_micro_usd=0,
                                        today=TODAY)
        self.assertEqual((winner.provider, winner.model, amount),
                         ("openrouter", "openrouter/free", 0))
        paid, estimated = choices.choose(
            input_estimate=100, output_limit=200,
            ceiling_micro_usd=500, today=TODAY, provider="deepseek",
        )
        self.assertEqual(paid.provider, "deepseek")
        self.assertEqual(estimated, 500)

    def test_refuse_unknown_stale_unreviewed_or_unfixed_quotes(self):
        stale = offer("openrouter", "free", days_old=31, price_in=0,
                      price_out=0)
        for broken in (
            stale,
            offer("openrouter", "free", reviewed=False, price_in=0, price_out=0),
            offer("openrouter", "free", fixed=False, price_in=0, price_out=0),
            offer("openrouter", "free", enabled=False, price_in=0, price_out=0),
            Offer("openrouter", "free", enabled=True, route_fixed=True),
        ):
            with self.subTest(broken=broken), self.assertRaises(RegistryRejected):
                Registry([broken]).choose(
                    input_estimate=100, output_limit=128,
                    ceiling_micro_usd=1000, today=TODAY,
                )

    def test_bounded_registry_rejects_bad_prices_and_path_ids(self):
        with self.assertRaises(RegistryRejected):
            Registry([offer("deepseek", "demo"), offer("deepseek", "demo")])
        for name in ("../evil", "model?api_key=abc", "evil\nheader", "a//b"):
            with self.subTest(name=name), self.assertRaises(RegistryRejected):
                offer("deepseek", name)
        for value in (True, -1, 1.4, 10**11):
            with self.subTest(price=value), self.assertRaises(RegistryRejected):
                offer("deepseek", "demo", price_in=value)
        for bad in (True, 0, -1, "100"):
            with self.subTest(tokens=bad), self.assertRaises(RegistryRejected):
                Registry([offer("fake", "fake-test")]).choose(
                    input_estimate=bad, output_limit=32,
                    ceiling_micro_usd=1000, today=TODAY,
                )
        self.assertEqual(json.loads(offline_demo())["provider_requests"], 0)

    def test_price_is_estimate_not_spending_cap(self):
        x = Registry([offer("deepseek", "d", price_in=1000000,
                            price_out=4000000)])
        picked, estimated = x.choose(input_estimate=200, output_limit=100,
                                     ceiling_micro_usd=600, today=TODAY)
        self.assertEqual((picked.model, estimated), ("d", 600))
        with self.assertRaises(RegistryRejected):
            x.choose(input_estimate=200, output_limit=100,
                     ceiling_micro_usd=599, today=TODAY)


class ChatWireTests(unittest.TestCase):
    def test_pinned_urls_and_context_not_sent_implicitly(self):
        self.assertEqual(URLS["9router"], "http://127.0.0.1:20128/v1/chat/completions")
        self.assertEqual(URLS["deepseek"], "https://api.deepseek.com/chat/completions")
        self.assertEqual(URLS["openrouter"],
                         "https://openrouter.ai/api/v1/chat/completions")
        payload = prepare("openrouter/free", TASK, max_tokens=128)
        self.assertEqual(payload["model"], "openrouter/free")
        self.assertEqual(payload["messages"][0]["role"], "user")
        self.assertFalse(payload["stream"])
        self.assertNotIn("api_key", str(payload))
        with self.assertRaises(ValueError):
            prepare("model", "private, unlabeled", max_tokens=128)

    def test_parse_strict_complete_reply_reject_tool_calls(self):
        answer = parse("openrouter", "openrouter/free", response())
        self.assertEqual(answer.text, "synthetic API completion")
        self.assertEqual(answer.usage["input_tokens"], 18)
        self.assertEqual(answer.usage["output_tokens"], 7)
        for bad in (
            b"oops",
            json.dumps({"choices": []}).encode(),
            json.dumps({"choices": [{"finish_reason": "length",
                        "message": {"content": "partial"}}]}).encode(),
            json.dumps({"choices": [{"finish_reason": "stop",
                        "message": {"content": "text", "tool_calls": [
                            {"type": "function", "function": {"name": "delete"}}
                        ]}}]}).encode(),
            b"z" * 131073,
        ):
            with self.subTest(bad=bad[:25]), self.assertRaises(ProviderError):
                parse("openrouter", "demo", bad)

    def test_no_redirect_credentials_never_in_url(self):
        class Reply:
            def read(self, amount):
                return response()
            def __enter__(self):
                return self
            def __exit__(self, *_):
                return False
        calls = []
        class Opener:
            def open(self, request, timeout):
                calls.append((request, timeout))
                return Reply()
        with patch("varyn.gateway_chat.urllib.request.build_opener",
                   side_effect=lambda *h: Opener()) as mk:
            raw = post("openrouter", prepare("openrouter/free", TASK, max_tokens=64),
                       KEY, 7)
        self.assertEqual(raw, response())
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][0].full_url, URLS["openrouter"])
        self.assertNotIn(KEY, calls[0][0].full_url)
        self.assertEqual(calls[0][0].get_header("Authorization"), "Bearer " + KEY)
        self.assertIsNone(mk.call_args.args[0].redirect_request(
            None, None, 302, "Redirect", {}, "https://evil.example/"
        ))


class GatewayConsentTests(unittest.TestCase):
    def test_fake_offline_requires_owner_review_and_reserves_budget(self):
        fake = offer("fake", "fake-test", price_in=0, price_out=0)
        budget = UsageBudget(max_requests=1)
        gateway = UniversalGateway(Registry([fake]), budget=budget)
        with self.assertRaises(PermissionError):
            gateway.generate(TASK, input_estimate=30, max_output_tokens=32,
                             ceiling_micro_usd=0, today=TODAY)
        self.assertEqual(budget.snapshot()["requests_reserved"], 0)
        result = gateway.generate(
            TASK, input_estimate=30, max_output_tokens=32,
            ceiling_micro_usd=0, today=TODAY, approve_request=True,
        )
        self.assertEqual(result["reply"].provider, "fake")
        self.assertFalse(result["actual_billing_cap_enforced"])
        self.assertFalse(result["native_consumer_history_sync"])
        with self.assertRaises(Exception):
            gateway.generate(TASK, input_estimate=30, max_output_tokens=32,
                             ceiling_micro_usd=0, today=TODAY,
                             approve_request=True)

    def test_live_network_disabled_before_transport(self):
        calls = []
        x = UniversalGateway(
            Registry([offer("openrouter", "openrouter/free", price_in=0,
                            price_out=0)]),
            transport=lambda *args: calls.append(args),
        )
        with patch.dict(os.environ, {KEY_ENVS["openrouter"]: KEY}):
            with self.assertRaises(PermissionError):
                x.generate(TASK, input_estimate=30, max_output_tokens=32,
                           today=TODAY, approve_request=True)
        self.assertEqual(calls, [])
        self.assertEqual(x.budget.snapshot()["requests_reserved"], 0)

    def test_explicit_live_key_and_approval_each_call(self):
        calls = []
        def transport(provider, payload, key, timeout):
            calls.append((provider, payload, key, timeout))
            return response()
        gateway = UniversalGateway(
            Registry([offer("deepseek", "deepseek-chat", price_in=0,
                            price_out=0)]),
            allow_network=True, transport=transport,
            budget=UsageBudget(max_requests=2),
        )
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ProviderError):
                gateway.generate(TASK, input_estimate=30, max_output_tokens=32,
                                 today=TODAY, approve_request=True)
        with patch.dict(os.environ, {KEY_ENVS["deepseek"]: KEY}):
            with self.assertRaises(PermissionError):
                gateway.generate(TASK, input_estimate=30, max_output_tokens=32,
                                 today=TODAY)
            result = gateway.generate(TASK, input_estimate=30,
                                      max_output_tokens=32, today=TODAY,
                                      approve_request=True)
        self.assertEqual(result["reply"].provider, "deepseek")
        self.assertEqual(result["reply"].usage["input_tokens"], 18)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][2], KEY)
        self.assertEqual(gateway.budget.snapshot()["requests_reserved"], 1)
        self.assertNotIn(KEY, repr(result))

    def test_local_9router_upstream_requires_separate_approval(self):
        calls = []
        gateway = UniversalGateway(
            Registry([offer("9router", "glm/test", price_in=0, price_out=0)]),
            allow_network=True, transport=lambda *args: (
                calls.append(args) or response()
            ),
        )
        with patch.dict(os.environ, {KEY_ENVS["9router"]: KEY}):
            with self.assertRaises(PermissionError):
                gateway.generate(TASK, input_estimate=30, max_output_tokens=32,
                                 today=TODAY, approve_request=True)
            self.assertEqual(len(calls), 0)
            result = gateway.generate(
                TASK, input_estimate=30, max_output_tokens=32,
                today=TODAY, approve_request=True, authorized_upstream=True,
            )
        self.assertEqual(result["reply"].provider, "9router")
        self.assertEqual(len(calls), 1)

    def test_transport_failure_reserves_once_no_fallback_and_no_leaks(self):
        from urllib.error import URLError
        calls = []
        def transport(*args):
            calls.append(1)
            raise URLError("secret request")
        gateway = UniversalGateway(
            Registry([offer("openrouter", "openrouter/free", price_in=0,
                            price_out=0)]),
            allow_network=True, transport=transport,
            budget=UsageBudget(max_requests=2),
        )
        with patch.dict(os.environ, {KEY_ENVS["openrouter"]: KEY}):
            with self.assertRaises(ProviderError) as caught:
                gateway.generate(TASK, input_estimate=30, max_output_tokens=32,
                                 today=TODAY, approve_request=True)
        self.assertEqual(calls, [1])
        self.assertNotIn("secret", str(caught.exception))
        self.assertNotIn(KEY, str(caught.exception))
        self.assertEqual(
            gateway.budget.snapshot()["requests_failed_or_uncertain"], 1
        )


if __name__ == "__main__":
    unittest.main()
