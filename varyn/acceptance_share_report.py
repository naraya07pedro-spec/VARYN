"""Minimal redacted offline share report for VARYN owner acceptance.

A share report makes local evidence inspectable in support chats without
revealing credentials, full model output, paths, private conversations, raw
request IDs, hashes, costs, account identifiers or exact timestamps.

It CANNOT independently authenticate provider billing or prove a genuine
request was made from a particular device. Do not use it as a release gate.
"""
from __future__ import annotations

import json

from varyn.owner_provider_acceptance import OwnerProviderAcceptance


_FORMAT = "varyn.owner_acceptance_share.v1"
_ALLOWED_RESULTS = frozenset({
    "verification_passed", "verification_failed",
    "approved_model_request_denied", "approved_public_read_denied",
    "needs_review", "running_or_interrupted",
})
_PROVIDER = frozenset({"openrouter", "deepseek"})


def _attempt(value):
    return value if type(value) is int and value in (0, 1) else None


def create_redacted_acceptance_report(record):
    """Fixed-schema privacy-minimized evidence. No untrusted strings copied.

    Only a valid full local checksum permits factual and usage fields.
    'source_kind' describes local adapter CONFIGURATION, not a remote
    attestation; a user with DB write access can forge local checksums.
    """
    verdict = OwnerProviderAcceptance.acceptance_gate(record)
    category = verdict["status"]
    intact = (
        type(record) is dict
        and record.get("local_digest_matches") is True
        and category not in ("receipt_untrusted", "no_receipt")
    )
    result = (record.get("status")
              if intact and type(record.get("status")) is str
              and record["status"] in _ALLOWED_RESULTS
              else "unknown")
    adapter = (
        "standard_varyn_adapter_configured"
        if intact and record.get("source_kind") ==
        "configured_network_adapters" else
        "injected_or_custom_adapter"
        if intact and record.get("source_kind") ==
        "injected_test_or_custom_transport" else "unknown"
    )
    identifier = record.get("provider_response_id_sha256") if intact else None
    reported_id_present = (
        type(identifier) is str
        and len(identifier) == 64
        and all(c in "0123456789abcdef" for c in identifier)
    )
    usage_available = (
        intact
        and type(record.get("input_tokens_reported")) is int
        and type(record.get("output_tokens_reported")) is int
        and record["input_tokens_reported"] >= 0
        and record["output_tokens_reported"] >= 0
    )
    summary = {
        "format": _FORMAT,
        "local_smoke_record_found": type(record) is dict,
        "local_receipt_integrity": (
            "intact" if intact else
            "no_record" if record is None else
            "not_verified"
        ),
        "local_evidence_category": category,
        "smoke_status": result,
        "provider": (
            record.get("provider") if intact and
            type(record.get("provider")) is str
            and record["provider"] in _PROVIDER else "unknown"
        ),
        "adapter_configuration": adapter,
        "public_gets_attempted": (
            _attempt(record.get("public_reads_attempted"))
            if intact else None
        ),
        "model_requests_attempted": (
            _attempt(record.get("model_requests_attempted"))
            if intact else None
        ),
        "fact_match_against_tool_observation": (
            record.get("fact_matches_tool") == 1
            if intact and type(record.get("fact_matches_tool")) is int
            and record["fact_matches_tool"] in (0, 1) else None
        ),
        "provider_response_id_reported": (
            reported_id_present if intact else None
        ),
        "provider_input_output_usage_reported": (
            usage_available if intact else None
        ),
        "provider_account_independently_authenticated": False,
        "actual_provider_charges_independently_verified": False,
        "model_weights_independently_attested": False,
        "safe_to_enable_unattended_spend": False,
        "next_action": (
            "run_one_owner_reviewed_smoke_on_windows"
            if record is None else
            "inspect_record_or_manual_provider_account_check"
        ),
    }
    return summary


def render_redacted_acceptance_report(record):
    return json.dumps(create_redacted_acceptance_report(record),
                      indent=2, sort_keys=True, ensure_ascii=True)
