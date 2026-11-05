"""17S-37: hosted Windows Tk exact consent, DPAPI archive reopen, no relay restore."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from varyn.desktop import VarynDesktop
from varyn.desktop_controller import DesktopController
from varyn.three_app_archive import load_readonly


@unittest.skipUnless(os.name == "nt", "native Windows Tk and DPAPI only")
class ArchiveWindowsTkTests(unittest.TestCase):
    def test_denial_save_and_readonly_reopen_after_workbench_exit(self):
        ui = VarynDesktop(controller=DesktopController(allow_live_providers=False))
        try:
            ui.withdraw()
            ui._open_relay_workbench()
            wb = ui._relay_workbench
            with patch("varyn.official_relay_workbench.filedialog.asksaveasfilename") as choose:
                wb._save_three_app_archive()
            choose.assert_not_called()
            wb._start_guided()
            for i, app in enumerate(("chatgpt", "claude", "gemini")):
                with patch.object(ui, "_review_manual_relay_packet", return_value=True):
                    wb._copy()
                self.assertEqual(ui._official_relay.status()["hops_used"], i+1)
                wb.reply.delete("1.0", "end")
                wb.reply.insert("1.0", "SYNTHETIC: imaginary " + app)
                with patch.object(ui, "_review_manual_reply_text", return_value=True):
                    wb._accept_reply()
                if i < 2:
                    wb._advance_guided()
            self.assertEqual(wb._guided_flow.phase, "completed")
            with tempfile.TemporaryDirectory() as folder:
                path = Path(folder) / "completed.varyn-archive"
                with patch.object(ui, "_review_scrollable_manual_text", return_value=False), \
                     patch("varyn.official_relay_workbench.filedialog.asksaveasfilename") as choose:
                    wb._save_three_app_archive()
                choose.assert_not_called()
                self.assertFalse(path.exists())
                with patch.object(ui, "_review_scrollable_manual_text", return_value=True), \
                     patch("varyn.official_relay_workbench.filedialog.asksaveasfilename",
                           return_value=str(path)):
                    wb._save_three_app_archive()
                self.assertEqual(len(load_readonly(path)["records"]), 3)
                self.assertNotIn(b"SYNTHETIC: imaginary", path.read_bytes())
                wb._dismiss()
                ui._discard_official_app_relay()
                ui._open_relay_workbench()
                other = ui._relay_workbench
                self.assertEqual(other._guided_flow.ledger.count, 0)
                with patch.object(ui, "_review_scrollable_manual_text", return_value=False), \
                     patch("varyn.official_relay_workbench.filedialog.askopenfilename",
                           return_value=str(path)):
                    other._open_three_app_archive()
                self.assertIsNone(other._saved_archive_window)
                with patch.object(ui, "_review_scrollable_manual_text", return_value=True), \
                     patch("varyn.official_relay_workbench.filedialog.askopenfilename",
                           return_value=str(path)):
                    other._open_three_app_archive()
                self.assertTrue(other._saved_archive_window.winfo_exists())
                self.assertIn("READ-ONLY", other._saved_archive_window.title())
                self.assertEqual(ui._official_relay.status()["hops_used"], 0)
                self.assertFalse(ui._official_relay.status()["awaiting_user_pasteback"])
                self.assertFalse(other._guided_flow.active)
                self.assertEqual(other._guided_flow.ledger.count, 0)
                self.assertEqual(ui.controller.status()["requests_used"], 0)
                other._clear_saved_archive_view()
                self.assertIsNone(other._saved_archive_window)
        finally:
            ui._close()


if __name__ == "__main__":
    unittest.main()
