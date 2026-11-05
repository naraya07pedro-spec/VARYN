"""17S-37: completed synthetic three-app session, user-approved DPAPI archive.

Strictly read-only after load; no authenticated account history, remote calls,
consent restoration, cross-device backup or automatic bidirectional sync.
"""
from dataclasses import asdict
import hashlib
import json
from pathlib import Path

from varyn.dpapi_vault import write_sealed, read_sealed
from varyn.guided_reply_ledger import GuidedReplyLedger, GuidedReplyRecord

FORMAT = "varyn.completed_synthetic_three_app_archive.v1"
SUFFIX = ".varyn-archive"
FIELDS = frozenset(("format", "records", "read_only", "manual_only",
                    "provider_origins_verified", "consumer_history_authenticated",
                    "automatic_sync", "relay_authority_restored"))
RECORD_FIELDS = frozenset(("stage", "claimed_provider", "reply_text",
                           "outbound_request_id", "outbound_digest",
                           "reply_digest", "local_chain_digest",
                           "provider_origin_verified"))
MAX_BYTES = 16000


class ArchiveRejected(ValueError):
    """Rejected archive; avoid leaking untrusted content via exceptions."""


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True).encode("utf-8")


def validate(value):
    if type(value) is not dict or set(value) != FIELDS:
        raise ArchiveRejected("Unrecognized archive schema")
    if (value["format"] != FORMAT or value["read_only"] is not True or
            value["manual_only"] is not True or
            any(value[key] is not False for key in (
                "provider_origins_verified", "consumer_history_authenticated",
                "automatic_sync", "relay_authority_restored")) or
            type(value["records"]) is not list or len(value["records"]) != 3):
        raise ArchiveRejected("Invalid archive authority/completion flags")
    records = []
    for i, raw in enumerate(value["records"], 1):
        if type(raw) is not dict or set(raw) != RECORD_FIELDS:
            raise ArchiveRejected("Invalid record fields")
        try:
            rec = GuidedReplyRecord(**raw)
        except (TypeError, ValueError) as exc:
            raise ArchiveRejected("Invalid local synthetic reply") from exc
        if rec.stage != i:
            raise ArchiveRejected("Invalid stage order")
        records.append(asdict(rec))
    result = {
        "format": FORMAT, "records": records,
        "read_only": True, "manual_only": True,
        "provider_origins_verified": False,
        "consumer_history_authenticated": False,
        "automatic_sync": False, "relay_authority_restored": False,
    }
    if len(encode(result)) > MAX_BYTES:
        raise ArchiveRejected("Archive too large")
    return result


def snapshot(ledger, *, phase):
    if type(ledger) is not GuidedReplyLedger or phase != "completed":
        raise ArchiveRejected("Only completed synthetic three-stage sessions")
    if ledger.count != 3:
        raise ArchiveRejected("All three locally reviewed replies required")
    return validate({
        "format": FORMAT, "records": [asdict(x) for x in ledger._records],
        "read_only": True, "manual_only": True,
        "provider_origins_verified": False,
        "consumer_history_authenticated": False,
        "automatic_sync": False, "relay_authority_restored": False,
    })


def digest(value):
    return hashlib.sha256(encode(validate(value))).hexdigest()


def review(value):
    return json.dumps(validate(value), indent=2, sort_keys=True)


def display(value):
    result = validate(value)
    parts = ["VARYN | READ-ONLY SYNTHETIC THREE-AI ARCHIVE",
             "Locally reviewed USER-PASTED replies; claimed origins "
             "UNVERIFIED. No permissions restored, no native app sync."]
    for rec in result["records"]:
        parts.append(
            "Stage " + str(rec["stage"]) + " | claimed source " +
            rec["claimed_provider"] + " | unverified\nLocal reply SHA256 " +
            rec["reply_digest"] + "\nUNTRUSTED COMPLETE REPLY:\n" +
            repr(rec["reply_text"])
        )
    return "\n\n".join(parts)


def _filename(path):
    p = Path(path)
    if not p.name.lower().endswith(SUFFIX):
        raise ArchiveRejected("Select a .varyn-archive file")
    return p


def save_new(path, value):
    return write_sealed(_filename(path), encode(validate(value)))


def load_readonly(path):
    data = read_sealed(_filename(path))
    if len(data) > MAX_BYTES:
        raise ArchiveRejected("Archive too large")
    try:
        parsed = json.loads(data.decode("utf-8"))
    except (ValueError, UnicodeError) as exc:
        raise ArchiveRejected("Invalid encrypted archive") from exc
    return validate(parsed)
