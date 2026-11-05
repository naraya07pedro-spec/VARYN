"""17S-37: completed local three-AI archive contract and Windows encryption."""
import hashlib
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from varyn.guided_reply_ledger import GuidedReplyLedger
from varyn.three_app_archive import (
    ArchiveRejected, snapshot, validate, encode, digest, save_new,
    load_readonly, display,
)
from varyn.dpapi_vault import SealedDataError, UnsupportedPlatformError


def fixture():
    ledger = GuidedReplyLedger()
    for i, provider in enumerate(("chatgpt", "claude", "gemini"), 1):
        text = "SYNTHETIC: imaginary " + provider
        request = format(i, "032x")
        outbound = format(i, "064x")
        reply_hash = hashlib.sha256(
            (request + "\n" + outbound + "\n" + text).encode()
        ).hexdigest()
        ledger.record(i, provider, text, {
            "provider_claim": provider, "manual_only": True,
            "provider_origin_verified": False,
            "outbound_request_id": request, "outbound_digest": outbound,
            "reply_digest": reply_hash,
            "local_chain_digest": format(i, "064x"),
        })
    return ledger


class ArchiveContractTests(unittest.TestCase):
    def test_complete_exact_readonly_and_false_provider_claims(self):
        value = snapshot(fixture(), phase="completed")
        self.assertEqual(value, validate(value))
        self.assertEqual(len(digest(value)), 64)
        self.assertEqual(len(value["records"]), 3)
        self.assertIn("imaginary chatgpt", display(value))
        for name in ("provider_origins_verified", "consumer_history_authenticated",
                     "automatic_sync", "relay_authority_restored"):
            self.assertIs(value[name], False)
        self.assertTrue(value["read_only"])

    def test_partial_or_unsafe_fields_refused(self):
        original = snapshot(fixture(), phase="completed")
        for phase in ("idle", "awaiting_reply", "ready", "ready_next"):
            with self.subTest(phase=phase), self.assertRaises(ArchiveRejected):
                snapshot(fixture(), phase=phase)
        for changed in (
            {"automatic_sync": True}, {"relay_authority_restored": True},
            {"consumer_history_authenticated": True}, {"read_only": False},
            {"invented_field": "new"},
        ):
            with self.subTest(changed=changed), self.assertRaises(ArchiveRejected):
                validate(dict(original, **changed))
        for records in (
            original["records"][:2],
            list(reversed(original["records"])),
            [dict(original["records"][0], reply_text="SYNTHETIC: altered"),
             *original["records"][1:]],
        ):
            with self.assertRaises(ArchiveRejected):
                validate(dict(original, records=records))
        with self.assertRaises(ArchiveRejected):
            snapshot(GuidedReplyLedger(), phase="completed")

    def test_encrypt_before_new_file_and_reject_plaintext_json(self):
        obj = snapshot(fixture(), phase="completed")
        with patch("varyn.three_app_archive.write_sealed") as writer:
            save_new("complete.varyn-archive", obj)
            writer.assert_called_once_with(
                Path("complete.varyn-archive"), encode(obj)
            )
        with patch("varyn.three_app_archive.write_sealed") as writer:
            with self.assertRaises(ArchiveRejected):
                save_new("archive.json", obj)
            writer.assert_not_called()
        with patch("varyn.three_app_archive.read_sealed", return_value=b"{}"):
            with self.assertRaises(ArchiveRejected):
                load_readonly("fixture.varyn-archive")
        with patch("varyn.three_app_archive.read_sealed",
                   return_value=b"not json"):
            with self.assertRaises(ArchiveRejected):
                load_readonly("fixture.varyn-archive")


@unittest.skipUnless(os.name == "nt", "actual Windows user DPAPI only")
class WindowsNativeArchiveTests(unittest.TestCase):
    def test_encrypted_disk_roundtrip_no_overwrite_and_tamper(self):
        obj = snapshot(fixture(), phase="completed")
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "archive.varyn-archive"
            save_new(target, obj)
            ciphertext = target.read_bytes()
            self.assertNotIn(b"SYNTHETIC: imaginary", ciphertext)
            self.assertEqual(load_readonly(target), obj)
            with self.assertRaises(FileExistsError):
                save_new(target, obj)
            self.assertEqual(target.read_bytes(), ciphertext)
            damaged = bytearray(ciphertext)
            damaged[-1] ^= 1
            target.write_bytes(damaged)
            with self.assertRaises(SealedDataError):
                load_readonly(target)


@unittest.skipIf(os.name == "nt", "non-Windows DPAPI only")
class UnsupportedPlatformTests(unittest.TestCase):
    def test_archive_cannot_be_written_unencrypted(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "archive.varyn-archive"
            with self.assertRaises(UnsupportedPlatformError):
                save_new(target, snapshot(fixture(), phase="completed"))
            self.assertFalse(target.exists())


if __name__ == "__main__":
    unittest.main()
