"""17S-26: owner pilot launcher is safe, bounded, and never app sync proof."""
import io
import json
import os
import unittest
from contextlib import redirect_stdout, redirect_stderr
from unittest.mock import patch

from varyn.official_relay_pilot import _STEPS
from varyn.owner_pilot_launcher import (
    _PROJECT_STEPS, combined_owner_report, collect_project_checks,
    main, run_owner_pilot, sanitized_child_environment,
)


class FakeDesktop:
    def __init__(self, *, early_exit=None):
        self.early_exit = early_exit
    def poll(self):
        return self.early_exit


def all_manual(value="pass"):
    return {step: value for step, _ in _STEPS}


def all_project(value="pass"):
    return {step: value for step, _ in _PROJECT_STEPS}


class OwnerPilotLauncherTests(unittest.TestCase):
    def test_no_child_sees_common_credential_env_vars(self):
        source = {
            "OPENAI_API_KEY": "SYNTHETIC_SECRET",
            "anthropic_api_key": "SYNTHETIC_SECRET",
            "GEMINI_API_KEY": "SYNTHETIC_SECRET",
            "AZURE_OPENAI_API_KEY": "SYNTHETIC_SECRET",
            "GH_TOKEN": "SYNTHETIC_SECRET",
            "GITHUB_TOKEN": "SYNTHETIC_SECRET",
            "OTHER_SAFE_VAR": "safe",
            "PATH": "synthetic",
        }
        clean = sanitized_child_environment(source)
        self.assertEqual(clean, {
            "OTHER_SAFE_VAR": "safe", "PATH": "synthetic",
        })
        self.assertNotIn("SYNTHETIC_SECRET", str(clean))
        self.assertEqual(source["OPENAI_API_KEY"], "SYNTHETIC_SECRET")

    def test_launches_real_desktop_module_as_child_without_shell(self):
        calls = []
        def fake_popen(args, **kwargs):
            calls.append((args, kwargs))
            return FakeDesktop()
        outputs = []
        answers = iter(["yes"] * (len(_STEPS) + len(_PROJECT_STEPS)))
        report = run_owner_pilot(
            windows=True, elevated=False, executable="python-test",
            popen=fake_popen, env={
                "OPENAI_API_KEY": "SYNTHETIC_SECRET", "PATH": "okay"},
            input_fn=lambda _prompt: next(answers),
            write=outputs.append,
        )
        self.assertEqual(report, 0)
        self.assertEqual(len(calls), 1)
        args, kwargs = calls[0]
        self.assertEqual(args, ["python-test", "-m", "varyn.desktop"])
        self.assertEqual(kwargs["env"], {"PATH": "okay"})
        self.assertNotIn("shell", kwargs)
        self.assertNotIn("SYNTHETIC_SECRET", str(outputs))
        self.assertIn("OWNER SELF-REPORT ONLY", outputs[-2])
        payload = json.loads(outputs[-3])
        self.assertEqual(payload["status"], "owner_self_reported_pilot_pass")
        self.assertFalse(payload["automatic_bidirectional_consumer_sync_verified"])
        self.assertFalse(payload["official_app_account_access_verified"])
        self.assertFalse(payload["actual_owner_clicks_verified"])
        self.assertFalse(payload["report_upload"])
        self.assertEqual(payload["launcher_network_calls"], 0)

    def test_admin_unknown_or_nonwindows_does_not_spawn(self):
        for windows, elevated in (
            (False, False), (True, True), (True, None),
            ("true", False), (True, "no")
        ):
            with self.subTest(windows=windows, elevated=elevated):
                calls = []
                result = run_owner_pilot(
                    windows=windows, elevated=elevated,
                    popen=lambda *a, **k: calls.append(1),
                    write=lambda _: None,
                )
                self.assertEqual(result, 2)
                self.assertFalse(calls)

    def test_python_launch_failure_and_early_exit_fail_closed(self):
        with patch("varyn.owner_pilot_launcher.collect_manual_pilot") as ask:
            fail = run_owner_pilot(
                windows=True, elevated=False, executable="python-test",
                popen=lambda *a, **k: (_ for _ in ()).throw(OSError("no GUI")),
                write=lambda _: None,
            )
            early = run_owner_pilot(
                windows=True, elevated=False, executable="python-test",
                popen=lambda *a, **k: FakeDesktop(early_exit=1),
                write=lambda _: None,
            )
            self.assertEqual(fail, 2)
            self.assertEqual(early, 2)
            ask.assert_not_called()

    def test_one_skipped_answer_cannot_unlock_project_pilot(self):
        manual = all_manual()
        project = all_project()
        project["project_conflict_shown"] = "not_checked"
        bad = combined_owner_report(manual, project)
        self.assertEqual(bad["status"], "incomplete_or_failed")
        self.assertFalse(bad["safe_private_data_access_authorized"])
        for key in manual:
            changed = dict(manual)
            changed[key] = "fail"
            self.assertEqual(
                combined_owner_report(changed, all_project())["status"],
                "incomplete_or_failed",
            )

    def test_project_report_only_whitelisted_enum_values(self):
        for bad in ("yes", "leak", True, 1, None, [], {}):
            rows = all_project()
            rows["project_note_review"] = bad
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                combined_owner_report(all_manual(), rows)
        for invalid in ({"foo": "pass"}, {}, {
            **all_project(), "extra": "pass"}):
            with self.assertRaises(ValueError):
                combined_owner_report(all_manual(), invalid)

    def test_project_answers_never_expose_user_text(self):
        responses = iter(["yes", "SYNTHETIC_SECRET_STRING", "skip"])
        output = []
        checks = collect_project_checks(
            input_fn=lambda _: next(responses), write=output.append)
        self.assertEqual(list(checks.values()),
                         ["pass", "not_checked", "not_checked"])
        report = json.dumps(combined_owner_report(all_manual(), checks))
        self.assertNotIn("SYNTHETIC_SECRET_STRING", report)

    def test_cli_requires_both_strict_flags(self):
        for args in ([], ["--manual-only"], ["--interactive"],
                     ["--manual-only", "--interactive", "--url",
                      "https://example.test"]):
            with self.subTest(args=args), redirect_stderr(io.StringIO()), \
                 self.assertRaises(SystemExit) as raised:
                main(args)
            self.assertEqual(raised.exception.code, 2)

    def test_report_false_flags_even_all_owner_answers_yes(self):
        good = combined_owner_report(all_manual(), all_project())
        self.assertEqual(good["status"], "owner_self_reported_pilot_pass")
        for key in (
            "actual_owner_clicks_verified",
            "provider_reply_origin_verified",
            "consumer_history_read_authority_verified",
            "consumer_history_write_authority_verified",
            "automatic_bidirectional_consumer_sync_verified",
        ):
            self.assertFalse(good[key])


if __name__ == "__main__":
    unittest.main()
