"""Checkpoint 17B synthetic directory-handle and grant lifecycle regression tests.

POSIX root/leaf path swaps are performed only in disposable temporary folders.
Windows tests exercise grant lifetime; native handle containment remains unverified.
"""
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from varyn.agent_runtime import AgentRejected
from varyn.file_grants import ScopedFileGrants
from varyn.scoped_files import ScopedLocalReader


class ScopedHandleLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "allowed"
        self.root.mkdir()
        (self.root / "hello.txt").write_text("approved synthetic record", encoding="utf-8")

    def reader(self):
        reader = ScopedLocalReader(self.root)
        self.addCleanup(reader.close)
        return reader

    def test_reader_close_disables_future_reads_and_listing(self):
        reader = self.reader()
        reader.close()
        for operation in (lambda: reader.read_text("hello.txt"), reader.list_files):
            with self.assertRaises(AgentRejected):
                operation()

    def test_reader_close_is_idempotent(self):
        reader = self.reader()
        reader.close()
        reader.close()
        self.assertTrue(reader._closed)
        self.assertIsNone(reader._root_fd)

    def test_revoke_closes_reader_and_refuses_existing_grant(self):
        grants = ScopedFileGrants()
        grant = grants.grant(self.root, user_confirmed=True)
        reader = grants._grants[grant.grant_id]["reader"]
        grants.revoke(grant.grant_id)
        self.assertTrue(reader._closed)
        with self.assertRaises(AgentRejected):
            grants.read_text(grant.grant_id, "hello.txt")

    def test_revoke_all_closes_all_directory_descriptors(self):
        grants = ScopedFileGrants()
        a = grants.grant(self.root, user_confirmed=True)
        b = grants.grant(self.root, user_confirmed=True)
        readers = [grants._grants[g.grant_id]["reader"] for g in (a, b)]
        grants.revoke_all()
        self.assertTrue(all(reader._closed for reader in readers))
        self.assertEqual(grants.status()["active"], 0)

    def test_expiry_releases_reader(self):
        clock = [10.0]
        grants = ScopedFileGrants(clock=lambda: clock[0])
        grant = grants.grant(self.root, user_confirmed=True, duration_seconds=1)
        reader = grants._grants[grant.grant_id]["reader"]
        clock[0] += 2.0
        with self.assertRaises(PermissionError):
            grants.read_text(grant.grant_id, "hello.txt")
        self.assertTrue(reader._closed)

    def test_last_successful_operation_releases_reader(self):
        grants = ScopedFileGrants()
        grant = grants.grant(self.root, user_confirmed=True, max_operations=1)
        reader = grants._grants[grant.grant_id]["reader"]
        result = grants.read_text(grant.grant_id, "hello.txt")
        self.assertEqual(result["text"], "approved synthetic record")
        self.assertTrue(reader._closed)
        with self.assertRaises(PermissionError):
            grants.list_files(grant.grant_id)

    def test_last_failed_operation_also_releases_reader(self):
        grants = ScopedFileGrants()
        grant = grants.grant(self.root, user_confirmed=True, max_operations=1)
        reader = grants._grants[grant.grant_id]["reader"]
        with self.assertRaises(AgentRejected):
            grants.read_text(grant.grant_id, "../escape.txt")
        self.assertTrue(reader._closed)

    @unittest.skipUnless(os.name == "nt", "Windows-specific reparse metadata check")
    def test_windows_detects_ancestor_reparse_change_at_access(self):
        from types import SimpleNamespace

        reader = self.reader()
        watched = self.root.parent
        original_lstat = Path.lstat

        def modified_lstat(path, *args, **kwargs):
            info = original_lstat(path, *args, **kwargs)
            if path == watched:
                return SimpleNamespace(
                    st_mode=info.st_mode, st_dev=info.st_dev,
                    st_ino=info.st_ino, st_nlink=1,
                    st_file_attributes=0x400,
                )
            return info

        with patch("varyn.scoped_files.Path.lstat", new=modified_lstat):
            with self.assertRaises(AgentRejected):
                reader.list_files()
            with self.assertRaises(AgentRejected):
                reader.read_text("hello.txt")

    @unittest.skipIf(os.name == "nt", "POSIX descriptor relative opens only")
    def test_posix_dir_descriptor_is_pinned(self):
        reader = self.reader()
        self.assertIsInstance(reader._root_fd, int)
        self.assertEqual(reader.read_text("hello.txt")["text"], "approved synthetic record")

    @unittest.skipIf(os.name == "nt", "POSIX descriptor relative scandir only")
    def test_posix_scan_does_not_follow_swapped_directory_path(self):
        reader = self.reader()
        original_check = reader._check_root
        moved = self.root.with_name("moved")
        triggered = [False]

        def checked_then_swapped():
            original_check()
            if not triggered[0]:
                triggered[0] = True
                self.root.rename(moved)
                self.root.mkdir()
                (self.root / "outsider.txt").write_text("outside scope")

        with patch.object(reader, "_check_root", side_effect=checked_then_swapped):
            listing = reader.list_files()
        self.assertEqual({x["name"] for x in listing["files"]}, {"hello.txt"})
        self.assertNotIn("outsider.txt", repr(listing))

    @unittest.skipIf(os.name == "nt", "POSIX descriptor relative opens only")
    def test_posix_read_refuses_root_swap_between_checks(self):
        reader = self.reader()
        original_check = reader._check_root
        moved = self.root.with_name("moved")
        triggered = [False]

        def checked_then_swapped():
            original_check()
            if not triggered[0]:
                triggered[0] = True
                self.root.rename(moved)
                self.root.mkdir()
                (self.root / "hello.txt").write_text("outside scope")

        with patch.object(reader, "_check_root", side_effect=checked_then_swapped):
            with self.assertRaises(AgentRejected):
                reader.read_text("hello.txt")
        self.assertNotIn("outside scope", repr(reader._root_stat))

    @unittest.skipIf(os.name == "nt", "POSIX nofollow flags only")
    def test_posix_swap_file_to_symlink_during_open_is_refused(self):
        reader = self.reader()
        outside = Path(self.tmp.name) / "outside.txt"
        outside.write_text("unauthorized synthetic fixture")
        real_open = os.open
        triggered = [False]

        def replace_during_open(path, flags, *args, **kwargs):
            if path == "hello.txt" and "dir_fd" in kwargs and not triggered[0]:
                triggered[0] = True
                (self.root / "hello.txt").unlink()
                (self.root / "hello.txt").symlink_to(outside)
            return real_open(path, flags, *args, **kwargs)

        with patch("varyn.scoped_files.os.open", side_effect=replace_during_open):
            with self.assertRaises(AgentRejected):
                reader.read_text("hello.txt")
        self.assertTrue(triggered[0])

    @unittest.skipIf(os.name == "nt", "POSIX directory fd creation only")
    def test_posix_scope_creation_rejects_root_swap_during_open(self):
        real_open = os.open
        moved = self.root.with_name("moved")
        triggered = [False]

        def replace_during_open(path, flags, *args, **kwargs):
            if Path(path) == self.root and not triggered[0]:
                triggered[0] = True
                self.root.rename(moved)
                self.root.mkdir()
            return real_open(path, flags, *args, **kwargs)

        with patch("varyn.scoped_files.os.open", side_effect=replace_during_open):
            with self.assertRaises(ValueError):
                ScopedLocalReader(self.root)
        self.assertTrue(triggered[0])


if __name__ == "__main__":
    unittest.main()
