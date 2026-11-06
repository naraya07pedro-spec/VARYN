"""17S-29: reviewable file-hash manifest for optional Windows portable build.

No network or file collection outside the explicitly supplied DIST folder.
The manifest detects accidental changes after packaging; it is NOT a signed
release, trusted publisher attestation, Windows sandbox, antivirus check,
private-data security guarantee or proof of external app history sync.
"""
import argparse
import hashlib
import json
from pathlib import Path

_MANIFEST = "BUNDLE-SHA256.json"
_EXECUTABLE = "VARYN-Portable.exe"
_README = "README-PORTABLE.txt"
_LAUNCHER = "Start-VARYN-OwnerPilot.ps1"
_MAX_FILES = 6000
_MAX_TOTAL_BYTES = 700 * 1024 * 1024


class PortableBundleRejected(ValueError):
    pass


def _inventory(directory):
    root = Path(directory)
    if not root.is_dir() or root.is_symlink():
        raise PortableBundleRejected("Portable root must be a directory")
    if (not (root / _EXECUTABLE).is_file() or
            not (root / "_internal").is_dir() or
            not (root / _README).is_file() or
            not (root / _LAUNCHER).is_file()):
        raise PortableBundleRejected("Missing executable, runtime or safety notes")
    entries = {}
    total = 0
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise PortableBundleRejected("Symlinks are forbidden in portable ZIP")
        if path.is_dir():
            continue
        if not path.is_file():
            raise PortableBundleRejected("Unrecognized bundle entry")
        name = path.relative_to(root).as_posix()
        if name == _MANIFEST:
            continue
        if (name.startswith("../") or name.startswith("/") or
                "\\" in name or name.lower().endswith(
                    (".sqlite3", ".db", ".env", ".log", ".spec", ".7z")
                ) or (name.lower().endswith(".zip") and
                      name != "_internal/base_library.zip") or
                name in (".env", "credentials.json", "cookies.sqlite")):
            raise PortableBundleRejected("Disallowed runtime/user data in bundle")
        total += path.stat().st_size
        if len(entries) >= _MAX_FILES or total > _MAX_TOTAL_BYTES:
            raise PortableBundleRejected("Bundle file count/size bound exceeded")
        with path.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        entries[name] = digest
    if (_EXECUTABLE not in entries or _README not in entries or
            _LAUNCHER not in entries or not any(
                n.startswith("_internal/") for n in entries
            )):
        raise PortableBundleRejected("Incomplete portable directory")
    with (root / _EXECUTABLE).open("rb") as stream:
        if stream.read(2) != b"MZ":
            raise PortableBundleRejected("No Windows PE signature header")
    return entries, total


def create_manifest(directory):
    root = Path(directory)
    if (root / _MANIFEST).exists() or (root / _MANIFEST).is_symlink():
        raise PortableBundleRejected("Refuse to overwrite existing manifest")
    inventory, total = _inventory(root)
    manifest = {
        "format": "varyn.windows_portable_sha256.v1",
        "build_mode": "windows_amd64_onedir",
        "files": inventory,
        "file_count": len(inventory),
        "bundle_bytes_excluding_manifest": total,
        "main_executable_sha256": inventory[_EXECUTABLE],
        "owner_pilot_launcher_sha256": inventory[_LAUNCHER],
        "publisher_codesign_verified": False,
        "human_owner_acceptance_verified": False,
        "official_consumer_history_two_way_sync_verified": False,
        "production_private_file_access_enabled": False,
    }
    text = json.dumps(
        manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
    ) + "\n"
    (root / _MANIFEST).write_text(text, encoding="utf-8", newline="\n")
    return manifest


def verify_manifest(directory):
    root = Path(directory)
    path = root / _MANIFEST
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 600000:
        raise PortableBundleRejected("Missing or invalid bundle manifest")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeError, ValueError) as e:
        raise PortableBundleRejected("Invalid manifest encoding/JSON") from e
    if type(payload) is not dict or payload.get("format") != (
        "varyn.windows_portable_sha256.v1"
    ):
        raise PortableBundleRejected("Manifest format not recognized")
    expected, total = _inventory(root)
    if (payload.get("files") != expected or
            type(payload.get("file_count")) is not int or
            payload["file_count"] != len(expected) or
            type(payload.get("bundle_bytes_excluding_manifest")) is not int or
            payload["bundle_bytes_excluding_manifest"] != total or
            payload.get("main_executable_sha256") != expected[_EXECUTABLE] or
            payload.get("owner_pilot_launcher_sha256") != expected[_LAUNCHER] or
            payload.get("publisher_codesign_verified") is not False or
            payload.get("human_owner_acceptance_verified") is not False or
            payload.get("official_consumer_history_two_way_sync_verified") is not False or
            payload.get("production_private_file_access_enabled") is not False):
        raise PortableBundleRejected("Bundle file hash/claimed authority mismatch")
    return {
        "format": "varyn.windows_portable_manifest_check.v1",
        "files": len(expected),
        "bytes": total,
        "exe_sha256": expected[_EXECUTABLE],
        "verified_against_unsigned_manifest_only": True,
        "codesign_verified": False,
        "external_app_access_verified": False,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="Check Windows portable build")
    parser.add_argument("--directory", required=True)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--create", action="store_true")
    group.add_argument("--verify", action="store_true")
    args = parser.parse_args(argv)
    if args.create:
        report = create_manifest(args.directory)
    else:
        report = verify_manifest(args.directory)
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
