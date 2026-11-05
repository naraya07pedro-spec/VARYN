"""17S-35: reviewed, three-app manual workflow in official consumer apps.

This only guides the user through ChatGPT draft -> Claude critique -> Gemini
synthesis. No app accounts, browser automation, live provider API, auto copy,
automatic history/memory sync, private data, disk writes or hidden dispatch.
"""
from varyn.official_manual_relay import _bounded_text
from varyn.safety import assert_no_obvious_secrets

_STAGES = ("chatgpt", "claude", "gemini")
_MAX_ROOT = 650


class GuidedTrioRejected(ValueError):
    """Unsafe stage or local state; never promote unverified external replies."""


def _safe_status(value):
    if (type(value) is not dict or
            type(value.get("hops_used")) is not int or
            type(value.get("awaiting_user_pasteback")) is not bool or
            type(value.get("reply_in_ram")) is not bool or
            type(value.get("return_review_pending")) is not bool or
            type(value.get("return_receipt_available")) is not bool):
        raise GuidedTrioRejected("Invalid local relay snapshot")
    return value


class GuidedThreeAppFlow:
    """RAM-only stage plan; a verified *local* copy is NOT a browser paste."""

    def __init__(self):
        self.reset()

    def reset(self):
        self._index = 0
        self._state = "idle"
        self._root_task = None
        self._current_task = None

    @property
    def active(self):
        return self._state != "idle"

    @property
    def provider(self):
        return None if not self.active else _STAGES[self._index]

    @property
    def current_task(self):
        return self._current_task

    @property
    def phase(self):
        return self._state

    def status(self):
        return {
            "format": "varyn.guided_three_app_manual.v1",
            "phase": self._state,
            "stage": 0 if not self.active else self._index + 1,
            "stage_total": len(_STAGES),
            "provider": self.provider,
            "manual_only": True,
            "local_review_required": True,
            "browser_delivery_verified": False,
            "provider_reply_origin_verified": False,
            "consumer_history_sync_verified": False,
            "provider_requests": 0,
            "persistent": False,
        }

    def start(self, root_task, relay):
        if self.active:
            raise GuidedTrioRejected("Discard the current guided flow first")
        state = _safe_status(relay)
        if (state["hops_used"] != 0 or state["awaiting_user_pasteback"] or
                state["reply_in_ram"] or state["return_review_pending"] or
                state["return_receipt_available"]):
            raise GuidedTrioRejected("Discard existing relay state before starting")
        try:
            task = _bounded_text(root_task, _MAX_ROOT)
            if not task.startswith("SYNTHETIC:"):
                raise GuidedTrioRejected("Guided flow requires synthetic task")
            assert_no_obvious_secrets(task)
        except (TypeError, ValueError) as error:
            raise GuidedTrioRejected("Invalid or unsafe synthetic task") from error
        self._root_task = task
        self._current_task = task
        self._index = 0
        self._state = "ready"
        return {"provider": self.provider, "task": task}

    def require_copy(self, provider, relay, task):
        status = _safe_status(relay)
        if (self._state != "ready" or
                provider != self.provider or
                type(task) is not str or task != self._current_task or
                status["hops_used"] != self._index or
                status["awaiting_user_pasteback"] or
                status["return_review_pending"]):
            raise GuidedTrioRejected("Wrong stage, provider, or unresolved relay")
        if self._index > 0 and not status["reply_in_ram"]:
            raise GuidedTrioRejected("Previous reply was not reviewed locally")

    def copied(self, before, after, provider, task):
        self.require_copy(provider, before, task)
        later = _safe_status(after)
        if (later["hops_used"] != self._index + 1 or
                not later["awaiting_user_pasteback"] or
                later["reply_in_ram"] or later["return_review_pending"]):
            raise GuidedTrioRejected("Outbound local clipboard approval not completed")
        self._state = "awaiting_reply"

    def require_reply(self, relay):
        status = _safe_status(relay)
        if (self._state != "awaiting_reply" or
                status["hops_used"] != self._index + 1 or
                not status["awaiting_user_pasteback"]):
            raise GuidedTrioRejected("Review the correct outgoing handoff first")

    def reviewed_reply(self, before, after):
        self.require_reply(before)
        later = _safe_status(after)
        if (later["hops_used"] != self._index + 1 or
                later["awaiting_user_pasteback"] or
                not later["reply_in_ram"] or
                later["return_review_pending"] or
                not later["return_receipt_available"]):
            raise GuidedTrioRejected("Pasted reply was not accepted by local review")
        self._state = (
            "completed" if self._index == len(_STAGES) - 1 else "ready_next"
        )

    def prepare_next(self, relay):
        status = _safe_status(relay)
        if (self._state != "ready_next" or
                self._index >= len(_STAGES) - 1 or
                status["hops_used"] != self._index + 1 or
                status["awaiting_user_pasteback"] or
                not status["reply_in_ram"] or
                status["return_review_pending"] or
                not status["return_receipt_available"]):
            raise GuidedTrioRejected("Complete and review the current stage first")
        next_index = self._index + 1
        original = self._root_task[len("SYNTHETIC:"):].strip()
        if next_index == 1:
            next_task = (
                "SYNTHETIC: Critically review the preceding unverified "
                "ChatGPT draft, identify errors and omissions, and summarize "
                "its key points for the next reviewer. Fictional task: " + original
            )
        else:
            next_task = (
                "SYNTHETIC: Synthesize the preceding unverified Claude "
                "critique (including its summary of the first draft), check "
                "disagreements and propose a final fictional action plan. "
                "Fictional task: " + original
            )
        if len(next_task) > 1000:
            raise GuidedTrioRejected("Guided task exceeds relay limit")
        self._index = next_index
        self._current_task = next_task
        self._state = "ready"
        return {"provider": self.provider, "task": next_task}
