"""17E ephemeral grants with optional in-process idle-expiry timer.

Grant creation must be called by TRUSTED host code after a real user decision;
an AI model must never receive this object. No persistent token, no model tools,
no network and no recursive access. Not a cross-process or OS security boundary.
"""
from collections import deque
from dataclasses import dataclass
from secrets import token_urlsafe
from threading import RLock, Timer
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

    def __init__(self, *, clock=monotonic, audit_limit=100,
                 auto_expire=False, timer_factory=Timer):
        if not callable(clock) or type(audit_limit) is not int or not 1 <= audit_limit <= 1000:
            raise ValueError("Invalid clock or audit capacity")
        if type(auto_expire) is not bool or not callable(timer_factory):
            raise ValueError("Invalid timer configuration")
        self._clock = clock
        self._lock = RLock()
        self._grants = {}
        self._audit = deque(maxlen=audit_limit)
        # Default-off for deterministic headless callers. Desktop opts in.
        # At most one in-process daemon timer is scheduled per manager.
        self._auto_expire = auto_expire
        self._timer_factory = timer_factory
        self._timer = None
        self._timer_generation = 0

    def _schedule_expiry_locked(self):
        """Replace one pending timer; ignore cancelled stale callbacks."""
        if not self._auto_expire:
            return
        self._timer_generation += 1
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None
        active = [entry["expiry"] for entry in self._grants.values()
                  if entry["remaining"] > 0]
        if not active:
            return
        generation = self._timer_generation
        delay = max(0.0, min(active) - self._clock())
        timer = None
        try:
            timer = self._timer_factory(delay, self._expire_due, args=(generation,))
            timer.daemon = True
            self._timer = timer
            timer.start()
        except Exception:
            # A failed scheduler cannot leave "live" unattended handles.
            # Revoke ALL this manager's grants rather than falling back to
            # idle handles that never expire.
            self._timer_generation += 1
            self._timer = None
            if timer is not None:
                try:
                    timer.cancel()
                except Exception:
                    pass
            for key, entry in self._grants.items():
                try:
                    self._release_entry(entry, "timer_revoked", key)
                except OSError:
                    pass
            self._grants.clear()
            self._audit.append(("timer_unavailable", ""))
            raise PermissionError(
                "Automatic expiry unavailable; all file grants revoked"
            ) from None

    def _expire_due(self, generation):
        """Runs inside the desktop process; never reads file contents."""
        with self._lock:
            if generation != self._timer_generation:
                return
            self._sweep_expired(self._clock())
            try:
                self._schedule_expiry_locked()
            except PermissionError:
                # Already failed closed and audited. No unhandled timer exception.
                return

    def _release_entry(self, entry, event, grant_id):
        """Once-only host-owned cleanup, strictly after directory handle close.

        Cleanup is a trusted host callback, never a model-supplied function.
        Holding RLock serializes read/revoke/timer teardown. A failed cleanup
        cannot reactivate a grant or expose filesystem paths in audit logs.
        """
        if entry.get("released", False):
            return
        entry["released"] = True
        callback = entry.pop("on_release", None)
        try:
            entry["reader"].close()
        finally:
            if callback is not None:
                try:
                    callback()
                except Exception:
                    # The handle is already closed; the owning UI can retry
                    # its fixture cleanup during normal shutdown.
                    self._audit.append(("cleanup_failed", grant_id[:8]))
            self._audit.append((event, grant_id[:8]))

    def _sweep_expired(self, now):
        """Release stale handles and host-owned fixtures on all expiry paths."""
        stale = [key for key, entry in self._grants.items()
                 if now >= entry["expiry"]]
        for key in stale:
            entry = self._grants.pop(key)
            self._release_entry(entry, "expired", key)
        return bool(stale)

    def grant(self, root, *, user_confirmed=False,
              duration_seconds=300, max_operations=10, max_bytes=16384,
              on_release=None):
        """Host passes directory; user confirmation is a caller assertion, not auth."""
        if user_confirmed is not True:
            raise PermissionError("Explicit host-obtained user consent required")
        if type(duration_seconds) is not int or not 1 <= duration_seconds <= 3600:
            raise ValueError("Grant duration must be 1..3600 seconds")
        if type(max_operations) is not int or not 1 <= max_operations <= 100:
            raise ValueError("Operation limit must be 1..100")
        if on_release is not None and not callable(on_release):
            raise ValueError("Trusted release hook must be callable")
        reader = ScopedLocalReader(root, max_bytes=max_bytes)
        with self._lock:
            now = self._clock()
            self._sweep_expired(now)
            grant_id = token_urlsafe(32)
            self._grants[grant_id] = {
                "reader": reader,
                "expiry": now + duration_seconds,
                "remaining": max_operations,
                "on_release": on_release,
                "released": False,
            }
            self._audit.append(("granted", grant_id[:8]))
            self._schedule_expiry_locked()
        return FileGrantPreview(grant_id, duration_seconds,
                                max_operations, (".txt", ".md"), False)

    def revoke(self, grant_id):
        with self._lock:
            self._sweep_expired(self._clock())
            if not isinstance(grant_id, str) or grant_id not in self._grants:
                raise AgentRejected("Unknown or revoked grant")
            entry = self._grants.pop(grant_id)
            self._release_entry(entry, "revoked", grant_id)
            self._schedule_expiry_locked()

    def _take(self, grant_id, operation):
        entry = self._grants.get(grant_id) if isinstance(grant_id, str) else None
        if entry is None:
            raise AgentRejected("Unknown or revoked grant")
        if self._clock() >= entry["expiry"]:
            del self._grants[grant_id]
            self._release_entry(entry, "expired", grant_id)
            raise PermissionError("Grant expired")
        if entry["remaining"] <= 0:
            self._release_entry(entry, "exhausted", grant_id)
            raise PermissionError("Grant operation limit reached")
        # Debit before the call. Failed attempts are counted to bound abuse.
        entry["remaining"] -= 1
        self._audit.append((operation, grant_id[:8]))
        return entry["reader"]

    def _perform(self, grant_id, operation, method, *args):
        with self._lock:
            try:
                reader = self._take(grant_id, operation)
                result = getattr(reader, method)(*args)
                entry = self._grants.get(grant_id)
                # Do not expose results from an operation crossing its lease.
                # An OS read cannot be interrupted by this Python check.
                if entry is None or self._clock() >= entry["expiry"]:
                    raise PermissionError("Grant expired during operation")
                return result
            finally:
                # Also handles expiry rejections from _take.
                self._sweep_expired(self._clock())
                entry = (self._grants.get(grant_id)
                         if isinstance(grant_id, str) else None)
                if entry is not None and entry["remaining"] == 0:
                    self._release_entry(entry, "exhausted", grant_id)
                self._schedule_expiry_locked()

    def list_files(self, grant_id):
        return self._perform(grant_id, "list_attempt", "list_files")

    def read_text(self, grant_id, filename):
        return self._perform(grant_id, "read_attempt", "read_text", filename)

    def status(self):
        with self._lock:
            now = self._clock()
            changed = self._sweep_expired(now)
            if changed:
                self._schedule_expiry_locked()
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
            for key, entry in self._grants.items():
                self._release_entry(entry, "revoked", key)
            self._grants.clear()
            self._audit.append(("revoked_all", ""))
            self._schedule_expiry_locked()
