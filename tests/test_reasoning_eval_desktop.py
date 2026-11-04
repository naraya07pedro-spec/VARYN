"""17Q desktop controls for user-authored offline literal audit."""
import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from varyn.desktop import VarynDesktop


class EvalDesktopStub:
    def __init__(self, report):
        self._busy = False
        self._closing = False
        self._last_collaboration = report
        self.messages = []

    def _append(self, label, message):
        self.messages.append((label, message))


def report():
    return {
        "format": "varyn.collaboration.v1",
        "status": "completed",
        "stages": [
            {"role": "analyst", "text": "Offline baseline"},
            {"role": "critic", "text": "Missing consent"},
            {"role": "synthesizer", "text": "Offline with consent and backup"},
        ],
        "final_answer": "Offline with consent and backup",
        "multi_model_review": False,
    }


class DesktopReasoningEvalTests(unittest.TestCase):
    def test_owner_supplied_rubric_produces_local_diagnostic(self):
        ui = EvalDesktopStub(report())
        text = json.dumps({
            "case_id": "example", "required": ["offline", "consent"],
            "forbidden": [], "alternatives": ["backup"],
        })
        with patch("varyn.desktop.simpledialog.askstring", return_value=text) as dialog:
            VarynDesktop._evaluate_collaboration(ui)
        dialog.assert_called_once()
        self.assertEqual(len(ui.messages), 1)
        result = ui.messages[0][1]
        self.assertIn("analyst literal coverage 1/2", result)
        self.assertIn("synthesis 2/2", result)
        self.assertIn("Not a controlled A/B", result)
        self.assertIn("NOT established", result)

    def test_malformed_rubric_fails_closed(self):
        ui = EvalDesktopStub(report())
        with patch("varyn.desktop.simpledialog.askstring", return_value="not json"):
            VarynDesktop._evaluate_collaboration(ui)
        self.assertIn("Invalid bounded rubric", str(ui.messages))
        self.assertNotIn("2/2", str(ui.messages))

    def test_cancel_does_not_log_or_score(self):
        ui = EvalDesktopStub(report())
        with patch("varyn.desktop.simpledialog.askstring", return_value=None):
            VarynDesktop._evaluate_collaboration(ui)
        self.assertEqual(ui.messages, [])

    def test_disabled_without_last_completed_collaboration(self):
        ui = EvalDesktopStub(None)
        with patch("varyn.desktop.simpledialog.askstring") as dialog:
            VarynDesktop._evaluate_collaboration(ui)
        dialog.assert_not_called()
        self.assertIn("No completed collaboration", str(ui.messages))

    def test_busy_or_closed_refuses_opening_dialog(self):
        ui = EvalDesktopStub(report())
        for attr in ("_busy", "_closing"):
            setattr(ui, attr, True)
            with patch("varyn.desktop.simpledialog.askstring") as dialog:
                VarynDesktop._evaluate_collaboration(ui)
            dialog.assert_not_called()
            setattr(ui, attr, False)


if __name__ == "__main__":
    unittest.main()
