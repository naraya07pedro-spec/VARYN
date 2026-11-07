"""Offline adversarial tests: evidence, independent scoring and durable quota."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import sqlite3
import unittest

from varyn.budgeted_reflection_scheduler import (
    BudgetedReflectionScheduler, ScheduleRejected,
    conservative_public_fact_reflector)
from varyn.grounded_benchmark import (
    BenchmarkRejected, GroundedFactBenchmark)
from varyn.grounded_github import GroundingRejected
from varyn.learning_kernel import LearningKernel
from varyn.verified_failure_feedback import (
    FeedbackRejected, VerifiedFailureLedger)

NOW = datetime(2026, 11, 7, 4, 0, tzinfo=timezone.utc)
CANDIDATE = conservative_public_fact_reflector({
    "family": "github_public_facts"})


def observed(i):
    return {
        "status": "completed", "network_dispatched": True,
        "result": {
            "format": "varyn.github_public_repo_metadata.v1",
            "repository": "owner/repo" + str(i),
            "default_branch": "main" if i % 2 == 0 else "develop",
            "stars": i * 5,
            "open_items_including_prs": i + 1,
            "archived": i == 3,
            "public": True, "read_only": True,
            "untrusted_external_data": True, "provider_handoff": False,
        },
    }


def cases(total=5):
    return tuple({
        "id": "heldout-" + str(i), "observation": observed(i),
    } for i in range(total))


def facts_json(public):
    return json.dumps({"action": "finish", "facts": public})


class FeedbackAndScheduling(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.path = Path(self.temp.name) / "learning.sqlite3"
        self.kernel = LearningKernel(self.path)
        self.ledger = VerifiedFailureLedger(self.kernel)
        self.scheduler = BudgetedReflectionScheduler(self.kernel, self.ledger)

    def tearDown(self):
        self.kernel.close()
        self.temp.cleanup()

    def seed_successes(self, start=0):
        ids = []
        for i in range(start, start + 2):
            ids.append(self.kernel.record_verified_outcome(
                "github_public_facts", "verified-case-" + str(i),
                format(i + 1, "064x"), succeeded=True,
                verified_by_host=True))
        return ids

    def seed_failure(self, run="a" * 32):
        return self.ledger.record(
            run, GroundingRejected("Model fact does not match observation"),
            observed(1), owner_opted_in=True)

    def benchmark(self, *, mode="improve", total=5):
        def independent_runner(skill, case_id, fields):
            if mode == "improve":
                okay = skill == CANDIDATE
            elif mode == "regression":
                if skill == "Prior accepted baseline instruction text.":
                    okay = case_id in ("heldout-0", "heldout-1")
                else:
                    okay = case_id in (
                        "heldout-1", "heldout-2",
                        "heldout-3", "heldout-4")
            else:
                okay = False
            if not okay:
                fields["stars"] += 1
            return facts_json(fields)
        return GroundedFactBenchmark(cases(total), independent_runner)

    def run_tick(self, bench=None, **changes):
        kwargs = {
            "enabled": True, "trusted_evaluator": True,
            "allow_declassified_reflection": True,
            "benchmark": bench or self.benchmark(),
            "reflector": conservative_public_fact_reflector,
            "now": NOW,
        }
        kwargs.update(changes)
        return self.scheduler.tick(**kwargs)

    def test_feedback_requires_exact_opt_in_and_safe_evidence(self):
        with self.assertRaises(PermissionError):
            self.ledger.record(
                "a" * 32,
                GroundingRejected("Model fact does not match observation"),
                observed(1))
        with self.assertRaises(FeedbackRejected):
            self.ledger.record(
                "not-a-real-run",
                GroundingRejected("Model fact does not match observation"),
                observed(1), owner_opted_in=True)
        self.assertEqual(self.ledger.summary()["total_failed_fact_checks"], 0)
        self.assertEqual(self.seed_failure()["status"], "recorded")
        self.assertEqual(self.seed_failure()["status"], "duplicate")
        summary = self.ledger.summary()
        self.assertEqual(summary["categories"], {"fact_mismatch": 1})
        self.assertFalse(summary["stored_raw_model_text"])
        self.assertEqual(len(self.ledger.recent_fingerprints()[0]), 64)
        assert self.kernel.db.execute(
            "SELECT COUNT(*) FROM grounded_failure_feedback").fetchone()[0] == 1

    def test_disabled_tick_does_not_touch_callbacks_or_reserve(self):
        used = []
        status = self.scheduler.tick(
            reflector=lambda ctx: used.append(ctx),
            enabled=False)
        self.assertEqual(status["status"], "disabled")
        self.assertEqual(used, [])
        self.assertEqual(self.scheduler.history(), [])
        with self.assertRaises(PermissionError):
            self.scheduler.tick(
                enabled=True, benchmark=self.benchmark(),
                reflector=conservative_public_fact_reflector)

    def test_not_ready_without_failure_or_two_verified_successes(self):
        self.seed_successes()
        self.assertEqual(self.run_tick()["status"], "no_verified_failure")
        self.seed_failure()
        # With two positives and a failure, the closed loop becomes eligible.
        self.assertEqual(self.run_tick()["status"], "promoted")

    def test_single_success_is_not_learning_evidence(self):
        self.seed_failure()
        self.kernel.record_verified_outcome(
            "github_public_facts", "just-one", "1" * 64,
            succeeded=True, verified_by_host=True)
        bench = self.benchmark()
        result = self.run_tick(bench)
        self.assertEqual(result["status"], "not_enough_success_evidence")
        self.assertEqual(bench.calls, 0)
        self.assertEqual(self.scheduler.history(), [])

    def test_promote_only_after_independent_improvement_and_no_regression(self):
        self.seed_successes()
        self.seed_failure()
        benchmark = self.benchmark()
        result = self.run_tick(benchmark)
        self.assertEqual(result["status"], "promoted")
        self.assertEqual(result["evaluator_calls"], 10)
        self.assertEqual(result["regressions"], 0)
        self.assertFalse(result["external_billing_cap_enforced"])
        self.assertEqual(self.kernel.active_skill(
            "github_public_facts")["text"], CANDIDATE)
        self.assertEqual(self.scheduler.history()[0]["status"], "promoted")
        self.assertEqual(self.run_tick(benchmark)["status"],
                         "already_processed")
        self.assertEqual(benchmark.calls, 10)

    def test_persistent_budget_and_batch_dedup_across_restart(self):
        self.seed_successes()
        self.seed_failure()
        result = self.run_tick()
        self.assertEqual(result["status"], "promoted")
        self.kernel.close()
        self.kernel = LearningKernel(self.path)
        self.ledger = VerifiedFailureLedger(self.kernel)
        self.scheduler = BudgetedReflectionScheduler(self.kernel, self.ledger)
        status = self.run_tick(now=NOW + timedelta(days=1))
        self.assertEqual(status["status"], "already_processed")
        self.assertEqual(len(self.scheduler.history()), 1)

    def test_larger_suite_over_daily_budget_never_dispatches(self):
        self.seed_successes()
        self.seed_failure()
        benchmark = self.benchmark(total=6)
        result = self.run_tick(
            benchmark, max_evaluator_calls_per_utc_day=10)
        self.assertEqual(result["status"], "budget_exhausted")
        self.assertEqual(benchmark.calls, 0)
        self.assertEqual(self.scheduler.history(), [])

    def test_regression_rejects_candidate_even_if_total_passes_improve(self):
        successes = self.seed_successes()
        baseline = "Prior accepted baseline instruction text."
        previous = self.kernel.propose_skill(
            "github_public_facts", baseline, successes)
        fixed_cases = ("x1", "x2", "x3", "x4", "x5")
        self.kernel.evaluate_and_select(
            previous, fixed_cases, lambda text, case: text == baseline)
        self.seed_failure()
        benchmark = self.benchmark(mode="regression")
        result = self.run_tick(benchmark)
        self.assertEqual(result["status"], "rejected")
        self.assertEqual(result["regressions"], 1)
        self.assertEqual(self.kernel.active_skill(
            "github_public_facts")["text"], baseline)

    def test_failed_runner_keeps_reservation_and_never_retries(self):
        self.seed_successes()
        self.seed_failure()
        calls = []
        def fail(skill, case_id, fields):
            calls.append(case_id)
            raise RuntimeError("fake crashed evaluator")
        benchmark = GroundedFactBenchmark(cases(), fail)
        with self.assertRaises(RuntimeError):
            self.run_tick(benchmark)
        self.assertEqual(calls, ["heldout-0"])
        self.assertEqual(self.scheduler.history()[0]["status"], "needs_review")
        next_run = self.run_tick(benchmark)
        self.assertEqual(next_run["status"], "already_processed")
        self.assertEqual(len(calls), 1)

    def test_suspicious_evaluator_is_rejected(self):
        with self.assertRaises(BenchmarkRejected):
            GroundedFactBenchmark((cases()[0],) * 5, lambda *args: "")
        valid = self.benchmark()
        with self.assertRaises(BenchmarkRejected):
            valid.evaluate(CANDIDATE, "not-a-heldout-case")

    def test_no_plain_task_identifiers_or_model_text_persisted(self):
        self.seed_successes()
        self.seed_failure()
        self.run_tick()
        rows = self.kernel.db.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' "
            "AND name='grounded_failure_feedback'").fetchone()
        self.assertNotIn("prompt", rows[0])
        self.assertNotIn("message", rows[0])
        self.assertEqual(
            self.kernel.db.execute(
                "SELECT category FROM grounded_failure_feedback"
            ).fetchone()[0], "fact_mismatch")


if __name__ == "__main__":
    unittest.main()
