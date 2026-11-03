"""Checkpoint 14A: local, deterministic, bounded agent execution.

No model or network integration. Tool proposals are UNTRUSTED. A fixed registry
is owned by the application, not by the model. Mutations require a one-time
explicit approval token and stay in synthetic in-memory workspace only.
"""
from dataclasses import dataclass
from hashlib import sha256
from secrets import token_urlsafe
from threading import RLock
import json
import re

_NAME = re.compile(r"\A[a-z][a-z0-9_]{0,39}\Z")
_MAX_ARGS_BYTES = 2048


class AgentRejected(ValueError):
    """Untrusted action is not valid or is not registered."""


class ApprovalRequired(PermissionError):
    """A mutating action requires explicit human approval."""


class AgentLimitReached(RuntimeError):
    """The session has exhausted its action limit."""


@dataclass(frozen=True)
class AgentProposal:
    proposal_id: str
    tool: str
    arguments: dict
    mutates: bool
    digest: str


@dataclass(frozen=True)
class AgentResult:
    tool: str
    status: str
    output: dict


class BoundedAgent:
    """Single in-process agent. No autonomous planning or hidden tool execution."""

    def __init__(self, *, max_steps=8, max_notes=20):
        if type(max_steps) is not int or not 1 <= max_steps <= 32:
            raise ValueError("max_steps must be 1..32")
        if type(max_notes) is not int or not 1 <= max_notes <= 100:
            raise ValueError("max_notes must be 1..100")
        self._max_steps = max_steps
        self._max_notes = max_notes
        self._lock = RLock()
        self._steps = 0
        self._proposals = {}
        self._used = set()
        self._notes = []
        self._audit = []
        self._handlers = {
            "inspect_status": (False, self._inspect),
            "stage_note": (True, self._stage_note),
        }

    @staticmethod
    def _validate(tool, arguments):
        if not isinstance(tool, str) or not _NAME.fullmatch(tool):
            raise AgentRejected("Invalid tool name")
        if not isinstance(arguments, dict):
            raise AgentRejected("Arguments must be a dictionary")
        if any(not isinstance(key, str) for key in arguments):
            raise AgentRejected("Argument names must be strings")
        try:
            raw = json.dumps(arguments, sort_keys=True, ensure_ascii=False,
                             allow_nan=False).encode("utf-8")
        except (ValueError, TypeError, UnicodeError):
            raise AgentRejected("Invalid JSON arguments") from None
        if len(raw) > _MAX_ARGS_BYTES:
            raise AgentRejected("Tool arguments exceed 2048 bytes")
        if tool == "inspect_status":
            if arguments:
                raise AgentRejected("inspect_status takes no arguments")
        elif tool == "stage_note":
            if set(arguments) != {"text"} or not isinstance(arguments["text"], str):
                raise AgentRejected("stage_note needs a text string")
            if not 1 <= len(arguments["text"].strip()) <= 200:
                raise AgentRejected("Note length must be 1..200 characters")
        else:
            raise AgentRejected("Tool is not registered")
        return raw

    def propose(self, tool, arguments):
        """Stage a proposal. This does not execute anything or reserve a step."""
        raw = self._validate(tool, arguments)
        with self._lock:
            if self._steps >= self._max_steps:
                raise AgentLimitReached("Agent step budget exhausted")
            proposal_id = token_urlsafe(24)
            digest = sha256(tool.encode("ascii") + b"\0" + raw).hexdigest()
            proposal = AgentProposal(proposal_id, tool,
                                     json.loads(raw.decode("utf-8")),
                                     self._handlers[tool][0], digest)
            self._proposals[proposal_id] = proposal
            self._audit.append(("proposed", tool, digest[:12]))
            return proposal

    def execute(self, proposal_id, *, approval_token=None):
        """Run only an exact pending proposal. Mutations require approved token.

        approve() must be called by the trusted UI/controller, never from model
        output. In this prototype, that separation is by caller convention,
        not an authenticated security boundary.
        """
        with self._lock:
            if self._steps >= self._max_steps:
                raise AgentLimitReached("Agent step budget exhausted")
            if not isinstance(proposal_id, str) or proposal_id not in self._proposals:
                raise AgentRejected("Unknown or consumed proposal")
            proposal = self._proposals[proposal_id]
            if proposal.mutates:
                approved = getattr(self, "_approvals", {}).get(proposal_id)
                if (not isinstance(approval_token, str) or
                        approved is None or approval_token != approved):
                    raise ApprovalRequired("Human approval required for this mutation")
            # Consume before dispatch. No automatic retry after failure.
            del self._proposals[proposal_id]
            if hasattr(self, "_approvals"):
                self._approvals.pop(proposal_id, None)
            self._used.add(proposal_id)
            self._steps += 1
            try:
                output = self._handlers[proposal.tool][1](proposal.arguments)
            except Exception:
                self._audit.append(("failed", proposal.tool, proposal.digest[:12]))
                raise
            self._audit.append(("executed", proposal.tool, proposal.digest[:12]))
            return AgentResult(proposal.tool, "completed", output)

    def approve(self, proposal_id):
        """Simulate human approval; UI authentication still not implemented."""
        with self._lock:
            proposal = self._proposals.get(proposal_id)
            if proposal is None:
                raise AgentRejected("Unknown or consumed proposal")
            if not proposal.mutates:
                raise AgentRejected("Read-only action does not require approval")
            token = token_urlsafe(32)
            if not hasattr(self, "_approvals"):
                self._approvals = {}
            self._approvals[proposal_id] = token
            self._audit.append(("approved", proposal.tool, proposal.digest[:12]))
            return token

    def reject(self, proposal_id):
        with self._lock:
            proposal = self._proposals.pop(proposal_id, None)
            if proposal is None:
                raise AgentRejected("Unknown or consumed proposal")
            if hasattr(self, "_approvals"):
                self._approvals.pop(proposal_id, None)
            self._audit.append(("rejected", proposal.tool, proposal.digest[:12]))

    def _inspect(self, _arguments):
        return {"stored_synthetic_notes": len(self._notes),
                "steps_used": self._steps, "steps_limit": self._max_steps}

    def _stage_note(self, arguments):
        if len(self._notes) >= self._max_notes:
            raise AgentLimitReached("Synthetic note storage limit reached")
        self._notes.append(arguments["text"].strip())
        return {"stored_synthetic_notes": len(self._notes)}

    def snapshot(self):
        """No prompts, note contents, approval secrets or provider credentials."""
        with self._lock:
            return {
                "format": "varyn.agent_runtime.v1",
                "steps_used": self._steps,
                "steps_limit": self._max_steps,
                "pending_proposals": len(self._proposals),
                "stored_synthetic_notes": len(self._notes),
                "audit": tuple(self._audit),
                "live_tools": False,
                "persistent": False,
                "approval_authenticated": False,
            }
