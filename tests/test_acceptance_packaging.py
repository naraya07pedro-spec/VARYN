"""17H: ZIP bundles the safe verification launcher, never account data."""
import tempfile
import unittest
import zipfile
from pathlib import Path

from varyn.package_desktop import build_zip


class SyntheticAcceptancePackageTests(unittest.TestCase):
    def test_source_zip_includes_offline_acceptance_and_no_sensitive_data(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "synthetic-ci.zip"
            result = build_zip(target)
            self.assertFalse(result["installer"])
            self.assertFalse(result["bundles_python_or_model"])
            self.assertEqual(result["api_calls"], 0)
            with zipfile.ZipFile(target) as z:
                names = set(z.namelist())
                self.assertIn("VARYN/Verify-VARYN-Synthetic.cmd", names)
                self.assertIn("VARYN/varyn/desktop_acceptance.py", names)
                self.assertIn("VARYN/varyn/official_app_evidence.py", names)
                self.assertTrue(all(
                    n.endswith((".py", ".md", ".cmd")) for n in names
                ))
                self.assertFalse(any(
                    n.endswith((".sqlite3", ".db", ".env", ".exe", ".json"))
                    for n in names
                ))

    def test_launch_script_invokes_only_synthetic_acceptance(self):
        text = (Path(__file__).resolve().parent.parent /
                "Verify-VARYN-Synthetic.cmd").read_text(encoding="utf-8")
        self.assertIn("--synthetic-only", text)
        self.assertIn("-m varyn.desktop_acceptance", text)
        self.assertNotIn("runas", text.lower())
        self.assertNotIn("ExecutionPolicy Bypass", text)

    def test_source_zip_never_contains_data_export_files(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "safe.zip"
            build_zip(output)
            with zipfile.ZipFile(output) as z:
                all_names = z.namelist()
                self.assertFalse(any(
                    "conversations.json" in name.lower() or
                    "takeout" in name.lower() or
                    ".env" in name.lower()
                    for name in all_names
                ))


if __name__ == "__main__":
    unittest.main()
