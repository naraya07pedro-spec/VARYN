"""17S-33 encrypted synthetic workbench draft: strict schema and Windows DPAPI."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from varyn.official_draft_resume import (
    SyntheticDraftRejected, make_draft, validate_draft, encode_draft,
    digest, save_new, load_existing,
)
from varyn.dpapi_vault import UnsupportedPlatformError, SealedDataError

def sample():
    return make_draft(
        target="chatgpt", project="VARYN", topic="next_step",
        task="SYNTHETIC: Continue a fictional three-step plan.",
        note="SYNTHETIC: Step two is fictional review.",
    )


class DraftSchemaContractTests(unittest.TestCase):
    def test_fixed_format_and_no_authority(self):
        draft = sample()
        self.assertEqual(draft["manual_only"], True)
        for key in ("provider_history_authenticated",
                    "automatic_bidirectional_sync", "pasted_reply_persisted"):
            self.assertIs(draft[key], False)
        self.assertEqual(validate_draft(draft), draft)
        self.assertEqual(len(digest(draft)), 64)

    def test_mutations_and_secret_like_content_fail_closed(self):
        for change in (
            {"automatic_bidirectional_sync": True},
            {"pasted_reply_persisted": True},
            {"manual_only": False},
            {"target": "custom"},
            {"task": "a real private task"},
            {"note": "unlabeled"},
            {"task": "SYNTHETIC: password=verysecretvalue1234"},
            {"topic": ".."},
            {"extra": "unexpected"},
        ):
            mutated = sample()
            mutated.update(change)
            with self.subTest(change=change), self.assertRaises(SyntheticDraftRejected):
                validate_draft(mutated)
        with self.assertRaises(SyntheticDraftRejected):
            validate_draft({"format": "other"})

    def test_tampered_payload_cannot_become_authority(self):
        import json
        value = sample()
        value["provider_history_authenticated"] = True
        with patch("varyn.official_draft_resume.read_sealed",
                   return_value=json.dumps(value).encode()):
            with self.assertRaises(SyntheticDraftRejected):
                load_existing("fixture.varyn")
        with patch("varyn.official_draft_resume.read_sealed",
                   return_value=b"not json"):
            with self.assertRaises(SyntheticDraftRejected):
                load_existing("fixture.varyn")

    def test_calls_existing_encrypted_store_not_plaintext_write(self):
        target = Path("test-draft.varyn")
        with patch("varyn.official_draft_resume.write_sealed",
                   return_value=target) as writer:
            self.assertEqual(save_new(target, sample()), target)
        writer.assert_called_once_with(target, encode_draft(sample()))

    def test_non_varyn_extension_refused_before_file_access(self):
        with patch("varyn.official_draft_resume.write_sealed") as writer:
            with self.assertRaises(SyntheticDraftRejected):
                save_new("draft.json", sample())
            writer.assert_not_called()
        with patch("varyn.official_draft_resume.read_sealed") as reader:
            with self.assertRaises(SyntheticDraftRejected):
                load_existing("draft.json")
            reader.assert_not_called()


@unittest.skipUnless(os.name == "nt", "Native Windows user DPAPI only")
class NativeWindowsDraftTests(unittest.TestCase):
    def test_encrypted_roundtrip_tamper_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "draft.varyn"
            first = sample()
            save_new(path, first)
            ciphertext = path.read_bytes()
            self.assertNotIn(b"SYNTHETIC:", ciphertext)
            self.assertNotIn(b"VARYN", ciphertext)
            self.assertEqual(load_existing(path), first)
            with self.assertRaises(FileExistsError):
                save_new(path, first)
            self.assertEqual(path.read_bytes(), ciphertext)
            damaged = bytearray(ciphertext)
            damaged[-1] ^= 1
            path.write_bytes(damaged)
            with self.assertRaises(SealedDataError):
                load_existing(path)


@unittest.skipIf(os.name == "nt", "Non-Windows platform only")
class UnsupportedPlatformTests(unittest.TestCase):
    def test_non_windows_cannot_save_new_encrypted_draft(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "draft.varyn"
            with self.assertRaises(UnsupportedPlatformError):
                save_new(path, sample())
            self.assertFalse(path.exists())


if __name__ == "__main__":
    unittest.main()
