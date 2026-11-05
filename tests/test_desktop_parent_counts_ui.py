"""17S-20: Tk callback semantics; simulated decisions, not human proof."""
import unittest
from unittest.mock import patch

from varyn.desktop import VarynDesktop


class FakeOwnerDesktop:
    _busy = False
    _closing = False

    def __init__(self):
        self.messages = []

    def _append(self, sender, message):
        self.messages.append((sender, message))


class OwnerConsentDesktopTests(unittest.TestCase):
    def test_deny_has_no_source_read_and_no_success(self):
        ui = FakeOwnerDesktop()
        with patch("varyn.desktop.messagebox.askyesno", return_value=False) as ask, \
             patch("varyn.parent_synthetic_read_broker.os.read",
                   side_effect=AssertionError("source read without approval")):
            VarynDesktop._review_parent_synthetic_counts(ui)
        self.assertEqual(ask.call_count, 1)
        self.assertIn("Declined", ui.messages[-1][1])
        self.assertNotIn("21", str(ui.messages))

    def test_approve_processes_generated_counts_locally(self):
        ui = FakeOwnerDesktop()
        with patch("varyn.desktop.messagebox.askyesno", return_value=True) as ask:
            VarynDesktop._review_parent_synthetic_counts(ui)
        self.assertEqual(ask.call_count, 1)
        self.assertIn("local integer sum: 21", ui.messages[-1][1])
        self.assertIn("No model", ui.messages[-1][1])

    def test_busy_closed_and_dialog_nested_close_never_dispatch(self):
        for flag in ("_busy", "_closing"):
            ui = FakeOwnerDesktop()
            setattr(ui, flag, True)
            with patch("varyn.desktop.messagebox.askyesno") as ask:
                VarynDesktop._review_parent_synthetic_counts(ui)
            ask.assert_not_called()
            self.assertFalse(ui.messages)
        ui = FakeOwnerDesktop()
        def nested_close(*args, **kwargs):
            ui._closing = True
            return True
        with patch("varyn.desktop.messagebox.askyesno",
                   side_effect=nested_close):
            VarynDesktop._review_parent_synthetic_counts(ui)
        self.assertFalse(ui.messages)


if __name__ == "__main__":
    unittest.main()
