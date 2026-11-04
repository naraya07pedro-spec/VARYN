"""17S-3: bounded background transport for one owner-reviewed GitHub read.

The worker NEVER touches Tk widgets. A GUI may poll result packets on its
main thread. Revoking suppresses delivery; it cannot retract sent HTTP.
"""
from dataclasses import dataclass
from queue import Empty, Queue
from threading import Lock, Thread

from varyn.public_github_tool import PublicGithubToolGateway, PublicToolRejected


@dataclass(frozen=True)
class ToolCompletion:
    request_id: int
    status: str
    result: dict | None


class PublicGithubToolWorker:
    """At most one underlying GET at a time; no auto-retries or leaked results."""

    def __init__(self, gateway, *, thread_factory=Thread):
        if not isinstance(gateway, PublicGithubToolGateway):
            raise TypeError("Expected PublicGithubToolGateway")
        if not callable(thread_factory):
            raise TypeError("Expected thread factory")
        self._gateway = gateway
        self._thread_factory = thread_factory
        self._lock = Lock()
        self._request_number = 0
        self._active = None
        self._worker_finished = False
        self._visible = None
        self._closed = False
        self._completed = Queue(maxsize=1)

    @property
    def busy(self):
        with self._lock:
            return self._active is not None

    def submit(self, review, *, network_consent=False):
        """Start after a trusted UI approval; NEVER block the caller on HTTP."""
        if network_consent is not True:
            raise PermissionError("Separate network consent must still be active")
        if (type(getattr(review, "proposal_id", None)) is not str or
                type(getattr(review, "digest", None)) is not str):
            raise PublicToolRejected("Exact reviewed proposal required")
        with self._lock:
            if self._closed or self._active is not None:
                raise PublicToolRejected("Public network tool is closed or busy")
            self._request_number += 1
            number = self._request_number
            self._active = number
            self._worker_finished = False
            self._visible = number
            try:
                thread = self._thread_factory(
                    target=self._execute,
                    args=(number, review.proposal_id, review.digest),
                    daemon=True,
                )
                thread.start()
            except Exception:
                self._active = None
                self._visible = None
                self._gateway.reject_all_pending()
                raise PublicToolRejected("Could not start tool worker") from None
            return number

    def _execute(self, number, proposal_id, digest):
        try:
            response = self._gateway.decide(
                proposal_id, digest, approved=True, network_consent=True,
            )
            outcome = ToolCompletion(number, "completed", response["result"])
        except Exception:
            # Never pass network exceptions or untrusted raw payloads to Tk.
            outcome = ToolCompletion(number, "failed_or_revoked", None)
        with self._lock:
            self._worker_finished = True
            if self._closed or self._visible != number:
                if self._active == number:
                    self._active = None
                return
            # Remain busy until the GUI takes the completion, avoiding a
            # second request overwriting a pending bounded result packet.
            try:
                self._completed.put_nowait(outcome)
            except Exception:
                # Defensive fail-closed result drop, never block a worker.
                self._active = None
                self._visible = None

    def poll(self):
        """Called from UI thread. No model actions, no extra network traffic."""
        with self._lock:
            try:
                packet = self._completed.get_nowait()
            except Empty:
                return None
            if self._closed or self._visible != packet.request_id:
                return None
            self._active = None
            self._visible = None
            return packet

    def revoke(self):
        """Discard pending/queued results and invalidate any in-flight result.

        The request may have already reached GitHub; this is NOT HTTP cancel.
        A replacement request cannot start until the original thread exits.
        """
        with self._lock:
            self._visible = None
            while True:
                try:
                    self._completed.get_nowait()
                except Empty:
                    break
            self._gateway.revoke_active()
            # A finished-but-unpolled result no longer has a running worker.
            # A live request still owns the sole worker slot until it exits.
            if self._worker_finished:
                self._active = None

    def close(self):
        """Instant local shutdown. No join and no accidental UI callbacks."""
        with self._lock:
            if self._closed:
                return
            self._closed = True
            self._visible = None
            while True:
                try:
                    self._completed.get_nowait()
                except Empty:
                    break
            self._gateway.close()

    def status(self):
        with self._lock:
            return {
                "format": "varyn.public_tool_background.v1",
                "busy": self._active is not None,
                "closed": self._closed,
                "visible_request": self._visible is not None,
                "thread_touches_gui": False,
                "http_cancel_guaranteed": False,
                "max_parallel_requests": 1,
            }
