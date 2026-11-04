"""In-process preflight request and output-token caps for VARYN providers.

Not a billing limit: provider may charge for input tokens, hidden usage, or
failed requests. Counts do not survive process restart and are not shared
between processes. No messages, API keys, model responses, or content stored.
"""
from threading import Lock

from varyn.providers import _validate


class BudgetExceeded(RuntimeError):
    """Request was not dispatched because a local budget was exhausted."""


class UsageBudget:
    def __init__(self, *, max_requests=10, max_reserved_output_tokens=4096):
        if type(max_requests) is not int or not 1 <= max_requests <= 100000:
            raise ValueError("max_requests must be 1..100000")
        if (type(max_reserved_output_tokens) is not int or
                not 16 <= max_reserved_output_tokens <= 100000000):
            raise ValueError("max_reserved_output_tokens must be 16..100000000")
        self.max_requests = max_requests
        self.max_reserved_output_tokens = max_reserved_output_tokens
        self._requests_reserved = 0
        self._output_tokens_reserved = 0
        self._requests_succeeded = 0
        self._requests_failed_or_uncertain = 0
        self._reported_input_tokens = 0
        self._reported_output_tokens = 0
        self._unreported_usage = 0
        self._lock = Lock()

    def reserve(self, max_output_tokens):
        """Consume quota BEFORE dispatch; no refunds on uncertain failures."""
        if type(max_output_tokens) is not int or not 16 <= max_output_tokens <= 2048:
            raise ValueError("Invalid max output token reservation")
        with self._lock:
            if (self._requests_reserved >= self.max_requests or
                    self._output_tokens_reserved + max_output_tokens >
                    self.max_reserved_output_tokens):
                raise BudgetExceeded("Local request or output-token budget exhausted")
            self._requests_reserved += 1
            self._output_tokens_reserved += max_output_tokens

    def report_success(self, usage):
        """Only sanitized aggregate counters, never message or provider content."""
        if not isinstance(usage, dict):
            usage = {}
        input_count = usage.get("input_tokens")
        output_count = usage.get("output_tokens")
        with self._lock:
            self._requests_succeeded += 1
            if type(input_count) is int and input_count >= 0:
                self._reported_input_tokens += input_count
            if type(output_count) is int and output_count >= 0:
                self._reported_output_tokens += output_count
            if type(input_count) is not int or type(output_count) is not int:
                self._unreported_usage += 1

    def report_failure(self):
        with self._lock:
            self._requests_failed_or_uncertain += 1

    def snapshot(self):
        with self._lock:
            return {
                "format": "varyn.usage_budget.v1",
                "max_requests": self.max_requests,
                "max_reserved_output_tokens": self.max_reserved_output_tokens,
                "requests_reserved": self._requests_reserved,
                "output_tokens_reserved": self._output_tokens_reserved,
                "requests_succeeded": self._requests_succeeded,
                "requests_failed_or_uncertain": self._requests_failed_or_uncertain,
                "reported_input_tokens": self._reported_input_tokens,
                "reported_output_tokens": self._reported_output_tokens,
                "responses_with_incomplete_usage": self._unreported_usage,
                "estimated_or_actual_cost": None,
                "persistent": False,
                "billing_guarantee": False,
            }


class BudgetedRouter:
    """Wrap an explicitly-selected provider router. No retries or failover."""

    def __init__(self, router, budget):
        if not isinstance(budget, UsageBudget):
            raise TypeError("budget must be UsageBudget")
        self.router = router
        self.budget = budget

    def generate(self, provider, question, *, model, context=None,
                 max_output_tokens=512, timeout_seconds=10,
                 allow_context_upload=False):
        # Validate preflight to prevent quota consumption for malformed calls.
        _validate(model, question, max_output_tokens, timeout_seconds, context)
        if context is not None and allow_context_upload is not True:
            raise PermissionError("Uploading local context requires explicit opt-in")
        if provider not in self.router.providers:
            raise ValueError("Unknown explicitly selected provider")
        self.budget.reserve(max_output_tokens)
        try:
            reply = self.router.generate(
                provider, question, model=model, context=context,
                max_output_tokens=max_output_tokens,
                timeout_seconds=timeout_seconds,
                allow_context_upload=allow_context_upload,
            )
        except BaseException:
            # Request may already have been billed; hold reservation.
            self.budget.report_failure()
            raise
        self.budget.report_success(reply.usage)
        return reply
