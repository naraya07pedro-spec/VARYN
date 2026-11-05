"""17S-18: host-owned approval before a bounded synthetic read-only dispatch.

This is an OFFLINE CI proof, not a production owner-approval UI. The test's
trusted host code simulates an explicit decision; the AppContainer child is
never granted the host file path, file handle, grant token or authority to
authorize new reads. It receives only validated small integer counts.

No real user files, arbitrary paths, provider sessions, network or writes.
The transport and operating-system containment are tested separately.
"""
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import secrets
import stat
import time

from varyn.bounded_broker_protocol import (
    BrokerRejected, canonical, strict_json,
)
from varyn.durable_broker_journal import DurableOneShotJournal

VERSION = "varyn.anon-pipes.v1"
ACTION = "sum_synthetic_counts"
_FILENAME = "synthetic-parent-counts.json"
_MAX_SOURCE = 512
_TTL = 20


@dataclass(frozen=True)
class SyntheticReadPreview:
    request_id: str
    digest: str
    description: str
    expires_at: int
    mutates: bool = False


class ParentSyntheticReadBroker:
    """One approved fixture read, one child dispatch, one verified response.

    The host is the *only* caller allowed to invoke owner_decide; child/model
    inputs must never map to that method. This trial intentionally requires
    a directory/filename owned by the CI harness, and must not be exposed as
    a general file-reading broker or a new production permission.
    """

    def __init__(self, fixture_root, journal, *, clock=None):
        if os.environ.get("GITHUB_ACTIONS") != "true" or (
                os.environ.get("VARYN_CI_APPCONTAINER_TRIAL") != "1"):
            raise BrokerRejected("Synthetic broker requires opted-in hosted CI")
        if not isinstance(journal, DurableOneShotJournal):
            raise BrokerRejected("Parent-only durable journal required")
        root = Path(fixture_root)
        if not root.is_absolute() or not root.is_dir() or root.is_symlink():
            raise BrokerRejected("Trusted synthetic fixture root required")
        self._root = root
        self._path = root / _FILENAME
        self._journal = journal
        self._clock = clock if clock is not None else lambda: int(time.time())
        if not callable(self._clock):
            raise BrokerRejected("Invalid trusted broker clock")
        self._state = "fresh"
        self._request_id = secrets.token_hex(16)
        self._nonce = secrets.token_hex(16)
        self._preview = None
        self._identity = None
        self._request = None
        self._expected = None

    def _now(self):
        value = self._clock()
        if type(value) is not int or value < 1:
            raise BrokerRejected("Invalid trusted broker time")
        return value

    def _metadata(self):
        if self._path.is_symlink():
            raise BrokerRejected("Synthetic fixture symlink refused")
        try:
            info = self._path.stat(follow_symlinks=False)
        except OSError:
            raise BrokerRejected("Synthetic fixture metadata unavailable") from None
        if not stat.S_ISREG(info.st_mode) or not 1 <= info.st_size <= _MAX_SOURCE:
            raise BrokerRejected("Synthetic fixture type or size rejected")
        return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns)

    def preview(self):
        if self._state != "fresh":
            raise BrokerRejected("Synthetic preview already issued")
        identity = self._metadata()  # NO CONTENT READ before simulated approval
        now = self._now()
        digest = hashlib.sha256(canonical({
            "action": ACTION, "request_id": self._request_id,
            "nonce": self._nonce, "filename": _FILENAME,
            "identity": list(identity), "expires_at": now + _TTL,
        })).hexdigest()
        self._identity = identity
        self._preview = SyntheticReadPreview(
            self._request_id, digest,
            "Read one disposable CI-only synthetic count fixture",
            now + _TTL,
        )
        self._state = "pending"
        return self._preview

    def owner_decide(self, request_id, displayed_digest, *, approved):
        """TRUSTED host-only callback, never derived from a child JSON field."""
        if type(approved) is not bool:
            raise BrokerRejected("Owner decision must be explicit boolean")
        if (self._state != "pending" or self._preview is None
                or type(request_id) is not str
                or type(displayed_digest) is not str
                or request_id != self._preview.request_id
                or not secrets.compare_digest(
                    displayed_digest, self._preview.digest)):
            raise BrokerRejected("Owner preview binding mismatch")
        # Consume preview even when denied. A fresh request requires a fresh
        # preview+decision; model input alone cannot revive this instance.
        if not approved:
            self._state = "denied"
            return False
        if self._now() > self._preview.expires_at:
            self._state = "expired"
            raise BrokerRejected("Owner approval already expired")
        self._state = "approved"
        return True

    def _read_approved_fixture(self):
        if self._identity != self._metadata():
            raise BrokerRejected("Synthetic fixture changed after preview")
        flags = os.O_RDONLY | getattr(os, "O_BINARY", 0)
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        fd = None
        try:
            fd = os.open(self._path, flags)
            identity = os.fstat(fd)
            actual = (identity.st_dev, identity.st_ino, identity.st_size,
                      identity.st_mtime_ns)
            if actual != self._identity or not stat.S_ISREG(identity.st_mode):
                raise BrokerRejected("Fixture identity changed during open")
            data = os.read(fd, _MAX_SOURCE + 1)
        except OSError:
            raise BrokerRejected("Approved synthetic file read refused") from None
        finally:
            if fd is not None:
                os.close(fd)
        if not 1 <= len(data) <= _MAX_SOURCE:
            raise BrokerRejected("Synthetic file size rejected")
        payload = strict_json(data)
        if set(payload) != {"counts"}:
            raise BrokerRejected("Unexpected owner fixture content")
        values = payload["counts"]
        if (type(values) is not list or not 1 <= len(values) <= 12 or
                any(type(v) is not int or not 0 <= v <= 10000 for v in values)):
            raise BrokerRejected("Synthetic fixture values rejected")
        return list(values)

    def claim_and_prepare(self):
        """Commit durable claim BEFORE caller's child CreateProcessW."""
        if self._state != "approved":
            raise BrokerRejected("No unused owner approval for dispatch")
        # Burn permission first, even when invalid or missing fixture is seen.
        self._state = "consumed"
        if self._preview is None or self._now() > self._preview.expires_at:
            raise BrokerRejected("Approved synthetic request expired")
        counts = self._read_approved_fixture()
        request = {
            "version": VERSION, "action": ACTION,
            "request_id": self._request_id,
            "nonce": self._nonce,
            "counts": counts,
        }
        canonical(request)  # bounded before journal or child spawn
        self._journal.claim(self._request_id)  # committed before returning
        self._expected = sum(counts)
        self._request = request
        self._state = "dispatched"
        return dict(request)

    def complete(self, raw_response):
        if self._state != "dispatched":
            raise BrokerRejected("No live approved dispatch to finalize")
        # Any attempt burns the single reply slot. Crash leaves claimed.
        self._state = "result_seen"
        try:
            reply = strict_json(raw_response)
            if set(reply) != {
                "version", "request_id", "nonce",
                "status", "total", "decoy_status",
            }:
                raise BrokerRejected("Unrecognized sandbox response")
            if (reply["version"] != VERSION
                    or reply["request_id"] != self._request_id
                    or reply["nonce"] != self._nonce
                    or reply["status"] != "ok"
                    or reply["decoy_status"] not in (
                        "verified_absent", "unavailable_errno22")
                    or type(reply["total"]) is not int
                    or reply["total"] != self._expected):
                raise BrokerRejected("Sandbox response mismatch")
            self._journal.finalize(self._request_id, succeeded=True)
        except Exception:
            # Preserve one-way failure/no-replay. Never accept later replies.
            try:
                self._journal.finalize(self._request_id, succeeded=False)
            except Exception:
                pass  # Still claimed means no replay after crash.
            self._state = "failed"
            raise BrokerRejected("Approved synthetic response rejected") from None
        self._state = "completed"
        return reply["total"]

    def revoke(self):
        if self._state in ("denied", "completed", "failed", "revoked"):
            return False
        dispatched = self._state == "dispatched"
        self._state = "revoked"
        if dispatched:
            self._journal.finalize(self._request_id, succeeded=False)
        return True

    @property
    def state(self):
        return self._state

    @property
    def request_id(self):
        return self._request_id
