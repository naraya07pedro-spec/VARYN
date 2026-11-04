"""Portable encrypted recovery tests: synthetic data and passphrases only."""
import sqlite3
import tempfile
import unittest
from pathlib import Path
from varyn.recovery import (
    RecoveryError, decrypt_recovery_image, encrypt_recovery_image,
    read_recovery, write_recovery,
)

PASSWORD = "synthetic recovery phrase 2026 only"


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.folder = Path(self.tmp.name)
        db = sqlite3.connect(":memory:")
        db.execute("CREATE TABLE notes(content TEXT)")
        db.execute("INSERT INTO notes VALUES ('storage synthetic anchor')")
        db.commit()
        self.image = db.serialize()
        db.close()

    def tearDown(self):
        self.tmp.cleanup()

    def test_roundtrip_without_windows_account(self):
        cipher = encrypt_recovery_image(self.image, PASSWORD)
        self.assertNotIn(b"storage synthetic anchor", cipher)
        self.assertNotIn(b"SQLite format 3", cipher)
        self.assertEqual(decrypt_recovery_image(cipher, PASSWORD), self.image)

    def test_wrong_password_rejected(self):
        cipher = encrypt_recovery_image(self.image, PASSWORD)
        with self.assertRaises(RecoveryError):
            decrypt_recovery_image(cipher, "incorrect synthetic phrase 2026")

    def test_ciphertext_tampering_rejected(self):
        cipher = bytearray(encrypt_recovery_image(self.image, PASSWORD))
        cipher[-1] ^= 1
        with self.assertRaises(RecoveryError):
            decrypt_recovery_image(bytes(cipher), PASSWORD)

    def test_header_tampering_rejected(self):
        cipher = bytearray(encrypt_recovery_image(self.image, PASSWORD))
        cipher[10] ^= 1
        with self.assertRaises(RecoveryError):
            decrypt_recovery_image(bytes(cipher), PASSWORD)

    def test_randomized_encryption(self):
        self.assertNotEqual(
            encrypt_recovery_image(self.image, PASSWORD),
            encrypt_recovery_image(self.image, PASSWORD),
        )

    def test_file_roundtrip_never_writes_plaintext(self):
        path = self.folder / "portable.varyn-recovery"
        write_recovery(path, self.image, PASSWORD)
        self.assertEqual(read_recovery(path, PASSWORD), self.image)
        self.assertNotIn(b"storage synthetic anchor", path.read_bytes())
        self.assertEqual({p.name for p in self.folder.iterdir()}, {path.name})

    def test_existing_file_not_replaced(self):
        path = self.folder / "portable.varyn-recovery"
        path.write_bytes(b"original")
        with self.assertRaises(FileExistsError):
            write_recovery(path, self.image, PASSWORD)
        self.assertEqual(path.read_bytes(), b"original")

    def test_rejects_short_passphrase_and_non_sqlite(self):
        with self.assertRaises(ValueError):
            encrypt_recovery_image(self.image, "short")
        with self.assertRaises(ValueError):
            encrypt_recovery_image(b"not sqlite", PASSWORD)

    def test_rejects_oversized_and_truncated_input(self):
        with self.assertRaises(ValueError):
            encrypt_recovery_image(b"SQLite format 3\x00" + b"x" * 1048576, PASSWORD)
        with self.assertRaises(RecoveryError):
            decrypt_recovery_image(b"VARYN-RECOVERY-v1\x00", PASSWORD)

    def test_symlink_refused(self):
        path = self.folder / "portable.varyn-recovery"
        write_recovery(path, self.image, PASSWORD)
        link = self.folder / "alias.varyn-recovery"
        try:
            link.symlink_to(path)
        except (OSError, NotImplementedError):
            self.skipTest("Host does not support symlinks")
        with self.assertRaises(RecoveryError):
            read_recovery(link, PASSWORD)


if __name__ == "__main__":
    unittest.main()
