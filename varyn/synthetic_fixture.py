"""17F: Disposable VARYN-owned synthetic fixtures for desktop file demo.

The desktop MUST NOT accept an arbitrary user directory until actual OS-level
isolation and authenticated file consent are established. This module creates
only fixed, non-sensitive sample text in a fresh private temporary directory.

This does not provide an OS sandbox or protect against code running as the
same operating-system user.
"""
from pathlib import Path
from threading import Lock
from tempfile import TemporaryDirectory


_FIXTURE_FILES = {
    "sample.txt": "VARYN local-only synthetic test record.\nNo personal data.\n",
    "notes.md": "# VARYN Demo\n\nSynthetic fixture; never provider context.\n",
}


class SyntheticFixture:
    """Owns only a newly created temporary directory and its sample files."""

    def __init__(self):
        self._tempdir = None
        self._close_lock = Lock()
        tempdir = TemporaryDirectory(prefix="varyn-synthetic-")
        try:
            root = Path(tempdir.name)
            for name, text in _FIXTURE_FILES.items():
                (root / name).write_text(text, encoding="utf-8")
        except BaseException:
            tempdir.cleanup()
            raise
        self._tempdir = tempdir
        self.root = root

    def close(self):
        """Thread-safe once-only cleanup; retryable after filesystem error.

        Background lease expiry and a user closing the UI can race. Never
        clear the TemporaryDirectory reference before successful cleanup.
        """
        with self._close_lock:
            tempdir = self._tempdir
            if tempdir is not None:
                tempdir.cleanup()
                self._tempdir = None
