"""17S-39: offline-only, consent-gated candidate model registry.

Prices are explicitly owner-reviewed snapshots, never independently certified;
estimates are NOT billing caps. No provider accounts are accessed.
"""
from dataclasses import dataclass
from datetime import date
import re

_VALID = re.compile(r"\A[A-Za-z0-9][A-Za-z0-9._:/+-]{0,119}\Z")
_PROVIDERS = frozenset(("openrouter", "deepseek", "9router", "fake"))


class RegistryRejected(ValueError):
    pass


@dataclass(frozen=True)
class Offer:
    provider: str
    model: str
    input_micro_usd_per_million: int | None = None
    output_micro_usd_per_million: int | None = None
    price_date: str | None = None
    owner_reviewed: bool = False
    route_fixed: bool = False
    enabled: bool = False

    def __post_init__(self):
        if (self.provider not in _PROVIDERS or
                type(self.model) is not str or not _VALID.fullmatch(self.model) or
                ".." in self.model or "//" in self.model or
                any(type(v) is not bool for v in
                    (self.owner_reviewed, self.route_fixed, self.enabled))):
            raise RegistryRejected("Invalid provider/model metadata")
        for value in (self.input_micro_usd_per_million,
                      self.output_micro_usd_per_million):
            if value is not None and (type(value) is not int or not 0 <= value <= 10**10):
                raise RegistryRejected("Invalid pricing snapshot")
        if self.price_date is not None:
            try:
                if (type(self.price_date) is not str or
                        date.fromisoformat(self.price_date).isoformat() != self.price_date):
                    raise ValueError()
            except ValueError:
                raise RegistryRejected("Invalid pricing date") from None

    def eligible(self, today):
        if (not self.enabled or not self.owner_reviewed or not self.route_fixed or
                self.price_date is None or
                self.input_micro_usd_per_million is None or
                self.output_micro_usd_per_million is None):
            return False
        age = (today - date.fromisoformat(self.price_date)).days
        return 0 <= age <= 30


class Registry:
    def __init__(self, offers):
        if (type(offers) not in (list, tuple) or not 1 <= len(offers) <= 128 or
                any(type(x) is not Offer for x in offers)):
            raise RegistryRejected("Expected bounded typed offers")
        keys = [(x.provider, x.model) for x in offers]
        if len(keys) != len(set(keys)):
            raise RegistryRejected("Duplicate model")
        self.offers = tuple(offers)

    def choose(self, *, input_estimate, output_limit, ceiling_micro_usd,
               today, provider=None):
        if (type(today) is not date or type(input_estimate) is not int or
                not 1 <= input_estimate <= 8192 or type(output_limit) is not int or
                not 16 <= output_limit <= 2048 or
                type(ceiling_micro_usd) is not int or
                not 0 <= ceiling_micro_usd <= 10**9 or
                (provider is not None and provider not in _PROVIDERS)):
            raise RegistryRejected("Invalid routing request")
        options = []
        for x in self.offers:
            if not x.eligible(today) or (provider is not None and x.provider != provider):
                continue
            numerator = (input_estimate * x.input_micro_usd_per_million +
                         output_limit * x.output_micro_usd_per_million)
            estimated = (numerator + 999999) // 1000000
            if estimated <= ceiling_micro_usd:
                options.append((estimated, x.provider, x.model, x))
        if not options:
            raise RegistryRejected("No fresh reviewed fixed-route quote available")
        estimated, _, _, selected = min(options)
        return selected, estimated


def offline_demo():
    from json import dumps
    today = date.today()
    offer = Offer("fake", "fake-test", 0, 0, today.isoformat(),
                  owner_reviewed=True, route_fixed=True, enabled=True)
    winner, cost = Registry([offer]).choose(
        input_estimate=64, output_limit=128,
        ceiling_micro_usd=0, today=today,
    )
    return dumps({"format": "varyn.registry_demo.v1", "provider": winner.provider,
                  "estimated_micro_usd": cost, "provider_requests": 0,
                  "real_price_verified": False, "automatic_sync": False,
                  "billing_cap_enforced": False}, sort_keys=True)


if __name__ == "__main__":
    print(offline_demo())
