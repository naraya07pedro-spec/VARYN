"""17S-33 hosted Windows Tk, real DPAPI and owner review callbacks (scripted)."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from varyn.desktop import VarynDesktop
from varyn.desktop_controller import DesktopController
from varyn.official_draft_resume import load_existing


@unittest.skipUnless(os.name == "nt", "Actual Windows Tk and DPAPI required")
class DraftWorkbenchWindowsTkTests(unittest.TestCase):
    def test_save_restore_and_refusal_without_relay_authority(self):
        ui = VarynDesktop(controller=DesktopController(allow_live_providers=False))
        try:
            ui.withdraw()
            ui._open_relay_workbench()
            wb = ui._relay_workbench
            with tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / "synthetic.varyn"
                wb.target.set("claude")
                wb.project.set("PROJECT_B")
                wb.topic.set("fiction")
                wb.task.delete("1.0", "end")
                wb.task.insert("1.0", "SYNTHETIC: Fictional todo draft.")
                wb.note.delete("1.0", "end")
                wb.note.insert("1.0", "SYNTHETIC: Fictional note.")
                with patch.object(ui, "_review_scrollable_manual_text",
                                  return_value=False), \
                     patch("varyn.official_relay_workbench.filedialog.asksaveasfilename") as picker:
                    wb._save_encrypted_draft()
                picker.assert_not_called()
                self.assertFalse(path.exists())
                with patch.object(ui, "_review_scrollable_manual_text",
                                  return_value=True), \
                     patch("varyn.official_relay_workbench.filedialog.asksaveasfilename",
                           return_value=str(path)):
                    wb._save_encrypted_draft()
                self.assertTrue(path.exists())
                self.assertEqual(load_existing(path)["target"], "claude")
                self.assertNotIn(b"SYNTHETIC:", path.read_bytes())
                wb.target.set("chatgpt")
                wb.project.set("VARYN")
                wb.topic.set("next_step")
                wb.task.delete("1.0", "end")
                wb.task.insert("1.0", "SYNTHETIC: New task.")
                wb.note.delete("1.0", "end")
                wb.note.insert("1.0", "SYNTHETIC: New note.")
                with patch.object(ui, "_review_scrollable_manual_text",
                                  return_value=False), \
                     patch("varyn.official_relay_workbench.filedialog.askopenfilename",
                           return_value=str(path)):
                    wb._restore_encrypted_draft()
                self.assertEqual(wb.target.get(), "chatgpt")
                with patch.object(ui, "_review_scrollable_manual_text",
                                  return_value=True), \
                     patch("varyn.official_relay_workbench.filedialog.askopenfilename",
                           return_value=str(path)):
                    wb._restore_encrypted_draft()
                self.assertEqual(wb.target.get(), "claude")
                self.assertEqual(wb.project.get(), "PROJECT_B")
                self.assertIn("Fictional todo draft.", wb.task.get("1.0", "end-1c"))
                self.assertFalse(wb.include_context.get())
                self.assertEqual(ui._official_relay.status()["hops_used"], 0)
                self.assertEqual(ui.controller.status()["requests_used"], 0)
                self.assertFalse(ui._official_relay.status()["reply_in_ram"])
                # No reopening a file path as if it were an approval token.
                wb.reply.insert("1.0", "SYNTHETIC: unsaved pasted reply")
                with patch("varyn.official_relay_workbench.filedialog.askopenfilename") as picker:
                    wb._restore_encrypted_draft()
                picker.assert_not_called()
        finally:
            ui._close()


if __name__ == "__main__":
    unittest.main()
