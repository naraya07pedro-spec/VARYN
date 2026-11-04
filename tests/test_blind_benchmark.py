"""17R blind A/B benchmark protocol without any real provider calls."""
import copy
import unittest

from varyn.blind_benchmark import prepare_blinded, score_blinded, synthetic_demo
from varyn.reasoning_eval import EvaluationError

SECRET = "organizer-controlled-private-seed"
DIMS = ("accuracy", "reasoning", "creativity", "usefulness")


def sample(case_id="example"):
    return {
        "case_id": case_id,
        "task": "SYNTHETIC: choose a local workflow design",
        "single": "Offline with consent and backup.",
        "collaboration": "Offline, consent, recovery, backups and limits.",
        "single_meta": {
            "requested_models": ["fake-test"],
            "requests": 1,
            "reserved_output_tokens": 768,
            "reported_input_tokens": None,
            "reported_output_tokens": None,
            "elapsed_ms": None,
            "api_cost_usd": None,
            "provider_attested": False,
        },
        "collaboration_meta": {
            "requested_models": ["fake-test", "fake-test", "fake-test"],
            "requests": 3,
            "reserved_output_tokens": 768,
            "reported_input_tokens": None,
            "reported_output_tokens": None,
            "elapsed_ms": None,
            "api_cost_usd": None,
            "provider_attested": False,
        },
    }


def score_record(case_id, rater, a=4, b=3):
    return {
        "case_id": case_id,
        "rater_id": rater,
        "A": {dim: a for dim in DIMS},
        "B": {dim: b for dim in DIMS},
    }


class BlindBenchmarkTests(unittest.TestCase):
    def test_synthetic_demo_exposes_positive_and_negative_cases(self):
        a = synthetic_demo()
        self.assertEqual(a, synthetic_demo())
        self.assertTrue(a["synthetic_demo_only"])
        self.assertFalse(a["real_model_outputs_used"])
        self.assertEqual(a["cases"], 2)
        self.assertFalse(a["performance_superiority_proven"])
        deltas = [
            x["collaboration_minus_single"]["accuracy"]
            for x in a["results"]
        ]
        self.assertTrue(any(x > 0 for x in deltas))
        self.assertTrue(any(x < 0 for x in deltas))

    def test_blind_packets_reveal_neither_model_identity_nor_mapping(self):
        packet, key = prepare_blinded([sample()], organizer_secret=SECRET)
        self.assertEqual(packet["format"], "varyn.blind_packet.v1")
        self.assertEqual(key["format"], "varyn.organizer_key.v1")
        self.assertEqual(len(packet["cases"]), 1)
        self.assertTrue(packet["cases"][0]["A"])
        self.assertTrue(packet["cases"][0]["B"])
        self.assertEqual(set(key["mapping"]["example"].values()),
                         {"single", "collaboration"})
        self.assertNotIn("fake-test", str(packet))
        self.assertNotIn("provider_attested", str(packet))
        self.assertNotIn(SECRET, str(packet))
        self.assertNotIn(SECRET, str(key))
        self.assertEqual(packet["network_calls"], 0)

    def test_same_secret_yields_identical_packet_order(self):
        a, ka = prepare_blinded([sample()], organizer_secret=SECRET)
        b, kb = prepare_blinded([sample()], organizer_secret=SECRET)
        self.assertEqual(a, b)
        self.assertEqual(ka, kb)

    def test_rating_report_marks_unverified_and_unmatched_actual_tokens(self):
        packet, key = prepare_blinded([sample()], organizer_secret=SECRET)
        ratings = [
            score_record("example", "rater_1", a=4, b=3),
            score_record("example", "rater_2", a=5, b=2),
        ]
        result = score_blinded(packet, key, ratings)
        self.assertEqual(result["cases"], 1)
        self.assertEqual(result["raters_per_case_min"], 2)
        self.assertFalse(result["all_token_budgets_matched"])
        self.assertFalse(result["all_providers_attested"])
        self.assertFalse(result["performance_superiority_proven"])
        self.assertFalse(result["human_independence_authenticated"])
        self.assertEqual(result["network_calls"], 0)
        scores = result["results"][0]
        self.assertEqual(scores["request_count_collaboration"], 3)
        self.assertEqual(scores["request_count_single"], 1)
        self.assertIn("accuracy", scores["rater_score_range"]["single"])

    def test_blind_key_reverses_A_B_without_mean_score_changes(self):
        packet, key = prepare_blinded([sample()], organizer_secret=SECRET)
        first = score_record("example", "rater_1", a=5, b=1)
        second = score_record("example", "rater_2", a=5, b=1)
        original = score_blinded(packet, key, [first, second])
        # When mapping is reversed, the same blinded A/B ratings reverse sign.
        altered = copy.deepcopy(key)
        altered["mapping"]["example"]["A"], altered["mapping"]["example"]["B"] = (
            altered["mapping"]["example"]["B"], altered["mapping"]["example"]["A"]
        )
        reversed_result = score_blinded(packet, altered, [first, second])
        a = original["results"][0]["collaboration_minus_single"]["accuracy"]
        b = reversed_result["results"][0]["collaboration_minus_single"]["accuracy"]
        self.assertEqual(a, -b)

    def test_two_distinct_raters_required_every_task(self):
        packet, key = prepare_blinded([sample()], organizer_secret=SECRET)
        with self.assertRaises(EvaluationError):
            score_blinded(packet, key, [score_record("example", "rater_1")])
        with self.assertRaises(EvaluationError):
            score_blinded(packet, key, [
                score_record("example", "rater_1"),
                score_record("example", "rater_1"),
            ])

    def test_malformed_scores_rejected_fail_closed(self):
        packet, key = prepare_blinded([sample()], organizer_secret=SECRET)
        for bad in (0, 6, 2.2, True, "5", None):
            records = [score_record("example", "first_rater"),
                       score_record("example", "second_rater")]
            records[0]["A"]["accuracy"] = bad
            with self.subTest(bad=bad), self.assertRaises(EvaluationError):
                score_blinded(packet, key, records)

    def test_tampering_with_packet_is_detected(self):
        packet, key = prepare_blinded([sample()], organizer_secret=SECRET)
        packet = copy.deepcopy(packet)
        packet["cases"][0]["A"] = "ALTERED!"
        with self.assertRaises(EvaluationError):
            score_blinded(packet, key, [
                score_record("example", "first_rater"),
                score_record("example", "second_rater"),
            ])

    def test_missing_case_or_extra_case_refused(self):
        cases = [sample("first"), sample("second")]
        packet, key = prepare_blinded(cases, organizer_secret=SECRET)
        with self.assertRaises(EvaluationError):
            score_blinded(packet, key, [
                score_record("first", "person_a"),
                score_record("first", "person_b"),
            ])
        with self.assertRaises(EvaluationError):
            score_blinded(packet, key, [
                score_record("first", "person_a"),
                score_record("first", "person_b"),
                score_record("third", "person_a"),
                score_record("second", "person_a"),
                score_record("second", "person_b"),
            ])

    def test_duplicate_cases_and_case_count_limit(self):
        with self.assertRaises(EvaluationError):
            prepare_blinded([sample("a"), sample("a")], organizer_secret=SECRET)
        with self.assertRaises(EvaluationError):
            prepare_blinded([sample(f"c{i}") for i in range(31)],
                            organizer_secret=SECRET)
        with self.assertRaises(EvaluationError):
            prepare_blinded([], organizer_secret=SECRET)

    def test_invalid_budget_and_provider_claim_fail_before_blinding(self):
        for field, invalid in (
            ("requests", 0),
            ("requests", True),
            ("reserved_output_tokens", 0),
            ("reported_input_tokens", -1),
            ("elapsed_ms", "10"),
            ("provider_attested", 1),
            ("api_cost_usd", -1.0),
        ):
            case = sample()
            case["single_meta"][field] = invalid
            with self.subTest(field=field), self.assertRaises(EvaluationError):
                prepare_blinded([case], organizer_secret=SECRET)

    def test_reject_malformed_secret_task_and_schema(self):
        with self.assertRaises(EvaluationError):
            prepare_blinded([sample()], organizer_secret="short")
        for edit in (lambda c: c.update(task=""),
                     lambda c: c.update(unknown=True),
                     lambda c: c.update(single=""),
                     lambda c: c.update(case_id="bad identifier")):
            case = sample()
            edit(case)
            with self.assertRaises(EvaluationError):
                prepare_blinded([case], organizer_secret=SECRET)

    def test_budget_equal_and_reported_tokens_equal_marked_only_as_token_match(self):
        case = sample()
        case["single_meta"]["reported_input_tokens"] = 300
        case["collaboration_meta"]["reported_input_tokens"] = 300
        packet, key = prepare_blinded([case], organizer_secret=SECRET)
        result = score_blinded(packet, key, [
            score_record("example", "person_one"),
            score_record("example", "person_two"),
        ])
        self.assertTrue(result["all_token_budgets_matched"])
        self.assertFalse(result["performance_superiority_proven"])
        self.assertFalse(result["all_providers_attested"])

    def test_exact_dimension_keys_and_rater_names(self):
        packet, key = prepare_blinded([sample()], organizer_secret=SECRET)
        reviews = [score_record("example", "person_one"),
                   score_record("example", "person_two")]
        reviews[0]["A"]["made_up"] = 5
        with self.assertRaises(EvaluationError):
            score_blinded(packet, key, reviews)
        reviews = [score_record("example", "one"),
                   score_record("example", "bad name")]
        with self.assertRaises(EvaluationError):
            score_blinded(packet, key, reviews)


if __name__ == "__main__":
    unittest.main()
