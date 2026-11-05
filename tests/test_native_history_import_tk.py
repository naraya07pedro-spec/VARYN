"""17S-30: hosted Windows Tk controls, no actual provider account or file I/O.

Scripted Button.invoke and mocked webbrowser/consents are NOT human
attestation or proof of native Gemini ZIP import.
"""
import sys
from tkinter import ttk
import unittest
from unittest.mock import patch

from varyn.desktop import VarynDesktop
from varyn.desktop_controller import DesktopController
from varyn.native_history_import_gui import NativeHistoryImportGuide


def find_button(root, label):
    nodes = [root]
    while nodes:
        current = nodes.pop()
        for child in current.winfo_children():
            if isinstance(child, ttk.Button) and child.cget("text") == label:
                return child
            nodes.append(child)
    raise AssertionError("Cannot find " + label)


@unittest.skipUnless(sys.platform == "win32", "Hosted native Windows Tk only")
class NativeImportGuiTests(unittest.TestCase):
    def setUp(self):
        self.ui = VarynDesktop(controller=DesktopController())
        self.ui.withdraw()
        self.ui._open_relay_workbench()
        self.workbench = self.ui._relay_workbench
        find_button(
            self.workbench,
            "17S-30 | Official one-time ChatGPT/Claude ZIP import to Gemini"
        ).invoke()
        self.guide = self.workbench._native_history_window
        self.assertIsInstance(self.guide, NativeHistoryImportGuide)

    def tearDown(self):
        self.ui._close()

    def _check_all(self):
        self.guide.ack_account.set(True)
        self.guide.ack_region.set(True)
        self.guide.ack_zip.set(True)
        self.guide.ack_privacy.set(True)

    def test_singleton_and_default_no_upload_or_browser(self):
        find_button(
            self.workbench,
            "17S-30 | Official one-time ChatGPT/Claude ZIP import to Gemini"
        ).invoke()
        self.assertIs(self.guide, self.workbench._native_history_window)
        self.assertFalse(self.guide.ack_zip.get())
        self.assertFalse(self.guide._session.status()[
            "official_browser_launch_requested"])
        with patch("varyn.native_history_import_gui.webbrowser.open_new_tab") as browser:
            find_button(
                self.guide, "5. Review and open official Gemini import page"
            ).invoke()
        browser.assert_not_called()
        self.assertIn("BLOCKED", self.guide.status_line.get())
        self.assertFalse(self.guide._session.status()["zip_read_by_varyn"])

    def test_source_instructions_consent_and_exact_pinned_url(self):
        self.guide.source.set("claude")
        with patch("varyn.native_history_import_gui.messagebox.askyesno",
                   return_value=False), \
             patch("varyn.native_history_import_gui.webbrowser.open_new_tab") as browser:
            find_button(
                self.guide, "1. Read OFFICIAL export instructions"
            ).invoke()
        browser.assert_not_called()
        with patch("varyn.native_history_import_gui.messagebox.askyesno",
                   return_value=True), \
             patch("varyn.native_history_import_gui.webbrowser.open_new_tab",
                   return_value=True) as browser:
            find_button(
                self.guide, "1. Read OFFICIAL export instructions"
            ).invoke()
        browser.assert_called_once_with(
            "https://support.claude.com/en/articles/9450526-export-your-claude-data"
        )

    def test_exclusive_consent_controls_gemini_native_browser_open(self):
        self._check_all()
        self.guide.source.set("chatgpt")
        with patch.object(self.ui, "_review_scrollable_manual_text",
                          return_value=True) as approved, \
             patch("varyn.native_history_import_gui.webbrowser.open_new_tab",
                   return_value=True) as browser:
            find_button(
                self.guide, "5. Review and open official Gemini import page"
            ).invoke()
        approved.assert_called_once()
        self.assertIn("Google Activity", approved.call_args.kwargs["content"])
        self.assertIn("Gemini", approved.call_args.kwargs["title"])
        browser.assert_called_once_with("https://gemini.google.com/")
        status = self.guide._session.status()
        self.assertTrue(status["official_browser_launch_requested"])
        self.assertFalse(status["provider_side_import_verified"])
        self.assertFalse(status["zip_read_by_varyn"])
        self.assertFalse(status["automatic_bidirectional_consumer_sync_verified"])
        self.assertEqual(self.ui.controller.status()["requests_used"], 0)
        self.guide.result.set("owner_reported_uploaded")
        find_button(self.guide, "Record self-report in RAM").invoke()
        self.assertEqual(self.guide._session.status()["owner_unverified_result"],
                         "owner_reported_uploaded")
        self.assertFalse(self.guide._session.status()["provider_side_import_verified"])
        find_button(self.guide, "Reset attempt and acknowledgements").invoke()
        self.assertFalse(self.guide.ack_privacy.get())
        self.assertFalse(self.guide._session.status()["official_browser_launch_requested"])

    def test_declined_source_change_and_privacy_change_do_not_open_browser(self):
        self._check_all()
        with patch.object(self.ui, "_review_scrollable_manual_text",
                          return_value=False), \
             patch("varyn.native_history_import_gui.webbrowser.open_new_tab") as browser:
            find_button(
                self.guide, "5. Review and open official Gemini import page"
            ).invoke()
        browser.assert_not_called()
        self._check_all()
        def mutate_source(**kwargs):
            self.guide.source.set("claude")
            return True
        with patch.object(self.ui, "_review_scrollable_manual_text",
                          side_effect=mutate_source), \
             patch("varyn.native_history_import_gui.webbrowser.open_new_tab") as browser:
            find_button(
                self.guide, "5. Review and open official Gemini import page"
            ).invoke()
        browser.assert_not_called()
        self.assertIn("Source changed", self.guide.status_line.get())
        self._check_all()
        def mutate_consent(**kwargs):
            self.guide.ack_privacy.set(False)
            return True
        with patch.object(self.ui, "_review_scrollable_manual_text",
                          side_effect=mutate_consent), \
             patch("varyn.native_history_import_gui.webbrowser.open_new_tab") as browser:
            find_button(
                self.guide, "5. Review and open official Gemini import page"
            ).invoke()
        browser.assert_not_called()
        self.assertIn("changed", self.guide.status_line.get())

    def test_closing_guide_does_not_destroy_workbench(self):
        self.guide._dismiss()
        self.assertIsNone(self.workbench._native_history_window)
        self.assertTrue(self.workbench.winfo_exists())
        self.assertEqual(self.guide._session.status()["owner_unverified_result"],
                         "not_reported")


if __name__ == "__main__":
    unittest.main()
