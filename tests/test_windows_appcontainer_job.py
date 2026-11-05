"""17S-17 portable reject tests for AppContainer-specific native Job guard.

Actual suspended AppContainer Job membership, memory/process readback and
kill-on-last-job-handle are tested on hosted Windows by
test_windows_appcontainer_trial.py. No real owner files are accessed.
"""
import os
import unittest

from varyn.public_github_tool import PublicToolRejected
from varyn.windows_child_job import (
    WindowsSuspendedAppContainerJob,
    MAX_CHILD_COMMIT_BYTES,
)
from varyn.public_tool_process import ProcessRepoFetcher


class SuspendedAppContainerJobPolicyTests(unittest.TestCase):
    def test_production_sandbox_still_unavailable(self):
        status = ProcessRepoFetcher().status()
        self.assertFalse(status["os_sandbox"])
        self.assertFalse(status["windows_restricted_primary_production_enabled"])
        self.assertEqual(MAX_CHILD_COMMIT_BYTES, 192 * 1024 * 1024)

    def test_missing_child_handle_refused(self):
        with self.assertRaises(PublicToolRejected):
            WindowsSuspendedAppContainerJob(None)

    def test_invalid_memory_limits_rejected_without_weakening(self):
        if os.name != "nt":
            with self.assertRaises(PublicToolRejected):
                WindowsSuspendedAppContainerJob(1, memory_cap=1)
            return
        for cap in (0, -1, True, "192MB", 64.0 * 1024 * 1024,
                    32 * 1024 * 1024, 257 * 1024 * 1024):
            with self.subTest(cap=cap):
                with self.assertRaises(PublicToolRejected):
                    WindowsSuspendedAppContainerJob(1, memory_cap=cap)

    def test_linux_never_claims_win32_job(self):
        if os.name == "nt":
            self.skipTest("Native kernel Job tests exercised separately")
        with self.assertRaises(PublicToolRejected):
            WindowsSuspendedAppContainerJob(1)


if __name__ == "__main__":
    unittest.main()
