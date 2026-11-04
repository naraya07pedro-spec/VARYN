"""VARYN 17S-2: consent-gated public GitHub repository metadata tool.

This is a real, READ-ONLY network tool with no token or OS file access.
It accepts *untrusted tool requests* but never grants itself permission.
Only the trusted desktop may create consent decisions and hold this object.
"""
from collections import deque
from dataclasses import dataclass
from hashlib import sha256
import json
import re
from secrets import token_urlsafe
from threading import RLock
from time import monotonic
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener


MAX_INTENT_BYTES = 2048
MAX_REPLY_BYTES = 65536
MAX_REQUESTS = 5
_REPO = re.compile(
    r"\A([A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?)/"
    r"([A-Za-z0-9_.-]{1,100})\Z",
)
_BRANCH = re.compile(r"\A[A-Za-z0-9_./-]{1,150}\Z")
_TOOL = "github_public_repo_metadata"
_FORMAT = "varyn.public_tool_intent.v1"


class PublicToolRejected(ValueError):
    """Untrusted intent, missing consent, or a failed public read."""


def _unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise PublicToolRejected("Duplicate JSON key")
        result[key] = value
    return result


def parse_public_tool_intent(raw):
    """Strictly parse a single untrusted JSON tool proposal, never an URL."""
    if type(raw) is not str or not raw or len(raw.encode("utf-8")) > MAX_INTENT_BYTES:
        raise PublicToolRejected("Tool intent must be bounded UTF-8 JSON")
    try:
        item = json.loads(
            raw, object_pairs_hook=_unique_pairs,
            parse_constant=lambda _: (_ for _ in ()).throw(
                PublicToolRejected("Non-finite JSON number")
            ),
        )
    except (ValueError, UnicodeError, TypeError, RecursionError):
        raise PublicToolRejected("Invalid tool intent JSON") from None
    if (type(item) is not dict or
            set(item) != {"format", "tool", "arguments"} or
            item["format"] != _FORMAT or item["tool"] != _TOOL or
            type(item["arguments"]) is not dict or
            set(item["arguments"]) != {"repository"}):
        raise PublicToolRejected("Unexpected tool intent schema")
    repository = item["arguments"]["repository"]
    if type(repository) is not str or not _REPO.fullmatch(repository):
        raise PublicToolRejected("Expected owner/repository, never URL or path")
    owner, name = repository.split("/")
    if name in {".", ".."} or name.endswith(".git"):
        raise PublicToolRejected("Invalid repository name")
    return owner + "/" + name


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def fetch_public_repo_metadata(repository):
    """Exactly one anonymous GET to GitHub's fixed public metadata endpoint.

    No bearer token, no proxy, no redirects, no local file URL, and no retries.
    This does not access private repositories or GitHub user/session credentials.
    """
    if type(repository) is not str or not _REPO.fullmatch(repository):
        raise PublicToolRejected("Invalid repository target")
    url = "https://api.github.com/repos/" + repository
    request = Request(
        url,
        headers={"Accept": "application/vnd.github+json",
                 "User-Agent": "VARYN-17S2-PublicRepoRead"},
        method="GET",
    )
    opener = build_opener(ProxyHandler({}), _NoRedirect())
    try:
        with opener.open(request, timeout=5) as response:
            if response.status != 200:
                raise PublicToolRejected("GitHub metadata endpoint did not return 200")
            mime = response.headers.get("Content-Type", "").split(";", 1)[0].lower()
            if mime not in {"application/json", "application/vnd.github+json"}:
                raise PublicToolRejected("Unexpected metadata content type")
            raw = response.read(MAX_REPLY_BYTES + 1)
        if len(raw) > MAX_REPLY_BYTES:
            raise PublicToolRejected("GitHub response exceeds read limit")
        data = json.loads(raw.decode("utf-8", "strict"))
    except (OSError, HTTPError, URLError, TimeoutError, ValueError, UnicodeError):
        raise PublicToolRejected("Public GitHub metadata unavailable or unsafe") from None
    if (type(data) is not dict or data.get("private") is not False or
            type(data.get("full_name")) is not str or
            data["full_name"].casefold() != repository.casefold() or
            type(data.get("default_branch")) is not str or
            not _BRANCH.fullmatch(data["default_branch"])):
        raise PublicToolRejected("GitHub returned invalid or unexpected repository")
    stars = data.get("stargazers_count")
    open_items = data.get("open_issues_count")
    if (type(stars) is not int or stars < 0 or
            type(open_items) is not int or open_items < 0 or
            type(data.get("archived")) is not bool):
        raise PublicToolRejected("Invalid GitHub public metadata fields")
    return {
        "format": "varyn.github_public_repo_metadata.v1",
        "repository": repository,
        "default_branch": data["default_branch"],
        "stars": stars, "open_items_including_prs": open_items,
        "archived": data["archived"], "public": True,
        "read_only": True, "untrusted_external_data": True,
        "provider_handoff": False,
    }


@dataclass(frozen=True)
class PublicToolReview:
    proposal_id: str
    digest: str
    repository: str
    tool: str = _TOOL


class PublicGithubToolGateway:
    """One-use review + fresh network consent checked again at dispatch.

    The trusted host owns the network toggle and fetcher. Both decisions and
    pending requests live only in RAM and disappear on close. Not OS auth.
    """

    def __init__(self, *, fetcher=None, max_requests=MAX_REQUESTS,
                 clock=monotonic, review_ttl_seconds=120):
        if fetcher is not None and not callable(fetcher):
            raise TypeError("Trusted fetcher must be callable")
        if type(max_requests) is not int or not 1 <= max_requests <= 20:
            raise ValueError("Invalid request budget")
        if not callable(clock) or type(review_ttl_seconds) is not int or not 1 <= review_ttl_seconds <= 600:
            raise ValueError("Invalid review clock or expiry")
        self._fetch = fetcher or fetch_public_repo_metadata
        self._clock = clock
        self._ttl = review_ttl_seconds
        self._max_requests = max_requests
        self._used = 0
        self._pending = {}
        self._audit = deque(maxlen=32)
        self._lock = RLock()
        self._epoch = 0
        self._closed = False
        self._in_flight = 0

    def propose(self, raw, *, network_consent=False):
        """Parsing/proposing never dispatches. Consent is a host assertion."""
        repository = parse_public_tool_intent(raw)
        if network_consent is not True:
            raise PermissionError("Explicit network consent required")
        with self._lock:
            if self._closed:
                raise PublicToolRejected("Public tool gateway closed")
            if self._used + len(self._pending) >= self._max_requests:
                raise PublicToolRejected("Local GitHub tool budget reached")
            proposal = token_urlsafe(24)
            digest = sha256(
                (proposal + ":" + token_urlsafe(24) + ":" + repository).encode()
            ).hexdigest()
            self._pending[proposal] = (digest, repository, self._clock() + self._ttl)
            self._audit.append("proposed")
            return PublicToolReview(proposal, digest, repository)

    def decide(self, proposal_id, digest, *, approved=False, network_consent=False):
        """Consume once, reserve budget, and execute outside the gateway lock.

        Revoking or closing during an in-flight GET cannot unsend it, but
        invalidates its result and refuses to deliver it to the caller.
        """
        if type(approved) is not bool or type(network_consent) is not bool:
            raise PublicToolRejected("Exact trusted boolean decisions required")
        with self._lock:
            if self._closed:
                raise PublicToolRejected("Public tool gateway closed")
            pending = self._pending.get(proposal_id) if type(proposal_id) is str else None
            if pending is None or type(digest) is not str or pending[0] != digest:
                raise PublicToolRejected("Unknown, stale or mismatched review")
            del self._pending[proposal_id]
            if self._clock() >= pending[2]:
                self._audit.append("expired")
                raise PublicToolRejected("Review expired before dispatch")
            if approved is False:
                self._audit.append("denied")
                return {"status": "rejected", "network_dispatched": False}
            if network_consent is not True:
                self._audit.append("consent_revoked")
                raise PermissionError("Network permission revoked before dispatch")
            self._used += 1  # count even when HTTP fails or is later revoked
            self._in_flight += 1
            epoch = self._epoch
            repository = pending[1]

        # The only outbound request is the bounded, fixed-host public GET.
        # A trusted host may revoke while this call blocks: NEVER hold the lock.
        try:
            result = self._fetch(repository)
            if (type(result) is not dict or
                    result.get("repository") != repository or
                    result.get("public") is not True or
                    result.get("read_only") is not True or
                    result.get("provider_handoff") is not False):
                raise PublicToolRejected("Untrusted GitHub result rejected")
        except Exception:
            with self._lock:
                self._in_flight -= 1
                self._audit.append("failed")
            raise PublicToolRejected("Approved GitHub public read failed") from None

        with self._lock:
            self._in_flight -= 1
            if self._closed or self._epoch != epoch:
                self._audit.append("result_suppressed")
                raise PublicToolRejected("Public GitHub result revoked after dispatch")
            self._audit.append("completed")
            return {"status": "completed", "network_dispatched": True,
                    "result": result}

    def revoke_active(self):
        """Invalidate every pending review and all in-flight results instantly.

        In-flight network transport can still finish; no retries or result
        delivery are authorized after this call. This is not HTTP cancellation.
        """
        with self._lock:
            if self._closed:
                return
            self._epoch += 1
            self._pending.clear()
            self._audit.append("revoked")

    def close(self):
        """Mark session closed without waiting for a potentially blocked GET."""
        with self._lock:
            if self._closed:
                return
            self._closed = True
            self._epoch += 1
            self._pending.clear()
            self._audit.append("closed")

    def reject_all_pending(self):
        with self._lock:
            count = len(self._pending)
            self._pending.clear()
            if count:
                self._audit.append("discarded")
            return count

    def status(self):
        """No request bodies, repository names, tokens, digests or response data."""
        with self._lock:
            return {"format": "varyn.public_github_tool_gateway.v1",
                    "used": self._used, "limit": self._max_requests,
                    "pending": len(self._pending), "in_flight": self._in_flight,
                    "closed": self._closed, "audit": tuple(self._audit),
                    "authenticated_identity": False,
                    "network_default": False,
                    "model_autodispatch": False}
