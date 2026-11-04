"""18A: offline acceptance tests; only newly generated example files."""
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from varyn.desktop_acceptance import main, run_synthetic_acceptance


class OfflineWindowsAcceptanceTests(unittest.TestCase):
    def test_actual_idle_expiry_and_cleanup_without_user_file(self):
        # Runs natively on Windows GitHub runner as well as Linux.
        report = run_synthetic_acceptance(duration_seconds=1, wait_seconds=6)
        self.assertTrue(report["passed"], report["checks"])
        self.assertTrue(all(report["checks"].values()))
        self.assertFalse(report["user_paths_accessed"])
        self.assertFalse(report["external_upload"])
        self.assertFalse(report["owner_windows_gui_verified"])
        self.assertEqual(report["network_requests"], 0)

    def test_sanitized_report_never_contains_fixture_path_or_bytes(self):
        with tempfile.TemporaryDirectory() as folder:
            marker = Path(folder) / "PRIVATE_SENTINEL.txt"
            marker.write_text("fake_secret_for_test", encoding="utf-8")
            report = run_synthetic_acceptance(duration_seconds=1,
                                              wait_seconds=6)
            output = json.dumps(report)
            self.assertTrue(report["passed"])
            self.assertNotIn(str(folder), output)
            self.assertNotIn("PRIVATE_SENTINEL", output)
            self.assertNotIn("fake_secret_for_test", output)
            self.assertNotIn("sample.txt", output)
            self.assertNotIn("notes.md", output)

    def test_creation_failure_is_fail_closed_without_exception_details(self):
        with patch("varyn.desktop_acceptance.SyntheticFixture",
                   side_effect=RuntimeError("PRIVATE_PATH or credentials")):
            report = run_synthetic_acceptance()
        self.assertFalse(report["passed"])
        self.assertEqual(report["network_requests"], 0)
        self.assertNotIn("PRIVATE_PATH", json.dumps(report))
        self.assertNotIn("credentials", json.dumps(report))

    def test_invalid_timing_never_runs_test(self):
        for values in (
            {"duration_seconds": True},
            {"duration_seconds": 0},
            {"duration_seconds": 9},
            {"wait_seconds": 0},
            {"wait_seconds": "9"},
        ):
            with self.subTest(values=values), self.assertRaises(ValueError):
                run_synthetic_acceptance(**values)

    def test_cli_requires_explicit_synthetic_only_mode(self):
        with redirect_stdout(io.StringIO()), self.assertRaises(SystemExit) as err:
            main([])
        self.assertEqual(err.exception.code, 2)

    def test_cli_disallows_any_user_supplied_folder_path(self):
        with redirect_stdout(io.StringIO()), self.assertRaises(SystemExit) as err:
            main(["--synthetic-only", "--folder", "C:/Users/Documents"])
        self.assertEqual(err.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
