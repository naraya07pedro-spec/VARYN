"""Checkpoint 17H: SAFE offline synthetic-only desktop acceptance probe.

Uses the real Windows native handle backend where available. Never accepts
a path, reads user data, invokes AI APIs, contacts a provider, opens a browser,
or launches Tk from CI. A passing result is NOT proof of a real GUI-click test.
"""
import argparse
import json
from threading import Event

from varyn.agent_runtime import AgentRejected
from varyn.file_grants import ScopedFileGrants
from varyn.synthetic_fixture import SyntheticFixture


def run_synthetic_acceptance(*, duration_seconds=1, wait_seconds=8):
    """Exercise real ephemeral grant, read-only listing and idle deletion."""
    if (type(duration_seconds) is not int or
            not 1 <= duration_seconds <= 5 or
            type(wait_seconds) is not int or not 2 <= wait_seconds <= 20):
        raise ValueError("Invalid synthetic acceptance timing")

    result = {
        "format": "varyn.synthetic_desktop_acceptance.v1",
        "test_data": "generated_synthetic_only",
        "ui_clicks_performed": False,
        "owner_windows_gui_verified": False,
        "user_paths_accessed": False,
        "provider_account_connected": False,
        "network_requests": 0,
        "external_upload": False,
        "files_deleted_outside_fixture": False,
        "checks": {
            "expected_sample_count": False,
            "read_only_bounded_scope": False,
            "automatic_idle_cleanup": False,
            "expired_grant_denied": False,
        },
        "passed": False,
    }
    fixture = None
    grants = ScopedFileGrants(auto_expire=True)
    finished = Event()
    try:
        fixture = SyntheticFixture()

        def clean_owned_fixture():
            fixture.close()
            finished.set()

        preview = grants.grant(
            fixture.root, user_confirmed=True,
            duration_seconds=duration_seconds, max_operations=3,
            on_release=clean_owned_fixture,
        )
        listing = grants.list_files(preview.grant_id)
        result["checks"]["expected_sample_count"] = (
            len(listing["files"]) == 2
            and {x["name"] for x in listing["files"]}
            == {"sample.txt", "notes.md"}
        )
        result["checks"]["read_only_bounded_scope"] = (
            listing["read_only"] is True
            and listing["recursive"] is False
            and preview.can_write is False
            and preview.max_operations == 3
        )
        # Do not poll status or touch the grant before the idle deadline;
        # otherwise the test could accidentally pass without a working timer.
        result["checks"]["automatic_idle_cleanup"] = (
            finished.wait(wait_seconds) and not fixture.root.exists()
        )
        try:
            grants.list_files(preview.grant_id)
        except (AgentRejected, PermissionError):
            result["checks"]["expired_grant_denied"] = True
        result["passed"] = all(result["checks"].values())
    except Exception:
        # No paths, exception text, credentials or file bytes in report.
        result["passed"] = False
    finally:
        grants.revoke_all()
        if fixture is not None:
            try:
                fixture.close()
            except OSError:
                result["passed"] = False
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Offline VARYN synthetic-only acceptance; no real user files"
    )
    parser.add_argument(
        "--synthetic-only", action="store_true", required=True,
        help="Explicitly confirm disposable VARYN sample data only",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    outcome = run_synthetic_acceptance()
    if args.json:
        print(json.dumps(outcome, sort_keys=True))
    else:
        print("VARYN synthetic desktop self-test:", "PASS" if outcome["passed"] else "FAIL")
        print("This is NOT a physical-PC GUI click or official-app sync test.")
        for name, valid in outcome["checks"].items():
            print(f"{name}: {'PASS' if valid else 'FAIL'}")
    return 0 if outcome["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
