"""Checkpoint 17I: minimal, local-only human GUI acceptance attestation.

This does NOT automate mouse clicks or authenticate the owner. The optional
interactive report is an unverified user self-report, not a signed audit or
evidence of provider sync. No files, paths, account data, network or hardware
identifiers are read or stored. The separate synthetic fixture CLI runs first.
"""
import argparse
import json

from varyn.desktop_acceptance import run_synthetic_acceptance

_STEPS = (
    ("gui_opened", "Tk desktop opened in a normal user session with FAKE provider and network OFF"),
    ("decline_safe", "Declining demo-folder consent left no active access"),
    ("grant_count_two", "Approving generated demo folder showed exactly 2 files on Inspect"),
    ("no_private_data", "No personal folders, file paths, filenames or contents appeared in chat"),
    ("revoke_denies", "After Revoke, Inspect reported no active access"),
    ("restart_denies", "After closing and reopening, the old grant was unavailable"),
    ("parent_count_denied", "Scroll to 17S-20 parent-only synthetic count; select No. Transcript states Declined, with no local integer sum or model request"),
    ("parent_count_approved", "Select 17S-20 parent-only synthetic count again and Yes. Transcript shows local integer sum: 21; no provider/network request occurred"),
)
_ALLOWED = {"yes": "pass", "no": "fail", "skip": "not_checked"}


def build_owner_report(synthetic, answers):
    """Bounded deterministic summary; never consume arbitrary answer strings.

    True CLI success is the ONLY machine-produced result. Mouse/GUI results
    are explicitly owner-attested, cannot be upgraded to independent proof.
    """
    if type(synthetic) is not dict or type(synthetic.get("passed")) is not bool:
        raise ValueError("Invalid synthetic acceptance evidence")
    if (type(answers) is not dict or
            set(answers) != {key for key, _ in _STEPS} or
            any(type(v) is not str or v not in _ALLOWED.values()
                for v in answers.values())):
        raise ValueError("Invalid bounded human observations")
    result = {
        "format": "varyn.owner_gui_self_report.v1",
        "report_kind": "owner_self_attested_not_independently_verified",
        "synthetic_cli_passed": synthetic["passed"],
        "owner_reported_checks": {
            key: answers[key] for key, _ in _STEPS
        },
        "owner_reported_all_passed": all(
            x == "pass" for x in answers.values()
        ),
        "acceptance_status": "owner_self_reported_pass"
            if synthetic["passed"] and all(x == "pass" for x in answers.values())
            else "incomplete_or_failed",
        "gui_clicks_observed_by_automated_test": False,
        "independently_verified_on_owner_pc": False,
        "identity_authenticated": False,
        "official_apps_connected": False,
        "automatic_official_app_sync_verified": False,
        "provider_requests_by_report_tool": 0,
        "user_file_paths_requested_by_report_tool": False,
        "report_saved_to_disk_by_tool": False,
    }
    return result


def collect_owner_observations(read_input=input, *, write=print):
    """Fail-closed yes/no/skip for fixed prompts. No free-text is retained."""
    write("Perform the real GUI steps manually. Do not use real user files.")
    write("Open a second normal-user terminal: py -3 -m varyn.desktop")
    write("Leave provider on fake, network OFF, and test only the generated samples.")
    write("Scroll the main window to reach late-stage consent buttons.")
    write("Answer each item with yes, no or skip (skip = not independently checked).")
    answers = {}
    for key, prompt in _STEPS:
        write(prompt)
        try:
            raw = read_input("Result [yes/no/skip]: ")
        except (EOFError, KeyboardInterrupt):
            raw = "skip"
        # Any malformed, blank or unexpected input is NOT a passing answer.
        answers[key] = _ALLOWED.get(raw.strip().lower()
                                    if isinstance(raw, str) else "", "not_checked")
    return answers


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Owner self-report for synthetic-only desktop GUI checks; no uploads"
    )
    parser.add_argument(
        "--synthetic-only", action="store_true", required=True,
        help="Only VARYN-generated temporary files, never user paths",
    )
    parser.add_argument(
        "--interactive", action="store_true", required=True,
        help="Require owner to answer bounded GUI observations",
    )
    args = parser.parse_args(argv)
    _ = args
    synthetic = run_synthetic_acceptance()
    print("CLI synthetic self-test:", "PASS" if synthetic["passed"] else "FAIL")
    answers = collect_owner_observations()
    report = build_owner_report(synthetic, answers)
    print(json.dumps(report, sort_keys=True))
    print("Owner SELF-REPORT only. No actual GUI clicks were observed by CI.")
    return 0 if report["acceptance_status"] == "owner_self_reported_pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
