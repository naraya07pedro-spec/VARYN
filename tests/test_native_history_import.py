"""17S-30: legitimate official export-to-Gemini USER-DRIVEN history import gates."""
from dataclasses import replace
import unittest

from varyn.native_history_import import (
    NativeHistoryRejected, NativeHistoryTransfer, native_destination_info,
    source_export_instructions,
)


def acknowledgements():
    return {
        "adult_personal_account": True,
        "supported_region": True,
        "zip_export_ready": True,
        "google_activity_privacy_ack": True,
    }


class NativeOneTimeImportTests(unittest.TestCase):
    def setUp(self):
        self.tick = [1000]
        self.guide = NativeHistoryTransfer(clock=lambda: self.tick[0])

    def test_only_supported_one_way_sources_have_official_guides(self):
        for source in ("chatgpt", "claude"):
            d = source_export_instructions(source)
            self.assertEqual(d["source"], source)
            self.assertTrue(d["export_guide_url"].startswith("https://"))
            self.assertTrue(d["manual_export_only"])
            self.assertFalse(d["accounts_accessed"])
            self.assertFalse(d["local_zip_opened"])
        for source in ("gemini", "anthropic_api", "ChatGPT", "", None,
                       "../claude", "fake"):
            with self.subTest(source=source), self.assertRaises(
                    NativeHistoryRejected):
                source_export_instructions(source)
        dest = native_destination_info()
        self.assertEqual(dest["destination_url"], "https://gemini.google.com/")
        self.assertTrue(dest["provider_supports_manual_native_zip_import"])
        self.assertFalse(dest["automatic_history_sync"])
        self.assertFalse(dest["data_is_uploaded_by_varyn"])
        self.assertIn("Google Activity", dest["privacy_warning"])

    def test_four_explicit_true_acknowledgements_required(self):
        for key in acknowledgements():
            for val in (False, "yes", 1, None):
                with self.subTest(key=key, val=val):
                    ack = acknowledgements()
                    ack[key] = val
                    with self.assertRaises(NativeHistoryRejected):
                        self.guide.prepare("chatgpt", ack)
        for bad in ({"adult_personal_account": True}, {},
                    {**acknowledgements(), "extra": True}, "yes", None):
            with self.assertRaises(NativeHistoryRejected):
                self.guide.prepare("chatgpt", bad)
        self.assertFalse(self.guide.status()["official_browser_launch_requested"])

    def test_review_replay_and_forged_preview_fail_closed(self):
        a = acknowledgements()
        token = self.guide.prepare("claude", a)
        self.assertFalse(token.provider_authority_verified)
        self.assertEqual(token.source, "claude")
        self.assertEqual(token.target, "https://gemini.google.com/")
        with self.assertRaises(NativeHistoryRejected):
            self.guide.prepare("claude", a)
        with self.assertRaises(NativeHistoryRejected):
            self.guide.decide(replace(token), approved=True,
                              browser_opened=True, acknowledgements=a)
        with self.assertRaises(NativeHistoryRejected):
            self.guide.decide(replace(token, source="chatgpt"),
                              approved=True, browser_opened=True,
                              acknowledgements=a)
        self.assertFalse(self.guide.status()["official_browser_launch_requested"])
        result = self.guide.decide(token, approved=True, browser_opened=True,
                                   acknowledgements=a)
        self.assertEqual(result["status"], "official_browser_open_requested")
        self.assertFalse(result["provider_verified"])
        with self.assertRaises(NativeHistoryRejected):
            self.guide.decide(token, approved=True, browser_opened=True,
                              acknowledgements=a)
        with self.assertRaises(NativeHistoryRejected):
            self.guide.prepare("claude", a)

    def test_declined_or_browser_failure_is_not_import(self):
        a = acknowledgements()
        token = self.guide.prepare("chatgpt", a)
        declined = self.guide.decide(token, approved=False,
                                     browser_opened=False, acknowledgements=a)
        self.assertEqual(declined["status"], "declined")
        self.assertFalse(self.guide.status()["official_browser_launch_requested"])
        token = self.guide.prepare("chatgpt", a)
        fail = self.guide.decide(token, approved=True, browser_opened=False,
                                 acknowledgements=a)
        self.assertEqual(fail["status"], "browser_not_opened")
        self.assertFalse(self.guide.status()["official_browser_launch_requested"])
        with self.assertRaises(NativeHistoryRejected):
            self.guide.report("owner_reported_uploaded")

    def test_change_in_privacy_during_review_refuses(self):
        a = acknowledgements()
        token = self.guide.prepare("chatgpt", a)
        changed = dict(a, google_activity_privacy_ack=False)
        with self.assertRaises(NativeHistoryRejected):
            self.guide.decide(token, approved=True, browser_opened=True,
                              acknowledgements=changed)
        self.assertFalse(self.guide.status()["official_browser_launch_requested"])
        self.assertFalse(self.guide.status()["pending_owner_review"])

    def test_expired_review_refuses_even_with_open_claim(self):
        a = acknowledgements()
        token = self.guide.prepare("chatgpt", a)
        self.tick[0] = token.expires_at + 1
        with self.assertRaises(NativeHistoryRejected):
            self.guide.decide(token, approved=True, browser_opened=True,
                              acknowledgements=a)
        self.assertFalse(self.guide.status()["official_browser_launch_requested"])

    def test_reset_revokes_staged_review_and_owner_report(self):
        a = acknowledgements()
        token = self.guide.prepare("chatgpt", a)
        self.guide.reset()
        with self.assertRaises(NativeHistoryRejected):
            self.guide.decide(token, approved=True, browser_opened=True,
                              acknowledgements=a)
        token = self.guide.prepare("chatgpt", a)
        self.guide.decide(token, approved=True, browser_opened=True,
                          acknowledgements=a)
        self.guide.report("owner_reported_uploaded")
        self.assertEqual(self.guide.status()["owner_unverified_result"],
                         "owner_reported_uploaded")
        self.assertFalse(self.guide.status()["provider_side_import_verified"])
        self.guide.reset()
        self.assertIsNone(self.guide.status()["source_claim"])
        self.assertEqual(self.guide.status()["owner_unverified_result"],
                         "not_reported")
        self.assertFalse(self.guide.status()["official_browser_launch_requested"])

    def test_fixed_self_reports_do_not_unlock_option_c(self):
        a = acknowledgements()
        token = self.guide.prepare("claude", a)
        self.guide.decide(token, approved=True, browser_opened=True,
                          acknowledgements=a)
        for label in ("not_checked", "owner_reported_partial",
                      "owner_reported_failed", "owner_reported_uploaded"):
            report = self.guide.report(label)
            self.assertFalse(report["provider_side_import_verified"])
            self.assertFalse(report["automatic_bidirectional_consumer_sync_verified"])
            self.assertFalse(report["app_history_read_api_verified"])
            self.assertFalse(report["app_history_write_api_verified"])
            self.assertFalse(report["zip_read_by_varyn"])
            self.assertFalse(report["zip_path_seen_by_varyn"])
            self.assertFalse(report["data_uploaded_by_varyn"])
            self.assertEqual(report["network_requests_by_state_machine"], 0)
        for value in (True, "done", "", None, "verified"):
            with self.assertRaises(NativeHistoryRejected):
                self.guide.report(value)

    def test_no_unreviewed_pretend_browser_success(self):
        for bad_approved, bad_opened in (
            (1, True), ("yes", True), (True, 1), (True, "yes"),
        ):
            self.guide.reset()
            a = acknowledgements()
            token = self.guide.prepare("chatgpt", a)
            with self.assertRaises(NativeHistoryRejected):
                self.guide.decide(token, approved=bad_approved,
                                  browser_opened=bad_opened,
                                  acknowledgements=a)
            self.guide.reset()
        a = acknowledgements()
        token = self.guide.prepare("claude", a)
        with self.assertRaises(NativeHistoryRejected):
            self.guide.decide(token, approved=False, browser_opened=True,
                              acknowledgements=a)

    def test_no_real_zip_path_persisted_in_public_status(self):
        import json
        self.guide.prepare("chatgpt", acknowledgements())
        report = json.dumps(self.guide.status(), sort_keys=True)
        for forbidden in ("credentials.json", "conversations.json",
                          "user_email", "chat_history_contents",
                          "outbound_packet", "absolute_file_path"):
            self.assertNotIn(forbidden, report)


if __name__ == "__main__":
    unittest.main()
