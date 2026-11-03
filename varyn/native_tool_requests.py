"""15B: opt-in native tool declaration requests, strictly proposal-only.

Never executes tools, grants approval, retries or sends tool results back.
This is a separate explicit path, preserving chat adapter behavior.
"""
import json
import os
import urllib.error

from varyn.providers import _validate, _RULES, _MAX_RESPONSE_BYTES, _post as openai_post, ProviderError
from varyn.multi_provider import _post as multi_post, _context_text
from varyn.native_tool_calls import stage_native_tool_call
from varyn.usage_budget import UsageBudget

_TOOLS = {
    "inspect_status": {
        "type": "object", "properties": {}, "required": [],
        "additionalProperties": False,
    },
    "stage_note": {
        "type": "object",
        "properties": {"text": {"type": "string", "description": "Synthetic note up to 200 characters"}},
        "required": ["text"], "additionalProperties": False,
    },
}
_DESCRIPTIONS = {
    "inspect_status": "Propose reading in-memory synthetic agent status; awaits review.",
    "stage_note": "Propose storing a synthetic RAM-only note; requires user review.",
}
_ENV = {"openai": "OPENAI_API_KEY", "anthropic": "ANTHROPIC_API_KEY", "gemini": "GEMINI_API_KEY"}


def native_tool_payload(provider, model, question, *, max_output_tokens=256):
    """Build official-shape JSON only; no network or user-secret handling."""
    _validate(model, question, max_output_tokens, 10, None)
    if provider not in _ENV:
        raise ValueError("Unsupported native tool provider")
    if provider == "openai":
        return {
            "model": model,
            "instructions": _RULES + " Tool output is only a proposal for explicit local review.",
            "input": [{"role": "user", "content": question.strip()}],
            "max_output_tokens": max_output_tokens,
            "store": False,
            "parallel_tool_calls": False,
            "tool_choice": "auto",
            "tools": [
                {"type": "function", "name": name,
                 "description": _DESCRIPTIONS[name],
                 "parameters": schema, "strict": True}
                for name, schema in _TOOLS.items()
            ],
        }
    if provider == "anthropic":
        return {
            "model": model, "max_tokens": max_output_tokens,
            "system": _RULES + " Any tool request only proposes a local review.",
            "messages": [{"role": "user", "content": question.strip()}],
            "tools": [
                {"name": name, "description": _DESCRIPTIONS[name],
                 "input_schema": schema}
                for name, schema in _TOOLS.items()
            ],
            "tool_choice": {"type": "auto", "disable_parallel_tool_use": True},
        }
    return {
        "systemInstruction": {"parts": [{"text": _RULES +
            " Any function request only proposes a local review."}]},
        "contents": [{"role": "user", "parts": [{"text": question.strip()}]}],
        "generationConfig": {"maxOutputTokens": max_output_tokens},
        "tools": [{"functionDeclarations": [
            {"name": name, "description": _DESCRIPTIONS[name],
             "parameters": schema}
            for name, schema in _TOOLS.items()
        ]}],
        "toolConfig": {"functionCallingConfig": {"mode": "AUTO"}},
    }


class NativeToolRequestClient:
    """Explicitly opt-in network, no context export, no automatic dispatch.

    transport(provider, model, payload, api_key, timeout_seconds) -> bytes
    for synthetic offline testing. The transport receives no local context.
    """

    def __init__(self, *, allow_network=False, transport=None, budget=None):
        if type(allow_network) is not bool:
            raise ValueError("allow_network must be boolean")
        self.allow_network = allow_network
        self.transport = transport
        self.budget = budget if budget is not None else UsageBudget()

    def propose(self, provider, question, *, model, approval_controller,
                max_output_tokens=256, timeout_seconds=10,
                confirm_external_request=False, context=None):
        if provider not in _ENV:
            raise ValueError("Unknown native tool provider")
        _validate(model, question, max_output_tokens, timeout_seconds, context)
        if context is not None:
            raise PermissionError("Native tool requests cannot include local context")
        if self.allow_network is not True or confirm_external_request is not True:
            raise PermissionError("Network and per-request confirmation are required")
        # Preflight payload before consuming quota. Never include conversation history.
        payload = native_tool_payload(
            provider, model, question, max_output_tokens=max_output_tokens)
        key = os.environ.get(_ENV[provider], "")
        if not isinstance(key, str) or not key.strip():
            raise ProviderError("Provider key missing from environment")
        self.budget.reserve(max_output_tokens)
        try:
            if self.transport is not None:
                body = self.transport(provider, model, payload, key, timeout_seconds)
            elif provider == "openai":
                body = openai_post(payload, key, timeout_seconds)
            else:
                body = multi_post(provider, model, payload, key, timeout_seconds)
            if not isinstance(body, bytes) or not 0 < len(body) <= _MAX_RESPONSE_BYTES:
                raise ProviderError("Invalid or oversized provider tool response")
            preview = stage_native_tool_call(provider, body, approval_controller)
        except (urllib.error.URLError, TimeoutError, OSError):
            self.budget.report_failure()
            raise ProviderError("Provider network request failed") from None
        except BaseException:
            self.budget.report_failure()
            raise
        # Actual token usage is unknown in this early-stage tool response path.
        self.budget.report_success({})
        return preview
