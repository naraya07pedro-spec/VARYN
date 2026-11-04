"""14C: tightly scoped, UNTRUSTED model-to-agent intent envelope.

This parser never calls tools or grants approvals. Only single explicit JSON
objects in the VARYN schema may become proposals through the desktop bridge.
No executable tool APIs are passed to a model.
"""
import json
from dataclasses import dataclass

from varyn.agent_runtime import AgentRejected, BoundedAgent

_MAX_INTENT_BYTES = 4096
_ALLOWED_KEYS = frozenset({"format", "tool", "arguments"})
_FORMAT = "varyn.tool_intent.v1"


@dataclass(frozen=True)
class ParsedIntent:
    tool: str
    arguments: dict


def _no_duplicates(pairs):
    output = {}
    for key, value in pairs:
        if key in output:
            raise AgentRejected("Duplicate JSON key in untrusted tool intent")
        output[key] = value
    return output


def parse_tool_intent(raw):
    """Reject markdown, arrays, approval/dispatch fields and unknown tools.

    A proposal, even for read-only tools, is not automatically executed.
    """
    if not isinstance(raw, str):
        raise AgentRejected("Tool intent must be a JSON string")
    if not raw or len(raw.encode("utf-8")) > _MAX_INTENT_BYTES:
        raise AgentRejected("Tool intent length is invalid")
    try:
        obj = json.loads(raw, object_pairs_hook=_no_duplicates,
                         parse_constant=lambda _: (_ for _ in ()).throw(
                             AgentRejected("Invalid JSON constant")))
    except (ValueError, UnicodeError, TypeError, RecursionError):
        raise AgentRejected("Malformed tool intent JSON") from None
    if not isinstance(obj, dict) or set(obj) != _ALLOWED_KEYS:
        raise AgentRejected("Tool intent fields do not match the schema")
    if obj["format"] != _FORMAT:
        raise AgentRejected("Unsupported tool intent format")
    tool = obj["tool"]
    arguments = obj["arguments"]
    # Reuse execution-time validation. This is not a model-authorized call.
    BoundedAgent._validate(tool, arguments)
    return ParsedIntent(tool=tool, arguments=arguments)


def stage_tool_intent(raw, approval_controller):
    """Prepare UI review only; no agent execution, network or approval."""
    intent = parse_tool_intent(raw)
    return approval_controller.propose(intent.tool, intent.arguments)


EXAMPLE_SYNTHETIC_INTENT = json.dumps({
    "format": _FORMAT,
    "tool": "stage_note",
    "arguments": {"text": "Synthetic agent proposal demo"},
}, ensure_ascii=False)
