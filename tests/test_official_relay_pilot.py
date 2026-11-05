"""17S-23: owner manual official app self-report is never verified app sync."""
import io
import json
import unittest
from contextlib import redirect_stdout, redirect_stderr
from unittest.mock import patch

from varyn.official_relay_pilot import (
    _STEPS, build_manual_pilot_report, collect_manual_pilot, main,
)


def all_answers(value="pass"):
    return {key: value for key, _ in _STEPS}


class ManualOwnerPilotTests(unittest.TestCase):
    def test_all_positive_owner_answers_are_still_unverified(self):
        report = build_manual_pilot_report(all_answers())
        self.assertEqual(report["status"], "owner_self_reported_manual_pilot_pass")
        self.assertEqual(report["report_kind"],
                         "owner_self_report_not_independently_verified")
        self.assertFalse(report["automatic_two_way_sync_verified"])
        self.assertFalse(report["official_consumer_history_read_verified"])
        self.assertFalse(report["official_consumer_history_write_verified"])
        self.assertFalse(report["official_app_accounts_authenticated_by_varyn"])
        self.assertFalse(report["provider_reply_origin_verified"])
        self.assertFalse(report["human_clicks_observed_by_ci"])
        self.assertFalse(report["can_dispatch"])
        self.assertFalse(report["report_saved_or_uploaded_by_tool"])
        self.assertEqual(report["network_calls_by_report_tool"], 0)

    def test_every_failed_or_skipped_step_blocks_passing(self):
        for step, _ in _STEPS:
            for failure in ("fail", "not_checked"):
                with self.subTest(step=step, failure=failure):
                    answers = all_answers()
                    answers[step] = failure
                    self.assertEqual(
                        build_manual_pilot_report(answers)["status"],
                        "incomplete_or_failed",
                    )

    def test_reject_missing_extra_non_str_and_forbidden_free_text(self):
        cases = [{}, {"other": "pass"}, {**all_answers(), "extra": "pass"}]
        for bad in (False, 1, None, [], {}, "yes", "C:\\my-private-chat",
                    "pass\nadmin"):
            row = all_answers()
            row["approved_packet_pasted"] = bad
            cases.append(row)
        for case in cases:
            with self.subTest(case=case), self.assertRaises(ValueError):
                build_manual_pilot_report(case)

    def test_collection_accepts_only_fixed_inputs(self):
        values = iter(["yes", "no", "skip", "  YES ", "please yes",
                       "nothing", "yes"])
        printed = []
        result = collect_manual_pilot(
            read_input=lambda _: next(values), write=printed.append)
        self.assertEqual(list(result.values()), [
            "pass", "fail", "not_checked", "pass",
            "not_checked", "not_checked", "pass",
        ])
        self.assertTrue(any("normal-user Windows terminal" in x for x in printed))

    def test_eof_cannot_auto_pass(self):
        result = collect_manual_pilot(
            read_input=lambda _: (_ for _ in ()).throw(EOFError),
            write=lambda _: None,
        )
        self.assertEqual(list(result.values()), ["not_checked"] * len(_STEPS))

    def test_reports_no_arbitrary_typed_content(self):
        values = iter(["yes", "yes", "TOP_SECRET_NON_REPLY", "yes",
                       "yes", "yes", "yes"])
        rows = collect_manual_pilot(
            read_input=lambda _: next(values), write=lambda _: None)
        report = json.dumps(build_manual_pilot_report(rows))
        self.assertNotIn("TOP_SECRET_NON_REPLY", report)
        self.assertNotIn("C:\\", report)
        self.assertEqual(rows["denied_copy_kept_clipboard"], "not_checked")

    def test_cli_refuses_unapproved_flags(self):
        for args in ([], ["--manual-only"], ["--interactive"],
                     ["--manual-only", "--interactive", "--url",
                      "https://example.com"]):
            with self.subTest(args=args), \
                 redirect_stderr(io.StringIO()), \
                 self.assertRaises(SystemExit) as raised:
                main(args)
            self.assertEqual(raised.exception.code, 2)

    def test_all_yes_cli_exit_zero_but_still_self_report(self):
        output = io.StringIO()
        with patch("varyn.official_relay_pilot.collect_manual_pilot",
                   return_value=all_answers()), redirect_stdout(output):
            self.assertEqual(main(["--manual-only", "--interactive"]), 0)
        self.assertIn("SELF-REPORT ONLY", output.getvalue())
        self.assertIn('"automatic_two_way_sync_verified": false',
                      output.getvalue())

    def test_skipped_cli_exits_nonzero(self):
        output = io.StringIO()
        values = all_answers()
        values["external_launch_consent"] = "not_checked"
        with patch("varyn.official_relay_pilot.collect_manual_pilot",
                   return_value=values), redirect_stdout(output):
            self.assertEqual(main(["--manual-only", "--interactive"]), 1)


if __name__ == "__main__":
    unittest.main()
