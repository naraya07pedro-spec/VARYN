"""17S-26 owner-visible, one-command official-app + project pilot launcher.

This launches the normal VARYN Tk process and asks the existing fixed-option
owner report. No browser automation, provider login, transcript capture,
network request by this launcher, private data, or permanent report writing.

The signed-in browser and VARYN UI are operated by the owner, not this tool.
All self-reported outcomes remain unverified.
"""
import argparse
import ctypes
import json
import os
from pathlib import Path
import subprocess
import sys

from varyn.official_relay_pilot import (
    build_manual_pilot_report,
    collect_manual_pilot,
)

_ROOT = Path(__file__).resolve().parent.parent
_SENSITIVE_KEYS = frozenset({
    "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY",
    "GOOGLE_API_KEY", "AZURE_OPENAI_API_KEY", "OPENROUTER_API_KEY",
    "GITHUB_TOKEN", "GH_TOKEN", "HF_TOKEN", "HUGGINGFACE_HUB_TOKEN",
})
_PROJECT_STEPS = (
    (
        "project_note_review",
        "17S-25: type a SYNTHETIC: note, set project VARYN / topic next_step "
        "and approve the exact temporary working note; no DB save",
    ),
    (
        "project_conflict_shown",
        "Change the same topic note. Confirm BOTH versions are shown "
        "and a separate Replace action is required",
    ),
    (
        "project_optin_and_discard",
        "Without opting in, next clipboard preview excludes the project note. "
        "Opt in explicitly, confirm only VARYN project notes appear, "
        "then Discard and check RAM note state is cleared",
    ),
)
_OPTIONS = {"yes": "pass", "no": "fail", "skip": "not_checked"}


def sanitized_child_environment(source=None):
    """Child API/CI keys are dropped; owner browser sessions are untouched."""
    original = os.environ if source is None else source
    if type(original) is not dict and original is not os.environ:
        raise TypeError("Expected environment mapping")
    return {
        key: value for key, value in original.items()
        if key.upper() not in _SENSITIVE_KEYS
    }


def is_windows_elevated():
    """If elevation cannot be checked, refuse normal-owner pilot."""
    if os.name != "nt":
        return None
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except (AttributeError, OSError, ValueError):
        return None


def collect_project_checks(*, input_fn=input, write=print):
    answers = {}
    for name, instruction in _PROJECT_STEPS:
        write(instruction)
        try:
            answer = input_fn("Result [yes/no/skip]: ")
        except (EOFError, KeyboardInterrupt):
            answer = "skip"
        answers[name] = _OPTIONS.get(
            answer.strip().lower() if type(answer) is str else "",
            "not_checked",
        )
    return answers


def combined_owner_report(manual, project):
    """Fixed-status only, no user text, credentials or OS identity."""
    baseline = build_manual_pilot_report(manual)
    if (type(project) is not dict or
            set(project) != {name for name, _ in _PROJECT_STEPS} or
            any(type(value) is not str or value not in _OPTIONS.values()
                for value in project.values())):
        raise ValueError("Only fixed project pilot observations allowed")
    all_pass = (
        baseline["status"] == "owner_self_reported_manual_pilot_pass" and
        all(value == "pass" for value in project.values())
    )
    return {
        "format": "varyn.owner_desktop_official_pilot.v1",
        "report_kind": "owner_self_report_not_independently_verified",
        "status": ("owner_self_reported_pilot_pass" if all_pass
                   else "incomplete_or_failed"),
        "manual_observations": baseline["steps"],
        "project_observations": dict(project),
        "actual_owner_clicks_verified": False,
        "official_app_account_access_verified": False,
        "provider_reply_origin_verified": False,
        "automatic_bidirectional_consumer_sync_verified": False,
        "consumer_history_read_authority_verified": False,
        "consumer_history_write_authority_verified": False,
        "safe_private_data_access_authorized": False,
        "report_disk_write": False,
        "report_upload": False,
        "launcher_network_calls": 0,
    }


def run_owner_pilot(*, windows=None, elevated=None,
                    executable=None, popen=None,
                    input_fn=input, write=print, env=None):
    """Launch real desktop once, then ask bounded owner observations.

    Dependency injection exists only for offline tests. This function never
    simulates a passing owner response.
    """
    running_windows = os.name == "nt" if windows is None else windows
    if type(running_windows) is not bool or not running_windows:
        write("Owner pilot requires an interactive Windows desktop.")
        return 2
    running_elevated = is_windows_elevated() if elevated is None else elevated
    if running_elevated is not False:
        write("Start from NORMAL non-administrator Windows; elevation "
              "status unknown or elevated. Nothing was launched.")
        return 2
    python = sys.executable if executable is None else executable
    if type(python) is not str or not python:
        write("Cannot locate a trusted Python interpreter.")
        return 2
    launch = subprocess.Popen if popen is None else popen
    args = [python, "-m", "varyn.desktop"]
    write("VARYN owner pilot: no keys, tokens, private documents or "
          "real client content. Use synthetic examples only.")
    write("Opening VARYN in a separate local process; official websites "
          "open ONLY after separate approval in the desktop.")
    try:
        process = launch(
            args, cwd=str(_ROOT), env=sanitized_child_environment(env),
        )
    except (OSError, ValueError):
        write("Cannot start VARYN desktop. Pilot NOT executed.")
        return 2
    if process.poll() is not None:
        write("Desktop exited immediately. Pilot NOT executed.")
        return 2
    write("Keep that desktop window open. This terminal asks ONLY yes/no/skip. "
          "No transcript or account data is collected.")
    manual = collect_manual_pilot(
        read_input=input_fn, write=write, desktop_already_launched=True,
    )
    write("Now verify reviewed project notes and explicit opt-in, "
          "using only SYNTHETIC: sample text.")
    project = collect_project_checks(input_fn=input_fn, write=write)
    report = combined_owner_report(manual, project)
    write(json.dumps(report, sort_keys=True))
    write("OWNER SELF-REPORT ONLY. CI cannot verify actual clicks, "
          "remote app account state or automatic sync.")
    write("The desktop may remain open. Close it normally after your checks.")
    return 0 if report["status"] == "owner_self_reported_pilot_pass" else 1


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Owner-only manual VARYN pilot (no autonomous syncing)")
    parser.add_argument("--manual-only", action="store_true", required=True)
    parser.add_argument("--interactive", action="store_true", required=True)
    parser.parse_args(argv)
    return run_owner_pilot()


if __name__ == "__main__":
    raise SystemExit(main())
