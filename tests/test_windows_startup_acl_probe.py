"""17S-12: real Windows resource access triage, offline and privacy-redacted.

The reported result is a restricted THREAD impersonation check on individual
resource handles. It does NOT imply that a restricted PRIMARY-token process
can load, and can never authorize private files or production tool dispatch.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

SCHEMA = "varyn.windows_startup_acl_probe.v1"
_PROBE = Path(__file__).with_name("windows_startup_acl_probe.py")


class PortableAccessTriagePolicy(unittest.TestCase):
    def test_preflight_script_is_excluded_from_desktop_and_production(self):
        from varyn.public_tool_process import ProcessRepoFetcher
        from varyn.package_desktop import archive_entries
        self.assertTrue(_PROBE.is_file())
        self.assertNotIn(_PROBE, archive_entries())
        status = ProcessRepoFetcher().status()
        self.assertFalse(status["os_sandbox"])
        self.assertFalse(status["windows_mic_blocks_private_reads"])
        self.assertFalse(status["windows_restricted_primary_production_enabled"])

    def test_non_windows_probe_refuses_to_attest_windows(self):
        if os.name == "nt":
            self.skipTest("Real Windows probe below")
        p = subprocess.run(
            [sys.executable, "-I", "-S", str(_PROBE)], input=b"{}",
            capture_output=True, timeout=5, check=False)
        self.assertEqual(p.returncode, 2)


@unittest.skipUnless(os.name == "nt", "Actual Win32 ACL check required")
class NativeWindowsResourceAccessTriage(unittest.TestCase):
    def _run(self, obj):
        return subprocess.run(
            [str(Path(sys.executable).resolve()), "-I", "-S", str(_PROBE)],
            input=json.dumps(obj).encode("utf-8"),
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10,
            cwd=str(Path(sys.executable).resolve().parent),
            env={"SystemRoot": os.environ["SystemRoot"]},
            shell=False, close_fds=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))

    def test_kernel_access_report_separates_runtime_and_synthetic_denial(self):
        with TemporaryDirectory(prefix="varyn-17s12-acl-") as folder:
            root = Path(folder)
            runtime = root / "runtime-copy"
            runtime.mkdir()
            original = Path(sys.executable).resolve()
            exe = runtime / original.name
            shutil.copy2(original, exe)
            dlls = sorted(original.parent.glob("python*.dll"))
            self.assertTrue(dlls, "Windows Python runtime DLL expected")
            dll = runtime / dlls[-1].name
            shutil.copy2(dlls[-1], dll)
            allowed = runtime / "synthetic-allowed.txt"
            allowed.write_bytes(b"varyn-no-private-data")
            denied = root / "synthetic-owner-only.txt"
            denied.write_bytes(b"varyn-no-private-data")

            acl = subprocess.run(
                ["icacls", str(runtime), "/grant",
                 "*S-1-5-12:(OI)(CI)RX", "/T"],
                capture_output=True, text=True, timeout=15, check=False)
            self.assertEqual(acl.returncode, 0, acl.stdout + acl.stderr)

            targets = {
                "synthetic_allowed": {"path": str(allowed), "kind": "file"},
                "synthetic_denied": {"path": str(denied), "kind": "file"},
                "runtime_copy_executable": {"path": str(exe), "kind": "file"},
                "runtime_copy_dll": {"path": str(dll), "kind": "file"},
                "runtime_copy_dir": {"path": str(runtime), "kind": "directory"},
                "runtime_ancestor_1": {"path": str(root), "kind": "directory"},
                "runtime_ancestor_2": {"path": str(root.parent), "kind": "directory"},
                "runtime_ancestor_3": {
                    "path": str(root.parent.parent), "kind": "directory"},
                "system_dll": {
                    "path": str(Path(os.environ["SystemRoot"]) /
                                "System32" / "kernel32.dll"), "kind": "file"},
            }
            outcome = self._run({"format": SCHEMA, "targets": targets})
            self.assertEqual(outcome.returncode, 0,
                             outcome.stdout.decode(errors="replace") +
                             outcome.stderr.decode(errors="replace"))
            observed = json.loads(outcome.stdout)
            self.assertEqual(observed["format"], SCHEMA)
            self.assertTrue(observed["restricted_thread_token"])
            self.assertFalse(observed["restricted_primary_runtime_executed"])
            self.assertFalse(observed["raw_paths_persisted"])
            self.assertFalse(observed["private_bytes_read"])
            self.assertEqual(set(observed["normal"]), set(targets))
            self.assertEqual(set(observed["restricted"]), set(targets))
            self.assertEqual(set(observed["normal_minimal"]), set(targets))
            self.assertEqual(set(observed["restricted_minimal"]), set(targets))
            self.assertEqual(
                observed["minimal_mode"],
                "FILE_TRAVERSE(directory)/FILE_EXECUTE(file)")
            self.assertTrue(all(x == "allowed" for x in
                                observed["normal"].values()))
            self.assertTrue(all(x == "allowed" for x in
                                observed["normal_minimal"].values()))
            # BOTH controls are required. An inaccessible/missing target
            # cannot be misclassified as an effective restricted access check.
            self.assertEqual(observed["restricted"]["synthetic_allowed"],
                             "allowed", observed["restricted"])
            self.assertEqual(observed["restricted"]["synthetic_denied"],
                             "denied", observed["restricted"])
            self.assertEqual(
                observed["restricted_minimal"]["synthetic_allowed"],
                "allowed", observed["restricted_minimal"])
            self.assertEqual(
                observed["restricted_minimal"]["synthetic_denied"],
                "denied", observed["restricted_minimal"])
            for value in (list(observed["restricted"].values()) +
                          list(observed["restricted_minimal"].values())):
                self.assertIn(value, ("allowed", "denied", "missing", "other"))
            report = outcome.stdout.decode("utf-8")
            self.assertNotIn(str(root), report)
            self.assertNotIn(str(original), report)
            self.assertNotIn("varyn-no-private-data", report)
            # Explainable, bounded summary only; not a path or user-SID dump.
            print("17S-12 GENERIC_READ by category (restricted THREAD): "
                  + json.dumps(observed["restricted"], sort_keys=True),
                  flush=True)
            print("17S-12 TRAVERSE/EXECUTE by category (restricted THREAD): "
                  + json.dumps(observed["restricted_minimal"], sort_keys=True),
                  flush=True)
            self.assertEqual(denied.read_bytes(), b"varyn-no-private-data")
            self.assertEqual(allowed.read_bytes(), b"varyn-no-private-data")

    def test_invalid_categories_and_shapes_do_not_collect_paths(self):
        bad = [
            {"format": SCHEMA, "targets": {"unknown": {"path": "C:\\", "kind": "file"}}},
            {"format": SCHEMA, "targets": {}},
            {"format": SCHEMA, "targets": {"synthetic_allowed":
                 {"path": "C:\\", "kind": "file", "secret": "never"}}},
            {"format": "wrong", "targets": {}},
        ]
        for obj in bad:
            with self.subTest(obj=list(obj)):
                result = self._run(obj)
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn(b'"restricted_thread_token": true',
                                 result.stdout)


if __name__ == "__main__":
    unittest.main()
