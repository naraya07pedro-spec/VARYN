"""17S-10 native Windows restricted-token read-isolation proof, offline only."""
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest


_PROBE = Path(__file__).with_name("windows_restricted_read_probe.py")


class PortableProbePolicyTests(unittest.TestCase):
    def test_probe_is_not_a_production_tool_or_desktop_module(self):
        self.assertTrue(_PROBE.is_file())
        from varyn.public_tool_process import ProcessRepoFetcher
        status = ProcessRepoFetcher().status()
        self.assertFalse(status["os_sandbox"])
        self.assertFalse(status["windows_mic_blocks_private_reads"])
        self.assertNotIn("restricted_token", status)
        from varyn.package_desktop import archive_entries
        self.assertNotIn(_PROBE, archive_entries())

    def test_non_windows_does_not_claim_kernel_attestation(self):
        if os.name == "nt":
            self.skipTest("Native Windows test runs in the next test class")
        proc = subprocess.run(
            [sys.executable, "-I", "-S", str(_PROBE)],
            input=b"no file\n", stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=5, check=False)
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(proc.stdout, b"")


@unittest.skipUnless(os.name == "nt", "Win32 OS tokens required")
class NativeWindowsRestrictedReadTests(unittest.TestCase):
    def _run(self, input_bytes):
        return subprocess.run(
            [sys.executable, "-I", "-S", str(_PROBE)],
            input=input_bytes, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            cwd=str(Path(sys.executable).resolve().parent),
            env={"SystemRoot": os.environ["SystemRoot"]},
            shell=False, close_fds=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            timeout=10, check=False)

    def test_real_restricted_token_denies_synthetic_owner_read(self):
        # Create only one disposable file, never any actual owner document.
        with TemporaryDirectory(prefix="varyn-restricted-read-") as folder:
            path = Path(folder) / "synthetic-owner-only.txt"
            path.write_bytes(b"varyn-synthetic-owner-only")
            self.assertEqual(path.read_bytes(), b"varyn-synthetic-owner-only")
            result = self._run((str(path) + "\n").encode("utf-8"))
            self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace") +
                             result.stdout.decode(errors="replace"))
            observed = json.loads(result.stdout)
            self.assertEqual(observed["format"], "varyn.windows_restricted_read_probe.v1")
            self.assertTrue(observed["positive_control_read"])
            self.assertTrue(observed["restricted_token_native"])
            self.assertTrue(observed["synthetic_read_denied"])
            self.assertEqual(observed["provider_calls"], 0)
            self.assertFalse(observed["production_subprocess_restricted"])
            self.assertEqual(path.read_bytes(), b"varyn-synthetic-owner-only")

    def test_missing_file_fails_without_claiming_protection(self):
        with TemporaryDirectory(prefix="varyn-restricted-absent-") as folder:
            missing = Path(folder) / "does-not-exist.txt"
            result = self._run((str(missing) + "\n").encode("utf-8"))
            self.assertNotEqual(result.returncode, 0)
            self.assertNotIn(b'"synthetic_read_denied": true', result.stdout)
            self.assertFalse(missing.exists())

    def test_empty_input_cannot_claim_protection(self):
        result = self._run(b"\n")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, b"")


if __name__ == "__main__":
    unittest.main()
