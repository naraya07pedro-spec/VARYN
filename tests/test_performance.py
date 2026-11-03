"""Test instrumentation behavior, not arbitrary speed thresholds."""
import json
import unittest
from varyn.performance import run_benchmark


class PerformanceBenchmarkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = run_benchmark(rows=40, repeats=2)

    def test_synthetic_provenance_and_historical_anchor(self):
        self.assertEqual(self.report["dataset"], "deterministic synthetic only")
        self.assertTrue(self.report["historical_anchor_retrieved"])

    def test_samples_and_monotonic_ranges(self):
        r = self.report
        self.assertEqual(r["rows"], 40)
        self.assertEqual(r["repeats"], 2)
        self.assertEqual(len(r["returned_items_per_query"]), 2)
        self.assertTrue(all(n > 0 for n in r["returned_items_per_query"]))
        self.assertLessEqual(r["query_ms_min"], r["query_ms_median"])
        self.assertLessEqual(r["query_ms_median"], r["query_ms_max"])
        self.assertGreaterEqual(r["index_build_ms"], 0)
        self.assertGreater(r["db_main_file_bytes_after_index"], 0)

    def test_memory_limits_and_serializable_output(self):
        self.assertIn("native SQLite", self.report["measurement_limits"])
        self.assertIn("process RSS", self.report["measurement_limits"])
        self.assertGreaterEqual(self.report["query_python_traced_peak_bytes_max"], 0)
        json.dumps(self.report)

    def test_invalid_inputs_rejected(self):
        for kwargs in (
            {"rows": True}, {"rows": 19}, {"rows": 5001},
            {"repeats": 0}, {"repeats": 21}, {"repeats": True},
        ):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                run_benchmark(**kwargs)


if __name__ == "__main__":
    unittest.main()
