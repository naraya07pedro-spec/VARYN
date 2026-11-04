"""17J real-Tk safety and provenance contract; synthetic-only offline tests.

Most cases run headlessly. A dedicated Windows CI step separately opens real
Tk widgets and invokes their button commands under simulated consent.
"""
import io
import json
import tkinter as tk
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest.mock import patch

from varyn.tk_widget_smoke import _BUTTONS, _buttons, _report, main, run_tk_widget_smoke


class FakeControl:
    def __init__(self, name=None, children=()):
        self.name = name
        self.children = children

    def winfo_children(self):
        return self.children

    def cget(self, name):
        if name != "text":
            raise ValueError("unexpected property")
        return self.name


class TkWidgetSmokeContractTests(unittest.TestCase):
    def test_report_cannot_claim_human_click_or_provider_access(self):
        row = _report()
        self.assertFalse(row["passed"])
        self.assertEqual(row["status"], "not_run")
        self.assertFalse(row["human_mouse_clicks_performed"])
        self.assertFalse(row["human_consent_obtained"])
        self.assertFalse(row["owner_physical_pc_tested"])
        self.assertFalse(row["official_provider_connected"])
        self.assertEqual(row["network_requests_by_test"], 0)
        self.assertFalse(row["personal_folders_selected"])

    def test_real_widget_discovery_rejects_missing_button(self):
        with patch("varyn.tk_widget_smoke.ttk.Button", FakeControl):
            tree = FakeControl(children=(FakeControl(_BUTTONS[0]),))
            with self.assertRaises(AssertionError):
                _buttons(tree)

    def test_real_widget_discovery_rejects_duplicate_buttons(self):
        with patch("varyn.tk_widget_smoke.ttk.Button", FakeControl):
            tree = FakeControl(children=tuple(FakeControl(x) for x in
                    (*_BUTTONS, _BUTTONS[1])))
            with self.assertRaises(AssertionError):
                _buttons(tree)

    def test_real_widget_discovery_finds_exact_nested_buttons(self):
        with patch("varyn.tk_widget_smoke.ttk.Button", FakeControl):
            tree = FakeControl(children=(
                FakeControl("not a scope action"),
                FakeControl(children=(
                    FakeControl(_BUTTONS[0]),
                    FakeControl(children=(
                        FakeControl(_BUTTONS[1]), FakeControl(_BUTTONS[2])
                    )),
                )),
            ))
            found = _buttons(tree)
        self.assertEqual(set(found), set(_BUTTONS))

    def test_no_graphics_is_not_a_pass(self):
        with patch("varyn.tk_widget_smoke.VarynDesktop",
                   side_effect=tk.TclError("sensitive display identifier")):
            report = run_tk_widget_smoke()
        self.assertEqual(report["status"], "unavailable_no_graphical_session")
        self.assertFalse(report["passed"])
        self.assertFalse(report["tk_widget_tree_created"])
        self.assertNotIn("sensitive", json.dumps(report))
        self.assertFalse(report["owner_physical_pc_tested"])

    def test_other_gui_exception_fails_closed_without_exception_details(self):
        with patch("varyn.tk_widget_smoke.VarynDesktop",
                   side_effect=RuntimeError("secret: hidden local path")):
            report = run_tk_widget_smoke()
        self.assertFalse(report["passed"])
        self.assertEqual(report["status"], "failed")
        self.assertNotIn("secret", json.dumps(report))

    def test_bounded_timeout_rejects_boolean_string_and_excess(self):
        for value in (None, True, 0, 1, 21, 2.0, "8", [], {}):
            with self.subTest(value=value), self.assertRaises(ValueError):
                run_tk_widget_smoke(timeout_seconds=value)

    def test_cli_requires_explicit_synthetic_only_flag(self):
        for args in ([], ["--json"], ["--require-display"],
                     ["--synthetic-only", "--folder", "C:/Users/private"]):
            with self.subTest(args=args), \
                    redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
                main(args)
            self.assertEqual(error.exception.code, 2)

    def test_cli_unavailable_remains_nonzero_even_without_require_display(self):
        with patch("varyn.tk_widget_smoke.run_tk_widget_smoke",
                   return_value={**_report(), "status": "unavailable_no_graphical_session"}), \
             redirect_stdout(io.StringIO()):
            self.assertEqual(main(["--synthetic-only"]), 2)
            self.assertEqual(main(["--synthetic-only", "--require-display"]), 1)

    def test_cli_outputs_bounded_json_and_returns_failure(self):
        fake = {**_report(), "status": "failed"}
        output = io.StringIO()
        with patch("varyn.tk_widget_smoke.run_tk_widget_smoke",
                   return_value=fake), redirect_stdout(output):
            self.assertEqual(main(["--synthetic-only", "--json"]), 1)
        row = json.loads(output.getvalue())
        self.assertEqual(row["network_requests_by_test"], 0)
        self.assertFalse(row["human_mouse_clicks_performed"])
        self.assertFalse(row["passed"])


if __name__ == "__main__":
    unittest.main()
