"""16B ephemeral explicit grants for a standalone read-only local reader.

Grant creation must be called by TRUSTED host code after a real user decision;
an AI model must never receive this object. No persistent token, no model tools,
no network and no recursive access. Not a cross-process or OS security boundary.
"""
from collections import deque
from dataclasses import dataclass
from secrets import token_urlsafe
from threading import RLock
from time import monotonic

from varyn.agent_runtime import AgentRejected
from varyn.scoped_files import ScopedLocalReader


@dataclass(frozen=True)
class FileGrantPreview:
    grant_id: str
    duration_seconds: int
    max_operations: int
    allowed_extensions: tuple
    can_write: bool


class ScopedFileGrants:
    """In-memory host-granted capability, fail-closed and revocable."""

    def __init__(self, *, clock=monotonic, audit_limit=100):
        if not callable(clock) or type(audit_limit) is not int or not 1 <= audit_limit <= 1000:
            raise ValueError("Invalid clock or audit capacity")
        self._clock = clock
        self._lock = RLock()
        self._grants = {}
        self._audit = deque(maxlen=audit_limit)

    def _sweep_expired(self, now):
        """Release stale handles on trusted host activity; no background timer."""
        stale = [key for key, entry in self._grants.items()
                 if now >= entry["expiry"]]
        for key in stale:
            entry = self._grants.pop(key)
            try:
                entry["reader"].close()
            finally:
                self._audit.append(("expired", key[:8]))

    def grant(self, root, *, user_confirmed=False,
              duration_seconds=300, max_operations=10, max_bytes=16384):
        """Host passes directory; user confirmation is a caller assertion, not auth."""
        if user_confirmed is not True:
            raise PermissionError("Explicit host-obtained user consent required")
        if type(duration_seconds) is not int or not 1 <= duration_seconds <= 3600:
            raise ValueError("Grant duration must be 1..3600 seconds")
        if type(max_operations) is not int or not 1 <= max_operations <= 100:
            raise ValueError("Operation limit must be 1..100")
        reader = ScopedLocalReader(root, max_bytes=max_bytes)
        with self._lock:
            now = self._clock()
            self._sweep_expired(now)
            grant_id = token_urlsafe(32)
            self._grants[grant_id] = {
                "reader": reader,
                "expiry": now + duration_seconds,
                "remaining": max_operations,
            }
            self._audit.append(("granted", grant_id[:8]))
        return FileGrantPreview(grant_id, duration_seconds,
                                max_operations, (".txt", ".md"), False)

    def revoke(self, grant_id):
        with self._lock:
            self._sweep_expired(self._clock())
            if not isinstance(grant_id, str) or grant_id not in self._grants:
                raise AgentRejected("Unknown or revoked grant")
            entry = self._grants.pop(grant_id)
            entry["reader"].close()
            self._audit.append(("revoked", grant_id[:8]))

    def _take(self, grant_id, operation):
        entry = self._grants.get(grant_id) if isinstance(grant_id, str) else None
        if entry is None:
            raise AgentRejected("Unknown or revoked grant")
        if self._clock() >= entry["expiry"]:
            del self._grants[grant_id]
            entry["reader"].close()
            self._audit.append(("expired", grant_id[:8]))
            raise PermissionError("Grant expired")
        if entry["remaining"] <= 0:
            entry["reader"].close()
            self._audit.append(("exhausted", grant_id[:8]))
            raise PermissionError("Grant operation limit reached")
        # Debit before the call. Failed attempts are counted to bound abuse.
        entry["remaining"] -= 1
        self._audit.append((operation, grant_id[:8]))
        return entry["reader"]

    def _perform(self, grant_id, operation, method, *args):
        with self._lock:
            reader = self._take(grant_id, operation)
            try:
                return getattr(reader, method)(*args)
            finally:
                # The final permitted operation may finish, but cannot leave
                # the pinned OS directory handle open after quota exhaustion.
                entry = self._grants.get(grant_id)
                if entry is not None and entry["remaining"] == 0:
                    entry["reader"].close()

    def list_files(self, grant_id):
        return self._perform(grant_id, "list_attempt", "list_files")

    def read_text(self, grant_id, filename):
        return self._perform(grant_id, "read_attempt", "read_text", filename)

    def status(self):
        with self._lock:
            now = self._clock()
            self._sweep_expired(now)
            return {
                "format": "varyn.file_grants.v1",
                "active": sum(entry["remaining"] > 0 and now < entry["expiry"]
                              for entry in self._grants.values()),
                "audit": tuple(self._audit),
                "file_contents_logged": False,
                "durable": False,
                "identity_authenticated": False,
                "model_connected": False,
            }

    def revoke_all(self):
        with self._lock:
            for entry in self._grants.values():
                entry["reader"].close()
            self._grants.clear()
            self._audit.append(("revoked_all", ""))
