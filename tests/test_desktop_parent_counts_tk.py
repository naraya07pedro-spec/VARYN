"""17S-20 hosted Windows Tk native widget wiring (button.invoke != human click)."""
import sys
import unittest
from tkinter import ttk
from unittest.mock import patch

from varyn.desktop import VarynDesktop
from varyn.desktop_controller import DesktopController


@unittest.skipUnless(sys.platform == "win32", "Hosted Windows Tk only")
class NativeOwnerSyntheticConsentTkTests(unittest.TestCase):
    def test_real_widget_button_denies_then_approves(self):
        ui = VarynDesktop(controller=DesktopController())
        try:
            ui.withdraw()
            stack = [ui]
            button = None
            while stack:
                parent = stack.pop()
                for child in parent.winfo_children():
                    if isinstance(child, ttk.Button) and (
                            child.cget("text") ==
                            "17S-20 | Review parent-only synthetic count"):
                        button = child
                    stack.append(child)
            self.assertIsNotNone(button)
            with patch("varyn.desktop.messagebox.askyesno",
                       return_value=False) as ask:
                button.invoke()
            self.assertEqual(ask.call_count, 1)
            transcript = ui.transcript.get("1.0", "end-1c")
            self.assertIn("Declined: no fixture content read", transcript)
            self.assertNotIn("local integer sum: 21", transcript)

            with patch("varyn.desktop.messagebox.askyesno",
                       return_value=True) as ask:
                button.invoke()
            self.assertEqual(ask.call_count, 1)
            transcript = ui.transcript.get("1.0", "end-1c")
            self.assertIn("local integer sum: 21", transcript)
            self.assertEqual(ui.controller.status()["requests_used"], 0)
        finally:
            ui._close()


if __name__ == "__main__":
    unittest.main()
