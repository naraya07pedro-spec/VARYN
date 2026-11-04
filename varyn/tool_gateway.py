"""17S-1: one-use reviewed read tool over VARYN-created synthetic fixtures.

Local UI tool bridge only: no model execution, OS sandbox, identity authentication,
or access to personal files. Grant IDs must stay inside trusted host code.
"""
from dataclasses import dataclass
from hashlib import sha256
import json
from secrets import token_urlsafe
from threading import RLock

from varyn.agent_runtime import AgentRejected
from varyn.file_grants import ScopedFileGrants
from varyn.synthetic_fixture import _FIXTURE_FILES


class ToolGatewayRejected(AgentRejected):
    """Unknown, stale, malformed or unauthorized tool proposal."""


@dataclass(frozen=True)
class ToolReview:
    proposal_id: str
    digest: str
    tool: str
    summary: str
    risk: str
    mutates: bool = False


class SyntheticReadToolGateway:
    """Bind a host grant to an exact one-time, caller-approved synthetic read."""

    TOOL = "read_generated_sample"

    def __init__(self, grants, *, max_pending=4, max_decisions=12):
        if not isinstance(grants, ScopedFileGrants):
            raise TypeError("ScopedFileGrants required")
        if type(max_pending) is not int or not 1 <= max_pending <= 20:
            raise ValueError("Invalid pending limit")
        if type(max_decisions) is not int or not 1 <= max_decisions <= 100:
            raise ValueError("Invalid decision limit")
        self._grants = grants
        self._pending = {}
        self._max_pending = max_pending
        self._max_decisions = max_decisions
        self._decisions = 0
        self._lock = RLock()
        self._events = []

    def propose(self, tool, arguments, *, grant_id):
        """Build a review, without reading files or making a provider request."""
        if type(tool) is not str or tool != self.TOOL:
            raise ToolGatewayRejected("Unregistered tool")
        if type(arguments) is not dict or set(arguments) != {"name"}:
            raise ToolGatewayRejected("Exact arguments required")
        name = arguments["name"]
        if type(name) is not str or name not in _FIXTURE_FILES:
            raise ToolGatewayRejected("Non-synthetic name denied")
        if type(grant_id) is not str or len(grant_id) < 16:
            raise ToolGatewayRejected("Missing host-owned grant")
        with self._lock:
            if (len(self._pending) >= self._max_pending or
                    self._decisions + len(self._pending) >= self._max_decisions):
                raise ToolGatewayRejected("Local tool limit reached")
            proposal_id = token_urlsafe(24)
            payload = json.dumps({"tool": tool, "name": name, "grant": grant_id,
                                  "proposal": proposal_id, "nonce": token_urlsafe(24)},
                                 sort_keys=True, separators=(",", ":"))
            digest = sha256(payload.encode("utf-8")).hexdigest()
            self._pending[proposal_id] = (digest, grant_id, name)
            self._events.append(("proposed", tool))
            return ToolReview(proposal_id, digest, tool,
                              "Read VARYN-generated disposable sample: " + name,
                              "Read-only, local, no AI provider handoff")

    def decide(self, proposal_id, displayed_digest, *, approved):
        """Consume before dispatch: rejected, expired or failed actions never replay."""
        if type(approved) is not bool:
            raise ToolGatewayRejected("Trusted boolean decision required")
        with self._lock:
            item = self._pending.get(proposal_id) if type(proposal_id) is str else None
            if (item is None or type(displayed_digest) is not str or
                    item[0] != displayed_digest):
                raise ToolGatewayRejected("Stale or mismatched tool review")
            del self._pending[proposal_id]
            self._decisions += 1
            if not approved:
                self._events.append(("denied", self.TOOL))
                return {"status": "rejected", "tool": self.TOOL,
                        "external_upload": False}
            _, grant_id, name = item
            try:
                result = self._grants.read_text(grant_id, name)
                # An edited, replaced, or user-authored file is NOT emitted.
                if (result.get("name") != name or
                        result.get("text") != _FIXTURE_FILES[name] or
                        result.get("external_upload") is not False):
                    raise ToolGatewayRejected("Fixture integrity mismatch")
            except (AgentRejected, PermissionError, OSError, ValueError):
                self._events.append(("failed", self.TOOL))
                raise ToolGatewayRejected("Synthetic read denied") from None
            self._events.append(("completed", self.TOOL))
            return {"status": "completed", "tool": self.TOOL,
                    "output": {"text": result["text"], "bytes": result["bytes"],
                               "synthetic_only": True},
                    "external_upload": False}

    def reject_all_pending(self):
        with self._lock:
            count = len(self._pending)
            self._pending.clear()
            if count:
                self._events.append(("discarded", self.TOOL))
            return count

    def status(self):
        """Metadata only: no grant tokens, names, paths, contents or digests."""
        with self._lock:
            return {"format": "varyn.synthetic_tool_gateway.v1",
                    "pending": len(self._pending), "decisions": self._decisions,
                    "decision_limit": self._max_decisions,
                    "events": tuple(self._events[-20:]),
                    "model_connected": False,
                    "provider_handoff_allowed": False,
                    "identity_authenticated": False,
                    "os_sandbox": False}
