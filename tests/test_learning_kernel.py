"""Isolated synthetic tests. No real model, network or external credentials."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from varyn.learning_kernel import LearningKernel, LearningRejected

FAMILY = "github_triage"
ONE = "Identify duplicate IDs and verify the source repository before processing issues."
TWO = "Identify duplicates, verify repository scope, and normalize issue labels consistently."

class LearningTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.kernel = LearningKernel(Path(self.temp.name) / "learn.sqlite3")

    def tearDown(self):
        self.kernel.close()
        self.temp.cleanup()

    def evidence(self, start=0):
        return [
            self.kernel.record_verified_outcome(
                FAMILY, "job-" + str(i), "a" * 64,
                succeeded=True, verified_by_host=True)
            for i in range(start, start + 2)
        ]

    def test_verified_only_and_duplicate_deny(self):
        with self.assertRaises(LearningRejected):
            self.kernel.record_verified_outcome(
                FAMILY, "job", "a" * 64, succeeded=True)
        ids = self.evidence()
        with self.assertRaises(LearningRejected):
            self.kernel.propose_skill("other_family", ONE, ids)
        with self.assertRaises(LearningRejected):
            self.kernel.record_verified_outcome(
                FAMILY, "job-0", "a" * 64,
                succeeded=True, verified_by_host=True)

    def test_promotion_persistence(self):
        ident = self.kernel.propose_skill(FAMILY, ONE, self.evidence())
        suite = ("a", "b", "c", "d", "e")
        result = self.kernel.evaluate_and_select(
            ident, suite, lambda text, case: text == ONE and case != "e")
        self.assertTrue(result["accepted"])
        self.assertEqual(result["baseline_passes"], 0)
        self.assertEqual(result["candidate_passes"], 4)
        self.kernel.close()
        self.kernel = LearningKernel(Path(self.temp.name) / "learn.sqlite3")
        self.assertEqual(self.kernel.active_skill(FAMILY)["text"], ONE)
        self.assertEqual(self.kernel.active_skill(FAMILY)["trust"],
                         "untrusted_procedural_reference")

    def test_regressions_block_improvement(self):
        first = self.kernel.propose_skill(FAMILY, ONE, self.evidence())
        suite = ("a", "b", "c", "d", "e")
        self.kernel.evaluate_and_select(
            first, suite, lambda t, c: t == ONE)
        second = self.kernel.propose_skill(FAMILY, TWO, self.evidence(2))
        def judge(t, c):
            return (c in ("a", "b")) if t == ONE else (c in ("b", "c", "d", "e"))
        result = self.kernel.evaluate_and_select(second, suite, judge)
        self.assertFalse(result["accepted"])
        self.assertEqual(result["regressions"], 1)
        self.assertEqual(self.kernel.active_skill(FAMILY)["id"], first)

    def test_rollback(self):
        first = self.kernel.propose_skill(FAMILY, ONE, self.evidence())
        suite = ("a", "b", "c", "d", "e")
        self.kernel.evaluate_and_select(
            first, suite, lambda t, c: t == ONE)
        second = self.kernel.propose_skill(FAMILY, TWO, self.evidence(2))
        self.kernel.evaluate_and_select(
            second, suite, lambda t, c: t == TWO)
        self.assertEqual(self.kernel.active_skill(FAMILY)["id"], second)
        self.kernel.rollback(FAMILY, first)
        self.assertEqual(self.kernel.active_skill(FAMILY)["id"], first)

    def test_stale_candidate_and_invalid_evaluator(self):
        ids = self.evidence()
        first = self.kernel.propose_skill(FAMILY, ONE, ids)
        stale = self.kernel.propose_skill(FAMILY, TWO, ids)
        suite = ("a", "b", "c", "d", "e")
        with self.assertRaises(LearningRejected):
            self.kernel.evaluate_and_select(
                first, suite, lambda t, c: 1)
        self.assertIsNone(self.kernel.active_skill(FAMILY))
        self.kernel.evaluate_and_select(
            first, suite, lambda t, c: t == ONE)
        with self.assertRaises(LearningRejected):
            self.kernel.evaluate_and_select(
                stale, suite, lambda t, c: t == TWO)

    def test_bad_suite_no_side_effects(self):
        ident = self.kernel.propose_skill(FAMILY, ONE, self.evidence())
        for cases in (("x",), ("x",) * 5, ["a", "b", "c", "d", "e"]):
            with self.assertRaises(LearningRejected):
                self.kernel.evaluate_and_select(
                    ident, cases, lambda t, c: True)
        self.assertIsNone(self.kernel.active_skill(FAMILY))

if __name__ == "__main__":
    unittest.main()
