"""17S-44 full SHA256 portable owner PowerShell launcher acceptance."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from varyn.portable_release import create_manifest, verify_manifest

REPO = Path(__file__).resolve().parents[1]
SCRIPT = "Start-VARYN-OwnerPilot.ps1"


class PortablePilotPowerShellSourceTests(unittest.TestCase):
    def test_default_offline_and_no_key_persistence_or_policy_bypass(self):
        text = (REPO / SCRIPT).read_text(encoding="utf-8").lower()
        for expected in (
            "verifyonly", "'offline'", "securestringtobstr",
            "zerofreebstr", "get-portablesha256", "bundle-sha256.json",
            "read-host", "start-process", "isinrole",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, text)
        for banned in ("-executionpolicy bypass", "setx.exe", " -verb runas",
                       "invoke-webrequest", "convertfrom-securestring",
                       "add-content", "out-file", "set-content"):
            with self.subTest(banned=banned):
                self.assertNotIn(banned, text)


@unittest.skipUnless(os.name == "nt", "Real Windows PowerShell required")
class PortablePilotPowerShellWindowsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "VARYN-Portable"
        self.root.mkdir()
        (self.root / "_internal").mkdir()
        (self.root / "VARYN-Portable.exe").write_bytes(
            b"MZ" + b"SYNTHETIC: not an executable, only hash test"
        )
        (self.root / "_internal" / "runtime.dll").write_bytes(b"SYNTHETIC")
        (self.root / "README-PORTABLE.txt").write_text(
            "SYNTHETIC: unsigned test bundle", encoding="utf-8"
        )
        shutil.copy2(REPO / SCRIPT, self.root / SCRIPT)
        create_manifest(self.root)
        self.assertEqual(verify_manifest(self.root)["files"], 4)

    def tearDown(self):
        self.temp.cleanup()

    def verify(self):
        env = os.environ.copy()
        for name in ("OPENROUTER_API_KEY", "DEEPSEEK_API_KEY",
                     "VARYN_9ROUTER_API_KEY"):
            env.pop(name, None)
        return subprocess.run(
            ["powershell.exe", "-NoLogo", "-NoProfile",
             "-File", str(self.root / SCRIPT), "-VerifyOnly"],
            cwd=self.root, env=env, capture_output=True, text=True,
            timeout=35, check=False,
        )

    def test_clean_folder_passes_real_windows_ps_51(self):
        p = self.verify()
        self.assertEqual(
            p.returncode, 0,
            "Synthetic owner script verify failed: " +
            p.stdout[-400:] + p.stderr[-400:],
        )
        self.assertIn("PASS: local file inventory", p.stdout)
        self.assertIn("UNSIGNED", p.stdout)

    def test_modified_launcher_is_denied_even_if_script_still_runs(self):
        path = self.root / SCRIPT
        path.write_text(
            path.read_text(encoding="utf-8") +
            "\n# SYNTHETIC altered launcher after hashing\n", encoding="utf-8",
        )
        p = self.verify()
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("BLOCKED", p.stdout)
        self.assertNotIn("PASS: local file inventory", p.stdout)

    def test_missing_or_extra_file_is_denied(self):
        extra = self.root / "_internal" / "unexpected.bin"
        extra.write_bytes(b"INJECTED")
        p = self.verify()
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("BLOCKED", p.stdout)
        extra.unlink()
        (self.root / "_internal" / "runtime.dll").unlink()
        p = self.verify()
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("BLOCKED", p.stdout)


if __name__ == "__main__":
    unittest.main()
