"""Portable password-encrypted recovery images for synthetic VARYN data.

Uses vetted cryptography primitives scrypt and AES-256-GCM. Recovery is
independent of the Windows DPAPI account, but password loss is unrecoverable.
Never writes plaintext image to a disk temporary file.
"""
import os
import tempfile
from pathlib import Path
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

_MAGIC = b"VARYN-RECOVERY-v1\x00"
_SALT_LENGTH = 16
_NONCE_LENGTH = 12
_TAG_LENGTH = 16
_MAX_IMAGE = 1024 * 1024
_MAX_FILE = len(_MAGIC) + _SALT_LENGTH + _NONCE_LENGTH + _MAX_IMAGE + _TAG_LENGTH


class RecoveryError(ValueError):
    """Generic recovery failure without disclosing secret material."""


def _derive(password, salt):
    if not isinstance(password, str) or not 16 <= len(password) <= 1024:
        raise ValueError("Recovery passphrase must contain 16-1024 characters")
    # 2**15 * 8 * 128 ~= 32 MiB KDF working memory, not process RSS.
    return Scrypt(salt=salt, length=32, n=1 << 15, r=8, p=1).derive(
        password.encode("utf-8")
    )


def encrypt_recovery_image(image, password):
    if not isinstance(image, bytes) or not 1 <= len(image) <= _MAX_IMAGE:
        raise ValueError("Recovery image must be nonempty bytes, at most 1 MiB")
    if not image.startswith(b"SQLite format 3\x00"):
        raise ValueError("Recovery export requires a SQLite image")
    salt = os.urandom(_SALT_LENGTH)
    nonce = os.urandom(_NONCE_LENGTH)
    key = _derive(password, salt)
    header = _MAGIC + salt + nonce
    return header + AESGCM(key).encrypt(nonce, image, header)


def decrypt_recovery_image(blob, password):
    if not isinstance(blob, bytes) or not (
        len(_MAGIC) + _SALT_LENGTH + _NONCE_LENGTH + _TAG_LENGTH + 1
        <= len(blob) <= _MAX_FILE
    ) or not blob.startswith(_MAGIC):
        raise RecoveryError("Invalid recovery envelope")
    offset = len(_MAGIC)
    salt = blob[offset:offset + _SALT_LENGTH]
    nonce = blob[offset + _SALT_LENGTH:offset + _SALT_LENGTH + _NONCE_LENGTH]
    header_end = offset + _SALT_LENGTH + _NONCE_LENGTH
    try:
        image = AESGCM(_derive(password, salt)).decrypt(
            nonce, blob[header_end:], blob[:header_end]
        )
    except (InvalidTag, ValueError):
        raise RecoveryError("Recovery authentication failed") from None
    if not image.startswith(b"SQLite format 3\x00"):
        raise RecoveryError("Invalid decrypted SQLite image")
    return image


def write_recovery(path, image, password):
    """Create fresh encrypted export without overwriting existing snapshots."""
    encrypted = encrypt_recovery_image(image, password)
    target = Path(path).absolute()
    if not target.parent.is_dir():
        raise FileNotFoundError("Recovery destination folder missing")
    if target.exists() or target.is_symlink():
        raise FileExistsError("Recovery destination already exists")
    fd, temporary = tempfile.mkstemp(prefix=".varyn-recovery-", dir=target.parent)
    try:
        with os.fdopen(fd, "wb") as output:
            output.write(encrypted)
            output.flush()
            os.fsync(output.fileno())
        os.link(temporary, target)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return target


def read_recovery(path, password):
    source = Path(path)
    if source.is_symlink() or not source.is_file():
        raise RecoveryError("Invalid recovery file")
    if source.stat().st_size > _MAX_FILE:
        raise RecoveryError("Recovery envelope exceeds size limit")
    return decrypt_recovery_image(source.read_bytes(), password)
