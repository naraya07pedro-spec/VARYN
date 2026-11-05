"""17S-41: OFFLINE readiness and content-free owner acceptance evidence.

This observes the VARYN adapter only. No signed account authentication,
provider attestation, real billing verification or native consumer-app sync.
An owner-selected receipt is intentionally metadata-only and NEW-FILE ONLY.
"""
from datetime import datetime, timezone
from decimal import Decimal
import json
import os
from pathlib import Path

from varyn.gateway_chat import KEY_ENVS
from varyn.model_registry import Offer
from varyn.providers import ModelReply

FORMAT = "varyn.local_provider_observation.v1"


class ReadinessRejected(ValueError):
    """No secrets or content in messages."""


def readiness(offer, *, live_capability=False, enabled_network=False,
              upstream_authorized=False, environment=None):
    """Only reads whether a key is configured. NEVER opens sockets or logs it."""
    if type(offer) is not Offer or any(type(b) is not bool for b in (
            live_capability, enabled_network, upstream_authorized)):
        raise ReadinessRejected("Invalid gateway readiness inputs")
    if environment is None:
        environment = os.environ
    if offer.provider == "fake":
        return {
            "format": "varyn.provider_readiness.v1",
            "provider": "fake", "model": offer.model,
            "mode": "simulation_only", "ready_for_live_attempt": False,
            "network_calls": 0, "key_present": False, "key_env_name": None,
            "limitations": "FAKE has no external AI connectivity",
        }
    if offer.provider not in KEY_ENVS:
        raise ReadinessRejected("Unsupported provider")
    key_name = KEY_ENVS[offer.provider]
    key = environment.get(key_name, "")
    key_present = type(key) is str and bool(key.strip())
    missing = []
    if not offer.eligible(datetime.now(timezone.utc).date()):
        missing.append("fresh_owner_reviewed_price_and_fixed_route")
    if not live_capability:
        missing.append("desktop_gateway_capability")
    if not enabled_network:
        missing.append("one_request_network_permission")
    if offer.provider == "9router" and not upstream_authorized:
        missing.append("9router_upstream_permission")
    if not key_present:
        missing.append("os_environment_credential")
    return {
        "format": "varyn.provider_readiness.v1",
        "provider": offer.provider, "model": offer.model,
        "mode": "attempt_only_not_connection_tested",
        "ready_for_live_attempt": not missing,
        "missing": missing, "network_calls": 0,
        "key_env_name": key_name, "key_present": key_present,
        "provider_endpoint_tested": False,
        "provider_account_verified": False,
        "actual_price_verified": False,
        "native_consumer_sync": False,
    }


def local_observation(result, *, quoted_offer, reported_at=None):
    """Bounded, content-free record for a successful *local adapter parse*."""
    if type(quoted_offer) is not Offer or quoted_offer.provider == "fake":
        raise ReadinessRejected("Only a candidate real API response is admissible")
    if type(result) is not dict:
        raise ReadinessRejected("Expected a gateway result")
    reply = result.get("reply")
    if (type(reply) is not ModelReply or
            reply.provider != quoted_offer.provider or
            reply.model != quoted_offer.model or
            type(result.get("estimated_micro_usd")) is not int or
            not 0 <= result["estimated_micro_usd"] <= 10**9 or
            result.get("actual_billing_cap_enforced") is not False or
            result.get("native_consumer_history_sync") is not False):
        raise ReadinessRejected("Invalid observation source or false authority")
    usage = reply.usage
    if type(usage) is not dict:
        usage = {}
    safe_usage = {}
    for name in ("input_tokens", "output_tokens"):
        value = usage.get(name)
        if type(value) is int and 0 <= value <= 100000000:
            safe_usage[name] = value
    claimed = result.get("provider_reported_model")
    if claimed is not None and (type(claimed) is not str or
                                not 1 <= len(claimed) <= 120 or
                                not all(ch.isalnum() or ch in "-._/+:" for ch in claimed)):
        claimed = None
    if reported_at is None:
        reported_at = datetime.now(timezone.utc)
    if type(reported_at) is not datetime or reported_at.tzinfo is None:
        raise ReadinessRejected("An aware timestamp is required")
    return {
        "format": FORMAT, "observed_at_utc": reported_at.astimezone(
            timezone.utc).isoformat(),
        "selected_provider": quoted_offer.provider,
        "selected_model": quoted_offer.model,
        "provider_reported_model_UNVERIFIED": claimed,
        "selected_model_equals_reported": (
            None if claimed is None else claimed == quoted_offer.model),
        "reported_token_counters_NOT_AUDITED": safe_usage,
        "owner_price_quote_date": quoted_offer.price_date,
        "owner_estimated_micro_usd_NOT_BILLING": result["estimated_micro_usd"],
        "real_amount_charged_usd": None,
        "local_adapter_parsed_response": True,
        "provider_identity_authenticated": False,
        "actual_cost_verified": False,
        "native_consumer_app_history_synced": False,
        "real_owner_device_independently_tested": False,
        "request_text_included": False,
        "response_text_included": False,
        "credential_included": False,
    }


def receipt_json(value):
    if type(value) is not dict or value.get("format") != FORMAT:
        raise ReadinessRejected("Invalid observation format")
    required_false = (
        "provider_identity_authenticated", "actual_cost_verified",
        "native_consumer_app_history_synced",
        "real_owner_device_independently_tested", "request_text_included",
        "response_text_included", "credential_included",
    )
    if any(value.get(k) is not False for k in required_false):
        raise ReadinessRejected("Receipt may not assert provider authority")
    if value.get("local_adapter_parsed_response") is not True:
        raise ReadinessRejected("Receipt is not an observed adapter response")
    if set(value) != {
        "format", "observed_at_utc", "selected_provider", "selected_model",
        "provider_reported_model_UNVERIFIED", "selected_model_equals_reported",
        "reported_token_counters_NOT_AUDITED", "owner_price_quote_date",
        "owner_estimated_micro_usd_NOT_BILLING", "real_amount_charged_usd",
        "local_adapter_parsed_response", *required_false,
    }:
        raise ReadinessRejected("Unknown receipt fields")
    # Domain values are constrained rather than copied from external text.
    if value["selected_provider"] not in ("openrouter", "deepseek", "9router"):
        raise ReadinessRejected("Unsupported receipt provider")
    if type(value["selected_model"]) is not str or len(value["selected_model"]) > 120:
        raise ReadinessRejected("Invalid receipt model")
    if value["real_amount_charged_usd"] is not None:
        raise ReadinessRejected("Billing was not independently verified")
    if (type(value["owner_estimated_micro_usd_NOT_BILLING"]) is not int or
            not 0 <= value["owner_estimated_micro_usd_NOT_BILLING"] <= 10**9):
        raise ReadinessRejected("Bad estimated usage")
    if (type(value["reported_token_counters_NOT_AUDITED"]) is not dict or
            set(value["reported_token_counters_NOT_AUDITED"]) -
                {"input_tokens", "output_tokens"}):
        raise ReadinessRejected("Bad usage counters")
    if any(type(n) is not int or not 0 <= n <= 100000000
           for n in value["reported_token_counters_NOT_AUDITED"].values()):
        raise ReadinessRejected("Invalid provider token usage")
    if value["selected_model_equals_reported"] not in (True, False, None):
        raise ReadinessRejected("Invalid model mismatch flag")
    try:
        timestamp = datetime.fromisoformat(value["observed_at_utc"])
        if timestamp.tzinfo is None:
            raise ValueError("No UTC offset")
    except (ValueError, TypeError, KeyError):
        raise ReadinessRejected("Invalid observation time") from None
    encoded = json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False)
    if len(encoded.encode("utf-8")) > 4096:
        raise ReadinessRejected("Observation too large")
    return encoded + "\n"


def save_new(path, value):
    """Explicit owner-path NEW-only, no plaintext conversational content."""
    text = receipt_json(value)
    target = Path(path)
    if target.suffix.lower() != ".json" or target.name.endswith("."):
        raise ReadinessRejected("Expected an explicit .json receipt filename")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(target, flags, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        try:
            target.unlink(missing_ok=True)
        except OSError:
            pass
        raise
    return target
