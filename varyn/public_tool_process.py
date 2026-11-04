"""17S-4: supervised SAME-USER Python child for public GitHub reads.

This is process separation and credential minimization, NOT Windows AppContainer,
restricted token, seccomp, signed code, impersonation resistance, or OS sandbox.
"""
import json
import os
from pathlib import Path
import subprocess
import sys
from threading import RLock

from varyn.public_github_tool import PublicToolRejected, _unique_pairs, _REPO


_CHILD_MAX_OUTPUT = 4096


class ProcessRepoFetcher:
    """One short-lived -I -S Python process per authorized public metadata GET.

    Only the trusted host may hold this object. No user-provided executable,
    URL, argv, environment or cwd is accepted. Only known JSON metadata exits.
    """

    def __init__(self, *, spawn=None, timeout_seconds=8):
        if spawn is not None and not callable(spawn):
            raise TypeError("spawn factory must be callable")
        if type(timeout_seconds) is not int or not 1 <= timeout_seconds <= 20:
            raise ValueError("bounded child timeout required")
        self._spawn = spawn or subprocess.Popen
        self._timeout = timeout_seconds
        self._lock = RLock()
        self._active = None
        self._epoch = 0
        self._closed = False
        self._attempts = 0
        self._terminations = 0

    @staticmethod
    def _command():
        exe = Path(sys.executable).resolve()
        entry = Path(__file__).resolve().with_name("public_tool_child.py")
        if not exe.is_file() or not entry.is_file():
            raise PublicToolRejected("Trusted child runtime unavailable")
        return [str(exe), "-I", "-S", str(entry)]

    @staticmethod
    def _environment():
        # Remove GitHub/API tokens, proxy env, PYTHONPATH and user-site configuration.
        # Windows Python's runtime may need SystemRoot/WINDIR to load OS libraries.
        allow = ("SystemRoot", "WINDIR", "TEMP", "TMP") if os.name == "nt" else ()
        return {key: os.environ[key] for key in allow if key in os.environ}

    @staticmethod
    def _terminate(proc):
        try:
            if proc.poll() is None:
                proc.kill()
        except (OSError, AttributeError):
            pass

    def __call__(self, repository):
        if type(repository) is not str or not _REPO.fullmatch(repository):
            raise PublicToolRejected("Invalid public repository")
        raw = json.dumps({
            "format": "varyn.public_tool_intent.v1",
            "tool": "github_public_repo_metadata",
            "arguments": {"repository": repository},
        }, separators=(",", ":")).encode("utf-8")
        with self._lock:
            if self._closed or self._active is not None:
                raise PublicToolRejected("Public child unavailable or already active")
            epoch = self._epoch
            command = self._command()
            try:
                proc = self._spawn(
                    command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL, shell=False, close_fds=True,
                    cwd=str(Path(sys.executable).resolve().parent),
                    env=self._environment(),
                    creationflags=(getattr(subprocess, "CREATE_NO_WINDOW", 0)
                                   if os.name == "nt" else 0),
                )
            except (OSError, ValueError, TypeError):
                raise PublicToolRejected("Could not start isolated child") from None
            self._active = proc
            self._attempts += 1

        try:
            stdout, _ = proc.communicate(input=raw, timeout=self._timeout)
            if proc.returncode != 0 or type(stdout) is not bytes or len(stdout) > _CHILD_MAX_OUTPUT:
                raise PublicToolRejected("Public child returned no valid metadata")
            result = json.loads(stdout.decode("utf-8", "strict"),
                                object_pairs_hook=_unique_pairs)
            if (type(result) is not dict or
                    result.get("format") != "varyn.github_public_repo_metadata.v1" or
                    result.get("repository") != repository):
                raise PublicToolRejected("Unexpected public child response")
            with self._lock:
                if self._closed or self._epoch != epoch:
                    raise PublicToolRejected("Child response revoked or session closed")
            return result
        except (OSError, ValueError, TypeError, UnicodeError, subprocess.TimeoutExpired):
            raise PublicToolRejected("Public child failed or exceeded time limit") from None
        finally:
            # May race with cancel(); a terminated child never returns a result.
            self._terminate(proc)
            with self._lock:
                if self._active is proc:
                    self._active = None

    def cancel(self):
        """Stop an active child if possible and invalidate previous results."""
        with self._lock:
            self._epoch += 1
            proc = self._active
            if proc is not None:
                self._terminations += 1
                self._terminate(proc)

    def close(self):
        with self._lock:
            if self._closed:
                return
            self._closed = True
        self.cancel()

    def status(self):
        with self._lock:
            return {
                "format": "varyn.public_tool_process.v1",
                "active": self._active is not None,
                "closed": self._closed,
                "attempts": self._attempts,
                "termination_attempts": self._terminations,
                "isolated_python_flags": True,
                "credential_env_allowlist": True,
                "os_sandbox": False,
                "os_authenticated_human": False,
            }
