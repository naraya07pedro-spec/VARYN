"""17S-29: offline portable entry and unsigned, bounded SHA256 bundle manifest."""
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from varyn import portable_entry
from varyn.portable_release import (
    PortableBundleRejected, create_manifest, verify_manifest,
)


class PortableEntryContractTests(unittest.TestCase):
    def test_normal_mode_declares_offline_model_capability(self):
        mocked_window = MagicMock()
        with patch.object(portable_entry, "DesktopController") as controller, \
             patch.object(portable_entry, "VarynDesktop",
                          return_value=mocked_window):
            result = portable_entry.create_portable_desktop()
        self.assertIs(result, mocked_window)
        controller.assert_called_once_with(allow_live_providers=False)
        mocked_window.after_idle.assert_called_once()
        self.assertEqual(
            mocked_window.after_idle.call_args.args,
            (mocked_window._open_relay_workbench,),
        )
        mocked_window.mainloop.assert_not_called()
        mocked_window._open_selected_official_app.assert_not_called()
        mocked_window._copy_official_app_relay.assert_not_called()

    def test_smoke_only_constructs_real_module_contract_without_dispatch(self):
        mocked_window = MagicMock()
        mocked_window._relay_workbench.winfo_exists.return_value = True
        mocked_window._model_center.winfo_exists.return_value = True
        mocked_window._model_center.network.get.return_value = False
        mocked_window._model_center._offers = []
        mocked_window._universal_model_live_capability = False
        ctrl = MagicMock()
        ctrl.status.return_value = {"mode": "offline_simulation"}
        with patch.object(portable_entry, "DesktopController",
                          return_value=ctrl) as controller, \
             patch.object(portable_entry, "VarynDesktop",
                          return_value=mocked_window):
            self.assertIsNone(
                portable_entry.create_portable_desktop(smoke_only=True))
        controller.assert_called_once_with(allow_live_providers=False)
        mocked_window.withdraw.assert_called_once()
        mocked_window._open_relay_workbench.assert_called_once()
        mocked_window._open_model_control_center.assert_called_once()
        mocked_window.update_idletasks.assert_called_once()
        mocked_window._close.assert_called_once()
        mocked_window.mainloop.assert_not_called()

    def test_smoke_fails_closed_if_workbench_missing(self):
        mocked_window = MagicMock()
        mocked_window._relay_workbench = None
        with patch.object(portable_entry, "DesktopController"), \
             patch.object(portable_entry, "VarynDesktop",
                          return_value=mocked_window):
            with self.assertRaises(RuntimeError):
                portable_entry.create_portable_desktop(smoke_only=True)
        mocked_window._close.assert_called_once()

    def test_non_boolean_smoke_mode_rejected(self):
        for item in (1, "true", None):
            with self.subTest(item=item), self.assertRaises(ValueError):
                portable_entry.create_portable_desktop(smoke_only=item)

    def test_portable_main_declines_non_admin_elevation_failure(self):
        with patch.object(portable_entry, "windows_non_admin",
                          return_value=False), \
             patch.object(portable_entry.messagebox, "showerror") as error, \
             patch.object(portable_entry, "create_portable_desktop") as start:
            self.assertEqual(portable_entry.main([]), 2)
        start.assert_not_called()
        error.assert_called_once()


class PortableManifestTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "VARYN-Portable"
        self.root.mkdir()
        self._internal = self.root / "_internal"
        self._internal.mkdir()
        (self.root / "VARYN-Portable.exe").write_bytes(b"MZ" + b"synthetic-pe")
        (self._internal / "python312.dll").write_bytes(b"synthetic-runtime")
        (self.root / "README-PORTABLE.txt").write_text(
            "Unsigned experimental synthetic portable", encoding="utf-8")

    def tearDown(self):
        self.temp.cleanup()

    def test_expected_inventory_and_source_free_release(self):
        report = create_manifest(self.root)
        self.assertEqual(report["build_mode"], "windows_amd64_onedir")
        self.assertEqual(report["file_count"], 3)
        self.assertFalse(report["publisher_codesign_verified"])
        self.assertFalse(report["official_consumer_history_two_way_sync_verified"])
        checked = verify_manifest(self.root)
        self.assertTrue(checked["verified_against_unsigned_manifest_only"])
        self.assertFalse(checked["codesign_verified"])
        self.assertEqual(
            checked["exe_sha256"],
            hashlib.sha256((self.root / "VARYN-Portable.exe").read_bytes()).hexdigest(),
        )

    def test_tamper_detected_for_binary_and_hidden_runtime(self):
        create_manifest(self.root)
        (self._internal / "python312.dll").write_bytes(b"malicious replacement")
        with self.assertRaises(PortableBundleRejected):
            verify_manifest(self.root)

    def test_tamper_detected_for_executable(self):
        create_manifest(self.root)
        (self.root / "VARYN-Portable.exe").write_bytes(b"MZ" + b"changed")
        with self.assertRaises(PortableBundleRejected):
            verify_manifest(self.root)

    def test_refuses_bundle_with_data_files_or_credentials(self):
        for path in ("memory.sqlite3", ".env", "credentials.json",
                     "notes.db", "private.zip"):
            with self.subTest(path=path):
                p = self.root / path
                p.write_text("SYNTHETIC_SECRET", encoding="utf-8")
                with self.assertRaises(PortableBundleRejected):
                    create_manifest(self.root)
                p.unlink()

    def test_refuses_manifest_overwrite(self):
        create_manifest(self.root)
        with self.assertRaises(PortableBundleRejected):
            create_manifest(self.root)

    def test_refuses_missing_exec_or_runtime(self):
        (self.root / "VARYN-Portable.exe").unlink()
        with self.assertRaises(PortableBundleRejected):
            create_manifest(self.root)

    def test_refuses_claims_of_verified_app_authority(self):
        create_manifest(self.root)
        path = self.root / "BUNDLE-SHA256.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["official_consumer_history_two_way_sync_verified"] = True
        path.write_text(json.dumps(payload), encoding="utf-8")
        with self.assertRaises(PortableBundleRejected):
            verify_manifest(self.root)

    def test_refuses_fake_binary_header(self):
        (self.root / "VARYN-Portable.exe").write_bytes(b"ZZ-not-an-executable")
        with self.assertRaises(PortableBundleRejected):
            create_manifest(self.root)

    def test_refuses_runtime_added_after_manifest(self):
        create_manifest(self.root)
        (self._internal / "injected.dll").write_bytes(b"attack")
        with self.assertRaises(PortableBundleRejected):
            verify_manifest(self.root)


if __name__ == "__main__":
    unittest.main()
