"""17S-23 hosted Windows Tk official-site launch contract.

The widget is real, but consent and browser launch are mocked. No actual
owner click, login, browser/network call or provider history is observed.
"""
import sys
import unittest
from tkinter import ttk
from unittest.mock import patch

from varyn.desktop import VarynDesktop
from varyn.desktop_controller import DesktopController


@unittest.skipUnless(sys.platform == "win32", "Hosted Windows Tk only")
class OfficialLaunchTkTests(unittest.TestCase):
    def test_real_open_button_requires_consent_and_uses_pinned_homepage(self):
        ui = VarynDesktop(controller=DesktopController())
        try:
            ui.withdraw()
            ui.official_relay_target.set("gemini")
            nodes = [ui]
            open_button = None
            while nodes:
                parent = nodes.pop()
                for child in parent.winfo_children():
                    if (isinstance(child, ttk.Button) and child.cget("text") ==
                            "17S-23 | Open selected official app in browser"):
                        open_button = child
                    nodes.append(child)
            self.assertIsNotNone(open_button)
            with patch("varyn.desktop.messagebox.askyesno",
                       return_value=False) as consent, \
                 patch("varyn.desktop.webbrowser.open_new_tab") as browser:
                open_button.invoke()
            self.assertEqual(consent.call_count, 1)
            browser.assert_not_called()
            self.assertEqual(ui._official_relay.status()["hops_used"], 0)

            with patch("varyn.desktop.messagebox.askyesno",
                       return_value=True) as consent, \
                 patch("varyn.desktop.webbrowser.open_new_tab",
                       return_value=True) as browser:
                open_button.invoke()
            self.assertEqual(consent.call_count, 1)
            browser.assert_called_once_with("https://gemini.google.com/")
            self.assertEqual(ui.controller.status()["requests_used"], 0)
            self.assertEqual(ui._official_relay.status()["provider_requests"], 0)
            self.assertEqual(ui._official_relay.status()["hops_used"], 0)
        finally:
            ui._close()


if __name__ == "__main__":
    unittest.main()
