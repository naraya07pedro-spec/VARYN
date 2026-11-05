"""17S-30 | Official, user-driven ONE-TIME history import TO Gemini Apps.

This is NOT an API connector, a VARYN file importer, or bidirectional sync.
This module NEVER reads ZIP files, prompts, cookies, accounts, local paths or
transcripts; it only validates a small explicit user-consent state machine.
Opening the provider site remains a separate Tk owner action.
"""
from dataclasses import dataclass
import hashlib
import secrets
import time

_SOURCES = {
    "chatgpt": (
        "https://help.openai.com/en/articles/7260999-exporting-your-chatgpt-history-and-data",
        "ChatGPT: Settings > Data controls > Export data > Confirm export. "
        "Download the resulting ZIP from your account email/SMS.",
    ),
    "claude": (
        "https://support.claude.com/en/articles/9450526-export-your-claude-data",
        "Claude web/Desktop: Settings > Privacy > Export data. "
        "Download the resulting export from your account email.",
    ),
}
_DESTINATION = "https://gemini.google.com/"
_GOOGLE_GUIDE = "https://support.google.com/gemini/answer/16868299?hl=en"
_PRIVACY_NOTE = (
    "Gemini's native import requires a supported adult (18+) personal "
    "Google account, outside EEA/Switzerland/UK. Import a ChatGPT/Claude "
    "history .zip DIRECTLY into Gemini Settings > Import memory to Gemini "
    "> Import chats > Add. The official help page lists a 5 GB file limit "
    "and up to 5 ZIP uploads per day. Uploaded and continued chats are "
    "saved in Google Activity and may be used to improve Google services. "
    "Review the provider's current controls before uploading."
)
_FLAGS = (
    "adult_personal_account",
    "supported_region",
    "zip_export_ready",
    "google_activity_privacy_ack",
)
_TTL = 90


class NativeHistoryRejected(ValueError):
    """Stale consent, unsupported direction or attempted authority escalation."""


@dataclass(frozen=True)
class NativeHistoryPreview:
    source: str
    target: str
    export_guide: str
    import_guide: str
    acknowledgements: tuple
    consent_digest: str
    expires_at: int
    token: str
    provider_authority_verified: bool = False


def source_export_instructions(source):
    if type(source) is not str or source not in _SOURCES:
        raise NativeHistoryRejected("No documented native transfer from source")
    guide, instructions = _SOURCES[source]
    return {
        "source": source,
        "export_guide_url": guide,
        "instructions": instructions,
        "manual_export_only": True,
        "accounts_accessed": False,
        "local_zip_opened": False,
    }


def native_destination_info():
    return {
        "provider": "gemini",
        "destination_url": _DESTINATION,
        "official_help_url": _GOOGLE_GUIDE,
        "privacy_warning": _PRIVACY_NOTE,
        "source_options": sorted(_SOURCES),
        "provider_supports_manual_native_zip_import": True,
        "automatic_history_sync": False,
        "data_is_uploaded_by_varyn": False,
        "requires_owner_actions_in_official_website": True,
    }


class NativeHistoryTransfer:
    """RAM-only proof-of-owner-guidance, never proof of provider-side state."""

    def __init__(self, *, clock=None):
        self._clock = clock if clock is not None else lambda: int(time.time())
        self._pending = None
        self._source = None
        self._browser_requested = False
        self._owner_result = "not_reported"

    def _now(self):
        now = self._clock()
        if type(now) is not int or now < 1:
            raise NativeHistoryRejected("Invalid local review clock")
        return now

    def prepare(self, source, acknowledgements):
        source_export_instructions(source)
        if self._pending is not None or self._browser_requested:
            raise NativeHistoryRejected("Complete or reset previous attempt")
        if (type(acknowledgements) is not dict or
                set(acknowledgements) != set(_FLAGS) or
                any(type(acknowledgements[k]) is not bool or
                    acknowledgements[k] is not True for k in _FLAGS)):
            raise NativeHistoryRejected(
                "All four explicit eligibility/ZIP/privacy acknowledgements required"
            )
        flags = tuple((k, acknowledgements[k]) for k in _FLAGS)
        token = secrets.token_hex(16)
        digest = hashlib.sha256(repr(
            (source, _DESTINATION, _GOOGLE_GUIDE, flags, token)
        ).encode("utf-8")).hexdigest()
        self._pending = NativeHistoryPreview(
            source, _DESTINATION, _SOURCES[source][0], _GOOGLE_GUIDE,
            flags, digest, self._now() + _TTL, token,
        )
        return self._pending

    def decide(self, preview, *, approved, browser_opened, acknowledgements):
        if type(approved) is not bool or type(browser_opened) is not bool:
            raise NativeHistoryRejected("Exact boolean decision/result required")
        if (type(preview) is not NativeHistoryPreview or
                self._pending is None or preview is not self._pending):
            raise NativeHistoryRejected("Stale, replayed or forged approval")
        self._pending = None
        if not approved:
            if browser_opened:
                raise NativeHistoryRejected("Cannot claim browser open on rejection")
            return {"status": "declined", "provider_verified": False}
        if self._now() > preview.expires_at:
            raise NativeHistoryRejected("Review expired; start again")
        if (type(acknowledgements) is not dict or
                tuple((k, acknowledgements.get(k)) for k in _FLAGS) !=
                preview.acknowledgements or
                set(acknowledgements) != set(_FLAGS)):
            raise NativeHistoryRejected("Eligibility/consent changed during review")
        if not browser_opened:
            return {"status": "browser_not_opened", "provider_verified": False}
        self._source = preview.source
        self._browser_requested = True
        self._owner_result = "not_reported"
        return {
            "status": "official_browser_open_requested",
            "source": self._source, "target": "gemini",
            "provider_verified": False,
            "zip_read_by_varyn": False,
            "native_import_completed_verified": False,
        }

    def report(self, result):
        if not self._browser_requested:
            raise NativeHistoryRejected("No reviewed browser request exists")
        if type(result) is not str or result not in (
            "owner_reported_uploaded", "owner_reported_partial",
            "owner_reported_failed", "not_checked",
        ):
            raise NativeHistoryRejected("Only fixed, unverified owner result types")
        self._owner_result = result
        return self.status()

    def reset(self):
        self._pending = None
        self._source = None
        self._browser_requested = False
        self._owner_result = "not_reported"

    def status(self):
        return {
            "format": "varyn.native_manual_history_import.v1",
            "source_claim": self._source,
            "target": "gemini",
            "pending_owner_review": self._pending is not None,
            "official_browser_launch_requested": self._browser_requested,
            "owner_unverified_result": self._owner_result,
            "native_transfer_attempted_not_confirmed": self._browser_requested,
            "provider_side_import_verified": False,
            "official_account_authenticated_by_varyn": False,
            "zip_read_by_varyn": False,
            "zip_path_seen_by_varyn": False,
            "data_uploaded_by_varyn": False,
            "app_history_read_api_verified": False,
            "app_history_write_api_verified": False,
            "automatic_bidirectional_consumer_sync_verified": False,
            "network_requests_by_state_machine": 0,
        }
