"""17S-40 real hosted Windows Tk owner controls, no network in CI."""
import json
import os
import time
import unittest
from tkinter import ttk
from unittest.mock import patch

from varyn.desktop import VarynDesktop
from varyn.desktop_controller import DesktopController
from varyn.model_control_center import ModelControlCenter


def drain(ui, center, *, timeout=3):
    end = time.monotonic() + timeout
    while center._running and time.monotonic() < end:
        ui.update()
        time.sleep(0.02)
    ui.update()
    if center._running:
        raise AssertionError("Synthetic model-center worker never completed")


@unittest.skipUnless(os.name == "nt", "Real hosted Windows Tk only")
class ModelControlCenterTkTests(unittest.TestCase):
    def _new(self, *, live=False):
        ui = VarynDesktop(
            controller=DesktopController(allow_live_providers=live),
        )
        ui.withdraw()
        return ui

    def test_actual_main_button_fake_route_review_and_ram_discard(self):
        ui = self._new()
        try:
            controls, pending = {}, [ui]
            while pending:
                node = pending.pop()
                for child in node.winfo_children():
                    pending.append(child)
                    if isinstance(child, ttk.Button):
                        controls[child.cget("text")] = child
            key = "17S-40 | Open Model Control Center (owner opt-in)"
            self.assertIn(key, controls)
            controls[key].invoke()
            center = ui._model_center
            self.assertTrue(center.winfo_exists())
            self.assertIsNone(ui._relay_workbench)
            self.assertFalse(center.network.get())
            self.assertFalse(center.upstream.get())
            self.assertFalse(center.reviewed.get())
            self.assertEqual(center._offers, [])

            center._add()
            self.assertEqual(center._offers, [])
            self.assertIn("BLOCKED", center.status.get())

            center.reviewed.set(True)
            center.fixed.set(True)
            center._add()
            self.assertEqual(len(center._offers), 1)
            self.assertFalse(center.reviewed.get())
            self.assertFalse(center.fixed.get())
            center._preview()
            self.assertIn("PREVIEW ONLY", center.status.get())
            self.assertEqual(ui.controller.status()["requests_used"], 0)

            with patch.object(ui, "_review_scrollable_manual_text",
                              return_value=False) as deny:
                center._send()
            self.assertEqual(deny.call_count, 1)
            self.assertIn("Request declined", center.status.get())
            self.assertEqual(center._budget.snapshot()["requests_reserved"], 0)
            self.assertEqual(ui.controller.status()["requests_used"], 0)

            with patch.object(ui, "_review_scrollable_manual_text",
                              return_value=True) as permit:
                center._send()
            self.assertEqual(permit.call_count, 1)
            self.assertIn("One NEW fake", permit.call_args.kwargs["heading"])
            drain(ui, center)
            self.assertIn("FAKE:", center.answer.get("1.0", "end-1c"))
            self.assertEqual(center._budget.snapshot()["requests_reserved"], 1)
            self.assertEqual(ui.controller.status()["requests_used"], 0)
            center._dismiss()
            self.assertIsNone(ui._model_center)
            self.assertEqual(center._offers, [])
            self.assertEqual(ui._universal_model_budget.snapshot()["requests_reserved"], 1)
            ui._open_model_control_center()
            self.assertEqual(ui._model_center._offers, [])
            self.assertFalse(ui._model_center.network.get())
            self.assertEqual(ui._model_center._budget.snapshot()["requests_reserved"], 1)
        finally:
            ui._close()

    def test_live_api_approval_denial_then_one_mocked_request(self):
        ui = self._new(live=True)
        calls = []
        try:
            ui._open_model_control_center()
            center = ui._model_center
            def transport(provider, payload, key, timeout):
                calls.append((provider, payload, key, timeout))
                return json.dumps({
                    "choices": [{"finish_reason": "stop",
                                 "message": {"role": "assistant",
                                             "content": "SYNTHETIC MOCK RESPONSE"}}],
                    "usage": {"prompt_tokens": 11, "completion_tokens": 5},
                }).encode()
            center._transport = transport
            center.provider.set("deepseek")
            center.model.set("deepseek-chat")
            center.input_price.set("0.1")
            center.output_price.set("0.2")
            center.ceiling.set("0.10")
            center.reviewed.set(True)
            center.fixed.set(True)
            center._add()
            self.assertEqual(len(center._offers), 1)

            with patch.object(ui, "_review_scrollable_manual_text") as approval:
                center._send()
            approval.assert_not_called()
            self.assertEqual(len(calls), 0)
            center.network.set(True)

            def deny(preview):
                raise AssertionError("Unexpected signature")
            with patch.object(ui, "_review_scrollable_manual_text", return_value=False):
                center._send()
            self.assertEqual(len(calls), 0)
            self.assertEqual(center._budget.snapshot()["requests_reserved"], 0)
            self.assertTrue(center.network.get())

            with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "SYNTHETIC_KEY_FAKE"}), \
                 patch.object(ui, "_review_scrollable_manual_text",
                              return_value=True) as permission:
                center._send()
                drain(ui, center)
            self.assertEqual(len(calls), 1)
            self.assertEqual(calls[0][0], "deepseek")
            self.assertEqual(calls[0][1]["model"], "deepseek-chat")
            self.assertNotIn("SYNTHETIC_KEY_FAKE", str(calls[0][1]))
            self.assertEqual(calls[0][2], "SYNTHETIC_KEY_FAKE")
            self.assertTrue(permission.call_args.kwargs["content"].find(
                "actual_bill_hard_cap"
            ) >= 0)
            self.assertEqual(center._budget.snapshot()["requests_reserved"], 1)
            self.assertFalse(center.network.get())
            self.assertFalse(center.upstream.get())
            self.assertIn("SYNTHETIC MOCK RESPONSE",
                          center.answer.get("1.0", "end-1c"))
            self.assertEqual(ui.controller.status()["requests_used"], 0)
        finally:
            ui._close()

    def test_offline_desktop_blocks_even_if_toggle_enabled(self):
        ui = self._new(live=False)
        try:
            ui._open_model_control_center()
            center = ui._model_center
            center.provider.set("openrouter")
            center.model.set("openrouter/free")
            center.reviewed.set(True)
            center.fixed.set(True)
            center._add()
            center.network.set(True)
            with patch.object(ui, "_review_scrollable_manual_text") as approve:
                center._send()
            approve.assert_not_called()
            self.assertEqual(center._budget.snapshot()["requests_reserved"], 0)
            self.assertIn("BLOCKED", center.status.get())
        finally:
            ui._close()


if __name__ == "__main__":
    unittest.main()
