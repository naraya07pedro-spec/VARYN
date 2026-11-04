"""Checkpoint 17A offline official-app feasibility and sync-planning tests.

All data here is synthetic. No customer data, network, provider account,
browser automation, credentials, or actual app-history operations.
"""
import io
import json
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from varyn.official_sync import (
    SyncContractError,
    SyncMarker,
    official_app_capability,
    plan_synthetic_reconciliation,
    main,
)


def item(record_id="item-1", revision=1, content="a", deleted=False):
    digest = "" if deleted else content * 64
    return SyncMarker(record_id, revision, digest, deleted)


def plan(base=None, local=None, official=None):
    return plan_synthetic_reconciliation(
        {} if base is None else base,
        {} if local is None else local,
        {} if official is None else official,
        synthetic_fixture=True,
    )


class OfficialAppCapabilityTests(unittest.TestCase):
    def test_all_three_official_apps_fail_closed(self):
        for provider in ("chatgpt", "claude", "gemini"):
            with self.subTest(provider=provider):
                result = official_app_capability(provider)
                self.assertEqual(result["provider"], provider)
                self.assertFalse(result["official_app_read_verified"])
                self.assertFalse(result["official_app_write_verified"])
                self.assertFalse(result["automatic_two_way_sync_verified"])
                self.assertFalse(result["can_dispatch"])
                self.assertTrue(result["export_documentation"].startswith("https://"))

    def test_unsupported_app_or_types_rejected(self):
        for provider in (None, False, 42, "unknown", "ChatGPT", "chatgpt\n"):
            with self.subTest(provider=provider), self.assertRaises(SyncContractError):
                official_app_capability(provider)

    def test_cli_is_offline_capability_diagnostic_only(self):
        stream = io.StringIO()
        with patch("sys.argv", ["varyn.official_sync", "--provider", "claude"]), redirect_stdout(stream):
            self.assertEqual(main(), 0)
        result = json.loads(stream.getvalue())
        self.assertFalse(result["can_dispatch"])
        self.assertEqual(result["provider"], "claude")

    def test_unparameterized_cli_shows_three_blocked_providers(self):
        stream = io.StringIO()
        with redirect_stdout(stream):
            self.assertEqual(main([]), 0)
        result = json.loads(stream.getvalue())
        self.assertEqual(len(result["providers"]), 3)
        self.assertTrue(all(not x["can_dispatch"] for x in result["providers"]))


class SyntheticReconciliationTests(unittest.TestCase):
    def test_explicit_fixture_consent_required(self):
        with self.assertRaises(PermissionError):
            plan_synthetic_reconciliation({}, {}, {})
        with self.assertRaises(PermissionError):
            plan_synthetic_reconciliation({}, {}, {}, synthetic_fixture=1)

    def test_empty_case_is_still_not_dispatchable(self):
        result = plan()
        self.assertEqual(result["decisions"], [])
        self.assertFalse(result["can_dispatch"])
        self.assertFalse(result["automatic_sync_available"])

    def test_local_only_creation_is_official_preview_not_write(self):
        result = plan(local={"item-1": item()})
        self.assertEqual(result["decisions"][0]["outcome"], "official_create_preview")
        self.assertFalse(result["decisions"][0]["can_dispatch"])

    def test_official_only_creation_is_local_preview_not_import(self):
        result = plan(official={"item-1": item()})
        self.assertEqual(result["decisions"][0]["outcome"], "local_import_preview")
        self.assertTrue(result["decisions"][0]["needs_human_review"])

    def test_changed_local_requires_official_update_review(self):
        old = item()
        new = item(revision=2, content="b")
        result = plan(base={old.record_id: old},
                      local={old.record_id: new},
                      official={old.record_id: old})
        decision = result["decisions"][0]
        self.assertEqual(decision["outcome"], "official_update_preview")
        self.assertEqual(decision["base_revision"], 1)
        self.assertEqual(decision["local_revision"], 2)
        self.assertEqual(decision["official_revision"], 1)

    def test_changed_official_requires_local_import_review(self):
        old = item()
        new = item(revision=2, content="b")
        result = plan(base={old.record_id: old},
                      local={old.record_id: old},
                      official={old.record_id: new})
        self.assertEqual(result["decisions"][0]["outcome"], "local_import_preview")

    def test_deletion_never_inferred_from_missing_record(self):
        old = item()
        result = plan(base={old.record_id: old},
                      local={},
                      official={old.record_id: old})
        self.assertEqual(result["decisions"][0]["outcome"], "incomplete_snapshot_review")

    def test_explicit_local_tombstone_review_not_delete(self):
        old = item()
        tombstone = item(revision=2, deleted=True)
        result = plan(base={old.record_id: old},
                      local={old.record_id: tombstone},
                      official={old.record_id: old})
        self.assertEqual(result["decisions"][0]["outcome"], "official_delete_review")
        self.assertFalse(result["decisions"][0]["can_dispatch"])

    def test_explicit_official_tombstone_review_not_delete(self):
        old = item()
        tombstone = item(revision=2, deleted=True)
        result = plan(base={old.record_id: old},
                      local={old.record_id: old},
                      official={old.record_id: tombstone})
        self.assertEqual(result["decisions"][0]["outcome"], "local_delete_review")

    def test_divergent_edits_blocked_not_last_write_wins(self):
        old = item()
        left = item(revision=2, content="b")
        right = item(revision=2, content="c")
        result = plan(base={old.record_id: old},
                      local={old.record_id: left},
                      official={old.record_id: right})
        self.assertEqual(result["decisions"][0]["outcome"],
                         "divergent_edits_conflict_review")

    def test_identical_edits_avoid_echo_loop(self):
        old = item()
        new = item(revision=2, content="b")
        result = plan(base={old.record_id: old},
                      local={old.record_id: new},
                      official={old.record_id: new})
        self.assertEqual(result["decisions"][0]["outcome"], "already_equal")
        self.assertFalse(result["decisions"][0]["needs_human_review"])

    def test_concurrent_creation_conflict(self):
        result = plan(local={"item-1": item(content="a")},
                      official={"item-1": item(content="b")})
        self.assertEqual(result["decisions"][0]["outcome"],
                         "concurrent_creation_conflict_review")

    def test_revision_regression_blocks_preview(self):
        old = item(revision=2)
        regressed = item(revision=1, content="b")
        result = plan(base={old.record_id: old},
                      local={old.record_id: regressed},
                      official={old.record_id: old})
        self.assertEqual(result["decisions"][0]["outcome"],
                         "revision_regressed_review")

    def test_changed_body_without_revision_increment_blocks_preview(self):
        old = item()
        altered = item(content="b")
        result = plan(base={old.record_id: old},
                      local={old.record_id: altered},
                      official={old.record_id: old})
        self.assertEqual(result["decisions"][0]["outcome"],
                         "revision_conflict_review")

    def test_order_is_deterministic_and_no_digest_returned(self):
        result = plan(local={"z": item("z"), "a": item("a")})
        self.assertEqual([x["record_id"] for x in result["decisions"]], ["a", "z"])
        self.assertNotIn("digest", json.dumps(result))
        self.assertNotIn("text", json.dumps(result))

    def test_oversized_combined_snapshot_rejected(self):
        local = {f"item{i}": item(f"item{i}") for i in range(60)}
        official = {f"other{i}": item(f"other{i}") for i in range(60)}
        with self.assertRaises(SyncContractError):
            plan(local=local, official=official)

    def test_invalid_snapshot_and_mismatched_keys_rejected(self):
        for bad in ([], {"different": item()}, {"item-1": None}):
            with self.subTest(snapshot=repr(bad)), self.assertRaises(SyncContractError):
                plan(local=bad)

    def test_record_schema_is_exact(self):
        cases = [
            ("../path", 1, "a" * 64, False),
            ("id", True, "a" * 64, False),
            ("id", 0, "a" * 64, False),
            ("id", 10**16, "a" * 64, False),
            ("id", 1, "not-sha256", False),
            ("id", 1, "a" * 64, True),
            ("id", 1, "", False),
            ("id", 1, "", 1),
        ]
        for args in cases:
            with self.subTest(args=args), self.assertRaises(SyncContractError):
                SyncMarker(*args)

    def test_no_mutation_of_supplied_snapshots(self):
        old = item()
        base = {"item-1": old}
        local = {"item-1": old}
        official = {"item-1": item(revision=2, content="b")}
        before = (dict(base), dict(local), dict(official))
        plan(base=base, local=local, official=official)
        self.assertEqual((base, local, official), before)


if __name__ == "__main__":
    unittest.main()
