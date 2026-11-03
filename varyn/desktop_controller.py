"""Headless VARYN desktop controller: explicit offline-only MVP.

Real-provider selectors are visible but never sent to network in this stage.
No chat or context saved to disk. One session-local usage budget.
"""
from dataclasses import dataclass
from varyn.multi_provider import ProviderRouter
from varyn.usage_budget import BudgetedRouter, UsageBudget

PROVIDERS = ("fake", "openai", "anthropic", "gemini")
DEFAULT_MODELS = {
    "fake": "fake-test",
    "openai": "",
    "anthropic": "",
    "gemini": "",
}


@dataclass(frozen=True)
class ScreenResult:
    answer: str
    provider: str
    model: str
    mode: str


class DesktopController:
    """UI-independent offline execution; strict no-network enforcement."""

    def __init__(self, *, max_requests=10, max_reserved_output_tokens=4096):
        self._budget = UsageBudget(
            max_requests=max_requests,
            max_reserved_output_tokens=max_reserved_output_tokens,
        )
        # Deliberately construct only the fake adapter in the UI registry.
        self._router = BudgetedRouter(
            ProviderRouter(providers={"fake": ProviderRouter().providers["fake"]}),
            self._budget,
        )
        self._history = []  # RAM only; no persistence
        self.network_consent = False
        self.context_consent = False

    def set_network_consent(self, enabled):
        if type(enabled) is not bool:
            raise ValueError("Expected boolean network consent")
        self.network_consent = enabled

    def set_context_consent(self, enabled):
        if type(enabled) is not bool:
            raise ValueError("Expected boolean context consent")
        self.context_consent = enabled

    def send(self, question, *, provider="fake", model=None, context=None,
             max_output_tokens=256):
        if provider not in PROVIDERS:
            raise ValueError("Unknown provider")
        if provider != "fake":
            # Both switches are *informational* during MVP. No real transport
            # is registered, even if a user has clicked both switches.
            raise PermissionError(
                "Live model connections are unavailable in the offline desktop MVP"
            )
        if context is not None:
            # VARYN memory is not read or attached automatically.
            if self.context_consent is not True:
                raise PermissionError("Local context sharing is disabled")
            # Although FakeProvider never uploads, preserve explicit consent.
        selected_model = model if model is not None else DEFAULT_MODELS[provider]
        reply = self._router.generate(
            provider, question, model=selected_model, context=context,
            max_output_tokens=max_output_tokens,
            allow_context_upload=self.context_consent,
        )
        result = ScreenResult(
            answer=reply.text, provider=provider, model=selected_model,
            mode="offline_simulation",
        )
        self._history.append(("user", question.strip()))
        self._history.append(("assistant", reply.text))
        return result

    @property
    def history(self):
        return tuple(self._history)

    def clear_history(self):
        self._history.clear()

    def status(self):
        usage = self._budget.snapshot()
        return {
            "mode": "offline_simulation",
            "network_enabled": False,  # Cannot be toggled by MVP interface.
            "requested_network_consent": self.network_consent,
            "context_consent": self.context_consent,
            "requests_used": usage["requests_reserved"],
            "requests_limit": usage["max_requests"],
            "output_tokens_reserved": usage["output_tokens_reserved"],
            "output_tokens_limit": usage["max_reserved_output_tokens"],
            "persistent": False,
            "monetary_budget_enforced": False,
        }
