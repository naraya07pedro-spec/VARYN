"""17N: controlled memory selection and real 3-stage context handoff."""
import queue
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from varyn.collaboration import Stage
from varyn.desktop import VarynDesktop
from varyn.desktop_controller import DesktopController
from varyn.desktop_collaboration import review_collaboration
from varyn.desktop_memory import DesktopMemory
from varyn.memory_handoff import parse_note_ids, selected_memory_context
from varyn.multi_provider import ProviderRouter
from varyn.providers import ModelReply
from varyn.usage_budget import UsageBudget
from varyn.collaboration import CollaborationEngine


OFFLINE = (("fake", "fake-test"),) * 3
MIXED = (
    ("fake", "fake-test"),
    ("anthropic", "model-critic"),
    ("gemini", "model-synthesis"),
)


class MemoryHandoffTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.memory = DesktopMemory(Path(self.temp.name) / "memory.sqlite3")
        self.addCleanup(self.memory.close)
        self.a = self.memory.save("VARYN", "SYNTHETIC: confirmed alpha", confirmed=True)
        self.b = self.memory.save("VARYN", "SYNTHETIC: confirmed beta", confirmed=True)
        self.foreign = self.memory.save(
            "RepoPilot", "SYNTHETIC: foreign forbidden", confirmed=True
        )

    def test_exact_references_and_order_in_snapshot(self):
        data = selected_memory_context(self.memory, "VARYN", (self.b, self.a))
        self.assertEqual(data["format"], "varyn.context.v1")
        self.assertEqual([i["ref"] for i in data["items"]],
                         [f"memory:{self.b}", f"memory:{self.a}"])
        self.assertEqual(data["project"], "VARYN")
        self.assertTrue(data["owner_label_not_authenticated"])
        self.assertFalse(data["items"][0]["source_verified"])
        self.assertTrue(data["items"][1]["untrusted"])

    def test_missing_or_cross_project_id_denies_entire_plan(self):
        for ids in ((self.a, self.foreign), (self.foreign,),
                    (self.a, self.foreign + 777)):
            with self.subTest(ids=ids), self.assertRaises(PermissionError):
                selected_memory_context(self.memory, "VARYN", ids)

    def test_bad_selection_types_and_duplicates(self):
        for ids in ((), (self.a, self.a), (0,), (True,),
                    (float(self.a),), ("1",), (1,2,3,4)):
            with self.subTest(ids=ids), self.assertRaises(ValueError):
                selected_memory_context(self.memory, "VARYN", ids)

    def test_no_implicit_memory_search_or_selection(self):
        self.assertEqual(parse_note_ids(f"{self.a}, {self.b}"), (self.a, self.b))
        for raw in ("", "alpha", "1,1", "0", "1,,2", "1,2,3,4", "1;2", None):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                parse_note_ids(raw)

    def test_selected_note_must_still_be_synthetic(self):
        # Another local CLI is not constrained by the desktop synthetic guard.
        self.memory._store.add("VARYN", "externally inserted real-looking text")
        idx = self.memory._store.db.execute(
            "SELECT MAX(id) FROM memories"
        ).fetchone()[0]
        with self.assertRaises(PermissionError):
            selected_memory_context(self.memory, "VARYN", (idx,))

    def test_context_requires_no_network_and_does_not_scan_other_projects(self):
        with patch("varyn.multi_provider._post",
                   side_effect=AssertionError("Unexpected network")):
            data = selected_memory_context(self.memory, "VARYN", (self.a,))
        self.assertEqual(len(data["items"]), 1)
        self.assertNotIn("foreign forbidden", str(data))

    def test_deleted_note_cannot_be_recovered_by_selected_id(self):
        self.assertTrue(self.memory.delete("VARYN", self.a, confirmed=True))
        with self.assertRaises(PermissionError):
            selected_memory_context(self.memory, "VARYN", (self.a,))

    def test_closed_memory_refuses_context(self):
        self.memory.close()
        with self.assertRaises(RuntimeError):
            selected_memory_context(self.memory, "VARYN", (self.a,))

    def test_review_discloses_memory_in_every_external_api_stage(self):
        warnings = []
        stages, approved = review_collaboration(
            "Test", MIXED, network_enabled=True, memory_attached=True,
            ask_approval=lambda message: warnings.append(message) or True,
        )
        self.assertEqual(approved, (False, True, True))
        self.assertEqual(len(warnings), 2)
        self.assertTrue(all("user-selected local memory" in m for m in warnings))
        self.assertEqual(stages[0].provider, "fake")

    def test_review_without_context_preserves_no_memory_statement(self):
        warnings = []
        review_collaboration(
            "Test", MIXED, network_enabled=True,
            ask_approval=lambda m: warnings.append(m) or True,
        )
        self.assertTrue(all("No stored memory is attached" in m for m in warnings))


class CapturingProvider:
    def __init__(self):
        self.inputs = []

    def generate(self, question, *, model, context=None, max_output_tokens=512,
                 timeout_seconds=10, allow_context_upload=False):
        self.inputs.append((question, context, allow_context_upload))
        return ModelReply("FAKE captured-stage output", "fake", model, {})


class ContextEngineTests(MemoryHandoffTests):
    def test_selected_context_reaches_analyst_only_with_source_references(self):
        spy = CapturingProvider()
        engine = CollaborationEngine(
            ProviderRouter(providers={"fake": spy}),
            budget=UsageBudget(max_requests=3, max_reserved_output_tokens=1024),
        )
        stages = tuple(Stage(role, "fake", "fake-test", 64) for role in
                       ("analyst", "critic", "synthesizer"))
        context = selected_memory_context(self.memory, "VARYN", (self.a,))
        with self.assertRaises(PermissionError):
            engine.run("Task", stages, context=context)
        self.assertEqual(len(spy.inputs), 0)
        result = engine.run("Task", stages, context=context,
                            context_upload_confirmed=True)
        self.assertEqual(spy.inputs[0][1], context)
        self.assertTrue(spy.inputs[0][2])
        self.assertIsNone(spy.inputs[1][1])
        self.assertIsNone(spy.inputs[2][1])
        self.assertEqual(result["context_source_refs"], [f"memory:{self.a}"])
        self.assertEqual(result["context_project"], "VARYN")
        self.assertFalse(result["multi_model_review"])


class FakeGUI:
    def __init__(self, memory):
        self._memory = memory
        self._busy = False
        self._closing = False
        self.memory_project = SimpleNamespace(get=lambda: "VARYN")
        self.controller = DesktopController()
        self.controller.set_context_consent(True)
        self.consent_context = SimpleNamespace(get=lambda: True)
        self.consent_network = SimpleNamespace(get=lambda: False)
        self.send_button = SimpleNamespace(configure=lambda **kw: None)
        self.collaborate_button = SimpleNamespace(configure=lambda **kw: None)
        self._lifecycle = SimpleNamespace(begin=lambda: 9)
        self._results = queue.Queue()
        self.messages = []
        self._refresh_status = lambda: None

    def _append(self, who, content):
        self.messages.append((who, content))

    def _collaboration_worker(self, *args):
        return VarynDesktop._collaboration_worker(self, *args)

    def _poll_result(self):
        return

    def after(self, *args):
        return


class DesktopMemoryContextTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = DesktopMemory(Path(self.temp.name) / "notes.sqlite3")
        self.addCleanup(self.db.close)
        self.idx = self.db.save("VARYN", "SYNTHETIC: selected one", confirmed=True)
        self.other = self.db.save("OTHER", "SYNTHETIC: private wrong scope", confirmed=True)
        self.ui = FakeGUI(self.db)

    def test_refuse_invalid_note_without_any_dialog_or_dispatch(self):
        with patch("varyn.desktop.messagebox.askyesno") as ask:
            self.assertFalse(VarynDesktop._start_collaboration(
                self.ui, "Task", OFFLINE, memory_ids=str(self.other)
            ))
        ask.assert_not_called()
        self.assertEqual(self.ui.controller.status()["requests_used"], 0)

    def test_refuse_when_context_permission_is_disabled(self):
        self.ui.controller.set_context_consent(False)
        with patch("varyn.desktop.messagebox.askyesno") as ask:
            self.assertFalse(VarynDesktop._start_collaboration(
                self.ui, "Task", OFFLINE, memory_ids=str(self.idx)
            ))
        ask.assert_not_called()

    def test_refuse_selected_memory_if_owner_declines_preview(self):
        with patch("varyn.desktop.messagebox.askyesno", return_value=False) as ask:
            self.assertFalse(VarynDesktop._start_collaboration(
                self.ui, "Task", OFFLINE, memory_ids=str(self.idx)
            ))
        self.assertEqual(ask.call_count, 1)
        self.assertEqual(self.ui.controller.status()["requests_used"], 0)

    def test_approved_context_reaches_worker_and_provenance(self):
        class ImmediateThread:
            def __init__(self, target, args, daemon):
                self.target, self.args = target, args
            def start(self):
                self.target(*self.args)
        with patch("varyn.desktop.messagebox.askyesno", return_value=True) as ask, \
             patch("varyn.desktop.threading.Thread", ImmediateThread):
            self.assertTrue(VarynDesktop._start_collaboration(
                self.ui, "Task", OFFLINE, memory_ids=str(self.idx)
            ))
        self.assertEqual(ask.call_count, 1)
        report = self.ui._results.get_nowait()[3]
        self.assertEqual(report["context_source_refs"], [f"memory:{self.idx}"])
        self.assertEqual(report["context_project"], "VARYN")
        self.assertEqual(self.ui.controller.status()["requests_used"], 3)

    def test_no_database_requires_refusal_before_disclosure(self):
        self.ui._memory = None
        with patch("varyn.desktop.messagebox.askyesno") as ask:
            self.assertFalse(VarynDesktop._start_collaboration(
                self.ui, "Task", OFFLINE, memory_ids="1"
            ))
        ask.assert_not_called()


if __name__ == "__main__":
    unittest.main()
