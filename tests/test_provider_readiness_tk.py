"""17S-41 hosted Windows native Tk readiness, owner receipt review/save."""
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from varyn.desktop import VarynDesktop
from varyn.desktop_controller import DesktopController
from varyn.provider_readiness import FORMAT


def drain(owner, center):
    deadline = time.monotonic() + 4
    while center._running and time.monotonic() < deadline:
        owner.update()
        time.sleep(0.02)
    owner.update()
    if center._running:
        raise AssertionError("Local synthetic model-center request did not complete")


@unittest.skipUnless(os.name == "nt", "Native hosted Windows Tk required")
class LocalModelAcceptanceWindowsTk(unittest.TestCase):
    def test_ready_without_network_then_save_metadata_only_after_explicit_review(self):
        ui = VarynDesktop(controller=DesktopController(allow_live_providers=True))
        ui.withdraw()
        try:
            ui._open_model_control_center()
            center = ui._model_center
            self.assertFalse(center.network.get())
            self.assertIsNone(center._last_receipt)
            self.assertIn("disabled", center.receipt_button.state())
            center.provider.set("deepseek")
            center.model.set("deepseek-flash")
            center.reviewed.set(True)
            center.fixed.set(True)
            center._add()
            center._check_readiness()
            self.assertIn("NOT READY", center.status.get())
            self.assertIn("DEEPSEEK_API_KEY", center.status.get())
            self.assertNotIn("FAKE-OWNER-KEY", center.status.get())
            center.network.set(True)
            with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "FAKE-OWNER-KEY"}):
                center._check_readiness()
                self.assertIn("READY FOR ONE", center.status.get())
                self.assertIn("NOT CONNECTED/VERIFIED", center.status.get())
                self.assertEqual(center._budget.snapshot()["requests_reserved"], 0)
                # Use a mock at the fixed transport seam; NO real internet.
                def synthetic_post(provider, payload, key, timeout):
                    self.assertEqual(provider, "deepseek")
                    self.assertEqual(key, "FAKE-OWNER-KEY")
                    self.assertEqual(payload["model"], "deepseek-flash")
                    return json.dumps({
                        "model": "proxy/upstream-claimed",
                        "choices": [{
                            "finish_reason": "stop",
                            "message": {
                                "role": "assistant",
                                "content": "SYNTHETIC: MOCK PRIVATE RETURN TEXT",
                            },
                        }],
                        "usage": {"prompt_tokens": 14, "completion_tokens": 9},
                    }).encode()
                with patch("varyn.universal_gateway.post",
                           side_effect=synthetic_post) as post, \
                     patch.object(ui, "_review_scrollable_manual_text",
                                  return_value=True):
                    center._send()
                    drain(ui, center)
                post.assert_called_once()
            self.assertFalse(center.network.get())
            self.assertEqual(center._budget.snapshot()["requests_reserved"], 1)
            self.assertIn("MODEL LABEL DIFFERS", center.status.get())
            self.assertIsNotNone(center._last_receipt)
            self.assertNotIn("disabled", center.receipt_button.state())
            with tempfile.TemporaryDirectory() as folder:
                receipt_path = Path(folder) / "local-observation.json"
                with patch.object(ui, "_review_scrollable_manual_text",
                                  return_value=False) as review, \
                     patch("varyn.model_control_center.filedialog.asksaveasfilename") as pick:
                    center._save_receipt()
                review.assert_called_once()
                self.assertIn("provider_reported_model_UNVERIFIED",
                              review.call_args.kwargs["content"])
                pick.assert_not_called()
                self.assertFalse(receipt_path.exists())
                with patch.object(ui, "_review_scrollable_manual_text",
                                  return_value=True), \
                     patch("varyn.model_control_center.filedialog.asksaveasfilename",
                           return_value=str(receipt_path)):
                    center._save_receipt()
                self.assertTrue(receipt_path.is_file())
                text = receipt_path.read_text(encoding="utf-8")
                data = json.loads(text)
                self.assertEqual(data["format"], FORMAT)
                self.assertEqual(data["selected_provider"], "deepseek")
                self.assertFalse(data["provider_identity_authenticated"])
                self.assertFalse(data["native_consumer_app_history_synced"])
                self.assertFalse(data["selected_model_equals_reported"])
                self.assertEqual(
                    data["provider_reported_model_UNVERIFIED"],
                    "proxy/upstream-claimed",
                )
                for secret in ("FAKE-OWNER-KEY",
                               "SYNTHETIC: MOCK PRIVATE RETURN TEXT",
                               center.task.get("1.0", "end-1c")):
                    self.assertNotIn(secret, text)
                before = receipt_path.read_bytes()
                with patch.object(ui, "_review_scrollable_manual_text",
                                  return_value=True), \
                     patch("varyn.model_control_center.filedialog.asksaveasfilename",
                           return_value=str(receipt_path)):
                    center._save_receipt()
                self.assertIn("BLOCKED", center.status.get())
                self.assertEqual(receipt_path.read_bytes(), before)
            center._clear()
            self.assertIsNone(center._last_receipt)
            self.assertIn("disabled", center.receipt_button.state())
        finally:
            ui._close()

    def test_fake_can_never_create_a_provider_receipt(self):
        ui = VarynDesktop(controller=DesktopController(allow_live_providers=False))
        ui.withdraw()
        try:
            ui._open_model_control_center()
            c = ui._model_center
            c.reviewed.set(True)
            c.fixed.set(True)
            c._add()
            c._check_readiness()
            self.assertIn("FAKE only", c.status.get())
            with patch.object(ui, "_review_scrollable_manual_text",
                              return_value=True):
                c._send()
                drain(ui, c)
            self.assertIsNone(c._last_receipt)
            self.assertIn("disabled", c.receipt_button.state())
        finally:
            ui._close()


if __name__ == "__main__":
    unittest.main()
