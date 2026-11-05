"""17S-31: real ZIP32 envelope fixtures, no archived content or user path leaks."""
import json
from pathlib import Path
import stat
import struct
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from varyn.native_export_inventory import (
    ExportInventoryRejected, inspect_export_zip_metadata,
)


class MetadataOnlyExportZipTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.path = Path(self.dir.name) / "synthetic-export.zip"

    def tearDown(self):
        self.dir.cleanup()

    def _zip(self, *, members=None, compression=zipfile.ZIP_STORED):
        if members is None:
            members = {
                "conversations.json": b"PRIVATE_MESSAGE_MUST_NOT_BE_EXPOSED",
                "account.json": b"SECRET_USER_EMAIL_NOT_FOR_OUTPUT",
                "assets/image.png": b"12345",
            }
        with zipfile.ZipFile(
            self.path, mode="w", compression=compression,
        ) as archive:
            for name, value in members.items():
                archive.writestr(name, value)
        return self.path

    def test_chatgpt_metadata_only_never_reads_member_payloads(self):
        self._zip()
        before = self.path.read_bytes()
        with patch.object(
            zipfile.ZipFile, "open",
            side_effect=AssertionError("Member payload access forbidden"),
        ), patch.object(
            zipfile.ZipFile, "read",
            side_effect=AssertionError("Member data access forbidden"),
        ), patch.object(
            zipfile.ZipFile, "extractall",
            side_effect=AssertionError("ZIP extraction forbidden"),
        ):
            result = inspect_export_zip_metadata(str(self.path), "chatgpt")
        self.assertEqual(result["zip_entry_count"], 3)
        self.assertEqual(result["chatgpt_named_conversation_json_hints"], 1)
        self.assertEqual(result["recognized_source_structure"],
                         "chatgpt_filename_hint_only")
        self.assertFalse(result["archive_member_payloads_read"])
        self.assertFalse(result["json_conversation_contents_parsed"])
        self.assertFalse(result["provider_origin_authenticated"])
        self.assertFalse(result["full_zip_integrity_verified"])
        self.assertFalse(result["gemini_acceptance_verified"])
        self.assertFalse(result["automatic_bidirectional_sync_verified"])
        self.assertEqual(result["disk_writes"], 0)
        self.assertEqual(before, self.path.read_bytes())
        printed = json.dumps(result)
        for forbidden in (
            "PRIVATE_MESSAGE_MUST_NOT_BE_EXPOSED",
            "SECRET_USER_EMAIL_NOT_FOR_OUTPUT",
            "account.json", "image.png", "conversations.json",
            str(self.path), self.dir.name,
        ):
            self.assertNotIn(forbidden, printed)

    def test_claude_does_not_pretend_to_understand_its_export_schema(self):
        self._zip(members={"conversations.json": b"dummy"})
        result = inspect_export_zip_metadata(str(self.path), "claude")
        self.assertEqual(result["recognized_source_structure"],
                         "zip_envelope_only")
        self.assertEqual(result["chatgpt_named_conversation_json_hints"], 0)
        self.assertEqual(result["declared_source_not_authenticated"], "claude")

    def test_chatgpt_multiple_numbered_json_hints_without_reading(self):
        self._zip(members={
            "conversations.json": b"opaque",
            "conversations_0.json": b"opaque",
            "data/conversations-02.json": b"opaque",
            "conversations-my-secret.json": b"unrelated",
        })
        result = inspect_export_zip_metadata(str(self.path), "chatgpt")
        self.assertEqual(result["chatgpt_named_conversation_json_hints"], 3)

    def test_bad_source_path_type_or_suffix_fails_closed(self):
        self._zip()
        for source in ("gemini", "ChatGPT", "", 4, None):
            with self.subTest(source=source), self.assertRaises(
                    ExportInventoryRejected):
                inspect_export_zip_metadata(str(self.path), source)
        for path in (None, 3, "", str(self.path) + "\x00"):
            with self.subTest(path=repr(path)), self.assertRaises(
                    ExportInventoryRejected):
                inspect_export_zip_metadata(path, "chatgpt")
        renamed = self.path.with_suffix(".txt")
        self.path.rename(renamed)
        with self.assertRaises(ExportInventoryRejected):
            inspect_export_zip_metadata(str(renamed), "chatgpt")

    def test_invalid_not_zip_and_zip64_style_footer_refused(self):
        self.path.write_bytes(b"not a ZIP at all")
        with self.assertRaises(ExportInventoryRejected):
            inspect_export_zip_metadata(str(self.path), "chatgpt")
        self._zip()
        buf = bytearray(self.path.read_bytes())
        index = buf.rfind(b"PK\x05\x06")
        self.assertGreaterEqual(index, 0)
        struct.pack_into("<H", buf, index + 10, 0xFFFF)
        self.path.write_bytes(buf)
        with self.assertRaises(ExportInventoryRejected):
            inspect_export_zip_metadata(str(self.path), "chatgpt")

    def test_unsafe_member_paths_duplicate_names_and_symlink_refused(self):
        for name in ("../escape.txt", "folder/../outside.txt",
                     "/absolute.txt", "C:private.txt",
                     "folder/./file.txt"):
            with self.subTest(name=name):
                self._zip(members={name: b"data"})
                with self.assertRaises(ExportInventoryRejected):
                    inspect_export_zip_metadata(str(self.path), "chatgpt")
        # zipfile's writer converts '\\' to '/' on Windows. Change the
        # RAW central-directory bytes so the test covers what an untrusted
        # ZIP actually contains on both operating systems.
        self._zip(members={"dir/outside.txt": b"payload"})
        raw = bytearray(self.path.read_bytes())
        central = raw.find(b"PK\\x01\\x02")
        self.assertGreaterEqual(central, 0)
        raw_name_at = central + 46
        self.assertEqual(raw[raw_name_at:raw_name_at + 15],
                         b"dir/outside.txt")
        raw[raw_name_at + 3] = ord("\\")
        self.path.write_bytes(raw)
        with self.assertRaises(ExportInventoryRejected):
            inspect_export_zip_metadata(str(self.path), "chatgpt")
        with zipfile.ZipFile(self.path, "w") as z:
            z.writestr("same.txt", b"one")
            z.writestr("same.txt", b"two")
        with self.assertRaises(ExportInventoryRejected):
            inspect_export_zip_metadata(str(self.path), "chatgpt")
        link = zipfile.ZipInfo("link")
        link.create_system = 3
        link.external_attr = (stat.S_IFLNK | 0o777) << 16
        with zipfile.ZipFile(self.path, "w") as z:
            z.writestr(link, b"target")
        with self.assertRaises(ExportInventoryRejected):
            inspect_export_zip_metadata(str(self.path), "chatgpt")

    def test_zip_bomb_like_ratio_and_encryption_flags_refused(self):
        self._zip(members={"huge.txt": b"A" * 2_000_000},
                  compression=zipfile.ZIP_DEFLATED)
        with self.assertRaises(ExportInventoryRejected):
            inspect_export_zip_metadata(str(self.path), "chatgpt")
        self._zip(members={"safe.txt": b"data"})
        buf = bytearray(self.path.read_bytes())
        cd = buf.find(b"PK\x01\x02")
        self.assertGreaterEqual(cd, 0)
        # Encrypted flag in central directory general purpose bit flags.
        struct.pack_into("<H", buf, cd + 8, 1)
        self.path.write_bytes(buf)
        with self.assertRaises(ExportInventoryRejected):
            inspect_export_zip_metadata(str(self.path), "chatgpt")

    def test_large_file_or_large_directory_refused_before_zipfile_loads(self):
        with self.path.open("wb") as stream:
            stream.seek(128 * 1024 * 1024)
            stream.write(b"0")
        with patch.object(
            zipfile, "ZipFile",
            side_effect=AssertionError("Oversize ZIP must not be opened"),
        ):
            with self.assertRaises(ExportInventoryRejected):
                inspect_export_zip_metadata(str(self.path), "chatgpt")
        self._zip()
        buf = bytearray(self.path.read_bytes())
        idx = buf.rfind(b"PK\x05\x06")
        struct.pack_into("<I", buf, idx + 12, 3 * 1024 * 1024)
        self.path.write_bytes(buf)
        with self.assertRaises(ExportInventoryRejected):
            inspect_export_zip_metadata(str(self.path), "chatgpt")

    def test_zip_central_directory_only_missing_payload_is_not_integrity_proof(self):
        self._zip(members={"conversations.json": b"AAAA"})
        data = bytearray(self.path.read_bytes())
        # Change local member body while leaving central directory unchanged.
        offset = data.index(b"AAAA")
        data[offset:offset + 4] = b"BBBB"
        self.path.write_bytes(data)
        result = inspect_export_zip_metadata(str(self.path), "chatgpt")
        self.assertEqual(result["chatgpt_named_conversation_json_hints"], 1)
        self.assertFalse(result["full_zip_integrity_verified"])
        self.assertFalse(result["provider_origin_authenticated"])


if __name__ == "__main__":
    unittest.main()
