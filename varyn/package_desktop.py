"""Deterministic source-only desktop ZIP package, no binaries or runtime data.

Launch-VARYN.cmd requires a preinstalled supported Python with Tkinter.
Never package .env, SQLite, snapshots, secrets, __pycache__, or API keys.
"""
import argparse
import hashlib
import json
import os
import stat
import zipfile
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_ALLOWED_TOP = (
    "Launch-VARYN.cmd", "Verify-VARYN-Synthetic.cmd",
    "Record-VARYN-GUI-Checks.cmd", "README.md",
)
_FIXED_DATE = (2024, 1, 1, 0, 0, 0)


def archive_entries(root=_ROOT):
    root = Path(root)
    files = [root / name for name in _ALLOWED_TOP]
    files += sorted((root / "varyn").glob("*.py"))
    if not (root / "varyn" / "desktop.py").is_file():
        raise FileNotFoundError("VARYN desktop entrypoint is missing")
    result = []
    for path in files:
        if path.is_symlink() or not path.is_file():
            raise ValueError("Package input must be a regular non-symlink file")
        info = path.stat(follow_symlinks=False)
        if not stat.S_ISREG(info.st_mode) or info.st_size > 512 * 1024:
            raise ValueError("Package input failed file size or file type check")
        result.append(path)
    return tuple(result)


def build_zip(output, *, root=_ROOT):
    target = Path(output).absolute()
    if target.exists() or target.is_symlink():
        raise FileExistsError("Package destination already exists")
    if not target.parent.is_dir():
        raise FileNotFoundError("Destination directory does not exist")
    files = archive_entries(root)
    # Only code/docs. No installed Python interpreter and no dependencies.
    with zipfile.ZipFile(target, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            name = "VARYN/" + path.relative_to(root).as_posix()
            item = zipfile.ZipInfo(name, date_time=_FIXED_DATE)
            item.compress_type = zipfile.ZIP_DEFLATED
            item.external_attr = 0o644 << 16
            archive.writestr(item, path.read_bytes())
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    return {
        "format": "varyn.desktop_source_package.v1",
        "files": len(files),
        "archive_bytes": target.stat().st_size,
        "sha256": digest,
        "bundles_python_or_model": False,
        "installer": False,
        "api_calls": 0,
    }


def main():
    parser = argparse.ArgumentParser(description="Make a source-only desktop ZIP")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    print(json.dumps(build_zip(args.output), sort_keys=True))


if __name__ == "__main__":
    main()
