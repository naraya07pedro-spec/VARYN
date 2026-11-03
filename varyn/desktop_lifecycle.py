"""Small headless UI lifecycle state machine.

A discarded result is only hidden locally. It DOES NOT cancel an already
dispatched external API request or its possible billing.
"""
from threading import Lock


class DesktopRequestState:
    def __init__(self):
        self._lock = Lock()
        self._generation = 0
        self._active = None
        self._closed = False

    @property
    def busy(self):
        with self._lock:
            return self._active is not None

    @property
    def closed(self):
        with self._lock:
            return self._closed

    def begin(self):
        with self._lock:
            if self._closed:
                raise RuntimeError("Desktop is closing")
            if self._active is not None:
                raise RuntimeError("A request is already in flight")
            self._generation += 1
            self._active = self._generation
            return self._active

    def finish(self, request_id):
        """True only for the active, visible request. Ignore stale results."""
        with self._lock:
            if self._closed or type(request_id) is not int:
                return False
            if request_id != self._active:
                return False
            self._active = None
            return True

    def discard_visible(self):
        """Hide in-flight result without implying cancellation of remote work."""
        with self._lock:
            if self._closed:
                return False
            self._active = None
            self._generation += 1
            return True

    def close(self):
        with self._lock:
            self._closed = True
            self._active = None
            self._generation += 1

