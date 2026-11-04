"""Headless desktop controller for offline and explicit-opt-in live provider use.

No automatic upload of memory, chat persistence or fallback. Live requests
require a deliberate installation opt-in AND consent for each call.
"""
from dataclasses import dataclass
from threading import Lock

from varyn.multi_provider import MessagesProvider, ProviderRouter
from varyn.providers import FakeProvider, OpenAIResponsesProvider, _validate
from varyn.usage_budget import BudgetedRouter, UsageBudget

PROVIDERS = ("fake", "openai", "anthropic", "gemini")
DEFAULT_MODELS = {
    "fake": "fake-test", "openai": "", "anthropic": "", "gemini": "",
}


@dataclass(frozen=True)
class ScreenResult:
    answer: str
    provider: str
    model: str
    mode: str


class DesktopController:
    """Bounded session with an explicit, disabled-by-default live adapter gate."""

    def __init__(self, *, max_requests=10, max_reserved_output_tokens=4096,
                 allow_live_providers=False, providers=None):
        if type(allow_live_providers) is not bool:
            raise ValueError("allow_live_providers must be boolean")
        self.allow_live_providers = allow_live_providers
        self._budget = UsageBudget(
            max_requests=max_requests,
            max_reserved_output_tokens=max_reserved_output_tokens,
        )
        if providers is None:
            providers = {"fake": FakeProvider()}
            if allow_live_providers:
                providers.update({
                    "openai": OpenAIResponsesProvider(allow_network=True),
                    "anthropic": MessagesProvider("anthropic", allow_network=True),
                    "gemini": MessagesProvider("gemini", allow_network=True),
                })
        # Reject injecting live registries in offline-only mode.
        if not allow_live_providers and set(providers) != {"fake"}:
            raise ValueError("Offline controller accepts only FakeProvider")
        self._router = BudgetedRouter(ProviderRouter(providers=providers), self._budget)
        self._history = []
        self._history_epoch = 0
        self._lock = Lock()
        self.network_consent = False
        self.context_consent = False

    def set_network_consent(self, enabled):
        if type(enabled) is not bool:
            raise ValueError("Expected boolean network consent")
        with self._lock:
            self.network_consent = enabled

    def set_context_consent(self, enabled):
        if type(enabled) is not bool:
            raise ValueError("Expected boolean context consent")
        with self._lock:
            self.context_consent = enabled

    def send(self, question, *, provider="fake", model=None, context=None,
             max_output_tokens=256, confirm_live_request=False):
        if provider not in PROVIDERS:
            raise ValueError("Unknown provider")
        selected_model = model if model is not None else DEFAULT_MODELS[provider]
        # Validate before holding a budget reservation or using any network.
        _validate(selected_model, question, max_output_tokens, 10, context)
        with self._lock:
            network_ok = self.network_consent
            context_ok = self.context_consent
            history_epoch = self._history_epoch
        if context is not None and not context_ok:
            raise PermissionError("Local context sharing is disabled")
        if provider != "fake":
            if not self.allow_live_providers:
                raise PermissionError("Live model connections are unavailable in offline mode")
            if not network_ok or confirm_live_request is not True:
                raise PermissionError("Live request needs network consent and per-request confirmation")
            if provider not in self._router.router.providers:
                raise PermissionError("Selected live provider is unavailable")
        reply = self._router.generate(
            provider, question, model=selected_model, context=context,
            max_output_tokens=max_output_tokens,
            allow_context_upload=context_ok,
        )
        result = ScreenResult(
            answer=reply.text, provider=provider, model=selected_model,
            mode="offline_simulation" if provider == "fake" else "live_opt_in",
        )
        # A mutex prevents the GUI clearing history concurrently with completion.
        with self._lock:
            if history_epoch == self._history_epoch:
                self._history.append(("user", question.strip()))
                self._history.append(("assistant", reply.text))
        return result

    def collaboration_engine(self):
        """Share this session's provider registry and in-memory request budget.

        Live capability is a snapshot of current network permission, not
        authorization to bypass each stage's separate human confirmation.
        """
        from varyn.collaboration import CollaborationEngine
        with self._lock:
            enabled = self.allow_live_providers and self.network_consent
        return CollaborationEngine(
            self._router.router, budget=self._budget, allow_live=enabled,
        )

    @property
    def history(self):
        with self._lock:
            return tuple(self._history)

    def clear_history(self):
        with self._lock:
            self._history_epoch += 1
            self._history.clear()

    def discard_pending_history(self):
        """Reject in-flight completion from future RAM history without canceling API."""
        with self._lock:
            self._history_epoch += 1

    def status(self):
        usage = self._budget.snapshot()
        with self._lock:
            consent_network = self.network_consent
            consent_context = self.context_consent
        return {
            "mode": "opt_in_live_available" if self.allow_live_providers else "offline_simulation",
            "network_enabled": bool(self.allow_live_providers and consent_network),
            "requested_network_consent": consent_network,
            "context_consent": consent_context,
            "requests_used": usage["requests_reserved"],
            "requests_limit": usage["max_requests"],
            "output_tokens_reserved": usage["output_tokens_reserved"],
            "output_tokens_limit": usage["max_reserved_output_tokens"],
            "persistent": False,
            "monetary_budget_enforced": False,
        }
