"""17S-38: real hosted Windows Tk selection, opt-in, fresh approval, discard."""
import hashlib
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from varyn.archive_continuation import CONTINUATION_TASK
from varyn.desktop import VarynDesktop
from varyn.desktop_controller import DesktopController
from varyn.guided_reply_ledger import GuidedReplyLedger
from varyn.three_app_archive import snapshot, save_new


def archive_fixture():
    ledger = GuidedReplyLedger()
    for stage, provider in enumerate(("chatgpt", "claude", "gemini"), 1):
        text = "SYNTHETIC: fictional previous " + provider
        rid = format(stage, "032x")
        out = format(stage, "064x")
        reply_digest = hashlib.sha256(
            (rid + "\n" + out + "\n" + text).encode()
        ).hexdigest()
        ledger.record(stage, provider, text, {
            "provider_claim": provider, "manual_only": True,
            "provider_origin_verified": False,
            "outbound_request_id": rid, "outbound_digest": out,
            "reply_digest": reply_digest,
            "local_chain_digest": format(stage, "064x"),
        })
    return snapshot(ledger, phase="completed")


@unittest.skipUnless(os.name == "nt", "real Windows Tk and DPAPI only")
class ArchiveContinuationWindowsTkTests(unittest.TestCase):
    def test_resume_old_archive_as_fresh_owner_approved_manual_task(self):
        ui = VarynDesktop(controller=DesktopController(allow_live_providers=False))
        try:
            ui.withdraw()
            ui._open_relay_workbench()
            wb = ui._relay_workbench
            self.assertIsNone(wb._archived_selection)
            self.assertFalse(wb.include_archived_context.get())
            with tempfile.TemporaryDirectory() as folder:
                path = Path(folder) / "old-session.varyn-archive"
                save_new(path, archive_fixture())
                picker = "varyn.official_relay_workbench.filedialog.askopenfilename"
                with patch.object(ui, "_review_scrollable_manual_text", return_value=False), \
                     patch(picker, return_value=str(path)):
                    wb._select_archive_resume()
                self.assertIsNone(wb._archived_selection)
                self.assertEqual(ui._official_relay.status()["hops_used"], 0)
                with patch.object(ui, "_review_scrollable_manual_text", return_value=True), \
                     patch(picker, return_value=str(path)):
                    wb._select_archive_resume()
                self.assertEqual(wb._archived_selection.claimed_provider, "gemini")
                self.assertEqual(wb._archived_selection.stage, 3)
                self.assertFalse(wb.include_archived_context.get())
                self.assertEqual(wb.task.get("1.0", "end-1c"), CONTINUATION_TASK)
                self.assertEqual(ui.controller.status()["requests_used"], 0)

                # Before the second opt-in, normal denial review has no archive.
                def deny_without_archive(preview):
                    self.assertNotIn(
                        "EXPLICITLY SELECTED READ-ONLY ARCHIVE", preview.packet
                    )
                    return False
                with patch.object(ui, "_review_manual_relay_packet",
                                  side_effect=deny_without_archive):
                    wb._copy()
                self.assertEqual(ui._official_relay.status()["hops_used"], 0)

                wb.include_archived_context.set(True)
                wb.archive_stage.set("2: Claude")
                with patch.object(ui, "_review_manual_relay_packet") as review:
                    wb._copy()
                review.assert_not_called()
                self.assertEqual(ui._official_relay.status()["hops_used"], 0)
                wb.archive_stage.set("3: Gemini")

                def deny_with_archive(preview):
                    self.assertIn(
                        "EXPLICITLY SELECTED READ-ONLY ARCHIVE", preview.packet
                    )
                    self.assertIn("fictional previous gemini", preview.packet)
                    self.assertIn("UNTRUSTED DATA", preview.packet)
                    return False
                with patch.object(ui, "_review_manual_relay_packet",
                                  side_effect=deny_with_archive):
                    wb._copy()
                self.assertEqual(ui._official_relay.status()["hops_used"], 0)

                with patch.object(ui, "_review_manual_relay_packet",
                                  return_value=True):
                    wb._copy()
                self.assertEqual(ui._official_relay.status()["hops_used"], 1)
                self.assertTrue(ui._official_relay.status()["awaiting_user_pasteback"])
                self.assertIn(
                    "EXPLICITLY SELECTED READ-ONLY ARCHIVE", ui.clipboard_get()
                )
                self.assertFalse(wb.include_archived_context.get())
                self.assertIsNone(wb._archived_selection)
                self.assertEqual(ui.controller.status()["requests_used"], 0)

                with patch(picker) as choose:
                    wb._select_archive_resume()
                choose.assert_not_called()
                wb._discard_relay()
                self.assertEqual(ui._official_relay.status()["hops_used"], 0)
                self.assertIsNone(wb._archived_selection)
                self.assertFalse(wb.include_archived_context.get())

                wb.archive_stage.set("1: ChatGPT")
                with patch.object(ui, "_review_scrollable_manual_text",
                                  return_value=True), \
                     patch(picker, return_value=str(path)):
                    wb._select_archive_resume()
                self.assertEqual(wb._archived_selection.stage, 1)
                wb._dismiss()
                ui._open_relay_workbench()
                other = ui._relay_workbench
                self.assertIsNone(other._archived_selection)
                self.assertFalse(other.include_archived_context.get())
                self.assertEqual(ui._official_relay.status()["hops_used"], 0)
        finally:
            ui._close()


if __name__ == "__main__":
    unittest.main()
