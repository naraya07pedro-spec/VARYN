"""Evaluation methodology and known limitations must remain visible."""
import json
import unittest
from varyn.evaluation import run_evaluation


class RetrievalEvaluationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = run_evaluation()
        cls.cases = {c["case"]: c for c in cls.report["cases"]}

    def test_known_literal_match(self):
        self.assertTrue(self.cases["literal_memory"]["hit"])

    def test_latest_revision_is_retrieved(self):
        self.assertTrue(self.cases["latest_revision"]["hit"])

    def test_project_exclusion_is_correct_rejection(self):
        self.assertTrue(self.cases["other_project_excluded"]["hit"])
        self.assertEqual(self.cases["other_project_excluded"]["returned"], [])

    def test_bilingual_glossary_recovers_storage_alias(self):
        self.assertTrue(self.cases["bilingual_storage_alias"]["hit"])
        self.assertEqual(self.cases["bilingual_storage_alias"]["status"], "matched")

    def test_index_finds_old_relevant_record(self):
        self.assertTrue(self.cases["historical_index_hit"]["hit"])

    def test_budget_failure_is_not_hidden(self):
        self.assertFalse(self.cases["over_budget"]["hit"])
        self.assertEqual(self.cases["over_budget"]["status"], "matches_exceeded_budget")

    def test_metrics_are_reproducible_and_not_inflated(self):
        m = self.report["metrics"]
        self.assertEqual(m["positive_cases"], 5)
        self.assertEqual(m["negative_cases"], 1)
        self.assertEqual(m["positive_hit_rate"], 0.8)
        self.assertEqual(m["positive_mrr"], 0.8)
        self.assertEqual(m["negative_correct_rejection_rate"], 1.0)
        self.assertEqual(self.report["dataset_type"], "hand_labeled_synthetic_only")

    def test_report_is_json_serializable(self):
        self.assertEqual(
            json.loads(json.dumps(self.report))["benchmark"],
            "varyn.synthetic.retrieval.v1",
        )


if __name__ == "__main__":
    unittest.main()
