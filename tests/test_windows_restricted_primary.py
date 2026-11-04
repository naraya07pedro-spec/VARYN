"""17S-11: real suspended Windows restricted-primary-token process tests.

No network, no owner documents, no inherited secret handles. Existing
production tool stays disabled for private files until fully integrated.
"""
import os
import shutil
import subprocess
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from varyn.public_github_tool import PublicToolRejected
from varyn.windows_restricted_primary import spawn_suspended_restricted_primary
from varyn.windows_child_job import WindowsChildJob


class PortableRestrictedPrimaryPolicyTests(unittest.TestCase):
    def test_restrictor_unavailable_outside_windows(self):
        if os.name == "nt":
            self.skipTest("Native Windows integration below")
        with self.assertRaises(PublicToolRejected):
            spawn_suspended_restricted_primary(
                (sys.executable, "-I"), cwd=str(Path(sys.executable).resolve().parent))

    def test_production_is_not_misrepresented_as_restricted_primary(self):
        from varyn.public_tool_process import ProcessRepoFetcher
        status = ProcessRepoFetcher().status()
        self.assertFalse(status["os_sandbox"])
        self.assertFalse(status["windows_mic_blocks_private_reads"])
        from varyn.package_desktop import archive_entries
        self.assertIn(Path(__file__).resolve().parent.parent /
                      "varyn/windows_restricted_primary.py", archive_entries())


@unittest.skipUnless(os.name == "nt", "Native Windows primary token required")
class NativeWindowsRestrictedPrimaryTests(unittest.TestCase):
    def test_control_normal_python_starts_with_same_minimal_environment(self):
        # Causal control: distinguish bad argv/env from the restricted token.
        import subprocess
        result = subprocess.run(
            [str(Path(sys.executable).resolve()), "-I", "-S",
             "-c", "import sys; sys.exit(0)"],
            cwd=str(Path(sys.executable).resolve().parent),
            env={"SystemRoot": os.environ["SystemRoot"]},
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            timeout=8, check=False,
        )
        self.assertEqual(result.returncode, 0)


    def _prepare_synthetic_python_runtime(self, root):
        """Copy only trusted Python runtime files; never edit source ACLs."""
        original = Path(sys.executable).resolve()
        dest = root / "trusted-runtime-copy"
        dest.mkdir()
        for item in original.parent.iterdir():
            if (item.is_file() and
                    (item.name.lower() == original.name.lower() or
                     (item.suffix.lower() == ".dll" and
                      item.name.lower().startswith(("python", "vcruntime"))))):
                shutil.copy2(item, dest / item.name)
        lib_src = Path(sys.base_prefix) / "Lib"
        lib_dest = dest / "Lib"
        lib_dest.mkdir()
        shutil.copytree(lib_src / "encodings", lib_dest / "encodings")
        for name in ("os.py", "codecs.py"):
            if (lib_src / name).is_file():
                shutil.copy2(lib_src / name, lib_dest / name)
        exe_copy = dest / original.name
        self.assertTrue(exe_copy.is_file())
        # READ+EXECUTE on disposable copies ONLY. No owner files or OS ACLs.
        result = subprocess.run(
            ["icacls", str(dest), "/grant", "*S-1-5-12:(OI)(CI)RX", "/T"],
            capture_output=True, text=True, timeout=15, check=False)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return exe_copy

    def _launch_probe(self, target, exe):
        # Restricted-primary token MUST exist before child starts (suspended),
        # then attach job + Low MIC before any untrusted argv executes.
        source = (
            "import sys\n"
            "try:\n"
            " with open(sys.argv[1],'rb') as f: f.read()\n"
            " sys.exit(61)\n"
            "except PermissionError:\n"
            " sys.exit(0)\n"
            "except FileNotFoundError:\n"
            " sys.exit(62)\n"
            "except Exception:\n"
            " sys.exit(63)\n"
        )
        command = (str(exe), "-I", "-S", "-c", source, str(target))
        # Test scope: trusted interpreter is an exact copied executable.
        with patch("varyn.windows_restricted_primary.sys.executable",
                   str(exe)):
            return spawn_suspended_restricted_primary(
                command, cwd=str(exe.parent))

    def test_diagnostic_primary_token_without_low_mic_denies_synthetic_read(self):
        with TemporaryDirectory(prefix="varyn-primary-token-") as folder:
            exe = self._prepare_synthetic_python_runtime(Path(folder))
            target = Path(folder) / "synthetic-private-only.txt"
            target.write_bytes(b"VARYN synthetic only")
            self.assertEqual(target.read_bytes(), b"VARYN synthetic only")
            proc = None
            guard = None
            try:
                proc = self._launch_probe(target, exe)
                self.assertIsNone(proc.poll())
                self.assertFalse(proc._resumed)
                # DIAGNOSTIC: no Low MIC or Job Object applied at startup.
                # This isolates whether the restricted primary token itself
                # can initialize Python. It is NOT the production integration.
                self.assertIsNone(proc.poll())
                proc.resume()
                observed = proc.wait(timeout=8)
                print("17S-11 restricted-primary diagnostic without Low MIC: "
                      + hex(observed), flush=True)
                self.assertEqual(observed, 0,
                                 "Restricted PRIMARY token must run and deny a "
                                 "fresh read even before Low MIC integration")
                self.assertEqual(target.read_bytes(), b"VARYN synthetic only")
            finally:
                if guard is not None:
                    guard.close()
                if proc is not None:
                    proc.close()

    def test_absent_file_cannot_be_counted_as_restricted_read_denial(self):
        with TemporaryDirectory(prefix="varyn-primary-absent-") as folder:
            exe = self._prepare_synthetic_python_runtime(Path(folder))
            target = Path(folder) / "never-created.txt"
            proc = None
            guard = None
            try:
                proc = self._launch_probe(target, exe)
                # Same causal diagnostic without the Low MIC transition.
                proc.resume()
                observed = proc.wait(timeout=8)
                print("17S-11 absent-file diagnostic without Low MIC: "
                      + hex(observed), flush=True)
                self.assertEqual(observed, 62)
            finally:
                if guard is not None:
                    guard.close()
                if proc is not None:
                    proc.close()

    def test_invalid_input_does_not_spawn_unrestricted_python(self):
        cwd = str(Path(sys.executable).resolve().parent)
        with self.assertRaises(PublicToolRejected):
            spawn_suspended_restricted_primary(
                ("C:\\windows\\system32\\cmd.exe", "/c", "echo"), cwd=cwd)
        with self.assertRaises(PublicToolRejected):
            spawn_suspended_restricted_primary(
                (sys.executable, "-I"), cwd="C:\\Windows")
        with patch("varyn.windows_restricted_primary._apis",
                   side_effect=PublicToolRejected("native unavailable")):
            with self.assertRaises(PublicToolRejected):
                spawn_suspended_restricted_primary(
                    (sys.executable, "-I"), cwd=cwd)


if __name__ == "__main__":
    unittest.main()
