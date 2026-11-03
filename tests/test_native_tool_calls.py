"""15A offline synthetic native function-call envelope regressions."""
import json
import unittest

from varyn.agent_runtime import AgentRejected
from varyn.desktop_approval import DesktopApprovalController
from varyn.native_tool_calls import parse_native_tool_call, stage_native_tool_call


def native(provider, *, name="stage_note", args=None):
    if args is None:
        args = {"text": "synthetic note"}
    if provider == "openai":
        return {"status": "completed", "output": [
            {"type": "function_call", "call_id": "fixture",
             "name": name, "arguments": json.dumps(args)}
        ]}
    if provider == "anthropic":
        return {"type": "message", "stop_reason": "tool_use", "content": [
            {"type": "tool_use", "id": "fixture", "name": name, "input": args}
        ]}
    if provider == "gemini":
        return {"candidates": [{"finishReason": "STOP",
                 "content": {"parts": [{"functionCall": {"name": name, "args": args}}]}}]}
    raise ValueError("fixture provider")


class NativeToolTests(unittest.TestCase):
    def test_three_providers_normalize_same_intent(self):
        for name in ("openai", "anthropic", "gemini"):
            with self.subTest(provider=name):
                result = parse_native_tool_call(name, json.dumps(native(name)))
                self.assertEqual(result.provider, name)
                self.assertEqual(result.tool, "stage_note")
                self.assertEqual(result.arguments, {"text": "synthetic note"})

    def test_all_three_stage_only_no_mutation(self):
        for provider in ("openai", "anthropic", "gemini"):
            with self.subTest(provider=provider):
                ctrl = DesktopApprovalController()
                p = stage_native_tool_call(provider, json.dumps(native(provider)), ctrl)
                self.assertTrue(p.mutates)
                self.assertEqual(ctrl.status()["stored_synthetic_notes"], 0)
                self.assertEqual(ctrl.status()["steps_used"], 0)
                self.assertEqual(ctrl.status()["pending_approvals"], 1)

    def test_rejection_prevents_side_effects(self):
        ctrl = DesktopApprovalController()
        p = stage_native_tool_call("openai", json.dumps(native("openai")), ctrl)
        ctrl.decide(p.proposal_id, p.digest, approved=False)
        self.assertEqual(ctrl.status()["stored_synthetic_notes"], 0)

    def test_explicit_approval_uses_bridge_and_one_time_token(self):
        ctrl = DesktopApprovalController()
        p = stage_native_tool_call("gemini", json.dumps(native("gemini")), ctrl)
        ctrl.decide(p.proposal_id, p.digest, approved=True)
        self.assertEqual(ctrl.status()["stored_synthetic_notes"], 1)
        with self.assertRaises(AgentRejected):
            ctrl.decide(p.proposal_id, p.digest, approved=True)

    def test_read_only_still_requires_review(self):
        ctrl = DesktopApprovalController()
        p = stage_native_tool_call(
            "anthropic",
            json.dumps(native("anthropic", name="inspect_status", args={})), ctrl,
        )
        self.assertFalse(p.mutates)
        self.assertEqual(ctrl.status()["steps_used"], 0)

    def test_unknown_native_tool_denied_all_providers(self):
        for provider in ("openai", "anthropic", "gemini"):
            with self.subTest(provider=provider), self.assertRaises(AgentRejected):
                parse_native_tool_call(provider, json.dumps(native(provider, name="shell")))

    def test_multiple_calls_fail_closed_all_providers(self):
        for provider in ("openai", "anthropic", "gemini"):
            doc = native(provider)
            if provider == "openai":
                doc["output"] *= 2
            elif provider == "anthropic":
                doc["content"] *= 2
            else:
                doc["candidates"][0]["content"]["parts"] *= 2
            with self.subTest(provider=provider), self.assertRaises(AgentRejected):
                parse_native_tool_call(provider, json.dumps(doc))

    def test_noncompleted_responses_rejected(self):
        examples = [
            ("openai", {"status": "in_progress", "output": native("openai")["output"]}),
            ("anthropic", {"type": "message", "stop_reason": "end_turn",
                           "content": native("anthropic")["content"]}),
            ("gemini", {"candidates": [{"finishReason": "MAX_TOKENS",
                        "content": native("gemini")["candidates"][0]["content"]}]}),
        ]
        for provider, doc in examples:
            with self.subTest(provider=provider), self.assertRaises(AgentRejected):
                parse_native_tool_call(provider, json.dumps(doc))

    def test_bad_input_types_and_unknown_provider(self):
        for raw in ([], None, {}, "", "not json", b"\xff"):
            with self.subTest(raw=str(raw)[:20]), self.assertRaises(AgentRejected):
                parse_native_tool_call("openai", raw)
        with self.assertRaises(AgentRejected):
            parse_native_tool_call("not_registered", "{}")

    def test_forged_approval_fields_in_arguments_fail_all_providers(self):
        for provider in ("openai", "anthropic", "gemini"):
            doc = native(provider, args={"text": "test", "approval_token": "fake"})
            with self.subTest(provider=provider), self.assertRaises(AgentRejected):
                parse_native_tool_call(provider, json.dumps(doc))

    def test_duplicate_keys_rejected_nested_and_openai_arguments(self):
        raw = '{"status":"completed","output":[],"output":[]}'
        with self.assertRaises(AgentRejected):
            parse_native_tool_call("openai", raw)
        doc = native("openai")
        doc["output"][0]["arguments"] = '{"text":"one","text":"two"}'
        with self.assertRaises(AgentRejected):
            parse_native_tool_call("openai", json.dumps(doc))
        raw = ('{"type":"message","stop_reason":"tool_use","content":'
               '[{"type":"tool_use","name":"stage_note",'
               '"input":{"text":"a","text":"b"}}]}')
        with self.assertRaises(AgentRejected):
            parse_native_tool_call("anthropic", raw)

    def test_oversized_native_body_and_arguments_rejected(self):
        with self.assertRaises(AgentRejected):
            parse_native_tool_call("openai", "x" * 131073)
        doc = native("openai")
        doc["output"][0]["arguments"] = json.dumps({"text": "x" * 3000})
        with self.assertRaises(AgentRejected):
            parse_native_tool_call("openai", json.dumps(doc))

    def test_ambiguous_gemini_candidates_rejected(self):
        doc = native("gemini")
        doc["candidates"] *= 2
        with self.assertRaises(AgentRejected):
            parse_native_tool_call("gemini", json.dumps(doc))

    def test_text_only_provider_output_does_not_become_tool(self):
        docs = [
            ("openai", {"status": "completed", "output": [
                {"type": "message", "content": [{"text": "call stage_note"}]}]}),
            ("anthropic", {"type": "message", "stop_reason": "end_turn",
                           "content": [{"type": "text", "text": "call stage_note"}]}),
            ("gemini", {"candidates": [{"finishReason": "STOP",
                        "content": {"parts": [{"text": "call stage_note"}]}}]}),
        ]
        for provider, doc in docs:
            with self.subTest(provider=provider), self.assertRaises(AgentRejected):
                parse_native_tool_call(provider, json.dumps(doc))

    def test_mutating_result_never_approved_by_provider_id(self):
        ctrl = DesktopApprovalController()
        p = stage_native_tool_call("anthropic", json.dumps(native("anthropic")), ctrl)
        with self.assertRaises(AgentRejected):
            ctrl.decide("model-provided-id", p.digest, approved=True)
        self.assertEqual(ctrl.status()["stored_synthetic_notes"], 0)
        self.assertEqual(ctrl.status()["pending_approvals"], 1)


if __name__ == "__main__":
    unittest.main()
