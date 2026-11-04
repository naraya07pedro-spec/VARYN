"""Checkpoint 17A: official-app sync capability gate and offline reconciliation.

This module does NOT access ChatGPT, Claude, Gemini, their app histories,
any network, or any local disk. It only models synthetic revision markers.
Export/Takeout support is NOT evidence for an official-app write API.

No operation returned by this module can be dispatched. A future, separately
reviewed connector must prove read + write authority and verify revision
preconditions before any state-changing action is even considered.
"""
from dataclasses import dataclass
from types import MappingProxyType
import argparse
import json
import re

_SYNC_REFS = MappingProxyType({
    "chatgpt": "https://help.openai.com/en/articles/7260999-exporting-your-chatgpt-history-and-data",
    "claude": "https://support.claude.com/en/articles/9450526-export-your-claude-data",
    "gemini": "https://support.google.com/gemini/answer/16920332",
})
_ID = re.compile(r"\A[A-Za-z0-9][A-Za-z0-9_.:-]{0,63}\Z")
_DIGEST = re.compile(r"\A[0-9a-f]{64}\Z")
_MAX_RECORDS = 100
_MAX_REVISION = 10**15


class SyncContractError(ValueError):
    """A structurally invalid or untrusted reconciliation fixture."""


def official_app_capability(provider):
    """Never claim official-app bidirectional capability from model API support.

    The known official guides document data export. They do not demonstrate a
    supported app-history write API. This is a conservative capability report,
    not a universal assertion that no such API could ever become available.
    """
    if type(provider) is not str or provider not in _SYNC_REFS:
        raise SyncContractError("Unknown official app provider")
    return {
        "format": "varyn.official_app_capability.v1",
        "provider": provider,
        "official_app_read_verified": False,
        "official_app_write_verified": False,
        "automatic_two_way_sync_verified": False,
        "status": "blocked_pending_provider_evidence",
        "export_documentation": _SYNC_REFS[provider],
        "model_api_is_app_sync": False,
        "can_dispatch": False,
    }


@dataclass(frozen=True)
class SyncMarker:
    """Synthetic metadata only, not transcript content or real remote data."""
    record_id: str
    revision: int
    digest: str
    deleted: bool = False

    def __post_init__(self):
        if (type(self.record_id) is not str or
                not _ID.fullmatch(self.record_id)):
            raise SyncContractError("Invalid synthetic record ID")
        if (type(self.revision) is not int or
                not 1 <= self.revision <= _MAX_REVISION):
            raise SyncContractError("Invalid synthetic revision")
        if type(self.deleted) is not bool:
            raise SyncContractError("Invalid deletion marker")
        if (type(self.digest) is not str or
                (self.digest != "" if self.deleted else
                 _DIGEST.fullmatch(self.digest) is None)):
            raise SyncContractError("Invalid synthetic digest or tombstone")


def _check_snapshot(snapshot):
    if type(snapshot) is not dict or len(snapshot) > _MAX_RECORDS:
        raise SyncContractError("Invalid or oversized snapshot")
    for identifier, marker in snapshot.items():
        if (type(identifier) is not str or
                type(marker) is not SyncMarker or
                marker.record_id != identifier):
            raise SyncContractError("Snapshot marker does not match its key")


def _state(marker):
    return None if marker is None else (marker.deleted, marker.digest)


def _decision(record_id, outcome, base, local, official):
    return {
        "record_id": record_id,
        "outcome": outcome,
        "base_revision": None if base is None else base.revision,
        "local_revision": None if local is None else local.revision,
        "official_revision": None if official is None else official.revision,
        "needs_human_review": outcome != "already_equal",
        "can_dispatch": False,
    }


def plan_synthetic_reconciliation(base, local, official, *,
                                  synthetic_fixture=False):
    """Compute deterministic, review-only changes for COMPLETE mock snapshots.

    A missing record present in the base is UNKNOWN, not a deletion. Deletions
    require explicit tombstones. No payload/text is ever placed in the result.
    Revisions must increase if an existing record changes; otherwise fail
    closed to a conflict. All candidates are previews, never actual writes.
    """
    if synthetic_fixture is not True:
        raise PermissionError("Reconciliation is synthetic-fixture-only")
    for snapshot in (base, local, official):
        _check_snapshot(snapshot)
    keys = sorted(set(base) | set(local) | set(official))
    if len(keys) > _MAX_RECORDS:
        raise SyncContractError("Combined synthetic snapshot limit exceeded")

    decisions = []
    for record_id in keys:
        b = base.get(record_id)
        l = local.get(record_id)
        o = official.get(record_id)

        if b is not None and (l is None or o is None):
            outcome = "incomplete_snapshot_review"
        elif (b is not None and
              (l.revision < b.revision or o.revision < b.revision)):
            outcome = "revision_regressed_review"
        elif (b is not None and
              ((_state(l) != _state(b) and l.revision <= b.revision) or
               (_state(o) != _state(b) and o.revision <= b.revision))):
            outcome = "revision_conflict_review"
        elif _state(l) == _state(o):
            outcome = "already_equal"
        elif b is None and l is not None and o is None:
            outcome = ("official_delete_review" if l.deleted else
                       "official_create_preview")
        elif b is None and o is not None and l is None:
            outcome = ("local_delete_review" if o.deleted else
                       "local_import_preview")
        elif b is None:
            outcome = "concurrent_creation_conflict_review"
        elif _state(l) == _state(b):
            outcome = ("local_delete_review" if o.deleted else
                       "local_import_preview")
        elif _state(o) == _state(b):
            outcome = ("official_delete_review" if l.deleted else
                       "official_update_preview")
        else:
            outcome = "divergent_edits_conflict_review"
        decisions.append(_decision(record_id, outcome, b, l, o))
    return {
        "format": "varyn.synthetic_sync_plan.v1",
        "simulation_only": True,
        "official_provider_connected": False,
        "automatic_sync_available": False,
        "can_dispatch": False,
        "count": len(decisions),
        "decisions": decisions,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Offline official-app sync capability status; no connections"
    )
    parser.add_argument("--provider", choices=tuple(_SYNC_REFS))
    args = parser.parse_args(argv)
    if args.provider:
        result = official_app_capability(args.provider)
    else:
        result = {
            "format": "varyn.official_app_capabilities.v1",
            "providers": [
                official_app_capability(p) for p in sorted(_SYNC_REFS)
            ],
            "can_dispatch": False,
        }
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
