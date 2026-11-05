"""17S-32 fixed-choice owner device self-report; Windows native Tk callbacks.

Automated widget invokes are NOT proof of real owner clicks or remote app use.
"""
import json
import sys
import unittest
from unittest.mock import patch

from varyn.official_relay_pilot import _STEPS as _MANUAL_STEPS
from varyn.owner_pilot_launcher import _PROJECT_STEPS
from varyn.owner_pilot_checklist_gui import (
    OwnerPilotChecklist, build_portable_owner_report,
)

_KEYS = [key for key, _ in _MANUAL_STEPS + _PROJECT_STEPS]


class OwnerPilotReportContracts(unittest.TestCase):
    def test_defaults_refuse_full_pass_and_retain_false_proof(self):
        report = build_portable_owner_report(
            {key: "not_checked" for key in _KEYS}
        )
        self.assertEqual(report["status"], "incomplete_or_failed")
        self.assertFalse(report["machine_verified_human_click"])
        self.assertFalse(report["official_app_delivery_verified"])
        self.assertFalse(report["automatic_bidirectional_consumer_sync_verified"])
        self.assertFalse(report["private_history_read"])
        self.assertFalse(report["report_saved_or_uploaded"])
        self.assertFalse(report["safe_private_data_access_authorized"])

    def test_all_owner_pass_still_cannot_attest_provider_or_human(self):
        report = build_portable_owner_report(
            {key: "pass" for key in _KEYS}
        )
        self.assertEqual(report["status"], "owner_self_reported_pilot_pass")
        self.assertEqual(
            report["report_kind"],
            "owner_entered_self_report_not_independently_verified",
        )
        self.assertFalse(report["actual_owner_clicks_verified"])
        self.assertFalse(report["official_app_account_access_verified"])
        self.assertFalse(report["consumer_history_read_authority_verified"])
        self.assertFalse(report["consumer_history_write_authority_verified"])
        self.assertFalse(report["report_disk_write"])
        self.assertFalse(report["report_upload"])

    def test_unexpected_keys_types_or_words_denied(self):
        valid = {key: "not_checked" for key in _KEYS}
        for bad in (
            dict(valid, user_story="sensitive"),
            {key: "yes" for key in _KEYS},
            {key: True for key in _KEYS},
            {key: "pass" for key in _KEYS[:-1]},
            [],
        ):
            with self.subTest(bad=type(bad).__name__):
                with self.assertRaises(ValueError):
                    build_portable_owner_report(bad)


@unittest.skipUnless(sys.platform == "win32", "Actual hosted Windows Tk only")
class OwnerPilotNativeTkTests(unittest.TestCase):
    def test_workbench_launch_review_consent_stale_and_discard(self):
        from tkinter import ttk
        from varyn.desktop import VarynDesktop
        from varyn.desktop_controller import DesktopController

        ui = VarynDesktop(controller=DesktopController(allow_live_providers=False))
        try:
            ui.withdraw()
            ui._open_relay_workbench()
            wb = ui._relay_workbench
            stack = [wb]
            found = None
            while stack:
                for child in stack.pop().winfo_children():
                    if (isinstance(child, ttk.Button) and child.cget("text") ==
                            "17S-32 | Owner PC acceptance checklist"):
                        found = child
                    stack.append(child)
            self.assertIsNotNone(found)
            found.invoke()
            checklist = wb._owner_checklist_window
            self.assertIsInstance(checklist, OwnerPilotChecklist)
            self.assertTrue(checklist.winfo_exists())
            self.assertEqual(len(checklist.fields), 10)
            self.assertEqual(
                set(checklist.observations().values()), {"not_checked"}
            )
            found.invoke()
            self.assertIs(wb._owner_checklist_window, checklist)

            ui.clipboard_clear()
            ui.clipboard_append("SYNTHETIC: existing-clipboard")
            checklist._copy()
            self.assertEqual(ui.clipboard_get(), "SYNTHETIC: existing-clipboard")
            checklist._review()
            with patch(
                "varyn.owner_pilot_checklist_gui.messagebox.askyesno",
                return_value=False,
            ):
                checklist._copy()
            self.assertEqual(ui.clipboard_get(), "SYNTHETIC: existing-clipboard")

            for field in checklist.fields.values():
                field.set("pass")
            self.assertIsNone(checklist._reviewed_json)
            checklist._copy()
            self.assertEqual(ui.clipboard_get(), "SYNTHETIC: existing-clipboard")
            checklist._review()
            self.assertIn("owner_self_reported_pilot_pass", checklist._reviewed_json)
            first = next(iter(checklist.fields.values()))
            first.set("fail")
            self.assertIsNone(checklist._reviewed_json)
            checklist._copy()
            self.assertEqual(ui.clipboard_get(), "SYNTHETIC: existing-clipboard")
            first.set("pass")
            checklist._review()
            with patch(
                "varyn.owner_pilot_checklist_gui.messagebox.askyesno",
                return_value=True,
            ):
                checklist._copy()
            copied = json.loads(ui.clipboard_get())
            self.assertEqual(copied["status"], "owner_self_reported_pilot_pass")
            self.assertFalse(copied["machine_verified_human_click"])
            self.assertFalse(copied["automatic_bidirectional_consumer_sync_verified"])
            self.assertEqual(ui.controller.status()["requests_used"], 0)
            checklist._dismiss()
            self.assertIsNone(wb._owner_checklist_window)
            self.assertFalse(checklist.winfo_exists())
        finally:
            ui._close()


if __name__ == "__main__":
    unittest.main()
