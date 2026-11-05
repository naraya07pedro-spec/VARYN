"""17S-27: opt-in metadata-only local UI callback audit.

Observes bounded application callback outcomes in THIS running VARYN process.
Never inspects clipboard contents, prompt, reply, browser tabs, credentials,
account state, history, local files, or provider HTTP. No disk/network I/O.

Programmatic Button.invoke() and fake mocks can also cause UI callbacks.
Therefore this is NOT proof of a physical human click, remote paste, official
app login, provider-origin authentication or automatic consumer-app sync.
"""
from collections import Counter
import json

_PROVIDERS = frozenset(("chatgpt", "claude", "gemini"))
_CODES = frozenset((
    "homepage_launch_requested",
    "approved_packet_copied",
    "reviewed_reply_staged",
    "working_note_reviewed",
    "project_context_included_in_copy",
    "relay_state_discarded",
    "working_context_discarded",
))
_PROVIDER_REQUIRED = frozenset((
    "homepage_launch_requested",
    "approved_packet_copied",
    "reviewed_reply_staged",
    "project_context_included_in_copy",
))
_MAX_EVENTS = 32


class PilotAuditRejected(ValueError):
    """Invalid, overflowed or non-owner active audit event."""


class PilotLocalAudit:
    """Bounded audit of successful local callback outcomes, never attestation."""

    def __init__(self):
        self._active = False
        self._events = []

    def start(self):
        if self._active:
            raise PilotAuditRejected("Audit already active; explicitly reset first")
        self._events.clear()
        self._active = True
        return self.snapshot()

    def record(self, code, *, provider=None):
        if not self._active:
            return False
        if type(code) is not str or code not in _CODES:
            raise PilotAuditRejected("Only recognized local callback outcomes")
        if code in _PROVIDER_REQUIRED:
            if type(provider) is not str or provider not in _PROVIDERS:
                raise PilotAuditRejected("Official provider identifier required")
        elif provider is not None:
            raise PilotAuditRejected("Provider identifier not allowed for this event")
        if len(self._events) >= _MAX_EVENTS:
            # Refuse to silently drop later events and produce a false complete log.
            raise PilotAuditRejected("Local callback audit capacity reached")
        self._events.append((code, provider))
        return True

    def reset(self):
        self._active = False
        self._events.clear()

    def snapshot(self):
        counts = Counter(code for code, _ in self._events)
        targets = sorted({
            provider for code, provider in self._events
            if code == "approved_packet_copied"
        })
        return {
            "format": "varyn.local_pilot_callbacks.v1",
            "active": self._active,
            "events_observed": len(self._events),
            "event_capacity": _MAX_EVENTS,
            "event_counts": {code: counts.get(code, 0) for code in sorted(_CODES)},
            "approved_clipboard_targets": targets,
            "local_two_target_attempt_observed": (
                len(targets) >= 2 and
                counts.get("reviewed_reply_staged", 0) >= 1
            ),
            "recording_scope": "in_process_callback_outcomes_only",
            "independent_human_click_verified": False,
            "official_account_authenticated": False,
            "remote_paste_or_delivery_verified": False,
            "pasted_reply_provider_origin_verified": False,
            "official_consumer_history_read_verified": False,
            "official_consumer_history_write_verified": False,
            "automatic_bidirectional_sync_verified": False,
            "production_private_access_authorized": False,
            "tamper_evident_or_signed": False,
            "stored_on_disk_or_uploaded_by_recorder": False,
        }

    def export_fixed_json(self):
        # The report contains ONLY allowlisted event codes, provider names
        # and constant false-claim flags. No event times, IDs or user content.
        return json.dumps(self.snapshot(), sort_keys=True, ensure_ascii=True)
