"""17L: actual UI review contract plus desktop worker/consent boundary."""
import queue
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from varyn.collaboration import Stage
from varyn.desktop import VarynDesktop
from varyn.desktop_collaboration import ROLES, review_collaboration
from varyn.desktop_controller import DesktopController


OFFLINE = (("fake", "fake-test"),) * 3
MIXED = (
    ("fake", "fake-test"),
    ("anthropic", "model-critic"),
    ("gemini", "model-synthesis"),
)


class CollaborationReviewTests(unittest.TestCase):
    def test_offline_plan_works_without_dialogs_or_network(self):
        with patch("varyn.desktop_collaboration.Stage", wraps=Stage) as make:
            stages, confirmations = review_collaboration(
                "Synthetic task", OFFLINE,
                network_enabled=False,
                ask_approval=lambda text: self.fail("No offline prompts"),
            )
        self.assertEqual(make.call_count, 3)
        self.assertEqual(tuple(s.role for s in stages), ROLES)
        self.assertEqual(confirmations, (False, False, False))

    def test_two_live_stages_each_show_distinct_explicit_consent(self):
        prompts = []
        stages, approvals = review_collaboration(
            "Synthetic task", MIXED, network_enabled=True,
            ask_approval=lambda msg: prompts.append(msg) or True,
        )
        self.assertEqual(len(prompts), 2)
        self.assertEqual(approvals, (False, True, True))
        self.assertIn("Step 2/3", prompts[0])
        self.assertIn("anthropic", prompts[0])
        self.assertIn("Step 3/3", prompts[1])
        self.assertIn("gemini", prompts[1])
        for prompt in prompts:
            self.assertIn("earlier", prompt)
            self.assertIn("can incur charges", prompt)
        self.assertEqual(stages[-1].role, "synthesizer")

    def test_any_denial_prevents_returning_approvals(self):
        for answers in ([False], [True, False], [True, None]):
            it = iter(answers)
            with self.subTest(answers=answers), self.assertRaises(PermissionError):
                review_collaboration(
                    "Task", MIXED, network_enabled=True,
                    ask_approval=lambda _: next(it),
                )

    def test_network_off_blocks_live_before_any_dialog(self):
        prompts = []
        with self.assertRaises(PermissionError):
            review_collaboration(
                "Task", MIXED, network_enabled=False,
                ask_approval=lambda msg: prompts.append(msg) or True,
            )
        self.assertEqual(prompts, [])

    def test_prevalidate_all_models_before_any_dialog(self):
        entries = (
            ("fake", "fake-test"), ("anthropic", "valid-model"),
            ("gemini", ""),
        )
        prompts = []
        with self.assertRaises(ValueError):
            review_collaboration(
                "Task", entries, network_enabled=True,
                ask_approval=lambda msg: prompts.append(msg) or True,
            )
        self.assertEqual(prompts, [])

    def test_bad_tasks_and_unknown_options_denied(self):
        bad = ("", "x" * 1201, None, "  ")
        for task in bad:
            with self.subTest(value=str(task)[:20]), self.assertRaises(ValueError):
                review_collaboration(task, OFFLINE)
        for value in (None, [], [("fake", "fake-test")],
                      [(1, "fake")] * 3,
                      [("claude", "x")] * 3):
            with self.subTest(value=value), self.assertRaises(ValueError):
                review_collaboration("Task", value)

    def test_bool_not_interpreted_as_network_approval(self):
        with self.assertRaises(PermissionError):
            review_collaboration(
                "Task", MIXED, network_enabled=1,
                ask_approval=lambda _: True,
            )

    def test_no_approval_callback_cannot_authorize_live_provider(self):
        with self.assertRaises(PermissionError):
            review_collaboration("Task", MIXED, network_enabled=True)

    def test_controller_collaboration_shares_budget_not_separate_quota(self):
        controller = DesktopController(
            max_requests=4, max_reserved_output_tokens=1024
        )
        engine = controller.collaboration_engine()
        self.assertIs(engine._budget, controller._budget)
        self.assertFalse(engine._allow_live)
        stages, confirms = review_collaboration("Task", OFFLINE)
        result = engine.run("Task", stages, live_confirmations=confirms)
        self.assertEqual(result["local_budget"]["requests_reserved"], 3)
        self.assertEqual(controller.status()["requests_used"], 3)
        with self.assertRaises(PermissionError):
            engine.run("Task", stages, live_confirmations=confirms)
        self.assertEqual(controller.status()["requests_used"], 3)

    def test_controller_snapshots_network_gate(self):
        controller = DesktopController(allow_live_providers=True)
        self.assertFalse(controller.collaboration_engine()._allow_live)
        controller.set_network_consent(True)
        self.assertTrue(controller.collaboration_engine()._allow_live)
        controller.set_network_consent(False)
        self.assertFalse(controller.collaboration_engine()._allow_live)


class FakeUI:
    def __init__(self):
        self._busy = False
        self._closing = False
        self.controller = DesktopController()
        self.consent_network = SimpleNamespace(get=lambda: False)
        self.send_button = SimpleNamespace(configure=lambda **kw: None)
        self.collaborate_button = SimpleNamespace(configure=lambda **kw: None)
        self._results = queue.Queue()
        self._lifecycle = SimpleNamespace(begin=lambda: 1)
        self.messages = []
        self.after_calls = []
        self.workers = []
        self._refresh_status = lambda: None

    def _append(self, who, msg):
        self.messages.append((who, msg))

    def after(self, delay, callback):
        self.after_calls.append((delay, callback))

    def _poll_result(self):
        pass

    def _collaboration_worker(self, request_id, task, stages, approvals, engine):
        return VarynDesktop._collaboration_worker(
            self, request_id, task, stages, approvals, engine
        )


class DesktopCollaborationTests(unittest.TestCase):
    def setUp(self):
        self.ui = FakeUI()

    def test_start_offline_collaboration_from_desktop(self):
        started = []
        class ImmediateThread:
            def __init__(self, target, args, daemon):
                self.target, self.args = target, args
                self.daemon = daemon
            def start(self):
                self.target(*self.args)
                started.append(True)
        with patch("varyn.desktop.threading.Thread", ImmediateThread):
            self.assertTrue(VarynDesktop._start_collaboration(
                self.ui, "Task", OFFLINE
            ))
        self.assertTrue(started)
        self.assertTrue(self.ui._busy)
        self.assertEqual(self.ui._results.qsize(), 1)
        request, kind, _, report = self.ui._results.get_nowait()
        self.assertEqual(request, 1)
        self.assertEqual(kind, "collaboration")
        self.assertEqual(len(report["stages"]), 3)
        self.assertFalse(report["multi_model_review"])
        self.assertEqual(self.ui.controller.status()["requests_used"], 3)
        self.assertEqual(len(self.ui.after_calls), 1)

    def test_desktop_declines_live_plan_when_network_is_off(self):
        with patch("varyn.desktop.messagebox.askyesno") as ask:
            self.assertFalse(VarynDesktop._start_collaboration(
                self.ui, "Task", MIXED
            ))
        ask.assert_not_called()
        self.assertFalse(self.ui._busy)
        self.assertEqual(self.ui.controller.status()["requests_used"], 0)

    def test_invalid_stage_model_fails_before_any_start(self):
        bad = list(OFFLINE)
        bad[-1] = ("gemini", "")
        with patch("varyn.desktop.messagebox.askyesno") as ask:
            self.assertFalse(VarynDesktop._start_collaboration(
                self.ui, "Task", tuple(bad)
            ))
        ask.assert_not_called()
        self.assertEqual(self.ui._results.qsize(), 0)

    def test_busy_or_closing_prevents_any_review(self):
        for attribute in ("_busy", "_closing"):
            setattr(self.ui, attribute, True)
            with patch("varyn.desktop.messagebox.askyesno") as ask:
                self.assertFalse(VarynDesktop._start_collaboration(
                    self.ui, "Task", OFFLINE
                ))
            ask.assert_not_called()
            setattr(self.ui, attribute, False)

    def test_worker_error_is_sanitized_and_stops(self):
        fake_engine = SimpleNamespace(
            run=lambda *_args, **_kwargs: (_ for _ in ()).throw(
                RuntimeError("secret-credential-and-user-path")
            )
        )
        VarynDesktop._collaboration_worker(
            self.ui, 7, "Task", (), (), fake_engine
        )
        response = self.ui._results.get_nowait()
        self.assertEqual(response[1], "collaboration_error")
        self.assertNotIn("secret-credential", str(response))
        self.assertIn("no automatic retry", response[3])

    def test_live_plan_cannot_bypass_offline_controller(self):
        self.ui.consent_network = SimpleNamespace(get=lambda: True)
        with patch("varyn.desktop.messagebox.askyesno") as ask:
            self.assertFalse(VarynDesktop._start_collaboration(
                self.ui, "Task", MIXED
            ))
        ask.assert_not_called()


if __name__ == "__main__":
    unittest.main()
