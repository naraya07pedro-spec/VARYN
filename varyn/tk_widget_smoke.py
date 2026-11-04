"""17J: actual Tk widget-command smoke on synthetic-only VARYN desktop.

Real tkinter widgets are instantiated and Button.invoke() is exercised, but
NO real human mouse click, consent, private file, provider account or network
request occurs. Refuses to claim physical owner acceptance or OS isolation.
"""
import argparse
import json
import tkinter as tk
from threading import Event
from tkinter import ttk
from unittest.mock import patch

from varyn.agent_runtime import AgentRejected
from varyn.desktop import VarynDesktop
from varyn.desktop_controller import DesktopController
from varyn.native_tool_requests import NativeToolRequestClient
from varyn.synthetic_fixture import SyntheticFixture


_BUTTONS = (
    "Create & grant VARYN demo folder",
    "Inspect test-folder count",
    "Revoke test-folder grant",
)


def _buttons(root):
    """Find actual ttk buttons via Tk's widget tree, not direct bound methods."""
    found = {}
    pending = [root]
    while pending:
        parent = pending.pop()
        for child in parent.winfo_children():
            if isinstance(child, ttk.Button):
                text = child.cget("text")
                if text in _BUTTONS:
                    if text in found:
                        raise AssertionError("Duplicate synthetic file UI action")
                    found[text] = child
            pending.append(child)
    if set(found) != set(_BUTTONS):
        raise AssertionError("Missing synthetic file UI buttons")
    return found


def _offline_native_factory(**_kwargs):
    # A live native-tool adapter is never constructed by this test.
    return NativeToolRequestClient(allow_network=False)


def _fixture_factory(captured):
    fixture = SyntheticFixture()
    closed = Event()
    actual_close = fixture.close

    def tracked_close():
        actual_close()
        closed.set()

    fixture.close = tracked_close
    captured.append((fixture, closed))
    return fixture


def _report():
    return {
        "format": "varyn.tk_widget_smoke.v1",
        "test_data": "VARYN_generated_synthetic_only",
        "tk_widget_tree_created": False,
        "button_commands_invoked_programmatically": False,
        "human_mouse_clicks_performed": False,
        "human_consent_obtained": False,
        "owner_physical_pc_tested": False,
        "official_provider_connected": False,
        "network_requests_by_test": 0,
        "personal_folders_selected": False,
        "checks": {
            "actual_tk_buttons_present": False,
            "refused_consent_creates_no_grant": False,
            "approved_generated_scope_count_two": False,
            "transcript_excludes_paths_and_contents": False,
            "revoke_deletes_fixture_and_denies_old_grant": False,
            "idle_expiry_deletes_without_click": False,
            "closed_window_does_not_restore_scope": False,
        },
        "status": "not_run",
        "passed": False,
    }


def run_tk_widget_smoke(*, timeout_seconds=8):
    """Exercise real Tk callback wiring; no actual user gestures or OS sandbox.

    Missing graphics is REPORTED as unavailable, never represented as PASS.
    A default-off DesktopController and offline-only native tool client are
    used throughout. Messagebox responses are simulated, not human consent.
    """
    if type(timeout_seconds) is not int or not 2 <= timeout_seconds <= 20:
        raise ValueError("Invalid synthetic GUI timeout")
    report = _report()
    windows = []
    fixtures = []
    try:
        with patch("varyn.desktop.NativeToolRequestClient",
                   side_effect=_offline_native_factory), \
             patch("varyn.desktop.SyntheticFixture",
                   side_effect=lambda: _fixture_factory(fixtures)), \
             patch("varyn.desktop.messagebox.askyesno",
                   side_effect=[False, True, True]) as consent:
            try:
                window = VarynDesktop(
                    controller=DesktopController(allow_live_providers=False)
                )
            except tk.TclError:
                report["status"] = "unavailable_no_graphical_session"
                return report
            windows.append(window)
            window.withdraw()
            window.update_idletasks()
            report["tk_widget_tree_created"] = True
            controls = _buttons(window)
            report["checks"]["actual_tk_buttons_present"] = True
            if (window.provider.get() != "fake" or
                    window.consent_network.get() or
                    window.controller.status()["network_enabled"]):
                raise AssertionError("GUI not in offline fake mode")

            controls[_BUTTONS[0]].invoke()
            report["checks"]["refused_consent_creates_no_grant"] = (
                window._file_grant_id is None and
                window._file_fixture is None and
                window._file_grants.status()["active"] == 0 and
                len(fixtures) == 0
            )
            controls[_BUTTONS[0]].invoke()
            first = window._file_grant_id
            fixture, released = fixtures[0]
            if first is None or not fixture.root.is_dir():
                raise AssertionError("Synthetic scope was not created")
            controls[_BUTTONS[1]].invoke()
            transcript = window.transcript.get("1.0", "end-1c")
            report["checks"]["approved_generated_scope_count_two"] = (
                "Allowed top-level synthetic file count: 2" in transcript and
                window._file_grants.status()["active"] == 1
            )
            report["checks"]["transcript_excludes_paths_and_contents"] = not any(
                secret in transcript for secret in (
                    str(fixture.root), "sample.txt", "notes.md",
                    "VARYN local-only synthetic test record.",
                    "Synthetic fixture; never provider context.",
                )
            )
            controls[_BUTTONS[2]].invoke()
            blocked = False
            try:
                window._file_grants.list_files(first)
            except (AgentRejected, PermissionError):
                blocked = True
            report["checks"]["revoke_deletes_fixture_and_denies_old_grant"] = (
                blocked and released.is_set() and
                not fixture.root.exists() and
                window._file_grant_id is None
            )
            # Exercise actual Tk approval button again, but shorten this
            # *synthetic-only* grant to one second to prove idle cleanup.
            grant = window._file_grants.grant

            def short_grant(path, **kwargs):
                return grant(path, duration_seconds=1, **kwargs)

            with patch.object(window._file_grants, "grant",
                              side_effect=short_grant):
                controls[_BUTTONS[0]].invoke()
            later_id = window._file_grant_id
            later_fixture, later_released = fixtures[1]
            # No Inspect/Revoke/status poll between grant and timeout.
            expired_without_ui = later_released.wait(timeout_seconds)
            report["checks"]["idle_expiry_deletes_without_click"] = (
                expired_without_ui and not later_fixture.root.exists()
            )
            window._close()
            report["checks"]["closed_window_does_not_restore_scope"] = (
                window._closing and
                window._file_grants.status()["active"] == 0 and
                window._file_grant_id is None
            )
            second = VarynDesktop(
                controller=DesktopController(allow_live_providers=False)
            )
            windows.append(second)
            second.withdraw()
            second.update_idletasks()
            if second._file_grants.status()["active"] != 0:
                report["checks"]["closed_window_does_not_restore_scope"] = False
            second._close()
            report["button_commands_invoked_programmatically"] = True
            if consent.call_count != 3:
                raise AssertionError("Unexpected synthetic consent count")
            if later_id is None:
                raise AssertionError("Missing temporary grant")
            report["passed"] = all(report["checks"].values())
            report["status"] = "passed" if report["passed"] else "failed"
    except Exception:
        # Never surface raw exception text, paths, prompts or runtime secrets.
        report["status"] = "failed"
        report["passed"] = False
    finally:
        for window in windows:
            try:
                window._file_grants.revoke_all()
                if not window._closing:
                    window._close()
            except Exception:
                try:
                    window.destroy()
                except Exception:
                    pass
        for fixture, _ in fixtures:
            try:
                fixture.close()
            except OSError:
                report["passed"] = False
                report["status"] = "failed"
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Offline REAL Tk widget command smoke with mock consent"
    )
    parser.add_argument("--synthetic-only", required=True, action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument(
        "--require-display", action="store_true",
        help="Return nonzero if no graphical Tk session is available",
    )
    args = parser.parse_args(argv)
    report = run_tk_widget_smoke()
    if args.json:
        print(json.dumps(report, sort_keys=True))
    else:
        print("Tk widget synthetic smoke:", report["status"])
        print("Programmatic button invocation only, no real human clicks.")
    return 0 if report["passed"] else 2 if (
        report["status"] == "unavailable_no_graphical_session"
        and not args.require_display
    ) else 1


if __name__ == "__main__":
    raise SystemExit(main())
