"""17S-5: hosted native Windows Job Object + SID and fail-closed checks.

No live GitHub HTTP; child scripts either wait on stdin or return synthetic
offline self-test metadata. These tests prove limits/kills, not sandboxing.
"""
import os
import subprocess
import sys
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from varyn.public_tool_process import ProcessRepoFetcher
from varyn.windows_child_job import WindowsChildJob, MAX_CHILD_COMMIT_BYTES
from varyn.public_github_tool import PublicToolRejected

REPO = "naraya07pedro-spec/VARYN"


class PortableJobPolicyTests(unittest.TestCase):
    def test_memory_cap_is_explicit_and_bounded(self):
        self.assertEqual(MAX_CHILD_COMMIT_BYTES, 192 * 1024 * 1024)
        self.assertFalse(ProcessRepoFetcher().status()["os_sandbox"])
        if os.name == "nt":
            self.assertTrue(ProcessRepoFetcher().status()[
                "windows_native_job_required"])
            self.assertTrue(ProcessRepoFetcher().status()[
                "windows_same_user_sid_required"])
        else:
            self.assertFalse(ProcessRepoFetcher().status()[
                "windows_native_job_required"])

    def test_job_is_not_available_on_non_windows(self):
        if os.name == "nt":
            self.skipTest("Actual Windows Job tests run below")
        with self.assertRaises(PublicToolRejected):
            WindowsChildJob(object())

    def test_attestation_missing_or_failed_disallows_stdin(self):
        class Proc:
            communicated = False
            killed = False
            returncode = None
            def poll(self):
                return self.returncode
            def kill(self):
                self.killed = True
                self.returncode = 9
            def wait(self, timeout):
                return self.returncode
            def communicate(self, **kwargs):
                self.communicated = True
                raise AssertionError("Must never reach child stdin")
        p = Proc()
        def spawn(*a, **kwargs):
            return p
        def invalid_guard(proc):
            raise PublicToolRejected("OS guard refused")
        fetch = ProcessRepoFetcher(spawn=spawn, guard_factory=invalid_guard)
        with self.assertRaises(PublicToolRejected):
            fetch(REPO)
        self.assertTrue(p.killed)
        self.assertFalse(p.communicated)
        self.assertIsNone(fetch.status()["active"])
        self.assertEqual(fetch.status()["attempts"], 1)

    def test_fake_guard_not_attached_fails_closed(self):
        class P:
            returncode = None
            payload_delivered = False
            def poll(self):
                return self.returncode
            def kill(self):
                self.returncode = 9
            def wait(self, timeout):
                return self.returncode
            def communicate(self, **kwargs):
                self.payload_delivered = True
        class Guard:
            attached = False
            def close(self):
                pass
        p = P()
        fetch = ProcessRepoFetcher(
            spawn=lambda *args, **kwargs: p, guard_factory=lambda _: Guard())
        with self.assertRaises(PublicToolRejected):
            fetch(REPO)
        self.assertFalse(p.payload_delivered)


@unittest.skipUnless(os.name == "nt", "Windows kernel Job Object required")
class NativeWindowsJobTests(unittest.TestCase):
    def test_actual_kernel_job_membership_sid_limits_and_kill_on_close(self):
        # Normal child, with stdin OPEN, blocks awaiting its only input.
        # No intent is sent; hence no GitHub network request can occur.
        proc = subprocess.Popen(
            ProcessRepoFetcher._command(),
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, close_fds=True,
            shell=False, env=ProcessRepoFetcher._environment(),
            cwd=str(Path(sys.executable).resolve().parent),
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        guard = None
        try:
            self.assertIsNone(proc.poll())
            guard = WindowsChildJob(proc)
            self.assertTrue(guard.attached)
            self.assertIsNone(proc.poll())
            guard.close()  # native KILL_ON_JOB_CLOSE
            self.assertIsNotNone(proc.wait(timeout=5))
            self.assertNotEqual(proc.returncode, 0)
        finally:
            if guard is not None:
                guard.close()
            if proc.poll() is None:
                proc.kill()
            proc.communicate(timeout=5)

    def test_actual_fetcher_requires_job_before_stdin_and_fails_on_non_metadata(self):
        command = ProcessRepoFetcher._command()
        with patch.object(ProcessRepoFetcher, "_command",
                          return_value=command + ["--offline-stdin-self-test"]):
            fetch = ProcessRepoFetcher()
            # The OS job guard must attach first; then the child receives stdin.
            # Child responds with a deliberately NON-metadata offline marker.
            with self.assertRaises(PublicToolRejected):
                fetch(REPO)
            self.assertEqual(fetch.status()["attempts"], 1)
            self.assertFalse(fetch.status()["active"])
            self.assertTrue(fetch.status()["windows_native_job_required"])


if __name__ == "__main__":
    unittest.main()
