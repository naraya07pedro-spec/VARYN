"""17S-27: bounded, non-PII local callback outcomes, never human/app proof."""
import json
import unittest

from varyn.local_pilot_audit import PilotLocalAudit, PilotAuditRejected


class LocalPilotAuditTests(unittest.TestCase):
    def setUp(self):
        self.audit = PilotLocalAudit()

    def test_off_by_default_and_start_is_explicit(self):
        self.assertFalse(self.audit.snapshot()["active"])
        self.assertFalse(
            self.audit.record("approved_packet_copied", provider="chatgpt")
        )
        self.assertEqual(self.audit.snapshot()["events_observed"], 0)
        self.audit.start()
        self.assertTrue(self.audit.snapshot()["active"])
        with self.assertRaises(PilotAuditRejected):
            self.audit.start()

    def test_no_outbound_claim_just_from_launching_homepage(self):
        self.audit.start()
        self.assertTrue(self.audit.record(
            "homepage_launch_requested", provider="chatgpt"
        ))
        state = self.audit.snapshot()
        self.assertEqual(state["approved_clipboard_targets"], [])
        self.assertFalse(state["local_two_target_attempt_observed"])
        self.assertFalse(state["official_account_authenticated"])
        self.assertFalse(state["remote_paste_or_delivery_verified"])

    def test_two_different_approved_clipboard_targets_still_not_external_proof(self):
        self.audit.start()
        self.audit.record("approved_packet_copied", provider="chatgpt")
        self.audit.record("reviewed_reply_staged", provider="chatgpt")
        self.assertFalse(self.audit.snapshot()["local_two_target_attempt_observed"])
        self.audit.record("approved_packet_copied", provider="claude")
        result = self.audit.snapshot()
        self.assertTrue(result["local_two_target_attempt_observed"])
        self.assertEqual(result["approved_clipboard_targets"], ["chatgpt", "claude"])
        for forbidden in (
            "independent_human_click_verified",
            "official_account_authenticated",
            "remote_paste_or_delivery_verified",
            "pasted_reply_provider_origin_verified",
            "official_consumer_history_read_verified",
            "official_consumer_history_write_verified",
            "automatic_bidirectional_sync_verified",
            "production_private_access_authorized",
            "tamper_evident_or_signed",
            "stored_on_disk_or_uploaded_by_recorder",
        ):
            self.assertFalse(result[forbidden], forbidden)

    def test_only_known_events_and_exact_provider_allowlist(self):
        self.audit.start()
        for code, provider in (
            ("shell_command", None),
            ("approved_packet_copied", "chatgpt.com/?access_token=secret"),
            ("approved_packet_copied", None),
            ("working_note_reviewed", "claude"),
            (0, None),
            ("homepage_launch_requested", "CHATGPT"),
            ("homepage_launch_requested", "openai"),
            ("reviewed_reply_staged", True),
        ):
            with self.subTest(code=code, provider=provider):
                with self.assertRaises(PilotAuditRejected):
                    self.audit.record(code, provider=provider)
        self.assertEqual(self.audit.snapshot()["events_observed"], 0)

    def test_fixed_json_never_exposes_prompt_reply_credentials_or_ids(self):
        self.audit.start()
        self.audit.record("approved_packet_copied", provider="gemini")
        self.audit.record("working_note_reviewed")
        serialized = self.audit.export_fixed_json()
        report = json.loads(serialized)
        self.assertEqual(report["event_counts"]["approved_packet_copied"], 1)
        self.assertEqual(report["event_counts"]["working_note_reviewed"], 1)
        self.assertNotIn("SECRET", serialized)
        self.assertNotIn("SYNTHETIC:", serialized)
        self.assertNotIn("outbound_request_id", serialized)
        self.assertNotIn("reply_digest", serialized)
        self.assertNotIn("clipboard_contents", serialized)
        self.assertNotIn("event_timestamp", serialized)

    def test_strict_capacity_no_truncation_or_false_fresh_report(self):
        self.audit.start()
        for _ in range(32):
            self.audit.record("relay_state_discarded")
        self.assertEqual(self.audit.snapshot()["events_observed"], 32)
        with self.assertRaises(PilotAuditRejected):
            self.audit.record("working_context_discarded")
        self.assertEqual(self.audit.snapshot()["events_observed"], 32)
        self.assertEqual(self.audit.snapshot()["event_capacity"], 32)

    def test_reset_revokes_prior_log_and_audit_stays_off(self):
        self.audit.start()
        self.audit.record("working_note_reviewed")
        self.audit.reset()
        self.assertEqual(self.audit.snapshot()["events_observed"], 0)
        self.assertEqual(self.audit.snapshot()["approved_clipboard_targets"], [])
        self.assertFalse(self.audit.snapshot()["active"])
        self.assertFalse(self.audit.record("working_note_reviewed"))
        self.audit.start()
        self.assertEqual(self.audit.snapshot()["events_observed"], 0)

    def test_local_context_and_discard_counts_are_only_callback_records(self):
        self.audit.start()
        self.audit.record("working_note_reviewed")
        self.audit.record("project_context_included_in_copy", provider="gemini")
        self.audit.record("working_context_discarded")
        self.audit.record("relay_state_discarded")
        s = self.audit.snapshot()["event_counts"]
        self.assertEqual(s["working_note_reviewed"], 1)
        self.assertEqual(s["project_context_included_in_copy"], 1)
        self.assertEqual(s["working_context_discarded"], 1)
        self.assertEqual(s["relay_state_discarded"], 1)
        self.assertFalse(self.audit.snapshot()["local_two_target_attempt_observed"])


if __name__ == "__main__":
    unittest.main()
