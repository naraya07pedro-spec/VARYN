"""17D: native Windows read consistency / fixed-drive safety, synthetic only."""
import os
import tempfile
import unittest
from pathlib import Path, PureWindowsPath
from types import SimpleNamespace
from unittest.mock import patch

from varyn.agent_runtime import AgentRejected
from varyn.scoped_files import ScopedLocalReader
from varyn.windows_scoped_native import (
    _require_fixed_local_volume, _content_signature,
    _OFFLINE, _RECALL_ON_DATA_ACCESS, _RECALL_ON_OPEN,
)


class FixedVolumePolicyTests(unittest.TestCase):
    def test_drive_letter_fixed_volume_is_accepted(self):
        calls = []
        fake = SimpleNamespace(GetDriveTypeW=lambda root: calls.append(root) or 3)
        _require_fixed_local_volume(PureWindowsPath("C:/synthetic"), fake)
        _require_fixed_local_volume(PureWindowsPath("d:/synthetic"), fake)
        self.assertEqual(len(calls), 2)
        self.assertTrue(all(x.endswith("\\") for x in calls))

    def test_remote_removable_unknown_cd_and_ram_denied(self):
        for code in (0, 1, 2, 4, 5, 6):
            with self.subTest(drive_type=code), self.assertRaises(AgentRejected):
                _require_fixed_local_volume(
                    PureWindowsPath("C:/synthetic"),
                    SimpleNamespace(GetDriveTypeW=lambda unused, n=code: n),
                )

    def test_unc_extended_and_drive_relative_paths_denied(self):
        fake = SimpleNamespace(GetDriveTypeW=lambda root: 3)
        for pathname in ("//server/share/test", "//?/C:/test", "C:relative"):
            with self.subTest(path=pathname), self.assertRaises(AgentRejected):
                _require_fixed_local_volume(PureWindowsPath(pathname), fake)

    def test_content_signature_detects_last_write_modification(self):
        def info(tick):
            return SimpleNamespace(
                dwVolumeSerialNumber=7, dwFileAttributes=32,
                nNumberOfLinks=1,
                ftLastWriteTime=SimpleNamespace(dwHighDateTime=1,
                                                dwLowDateTime=tick),
            )
        first = _content_signature(info(100), 20, 42)
        self.assertNotEqual(first, _content_signature(info(101), 20, 42))
        self.assertNotEqual(first, _content_signature(info(100), 21, 42))
        self.assertNotEqual(first, _content_signature(info(100), 20, 43))


@unittest.skipUnless(os.name == "nt", "Requires real Windows native handle")
class NativeWindowsReadStabilityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "test"
        self.root.mkdir()
        self.file = self.root / "allowed.txt"
        self.file.write_text("synthetic original content", encoding="utf-8")

    def reader(self):
        reader = ScopedLocalReader(self.root)
        self.addCleanup(reader.close)
        return reader

    def test_native_read_detects_append_between_metadata_and_read(self):
        reader = self.reader()
        native = reader._win_scope
        original_kernel = native._kernel
        path = self.file

        class MutatingKernel:
            def __getattr__(self, name):
                return getattr(original_kernel, name)

            def ReadFile(self, *args):
                with path.open("ab") as output:
                    output.write(b" appended")
                    output.flush()
                return original_kernel.ReadFile(*args)

        native._kernel = MutatingKernel()
        with self.assertRaises(AgentRejected):
            reader.read_text("allowed.txt")
        self.assertTrue(self.file.read_bytes().endswith(b" appended"))

    def test_native_read_blocks_remote_placeholder_attributes(self):
        import varyn.windows_scoped_native as native_module

        reader = self.reader()
        original = native_module._file_info
        for flag in (_OFFLINE, _RECALL_ON_OPEN, _RECALL_ON_DATA_ACCESS):
            def flagged_info(kernel, handle, chosen=flag):
                metadata, size, identifier = original(kernel, handle)
                metadata.dwFileAttributes |= chosen
                return metadata, size, identifier

            with self.subTest(flag=flag), patch.object(
                native_module, "_file_info", side_effect=flagged_info
            ):
                with self.assertRaises(AgentRejected):
                    reader.read_text("allowed.txt")
        self.assertEqual(self.file.read_text(encoding="utf-8"),
                         "synthetic original content")

    def test_real_fixed_volume_native_read_is_unchanged(self):
        reader = self.reader()
        self.assertEqual(
            reader.read_text("allowed.txt")["text"],
            "synthetic original content",
        )


if __name__ == "__main__":
    unittest.main()
