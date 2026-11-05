"""17S-13: CI-only native AppContainer profile/token/process trial.

No user files, provider accounts, network traffic, shell requests, or
production public GitHub tool are accessed. A profile is created and deleted
only on an opted-in ephemeral Windows GitHub Actions runner.
"""
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

from varyn.public_github_tool import PublicToolRejected
from varyn.public_tool_process import ProcessRepoFetcher
from varyn.windows_appcontainer_trial import run_ci_only_zero_capability_trial


class AppContainerFailClosedPolicyTests(unittest.TestCase):
    def test_normal_desktop_never_creates_trial_profile(self):
        with patch.dict(os.environ, {"GITHUB_ACTIONS": "false",
                                     "VARYN_CI_APPCONTAINER_TRIAL": "1"}):
            with self.assertRaises(PublicToolRejected):
                run_ci_only_zero_capability_trial()

    def test_ci_without_explicit_optin_never_creates_profile(self):
        with patch.dict(os.environ, {"VARYN_CI_APPCONTAINER_TRIAL": "0"}):
            with self.assertRaises(PublicToolRejected):
                run_ci_only_zero_capability_trial()

    def test_production_does_not_claim_appcontainer_or_private_file_isolation(self):
        status = ProcessRepoFetcher().status()
        self.assertFalse(status["os_sandbox"])
        self.assertFalse(status["windows_restricted_primary_production_enabled"])
        self.assertFalse(status["windows_mic_blocks_private_reads"])
        from varyn.package_desktop import archive_entries
        self.assertIn(
            Path(__file__).resolve().parent.parent /
            "varyn/windows_appcontainer_trial.py", archive_entries())

    def test_linux_cannot_attest_windows_appcontainer(self):
        if os.name == "nt":
            self.skipTest("Native Windows code exercised separately")
        with patch.dict(os.environ, {"GITHUB_ACTIONS": "true",
                                     "RUNNER_OS": "Windows",
                                     "VARYN_CI_APPCONTAINER_TRIAL": "1"}):
            with self.assertRaises(PublicToolRejected):
                run_ci_only_zero_capability_trial()


@unittest.skipUnless(os.name == "nt", "Native Win32 AppContainer required")
class NativeWindowsAppContainerTrial(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if os.name != "nt":
            return
        if (os.environ.get("GITHUB_ACTIONS") != "true" or
                os.environ.get("RUNNER_OS") != "Windows"):
            raise unittest.SkipTest(
                "No profile changes on owner Windows PC; hosted CI only")
        with patch.dict(os.environ, {"VARYN_CI_APPCONTAINER_TRIAL": "1"}):
            cls.report = run_ci_only_zero_capability_trial()

    def test_actual_suspended_child_is_appcontainer_without_capabilities(self):
        result = self.report
        self.assertEqual(result["format"], "varyn.windows_appcontainer_trial.v1")
        self.assertTrue(result["native_primary_appcontainer_attested"])
        self.assertTrue(result["zero_capability_sids_attested"])
        self.assertFalse(result["inherited_handles"])
        self.assertTrue(result["process_terminated"])
        self.assertTrue(result["disposable_profile_deleted"])
        self.assertFalse(result["network_used"])
        self.assertFalse(result["private_file_test_executed"])
        self.assertFalse(result["production_tool_integrated"])
        self.assertIs(type(result["python_runtime_executed"]), bool)
        self.assertIs(type(result["python_exit_status"]), int)
        print("17S-13 native AppContainer: token attested, caps=0, "
              "temp profile deleted; Python runtime started="
              + str(result["python_runtime_executed"]) +
              "; exit_status=0x" + format(result["python_exit_status"], "x"),
              flush=True)

    def test_python_reaches_known_exit_marker_or_explicitly_unavailable(self):
        if not self.report["python_runtime_executed"]:
            self.skipTest("AppContainer primary token attested but trusted "
                          "Python runtime did not reach marker; no private "
                          "file read-denial claim")
        self.assertEqual(self.report["python_exit_status"], 73)


if __name__ == "__main__":
    unittest.main()
