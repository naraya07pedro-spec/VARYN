"""17S-31 | Consent-only, metadata-only offline ZIP inventory for official exports.

A user explicitly selects ONE local ZIP through the GUI. This module reads
the ZIP envelope and central-directory metadata ONLY: no member .open(),
.read(), extraction, JSON parsing, conversation content, network, or disk
writes. Output never includes path, member names, chat titles or identifiers.

Bounded preflight deliberately supports only ordinary ZIP32, <=128 MiB
compressed, <=2 MiB central directory, <=5000 entries. Large, ZIP64 or
unusual exports are NOT inspected; user should use official provider tools.
This is an inventory HINT, not verification of export origin, content
integrity, ZIP member safety, or Gemini import compatibility.
"""
from pathlib import Path
import os
import re
import stat
import struct
import zipfile

_MAX_ARCHIVE_BYTES = 128 * 1024 * 1024
_MAX_DIRECTORY_BYTES = 2 * 1024 * 1024
_MAX_ENTRIES = 5000
_MAX_DECLARED_BYTES = 5 * 1024 * 1024 * 1024
_MAX_RATIO = 1000
_EOCD = b"PK\x05\x06"
_MAX_TAIL = 65535 + 22


class ExportInventoryRejected(ValueError):
    """A selected export cannot be safely inventoried under these bounds."""


def _zip32_preflight(handle, length):
    """Reject huge/ZIP64/ambiguous central directories BEFORE zipfile loads."""
    if length < 22 or length > _MAX_ARCHIVE_BYTES:
        raise ExportInventoryRejected(
            "Archive exceeds 128 MiB pilot bound or is not a ZIP"
        )
    handle.seek(max(0, length - _MAX_TAIL))
    tail = handle.read(min(length, _MAX_TAIL))
    idx = tail.rfind(_EOCD)
    if idx < 0 or len(tail) - idx < 22:
        raise ExportInventoryRejected("Standard ZIP directory footer missing")
    _, disk, cd_disk, this_disk, total, cd_size, cd_start, comment = (
        struct.unpack_from("<IHHHHIIH", tail, idx)
    )
    footer_offset = length - len(tail) + idx
    if (disk != 0 or cd_disk != 0 or this_disk != total or
            total == 0 or total > _MAX_ENTRIES or
            total == 0xFFFF or cd_start == 0xFFFFFFFF or
            cd_size == 0xFFFFFFFF or cd_size > _MAX_DIRECTORY_BYTES or
            footer_offset + 22 + comment != length or
            cd_start + cd_size != footer_offset):
        raise ExportInventoryRejected(
            "ZIP64, multi-volume, suspicious or oversized directory unsupported"
        )
    return total


def inspect_export_zip_metadata(path, source):
    """Read only ZIP32 central-directory metadata after explicit GUI approval.

    Does not return or persist the path, any member name, title or content.
    """
    if type(path) is not str or not path or "\x00" in path:
        raise ExportInventoryRejected("Select one ordinary ZIP file")
    if type(source) is not str or source not in ("chatgpt", "claude"):
        raise ExportInventoryRejected("Unsupported declared export source")
    local = Path(path)
    if local.suffix.lower() != ".zip" or local.is_symlink():
        raise ExportInventoryRejected("Only a directly selected ZIP is accepted")
    try:
        with local.open("rb") as stream:
            st = os.fstat(stream.fileno())
            if not stat.S_ISREG(st.st_mode):
                raise ExportInventoryRejected("Only a regular local file is accepted")
            expected = _zip32_preflight(stream, st.st_size)
            stream.seek(0)
            with zipfile.ZipFile(stream, mode="r", allowZip64=False) as archive:
                infos = archive.infolist()
                if len(infos) != expected:
                    raise ExportInventoryRejected("ZIP entry count mismatch")
                seen = set()
                declared = 0
                recognized = 0
                for info in infos:
                    name = info.filename
                    # Member names are read transiently to classify the
                    # envelope; NEVER emitted in reports or error text.
                    if (not name or name.startswith("/") or
                            "\\" in name or ":" in name or
                            any(part in ("", ".", "..")
                                for part in name.rstrip("/").split("/")) or
                            len(name) > 256 or name in seen or
                            stat.S_ISLNK((info.external_attr >> 16) & 0xFFFF) or
                            info.flag_bits & 0x1 or
                            info.file_size < 0 or info.compress_size < 0 or
                            info.file_size > _MAX_DECLARED_BYTES):
                        raise ExportInventoryRejected(
                            "Unsafe/ambiguous ZIP member metadata"
                        )
                    seen.add(name)
                    declared += info.file_size
                    if declared > _MAX_DECLARED_BYTES:
                        raise ExportInventoryRejected(
                            "Declared uncompressed total exceeds 5 GiB pilot bound"
                        )
                    if (info.file_size and
                            info.file_size > max(info.compress_size, 1) * _MAX_RATIO):
                        raise ExportInventoryRejected(
                            "Extreme compression ratio; not inspected"
                        )
                    if (not info.is_dir() and
                            re.fullmatch(
                                r"conversations(?:[-_]\d+)?\.json",
                                name.rsplit("/", 1)[-1],
                                flags=re.IGNORECASE,
                            )):
                        recognized += 1
            # Verify selected file's current length didn't change while
            # reading metadata. No claim of cryptographic stability.
            if os.fstat(stream.fileno()).st_size != st.st_size:
                raise ExportInventoryRejected("Selected ZIP changed during inventory")
    except ExportInventoryRejected:
        raise
    except (OSError, zipfile.BadZipFile, zipfile.LargeZipFile,
            struct.error, EOFError, ValueError) as exc:
        raise ExportInventoryRejected(
            "ZIP envelope could not be safely inventoried; no member extracted"
        ) from exc
    return {
        "format": "varyn.local_export_metadata_inventory.v1",
        "declared_source_not_authenticated": source,
        "archive_bytes": st.st_size,
        "zip_entry_count": len(infos),
        "declared_uncompressed_bytes_not_verified": declared,
        "chatgpt_named_conversation_json_hints": recognized if source == "chatgpt" else 0,
        "recognized_source_structure": (
            "chatgpt_filename_hint_only" if source == "chatgpt" and recognized
            else "zip_envelope_only"
        ),
        "archive_member_payloads_read": False,
        "json_conversation_contents_parsed": False,
        "member_names_or_paths_reported": False,
        "zip_extracted": False,
        "provider_origin_authenticated": False,
        "full_zip_integrity_verified": False,
        "gemini_acceptance_verified": False,
        "user_history_persisted": False,
        "automatic_bidirectional_sync_verified": False,
        "network_calls": 0,
        "disk_writes": 0,
    }
