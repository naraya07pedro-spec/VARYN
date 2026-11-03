"""Headless desktop MVP tests. No Tk window, keys, models or network."""
import json
import unittest

from varyn.desktop_controller import (
    DesktopController, DEFAULT_MODELS, PROVIDERS,
)
from varyn.usage_budget import BudgetExceeded


class DesktopControllerTests(unittest.TestCase):
    def test_initial_state_denies_network_and_context(self):
        controller = DesktopController()
        state = controller.status()
        self.assertFalse(state["network_enabled"])
        self.assertFalse(state["requested_network_consent"])
        self.assertFalse(state["context_consent"])
        self.assertFalse(state["persistent"])
        self.assertFalse(state["monetary_budget_enforced"])

    def test_offline_fake_chat_works(self):
        controller = DesktopController()
        result = controller.send("test request")
        self.assertEqual(result.provider, "fake")
        self.assertEqual(result.model, "fake-test")
        self.assertEqual(result.mode, "offline_simulation")
        self.assertIn("FAKE", result.answer)
        self.assertEqual(controller.status()["requests_used"], 1)
        self.assertEqual(len(controller.history), 2)

    def test_real_providers_never_contacted_even_after_checkbox_consent(self):
        controller = DesktopController()
        controller.set_network_consent(True)
        controller.set_context_consent(True)
        for provider in ("openai", "anthropic", "gemini"):
            with self.subTest(provider=provider), self.assertRaises(PermissionError):
                controller.send("test", provider=provider, model="example")
        self.assertFalse(controller.status()["network_enabled"])
        self.assertEqual(controller.status()["requests_used"], 0)
        self.assertEqual(controller.history, ())

    def test_context_requires_explicit_permission(self):
        controller = DesktopController()
        context = {"format": "varyn.context.v1", "items": []}
        with self.assertRaises(PermissionError):
            controller.send("test", context=context)
        self.assertEqual(controller.status()["requests_used"], 0)
        controller.set_context_consent(True)
        result = controller.send("test", context=context)
        self.assertEqual(result.provider, "fake")

    def test_clear_history_does_not_refund_budget(self):
        controller = DesktopController()
        controller.send("test")
        controller.clear_history()
        self.assertEqual(controller.history, ())
        self.assertEqual(controller.status()["requests_used"], 1)

    def test_budget_enforced_via_ui_controller(self):
        controller = DesktopController(
            max_requests=1, max_reserved_output_tokens=256
        )
        controller.send("test")
        with self.assertRaises(BudgetExceeded):
            controller.send("second test")
        self.assertEqual(len(controller.history), 2)

    def test_invalid_message_does_not_change_history_or_quota(self):
        controller = DesktopController()
        for bad in ("", " " * 3, "x" * 4001):
            with self.subTest(length=len(bad)), self.assertRaises(ValueError):
                controller.send(bad)
        self.assertEqual(controller.history, ())
        self.assertEqual(controller.status()["requests_used"], 0)

    def test_unknown_provider_rejected_without_quota(self):
        controller = DesktopController()
        with self.assertRaises(ValueError):
            controller.send("test", provider="all")
        self.assertEqual(controller.status()["requests_used"], 0)

    def test_consent_requires_boolean(self):
        controller = DesktopController()
        with self.assertRaises(ValueError):
            controller.set_network_consent("yes")
        with self.assertRaises(ValueError):
            controller.set_context_consent(1)
        self.assertFalse(controller.status()["requested_network_consent"])

    def test_provider_menu_is_explicit_and_models_unconfigured(self):
        self.assertEqual(PROVIDERS, ("fake", "openai", "anthropic", "gemini"))
        self.assertEqual(DEFAULT_MODELS["fake"], "fake-test")
        for name in ("openai", "anthropic", "gemini"):
            self.assertEqual(DEFAULT_MODELS[name], "")

    def test_status_does_not_expose_chat(self):
        controller = DesktopController()
        controller.send("unique-synthetic-record")
        report = json.dumps(controller.status())
        self.assertNotIn("unique-synthetic-record", report)
        self.assertNotIn("FAKE", report)

    def test_new_instance_has_empty_ephemeral_state(self):
        a = DesktopController()
        a.send("test")
        b = DesktopController()
        self.assertEqual(b.history, ())
        self.assertEqual(b.status()["requests_used"], 0)

    def test_failed_real_selection_does_not_log_user_input(self):
        controller = DesktopController()
        with self.assertRaises(PermissionError):
            controller.send("do-not-log-this", provider="gemini", model="example")
        self.assertEqual(controller.history, ())


if __name__ == "__main__":
    unittest.main()
