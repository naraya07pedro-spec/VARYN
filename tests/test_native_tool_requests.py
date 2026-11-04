"""15B mock-only provider-native tool request integration tests."""
import json
import unittest
from unittest.mock import patch

from varyn.agent_runtime import AgentRejected
from varyn.desktop_approval import DesktopApprovalController
from varyn.native_tool_requests import NativeToolRequestClient, native_tool_payload
from varyn.providers import ProviderError
from varyn.usage_budget import UsageBudget, BudgetExceeded


def response(provider, *, name="stage_note", text="synthetic note"):
    if provider == "openai":
        return json.dumps({"status": "completed", "output": [
            {"type": "function_call", "name": name,
             "arguments": json.dumps({"text": text})}
        ]}).encode()
    if provider == "anthropic":
        return json.dumps({"type": "message", "stop_reason": "tool_use",
                           "content": [{"type": "tool_use", "name": name,
                                        "input": {"text": text}}]}).encode()
    if provider == "gemini":
        return json.dumps({"candidates": [{"finishReason": "STOP",
            "content": {"parts": [{"functionCall": {
                "name": name, "args": {"text": text},
            }}]}}]}).encode()
    raise AssertionError("fixture")


class NativeRequestTests(unittest.TestCase):
    def test_payloads_advertise_only_two_registered_tools(self):
        for provider in ("openai", "anthropic", "gemini"):
            with self.subTest(provider=provider):
                doc = native_tool_payload(provider, "synthetic-model", "demo")
                tools = (doc["tools"] if provider != "gemini"
                         else doc["tools"][0]["functionDeclarations"])
                self.assertEqual({t["name"] for t in tools},
                                 {"inspect_status", "stage_note"})
                self.assertNotIn("API_KEY", json.dumps(doc))
                self.assertNotIn("shell", json.dumps(doc))

    def test_openai_disables_parallel_and_storage(self):
        payload = native_tool_payload("openai", "test-model", "demo")
        self.assertFalse(payload["parallel_tool_calls"])
        self.assertFalse(payload["store"])
        self.assertEqual(payload["tool_choice"], "auto")
        self.assertTrue(all(x["strict"] for x in payload["tools"]))

    def test_anthropic_disables_parallel(self):
        payload = native_tool_payload("anthropic", "test-model", "demo")
        self.assertTrue(payload["tool_choice"]["disable_parallel_tool_use"])
        self.assertEqual(payload["tool_choice"]["type"], "auto")

    def test_gemini_uses_function_declarations_auto(self):
        payload = native_tool_payload("gemini", "test-model", "demo")
        self.assertEqual(payload["toolConfig"]["functionCallingConfig"]["mode"], "AUTO")
        self.assertEqual(len(payload["tools"]), 1)

    def test_default_network_denied_before_transport(self):
        calls = []
        client = NativeToolRequestClient(
            transport=lambda *args: calls.append(args))
        with self.assertRaises(PermissionError):
            client.propose("openai", "demo", model="test-model",
                           approval_controller=DesktopApprovalController(),
                           confirm_external_request=True)
        self.assertFalse(calls)
        self.assertEqual(client.budget.snapshot()["requests_reserved"], 0)

    def test_per_request_confirmation_denied(self):
        calls = []
        client = NativeToolRequestClient(
            allow_network=True,
            transport=lambda *args: calls.append(args))
        with self.assertRaises(PermissionError):
            client.propose("openai", "demo", model="test-model",
                           approval_controller=DesktopApprovalController())
        self.assertFalse(calls)
        self.assertEqual(client.budget.snapshot()["requests_reserved"], 0)

    def test_missing_key_denied_without_quota(self):
        client = NativeToolRequestClient(allow_network=True)
        with patch.dict("os.environ", {"OPENAI_API_KEY": ""}):
            with self.assertRaises(ProviderError):
                client.propose("openai", "demo", model="test-model",
                               approval_controller=DesktopApprovalController(),
                               confirm_external_request=True)
        self.assertEqual(client.budget.snapshot()["requests_reserved"], 0)

    def test_three_providers_transport_and_stage_without_execution(self):
        for provider, keyname in (("openai", "OPENAI_API_KEY"),
                                  ("anthropic", "ANTHROPIC_API_KEY"),
                                  ("gemini", "GEMINI_API_KEY")):
            captured = []
            def transport(name, model, payload, key, timeout):
                captured.append((name, model, payload, key, timeout))
                return response(name)
            client = NativeToolRequestClient(
                allow_network=True, transport=transport)
            controller = DesktopApprovalController()
            with patch.dict("os.environ", {keyname: "synthetic-key"}):
                preview = client.propose(provider, "synthetic demo",
                    model="test-model", approval_controller=controller,
                    confirm_external_request=True)
            self.assertEqual(len(captured), 1)
            self.assertEqual(preview.tool, "stage_note")
            self.assertEqual(controller.status()["steps_used"], 0)
            self.assertEqual(controller.status()["stored_synthetic_notes"], 0)
            self.assertEqual(controller.status()["pending_approvals"], 1)
            self.assertEqual(client.budget.snapshot()["requests_reserved"], 1)

    def test_context_never_uploaded_even_when_valid(self):
        calls = []
        client = NativeToolRequestClient(
            allow_network=True, transport=lambda *args: calls.append(args))
        with self.assertRaises(PermissionError):
            client.propose("openai", "demo", model="test-model",
                approval_controller=DesktopApprovalController(),
                confirm_external_request=True,
                context={"format": "varyn.context.v1", "items": []})
        self.assertFalse(calls)

    def test_invalid_input_does_not_reserve(self):
        client = NativeToolRequestClient(allow_network=True)
        with self.assertRaises(ValueError):
            client.propose("openai", "", model="test-model",
                approval_controller=DesktopApprovalController(),
                confirm_external_request=True)
        with self.assertRaises(ValueError):
            client.propose("fake", "demo", model="test-model",
                approval_controller=DesktopApprovalController(),
                confirm_external_request=True)
        self.assertEqual(client.budget.snapshot()["requests_reserved"], 0)

    def test_failed_transport_consumes_quota_and_never_retries(self):
        calls = []
        def fail(*args):
            calls.append(1)
            raise TimeoutError("synthetic timeout")
        budget = UsageBudget(max_requests=1)
        client = NativeToolRequestClient(
            allow_network=True, transport=fail, budget=budget)
        with patch.dict("os.environ", {"OPENAI_API_KEY": "synthetic"}):
            with self.assertRaises(ProviderError):
                client.propose("openai", "demo", model="test-model",
                    approval_controller=DesktopApprovalController(),
                    confirm_external_request=True, max_output_tokens=16)
            with self.assertRaises(BudgetExceeded):
                client.propose("openai", "demo", model="test-model",
                    approval_controller=DesktopApprovalController(),
                    confirm_external_request=True, max_output_tokens=16)
        self.assertEqual(calls, [1])
        self.assertEqual(budget.snapshot()["requests_failed_or_uncertain"], 1)

    def test_malformed_provider_response_leaves_no_proposal(self):
        controller = DesktopApprovalController()
        client = NativeToolRequestClient(
            allow_network=True, transport=lambda *args: b"not json")
        with patch.dict("os.environ", {"OPENAI_API_KEY": "synthetic"}):
            with self.assertRaises(AgentRejected):
                client.propose("openai", "demo", model="test-model",
                    approval_controller=controller,
                    confirm_external_request=True)
        self.assertEqual(controller.status()["pending_approvals"], 0)
        self.assertEqual(client.budget.snapshot()["requests_failed_or_uncertain"], 1)

    def test_multiple_model_calls_rejected_without_execution(self):
        doc = json.loads(response("openai"))
        doc["output"] *= 2
        controller = DesktopApprovalController()
        client = NativeToolRequestClient(
            allow_network=True,
            transport=lambda *args: json.dumps(doc).encode())
        with patch.dict("os.environ", {"OPENAI_API_KEY": "synthetic"}):
            with self.assertRaises(AgentRejected):
                client.propose("openai", "demo", model="test-model",
                    approval_controller=controller,
                    confirm_external_request=True)
        self.assertEqual(controller.status()["steps_used"], 0)

    def test_oversized_response_rejected(self):
        client = NativeToolRequestClient(
            allow_network=True, transport=lambda *args: b"x" * 131073)
        with patch.dict("os.environ", {"OPENAI_API_KEY": "synthetic"}):
            with self.assertRaises(ProviderError):
                client.propose("openai", "demo", model="test-model",
                    approval_controller=DesktopApprovalController(),
                    confirm_external_request=True)

    def test_caller_explicitly_can_reject_proposal(self):
        controller = DesktopApprovalController()
        client = NativeToolRequestClient(
            allow_network=True, transport=lambda *args: response("openai"))
        with patch.dict("os.environ", {"OPENAI_API_KEY": "synthetic"}):
            preview = client.propose("openai", "demo", model="test-model",
                approval_controller=controller,
                confirm_external_request=True)
        controller.decide(preview.proposal_id, preview.digest, approved=False)
        self.assertEqual(controller.status()["stored_synthetic_notes"], 0)


if __name__ == "__main__":
    unittest.main()
