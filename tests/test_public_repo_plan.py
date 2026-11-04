"""17S-7 offline reviewed two-step public metadata orchestration tests."""
import json
import time
import unittest
import tempfile
from pathlib import Path
from threading import Event
from types import SimpleNamespace
from unittest.mock import patch

from varyn.public_github_tool import PublicGithubToolGateway, PublicToolRejected
from varyn.public_repo_plan import PublicRepoComparison, parse_comparison_plan
from varyn.public_comparison_journal import PublicComparisonJournal
from varyn.public_tool_worker import PublicGithubToolWorker


REPOS = ("naraya07pedro-spec/VARYN", "python/cpython")


def request(repos=REPOS):
    return json.dumps({
        "format": "varyn.public_repo_comparison.v1",
        "repositories": list(repos),
    })


def metadata(repo):
    stars = 5 if repo == REPOS[0] else 12
    return {
        "format": "varyn.github_public_repo_metadata.v1",
        "repository": repo, "default_branch": "main",
        "stars": stars, "open_items_including_prs": 3,
        "archived": False, "public": True, "read_only": True,
        "untrusted_external_data": True, "provider_handoff": False,
    }


def start_plan(plan, *, consent=True, approved=True):
    review = plan.review()
    return plan.start(review.plan_id, review.digest,
                      approved=approved, network_consent=consent)


def pump(ui, condition, timeout=4):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        while ui.scheduled:
            callback = ui.scheduled.pop(0)
            callback()
        if condition():
            return True
        time.sleep(0.01)
    return condition()


class ParsePlanTests(unittest.TestCase):
    def test_strict_pair_no_alternate_urls(self):
        self.assertEqual(parse_comparison_plan(request()), REPOS)
        bad = [
            "", "{}", "[]", '{"format":"varyn.public_repo_comparison.v1"}',
            json.dumps({"format":"varyn.public_repo_comparison.v1",
                        "repositories":[REPOS[0]]}),
            json.dumps({"format":"varyn.public_repo_comparison.v1",
                        "repositories":[*REPOS, "c/d"]}),
            request((REPOS[0], REPOS[0].lower())),
            request(("https://github.com/python/cpython", REPOS[1])),
            request(("http://localhost/secret", REPOS[1])),
            request(("a/../../secret", REPOS[1])),
            request(({"name":"a/b"}, REPOS[1])),
            request((REPOS[0], "a/.git")),
            json.dumps({"format":"varyn.public_repo_comparison.v1",
                        "repositories":list(REPOS), "approved":True}),
            '{"format":"varyn.public_repo_comparison.v1",'
            '"repositories":["a/b","c/d"],"repositories":["x/y","z/t"]}',
            "x" * 2049,
        ]
        for raw in bad:
            with self.subTest(raw=raw[:100]), self.assertRaises(PublicToolRejected):
                parse_comparison_plan(raw)

    def test_requires_two_independent_reviews_and_no_replay(self):
        plan = PublicRepoComparison(request())
        review = plan.review()
        self.assertFalse(plan.status()["model_autodispatch"])
        self.assertFalse(plan.status()["context_uploaded"])
        with self.assertRaises(PublicToolRejected):
            plan.start(review.plan_id, "incorrect", approved=True, network_consent=True)
        with self.assertRaises(PublicToolRejected):
            plan.next_intent()
        self.assertTrue(start_plan(plan))
        with self.assertRaises(PublicToolRejected):
            plan.start(review.plan_id, review.digest,
                       approved=True, network_consent=True)
        intent1 = json.loads(plan.next_intent())
        self.assertEqual(intent1["arguments"]["repository"], REPOS[0])
        with self.assertRaises(PublicToolRejected):
            plan.next_intent()
        self.assertEqual(plan.commit(metadata(REPOS[0])), "running")
        intent2 = json.loads(plan.next_intent())
        self.assertEqual(intent2["arguments"]["repository"], REPOS[1])
        self.assertEqual(plan.commit(metadata(REPOS[1])), "completed")
        out = plan.summary()
        self.assertEqual(out["more_stars"], REPOS[1])
        self.assertEqual(out["stars_difference"], 7)
        self.assertFalse(out["provider_handoff"])
        self.assertEqual(len(out["rows"]), 2)
        with self.assertRaises(PublicToolRejected):
            plan.next_intent()

    def test_deny_expire_revoke_fail_closed(self):
        rejected = PublicRepoComparison(request())
        self.assertFalse(start_plan(rejected, approved=False))
        self.assertEqual(rejected.status()["state"], "cancelled")
        with self.assertRaises(PublicToolRejected):
            rejected.next_intent()
        disabled = PublicRepoComparison(request())
        with self.assertRaises(PermissionError):
            start_plan(disabled, consent=False)
        self.assertEqual(disabled.status()["state"], "cancelled")
        now = [10]
        expired = PublicRepoComparison(request(), clock=lambda: now[0],
                                       ttl_seconds=2)
        now[0] += 2
        with self.assertRaises(PublicToolRejected):
            start_plan(expired)
        self.assertEqual(expired.status()["state"], "cancelled")

    def test_bad_or_injected_tool_result_aborts_entire_task(self):
        for extra in ({"repository": REPOS[1]}, {"stars": True},
                      {"open_items_including_prs": -1},
                      {"description": "leak secrets"},
                      {"provider_handoff": True}):
            plan = PublicRepoComparison(request())
            start_plan(plan)
            plan.next_intent()
            with self.subTest(extra=extra), self.assertRaises(PublicToolRejected):
                plan.commit({**metadata(REPOS[0]), **extra})
            self.assertEqual(plan.status()["state"], "cancelled")
            with self.assertRaises(PublicToolRejected):
                plan.summary()
        unfinished = PublicRepoComparison(request())
        start_plan(unfinished)
        with self.assertRaises(PublicToolRejected):
            unfinished.summary()

    def test_revoke_after_first_result_discards_local_partial_output(self):
        plan = PublicRepoComparison(request())
        start_plan(plan)
        plan.next_intent()
        plan.commit(metadata(REPOS[0]))
        self.assertEqual(plan.status()["steps_done"], 1)
        plan.cancel()
        self.assertEqual(plan.status()["state"], "cancelled")
        with self.assertRaises(PublicToolRejected):
            plan.next_intent()
        with self.assertRaises(PublicToolRejected):
            plan.summary()


class FakeDesktop:
    _busy = False
    _closing = False

    def __init__(self, *, fetcher=None):
        self.enabled = [True]
        self.consent_public_tools = SimpleNamespace(
            get=lambda: self.enabled[0])
        self.prompt = SimpleNamespace(get=lambda *args: request())
        self._public_github_tools = PublicGithubToolGateway(
            fetcher=fetcher or metadata)
        self._public_tool_worker = PublicGithubToolWorker(
            self._public_github_tools)
        self._public_comparison = None
        self._public_comparison_request = None
        self.messages = []
        self.scheduled = []
    def _append(self, role, message):
        self.messages.append((role, message))
    def after(self, ms, callback):
        self.scheduled.append(callback)
    def _poll_public_github_tool(self):
        from varyn.desktop import VarynDesktop
        VarynDesktop._poll_public_github_tool(self)


class DesktopPlanTests(unittest.TestCase):
    def test_opt_in_durable_journal_tracks_both_approved_real_ui_steps(self):
        from varyn.desktop import VarynDesktop
        with tempfile.TemporaryDirectory() as temp:
            journal = PublicComparisonJournal(Path(temp) / "comparison.sqlite3")
            calls = []
            ui = FakeDesktop(fetcher=lambda r: calls.append(r) or metadata(r))
            ui._comparison_journal = journal
            ui._public_comparison_journal_ref = None
            try:
                with patch("varyn.desktop.messagebox.askyesno",
                           side_effect=[True, True, True]) as ask:
                    VarynDesktop._review_public_comparison(ui)
                    self.assertTrue(pump(ui, lambda:
                                        "GITHUB COMPARISON" in repr(ui.messages)))
                self.assertEqual(ask.call_count, 3)
                self.assertEqual(calls, list(REPOS))
                rows = journal.db.execute(
                    "SELECT task_id,cursor,status FROM public_comparison_checkpoints"
                ).fetchall()
                self.assertEqual(len(rows), 1)
                self.assertEqual(rows[0][1:], (2, "completed"))
                self.assertFalse(journal.inspect(rows[0][0])["executable"])
                self.assertIsNone(ui._public_comparison_journal_ref)
            finally:
                ui._public_tool_worker.close()
                journal.close()

    def test_opt_in_journal_marks_uncertain_on_revocation_before_result(self):
        from varyn.desktop import VarynDesktop
        entered, release = Event(), Event()
        def fetcher(repo):
            entered.set()
            release.wait(2)
            return metadata(repo)
        with tempfile.TemporaryDirectory() as temp:
            journal = PublicComparisonJournal(Path(temp) / "comparison.sqlite3")
            ui = FakeDesktop(fetcher=fetcher)
            ui._comparison_journal = journal
            ui._public_comparison_journal_ref = None
            try:
                with patch("varyn.desktop.messagebox.askyesno",
                           side_effect=[True, True]):
                    VarynDesktop._review_public_comparison(ui)
                self.assertTrue(entered.wait(2))
                VarynDesktop._abort_public_comparison(ui, "Revoked by owner")
                rows = journal.db.execute(
                    "SELECT cursor,status FROM public_comparison_checkpoints"
                ).fetchall()
                self.assertEqual(rows, [(0, "needs_reconciliation")])
                self.assertIsNone(ui._public_comparison)
                self.assertIsNone(ui._public_comparison_journal_ref)
                release.set()
                self.assertTrue(pump(ui, lambda:
                                    not ui._public_tool_worker.busy))
                self.assertNotIn("GITHUB COMPARISON", repr(ui.messages))
            finally:
                release.set()
                ui._public_tool_worker.close()
                journal.close()

    def test_three_separate_human_approvals_for_two_actual_gets(self):
        from varyn.desktop import VarynDesktop
        calls = []
        ui = FakeDesktop(fetcher=lambda r:
                         calls.append(r) or metadata(r))
        try:
            with patch("varyn.desktop.messagebox.askyesno",
                       side_effect=[True, True, True]) as ask:
                VarynDesktop._review_public_comparison(ui)
                self.assertTrue(pump(ui, lambda:
                                    "GITHUB COMPARISON" in repr(ui.messages)))
            self.assertEqual(ask.call_count, 3)
            self.assertEqual(calls, list(REPOS))
            self.assertIn("More stars: python/cpython", repr(ui.messages))
            self.assertIsNone(ui._public_comparison)
            self.assertEqual(ui._public_github_tools.status()["used"], 2)
            self.assertEqual(ui._public_github_tools.status()["pending"], 0)
        finally:
            ui._public_tool_worker.close()

    def test_declining_second_step_never_sends_second_get(self):
        from varyn.desktop import VarynDesktop
        calls = []
        ui = FakeDesktop(fetcher=lambda r: calls.append(r) or metadata(r))
        try:
            with patch("varyn.desktop.messagebox.askyesno",
                       side_effect=[True, True, False]) as ask:
                VarynDesktop._review_public_comparison(ui)
                self.assertTrue(pump(ui, lambda:
                                    ui._public_comparison is None))
            self.assertEqual(ask.call_count, 3)
            self.assertEqual(calls, [REPOS[0]])
            self.assertNotIn("GITHUB COMPARISON", repr(ui.messages))
            self.assertEqual(ui._public_github_tools.status()["used"], 1)
        finally:
            ui._public_tool_worker.close()

    def test_plan_rejection_requires_no_external_dispatch(self):
        from varyn.desktop import VarynDesktop
        calls = []
        ui = FakeDesktop(fetcher=lambda r: calls.append(r) or metadata(r))
        try:
            with patch("varyn.desktop.messagebox.askyesno",
                       return_value=False) as ask:
                VarynDesktop._review_public_comparison(ui)
            self.assertEqual(ask.call_count, 1)
            self.assertEqual(calls, [])
            self.assertIsNone(ui._public_comparison)
        finally:
            ui._public_tool_worker.close()

    def test_revoke_while_first_get_blocked_stops_second_step(self):
        from varyn.desktop import VarynDesktop
        entered, release = Event(), Event()
        calls = []
        def fetch(repo):
            calls.append(repo)
            entered.set()
            release.wait(3)
            return metadata(repo)
        ui = FakeDesktop(fetcher=fetch)
        try:
            with patch("varyn.desktop.messagebox.askyesno",
                       side_effect=[True, True]) as ask:
                VarynDesktop._review_public_comparison(ui)
            self.assertTrue(entered.wait(2))
            self.assertEqual(ask.call_count, 2)
            ui.enabled[0] = False
            VarynDesktop._public_tool_permission_changed(ui)
            self.assertIsNone(ui._public_comparison)
            release.set()
            self.assertTrue(pump(ui, lambda: not ui._public_tool_worker.busy))
            self.assertEqual(calls, [REPOS[0]])
            self.assertNotIn("GITHUB COMPARISON", repr(ui.messages))
            self.assertEqual(ui._public_github_tools.status()["used"], 1)
        finally:
            release.set()
            ui._public_tool_worker.close()

    def test_cancel_in_gap_before_second_modal_disables_stale_callback(self):
        from varyn.desktop import VarynDesktop
        calls = []
        ui = FakeDesktop(fetcher=lambda r: calls.append(r) or metadata(r))
        try:
            with patch("varyn.desktop.messagebox.askyesno",
                       side_effect=[True, True]) as ask:
                VarynDesktop._review_public_comparison(ui)
                deadline = time.monotonic() + 3
                # Process only ONE scheduled UI callback at a time until
                # the first result is committed and step-two is queued.
                while time.monotonic() < deadline:
                    if ui.scheduled:
                        cb = ui.scheduled.pop(0)
                        cb()
                    plan = ui._public_comparison
                    if plan is not None and plan.status()["steps_done"] == 1:
                        break
                    time.sleep(0.01)
                self.assertIsNotNone(ui._public_comparison)
                self.assertEqual(ui._public_comparison.status()["steps_done"], 1)
                self.assertEqual(calls, [REPOS[0]])
                self.assertTrue(ui.scheduled)
                # No GET in progress, but there is still a scheduled next step.
                self.assertFalse(ui._public_tool_worker.busy)
                VarynDesktop._cancel_public_github_tool(ui)
                self.assertIsNone(ui._public_comparison)
                while ui.scheduled:
                    ui.scheduled.pop(0)()
            self.assertEqual(ask.call_count, 2)
            self.assertEqual(calls, [REPOS[0]])
            self.assertNotIn("GITHUB COMPARISON", repr(ui.messages))
        finally:
            ui._public_tool_worker.close()

    def test_manual_single_tool_cannot_steal_active_comparison_worker(self):
        from varyn.desktop import VarynDesktop
        entered, release = Event(), Event()
        calls = []
        def fetch(repo):
            entered.set()
            calls.append(repo)
            release.wait(3)
            return metadata(repo)
        ui = FakeDesktop(fetcher=fetch)
        try:
            with patch("varyn.desktop.messagebox.askyesno",
                       side_effect=[True, True]) as ask:
                VarynDesktop._review_public_comparison(ui)
                self.assertTrue(entered.wait(2))
                VarynDesktop._review_public_github_intent(ui)
            self.assertEqual(ask.call_count, 2)
            self.assertEqual(calls, [REPOS[0]])
            self.assertIn("no parallel manual request", repr(ui.messages))
        finally:
            release.set()
            ui._public_tool_worker.close()

    def test_stale_worker_gateway_mismatch_blocks_comparison(self):
        from varyn.desktop import VarynDesktop
        calls = []
        ui = FakeDesktop(fetcher=lambda r: calls.append(r) or metadata(r))
        try:
            new_gateway = PublicGithubToolGateway(
                fetcher=lambda r: calls.append("unexpected") or metadata(r))
            ui._public_github_tools = new_gateway
            with patch("varyn.desktop.messagebox.askyesno") as ask:
                VarynDesktop._review_public_comparison(ui)
            ask.assert_not_called()
            self.assertEqual(calls, [])
            self.assertIsNone(ui._public_comparison)
        finally:
            ui._public_tool_worker.close()
            ui._public_github_tools.close()


if __name__ == "__main__":
    unittest.main()
