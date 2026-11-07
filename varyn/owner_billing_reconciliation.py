"""Owner-supplied offline billing correlation for VARYN live benchmarks.

STRICT limitations: a CSV uploaded by the owner is NOT an authenticated
invoice, official provider API response, cryptographic billing attestation,
nor a provider-side spend cap. Correlation works only when all ten successful
provider responses contained unique request IDs. Raw IDs, CSV, and file
paths are never persisted; only SHA-256 fingerprints and totals remain.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from io import StringIO
import csv
import json
import re
import sqlite3

from varyn.learning_kernel import LearningKernel
from varyn.local_evaluation_receipts import LocalEvaluationReceipts


class BillingReconciliationRejected(ValueError):
    pass


_HASH = re.compile(r"\A[0-9a-f]{64}\Z")
_RESPONSE_ID = re.compile(r"\A[A-Za-z0-9][A-Za-z0-9._:-]{2,159}\Z")
_COLUMNS = ("request_id", "charged_micro_usd")


class OwnerBillingReconciliation:
    """A trusted host only. NEVER expose to LLM tools or remote HTTP."""
    def __init__(self, kernel):
        if not isinstance(kernel, LearningKernel):
            raise TypeError("LearningKernel required")
        self.kernel = kernel
        self.receipts = LocalEvaluationReceipts(kernel)
        kernel.db.execute("""
            CREATE TABLE IF NOT EXISTS live_provider_response_fingerprints(
                session_id TEXT NOT NULL,
                response_id_sha256 TEXT NOT NULL,
                PRIMARY KEY(session_id,response_id_sha256)
            )
        """)
        kernel.db.execute("""
            CREATE TABLE IF NOT EXISTS owner_billing_reconciliation(
                session_id TEXT PRIMARY KEY,
                recorded_utc TEXT NOT NULL,
                source_type TEXT NOT NULL,
                matched_response_ids INTEGER NOT NULL,
                owner_reported_total_micro_usd INTEGER NOT NULL,
                estimated_total_micro_usd INTEGER NOT NULL,
                difference_micro_usd INTEGER NOT NULL,
                normalized_rows_sha256 TEXT NOT NULL,
                record_sha256 TEXT NOT NULL
            )
        """)

    def capture_provider_response(self, session_id, response_id_sha256):
        """Called solely by trusted runtime after an actual gateway response."""
        # A missing upstream ID can never be magically reconciled.
        if response_id_sha256 is None:
            return {"status": "provider_id_missing"}
        if (type(response_id_sha256) is not str
                or _HASH.fullmatch(response_id_sha256) is None):
            raise BillingReconciliationRejected("Malformed provider response ID digest")
        record = self.receipts.get(session_id)
        if record is None or record["status"] != "running_or_interrupted":
            raise BillingReconciliationRejected("Active local evaluation required")
        try:
            self.kernel.db.execute(
                "INSERT INTO live_provider_response_fingerprints "
                "(session_id,response_id_sha256) VALUES(?,?)",
                (session_id, response_id_sha256))
        except sqlite3.IntegrityError:
            raise BillingReconciliationRejected(
                "Duplicate provider response ID: session cannot be reconciled") from None
        return {"status": "captured"}

    def _validated_session(self, session_id):
        receipt = self.receipts.get(session_id)
        if receipt is None or receipt["status"] not in ("completed", "rejected"):
            raise BillingReconciliationRejected(
                "Only completed ten-response evaluations can be correlated")
        if receipt["local_receipt_digest_matches"] is not True:
            raise BillingReconciliationRejected("Evaluation receipt checksum mismatch")
        if (receipt["public_reads"] != 5
                or receipt["model_requests_attempted"] != 10
                or receipt["model_responses_succeeded"] != 10
                or receipt["model_requests_failed_or_uncertain"] != 0):
            raise BillingReconciliationRejected(
                "All ten model responses must have completed successfully")
        known = [row[0] for row in self.kernel.db.execute(
            "SELECT response_id_sha256 FROM live_provider_response_fingerprints "
            "WHERE session_id=?", (session_id,))]
        if len(known) != 10:
            raise BillingReconciliationRejected(
                "Ten distinct provider response IDs unavailable")
        return receipt, set(known)

    @staticmethod
    def _parse_csv(csv_text):
        if (type(csv_text) is not str or not 1 <= len(csv_text.encode("utf-8")) <= 16384
                or "\x00" in csv_text):
            raise BillingReconciliationRejected("Bounded UTF-8 CSV text required")
        try:
            rows = list(csv.reader(StringIO(csv_text, newline=""), strict=True))
        except csv.Error:
            raise BillingReconciliationRejected("Malformed CSV") from None
        if len(rows) != 11 or tuple(rows[0]) != _COLUMNS:
            raise BillingReconciliationRejected(
                "Exactly ten rows and request_id,charged_micro_usd header required")
        mapped = {}
        for row in rows[1:]:
            if len(row) != 2:
                raise BillingReconciliationRejected("Exactly two CSV columns required")
            label, cost = row
            if (type(label) is not str or _RESPONSE_ID.fullmatch(label) is None
                    or not re.fullmatch(r"(0|[1-9][0-9]{0,9})", cost)):
                raise BillingReconciliationRejected("Invalid ID or integer micro-USD")
            fingerprint = sha256(label.encode("utf-8")).hexdigest()
            if fingerprint in mapped:
                raise BillingReconciliationRejected("Duplicate CSV request ID")
            mapped[fingerprint] = int(cost)
        return mapped

    def preview(self, session_id, csv_text):
        receipt, expected = self._validated_session(session_id)
        mapping = self._parse_csv(csv_text)
        if set(mapping) != expected:
            return {
                "status": "id_mismatch",
                "matched_count": len(set(mapping) & expected),
                "expected_count": 10,
                "owner_reported_total_micro_usd": None,
                "provider_account_verified": False,
            }
        total = sum(mapping.values())
        estimate = receipt["estimated_micro_usd"]
        canonical = json.dumps(
            sorted(mapping.items()), separators=(",", ":"), ensure_ascii=True)
        return {
            "status": "ready_for_owner_review",
            "matched_count": 10,
            "expected_count": 10,
            "owner_reported_total_micro_usd": total,
            "estimated_total_micro_usd": estimate,
            "difference_micro_usd": total - estimate,
            "normalized_rows_sha256": sha256(canonical.encode()).hexdigest(),
            "provider_account_verified": False,
            "external_source_authentication": False,
            "owner_supplied_data_only": True,
        }

    def reconcile(self, session_id, csv_text, *, owner_approved=False):
        if owner_approved is not True:
            raise PermissionError("Separate owner confirmation required")
        info = self.preview(session_id, csv_text)
        if info["status"] != "ready_for_owner_review":
            raise BillingReconciliationRejected("Cannot match all ten provider IDs")
        now = datetime.now(timezone.utc).isoformat()
        record = {
            "session_id": session_id,
            "recorded_utc": now,
            "source_type": "owner_normalized_csv",
            "matched_response_ids": 10,
            "owner_reported_total_micro_usd": info["owner_reported_total_micro_usd"],
            "estimated_total_micro_usd": info["estimated_total_micro_usd"],
            "difference_micro_usd": info["difference_micro_usd"],
            "normalized_rows_sha256": info["normalized_rows_sha256"],
        }
        digest = sha256(json.dumps(
            record, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        try:
            self.kernel.db.execute(
                "INSERT INTO owner_billing_reconciliation "
                "(session_id,recorded_utc,source_type,matched_response_ids,"
                "owner_reported_total_micro_usd,estimated_total_micro_usd,"
                "difference_micro_usd,normalized_rows_sha256,record_sha256) "
                "VALUES(?,?,?,?,?,?,?,?,?)",
                (record["session_id"], record["recorded_utc"], record["source_type"],
                 record["matched_response_ids"], record["owner_reported_total_micro_usd"],
                 record["estimated_total_micro_usd"], record["difference_micro_usd"],
                 record["normalized_rows_sha256"], digest))
        except sqlite3.IntegrityError:
            raise BillingReconciliationRejected(
                "Owner-supplied reconciliation already recorded; no overwrite") from None
        return self.get(session_id)

    def get(self, session_id):
        row = self.kernel.db.execute(
            "SELECT * FROM owner_billing_reconciliation WHERE session_id=?",
            (session_id,)).fetchone()
        if row is None:
            return None
        record = dict(row)
        values = {key: record[key] for key in (
            "session_id", "recorded_utc", "source_type",
            "matched_response_ids", "owner_reported_total_micro_usd",
            "estimated_total_micro_usd", "difference_micro_usd",
            "normalized_rows_sha256")}
        expected = sha256(json.dumps(
            values, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        record.update({
            "local_checksum_matches": expected == record["record_sha256"],
            "provider_account_verified": False,
            "actual_provider_cost_independently_verified": False,
            "owner_supplied_data_only": True,
            "spend_hard_cap_enforced": False,
            "raw_response_ids_stored": False,
            "raw_csv_stored": False,
        })
        return record
