"""17S-43: explicit, read-only provider model ID discovery for owner pilot.

A successful GET /models only reports untrusted model IDs exposed by that
endpoint. It proves neither API account authorization to infer, provider/model
identity, availability, quota, price, nor zero billing. No account sync.
"""
import json
import os
import re
import urllib.error
import urllib.request

from varyn.gateway_chat import KEY_ENVS

PINNED_MODEL_URLS = {
    "openrouter": "https://openrouter.ai/api/v1/models",
    "deepseek": "https://api.deepseek.com/models",
    "9router": "http://127.0.0.1:20128/v1/models",
}
MAX_REPLY_BYTES = 3 * 1024 * 1024
MAX_ITEMS = 10000
MAX_LISTED_IDS = 60
_ID_PATTERN = re.compile(r"\A[A-Za-z0-9][A-Za-z0-9._:/+-]{0,119}\Z")


class DiscoveryRejected(ValueError):
    """Errors must never quote a remote payload or an API token."""


def safe_model_id(value):
    return (type(value) is str and bool(_ID_PATTERN.fullmatch(value)) and
            ".." not in value and "//" not in value)


def parse_catalog(body):
    """Accept only normalized, bounded model IDs; discard all remote prose."""
    if type(body) is not bytes or not 1 <= len(body) <= MAX_REPLY_BYTES:
        raise DiscoveryRejected("Model list payload missing or oversized")
    try:
        raw = json.loads(body)
        if type(raw) is not dict or type(raw.get("data")) is not list:
            raise ValueError()
        data = raw["data"]
        if not 0 <= len(data) <= MAX_ITEMS:
            raise ValueError()
        seen = set()
        selected = []
        for entry in data:
            if type(entry) is not dict:
                continue
            model_id = entry.get("id")
            if not safe_model_id(model_id) or model_id in seen:
                continue
            seen.add(model_id)
            selected.append(model_id)
        # Do not turn remote labels/pricing/marketing copy into authorities.
        selected.sort()
        return {
            "model_ids": tuple(selected[:MAX_LISTED_IDS]),
            "total_sanitized_model_ids": len(selected),
            "list_truncated": len(selected) > MAX_LISTED_IDS,
            "raw_items_reported": len(data),
            "provider_model_access_verified": False,
            "price_or_free_tier_verified": False,
            "provider_identity_independently_verified": False,
            "native_consumer_history_synced": False,
        }
    except (ValueError, TypeError, KeyError, UnicodeError, OverflowError):
        raise DiscoveryRejected("Invalid provider model catalog response") from None


def get_pinned_models(provider, key, timeout_seconds=10):
    """Single request, no redirects, fixed host, localhost proxy bypass."""
    if provider not in PINNED_MODEL_URLS:
        raise DiscoveryRejected("Unsupported model discovery provider")
    if type(key) is not str or not key.strip():
        raise DiscoveryRejected("Credential missing on owner machine")
    if type(timeout_seconds) not in (int, float) or not 1 <= timeout_seconds <= 30:
        raise DiscoveryRejected("Invalid discovery timeout")
    request = urllib.request.Request(
        PINNED_MODEL_URLS[provider], method="GET",
        headers={"Authorization": "Bearer " + key,
                 "Accept": "application/json"},
    )

    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None

    handlers = [NoRedirect()]
    if provider == "9router":
        handlers.append(urllib.request.ProxyHandler({}))
    try:
        with urllib.request.build_opener(*handlers).open(
            request, timeout=timeout_seconds,
        ) as res:
            data = res.read(MAX_REPLY_BYTES + 1)
    except (urllib.error.HTTPError, urllib.error.URLError,
            TimeoutError, OSError, ValueError):
        # HTTP response bodies can include sensitive data. Never echo them.
        raise DiscoveryRejected("Model catalog request failed") from None
    return parse_catalog(data)


def discover_once(provider, *, owner_approved=False,
                  network_enabled=False, authorized_upstream=False,
                  environment=None, transport=None):
    """Fresh explicit owner permission. No automatic discovery or retry."""
    if (type(provider) is not str or provider not in PINNED_MODEL_URLS or
            type(network_enabled) is not bool or
            type(authorized_upstream) is not bool):
        raise DiscoveryRejected("Invalid provider selection or policy")
    if owner_approved is not True or network_enabled is not True:
        raise PermissionError("Model catalog network request not approved")
    if provider == "9router" and authorized_upstream is not True:
        raise PermissionError("9Router upstream account not authorized")
    env = os.environ if environment is None else environment
    key = env.get(KEY_ENVS[provider], "")
    if type(key) is not str or not key.strip():
        raise DiscoveryRejected("Expected OS environment API credential")
    try:
        result = (transport(provider, key, 10) if transport is not None else
                  get_pinned_models(provider, key, 10))
    except (urllib.error.HTTPError, urllib.error.URLError,
            TimeoutError, OSError, ValueError):
        raise DiscoveryRejected("Model catalog request failed") from None
    if type(result) is not dict or result.get("native_consumer_history_synced") is not False:
        raise DiscoveryRejected("Unrecognized model list result")
    ids = result.get("model_ids")
    count = result.get("total_sanitized_model_ids")
    truncated = result.get("list_truncated")
    if (type(ids) is not tuple or len(ids) > MAX_LISTED_IDS or
            any(not safe_model_id(x) for x in ids) or len(set(ids)) != len(ids) or
            type(count) is not int or not len(ids) <= count <= MAX_ITEMS or
            type(truncated) is not bool or
            truncated != (count > MAX_LISTED_IDS)):
        raise DiscoveryRejected("Invalid normalized model list result")
    return {
        "provider": provider,
        "ids": tuple(result["model_ids"]),
        "total_sanitized_model_ids": result["total_sanitized_model_ids"],
        "list_truncated": result["list_truncated"],
        "provider_model_access_verified": False,
        "actual_provider_identity_verified": False,
        "price_or_free_tier_verified": False,
        "native_consumer_history_synced": False,
        "one_owner_approved_model_list_request": True,
    }
