"""16A tests of a host-selected, bounded read-only local directory."""
import os
import tempfile
import unittest
from pathlib import Path

from varyn.agent_runtime import AgentRejected
from varyn.scoped_files import ScopedLocalReader


class ScopedFileTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "hello.txt").write_text("synthetic hello", encoding="utf-8")
        (self.root / "notes.md").write_text("# synthetic", encoding="utf-8")
        self.reader = ScopedLocalReader(self.root, max_bytes=1024)

    def test_list_is_read_only_and_bounded(self):
        report = self.reader.list_files()
        self.assertEqual({x["name"] for x in report["files"]},
                         {"hello.txt", "notes.md"})
        self.assertFalse(report["recursive"])
        self.assertTrue(report["read_only"])

    def test_read_exact_utf8_basename(self):
        result = self.reader.read_text("hello.txt")
        self.assertEqual(result["text"], "synthetic hello")
        self.assertEqual(result["name"], "hello.txt")
        self.assertFalse(result["external_upload"])

    def test_traversal_absolute_and_backslash_rejected(self):
        for name in ("../hello.txt", "sub/hello.txt", "sub\\hello.txt",
                     "/tmp/hello.txt", "C:\\secret.txt", "..",
                     "hello.txt/.."):
            with self.subTest(name=name), self.assertRaises(AgentRejected):
                self.reader.read_text(name)

    def test_disallow_non_text_and_hidden(self):
        (self.root / "secret.env").write_text("synthetic", encoding="utf-8")
        (self.root / ".hidden.txt").write_text("synthetic", encoding="utf-8")
        for name in ("secret.env", ".hidden.txt", "image.png", "notes.docx"):
            with self.subTest(name=name), self.assertRaises(AgentRejected):
                self.reader.read_text(name)
        self.assertNotIn("secret.env",
            [x["name"] for x in self.reader.list_files()["files"]])

    def test_no_recursive_subdirectory(self):
        (self.root / "nested").mkdir()
        (self.root / "nested" / "child.txt").write_text("synthetic")
        names = [x["name"] for x in self.reader.list_files()["files"]]
        self.assertNotIn("child.txt", names)
        with self.assertRaises(AgentRejected):
            self.reader.read_text("nested/child.txt")

    def test_oversize_is_excluded_and_denied(self):
        (self.root / "large.txt").write_bytes(b"x" * 1025)
        with self.assertRaises(AgentRejected):
            self.reader.read_text("large.txt")
        self.assertNotIn("large.txt",
            [x["name"] for x in self.reader.list_files()["files"]])

    def test_reject_non_utf8_binary_and_null(self):
        (self.root / "binary.txt").write_bytes(b"\xff\xfe")
        (self.root / "nul.txt").write_bytes(b"a\x00b")
        with self.assertRaises(AgentRejected):
            self.reader.read_text("binary.txt")
        with self.assertRaises(AgentRejected):
            self.reader.read_text("nul.txt")

    def test_symlink_outside_root_is_not_read(self):
        target = self.root.parent / ("outside_" + self.root.name + ".txt")
        target.write_text("outside synthetic", encoding="utf-8")
        self.addCleanup(lambda: target.unlink(missing_ok=True))
        link = self.root / "link.txt"
        try:
            link.symlink_to(target)
        except (OSError, NotImplementedError):
            self.skipTest("Symlink creation unavailable")
        with self.assertRaises(AgentRejected):
            self.reader.read_text("link.txt")
        self.assertNotIn("link.txt",
            [x["name"] for x in self.reader.list_files()["files"]])

    def test_root_symlink_disallowed(self):
        link = self.root.parent / ("link_" + self.root.name)
        try:
            link.symlink_to(self.root, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("Directory symlink unavailable")
        self.addCleanup(lambda: link.unlink(missing_ok=True))
        with self.assertRaises(ValueError):
            ScopedLocalReader(link)

    def test_nonexistent_or_relative_root_denied(self):
        with self.assertRaises(ValueError):
            ScopedLocalReader(Path("relative_folder"))
        with self.assertRaises(ValueError):
            ScopedLocalReader(self.root / "absent")

    def test_replaced_root_identity_denied(self):
        replacement = self.root.parent / (self.root.name + "_old")
        try:
            self.root.rename(replacement)
            self.root.mkdir()
        except OSError:
            self.skipTest("Platform prevented root directory rename")
        self.addCleanup(lambda: replacement.exists() and
                        __import__("shutil").rmtree(replacement, ignore_errors=True))
        with self.assertRaises(AgentRejected):
            self.reader.list_files()

    def test_list_cap_and_deterministic_order(self):
        for index in range(7):
            (self.root / f"item{index}.txt").write_text("x")
        reader = ScopedLocalReader(self.root, max_list=3)
        result = reader.list_files()
        self.assertEqual(len(result["files"]), 3)
        self.assertTrue(result["truncated"])
        self.assertEqual([x["name"] for x in result["files"]],
                         sorted([x["name"] for x in result["files"]],
                                key=str.casefold))

    def test_invalid_limits_and_names(self):
        for kwargs in ({"max_bytes": 12}, {"max_bytes": True},
                       {"max_list": 0}, {"max_list": 101}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                ScopedLocalReader(self.root, **kwargs)
        for name in (42, None, "a" * 130 + ".txt", "x.txt\n"):
            with self.subTest(name=str(name)[:8]), self.assertRaises(AgentRejected):
                self.reader.read_text(name)

    def test_missing_file_fails_closed(self):
        with self.assertRaises(AgentRejected):
            self.reader.read_text("notfound.txt")

    def test_reader_has_no_mutating_tool_api(self):
        self.assertFalse(hasattr(self.reader, "write_text"))
        self.assertFalse(hasattr(self.reader, "delete"))
        self.assertFalse(hasattr(self.reader, "execute"))


if __name__ == "__main__":
    unittest.main()
