"""Desktop release and offline preflight regression tests."""
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from varyn.doctor import process_rss_bytes, run_preflight
from varyn.package_desktop import archive_entries, build_zip


class DesktopPackagingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "varyn").mkdir()
        (self.root / "Launch-VARYN.cmd").write_text("@echo off\n", encoding="utf-8")
        (self.root / "Verify-VARYN-Synthetic.cmd").write_text("@echo off\n", encoding="utf-8")
        (self.root / "README.md").write_text("synthetic", encoding="utf-8")
        (self.root / "varyn" / "desktop.py").write_text("print('fake')\n", encoding="utf-8")
        (self.root / "varyn" / "providers.py").write_text("MODEL = 1\n", encoding="utf-8")
        (self.root / ".env").write_text("synthetic-key", encoding="utf-8")
        (self.root / "memory.sqlite3").write_bytes(b"synthetic db bytes")
        (self.root / "varyn" / "temp.pyc").write_bytes(b"cache")
        self.output = self.root / "desktop.zip"

    def tearDown(self):
        self.temp.cleanup()

    def test_zip_contains_only_selected_source(self):
        report = build_zip(self.output, root=self.root)
        self.assertFalse(report["installer"])
        self.assertFalse(report["bundles_python_or_model"])
        with zipfile.ZipFile(self.output) as archive:
            names = archive.namelist()
            self.assertIn("VARYN/Launch-VARYN.cmd", names)
            self.assertIn("VARYN/Verify-VARYN-Synthetic.cmd", names)
            self.assertIn("VARYN/varyn/desktop.py", names)
            self.assertNotIn("VARYN/.env", names)
            self.assertNotIn("VARYN/memory.sqlite3", names)
            self.assertFalse(any(name.endswith(".pyc") for name in names))
            self.assertNotIn(b"synthetic-key", archive.read("VARYN/README.md"))

    def test_missing_required_synthetic_verifier_is_denied(self):
        (self.root / "Verify-VARYN-Synthetic.cmd").unlink()
        with self.assertRaises(ValueError):
            archive_entries(self.root)

    def test_archive_deterministic_for_same_source(self):
        a = build_zip(self.output, root=self.root)
        second = self.root / "other.zip"
        b = build_zip(second, root=self.root)
        self.assertEqual(a["sha256"], b["sha256"])
        self.assertEqual(self.output.read_bytes(), second.read_bytes())

    def test_no_overwrite_existing_archive(self):
        self.output.write_bytes(b"prior")
        with self.assertRaises(FileExistsError):
            build_zip(self.output, root=self.root)
        self.assertEqual(self.output.read_bytes(), b"prior")

    def test_missing_destination_directory_rejected(self):
        with self.assertRaises(FileNotFoundError):
            build_zip(self.root / "missing" / "archive.zip", root=self.root)

    def test_missing_entrypoint_rejected(self):
        (self.root / "varyn" / "desktop.py").unlink()
        with self.assertRaises(FileNotFoundError):
            archive_entries(self.root)

    def test_symlink_source_rejected(self):
        item = self.root / "varyn" / "providers.py"
        item.unlink()
        try:
            item.symlink_to(self.root / "README.md")
        except (OSError, NotImplementedError):
            self.skipTest("Host cannot create symlink")
        with self.assertRaises(ValueError):
            archive_entries(self.root)

    def test_oversized_source_rejected(self):
        (self.root / "varyn" / "providers.py").write_bytes(b"x" * (512 * 1024 + 1))
        with self.assertRaises(ValueError):
            archive_entries(self.root)


class DesktopDoctorTests(unittest.TestCase):
    def test_preflight_does_not_create_window_by_default(self):
        status = run_preflight()
        self.assertEqual(status["gui_smoke"], "not_requested")
        self.assertEqual(status["network_calls"], 0)
        self.assertFalse(status["live_provider_enabled"])
        self.assertEqual(status["rss_scope"], "doctor_process_only")

    def test_preflight_report_contains_no_credentials(self):
        with patch.dict("os.environ", {
            "OPENAI_API_KEY": "synthetic-private-token",
            "GEMINI_API_KEY": "synthetic-private-token",
        }):
            text = json.dumps(run_preflight())
        self.assertNotIn("synthetic-private-token", text)
        self.assertNotIn("OPENAI_API_KEY", text)

    def test_process_rss_is_integer_or_unavailable(self):
        reading = process_rss_bytes()
        self.assertTrue(reading is None or (type(reading) is int and reading > 0))


if __name__ == "__main__":
    unittest.main()
