"""17S-23: owner-run manual official-app pilot; no credential or transcript input.

This only records bounded USER-REPORTED yes/no/skip observations in process
memory, prints structured summary and exits. It never accesses any account,
browser, clipboard, files, network or official app history itself.
"""
import argparse
import json

_STEPS = (
    (
        "desktop_offline",
        "VARYN desktop opened in ordinary-user Windows session, "
        "fake provider selected, VARYN API/network permissions OFF",
    ),
    (
        "external_launch_consent",
        "Click 17S-23 Open selected official app; decline once (no browser launch), "
        "then approve; correct pinned official homepage opens",
    ),
    (
        "denied_copy_kept_clipboard",
        "Use non-sensitive sample text; Reject the exact packet preview. "
        "Existing clipboard remained unchanged",
    ),
    (
        "approved_packet_pasted",
        "Approve a fresh non-sensitive task preview, then manually paste "
        "the packet into the FIRST official app",
    ),
    (
        "manual_response_returned",
        "Copy a short test reply from that official app into VARYN Message; "
        "review its exact text and accept into temporary VARYN RAM",
    ),
    (
        "second_app_handoff",
        "Choose a SECOND official app and review a new packet: the earlier "
        "reply is quoted and labelled unverified; paste manually if desired",
    ),
    (
        "discard_and_no_auto_sync",
        "Discard VARYN manual relay state: staged reply no longer available. "
        "No automatic history/memory sync or hidden VARYN API call claimed",
    ),
)
_ALLOWED = {"yes": "pass", "no": "fail", "skip": "not_checked"}


def build_manual_pilot_report(answers):
    if (type(answers) is not dict or
            set(answers) != {key for key, _ in _STEPS} or
            any(type(value) is not str or value not in _ALLOWED.values()
                for value in answers.values())):
        raise ValueError("Expected only bounded yes/no/skip observations")
    positive = all(answers[key] == "pass" for key, _ in _STEPS)
    return {
        "format": "varyn.manual_official_app_owner_pilot.v1",
        "report_kind": "owner_self_report_not_independently_verified",
        "steps": {key: answers[key] for key, _ in _STEPS},
        "status": ("owner_self_reported_manual_pilot_pass"
                   if positive else "incomplete_or_failed"),
        "human_clicks_observed_by_ci": False,
        "official_app_accounts_authenticated_by_varyn": False,
        "provider_reply_origin_verified": False,
        "official_consumer_history_read_verified": False,
        "official_consumer_history_write_verified": False,
        "automatic_two_way_sync_verified": False,
        "can_dispatch": False,
        "network_calls_by_report_tool": 0,
        "accounts_or_credentials_requested": False,
        "transcript_text_requested": False,
        "report_saved_or_uploaded_by_tool": False,
    }


def collect_manual_pilot(read_input=input, *, write=print,
                         desktop_already_launched=False):
    write("17S-23: owner-run non-sensitive manual continuity pilot.")
    if desktop_already_launched:
        write("The launcher requested a desktop window. Verify it actually opened.")
    else:
        write("Launch from another normal-user Windows terminal: py -3 -m varyn.desktop")
    write("Do NOT use personal conversations, API keys or customer data.")
    write("Use two existing official AI apps; login is performed in the browser,")
    write("never by VARYN. Answer only yes/no/skip (skip is not a pass).")
    results = {}
    for key, instruction in _STEPS:
        write(instruction)
        try:
            response = read_input("Result [yes/no/skip]: ")
        except (KeyboardInterrupt, EOFError):
            response = "skip"
        results[key] = _ALLOWED.get(
            response.strip().lower() if type(response) is str else "",
            "not_checked",
        )
    return results


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Manual official-app owner self-report, no live connectivity")
    parser.add_argument("--manual-only", action="store_true", required=True)
    parser.add_argument("--interactive", action="store_true", required=True)
    parser.parse_args(argv)
    report = build_manual_pilot_report(collect_manual_pilot())
    print(json.dumps(report, sort_keys=True))
    print("SELF-REPORT ONLY; owner-device action NOT independently verified.")
    return 0 if report["status"] == "owner_self_reported_manual_pilot_pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
