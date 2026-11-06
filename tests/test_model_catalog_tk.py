"""17S-43: actual Windows Tk discovery review and model ID staging, NO APIs."""
import os
import time
import unittest
from unittest.mock import patch

from varyn.desktop import VarynDesktop
from varyn.desktop_controller import DesktopController
from varyn.model_discovery import parse_catalog


def drain(owner, catalog):
    deadline = time.monotonic() + 5
    while catalog._running and time.monotonic() < deadline:
        owner.update()
        time.sleep(0.015)
    owner.update()
    if catalog._running:
        raise AssertionError("Synthetic catalog did not settle")


def response():
    return parse_catalog(b'{"data":[{"id":"qwen/synthetic-32b","pricing":{"prompt":"0"}},'
                         b'{"id":"deepseek-synthetic"},{"id":"../malicious"}]}')


@unittest.skipUnless(os.name == "nt", "Windows real Tk only")
class OwnerCatalogNativeTk(unittest.TestCase):
    def test_denied_then_approved_one_get_and_no_free_quote_assumption(self):
        ui = VarynDesktop(controller=DesktopController(allow_live_providers=True))
        ui.withdraw()
        calls = []
        try:
            ui._open_model_control_center()
            center = ui._model_center
            center._open_catalog()
            catalog = center._catalog_window
            self.assertTrue(catalog.winfo_exists())
            self.assertTrue(center._catalog_lock)
            self.assertFalse(center._allowed())
            self.assertFalse(catalog.allow_network.get())
            self.assertFalse(catalog.authorize_upstream.get())
            self.assertEqual(catalog.models.size(), 0)
            self.assertFalse(catalog._attempted)
            catalog.provider.set("openrouter")
            def transport(provider, key, timeout):
                calls.append((provider, key, timeout))
                return response()
            catalog._transport = transport
            with patch.dict(os.environ, {"OPENROUTER_API_KEY": "SYNTHETIC-INVALID-NO-API"}):
                with patch.object(ui, "_review_scrollable_manual_text") as review:
                    catalog._request_models()
                review.assert_not_called()
                self.assertEqual(calls, [])
                self.assertIn("BLOCKED", catalog.status.get())
                catalog.allow_network.set(True)
                with patch.object(ui, "_review_scrollable_manual_text",
                                  return_value=False) as review:
                    catalog._request_models()
                review.assert_called_once()
                self.assertIn("GET /models", review.call_args.kwargs["heading"])
                self.assertNotIn("SYNTHETIC-INVALID-NO-API",
                                 review.call_args.kwargs["content"])
                self.assertFalse(catalog._attempted)
                self.assertEqual(calls, [])
                with patch.object(ui, "_review_scrollable_manual_text",
                                  return_value=True):
                    catalog._request_models()
                    drain(ui, catalog)
            self.assertEqual(len(calls), 1)
            self.assertEqual(calls[0][0], "openrouter")
            self.assertEqual(catalog.models.size(), 2)
            self.assertIn("UNTRUSTED", catalog.status.get())
            self.assertFalse(catalog.allow_network.get())
            self.assertTrue(catalog._attempted)
            catalog.allow_network.set(True)
            with patch.object(ui, "_review_scrollable_manual_text") as review:
                catalog._request_models()
            review.assert_not_called()
            self.assertEqual(len(calls), 1)
            catalog.models.selection_set(1)
            catalog._use_selected()
            self.assertIsNone(center._catalog_window)
            self.assertFalse(center._catalog_lock)
            self.assertEqual(center.provider.get(), "openrouter")
            self.assertEqual(center.model.get(), "qwen/synthetic-32b")
            self.assertEqual(center.input_price.get(), "")
            self.assertEqual(center.output_price.get(), "")
            self.assertFalse(center.reviewed.get())
            self.assertFalse(center.fixed.get())
            self.assertFalse(center.network.get())
            self.assertEqual(center._offers, [])
            center._add()
            self.assertEqual(center._offers, [])
            self.assertIn("BLOCKED", center.status.get())
            self.assertEqual(center._budget.snapshot()["requests_reserved"], 0)
        finally:
            ui._close()

    def test_offline_desktop_and_9router_upstream_permissions(self):
        ui = VarynDesktop(controller=DesktopController(allow_live_providers=False))
        ui.withdraw()
        try:
            ui._open_model_control_center()
            c = ui._model_center
            c._open_catalog()
            win = c._catalog_window
            win.provider.set("deepseek")
            win.allow_network.set(True)
            with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "SYNTHETIC"}), \
                 patch.object(ui, "_review_scrollable_manual_text") as review:
                win._request_models()
            review.assert_not_called()
            self.assertIn("BLOCKED", win.status.get())
            win._dismiss()
            self.assertFalse(c._catalog_lock)
            c._open_catalog()
            self.assertIsNot(win, c._catalog_window)
            c._catalog_window._dismiss()
        finally:
            ui._close()

    def test_9router_upstream_authorization_required_before_review(self):
        ui = VarynDesktop(controller=DesktopController(allow_live_providers=True))
        ui.withdraw()
        try:
            ui._open_model_control_center()
            c = ui._model_center
            c._open_catalog()
            win = c._catalog_window
            win.provider.set("9router")
            win.allow_network.set(True)
            with patch.dict(os.environ, {"VARYN_9ROUTER_API_KEY": "SYNTHETIC"}), \
                 patch.object(ui, "_review_scrollable_manual_text") as review:
                win._request_models()
            review.assert_not_called()
            self.assertIn("BLOCKED", win.status.get())
            self.assertFalse(win._attempted)
        finally:
            ui._close()


if __name__ == "__main__":
    unittest.main()
