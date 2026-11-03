"""15A native provider tool-call normalization into REVIEW-ONLY VARYN proposals.

Native payloads are untrusted, bounded and parsed without side effects.
No API request is made, no approval granted and no tool executed here.
Only one native tool call is accepted per response to avoid hidden batches.
"""
import json
from dataclasses import dataclass

from varyn.agent_runtime import AgentRejected
from varyn.tool_protocol import parse_tool_intent

_MAX_BODY_BYTES = 131072
_MAX_ARGS_BYTES = 2048


@dataclass(frozen=True)
class NativeToolIntent:
    provider: str
    tool: str
    arguments: dict


def _no_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise AgentRejected("Duplicate native response key")
        result[key] = value
    return result


def _decode_json(raw, *, max_bytes):
    if isinstance(raw, bytes):
        if not 0 < len(raw) <= max_bytes:
            raise AgentRejected("Native response exceeds permitted size")
        try:
            raw = raw.decode("utf-8", errors="strict")
        except UnicodeError:
            raise AgentRejected("Invalid native response encoding") from None
    if not isinstance(raw, str):
        raise AgentRejected("Native response must be JSON")
    try:
        if not 0 < len(raw.encode("utf-8")) <= max_bytes:
            raise AgentRejected("Native response exceeds permitted size")
        return json.loads(
            raw, object_pairs_hook=_no_duplicate_keys,
            parse_constant=lambda _: (_ for _ in ()).throw(
                AgentRejected("Invalid native JSON constant")),
        )
    except (ValueError, UnicodeError, TypeError, RecursionError):
        raise AgentRejected("Malformed native response") from None


def _validated(provider, name, arguments):
    # Re-use the 14C schema as the only bridge into the registered tool set.
    if not isinstance(arguments, dict):
        raise AgentRejected("Tool arguments must be an object")
    envelope = json.dumps({
        "format": "varyn.tool_intent.v1",
        "tool": name, "arguments": arguments,
    }, ensure_ascii=False, allow_nan=False)
    if len(envelope.encode("utf-8")) > 4096:
        raise AgentRejected("Native tool intent too large")
    parsed = parse_tool_intent(envelope)
    return NativeToolIntent(provider, parsed.tool, parsed.arguments)


def parse_native_tool_call(provider, response):
    """Normalize ONE completed native tool request from a provider response.

    Supported response shapes:
    - OpenAI Responses: output[].type=function_call, status=completed
    - Anthropic Messages: content[].type=tool_use, stop_reason=tool_use
    - Gemini generateContent: candidates[0].content.parts[].functionCall
    """
    if provider not in ("openai", "anthropic", "gemini"):
        raise AgentRejected("Unsupported native tool provider")
    data = _decode_json(response, max_bytes=_MAX_BODY_BYTES)
    if not isinstance(data, dict):
        raise AgentRejected("Native response is not an object")
    try:
        if provider == "openai":
            if data.get("status") != "completed":
                raise AgentRejected("OpenAI tool response was not completed")
            output = data["output"]
            if not isinstance(output, list):
                raise AgentRejected("Invalid OpenAI output")
            calls = [v for v in output if isinstance(v, dict)
                     and v.get("type") == "function_call"]
            if len(calls) != 1:
                raise AgentRejected("Expected exactly one native tool call")
            entry = calls[0]
            name = entry["name"]
            arguments = _decode_json(entry["arguments"], max_bytes=_MAX_ARGS_BYTES)
        elif provider == "anthropic":
            if data.get("type") != "message" or data.get("stop_reason") != "tool_use":
                raise AgentRejected("Anthropic did not request a tool")
            output = data["content"]
            if not isinstance(output, list):
                raise AgentRejected("Invalid Anthropic content")
            calls = [v for v in output if isinstance(v, dict)
                     and v.get("type") == "tool_use"]
            if len(calls) != 1:
                raise AgentRejected("Expected exactly one native tool call")
            name = calls[0]["name"]
            arguments = calls[0]["input"]
        else:
            candidates = data["candidates"]
            if not isinstance(candidates, list) or len(candidates) != 1:
                raise AgentRejected("Ambiguous Gemini candidates")
            candidate = candidates[0]
            if not isinstance(candidate, dict) or candidate.get("finishReason") != "STOP":
                raise AgentRejected("Gemini output was not completed")
            parts = candidate["content"]["parts"]
            if not isinstance(parts, list):
                raise AgentRejected("Invalid Gemini parts")
            calls = [v["functionCall"] for v in parts
                     if isinstance(v, dict) and "functionCall" in v]
            if len(calls) != 1:
                raise AgentRejected("Expected exactly one native tool call")
            name = calls[0]["name"]
            arguments = calls[0]["args"]
        return _validated(provider, name, arguments)
    except (KeyError, TypeError, ValueError, UnicodeError, OverflowError):
        raise AgentRejected("Invalid native tool-call response") from None


def stage_native_tool_call(provider, response, approval_controller):
    """Stage review without execution, approval, network or model inference."""
    intent = parse_native_tool_call(provider, response)
    return approval_controller.propose(intent.tool, intent.arguments)
