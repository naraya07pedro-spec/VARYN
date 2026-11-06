"""17S-42: frozen portable Model Control Center contract and hosted real Tk."""
import os
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from varyn.frozen_model_center_smoke import (
    FrozenModelSmokeRejected, synthetic_center_acceptance,
)


class FrozenCenterPreflightTests(unittest.TestCase):
    def test_refuses_missing_owner_and_live_capable_owner(self):
        with self.assertRaises(FrozenModelSmokeRejected):
            synthetic_center_acceptance(None)
        for live, closing in ((True, False), (False, True)):
            with self.subTest(live=live, closing=closing):
                with self.assertRaises(FrozenModelSmokeRejected):
                    synthetic_center_acceptance(SimpleNamespace(
                        _closing=closing,
                        _universal_model_live_capability=live,
                    ))

    def test_refuses_missing_model_center_or_non_offline_controller(self):
        class Controller:
            def status(self):
                return {"mode": "opt_in_live_available"}
        owner = SimpleNamespace(
            _closing=False, _universal_model_live_capability=False,
            controller=Controller(), _model_center=None,
        )
        with self.assertRaises(FrozenModelSmokeRejected):
            synthetic_center_acceptance(owner)
        owner.controller = type("Offline", (), {
            "status": lambda self: {"mode": "offline_simulation"},
        })()
        with self.assertRaises(FrozenModelSmokeRejected):
            synthetic_center_acceptance(owner)


@unittest.skipUnless(os.name == "nt", "Native hosted Windows Tk required")
class FrozenCenterNativeTkTests(unittest.TestCase):
    def test_true_tk_fixed_fake_review_denial_and_offline_api_refusal(self):
        from varyn.desktop import VarynDesktop
        from varyn.desktop_controller import DesktopController
        owner = VarynDesktop(
            controller=DesktopController(allow_live_providers=False),
        )
        try:
            owner.withdraw()
            owner._open_model_control_center()
            with patch("varyn.gateway_chat.post", side_effect=AssertionError(
                    "Provider transport must NEVER run in frozen synthetic smoke")), \
                 patch("varyn.universal_gateway.post", side_effect=AssertionError(
                    "Model gateway must NEVER call external provider")):
                result = synthetic_center_acceptance(owner)
            self.assertEqual(
                result["format"], "varyn.frozen_model_center_synthetic.v1"
            )
            self.assertTrue(result["unreviewed_quote_denied"])
            self.assertTrue(result["fake_review_rejected"])
            self.assertTrue(result["one_mock_owner_approved_fake_execution"])
            self.assertTrue(result["live_model_dispatch_denied"])
            self.assertTrue(result["model_catalog_default_off"])
            self.assertTrue(result["model_catalog_network_denied"])
            self.assertFalse(result["operator_personally_approved"])
            self.assertFalse(result["actual_provider_api_tested"])
            self.assertEqual(result["external_provider_requests"], 0)
            self.assertIsNone(owner._model_center)
            self.assertEqual(owner._universal_model_budget.snapshot()[
                "requests_reserved"], 1)
            self.assertEqual(owner.controller.status()["requests_used"], 0)
        finally:
            owner._close()


if __name__ == "__main__":
    unittest.main()
