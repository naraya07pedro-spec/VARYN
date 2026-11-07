"""Deterministic promotion and regression tests, no model or network calls."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from varyn.learning_kernel import LearningKernel
from varyn.verified_reflection import VerifiedReflectionWorker, ReflectionRejected

FAMILY = "github_triage"
OLD = "Check duplicate issue identifiers before reporting public GitHub repository status."
NEW = "Check issue identifiers, repository scope, and normalized metadata before reporting status."


class VerifiedReflectionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.kernel = LearningKernel(Path(self.tmp.name) / "learn.sqlite3")
        self.worker = VerifiedReflectionWorker(self.kernel)
        self.suite = ("case-a", "case-b", "case-c", "case-d", "case-e")

    def tearDown(self):
        self.kernel.close()
        self.tmp.cleanup()

    def lessons(self, start=0):
        result = []
        for i in (start, start + 1):
            receipt = self.kernel.record_verified_outcome(
                FAMILY, "task-" + str(i), "a" * 64,
                succeeded=True, verified_by_host=True)
            result.append({
                "outcome_id": receipt,
                "lesson": "Verified task " + str(i) +
                          " required checking duplicate repository issues.",
            })
        return result

    def test_skill_proposed_evaluated_and_promoted(self):
        items = self.lessons()
        calls = []
        def reflect(context):
            calls.append(context)
            return OLD
        verdict = self.worker.learn(
            FAMILY, items, reflector=reflect,
            evaluator=lambda text, case: text == OLD and case != "case-e",
            heldout_cases=self.suite,
            allow_declassified_reflection=True, trusted_evaluator=True)
        self.assertEqual(verdict["status"], "promoted")
        self.assertEqual(verdict["evaluation"]["candidate_passes"], 4)
        self.assertEqual(len(calls), 1)
        self.assertNotIn("heldout_cases", calls[0])
        self.assertEqual(self.kernel.active_skill(FAMILY)["text"], OLD)
        self.assertFalse(verdict["model_weights_modified"])

    def test_regression_does_not_replace_working_skill(self):
        first = self.lessons()
        self.worker.learn(
            FAMILY, first, reflector=lambda ctx: OLD,
            evaluator=lambda text, case: text == OLD,
            heldout_cases=self.suite,
            allow_declassified_reflection=True, trusted_evaluator=True)
        second = self.lessons(2)
        def evaluator(text, case):
            if text == OLD:
                return case in ("case-a", "case-b")
            return case in ("case-b", "case-c", "case-d", "case-e")
        result = self.worker.learn(
            FAMILY, second, reflector=lambda ctx: NEW,
            evaluator=evaluator, heldout_cases=self.suite,
            allow_declassified_reflection=True, trusted_evaluator=True)
        self.assertEqual(result["status"], "rejected")
        self.assertEqual(result["evaluation"]["regressions"], 1)
        self.assertEqual(self.kernel.active_skill(FAMILY)["text"], OLD)

    def test_reflection_default_denied(self):
        called = []
        items = self.lessons()
        with self.assertRaises(PermissionError):
            self.worker.learn(
                FAMILY, items,
                reflector=lambda ctx: called.append(ctx) or OLD,
                evaluator=lambda text, case: True,
                heldout_cases=self.suite)
        self.assertEqual(called, [])
        self.assertEqual(self.kernel.db.execute(
            "SELECT COUNT(*) FROM reflection_attempts").fetchone()[0], 0)

    def test_repeat_evidence_never_reprocessed(self):
        items = self.lessons()
        self.worker.learn(
            FAMILY, items, reflector=lambda ctx: OLD,
            evaluator=lambda text, case: text == OLD,
            heldout_cases=self.suite,
            allow_declassified_reflection=True, trusted_evaluator=True)
        invoked = []
        with self.assertRaises(ReflectionRejected):
            self.worker.learn(
                FAMILY, list(reversed(items)),
                reflector=lambda ctx: invoked.append(ctx) or NEW,
                evaluator=lambda text, case: text == NEW,
                heldout_cases=self.suite,
                allow_declassified_reflection=True, trusted_evaluator=True)
        self.assertEqual(invoked, [])

    def test_failed_or_cross_family_source_denied(self):
        items = self.lessons()
        failed = self.kernel.record_verified_outcome(
            FAMILY, "failed", "b" * 64,
            succeeded=False, verified_by_host=True)
        items[1]["outcome_id"] = failed
        with self.assertRaises(ReflectionRejected):
            self.worker.learn(
                FAMILY, items, reflector=lambda ctx: OLD,
                evaluator=lambda text, case: True,
                heldout_cases=self.suite,
                allow_declassified_reflection=True, trusted_evaluator=True)
        self.assertEqual(self.kernel.db.execute(
            "SELECT COUNT(*) FROM reflection_attempts").fetchone()[0], 0)

    def test_reflector_exception_preserves_reconciliation(self):
        items = self.lessons()
        def failure(ctx):
            raise RuntimeError("synthetic model failure")
        with self.assertRaises(RuntimeError):
            self.worker.learn(
                FAMILY, items, reflector=failure,
                evaluator=lambda text, case: True,
                heldout_cases=self.suite,
                allow_declassified_reflection=True, trusted_evaluator=True)
        self.assertEqual(self.kernel.db.execute(
            "SELECT status FROM reflection_attempts").fetchone()[0],
            "needs_review")
        self.assertIsNone(self.kernel.active_skill(FAMILY))

    def test_duplicate_ids_and_invalid_data_denied(self):
        items = self.lessons()
        items[1]["outcome_id"] = items[0]["outcome_id"]
        with self.assertRaises(ReflectionRejected):
            self.worker.learn(
                FAMILY, items, reflector=lambda ctx: OLD,
                evaluator=lambda text, case: True,
                heldout_cases=self.suite,
                allow_declassified_reflection=True, trusted_evaluator=True)
        self.assertEqual(self.kernel.db.execute(
            "SELECT COUNT(*) FROM reflection_attempts").fetchone()[0], 0)


if __name__ == "__main__":
    unittest.main()
