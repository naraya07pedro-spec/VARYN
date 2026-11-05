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
        self.assertTrue(result["private_file_test_executed"])
        self.assertTrue(result["synthetic_owner_positive_control"])
        self.assertTrue(result["synthetic_granted_read_ok"])
        self.assertTrue(result["synthetic_private_read_denied"])
        self.assertFalse(result["production_tool_integrated"])
        self.assertIs(type(result["python_runtime_executed"]), bool)
        self.assertIs(type(result["python_exit_status"]), int)
        print("17S-13 native AppContainer: actual primary token attested, "
              "caps=0, profile deleted; Python executed="
              + str(result["python_runtime_executed"]) +
              "; synthetic granted read=" + str(result["synthetic_granted_read_ok"]) +
              "; synthetic owner-only read denied=" +
              str(result["synthetic_private_read_denied"]) +
              "; exit_status=0x" + format(result["python_exit_status"], "x"),
              flush=True)

    def test_native_python_denies_present_owner_only_file_after_granted_read(self):
        # Hard FAIL, not SKIP: security proof is the entire 17S-13 gate.
        # Exit 73 requires the verified owner file to exist, normal-owner
        # read OK, granted in-container read OK and private read denied.
        self.assertTrue(self.report["python_runtime_executed"])
        self.assertTrue(self.report["synthetic_owner_positive_control"])
        self.assertTrue(self.report["synthetic_granted_read_ok"])
        self.assertTrue(self.report["private_file_test_executed"])
        self.assertTrue(self.report["synthetic_private_read_denied"])
        self.assertEqual(self.report["python_exit_status"], 73)


if __name__ == "__main__":
    unittest.main()
