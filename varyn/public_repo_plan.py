"""17S-7: bounded sequential public GitHub comparison task (no model autonomy).

A structured, UNTRUSTED two-target task is validated here. Only trusted
desktop controls may approve the plan and then separately approve EVERY
public network read. This module never opens network connections or files.
"""
from dataclasses import dataclass
from hashlib import sha256
import json
from secrets import token_urlsafe
from time import monotonic

from varyn.public_github_tool import (
    PublicToolRejected, _BRANCH, _unique_pairs, parse_public_tool_intent,
)

_PLAN_FORMAT = "varyn.public_repo_comparison.v1"
_MAX_PLAN_BYTES = 2048
_RESULT_FIELDS = {
    "format", "repository", "default_branch", "stars",
    "open_items_including_prs", "archived", "public", "read_only",
    "untrusted_external_data", "provider_handoff",
}


@dataclass(frozen=True)
class ComparisonReview:
    plan_id: str
    digest: str
    repositories: tuple


def parse_comparison_plan(raw):
    """Two exact, distinct public repo slugs; no URLs or injected tool names."""
    if type(raw) is not str or not raw:
        raise PublicToolRejected("Invalid or oversized comparison task")
    try:
        encoded_length = len(raw.encode("utf-8", "strict"))
    except UnicodeError:
        raise PublicToolRejected("Invalid comparison text encoding") from None
    if encoded_length > _MAX_PLAN_BYTES:
        raise PublicToolRejected("Invalid or oversized comparison task")
    try:
        data = json.loads(raw, object_pairs_hook=_unique_pairs)
    except (ValueError, TypeError, RecursionError, UnicodeError):
        raise PublicToolRejected("Malformed comparison task JSON") from None
    if (type(data) is not dict or set(data) != {"format", "repositories"} or
            data["format"] != _PLAN_FORMAT or
            type(data["repositories"]) is not list or
            len(data["repositories"]) != 2):
        raise PublicToolRejected("Comparison requires exactly two public repositories")
    names = []
    for repo in data["repositories"]:
        # Reuse exactly the same allowlist/host-injection checks as the
        # one-step public GitHub tool. A plan never accepts a custom URL.
        intent = json.dumps({
            "format": "varyn.public_tool_intent.v1",
            "tool": "github_public_repo_metadata",
            "arguments": {"repository": repo},
        }, separators=(",", ":"))
        names.append(parse_public_tool_intent(intent))
    if names[0].casefold() == names[1].casefold():
        raise PublicToolRejected("Comparing the same repository twice is denied")
    return tuple(names)


class PublicRepoComparison:
    """RAM-only task lifecycle, with no implicit authorization or retry."""

    def __init__(self, raw, *, clock=monotonic, ttl_seconds=120):
        if not callable(clock) or type(ttl_seconds) is not int or not 1 <= ttl_seconds <= 600:
            raise ValueError("Invalid task review expiry")
        self.repositories = parse_comparison_plan(raw)
        self._clock = clock
        self._expires = clock() + ttl_seconds
        self._id = token_urlsafe(24)
        self._digest = sha256(
            (self._id + ":" + token_urlsafe(24) + ":" +
             ":".join(self.repositories)).encode("utf-8")
        ).hexdigest()
        self._state = "review"
        self._index = 0
        self._waiting_for = None
        self._results = []

    def review(self):
        if self._state != "review":
            raise PublicToolRejected("Task review already consumed")
        return ComparisonReview(self._id, self._digest, self.repositories)

    def start(self, plan_id, digest, *, approved=False, network_consent=False):
        """Consume whole-task review, but NEVER approve a per-step tool GET."""
        if type(approved) is not bool or type(network_consent) is not bool:
            raise PublicToolRejected("Exact trusted booleans are required")
        if (self._state != "review" or type(plan_id) is not str or
                type(digest) is not str or plan_id != self._id or
                digest != self._digest):
            raise PublicToolRejected("Invalid or replayed comparison review")
        if self._clock() >= self._expires:
            self.cancel()
            raise PublicToolRejected("Comparison review expired")
        if not approved:
            self.cancel()
            return False
        if not network_consent:
            self.cancel()
            raise PermissionError("Separate GitHub network permission is required")
        self._state = "running"
        return True

    def next_intent(self):
        """Only the next unperformed step; never schedule two GETs at once."""
        if self._state != "running" or self._waiting_for is not None:
            raise PublicToolRejected("Comparison step not ready")
        if self._index >= len(self.repositories):
            raise PublicToolRejected("No comparison steps remaining")
        repo = self.repositories[self._index]
        self._waiting_for = repo
        return json.dumps({
            "format": "varyn.public_tool_intent.v1",
            "tool": "github_public_repo_metadata",
            "arguments": {"repository": repo},
        }, separators=(",", ":"), sort_keys=True)

    def commit(self, metadata):
        """Record only validated output from the host-approved gateway."""
        if self._state != "running" or self._waiting_for is None:
            raise PublicToolRejected("No active reviewed comparison step")
        repo = self._waiting_for
        if (type(metadata) is not dict or set(metadata) != _RESULT_FIELDS or
                metadata.get("format") != "varyn.github_public_repo_metadata.v1" or
                metadata.get("repository") != repo or
                metadata.get("public") is not True or
                metadata.get("read_only") is not True or
                metadata.get("untrusted_external_data") is not True or
                metadata.get("provider_handoff") is not False or
                type(metadata.get("default_branch")) is not str or
                not _BRANCH.fullmatch(metadata["default_branch"]) or
                type(metadata.get("stars")) is not int or
                metadata["stars"] < 0 or
                type(metadata.get("open_items_including_prs")) is not int or
                metadata["open_items_including_prs"] < 0 or
                type(metadata.get("archived")) is not bool):
            self.cancel()
            raise PublicToolRejected("Untrusted comparison result failed validation")
        # Copy the independently validated fields; no free text/context upload.
        self._results.append(dict(metadata))
        self._waiting_for = None
        self._index += 1
        if self._index == 2:
            self._state = "completed"
        return self._state

    def summary(self):
        if self._state != "completed" or len(self._results) != 2:
            raise PublicToolRejected("Comparison has no complete trusted result")
        a, b = self._results
        if a["stars"] > b["stars"]:
            leader = a["repository"]
        elif b["stars"] > a["stars"]:
            leader = b["repository"]
        else:
            leader = None
        return {
            "format": "varyn.public_repo_comparison_result.v1",
            "repositories": tuple(self.repositories),
            "rows": tuple({
                "repository": x["repository"], "default_branch": x["default_branch"],
                "stars": x["stars"], "open_items_including_prs": x["open_items_including_prs"],
                "archived": x["archived"],
            } for x in self._results),
            "more_stars": leader,
            "stars_difference": abs(a["stars"] - b["stars"]),
            "comparison_basis": "public GitHub metadata, not code quality or security",
            "provider_handoff": False,
            "read_only": True,
            "untrusted_external_data": True,
        }

    def cancel(self):
        if self._state != "completed":
            self._state = "cancelled"
            self._waiting_for = None
            self._results.clear()

    def status(self):
        return {
            "format": "varyn.public_repo_comparison_state.v1",
            "state": self._state,
            "steps_done": self._index,
            "steps_total": 2,
            "network_default": False,
            "human_approvals_per_get": True,
            "model_autodispatch": False,
            "context_uploaded": False,
        }
