"""17S-34 frozen restart process gates: strict temp scope and fixed synthetic data."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, MagicMock

from varyn.frozen_draft_probe import (
    _FIXED, FrozenProbeRejected, probe_directory, run_probe_phase,
    frozen_restart_acceptance, _child,
)


class FrozenRestartContractTests(unittest.TestCase):
    def test_fixed_fixture_stays_synthetic_without_authentication_claims(self):
        self.assertTrue(_FIXED["task"].startswith("SYNTHETIC:"))
        self.assertTrue(_FIXED["note"].startswith("SYNTHETIC:"))
        for k in ("provider_history_authenticated",
                  "automatic_bidirectional_sync", "pasted_reply_persisted"):
            self.assertIs(_FIXED[k], False)

    def test_only_single_temporary_named_folder_permitted(self):
        with tempfile.TemporaryDirectory(prefix="varyn-probe-") as d:
            self.assertEqual(probe_directory(d), Path(d))
        with tempfile.TemporaryDirectory(prefix="other-temp-") as d:
            with self.assertRaises(FrozenProbeRejected):
                probe_directory(d)
        with self.assertRaises(FrozenProbeRejected):
            probe_directory("not-a-directory")
        with self.assertRaises(FrozenProbeRejected):
            probe_directory(5)

    def test_refuses_subfolder_and_foreign_paths(self):
        with tempfile.TemporaryDirectory(prefix="varyn-probe-") as d:
            folder = Path(d) / "child"
            folder.mkdir()
            with self.assertRaises(FrozenProbeRejected):
                probe_directory(str(folder))

    def test_unsupported_phase_never_reaches_dpapi(self):
        with patch("varyn.frozen_draft_probe.save_new") as writer, \
             patch("varyn.frozen_draft_probe.load_existing") as reader:
            with self.assertRaises(FrozenProbeRejected):
                run_probe_phase("export-browser-history", "x")
        writer.assert_not_called()
        reader.assert_not_called()

    def test_child_uses_argument_list_not_shell_or_console(self):
        fake = MagicMock()
        fake.returncode = 0
        with patch("varyn.frozen_draft_probe.subprocess.run",
                   return_value=fake) as call:
            self.assertEqual(_child("VARYN-Portable.exe", "read",
                                    "synthetic-directory"), 0)
        args, kw = call.call_args
        self.assertEqual(args[0][1:3], ["--synthetic-draft-smoke", "read"])
        self.assertNotIn("shell", kw)
        self.assertEqual(kw["timeout"], 40)
        self.assertIs(kw["check"], False)

    def test_no_win_acceptance_claim(self):
        if os.name != "nt":
            with self.assertRaises(FrozenProbeRejected):
                frozen_restart_acceptance("VARYN-Portable.exe")
        else:
            with self.assertRaises(FrozenProbeRejected):
                frozen_restart_acceptance("not-the-portable.exe")


@unittest.skipUnless(os.name == "nt", "Native Windows DPAPI and temp directory only")
class WindowsNativeFrozenProbeUnitTests(unittest.TestCase):
    def test_source_process_dpapi_phases_refuse_overwrite_and_tamper(self):
        with tempfile.TemporaryDirectory(prefix="varyn-probe-") as d:
            from varyn.dpapi_vault import SealedDataError
            path = Path(d) / "synthetic-draft.varyn"
            self.assertEqual(run_probe_phase("write", d), 0)
            self.assertEqual(run_probe_phase("read", d), 0)
            with self.assertRaises(FileExistsError):
                run_probe_phase("write", d)
            data = bytearray(path.read_bytes())
            data[-1] ^= 1
            path.write_bytes(data)
            with self.assertRaises(SealedDataError):
                run_probe_phase("read", d)


if __name__ == "__main__":
    unittest.main()
