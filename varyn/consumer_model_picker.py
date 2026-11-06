"""Official model picker metadata, fetched only after owner clicks Connect.

Pricing is displayed as a provider-reported snapshot, NOT a hard billing cap.
No silent fallback to free models, no model-ID guesswork, no key persistence.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import json
import re
import urllib.error
import urllib.request

from varyn.model_discovery import PINNED_MODEL_URLS, safe_model_id

MAX_BYTES = 8 * 1024 * 1024
MODEL_MAX = 2000
_NAME = re.compile(r"\A[^\x00-\x1f\x7f]{1,115}\Z")


class ModelListError(ValueError):
    pass


@dataclass(frozen=True)
class ListedModel:
    provider: str
    id: str
    label: str
    input_usd_m: str | None
    output_usd_m: str | None
    price_source: str


# DeepSeek GET /models does not document prices. Rates below are the
# published official *peak* cache-miss/output prices on 2026-11-06.
# Prompt user to independently recheck the pricing page before acceptance.
DEEPSEEK_SNAPSHOT = {
    "deepseek-flash": ("0.30", "1.20"),
    "deepseek-v4-pro": ("1.32", "3.96"),
}
PRICING_PAGES = {
    "openrouter": "https://openrouter.ai/models",
    "deepseek": "https://api-docs.deepseek.com/quick_start/pricing/",
}
KEY_PAGES = {
    "openrouter": "https://openrouter.ai/settings/keys",
    "deepseek": "https://platform.deepseek.com/api_keys",
}


def _rate(value):
    try:
        if type(value) not in (str, int, float):
            return None
        decimal = Decimal(str(value))
        if not decimal.is_finite() or not 0 <= decimal <= 0.001:
            return None
        return format(decimal * 1000000, "f")
    except (ValueError, InvalidOperation):
        return None


def parse_list(provider, raw):
    if provider not in ("openrouter", "deepseek"):
        raise ModelListError("Unsupported AI provider")
    if type(raw) is not bytes or not 1 <= len(raw) <= MAX_BYTES:
        raise ModelListError("Model catalog too large or missing")
    try:
        data = json.loads(raw)
        if type(data) is not dict or type(data.get("data")) is not list:
            raise ValueError()
        if len(data["data"]) > 12000:
            raise ValueError()
        result = []
        seen = set()
        for item in data["data"]:
            if type(item) is not dict:
                continue
            ident = item.get("id")
            if not safe_model_id(ident) or ident in seen:
                continue
            seen.add(ident)
            label = item.get("name")
            if type(label) is not str or not _NAME.fullmatch(label):
                label = ident
            if provider == "openrouter":
                prices = item.get("pricing")
                prices = prices if type(prices) is dict else {}
                rate_in = _rate(prices.get("prompt"))
                rate_out = _rate(prices.get("completion"))
                source = "Provider API /models (USD/1M, not a billing cap)"
            else:
                pair = DEEPSEEK_SNAPSHOT.get(ident)
                rate_in, rate_out = pair if pair is not None else (None, None)
                source = ("Published peak rate snapshot 2026-11-06; "
                          "verify actual pricing before enabling")
            result.append(ListedModel(provider, ident, label, rate_in, rate_out, source))
            if len(result) >= MODEL_MAX:
                break
        if not result:
            raise ValueError()
        return tuple(sorted(result, key=lambda row: (row.label.casefold(), row.id)))
    except (TypeError, UnicodeError, ValueError, OverflowError):
        raise ModelListError("Invalid provider model catalog") from None


def fetch_models(provider, credential, *, timeout=12, transport=None):
    if provider not in ("openrouter", "deepseek"):
        raise ModelListError("Unsupported AI provider")
    if type(credential) is not str or (
        provider == "deepseek" and not 8 <= len(credential) <= 1000
    ) or (provider == "openrouter" and credential and
          not 8 <= len(credential) <= 1000):
        raise ModelListError("API key is missing or invalid")
    if transport is not None:
        return parse_list(provider, transport(provider, credential))
    endpoint = PINNED_MODEL_URLS[provider]
    headers = {"Accept": "application/json"}
    # OpenRouter's global catalog currently responds without auth. This is
    # best-effort public browsing, not proof a model/account is eligible.
    # DeepSeek documents bearer auth, so it always requires the owner key.
    if credential:
        headers["Authorization"] = "Bearer " + credential
    request = urllib.request.Request(endpoint, headers=headers, method="GET")
    class DenyRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None
    try:
        with urllib.request.build_opener(DenyRedirect()).open(
            request, timeout=timeout,
        ) as response:
            data = response.read(MAX_BYTES + 1)
    except (urllib.error.HTTPError, urllib.error.URLError, OSError,
            TimeoutError, ValueError):
        # Never surface URL/header/exception; auth token could be in request.
        raise ModelListError("Unable to retrieve provider models") from None
    return parse_list(provider, data)
