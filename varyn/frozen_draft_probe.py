"""17S-34: process-restart acceptance for ACTUAL frozen Windows portable EXE.

CI launches the same bundled EXE in distinct processes. The only payload is a
literal, harmless synthetic task/note; files are confined to a fresh temporary
directory and removed by the orchestrator. This is NOT owner-PC acceptance,
consumer-app login/sync, native history authority, or production backup.
"""
import argparse
import os
from pathlib import Path
import re
import subprocess
import tempfile

from varyn.official_draft_resume import make_draft, save_new, load_existing
from varyn.owner_pilot_launcher import sanitized_child_environment

_NAME = "synthetic-draft.varyn"
_DIR_RE = re.compile(r"\Avaryn-probe-[A-Za-z0-9_-]{8,40}\Z")
_PHASES = frozenset(("write", "read"))
_FIXED = make_draft(
    target="claude",
    project="VARYN",
    topic="fictional_plan",
    task="SYNTHETIC: Make a two-step plan for a fictional book club.",
    note="SYNTHETIC: The book club and tasks are invented test fixtures.",
)


class FrozenProbeRejected(ValueError):
    """Restricted test-only phase failed closed; never echo user content."""


def probe_directory(directory):
    """Allow one direct child of the current OS temporary directory only."""
    if type(directory) is not str:
        raise FrozenProbeRejected("Invalid probe directory")
    candidate = Path(directory)
    if (not _DIR_RE.fullmatch(candidate.name) or
            candidate.is_symlink() or not candidate.is_dir()):
        raise FrozenProbeRejected("Test-only temporary directory missing")
    temp_root = Path(tempfile.gettempdir()).resolve()
    if candidate.resolve() != temp_root / candidate.name:
        raise FrozenProbeRejected("Probe must be immediately inside OS temp")
    if candidate.resolve().parent != temp_root:
        raise FrozenProbeRejected("Probe directory escaped OS temp")
    return candidate


def run_probe_phase(phase, directory):
    """A single EXE process performs one fixed synthetic DPAPI action."""
    if os.name != "nt":
        raise FrozenProbeRejected("Windows-only DPAPI restart probe")
    if type(phase) is not str or phase not in _PHASES:
        raise FrozenProbeRejected("Unsupported test phase")
    root = probe_directory(directory)
    path = root / _NAME
    if path.is_symlink():
        raise FrozenProbeRejected("Symlink synthetic fixture refused")
    if phase == "write":
        save_new(path, _FIXED)
    else:
        if load_existing(path) != _FIXED:
            raise FrozenProbeRejected("Restored synthetic draft mismatch")
    return 0


def _child(exe, phase, root):
    """Never contact a provider; no command shell or real file path exposure."""
    try:
        child = subprocess.run(
            [str(exe), "--synthetic-draft-smoke", phase,
             "--smoke-directory", str(root)],
            env=sanitized_child_environment(dict(os.environ)),
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, timeout=40, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise FrozenProbeRejected("Frozen executable failed to exit") from error
    return child.returncode


def frozen_restart_acceptance(executable):
    """Run 4 launches, including no-overwrite and corruption refusal."""
    if os.name != "nt":
        raise FrozenProbeRejected("Frozen resume acceptance requires Windows")
    exe = Path(executable).resolve()
    if not exe.is_file() or exe.name.lower() != "varyn-portable.exe":
        raise FrozenProbeRejected("Only the built portable EXE may be tested")
    with tempfile.TemporaryDirectory(prefix="varyn-probe-") as folder:
        root = probe_directory(folder)
        if _child(exe, "write", root) != 0:
            raise FrozenProbeRejected("First process failed to seal synthetic draft")
        fixture = root / _NAME
        encrypted = fixture.read_bytes()
        if (len(encrypted) < 32 or
                _FIXED["task"].encode("utf-8") in encrypted or
                _FIXED["note"].encode("utf-8") in encrypted or
                b'"project":"VARYN"' in encrypted):
            raise FrozenProbeRejected("Encrypted fixture leaked synthetic plaintext")
        if _child(exe, "read", root) != 0:
            raise FrozenProbeRejected("Second process failed to restore draft")
        if _child(exe, "write", root) == 0 or fixture.read_bytes() != encrypted:
            raise FrozenProbeRejected("Third process overwrote existing encrypted draft")
        tampered = bytearray(encrypted)
        tampered[-1] ^= 1
        fixture.write_bytes(tampered)
        if _child(exe, "read", root) == 0:
            raise FrozenProbeRejected("Fourth process accepted tampered DPAPI draft")
        # The TemporaryDirectory context deletes only this synthetic folder.
        return {
            "format": "varyn.frozen_synthetic_restart_probe.v1",
            "separate_frozen_processes": 4,
            "encrypted_write_new_only": True,
            "restored_fixed_synthetic_fields": True,
            "existing_file_overwrite_refused": True,
            "tampered_dpapi_refused": True,
            "temporary_probe_removed_on_exit": True,
            "provider_requests": 0,
            "owner_human_click_verified": False,
            "official_app_access_verified": False,
            "official_consumer_history_sync_verified": False,
            "real_owner_device_verified": False,
        }


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="CI-only frozen VARYN cross-process synthetic DPAPI smoke"
    )
    parser.add_argument("--executable", required=True)
    args = parser.parse_args(argv)
    import json
    print(json.dumps(frozen_restart_acceptance(args.executable), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
