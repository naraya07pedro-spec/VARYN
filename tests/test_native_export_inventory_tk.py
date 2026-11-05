"""17S-31: hosted Windows actual Tk consent before private ZIP metadata access.

The test uses only a synthetic ZIP created by the test. No real user file,
browser login, conversation content, app sync or provider network request.
"""
from pathlib import Path
import sys
import tempfile
from tkinter import ttk
import unittest
from unittest.mock import patch
import zipfile

from varyn.desktop import VarynDesktop
from varyn.desktop_controller import DesktopController


def find_button(root, title):
    stack = [root]
    while stack:
        current = stack.pop()
        for child in current.winfo_children():
            if isinstance(child, ttk.Button) and child.cget("text") == title:
                return child
            stack.append(child)
    raise AssertionError("Missing " + title)


@unittest.skipUnless(sys.platform == "win32", "Hosted Windows actual Tk only")
class NativeZipMetadataTkTests(unittest.TestCase):
    def setUp(self):
        self.ui = VarynDesktop(controller=DesktopController())
        self.ui.withdraw()
        self.ui._open_relay_workbench()
        self.wb = self.ui._relay_workbench
        find_button(
            self.wb,
            "17S-30 | Official one-time ChatGPT/Claude ZIP import to Gemini",
        ).invoke()
        self.guide = self.wb._native_history_window

    def tearDown(self):
        self.ui._close()

    def _inspect(self):
        find_button(
            self.guide,
            "17S-31 | Inspect selected ZIP metadata locally (optional)",
        ).invoke()

    def test_denied_initial_read_does_not_open_file_picker_or_zip(self):
        with patch("varyn.native_history_import_gui.messagebox.askyesno",
                   return_value=False), \
             patch("varyn.native_history_import_gui.filedialog.askopenfilename"
                   ) as picker, \
             patch("varyn.native_history_import_gui.inspect_export_zip_metadata"
                   ) as inspector:
            self._inspect()
        picker.assert_not_called()
        inspector.assert_not_called()
        self.assertIsNone(self.guide._metadata_inventory)

    def test_denied_second_review_no_member_or_zip_read(self):
        with patch("varyn.native_history_import_gui.messagebox.askyesno",
                   return_value=True), \
             patch("varyn.native_history_import_gui.filedialog.askopenfilename",
                   return_value="C:/FAKE/secret.zip") as picker, \
             patch.object(self.ui, "_review_scrollable_manual_text",
                          return_value=False) as modal, \
             patch("varyn.native_history_import_gui.inspect_export_zip_metadata"
                   ) as inspector:
            self._inspect()
        picker.assert_called_once()
        modal.assert_called_once()
        inspector.assert_not_called()
        self.assertIsNone(self.guide._metadata_inventory)
        self.assertIn("No ZIP read", self.guide.status_line.get())

    def test_actual_synthetic_zip_inventory_after_two_approvals_no_upload(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "PRIVATE_PATH_NOT_IN_REPORT.zip"
            with zipfile.ZipFile(path, mode="w") as archive:
                archive.writestr(
                    "conversations.json",
                    b"PRIVATE_CHAT_CONTENT_CANNOT_LEAK",
                )
                archive.writestr("assets/picture.png", b"binary")
            with patch("varyn.native_history_import_gui.messagebox.askyesno",
                       return_value=True), \
                 patch("varyn.native_history_import_gui.filedialog.askopenfilename",
                       return_value=str(path)), \
                 patch.object(self.ui, "_review_scrollable_manual_text",
                              return_value=True), \
                 patch("varyn.native_history_import_gui.webbrowser.open_new_tab"
                       ) as browser:
                self._inspect()
            browser.assert_not_called()
            result = self.guide._metadata_inventory
            self.assertEqual(result["zip_entry_count"], 2)
            self.assertEqual(result["chatgpt_named_conversation_json_hints"], 1)
            self.assertFalse(result["archive_member_payloads_read"])
            self.assertFalse(result["user_history_persisted"])
            self.assertFalse(result["automatic_bidirectional_sync_verified"])
            self.assertNotIn(str(path), self.guide.status_line.get())
            self.assertNotIn("PRIVATE_CHAT_CONTENT", self.guide.status_line.get())
            self.assertNotIn("PRIVATE_PATH", self.guide.status_line.get())
            find_button(
                self.guide, "Reset attempt and acknowledgements",
            ).invoke()
            self.assertIsNone(self.guide._metadata_inventory)

    def test_changed_source_during_second_approval_refuses_zip_scan(self):
        def change_during_review(**kwargs):
            self.guide.source.set("claude")
            return True
        with patch("varyn.native_history_import_gui.messagebox.askyesno",
                   return_value=True), \
             patch("varyn.native_history_import_gui.filedialog.askopenfilename",
                   return_value="C:/FAKE/export.zip"), \
             patch.object(self.ui, "_review_scrollable_manual_text",
                          side_effect=change_during_review), \
             patch("varyn.native_history_import_gui.inspect_export_zip_metadata"
                   ) as inspector:
            self._inspect()
        inspector.assert_not_called()
        self.assertIsNone(self.guide._metadata_inventory)


if __name__ == "__main__":
    unittest.main()
