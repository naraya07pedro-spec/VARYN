"""17S-25 hosted Windows actual Tk owner-reviewed temporary project notes.

Programmatic button.invoke + mocked owner modal, NOT physical human consent,
provider identity, external app delivery or encrypted persistent memory.
"""
import sys
from tkinter import ttk
import unittest
from unittest.mock import patch

from varyn.desktop import VarynDesktop
from varyn.desktop_controller import DesktopController


@unittest.skipUnless(sys.platform == "win32", "Hosted Windows Tk required")
class WorkingContextTkTests(unittest.TestCase):
    def test_actual_review_share_and_discard_widgets(self):
        ui = VarynDesktop(controller=DesktopController())
        try:
            ui.withdraw()
            ui.prompt.insert("1.0", "SYNTHETIC: keep next task constrained")
            nodes = [ui]
            buttons = {}
            while nodes:
                p = nodes.pop()
                for child in p.winfo_children():
                    if isinstance(child, ttk.Button):
                        buttons[child.cget("text")] = child
                    nodes.append(child)
            stage = buttons["17S-25 | Review project working note (RAM-only)"]
            reset = buttons["17S-25 | Discard all temporary project notes"]
            copy = buttons["17S-22 | Review and copy task to official app"]

            with patch.object(ui, "_review_scrollable_manual_text",
                              return_value=True) as review:
                stage.invoke()
            review.assert_called_once()
            self.assertEqual(ui._working_context.status()["saved_count"], 1)
            self.assertFalse(ui.include_working_context.get())
            ui.include_working_context.set(True)
            with patch.object(ui, "_review_manual_relay_packet",
                              return_value=True) as approval:
                copy.invoke()
            approval.assert_called_once()
            self.assertIn("TEMPORARY PROJECT NOTES", ui.clipboard_get())
            self.assertEqual(ui.controller.status()["requests_used"], 0)
            reset.invoke()
            self.assertEqual(ui._working_context.status()["saved_count"], 0)
            self.assertFalse(ui.include_working_context.get())
            self.assertIsNone(ui._official_relay.last_return_receipt())
        finally:
            ui._close()


if __name__ == "__main__":
    unittest.main()
