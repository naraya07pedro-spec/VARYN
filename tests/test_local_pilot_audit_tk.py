"""17S-27 hosted Windows Tk local event audit widget contract.

Scripted Button.invoke is NOT human input, and mocked browser access is NOT
official-app proof. Only verifies real Tk UI callback wiring and RAM report.
"""
import json
import sys
from tkinter import ttk
import unittest
from unittest.mock import patch

from varyn.desktop import VarynDesktop
from varyn.desktop_controller import DesktopController


@unittest.skipUnless(sys.platform == "win32", "Hosted Windows Tk only")
class NativeLocalPilotAuditTests(unittest.TestCase):
    def test_real_windows_buttons_record_local_events_and_copy_fixed_report(self):
        ui = VarynDesktop(controller=DesktopController())
        try:
            ui.withdraw()
            controls = {}
            stack = [ui]
            while stack:
                node = stack.pop()
                for child in node.winfo_children():
                    if isinstance(child, ttk.Button):
                        controls[child.cget("text")] = child
                    stack.append(child)
            start = controls["17S-27 | Start local event audit"]
            report = controls["17S-27 | Review / copy audit"]
            reset = controls["17S-27 | Reset audit"]
            copy = controls["17S-22 | Review and copy task to official app"]
            paste = controls["17S-22 | Review pasted reply (RAM-only)"]
            launch = controls["17S-23 | Open selected official app in browser"]

            self.assertFalse(ui._pilot_audit.snapshot()["active"])
            start.invoke()
            self.assertTrue(ui._pilot_audit.snapshot()["active"])

            ui.official_relay_target.set("chatgpt")
            ui.prompt.insert("1.0", "SYNTHETIC: tiny task")
            with patch("varyn.desktop.messagebox.askyesno",
                       return_value=True), \
                 patch("varyn.desktop.webbrowser.open_new_tab",
                       return_value=True) as browser:
                launch.invoke()
            browser.assert_called_once_with("https://chatgpt.com/")
            with patch.object(ui, "_review_manual_relay_packet",
                              return_value=True):
                copy.invoke()
            ui.prompt.delete("1.0", "end")
            ui.prompt.insert("1.0", "SYNTHETIC: pasted source is unverified")
            with patch.object(ui, "_review_manual_reply_text",
                              return_value=True):
                paste.invoke()
            ui.official_relay_target.set("claude")
            ui.prompt.delete("1.0", "end")
            ui.prompt.insert("1.0", "SYNTHETIC: review second app")
            with patch.object(ui, "_review_manual_relay_packet",
                              return_value=True):
                copy.invoke()
            state = ui._pilot_audit.snapshot()
            self.assertTrue(state["local_two_target_attempt_observed"])
            self.assertFalse(state["automatic_bidirectional_sync_verified"])

            original_clip = ui.clipboard_get()
            with patch.object(ui, "_review_scrollable_manual_text",
                              return_value=False):
                report.invoke()
            self.assertEqual(ui.clipboard_get(), original_clip)
            with patch.object(ui, "_review_scrollable_manual_text",
                              return_value=True):
                report.invoke()
            fixed = json.loads(ui.clipboard_get())
            self.assertEqual(fixed["approved_clipboard_targets"],
                             ["chatgpt", "claude"])
            self.assertFalse(fixed["remote_paste_or_delivery_verified"])
            self.assertFalse(fixed["independent_human_click_verified"])
            self.assertEqual(ui.controller.status()["requests_used"], 0)

            with patch("varyn.desktop.messagebox.askyesno",
                       return_value=True):
                reset.invoke()
            self.assertFalse(ui._pilot_audit.snapshot()["active"])
            self.assertEqual(ui._pilot_audit.snapshot()["events_observed"], 0)
        finally:
            ui._close()


if __name__ == "__main__":
    unittest.main()
