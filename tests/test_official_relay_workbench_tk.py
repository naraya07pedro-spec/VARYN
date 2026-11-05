"""17S-28: actual hosted-Windows Tk focused workbench, real widget commands.

These tests invoke Tk buttons programmatically and mock the user's modal
decisions and web browser. They are not owner-device acceptance, remote site
delivery, provider account authentication, or automatic history sync.
"""
import sys
import tkinter as tk
from tkinter import ttk
import unittest
from unittest.mock import patch

from varyn.desktop import VarynDesktop
from varyn.desktop_controller import DesktopController
from varyn.official_relay_workbench import OfficialRelayWorkbench


def find_button(root, label):
    nodes = [root]
    while nodes:
        widget = nodes.pop()
        for child in widget.winfo_children():
            if isinstance(child, ttk.Button) and child.cget("text") == label:
                return child
            nodes.append(child)
    raise AssertionError("Missing workbench button: " + label)


@unittest.skipUnless(sys.platform == "win32", "Hosted Windows native Tk only")
class OfficialRelayWorkbenchTkTests(unittest.TestCase):
    def test_open_single_workbench_and_end_to_end_manual_local_callbacks(self):
        ui = VarynDesktop(controller=DesktopController())
        try:
            ui.withdraw()
            ui.prompt.insert(
                "1.0", "SYNTHETIC: main VARYN message must not be overwritten")
            find_button(ui, "17S-28 | Open official-app relay workbench").invoke()
            wb = ui._relay_workbench
            self.assertIsInstance(wb, OfficialRelayWorkbench)
            self.assertTrue(wb.winfo_exists())
            self.assertFalse(wb.include_context.get())
            self.assertIn("SYNTHETIC:", wb.task.get("1.0", "end-1c"))
            find_button(ui, "17S-28 | Open official-app relay workbench").invoke()
            self.assertIs(ui._relay_workbench, wb)

            wb.target.set("chatgpt")
            with patch("varyn.desktop.messagebox.askyesno",
                       return_value=False), \
                 patch("varyn.desktop.webbrowser.open_new_tab") as browser:
                find_button(wb, "1. Open official site (consent)").invoke()
            browser.assert_not_called()
            with patch("varyn.desktop.messagebox.askyesno",
                       return_value=True), \
                 patch("varyn.desktop.webbrowser.open_new_tab",
                       return_value=True) as browser:
                find_button(wb, "1. Open official site (consent)").invoke()
            browser.assert_called_once_with("https://chatgpt.com/")

            wb.task.delete("1.0", "end")
            wb.task.insert("1.0", "SYNTHETIC: workbench-only sample")
            with patch.object(ui, "_review_manual_relay_packet",
                              return_value=True):
                find_button(
                    wb, "2. Review EXACT packet and copy to clipboard").invoke()
            self.assertIn("SYNTHETIC: workbench-only sample", ui.clipboard_get())
            self.assertNotIn(
                "main VARYN message", ui.clipboard_get()
            )
            self.assertIn(
                "main VARYN message", ui.prompt.get("1.0", "end-1c")
            )
            self.assertTrue(ui._official_relay.status()["awaiting_user_pasteback"])
            self.assertIn("Awaiting manual reply", wb.stage_label.get())

            wb.reply.insert("1.0", "SYNTHETIC: unverified browser response")
            with patch.object(ui, "_review_manual_reply_text",
                              return_value=True):
                find_button(
                    wb, "3. Review EXACT pasted reply and stage in RAM").invoke()
            self.assertTrue(ui._official_relay.status()["reply_in_ram"])
            self.assertIn("Unverified pasted reply", wb.stage_label.get())

            wb.target.set("claude")
            wb.task.delete("1.0", "end")
            wb.task.insert("1.0", "SYNTHETIC: critique the earlier answer")
            with patch.object(ui, "_review_manual_relay_packet",
                              return_value=True):
                find_button(
                    wb, "2. Review EXACT packet and copy to clipboard").invoke()
            self.assertEqual(ui._official_relay.status()["hops_used"], 2)
            self.assertIn("claimed source: chatgpt", ui.clipboard_get())
            self.assertIn("NOT verified", ui.clipboard_get())
            self.assertEqual(ui.controller.status()["requests_used"], 0)
            self.assertEqual(ui._official_relay.status()["provider_requests"], 0)

            find_button(wb, "Discard relay RAM").invoke()
            self.assertFalse(ui._official_relay.status()["reply_in_ram"])
            self.assertEqual(ui._official_relay.status()["hops_used"], 0)
            wb._dismiss()
            self.assertIsNone(ui._relay_workbench)
            self.assertFalse(wb.winfo_exists())
        finally:
            ui._close()

    def test_notes_share_only_by_optin_and_reuse_original_review_path(self):
        ui = VarynDesktop(controller=DesktopController())
        try:
            ui.withdraw()
            ui._open_relay_workbench()
            wb = ui._relay_workbench
            wb.project.set("PROJECT_A")
            wb.topic.set("next")
            wb.note.delete("1.0", "end")
            wb.note.insert("1.0", "SYNTHETIC: special project A note")
            with patch.object(ui, "_review_scrollable_manual_text",
                              return_value=True):
                find_button(
                    wb, "4. Review project note / show conflicts").invoke()
            self.assertEqual(ui._working_context.status()["saved_count"], 1)
            self.assertFalse(wb.include_context.get())

            with patch.object(ui, "_review_manual_relay_packet",
                              return_value=True):
                find_button(
                    wb, "2. Review EXACT packet and copy to clipboard").invoke()
            self.assertNotIn(
                "special project A note", ui.clipboard_get()
            )
            find_button(wb, "Discard relay RAM").invoke()

            wb.include_context.set(True)
            with patch.object(ui, "_review_manual_relay_packet",
                              return_value=True):
                find_button(
                    wb, "2. Review EXACT packet and copy to clipboard").invoke()
            self.assertIn("special project A note", ui.clipboard_get())
            self.assertIn("not verified facts", ui.clipboard_get())
            find_button(
                wb, "Discard project RAM notes").invoke()
            self.assertFalse(wb.include_context.get())
            self.assertEqual(ui._working_context.status()["saved_count"], 0)
            self.assertFalse(ui.include_working_context.get())
        finally:
            ui._close()

    def test_no_copy_if_sample_invalid_or_review_declined(self):
        ui = VarynDesktop(controller=DesktopController())
        try:
            ui.withdraw()
            ui._open_relay_workbench()
            wb = ui._relay_workbench
            wb.task.delete("1.0", "end")
            wb.task.insert("1.0", "REAL PRIVATE TEXT WITHOUT SYNTHETIC PREFIX")
            with patch.object(ui, "_review_manual_relay_packet") as reviewer:
                find_button(
                    wb, "2. Review EXACT packet and copy to clipboard").invoke()
            reviewer.assert_not_called()
            self.assertIn("BLOCKED", wb.detail_label.get())
            self.assertEqual(ui._official_relay.status()["hops_used"], 0)
            wb.task.delete("1.0", "end")
            wb.task.insert("1.0", "SYNTHETIC: harmless demo")
            with patch.object(ui, "_review_manual_relay_packet",
                              return_value=False):
                find_button(
                    wb, "2. Review EXACT packet and copy to clipboard").invoke()
            self.assertEqual(ui._official_relay.status()["hops_used"], 0)
            self.assertFalse(ui._official_relay.status()["awaiting_user_pasteback"])
        finally:
            ui._close()


if __name__ == "__main__":
    unittest.main()
