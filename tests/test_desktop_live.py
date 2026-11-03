"""Live provider UI controller gates, tested without any network."""
import unittest
from varyn.desktop_controller import DesktopController
from varyn.providers import ModelReply, ProviderError


class SyntheticProvider:
    def __init__(self):
        self.calls = []
        self.fail = False

    def generate(self, question, *, model, context=None, max_output_tokens=256,
                 timeout_seconds=10, allow_context_upload=False):
        self.calls.append((question, model, context))
        if self.fail:
            raise ProviderError("Synthetic failure")
        return ModelReply("Synthetic response", "openai", model, {})


class LiveControllerTests(unittest.TestCase):
    def setUp(self):
        self.provider = SyntheticProvider()
        self.controller = DesktopController(
            allow_live_providers=True,
            providers={"fake": SyntheticProvider(), "openai": self.provider},
            max_requests=2,
        )

    def test_no_network_without_consent(self):
        with self.assertRaises(PermissionError):
            self.controller.send("hello", provider="openai", model="demo",
                                 confirm_live_request=True)
        self.assertEqual(self.provider.calls, [])

    def test_per_request_confirmation_required(self):
        self.controller.set_network_consent(True)
        with self.assertRaises(PermissionError):
            self.controller.send("hello", provider="openai", model="demo")
        self.assertEqual(self.provider.calls, [])

    def test_successful_explicit_live_call(self):
        self.controller.set_network_consent(True)
        result = self.controller.send(
            "hello", provider="openai", model="demo", confirm_live_request=True,
        )
        self.assertEqual(result.mode, "live_opt_in")
        self.assertEqual(len(self.provider.calls), 1)
        self.assertEqual(self.controller.status()["requests_used"], 1)

    def test_context_needs_separate_opt_in(self):
        self.controller.set_network_consent(True)
        context = {"format": "varyn.context.v1", "items": []}
        with self.assertRaises(PermissionError):
            self.controller.send("hello", provider="openai", model="demo",
                                 context=context, confirm_live_request=True)
        self.assertEqual(self.controller.status()["requests_used"], 0)
        self.controller.set_context_consent(True)
        self.controller.send("hello", provider="openai", model="demo",
                             context=context, confirm_live_request=True)
        self.assertEqual(self.provider.calls[-1][2], context)

    def test_failure_no_retry_and_no_history(self):
        self.provider.fail = True
        self.controller.set_network_consent(True)
        with self.assertRaises(ProviderError):
            self.controller.send("hello", provider="openai", model="demo",
                                 confirm_live_request=True)
        self.assertEqual(len(self.provider.calls), 1)
        self.assertEqual(self.controller.history, ())
        self.assertEqual(self.controller.status()["requests_used"], 1)

    def test_invalid_model_no_quota(self):
        self.controller.set_network_consent(True)
        with self.assertRaises(ValueError):
            self.controller.send("hello", provider="openai", model="",
                                 confirm_live_request=True)
        self.assertEqual(self.controller.status()["requests_used"], 0)

    def test_two_requests_use_full_local_budget(self):
        self.controller.set_network_consent(True)
        for _ in range(2):
            self.controller.send("hello", provider="openai", model="demo",
                                 confirm_live_request=True)
        with self.assertRaises(RuntimeError):
            self.controller.send("hello", provider="openai", model="demo",
                                 confirm_live_request=True)
        self.assertEqual(len(self.provider.calls), 2)

    def test_offline_default_preserved(self):
        offline = DesktopController()
        offline.set_network_consent(True)
        with self.assertRaises(PermissionError):
            offline.send("hello", provider="openai", model="demo",
                         confirm_live_request=True)

    def test_live_provider_injection_denied_when_offline(self):
        with self.assertRaises(ValueError):
            DesktopController(providers={
                "fake": SyntheticProvider(), "openai": SyntheticProvider(),
            })


if __name__ == "__main__":
    unittest.main()
