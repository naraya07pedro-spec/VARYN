"""17I: owner GUI checks are only bounded self-report, never auto-verified."""
import io
import json
import unittest
from contextlib import redirect_stdout, redirect_stderr
from unittest.mock import patch

from varyn.owner_acceptance import (
    _STEPS,
    build_owner_report,
    collect_owner_observations,
    main,
)


def answers(value="pass"):
    return {key: value for key, _ in _STEPS}


class BoundedHumanAttestationTests(unittest.TestCase):
    def test_all_pass_is_still_owner_report_not_independent_verification(self):
        result = build_owner_report({"passed": True}, answers())
        self.assertEqual(result["acceptance_status"], "owner_self_reported_pass")
        self.assertEqual(
            result["report_kind"], "owner_self_attested_not_independently_verified"
        )
        self.assertFalse(result["independently_verified_on_owner_pc"])
        self.assertFalse(result["gui_clicks_observed_by_automated_test"])
        self.assertFalse(result["automatic_official_app_sync_verified"])
        self.assertFalse(result["official_apps_connected"])
        self.assertFalse(result["identity_authenticated"])

    def test_synthetic_failure_blocks_even_all_positive_owner_answers(self):
        result = build_owner_report({"passed": False}, answers())
        self.assertFalse(result["synthetic_cli_passed"])
        self.assertEqual(result["acceptance_status"], "incomplete_or_failed")

    def test_any_failed_step_prevents_self_reported_pass(self):
        for step, _ in _STEPS:
            with self.subTest(step=step):
                values = answers()
                values[step] = "fail"
                result = build_owner_report({"passed": True}, values)
                self.assertEqual(result["acceptance_status"], "incomplete_or_failed")

    def test_skipped_step_cannot_be_counted_as_pass(self):
        values = answers()
        values["revoke_denies"] = "not_checked"
        report = build_owner_report({"passed": True}, values)
        self.assertFalse(report["owner_reported_all_passed"])
        self.assertEqual(report["acceptance_status"], "incomplete_or_failed")

    def test_refuses_extra_or_missing_fields(self):
        for values in ({}, {**answers(), "extra": "pass"},
                       {key: "pass" for key, _ in _STEPS[1:]}):
            with self.subTest(values=values), self.assertRaises(ValueError):
                build_owner_report({"passed": True}, values)

    def test_rejects_non_string_and_free_text_observations(self):
        for malicious in (True, 1, None, [], "yes", "pass\nsecret", "C:\\private"):
            values = answers()
            values["no_private_data"] = malicious
            with self.subTest(value=malicious), self.assertRaises(ValueError):
                build_owner_report({"passed": True}, values)

    def test_rejects_fake_or_untyped_synthetic_evidence(self):
        for value in (None, True, [], {}, {"passed": 1}, {"passed": "true"}):
            with self.subTest(value=value), self.assertRaises(ValueError):
                build_owner_report(value, answers())

    def test_collector_only_accepts_exact_yes_no_skip(self):
        values = iter(["yes", "no", "skip", "yes please", "", " YES ", "yes", "no"])
        spoken = []
        got = collect_owner_observations(
            read_input=lambda _prompt: next(values),
            write=spoken.append,
        )
        self.assertEqual(
            list(got.values()),
            ["pass", "fail", "not_checked", "not_checked", "not_checked", "pass", "pass", "fail"],
        )
        self.assertTrue(any("normal-user terminal" in line for line in spoken))

    def test_parent_review_is_required_for_full_owner_self_report(self):
        reports = answers()
        reports["parent_count_denied"] = "not_checked"
        self.assertEqual(
            build_owner_report({"passed": True}, reports)["acceptance_status"],
            "incomplete_or_failed",
        )
        reports = answers()
        reports["parent_count_approved"] = "fail"
        self.assertEqual(
            build_owner_report({"passed": True}, reports)["acceptance_status"],
            "incomplete_or_failed",
        )

    def test_eof_marks_remaining_observation_unchecked(self):
        report = collect_owner_observations(
            read_input=lambda _: (_ for _ in ()).throw(EOFError),
            write=lambda _: None,
        )
        self.assertEqual(list(report.values()), ["not_checked"] * len(_STEPS))

    def test_output_does_not_echo_raw_free_text_or_paths(self):
        user_answers = iter(["yes", "yes", "yes", "SECRET_PASSWORD", "yes", "yes", "yes", "yes"])
        spoken = []
        obs = collect_owner_observations(
            read_input=lambda _prompt: next(user_answers),
            write=spoken.append,
        )
        result = build_owner_report({"passed": True}, obs)
        serialized = json.dumps(result)
        self.assertNotIn("SECRET_PASSWORD", serialized)
        self.assertNotIn("C:\\", serialized)
        self.assertEqual(result["owner_reported_checks"]["no_private_data"],
                         "not_checked")
        self.assertEqual(result["provider_requests_by_report_tool"], 0)
        self.assertFalse(result["report_saved_to_disk_by_tool"])

    def test_cli_requires_opt_in_flags(self):
        for parameters in ([], ["--interactive"], ["--synthetic-only"],
                           ["--synthetic-only", "--interactive", "--folder", "C:\\private"]):
            with self.subTest(args=parameters), \
                 redirect_stderr(io.StringIO()), \
                 self.assertRaises(SystemExit) as error:
                main(parameters)
            self.assertEqual(error.exception.code, 2)

    def test_cli_success_still_prints_self_report_only(self):
        output = io.StringIO()
        with patch("varyn.owner_acceptance.run_synthetic_acceptance",
                   return_value={"passed": True}), \
             patch("varyn.owner_acceptance.collect_owner_observations",
                   return_value=answers()), \
             redirect_stdout(output):
            exit_code = main(["--synthetic-only", "--interactive"])
        self.assertEqual(exit_code, 0)
        self.assertIn('"independently_verified_on_owner_pc": false',
                      output.getvalue())
        self.assertIn("SELF-REPORT", output.getvalue())

    def test_cli_failed_observation_exits_nonzero(self):
        observation = answers()
        observation["gui_opened"] = "fail"
        with patch("varyn.owner_acceptance.run_synthetic_acceptance",
                   return_value={"passed": True}), \
             patch("varyn.owner_acceptance.collect_owner_observations",
                   return_value=observation), \
             redirect_stdout(io.StringIO()):
            self.assertEqual(
                main(["--synthetic-only", "--interactive"]), 1
            )


if __name__ == "__main__":
    unittest.main()
