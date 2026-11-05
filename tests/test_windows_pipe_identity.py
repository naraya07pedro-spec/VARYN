"""17S-15 real Win32 named-pipe PID attestation, same-user synthetic proof.

Native Windows tests must run, not silently pass on CI. This proves only that
Windows reports the connecting ordinary child PID and that the broker
rejects a mismatched expected PID. AppContainer SID permission/transport is
a separate incomplete gate; no production tool uses this helper.
"""
import os
from pathlib import Path
import subprocess
import sys
import unittest

from varyn.public_github_tool import PublicToolRejected
from varyn.windows_pipe_identity import OneShotWindowsPipe

_CLIENT = Path(__file__).with_name("windows_pipe_pid_client.py")


class PortableNamedPipePolicy(unittest.TestCase):
    def test_windows_helper_not_exposed_as_production_sandbox(self):
        from varyn.public_tool_process import ProcessRepoFetcher
        from varyn.package_desktop import archive_entries
        status = ProcessRepoFetcher().status()
        self.assertFalse(status["os_sandbox"])
        self.assertFalse(status["windows_restricted_primary_production_enabled"])
        self.assertTrue(_CLIENT.is_file())
        self.assertNotIn(_CLIENT, archive_entries())

    def test_non_windows_cannot_mint_native_pid_proof(self):
        if os.name == "nt":
            self.skipTest("Real Win32 tests below")
        with self.assertRaises(PublicToolRejected):
            OneShotWindowsPipe()


@unittest.skipUnless(os.name == "nt", "Real native Win32 named pipe required")
class NativeWin32PipeIdentityTests(unittest.TestCase):
    def _start(self, name):
        return subprocess.Popen(
            [str(Path(sys.executable).resolve()), "-I", "-S",
             str(_CLIENT), name],
            cwd=str(Path(sys.executable).resolve().parent),
            env={"SystemRoot": os.environ["SystemRoot"]},
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            close_fds=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))

    def test_win32_getnamedpipeclientprocessid_matches_real_child(self):
        pipe = OneShotWindowsPipe()
        child = None
        try:
            child = self._start(pipe.name)
            report = pipe.verify_one_client(child.pid)
            self.assertTrue(report["os_client_pid_verified"])
            self.assertTrue(report["one_shot"])
            self.assertTrue(report["local_only"])
            self.assertTrue(report["owner_only_dacl"])
            self.assertFalse(report["inherited_handles"])
            self.assertFalse(report["appcontainer_sid_verified"])
            self.assertEqual(child.wait(timeout=6), 0)
            with self.assertRaises(PublicToolRejected):
                pipe.verify_one_client(child.pid)
        finally:
            pipe.close()
            if child is not None and child.poll() is None:
                child.kill()
                child.wait(timeout=3)

    def test_forged_claimed_pid_is_rejected_without_reading_payload(self):
        pipe = OneShotWindowsPipe()
        child = None
        try:
            child = self._start(pipe.name)
            with self.assertRaises(PublicToolRejected):
                pipe.verify_one_client(child.pid + 1)
            with self.assertRaises(PublicToolRejected):
                pipe.verify_one_client(child.pid)
        finally:
            pipe.close()
            if child is not None and child.poll() is None:
                child.kill()
                child.wait(timeout=3)

    def test_invalid_pid_burns_single_pipe_session(self):
        pipe = OneShotWindowsPipe()
        try:
            with self.assertRaises(PublicToolRejected):
                pipe.verify_one_client(True)
            with self.assertRaises(PublicToolRejected):
                pipe.verify_one_client(100)
        finally:
            pipe.close()


if __name__ == "__main__":
    unittest.main()
