"""Read-only storage lifecycle inventory and conservative retention advice.

NO deletion, cleanup, decryption, or permission changes. Names and paths are
not included in reports; unknown files are excluded from snapshot totals.
Only direct regular files with the exact managed filename pattern are counted.
"""
import argparse
import json
import re
import stat
from pathlib import Path

_MANAGED = re.compile(r"checkpoint-[0-9a-f]{32}\.varyn\Z")
_MAX_SCAN = 10000


class CheckpointInventoryError(ValueError):
    """Unsafe or excessive checkpoint inventory."""


def _files(directory):
    root = Path(directory)
    if root.is_symlink() or not root.is_dir():
        raise CheckpointInventoryError("Expected an existing non-symlink directory")
    entries = []
    # A cap prevents an unbounded report scan and memory allocation.
    for count, child in enumerate(root.iterdir(), start=1):
        if count > _MAX_SCAN:
            raise CheckpointInventoryError("Directory has too many entries to audit")
        if not _MANAGED.fullmatch(child.name):
            continue
        if child.is_symlink():
            raise CheckpointInventoryError("Managed-name symlink encountered")
        info = child.stat(follow_symlinks=False)
        if not stat.S_ISREG(info.st_mode):
            raise CheckpointInventoryError("Managed checkpoint is not a regular file")
        entries.append((info.st_mtime_ns, child.name, info.st_size))
    return entries


def inventory_checkpoints(directory, *, keep_latest=10, max_bytes=100 * 1024 * 1024):
    """Return metadata-only inventory; never approve deletion automatically."""
    if type(keep_latest) is not int or not 2 <= keep_latest <= 10000:
        raise ValueError("keep_latest must be 2..10000")
    if type(max_bytes) is not int or not 1 <= max_bytes <= (1 << 40):
        raise ValueError("max_bytes must be a positive integer up to 1 TiB")
    entries = sorted(_files(directory), reverse=True)
    total = sum(entry[2] for entry in entries)
    # No deletion list or paths are returned: recovery verification under the
    # correct DPAPI account and portable backup custody are not established.
    return {
        "format": "varyn.checkpoint_inventory.v1",
        "checkpoint_count": len(entries),
        "total_ciphertext_bytes": total,
        "largest_checkpoint_bytes": max((item[2] for item in entries), default=0),
        "configured_keep_latest": keep_latest,
        "configured_budget_bytes": max_bytes,
        "over_budget": total > max_bytes,
        "over_count_target": len(entries) > keep_latest,
        "read_only": True,
        "automatic_delete_allowed": False,
        "eligible_for_unattended_pruning": False,
        "recovery_tested": False,
        "recommendation": (
            "Review storage and verify independent recovery before ANY manual deletion"
            if len(entries) > keep_latest or total > max_bytes
            else "No retention action suggested"
        ),
    }


def require_checkpoint_capacity(directory, *, max_checkpoints=100):
    """Refuse writes once count reaches cap; never remove prior snapshots."""
    if type(max_checkpoints) is not int or not 2 <= max_checkpoints <= 10000:
        raise ValueError("max_checkpoints must be 2..10000")
    if len(_files(directory)) >= max_checkpoints:
        raise CheckpointInventoryError(
            "Checkpoint count cap reached; no data was removed"
        )


def main():
    parser = argparse.ArgumentParser(description="Read-only VARYN checkpoint inventory")
    parser.add_argument("--directory", required=True)
    parser.add_argument("--keep-latest", type=int, default=10)
    parser.add_argument("--max-bytes", type=int, default=100 * 1024 * 1024)
    args = parser.parse_args()
    print(json.dumps(inventory_checkpoints(
        args.directory, keep_latest=args.keep_latest, max_bytes=args.max_bytes
    ), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
