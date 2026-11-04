"""Windows-native DPAPI tests, plus fail-closed checks on other OSes."""
import os
import tempfile
import unittest
from pathlib import Path

from varyn.dpapi_vault import (
    UnsupportedPlatformError, SealedDataError, seal_bytes,
    unseal_bytes, write_sealed, read_sealed,
)


class EnvelopeTests(unittest.TestCase):
    def test_rejects_invalid_input_before_native_call(self):
        for invalid in (b"", b"x" * (1024 * 1024 + 1), "not bytes"):
            with self.subTest(kind=str(type(invalid))):
                with self.assertRaises(ValueError):
                    seal_bytes(invalid)

    def test_unseal_rejects_plaintext(self):
        with self.assertRaises(SealedDataError):
            unseal_bytes(b"plain text")

    @unittest.skipIf(os.name == "nt", "Non-Windows rejection only")
    def test_non_windows_fails_closed(self):
        with self.assertRaises(UnsupportedPlatformError):
            seal_bytes(b"synthetic demo only")


@unittest.skipUnless(os.name == "nt", "Windows DPAPI needs a Windows user profile")
class WindowsDpapiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.target = Path(self.temp.name) / "synthetic.sealed"

    def tearDown(self):
        self.temp.cleanup()

    def test_native_roundtrip_and_envelope_hides_plaintext(self):
        plain = b"private synthetic verification record 2026"
        ciphertext = seal_bytes(plain)
        self.assertNotIn(plain, ciphertext)
        self.assertNotEqual(plain, ciphertext)
        self.assertEqual(unseal_bytes(ciphertext), plain)

    def test_tampering_is_rejected(self):
        ciphertext = bytearray(seal_bytes(b"synthetic check"))
        ciphertext[-1] ^= 0x01
        with self.assertRaises(SealedDataError):
            unseal_bytes(bytes(ciphertext))

    def test_file_roundtrip_never_writes_plaintext(self):
        plain = b"synthetic note is not secret"
        write_sealed(self.target, plain)
        self.assertNotIn(plain, self.target.read_bytes())
        self.assertEqual(read_sealed(self.target), plain)

    def test_never_overwrites_existing_target(self):
        self.target.write_bytes(b"must keep")
        with self.assertRaises(FileExistsError):
            write_sealed(self.target, b"replacement")
        self.assertEqual(self.target.read_bytes(), b"must keep")

    def test_symlink_input_is_refused(self):
        write_sealed(self.target, b"synthetic")
        link = self.target.with_name("shortcut.sealed")
        try:
            link.symlink_to(self.target)
        except (OSError, NotImplementedError):
            self.skipTest("Host does not allow creating symlinks")
        with self.assertRaises(SealedDataError):
            read_sealed(link)


if __name__ == "__main__":
    unittest.main()
