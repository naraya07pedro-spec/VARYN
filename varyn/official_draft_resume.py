"""17S-33: opt-in DPAPI draft persistence for synthetic manual workbench fields.

Only owner-authored synthetic task/note/scope/target are persisted. No returned
provider text, relay state, approvals, history, cookie, key or provider access.
No automatic saves, restores, network request or database migrations.
"""
import hashlib
import json
from pathlib import Path

from varyn.dpapi_vault import read_sealed, write_sealed
from varyn.official_manual_relay import OFFICIAL_APP_LINKS, _bounded_text
from varyn.relay_working_context import _scope, _text
from varyn.safety import assert_no_obvious_secrets

_FORMAT = "varyn.synthetic_official_draft.v1"
_FIELDS = frozenset({
    "format", "target", "project", "topic", "task", "note",
    "manual_only", "provider_history_authenticated",
    "automatic_bidirectional_sync", "pasted_reply_persisted",
})
_MAX_PAYLOAD = 4096


class SyntheticDraftRejected(ValueError):
    """Rejected unsafe or ambiguous local workbench draft without echoing it."""


def validate_draft(value):
    if type(value) is not dict or set(value) != _FIELDS:
        raise SyntheticDraftRejected("Unrecognized synthetic draft schema")
    if (value.get("format") != _FORMAT or value.get("manual_only") is not True or
            value.get("provider_history_authenticated") is not False or
            value.get("automatic_bidirectional_sync") is not False or
            value.get("pasted_reply_persisted") is not False):
        raise SyntheticDraftRejected("Unsupported draft version or authority claims")
    target = value["target"]
    if type(target) is not str or target not in OFFICIAL_APP_LINKS:
        raise SyntheticDraftRejected("Invalid official destination")
    try:
        project, topic = _scope(value["project"], value["topic"])
        task = _bounded_text(value["task"], 1000)
        note = _text(value["note"])
        if not task.startswith("SYNTHETIC:") or task != value["task"] or note != value["note"]:
            raise SyntheticDraftRejected("Draft requires exact synthetic-only text")
        assert_no_obvious_secrets(task, note)
    except (ValueError, TypeError) as error:
        raise SyntheticDraftRejected("Unsafe synthetic workbench draft") from error
    result = {
        "format": _FORMAT,
        "target": target, "project": project, "topic": topic,
        "task": task, "note": note,
        "manual_only": True,
        "provider_history_authenticated": False,
        "automatic_bidirectional_sync": False,
        "pasted_reply_persisted": False,
    }
    if len(encode_draft(result)) > _MAX_PAYLOAD:
        raise SyntheticDraftRejected("Synthetic draft exceeds maximum size")
    return result


def make_draft(*, target, project, topic, task, note):
    return validate_draft({
        "format": _FORMAT,
        "target": target, "project": project, "topic": topic,
        "task": task, "note": note,
        "manual_only": True,
        "provider_history_authenticated": False,
        "automatic_bidirectional_sync": False,
        "pasted_reply_persisted": False,
    })


def encode_draft(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
    ).encode("utf-8")


def review_text(value):
    data = encode_draft(validate_draft(value))
    return json.dumps(json.loads(data), indent=2, sort_keys=True)


def digest(value):
    return hashlib.sha256(encode_draft(validate_draft(value))).hexdigest()


def _path(value):
    path = Path(value)
    if path.suffix.lower() != ".varyn":
        raise SyntheticDraftRejected("Choose a .varyn draft filename")
    return path


def save_new(path, value):
    """Encrypt and atomically publish a NEW file; never overwrite prior drafts."""
    payload = encode_draft(validate_draft(value))
    return write_sealed(_path(path), payload)


def load_existing(path):
    """Read owner-selected DPAPI file; decrypt then reject untrusted schema."""
    raw = read_sealed(_path(path))
    if len(raw) > _MAX_PAYLOAD:
        raise SyntheticDraftRejected("Draft too large")
    try:
        value = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeError) as error:
        raise SyntheticDraftRejected("Invalid encrypted draft") from error
    return validate_draft(value)
