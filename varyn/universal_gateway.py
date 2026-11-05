"""17S-39: opt-in, non-retrying model execution via verified fixed endpoints.

Default network OFF. All live calls need fresh owner approval and env API key;
9Router additionally requires upstream-use authorization. No native app sync.
Owner-reviewed cost estimates do NOT enforce actual provider billing limits.
"""
import os
import urllib.error
from datetime import date

from varyn.gateway_chat import KEY_ENVS, prepare, parse, post
from varyn.model_registry import Registry, RegistryRejected
from varyn.providers import ModelReply, ProviderError
from varyn.safety import assert_no_obvious_secrets
from varyn.usage_budget import UsageBudget


class UniversalGateway:
    def __init__(self, registry, *, allow_network=False, budget=None,
                 transport=None):
        if type(registry) is not Registry or type(allow_network) is not bool:
            raise TypeError("Gateway requires explicit registry and network policy")
        if budget is not None and type(budget) is not UsageBudget:
            raise TypeError("Expected local request budget")
        self.registry = registry
        self.allow_network = allow_network
        self.budget = budget if budget is not None else UsageBudget()
        self.transport = transport

    def generate(self, task, *, input_estimate, max_output_tokens=512,
                 ceiling_micro_usd=0, today=None, provider=None,
                 approve_request=False, authorized_upstream=False,
                 timeout_seconds=10):
        # Always validate BEFORE reserving the uncertain request budget.
        today = date.today() if today is None else today
        selected, amount = self.registry.choose(
            input_estimate=input_estimate, output_limit=max_output_tokens,
            ceiling_micro_usd=ceiling_micro_usd, today=today,
            provider=provider,
        )
        payload = prepare(selected.model, task, max_tokens=max_output_tokens)
        assert_no_obvious_secrets(task)
        if type(timeout_seconds) not in (int, float) or not 1 <= timeout_seconds <= 60:
            raise RegistryRejected("Invalid provider timeout")
        if approve_request is not True:
            raise PermissionError("Explicit fresh per-request approval required")
        key = None
        if selected.provider != "fake":
            if self.allow_network is not True:
                raise PermissionError("Model network disabled")
            if selected.provider == "9router" and authorized_upstream is not True:
                raise PermissionError("9Router upstream account use not approved")
            key = os.environ.get(KEY_ENVS[selected.provider], "")
            if type(key) is not str or not key.strip():
                raise ProviderError("Model API credential missing")
        self.budget.reserve(max_output_tokens)
        try:
            if selected.provider == "fake":
                reply = ModelReply("FAKE: no API or paid model called",
                                   "fake", selected.model, {})
            else:
                body = (self.transport(selected.provider, payload, key,
                                       timeout_seconds)
                        if self.transport is not None else
                        post(selected.provider, payload, key, timeout_seconds))
                reply = parse(selected.provider, selected.model, body)
        except (urllib.error.URLError, TimeoutError, OSError):
            self.budget.report_failure()
            raise ProviderError("Model API request failed") from None
        except BaseException:
            self.budget.report_failure()
            raise
        self.budget.report_success(reply.usage)
        return {
            "reply": reply, "estimated_micro_usd": amount,
            "estimate_only": True, "actual_billing_cap_enforced": False,
            "native_consumer_history_sync": False, "varyn_fallback": False,
        }
