"""17C native Windows handle-anchored access tests, disposable synthetic only."""
import os
import tempfile
import unittest
from pathlib import Path

from varyn.agent_runtime import AgentRejected
from varyn.scoped_files import ScopedLocalReader
from varyn.windows_scoped_native import WindowsScopedDirectory


class NativePlatformGateTests(unittest.TestCase):
    @unittest.skipIf(os.name == "nt", "Non-Windows-only test")
    def test_native_scope_unavailable_without_windows(self):
        with self.assertRaises(AgentRejected):
            WindowsScopedDirectory(Path("/tmp"), 1)


@unittest.skipUnless(os.name == "nt", "Needs a real Windows kernel handle")
class NativeWindowsHandleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "approved"
        self.root.mkdir()
        (self.root / "allowed.txt").write_text(
            "synthetic approved content", encoding="utf-8"
        )
        (self.root / "notes.md").write_text("synthetic notes", encoding="utf-8")
        (self.root / "private.env").write_text("synthetic denied", encoding="utf-8")

    def reader(self):
        reader = ScopedLocalReader(self.root)
        self.addCleanup(reader.close)
        self.assertIsNotNone(reader._win_scope)
        return reader

    def test_real_native_handle_reader_round_trip(self):
        reader = self.reader()
        self.assertIsNone(reader._root_fd)
        self.assertEqual(reader.read_text("allowed.txt")["text"],
                         "synthetic approved content")
        self.assertFalse(reader.read_text("allowed.txt")["external_upload"])

    def test_native_listing_uses_pinned_directory(self):
        reader = self.reader()
        listed = reader.list_files()
        self.assertEqual(
            {entry["name"] for entry in listed["files"]},
            {"allowed.txt", "notes.md"},
        )
        self.assertTrue(listed["read_only"])
        self.assertFalse(listed["recursive"])

    def test_native_close_blocks_further_reads(self):
        reader = self.reader()
        native = reader._win_scope
        reader.close()
        self.assertIsNone(native._handle)
        with self.assertRaises(AgentRejected):
            reader.list_files()
        with self.assertRaises(AgentRejected):
            native.read_bounded("allowed.txt", 128)

    def test_native_scope_rejects_hardlink_to_external_file(self):
        outside = Path(self.temp.name) / "outsider.txt"
        outside.write_text("outside synthetic", encoding="utf-8")
        linked = self.root / "linked.txt"
        try:
            os.link(outside, linked)
        except OSError:
            self.skipTest("Windows filesystem does not permit hardlinks")
        reader = self.reader()
        with self.assertRaises(AgentRejected):
            reader.read_text("linked.txt")
        self.assertNotIn("linked.txt", [f["name"] for f in reader.list_files()["files"]])

    def test_native_scope_rejects_reparse_symlink_to_external_file(self):
        outside = Path(self.temp.name) / "outsider.txt"
        outside.write_text("outside synthetic", encoding="utf-8")
        linked = self.root / "redirect.txt"
        try:
            linked.symlink_to(outside)
        except (OSError, NotImplementedError):
            self.skipTest("Windows native symlink creation unavailable")
        reader = self.reader()
        with self.assertRaises(AgentRejected):
            reader.read_text("redirect.txt")
        self.assertNotIn("redirect.txt", [f["name"] for f in reader.list_files()["files"]])

    def test_native_scope_never_uses_path_fallback(self):
        reader = self.reader()
        native = reader._win_scope
        native.close()
        with self.assertRaises(AgentRejected):
            reader.read_text("allowed.txt")
        with self.assertRaises(AgentRejected):
            reader.list_files()

    def test_native_file_limit_and_non_text_file_rejections(self):
        reader = self.reader()
        (self.root / "large.txt").write_bytes(b"x" * 17000)
        with self.assertRaises(AgentRejected):
            reader.read_text("large.txt")
        with self.assertRaises(AgentRejected):
            reader.read_text("private.env")
        self.assertNotIn("large.txt", [f["name"] for f in reader.list_files()["files"]])

    def test_native_relative_child_cannot_be_absolute_or_nested(self):
        reader = self.reader()
        native = reader._win_scope
        for name in ("../allowed.txt", "..\\allowed.txt",
                     "C:\\outside.txt", "/outside.txt"):
            with self.subTest(name=name), self.assertRaises(AgentRejected):
                native.read_bounded(name, 128)

    def test_native_handle_pins_origin_across_directory_path_swap(self):
        reader = self.reader()
        native = reader._win_scope
        moved = self.root.with_name("moved")
        try:
            self.root.rename(moved)
        except OSError:
            self.skipTest("Windows prevented renaming an open directory")
        self.root.mkdir()
        (self.root / "allowed.txt").write_text(
            "new unapproved content", encoding="utf-8"
        )
        # Pinned native handle still references the original directory object.
        self.assertEqual(native.read_bounded("allowed.txt", 128),
                         b"synthetic approved content")
        with self.assertRaises(AgentRejected):
            reader.read_text("allowed.txt")


if __name__ == "__main__":
    unittest.main()
